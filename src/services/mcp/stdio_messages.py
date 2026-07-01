"""
Stdio MCP Messages - JSON-RPC 2.0 representations.
"""
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

class MCPProtocolError(Exception):
    """Base exception for MCP protocol errors."""
    pass

class MCPParseError(MCPProtocolError):
    """Failed to parse JSON-RPC response."""
    pass

class MCPRequestError(MCPProtocolError):
    """MCP server returned an error response."""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"MCP Error {code}: {message}")

@dataclass
class JSONRPCRequest:
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        obj = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            obj["id"] = self.id
        if self.params is not None:
            obj["params"] = self.params
        return json.dumps(obj)

    @classmethod
    def from_json(cls, data: str) -> "JSONRPCRequest":
        obj = json.loads(data)
        return cls(
            id=obj.get("id"),
            method=obj.get("method", ""),
            params=obj.get("params"),
        )

@dataclass
class JSONRPCResponse:
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @classmethod
    def from_json(cls, data: str) -> "JSONRPCResponse":
        obj = json.loads(data)
        return cls(
            id=obj.get("id"),
            result=obj.get("result"),
            error=obj.get("error"),
        )

@dataclass
class ToolManifest:
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolManifest":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
        )
