"""Local Execution Module."""
import asyncio
import logging
import os
import time
from typing import Dict, Any
from src.domain.exceptions import SandboxExecutionError

logger = logging.getLogger(__name__)

async def run_local_dev(
    command: str, cwd: str, timeout: int, t0: float
) -> Dict[str, Any]:
    shell_cmd = (
        ["cmd", "/c", command] if os.name == "nt"
        else ["/bin/sh", "-c", command]
    )

    safe_env = {
        k: v for k, v in os.environ.items()
        if k not in {"AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "JWT_SECRET", "APP_SECRET_KEY"}
    }
    safe_env["SANDBOX_MODE"] = "local_dev"
    
    if not os.path.exists(cwd):
        logger.warning(f"[Sandbox] cwd {cwd} does not exist, falling back to current directory")
        cwd = os.getcwd()

    try:
        proc = await asyncio.create_subprocess_exec(
            *shell_cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:50000],
            "stderr": stderr.decode("utf-8", errors="replace")[:10000],
            "duration_ms": round((time.time() - t0) * 1000),
            "sandbox": "local_dev",
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Local timeout after {timeout}s", "sandbox": "local_dev"}
    except Exception as e:
        raise SandboxExecutionError(f"Local execution failed: {e}")
