"""Bash Exec MCP — Run shell commands on the host system."""
import asyncio
import sys
from agentcore.mcps import register_mcp


@register_mcp
class BashExecMCP:
    name = "bash-exec-mcp"
    description = "Execute shell commands (PowerShell on Windows, bash on Linux)"
    TOOLS = {
        "bash_execute": {"params": {"command": "string", "cwd": "string"}, "desc": "Run a shell command and return stdout/stderr"},
    }
    DESTRUCTIVE_PATTERNS = ["rm -rf", "rmdir /s", "del /f", "format ", "shutdown", "mkfs"]

    async def call_tool(self, name: str, args: dict) -> dict:
        cmd = args["command"]
        cwd = args.get("cwd", ".")
        shell_cmd = ["powershell", "-Command", cmd] if sys.platform == "win32" else ["bash", "-c", cmd]
        proc = await asyncio.create_subprocess_exec(
            *shell_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return {
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip(),
            "exit_code": proc.returncode,
        }
