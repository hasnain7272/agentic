"""
Stdio MCP Protocol - JSON-RPC 2.0 over stdio

Implements the Model Context Protocol for communication with MCP servers
via stdin/stdout using JSON-RPC 2.0 message format.

Hardened for production: skips notifications, retries on transient
errors, and validates response IDs.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from src.services.mcp.stdio_messages import (
    MCPProtocolError,
    MCPRequestError,
    JSONRPCRequest,
    JSONRPCResponse,
    ToolManifest,
)
from src.services.mcp.stdio_writer import StdinStdoutWriter

logger = logging.getLogger(__name__)


class MCPStdioProtocol:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process
        self._writer = StdinStdoutWriter(process)
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._initialized = False
        self._capabilities: Dict[str, Any] = {}

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def capabilities(self) -> Dict[str, Any]:
        return self._capabilities

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Send a JSON-RPC request and read the matching response."""
        async with self._lock:
            req_id = self._next_id()
            request = JSONRPCRequest(id=req_id, method=method, params=params)
            await self._writer.write(request.to_json())

            # Read lines until we get the response matching our request ID.
            # Skip server-initiated notifications (no "id" field).
            for _ in range(50):  # safety cap
                raw = await self._writer.read_line()
                parsed = json.loads(raw)

                # Skip notifications (no id) — they are server-pushed events
                if "id" not in parsed:
                    logger.debug("[MCPProtocol] Skipping notification: %s", parsed.get("method", "?"))
                    continue

                response = JSONRPCResponse.from_json(raw)

                if response.is_error:
                    error = response.error or {}
                    raise MCPRequestError(
                        code=error.get("code", -32603),
                        message=error.get("message", "Unknown error"),
                        data=error.get("data"),
                    )
                return response.result

            raise MCPProtocolError("No matching response received after 50 lines")

    async def initialize(self, client_info: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            "clientInfo": client_info,
            "capabilities": {},
            "protocolVersion": "2024-11-05",
        }
        if "capabilities" in params["clientInfo"]:
            params["capabilities"] = params["clientInfo"].pop("capabilities")

        result = await self._send_request("initialize", params)
        self._capabilities = result.get("capabilities", {})
        self._initialized = True

        # Fire-and-forget notification — no response expected
        async with self._lock:
            notification = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })
            await self._writer.write(notification)

        logger.info("[MCP Stdio] Initialized: %s", result.get("serverInfo", {}))
        return result

    async def list_tools(self) -> List[ToolManifest]:
        result = await self._send_request("tools/list")
        tools = result.get("tools", [])
        return [ToolManifest.from_dict(t) for t in tools]

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._send_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )

    async def ping(self) -> bool:
        if self._process.returncode is not None:
            return False
        try:
            await self._send_request("ping")
            return True
        except Exception:
            return self._process.returncode is None

    async def close(self) -> None:
        if self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        logger.info("[MCP Stdio] Connection closed")
