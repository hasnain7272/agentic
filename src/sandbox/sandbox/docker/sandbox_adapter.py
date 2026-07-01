"""Sandbox Adapter Main Class."""
import asyncio
import logging
import time
from typing import Any, Dict

from src.domain.exceptions import SandboxExecutionError
from src.infrastructure.runtime.config import SANDBOX_IMAGE, ALLOW_ANON_LOCAL
from src.infrastructure.runtime.paths import get_session_root, resolve_workspace_path

from .docker_runner import run_in_docker
from .local_runner import run_local_dev

logger = logging.getLogger(__name__)

class SandboxAdapter:
    def __init__(self, image: str = SANDBOX_IMAGE):
        self.image = image
        self._docker_available: bool | None = None

    async def _check_docker(self) -> bool:
        if self._docker_available is not None:
            return self._docker_available
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3)
            self._docker_available = proc.returncode == 0
        except Exception:
            self._docker_available = False

        if not self._docker_available:
            logger.warning("[Sandbox] Docker daemon not reachable")
        return self._docker_available

    async def execute(
        self,
        command: str,
        session_id: str,
        tenant_id: str,
        working_dir: str = ".",
        timeout: int = 30,
        memory_limit_mb: int = 512,
        network_mode: str = "none",
    ) -> Dict[str, Any]:
        start_time = time.time()
        session_root = get_session_root(tenant_id, session_id)
        session_root.mkdir(parents=True, exist_ok=True)
        working_path = resolve_workspace_path(working_dir, session_id=session_id, tenant_id=tenant_id)
        
        try:
            relative_workdir = working_path.relative_to(session_root)
            container_workdir = "/workspace"
            if str(relative_workdir) not in {"", "."}:
                container_workdir = f"/workspace/{relative_workdir.as_posix()}"
        except ValueError:
            raise SandboxExecutionError(f"Working directory escapes session root: {working_path}")
        
        if await self._check_docker():
            return await run_in_docker(
                self.image, command, str(session_root), container_workdir, memory_limit_mb, network_mode, timeout, start_time
            )

        if ALLOW_ANON_LOCAL:
            logger.warning("[Sandbox] DEV MODE: Running locally (no Docker)")
            return await run_local_dev(command, str(working_path), timeout, start_time)

        raise SandboxExecutionError(
            "Docker is required for command execution in production. Set ALLOW_ANON_LOCAL=true for local development."
        )
