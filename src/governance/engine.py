"""
Governance Engine - Policy Evaluation and Enforcement

Stateless policy evaluator that enforces role-based access,
tenant policies, path isolation, and approval requirements.
"""
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.governance.roles import (
    Role,
    is_tool_allowed,
    requires_approval,
    is_sandboxed,
    TenantToolPolicy,
    DEFAULT_TENANT_POLICIES,
)
from src.runtime.paths import resolve_workspace_path

logger = logging.getLogger(__name__)


class GovernanceError(Exception):
    """Base governance exception."""
    pass


class GovernanceDeniedError(GovernanceError):
    """Action denied by policy."""
    pass


class GovernanceApprovalRequiredError(GovernanceError):
    """Action requires human approval (HITL)."""
    
    def __init__(self, tool_name: str, message: str = None, approval_id: str = None):
        self.tool_name = tool_name
        self.approval_id = approval_id
        super().__init__(message or f"Action '{tool_name}' requires approval")


class GovernanceEngine:
    """Stateless policy evaluator - no side effects, pure validation."""
    
    def __init__(self):
        self._tenant_policies: Dict[str, TenantToolPolicy] = DEFAULT_TENANT_POLICIES.copy()
    
    def register_tenant_policy(self, policy: TenantToolPolicy) -> None:
        """Register or update a tenant's tool policy."""
        self._tenant_policies[policy.tenant_id] = policy
        logger.info(f"Registered governance policy for tenant: {policy.tenant_id}")
    
    def get_tenant_policy(self, tenant_id: str) -> TenantToolPolicy:
        """Get tenant policy, returning permissive default if not found."""
        return self._tenant_policies.get(tenant_id, TenantToolPolicy(tenant_id=tenant_id, allow_tools=["*"]))
    
    def assert_action_allowed(
        self,
        session: Any,
        tool_name: str,
        kwargs: Dict[str, Any],
        tenant_policy: Optional[TenantToolPolicy] = None,
    ) -> None:
        """
        Raise GovernanceDeniedError or GovernanceApprovalRequiredError if not allowed.
        
        Args:
            session: Session object with user_role, tenant_id, risk_mode, id
            tool_name: Name of tool being invoked
            kwargs: Tool arguments (for path validation)
            tenant_policy: Optional tenant-specific policy
        """
        # Extract session attributes
        user_role = getattr(session, "user_role", Role.DEVELOPER)
        if isinstance(user_role, str):
            user_role = Role(user_role)
        
        tenant_id = getattr(session, "tenant_id", "local")
        risk_mode = getattr(session, "risk_mode", "auto")
        session_id = getattr(session, "id", None)
        
        # Use provided policy or fetch default
        policy = tenant_policy or self.get_tenant_policy(tenant_id)
        
        # 1. Check tenant tool policy
        if not policy.is_allowed(tool_name):
            raise GovernanceDeniedError(f"Tool '{tool_name}' denied by tenant policy")
        
        # 2. Check role-based tool permission
        if not is_tool_allowed(user_role, tool_name):
            raise GovernanceDeniedError(
                f"Tool '{tool_name}' not permitted for role '{user_role.value}'"
            )
        
        # 3. Check path isolation for filesystem tools
        self._validate_paths(tool_name, kwargs, session_id, tenant_id)
        
        # 4. Check approval requirement
        if requires_approval(risk_mode, tool_name):
            # Skip if already approved
            if not kwargs.get("__approved__"):
                raise GovernanceApprovalRequiredError(
                    tool_name=tool_name,
                    message=f"Action '{tool_name}' requires your approval in {risk_mode} mode",
                )
    
    def _validate_paths(
        self,
        tool_name: str,
        kwargs: Dict[str, Any],
        session_id: Optional[str],
        tenant_id: str,
    ) -> None:
        """Validate file paths for isolation."""
        
        filesystem_tools = {
            "read_file", "write_file", "create_file", "edit_file", "delete_file",
            "list_files", "glob_files", "grep_files",
        }
        
        if tool_name not in filesystem_tools:
            return
        
        # Get filepath from kwargs
        filepath = kwargs.get("filepath") or kwargs.get("path")
        if not filepath:
            return
        
        try:
            resolved = resolve_workspace_path(filepath, session_id=session_id, tenant_id=tenant_id)
        except Exception as e:
            raise GovernanceDeniedError(f"Path resolution failed: {e}")
        
        # Check temp directory access
        temp_root = Path(tempfile.gettempdir()).resolve()
        if str(resolved).startswith(str(temp_root)):
            if tool_name != "read_file":
                raise GovernanceDeniedError("Writing to system temporary directory is forbidden")
        
        # Additional path checks could go here:
        # - Symlink resolution
        # - Mount point traversal
        # - Protected system directories
    
    def get_allowed_tools(
        self,
        role: Role,
        tenant_id: str = "local",
        risk_mode: str = "auto",
    ) -> List[str]:
        """Get list of allowed tool names for a role/tenant combination."""
        policy = self.get_tenant_policy(tenant_id)
        
        # Start with all possible tools
        all_tools = set()
        for tools in [
            "read_file", "write_file", "create_file", "edit_file", "delete_file",
            "list_files", "glob_files", "grep_files",
            "bash_execute", "bash_background",
            "git_clone", "git_read", "git_write", "git_commit", "git_create_pr",
            "git_status", "git_log", "git_diff",
            "code_review", "security_scan", "generate_tests", "generate_docs", "generate_cicd",
            "code_graph_query", "database_query", "api_test", "manage_dependencies",
            "web_search", "web_fetch",
            "delegate_task", "dispatch_output", "update_agent_memory", "search_past_decisions",
        ]:
            if is_tool_allowed(role, tools) and policy.is_allowed(tools):
                all_tools.add(tools)
        
        return sorted(all_tools)
    
    def check_approval_status(
        self,
        tool_name: str,
        risk_mode: str,
        approved: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if tool needs approval and return (needs_approval, message).
        
        Returns:
            (bool: needs_approval, str: approval_message or None)
        """
        if not requires_approval(risk_mode, tool_name):
            return False, None
        
        if approved:
            return False, None
        
        # Generate approval message
        sandboxed = is_sandboxed(tool_name)
        if sandboxed:
            msg = f"Tool '{tool_name}' runs in a sandboxed environment. Approve to execute?"
        else:
            msg = f"Tool '{tool_name}' will execute on the host system. Are you sure?"
        
        return True, msg
    
    def evaluate_batch(
        self,
        session: Any,
        tool_calls: List[Dict[str, Any]],
        tenant_policy: Optional[TenantToolPolicy] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate multiple tool calls at once.
        
        Returns:
            {
                "allowed": [tool_names],
                "denied": [{"tool": name, "reason": reason}],
                "needs_approval": [{"tool": name, "message": msg}],
            }
        """
        result = {
            "allowed": [],
            "denied": [],
            "needs_approval": [],
        }
        
        for call in tool_calls:
            tool_name = call.get("name") or call.get("tool_name")
            kwargs = call.get("arguments") or call.get("kwargs") or {}
            
            try:
                self.assert_action_allowed(session, tool_name, kwargs, tenant_policy)
                
                # Check if approval needed
                risk_mode = getattr(session, "risk_mode", "auto")
                approved = kwargs.get("__approved__", False)
                needs_approval, msg = self.check_approval_status(tool_name, risk_mode, approved)
                
                if needs_approval:
                    result["needs_approval"].append({"tool": tool_name, "message": msg})
                else:
                    result["allowed"].append(tool_name)
                    
            except GovernanceApprovalRequiredError as e:
                result["needs_approval"].append({"tool": tool_name, "message": str(e)})
            except GovernanceDeniedError as e:
                result["denied"].append({"tool": tool_name, "reason": str(e)})
            except Exception as e:
                result["denied"].append({"tool": tool_name, "reason": f"Evaluation error: {e}"})
        
        return result


# Global engine instance
_engine: Optional[GovernanceEngine] = None


def get_governance_engine() -> GovernanceEngine:
    """Get or create the global governance engine."""
    global _engine
    if _engine is None:
        _engine = GovernanceEngine()
    return _engine