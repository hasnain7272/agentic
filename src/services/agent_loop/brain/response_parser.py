"""Response parsing for brain."""
import json
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.services.memory.context_builder import persist_message
from src.infrastructure.observability.tracing import milestones

logger = logging.getLogger(__name__)

async def process_response(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    task_id: str,
    trace_id: str,
    collected_content: List[str],
    tool_calls_dict: Dict[int, Any]
) -> None:
    broker = await get_streams_broker()
    full_content = "".join(collected_content)

    if full_content:
        await broker.publish(f"task_log:{task_id}", b"\r\n")
        try:
            from src.services.memory.semantic_memory import semantic_memory
            await semantic_memory.index_event(
                session_id=session_id, tenant_id=tenant_id, event_type="thought", content=full_content, task_id=task_id
            )
        except Exception as mem_err:
            logger.error(f"[Brain] Failed to index thought: {mem_err}")

    if tool_calls_dict:
        combined_calls = list(tool_calls_dict.values())
        await persist_message(db, session_id, "assistant", full_content, task_id=task_id, tool_calls=combined_calls)

        tools_payload = []
        for tc in combined_calls:
            await broker.publish(f"task_log:{task_id}", {
                "event": "tool_start", "name": tc['function']['name'], "args": tc['function']['arguments']
            })
            milestones.milestone("Action Dispatched", {"tool": tc['function']['name']})
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                error_msg = f"Tool call arguments were invalid JSON for {tc['function']['name']}: {exc}"
                logger.warning("[Brain] %s", error_msg)
                await persist_message(db, session_id, "assistant", error_msg, task_id=task_id)
                await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
                await db.commit()
                return
            tools_payload.append({"id": tc["id"], "name": tc["function"]["name"], "args": args})
            logger.info(f"[Brain] -> EXECUTE: {tc['function']['name']}")

        await broker.publish("execution_queue", {
            "event_type": "EXECUTE_TOOL_BATCH",
            "task_id": task_id,
            "session_id": session_id,
            "tools": tools_payload,
            "tenant_id": tenant_id,
        }, trace_id=trace_id)
    else:
        await persist_message(db, session_id, "assistant", full_content, task_id=task_id)
        await broker.publish("task_resolved", {
            "event_type": "TASK_RESOLVED", "task_id": task_id, "session_id": session_id, "output": full_content,
        }, trace_id=trace_id)
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
        milestones.milestone("Task Resolved", {"task_id": task_id})
        logger.info("[Brain] Task resolved.")

    await db.commit()
