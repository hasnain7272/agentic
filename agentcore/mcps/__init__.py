"""
AgentCore MCPs — Pre-built MCP Server Registry

Auto-discovers and registers all built-in MCP servers.
Each MCP is a Python class with name, description, TOOLS dict, and call_tool().
"""
from typing import Dict, Any, List

# Registry of all built-in MCP server classes
_BUILTIN_MCPS: Dict[str, Any] = {}


def register_mcp(cls):
    """Decorator to register a built-in MCP server class."""
    _BUILTIN_MCPS[cls.name] = cls
    return cls


def get_all_mcps() -> Dict[str, Any]:
    """Return dict of name → MCP class for all built-ins."""
    # Trigger imports to register all MCPs
    from agentcore.mcps import (
        filesystem, bash_exec, python_exec, git_ops, github_api,
        web_fetch, web_search, sqlite_db, memory, image_gen, project_ops,
    )
    return dict(_BUILTIN_MCPS)


def create_mcp_instance(name: str) -> Any:
    """Create an instance of a built-in MCP server by name."""
    mcps = get_all_mcps()
    if name not in mcps:
        raise ValueError(f"Unknown MCP: {name}. Available: {list(mcps.keys())}")
    return mcps[name]()


def get_mcp_tool_schemas(mcp_instance) -> List[Dict[str, Any]]:
    """Extract OpenAI-compatible tool schemas from an MCP instance."""
    schemas = []
    for tool_name, tool_info in mcp_instance.TOOLS.items():
        props = {}
        required = []
        for param_name, param_type in tool_info.get("params", {}).items():
            props[param_name] = {"type": param_type, "description": param_name}
            required.append(param_name)
        schemas.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_info.get("desc", tool_name),
                "parameters": {"type": "object", "properties": props, "required": required},
            }
        })
    return schemas
