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
    """Isolated agent owning one MCP server. Runs ReAct loop within a tiny context."""
    def __init__(self, mcp_name: str):
        self.name = mcp_name
        self.mcp = create_mcp_instance(mcp_name)
        self.skills = list(self.mcp.TOOLS.keys())
        self.card = AgentCard(name=mcp_name, description=self.mcp.description, skills=self.skills)
        self.llm = LLMCaller()

    async def run(self, task: str, session_id: str, context: Optional[AgentContext] = None) -> str:
        """Isolated ReAct loop (up to 5 steps) using only this agent's tools."""
        logger.info(f"Agent {self.name} starting task: {task}")
        tool_schemas = get_mcp_tool_schemas(self.mcp)
        messages = [
            {"role": "system", "content": f"You are {self.name}, an expert specialized worker agent. Your description is: {self.mcp.description}. You must solve the user's task using your tools. Always specify thought and action in each turn."},
            {"role": "user", "content": task}
        ]
        
        for step in range(5):
            content_accum = []
            tool_calls_accum = []
            
            # Consume the async generator stream
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
                
            # Execute tool calls
            for tool_call in tool_calls_accum:
                func_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                try:
                    result = await self.mcp.call_tool(func_name, args)
                    res_str = json.dumps(result)
                except Exception as e:
                    res_str = f"Error executing tool {func_name}: {str(e)}"
                messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": func_name, "content": res_str})
        return "Max steps reached"


class ManagementAgent:
    """The central Coordinator. Plans tasks, delegates to workers, handles approvals."""
    def __init__(self, session_id: str, db_session: Any, context: Optional[AgentContext] = None):
        self.session_id = session_id
        self.db = db_session
        self.context = context
        self.llm = LLMCaller()
        self.context_window = ContextWindow(max_tokens=4000)
        self.workers: Dict[str, MCPAgent] = {}
        self._load_agents()

    def _load_agents(self):
        # Auto-register all 10 pre-built workers
        for mcp_name in get_all_mcps().keys():
            self.workers[mcp_name] = MCPAgent(mcp_name)

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Coordinator ReAct Loop. Generates streaming updates."""
        # 1. Store user message in DB
        await add_message(self.db, self.session_id, "user", user_message)
        
        # Build cards list for system prompt
        cards_str = "\n".join([f"- {w.name}: {w.mcp.description} (Skills: {w.skills})" for w in self.workers.values()])
        system_prompt = f"""You are the Management Agent. You plan and orchestrate task execution.
You must NOT execute tools directly. You must delegate to your specialized workers:
{cards_str}

Use the 'delegate_to_agent' tool to assign tasks.
If you need a new worker or MCP connection, use the 'create_mcp_agent' tool.
Explain your reasoning (Thought) in every turn before making an Action.
When all subtasks are finished, reply directly to the user."""

        # Define coordinator's delegation tools
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

        # Plan-Act-Observe Loop
        for loop_idx in range(10):
            compacted = self.context_window.compact(messages)
            content_accum = []
            tool_calls_accum = []
            
            # Consume the async generator stream from LLMCaller
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
            
            # Record reasoning in messages
            messages.append({"role": "assistant", "content": thought, "tool_calls": tool_calls_accum})

            if not tool_calls_accum:
                # Direct response to user
                if thought:
                    await add_message(self.db, self.session_id, "assistant", thought)
                yield {"type": "completed", "content": thought}
                break

            # Handle Actions
            for tool_call in tool_calls_accum:
                func_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                tc_id = tool_call["id"]
                
                yield {"type": "tool_call", "id": tc_id, "name": func_name, "arguments": args}

                # Destructive commands approval check
                from agentcore.governance import check_destructive
                if await check_destructive(func_name, args):
                    yield {"type": "approval_required", "id": tc_id, "name": func_name, "arguments": args}
                    # Pause loop wait for approval
                    return

                # Execute action
                if func_name == "delegate_to_agent":
                    agent_name = args["agent_name"]
                    task_text = args["task"]
                    
                    if agent_name not in self.workers:
                        res_str = f"Error: Agent '{agent_name}' not found."
                    else:
                        worker = self.workers[agent_name]
                        try:
                            # Run worker isolated loop
                            worker_res = await worker.run(task_text, self.session_id, context=self.context)
                            res_str = self.context_window.format_agent_result(agent_name, task_text, worker_res)
                        except Exception as e:
                            res_str = f"Error executing worker {agent_name}: {str(e)}"
                    
                    messages.append({"role": "tool", "tool_call_id": tc_id, "name": func_name, "content": res_str})
                    yield {"type": "tool_result", "id": tc_id, "result": res_str}
                    
                elif func_name == "create_mcp_agent":
                    # Register dynamically
                    name = args["name"]
                    desc = args["description"]
                    # Add to registry
                    self.workers[name] = MCPAgent(name) # Stubs it
                    res_str = f"Agent '{name}' created successfully for '{desc}'."
                    messages.append({"role": "tool", "tool_call_id": tc_id, "name": func_name, "content": res_str})
                    yield {"type": "tool_result", "id": tc_id, "result": res_str}
