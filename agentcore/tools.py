"""
AgentCore Tools — Minimal Registry and Schemas
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

    def to_openai_function(self) -> Dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    def to_anthropic_tool(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return not self.success

    def to_llm_content(self) -> List[Dict[str, Any]]:
        if self.success:
            return [{"type": "text", "text": str(self.data)}]
        return [{"type": "text", "text": f"Error: {self.error}"}]


@dataclass
class RegisteredTool:
    name: str
    description: str
    schema: ToolSchema
    handler: callable
    category: str = "general"


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, name: str, description: str, schema: ToolSchema, handler: callable, category: str = "general") -> None:
        self._tools[name] = RegisteredTool(name=name, description=description, schema=schema, handler=handler, category=category)

    def get(self, name: str) -> Optional[RegisteredTool]:
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[ToolSchema]:
        tool = self.get(name)
        return tool.schema if tool else None

    def get_handler(self, name: str) -> Optional[callable]:
        tool = self.get(name)
        return tool.handler if tool else None

    def get_all_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[ToolSchema]:
        return [t.schema for t in self._tools.values()]

    def get_catalog(self) -> List[Dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "category": t.category} for t in self._tools.values()]


_registry = ToolRegistry()


# Coordinator level tools registered by default
delegate_schema = ToolSchema(
    name="delegate_to_agent",
    description="Delegate task using A2A.",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "task": {"type": "string"}
        },
        "required": ["agent_name", "task"]
    }
)

create_agent_schema = ToolSchema(
    name="create_mcp_agent",
    description="Register a new custom MCP worker.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"}
        },
        "required": ["name", "description"]
    }
)

_registry.register("delegate_to_agent", "Delegate a subtask to an A2A agent", delegate_schema, lambda: None, "a2a")
_registry.register("create_mcp_agent", "Create a new MCP worker", create_agent_schema, lambda: None, "mcp")


def get_tool_registry() -> ToolRegistry:
    return _registry

def get_tool_handler(name: str) -> Optional[callable]:
    return _registry.get_handler(name)

def get_all_tool_schemas() -> List[ToolSchema]:
    return _registry.get_all_schemas()

def get_all_tool_names() -> List[str]:
    return _registry.get_all_names()