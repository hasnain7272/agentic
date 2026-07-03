"""
AgentCore API - Minimalist App Factory
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agentcore.config import get_settings
from agentcore.auth import AuthMiddleware
from agentcore.routers import all_routers

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="AgentCore API",
        description="Modular Minimalist agentic runtime",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware
    app.add_middleware(AuthMiddleware)

    # Mount dynamically discovered routers
    prefix = settings.api_prefix
    for router in all_routers:
        app.include_router(router, prefix=prefix)

    # WebSocket routes
    try:
        from agentcore.websocket import router as ws_router
        app.include_router(ws_router, prefix=f"{prefix}/ws")
    except ImportError:
        pass

    # Root health
    @app.get("/health")
    async def root_health():
        return {"status": "healthy"}

    # Startup: init DB
    @app.on_event("startup")
    async def on_startup():
        from agentcore.database import init_db
        await init_db()
        logger.info("AgentCore started")

    return app
