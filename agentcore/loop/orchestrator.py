"""
AgentCore Loop — Orchestrator (ReAct Agent Loop)

Swarm-aware orchestrator with:
- Context compression (rolling summary, not truncation)
- Session-level tool filtering (UI-managed)
- Error message persistence to DB
- A2A linked session context injection
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

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

from .state import AgentState, AgentContext
from .llm import LLMCaller

class AgentLoop:
    def __init__(self, llm_client: Any = None, system_prompt: str = None):
        self.llm_caller = llm_client or LLMCaller()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.tool_registry = get_tool_registry()
        self.governance = get_governance_engine()
        self._running_tasks: Dict[str, asyncio.Task] = {}

    def _default_system_prompt(self) -> str:
        return """You are AgentCore, an autonomous AI agent operating as part of a swarm.

You have access to skilled tools organized by category:
- **Web**: Search the web and fetch content from URLs
- **Knowledge**: Store and recall memories in your session database
- **Code**: Execute Python code snippets for calculations and analysis
- **Integration**: Make HTTP requests to external APIs
- **Content**: Generate images and documents
- **Communication**: Send notifications via various channels
- **A2A**: Delegate tasks to or query other agent sessions in the swarm

Everything you know and produce is stored in the database. You have NO filesystem access.

When working:
1. Think about what you need to accomplish
2. Use the most appropriate tool for each step
3. Store important findings in memory for later recall
4. Collaborate with linked sessions via A2A tools when needed
5. Always explain your reasoning before taking actions

You are part of an Orchestrator-Planner-Executor-Reviewer swarm.
Be thorough, proactive, and always verify your work."""

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

        # Load A2A linked sessions context + session tool config
        a2a_context = ""
        enabled_tools = None
        async for db in get_db():
            try:
                s_res = await db.execute(select(SessionModel).where(SessionModel.id == context.session_id))
                session_obj = s_res.scalar_one_or_none()
                if session_obj and session_obj.meta:
                    enabled_tools = session_obj.meta.get("enabled_tools")
                    linked_ids = session_obj.meta.get("a2a_links", [])
                    if linked_ids:
                        context_parts = []
                        for lid in linked_ids:
                            l_res = await db.execute(select(SessionModel).where(SessionModel.id == lid))
                            linked_sess = l_res.scalar_one_or_none()
                            if linked_sess:
                                m_res = await db.execute(
                                    select(MessageModel).where(MessageModel.session_id == lid)
                                    .order_by(MessageModel.created_at.desc()).limit(5)
                                )
                                msgs = list(reversed(m_res.scalars().all()))
                                msg_lines = [f"    * {'User' if m.role == 'user' else 'Agent'}: {m.content[:300]}" for m in msgs]
                                context_parts.append(
                                    f"- Session '{linked_sess.title}' (ID: {lid}):\n" +
                                    ("\n".join(msg_lines) if msg_lines else "    * (No messages yet)")
                                )
                        if context_parts:
                            a2a_context = "\n### Linked Swarm Sessions (A2A Mesh Context)\n" + "\n".join(context_parts)
            except Exception as e:
                logger.error(f"Error loading A2A context: {e}")
            break

        try:
            await self._update_task(context, TaskStatus.running)
            while context.current_step < context.max_steps:
                context.current_step += 1

                context.state = AgentState.THINKING
                yield {"type": "state_change", "state": context.state.value}

                # Session-level tool filtering
                all_names = self.tool_registry.get_all_names()
                if enabled_tools is not None:
                    all_names = [n for n in all_names if n in enabled_tools]
                tools = [self.tool_registry.get_schema(n) for n in all_names]
                tools = [t for t in tools if t is not None]
                openai_tools = [t.to_openai_function() for t in tools]

                system_content = self.system_prompt
                if a2a_context:
                    system_content += "\n" + a2a_context

                # Context compression: rolling summary for older messages
                compressed_messages = self._compress_context(context.messages)

                async for event in self.llm_caller.call(
                    [{"role": "system", "content": system_content}] + compressed_messages,
                    tools=openai_tools,
                    stream=stream,
                    context=context,
                ):
                    if event["type"] in ("token", "reasoning", "state_change"):
                        yield event
                    elif event["type"] == "tool_calls":
                        tool_calls = event["calls"]
                        content = event.get("content", "")
                        context.messages.append({
                            "role": "assistant", "content": content, "tool_calls": tool_calls,
                        })
                        await self._persist_message_with_tool_calls(context, "assistant", content, tool_calls)
                        for tool_call in tool_calls:
                            async for tool_event in self._execute_tool(context, tool_call):
                                yield tool_event
                        break
                    elif event["type"] == "message":
                        content = event["content"]
                        context.messages.append({"role": "assistant", "content": content})
                        await self._persist_message(context, "assistant", content)
                        yield {"type": "message", "role": "assistant", "content": content}
                        context.state = AgentState.COMPLETED
                        await self._update_task(context, TaskStatus.completed, result=content)
                        yield {"type": "state_change", "state": context.state.value}
                        yield {"type": "done", "result": "Task completed"}
                        return
                    elif event["type"] == "error":
                        error_msg = event.get("error") or "Unknown error"
                        await self._persist_message(context, "assistant", f"Error: {error_msg}")
                        await self._update_task(context, TaskStatus.failed, error=error_msg)
                        yield event
                        return

            if context.current_step >= context.max_steps:
                error_msg = "Max steps reached"
                await self._persist_message(context, "assistant", f"Error: {error_msg}")
                await self._update_task(context, TaskStatus.failed, error=error_msg)
                yield {"type": "error", "error": error_msg}
                return

            context.state = AgentState.COMPLETED
            await self._update_task(context, TaskStatus.completed)
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "done", "result": "Task completed"}

        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            context.state = AgentState.ERROR
            error_msg = str(e)
            await self._persist_message(context, "assistant", f"Error: {error_msg}")
            await self._update_task(context, TaskStatus.failed, error=error_msg)
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "error", "error": error_msg}

    def _compress_context(self, messages: List[Dict[str, Any]], keep_recent: int = 8, max_content_len: int = 2000) -> List[Dict[str, Any]]:
        """Compress context: keep recent messages verbatim, summarize older ones.
        
        Strategy (rolling compression):
        - Last `keep_recent` messages: kept verbatim (but capped per-message)
        - Older messages: compressed into a single summary block
        This prevents the 1.7M token overflow while preserving recent context.
        """
        if len(messages) <= keep_recent:
            # All messages fit — just cap individual content length
            return [self._cap_message(m, max_content_len * 2) for m in messages]

        older = messages[:-keep_recent]
        recent = messages[-keep_recent:]

        # Build compressed summary of older messages
        summary_parts = []
        for msg in older:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 300:
                content = content[:300] + "..."
            if content:
                summary_parts.append(f"[{role}] {content}")

        summary_text = "\n".join(summary_parts[-20:])  # Keep at most last 20 older messages in summary
        compressed = []
        if summary_text:
            compressed.append({
                "role": "system",
                "content": f"### Conversation History Summary (older messages compressed)\n{summary_text}",
            })

        # Add recent messages verbatim but capped
        for msg in recent:
            compressed.append(self._cap_message(msg, max_content_len))

        return compressed

    def _cap_message(self, msg: Dict[str, Any], max_len: int) -> Dict[str, Any]:
        """Cap a single message's content length to prevent token overflow."""
        result = dict(msg)
        content = result.get("content", "")
        if isinstance(content, str) and len(content) > max_len:
            result["content"] = content[:max_len] + f"\n... (truncated from {len(content)} chars)"
        return result

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
                "type": "approval_required", "tool": tool_name, "arguments": arguments,
                "message": str(e), "approval_id": tool_call_id, "tool_call_id": tc.id,
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
            from sqlalchemy import update
            await db.execute(
                update(ToolCallModel).where(ToolCallModel.id == tc.id)
                .values(started_at=datetime.utcnow(), completed_at=datetime.utcnow() if tool_success else None)
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

        context.messages.append({"role": "tool", "content": content, "tool_call_id": tool_call_id})
        await self._persist_message(context, "tool", content, tool_call_id)

        yield {"type": "tool_progress", "tool": tool_name, "tool_call_id": tool_call_id, "progress": 100, "status": "completed"}
        yield {"type": "tool_result", "tool": tool_name, "result": result_data}

    async def _persist_message(self, context: AgentContext, role: str, content: str, tool_call_id: str = None) -> None:
        try:
            async for db in get_db():
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
                    session_id=context.session_id, task_id=context.task_id,
                    role=role, content=content, tool_calls=tool_calls,
                )
                db.add(msg)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist message with tool_calls: {e}")

    async def _update_task(self, context: AgentContext, status: TaskStatus,
                           result: Optional[str] = None, error: Optional[str] = None) -> None:
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
