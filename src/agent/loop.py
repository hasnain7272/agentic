"""
Agent Loop - Core Agentic Orchestration Engine

Implements the main agent loop: perceive → plan → act → observe.
Handles tool calling, streaming, and state management.
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from src.tools.registry import get_tool_registry
from src.tools.schemas import ToolResult, ToolSchema
from src.governance import get_governance_engine, GovernanceApprovalRequiredError
from src.auth.jwt import TokenPayload
from src.config.settings import get_settings
from src.db.session import get_db
from src.db.models import SessionModel, TaskModel, ToolCallModel, MessageModel

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent execution states."""
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
    """Context passed to agent during execution."""
    session_id: str
    task_id: str
    user_id: str
    tenant_id: str
    organization_id: Optional[str] = None
    user_role: str = "developer"
    risk_mode: str = "auto"
    workspace_path: str = "/workspace"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state
    state: AgentState = AgentState.IDLE
    current_step: int = 0
    max_steps: int = 20
    
    # History
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # Streaming
    stream_callback: Optional[Callable] = None
    
    def to_session_dict(self) -> Dict[str, Any]:
        """Convert to session-compatible dict."""
        return {
            "id": self.session_id,
            "user_role": self.user_role,
            "tenant_id": self.tenant_id,
            "risk_mode": self.risk_mode,
        }


class AgentLoop:
    """Main agent orchestration loop."""
    
    def __init__(
        self,
        llm_client: Any = None,
        system_prompt: str = None,
        tool_registry: Any = None,
    ):
        self.llm_client = llm_client
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.tool_registry = tool_registry or get_tool_registry()
        self.governance = get_governance_engine()
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    def _default_system_prompt(self) -> str:
        """Default system prompt for the agent."""
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
        """
        Run the agent loop.
        
        Yields events:
        - {"type": "state_change", "state": AgentState}
        - {"type": "thinking", "content": "..."}
        - {"type": "tool_call", "tool": name, "arguments": {...}}
        - {"type": "tool_result", "tool": name, "result": ToolResult}
        - {"type": "approval_required", "tool": name, "message": "..."}
        - {"type": "message", "role": "assistant", "content": "..."}
        - {"type": "done", "result": "..."}
        - {"type": "error", "error": "..."}
        """
        context.state = AgentState.THINKING
        yield {"type": "state_change", "state": context.state.value}
        
        # Add user message to history
        context.messages.append({"role": "user", "content": user_message})
        
        # Persist user message
        await self._persist_message(context, "user", user_message)
        
        try:
            while context.current_step < context.max_steps:
                context.current_step += 1
                
                # Get LLM response
                context.state = AgentState.THINKING
                yield {"type": "state_change", "state": context.state.value}
                
                response = await self._call_llm(context)
                
                if not response:
                    yield {"type": "error", "error": "Empty response from LLM"}
                    break
                
                # Check if response contains tool calls
                tool_calls = self._extract_tool_calls(response)
                
                if tool_calls:
                    # Execute tools
                    for tool_call in tool_calls:
                        yield await self._execute_tool(context, tool_call)
                else:
                    # Just a message response
                    context.messages.append({"role": "assistant", "content": response})
                    await self._persist_message(context, "assistant", response)
                    yield {"type": "message", "role": "assistant", "content": response}
                    break
            
            if context.current_step >= context.max_steps:
                yield {"type": "error", "error": "Max steps reached"}
            
            context.state = AgentState.COMPLETED
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "done", "result": "Task completed"}
            
        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            context.state = AgentState.ERROR
            yield {"type": "state_change", "state": context.state.value}
            yield {"type": "error", "error": str(e)}
    
    async def _call_llm(self, context: AgentContext) -> str:
        """Call LLM with current context."""
        if not self.llm_client:
            # Mock response for testing
            return "I'll help you with that task. Let me start by exploring the workspace."
        
        # Prepare messages
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add available tools
        tools = self.tool_registry.get_openai_functions()
        if tools:
            # Add tool definitions to system prompt or use function calling
            pass
        
        # Add conversation history
        messages.extend(context.messages[-20:])  # Limit history
        
        # Call LLM
        try:
            response = await self.llm_client.chat.completions.create(
                model=get_settings().llm_model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.1,
                max_tokens=4096,
            )
            
            message = response.choices[0].message
            
            if message.tool_calls:
                # Convert to our format
                return json.dumps([{
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                } for tc in message.tool_calls])
            
            return message.content or ""
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"Error calling LLM: {e}"
    
    def _extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response."""
        try:
            # Try parsing as JSON array of tool calls
            data = json.loads(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "name" in data:
                return [data]
        except json.JSONDecodeError:
            pass
        
        # Try to find tool calls in text (for non-function-calling models)
        # This is a simple pattern - real implementation would be more robust
        return []
    
    async def _execute_tool(
        self,
        context: AgentContext,
        tool_call: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single tool call with governance."""
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})
        
        # Add context to arguments
        arguments["context"] = {
            "session_id": context.session_id,
            "task_id": context.task_id,
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
        }
        
        # Governance check
        try:
            session_obj = type('Session', (), context.to_session_dict())()
            self.governance.assert_action_allowed(
                session_obj, tool_name, arguments
            )
        except GovernanceApprovalRequiredError as e:
            # Request approval
            context.state = AgentState.WAITING_APPROVAL
            approval_event = {
                "type": "approval_required",
                "tool": tool_name,
                "arguments": arguments,
                "message": str(e),
                "approval_id": str(uuid.uuid4()),
            }
            
            # Persist pending tool call
            await self._persist_tool_call(
                context, tool_name, arguments, "pending_approval"
            )
            
            return approval_event
        
        # Execute tool
        context.state = AgentState.EXECUTING
        yield {"type": "state_change", "state": context.state.value}
        
        yield {"type": "tool_call", "tool": tool_name, "arguments": arguments}
        
        result = await self.tool_registry.execute(tool_name, arguments)
        
        # Record tool call
        context.tool_calls.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": result.model_dump(),
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        await self._persist_tool_call(
            context, tool_name, arguments, "completed" if result.success else "failed", result
        )
        
        # Add result to conversation
        context.messages.append({
            "role": "tool",
            "name": tool_name,
            "content": result.to_llm_content(),
        })
        
        yield {"type": "tool_result", "tool": tool_name, "result": result.model_dump()}
        
        return {"type": "tool_result", "tool": tool_name, "result": result.model_dump()}
    
    async def _persist_message(
        self,
        context: AgentContext,
        role: str,
        content: str,
    ) -> None:
        """Persist message to database."""
        try:
            async for db in get_db():
                msg = MessageModel(
                    session_id=context.session_id,
                    task_id=context.task_id,
                    role=role,
                    content=content,
                )
                db.add(msg)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")
    
    async def _persist_tool_call(
        self,
        context: AgentContext,
        tool_name: str,
        arguments: Dict[str, Any],
        status: str,
        result: ToolResult = None,
    ) -> None:
        """Persist tool call to database."""
        try:
            async for db in get_db():
                tool_call = ToolCallModel(
                    session_id=context.session_id,
                    task_id=context.task_id,
                    name=tool_name,
                    arguments=arguments,
                    status=status,
                    result=result.data if result and result.success else None,
                    error=result.error if result and not result.success else None,
                )
                db.add(tool_call)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist tool call: {e}")


# Convenience function for simple execution
async def run_agent(
    session_id: str,
    task_id: str,
    user_message: str,
    user: TokenPayload,
    llm_client: Any = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run agent with minimal setup."""
    context = AgentContext(
        session_id=session_id,
        task_id=task_id,
        user_id=user.sub,
        tenant_id=user.tenant_id,
        organization_id=user.organization_id,
        user_role=user.role,
        risk_mode="auto",
    )
    
    agent = AgentLoop(llm_client=llm_client)
    
    async for event in agent.run(context, user_message):
        yield event