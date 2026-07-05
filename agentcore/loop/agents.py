"""
AgentCore Loop — Supervisor & MCP Workers (A2A + ReAct Loop)
"""
import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from agentcore.config import get_settings
from agentcore.mcps import create_mcp_instance, get_all_mcps, get_mcp_tool_schemas
from agentcore.loop.context import ContextWindow
from agentcore.loop.state import AgentContext
from agentcore.loop.llm import LLMCaller
from agentcore.database import add_message, add_tool_call, update_tool_call

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AgentCard:
    name: str
    description: str
    skills: List[str]
    status: str = "ready"


class MCPAgent:
    """Isolated agent owning one MCP server (built-in or custom stdio). Runs ReAct loop."""
    def __init__(self, mcp_name: str, mcp_client: Any = None):
        self.name = mcp_name
        self.mcp = mcp_client or create_mcp_instance(mcp_name)
        if hasattr(self.mcp, "tools"):  # Custom Stdio Client
            self.skills = [t["name"] for t in self.mcp.tools]
            self.description = getattr(self.mcp, "description", f"Custom Stdio MCP: {mcp_name}")
        else:  # Built-in
            self.skills = list(self.mcp.TOOLS.keys())
            self.description = self.mcp.description
        self.card = AgentCard(name=mcp_name, description=self.description, skills=self.skills)
        self.llm = LLMCaller()

    async def run(self, task: str, session_id: str, context: Optional[AgentContext] = None) -> str:
        """Isolated ReAct loop (up to 5 steps) using only this agent's tools."""
        logger.info(f"Agent {self.name} starting task: {task}")
        
        # Build schemas
        if hasattr(self.mcp, "tools"):
            tool_schemas = []
            for t in self.mcp.tools:
                tool_schemas.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", t["name"]),
                        "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
                    }
                })
        else:
            tool_schemas = get_mcp_tool_schemas(self.mcp)
            
        messages = [
            {"role": "system", "content": f"You are {self.name}, an expert specialized worker agent. Your description is: {self.description}. You must solve the user's task using your tools. Always specify thought and action in each turn."},
            {"role": "user", "content": task}
        ]
        
        for step in range(5):
            content_accum = []
            tool_calls_accum = []
            
            async for chunk in self.llm.call(messages, tools=tool_schemas, stream=True, context=context):
                if chunk["type"] == "tool_calls":
                    tool_calls_accum = chunk["calls"]
                    content_accum.append(chunk["content"])
                elif chunk["type"] == "message":
                    content_accum.append(chunk["content"])
                    
            content = "".join(content_accum)
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls_accum})
            
            if not tool_calls_accum:
                return content or "Task finished"
                
            for tool_call in tool_calls_accum:
                func_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                try:
                    # Enforce 30s timeout per tool call
                    if hasattr(self.mcp, "tools"):
                        res = await asyncio.wait_for(self.mcp.call_tool(func_name, args), timeout=30.0)
                        # Extract text contents from standard MCP tool response
                        content_list = res.get("content") or []
                        res_str = "\n".join(c.get("text", "") for c in content_list if c.get("type") == "text")
                        if not res_str:
                            res_str = json.dumps(res)
                    else:
                        result = await asyncio.wait_for(self.mcp.call_tool(func_name, args, session_id=session_id, context=context), timeout=30.0)
                        res_str = json.dumps(result)
                except Exception as e:
                    res_str = f"Error executing tool {func_name}: {str(e)}"
                messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": func_name, "content": res_str})
        return "Max steps reached"


# Module-level cache for built-in MCPAgents
_BUILTIN_AGENT_CACHE: Dict[str, MCPAgent] = {}


class ManagementAgent:
    """The central Coordinator. Plans tasks, delegates to workers, handles approvals."""
    def __init__(self, session_id: str, db_session: Any, context: Optional[AgentContext] = None):
        self.session_id = session_id
        self.db = db_session
        self.context = context
        self.llm = LLMCaller()
        self.context_window = ContextWindow(max_tokens=4000)
        self.workers: Dict[str, MCPAgent] = {}
        self._load_builtin_agents()

    def _load_builtin_agents(self):
        # Retrieve cached builtins or instantiate them
        for mcp_name in get_all_mcps().keys():
            if mcp_name not in _BUILTIN_AGENT_CACHE:
                _BUILTIN_AGENT_CACHE[mcp_name] = MCPAgent(mcp_name)
            self.workers[mcp_name] = _BUILTIN_AGENT_CACHE[mcp_name]

    async def _load_custom_agents(self):
        """Asynchronously load custom Stdio MCP servers and spawn/connect clients."""
        from agentcore.mcp import get_mcp_manager
        from sqlalchemy import select
        from agentcore.database import SessionModel, TenantModel
        
        manager = get_mcp_manager()
        configs = []
        
        # Load from Session meta
        try:
            res = await self.db.execute(select(SessionModel).where(SessionModel.id == self.session_id))
            session = res.scalar_one_or_none()
            if session and session.meta:
                configs.extend(session.meta.get("mcp_servers", []))
        except Exception as e:
            logger.error(f"Failed to query session custom MCP servers: {e}")
            
        # Load from Tenant settings
        if self.context and self.context.tenant_id:
            try:
                res = await self.db.execute(select(TenantModel).where(TenantModel.id == self.context.tenant_id))
                tenant = res.scalar_one_or_none()
                if tenant and tenant.settings:
                    configs.extend(tenant.settings.get("mcp_servers", []))
            except Exception as e:
                logger.error(f"Failed to query tenant custom MCP servers: {e}")
                
        # Register/Connect and load them as MCPAgent workers
        for cfg in configs:
            if cfg.get("type") == "builtin" or not cfg.get("command"):
                continue
            name = cfg.get("name")
            if name:
                try:
                    client = await manager.get_or_create_client(name, cfg)
                    # If client initialized successfully, register as worker
                    self.workers[name] = MCPAgent(name, mcp_client=client)
                except Exception as e:
                    logger.error(f"Failed to load custom MCP worker '{name}': {e}")

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Coordinator ReAct Loop. Generates streaming updates."""
        await add_message(self.db, self.session_id, "user", user_message)
        
        # Dynamically load custom registered agents at runtime start
        await self._load_custom_agents()
        
        cards_str = "\n".join([f"- {w.name}: {w.description} (Skills: {w.skills})" for w in self.workers.values()])
        system_prompt = f"""You are the Management Agent. You plan and orchestrate task execution.
You must NOT execute tools directly. You must delegate to your specialized workers:
{cards_str}

Use the 'delegate_to_agent' tool to assign tasks.
If you need a new worker or MCP connection, use the 'create_mcp_agent' tool.
Explain your reasoning (Thought) in every turn before making an Action.
When all subtasks are finished, reply directly to the user."""

        coordinator_tools = [
            {
                "type": "function",
                "function": {
                    "name": "delegate_to_agent",
                    "description": "Send a subtask to a specialized worker agent using A2A.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_name": {"type": "string", "description": "Name of the worker agent"},
                            "task": {"type": "string", "description": "Specific task description"}
                        },
                        "required": ["agent_name", "task"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_mcp_agent",
                    "description": "Auto-create a new MCP agent. Only asks for missing required parameters (e.g. API keys).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the agent"},
                            "description": {"type": "string", "description": "Role / details"}
                        },
                        "required": ["name", "description"]
                    }
                }
            }
        ]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        for loop_idx in range(10):
            # Check for task cancellation from client
            from agentcore.database import TaskModel, TaskStatus
            try:
                if self.context and self.context.task_id:
                    res = await self.db.execute(select(TaskModel).where(TaskModel.id == self.context.task_id))
                    task_obj = res.scalar_one_or_none()
                    if task_obj and task_obj.status == TaskStatus.cancelled:
                        logger.info(f"Task {self.context.task_id} cancellation detected. Aborting execution loop.")
                        yield {"type": "error", "error": "Task execution was cancelled by the user."}
                        return
            except Exception as e:
                logger.debug(f"Task cancellation check failed: {e}")

            compacted = self.context_window.compact(messages)
            content_accum = []
            tool_calls_accum = []
            
            async for chunk in self.llm.call(compacted, tools=coordinator_tools, context=self.context):
                if chunk["type"] == "reasoning":
                    yield {"type": "reasoning", "text": chunk["text"]}
                elif chunk["type"] == "token":
                    yield {"type": "token", "text": chunk["text"]}
                elif chunk["type"] == "tool_calls":
                    tool_calls_accum = chunk["calls"]
                    content_accum.append(chunk["content"])
                elif chunk["type"] == "message":
                    content_accum.append(chunk["content"])
                elif chunk["type"] == "error":
                    yield chunk
                    return

            thought = "".join(content_accum)
            messages.append({"role": "assistant", "content": thought, "tool_calls": tool_calls_accum})

            if not tool_calls_accum:
                if thought:
                    await add_message(self.db, self.session_id, "assistant", thought)
                yield {"type": "completed", "content": thought}
                break

            for tool_call in tool_calls_accum:
                func_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                tc_id = tool_call["id"]
                
                yield {"type": "tool_call", "id": tc_id, "name": func_name, "arguments": args}

                from agentcore.governance import check_destructive
                if await check_destructive(func_name, args):
                    yield {"type": "approval_required", "id": tc_id, "name": func_name, "arguments": args}
                    return

                if func_name == "delegate_to_agent":
                    agent_name = args["agent_name"]
                    task_text = args["task"]
                    
                    if agent_name not in self.workers:
                        res_str = f"Error: Agent '{agent_name}' not found."
                    else:
                        worker = self.workers[agent_name]
                        try:
                            # Stream A2A progression status to the UI
                            yield {"type": "tool_executing", "id": tc_id, "tool": func_name, "message": f"Delegating task to specialized agent '{agent_name}'..."}
                            worker_res = await worker.run(task_text, self.session_id, context=self.context)
                            res_str = self.context_window.format_agent_result(agent_name, task_text, worker_res)
                        except Exception as e:
                            res_str = f"Error executing worker {agent_name}: {str(e)}"
                    
                    messages.append({"role": "tool", "tool_call_id": tc_id, "name": func_name, "content": res_str})
                    yield {"type": "tool_result", "id": tc_id, "result": {"success": "Error" not in res_str, "data": res_str}}
                    
                elif func_name == "create_mcp_agent":
                    name = args["name"]
                    desc = args["description"]
                    self.workers[name] = MCPAgent(name)
                    res_str = f"Agent '{name}' created successfully for '{desc}'."
                    messages.append({"role": "tool", "tool_call_id": tc_id, "name": func_name, "content": res_str})
                    yield {"type": "tool_result", "id": tc_id, "result": {"success": True, "data": res_str}}

