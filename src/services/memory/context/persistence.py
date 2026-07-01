"""Database loading and persistence logic."""
import logging
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.models.session_model import SessionModel
from src.infrastructure.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from src.services.memory.context.models import SessionContext

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Manages database persistence for session context."""

    def __init__(self, max_recent: int = 10):
        self.max_recent = max_recent

    async def load_from_db(
        self,
        session_id: str,
        user_id: str
    ) -> Optional["SessionContext"]:
        """Load session context from database with tenant isolation."""
        from src.services.memory.context.models import SessionContext

        context = SessionContext(
            session_id=session_id,
            user_id=user_id
        )

        async with AsyncSessionLocal() as db:
            # Load session to get tenant_id for isolation
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return None
            tenant_id = session.tenant_id

            # Load recent messages with tenant filter
            result = await db.execute(
                select(MessageModel)
                .where(
                    MessageModel.session_id == session_id,
                    MessageModel.tenant_id == tenant_id
                )
                .order_by(MessageModel.sequence.desc())
                .limit(self.max_recent * 2)  # Load more for processing
            )
            messages = result.scalars().all()

            if not messages:
                return None

            # Reverse to chronological order
            messages = list(reversed(messages))

            for msg in messages:
                context.last_sequence = max(context.last_sequence, msg.sequence)
                context.recent_messages.append({
                    "sequence": msg.sequence,
                    "role": msg.role,
                    "content": msg.content,
                    "task_id": msg.task_id,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                })

            context.total_messages = context.last_sequence

        return context

    async def persist_to_db(self, context: "SessionContext") -> None:
        """Persist session context to database with tenant isolation."""
        async with AsyncSessionLocal() as db:
            # Resolve tenant_id from session
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == context.session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                logger.error(f"[Persistence] Session {context.session_id} not found — cannot persist messages")
                return
            tenant_id = session.tenant_id

            # Persist recent messages
            for msg in context.recent_messages:
                # Check if already exists (within same tenant+session+sequence)
                existing = await db.execute(
                    select(MessageModel).where(
                        MessageModel.session_id == context.session_id,
                        MessageModel.sequence == msg["sequence"],
                        MessageModel.tenant_id == tenant_id
                    )
                )

                if existing.scalar_one_or_none():
                    continue

                # Create new message with tenant_id
                new_msg = MessageModel(
                    session_id=context.session_id,
                    tenant_id=tenant_id,
                    role=msg["role"],
                    content=msg["content"],
                    sequence=msg["sequence"],
                    task_id=msg.get("task_id"),
                )
                db.add(new_msg)

            await db.commit()

    async def clear_from_db(self, session_id: str) -> None:
        """Clear all messages for a session from database."""
        from sqlalchemy import delete

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(MessageModel).where(MessageModel.session_id == session_id)
            )
            await db.commit()

    async def infer_user_id(self, session_id: str) -> Optional[str]:
        """Try to infer user_id from session."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                return session.user_id
        return None
