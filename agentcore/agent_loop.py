"""
AgentCore Agent Loop - Orchestration Engine

Consolidated agent loop: core orchestration + LLM calling + response parsing + ReAct loop.
"""
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

from agentcore.config import get_settings
from agentcore.tools import get_tool_registry, get_tool_handler, get_all_tool_schemas
from agentcore.governance import get_governance_engine, GovernanceApprovalRequiredError
from agentcore.database import (
    get_db, create_session, create_task, add_message, add_tool_call,
    update_tool_call, TaskModel, TaskStatus, MessageModel,
)
from agentcore.auth import TokenPayload

logger = logging.getLogger(__name__)


# =============================================================================
# STATE & CONTEXT
# =============================================================================

class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_APPROVAL = "waiting_approval"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentContext:
    session_id: str
    task_id: str
    user_id: str
    tenant_id: str
    organization_id: Optional[str] = None
    user_role: str = "developer"
    risk_mode: str = "auto"
    workspace_path: str = "/workspace"
    metadata: Dict[str, Any] = field(default_factory=dict)

    state: AgentState = AgentState.IDLE
    current_step: int = 0
    max_steps: int = 20
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    stream_callback: Optional[Callable] = None

    def to_session_dict(self) -> Dict[str, Any]:
        return {
            "id": self.session_id,
            "user_role": self.user_role,
            "tenant_id": self.tenant_id,
            "risk_mode": self.risk_mode,
        }


# =============================================================================
# LLM CALLER
# =============================================================================

class LLMCaller:
    def __init__(self):
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5

    async def call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        stream: bool = True,
        context: Optional[AgentContext] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        settings = get_settings()
        raw_key = settings.llm_api_key
        base_url = settings.llm_base_url
        model = settings.llm_model
        temperature = settings.llm_temperature
        max_tokens = settings.llm_max_tokens

        if context and context.tenant_id:
            from sqlalchemy import select
            from agentcore.database import get_db, TenantModel, SessionModel
            async for db in get_db():
                try:
                    t_res = await db.execute(select(TenantModel).where(TenantModel.id == context.tenant_id))
                    tenant = t_res.scalar_one_or_none()
                    if tenant and tenant.settings:
                        byom_configs = tenant.settings.get("byom_configs", [])
                        if byom_configs:
                            selected = byom_configs[0]
                            s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                            session = s_res.scalar_one_or_none()
                            if session and session.active_model_id:
                                for cfg in byom_configs:
                                    if cfg.get("id") == session.active_model_id:
                                        selected = cfg
                                        break
                            if selected:
                                if selected.get("api_key"):
                                    raw_key = selected.get("api_key")
                                if selected.get("model"):
                                    model = selected.get("model")
                                if selected.get("base_url") is not None:
                                    base_url = selected.get("base_url")
                                if selected.get("temperature") is not None:
                                    temperature = float(selected.get("temperature"))
                                if selected.get("max_tokens") is not None:
                                    max_tokens = int(selected.get("max_tokens"))
                except Exception as e:
                    logger.error(f"Failed to load dynamic BYOM config: {e}")
                break

        if not raw_key:
            yield {"type": "error", "error": "No API key configured. Please enter your API key in settings."}
            return

        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if settings.llm_top_p:
            completion_kwargs["top_p"] = settings.llm_top_p
        if max_tokens:
            completion_kwargs["max_tokens"] = max_tokens
        if tools:
            completion_kwargs["tools"] = tools
            completion_kwargs["tool_choice"] = "auto"

        try:
            if base_url:
                client = AsyncOpenAI(base_url=base_url, api_key=raw_key)
                response = await client.chat.completions.create(**completion_kwargs)
            else:
                completion_kwargs["api_key"] = raw_key
                if "/" in model:
                    completion_kwargs["custom_llm_provider"] = model.split("/")[0]
                else:
                    completion_kwargs["custom_llm_provider"] = "openai"
                response = await acompletion(**completion_kwargs)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            yield {"type": "error", "error": f"LLM error: {e}"}
            return

        self._circuit_breaker_failures = 0
        tool_calls_dict = {}
        collected_content = []

        try:
            async for chunk in response:
                choices = getattr(chunk, "choices", None) or []
                if not choices or getattr(choices[0], "delta", None) is None:
                    continue
                delta = choices[0].delta

                if getattr(delta, "reasoning_content", None):
                    yield {"type": "reasoning", "text": delta.reasoning_content}

                if delta.content:
                    collected_content.append(delta.content)
                    yield {"type": "token", "text": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {"id": tc.id, "type": tc.type, "function": {"name": "", "arguments": ""}}
                        if tc.function:
                            if tc.function.name:
                                tool_calls_dict[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments

        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield {"type": "error", "error": f"Streaming error: {e}"}
            return

        # Yield final aggregated result
        if tool_calls_dict:
            combined_calls = list(tool_calls_dict.values())
            yield {"type": "tool_calls", "calls": combined_calls, "content": "".join(collected_content)}
        else:
            yield {"type": "message", "content": "".join(collected_content)}


# =============================================================================
# AGENT LOOP
# =============================================================================

class AgentLoop:
    def __init__(self, llm_client: Any = None, system_prompt: str = None):
        self.llm_caller = llm_client or LLMCaller()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.tool_registry = get_tool_registry()
        self.governance = get_governance_engine()
        self._running_tasks: Dict[str, asyncio.Task] = {}

    def _default_system_prompt(self) -> str:
        return """You are AgentCore, an autonomous coding agent with access to tools.

You can:
- Read, write, and edit files in the workspace
- Execute bash commands in a sandboxed environment
- Search the web for information
- Use MCP tools when available

Your goal is to complete the user's task efficiently and safely.

When using tools:
1. Think about what you need to do
2. Call the appropriate tool
3. Observe the result
4. Continue until the task is complete

Always explain your reasoning before taking actions."""

    async def run(
        self,
        context: AgentContext,
        user_message: str,
        stream: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        context.state = AgentState.THINKING
        yield {"type": "state_change", "state": context.state.value}

        context.messages.append({"role": "user", "content": user_message})
        await self._persist_message(context, "user", user_message)

        try:
            await self._update_task(context, TaskStatus.running)
            while context.current_step < context.max_steps:
                context.current_step += 1

                context.state = AgentState.THINKING
                yield {"type": "state_change", "state": context.state.value}

                tools = self.tool_registry.get_all_schemas()
                openai_tools = [t.to_openai_function() for t in tools]

                async for event in self.llm_caller.call(
                    [{"role": "system", "content": self.system_prompt}] + context.messages[-20:],
                    tools=openai_tools,
                    stream=stream,
                    context=context,
                ):
                    if event["type"] in ("token", "reasoning", "state_change"):
                        yield event
                    elif event["type"] == "tool_calls":
                        # Store the assistant message with tool_calls for the conversation history
                        tool_calls = event["calls"]
                        content = event.get("content", "")
                        context.messages.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": tool_calls,
                        })
                        await self._persist_message_with_tool_calls(context, "assistant", content, tool_calls)
                        
                        for tool_call in tool_calls:
                            async for tool_event in self._execute_tool(context, tool_call):
                                yield tool_event
                        break  # Break inner loop, continue outer loop with new context
                    elif event["type"] == "message":
                        content = event["content"]
                        context.messages.append({"role": "assistant", "content": content})
                        await self._persist_message(context, "assistant", content)
                        yield {"type": "message", "role": "assistant", "content": content}
                        # Task complete
                        context.state = AgentState.COMPLETED
                        await self._update_task(context, TaskStatus.completed, result=content)
                        yield {"type": "state_change", "state": context.state.value}
                        yield {"type": "done", "result": "Task completed"}
                        return
                    elif event["type"] == "error":
                        await self._update_task(context, TaskStatus.failed, error=event.get("error"))
                        yield event
                        return

            if context.current_step >= context.max_steps:
                await self._update_task(context, TaskStatus.failed, error="Max steps reached")
                yield {"type": "error", "error": "Max steps reached"}
                return

            context.state = AgentState.COMPLETED
            await self._update_task(context, TaskStatus.completed)
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "done", "result": "Task completed"}

        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            context.state = AgentState.ERROR
            await self._update_task(context, TaskStatus.failed, error=str(e))
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "error", "error": str(e)}

    async def _execute_tool(
        self,
        context: AgentContext,
        tool_call: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool_name = tool_call.get("function", {}).get("name") or tool_call.get("name")
        arguments_str = tool_call.get("function", {}).get("arguments", "{}")
        tool_call_id = tool_call.get("id", str(uuid.uuid4()))

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}

        arguments["session_id"] = context.session_id
        arguments["task_id"] = context.task_id
        arguments["user_id"] = context.user_id
        arguments["tenant_id"] = context.tenant_id

        # Governance check
        try:
            session_obj = type('Session', (), context.to_session_dict())()
            self.governance.assert_action_allowed(session_obj, tool_name, arguments)
        except GovernanceApprovalRequiredError as e:
            context.state = AgentState.WAITING_APPROVAL
            await self._update_task(context, TaskStatus.needs_approval)
            yield {"type": "state_change", "state": context.state.value}
            async for db in get_db():
                tc = await add_tool_call(db, context.session_id, context.task_id, tool_name, arguments, "pending_approval")
                break
            yield {
                "type": "approval_required",
                "tool": tool_name,
                "arguments": arguments,
                "message": str(e),
                "approval_id": tool_call_id,
                "tool_call_id": tc.id,
            }
            return

        # Execute tool
        context.state = AgentState.EXECUTING
        yield {"type": "state_change", "state": context.state.value}
        yield {"type": "tool_call", "tool": tool_name, "arguments": arguments, "tool_call_id": tool_call_id}
        yield {"type": "tool_progress", "tool": tool_name, "tool_call_id": tool_call_id, "progress": 0, "status": "starting"}

        handler = get_tool_handler(tool_name)
        if not handler:
            result_data = {"success": False, "error": f"Unknown tool: {tool_name}"}
        else:
            try:
                yield {"type": "tool_progress", "tool": tool_name, "tool_call_id": tool_call_id, "progress": 50, "status": "running"}
                result = await handler(**arguments)
                result_data = result.model_dump() if hasattr(result, 'model_dump') else result
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                result_data = {"success": False, "error": str(e)}
                yield {"type": "tool_progress", "tool": tool_name, "tool_call_id": tool_call_id, "progress": 100, "status": "failed", "error": str(e)}

        context.tool_calls.append({
            "tool": tool_name, "arguments": arguments, "result": result_data,
            "timestamp": datetime.utcnow().isoformat(),
        })

        async for db in get_db():
            tool_success = result_data.get("success") if isinstance(result_data, dict) else False
            tc = await add_tool_call(
                db, context.session_id, context.task_id,
                tool_name, arguments, "completed" if tool_success else "failed",
                result_data.get("data") if isinstance(result_data, dict) else result_data,
                result_data.get("error") if isinstance(result_data, dict) else None,
            )
            # Update started_at and completed_at timestamps
            from sqlalchemy import update
            await db.execute(
                update(ToolCallModel)
                .where(ToolCallModel.id == tc.id)
                .values(
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow() if tool_success else None,
                )
            )
            await db.commit()
            break

        # Add result to conversation
        if isinstance(result_data, dict) and result_data.get("success"):
            content = result_data.get("data", "")
        else:
            content = result_data.get("error", "Tool failed") if isinstance(result_data, dict) else str(result_data)
        if not isinstance(content, str):
            content = json.dumps(content, default=str)

        context.messages.append({
            "role": "tool", "content": content, "tool_call_id": tool_call_id,
        })
        
        # Persist the tool result message to database
        await self._persist_message(context, "tool", content, tool_call_id)

        yield {"type": "tool_progress", "tool": tool_name, "tool_call_id": tool_call_id, "progress": 100, "status": "completed"}
        yield {"type": "tool_result", "tool": tool_name, "result": result_data}

    async def _persist_message(self, context: AgentContext, role: str, content: str, tool_call_id: str = None) -> None:
        try:
            async for db in get_db():
                from sqlalchemy import select
                existing = await db.execute(
                    select(MessageModel.id).where(
                        MessageModel.session_id == context.session_id,
                        MessageModel.task_id == context.task_id,
                        MessageModel.role == role,
                        MessageModel.content == content,
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    break
                await add_message(db, context.session_id, role, content, context.task_id, tool_call_id)
                break
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

    async def _persist_message_with_tool_calls(self, context: AgentContext, role: str, content: str, tool_calls: list) -> None:
        """Persist a message that includes tool_calls (for assistant messages with function calls)."""
        try:
            async for db in get_db():
                from sqlalchemy import select
                existing = await db.execute(
                    select(MessageModel.id).where(
                        MessageModel.session_id == context.session_id,
                        MessageModel.task_id == context.task_id,
                        MessageModel.role == role,
                        MessageModel.content == content,
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    break
                msg = MessageModel(
                    session_id=context.session_id,
                    task_id=context.task_id,
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                )
                db.add(msg)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist message with tool_calls: {e}")

    async def _update_task(
        self,
        context: AgentContext,
        status: TaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        try:
            async for db in get_db():
                task = await db.get(TaskModel, context.task_id)
                if not task:
                    break
                task.status = status
                if status == TaskStatus.running and not task.started_at:
                    task.started_at = datetime.utcnow()
                if status in {TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled}:
                    task.completed_at = datetime.utcnow()
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                db.add(task)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to update task state: {e}")


# =============================================================================
# WORKER MODE (for background processing)
# =============================================================================

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

        llm_caller = LLMCaller()
        async for event in llm_caller.call(
            [{"role": "system", "content": AgentLoop()._default_system_prompt()}] + messages,
            tools=openai_tools,
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


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

async def run_agent(
    session_id: str,
    task_id: str,
    user_message: str,
    user: TokenPayload,
    llm_client: Any = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    context = AgentContext(
        session_id=session_id, task_id=task_id, user_id=user.sub,
        tenant_id=user.tenant_id, organization_id=user.organization_id,
        user_role=user.role, risk_mode="auto",
    )
    agent = AgentLoop(llm_client=llm_client)
    async for event in agent.run(context, user_message):
        yield event


async def run_agent_stream(
    session_id: str,
    task_id: str,
    user_message: str,
    tenant_id: str,
    user_id: str,
    user_role: str = "developer",
    llm_client: Any = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Convenience wrapper for WebSocket callers that pass individual fields."""
    user = TokenPayload(
        sub=user_id, tenant_id=tenant_id,
        role=user_role, email="", organization_id=None,
        exp=0, iat=0,
    )
    async for event in run_agent(session_id, task_id, user_message, user, llm_client):
        yield event
