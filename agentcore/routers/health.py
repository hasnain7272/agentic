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

health_router = APIRouter(prefix="/health", tags=["health"])

@health_router.get("/")
async def health_check():
    return {"status": "healthy", "service": "AgentCore", "version": "1.0.0"}

@health_router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status,
        "environment": settings.app_env,
    }
