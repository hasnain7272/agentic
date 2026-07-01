"""
Docker Sandbox Runner - Docker-based Code Execution

Implements sandbox interface using Docker containers.
Provides secure, isolated execution with resource limits.
"""
import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from src.sandbox.interface import (
    SandboxInterface,
    SandboxLimits,
    SandboxMount,
    ExecutionRequest,
    ExecutionResult,
    SandboxInfo,
    SandboxError,
    SandboxNotFoundError,
    SandboxTimeoutError,
    SandboxResourceError,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class DockerSandboxRunner(SandboxInterface):
    """Docker-based sandbox implementation."""
    
    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._sandboxes: Dict[str, Dict[str, Any]] = {}
        self._settings = get_settings()
    
    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client
    
    def _build_create_options(self, limits: SandboxLimits) -> Dict[str, Any]:
        """Build Docker container create options from limits."""
        # Parse memory limit (e.g., "512m" -> 512 * 1024 * 1024)
        mem_bytes = self._parse_memory(limits.memory_limit)
        
        # CPU quota/period for CFS scheduler
        cpu_quota = int(float(limits.cpu_limit) * 100000)
        cpu_period = 100000
        
        return {
            "image": self._settings.docker_image,
            "command": ["sleep", "infinity"],  # Keep container running
            "detach": True,
            "network_mode": self._settings.docker_network if limits.network_enabled else "none",
            "cpus": float(limits.cpu_limit),
            "mem_limit": mem_bytes,
            "memswap_limit": mem_bytes,  # Disable swap
            "pids_limit": limits.pids_limit,
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "read_only": False,
            "tmpfs": {"/tmp": "size=100m,noexec,nosuid"},
            "working_dir": self._settings.sandbox_workdir,
            "user": "sandbox:sandbox",  # Non-root user
            "labels": {"agentic.sandbox": "true"},
        }
    
    def _parse_memory(self, mem_str: str) -> int:
        """Parse memory string to bytes."""
        mem_str = mem_str.lower().strip()
        if mem_str.endswith('g'):
            return int(float(mem_str[:-1]) * 1024 * 1024 * 1024)
        elif mem_str.endswith('m'):
            return int(float(mem_str[:-1]) * 1024 * 1024)
        elif mem_str.endswith('k'):
            return int(float(mem_str[:-1]) * 1024)
        else:
            return int(mem_str)
    
    async def create(self, limits: Optional[SandboxLimits] = None) -> str:
        """Create a new Docker container sandbox."""
        limits = limits or SandboxLimits()
        sandbox_id = f"sandbox-{uuid.uuid4().hex[:12]}"
        
        try:
            # Ensure image exists
            await self._ensure_image()
            
            options = self._build_create_options(limits)
            container = self.client.containers.create(**options, name=sandbox_id)
            container.start()
            
            # Verify container is running
            container.reload()
            if container.status != "running":
                raise SandboxError(f"Container failed to start: {container.status}")
            
            self._sandboxes[sandbox_id] = {
                "container": container,
                "limits": limits,
                "created_at": asyncio.get_event_loop().time(),
            }
            
            logger.info(f"Created sandbox: {sandbox_id}")
            return sandbox_id
            
        except ImageNotFound:
            raise SandboxError(f"Docker image not found: {self._settings.docker_image}")
        except DockerException as e:
            raise SandboxError(f"Failed to create sandbox: {e}")
    
    async def _ensure_image(self) -> None:
        """Ensure Docker image is available locally."""
        try:
            self.client.images.get(self._settings.docker_image)
        except ImageNotFound:
            logger.info(f"Pulling image: {self._settings.docker_image}")
            self.client.images.pull(self._settings.docker_image)
    
    async def execute(self, sandbox_id: str, request: ExecutionRequest) -> ExecutionResult:
        """Execute command in Docker sandbox."""
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        
        # Prepare execution command
        cmd = request.command
        workdir = request.working_dir or self._settings.sandbox_workdir
        env = request.environment or {}
        
        # Apply user-specific environment
        if request.user:
            env["HOME"] = f"/home/{request.user}"
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Execute in container
            exec_id = self.client.api.exec_create(
                container.id,
                cmd,
                workdir=workdir,
                environment=env,
                user=request.user,
                stdin=bool(request.stdin),
            )["Id"]
            
            # Stream output
            output = self.client.api.exec_start(
                exec_id,
                stream=True,
                stdin=request.stdin,
            )
            
            stdout_chunks = []
            stderr_chunks = []
            
            for chunk in output:
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors="replace")
                # Docker multiplexes stdout/stderr - first byte indicates stream
                if chunk.startswith('\x01'):  # stdout
                    stdout_chunks.append(chunk[1:])
                elif chunk.startswith('\x02'):  # stderr
                    stderr_chunks.append(chunk[1:])
                else:
                    stdout_chunks.append(chunk)
            
            # Get exit code
            exec_inspect = self.client.api.exec_inspect(exec_id)
            exit_code = exec_inspect.get("ExitCode", -1)
            
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            return ExecutionResult(
                exit_code=exit_code,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                duration_ms=duration_ms,
            )
            
        except DockerException as e:
            if "timeout" in str(e).lower():
                raise SandboxTimeoutError(f"Execution timed out: {e}")
            if "oom" in str(e).lower() or "memory" in str(e).lower():
                raise SandboxResourceError(f"Memory limit exceeded: {e}")
            raise SandboxError(f"Execution failed: {e}")
    
    async def upload_file(
        self, 
        sandbox_id: str, 
        local_path: str, 
        remote_path: str
    ) -> bool:
        """Upload file to sandbox using tar archive."""
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        
        try:
            import tarfile
            import io
            
            # Create tar archive
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(local_path, arcname=os.path.basename(remote_path))
            tar_stream.seek(0)
            
            # Put archive in container
            success = container.put_archive(
                os.path.dirname(remote_path) or "/",
                tar_stream.read()
            )
            return success
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    async def download_file(
        self, 
        sandbox_id: str, 
        remote_path: str, 
        local_path: str
    ) -> bool:
        """Download file from sandbox using tar archive."""
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        
        try:
            import tarfile
            import io
            
            # Get archive from container
            bits, stat = container.get_archive(remote_path)
            
            # Extract to local path
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)
            
            with tarfile.open(fileobj=tar_stream, mode='r') as tar:
                tar.extractall(os.path.dirname(local_path) or ".")
            
            return True
            
        except NotFound:
            logger.error(f"File not found: {remote_path}")
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        """List files in sandbox directory."""
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        
        try:
            result = await self.execute(sandbox_id, ExecutionRequest(
                command=["ls", "-la", path],
                working_dir="/",
            ))
            
            files = []
            for line in result.stdout.strip().split("\n")[1:]:  # Skip total line
                parts = line.split()
                if len(parts) >= 9:
                    files.append({
                        "name": parts[8],
                        "size": int(parts[4]),
                        "type": "dir" if parts[0].startswith("d") else "file",
                        "modified": " ".join(parts[5:8]),
                        "permissions": parts[0],
                    })
            return files
            
        except Exception as e:
            logger.error(f"List files failed: {e}")
            return []
    
    async def delete(self, sandbox_id: str) -> bool:
        """Delete sandbox container."""
        if sandbox_id not in self._sandboxes:
            return True  # Idempotent
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        
        try:
            container.stop(timeout=5)
            container.remove(force=True)
            del self._sandboxes[sandbox_id]
            logger.info(f"Deleted sandbox: {sandbox_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    async def get_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Get sandbox status information."""
        if sandbox_id not in self._sandboxes:
            return None
        
        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]
        container.reload()
        
        return SandboxInfo(
            sandbox_id=sandbox_id,
            status=container.status,
            container_id=container.id,
            limits=sandbox["limits"],
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Docker daemon health."""
        try:
            self.client.ping()
            info = self.client.info()
            return {
                "status": "healthy",
                "type": "docker",
                "containers_running": info.get("ContainersRunning", 0),
                "images": info.get("Images", 0),
                "docker_version": info.get("ServerVersion", "unknown"),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
_docker_runner: Optional[DockerSandboxRunner] = None


def get_docker_runner() -> DockerSandboxRunner:
    """Get or create the global Docker sandbox runner."""
    global _docker_runner
    if _docker_runner is None:
        _docker_runner = DockerSandboxRunner()
    return _docker_runner