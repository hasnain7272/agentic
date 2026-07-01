"""
Tools Router - Tool Management Endpoints

Provides endpoints for listing, discovering, and executing tools.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from src.tools.registry import get_tool_registry, ToolRegistry
from src.tools.schemas import ToolSchema, ToolResult
from src.api.rest.dependencies import get_current_user_dep, TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


class ToolExecuteResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ToolCatalogResponse(BaseModel):
    name: str
    description: str
    category: str
    origin: str
    requires_sandbox: bool
    parameters: List[Dict[str, Any]]


@router.get("/", response_model=List[ToolSchema])
async def list_tools(
    category: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """List all available tools, optionally filtered by category."""
    registry = get_tool_registry()
    schemas = registry.get_schemas(category)
    return schemas


@router.get("/catalog", response_model=List[ToolCatalogResponse])
async def get_tool_catalog(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get tool catalog with metadata for UI."""
    from src.tools.registry import get_tool_catalog
    catalog = get_tool_catalog()
    return catalog


@router.get("/openai-functions", response_model=List[Dict[str, Any]])
async def get_openai_functions(
    category: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get tools in OpenAI function calling format."""
    registry = get_tool_registry()
    return registry.get_openai_functions(category)


@router.get("/anthropic-tools", response_model=List[Dict[str, Any]])
async def get_anthropic_tools(
    category: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get tools in Anthropic tool format."""
    registry = get_tool_registry()
    return registry.get_anthropic_tools(category)


@router.get("/categories", response_model=List[str])
async def get_categories(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get all tool categories."""
    registry = get_tool_registry()
    return registry.get_categories()


@router.get("/{tool_name}", response_model=ToolSchema)
async def get_tool(
    tool_name: str,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get a specific tool schema."""
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}",
        )
    
    return tool.schema


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    request: ToolExecuteRequest,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Execute a tool with given arguments."""
    registry = get_tool_registry()
    
    # Add user context to arguments
    arguments = request.arguments.copy()
    arguments["context"] = {
        "user_id": current_user.sub,
        "tenant_id": current_user.tenant_id,
        "organization_id": getattr(current_user, "organization_id", None),
    }
    
    result = await registry.execute(request.name, arguments)
    
    return ToolExecuteResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        metadata=result.metadata,
    )


@router.post("/discover-mcp")
async def discover_mcp_tools(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Discover and register tools from MCP clients."""
    registry = get_tool_registry()
    count = await registry.discover_mcp_tools()
    return {"discovered": count, "message": f"Discovered {count} MCP tools"}