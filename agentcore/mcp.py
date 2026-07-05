"""
AgentCore MCP — In-process Mock/Routing & Custom Stdio Client Manager Layer
"""
import logging
from typing import Any, Dict, Optional
from agentcore.mcp_client import StdioMCPClient

logger = logging.getLogger(__name__)

# Mock traffic list to prevent router import crashes
_mcp_traffic = []


class MCPServerInstance:
    """Wrapper around local/builtin MCP servers to act as standard server."""
    def __init__(self, name: str, description: str, tools: list):
        self.name = name
        self.description = description
        self.tools = tools


class MCPClientManager:
    """Active connection manager for custom Stdio MCP server clients."""
    def __init__(self):
        self._clients: Dict[str, StdioMCPClient] = {}

    def get_client(self, name: str) -> Optional[StdioMCPClient]:
        """Retrieve cached client instance."""
        return self._clients.get(name)

    async def get_or_create_client(self, name: str, config: Dict[str, Any]) -> StdioMCPClient:
        """Get existing or instantiate & connect a new custom client."""
        client = self._clients.get(name)
        if not client:
            client = StdioMCPClient(name, config)
            self._clients[name] = client
        if client.status == "offline":
            await client.connect()
        return client

    async def add_server(self, config: Dict[str, Any]) -> None:
        """Register and start an MCP server client."""
        name = config.get("name")
        if not name:
            return
        await self.get_or_create_client(name, config)

    async def remove_server(self, name: str) -> None:
        """Shutdown and remove an MCP server client."""
        client = self._clients.pop(name, None)
        if client:
            await client.disconnect()


_mcp_manager = MCPClientManager()

def get_mcp_manager() -> MCPClientManager:
    """Single global connection manager for Stdio MCP subprocesses."""
    return _mcp_manager