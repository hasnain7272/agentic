"""
AgentCore Loop — Planner-Generator-Evaluator (PGE) Harness powered by LangGraph.
"""
import asyncio
import json
import logging
import uuid
import os
from typing import AsyncGenerator, Dict, Any, List, Optional
from dataclasses import dataclass

from agentcore.config import get_settings
from agentcore.loop.state import AgentContext

logger = logging.getLogger(__name__)
settings = get_settings()

def extract_first_json_object(text: str) -> Optional[str]:
    start_idx = text.find('{')
    if start_idx == -1:
        start_idx = text.find('[')
        if start_idx == -1:
            return None
        
    brace_count = 0
    in_string = False
    escape = False
    open_char = text[start_idx]
    close_char = '}' if open_char == '{' else ']'
    
    for idx in range(start_idx, len(text)):
        char = text[idx]
        
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == open_char:
                brace_count += 1
            elif char == close_char:
                brace_count -= 1
                if brace_count == 0:
                    return text[start_idx : idx + 1]
                    
    return None


def parse_text_tool_call(content: str) -> Optional[Dict[str, Any]]:
    json_str = extract_first_json_object(content)
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and "name" in data:
            args = data.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            return {"name": data["name"], "arguments": args}
    except Exception:
        pass
    return None


@dataclass
class AgentCard:
    name: str
    description: str
    skills: List[str]
    status: str = "ready"


class MCPAgent:
    """Stub class kept for backwards compatibility with legacy imports."""
    def __init__(self, mcp_name: str, mcp_client: Any = None):
        self.name = mcp_name
        self.description = f"Legacy Stub: {mcp_name}"
        self.skills = []
        self.card = AgentCard(name=mcp_name, description=self.description, skills=[])


class ManagementAgent:
    """
    The PGE (Planner-Generator-Evaluator) Orchestrator wrapping LangGraph runtime.
    Decomposes the task into sprints, negotiates contracts, generates code,
    and tests/grades features dynamically.
    """
    def __init__(self, session_id: str, db_session: Any, context: Optional[AgentContext] = None):
        self.session_id = session_id
        self.db = db_session
        self.context = context

    async def _execute_local_tool(self, func_name: str, args: dict) -> str:
        """Executes a legacy local built-in tool or custom stdio tool directly."""
        from agentcore.mcps import get_all_mcps
        mcps = get_all_mcps()
        for mcp_name, mcp_class in mcps.items():
            instance = mcp_class()
            if func_name in instance.TOOLS:
                try:
                    import inspect
                    sig = inspect.signature(instance.call_tool)
                    kwargs = {}
                    if "session_id" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                        kwargs["session_id"] = self.session_id
                    if "context" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                        kwargs["context"] = self.context

                    res = await asyncio.wait_for(instance.call_tool(func_name, args, **kwargs), timeout=30.0)
                    if isinstance(res, dict) and "content" in res:
                        return res["content"]
                    if isinstance(res, dict) and "written_bytes" in res:
                        return f"Successfully wrote {res['written_bytes']} bytes to {res['path']}"
                    return json.dumps(res)
                except Exception as e:
                    return f"Error executing built-in tool {func_name}: {str(e)}"

        from agentcore.mcp import get_mcp_manager
        manager = get_mcp_manager()
        for client_name, client in manager._clients.items():
            if client.status == "healthy":
                for tool in client.tools:
                    if tool.get("name") == func_name:
                        try:
                            res = await asyncio.wait_for(client.call_tool(func_name, args), timeout=30.0)
                            content_list = res.get("content") or []
                            res_str = "\n".join(c.get("text", "") for c in content_list if c.get("type") == "text")
                            return res_str or json.dumps(res)
                        except Exception as e:
                            return f"Error executing custom stdio tool {func_name}: {str(e)}"

        return f"Error: Tool '{func_name}' not found."

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Runs the LangGraph orchestration flow and yields events in real-time."""
        from agentcore.loop.graph import get_compiled_graph
        from langchain_core.messages import HumanMessage
        from langgraph.errors import GraphInterrupt
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        event_queue = asyncio.Queue()

        async def callback(event: Dict[str, Any]):
            await event_queue.put(event)

        task_id = self.context.task_id if (self.context and self.context.task_id) else self.session_id
        config = {
            "configurable": {
                "thread_id": task_id,
                "callback": callback,
                "context": self.context,
            }
        }

        async def execute_graph():
            try:
                # Load and start custom stdio MCP servers from session/tenant metadata
                try:
                    from agentcore.mcp import get_mcp_manager
                    from agentcore.database import SessionModel, TenantModel
                    session = await self.db.get(SessionModel, self.session_id)
                    servers = []
                    if session and session.meta:
                        servers.extend(session.meta.get("mcp_servers", []))
                    if self.context and self.context.tenant_id:
                        tenant = await self.db.get(TenantModel, self.context.tenant_id)
                        if tenant and tenant.settings:
                            servers.extend(tenant.settings.get("mcp_servers", []))
                    mcp_manager = get_mcp_manager()
                    for s in servers:
                        if s.get("type") == "builtin" or not s.get("command"):
                            continue
                        await mcp_manager.add_server(s)
                except Exception as e:
                    logger.error(f"Failed to auto-start configured MCP servers: {e}")

                from agentcore.loop.graph import AsyncRedisSaver
                memory = AsyncRedisSaver()
                
                async def run_compiled(graph):
                    state_snapshot = await graph.aget_state(config)
                    if state_snapshot.values:
                        if state_snapshot.next:
                            await graph.ainvoke(None, config)
                        else:
                            await graph.ainvoke({"messages": [HumanMessage(content=user_message)]}, config)
                    else:
                        initial_state = {
                            "messages": [HumanMessage(content=user_message)],
                            "session_id": self.session_id,
                            "task_id": self.context.task_id if self.context else str(uuid.uuid4()),
                            "tenant_id": self.context.tenant_id if self.context else "local",
                            "user_id": self.context.user_id if self.context else "local",
                            "user_role": self.context.user_role if self.context else "developer",
                            "route": "PGE",
                            "modified_files": [],
                            "step_count": 0,
                            "agents": [],
                            "tasks": [],
                        }
                        await graph.ainvoke(initial_state, config)
                    await event_queue.put({"type": "done"})

                try:
                    await asyncio.wait_for(memory.redis.ping(), timeout=1.0)
                    logger.info("Successfully connected to Redis checkpointer.")
                    compiled_graph = get_compiled_graph(memory)
                    await run_compiled(compiled_graph)
                except Exception as e:
                    logger.warning(f"Redis not available ({e}), falling back to AsyncSqliteSaver.")
                    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                    async with AsyncSqliteSaver.from_conn_string("graph_checkpoints.db") as sqlite_memory:
                        compiled_graph = get_compiled_graph(sqlite_memory)
                        await run_compiled(compiled_graph)
            except GraphInterrupt as gi:
                logger.info(f"Graph execution paused for approval: {gi}")
                await event_queue.put({"type": "done"})
            except Exception as e:
                logger.error(f"Error executing LangGraph: {e}", exc_info=True)
                await event_queue.put({"type": "error", "error": str(e)})

        task = asyncio.create_task(execute_graph())

        try:
            while True:
                event = await event_queue.get()
                yield event
                if event.get("type") in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()
