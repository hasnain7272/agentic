"""
Intelligent Resource Multiplexer for Agentic Governance.

Handles tool-level resource locking and queuing to prevent 
state corruption when multiple users request the same stateful tool
(e.g., Blender, Git checkout).
"""
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ResourceMultiplexer:
    """
    Manages access to stateful tools using asyncio Locks.
    Ensures that consecutive requests for a locked resource queue up
    intelligently instead of crashing the tool instance.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._locks: Dict[str, asyncio.Lock] = {}
        return cls._instance

    def _get_lock(self, resource_name: str) -> asyncio.Lock:
        if resource_name not in self._locks:
            self._locks[resource_name] = asyncio.Lock()
        return self._locks[resource_name]

    async def acquire(self, resource_name: str):
        """Acquires a lock for a specific stateful resource."""
        lock = self._get_lock(resource_name)
        if lock.locked():
            logger.info(f"[Multiplexer] Resource '{resource_name}' is currently in use. Queuing request...")
        await lock.acquire()
        logger.debug(f"[Multiplexer] Acquired lock for '{resource_name}'")

    def release(self, resource_name: str):
        """Releases the lock for a specific stateful resource."""
        lock = self._get_lock(resource_name)
        if lock.locked():
            lock.release()
            logger.debug(f"[Multiplexer] Released lock for '{resource_name}'")

# Global singleton
resource_multiplexer = ResourceMultiplexer()
