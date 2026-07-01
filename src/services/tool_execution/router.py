"""
Tool Execution Router — Unified entry point for all tool execution.

Responsibilities:
- Route bash/shell commands through the SandboxAdapter
- Execute all other tools directly via their async execute() method
- Enforce workspace isolation via folder_slug
"""
import logging
from typing import Any, Dict

from src.domain.exceptions import ToolExecutionError
from src.infrastructure.runtime.config import SANDBOX_MODE, KUBERNETES_MODE, ALLOW_ANON_LOCAL
from src.infrastructure.sandbox.docker import SandboxAdapter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor
from src.tools.core.base import BaseTool

logger = logging.getLogger(__name__)


class ToolExecutionRouter:
    """Routes tool execution through appropriate sandbox/direct paths."""

    def __init__(self):
        self._sandbox = SandboxAdapter()
        self._kubernetes = None

    async def _get_sandbox(self):
        """Get sandbox executor (lazy k8s initialization)."""
        if KUBERNETES_MODE:
            if self._kubernetes is None:
                self._kubernetes = await get_sandbox_executor()
            return self._kubernetes
        return self._sandbox

    async def execute_tool(
        self, tool_: BaseTool, session_id: str, kwargs: Dict[str, Any], tenant_id: str = "local"
    ) -> Any:
        """Execute a tool through the appropriate isolation layer."""
        logger.info(f"[Router] Executing: {tool_.name} (tenant={tenant_id})")

        # Extract folder_slug for workspace isolation
        folder_slug = kwargs.pop("folder_slug", "") or ""

        should_sandbox = getattr(tool_, "requires_sandbox", False) or tool_.name == "bash_execute"

        if should_sandbox:
            return await self._execute_sandboxed(
                tool_, session_id, tenant_id, kwargs, folder_slug
            )

        from src.services.tool_execution.multiplexer import resource_multiplexer

        if folder_slug and "working_dir" not in kwargs:
            kwargs["working_dir"] = folder_slug
             
        # Identify if this is a stateful resource (like an MCP server)
        # MCP tools are named 'mcp_<serverName>_<toolName>'
        is_mcp = tool_.name.startswith("mcp_")
        resource_name = tool_.name.split("_")[1] if is_mcp else None

        if is_mcp and resource_name:
            await resource_multiplexer.acquire(resource_name)
            try:
                return await tool_.execute(session_id=session_id, **kwargs)
            finally:
                resource_multiplexer.release(resource_name)
        else:
            return await tool_.execute(session_id=session_id, **kwargs)

    async def _execute_sandboxed(
        self, tool_: BaseTool, session_id: str, tenant_id: str,
        kwargs: Dict[str, Any], folder_slug: str
    ) -> Any:
        """Route commands through sandbox."""
        sandbox = await self._get_sandbox()
        
        # If it's bash, use the command directly
        if tool_.name == "bash_execute":
            command = kwargs.get("command")
            if not command:
                raise ToolExecutionError("Missing command for bash_execute", tool_.name)
            
            # SandboxAdapter from docker_adapter.py
            if hasattr(sandbox, "image"):
                return await sandbox.execute(
                    command=command,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    working_dir=folder_slug or ".",
                    timeout=kwargs.get("timeout", 30),
                )
            else:
                # LocalSandboxExecutor or KubernetesSandboxExecutor expects SandboxConfig
                from src.infrastructure.sandbox.kubernetes import SandboxConfig
                from src.infrastructure.runtime.paths import resolve_workspace_path
                safe_cwd = str(resolve_workspace_path(folder_slug or ".", session_id=session_id, tenant_id=tenant_id))
                config = SandboxConfig(
                    command=command,
                    working_dir=safe_cwd,
                    timeout=kwargs.get("timeout", 30)
                )
                result = await sandbox.execute(config)
                return {
                    "success": result.exit_code == 0,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration_ms": result.duration_ms,
                    "sandbox": "kubernetes" if "Kubernetes" in sandbox.__class__.__name__ else "local"
                }
        
        # For other tools (like git_clone, git_write), we rely on their internal
        # use of get_sandbox_executor() OR we need to wrap them.
        # For now, we allow direct execution as most tools are already 'safe'
        # or handle their own sandbox (like the Git tools).
        return await tool_.execute(session_id=session_id, **kwargs)
