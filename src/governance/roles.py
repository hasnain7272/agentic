"""
Governance Roles - Role Definitions and Permissions

Defines roles, their permissions, and default policies.
"""
from typing import Dict, List, Set
from enum import Enum


class Role(str, Enum):
    """System roles with increasing privileges."""
    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"
    
    @classmethod
    def hierarchy(cls) -> List["Role"]:
        """Return roles in order of privilege."""
        return [cls.VIEWER, cls.DEVELOPER, cls.ADMIN]
    
    def can_access(self, other: "Role") -> bool:
        """Check if this role can access resources of another role."""
        return self.hierarchy().index(self) >= self.hierarchy().index(other)


# Core tool categories
TOOL_CATEGORIES = {
    "filesystem": [
        "read_file", "write_file", "create_file", "edit_file", "delete_file",
        "list_files", "glob_files", "grep_files",
    ],
    "shell": [
        "bash_execute", "bash_background",
    ],
    "git": [
        "git_clone", "git_read", "git_write", "git_commit",
        "git_create_pr", "git_status", "git_log", "git_diff",
    ],
    "code": [
        "code_review", "security_scan", "generate_tests",
        "generate_docs", "generate_cicd", "code_graph_query",
    ],
    "data": [
        "database_query", "api_test", "manage_dependencies",
    ],
    "web": [
        "web_search", "web_fetch",
    ],
    "mcp": [
        "mcp_*",  # Dynamic - all MCP tools
    ],
    "agent": [
        "delegate_task", "dispatch_output", "update_agent_memory",
        "search_past_decisions",
    ],
}


# Role permissions - which tool categories each role can access
ROLE_TOOL_CATEGORIES: Dict[Role, List[str]] = {
    Role.ADMIN: ["*"],  # All categories
    Role.DEVELOPER: [
        "filesystem", "shell", "git", "code", "data", "web", "mcp", "agent"
    ],
    Role.VIEWER: [
        "filesystem", "code", "web", "agent"  # Read-only categories
    ],
}


# Specific tool permissions (overrides categories)
ROLE_TOOL_PERMISSIONS: Dict[Role, Dict[str, bool]] = {
    Role.ADMIN: {},  # Admin has all
    Role.DEVELOPER: {
        # Explicitly allow dangerous tools
        "bash_execute": True,
        "bash_background": True,
        "git_write": True,
        "git_commit": True,
        "git_create_pr": True,
        "delete_file": True,
        "security_scan": True,
    },
    Role.VIEWER: {
        # Explicitly deny dangerous tools
        "bash_execute": False,
        "bash_background": False,
        "git_write": False,
        "git_commit": False,
        "git_create_pr": False,
        "delete_file": False,
        "write_file": False,
        "create_file": False,
        "edit_file": False,
        "security_scan": False,
    },
}


# Tools that require approval based on risk mode
APPROVAL_REQUIRED: Dict[str, Dict[str, bool]] = {
    "auto": {
        # Only truly irreversible tools need approval in auto mode
        "bash_execute": False,  # Runs in sandbox
        "git_create_pr": True,  # External side effect
        "delete_file": True,    # Irreversible
    },
    "strict": {
        # Everything dangerous needs approval
        "bash_execute": True,
        "bash_background": True,
        "git_write": True,
        "git_commit": True,
        "git_create_pr": True,
        "write_file": True,
        "create_file": True,
        "edit_file": True,
        "delete_file": True,
        "database_query": True,
        "mcp_*": True,  # All MCP tools
    },
}


# Tools that run in sandbox (auto-approved in "auto" mode)
SANDBOXED_TOOLS = {
    "bash_execute",
    "bash_background",
    "python_execute",
    "node_execute",
}


# Tools that are never sandboxed
UNSANDBOXED_TOOLS = {
    "read_file",
    "list_files",
    "glob_files",
    "grep_files",
    "git_read",
    "git_status",
    "git_log",
    "git_diff",
    "code_graph_query",
    "web_search",
    "web_fetch",
    "database_query",
    "api_test",
    "delegate_task",
    "dispatch_output",
    "update_agent_memory",
    "search_past_decisions",
}


def get_allowed_categories(role: Role) -> List[str]:
    """Get allowed tool categories for a role."""
    return ROLE_TOOL_CATEGORIES.get(role, [])


def is_tool_allowed(role: Role, tool_name: str) -> bool:
    """Check if a specific tool is allowed for a role."""
    # Admin has everything
    if role == Role.ADMIN:
        return True
    
    # Check explicit permission
    explicit = ROLE_TOOL_PERMISSIONS.get(role, {}).get(tool_name)
    if explicit is not None:
        return explicit
    
    # Check category
    for category, tools in TOOL_CATEGORIES.items():
        if tool_name in tools or (category == "mcp" and tool_name.startswith("mcp_")):
            allowed_cats = get_allowed_categories(role)
            return "*" in allowed_cats or category in allowed_cats
    
    # Unknown tool - deny by default
    return False


def requires_approval(risk_mode: str, tool_name: str) -> bool:
    """Check if tool requires approval in given risk mode."""
    mode_rules = APPROVAL_REQUIRED.get(risk_mode, APPROVAL_REQUIRED["auto"])
    
    # Check explicit tool
    if tool_name in mode_rules:
        return mode_rules[tool_name]
    
    # Check MCP wildcard
    if tool_name.startswith("mcp_") and "mcp_*" in mode_rules:
        return mode_rules["mcp_*"]
    
    # Default: no approval needed
    return False


def is_sandboxed(tool_name: str) -> bool:
    """Check if tool runs in sandbox."""
    return tool_name in SANDBOXED_TOOLS


def is_unsandboxed(tool_name: str) -> bool:
    """Check if tool runs outside sandbox."""
    return tool_name in UNSANDBOXED_TOOLS


# Default risk mode per role
DEFAULT_RISK_MODE: Dict[Role, str] = {
    Role.ADMIN: "auto",
    Role.DEVELOPER: "auto",
    Role.VIEWER: "strict",
}


# Tenant-level tool overrides
class TenantToolPolicy:
    """Tenant-specific tool allow/deny lists."""
    
    def __init__(
        self,
        tenant_id: str,
        allow_tools: List[str] = None,
        deny_tools: List[str] = None,
        custom_policies: Dict[str, Dict] = None,
    ):
        self.tenant_id = tenant_id
        self.allow_tools = set(allow_tools or [])
        self.deny_tools = set(deny_tools or [])
        self.custom_policies = custom_policies or {}
    
    def is_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed for this tenant."""
        if tool_name in self.deny_tools:
            return False
        if self.allow_tools and tool_name not in self.allow_tools:
            return False
        return True
    
    def get_custom_policy(self, tool_name: str) -> Optional[Dict]:
        """Get custom policy for a tool."""
        return self.custom_policies.get(tool_name)


# Default policies for common scenarios
DEFAULT_TENANT_POLICIES = {
    "strict": TenantToolPolicy(
        tenant_id="strict",
        deny_tools=["bash_execute", "bash_background", "git_write", "delete_file"],
    ),
    "permissive": TenantToolPolicy(
        tenant_id="permissive",
        allow_tools=["*"],  # Allow all
    ),
    "readonly": TenantToolPolicy(
        tenant_id="readonly",
        deny_tools=["write_file", "create_file", "edit_file", "delete_file",
                   "bash_execute", "bash_background", "git_write", "git_commit"],
    ),
}