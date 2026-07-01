"""
API REST Routers Package

Consolidated router exports for the AgentCore API.
"""
from src.api.rest.routers.auth import router as auth_router
from src.api.rest.routers.health import router as health_router
from src.api.rest.routers.sessions import router as sessions_router
from src.api.rest.routers.tasks import router as tasks_router
from src.api.rest.routers.tools import router as tools_router
from src.api.rest.routers.mcp_plugins import router as mcp_router
from src.api.rest.routers.governance import router as governance_router

# Placeholder for approvals router (to be created)
from fastapi import APIRouter
approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])

__all__ = [
    "auth_router",
    "health_router",
    "sessions_router",
    "tasks_router",
    "tools_router",
    "mcp_router",
    "governance_router",
    "approvals_router",
]