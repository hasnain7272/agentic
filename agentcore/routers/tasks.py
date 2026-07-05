import logging
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, WebSocket, WebSocketDisconnect

from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, and_, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import secrets
from pathlib import Path

from agentcore.config import get_settings
from agentcore.database import *
from agentcore.auth import *
from agentcore.schema import *
from agentcore.utils import *
from agentcore.governance import get_governance_engine
from agentcore.tools import get_tool_registry

logger = logging.getLogger(__name__)
settings = get_settings()


tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])

@tasks_router.post("/", status_code=202)
async def dispatch_task(
    req: TaskCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session access
    result = await db.execute(
        select(SessionModel.id).where(
            and_(SessionModel.id == req.session_id, SessionModel.tenant_id == user.tenant_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not authorized or session not found")

    task = TaskModel(
        tenant_id=user.tenant_id, session_id=req.session_id,
        description=req.description, status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"status": "accepted", "task_id": task.id}

@tasks_router.get("/")
async def list_tasks(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TaskModel).where(TaskModel.tenant_id == user.tenant_id)
        .order_by(TaskModel.created_at.desc()).limit(50)
    )
    return {
        "tasks": [
            {"id": t.id, "description": t.description, "status": t.status,
             "created_at": t.created_at.isoformat()}
            for t in result.scalars().all()
        ]
    }

@tasks_router.websocket("/{task_id}/stream")
async def ws_task_stream(
    websocket: WebSocket,
    task_id: str,
    token: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
):
    from agentcore.websocket import _authenticate, manager
    auth = _authenticate(token) if token else None
    if not auth:
        await websocket.close(code=4001, reason="Auth failed")
        return

    async for db in get_db():
        result = await db.execute(
            select(TaskModel).where(
                and_(TaskModel.id == task_id, TaskModel.tenant_id == auth["tenant_id"])
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            await websocket.close(code=4004, reason="Task not found")
            return
        session_id = task.session_id
        description = task.description
        break

    conn_id = f"agent-{session_id}-{task_id}-{auth['user_id']}"
    await manager.connect(websocket, conn_id, {**auth, "session_id": session_id, "task_id": task_id})

    try:
        await manager.send(conn_id, {"type": "connected", "session_id": session_id, "task_id": task_id})

        # Heartbeat task to keep the WebSocket active during long agent/MCP executions
        async def send_heartbeats():
            try:
                while True:
                    await asyncio.sleep(10.0)
                    await manager.send(conn_id, {"type": "heartbeat"})
            except asyncio.CancelledError:
                pass
            except Exception as ex:
                logger.debug(f"Heartbeat send error: {ex}")

        hb_task = asyncio.create_task(send_heartbeats())

        try:
            from agentcore.agent_loop import run_agent_stream
            async for event in run_agent_stream(
                session_id=session_id,
                task_id=task_id,
                user_message=description,
                tenant_id=auth["tenant_id"],
                user_id=auth["user_id"],
                user_role=auth["role"],
            ):
                await manager.send(conn_id, event)
                if event.get("type") in ("done", "error"):
                    break
        finally:
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await manager.send(conn_id, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        logger.error(f"WS task stream error: {e}")
        await manager.send(conn_id, {"type": "error", "error": str(e)})
        manager.disconnect(conn_id)

@tasks_router.post("/{task_id}/stop")
async def stop_task(
    task_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from agentcore.database import TaskModel, TaskStatus
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id, TaskModel.tenant_id == user.tenant_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.status in (TaskStatus.running, TaskStatus.pending, TaskStatus.needs_approval):
        task.status = TaskStatus.cancelled
        db.add(task)
        await db.commit()
        return {"status": "success", "message": "Task cancellation requested."}
        
    return {"status": "ignored", "message": f"Task already in terminal state: {task.status}"}

