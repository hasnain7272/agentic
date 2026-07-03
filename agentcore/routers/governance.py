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

governance_router = APIRouter(prefix="/governance", tags=["governance"])

@governance_router.post("/check")
async def check_policy(
    req: PolicyCheckRequest,
    user: TokenPayload = Depends(get_current_user),
):
    engine = get_governance_engine()
    decision = engine.evaluate(
        type("Ctx", (), {"user_role": user.role, "tenant_id": user.tenant_id})(),
        req.action, req.resource, req.context,
    )
    return {"allowed": decision.allowed, "reason": decision.reason}

@governance_router.get("/roles")
async def list_roles(user: TokenPayload = Depends(get_current_user)):
    from agentcore.governance import Role, ROLE_TOOL_CATEGORIES
    return [
        {"name": role.value, "categories": cats}
        for role, cats in ROLE_TOOL_CATEGORIES.items()
    ]
