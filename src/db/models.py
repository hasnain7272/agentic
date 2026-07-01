"""
Database Models - SQLAlchemy Models

All ORM models in one file for easy reference.
Each model maps to a table with proper indexes and constraints.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, Enum, JSON
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


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


class TenantModel(Base):
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    tier = Column(String(20), default="pro")  # free, pro, enterprise
    status = Column(String(20), default="active")
    quota_usd = Column(Integer, default=5000)  # cents
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
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)
    
    tenant = relationship("TenantModel", back_populates="sessions")
    user = relationship("UserModel", back_populates="sessions")
    tasks = relationship("TaskModel", back_populates="session")
    messages = relationship("MessageModel", back_populates="session")


class TaskModel(Base):
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.pending, index=True)
    iteration_count = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    tenant = relationship("TenantModel", back_populates="tasks")
    session = relationship("SessionModel", back_populates="tasks")
    tool_calls = relationship("ToolCallModel", back_populates="task")


class MessageModel(Base):
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    tool_calls = Column(JSON, default=list)
    tool_call_id = Column(String(36), nullable=True)
    status = Column(String(20), default="completed")
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    session = relationship("SessionModel", back_populates="messages")
    task = relationship("TaskModel")


class ToolCallModel(Base):
    __tablename__ = "tool_calls"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    arguments = Column(JSON, default=dict)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
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
    endpoint_url = Column(String(500), nullable=True)  # For HTTP MCP
    transport = Column(String(20), default="stdio")  # stdio, http
    command = Column(String(500), nullable=True)  # For stdio
    args = Column(JSON, default=list)
    env = Column(JSON, default=dict)
    timeout_seconds = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    verify_ssl = Column(Boolean, default=True)
    allowed_hosts = Column(JSON, default=list)
    parameters = Column(JSON, default=list)
    status = Column(String(20), default="registered")  # registered, running, error
    tools = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_mcp_tenant_name", "tenant_id", "name", unique=True),
    )


# Indexes for common queries
Index("ix_sessions_tenant_user", SessionModel.tenant_id, SessionModel.user_id)
Index("ix_tasks_session_status", TaskModel.session_id, TaskModel.status)
Index("ix_messages_session_created", MessageModel.session_id, MessageModel.created_at)
Index("ix_tool_calls_task_status", ToolCallModel.task_id, ToolCallModel.status)