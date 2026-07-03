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

tools_router = APIRouter(prefix="/tools", tags=["tools"])

@tools_router.get("/")
async def list_tools(
    category: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    return registry.get_schemas(category)

@tools_router.get("/categories")
async def get_categories(user: TokenPayload = Depends(get_current_user)):
    registry = get_tool_registry()
    return registry.get_categories()

@tools_router.get("/openai-functions")
async def get_openai_functions(
    category: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    return registry.get_openai_functions(category)

@tools_router.post("/execute")
async def execute_tool(
    req: ToolExecuteRequest,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    args = req.arguments.copy()
    args["context"] = {"user_id": user.user_id, "tenant_id": user.tenant_id}
    result = await registry.execute(req.name, args)
    return {"success": result.success, "data": result.data, "error": result.error}

@tools_router.post("/discover-mcp")
async def discover_mcp_tools(user: TokenPayload = Depends(get_current_user)):
    registry = get_tool_registry()
    count = await registry.discover_mcp_tools()
    return {"discovered": count}
