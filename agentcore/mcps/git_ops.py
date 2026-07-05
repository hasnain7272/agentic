"""Git Operations MCP — Local git repositories management."""
import asyncio
import sys
from agentcore.mcps import register_mcp


@register_mcp
class GitOpsMCP:
    name = "git-mcp"
    description = "Manage local git repositories: status, diff, commit, branch, push, checkout"
    TOOLS = {
        "git_status":   {"params": {"repo_path": "string"}, "desc": "Check git repository status"},
        "git_diff":     {"params": {"repo_path": "string"}, "desc": "Show unstaged/staged git changes"},
        "git_commit":   {"params": {"repo_path": "string", "message": "string"}, "desc": "Stage all files and commit with a message"},
        "git_branch":   {"params": {"repo_path": "string"}, "desc": "List all branches"},
        "git_checkout": {"params": {"repo_path": "string", "branch": "string"}, "desc": "Switch branches or create a new branch"},
        "git_push":     {"params": {"repo_path": "string", "remote": "string", "branch": "string"}, "desc": "Push commits to remote (force requires approval)"},
    }

    async def _run_git(self, repo_path: str, args: list) -> dict:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=repo_path
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip(),
            "exit_code": proc.returncode,
        }

    async def call_tool(self, name: str, args: dict) -> dict:
        rp = args.get("repo_path", ".")
        if name == "git_status":
            return await self._run_git(rp, ["status"])
        elif name == "git_diff":
            return await self._run_git(rp, ["diff"])
        elif name == "git_commit":
            # Add and commit
            await self._run_git(rp, ["add", "-A"])
            return await self._run_git(rp, ["commit", "-m", args["message"]])
        elif name == "git_branch":
            return await self._run_git(rp, ["branch", "-a"])
        elif name == "git_checkout":
            return await self._run_git(rp, ["checkout", args["branch"]])
        elif name == "git_push":
            r = args.get("remote", "origin")
            b = args.get("branch", "main")
            return await self._run_git(rp, ["push", r, b])
        raise ValueError(f"Unknown tool: {name}")
