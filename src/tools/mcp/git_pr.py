"""GitHub PR creation tool."""
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class GitPRTool(BaseTool):
    """Create pull requests via GitHub CLI."""
    name = "git_create_pr"
    description = "Create pull request on GitHub"
    parameters = [
        ToolParameter(name="title", type="string", description="PR title"),
        ToolParameter(name="body", type="string", description="PR description", required=False, default=""),
        ToolParameter(name="head_branch", type="string", description="Source branch"),
        ToolParameter(name="base_branch", type="string", description="Target branch", default="main"),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        title = kwargs.get("title", "Agent update")
        body = kwargs.get("body", "Changes made by Antigravity Agent")
        head = kwargs.get("head_branch")
        base = kwargs.get("base_branch", "main")
        workspace = f"/workspace/{session_id}/repos"

        if not head:
            # Get current branch
            executor = await get_sandbox_executor()
            result = await executor.execute(command=f"cd {workspace} && git branch --show-current")
            head = result.stdout.strip() if result.exit_code == 0 else "agent-changes"

        safe_title = title.replace("'", "'\"'\"'")
        safe_body = body.replace("'", "'\"'\"'")

        executor = await get_sandbox_executor()
        command = f"""cd {workspace} && \
            gh pr create \
            --title '{safe_title}' \
            --body '{safe_body}' \
            --head {head} \
            --base {base} \
            --web 2>/dev/null || \
            gh pr create --title '{safe_title}' --body '{safe_body}' --head {head} --base {base}"""

        result = await executor.execute(command=command)

        # Extract PR URL
        pr_url = None
        for line in result.stdout.splitlines():
            if "github.com" in line and "/pull/" in line:
                pr_url = line.strip()
                break

        return {
            "success": result.exit_code == 0,
            "title": title,
            "head": head,
            "base": base,
            "pr_url": pr_url,
            "output": result.stdout,
            "error": result.stderr if result.exit_code != 0 else None,
        }
