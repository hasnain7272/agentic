"""Git commit tool with governance."""
import subprocess
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class GitCommitTool(BaseTool):
    """Commit changes with security scanning."""
    name = "git_commit"
    description = "Commit staged changes to repository"
    parameters = [
        ToolParameter(name="message", type="string", description="Commit message"),
        ToolParameter(name="branch", type="string", description="Target branch", required=False),
        ToolParameter(name="push", type="boolean", description="Push to remote", default=False),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        message = kwargs.get("message", "Agent update")
        branch = kwargs.get("branch")
        push = kwargs.get("push", False)
        workspace = f"/workspace/{session_id}/repos"

        # Scan for security risks before commit
        scan_result = await self._scan_changes(workspace)
        if scan_result.get("risks"):
            return {
                "success": False,
                "requires_approval": True,
                "risks": scan_result["risks"],
                "suggestion": "Review risks before committing",
            }

        executor = await get_sandbox_executor()
        safe_message = message.replace("'", "'\"'\"'")

        commands = [f"cd {workspace}"]
        if branch:
            commands.append(f"git checkout {branch}")
        commands.extend([
            f"git config user.email 'agent@antigravity.dev'",
            f"git config user.name 'Antigravity Agent'",
            f"git commit -m '{safe_message}' --allow-empty",
        ])
        if push:
            commands.append(f"git push origin {branch or 'HEAD'}")

        result = await executor.execute(command=" && ".join(commands))

        return {
            "success": result.exit_code == 0,
            "message": message,
            "branch": branch,
            "pushed": push,
            "stdout": result.stdout,
            "commit_hash": self._extract_hash(result.stdout) if result.exit_code == 0 else None,
        }

    async def _scan_changes(self, workspace: str) -> Dict:
        """Scan staged changes for risks."""
        executor = await get_sandbox_executor()
        result = await executor.execute(command=f"cd {workspace} && git diff --cached")

        risks = []
        diff = result.stdout.lower()

        dangerous_patterns = [
            ("password", "Hardcoded password"),
            ("api_key", "Hardcoded API key"),
            ("secret", "Potential secret"),
            ("rm -rf /", "Dangerous rm command"),
            ("eval(", "Eval usage"),
        ]

        for pattern, risk in dangerous_patterns:
            if pattern in diff:
                risks.append(risk)

        return {"risks": risks}

    def _extract_hash(self, output: str) -> str:
        """Extract commit hash from git output."""
        if "commit" in output.lower():
            parts = output.split()
            for part in parts:
                if len(part) == 40 and all(c in "0123456789abcdef" for c in part.lower()):
                    return part[:8]
        return "unknown"
