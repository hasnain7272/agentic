"""Kernel API gateway — Ultra-premium production gateway."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from src.api.rest.config.cors import setup_cors
from src.api.rest.routes import include_routers
from src.infrastructure.db.session import init_db
from src.infrastructure.runtime.config import APP_VERSION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_db()

    # Initialize tracing
    from src.infrastructure.observability.tracing import instrument_fastapi
    instrument_fastapi(app)

    # Restore persisted MCP Stdio Servers
    from src.services.mcp.stdio_manager import stdio_mcp_manager
    logger.info("Restoring persisted MCP Stdio Servers...")
    await stdio_mcp_manager.restore_persisted_servers()

    # Hybrid mode: Start worker in same process
    hybrid_mode = os.environ.get("HYBRID_MODE", "true").lower() == "true"
    worker_task = None

    if hybrid_mode:
        from src.services.agent_loop.worker_main import start_worker
        logger.info("🚀 Gateway in HYBRID MODE")
        worker_task = asyncio.create_task(start_worker(init_database=False))
    else:
        logger.info("📡 Gateway in STATELESS MODE")

    yield

    if worker_task:
        logger.info("Shutting down worker...")
        worker_task.cancel()
        try:
            # Give worker 5 seconds to clean up
            await asyncio.wait_for(worker_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            logger.warning("Worker shutdown timed out or was cancelled.")
        except Exception as e:
            logger.error(f"Error during worker shutdown: {e}")

    logger.info("Gateway shutdown.")


# Create FastAPI app
is_prod = os.environ.get("ENVIRONMENT") == "production"
app = FastAPI(
    title="Project Kernel Runtime",
    version=APP_VERSION,
    docs_url=None if is_prod else "/api/docs",
    redoc_url=None if is_prod else "/api/redoc",
    lifespan=lifespan,
)

# Setup CORS and routes
setup_cors(app)
include_routers(app)


from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler to ensure JSON response."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal Server Error",
            "detail": str(exc) if not is_prod else "Contact support"
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    from src.infrastructure.queue.redis_streams_broker import get_streams_broker
    broker = await get_streams_broker()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "broker": type(broker).__name__,
    }


@app.get("/api/v1/health/workers")
async def workers_health():
    """Worker health status."""
    from src.infrastructure.queue.redis_streams_broker import get_streams_broker
    broker = await get_streams_broker()
    return {
        "broker_type": type(broker).__name__,
        "stream_count": len(getattr(broker, "_streams", {})),
    }


@app.get("/api/v1/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from src.infrastructure.observability.metrics import metrics
    return {"metrics": metrics.get_metrics()}


# No SPA static files served by the backend anymore. 
# The UI is exclusively hosted on GitHub Pages or external CDNs.

