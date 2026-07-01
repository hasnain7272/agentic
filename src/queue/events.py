"""
Queue Events - Standard Event Definitions

Defines all event types used across the agent system.
Each event has a specific payload structure.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class EventType(str, Enum):
    """Standard event types for the agent system."""
    
    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_NEEDS_APPROVAL = "task.needs_approval"
    TASK_APPROVED = "task.approved"
    TASK_DENIED = "task.denied"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # Tool execution
    TOOL_STARTED = "tool.started"
    TOOL_PROGRESS = "tool.progress"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    
    # Agent loop
    AGENT_THINKING = "agent.thinking"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_RESPONSE = "agent.response"
    AGENT_ITERATION = "agent.iteration"
    
    # Session
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_ARCHIVED = "session.archived"
    
    # MCP
    MCP_PLUGIN_REGISTERED = "mcp.plugin_registered"
    MCP_PLUGIN_STARTED = "mcp.plugin_started"
    MCP_PLUGIN_STOPPED = "mcp.plugin_stopped"
    MCP_PLUGIN_ERROR = "mcp.plugin_error"
    
    # WebSocket
    WS_CONNECTED = "ws.connected"
    WS_DISCONNECTED = "ws.disconnected"
    WS_MESSAGE = "ws.message"


# Payload type definitions for each event
TASK_CREATED_PAYLOAD = {
    "task_id": "str",
    "session_id": "str",
    "tenant_id": "str",
    "description": "str",
    "priority": "int",
}

TASK_STARTED_PAYLOAD = {
    "task_id": "str",
    "session_id": "str",
    "worker_id": "str",
}

TASK_NEEDS_APPROVAL_PAYLOAD = {
    "task_id": "str",
    "session_id": "str",
    "tool_name": "str",
    "arguments": "dict",
    "approval_id": "str",
}

TASK_COMPLETED_PAYLOAD = {
    "task_id": "str",
    "session_id": "str",
    "result": "str",
    "duration_ms": "int",
}

TASK_FAILED_PAYLOAD = {
    "task_id": "str",
    "session_id": "str",
    "error": "str",
    "duration_ms": "int",
}

TOOL_STARTED_PAYLOAD = {
    "tool_call_id": "str",
    "task_id": "str",
    "session_id": "str",
    "tool_name": "str",
    "arguments": "dict",
}

TOOL_PROGRESS_PAYLOAD = {
    "tool_call_id": "str",
    "progress": "int",  # 0-100
    "message": "str",
}

TOOL_COMPLETED_PAYLOAD = {
    "tool_call_id": "str",
    "task_id": "str",
    "result": "any",
    "duration_ms": "int",
}

TOOL_FAILED_PAYLOAD = {
    "tool_call_id": "str",
    "task_id": "str",
    "error": "str",
    "duration_ms": "int",
}

AGENT_THINKING_PAYLOAD = {
    "task_id": "str",
    "iteration": "int",
    "reasoning": "str",
}

AGENT_TOOL_CALL_PAYLOAD = {
    "task_id": "str",
    "iteration": "int",
    "tool_name": "str",
    "arguments": "dict",
}

AGENT_RESPONSE_PAYLOAD = {
    "task_id": "str",
    "content": "str",
    "is_final": "bool",
}


def create_task_event(
    event_type: EventType,
    task_id: str,
    session_id: str,
    tenant_id: str = "local",
    **payload
) -> Dict[str, Any]:
    """Create a standardized task event."""
    base = {
        "task_id": task_id,
        "session_id": session_id,
    }
    base.update(payload)
    return {"event_type": event_type.value, "payload": base, "tenant_id": tenant_id}


def create_tool_event(
    event_type: EventType,
    tool_call_id: str,
    task_id: str,
    session_id: str,
    tenant_id: str = "local",
    **payload
) -> Dict[str, Any]:
    """Create a standardized tool event."""
    base = {
        "tool_call_id": tool_call_id,
        "task_id": task_id,
        "session_id": session_id,
    }
    base.update(payload)
    return {"event_type": event_type.value, "payload": base, "tenant_id": tenant_id}


def create_agent_event(
    event_type: EventType,
    task_id: str,
    session_id: str,
    tenant_id: str = "local",
    **payload
) -> Dict[str, Any]:
    """Create a standardized agent event."""
    base = {
        "task_id": task_id,
        "session_id": session_id,
    }
    base.update(payload)
    return {"event_type": event_type.value, "payload": base, "tenant_id": tenant_id}