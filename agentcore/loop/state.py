"""
AgentCore Loop — Agent State & Context
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_APPROVAL = "waiting_approval"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentContext:
    session_id: str
    task_id: str
    user_id: str
    tenant_id: str
    organization_id: Optional[str] = None
    user_role: str = "developer"
    risk_mode: str = "auto"
    metadata: Dict[str, Any] = field(default_factory=dict)

    state: AgentState = AgentState.IDLE
    current_step: int = 0
    max_steps: int = 20
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    stream_callback: Optional[Callable] = None

    def to_session_dict(self) -> Dict[str, Any]:
        return {
            "id": self.session_id,
            "user_role": self.user_role,
            "tenant_id": self.tenant_id,
            "risk_mode": self.risk_mode,
        }
