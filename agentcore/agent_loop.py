"""
AgentCore Agent Loop - Facade
"""
from typing import Any, AsyncGenerator, Dict
from agentcore.auth import TokenPayload
from agentcore.loop.state import AgentState, AgentContext
from agentcore.loop.llm import LLMCaller
from agentcore.loop.orchestrator import AgentLoop
from agentcore.loop.worker import process_task_event, process_tool_event

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
