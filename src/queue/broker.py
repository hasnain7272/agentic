"""
Queue Broker - Redis Streams + Local Fallback

Provides unified interface for message queue operations.
Supports Redis Streams (production) and in-memory (development).
"""
import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class QueueEvent:
    """Standard event structure for queue messages."""
    event_type: str
    payload: Dict[str, Any]
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    tenant_id: Optional[str] = None


class QueueBroker(ABC):
    """Abstract queue broker interface."""
    
    @abstractmethod
    async def publish(self, stream: str, event: QueueEvent) -> str:
        """Publish event to stream, return message ID."""
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        stream: str, 
        group: str, 
        consumer: str,
        handler: Callable[[QueueEvent], Any],
        block_ms: int = 5000,
    ) -> None:
        """Subscribe to stream with consumer group."""
        pass
    
    @abstractmethod
    async def read_stream(
        self, 
        stream: str, 
        count: int = 10, 
        block_ms: int = 5000,
    ) -> List[QueueEvent]:
        """Read events from stream."""
        pass
    
    @abstractmethod
    async def acknowledge(self, stream: str, message_id: str) -> bool:
        """Acknowledge message processing."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return broker health status."""
        pass


class RedisStreamsBroker(QueueBroker):
    """Redis Streams implementation with consumer groups."""
    
    def __init__(self, redis_url: str, max_connections: int = 50):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._consumers: Dict[str, asyncio.Task] = {}
    
    async def connect(self) -> None:
        """Establish Redis connection pool."""
        self._pool = redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=self.max_connections,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        await self._client.ping()
        logger.info("Redis Streams broker connected")
    
    async def close(self) -> None:
        """Close connections and stop consumers."""
        for task in self._consumers.values():
            task.cancel()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis Streams broker closed")
    
    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Broker not connected. Call connect() first.")
        return self._client
    
    async def publish(self, stream: str, event: QueueEvent) -> str:
        """Publish event to Redis stream."""
        data = {
            "event_type": event.event_type,
            "payload": json.dumps(event.payload),
            "trace_id": event.trace_id,
            "timestamp": str(event.timestamp),
        }
        if event.tenant_id:
            data["tenant_id"] = event.tenant_id
        
        msg_id = await self.client.xadd(stream, data, maxlen=10000)
        return msg_id
    
    async def subscribe(
        self,
        stream: str,
        group: str,
        consumer: str,
        handler: Callable[[QueueEvent], Any],
        block_ms: int = 5000,
    ) -> None:
        """Subscribe with consumer group for exactly-once processing."""
        # Create consumer group if not exists
        try:
            await self.client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        
        consumer_key = f"{stream}:{group}:{consumer}"
        
        async def consumer_loop():
            logger.info(f"Starting consumer {consumer_key} on {stream}")
            while True:
                try:
                    messages = await self.client.xreadgroup(
                        group, consumer, {stream: ">"}, count=10, block=block_ms
                    )
                    
                    for stream_name, entries in messages:
                        for msg_id, data in entries:
                            try:
                                event = QueueEvent(
                                    event_type=data["event_type"],
                                    payload=json.loads(data["payload"]),
                                    trace_id=data["trace_id"],
                                    timestamp=float(data["timestamp"]),
                                    tenant_id=data.get("tenant_id"),
                                )
                                await handler(event)
                                await self.client.xack(stream_name, group, msg_id)
                            except Exception as e:
                                logger.error(f"Error processing {msg_id}: {e}")
                                # Don't ack - will be redelivered
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Consumer error: {e}")
                    await asyncio.sleep(1)
        
        task = asyncio.create_task(consumer_loop())
        self._consumers[consumer_key] = task
    
    async def read_stream(
        self, 
        stream: str, 
        count: int = 10, 
        block_ms: int = 5000,
    ) -> List[QueueEvent]:
        """Read events without consumer group (for debugging)."""
        messages = await self.client.xread({stream: "0"}, count=count, block=block_ms)
        events = []
        for stream_name, entries in messages:
            for msg_id, data in entries:
                events.append(QueueEvent(
                    event_type=data["event_type"],
                    payload=json.loads(data["payload"]),
                    trace_id=data["trace_id"],
                    timestamp=float(data["timestamp"]),
                    tenant_id=data.get("tenant_id"),
                ))
        return events
    
    async def acknowledge(self, stream: str, message_id: str) -> bool:
        """Acknowledge message (for non-group reads)."""
        # For streams without group, we use XDEL
        result = await self.client.xdel(stream, message_id)
        return result > 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        try:
            await self.client.ping()
            info = await self.client.info("memory")
            return {
                "status": "healthy",
                "type": "redis_streams",
                "memory_used_mb": info.get("used_memory", 0) / 1024 / 1024,
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class LocalQueueBroker(QueueBroker):
    """In-memory queue for development/testing."""
    
    def __init__(self):
        self._streams: Dict[str, List[QueueEvent]] = defaultdict(list)
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def publish(self, stream: str, event: QueueEvent) -> str:
        async with self._lock:
            msg_id = f"{time.time()}-{uuid.uuid4().hex[:8]}"
            self._streams[stream].append(event)
            # Notify subscribers
            for queue in self._subscribers.get(stream, []):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass
            return msg_id
    
    async def subscribe(
        self,
        stream: str,
        group: str,
        consumer: str,
        handler: Callable[[QueueEvent], Any],
        block_ms: int = 5000,
    ) -> None:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers[stream].append(queue)
        
        async def consumer_loop():
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=block_ms / 1000)
                    await handler(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Local consumer error: {e}")
        
        asyncio.create_task(consumer_loop())
    
    async def read_stream(
        self, 
        stream: str, 
        count: int = 10, 
        block_ms: int = 5000,
    ) -> List[QueueEvent]:
        async with self._lock:
            return self._streams.get(stream, [])[-count:]
    
    async def acknowledge(self, stream: str, message_id: str) -> bool:
        # No-op for local
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "type": "local",
            "streams": len(self._streams),
            "total_messages": sum(len(s) for s in self._streams.values()),
        }


# Global broker instance
_broker: Optional[QueueBroker] = None


async def get_queue_broker() -> QueueBroker:
    """Get or create the global queue broker."""
    global _broker
    if _broker is None:
        settings = get_settings()
        if settings.queue_backend == "redis":
            _broker = RedisStreamsBroker(
                settings.redis_url,
                settings.redis_max_connections,
            )
            await _broker.connect()
        else:
            _broker = LocalQueueBroker()
    return _broker


async def close_queue_broker() -> None:
    """Close the global queue broker."""
    global _broker
    if _broker:
        if hasattr(_broker, "close"):
            await _broker.close()
        _broker = None