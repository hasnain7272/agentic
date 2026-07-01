"""Task WebSocket streaming helpers."""
import asyncio
import logging
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, select

from src.infrastructure.auth.jwt_auth import TokenPayload, decode_token
from src.infrastructure.db.models.task_model import TaskModel
from src.infrastructure.db.session import AsyncSessionLocal
from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.infrastructure.runtime.config import ALLOW_ANON_LOCAL

logger = logging.getLogger(__name__)


def resolve_stream_user(token: str | None, tenant_id: str | None) -> TokenPayload | None:
    try:
        if token:
            return decode_token(token)
    except HTTPException:
        return None
    if not ALLOW_ANON_LOCAL:
        return None
    return TokenPayload(
        tenant_id=tenant_id or "local",
        user_id="local",
        email="local@dev.local",
        role="developer",
        tier="pro",
        limits={"rpm": 60, "rph": 500},
        exp=0,
        iat=0,
        organization_id=None,
    )


async def task_belongs_to_tenant(task_id: str, tenant_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TaskModel.id).where(and_(TaskModel.id == task_id, TaskModel.tenant_id == tenant_id)))
        return result.scalar_one_or_none() is not None


async def bridge_task_stream(websocket: WebSocket, task_id: str, user: TokenPayload) -> None:
    broker = await get_streams_broker()

    async def stream_handler(msg: Any):
        try:
            data = getattr(msg, "data", msg)
            if not isinstance(data, dict):
                await websocket.send_text(str(data))
                return
            if data.get("tenant_id") and data.get("tenant_id") != user.tenant_id:
                return
            data["tenant_id"] = user.tenant_id
            await websocket.send_json(data)
        except Exception as exc:
            logger.error("[WS] Send error: %s", exc)

    listener_task = asyncio.create_task(broker.subscribe_channel(f"task_log:{task_id}", stream_handler))
    try:
        while True:
            data = await websocket.receive_text()
            if data.strip() == "\x03":
                await broker.publish(f"task_action:{task_id}", {"action": "interrupt", "tenant_id": user.tenant_id}, tenant_id=user.tenant_id)
    except WebSocketDisconnect:
        pass
    finally:
        listener_task.cancel()
