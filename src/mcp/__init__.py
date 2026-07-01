"""
MCP Package - Model Context Protocol Integration

Provides MCP client and server implementations for tool, resource,
and prompt sharing between agents and applications.
"""
from src.mcp.protocol import (
    MCPMethod,
    MCPErrorCode,
    MCPTool,
    MCPResource,
    MCPPrompt,
    MCPServerInfo,
    MCPInitializeParams,
    MCPInitializeResult,
    MCPListToolsResult,
    MCPListResourcesResult,
    MCPListPromptsResult,
    MCPCallToolParams,
    MCPCallToolResult,
    MCPReadResourceParams,
    MCPReadResourceResult,
    MCPGetPromptParams,
    MCPGetPromptResult,
    MCPRequest,
    MCPResponse,
    MCPError,
)
from src.mcp.client import (
    MCPClient,
    MCPClientManager,
    MCPServerConfig,
    get_mcp_manager,
)
from src.mcp.stdio.server import (
    MCPStdioServer,
    create_default_server,
    run_mcp_server,
)

__all__ = [
    "MCPMethod",
    "MCPErrorCode",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    "MCPServerInfo",
    "MCPInitializeParams",
    "MCPInitializeResult",
    "MCPListToolsResult",
    "MCPListResourcesResult",
    "MCPListPromptsResult",
    "MCPCallToolParams",
    "MCPCallToolResult",
    "MCPReadResourceParams",
    "MCPReadResourceResult",
    "MCPGetPromptParams",
    "MCPGetPromptResult",
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "MCPClient",
    "MCPClientManager",
    "MCPServerConfig",
    "get_mcp_manager",
    "MCPStdioServer",
    "create_default_server",
    "run_mcp_server",
]