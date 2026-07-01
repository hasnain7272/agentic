"""Server-Sent Events for real-time frontend UI sync."""
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import get_current_user_dep, TokenPayload, get_db
from src.infrastructure.db.models.session_model import SessionModel
from src.infrastructure.queue.redis_streams_broker import get_streams_broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["Stream"])

async def event_generator(request: Request, session_id: str, user: TokenPayload) -> AsyncGenerator[str, None]:
    """Yields SSE events from the memory broker to the client."""
    broker = await get_streams_broker()
    
    # We create a unique queue for this connection
    queue = asyncio.Queue()
    
    async def handler(msg):
        await queue.put(msg)
        
    topic = f"state:{session_id}"
    # Subscribe in background (broker subscribe is a long-running loop).
    listener_task = asyncio.create_task(
        broker.subscribe(topic, f"sse-{user.tenant_id}:{id(queue)}", handler)
    )
    logger.info(f"[SSE] Client connected to {topic}")
    
    try:
        while True:
            if await request.is_disconnected():
                break
                
            try:
                # Wait for a message with a timeout to send ping keepalives
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                data = msg.data
                
                # Format as SSE
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive
                yield ": ping\n\n"
                
    except asyncio.CancelledError:
        pass
    finally:
        logger.info(f"[SSE] Client disconnected from {topic}")
        listener_task.cancel()
        try:
            await listener_task
        except Exception:
            pass

@router.get("/state")
async def stream_state(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user_dep),
):
    """
    Subscribe to real-time state changes (Capabilities, Tools, Tasks, Workspace).
    This replaces polling and optimistic UI updates, making the UX ultra-premium.
    """
    # Tenant isolation: ensure the requested session belongs to the tenant.
    result = await db.execute(
        select(SessionModel.id).where(
            and_(
                SessionModel.id == session_id,
                SessionModel.tenant_id == user.tenant_id,
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        event_generator(request, session_id, user),
        media_type="text/event-stream"
    )
