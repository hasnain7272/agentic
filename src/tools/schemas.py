"""
Tool Schemas - Pydantic Models for Tool Definitions

Defines tool schema format, validation, and LLM function calling formats.
"""
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field, validator
from enum import Enum


class ParameterType(str, Enum):
    """JSON Schema parameter types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """Single tool parameter definition."""
    name: str
    type: ParameterType
    description: str
    required: bool = False
    default: Any = None
    enum: List[Any] = Field(default_factory=list)
    items: Optional["ToolParameter"] = None  # For arrays
    properties: Optional[Dict[str, "ToolParameter"]] = None  # For objects
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema fragment."""
        schema = {
            "type": self.type.value,
            "description": self.description,
        }
        
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        if self.items:
            schema["items"] = self.items.to_json_schema()
        if self.properties:
            schema["properties"] = {
                name: prop.to_json_schema() 
                for name, prop in self.properties.items()
            }
            required_props = [
                name for name, prop in self.properties.items() 
                if prop.required
            ]
            if required_props:
                schema["required"] = required_props
        
        return schema


class ToolSchema(BaseModel):
    """Complete tool schema for LLM function calling."""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)
    
    @classmethod
    def from_function(cls, func) -> "ToolSchema":
        """Create schema from function signature (deprecated - use manual)."""
        import inspect
        
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for name, param in sig.parameters.items():
            if name in ("self", "cls", "context", "kwargs"):
                continue
            
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                param_type = str
            
            # Map Python types to JSON schema types
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }
            json_type = type_map.get(param_type, "string")
            
            properties[name] = {"type": json_type}
            
            if param.default == inspect.Parameter.empty:
                required.append(name)
        
        return cls(
            name=func.__name__,
            description=func.__doc__ or "",
            parameters={"type": "object", "properties": properties, "required": required},
        )
    
    def validate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate arguments against schema."""
        # Basic validation - could be enhanced with jsonschema
        validated = {}
        
        for param_name in self.required:
            if param_name not in args:
                raise ValueError(f"Missing required parameter: {param_name}")
            validated[param_name] = args[param_name]
        
        # Include optional params if provided
        for param_name, value in args.items():
            if param_name not in validated:
                validated[param_name] = value
        
        return validated
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
    
    def to_anthropic_tool(self) -> Dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class ToolResult(BaseModel):
    """Standardized tool execution result."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def is_error(self) -> bool:
        return not self.success
    
    def to_llm_content(self) -> List[Dict[str, Any]]:
        """Convert to LLM-readable content format."""
        if self.success:
            if isinstance(self.data, str):
                return [{"type": "text", "text": self.data}]
            elif isinstance(self.data, dict):
                return [{"type": "text", "text": str(self.data)}]
            elif isinstance(self.data, list):
                return [
                    {"type": "text", "text": str(item)} 
                    for item in self.data
                ]
            else:
                return [{"type": "text", "text": str(self.data)}]
        else:
            return [{"type": "text", "text": f"Error: {self.error}"}]


# Built-in tool schemas for core functionality
BUILTIN_TOOL_SCHEMAS = {
    "read_file": ToolSchema(
        name="read_file",
        description="Read a file from the workspace",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to file"},
            },
            "required": ["filepath"],
        },
    ),
    "write_file": ToolSchema(
        name="write_file",
        description="Write content to a file in the workspace",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["filepath", "content"],
        },
    ),
    "list_files": ToolSchema(
        name="list_files",
        description="List files in a directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "pattern": {"type": "string", "description": "Glob pattern", "default": "*"},
            },
            "required": [],
        },
    ),
    "bash_execute": ToolSchema(
        name="bash_execute",
        description="Execute a bash command in the sandbox",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "working_dir": {"type": "string", "description": "Working directory", "default": "."},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            },
            "required": ["command"],
        },
    ),
    "grep_files": ToolSchema(
        name="grep_files",
        description="Search for pattern in files",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "path": {"type": "string", "description": "Search path", "default": "."},
                "file_pattern": {"type": "string", "description": "File glob pattern", "default": "*"},
            },
            "required": ["pattern"],
        },
    ),
    "web_search": ToolSchema(
        name="web_search",
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
    ),
}


def get_builtin_schemas() -> List[ToolSchema]:
    """Get all built-in tool schemas."""
    return list(BUILTIN_TOOL_SCHEMAS.values())


def get_builtin_schema(name: str) -> Optional[ToolSchema]:
    """Get a built-in tool schema by name."""
    return BUILTIN_TOOL_SCHEMAS.get(name)