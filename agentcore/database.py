"""
AgentCore Database - Models + Session Management

Consolidated database: SQLAlchemy models + async session management.
"""
import enum
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, Enum, JSON
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.pool import NullPool

from agentcore.config import get_settings

logger = __import__("logging").getLogger(__name__)

Base = declarative_base()


# =============================================================================
# ENUMS
# =============================================================================

class UserRole(str, enum.Enum):
    admin = "admin"
    developer = "developer"
    viewer = "viewer"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    needs_approval = "needs_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SessionStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deleted = "deleted"


# =============================================================================
# MODELS
# =============================================================================

class TenantModel(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    tier = Column(String(20), default="pro")
    status = Column(String(20), default="active")
    quota_usd = Column(Integer, default=5000)
    cost_cents = Column(Integer, default=0)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("UserModel", back_populates="tenant")
    sessions = relationship("SessionModel", back_populates="tenant")
    tasks = relationship("TaskModel", back_populates="tenant")


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    is_default = Column(Boolean, default=False)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("TenantModel")
    users = relationship("UserModel", back_populates="organization")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(200), default="")
    role = Column(Enum(UserRole), default=UserRole.developer, nullable=False)
    password_hash = Column(String(255), nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    api_key_hash = Column(String(64), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("TenantModel", back_populates="users")
    organization = relationship("OrganizationModel", back_populates="users")
    sessions = relationship("SessionModel", back_populates="user")


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), default="New Session")
    status = Column(Enum(SessionStatus), default=SessionStatus.active, index=True)
    risk_mode = Column(String(20), default="auto")
    active_model_id = Column(String(100), nullable=True)
    context_window = Column(Integer, default=50)
    system_prompt = Column(Text, nullable=True)
    # Session-level API key (BYOK - Bring Your Own Key)
    api_key = Column(Text, nullable=True)
    api_provider = Column(String(50), nullable=True)
    api_base_url = Column(String(500), nullable=True)
    api_model = Column(String(100), nullable=True)
    api_temperature = Column(Integer, default=20)  # stored as int * 100 (e.g., 20 = 0.2)
    api_top_p = Column(Integer, default=95)  # stored as int * 100 (e.g., 95 = 0.95)
    api_max_tokens = Column(Integer, default=8192)
    meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)

    tenant = relationship("TenantModel", back_populates="sessions")

    @property
    def name(self) -> str:
        return self.title

    @property
    def model(self) -> str:
        return self.active_model_id
    user = relationship("UserModel", back_populates="sessions")
    tasks = relationship("TaskModel", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.pending, index=True)
    iteration_count = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    tenant = relationship("TenantModel", back_populates="tasks")
    session = relationship("SessionModel", back_populates="tasks")
    tool_calls = relationship("ToolCallModel", back_populates="task", cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    tool_calls = Column(JSON, default=list)
    tool_call_id = Column(String(36), nullable=True)
    status = Column(String(20), default="completed")
    meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    session = relationship("SessionModel", back_populates="messages")
    task = relationship("TaskModel")


class ToolCallModel(Base):
    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    arguments = Column(JSON, default=dict)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    duration_ms = Column(Integer, default=0)
    approval_required = Column(Boolean, default=False)
    approved = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("TaskModel", back_populates="tool_calls")


class MCPPluginModel(Base):
    __tablename__ = "mcp_plugins"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    endpoint_url = Column(String(500), nullable=True)
    transport = Column(String(20), default="stdio")
    command = Column(String(500), nullable=True)
    args = Column(JSON, default=list)
    env = Column(JSON, default=dict)
    timeout_seconds = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    verify_ssl = Column(Boolean, default=True)
    allowed_hosts = Column(JSON, default=list)
    parameters = Column(JSON, default=list)
    status = Column(String(20), default="registered")
    tools = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_mcp_tenant_name", "tenant_id", "name", unique=True),)


class ApprovalModel(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=lambda: f"appr-{uuid.uuid4().hex[:12]}")
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    requester_id = Column(String(36), nullable=False)
    approver_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(500), nullable=True)
    context = Column(JSON, default=dict)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)


# Indexes
Index("ix_sessions_tenant_user", SessionModel.tenant_id, SessionModel.user_id)
Index("ix_tasks_session_status", TaskModel.session_id, TaskModel.status)
Index("ix_messages_session_created", MessageModel.session_id, MessageModel.created_at)
Index("ix_tool_calls_task_status", ToolCallModel.task_id, ToolCallModel.status)


# =============================================================================
# DATABASE MANAGER
# =============================================================================

class DatabaseManager:
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def initialize(self) -> None:
        settings = get_settings()
        self._engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            poolclass=NullPool if "sqlite" in settings.database_url else None,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False, autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self.initialize()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            self.initialize()
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_tables(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_manager().session() as session:
        yield session


async def init_db() -> None:
    await get_db_manager().create_tables()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def add_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    task_id: str = None,
    tool_call_id: str = None,
) -> MessageModel:
    msg = MessageModel(
        session_id=session_id, task_id=task_id, role=role, content=content,
        tool_call_id=tool_call_id,
    )
    db.add(msg)
    await db.commit()
    return msg


async def add_tool_call(
    db: AsyncSession,
    session_id: str,
    task_id: str,
    name: str,
    arguments: dict,
    status: str,
    result: any = None,
    error: str = None,
) -> ToolCallModel:
    tc = ToolCallModel(
        session_id=session_id, task_id=task_id, name=name, arguments=arguments,
        status=status, result=str(result) if result else None, error=error,
    )
    db.add(tc)
    await db.commit()
    return tc


async def update_tool_call(
    db: AsyncSession,
    tool_call_id: str,
    status: str,
    result: any = None,
    error: str = None,
) -> None:
    from sqlalchemy import update
    await db.execute(
        update(ToolCallModel).where(ToolCallModel.id == tool_call_id).values(
            status=status, result=str(result) if result else None, error=error,
            completed_at=datetime.utcnow(),
        )
    )
    await db.commit()


async def create_session(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    name: str = "New Session",
    model: str = None,
) -> SessionModel:
    session = SessionModel(
        tenant_id=tenant_id, user_id=user_id, title=name,
        active_model_id=model or get_settings().default_model,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def create_task(
    db: AsyncSession,
    tenant_id: str,
    session_id: str,
    description: str,
) -> TaskModel:
    task = TaskModel(
        tenant_id=tenant_id, session_id=session_id,
        description=description, status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task