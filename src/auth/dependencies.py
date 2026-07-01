"""
Auth Dependencies - FastAPI Security Dependencies

Provides reusable FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import Optional, List, Callable
from functools import wraps

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import (
    TokenPayload,
    decode_token,
    verify_token,
    get_jwt_manager,
)
from src.db.session import get_db
from src.db.models import UserModel, SessionModel
from src.config.settings import get_settings
from src.runtime.paths import resolve_tenant_id

logger = logging.getLogger(__name__)

# Security schemes
http_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    """
    Get current authenticated user from JWT or API key.
    
    Priority:
    1. Bearer token (JWT)
    2. API key header
    3. Anonymous (if allowed by endpoint)
    """
    # Try JWT first
    if credentials and credentials.credentials:
        token = credentials.credentials
        payload = verify_token(token)
        if payload:
            # Verify user still exists and is active
            user = await _get_user(db, payload.sub)
            if user and user.is_active:
                # Update token with fresh user data
                payload.role = user.role
                payload.email = user.email
                payload.organization_id = user.organization_id
                return payload
    
    # Try API key
    if api_key:
        payload = await _verify_api_key(db, api_key)
        if payload:
            return payload
    
    # No valid auth
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[TokenPayload]:
    """Get current user if authenticated, otherwise None."""
    try:
        return await get_current_user(credentials, api_key, db)
    except HTTPException:
        return None


async def _get_user(db: AsyncSession, user_id: str) -> Optional[UserModel]:
    """Fetch user by ID."""
    from sqlalchemy import select
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def _verify_api_key(db: AsyncSession, api_key: str) -> Optional[TokenPayload]:
    """Verify API key and return token payload."""
    import hashlib
    
    # Hash the provided API key
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    from sqlalchemy import select
    result = await db.execute(
        select(UserModel).where(UserModel.api_key_hash == key_hash)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_active:
        return TokenPayload(
            sub=user.id,
            email=user.email,
            role=user.role,
            tenant_id=user.tenant_id,
            organization_id=user.organization_id,
            permissions=["api"],
            exp=0,  # No expiry for API keys
            iat=0,
            jti="api",
            type="api_key",
        )
    
    return None


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory for role-based access control."""
    async def _check_role(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(allowed_roles)}. Current: {current_user.role}",
            )
        return current_user
    return _check_role


def require_permissions(*required_perms: str) -> Callable:
    """Dependency factory for permission-based access control."""
    async def _check_perms(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        for perm in required_perms:
            if not current_user.has_permission(perm):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {perm}",
                )
        return current_user
    return _check_perms


def require_tenant_access(
    tenant_id_param: str = "tenant_id",
) -> Callable:
    """Dependency to ensure user can access requested tenant."""
    async def _check_tenant(
        current_user: TokenPayload = Depends(get_current_user),
        request: Request = None,
    ) -> TokenPayload:
        # Admin can access any tenant
        if current_user.is_admin():
            return current_user
        
        # Get tenant_id from path/query params
        requested_tenant = None
        if request:
            requested_tenant = request.path_params.get(tenant_id_param) or request.query_params.get(tenant_id_param)
        
        if hasattr
        # Check if user belongs to tenant or has cross-tenant access
        if requested_tenant and current_user.tenant_id != requested_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to tenant: {requested_tenant}",
            )
        
        return current_user
    return _check_tenant


def require_session_access(
    session_id_param: str = "session_id",
) -> Callable:
    """Dependency to ensure user can access requested session."""
    async def _check_session(
        current_user: TokenPayload = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        request: Request = None,
    ) -> TokenPayload:
        # Admin can access any session
        if current_user.is_admin():
            return current_user
        
        session_id = None
        if request:
            session_id = request.path_params.get(session_id_param) or request.query_params.get(session_id_param)
        
        if session_id:
            from sqlalchemy import select
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found",
                )
            
            # Check tenant match
            if session.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session belongs to different tenant",
                )
            
            # Check ownership (unless admin/developer with org access)
            if session.user_id != current_user.sub and current_user.role != "admin":
                # Check org membership
                if current_user.organization_id != session.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this session",
                    )
        
        return current_user
    return _check_session


# Common role dependencies
require_admin = require_roles("admin")
require_developer = require_roles("admin", "developer")
require_viewer = require_roles("admin", "developer", "viewer")


# Tenant context extraction
def get_tenant_id(
    current_user: TokenPayload = Depends(get_current_user),
) -> str:
    """Extract tenant ID from current user."""
    return current_user.tenant_id


def get_organization_id(
    current_user: TokenPayload = Depends(get_current_user),
) -> Optional[str]:
    """Extract organization ID from current user."""
    return current_user.organization_id


# Session context (for WebSocket auth)
async def get_ws_token_payload(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    """Validate WebSocket connection token."""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WebSocket token",
        )
    
    # Verify user still active
    user = await _get_user(db, payload.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return payload