"""
agentcore/mcp_client.py — Production-grade Stdio JSON-RPC MCP Client
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class StdioMCPClient:
    """Client for Model Context Protocol servers running over Stdio transport."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.command = config.get("command")
        self.args = config.get("args") or []
        self.description = config.get("description") or f"Stdio MCP: {name}"
        self.status = "offline"
        self.tools: List[Dict[str, Any]] = []
        
        self._process: Optional[asyncio.subprocess.Process] = None
        self._read_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._request_id = 1
        self._lock = asyncio.Lock()

    async def connect(self, timeout: float = 10.0) -> bool:
        """Spawn the process and perform the standard initialization handshake."""
        async with self._lock:
            if self.status == "healthy" and self._process:
                return True
            
            self.status = "connecting"
            logger.info(f"Connecting to Stdio MCP server '{self.name}' via '{self.command} {self.args}'")
            
            try:
                self._process = await asyncio.create_subprocess_exec(
                    self.command,
                    *self.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )
                
                self._read_task = asyncio.create_task(self._read_loop())
                
                # Handshake 1: Initialize
                init_res = await self._send_request("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agentcore-client", "version": "1.0.0"}
                }, timeout=timeout)
                
                # Handshake 2: Initialized notification
                await self._send_notification("notifications/initialized")
                
                # Fetch list of tools
                tools_res = await self._send_request("tools/list", {}, timeout=timeout)
                self.tools = tools_res.get("tools") or []
                self.status = "healthy"
                logger.info(f"Connected to MCP '{self.name}'. Registered {len(self.tools)} tools.")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to MCP '{self.name}': {e}")
                await self.disconnect()
                return False

    async def _read_loop(self):
        """Read standard output stream from process and route responses to pending futures."""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                try:
                    payload = json.loads(line.decode("utf-8").strip())
                    if "id" in payload:
                        req_id = payload["id"]
                        future = self._pending_requests.pop(req_id, None)
                        if future and not future.done():
                            if "error" in payload:
                                future.set_exception(Exception(payload["error"].get("message", "Unknown error")))
                            else:
                                future.set_result(payload.get("result", {}))
                except Exception as ex:
                    logger.debug(f"Error parsing json-rpc output: {ex}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Read loop crash for MCP '{self.name}': {e}")
        finally:
            self.status = "offline"

    async def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 15.0) -> Any:
        """Send a JSON-RPC request and await response."""
        if not self._process or not self._process.stdin:
            raise Exception("Subprocess not running")
            
        req_id = self._request_id
        self._request_id += 1
        
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = future
        
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        try:
            self._process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await self._process.stdin.drain()
            return await asyncio.wait_for(future, timeout=timeout)
        except Exception as e:
            self._pending_requests.pop(req_id, None)
            raise e

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        self._process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._process.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Execute a tool on the stdio MCP server."""
        if self.status != "healthy":
            connected = await self.connect()
            if not connected:
                raise Exception(f"MCP server '{self.name}' is offline")
                
        try:
            res = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            }, timeout=timeout)
            return res
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}' on MCP '{self.name}': {e}")
            raise e

    async def disconnect(self) -> None:
        """Shut down background loops and terminate the subprocess."""
        self.status = "offline"
        if self._read_task:
            self._read_task.cancel()
            self._read_task = None
            
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        logger.info(f"Disconnected from Stdio MCP server '{self.name}'")
