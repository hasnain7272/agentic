from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, and_, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import secrets
from pathlib import Path

from agentcore.config import get_settings
from agentcore.database import *
from agentcore.auth import *
from agentcore.schema import *
from agentcore.utils import *
from agentcore.governance import get_governance_engine
from agentcore.tools import get_tool_registry

settings = get_settings()

settings_router = APIRouter(prefix="/settings", tags=["settings"])

class BYOMConfigRequest(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    temperature: Optional[float] = 0.2
    top_p: Optional[float] = 0.95
    max_tokens: Optional[int] = 8192

@settings_router.get("/byok")
async def get_byok_settings(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_user = await _get_db_user(db, user.user_id)
    byom_configs = (db_user.settings or {}).get("byom_configs", [])
    data = []
    for cfg in byom_configs:
        data.append({
            "id": cfg.get("id"),
            "name": cfg.get("name"),
            "provider": cfg.get("provider"),
            "model": cfg.get("model"),
            "base_url": cfg.get("base_url"),
            "temperature": cfg.get("temperature"),
            "top_p": cfg.get("top_p"),
            "max_tokens": cfg.get("max_tokens"),
            "is_configured": bool(cfg.get("api_key")),
        })
    return {"status": "success", "data": data}

@settings_router.post("/byok")
async def save_byok_settings(
    req: BYOMConfigRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_user = await _get_db_user(db, user.user_id)
    user_settings = dict(db_user.settings or {})
    byom_configs = list(user_settings.get("byom_configs", []))
    
    found = False
    for i, cfg in enumerate(byom_configs):
        if cfg.get("id") == req.id:
            api_key = req.api_key if req.api_key else cfg.get("api_key", "")
            byom_configs[i] = {
                "id": req.id,
                "name": req.name,
                "provider": req.provider,
                "model": req.model,
                "api_key": api_key,
                "base_url": req.base_url,
                "temperature": req.temperature,
                "top_p": req.top_p,
                "max_tokens": req.max_tokens,
            }
            found = True
            break
    
    if not found:
        byom_configs.append({
            "id": req.id,
            "name": req.name,
            "provider": req.provider,
            "model": req.model,
            "api_key": req.api_key or "",
            "base_url": req.base_url,
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_tokens": req.max_tokens,
        })
    
    user_settings["byom_configs"] = byom_configs
    db_user.settings = user_settings
    db.add(db_user)
    await db.commit()
    return {"status": "success", "data": {"status": "success"}}

@settings_router.delete("/byok/{config_id}")
async def delete_byok_settings(
    config_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_user = await _get_db_user(db, user.user_id)
    user_settings = dict(db_user.settings or {})
    byom_configs = list(user_settings.get("byom_configs", []))
    byom_configs = [cfg for cfg in byom_configs if cfg.get("id") != config_id]
    
    user_settings["byom_configs"] = byom_configs
    db_user.settings = user_settings
    db.add(db_user)
    await db.commit()
    return {"status": "success"}
