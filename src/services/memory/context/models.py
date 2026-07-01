"""Data models for session context management."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


@dataclass
class ContextWindow:
    """Represents a window of messages in the context."""
    start_sequence: int
    end_sequence: int
    messages: List[Dict[str, Any]]
    summary: Optional[str] = None
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionContext:
    """Full session context with efficient storage."""
    session_id: str
    user_id: str
    windows: List[ContextWindow] = field(default_factory=list)
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # State tracking
    last_sequence: int = 0
    total_messages: int = 0
    is_dirty: bool = False
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    # Smart context
    key_topics: List[str] = field(default_factory=list)
    action_history: List[str] = field(default_factory=list)
    file_references: Set[str] = field(default_factory=set)
