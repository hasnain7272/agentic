"""
AgentCore - API Utilities
"""
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from agentcore.database import SessionModel, UserModel, TenantModel
from agentcore.auth import TokenPayload
from agentcore.config import get_settings

settings = get_settings()

__all__ = [
    '_fallback_session_name',
    '_get_owned_session',
    '_get_db_user',
    '_update_meta_config',
]


def _fallback_session_name(message: str) -> str:
    """Generate a fallback session name from message without LLM."""
    msg = message.strip()
    if not msg:
        return "New Session"
    import re
    sentences = re.split(r'[.!?]+', msg)
    first_sentence = sentences[0].strip() if sentences else msg
    if len(first_sentence) > 50:
        first_sentence = first_sentence[:47] + "..."
    if first_sentence:
        first_sentence = first_sentence[0].upper() + first_sentence[1:]
    return first_sentence or "New Session"

async def _get_owned_session(db: AsyncSession, session_id: str, user: TokenPayload) -> SessionModel:
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return session

async def _get_db_user(db: AsyncSession, user_id: str) -> UserModel:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found")
    return db_user

async def _update_meta_config(db: AsyncSession, user: TokenPayload, session_id: Optional[str], config_key: str, update_fn) -> Any:
    if session_id:
        session = await _get_owned_session(db, session_id, user)
        meta = dict(session.meta or {})
        items = list(meta.get(config_key, []))
        new_items = update_fn(items)
        meta[config_key] = new_items
        session.meta = meta
        db.add(session)
        await db.commit()
        return new_items
    else:
        result = await db.execute(select(TenantModel).where(TenantModel.id == user.tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        tenant_settings = dict(tenant.settings or {})
        items = list(tenant_settings.get(config_key, []))
        new_items = update_fn(items)
        tenant_settings[config_key] = new_items
        tenant.settings = tenant_settings
        db.add(tenant)
        await db.commit()
        return new_items