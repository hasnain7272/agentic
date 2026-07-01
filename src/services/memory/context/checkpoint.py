"""Background checkpointing for dirty sessions."""
import asyncio
import logging
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from src.services.memory.context.models import SessionContext
    from src.services.memory.context.persistence import PersistenceManager

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages background checkpointing of dirty sessions."""

    def __init__(
        self,
        persistence: "PersistenceManager",
        checkpoint_interval: int = 60
    ):
        self.persistence = persistence
        self.checkpoint_interval = checkpoint_interval
        self._dirty_sessions: Set[str] = set()
        self._lock = asyncio.Lock()
        self._checkpoint_task: asyncio.Task | None = None
        self._running = False

    def mark_dirty(self, session_id: str) -> None:
        """Mark a session as needing persistence."""
        self._dirty_sessions.add(session_id)

    def is_dirty(self, session_id: str) -> bool:
        """Check if a session is marked dirty."""
        return session_id in self._dirty_sessions

    def clear_dirty(self, session_id: str) -> None:
        """Remove a session from the dirty set."""
        self._dirty_sessions.discard(session_id)

    async def start(self) -> None:
        """Start background checkpointing."""
        self._running = True
        self._checkpoint_task = asyncio.create_task(self._checkpoint_loop())
        logger.info("[CheckpointManager] Started")

    async def stop(self) -> None:
        """Stop checkpointing and flush all pending changes."""
        self._running = False
        if self._checkpoint_task:
            self._checkpoint_task.cancel()
            try:
                await self._checkpoint_task
            except asyncio.CancelledError:
                pass

    async def _checkpoint_loop(self) -> None:
        """Background loop to persist dirty sessions."""
        while self._running:
            try:
                await asyncio.sleep(self.checkpoint_interval)
                await self.flush_dirty_sessions()
            except Exception as e:
                logger.error(f"[CheckpointManager] Checkpoint error: {e}")

    async def flush_dirty_sessions(
        self,
        get_context: callable = None
    ) -> None:
        """Persist all dirty sessions to database."""
        if not self._dirty_sessions:
            return

        sessions_to_flush = list(self._dirty_sessions)
        self._dirty_sessions.clear()

        async with self._lock:
            for session_id in sessions_to_flush:
                if get_context is None:
                    continue

                context = get_context(session_id)
                if context is None or not context.is_dirty:
                    continue

                await self.persistence.persist_to_db(context)
                context.is_dirty = False

        logger.debug(f"[CheckpointManager] Flushed {len(sessions_to_flush)} sessions")

    async def flush_all(
        self,
        get_all_contexts: callable = None
    ) -> None:
        """Flush all cached sessions."""
        if get_all_contexts is None:
            return

        async with self._lock:
            for session_id, context in get_all_contexts():
                if context.is_dirty:
                    await self.persistence.persist_to_db(context)
                    context.is_dirty = False
