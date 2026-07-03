"""
AgentCore - API Schemas
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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

class SessionCreateRequest(BaseModel):
    name: Optional[str] = None
    model: str = ""
    system_prompt: str = ""
    agentic_naming: bool = True
    # Session-level BYOK (Bring Your Own Key)
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    api_temperature: Optional[float] = 0.2
    api_top_p: Optional[float] = 0.95
    api_max_tokens: Optional[int] = 8192

class TaskCreateRequest(BaseModel):
    session_id: str
    description: str

class ToolExecuteRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}

class PolicyCheckRequest(BaseModel):
    action: str
    resource: Optional[str] = None
    context: Dict[str, Any] = {}

class ApprovalDecision(BaseModel):
    approved: bool
    reason: Optional[str] = None

class ChatCreateRequest(BaseModel):
    session_id: str
    message: str
    shadow_mode: Optional[bool] = False
    active_model_id: Optional[str] = None

class BYOMConfigRequest(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None
    temperature: Optional[float] = 0.2
    top_p: Optional[float] = 0.95
    max_tokens: Optional[int] = 8192