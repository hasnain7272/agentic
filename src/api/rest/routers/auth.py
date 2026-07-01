"""
Auth Router — Production-grade JWT authentication.
"""
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.rest.dependencies import get_db
from src.infrastructure.auth.jwt_auth import (
    create_token_pair,
    create_access_token,
    TokenPayload,
)
from src.infrastructure.db.models.tenant_model import TenantModel, UserModel, OrganizationModel
import bcrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    user_id: str
    email: str
    role: str


def _generate_slug(email: str) -> str:
    """Generate a unique slug from email."""
    base = email.split("@")[0]
    # Remove non-alphanumeric and limit length
    slug = "".join(c for c in base if c.isalnum())[:30]
    # Add random suffix to ensure uniqueness
    return f"{slug}_{secrets.token_hex(4)}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(UserModel).where(UserModel.email == req.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Create tenant for the user
    tenant_slug = _generate_slug(req.email)
    tenant = TenantModel(
        slug=tenant_slug,
        name=f"{req.name or req.email}'s Tenant",
        tier="pro",  # default tier
        status="active",
    )
    db.add(tenant)
    await db.flush()  # to get tenant.id

    # Create default organization for the tenant (optional)
    org = OrganizationModel(
        tenant_id=tenant.id,
        name="Default Organization",
        slug="default",
        is_default=True,
    )
    db.add(org)
    await db.flush()

    # Hash password
    password_hash = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    # Create user
    user = UserModel(
        email=req.email,
        name=req.name or "",
        role="developer",
        password_hash=password_hash,
        tenant_id=tenant.id,
        organization_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create token pair
    tokens = create_token_pair(
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
        role=user.role,
        organization_id=org.id,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Find user by email
    result = await db.execute(select(UserModel).where(UserModel.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not bcrypt.checkpw(
        req.password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Get tenant and organization info
    result = await db.execute(
        select(TenantModel, OrganizationModel)
        .join(OrganizationModel, OrganizationModel.id == user.organization_id)
        .where(TenantModel.id == user.tenant_id)
    )
    tenant_row = result.first()
    if not tenant_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant or organization not found",
        )
    tenant, org = tenant_row

    # Create token pair
    tokens = create_token_pair(
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
        role=user.role,
        organization_id=org.id,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

from src.api.rest.dependencies import get_current_user_dep, TokenPayload

@router.get("/me")
async def get_current_user_info(
    payload: TokenPayload = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(TenantModel).where(TenantModel.id == payload.tenant_id))
    tenant = result.scalar_one_or_none()
    
    # We should also get the UserModel to fetch email, name, role if needed
    # Or just use payload since it has email and role!
    user_result = await db.execute(select(UserModel).where(UserModel.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    
    # If user doesn't exist but local anon, provide defaults
    try:
        quota = float(tenant.quota_usd) if tenant and tenant.quota_usd else 50.0
    except (ValueError, TypeError):
        quota = 50.0

    return {
        "id": payload.user_id,
        "email": user.email if user else payload.email,
        "name": user.name if user else "Local Admin",
        "role": payload.role,
        "tenant_id": payload.tenant_id,
        "tenant_name": tenant.name if tenant else "Local Sandbox",
        "cost_cents": tenant.cost_cents if tenant else 0,
        "quota_usd": quota
    }
