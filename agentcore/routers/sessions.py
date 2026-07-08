"""
AgentCore Sessions Router — Session CRUD, A2A linking, tool toggles, BYOK config
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from agentcore.config import get_settings
from agentcore.database import *
from agentcore.auth import *
from agentcore.schema import *
from agentcore.utils import *
from agentcore.tools import get_tool_registry

settings = get_settings()

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])

@sessions_router.post("/", status_code=201)
async def create_session(
    req: SessionCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime

    title = f"Session {datetime.utcnow().strftime('%d %b, %H:%M')}"
    if req.name and req.name != "New Session":
        title = req.name

    # Build session-level BYOK config if provided
    session_byok = None
    if req.api_key:
        session_byok = {
            "provider": req.api_provider,
            "model": req.api_model or req.model,
            "api_key": req.api_key,
            "base_url": req.api_base_url,
            "temperature": req.api_temperature,
            "top_p": req.api_top_p,
            "max_tokens": req.api_max_tokens,
        }

    # All tools enabled by default
    all_tool_names = get_tool_registry().get_all_names()

    # Pre-register the built-in local host PC MCP server
    default_mcp_servers = [
        {"name": "filesystem-mcp", "type": "builtin", "description": "Read, write, search, and manage local files"},
        {"name": "bash-exec-mcp", "type": "builtin", "description": "Execute shell commands (PowerShell/bash)"},
        {"name": "python-exec-mcp", "type": "builtin", "description": "Run arbitrary Python code snippets"},
        {"name": "git-mcp", "type": "builtin", "description": "Manage local git repositories"},
        {"name": "github-mcp", "type": "builtin", "description": "GitHub API integration"},
        {"name": "web-fetch-mcp", "type": "builtin", "description": "Fetch web pages and extract text"},
        {"name": "web-search-mcp", "type": "builtin", "description": "Search the web via DuckDuckGo"},
        {"name": "sqlite-mcp", "type": "builtin", "description": "Query and manage local SQLite databases"},
        {"name": "memory-mcp", "type": "builtin", "description": "Store and recall key-value facts"},
        {"name": "image-gen-mcp", "type": "builtin", "description": "Generate images and mockups"},
        {"name": "project-ops-mcp", "type": "builtin", "description": "Workspace diagnostics, API rate limit audits, and code verification"},
    ]

    session = SessionModel(
        tenant_id=user.tenant_id, user_id=user.user_id,
        title=title, active_model_id=req.model or settings.default_model,
        system_prompt=req.system_prompt,
        meta={
            "a2a_links": [],
            "byok_config": session_byok,
            "enabled_tools": all_tool_names,
            "mcp_servers": default_mcp_servers
        },
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "name": session.title, "tenant_id": session.tenant_id}

@sessions_router.get("/")
async def list_sessions(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.tenant_id == user.tenant_id)
        .order_by(SessionModel.created_at.desc()).limit(50)
    )
    return {
        "sessions": [
            {
                "id": s.id, "name": s.name, "model": s.model,
                "created_at": s.created_at.isoformat(),
                "a2a_links": (s.meta or {}).get("a2a_links", []),
            }
            for s in result.scalars().all()
        ]
    }

@sessions_router.post("/{session_id}/link")
async def link_session(
    session_id: str,
    req: Dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, user)
    target_id = req.get("target_session_id")
    if not target_id:
        raise HTTPException(400, "target_session_id required")
    meta = dict(session.meta or {})
    a2a_links = list(meta.get("a2a_links", []))
    if target_id not in a2a_links:
        a2a_links.append(target_id)
    meta["a2a_links"] = a2a_links
    session.meta = meta
    db.add(session)
    await db.commit()
    return {"a2a_links": a2a_links}

@sessions_router.delete("/{session_id}/link/{target_id}")
async def unlink_session(
    session_id: str,
    target_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, user)
    meta = dict(session.meta or {})
    a2a_links = [tid for tid in meta.get("a2a_links", []) if tid != target_id]
    meta["a2a_links"] = a2a_links
    session.meta = meta
    db.add(session)
    await db.commit()
    return {"a2a_links": a2a_links}

@sessions_router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    msgs = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at)
    )
    return {
        "id": session.id, "name": session.name, "model": session.model,
        "a2a_links": (session.meta or {}).get("a2a_links", []),
        "enabled_tools": (session.meta or {}).get("enabled_tools", []),
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in msgs.scalars().all()
        ],
    }

@sessions_router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # Remove from other sessions' a2a_links
    other_result = await db.execute(
        select(SessionModel).where(
            and_(
                SessionModel.tenant_id == user.tenant_id,
                SessionModel.user_id == user.user_id,
                SessionModel.id != session_id,
            )
        )
    )
    for other in other_result.scalars().all():
        meta = dict(other.meta or {})
        a2a_links = [tid for tid in meta.get("a2a_links", []) if tid != session_id]
        meta["a2a_links"] = a2a_links
        other.meta = meta
        db.add(other)

    await db.execute(MessageModel.__table__.delete().where(MessageModel.session_id == session_id))
    await db.execute(TaskModel.__table__.delete().where(TaskModel.session_id == session_id))
    await db.execute(ToolCallModel.__table__.delete().where(ToolCallModel.session_id == session_id))
    await db.execute(ApprovalModel.__table__.delete().where(ApprovalModel.tenant_id == user.tenant_id))
    await db.delete(session)
    await db.commit()
    return {"deleted": True}

@sessions_router.patch("/{session_id}")
async def rename_session(
    session_id: str,
    req: Dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, user)
    new_name = req.get("name", "").strip()
    if new_name:
        session.title = new_name
        db.add(session)
        await db.commit()
    return {"id": session.id, "name": session.title}


# =============================================================================
# TOOL TOGGLES (UI-managed per session)
# =============================================================================

@sessions_router.get("/{session_id}/tools")
async def get_session_tools(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the list of enabled tools for this session, plus the full catalog."""
    session = await _get_owned_session(db, session_id, user)
    enabled = (session.meta or {}).get("enabled_tools")
    catalog = get_tool_registry().get_catalog()
    # If enabled_tools not set yet, all are enabled
    if enabled is None:
        enabled = [t["name"] for t in catalog]
    return {
        "enabled_tools": enabled,
        "catalog": catalog,
    }

@sessions_router.patch("/{session_id}/tools")
async def update_session_tools(
    session_id: str,
    req: Dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle tools on/off for a session. Body: {"enabled_tools": ["web_search", ...]}"""
    session = await _get_owned_session(db, session_id, user)
    enabled = req.get("enabled_tools")
    if enabled is None:
        raise HTTPException(400, "enabled_tools list required")
    meta = dict(session.meta or {})
    meta["enabled_tools"] = list(enabled)
    session.meta = meta
    db.add(session)
    await db.commit()
    return {"enabled_tools": enabled}


# =============================================================================
# SESSION CONFIG (BYOK)
# =============================================================================

@sessions_router.get("/{session_id}/config")
async def get_session_config(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    byok_config = (session.meta or {}).get("byok_config")
    has_key = bool(byok_config and byok_config.get("api_key"))
    model_priorities = (session.meta or {}).get("model_priorities", [])

    return {
        "model": session.active_model_id or settings.default_model,
        "model_priorities": model_priorities,
        "api_key_masked": "********" if has_key else "",
        "byok_config": byok_config,
    }

@sessions_router.patch("/{session_id}/config")
async def update_session_config(
    session_id: str,
    req: Dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, user)
    meta = dict(session.meta or {})
    
    if "model_priorities" in req:
        meta["model_priorities"] = req["model_priorities"]
        # Maintain sync with active_model_id as the first element in priorities
        if req["model_priorities"]:
            session.active_model_id = req["model_priorities"][0]
        
    if "model" in req:
        session.active_model_id = req["model"]
        
    session.meta = meta
    db.add(session)
    await db.commit()
    return {
        "model": session.active_model_id,
        "model_priorities": meta.get("model_priorities", [])
    }
