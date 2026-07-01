"""
AgentCore Auth - JWT + FastAPI Dependencies + Middleware

Consolidated authentication: token creation, validation, API keys, and request middleware.
"""
import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentcore.config import get_settings
from agentcore.database import get_db

logger = logging.getLogger(__name__)

# Security schemes
http_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class TokenPayload:
    """Decoded JWT token payload with typed fields."""

    def __init__(
        self,
        sub: str,  # User ID
        email: str,
        role: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
        permissions: List[str] = None,
        exp: int = 0,
        iat: int = 0,
        jti: str = "",
        type: str = "access",
    ):
        self.sub = sub
        self.email = email
        self.role = role
        self.tenant_id = tenant_id
        self.organization_id = organization_id
        self.session_id = session_id
        self.permissions = permissions or []
        self.exp = exp
        self.iat = iat
        self.jti = jti
        self.type = type

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        return cls(
            sub=data.get("sub", ""),
            email=data.get("email", ""),
            role=data.get("role", "developer"),
            tenant_id=data.get("tenant_id", "local"),
            organization_id=data.get("organization_id"),
            session_id=data.get("session_id"),
            permissions=data.get("permissions", []),
            exp=data.get("exp", 0),
            iat=data.get("iat", 0),
            jti=data.get("jti", ""),
            type=data.get("type", "access"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.sub,
            "email": self.email,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "session_id": self.session_id,
            "permissions": self.permissions,
            "exp": self.exp,
            "iat": self.iat,
            "jti": self.jti,
            "type": self.type,
        }

    @property
    def user_id(self) -> str:
        return self.sub

    def is_expired(self) -> bool:
        return time.time() > self.exp

    def has_permission(self, perm: str) -> bool:
        return "*" in self.permissions or perm in self.permissions

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_developer(self) -> bool:
        return self.role in ("admin", "developer")


class JWTManager:
    """Manages JWT token creation, validation, and refresh."""

    def __init__(self):
        self._settings = get_settings()
        self._algorithm = self._settings.jwt_algorithm
        self._secret = self._settings.jwt_secret
        self._access_ttl = self._settings.access_token_expire_minutes * 60
        self._refresh_ttl = self._settings.refresh_token_expire_days * 86400

        if self._settings.is_production and not self._secret:
            raise ValueError("JWT_SECRET must be set in production")

        if not self._secret:
            import os
            secret_file = ".runtime_secret.key"
            if os.path.exists(secret_file):
                try:
                    with open(secret_file, "r") as f:
                        self._secret = f.read().strip()
                except Exception:
                    pass
            if not self._secret:
                self._secret = secrets.token_urlsafe(32)
                try:
                    with open(secret_file, "w") as f:
                        f.write(self._secret)
                except Exception:
                    pass
            logger.warning("Using generated persistent JWT secret - not for production!")

    def create_access_token(
        self,
        user_id: str,
        email: str,
        role: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
        permissions: List[str] = None,
        extra_claims: Dict[str, Any] = None,
    ) -> str:
        now = int(time.time())
        jti = secrets.token_urlsafe(16)

        payload = TokenPayload(
            sub=user_id,
            email=email,
            role=role,
            tenant_id=tenant_id,
            organization_id=organization_id,
            session_id=session_id,
            permissions=permissions or self._default_permissions(role),
            exp=now + self._access_ttl,
            iat=now,
            jti=jti,
            type="access",
        )

        if extra_claims:
            payload_dict = payload.to_dict()
            payload_dict.update(extra_claims)
            return jwt.encode(payload_dict, self._secret, algorithm=self._algorithm)

        return jwt.encode(payload.to_dict(), self._secret, algorithm=self._algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        now = int(time.time())
        jti = secrets.token_urlsafe(16)

        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "exp": now + self._refresh_ttl,
            "iat": now,
            "jti": jti,
            "type": "refresh",
        }

        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        role: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, str]:
        return {
            "access_token": self.create_access_token(
                user_id, email, role, tenant_id, organization_id, session_id
            ),
            "refresh_token": self.create_refresh_token(user_id, tenant_id, session_id),
            "token_type": "bearer",
            "expires_in": self._access_ttl,
        }

    def decode_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"verify_exp": True},
            )
            return TokenPayload.from_dict(payload)
        except JWTError as e:
            logger.warning(f"Token decode failed: {e}")
            raise ValueError(f"Invalid token: {e}")

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        try:
            return self.decode_token(token)
        except ValueError:
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        payload = self.verify_token(refresh_token)
        if not payload or payload.type != "refresh":
            return None

        return self.create_access_token(
            user_id=payload.sub,
            email="",
            role="developer",
            tenant_id=payload.tenant_id,
            organization_id=payload.organization_id,
            session_id=payload.session_id,
        )

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    def _default_permissions(self, role: str) -> List[str]:
        perms = {
            "admin": ["*"],
            "developer": [
                "chat", "tools", "mcp", "sessions", "tasks",
                "read", "write", "execute", "search",
            ],
            "viewer": ["chat", "read", "search"],
        }
        return perms.get(role, ["chat", "read"])


_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# Convenience functions
def create_access_token(
    user_id: str,
    email: str,
    role: str,
    tenant_id: str,
    organization_id: Optional[str] = None,
    session_id: Optional[str] = None,
    permissions: List[str] = None,
    extra_claims: Dict[str, Any] = None,
) -> str:
    return get_jwt_manager().create_access_token(
        user_id=user_id, email=email, role=role, tenant_id=tenant_id,
        organization_id=organization_id, session_id=session_id,
        permissions=permissions, extra_claims=extra_claims,
    )


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    session_id: Optional[str] = None,
) -> str:
    return get_jwt_manager().create_refresh_token(
        user_id=user_id, tenant_id=tenant_id, session_id=session_id
    )


def create_token_pair(
    user_id: str,
    email: str,
    role: str,
    tenant_id: str,
    organization_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, str]:
    return get_jwt_manager().create_token_pair(
        user_id=user_id, email=email, role=role, tenant_id=tenant_id,
        organization_id=organization_id, session_id=session_id,
    )


def decode_token(token: str) -> TokenPayload:
    return get_jwt_manager().decode_token(token)


def verify_token(token: str) -> Optional[TokenPayload]:
    return get_jwt_manager().verify_token(token)


def hash_password(password: str) -> str:
    return get_jwt_manager().hash_password(password)


def verify_password(plain: str, hashed: str) -> bool:
    return get_jwt_manager().verify_password(plain, hashed)


# --- FastAPI Dependencies ---


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    if credentials and credentials.credentials:
        token = credentials.credentials
        payload = verify_token(token)
        if payload:
            user = await _get_user(db, payload.sub)
            if user and user.is_active:
                payload.role = user.role
                payload.email = user.email
                payload.organization_id = user.organization_id
                return payload

    if api_key:
        payload = await _verify_api_key(db, api_key)
        if payload:
            return payload

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
    try:
        return await get_current_user(credentials, api_key, db)
    except HTTPException:
        return None


async def _get_user(db: AsyncSession, user_id: str):
    from agentcore.database import UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def _verify_api_key(db: AsyncSession, api_key: str) -> Optional[TokenPayload]:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    from agentcore.database import UserModel
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
            exp=0,
            iat=0,
            jti="api",
            type="api_key",
        )
    return None


def require_roles(*allowed_roles: str) -> Callable:
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
    async def _check_tenant(
        current_user: TokenPayload = Depends(get_current_user),
        request: Request = None,
    ) -> TokenPayload:
        if current_user.is_admin():
            return current_user

        requested_tenant = None
        if request:
            requested_tenant = request.path_params.get(tenant_id_param) or request.query_params.get(tenant_id_param)

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
    async def _check_session(
        current_user: TokenPayload = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        request: Request = None,
    ) -> TokenPayload:
        if current_user.is_admin():
            return current_user

        session_id = None
        if request:
            session_id = request.path_params.get(session_id_param) or request.query_params.get(session_id_param)

        if session_id:
            from agentcore.database import SessionModel
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found",
                )

            if session.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session belongs to different tenant",
                )

            if session.user_id != current_user.sub and current_user.role != "admin":
                if current_user.organization_id != session.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this session",
                    )
        return current_user
    return _check_session


require_admin = require_roles("admin")
require_developer = require_roles("admin", "developer")
require_viewer = require_roles("admin", "developer", "viewer")


def get_tenant_id(
    current_user: TokenPayload = Depends(get_current_user),
) -> str:
    return current_user.tenant_id


def get_organization_id(
    current_user: TokenPayload = Depends(get_current_user),
) -> Optional[str]:
    return current_user.organization_id


async def get_ws_token_payload(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WebSocket token",
        )

    user = await _get_user(db, payload.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return payload


# --- Middleware ---

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


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: set = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or PUBLIC_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        if request.url.path.startswith("/ws") or request.url.path.startswith("/api/v1/ws"):
            return await call_next(request)

        token = self._extract_token(request)

        if token:
            payload = verify_token(token)
            if payload:
                async for db in get_db():
                    user = await _get_user(db, payload.sub)
                    if user and user.is_active:
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
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "User not found or inactive"},
                        )
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )
        else:
            request.state.authenticated = False

        # Tenant header
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            request.state.tenant_id = tenant_header

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    def _extract_token(self, request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        token = request.cookies.get("access_token")
        if token:
            return token

        token = request.query_params.get("token")
        if token:
            return token

        return None


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not hasattr(request.state, "tenant_id") or not request.state.tenant_id:
            request.state.tenant_id = request.headers.get("X-Tenant-ID") or "local"

        response = await call_next(request)
        response.headers["X-Tenant-ID"] = request.state.tenant_id
        return response


def get_request_context(request: Request) -> dict:
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


def get_current_context(request: Request) -> dict:
    return get_request_context(request)


# --- CORS ---

def get_cors_config() -> Tuple[List[str], List[str], List[str], bool]:
    is_prod = get_settings().is_production

    if is_prod:
        origins = os.environ.get(
            "ALLOWED_ORIGINS",
            "https://app.antigravity.dev,https://api.antigravity.dev,https://*.github.io,https://*.trycloudflare.com"
        ).split(",")
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        headers = ["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-ID"]
    else:
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8089",
            "http://localhost:8089",
            "http://0.0.0.0:8089",
            "ws://localhost:8089",
        ]
        methods = ["*"]
        headers = ["*"]

    return origins, methods, headers, is_prod


def setup_cors(app: FastAPI):
    origins, methods, headers, is_prod = get_cors_config()

    if is_prod:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=".*",
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
            expose_headers=["X-Request-ID"],
            max_age=3600,
        )