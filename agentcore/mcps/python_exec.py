"""Python Exec MCP — Execute Python code snippets in a subprocess."""
import asyncio
import sys
import tempfile
from pathlib import Path
from agentcore.mcps import register_mcp


@register_mcp
class PythonExecMCP:
    name = "python-exec-mcp"
    description = "Run arbitrary Python code snippets and return stdout/stderr"
    TOOLS = {
        "python_run": {"params": {"code": "string"}, "desc": "Execute python code snippet in a separate process"},
    }

    async def call_tool(self, name: str, args: dict) -> dict:
        code = args["code"]
        # Write snippet to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            return {
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
                "exit_code": proc.returncode,
            }
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
