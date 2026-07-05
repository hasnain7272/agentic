"""
Memory MCP — Session and User Scoped Memories
"""
import logging
from agentcore.mcps import register_mcp

logger = logging.getLogger(__name__)

@register_mcp
class MemoryMCP:
    name = "memory-mcp"
    description = "Store and recall memories in 2 scopes: session-specific and user-specific."
    TOOLS = {
        "session_memory_store":  {"params": {"key": "string", "value": "string"}, "desc": "Store a memory scoped to the current session"},
        "session_memory_recall": {"params": {"key": "string"}, "desc": "Retrieve a session-scoped memory by key"},
        "user_memory_store":     {"params": {"key": "string", "value": "string"}, "desc": "Store a memory scoped to the current user (cross-session)"},
        "user_memory_recall":    {"params": {"key": "string"}, "desc": "Retrieve a user-scoped memory by key"},
        "list_memories":         {"desc": "List all stored session and user memories"},
    }

    async def call_tool(self, name: str, args: dict, **kwargs) -> dict:
        session_id = kwargs.get("session_id")
        context = kwargs.get("context")
        user_id = context.user_id if context else None
        
        from agentcore.database import get_db_manager, SessionModel, UserModel
        from sqlalchemy import select
        
        db_manager = get_db_manager()
        
        if name == "session_memory_store":
            if not session_id:
                return {"error": "No active session"}
            k, v = args["key"], args["value"]
            async with db_manager.session() as db:
                res = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
                session = res.scalar_one_or_none()
                if session:
                    meta = dict(session.meta or {})
                    memories = dict(meta.get("memories") or {})
                    memories[k] = v
                    meta["memories"] = memories
                    session.meta = meta
                    db.add(session)
                    await db.commit()
                    return {"key": k, "scope": "session", "status": "stored"}
            return {"error": "Session not found"}
            
        elif name == "session_memory_recall":
            if not session_id:
                return {"value": None}
            k = args["key"]
            async with db_manager.session() as db:
                res = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
                session = res.scalar_one_or_none()
                if session and session.meta:
                    memories = session.meta.get("memories") or {}
                    return {"key": k, "scope": "session", "value": memories.get(k)}
            return {"value": None}
            
        elif name == "user_memory_store":
            if not user_id:
                return {"error": "No active user"}
            k, v = args["key"], args["value"]
            async with db_manager.session() as db:
                res = await db.execute(select(UserModel).where(UserModel.id == user_id))
                user = res.scalar_one_or_none()
                if user:
                    settings = dict(user.settings or {})
                    memories = dict(settings.get("memories") or {})
                    memories[k] = v
                    settings["memories"] = memories
                    user.settings = settings
                    db.add(user)
                    await db.commit()
                    return {"key": k, "scope": "user", "status": "stored"}
            return {"error": "User not found"}
            
        elif name == "user_memory_recall":
            if not user_id:
                return {"value": None}
            k = args["key"]
            async with db_manager.session() as db:
                res = await db.execute(select(UserModel).where(UserModel.id == user_id))
                user = res.scalar_one_or_none()
                if user and user.settings:
                    memories = user.settings.get("memories") or {}
                    return {"key": k, "scope": "user", "value": memories.get(k)}
            return {"value": None}
            
        elif name == "list_memories":
            session_mem = {}
            user_mem = {}
            async with db_manager.session() as db:
                if session_id:
                    res = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
                    session = res.scalar_one_or_none()
                    if session and session.meta:
                        session_mem = session.meta.get("memories") or {}
                if user_id:
                    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
                    user = res.scalar_one_or_none()
                    if user and user.settings:
                        user_mem = user.settings.get("memories") or {}
            return {"session_memories": session_mem, "user_memories": user_mem}
            
        raise ValueError(f"Unknown tool: {name}")
