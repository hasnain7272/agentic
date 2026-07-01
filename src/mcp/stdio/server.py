"""
MCP Stdio Server - Run AgentCore as an MCP Server

Allows AgentCore to be used as an MCP server by other agents/tools.
Exposes tools, resources, and prompts via stdio transport.
"""
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.mcp.protocol import (
    MCPMethod,
    MCPErrorCode,
    MCPTool,
    MCPResource,
    MCPPrompt,
    MCPInitializeParams,
    MCPInitializeResult,
    MCPServerInfo,
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
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Internal tool definition for registration."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    category: str = "general"


@dataclass
class ResourceDefinition:
    """Internal resource definition."""
    uri: str
    name: str
    description: Optional[str]
    mime_type: Optional[str]
    handler: Callable


@dataclass
class PromptDefinition:
    """Internal prompt definition."""
    name: str
    description: Optional[str]
    arguments: Optional[List[Dict[str, Any]]]
    handler: Callable


class MCPStdioServer:
    """MCP server using stdio transport."""
    
    def __init__(self, name: str = "AgentCore", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: Dict[str, ToolDefinition] = {}
        self._resources: Dict[str, ResourceDefinition] = {}
        self._prompts: Dict[str, PromptDefinition] = {}
        self._initialized = False
        self._running = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
    
    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
        category: str = "general",
    ) -> None:
        """Register a tool with the MCP server."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            category=category,
        )
        logger.info(f"Registered MCP tool: {name}")
    
    def register_resource(
        self,
        uri: str,
        name: str,
        description: Optional[str],
        mime_type: Optional[str],
        handler: Callable,
    ) -> None:
        """Register a resource with the MCP server."""
        self._resources[uri] = ResourceDefinition(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            handler=handler,
        )
        logger.info(f"Registered MCP resource: {uri}")
    
    def register_prompt(
        self,
        name: str,
        description: Optional[str],
        arguments: Optional[List[Dict[str, Any]]],
        handler: Callable,
    ) -> None:
        """Register a prompt with the MCP server."""
        self._prompts[name] = PromptDefinition(
            name=name,
            description=description,
            arguments=arguments,
            handler=handler,
        )
        logger.info(f"Registered MCP prompt: {name}")
    
    async def run(self) -> None:
        """Run the MCP server on stdio."""
        self._running = True
        
        # Setup stdio streams
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            sys.stdin.buffer,
        )
        
        self._writer = asyncio.StreamWriter(
            sys.stdout.buffer,
            protocol=None,
            reader=None,
            loop=asyncio.get_event_loop(),
        )
        
        logger.info(f"MCP server {self.name} started on stdio")
        
        try:
            while self._running:
                line = await self._reader.readline()
                if not line:
                    break
                
                try:
                    request_data = json.loads(line.decode())
                    await self._handle_request(request_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON: {e}")
                    await self._send_error(None, MCPErrorCode.PARSE_ERROR, "Parse error")
                except Exception as e:
                    logger.error(f"Request handling error: {e}")
                    await self._send_error(None, MCPErrorCode.INTERNAL_ERROR, str(e))
        finally:
            await self.shutdown()
    
    async def _handle_request(self, request_data: Dict[str, Any]) -> None:
        """Handle incoming JSON-RPC request."""
        request = MCPRequest(**request_data)
        
        # Handle notification (no response expected)
        if request.id is None:
            await self._handle_notification(request)
            return
        
        try:
            if request.method == MCPMethod.INITIALIZE:
                result = await self._handle_initialize(request.params)
            elif request.method == MCPMethod.TOOLS_LIST:
                result = await self._handle_tools_list()
            elif request.method == MCPMethod.TOOLS_CALL:
                result = await self._handle_tools_call(request.params)
            elif request.method == MCPMethod.RESOURCES_LIST:
                result = await self._handle_resources_list()
            elif request.method == MCPMethod.RESOURCES_READ:
                result = await self._handle_resources_read(request.params)
            elif request.method == MCPMethod.PROMPTS_LIST:
                result = await self._handle_prompts_list()
            elif request.method == MCPMethod.PROMPTS_GET:
                result = await self._handle_prompts_get(request.params)
            elif request.method == MCPMethod.PING:
                result = {}
            else:
                raise ValueError(f"Method not found: {request.method}")
            
            await self._send_response(request.id, result)
            
        except ValueError as e:
            await self._send_error(request.id, MCPErrorCode.METHOD_NOT_FOUND, str(e))
        except Exception as e:
            logger.error(f"Handler error for {request.method}: {e}")
            await self._send_error(request.id, MCPErrorCode.INTERNAL_ERROR, str(e))
    
    async def _handle_notification(self, request: MCPRequest) -> None:
        """Handle notification (no response)."""
        if request.method == MCPMethod.INITIALIZED:
            self._initialized = True
            logger.info("MCP initialization complete")
        # Handle other notifications as needed
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        init_params = MCPInitializeParams(**params)
        
        result = MCPInitializeResult(
            protocol_version="2024-11-05",
            capabilities={
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            server_info=MCPServerInfo(
                name=self.name,
                version=self.version,
            ),
        )
        return result.model_dump()
    
    async def _handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = [
            MCPTool(
                name=name,
                definition=defn.description,
                input_schema=defn.input_schema,
            )
            for name, defn in self._tools.items()
        ]
        result = MCPListToolsResult(tools=tools)
        return result.model_dump()
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        call_params = MCPCallToolParams(**params)
        
        if call_params.name not in self._tools:
            raise ValueError(f"Tool not found: {call_params.name}")
        
        tool_def = self._tools[call_params.name]
        
        try:
            # Execute handler
            if asyncio.iscoroutinefunction(tool_def.handler):
                result = await tool_def.handler(**call_params.arguments)
            else:
                result = tool_def.handler(**call_params.arguments)
            
            # Format result
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                is_error = result.get("is_error", False)
            else:
                content = [{"type": "text", "text": str(result)}]
                is_error = False
            
            call_result = MCPCallToolResult(content=content, is_error=is_error)
            return call_result.model_dump()
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            call_result = MCPCallToolResult(
                content=[{"type": "text", "text": f"Error: {e}"}],
                is_error=True,
            )
            return call_result.model_dump()
    
    async def _handle_resources_list(self) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = [
            MCPResource(
                uri=uri,
                name=defn.name,
                description=defn.description,
                mime_type=defn.mime_type,
            )
            for uri, defn in self._resources.items()
        ]
        result = MCPListResourcesResult(resources=resources)
        return result.model_dump()
    
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        read_params = MCPReadResourceParams(**params)
        
        if read_params.uri not in self._resources:
            raise ValueError(f"Resource not found: {read_params.uri}")
        
        resource_def = self._resources[read_params.uri]
        
        try:
            if asyncio.iscoroutinefunction(resource_def.handler):
                content = await resource_def.handler()
            else:
                content = resource_def.handler()
            
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            elif isinstance(content, dict):
                content = [content]
            elif not isinstance(content, list):
                content = [{"type": "text", "text": str(content)}]
            
            result = MCPReadResourceResult(contents=content)
            return result.model_dump()
            
        except Exception as e:
            logger.error(f"Resource read error: {e}")
            raise
    
    async def _handle_prompts_list(self) -> Dict[str, Any]:
        """Handle prompts/list request."""
        prompts = [
            MCPPrompt(
                name=name,
                description=defn.description,
                arguments=defn.arguments,
            )
            for name, defn in self._prompts.items()
        ]
        result = MCPListPromptsResult(prompts=prompts)
        return result.model_dump()
    
    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        get_params = MCPGetPromptParams(**params)
        
        if get_params.name not in self._prompts:
            raise ValueError(f"Prompt not found: {get_params.name}")
        
        prompt_def = self._prompts[get_params.name]
        
        try:
            if asyncio.iscoroutinefunction(prompt_def.handler):
                messages = await prompt_def.handler(**get_params.arguments)
            else:
                messages = prompt_def.handler(**get_params.arguments)
            
            if isinstance(messages, str):
                messages = [{"role": "user", "content": {"type": "text", "text": messages}}]
            elif isinstance(messages, dict):
                messages = [messages]
            
            result = MCPGetPromptResult(
                description=prompt_def.description,
                messages=messages,
            )
            return result.model_dump()
            
        except Exception as e:
            logger.error(f"Prompt get error: {e}")
            raise
    
    async def _send_response(self, request_id: Union[str, int], result: Dict[str, Any]) -> None:
        """Send JSON-RPC response."""
        response = MCPResponse(id=request_id, result=result)
        await self._send(response.model_dump())
    
    async def _send_error(
        self,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
    ) -> None:
        """Send JSON-RPC error response."""
        response = MCPResponse(
            id=request_id,
            error=MCPError(code=code, message=message),
        )
        await self._send(response.model_dump())
    
    async def _send(self, data: Dict[str, Any]) -> None:
        """Send JSON-RPC message."""
        line = json.dumps(data) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()
    
    async def shutdown(self) -> None:
        """Shutdown the server."""
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()


def create_default_server() -> MCPStdioServer:
    """Create a default MCP server with built-in tools."""
    server = MCPStdioServer()
    
    # Register default tools
    def read_file(filepath: str) -> str:
        """Read a file from the workspace."""
        from src.runtime.paths import resolve_workspace_path
        path = resolve_workspace_path(filepath)
        return path.read_text()
    
    def write_file(filepath: str, content: str) -> str:
        """Write a file to the workspace."""
        from src.runtime.paths import resolve_workspace_path
        path = resolve_workspace_path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Written to {filepath}"
    
    def list_files(path: str = ".") -> List[str]:
        """List files in workspace."""
        from src.runtime.paths import resolve_workspace_path
        base = resolve_workspace_path(path)
        return [str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()]
    
    def bash_execute(command: str, working_dir: str = ".") -> Dict[str, Any]:
        """Execute bash command in sandbox."""
        import subprocess
        from src.runtime.paths import resolve_workspace_path
        cwd = resolve_workspace_path(working_dir)
        result = subprocess.run(
            command, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=60
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    
    server.register_tool(
        "read_file",
        "Read a file from the workspace",
        {
            "type": "object",
            "properties": {"filepath": {"type": "string"}},
            "required": ["filepath"],
        },
        read_file,
        "filesystem",
    )
    
    server.register_tool(
        "write_file",
        "Write a file to the workspace",
        {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filepath", "content"],
        },
        write_file,
        "filesystem",
    )
    
    server.register_tool(
        "list_files",
        "List files in the workspace",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
        list_files,
        "filesystem",
    )
    
    server.register_tool(
        "bash_execute",
        "Execute bash command in sandbox",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "working_dir": {"type": "string", "default": "."},
            },
            "required": ["command"],
        },
        bash_execute,
        "shell",
    )
    
    return server


async def run_mcp_server() -> None:
    """Entry point to run MCP server."""
    server = create_default_server()
    await server.run()


if __name__ == "__main__":
    asyncio.run(run_mcp_server())