"""
Stdio MCP Models - Data classes and enums for stdio MCP servers.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.services.mcp.stdio_messages import ToolManifest
from src.services.mcp.stdio_protocol import MCPStdioProtocol


class ServerStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RESTARTING = "restarting"


@dataclass
class MCPServerMetrics:
    total_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_called: Optional[float] = None
    restart_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls


@dataclass
class StdioMCPServer:
    name: str
    command: str
    args: List[str]
    working_dir: Optional[str] = None
    description: str = ""
    tenant_id: str = "default"
    status: ServerStatus = ServerStatus.STARTING
    process: Optional[Any] = field(default=None, repr=False)
    protocol: Optional[MCPStdioProtocol] = field(default=None, repr=False)
    tools: List[ToolManifest] = field(default_factory=list)
    metrics: MCPServerMetrics = field(default_factory=MCPServerMetrics)
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_health_check: float = field(default_factory=time.time)
