"""
AgentCore Sandbox - Docker + Local Execution Interface

Consolidated sandbox: interface + Docker runner + Local runner.
"""
import abc
import asyncio
import importlib.util
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentcore.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# CORE DATA TYPES
# =============================================================================

@dataclass
class SandboxLimits:
    cpu_limit: str = "1.0"
    memory_limit: str = "512m"
    timeout_seconds: int = 300
    pids_limit: int = 100
    disk_limit: str = "1g"
    network_enabled: bool = True


@dataclass
class SandboxMount:
    source: str
    target: str
    read_only: bool = False


@dataclass
class ExecutionRequest:
    command: List[str]
    working_dir: str = "/workspace"
    environment: Dict[str, str] = None
    limits: Optional[SandboxLimits] = None
    mounts: List[SandboxMount] = None
    stdin: Optional[str] = None
    user: Optional[str] = None


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    oom_killed: bool = False
    error: Optional[str] = None


@dataclass
class SandboxInfo:
    sandbox_id: str
    status: str
    container_id: Optional[str] = None
    created_at: Optional[str] = None
    limits: Optional[SandboxLimits] = None


class SandboxError(Exception):
    pass


class SandboxNotFoundError(SandboxError):
    pass


class SandboxTimeoutError(SandboxError):
    pass


class SandboxResourceError(SandboxError):
    pass


DEFAULT_LIMITS = SandboxLimits()
STRICT_LIMITS = SandboxLimits(
    cpu_limit="0.5", memory_limit="256m", timeout_seconds=60,
    pids_limit=50, disk_limit="500m", network_enabled=False,
)
DEVELOPMENT_LIMITS = SandboxLimits(
    cpu_limit="2.0", memory_limit="2g", timeout_seconds=600,
    pids_limit=200, disk_limit="5g", network_enabled=True,
)


# =============================================================================
# INTERFACE
# =============================================================================

class SandboxInterface(abc.ABC):
    @abc.abstractmethod
    async def create(self, limits: Optional[SandboxLimits] = None) -> str:
        pass

    @abc.abstractmethod
    async def execute(self, sandbox_id: str, request: ExecutionRequest) -> ExecutionResult:
        pass

    @abc.abstractmethod
    async def upload_file(self, sandbox_id: str, local_path: str, remote_path: str) -> bool:
        pass

    @abc.abstractmethod
    async def download_file(self, sandbox_id: str, remote_path: str, local_path: str) -> bool:
        pass

    @abc.abstractmethod
    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    async def delete(self, sandbox_id: str) -> bool:
        pass

    @abc.abstractmethod
    async def get_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass


# =============================================================================
# DOCKER RUNNER
# =============================================================================

class DockerSandboxRunner(SandboxInterface):
    def __init__(self):
        self._client = None
        self._sandboxes: Dict[str, Dict[str, Any]] = {}
        self._settings = get_settings()

    @property
    def client(self):
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def _parse_memory(self, mem_str: str) -> int:
        mem_str = mem_str.lower().strip()
        if mem_str.endswith('g'):
            return int(float(mem_str[:-1]) * 1024 * 1024 * 1024)
        elif mem_str.endswith('m'):
            return int(float(mem_str[:-1]) * 1024 * 1024)
        elif mem_str.endswith('k'):
            return int(float(mem_str[:-1]) * 1024)
        return int(mem_str)

    def _build_create_options(self, limits: SandboxLimits) -> Dict[str, Any]:
        mem_bytes = self._parse_memory(limits.memory_limit)
        cpu_quota = int(float(limits.cpu_limit) * 100000)

        return {
            "image": self._settings.docker_image,
            "command": ["sleep", "infinity"],
            "detach": True,
            "network_mode": self._settings.docker_network if limits.network_enabled else "none",
            "cpus": float(limits.cpu_limit),
            "mem_limit": mem_bytes,
            "memswap_limit": mem_bytes,
            "pids_limit": limits.pids_limit,
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "tmpfs": {"/tmp": "size=100m,noexec,nosuid"},
            "working_dir": self._settings.sandbox_workdir,
            "user": "sandbox:sandbox",
            "labels": {"agentcore.sandbox": "true"},
        }

    async def create(self, limits: Optional[SandboxLimits] = None) -> str:
        limits = limits or SandboxLimits()
        sandbox_id = f"sandbox-{uuid.uuid4().hex[:12]}"

        try:
            await self._ensure_image()
            options = self._build_create_options(limits)
            container = self.client.containers.create(**options, name=sandbox_id)
            container.start()

            container.reload()
            if container.status != "running":
                raise SandboxError(f"Container failed to start: {container.status}")

            self._sandboxes[sandbox_id] = {
                "container": container,
                "limits": limits,
                "created_at": time.time(),
            }
            logger.info(f"Created sandbox: {sandbox_id}")
            return sandbox_id

        except Exception as e:
            raise SandboxError(f"Failed to create sandbox: {e}")

    async def _ensure_image(self) -> None:
        try:
            self.client.images.get(self._settings.docker_image)
        except Exception:
            logger.info(f"Pulling image: {self._settings.docker_image}")
            self.client.images.pull(self._settings.docker_image)

    async def execute(self, sandbox_id: str, request: ExecutionRequest) -> ExecutionResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]

        cmd = request.command
        workdir = request.working_dir or self._settings.sandbox_workdir
        env = request.environment or {}

        start_time = time.time()

        try:
            exec_id = self.client.api.exec_create(
                container.id,
                cmd,
                workdir=workdir,
                environment=env,
                user=request.user,
                stdin=bool(request.stdin),
            )["Id"]

            output = self.client.api.exec_start(exec_id, stream=True, stdin=request.stdin)

            stdout_chunks = []
            stderr_chunks = []

            for chunk in output:
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors="replace")
                if chunk.startswith('\x01'):
                    stdout_chunks.append(chunk[1:])
                elif chunk.startswith('\x02'):
                    stderr_chunks.append(chunk[1:])
                else:
                    stdout_chunks.append(chunk)

            exec_inspect = self.client.api.exec_inspect(exec_id)
            exit_code = exec_inspect.get("ExitCode", -1)

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                exit_code=exit_code,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                duration_ms=duration_ms,
            )

        except Exception as e:
            if "timeout" in str(e).lower():
                raise SandboxTimeoutError(f"Execution timed out: {e}")
            if "oom" in str(e).lower() or "memory" in str(e).lower():
                raise SandboxResourceError(f"Memory limit exceeded: {e}")
            raise SandboxError(f"Execution failed: {e}")

    async def upload_file(self, sandbox_id: str, local_path: str, remote_path: str) -> bool:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]

        try:
            import tarfile
            import io

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(local_path, arcname=os.path.basename(remote_path))
            tar_stream.seek(0)

            success = container.put_archive(
                os.path.dirname(remote_path) or "/",
                tar_stream.read()
            )
            return success
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    async def download_file(self, sandbox_id: str, remote_path: str, local_path: str) -> bool:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        container = sandbox["container"]

        try:
            import tarfile
            import io

            bits, _ = container.get_archive(remote_path)
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            with tarfile.open(fileobj=tar_stream, mode='r') as tar:
                tar.extractall(os.path.dirname(local_path) or ".")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        try:
            result = await self.execute(sandbox_id, ExecutionRequest(
                command=["ls", "-la", path],
                working_dir="/",
            ))

            files = []
            for line in result.stdout.strip().split("\n")[1:]:
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
        if sandbox_id not in self._sandboxes:
            return True

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


# =============================================================================
# LOCAL RUNNER
# =============================================================================

class LocalSandboxRunner(SandboxInterface):
    def __init__(self):
        self._sandboxes: Dict[str, Dict[str, Any]] = {}
        self._settings = get_settings()
        self._base_workdir = Path(self._settings.sandbox_workdir or "./workspace")
        self._base_workdir.mkdir(parents=True, exist_ok=True)

    async def create(self, limits: Optional[SandboxLimits] = None) -> str:
        sandbox_id = f"local-{uuid.uuid4().hex[:12]}"
        workdir = self._base_workdir / sandbox_id
        workdir.mkdir(parents=True, exist_ok=True)

        effective_limits = limits or SandboxLimits()

        self._sandboxes[sandbox_id] = {
            "workdir": workdir,
            "limits": effective_limits,
            "created_at": time.time(),
            "processes": [],
        }

        logger.info(f"Created local sandbox: {sandbox_id} at {workdir}")
        return sandbox_id

    async def execute(self, sandbox_id: str, request: ExecutionRequest) -> ExecutionResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        workdir = sandbox["workdir"]
        limits = sandbox["limits"]

        cmd = request.command
        env = os.environ.copy()
        if request.environment:
            env.update(request.environment)

        cwd = request.working_dir
        if not os.path.isabs(cwd):
            cwd = str(workdir / cwd)

        Path(cwd).mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        timeout = request.limits.timeout_seconds if request.limits else limits.timeout_seconds

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE if request.stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,
            )

            sandbox["processes"].append(process)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=request.stdin.encode() if request.stdin else None),
                    timeout=timeout,
                )
                exit_code = process.returncode
                timed_out = False
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
                exit_code = -1
                timed_out = True
                stdout = b""
                stderr = b"Execution timed out"

            duration_ms = int((time.time() - start_time) * 1000)

            sandbox["processes"] = [p for p in sandbox["processes"] if p.returncode is None]

            return ExecutionResult(
                exit_code=exit_code,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_ms=duration_ms,
                timed_out=timed_out,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Local execution failed: {e}")
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error=str(e),
            )

    async def upload_file(self, sandbox_id: str, local_path: str, remote_path: str) -> bool:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        workdir = sandbox["workdir"]

        try:
            src = Path(local_path)
            dst = workdir / remote_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(f"Uploaded {src} -> {dst}")
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    async def download_file(self, sandbox_id: str, remote_path: str, local_path: str) -> bool:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        workdir = sandbox["workdir"]

        try:
            src = workdir / remote_path
            dst = Path(local_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(f"Downloaded {src} -> {dst}")
            return True
        except FileNotFoundError:
            logger.error(f"File not found: {remote_path}")
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> List[Dict[str, Any]]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        workdir = sandbox["workdir"]

        if path == "/workspace":
            target = workdir
        elif path.startswith("/workspace/"):
            target = workdir / path[len("/workspace/"):]
        else:
            target = workdir / path.lstrip("/")

        try:
            files = []
            for entry in target.iterdir():
                stat = entry.stat()
                files.append({
                    "name": entry.name,
                    "size": stat.st_size,
                    "type": "dir" if entry.is_dir() else "file",
                    "modified": time.ctime(stat.st_mtime),
                    "permissions": oct(stat.st_mode)[-3:],
                })
            return files
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"List files failed: {e}")
            return []

    async def delete(self, sandbox_id: str) -> bool:
        if sandbox_id not in self._sandboxes:
            return True

        sandbox = self._sandboxes[sandbox_id]

        for process in sandbox["processes"]:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            except Exception:
                pass

        try:
            shutil.rmtree(sandbox["workdir"], ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to remove workdir: {e}")

        del self._sandboxes[sandbox_id]
        logger.info(f"Deleted local sandbox: {sandbox_id}")
        return True

    async def get_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
        if sandbox_id not in self._sandboxes:
            return None

        sandbox = self._sandboxes[sandbox_id]
        return SandboxInfo(
            sandbox_id=sandbox_id,
            status="running" if sandbox["processes"] else "idle",
            limits=sandbox["limits"],
        )

    async def health_check(self) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "echo", "health_check",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return {
                "status": "healthy" if proc.returncode == 0 else "degraded",
                "type": "local",
                "active_sandboxes": len(self._sandboxes),
                "base_workdir": str(self._base_workdir),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# =============================================================================
# FACTORY
# =============================================================================

_docker_runner: Optional[DockerSandboxRunner] = None
_local_runner: Optional[LocalSandboxRunner] = None


def get_sandbox_runner(sandbox_type: str = None) -> SandboxInterface:
    """Get sandbox runner by type (docker or local)."""
    global _docker_runner, _local_runner

    settings = get_settings()
    sandbox_type = sandbox_type or settings.sandbox_type

    if sandbox_type == "docker":
        if _docker_runner is None:
            try:
                _docker_runner = DockerSandboxRunner()
            except Exception as e:
                logger.warning(f"Docker unavailable, falling back to local: {e}")
                sandbox_type = "local"

    if sandbox_type == "local" or sandbox_type != "docker":
        if _local_runner is None:
            _local_runner = LocalSandboxRunner()
        return _local_runner

    return _docker_runner