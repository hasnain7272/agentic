"""
Approvals Router - Human-in-the-Loop Approval Endpoints

Handles approval requests for governance-gated actions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from src.api.rest.dependencies import get_db, get_current_user_dep, get_tenant_id
from src.governance import get_approval_manager, ApprovalStatus
from src.auth.jwt import TokenPayload

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequestCreate(BaseModel):
    """Request to create an approval."""
    action: str = Field(..., description="Action being requested")
    resource: Optional[str] = Field(None, description="Resource being acted on")
    context: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = Field(None, description="Reason for request")
    expires_in_seconds: int = Field(default=3600, description="Expiration time")


class ApprovalDecision(BaseModel):
    """Decision on an approval request."""
    approved: bool
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval response model."""
    id: str
    action: str
    resource: Optional[str]
    context: Dict[str, Any]
    reason: Optional[str]
    status: str
    requester_id: str
    approver_id: Optional[str]
    created_at: datetime
    expires_at: datetime
    decided_at: Optional[datetime] = None


@router.post("", response_model=ApprovalResponse)
async def create_approval_request(
    request: ApprovalRequestCreate,
    current_user: TokenPayload = Depends(get_current_user_dep),
    tenant_id: str = Depends(get_tenant_id),
    db = Depends(get_db),
):
    """Create a new approval request."""
    from src.db.models import ApprovalModel
    
    approval = ApprovalModel(
        id=f"appr-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        requester_id=current_user.sub,
        action=request.action,
        resource=request.resource,
        context=request.context,
        reason=request.reason,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(seconds=request.expires_in_seconds),
    )
    
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    
    return ApprovalResponse(
        id=approval.id,
        action=approval.action,
        resource=approval.resource,
        context=approval.context,
        reason=approval.reason,
        status=approval.status,
        requester_id=approval.requester_id,
        approver_id=approval.approver_id,
        created_at=approval.created_at,
        expires_at=approval.expires_at,
    )


@router.get("", response_model=List[ApprovalResponse])
async def list_approvals(
    status: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user_dep),
    tenant_id: str = Depends(get_tenant_id),
    db = Depends(get_db),
):
    """List approval requests for the tenant."""
    from sqlalchemy import select
    from src.db.models import ApprovalModel
    
    query = select(ApprovalModel).where(ApprovalModel.tenant_id == tenant_id)
    
    if status:
        query = query.where(ApprovalModel.status == status)
    
    # Non-admins only see their own requests
    if current_user.role not in ("admin", "service"):
        query = query.where(ApprovalModel.requester_id == current_user.sub)
    
    query = query.order_by(ApprovalModel.created_at.desc()).limit(100)
    
    result = await db.execute(query)
    approvals = result.scalars().all()
    
    return [
        ApprovalResponse(
            id=a.id,
            action=a.action,
            resource=a.resource,
            context=a.context,
            reason=a.reason,
            status=a.status,
            requester_id=a.requester_id,
            approver_id=a.approver_id,
            created_at=a.created_at,
            expires_at=a.expires_at,
            decided_at=a.approved_at,
        )
        for a in approvals
    ]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    current_user: TokenPayload = Depends(get_current_user_dep),
    tenant_id: str = Depends(get_tenant_id),
    db = Depends(get_db),
):
    """Get approval request by ID."""
    from sqlalchemy import select
    from src.db.models import ApprovalModel
    
    result = await db.execute(
        select(ApprovalModel).where(
            ApprovalModel.id == approval_id,
            ApprovalModel.tenant_id == tenant_id,
        )
    )
    approval = result.scalar_one_or_none()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    # Check permissions
    if current_user.role not in ("admin", "service") and approval.requester_id != current_user.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return ApprovalResponse(
        id=approval.id,
        action=approval.action,
        resource=approval.resource,
        context=approval.context,
        reason=approval.reason,
        status=approval.status,
        requester_id=approval.requester_id,
        approver_id=approval.approver_id,
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        decided_at=approval.approved_at,
    )


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    current_user: TokenPayload = Depends(get_current_user_dep),
    tenant_id: str = Depends(get_tenant_id),
    db = Depends(get_db),
):
    """Approve or deny an approval request."""
    from sqlalchemy import select
    from src.db.models import ApprovalModel
    from src.governance import get_approval_manager
    
    result = await db.execute(
        select(ApprovalModel).where(
            ApprovalModel.id == approval_id,
            ApprovalModel.tenant_id == tenant_id,
        )
    )
    approval = result.scalar_one_or_none()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already {approval.status}")
    
    if approval.expires_at and approval.expires_at < datetime.utcnow():
        approval.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Approval expired")
    
    # Check permissions - admins and service accounts can approve
    if current_user.role not in ("admin", "service"):
        raise HTTPException(status_code=403, detail="Not authorized to approve")
    
    approval.status = "approved" if decision.approved else "rejected"
    approval.approver_id = current_user.sub
    approval.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(approval)
    
    # Notify approval manager
    approval_manager = get_approval_manager()
    await approval_manager.resolve(approval_id, decision.approved)
    
    return ApprovalResponse(
        id=approval.id,
        action=approval.action,
        resource=approval.resource,
        context=approval.context,
        reason=approval.reason,
        status=approval.status,
        requester_id=approval.requester_id,
        approver_id=approval.approver_id,
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        decided_at=approval.approved_at,
    )


@router.get("/pending/me", response_model=List[ApprovalResponse])
async def get_my_pending_approvals(
    current_user: TokenPayload = Depends(get_current_user_dep),
    tenant_id: str = Depends(get_tenant_id),
    db = Depends(get_db),
):
    """Get pending approvals for current user."""
    from sqlalchemy import select
    from src.db.models import ApprovalModel
    
    result = await db.execute(
        select(ApprovalModel).where(
            ApprovalModel.tenant_id == tenant_id,
            ApprovalModel.requester_id == current_user.sub,
            ApprovalModel.status == "pending",
        ).order_by(ApprovalModel.created_at.desc())
    )
    approvals = result.scalars().all()
    
    return [
        ApprovalResponse(
            id=a.id,
            action=a.action,
            resource=a.resource,
            context=a.context,
            reason=a.reason,
            status=a.status,
            requester_id=a.requester_id,
            approver_id=a.approver_id,
            created_at=a.created_at,
            expires_at=a.expires_at,
        )
        for a in approvals
    ]