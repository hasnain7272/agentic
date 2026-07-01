from typing import List

from src.tools.registry import get_tool_catalog


def _skill_catalog() -> List[dict]:
    tools = get_tool_catalog()
    by_name = {tool["name"]: tool for tool in tools}
    skills = [
        {
            "id": "build-ship",
            "name": "Build & Ship",
            "description": "Generate code, validate it, and prepare delivery through Git or workspace output.",
            "prompt": "Implement the requested change, verify it, then prepare the output for dispatch or Git delivery.",
            "tool_names": ["write_file", "generate_tests", "git_write", "git_commit", "git_create_pr", "dispatch_output"],
        },
        {
            "id": "review-secure",
            "name": "Review & Secure",
            "description": "Inspect code quality and security posture before merging or releasing.",
            "prompt": "Review the relevant code and highlight bugs, regressions, and security issues before proposing changes.",
            "tool_names": ["read_file", "code_review", "security_scan", "search_past_decisions"],
        },
        {
            "id": "research-context",
            "name": "Research & Context",
            "description": "Gather current information and connect it to project memory and structure.",
            "prompt": "Research the current best approach, compare it to our codebase, and summarize the right implementation direction.",
            "tool_names": ["web_search", "code_graph_query", "search_past_decisions", "update_agent_memory"],
        },
        {
            "id": "repo-automation",
            "name": "Repo Automation",
            "description": "Work across repositories, branches, and pull requests from one workflow.",
            "prompt": "Clone the repository, inspect the target files, make the requested changes, and prepare the branch for review.",
            "tool_names": ["git_clone", "git_read", "git_write", "git_commit", "git_create_pr"],
        },
    ]
    for skill in skills:
        skill["tools"] = [by_name[name] for name in skill["tool_names"] if name in by_name]
        skill["missing_tools"] = [name for name in skill["tool_names"] if name not in by_name]
        skill["ready"] = len(skill["missing_tools"]) == 0
        skill["coverage"] = len(skill["tools"]) / max(len(skill["tool_names"]), 1)
    return skills
