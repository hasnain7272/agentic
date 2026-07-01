"""
Session Context Management Package

Provides efficient persistence of session context with:
- Incremental storage (only changed messages)
- Smart summarization for long sessions
- LRU caching for active sessions
- Vector embeddings for semantic search
"""

from src.services.memory.context.cache import ContextCache
from src.services.memory.context.checkpoint import CheckpointManager
from src.services.memory.context.manager import ContextPersistenceManager
from src.services.memory.context.message_handler import MessageHandler
from src.services.memory.context.models import ContextWindow, SessionContext

__all__ = [
    "ContextWindow",
    "SessionContext",
    "ContextCache",
    "CheckpointManager",
    "MessageHandler",
    "ContextPersistenceManager",
]

# Global instance
_context_manager: ContextPersistenceManager | None = None


async def get_context_manager() -> ContextPersistenceManager:
    """Get or create the global context manager."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextPersistenceManager()
        await _context_manager.start()
    return _context_manager
