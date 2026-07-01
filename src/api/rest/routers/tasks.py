"""Tenant-scoped task dispatch, listing, and streaming."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import get_broker_dep, get_current_user_dep, get_db
from src.api.rest.routers.task_stream import bridge_task_stream, resolve_stream_user, task_belongs_to_tenant
from src.domain.entities.task import TaskStatus
from src.infrastructure.auth.jwt_auth import TokenPayload
from src.infrastructure.db.models.session_model import SessionModel
from src.infrastructure.db.models.task_model import TaskModel

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    session_id: str
    description: str


async def assert_session_access(db: AsyncSession, session_id: str, user: TokenPayload) -> None:
    result = await db.execute(
        select(SessionModel.id).where(
            and_(SessionModel.id == session_id, SessionModel.tenant_id == user.tenant_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized or session not found")


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_task(
    req: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_broker_dep),
    user: TokenPayload = Depends(get_current_user_dep),
) -> Dict[str, Any]:
    await assert_session_access(db, req.session_id, user)
    task = TaskModel(tenant_id=user.tenant_id, session_id=req.session_id, description=req.description, status=TaskStatus.PENDING.value)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await broker.publish(
        "task_queue",
        {"event_type": "AGENT_THINK", "task_id": task.id, "session_id": req.session_id, "description": req.description},
        tenant_id=user.tenant_id,
    )
    return {"status": "accepted", "task_id": task.id}


@router.get("/")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user_dep),
) -> Dict[str, Any]:
    result = await db.execute(select(TaskModel).where(TaskModel.tenant_id == user.tenant_id).order_by(TaskModel.created_at.desc()).limit(50))
    return {
        "tasks": [
            {"id": task.id, "tenant_id": task.tenant_id, "description": task.description, "status": task.status, "created_at": task.created_at.isoformat()}
            for task in result.scalars().all()
        ]
    }


@router.websocket("/{task_id}/stream")
async def stream_task_logs(websocket: WebSocket, task_id: str, tenant_id: str = Query(None), token: str | None = Query(None)):
    user = resolve_stream_user(token, tenant_id)
    if user is None:
        await websocket.close(code=4401)
        return
    if not await task_belongs_to_tenant(task_id, user.tenant_id):
        await websocket.close(code=4404)
        return
    await websocket.accept()
    await bridge_task_stream(websocket, task_id, user)
