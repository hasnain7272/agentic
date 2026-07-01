"""
WebSocket Router - Real-time Communication

Provides WebSocket endpoints for agent streaming, tool execution updates,
and real-time notifications.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from src.auth.jwt import decode_token
from src.auth.dependencies import get_db
from src.agent.loop import run_agent, AgentContext
from src.tools.registry import get_tool_registry
from src.memory.manager import get_memory_manager
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, metadata: Dict[str, Any]):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = metadata
        logger.info(f"WebSocket connected: {connection_id}")
    
    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_json(self, connection_id: str, data: Dict[str, Any]):
        websocket = self.active_connections.get(connection_id)
        if websocket:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Failed to send to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast(self, data: Dict[str, Any], tenant_id: str = None):
        for conn_id, metadata in self.connection_metadata.items():
            if tenant_id is None or metadata.get("tenant_id") == tenant_id:
                await self.send_json(conn_id, data)


manager = ConnectionManager()


async def authenticate_websocket(
    websocket: WebSocket,
    token: str = Query(...),
) -> Optional[Dict[str, Any]]:
    """Authenticate WebSocket connection."""
    try:
        payload = decode_token(token)
        return {
            "user_id": payload.sub,
            "tenant_id": payload.tenant_id,
            "organization_id": payload.organization_id,
            "role": payload.role,
            "email": payload.email,
        }
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return None


@router.websocket("/agent")
async def websocket_agent(
    websocket: WebSocket,
    session_id: str = Query(...),
    task_id: str = Query(...),
    token: str = Query(...),
):
    """WebSocket for agent execution streaming."""
    auth = await authenticate_websocket(websocket, token)
    if not auth:
        return
    
    connection_id = f"agent-{session_id}-{auth['user_id']}"
    
    await manager.connect(websocket, connection_id, {
        **auth,
        "session_id": session_id,
        "task_id": task_id,
    })
    
    try:
        # Send connection confirmed
        await manager.send_json(connection_id, {
            "type": "connected",
            "session_id": session_id,
            "task_id": task_id,
        })
        
        # Listen for messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "run":
                # Run agent with user message
                user_message = data.get("message", "")
                
                context = AgentContext(
                    session_id=session_id,
                    task_id=task_id,
                    user_id=auth["user_id"],
                    tenant_id=auth["tenant_id"],
                    organization_id=auth.get("organization_id"),
                    user_role=auth["role"],
                )
                
                # Stream agent events
                async for event in run_agent(
                    session_id=session_id,
                    task_id=task_id,
                    user_message=user_message,
                    user=type('TokenPayload', (), auth)(),
                ):
                    await manager.send_json(connection_id, event)
                    
                    if event.get("type") == "done":
                        break
                    elif event.get("type") == "error":
                        break
            
            elif data.get("type") == "ping":
                await manager.send_json(connection_id, {"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.send_json(connection_id, {"type": "error", "error": str(e)})
        manager.disconnect(connection_id)


@router.websocket("/tools")
async def websocket_tools(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket for tool execution updates."""
    auth = await authenticate_websocket(websocket, token)
    if not auth:
        return
    
    connection_id = f"tools-{auth['user_id']}"
    
    await manager.connect(websocket, connection_id, auth)
    
    try:
        await manager.send_json(connection_id, {"type": "connected"})
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "execute":
                tool_name = data.get("tool")
                arguments = data.get("arguments", {})
                
                registry = get_tool_registry()
                arguments["context"] = {
                    "user_id": auth["user_id"],
                    "tenant_id": auth["tenant_id"],
                }
                
                # Send started
                await manager.send_json(connection_id, {
                    "type": "tool_started",
                    "tool": tool_name,
                })
                
                result = await registry.execute(tool_name, arguments)
                
                # Send result
                await manager.send_json(connection_id, {
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": result.model_dump(),
                })
            
            elif data.get("type") == "list":
                registry = get_tool_registry()
                tools = registry.get_schemas()
                await manager.send_json(connection_id, {
                    "type": "tools_list",
                    "tools": [t.model_dump() for t in tools],
                })
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"Tools WebSocket error: {e}")
        manager.disconnect(connection_id)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket for general notifications."""
    auth = await authenticate_websocket(websocket, token)
    if not auth:
        return
    
    connection_id = f"notify-{auth['user_id']}"
    
    await manager.connect(websocket, connection_id, auth)
    
    try:
        await manager.send_json(connection_id, {"type": "connected"})
        
        # Keep alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(connection_id)


def get_connection_manager() -> ConnectionManager:
    """Get the WebSocket connection manager."""
    return manager