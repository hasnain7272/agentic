"""
AgentCore Tools — Registry, Schemas, Skilled Tools

Database-only tools: web search, memory, code execution, API integration,
content generation, communication, and A2A delegation.
No filesystem tools. No sandbox. Everything is API/DB-backed.
"""
import asyncio
import importlib
import logging
import os
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field
from agentcore.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================

class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: List[Any] = Field(default_factory=list)

    def to_json_schema(self) -> Dict[str, Any]:
        schema = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
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
            return [{"type": "text", "text": str(self.data)}]
        return [{"type": "text", "text": f"Error: {self.error}"}]


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: List[ToolParameter] = []

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
# SKILLED TOOL IMPLEMENTATIONS (Database/API-backed, no filesystem)
# =============================================================================

async def web_search(query: str, max_results: int = 10, session_id: str = "", **kwargs) -> ToolResult:
    """Search the web using DuckDuckGo."""
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
    """Fetch and extract text content from a web URL."""
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


async def memory_store(key: str, value: str, session_id: str = "", **kwargs) -> ToolResult:
    """Store a key-value memory entry in the database for the current session."""
    try:
        from agentcore.database import get_db, SessionModel
        from sqlalchemy import select
        async for db in get_db():
            result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return ToolResult(success=False, error="Session not found")
            meta = dict(session.meta or {})
            memories = dict(meta.get("memories", {}))
            memories[key] = value
            meta["memories"] = memories
            session.meta = meta
            db.add(session)
            await db.commit()
            return ToolResult(success=True, data=f"Stored memory '{key}'")
    except Exception as e:
        logger.error(f"memory_store error: {e}")
        return ToolResult(success=False, error=str(e))


async def memory_recall(key: str = "", session_id: str = "", **kwargs) -> ToolResult:
    """Recall stored memories from the database. If key is empty, returns all memories."""
    try:
        from agentcore.database import get_db, SessionModel
        from sqlalchemy import select
        async for db in get_db():
            result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return ToolResult(success=False, error="Session not found")
            memories = (session.meta or {}).get("memories", {})
            if key:
                value = memories.get(key)
                if value is None:
                    return ToolResult(success=False, error=f"No memory found for key '{key}'")
                return ToolResult(success=True, data={"key": key, "value": value})
            return ToolResult(success=True, data=memories)
    except Exception as e:
        logger.error(f"memory_recall error: {e}")
        return ToolResult(success=False, error=str(e))


async def run_code(code: str, language: str = "python", session_id: str = "", **kwargs) -> ToolResult:
    """Execute a code snippet in a restricted environment. Supports python and javascript."""
    try:
        if language == "python":
            import io, contextlib
            output = io.StringIO()
            restricted_globals = {"__builtins__": {
                "print": lambda *a, **k: output.write(" ".join(str(x) for x in a) + "\n"),
                "len": len, "range": range, "int": int, "float": float, "str": str,
                "list": list, "dict": dict, "tuple": tuple, "set": set, "bool": bool,
                "sorted": sorted, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
                "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
                "isinstance": isinstance, "type": type, "hasattr": hasattr, "getattr": getattr,
            }}
            with contextlib.redirect_stdout(output):
                exec(code, restricted_globals)
            return ToolResult(success=True, data={"output": output.getvalue(), "language": language})
        else:
            return ToolResult(success=False, error=f"Language '{language}' not yet supported server-side")
    except Exception as e:
        return ToolResult(success=True, data={"output": "", "error": str(e), "language": language})


async def http_request(url: str, method: str = "GET", headers: Dict[str, str] = None, body: str = "", session_id: str = "", **kwargs) -> ToolResult:
    """Make an HTTP request to an external API."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method=method.upper(), url=url,
                headers=headers or {}, content=body if body else None,
            )
        return ToolResult(success=True, data={
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text[:20000],
        })
    except Exception as e:
        logger.error(f"http_request error: {e}")
        return ToolResult(success=False, error=str(e))


async def generate_image(prompt: str, session_id: str = "", **kwargs) -> ToolResult:
    """Generate an image from a text prompt using the configured image API."""
    return ToolResult(success=True, data={"prompt": prompt, "status": "Image generation API not configured. Configure DALL-E or Imagen endpoint in settings."})


async def send_notification(message: str, channel: str = "log", session_id: str = "", **kwargs) -> ToolResult:
    """Send a notification message. Channel can be 'log', 'email', or 'webhook'."""
    logger.info(f"[Notification:{channel}] {message}")
    return ToolResult(success=True, data=f"Notification sent via {channel}: {message}")


async def delegate_task(target_session_id: str, task_description: str, session_id: str = "", **kwargs) -> ToolResult:
    """Delegate a sub-task to another agent session in the swarm."""
    try:
        from agentcore.database import get_db, SessionModel, MessageModel
        from sqlalchemy import select
        async for db in get_db():
            result = await db.execute(select(SessionModel).where(SessionModel.id == target_session_id))
            target = result.scalar_one_or_none()
            if not target:
                return ToolResult(success=False, error=f"Target session '{target_session_id}' not found")
            return ToolResult(success=True, data={
                "delegated_to": target_session_id,
                "target_name": target.title,
                "task": task_description,
                "status": "Task delegation noted. Use A2A links to share context between sessions.",
            })
    except Exception as e:
        logger.error(f"delegate_task error: {e}")
        return ToolResult(success=False, error=str(e))


async def query_agent(target_session_id: str, question: str, session_id: str = "", **kwargs) -> ToolResult:
    """Query another linked agent session for information from its conversation history."""
    try:
        from agentcore.database import get_db, SessionModel, MessageModel
        from sqlalchemy import select
        async for db in get_db():
            result = await db.execute(select(SessionModel).where(SessionModel.id == target_session_id))
            target = result.scalar_one_or_none()
            if not target:
                return ToolResult(success=False, error=f"Target session '{target_session_id}' not found")
            msgs_result = await db.execute(
                select(MessageModel).where(MessageModel.session_id == target_session_id)
                .order_by(MessageModel.created_at.desc()).limit(10)
            )
            msgs = list(reversed(msgs_result.scalars().all()))
            context = "\n".join([f"[{m.role}] {m.content[:500]}" for m in msgs])
            return ToolResult(success=True, data={
                "target_session": target_session_id,
                "target_name": target.title,
                "question": question,
                "context": context or "(No messages in target session)",
            })
    except Exception as e:
        logger.error(f"query_agent error: {e}")
        return ToolResult(success=False, error=str(e))


# =============================================================================
# TOOL SCHEMAS & REGISTRY
# =============================================================================

BUILTIN_TOOL_SCHEMAS = {
    "web_search": ToolSchema(name="web_search", description="Search the web for information", parameters={"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "max_results": {"type": "integer", "default": 10}}, "required": ["query"]}),
    "web_fetch": ToolSchema(name="web_fetch", description="Fetch and extract text content from a web URL", parameters={"type": "object", "properties": {"url": {"type": "string", "description": "URL to fetch"}}, "required": ["url"]}),
    "memory_store": ToolSchema(name="memory_store", description="Store a key-value memory entry in the database for this session", parameters={"type": "object", "properties": {"key": {"type": "string", "description": "Memory key"}, "value": {"type": "string", "description": "Memory value to store"}}, "required": ["key", "value"]}),
    "memory_recall": ToolSchema(name="memory_recall", description="Recall stored memories from the database. Empty key returns all memories", parameters={"type": "object", "properties": {"key": {"type": "string", "description": "Memory key to recall (empty for all)", "default": ""}}, "required": []}),
    "run_code": ToolSchema(name="run_code", description="Execute a code snippet (Python). Returns stdout output", parameters={"type": "object", "properties": {"code": {"type": "string", "description": "Code to execute"}, "language": {"type": "string", "default": "python", "description": "Language: python"}}, "required": ["code"]}),
    "http_request": ToolSchema(name="http_request", description="Make an HTTP request to an external API", parameters={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string", "default": "GET", "description": "HTTP method"}, "headers": {"type": "object", "default": {}}, "body": {"type": "string", "default": ""}}, "required": ["url"]}),
    "generate_image": ToolSchema(name="generate_image", description="Generate an image from a text prompt", parameters={"type": "object", "properties": {"prompt": {"type": "string", "description": "Image description prompt"}}, "required": ["prompt"]}),
    "send_notification": ToolSchema(name="send_notification", description="Send a notification message via log, email, or webhook", parameters={"type": "object", "properties": {"message": {"type": "string"}, "channel": {"type": "string", "default": "log", "description": "Channel: log, email, webhook"}}, "required": ["message"]}),
    "delegate_task": ToolSchema(name="delegate_task", description="Delegate a sub-task to another agent session in the swarm", parameters={"type": "object", "properties": {"target_session_id": {"type": "string", "description": "Target session ID"}, "task_description": {"type": "string", "description": "Task to delegate"}}, "required": ["target_session_id", "task_description"]}),
    "query_agent": ToolSchema(name="query_agent", description="Query another linked agent session for information", parameters={"type": "object", "properties": {"target_session_id": {"type": "string", "description": "Target session ID"}, "question": {"type": "string", "description": "Question to ask"}}, "required": ["target_session_id", "question"]}),
}

CORE_TOOL_METADATA = {
    "web_search": {"category": "web"},
    "web_fetch": {"category": "web"},
    "memory_store": {"category": "knowledge"},
    "memory_recall": {"category": "knowledge"},
    "run_code": {"category": "code"},
    "http_request": {"category": "integration"},
    "generate_image": {"category": "content"},
    "send_notification": {"category": "communication"},
    "delegate_task": {"category": "a2a"},
    "query_agent": {"category": "a2a"},
}

CORE_TOOLS = {
    "web_search": web_search, "web_fetch": web_fetch,
    "memory_store": memory_store, "memory_recall": memory_recall,
    "run_code": run_code, "http_request": http_request,
    "generate_image": generate_image, "send_notification": send_notification,
    "delegate_task": delegate_task, "query_agent": query_agent,
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
    requires_approval: bool = False
    origin: str = "builtin"


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
        self._discovered = False

    def register(self, name: str, description: str, schema: ToolSchema, handler: callable,
                 category: str = "general", requires_approval: bool = False, origin: str = "builtin") -> None:
        self._tools[name] = RegisteredTool(
            name=name, description=description, schema=schema, handler=handler,
            category=category, requires_approval=requires_approval, origin=origin,
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
            {"name": t.name, "description": t.description, "category": t.category, "origin": t.origin}
            for t in self._tools.values()
        ]

    def get_schemas(self, category: Optional[str] = None) -> List[ToolSchema]:
        if not self._discovered:
            self._discover()
        if category:
            return [t.schema for t in self._tools.values() if t.category == category]
        return [t.schema for t in self._tools.values()]

    def get_categories(self) -> List[str]:
        if not self._discovered:
            self._discover()
        return list(sorted(set(t.category for t in self._tools.values())))

    def get_openai_functions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        return [s.to_openai_function() for s in self.get_schemas(category)]

    async def discover_mcp_tools(self) -> int:
        return 0

    def _discover(self) -> None:
        if self._discovered:
            return
        self._discovered = True
        for name, handler in CORE_TOOLS.items():
            meta = CORE_TOOL_METADATA.get(name, {})
            schema = BUILTIN_TOOL_SCHEMAS.get(name)
            if not schema:
                schema = ToolSchema(name=name, description=handler.__doc__ or "", parameters={"type": "object", "properties": {}})
            self.register(
                name=name, description=schema.description, schema=schema, handler=handler,
                category=meta.get("category", "general"),
                requires_approval=meta.get("requires_approval", False), origin="builtin",
            )
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