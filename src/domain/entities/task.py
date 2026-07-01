"""
Domain Entity: Task
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    CODE_GEN = "code_generation"
    DEBUG = "debugging"
    CUSTOM = "custom"

@dataclass
class TaskStep:
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    tools: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class Task:
    """Core durable task for the event-driven DAG."""
    id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    session_id: str = ""
    type: TaskType = TaskType.CUSTOM
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    steps: List[TaskStep] = field(default_factory=list)
    context: Dict = field(default_factory=dict)
    current_step_index: int = 0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def progress(self) -> float:
        if not self.steps: return 0.0
        completed = sum(1 for s in self.steps if s.status == TaskStatus.COMPLETED)
        return (completed / len(self.steps)) * 100.0

    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.updated_at = datetime.now(timezone.utc)
