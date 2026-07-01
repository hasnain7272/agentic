"""BrainWorker Main Class."""
import logging
from typing import Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.infrastructure.observability.tracing import traced, milestones
from src.infrastructure.db.models.task_model import TaskModel
from src.infrastructure.db.models.session_model import SessionModel
from src.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.services.memory.context_builder import persist_message, build_llm_context
from src.tools.registry import get_all_tool_schemas

from .config_loader import load_session_llm_config
from .llm_caller import call_llm_and_stream

logger = logging.getLogger(__name__)

class BrainWorker:
    def __init__(self):
        self._circuit_breaker = CircuitBreaker("llm-api", CircuitBreakerConfig(failure_threshold=5, success_threshold=2, timeout=30.0))

    @traced("brain.process_task_event")
    async def process_task_event(self, event: Dict[str, Any], db: AsyncSession):
        task_id = event.get("task_id")
        session_id = event.get("session_id")
        description = event.get("description", "")
        trace_id = event.get("trace_id")
        tenant_id = event.get("tenant_id")
        broker = await get_streams_broker()

        milestones.milestone("Thinking Start", {"task_id": task_id, "session_id": session_id})
        logger.info(f"[Brain] {task_id} - Reasoning step initiated")

        stmt = select(SessionModel).where(SessionModel.id == session_id)
        if tenant_id:
            stmt = stmt.where(SessionModel.tenant_id == tenant_id)
        session_result = await db.execute(stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            logger.error(f"[Brain] Session {session_id} not found")
            await persist_message(db, session_id, "system", "⚠️ Session not found.", task_id=task_id)
            await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
            await db.commit()
            return
        
        tenant_id = session.tenant_id

        task_conds = [TaskModel.id == task_id, TaskModel.session_id == session_id]
        if tenant_id:
            task_conds.append(TaskModel.tenant_id == tenant_id)
        task_result = await db.execute(select(TaskModel).where(and_(*task_conds)))
        task = task_result.scalar_one_or_none()

        if task:
            task.iteration_count += 1
            if task.iteration_count > 50:
                out = "⚠️ Max iterations reached."
                await persist_message(db, session_id, "assistant", out, task_id=task_id)
                await broker.publish(f"task_log:{task_id}", out.encode('utf-8'))
                await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
                await db.commit()
                return
            if task.iteration_count == 40:
                await persist_message(db, session_id, "system", "[SYSTEM] Wrap up task.", task_id=task_id)

        if description.strip():
            await persist_message(db, session_id, "user", description, task_id=task_id)

        await broker.publish(f"task_log:{task_id}", {"status": "thinking", "message": "Analyzing..."})

        messages = await build_llm_context(db, session_id, task_id, session=session)
        tools = get_all_tool_schemas()
        llm_config = await load_session_llm_config(db, session_id, session=session)

        from src.services.billing.usage_tracker import usage_tracker, QuotaExceededError
        try:
            await usage_tracker.check_quota(db, tenant_id)
        except QuotaExceededError as e:
            await persist_message(db, session_id, "system", str(e), task_id=task_id)
            await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
            await db.commit()
            return

        await call_llm_and_stream(db, session_id, tenant_id, task_id, trace_id, messages, tools, llm_config, self._circuit_breaker)
