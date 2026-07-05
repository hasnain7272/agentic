"""GitHub API MCP — Interact with remote GitHub repositories."""
import asyncio
from agentcore.mcps import register_mcp


@register_mcp
class GitHubAPIMCP:
    name = "github-mcp"
    description = "Search repos, create issues, review/create PRs on GitHub"
    TOOLS = {
        "gh_search_repos": {"params": {"query": "string"}, "desc": "Search repositories on GitHub"},
        "gh_create_issue": {"params": {"repo": "string", "title": "string", "body": "string"}, "desc": "Create a GitHub issue"},
        "gh_list_prs":     {"params": {"repo": "string"}, "desc": "List pull requests for a repository"},
        "gh_create_pr":    {"params": {"repo": "string", "title": "string", "head": "string", "base": "string"}, "desc": "Create a pull request"},
    }

    async def _run_gh(self, args: list) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
            return {
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
                "exit_code": proc.returncode,
            }
        except FileNotFoundError:
            return {"error": "GitHub CLI 'gh' is not installed or not in PATH.", "exit_code": 127}

    async def call_tool(self, name: str, args: dict) -> dict:
        if name == "gh_search_repos":
            return await self._run_gh(["repo", "list", args["query"]])
        elif name == "gh_create_issue":
            return await self._run_gh(["issue", "create", "-R", args["repo"], "-t", args["title"], "-b", args["body"]])
        elif name == "gh_list_prs":
            return await self._run_gh(["pr", "list", "-R", args["repo"]])
        elif name == "gh_create_pr":
            return await self._run_gh(["pr", "create", "-R", args["repo"], "-t", args["title"], "-H", args["head"], "-B", args["base"]])
        raise ValueError(f"Unknown tool: {name}")
