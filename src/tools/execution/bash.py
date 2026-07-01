"""
Bash Execute Tool — Production-Grade Shell Execution

Uses proper shell invocation (`sh -c` / `cmd /c`) instead of naive split().
Applies a targeted blocklist for truly dangerous operations while allowing
standard shell operators (pipes, redirects, variables) that agents need.
"""
import asyncio
import os
import re
import time
from typing import Any, Dict

from src.infrastructure.runtime.paths import resolve_workspace_path
from src.tools.core.base import BaseTool, ToolParameter

# Only block commands that are *destructive at the OS level*.
# NOT shell operators — those are required for real work.
BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "format c:",
    "del /f /s /q c:",
    "rd /s /q c:",
    "takeown /f c:",
    "icacls c:",
    "chmod -R 777 /",
    "chown -R",
    "curl | sh",
    "curl | bash",
    "wget -O- |",
    "nc -e",
    "/dev/tcp",
]

MAX_COMMAND_LENGTH = 10_000
MAX_OUTPUT_BYTES = 50_000


class BashExecuteTool(BaseTool):
    name = "bash_execute"
    description = (
        "Execute a shell command in the workspace. Supports pipes, redirects, "
        "variables, and all standard shell features. Returns stdout, stderr, "
        "and exit code."
    )
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="The shell command to run. Supports pipes, redirects, etc.",
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory relative to workspace root (default: '.')",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds (1-120, default 30)",
            required=False,
        ),
    ]
    requires_sandbox = True

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Validate command against destructive patterns only."""
        if not command or not command.strip():
            return False, "Empty command"

        if len(command) > MAX_COMMAND_LENGTH:
            return False, f"Command exceeds {MAX_COMMAND_LENGTH} character limit"

        cmd_lower = command.lower().strip()
        for pattern in BLOCKED_COMMANDS:
            if pattern in cmd_lower:
                return False, f"BLOCKED: Matches destructive pattern '{pattern}'"

        return True, ""

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        command = kwargs.get("command", "")
        working_dir = kwargs.get("working_dir", ".")
        timeout = min(max(int(kwargs.get("timeout", 30)), 1), 120)

        is_valid, error_msg = self._validate_command(command)
        if not is_valid:
            return {"success": False, "error": error_msg}

        safe_cwd = str(resolve_workspace_path(working_dir))
        start = time.time()

        # Use proper shell invocation — this allows pipes, redirects, variables
        if os.name == "nt":
            shell_cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", command]
        else:
            shell_cmd = ["/bin/sh", "-c", command]

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=safe_cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES],
                "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES],
                "duration_ms": round((time.time() - start) * 1000),
            }
        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
            return {"success": False, "error": f"Timed out after {timeout}s"}
        except FileNotFoundError:
            return {"success": False, "error": f"Shell not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:500]}
