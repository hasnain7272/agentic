"""LRU cache management for active sessions."""
from datetime import datetime
from typing import Optional

from cachetools import LRUCache

from src.services.memory.context.models import SessionContext


class ContextCache:
    """LRU cache for active session contexts."""

    def __init__(self, maxsize: int = 1000):
        self._cache: LRUCache[str, SessionContext] = LRUCache(maxsize=maxsize)

    def get(self, session_id: str) -> Optional[SessionContext]:
        """Get context from cache and update access time."""
        context = self._cache.get(session_id)
        if context:
            context.last_accessed = datetime.utcnow()
        return context

    def put(self, session_id: str, context: SessionContext) -> None:
        """Store context in cache."""
        self._cache[session_id] = context

    def remove(self, session_id: str) -> bool:
        """Remove context from cache."""
        if session_id in self._cache:
            del self._cache[session_id]
            return True
        return False

    def contains(self, session_id: str) -> bool:
        """Check if session is in cache."""
        return session_id in self._cache

    def get_all_items(self):
        """Get all cached items for iteration."""
        return self._cache.items()

    def clear(self) -> None:
        """Clear all cached contexts."""
        self._cache.clear()
