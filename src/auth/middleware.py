"""
Auth Middleware - Request Processing for Tenant Context

Adds tenant/user context to every request and handles session management.
"""
import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.auth.jwt import verify_token, get_jwt_manager
from src.auth.dependencies import _verify_api_key, _get_user
from src.db.session import get_db
from src.runtime.paths import resolve_tenant_id

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate auth on every request."""
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/api/v1/health",
        "/api/docs",
        "/api/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
    }
    
    def __init__(self, app, exclude_paths: set = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or self.PUBLIC_PATHS
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for public paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Skip for WebSocket (handled separately)
        if request.url.path.startswith("/ws") or request.url.path.startswith("/api/v1/ws"):
            return await call_next(request)
        
        # Extract token
        token = self._extract_token(request)
        
        if token:
            # Validate token
            payload = verify_token(token)
            
            if payload:
                # Get DB session
                async for db in get_db():
                    user = await _get_user(db, payload.sub)
                    if user and user.is_active:
                        # Attach user context to request state
                        request.state.user_id = user.id
                        request.state.user_email = user.email
                        request.state.user_role = user.role
                        request.state.tenant_id = user.tenant_id
                        request.state.organization_id = user.organization_id
                        request.state.session_id = payload.session_id
                        request.state.permissions = payload.permissions
                        request.state.authenticated = True
                        break
                    else:
                        # Invalid user
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "User not found or inactive"},
                        )
            else:
                # Invalid token
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )
        else:
            # No token - allow but mark unauthenticated
            request.state.authenticated = False
        
        # Add tenant context from header (for multi-tenant routing)
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            request.state.tenant_id = resolve_tenant_id(tenant_header)
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from Authorization header or cookie."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # Check cookie
        token = request.cookies.get("access_token")
        if token:
            return token
        
        # Check query param (for WebSocket upgrades)
        token = request.query_params.get("token")
        if token:
            return token
        
        return None


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure tenant context is available."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Ensure tenant_id is set
        if not hasattr(request.state, "tenant_id") or not request.state.tenant_id:
            # Try to resolve from various sources
            request.state.tenant_id = resolve_tenant_id(
                request.headers.get("X-Tenant-ID") or "local"
            )
        
        # Add to response headers for debugging
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = request.state.tenant_id
        
        return response


# Helper to get current request context
def get_request_context(request: Request) -> dict:
    """Extract authentication context from request state."""
    return {
        "user_id": getattr(request.state, "user_id", None),
        "user_email": getattr(request.state, "user_email", None),
        "user_role": getattr(request.state, "user_role", None),
        "tenant_id": getattr(request.state, "tenant_id", "local"),
        "organization_id": getattr(request.state, "organization_id", None),
        "session_id": getattr(request.state, "session_id", None),
        "permissions": getattr(request.state, "permissions", []),
        "authenticated": getattr(request.state, "authenticated", False),
    }


# FastAPI dependency for request context
def get_current_context(request: Request) -> dict:
    """FastAPI dependency to get request context."""
    return get_request_context(request)