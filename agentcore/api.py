"""
AgentCore API - FastAPI + All Routes

Consolidated API: FastAPI app, middleware, all REST endpoints in one file.
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from agentcore.config import get_settings
from agentcore.auth import (
    AuthMiddleware, get_current_user, create_token_pair, hash_password,
    verify_password, TokenPayload,
)
from agentcore.database import (
    get_db, TenantModel, UserModel, OrganizationModel, SessionModel,
    TaskModel, ApprovalModel, MessageModel, Base,
    create_session as db_create_session, create_task as db_create_task,
)
from agentcore.governance import get_governance_engine
from agentcore.tools import get_tool_registry

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

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
    name: str = "New Session"
    model: str = ""
    system_prompt: str = ""

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


# =============================================================================
# ROUTER: HEALTH
# =============================================================================

health_router = APIRouter(prefix="/health", tags=["health"])

@health_router.get("/")
async def health_check():
    return {"status": "healthy", "service": "AgentCore", "version": "1.0.0"}

@health_router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status,
        "environment": settings.app_env,
    }


# =============================================================================
# ROUTER: AUTH
# =============================================================================

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

    tokens = create_token_pair(tenant.id, user.id, user.email, user.role, org.id)
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

    tokens = create_token_pair(user.tenant_id, user.id, user.email, user.role, user.organization_id)
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
    return {
        "id": user.user_id, "email": db_user.email if db_user else user.email,
        "name": db_user.name if db_user else "User", "role": user.role,
        "tenant_id": user.tenant_id,
    }


# =============================================================================
# ROUTER: SESSIONS
# =============================================================================

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])

@sessions_router.post("/", status_code=201)
async def create_session(
    req: SessionCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = SessionModel(
        tenant_id=user.tenant_id, user_id=user.user_id,
        name=req.name, model=req.model or settings.default_model,
        system_prompt=req.system_prompt,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "name": session.name}

@sessions_router.get("/")
async def list_sessions(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.tenant_id == user.tenant_id)
        .order_by(SessionModel.created_at.desc()).limit(50)
    )
    return {
        "sessions": [
            {"id": s.id, "name": s.name, "model": s.model, "created_at": s.created_at.isoformat()}
            for s in result.scalars().all()
        ]
    }

@sessions_router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    msgs = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at)
    )
    return {
        "id": session.id, "name": session.name, "model": session.model,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in msgs.scalars().all()
        ],
    }

@sessions_router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
    return {"deleted": True}


# =============================================================================
# ROUTER: TASKS
# =============================================================================

tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])

@tasks_router.post("/", status_code=202)
async def dispatch_task(
    req: TaskCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session access
    result = await db.execute(
        select(SessionModel.id).where(
            and_(SessionModel.id == req.session_id, SessionModel.tenant_id == user.tenant_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not authorized or session not found")

    task = TaskModel(
        tenant_id=user.tenant_id, session_id=req.session_id,
        description=req.description, status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"status": "accepted", "task_id": task.id}

@tasks_router.get("/")
async def list_tasks(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TaskModel).where(TaskModel.tenant_id == user.tenant_id)
        .order_by(TaskModel.created_at.desc()).limit(50)
    )
    return {
        "tasks": [
            {"id": t.id, "description": t.description, "status": t.status,
             "created_at": t.created_at.isoformat()}
            for t in result.scalars().all()
        ]
    }


# =============================================================================
# ROUTER: TOOLS
# =============================================================================

tools_router = APIRouter(prefix="/tools", tags=["tools"])

@tools_router.get("/")
async def list_tools(
    category: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    return registry.get_schemas(category)

@tools_router.get("/categories")
async def get_categories(user: TokenPayload = Depends(get_current_user)):
    registry = get_tool_registry()
    return registry.get_categories()

@tools_router.get("/openai-functions")
async def get_openai_functions(
    category: Optional[str] = None,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    return registry.get_openai_functions(category)

@tools_router.post("/execute")
async def execute_tool(
    req: ToolExecuteRequest,
    user: TokenPayload = Depends(get_current_user),
):
    registry = get_tool_registry()
    args = req.arguments.copy()
    args["context"] = {"user_id": user.user_id, "tenant_id": user.tenant_id}
    result = await registry.execute(req.name, args)
    return {"success": result.success, "data": result.data, "error": result.error}

@tools_router.post("/discover-mcp")
async def discover_mcp_tools(user: TokenPayload = Depends(get_current_user)):
    registry = get_tool_registry()
    count = await registry.discover_mcp_tools()
    return {"discovered": count}


# =============================================================================
# ROUTER: GOVERNANCE
# =============================================================================

governance_router = APIRouter(prefix="/governance", tags=["governance"])

@governance_router.post("/check")
async def check_policy(
    req: PolicyCheckRequest,
    user: TokenPayload = Depends(get_current_user),
):
    engine = get_governance_engine()
    decision = engine.evaluate(
        type("Ctx", (), {"user_role": user.role, "tenant_id": user.tenant_id})(),
        req.action, req.resource, req.context,
    )
    return {"allowed": decision.allowed, "reason": decision.reason}

@governance_router.get("/roles")
async def list_roles(user: TokenPayload = Depends(get_current_user)):
    from agentcore.governance import Role, ROLE_TOOL_CATEGORIES
    return [
        {"name": role.value, "categories": cats}
        for role, cats in ROLE_TOOL_CATEGORIES.items()
    ]


# =============================================================================
# ROUTER: APPROVALS
# =============================================================================

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


# =============================================================================
# APP FACTORY
# =============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentCore API",
        description="Minimalist agentic runtime",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware
    app.add_middleware(AuthMiddleware)

    # Mount routers
    prefix = settings.api_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(auth_router, prefix=prefix)
    app.include_router(sessions_router, prefix=prefix)
    app.include_router(tasks_router, prefix=prefix)
    app.include_router(tools_router, prefix=prefix)
    app.include_router(governance_router, prefix=prefix)
    app.include_router(approvals_router, prefix=prefix)

    # WebSocket routes
    from agentcore.websocket import router as ws_router
    app.include_router(ws_router, prefix=f"{prefix}/ws")

    # Root health
    @app.get("/health")
    async def root_health():
        return {"status": "healthy"}

    # Startup: init DB
    @app.on_event("startup")
    async def on_startup():
        from agentcore.database import init_db
        await init_db()
        logger.info("AgentCore started")

    return app
