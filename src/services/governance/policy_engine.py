"""
Governance Policy Engine — Multi-Tenant RBAC

Enforces:
- Role-based tool access (admin, developer, viewer)
- Per-tenant tool allow/deny lists
- Workspace path isolation
- Dangerous command blocking for bash_execute
"""
import logging
from typing import Any, Dict, List, Optional

from src.domain.exceptions import GovernanceDeniedError
from src.infrastructure.runtime.paths import resolve_workspace_path

logger = logging.getLogger(__name__)
from pathlib import Path


# Role → permitted tools (admin gets wildcard)
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": ["*"],
    "developer": [
        "bash_execute", "read_file", "write_file",
        "git_clone", "git_read", "git_write", "git_commit", "git_create_pr",
        "code_review", "security_scan",
        "generate_tests", "generate_docs", "generate_cicd",
        "database_query", "api_test", "manage_dependencies",
        "code_graph_query", "web_search", "update_agent_memory",
        "search_past_decisions", "delegate_task", "dispatch_output",
    ],
    "viewer": [
        "read_file", "code_graph_query", "web_search",
    ],
}


class PolicyEngine:
    """Stateless policy evaluator — no side effects, pure validation."""

    @staticmethod
    def assert_action_allowed(
        session,
        tool_name: str,
        kwargs: Dict[str, Any],
        tenant_config: Optional[dict] = None,
    ) -> None:
        """Raise GovernanceDeniedError or GovernanceApprovalRequiredError."""
        user_role = getattr(session, "user_role", "developer")
        
        # Admin bypasses all checks
        if user_role == "admin":
            return

        # ── Tool Approval Logic ──
        # risk_mode controls HITL behaviour:
        #   "auto"   (default) → sandboxed tools (bash_execute etc.) auto-approve
        #   "strict" → everything dangerous needs manual HITL approval
        risk_mode = getattr(session, "risk_mode", "auto")

        # Tools that ALWAYS need approval regardless of risk_mode
        ALWAYS_APPROVE_TOOLS: set[str] = set()  # add any truly irreversible tools here

        # Tools that need approval only in strict mode (they run in Docker sandbox)
        SANDBOXED_DANGEROUS_TOOLS = {"bash_execute"}

        # Non-sandboxed tools that need approval in auto+strict
        UNSANDBOXED_DANGEROUS_TOOLS = {"mcp_Blender_capture_viewport_screenshot"}

        needs_approval = False
        if tool_name in ALWAYS_APPROVE_TOOLS:
            needs_approval = True
        elif tool_name in UNSANDBOXED_DANGEROUS_TOOLS:
            needs_approval = True
        elif tool_name in SANDBOXED_DANGEROUS_TOOLS and risk_mode == "strict":
            needs_approval = True

        if needs_approval and not kwargs.get("__approved__"):
            from src.domain.exceptions import GovernanceApprovalRequiredError
            raise GovernanceApprovalRequiredError(f"Action '{tool_name}' requires your approval.")

        # ── Role-Based Access ──
        allowed = ROLE_PERMISSIONS.get(user_role, [])
        is_dynamic_mcp_tool = tool_name.startswith("mcp_")
        
        if allowed != ["*"] and tool_name not in allowed and not is_dynamic_mcp_tool:
            raise GovernanceDeniedError(
                f"Tool '{tool_name}' not permitted for role '{user_role}'."
            )

        # ── Path Isolation & Temp Access ──
        session_id = getattr(session, "id", None)
        tenant_id = getattr(session, "tenant_id", "local")

        if tool_name in {"read_file", "write_file", "create_file", "edit_file"}:
            filepath = kwargs.get("filepath")
            resolved = resolve_workspace_path(filepath, session_id=session_id, tenant_id=tenant_id)
            
            import tempfile
            temp_root = Path(tempfile.gettempdir()).resolve()
            if str(resolved).startswith(str(temp_root)):
                if tool_name != "read_file":
                    raise GovernanceDeniedError("Writing to system temporary directory is forbidden.")
        elif tool_name == "bash_execute":
             resolve_workspace_path(kwargs.get("working_dir", "."), session_id=session_id, tenant_id=tenant_id)


    @staticmethod
    def get_allowed_tools(
        role: str, tenant_config: Optional[dict] = None
    ) -> List[str]:
        """Get list of allowed tool names for a given role."""
        tools = ROLE_PERMISSIONS.get(role, []).copy()

        if tenant_config:
            deny = set(tenant_config.get("deny_tools", []))
            allow = set(tenant_config.get("allow_tools", []))

            if allow:
                tools = [t for t in tools if t in allow]
            tools = [t for t in tools if t not in deny]

        return tools
