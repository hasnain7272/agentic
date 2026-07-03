from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, and_, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import secrets
from pathlib import Path

from agentcore.config import get_settings
from agentcore.database import *
from agentcore.auth import *
from agentcore.schema import *
from agentcore.utils import *
from agentcore.governance import get_governance_engine
from agentcore.tools import get_tool_registry

settings = get_settings()

approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])

@approvals_router.get("/")
async def list_approvals(
    approval_status: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ApprovalModel).where(ApprovalModel.tenant_id == user.tenant_id)
    if approval_status:
        query = query.where(ApprovalModel.status == approval_status)
    query = query.order_by(ApprovalModel.created_at.desc()).limit(100)
    result = await db.execute(query)
    return [
        {"id": a.id, "action": a.action, "status": a.status, "created_at": a.created_at.isoformat()}
        for a in result.scalars().all()
    ]

@approvals_router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApprovalModel).where(
            ApprovalModel.id == approval_id,
            ApprovalModel.tenant_id == user.tenant_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Approval not found")
    if approval.status != "pending":
        raise HTTPException(400, f"Approval already {approval.status}")

    approval.status = "approved" if decision.approved else "rejected"
    approval.approver_id = user.user_id
    approval.approved_at = datetime.utcnow()
    await db.commit()
    return {"status": approval.status}
