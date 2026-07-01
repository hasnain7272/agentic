"""
Domain Entity: Tool Call
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

@dataclass
class ToolCallRequest:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: str = "system"

@dataclass
class ToolCallResult:
    tool_call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
