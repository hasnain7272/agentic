"""
Health Router - Health Check Endpoints

Provides health check endpoints for load balancers and monitoring.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.api.rest.dependencies import get_db
from src.config.settings import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "AgentCore", "version": "1.0.0"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check including database connectivity."""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    
    settings = get_settings()
    
    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status,
        "environment": settings.environment,
        "version": "1.0.0",
    }


@router.get("/live")
async def liveness_check():
    """Liveness check (for Kubernetes)."""
    return {"status": "alive"}