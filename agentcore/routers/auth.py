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

auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "User already exists")

    tenant = TenantModel(
        slug=f"{req.email.split('@')[0]}_{secrets.token_hex(4)}",
        name=f"{req.name or req.email}'s Tenant",
        tier="pro", status="active",
    )
    db.add(tenant)
    await db.flush()

    org = OrganizationModel(
        tenant_id=tenant.id, name="Default Organization",
        slug="default", is_default=True,
    )
    db.add(org)
    await db.flush()

    user = UserModel(
        email=req.email, name=req.name or "",
        role="developer", password_hash=hash_password(req.password),
        tenant_id=tenant.id, organization_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = create_token_pair(
        user_id=user.id, email=user.email, role=user.role,
        tenant_id=tenant.id, organization_id=org.id,
    )
    return TokenResponse(
        access_token=tokens["access_token"], refresh_token=tokens["refresh_token"],
        expires_in=tokens["expires_in"], tenant_id=tenant.id,
        user_id=user.id, email=user.email, role=user.role,
    )

@auth_router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    tokens = create_token_pair(
        user_id=user.id, email=user.email, role=user.role,
        tenant_id=user.tenant_id, organization_id=user.organization_id,
    )
    return TokenResponse(
        access_token=tokens["access_token"], refresh_token=tokens["refresh_token"],
        expires_in=tokens["expires_in"], tenant_id=user.tenant_id,
        user_id=user.id, email=user.email, role=user.role,
    )

@auth_router.get("/me")
async def get_me(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserModel).where(UserModel.id == user.user_id))
    db_user = result.scalar_one_or_none()
    tenant = None
    if db_user:
        tenant_result = await db.execute(select(TenantModel).where(TenantModel.id == db_user.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
    return {
        "id": user.user_id, "email": db_user.email if db_user else user.email,
        "name": db_user.name if db_user else "User", "role": user.role,
        "tenant_id": user.tenant_id,
        "cost_cents": tenant.cost_cents if tenant else 0,
        "quota_usd": tenant.quota_usd if tenant else 0,
    }
