from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.db.session import AsyncSessionLocal
from src.infrastructure.db.models.session_model import SessionModel

class UpdateAgentMemoryTool(BaseTool):
    name = "update_agent_memory"
    description = "Append or update Codex Persistent Memory to remember facts, API rules, or plans across iterations."
    parameters = [
        ToolParameter(
            name="memory_update",
            type="string",
            description="The new context or facts to append to your persistent memory block."
        ),
        ToolParameter(
            name="action",
            type="string",
            description="Whether to 'append' to existing memory or completely 'replace' it.",
            required=False
        )
    ]

    async def execute(self, session_id: str, **kwargs) -> Any:
        update_text = kwargs.get("memory_update", "")
        action = kwargs.get("action", "append")

        if not update_text:
            return "Error: memory_update text is required."

        try:
            async with AsyncSessionLocal() as db:
                from src.infrastructure.db.session import _is_postgres
                stmt = select(SessionModel).where(SessionModel.id == session_id)
                if _is_postgres:
                    stmt = stmt.with_for_update()
                result = await db.execute(stmt)
                session = result.scalar_one_or_none()
                if not session:
                    return "Error: Session not found in DB."

                ctx_dict = dict(session.context or {})
                existing_memory = ctx_dict.get("agent_memory", "")

                if action == "append" and existing_memory:
                    new_memory = f"{existing_memory}\n- {update_text}"
                else:
                    new_memory = update_text

                ctx_dict["agent_memory"] = new_memory
                session.context = ctx_dict

                await db.commit()
                return f"Successfully updated Agent Memory. Current payload size: {len(new_memory)} characters."
        except Exception as e:
            return f"Failed to update memory: {str(e)}"
