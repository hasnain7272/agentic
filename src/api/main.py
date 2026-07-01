"""
API Package - REST API and WebSocket Endpoints

Provides FastAPI application with all endpoints for:
- Authentication
- Sessions and tasks
- Agent execution
- Tools and MCP
- Governance and approval
- WebSocket for real-time updates
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from src.auth.middleware import AuthMiddleware, TenantContextMiddleware

settings = get_settings()

app = FastAPI(
    title="AgentCore API",
    description="Minimalist agentic runtime API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(TenantContextMiddleware)

# Health check (public)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agentcore"}

@app.get("/api/v1/health")
async def api_health_check():
    return {"status": "healthy", "service": "agentcore", "version": "1.0.0"}

# Include routers
from src.api.rest.routers import auth, sessions, tasks, tools, mcp, governance, approvals

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["mcp"])
app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["approvals"])

# WebSocket
from src.api.websocket import router as ws_router
app.include_router(ws_router, prefix="/api/v1/ws", tags=["websocket"])

# Mount static files for UI (in production)
if settings.ui_dist_path:
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=settings.ui_dist_path, html=True), name="ui")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    return app


# Export for ASGI servers
__all__ = ["app", "create_app"]