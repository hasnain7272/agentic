"""
Domain Entity: Session
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

@dataclass
class Session:
    """Core Session state tracking for agents."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = "system"
    workspace_path: str = "."
    mode: str = "cli"
    user_role: str = "developer"
    risk_mode: str = "auto"
    context: Dict = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # History constraints
    task_history: List[str] = field(default_factory=list)
    file_history: List[str] = field(default_factory=list)
    conversation_history: List[Dict] = field(default_factory=list)

    def update_activity(self):
        self.last_active_at = datetime.now(timezone.utc)

    def add_message(self, role: str, content: str):
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(self.conversation_history) > 200:
            self.conversation_history = self.conversation_history[-200:]
        self.update_activity()

    def end_session(self):
        self.is_active = False
        self.context["ended"] = True
        self.update_activity()
