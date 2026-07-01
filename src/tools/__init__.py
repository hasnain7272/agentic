"""
Tools Package - Agent Tool Registry and Execution

Provides a unified tool system with:
- Built-in core tools (bash, file ops, search, etc.)
- MCP (Model Context Protocol) tool integration
- Auto-discovery and registration
"""
from src.tools.registry import ToolRegistry, get_tool_registry
from src.tools.schemas import ToolSchema, ToolParameter, ToolResult
from src.tools.core.base import BaseTool, ToolContext
from src.tools.core.builtin import (
    BashTool,
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    WebSearchTool,
    GetMemoryTool,
    SetMemoryTool,
    DelegateTaskTool,
)

__all__ = [
    "ToolRegistry",
    "get_tool_registry",
    "ToolSchema",
    "ToolParameter",
    "ToolResult",
    "BaseTool",
    "ToolContext",
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "WebSearchTool",
    "GetMemoryTool",
    "SetMemoryTool",
    "DelegateTaskTool",
]