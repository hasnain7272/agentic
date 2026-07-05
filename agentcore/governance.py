"""
AgentCore Governance — Simple Destructive Pattern Approval Guardrails
"""
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class Role(str, Enum):
    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


ROLE_TOOL_CATEGORIES = {
    Role.ADMIN: ["*"],
    Role.DEVELOPER: ["web", "knowledge", "code", "integration", "content", "communication", "a2a", "mcp"],
    Role.VIEWER: ["web", "knowledge", "a2a"],
}


class GovernanceError(Exception):
    pass


class GovernanceDeniedError(GovernanceError):
    pass


class GovernanceApprovalRequiredError(GovernanceError):
    def __init__(self, tool_name: str, message: str = None, approval_id: str = None):
        self.tool_name = tool_name
        self.approval_id = approval_id
        super().__init__(message or f"Action '{tool_name}' requires approval")


class Decision:
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason


class GovernanceEngine:
    """Simple evaluator stub to support existing router check endpoints."""
    def evaluate(self, session_context: Any, action: str, resource: Optional[str] = None, context: Optional[dict] = None) -> Decision:
        return Decision(allowed=True, reason="Governance policy allowed by default")


_engine = GovernanceEngine()


def get_governance_engine() -> GovernanceEngine:
    return _engine


# Destructive command patterns for governance checks
DESTRUCTIVE_PATTERNS = [
    r"rm\s+-rf", r"rmdir\s+/s", r"del\s+/[sf]",
    r"DROP\s+(TABLE|DATABASE|SCHEMA)", r"TRUNCATE",
    r"DELETE\s+FROM(?!.*WHERE)", r"git\s+push\s+--force",
    r"format\s+[a-z]:", r"shutdown", r"mkfs",
]


async def check_destructive(tool_name: str, args: dict) -> bool:
    """
    Returns True if the tool name and arguments match pattern of destructive commands
    that must require user approval before running.
    """
    if tool_name in ("delete_file", "bash_execute", "sql_execute", "git_push"):
        import json
        text = json.dumps(args)
        return any(re.search(p, text, re.I) for p in DESTRUCTIVE_PATTERNS)
    return False