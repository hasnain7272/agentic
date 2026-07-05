"""Memory MCP — Manage session memories using a local dictionary / key-value store."""
from agentcore.mcps import register_mcp

# Global in-memory storage for simplicity, scoped per session/agent in loop
_SESSION_MEMORIES = {}


@register_mcp
class MemoryMCP:
    name = "memory-mcp"
    description = "Store and recall persistent key-value memories within a session"
    TOOLS = {
        "memory_store":  {"params": {"key": "string", "value": "string"}, "desc": "Store a memory value for a key"},
        "memory_recall": {"params": {"key": "string"}, "desc": "Retrieve the stored memory value for a key"},
        "memory_list":   {"desc": "List all stored memory keys and values"},
    }

    async def call_tool(self, name: str, args: dict) -> dict:
        if name == "memory_store":
            k, v = args["key"], args["value"]
            _SESSION_MEMORIES[k] = v
            return {"key": k, "status": "stored"}
        elif name == "memory_recall":
            k = args["key"]
            return {"key": k, "value": _SESSION_MEMORIES.get(k)}
        elif name == "memory_list":
            return {"memories": _SESSION_MEMORIES}
        raise ValueError(f"Unknown tool: {name}")
