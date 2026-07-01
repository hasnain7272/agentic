"""
AgentCore WebSocket - Real-time Communication

Consolidated WebSocket: connection manager + agent streaming + tool execution + notifications.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from agentcore.auth import decode_token
from agentcore.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    """Thread-safe WebSocket connection manager."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}

    async def connect(self, ws: WebSocket, conn_id: str, meta: Dict[str, Any]):
        await ws.accept()
        self.connections[conn_id] = ws
        self.metadata[conn_id] = meta
        logger.info(f"WS connected: {conn_id}")

    def disconnect(self, conn_id: str):
        self.connections.pop(conn_id, None)
        self.metadata.pop(conn_id, None)
        logger.info(f"WS disconnected: {conn_id}")

    async def send(self, conn_id: str, data: Dict[str, Any]):
        ws = self.connections.get(conn_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.error(f"WS send error {conn_id}: {e}")
                self.disconnect(conn_id)

    async def broadcast(self, data: Dict[str, Any], tenant_id: str = None):
        for cid, meta in list(self.metadata.items()):
            if tenant_id is None or meta.get("tenant_id") == tenant_id:
                await self.send(cid, data)


manager = ConnectionManager()


def _authenticate(token: str) -> Optional[Dict[str, Any]]:
    """Authenticate a WebSocket token, return user info or None."""
    try:
        payload = decode_token(token)
        return {
            "user_id": payload.user_id,
            "tenant_id": payload.tenant_id,
            "role": payload.role,
            "email": payload.email,
        }
    except Exception:
        return None


# =============================================================================
# AGENT STREAMING ENDPOINT
# =============================================================================

@router.websocket("/agent")
async def ws_agent(
    websocket: WebSocket,
    session_id: str = Query(...),
    task_id: str = Query(...),
    token: str = Query(...),
):
    """WebSocket for agent execution streaming."""
    auth = _authenticate(token)
    if not auth:
        await websocket.close(code=4001, reason="Auth failed")
        return

    conn_id = f"agent-{session_id}-{auth['user_id']}"
    await manager.connect(websocket, conn_id, {**auth, "session_id": session_id, "task_id": task_id})

    try:
        await manager.send(conn_id, {"type": "connected", "session_id": session_id, "task_id": task_id})

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "run":
                from agentcore.agent_loop import run_agent_stream
                user_msg = data.get("message", "")

                async for event in run_agent_stream(
                    session_id=session_id,
                    task_id=task_id,
                    user_message=user_msg,
                    tenant_id=auth["tenant_id"],
                    user_id=auth["user_id"],
                    user_role=auth["role"],
                ):
                    await manager.send(conn_id, event)
                    if event.get("type") in ("done", "error"):
                        break

            elif data.get("type") == "ping":
                await manager.send(conn_id, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        logger.error(f"WS agent error: {e}")
        await manager.send(conn_id, {"type": "error", "error": str(e)})
        manager.disconnect(conn_id)


# =============================================================================
# TOOL EXECUTION ENDPOINT
# =============================================================================

@router.websocket("/tools")
async def ws_tools(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket for real-time tool execution."""
    auth = _authenticate(token)
    if not auth:
        await websocket.close(code=4001, reason="Auth failed")
        return

    conn_id = f"tools-{auth['user_id']}"
    await manager.connect(websocket, conn_id, auth)

    try:
        await manager.send(conn_id, {"type": "connected"})

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "execute":
                from agentcore.tools import get_tool_registry
                registry = get_tool_registry()
                tool_name = data.get("tool")
                args = data.get("arguments", {})
                args["context"] = {"user_id": auth["user_id"], "tenant_id": auth["tenant_id"]}

                await manager.send(conn_id, {"type": "tool_started", "tool": tool_name})
                result = await registry.execute(tool_name, args)
                await manager.send(conn_id, {
                    "type": "tool_result", "tool": tool_name,
                    "result": {"success": result.success, "data": result.data, "error": result.error},
                })

            elif data.get("type") == "list":
                from agentcore.tools import get_tool_registry
                registry = get_tool_registry()
                schemas = registry.get_schemas()
                await manager.send(conn_id, {
                    "type": "tools_list",
                    "tools": [s.model_dump() if hasattr(s, "model_dump") else s for s in schemas],
                })

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        logger.error(f"WS tools error: {e}")
        manager.disconnect(conn_id)


# =============================================================================
# NOTIFICATIONS ENDPOINT
# =============================================================================

@router.websocket("/notifications")
async def ws_notifications(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket for general notifications / keep-alive."""
    auth = _authenticate(token)
    if not auth:
        await websocket.close(code=4001, reason="Auth failed")
        return

    conn_id = f"notify-{auth['user_id']}"
    await manager.connect(websocket, conn_id, auth)

    try:
        await manager.send(conn_id, {"type": "connected"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(conn_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global WebSocket connection manager."""
    return manager
