"""
AgentCore Tools - Registry, Schemas, Builtin Tools

Consolidated tools: registry + schemas + core builtin tools (filesystem, shell, web).
"""
import asyncio
import importlib
import inspect
import logging
import os
import pkgutil
import re
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field
from agentcore.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================

class ParameterType(str):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: List[Any] = Field(default_factory=list)
    items: Optional["ToolParameter"] = None
    properties: Optional[Dict[str, "ToolParameter"]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        schema = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        if self.items:
            schema["items"] = self.items.to_json_schema()
        if self.properties:
            schema["properties"] = {n: p.to_json_schema() for n, p in self.properties.items()}
            req = [n for n, p in self.properties.items() if p.required]
            if req:
                schema["required"] = req
        return schema


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

    def validate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        validated = {}
        for param in self.required:
            if param not in args:
                raise ValueError(f"Missing required parameter: {param}")
            validated[param] = args[param]
        for param, value in args.items():
            if param not in validated:
                validated[param] = value
        return validated

    def to_openai_function(self) -> Dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    def to_anthropic_tool(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return not self.success

    def to_llm_content(self) -> List[Dict[str, Any]]:
        if self.success:
            if isinstance(self.data, str):
                return [{"type": "text", "text": self.data}]
            elif isinstance(self.data, (dict, list)):
                return [{"type": "text", "text": str(self.data)}]
            return [{"type": "text", "text": str(self.data)}]
        return [{"type": "text", "text": f"Error: {self.error}"}]


# =============================================================================
# BASE TOOL
# =============================================================================

class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: List[ToolParameter] = []
    requires_sandbox: bool = False

    def get_schema(self) -> Dict[str, Any]:
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
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        }

    @abstractmethod
    async def execute(self, session_id: str, **kwargs) -> Any:
        pass


# =============================================================================
# BUILTIN TOOL IMPLEMENTATIONS
# =============================================================================

def resolve_workspace_path(path: str) -> Path:
    """Resolve workspace path with security."""
    settings = get_settings()
    base = Path(settings.sandbox_workdir or "./workspace")
    base.mkdir(parents=True, exist_ok=True)
    target = base / path
    target = target.resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError("Path traversal not allowed")
    return target


async def read_file(filepath: str, session_id: str = "", **kwargs) -> ToolResult:
    try:
        path = resolve_workspace_path(filepath)
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {filepath}")
        if not path.is_file():
            return ToolResult(success=False, error=f"Not a file: {filepath}")
        size = path.stat().st_size
        if size > 10 * 1024 * 1024:
            return ToolResult(success=False, error="File too large")
        content = path.read_text(encoding="utf-8", errors="replace")
        return ToolResult(success=True, data=content)
    except Exception as e:
        logger.error(f"read_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def write_file(filepath: str, content: str, session_id: str = "", **kwargs) -> ToolResult:
    try:
        path = resolve_workspace_path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, data=f"Written {len(content)} bytes to {filepath}")
    except Exception as e:
        logger.error(f"write_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def edit_file(filepath: str, old_text: str, new_text: str, session_id: str = "", **kwargs) -> ToolResult:
    try:
        path = resolve_workspace_path(filepath)
        if not path.exists():
            return ToolResult(success=False, error="File not found")
        content = path.read_text(encoding="utf-8", errors="replace")
        if old_text not in content:
            return ToolResult(success=False, error="Old text not found")
        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, data=f"Edited {filepath}")
    except Exception as e:
        logger.error(f"edit_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def delete_file(filepath: str, session_id: str = "", **kwargs) -> ToolResult:
    try:
        path = resolve_workspace_path(filepath)
        if not path.exists():
            return ToolResult(success=False, error="File not found")
        path.unlink()
        return ToolResult(success=True, data=f"Deleted {filepath}")
    except Exception as e:
        logger.error(f"delete_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def list_files(path: str = ".", pattern: str = "*", session_id: str = "", **kwargs) -> ToolResult:
    try:
        base = resolve_workspace_path(path)
        if not base.exists():
            return ToolResult(success=False, error="Directory not found")
        files = []
        for item in base.rglob(pattern):
            if item.is_file():
                try:
                    rel = item.relative_to(base)
                    stat = item.stat()
                    files.append({"path": str(rel), "size": stat.st_size, "modified": stat.st_mtime})
                except ValueError:
                    pass
        return ToolResult(success=True, data=sorted(files, key=lambda x: x["path"]))
    except Exception as e:
        logger.error(f"list_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def glob_files(pattern: str, path: str = ".", session_id: str = "", **kwargs) -> ToolResult:
    try:
        base = resolve_workspace_path(path)
        files = []
        for item in base.glob(pattern):
            if item.is_file():
                try:
                    files.append(str(item.relative_to(base)))
                except ValueError:
                    pass
        return ToolResult(success=True, data=sorted(files))
    except Exception as e:
        logger.error(f"glob_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def grep_files(pattern: str, path: str = ".", file_pattern: str = "*", session_id: str = "", **kwargs) -> ToolResult:
    try:
        base = resolve_workspace_path(path)
        regex = re.compile(pattern)
        matches = []
        for item in base.rglob(file_pattern):
            if not item.is_file():
                continue
            try:
                content = item.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    try:
                        matches.append({"file": str(item.relative_to(base)), "line": i, "content": line.strip()[:200]})
                    except ValueError:
                        pass
        return ToolResult(success=True, data=matches[:100])
    except Exception as e:
        logger.error(f"grep_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def bash_execute(
    command: str,
    working_dir: str = ".",
    timeout: int = 60,
    session_id: str = "",
    **kwargs,
) -> ToolResult:
    try:
        cwd = resolve_workspace_path(working_dir)
        dangerous = ["rm -rf /", "format", "mkfs", "dd if=", "shutdown", "reboot"]
        if any(d in command.lower() for d in dangerous):
            return ToolResult(success=False, error="Command rejected: potentially dangerous")
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "HOME": str(cwd)},
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        return ToolResult(
            success=process.returncode == 0,
            data={
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
            },
            error=stderr.decode("utf-8", errors="replace") if process.returncode != 0 else None,
        )
    except Exception as e:
        logger.error(f"bash_execute error: {e}")
        return ToolResult(success=False, error=str(e))


async def web_search(query: str, max_results: int = 10, session_id: str = "", **kwargs) -> ToolResult:
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/", params={"q": query}, headers={"User-Agent": "Mozilla/5.0"}
            )
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.select(".result")[:max_results]:
            title_elem = result.select_one(".result__title")
            snippet_elem = result.select_one(".result__snippet")
            link_elem = result.select_one(".result__url")
            if title_elem:
                results.append({
                    "title": title_elem.get_text(strip=True),
                    "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                    "url": link_elem.get_text(strip=True) if link_elem else "",
                })
        return ToolResult(success=True, data=results)
    except Exception as e:
        logger.error(f"web_search error: {e}")
        return ToolResult(success=True, data=[{"title": f"Search: {query}", "snippet": "Search unavailable", "url": ""}])


async def web_fetch(url: str, session_id: str = "", **kwargs) -> ToolResult:
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return ToolResult(success=True, data={"url": url, "title": soup.title.string if soup.title else "", "content": text[:50000]})
    except Exception as e:
        logger.error(f"web_fetch error: {e}")
        return ToolResult(success=False, error=str(e))


# =============================================================================
# BUILTIN TOOL SCHEMAS
# =============================================================================

BUILTIN_TOOL_SCHEMAS = {
    "read_file": ToolSchema(name="read_file", description="Read a file from the workspace", parameters={"type": "object", "properties": {"filepath": {"type": "string", "description": "Path to file"}}, "required": ["filepath"]}),
    "write_file": ToolSchema(name="write_file", description="Write content to a file", parameters={"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}),
    "edit_file": ToolSchema(name="edit_file", description="Edit a file by replacing text", parameters={"type": "object", "properties": {"filepath": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["filepath", "old_text", "new_text"]}),
    "delete_file": ToolSchema(name="delete_file", description="Delete a file", parameters={"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}),
    "list_files": ToolSchema(name="list_files", description="List files in a directory", parameters={"type": "object", "properties": {"path": {"type": "string", "default": "."}, "pattern": {"type": "string", "default": "*"}}, "required": []}),
    "glob_files": ToolSchema(name="glob_files", description="Find files matching glob pattern", parameters={"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}}, "required": ["pattern"]}),
    "grep_files": ToolSchema(name="grep_files", description="Search for regex pattern in files", parameters={"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}, "file_pattern": {"type": "string", "default": "*"}}, "required": ["pattern"]}),
    "bash_execute": ToolSchema(name="bash_execute", description="Execute bash command in sandbox", parameters={"type": "object", "properties": {"command": {"type": "string"}, "working_dir": {"type": "string", "default": "."}, "timeout": {"type": "integer", "default": 60}}, "required": ["command"]}),
    "web_search": ToolSchema(name="web_search", description="Search the web", parameters={"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 10}}, "required": ["query"]}),
    "web_fetch": ToolSchema(name="web_fetch", description="Fetch web URL content", parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
}

CORE_TOOL_METADATA = {
    "read_file": {"category": "filesystem", "requires_sandbox": False},
    "write_file": {"category": "filesystem", "requires_sandbox": False, "requires_approval": True},
    "edit_file": {"category": "filesystem", "requires_sandbox": False, "requires_approval": True},
    "list_files": {"category": "filesystem", "requires_sandbox": False},
    "glob_files": {"category": "filesystem", "requires_sandbox": False},
    "grep_files": {"category": "filesystem", "requires_sandbox": False},
    "delete_file": {"category": "filesystem", "requires_sandbox": False, "requires_approval": True},
    "bash_execute": {"category": "shell", "requires_sandbox": True},
    "web_search": {"category": "web", "requires_sandbox": False},
    "web_fetch": {"category": "web", "requires_sandbox": False},
}

CORE_TOOLS = {
    "read_file": read_file, "write_file": write_file, "edit_file": edit_file,
    "delete_file": delete_file, "list_files": list_files, "glob_files": glob_files,
    "grep_files": grep_files, "bash_execute": bash_execute, "web_search": web_search,
    "web_fetch": web_fetch,
}


# =============================================================================
# TOOL REGISTRY
# =============================================================================

@dataclass
class RegisteredTool:
    name: str
    description: str
    schema: ToolSchema
    handler: callable
    category: str = "general"
    requires_sandbox: bool = False
    requires_approval: bool = False
    origin: str = "builtin"


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
        self._discovered = False

    def register(
        self,
        name: str,
        description: str,
        schema: ToolSchema,
        handler: callable,
        category: str = "general",
        requires_sandbox: bool = False,
        requires_approval: bool = False,
        origin: str = "builtin",
    ) -> None:
        self._tools[name] = RegisteredTool(
            name=name, description=description, schema=schema, handler=handler,
            category=category, requires_sandbox=requires_sandbox,
            requires_approval=requires_approval, origin=origin,
        )
        logger.info(f"Registered tool: {name}")

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[RegisteredTool]:
        if not self._discovered:
            self._discover()
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[ToolSchema]:
        tool = self.get(name)
        return tool.schema if tool else None

    def get_handler(self, name: str) -> Optional[callable]:
        tool = self.get(name)
        return tool.handler if tool else None

    def get_all_schemas(self) -> List[ToolSchema]:
        if not self._discovered:
            self._discover()
        return [t.schema for t in self._tools.values()]

    def get_all_names(self) -> List[str]:
        if not self._discovered:
            self._discover()
        return list(self._tools.keys())

    def get_catalog(self) -> List[Dict[str, Any]]:
        if not self._discovered:
            self._discover()
        return [
            {
                "name": t.name, "description": t.description, "category": t.category,
                "origin": t.origin, "requires_sandbox": t.requires_sandbox,
                "requires_approval": t.requires_approval,
                "parameters": t.schema.parameters,
            }
            for t in self._tools.values()
        ]

    def _discover(self) -> None:
        if self._discovered:
            return
        self._discovered = True

        # Register core tools
        for name, handler in CORE_TOOLS.items():
            meta = CORE_TOOL_METADATA.get(name, {})
            schema = BUILTIN_TOOL_SCHEMAS.get(name)
            if not schema:
                schema = ToolSchema(name=name, description=handler.__doc__ or "", parameters={"type": "object", "properties": {}})
            self.register(
                name=name, description=schema.description, schema=schema, handler=handler,
                category=meta.get("category", "general"), requires_sandbox=meta.get("requires_sandbox", False),
                requires_approval=meta.get("requires_approval", False), origin="builtin",
            )

        # Auto-discover from src.tools (fallback)
        try:
            import os
            if os.path.exists("src"):
                import src.tools as tools_pkg
                prefix = tools_pkg.__name__ + "."
                for _, modname, ispkg in pkgutil.walk_packages(tools_pkg.__path__, prefix):
                    if not ispkg:
                        try:
                            importlib.import_module(modname)
                        except Exception as e:
                            logger.warning(f"Failed to load tool module {modname}: {e}")
        except Exception as e:
            pass

        logger.info(f"Tool registry initialized with {len(self._tools)} tools")


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


# Convenience functions
def get_tool_schema(name: str) -> Optional[ToolSchema]:
    return get_tool_registry().get_schema(name)


def get_tool_handler(name: str) -> Optional[callable]:
    return get_tool_registry().get_handler(name)


def get_all_tool_schemas() -> List[ToolSchema]:
    return get_tool_registry().get_all_schemas()


def get_all_tool_names() -> List[str]:
    return get_tool_registry().get_all_names()


def get_tool_catalog() -> List[Dict[str, Any]]:
    return get_tool_registry().get_catalog()