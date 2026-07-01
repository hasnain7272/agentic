"""
MCP Client - Model Context Protocol Client Implementation

Connects to MCP servers via stdio or HTTP and manages tool discovery.
"""
import asyncio
import json
import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.mcp.protocol import (
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
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    command: List[str]  # For stdio transport
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None  # For HTTP transport
    transport: str = "stdio"  # stdio, http, sse
    enabled: bool = True
    timeout_seconds: int = 30
    auto_reconnect: bool = True


class MCPClient:
    """MCP client for stdio transport."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._initialized = False
        self._server_info: Optional[MCPServerInfo] = None
        self._tools: List[MCPTool] = []
        self._resources: List[MCPResource] = []
        self._prompts: List[MCPPrompt] = []
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> MCPServerInfo:
        """Connect to MCP server and initialize."""
        if self.config.transport == "stdio":
            return await self._connect_stdio()
        elif self.config.transport == "http":
            return await self._connect_http()
        else:
            raise ValueError(f"Unsupported transport: {self.config.transport}")
    
    async def _connect_stdio(self) -> MCPServerInfo:
        """Connect via stdio subprocess."""
        logger.info(f"Starting MCP server: {self.config.name}")
        
        # Prepare environment
        env = {**self.config.env}
        
        # Start process
        self._process = subprocess.Popen(
            self.config.command + self.config.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=False,  # Binary mode
        )
        
        # Create async readers/writers
        self._reader = asyncio.StreamReader()
        self._writer = asyncio.StreamWriter(self._UnixSelectorEventLoop().connect_write_pipe(
            lambda: asyncio.StreamReaderProtocol(self._reader),
            self._process.stdout,
        )  # This needs fixing
        
        # Actually, let's use a simpler approach
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            self._process.stdout,
        )
        
        # Start read loop
        self._read_task = asyncio.create_task(self._read_loop())
        
        # Initialize
        return await self._initialize()
    
    async def _initialize(self) -> MCPServerInfo:
        """Send initialize request."""
        params = MCPInitializeParams(
            protocol_version="2024-11-05",
            capabilities={
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            client_info={
                "name": "AgentCore",
                "version": "1.0.0",
            },
        )
        
        result = await self._send_request("initialize", params.model_dump())
        init_result = MCPInitializeResult(**result)
        
        self._server_info = init_result.server_info
        self._initialized = True
        
        # Discover tools, resources, prompts
        await self._discover_capabilities()
        
        logger.info(f"MCP server {self.config.name} initialized: {self._server_info.name}")
        return self._server_info
    
    async def _discover_capabilities(self) -> None:
        """Discover tools, resources, and prompts."""
        try:
            tools_result = await self.list_tools()
            self._tools = tools_result.tools
        except Exception as e:
            logger.warning(f"Failed to list tools: {e}")
        
        try:
            resources_result = await self.list_resources()
            self._resources = resources_result.resources
        except Exception as e:
            logger.warning(f"Failed to list resources: {e}")
        
        try:
            prompts_result = await self.list_prompts()
            self._prompts = prompts_result.prompts
        except Exception as e:
            logger.warning(f"Failed to list prompts: {e}")
    
    async def list_tools(self) -> MCPListToolsResult:
        """List available tools."""
        result = await self._send_request("tools/list", {})
        return MCPListToolsResult(**result)
    
    async def list_resources(self) -> MCPListResourcesResult:
        """List available resources."""
        result = await self._send_request("resources/list", {})
        return MCPListResourcesResult(**result)
    
    async def list_prompts(self) -> MCPListPromptsResult:
        """List available prompts."""
        result = await self._send_request("prompts/list", {})
        return MCPListPromptsResult(**result)
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPCallToolResult:
        """Call a tool on the MCP server."""
        params = MCPCallToolParams(name=name, arguments=arguments)
        result = await self._send_request("tools/call", params.model_dump())
        return MCPCallToolResult(**result)
    
    async def read_resource(self, uri: str) -> MCPReadResourceResult:
        """Read a resource from the MCP server."""
        params = MCPReadResourceParams(uri=uri)
        result = await self._send_request("resources/read", params.model_dump())
        return MCPReadResourceResult(**result)
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> MCPGetPromptResult:
        """Get a prompt from the MCP server."""
        params = MCPGetPromptParams(name=name, arguments=arguments or {})
        result = await self._send_request("prompts/get", params.model_dump())
        return MCPGetPromptResult(**result)
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request and wait for response."""
        if not self._initialized and method != "initialize":
            await self._initialize()
        
        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        # Send request
        data = json.dumps(request) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()
        
        try:
            response = await asyncio.wait_for(future, timeout=self.config.timeout_seconds)
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request timed out: {method}")
        except Exception as e:
            del self._pending_requests[request_id]
            raise
        
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def _read_loop(self) -> None:
        """Read responses from MCP server."""
        while True:
            try:
                line = await self._reader.readline()
                if not line:
                    break
                
                response = json.loads(line.decode())
                request_id = response.get("id")
                
                if request_id and request_id in self._pending_requests:
                    future = self._pending_requests.pop(request_id)
                    if not future.done():
                        future.set_result(response)
                elif "method" in response:
                    # Handle notifications
                    await self._handle_notification(response)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"MCP JSON decode error: {e}")
            except Exception as e:
                logger.error(f"MCP read error: {e}")
                break
    
    async def _handle_notification(self, notification: Dict[str, Any]) -> None:
        """Handle MCP notifications."""
        method = notification.get("method")
        params = notification.get("params", {})
        
        if method == "notifications/tools/list_changed":
            await self._discover_capabilities()
        # Add more notifications as needed
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        
        self._initialized = False
        logger.info(f"Disconnected from MCP server: {self.config.name}")
    
    def get_tools(self) -> List[MCPTool]:
        """Get cached tool list."""
        return self._tools
    
    def get_resources(self) -> List[MCPResource]:
        """Get cached resource list."""
        return self._resources
    
    def get_prompts(self) -> List[MCPPrompt]:
        """Get cached prompt list."""
        return self._prompts


class MCPClientManager:
    """Manages multiple MCP server connections."""
    
    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._configs: Dict[str, MCPServerConfig] = {}
    
    def add_server(self, config: MCPServerConfig) -> None:
        """Add MCP server configuration."""
        self._configs[config.name] = config
    
    def remove_server(self, name: str) -> bool:
        """Remove MCP server."""
        if name in self._clients:
            asyncio.create_task(self._clients[name].disconnect())
            del self._clients[name]
        return self._configs.pop(name, None) is not None
    
    async def connect_all(self) -> Dict[str, MCPServerInfo]:
        """Connect to all configured servers."""
        results = {}
        for name, config in self._configs.items():
            if not config.enabled:
                continue
            try:
                client = MCPClient(config)
                info = await client.connect()
                self._clients[name] = client
                results[name] = info
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {name}: {e}")
        return results
    
    async def disconnect_all(self) -> None:
        """Disconnect all clients."""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get connected client by name."""
        return self._clients.get(name)
    
    def get_all_tools(self) -> Dict[str, List[MCPTool]]:
        """Get tools from all connected clients."""
        return {name: client.get_tools() for name, client in self._clients.items()}
    
    def get_all_resources(self) -> Dict[str, List[MCPResource]]:
        """Get resources from all connected clients."""
        return {name: client.get_resources() for name, client in self._clients.items()}
    
    def get_all_prompts(self) -> Dict[str, List[MCPPrompt]]:
        """Get prompts from all connected clients."""
        return {name: client.get_prompts() for name, client in self._clients.items()}


# Global manager
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    """Get or create global MCP client manager."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager