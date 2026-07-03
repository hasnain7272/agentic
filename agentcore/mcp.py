"""
AgentCore MCP - Client, Protocol, Stdio Server

Consolidated MCP: stdio client + protocol models + stdio server.
"""
import asyncio
import json
import logging
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel
from agentcore.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOL MODELS
# =============================================================================

class MCPServerInfo(BaseModel):
    name: str
    version: str


class MCPInitializeParams(BaseModel):
    protocol_version: str
    capabilities: Dict[str, Any]
    client_info: Dict[str, str]


class MCPInitializeResult(BaseModel):
    protocol_version: str
    capabilities: Dict[str, Any]
    server_info: MCPServerInfo


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPListToolsResult(BaseModel):
    tools: List[MCPTool]


class MCPCallToolParams(BaseModel):
    name: str
    arguments: Dict[str, Any]


class MCPCallToolResult(BaseModel):
    content: List[Dict[str, Any]]
    is_error: bool = False


class MCPResource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPListResourcesResult(BaseModel):
    resources: List[MCPResource]


class MCPReadResourceParams(BaseModel):
    uri: str


class MCPReadResourceResult(BaseModel):
    contents: List[Dict[str, Any]]


class MCPPrompt(BaseModel):
    name: str
    description: Optional[str] = None
    arguments: Optional[List[Dict[str, Any]]] = None


class MCPListPromptsResult(BaseModel):
    prompts: List[MCPPrompt]


class MCPGetPromptParams(BaseModel):
    name: str
    arguments: Optional[Dict[str, Any]] = None


class MCPGetPromptResult(BaseModel):
    description: Optional[str] = None
    messages: List[Dict[str, Any]]


class MCPNotification(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None


class MCPMethod:
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    NOTIFICATIONS_TOOLS_CHANGED = "notifications/tools/list_changed"
    NOTIFICATIONS_RESOURCES_CHANGED = "notifications/resources/list_changed"
    NOTIFICATIONS_PROMPTS_CHANGED = "notifications/prompts/list_changed"
    PING = "ping"


class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000
    TOOL_NOT_FOUND = -32001
    RESOURCE_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003


# =============================================================================
# CLIENT CONFIG
# =============================================================================

@dataclass
class MCPServerConfig:
    name: str
    command: List[str]
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    transport: str = "stdio"
    enabled: bool = True
    timeout_seconds: int = 30
    auto_reconnect: bool = True


# =============================================================================
# CLIENT
# =============================================================================

class MCPClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._initialized = False
        self._server_info: Optional[MCPServerInfo] = None
        self._tools: List[MCPTool] = []
        self._resources: List[MCPResource] = []
        self._prompts: List[MCPPrompt] = []
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self) -> MCPServerInfo:
        if self.config.transport == "stdio":
            return await self._connect_stdio()
        raise ValueError(f"Unsupported transport: {self.config.transport}")

    async def _connect_stdio(self) -> MCPServerInfo:
        logger.info(f"Starting MCP server: {self.config.name}")

        env = {**self.config.env}
        self._process = subprocess.Popen(
            self.config.command + self.config.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=False,
        )

        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            self._process.stdout,
        )

        self._read_task = asyncio.create_task(self._read_loop())
        return await self._initialize()

    async def _initialize(self) -> MCPServerInfo:
        params = MCPInitializeParams(
            protocol_version="2024-11-05",
            capabilities={"tools": {}, "resources": {}, "prompts": {}},
            client_info={"name": "AgentCore", "version": "1.0.0"},
        )

        result = await self._send_request("initialize", params.model_dump())
        init_result = MCPInitializeResult(**result)

        self._server_info = init_result.server_info
        self._initialized = True
        await self._discover_capabilities()

        logger.info(f"MCP server {self.config.name} initialized: {self._server_info.name}")
        return self._server_info

    async def _discover_capabilities(self) -> None:
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
        result = await self._send_request("tools/list", {})
        return MCPListToolsResult(**result)

    async def list_resources(self) -> MCPListResourcesResult:
        result = await self._send_request("resources/list", {})
        return MCPListResourcesResult(**result)

    async def list_prompts(self) -> MCPListPromptsResult:
        result = await self._send_request("prompts/list", {})
        return MCPListPromptsResult(**result)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPCallToolResult:
        params = MCPCallToolParams(name=name, arguments=arguments)
        result = await self._send_request("tools/call", params.model_dump())
        return MCPCallToolResult(**result)

    async def read_resource(self, uri: str) -> MCPReadResourceResult:
        params = MCPReadResourceParams(uri=uri)
        result = await self._send_request("resources/read", params.model_dump())
        return MCPReadResourceResult(**result)

    async def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> MCPGetPromptResult:
        params = MCPGetPromptParams(name=name, arguments=arguments or {})
        result = await self._send_request("prompts/get", params.model_dump())
        return MCPGetPromptResult(**result)

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._initialized and method != "initialize":
            await self._initialize()

        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        data = json.dumps(request) + "\n"
        self._process.stdin.write(data.encode())
        await asyncio.get_event_loop().run_in_executor(None, self._process.stdin.flush)

        try:
            response = await asyncio.wait_for(future, timeout=self.config.timeout_seconds)
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request timed out: {method}")

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    async def _read_loop(self) -> None:
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
                    await self._handle_notification(response)

            except json.JSONDecodeError as e:
                logger.warning(f"MCP JSON decode error: {e}")
            except Exception as e:
                logger.error(f"MCP read error: {e}")
                break

    async def _handle_notification(self, notification: Dict[str, Any]) -> None:
        method = notification.get("method")
        if method == "notifications/tools/list_changed":
            await self._discover_capabilities()

    async def disconnect(self) -> None:
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self._process.wait),
                    timeout=5
                )
            except asyncio.TimeoutError:
                self._process.kill()
                await asyncio.get_event_loop().run_in_executor(None, self._process.wait)

        self._initialized = False
        logger.info(f"Disconnected from MCP server: {self.config.name}")

    def get_tools(self) -> List[MCPTool]:
        return self._tools

    def get_resources(self) -> List[MCPResource]:
        return self._resources

    def get_prompts(self) -> List[MCPPrompt]:
        return self._prompts


class MCPClientManager:
    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._configs: Dict[str, MCPServerConfig] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        self._configs[config.name] = config

    def remove_server(self, name: str) -> bool:
        if name in self._clients:
            asyncio.create_task(self._clients[name].disconnect())
            del self._clients[name]
        return self._configs.pop(name, None) is not None

    async def connect_all(self) -> Dict[str, MCPServerInfo]:
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
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()

    def get_client(self, name: str) -> Optional[MCPClient]:
        return self._clients.get(name)

    def get_all_tools(self) -> Dict[str, List[MCPTool]]:
        return {name: client.get_tools() for name, client in self._clients.items()}


_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager


# =============================================================================
# STDIO SERVER
# =============================================================================

@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    category: str = "general"


@dataclass
class ResourceDefinition:
    uri: str
    name: str
    description: Optional[str]
    mime_type: Optional[str]
    handler: Callable


@dataclass
class PromptDefinition:
    name: str
    description: Optional[str]
    arguments: Optional[List[Dict[str, Any]]]
    handler: Callable


class MCPStdioServer:
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
        self._tools[name] = ToolDefinition(
            name=name, description=description, input_schema=input_schema,
            handler=handler, category=category,
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
        self._resources[uri] = ResourceDefinition(
            uri=uri, name=name, description=description,
            mime_type=mime_type, handler=handler,
        )
        logger.info(f"Registered MCP resource: {uri}")

    def register_prompt(
        self,
        name: str,
        description: Optional[str],
        arguments: Optional[List[Dict[str, Any]]],
        handler: Callable,
    ) -> None:
        self._prompts[name] = PromptDefinition(
            name=name, description=description, arguments=arguments, handler=handler,
        )
        logger.info(f"Registered MCP prompt: {name}")

    async def run(self) -> None:
        self._running = True

        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            sys.stdin.buffer,
        )

        self._writer = asyncio.StreamWriter(
            sys.stdout.buffer, protocol=None, reader=None, loop=asyncio.get_event_loop(),
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
        request = MCPRequest(**request_data)

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
        if request.method == MCPMethod.INITIALIZED:
            self._initialized = True
            logger.info("MCP initialization complete")

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        init_params = MCPInitializeParams(**params)
        result = MCPInitializeResult(
            protocol_version="2024-11-05",
            capabilities={"tools": {}, "resources": {}, "prompts": {}},
            server_info=MCPServerInfo(name=self.name, version=self.version),
        )
        return result.model_dump()

    async def _handle_tools_list(self) -> Dict[str, Any]:
        tools = [
            MCPTool(name=name, description=defn.description, input_schema=defn.input_schema)
            for name, defn in self._tools.items()
        ]
        result = MCPListToolsResult(tools=tools)
        return result.model_dump()

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        call_params = MCPCallToolParams(**params)

        if call_params.name not in self._tools:
            raise ValueError(f"Tool not found: {call_params.name}")

        tool_def = self._tools[call_params.name]

        try:
            if asyncio.iscoroutinefunction(tool_def.handler):
                result = await tool_def.handler(**call_params.arguments)
            else:
                result = tool_def.handler(**call_params.arguments)

            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            elif isinstance(result, dict):
                content = [result]
            elif not isinstance(result, list):
                content = [{"type": "text", "text": str(result)}]
            else:
                content = result

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
        resources = [
            MCPResource(uri=uri, name=defn.name, description=defn.description, mime_type=defn.mime_type)
            for uri, defn in self._resources.items()
        ]
        result = MCPListResourcesResult(resources=resources)
        return result.model_dump()

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
        prompts = [
            MCPPrompt(name=name, description=defn.description, arguments=defn.arguments)
            for name, defn in self._prompts.items()
        ]
        result = MCPListPromptsResult(prompts=prompts)
        return result.model_dump()

    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
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

            result = MCPGetPromptResult(description=prompt_def.description, messages=messages)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Prompt get error: {e}")
            raise

    async def _send_response(self, request_id: Union[str, int], result: Dict[str, Any]) -> None:
        response = MCPResponse(id=request_id, result=result)
        await self._send(response.model_dump())

    async def _send_error(
        self,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
    ) -> None:
        response = MCPResponse(id=request_id, error=MCPError(code=code, message=message))
        await self._send(response.model_dump())

    async def _send(self, data: Dict[str, Any]) -> None:
        line = json.dumps(data) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()

    async def shutdown(self) -> None:
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()


def create_default_server() -> MCPStdioServer:
    server = MCPStdioServer()

    # Register database-backed MCP tools (no filesystem, no shell)
    from agentcore.tools import web_search as _web_search, memory_store as _mem_store

    async def mcp_web_search(query: str) -> str:
        result = await _web_search(query=query)
        return str(result.data) if result.success else result.error

    async def mcp_memory_store(key: str, value: str) -> str:
        result = await _mem_store(key=key, value=value)
        return str(result.data) if result.success else result.error

    server.register_tool(
        "web_search", "Search the web for information",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        mcp_web_search, "web",
    )
    server.register_tool(
        "memory_store", "Store a key-value memory entry",
        {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]},
        mcp_memory_store, "knowledge",
    )

    return server


async def run_mcp_server() -> None:
    server = create_default_server()
    await server.run()


if __name__ == "__main__":
    asyncio.run(run_mcp_server())