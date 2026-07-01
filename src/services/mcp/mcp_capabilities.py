"""
MCP Capability Models and Validation

Defines MCP server capabilities and validates tool schemas
against the Model Context Protocol specification.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import re


class Capability(str, Enum):
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "promts"
    LOGGING = "logging"


SUPPORTED_PROTOCOL_VERSIONS = {"1.0.0", "2024-11-05"}
MAX_PARAMETERS = 50
MAX_DESCRIPTION_LENGTH = 1000
MAX_TOOL_NAME_LENGTH = 128


@dataclass
class ToolCapability:
    name: str
    description: str
    parameters: List["ParameterSchema"] = field(default_factory=list)
    annotations: Optional[Dict[str, Any]] = None

    def validate(self) -> List[str]:
        errors = []
        if len(self.name) > MAX_TOOL_NAME_LENGTH:
            errors.append(f"Tool name exceeds {MAX_TOOL_NAME_LENGTH} chars")
        if not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            errors.append("Tool name contains invalid characters")
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            errors.append(f"Description exceeds {MAX_DESCRIPTION_LENGTH} chars")
        if len(self.parameters) > MAX_PARAMETERS:
            errors.append(f"Exceeds maximum {MAX_PARAMETERS} parameters")
        for param in self.parameters:
            errors.extend(param.validate())
        return errors


@dataclass
class ParameterSchema:
    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    VALID_TYPES = {"string", "number", "integer", "boolean", "array", "object"}

    def validate(self) -> List[str]:
        errors = []
        if self.type not in self.VALID_TYPES:
            errors.append(f"Invalid parameter type: {self.type}")
        if self.enum and not all(isinstance(v, str) for v in self.enum):
            errors.append("Enum values must be strings")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                errors.append("Minimum exceeds maximum")
        return errors


@dataclass
class MCPServerCapabilities:
    version: str
    tools: List[ToolCapability] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    logging_level: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if self.version not in SUPPORTED_PROTOCOL_VERSIONS:
            errors.append(f"Unsupported protocol version: {self.version}")
        for tool in self.tools:
            errors.extend(tool.validate())
        if self.logging_level and self.logging_level not in {"debug", "info", "warn", "error"}:
            errors.append(f"Invalid logging level: {self.logging_level}")
        return errors

    def get_tool_names(self) -> Set[str]:
        return {t.name for t in self.tools}


@dataclass
class MCPConnectionConfig:
    endpoint_url: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    allowed_hosts: Optional[List[str]] = None

    def validate(self) -> List[str]:
        errors = []
        if self.timeout_seconds <= 0 or self.timeout_seconds > 300:
            errors.append("Timeout must be between 0 and 300 seconds")
        if self.max_retries < 0 or self.max_retries > 10:
            errors.append("Max retries must be between 0 and 10")
        return errors