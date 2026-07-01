"""
Stdio MCP Manager - Premium Production Grade

Provides lifecycle management, health monitoring, and tool execution
for local subprocess-based MCP servers using JSON-RPC over stdio.
"""
import asyncio
from typing import Dict, Optional

from src.services.mcp.stdio_models import StdioMCPServer, ServerStatus
from src.services.mcp.stdio_lifecycle import StdioMCPLifecycleMixin
from src.services.mcp.stdio_execution import StdioMCPExecutionMixin
from src.services.mcp.stdio_health import StdioMCPHealthMixin


class StdioMCPManager(
    StdioMCPLifecycleMixin,
    StdioMCPExecutionMixin,
    StdioMCPHealthMixin,
):
    """
    Singleton manager for stdio-based MCP servers.
    Combines lifecycle, execution, and health monitoring logic.
    """
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
            
        self._tenant_servers: Dict[str, Dict[str, StdioMCPServer]] = {}
        self._tool_name_to_server: Dict[str, str] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30.0
        self._max_restart_attempts = 5
        
        self._initialized = True

    def _get_tenant_servers(self, tenant_id: str) -> Dict[str, StdioMCPServer]:
        if tenant_id not in self._tenant_servers:
            self._tenant_servers[tenant_id] = {}
        return self._tenant_servers[tenant_id]

# Global singleton instance
stdio_mcp_manager = StdioMCPManager()