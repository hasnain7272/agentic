"""
Queue Consumer - Background Event Processor

Manages background consumers for processing queue events.
Handles graceful shutdown, retries, and error tracking.
"""
import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.queue.broker import QueueBroker, QueueEvent, get_queue_broker, close_queue_broker
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ConsumerConfig:
    """Configuration for a consumer."""
    stream: str
    group: str
    consumer: str
    handler: Callable[[QueueEvent], Any]
    block_ms: int = 5000
    max_retries: int = 3
    retry_delay_ms: int = 1000


class ConsumerManager:
    """Manages multiple queue consumers with lifecycle control."""
    
    def __init__(self):
        self._consumers: Dict[str, ConsumerConfig] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        self._broker: Optional[QueueBroker] = None
    
    def register_consumer(self, config: ConsumerConfig) -> None:
        """Register a consumer configuration."""
        key = f"{config.stream}:{config.group}:{config.consumer}"
        self._consumers[key] = config
        logger.info(f"Registered consumer: {key}")
    
    async def start_all(self) -> None:
        """Start all registered consumers."""
        self._broker = await get_queue_broker()
        self._shutdown_event.clear()
        
        for key, config in self._consumers.items():
            task = asyncio.create_task(self._run_consumer(key, config))
            self._tasks[key] = task
            logger.info(f"Started consumer: {key}")
    
    async def _run_consumer(self, key: str, config: ConsumerConfig) -> None:
        """Run a single consumer with retry logic."""
        while not self._shutdown_event.is_set():
            try:
                await self._broker.subscribe(
                    stream=config.stream,
                    group=config.group,
                    consumer=config.consumer,
                    handler=self._wrap_handler(config.handler),
                    block_ms=config.block_ms,
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer {key} error: {e}")
                if not self._shutdown_event.is_set():
                    await asyncio.sleep(config.retry_delay_ms / 1000)
    
    def _wrap_handler(self, handler: Callable[[QueueEvent], Any]) -> Callable[[QueueEvent], Any]:
        """Wrap handler with error tracking."""
        async def wrapped(event: QueueEvent) -> Any:
            try:
                return await handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.event_type}: {e}")
                raise
        return wrapped
    
    async def stop_all(self) -> None:
        """Stop all consumers gracefully."""
        logger.info("Stopping all consumers...")
        self._shutdown_event.set()
        
        for key, task in self._tasks.items():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"Consumer {key} shutdown timeout")
            except Exception as e:
                logger.error(f"Consumer {key} shutdown error: {e}")
        
        self._tasks.clear()
        await close_queue_broker()
        logger.info("All consumers stopped")
    
    @asynccontextmanager
    async def lifespan(self):
        """Context manager for consumer lifecycle."""
        await self.start_all()
        try:
            yield self
        finally:
            await self.stop_all()


# Global consumer manager
consumer_manager = ConsumerManager()


def register_task_handlers(
    handle_task_created: Callable,
    handle_task_needs_approval: Callable,
    handle_tool_execution: Callable,
) -> None:
    """Register standard task processing handlers."""
    
    consumer_manager.register_consumer(ConsumerConfig(
        stream="tasks",
        group="task-workers",
        consumer=f"worker-{asyncio.current_task().get_name() if asyncio.current_task() else 'main'}",
        handler=handle_task_created,
    ))
    
    consumer_manager.register_consumer(ConsumerConfig(
        stream="approvals",
        group="approval-handlers",
        consumer=f"approval-{asyncio.current_task().get_name() if asyncio.current_task() else 'main'}",
        handler=handle_task_needs_approval,
    ))
    
    consumer_manager.register_consumer(ConsumerConfig(
        stream="tool_executions",
        group="tool-workers",
        consumer=f"tool-{asyncio.current_task().get_name() if asyncio.current_task() else 'main'}",
        handler=handle_tool_execution,
    ))


async def setup_signal_handlers(manager: ConsumerManager) -> None:
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()
    
    def signal_handler(sig):
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        asyncio.create_task(manager.stop_all())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))