"""
Domain Exceptions

Core business exceptions for the Agentic OS.
"""

class BaseDomainError(Exception):
    """Base exception for all domain errors."""
    pass

class GovernanceDeniedError(BaseDomainError):
    """Raised when a tool action is explicitly denied by RBAC policy."""
    pass

class GovernanceApprovalRequiredError(BaseDomainError):
    """Raised when a tool action requires human-in-the-loop approval."""
    pass

class SandboxExecutionError(BaseDomainError):
    """Raised when sandbox execution crashes or times out."""
    pass

class ToolExecutionError(BaseDomainError):
    """Raised for general tool execution failures."""
    def __init__(self, message: str, tool_name: str):
        super().__init__(f"Tool '{tool_name}' failed: {message}")
        self.tool_name = tool_name
