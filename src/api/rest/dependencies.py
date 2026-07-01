"""
FastAPI dependencies — Multi-tenant aware.

- Tenant context from JWT
- Per-tenant rate limiting
- Tenant-scoped database queries

Backward compatibility: Legacy functions for old router code.
"""
import os
from typing import AsyncGenerator, Optional

from fastapi import Header, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session
from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.infrastructure.runtime.config import ALLOW_ANON_LOCAL
from src.infrastructure.auth.jwt_auth import (
    decode_token,
    TokenPayload,
    create_token_pair,
)

REDIS_URL = os.environ.get("REDIS_URL", "")

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_broker_dep():
    return await get_streams_broker()


async def get_current_user_dep(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TokenPayload:
    """Get current user from JWT token (header or query param)."""
    token = None
    if credentials:
        token = credentials.credentials
    elif request and "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        if ALLOW_ANON_LOCAL:
            return TokenPayload(
                tenant_id="local",
                user_id="local",
                email="local@dev.local",
                role="developer",
                tier="pro",
                limits={"rpm": 60, "rph": 500},
                exp=0,
                iat=0,
                organization_id=None,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    
    return decode_token(token)


async def get_tenant_id(
    user: TokenPayload = Depends(get_current_user_dep),
) -> str:
    """Get current tenant ID."""
    return user.tenant_id


async def check_rate_limit(user: TokenPayload = Depends(get_current_user_dep)):
    """Rate limit check per tenant."""
    if not REDIS_URL:
        return
    
    from src.infrastructure.resilience.rate_limiter import RedisRateLimiter, RateLimitConfig, RateLimitStrategy
    
    limiter = RedisRateLimiter(REDIS_URL)
    config = RateLimitConfig(
        requests_per_minute=user.limits.get("rpm", 60),
        requests_per_hour=user.limits.get("rph", 500),
        strategy=RateLimitStrategy.SLIDING_WINDOW,
    )
    
    limit_result = await limiter.check_rate_limit(f"ratelimit:{user.tenant_id}", config)
    
    if not limit_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": int(limit_result.retry_after or 60),
                "limit": limit_result.limit,
            }
        )


# Backward compatibility: Legacy functions for old routers
async def get_current_user(
    payload: TokenPayload = Depends(get_current_user_dep)
) -> str:
    """Legacy: Return user_id string (backward compat)."""
    return payload.user_id


async def resolve_current_user(tenant_id: str | None) -> str:
    """Legacy: Resolve current user ID."""
    if tenant_id and tenant_id.strip():
        return tenant_id.strip()
    if ALLOW_ANON_LOCAL:
        return "local"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-Tenant-Id header.",
    )
