"""
AgentCore MCP — In-process Mock/Routing Layer
"""
import logging

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
    """Mock client manager stub."""
    def get_client(self, name: str):
        return None

    def add_server(self, config: Any) -> None:
        pass

    def remove_server(self, name: str) -> None:
        pass


def get_mcp_manager() -> MCPClientManager:
    return MCPClientManager()