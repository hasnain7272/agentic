import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from litellm import acompletion
from openai import AsyncOpenAI
from sqlalchemy import select

from agentcore.config import get_settings
from agentcore.tools import get_tool_registry, get_tool_handler, get_all_tool_schemas
from agentcore.governance import get_governance_engine, GovernanceApprovalRequiredError
from agentcore.database import (
    get_db, get_db_manager, create_session, create_task, add_message, add_tool_call,
    update_tool_call, TaskModel, TaskStatus, MessageModel, ToolCallModel, SessionModel, UserModel
)
from agentcore.auth import TokenPayload

logger = logging.getLogger(__name__)
settings = get_settings()

from .state import AgentContext
from .orchestrator import AgentLoop
from .llm import LLMCaller


async def process_task_event(
    event: Dict[str, Any],
    db_session: Any = None,
) -> None:
    """Process a task event from queue (worker mode)."""
    from agentcore.queue import get_broker
    from agentcore.database import AsyncSessionLocal

    task_id = event.get("task_id")
    session_id = event.get("session_id")
    description = event.get("description", "")
    tenant_id = event.get("tenant_id")
    trace_id = event.get("trace_id")

    broker = await get_broker()
    db = db_session or AsyncSessionLocal()

    try:
        await broker.publish(f"task_log:{task_id}", {"status": "thinking", "message": "Analyzing..."})

        # Get session
        from sqlalchemy import select
        from agentcore.database import SessionModel, TaskModel

        stmt = select(SessionModel).where(SessionModel.id == session_id)
        if tenant_id:
            stmt = stmt.where(SessionModel.tenant_id == tenant_id)
        session_result = await db.execute(stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
            return

        if description:
            await add_message(db, session_id, "user", description, task_id)

        # Get task
        task_result = await db.execute(
            select(TaskModel).where(TaskModel.id == task_id, TaskModel.session_id == session_id)
        )
        task = task_result.scalar_one_or_none()

        if task:
            task.iteration_count += 1
            if task.iteration_count > 50:
                await add_message(db, session_id, "assistant", "Max iterations reached", task_id=task_id)
                await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
                await db.commit()
                return

        # Build messages for LLM
        messages = []
        msg_result = await db.execute(
            select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.created_at)
        )
        for msg in msg_result.scalars().all():
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.role == "tool" and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            messages.append(msg_dict)

        # Call LLM
        tools = get_all_tool_schemas()
        openai_tools = [t.to_openai_function() for t in tools]

        # Create context for session-level BYOK
        from agentcore.auth import TokenPayload
        context = AgentContext(
            session_id=session_id, task_id=task_id, user_id=event.get("user_id", ""),
            tenant_id=tenant_id, organization_id=None,
            user_role="developer", risk_mode="auto",
        )
        
        llm_caller = LLMCaller()
        async for event in llm_caller.call(
            [{"role": "system", "content": AgentLoop()._default_system_prompt()}] + messages,
            tools=openai_tools,
            context=context,
        ):
            if event["type"] == "tool_calls":
                for tool_call in event["calls"]:
                    # Execute via tool worker queue
                    await broker.publish("execution_queue", {
                        "event_type": "EXECUTE_TOOL_BATCH",
                        "task_id": task_id,
                        "session_id": session_id,
                        "tools": [{
                            "id": tc["id"], "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"] or "{}")
                        } for tc in event["calls"]],
                        "tenant_id": tenant_id,
                    }, trace_id=trace_id)
                break
            elif event["type"] == "message":
                await add_message(db, session_id, "assistant", event["content"], task_id)
                await broker.publish("task_resolved", {
                    "event_type": "TASK_RESOLVED", "task_id": task_id, "session_id": session_id,
                    "output": event["content"],
                }, trace_id=trace_id)
                await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
                break

        await db.commit()

    except Exception as e:
        logger.error(f"Process task event error: {e}")
        await broker.publish(f"task_log:{task_id}", {"event_type": "TASK_RESOLVED"})
    finally:
        if not db_session:
            await db.close()


async def process_tool_event(
    event: Dict[str, Any],
    db_session: Any = None,
) -> None:
    """Process a tool execution event from queue (worker mode)."""
    from agentcore.queue import get_broker
    from agentcore.database import AsyncSessionLocal, SessionModel, ToolCallModel
    from sqlalchemy import select, and_

    task_id = event.get("task_id")
    session_id = event.get("session_id")
    tenant_id = event.get("tenant_id")
    trace_id = event.get("trace_id")
    tools = event.get("tools", [])

    broker = await get_broker()
    db = db_session or AsyncSessionLocal()

    try:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        if tenant_id:
            stmt = stmt.where(SessionModel.tenant_id == tenant_id)
        session_result = await db.execute(stmt)
        session = session_result.scalar_one_or_none()

        any_approval_required = False

        for tool_spec in tools:
            tool_name = tool_spec.get("name", "")
            tool_args = tool_spec.get("args", {})
            tool_call_id = tool_spec.get("id")

            await broker.publish(f"task_log:{task_id}", {"event": "tool_executing", "name": tool_name})

            # Governance
            try:
                if session:
                    session_obj = type('Session', (), {
                        "id": session_id, "user_role": "developer",
                        "tenant_id": tenant_id, "risk_mode": "auto"
                    })()
                    get_governance_engine().assert_action_allowed(session_obj, tool_name, tool_args)
            except GovernanceApprovalRequiredError as e:
                await add_message(db, session_id, "tool", f"APPROVAL REQUIRED: {e}", task_id=task_id, tool_call_id=tool_call_id)
                any_approval_required = True
                await broker.publish(f"task_log:{task_id}", {"event": "tool_approval_required", "name": tool_name})
                continue

            # Execute
            handler = get_tool_handler(tool_name)
            if not handler:
                output = f"Unknown tool: {tool_name}"
            else:
                try:
                    result = await handler(**tool_args)
                    output = str(result.data) if hasattr(result, 'data') else str(result)
                except Exception as e:
                    output = f"TOOL ERROR: {e}"

            # Persist
            await add_message(db, session_id, "tool", output, task_id=task_id, tool_call_id=tool_call_id)
            await db.commit()

            await broker.publish(f"task_log:{task_id}", {"event": "tool_done", "name": tool_name, "result_preview": output[:100]})

        # Re-trigger brain
        if not any_approval_required:
            await broker.publish("task_queue", {
                "event_type": "AGENT_THINK",
                "task_id": task_id,
                "session_id": session_id,
                "description": "",
                "tenant_id": tenant_id,
            }, trace_id=trace_id)

    except Exception as e:
        logger.error(f"Process tool event error: {e}")
    finally:
        if not db_session:
            await db.close()
