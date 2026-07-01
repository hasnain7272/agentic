"""
Governance Package - Policy Engine, Roles, and Approval

Provides comprehensive governance for agent actions:
- Role-based access control (RBAC)
- Tenant-level tool policies
- Path isolation and sandbox enforcement
- Human-in-the-loop (HITL) approval workflow
"""
from src.governance.roles import (
    Role,
    TOOL_CATEGORIES,
    ROLE_TOOL_CATEGORIES,
    ROLE_TOOL_PERMISSIONS,
    APPROVAL_REQUIRED,
    SANDBOXED_TOOLS,
    UNSANDBOXED_TOOLS,
    DEFAULT_RISK_MODE,
    TenantToolPolicy,
    DEFAULT_TENANT_POLICIES,
    get_allowed_categories,
    is_tool_allowed,
    requires_approval,
    is_sandboxed,
    is_unsandboxed,
)
from src.governance.engine import (
    GovernanceEngine,
    GovernanceDeniedError,
    GovernanceApprovalRequiredError,
    get_governance_engine,
)
from src.governance.approval import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    get_approval_manager,
    request_approval,
    wait_for_approval,
    approve_request,
    deny_request,
)

__all__ = [
    "Role",
    "TOOL_CATEGORIES",
    "ROLE_TOOL_CATEGORIES",
    "ROLE_TOOL_PERMISSIONS",
    "APPROVAL_REQUIRED",
    "SANDBOXED_TOOLS",
    "UNSANDBOXED_TOOLS",
    "DEFAULT_RISK_MODE",
    "TenantToolPolicy",
    "DEFAULT_TENANT_POLICIES",
    "get_allowed_categories",
    "is_tool_allowed",
    "requires_approval",
    "is_sandboxed",
    "is_unsandboxed",
    "GovernanceEngine",
    "GovernanceDeniedError",
    "GovernanceApprovalRequiredError",
    "get_governance_engine",
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
    "get_approval_manager",
    "request_approval",
    "wait_for_approval",
    "approve_request",
    "deny_request",
]