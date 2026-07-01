"""
Core Tool Interface
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True

class BaseTool(ABC):
    """Abstract basis for all modular, tightly-bounded tools."""
    name: str = ""
    description: str = ""
    parameters: List[ToolParameter] = []
    requires_sandbox: bool = False

    def get_schema(self) -> Dict[str, Any]:
        """Generate OpenAI/Anthropic compatible JSON schema."""
        props = {}
        required = []
        for p in self.parameters:
            props[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required
                }
            }
        }

    @abstractmethod
    async def execute(self, session_id: str, **kwargs) -> Any:
        """Core execution logic. Must be overridden."""
        pass
