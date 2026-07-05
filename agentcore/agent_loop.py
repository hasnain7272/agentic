"""
AgentCore Agent Loop runner adapter for WebSocket task stream.
"""
import logging
from typing import AsyncGenerator, Dict, Any
from agentcore.database import get_db
from agentcore.loop.state import AgentContext
from agentcore.loop.agents import ManagementAgent

logger = logging.getLogger(__name__)


async def run_agent_stream(
    session_id: str,
    task_id: str,
    user_message: str,
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Wraps ManagementAgent coordinator run generator for routers/tasks.py WS stream."""
    logger.info(f"Starting agent loop stream for session {session_id}, task {task_id}")
    
    context = AgentContext(
        session_id=session_id,
        task_id=task_id,
        user_id=user_id,
        tenant_id=tenant_id,
        user_role=user_role
    )
    
    async for db in get_db():
        agent = ManagementAgent(session_id=session_id, db_session=db, context=context)
        try:
            async for event in agent.run(user_message):
                yield event
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"Error in agent stream: {e}")
            yield {"type": "error", "error": str(e)}
        break
