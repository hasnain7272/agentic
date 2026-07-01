"""Docker Execution Module."""
import asyncio
import os
import time
from typing import Dict, Any
from src.domain.exceptions import SandboxExecutionError

async def run_in_docker(
    image: str,
    command: str,
    workspace: str,
    container_workdir: str,
    memory_mb: int,
    network: str,
    timeout: int,
    t0: float,
) -> Dict[str, Any]:
    enable_dood = os.environ.get("ENABLE_SANDBOX_DOCKER", "false").lower() == "true"
    docker_socket = os.environ.get("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
    actual_network = "bridge" if enable_dood else network

    docker_args = [
        "docker", "run", "--rm",
        f"--memory={memory_mb}m",
        f"--network={actual_network}",
        "--pids-limit", "256",
    ]

    if not enable_dood:
        docker_args.append("--read-only")
        docker_args.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
    else:
        docker_args.extend(["-v", f"{docker_socket}:{docker_socket}"])

    docker_args.extend([
        "-v", f"{os.path.abspath(workspace)}:/workspace:rw",
        "-w", container_workdir,
        image, "/bin/sh", "-c", command,
    ])

    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:50000],
            "stderr": stderr.decode("utf-8", errors="replace")[:10000],
            "duration_ms": round((time.time() - t0) * 1000),
            "sandbox": "docker",
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Docker timeout after {timeout}s", "sandbox": "docker"}
    except Exception as e:
        raise SandboxExecutionError(f"Docker execution failed: {e}")
