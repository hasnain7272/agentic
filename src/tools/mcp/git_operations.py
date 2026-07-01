"""Git MCP tools - Clone, Read, Write operations."""
import subprocess
from pathlib import Path
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class GitCloneTool(BaseTool):
    """Clone repositories into isolated sandbox."""
    name = "git_clone"
    description = "Clone a GitHub repository to workspace"
    parameters = [
        ToolParameter(name="repo_url", type="string", description="HTTPS or SSH URL"),
        ToolParameter(name="branch", type="string", description="Branch to clone", required=False, default="main"),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        repo_url = kwargs.get("repo_url")
        branch = kwargs.get("branch", "main")
        
        from src.infrastructure.runtime.paths import resolve_workspace_path
        try:
            repos_dir = resolve_workspace_path("repos", session_id=session_id)
            repos_dir.mkdir(parents=True, exist_ok=True)
            workspace = str(repos_dir)
        except Exception as e:
            return {"success": False, "error": str(e)}

        executor = await get_sandbox_executor()
        command = f"git clone -b {branch} {repo_url} ."

        # Run with explicit working dir to avoid cd
        result = await executor.execute(config={"command": command, "working_dir": workspace, "image": "alpine/git", "memory_limit": "512m", "timeout": 300})
        
        return {
            "success": result.exit_code == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "workspace": "repos",
            "branch": branch,
        }


class GitReadTool(BaseTool):
    """Read files from cloned repository."""
    name = "git_read"
    description = "Read file contents from repository"
    parameters = [
        ToolParameter(name="filepath", type="string", description="Relative file path"),
        ToolParameter(name="limit", type="integer", description="Max lines to read", required=False, default=500),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        from src.infrastructure.runtime.paths import resolve_workspace_path
        
        filepath = kwargs.get("filepath")
        limit = kwargs.get("limit", 500)
        
        # Use safe path resolution
        try:
            full_path = resolve_workspace_path(f"repos/{filepath}", session_id=session_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

        if not full_path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    lines.append(line)
            
            content = "".join(lines)
            return {
                "success": True,
                "content": content,
                "filepath": filepath,
                "truncated": "Truncated by limit" if len(lines) == limit else "Full file",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GitWriteTool(BaseTool):
    """Write files to repository on feature branch."""
    name = "git_write"
    description = "Write file to repository (creates feature branch)"
    parameters = [
        ToolParameter(name="filepath", type="string", description="Relative file path"),
        ToolParameter(name="content", type="string", description="File content"),
        ToolParameter(name="branch", type="string", description="Feature branch name"),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        filepath = kwargs.get("filepath")
        content = kwargs.get("content", "")
        branch = kwargs.get("branch", f"agent/edit-{hash(filepath) % 10000}")
        workspace = "/workspace/repos"

        # Escape content for shell
        safe_content = content.replace("'", "'\"'\"'")

        executor = await get_sandbox_executor()
        command = f"""cd {workspace} && \
            git checkout -b {branch} 2>/dev/null || git checkout {branch} && \
            mkdir -p $(dirname {filepath}) && \
            echo '{safe_content}' > {filepath} && \
            git add {filepath}"""

        result = await executor.execute(command=command)
        return {
            "success": result.exit_code == 0,
            "filepath": filepath,
            "branch": branch,
            "bytes_written": len(content),
        }
