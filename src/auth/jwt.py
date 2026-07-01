"""
JWT Authentication - Token Creation and Validation

Handles JWT access/refresh tokens with tenant context.
Uses RS256 for production, HS256 for development.
"""
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from jose import jwt, JWTError
from passlib.context import CryptContext

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload:
    """Decoded JWT token payload with typed fields."""
    
    def __init__(
        self,
        sub: str,                    # User ID
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
        """Create from decoded JWT payload."""
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
        """Convert to dictionary for encoding."""
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
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return time.time() > self.exp
    
    def has_permission(self, perm: str) -> bool:
        """Check if token has specific permission."""
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
        
        # Validate secret in production
        if self._settings.is_production and not self._secret:
            raise ValueError("JWT_SECRET must be set in production")
        
        # Generate secret if not set (dev only)
        if not self._secret:
            self._secret = secrets.token_urlsafe(32)
            logger.warning("Using generated JWT secret - not for production!")
    
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
        """Create short-lived access token."""
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
        """Create long-lived refresh token."""
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
        """Create both access and refresh tokens."""
        return {
            "access_token": self.create_access_token(
                user_id, email, role, tenant_id, organization_id, session_id
            ),
            "refresh_token": self.create_refresh_token(user_id, tenant_id, session_id),
            "token_type": "bearer",
            "expires_in": self._access_ttl,
        }
    
    def decode_token(self, token: str) -> TokenPayload:
        """Decode and validate JWT token."""
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
        """Verify token without raising exception."""
        try:
            return self.decode_token(token)
        except ValueError:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create new access token from valid refresh token."""
        payload = self.verify_token(refresh_token)
        if not payload or payload.type != "refresh":
            return None
        
        # In production, verify refresh token against stored hash
        # For now, trust valid refresh tokens
        return self.create_access_token(
            user_id=payload.sub,
            email="",  # Would fetch from DB
            role="developer",  # Would fetch from DB
            tenant_id=payload.tenant_id,
            organization_id=payload.organization_id,
            session_id=payload.session_id,
        )
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain: str, hashed: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain, hashed)
    
    def _default_permissions(self, role: str) -> List[str]:
        """Get default permissions for role."""
        perms = {
            "admin": ["*"],
            "developer": [
                "chat", "tools", "mcp", "sessions", "tasks",
                "read", "write", "execute", "search",
            ],
            "viewer": ["chat", "read", "search"],
        }
        return perms.get(role, ["chat", "read"])


# Singleton
_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    """Get or create global JWT manager."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# Convenience functions
def create_access_token(**kwargs) -> str:
    return get_jwt_manager().create_access_token(**kwargs)


def create_refresh_token(**kwargs) -> str:
    return get_jwt_manager().create_refresh_token(**kwargs)


def create_token_pair(**kwargs) -> Dict[str, str]:
    return get_jwt_manager().create_token_pair(**kwargs)


def decode_token(token: str) -> TokenPayload:
    return get_jwt_manager().decode_token(token)


def verify_token(token: str) -> Optional[TokenPayload]:
    return get_jwt_manager().verify_token(token)


def hash_password(password: str) -> str:
    return get_jwt_manager().hash_password(password)


def verify_password(plain: str, hashed: str) -> bool:
    return get_jwt_manager().verify_password(plain, hashed)