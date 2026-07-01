"""Main ContextPersistenceManager implementation."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.services.memory.context.builder import ContextBuilder
from src.services.memory.context.cache import ContextCache
from src.services.memory.context.checkpoint import CheckpointManager
from src.services.memory.context.message_handler import MessageHandler
from src.services.memory.context.models import SessionContext
from src.services.memory.context.persistence import PersistenceManager
from src.services.memory.context.windows import WindowManager

logger = logging.getLogger(__name__)


class ContextPersistenceManager:
    """
    Manages session context with:
    - Incremental persistence (only new messages)
    - Automatic summarization
    - LRU cache for active sessions
    - Background checkpointing
    """

    # Configuration
    WINDOW_SIZE = 20
    MAX_RECENT = 10
    SUMMARY_THRESHOLD = 100
    CHECKPOINT_INTERVAL = 60
    CACHE_SIZE = 1000

    def __init__(self):
        self._cache = ContextCache(maxsize=self.CACHE_SIZE)
        self._persistence = PersistenceManager(max_recent=self.MAX_RECENT)
        self._checkpoint = CheckpointManager(
            self._persistence,
            checkpoint_interval=self.CHECKPOINT_INTERVAL
        )
        self._windows = WindowManager(window_size=self.WINDOW_SIZE)
        self._builder = ContextBuilder(
            max_recent=self.MAX_RECENT,
            max_windows=3
        )
        self._handler = MessageHandler(
            max_recent=self.MAX_RECENT,
            summary_threshold=self.SUMMARY_THRESHOLD,
            windows=self._windows,
            checkpoint=self._checkpoint
        )
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start background checkpointing."""
        await self._checkpoint.start()
        logger.info("[ContextManager] Started")

    async def stop(self) -> None:
        """Stop and flush all pending changes."""
        await self._checkpoint.stop()
        await self._flush_all()
        logger.info("[ContextManager] Stopped")

    async def get_or_create_context(
        self, session_id: str, user_id: str
    ) -> SessionContext:
        """Get existing context or create new."""
        context = self._cache.get(session_id)
        if context:
            return context

        context = await self._persistence.load_from_db(session_id, user_id)
        if context:
            self._cache.put(session_id, context)
            return context

        context = SessionContext(session_id=session_id, user_id=user_id)
        self._cache.put(session_id, context)
        return context

    async def _get_from_cache_or_db(
        self, session_id: str
    ) -> Optional[SessionContext]:
        """Get context from cache or load from DB."""
        context = self._cache.get(session_id)
        if context:
            return context

        user_id = await self._persistence.infer_user_id(session_id)
        if user_id:
            return await self._persistence.load_from_db(session_id, user_id)
        return None

    async def add_message(
        self, session_id: str, role: str, content: str,
        task_id: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_results: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Add message to session context."""
        async with self._lock:
            context = await self._get_from_cache_or_db(session_id)
            if not context:
                logger.warning(f"[ContextManager] No context for {session_id}")
                return {"error": "Session not found"}
            return await self._handler.add_message(
                context, role, content, task_id, tool_calls, tool_results
            )

    async def get_context_for_llm(
        self, session_id: str, max_tokens: int = 8000
    ) -> List[Dict[str, str]]:
        """Get context formatted for LLM consumption."""
        context = await self._get_from_cache_or_db(session_id)
        return self._builder.build_for_llm(context, max_tokens) if context else []

    async def get_context_for_ui(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get context for UI display."""
        context = await self._get_from_cache_or_db(session_id)
        return self._builder.build_for_ui(context, limit) if context else []

    async def search_context(
        self, session_id: str, query: str
    ) -> List[Dict[str, Any]]:
        """Search within session context."""
        context = await self._get_from_cache_or_db(session_id)
        return self._builder.search(context, query) if context else []

    async def get_file_context(
        self, session_id: str, filepath: str
    ) -> List[Dict[str, Any]]:
        """Get all messages referencing a specific file."""
        context = await self._get_from_cache_or_db(session_id)
        return self._builder.get_file_context(context, filepath) if context else []

    async def clear_context(self, session_id: str) -> bool:
        """Clear all context for a session."""
        async with self._lock:
            self._cache.remove(session_id)
            self._checkpoint.clear_dirty(session_id)
            await self._persistence.clear_from_db(session_id)
        return True

    async def _flush_all(self) -> None:
        """Flush all cached sessions."""
        async with self._lock:
            for _, context in self._cache.get_all_items():
                if context.is_dirty:
                    await self._persistence.persist_to_db(context)
                    context.is_dirty = False
