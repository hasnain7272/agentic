"""
API Router - Main API Router Aggregator

Aggregates all REST API routers into a single FastAPI router.
"""
from fastapi import APIRouter

# Import existing routers
from src.api.rest.routers.auth import router as auth_router
from src.api.rest.routers.sessions import router as sessions_router
from src.api.rest.routers.tasks import router as tasks_router
from src.api.rest.routers.workspace import router as workspace_router
from src.api.rest.routers.chat import router as chat_router
from src.api.rest.routers.mcp_stdio import router as mcp_stdio_router
from src.api.rest.routers.mcp_plugins import router as mcp_plugins_router
from src.api.rest.routers.mcp_schemas import router as mcp_schemas_router
from src.api.rest.routers.folders import router as folders_router

# Import new minimal routers
from src.api.rest.routers.tools import router as tools_router
from src.api.rest.routers.governance import router as governance_router
from src.api.rest.routers.health import router as health_router

# Main API router
api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
api_router.include_router(tasks_router)
api_router.include_router(workspace_router)
api_router.include_router(chat_router)
api_router.include_router(mcp_stdio_router)
api_router.include_router(mcp_plugins_router)
api_router.include_router(mcp_schemas_router)
api_router.include_router(folders_router)

# New minimal routers
api_router.include_router(health_router)
api_router.include_router(tools_router)
api_router.include_router(governance_router)


# Health check at root
@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "AgentCore"}


__all__ = ["api_router"]