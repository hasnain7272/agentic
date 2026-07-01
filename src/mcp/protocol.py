"""
MCP Protocol - Model Context Protocol Data Models

Pydantic models for MCP JSON-RPC messages and capabilities.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# Base models
class MCPServerInfo(BaseModel):
    """MCP server information."""
    name: str
    version: str


# Initialize
class MCPInitializeParams(BaseModel):
    """Initialize request parameters."""
    protocol_version: str
    capabilities: Dict[str, Any]
    client_info: Dict[str, str]


class MCPInitializeResult(BaseModel):
    """Initialize response."""
    protocol_version: str
    capabilities: Dict[str, Any]
    server_info: MCPServerInfo


# Tools
class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPListToolsResult(BaseModel):
    """Tools list response."""
    tools: List[MCPTool]


class MCPCallToolParams(BaseModel):
    """Call tool parameters."""
    name: str
    arguments: Dict[str, Any]


class MCPCallToolResult(BaseModel):
    """Call tool result."""
    content: List[Dict[str, Any]]
    is_error: bool = False


# Resources
class MCPResource(BaseModel):
    """MCP resource definition."""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPListResourcesResult(BaseModel):
    """Resources list response."""
    resources: List[MCPResource]


class MCPReadResourceParams(BaseModel):
    """Read resource parameters."""
    uri: str


class MCPReadResourceResult(BaseModel):
    """Read resource result."""
    contents: List[Dict[str, Any]]


# Prompts
class MCPPrompt(BaseModel):
    """MCP prompt definition."""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[Dict[str, Any]]] = None


class MCPListPromptsResult(BaseModel):
    """Prompts list response."""
    prompts: List[MCPPrompt]


class MCPGetPromptParams(BaseModel):
    """Get prompt parameters."""
    name: str
    arguments: Optional[Dict[str, Any]] = None


class MCPGetPromptResult(BaseModel):
    """Get prompt result."""
    description: Optional[str] = None
    messages: List[Dict[str, Any]]


# Notifications
class MCPNotification(BaseModel):
    """MCP notification message."""
    method: str
    params: Optional[Dict[str, Any]] = None


# Error
class MCPError(BaseModel):
    """MCP error response."""
    code: int
    message: str
    data: Optional[Any] = None


# Request/Response wrapper
class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None


# Standard method names
class MCPMethod:
    """Standard MCP method names."""
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    
    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"
    
    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    
    # Notifications
    NOTIFICATIONS_TOOLS_CHANGED = "notifications/tools/list_changed"
    NOTIFICATIONS_RESOURCES_CHANGED = "notifications/resources/list_changed"
    NOTIFICATIONS_PROMPTS_CHANGED = "notifications/prompts/list_changed"
    
    # Ping
    PING = "ping"


# Standard error codes
class MCPErrorCode:
    """Standard MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000  # Server-specific errors start here
    TOOL_NOT_FOUND = -32001
    RESOURCE_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003