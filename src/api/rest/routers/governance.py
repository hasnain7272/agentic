"""
Governance Router - Governance and Policy Endpoints

Provides endpoints for role management, policy evaluation, and governance info.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from src.governance import (
    get_governance_engine,
    get_roles,
    get_role,
    GovernanceEngine,
)
from src.governance.roles import Role, Permission, RoleDefinition
from src.governance.engine import PolicyDecision
from src.auth.dependencies import get_current_user_dep, TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/governance", tags=["governance"])


class PolicyCheckRequest(BaseModel):
    action: str
    resource: Optional[str] = None
    context: Dict[str, Any] = {}


class PolicyCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    required_approval: bool = False


class RoleResponse(BaseModel):
    name: str
    description: str
    permissions: List[str]
    inherits: List[str]


class ApprovalRequest(BaseModel):
    request_id: str
    action: str
    resource: str
    context: Dict[str, Any]
    reason: Optional[str] = None


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """List all available roles."""
    roles = get_roles()
    return [
        RoleResponse(
            name=role.name,
            description=role.description,
            permissions=[p.value for p in role.permissions],
            inherits=role.inherits,
        )
        for role in roles.values()
    ]


@router.get("/roles/{role_name}", response_model=RoleResponse)
async def get_role_info(
    role_name: str,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get details of a specific role."""
    role = get_role(role_name)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role not found: {role_name}",
        )
    
    return RoleResponse(
        name=role.name,
        description=role.description,
        permissions=[p.value for p in role.permissions],
        inherits=role.inherits,
    )


@router.get("/my-role")
async def get_my_role(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Get current user's role and permissions."""
    from src.governance.roles import get_role
    role = get_role(current_user.role)
    
    if not role:
        return {"role": current_user.role, "permissions": [], "error": "Role not defined"}
    
    return {
        "role": current_user.role,
        "permissions": [p.value for p in role.permissions],
        "inherits": role.inherits,
    }


@router.post("/check", response_model=PolicyCheckResponse)
async def check_policy(
    request: PolicyCheckRequest,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Check if an action is allowed under current governance."""
    engine = get_governance_engine()
    
    # Create a session-like object
    session = type('Session', (), {
        'id': 'api-check',
        'user_role': current_user.role,
        'tenant_id': current_user.tenant_id,
    })()
    
    decision = engine.evaluate(session, request.action, request.resource, request.context)
    
    return PolicyCheckResponse(
        allowed=decision.allowed,
        reason=decision.reason,
        required_approval=decision.required_approval,
    )


@router.get("/policies")
async def list_policies(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """List all governance policies."""
    engine = get_governance_engine()
    policies = engine.get_policies()
    
    return [
        {
            "name": p.name,
            "description": p.description,
            "roles": p.roles,
            "actions": p.actions,
            "resources": p.resources,
            "requires_approval": p.requires_approval,
            "priority": p.priority,
        }
        for p in policies
    ]


@router.post("/approvals/request")
async def request_approval(
    request: ApprovalRequest,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Request approval for an action (HITL workflow)."""
    from src.governance.approval import get_approval_manager
    
    manager = get_approval_manager()
    
    # Create approval request
    approval_id = await manager.request_approval(
        requester_id=current_user.sub,
        action=request.action,
        resource=request.resource,
        context=request.context,
        reason=request.reason,
    )
    
    return {"approval_id": approval_id, "status": "pending"}


@router.get("/approvals/pending")
async def list_pending_approvals(
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """List pending approvals for the current user."""
    from src.governance.approval import get_approval_manager
    
    manager = get_approval_manager()
    approvals = await manager.get_pending_for_user(current_user.sub)
    
    return approvals


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Approve a pending request."""
    from src.governance.approval import get_approval_manager
    
    manager = get_approval_manager()
    success = await manager.approve(approval_id, current_user.sub)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to approve (not found or already decided)",
        )
    
    return {"status": "approved"}


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    reason: str = "",
    current_user: TokenPayload = Depends(get_current_user_dep),
):
    """Reject a pending request."""
    from src.governance.approval import get_approval_manager
    
    manager = get_approval_manager()
    success = await manager.reject(approval_id, current_user.sub, reason)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reject (not found or already decided)",
        )
    
    return {"status": "rejected"}