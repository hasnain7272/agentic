"""
Governance Approval - Human-in-the-Loop (HITL) Approval Flow

Manages approval requests, decisions, and callbacks for governed tools.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.db.session import get_db
from src.db.models import ToolCallModel

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """Approval request for a governed tool action."""
    id: str
    session_id: str
    task_id: str
    tool_name: str
    arguments: Dict[str, Any]
    risk_mode: str
    message: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    
    # Callback for async waiting
    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _result: Optional[bool] = field(default=None, init=False)
    
    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=5)
    
    def approve(self, user_id: str, reason: str = None) -> None:
        """Mark as approved."""
        self.status = ApprovalStatus.APPROVED
        self.decided_at = datetime.utcnow()
        self.decided_by = user_id
        self.decision_reason = reason
        self._result = True
        self._event.set()
    
    def deny(self, user_id: str, reason: str = None) -> None:
        """Mark as denied."""
        self.status = ApprovalStatus.DENIED
        self.decided_at = datetime.utcnow()
        self.decided_by = user_id
        self.decision_reason = reason
        self._result = False
        self._event.set()
    
    def cancel(self) -> None:
        """Cancel the approval request."""
        self.status = ApprovalStatus.CANCELLED
        self._event.set()
    
    def is_expired(self) -> bool:
        """Check if approval has expired."""
        return datetime.utcnow() > self.expires_at
    
    async def wait(self, timeout: float = None) -> bool:
        """Wait for approval decision."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return self._result or False
        except asyncio.TimeoutError:
            self.status = ApprovalStatus.EXPIRED
            return False


class ApprovalManager:
    """Manages approval requests and decisions."""
    
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._session_requests: Dict[str, List[str]] = {}  # session_id -> [request_ids]
        self._callbacks: Dict[str, List[Callable]] = {}  # request_id -> [callbacks]
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired requests."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Approval cleanup error: {e}")
    
    async def _cleanup_expired(self) -> None:
        """Remove expired approval requests."""
        now = datetime.utcnow()
        expired_ids = [
            req_id for req_id, req in self._requests.items()
            if req.status == ApprovalStatus.PENDING and req.expires_at < now
        ]
        
        for req_id in expired_ids:
            req = self._requests[req_id]
            req.status = ApprovalStatus.EXPIRED
            req._event.set()
            
            # Remove from session index
            session_id = req.session_id
            if session_id in self._session_requests:
                self._session_requests[session_id] = [
                    rid for rid in self._session_requests[session_id] if rid != req_id
                ]
            
            logger.info(f"Approval expired: {req_id}")
    
    def create_request(
        self,
        session_id: str,
        task_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_mode: str,
        message: str = None,
        ttl_minutes: int = 5,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        request_id = f"appr-{uuid.uuid4().hex[:12]}"
        
        request = ApprovalRequest(
            id=request_id,
            session_id=session_id,
            task_id=task_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_mode=risk_mode,
            message=message or f"Approve execution of '{tool_name}'?",
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        )
        
        self._requests[request_id] = request
        
        # Index by session
        if session_id not in self._session_requests:
            self._session_requests[session_id] = []
        self._session_requests[session_id].append(request_id)
        
        logger.info(f"Created approval request: {request_id} for {tool_name}")
        return request
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self._requests.get(request_id)
    
    def get_session_requests(self, session_id: str) -> List[ApprovalRequest]:
        """Get all approval requests for a session."""
        request_ids = self._session_requests.get(session_id, [])
        return [self._requests[rid] for rid in request_ids if rid in self._requests]
    
    def get_pending_requests(self, session_id: str = None) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        requests = self._requests.values()
        if session_id:
            requests = [r for r in requests if r.session_id == session_id]
        return [r for r in requests if r.status == ApprovalStatus.PENDING]
    
    async def decide(
        self,
        request_id: str,
        decision: bool,
        user_id: str,
        reason: str = None,
    ) -> bool:
        """Record approval decision."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Approval request not found: {request_id}")
        
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already decided: {request.status.value}")
        
        if decision:
            request.approve(user_id, reason)
        else:
            request.deny(user_id, reason)
        
        # Notify callbacks
        for callback in self._callbacks.get(request_id, []):
            try:
                await callback(request)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")
        
        # Persist to database
        await self._persist_decision(request)
        
        logger.info(f"Approval {request_id}: {'APPROVED' if decision else 'DENIED'} by {user_id}")
        return True
    
    async def _persist_decision(self, request: ApprovalRequest) -> None:
        """Persist approval decision to database."""
        try:
            async for db in get_db():
                # Find tool call record
                from sqlalchemy import select
                result = await db.execute(
                    select(ToolCallModel).where(
                        ToolCallModel.task_id == request.task_id,
                        ToolCallModel.name == request.tool_name,
                    )
                )
                tool_call = result.scalar_one_or_none()
                
                if tool_call:
                    tool_call.approved = request.status == ApprovalStatus.APPROVED
                    tool_call.status = "approved" if request.status == ApprovalStatus.APPROVED else "denied"
                    await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist approval: {e}")
    
    def register_callback(self, request_id: str, callback: Callable) -> None:
        """Register callback for approval decision."""
        if request_id not in self._callbacks:
            self._callbacks[request_id] = []
        self._callbacks[request_id].append(callback)
    
    def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending approval request."""
        request = self._requests.get(request_id)
        if request and request.status == ApprovalStatus.PENDING:
            request.cancel()
            return True
        return False
    
    def cancel_session_requests(self, session_id: str) -> int:
        """Cancel all pending requests for a session."""
        count = 0
        for request_id in self._session_requests.get(session_id, []):
            if self.cancel_request(request_id):
                count += 1
        return count


# Global manager
_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """Get or create the global approval manager."""
    global _manager
    if _manager is None:
        _manager = ApprovalManager()
    return _manager


# Convenience functions
async def request_approval(
    session_id: str,
    task_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    risk_mode: str,
    message: str = None,
) -> ApprovalRequest:
    """Create and return an approval request."""
    manager = get_approval_manager()
    return manager.create_request(session_id, task_id, tool_name, arguments, risk_mode, message)


async def wait_for_approval(request: ApprovalRequest, timeout: float = 300) -> bool:
    """Wait for approval decision with timeout."""
    return await request.wait(timeout=timeout)


async def approve_request(request_id: str, user_id: str, reason: str = None) -> bool:
    """Approve a request by ID."""
    manager = get_approval_manager()
    return await manager.decide(request_id, True, user_id, reason)


async def deny_request(request_id: str, user_id: str, reason: str = None) -> bool:
    """Deny a request by ID."""
    manager = get_approval_manager()
    return await manager.decide(request_id, False, user_id, reason)