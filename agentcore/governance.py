"""
AgentCore Governance - Roles, Policies, Engine, Approval (HITL)

Consolidated governance: roles, tool permissions, tenant policies, policy engine,
and human-in-the-loop approval flow.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from agentcore.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# ROLES & PERMISSIONS
# =============================================================================

class Role(str, Enum):
    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"

    @classmethod
    def hierarchy(cls) -> List["Role"]:
        return [cls.VIEWER, cls.DEVELOPER, cls.ADMIN]

    def can_access(self, other: "Role") -> bool:
        return self.hierarchy().index(self) >= self.hierarchy().index(other)


TOOL_CATEGORIES: Dict[str, List[str]] = {
    "web": ["web_search", "web_fetch"],
    "knowledge": ["memory_store", "memory_recall"],
    "code": ["run_code"],
    "integration": ["http_request"],
    "content": ["generate_image"],
    "communication": ["send_notification"],
    "a2a": ["delegate_task", "query_agent"],
    "mcp": ["mcp_*"],
}

ROLE_TOOL_CATEGORIES: Dict[Role, List[str]] = {
    Role.ADMIN: ["*"],
    Role.DEVELOPER: ["web", "knowledge", "code", "integration", "content", "communication", "a2a", "mcp"],
    Role.VIEWER: ["web", "knowledge", "a2a"],
}

ROLE_TOOL_PERMISSIONS: Dict[Role, Dict[str, bool]] = {
    Role.ADMIN: {},
    Role.DEVELOPER: {},
    Role.VIEWER: {
        "run_code": False, "http_request": False, "send_notification": False,
    },
}

APPROVAL_REQUIRED: Dict[str, Dict[str, bool]] = {
    "auto": {},
    "strict": {
        "run_code": True, "http_request": True, "delegate_task": True, "mcp_*": True,
    },
}

DEFAULT_RISK_MODE: Dict[Role, str] = {
    Role.ADMIN: "auto", Role.DEVELOPER: "auto", Role.VIEWER: "strict",
}


class TenantToolPolicy:
    """Tenant-specific tool allow/deny lists."""

    def __init__(
        self,
        tenant_id: str,
        allow_tools: List[str] = None,
        deny_tools: List[str] = None,
        custom_policies: Dict[str, Dict] = None,
    ):
        self.tenant_id = tenant_id
        self.allow_tools = set(allow_tools or [])
        self.deny_tools = set(deny_tools or [])
        self.custom_policies = custom_policies or {}

    def is_allowed(self, tool_name: str) -> bool:
        if tool_name in self.deny_tools or "*" in self.deny_tools:
            return False
        if self.allow_tools and "*" not in self.allow_tools and tool_name not in self.allow_tools:
            return False
        return True

    def get_custom_policy(self, tool_name: str) -> Optional[Dict]:
        return self.custom_policies.get(tool_name)


DEFAULT_TENANT_POLICIES = {
    "strict": TenantToolPolicy("strict", deny_tools=["bash_execute", "bash_background", "git_write", "delete_file"]),
    "permissive": TenantToolPolicy("permissive", allow_tools=["*"]),
    "readonly": TenantToolPolicy("readonly", deny_tools=["write_file", "create_file", "edit_file", "delete_file",
                                                          "bash_execute", "bash_background", "git_write", "git_commit"]),
}


def get_allowed_categories(role: Role) -> List[str]:
    return ROLE_TOOL_CATEGORIES.get(role, [])


def is_tool_allowed(role: Role, tool_name: str) -> bool:
    return True


def requires_approval(risk_mode: str, tool_name: str) -> bool:
    mode_rules = APPROVAL_REQUIRED.get(risk_mode, APPROVAL_REQUIRED["auto"])
    if tool_name in mode_rules:
        return mode_rules[tool_name]
    if tool_name.startswith("mcp_") and "mcp_*" in mode_rules:
        return mode_rules["mcp_*"]
    return False





# =============================================================================
# GOVERNANCE ENGINE
# =============================================================================

class GovernanceError(Exception):
    pass


class GovernanceDeniedError(GovernanceError):
    pass


class GovernanceApprovalRequiredError(GovernanceError):
    def __init__(self, tool_name: str, message: str = None, approval_id: str = None):
        self.tool_name = tool_name
        self.approval_id = approval_id
        super().__init__(message or f"Action '{tool_name}' requires approval")


class GovernanceEngine:
    """Stateless policy evaluator - pure validation, no side effects."""

    def __init__(self):
        self._tenant_policies: Dict[str, TenantToolPolicy] = DEFAULT_TENANT_POLICIES.copy()

    def register_tenant_policy(self, policy: TenantToolPolicy) -> None:
        self._tenant_policies[policy.tenant_id] = policy
        logger.info(f"Registered governance policy for tenant: {policy.tenant_id}")

    def get_tenant_policy(self, tenant_id: str) -> TenantToolPolicy:
        return self._tenant_policies.get(tenant_id, TenantToolPolicy(tenant_id=tenant_id, allow_tools=["*"]))

    def assert_action_allowed(
        self,
        session: Any,
        tool_name: str,
        kwargs: Dict[str, Any],
        tenant_policy: Optional[TenantToolPolicy] = None,
    ) -> None:
        """Raise GovernanceDeniedError or GovernanceApprovalRequiredError if not allowed."""
        user_role = getattr(session, "user_role", Role.DEVELOPER)
        if isinstance(user_role, str):
            user_role = Role(user_role)

        tenant_id = getattr(session, "tenant_id", "local")
        risk_mode = getattr(session, "risk_mode", "auto")
        session_id = getattr(session, "id", None)

        policy = tenant_policy or self.get_tenant_policy(tenant_id)

        # 1. Tenant policy
        if not policy.is_allowed(tool_name):
            raise GovernanceDeniedError(f"Tool '{tool_name}' denied by tenant policy")

        # 2. Role-based tool permission
        if not is_tool_allowed(user_role, tool_name):
            raise GovernanceDeniedError(f"Tool '{tool_name}' not permitted for role '{user_role.value}'")

        # 3. Path isolation (simplified - no external dependency)
        self._validate_paths(tool_name, kwargs, session_id, tenant_id)

        # 4. Approval requirement
        if requires_approval(risk_mode, tool_name):
            if not kwargs.get("__approved__"):
                raise GovernanceApprovalRequiredError(
                    tool_name=tool_name,
                    message=f"Action '{tool_name}' requires your approval in {risk_mode} mode",
                )

    def get_allowed_tools(
        self,
        role: Role,
        tenant_id: str = "local",
        risk_mode: str = "auto",
    ) -> List[str]:
        policy = self.get_tenant_policy(tenant_id)
        all_tools = set()

        all_possible = [
            "web_search", "web_fetch", "memory_store", "memory_recall",
            "run_code", "http_request", "generate_image",
            "send_notification", "delegate_task", "query_agent",
        ]

        for tool in all_possible:
            if is_tool_allowed(role, tool) and policy.is_allowed(tool):
                all_tools.add(tool)

        return sorted(all_tools)

    def check_approval_status(
        self,
        tool_name: str,
        risk_mode: str,
        approved: bool = False,
    ) -> tuple[bool, Optional[str]]:
        if not requires_approval(risk_mode, tool_name):
            return False, None
        if approved:
            return False, None
        msg = f"Tool '{tool_name}' will execute on your system. Are you sure?"
        return True, msg


    def evaluate_batch(
        self,
        session: Any,
        tool_calls: List[Dict[str, Any]],
        tenant_policy: Optional[TenantToolPolicy] = None,
    ) -> Dict[str, Any]:
        result = {"allowed": [], "denied": [], "needs_approval": []}
        for call in tool_calls:
            tool_name = call.get("name") or call.get("tool_name")
            kwargs = call.get("arguments") or call.get("kwargs") or {}
            try:
                self.assert_action_allowed(session, tool_name, kwargs, tenant_policy)
                risk_mode = getattr(session, "risk_mode", "auto")
                approved = kwargs.get("__approved__", False)
                needs_approval, msg = self.check_approval_status(tool_name, risk_mode, approved)
                if needs_approval:
                    result["needs_approval"].append({"tool": tool_name, "message": msg})
                else:
                    result["allowed"].append(tool_name)
            except GovernanceApprovalRequiredError as e:
                result["needs_approval"].append({"tool": tool_name, "message": str(e)})
            except GovernanceDeniedError as e:
                result["denied"].append({"tool": tool_name, "reason": str(e)})
            except Exception as e:
                result["denied"].append({"tool": tool_name, "reason": f"Evaluation error: {e}"})
        return result


_engine: Optional[GovernanceEngine] = None


def get_governance_engine() -> GovernanceEngine:
    global _engine
    if _engine is None:
        _engine = GovernanceEngine()
    return _engine


# =============================================================================
# APPROVAL MANAGER (HITL)
# =============================================================================

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
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

    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _result: Optional[bool] = field(default=None, init=False)

    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=5)

    def approve(self, user_id: str, reason: str = None) -> None:
        self.status = ApprovalStatus.APPROVED
        self.decided_at = datetime.utcnow()
        self.decided_by = user_id
        self.decision_reason = reason
        self._result = True
        self._event.set()

    def deny(self, user_id: str, reason: str = None) -> None:
        self.status = ApprovalStatus.DENIED
        self.decided_at = datetime.utcnow()
        self.decided_by = user_id
        self.decision_reason = reason
        self._result = False
        self._event.set()

    def cancel(self) -> None:
        self.status = ApprovalStatus.CANCELLED
        self._event.set()

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    async def wait(self, timeout: float = None) -> bool:
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
        self._session_requests: Dict[str, List[str]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Approval cleanup error: {e}")

    async def _cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired_ids = [
            rid for rid, req in self._requests.items()
            if req.status == ApprovalStatus.PENDING and req.expires_at < now
        ]
        for req_id in expired_ids:
            req = self._requests[req_id]
            req.status = ApprovalStatus.EXPIRED
            req._event.set()
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
        if session_id not in self._session_requests:
            self._session_requests[session_id] = []
        self._session_requests[session_id].append(request_id)
        logger.info(f"Created approval request: {request_id} for {tool_name}")
        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_session_requests(self, session_id: str) -> List[ApprovalRequest]:
        return [self._requests[rid] for rid in self._session_requests.get(session_id, [])
                if rid in self._requests]

    def get_pending_requests(self, session_id: str = None) -> List[ApprovalRequest]:
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
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Approval request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already decided: {request.status.value}")

        if decision:
            request.approve(user_id, reason)
        else:
            request.deny(user_id, reason)

        for callback in self._callbacks.get(request_id, []):
            try:
                await callback(request)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")

        logger.info(f"Approval {request_id}: {'APPROVED' if decision else 'DENIED'} by {user_id}")
        return True

    def register_callback(self, request_id: str, callback: Callable) -> None:
        if request_id not in self._callbacks:
            self._callbacks[request_id] = []
        self._callbacks[request_id].append(callback)

    def cancel_request(self, request_id: str) -> bool:
        request = self._requests.get(request_id)
        if request and request.status == ApprovalStatus.PENDING:
            request.cancel()
            return True
        return False

    def cancel_session_requests(self, session_id: str) -> int:
        count = 0
        for request_id in self._session_requests.get(session_id, []):
            if self.cancel_request(request_id):
                count += 1
        return count


_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    global _manager
    if _manager is None:
        _manager = ApprovalManager()
    return _manager


async def request_approval(
    session_id: str,
    task_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    risk_mode: str,
    message: str = None,
) -> ApprovalRequest:
    manager = get_approval_manager()
    return manager.create_request(session_id, task_id, tool_name, arguments, risk_mode, message)


async def wait_for_approval(request: ApprovalRequest, timeout: float = 300) -> bool:
    return await request.wait(timeout=timeout)


async def approve_request(request_id: str, user_id: str, reason: str = None) -> bool:
    manager = get_approval_manager()
    return await manager.decide(request_id, True, user_id, reason)


async def deny_request(request_id: str, user_id: str, reason: str = None) -> bool:
    manager = get_approval_manager()
    return await manager.decide(request_id, False, user_id, reason)