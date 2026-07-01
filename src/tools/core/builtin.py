"""
Core Tools - Built-in Tool Implementations

Provides fundamental filesystem, shell, and search tools.
"""
import asyncio
import logging
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.tools.schemas import ToolResult
from src.runtime.paths import resolve_workspace_path

logger = logging.getLogger(__name__)


# ==================== FILESYSTEM TOOLS ====================

async def read_file(filepath: str, context: Dict[str, Any] = None) -> ToolResult:
    """Read a file from the workspace."""
    try:
        path = resolve_workspace_path(filepath)
        
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {filepath}")
        
        if not path.is_file():
            return ToolResult(success=False, error=f"Not a file: {filepath}")
        
        # Check file size
        size = path.stat().st_size
        if size > 10 * 1024 * 1024:  # 10MB
            return ToolResult(success=False, error=f"File too large: {size} bytes")
        
        content = path.read_text(encoding="utf-8", errors="replace")
        return ToolResult(success=True, data=content)
        
    except Exception as e:
        logger.error(f"read_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def write_file(filepath: str, content: str, context: Dict[str, Any] = None) -> ToolResult:
    """Write content to a file in the workspace."""
    try:
        path = resolve_workspace_path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, data=f"Written {len(content)} bytes to {filepath}")
        
    except Exception as e:
        logger.error(f"write_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def edit_file(filepath: str, old_text: str, new_text: str, context: Dict[str, Any] = None) -> ToolResult:
    """Edit a file by replacing text."""
    try:
        path = resolve_workspace_path(filepath)
        
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {filepath}")
        
        content = path.read_text(encoding="utf-8", errors="replace")
        
        if old_text not in content:
            return ToolResult(success=False, error="Old text not found in file")
        
        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        
        return ToolResult(success=True, data=f"Edited {filepath}")
        
    except Exception as e:
        logger.error(f"edit_file error: {e}")
        return ToolResult(success=False, error=str(e))


async def list_files(path: str = ".", pattern: str = "*", context: Dict[str, Any] = None) -> ToolResult:
    """List files in a directory."""
    try:
        base = resolve_workspace_path(path)
        
        if not base.exists():
            return ToolResult(success=False, error=f"Directory not found: {path}")
        
        files = []
        for item in base.rglob(pattern):
            if item.is_file():
                try:
                    rel = item.relative_to(base)
                    stat = item.stat()
                    files.append({
                        "path": str(rel),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except ValueError:
                    pass  # Skip files outside workspace
        
        return ToolResult(success=True, data=sorted(files, key=lambda x: x["path"]))
        
    except Exception as e:
        logger.error(f"list_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def glob_files(pattern: str, path: str = ".", context: Dict[str, Any] = None) -> ToolResult:
    """Find files matching a glob pattern."""
    try:
        base = resolve_workspace_path(path)
        
        files = []
        for item in base.glob(pattern):
            if item.is_file():
                try:
                    rel = item.relative_to(base)
                    files.append(str(rel))
                except ValueError:
                    pass
        
        return ToolResult(success=True, data=sorted(files))
        
    except Exception as e:
        logger.error(f"glob_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def grep_files(pattern: str, path: str = ".", file_pattern: str = "*", context: Dict[str, Any] = None) -> ToolResult:
    """Search for regex pattern in files."""
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
                        rel = item.relative_to(base)
                        matches.append({
                            "file": str(rel),
                            "line": i,
                            "content": line.strip()[:200],
                        })
                    except ValueError:
                        pass
        
        return ToolResult(success=True, data=matches[:100])  # Limit results
        
    except Exception as e:
        logger.error(f"grep_files error: {e}")
        return ToolResult(success=False, error=str(e))


async def delete_file(filepath: str, context: Dict[str, Any] = None) -> ToolResult:
    """Delete a file from the workspace."""
    try:
        path = resolve_workspace_path(filepath)
        
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {filepath}")
        
        path.unlink()
        return ToolResult(success=True, data=f"Deleted {filepath}")
        
    except Exception as e:
        logger.error(f"delete_file error: {e}")
        return ToolResult(success=False, error=str(e))


# ==================== SHELL TOOLS ====================

async def bash_execute(
    command: str,
    working_dir: str = ".",
    timeout: int = 60,
    context: Dict[str, Any] = None,
) -> ToolResult:
    """Execute a bash command in the sandbox."""
    try:
        cwd = resolve_workspace_path(working_dir)
        
        # Security: reject dangerous commands
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
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout}s",
            )
        
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


# ==================== WEB TOOLS ====================

async def web_search(query: str, max_results: int = 10, context: Dict[str, Any] = None) -> ToolResult:
    """Search the web for information."""
    try:
        # This would integrate with a search API (DuckDuckGo, Bing, etc.)
        # For now, return a placeholder
        import httpx
        
        # Example using DuckDuckGo HTML scrape
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
        
        from bs4 import BeautifulSoup
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
        # Return mock results for development
        return ToolResult(
            success=True,
            data=[{
                "title": f"Search results for: {query}",
                "snippet": "Web search not configured. Add API keys for real search.",
                "url": "",
            }],
        )


async def web_fetch(url: str, context: Dict[str, Any] = None) -> ToolResult:
    """Fetch content from a web URL."""
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text(separator="\n", strip=True)
        
        return ToolResult(
            success=True,
            data={
                "url": url,
                "title": soup.title.string if soup.title else "",
                "content": text[:50000],  # Limit size
            },
        )
        
    except Exception as e:
        logger.error(f"web_fetch error: {e}")
        return ToolResult(success=False, error=str(e))


# ==================== TOOL REGISTRATION ====================

CORE_TOOLS = {
    # Filesystem
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "glob_files": glob_files,
    "grep_files": grep_files,
    "delete_file": delete_file,
    
    # Shell
    "bash_execute": bash_execute,
    
    # Web
    "web_search": web_search,
    "web_fetch": web_fetch,
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


def register_core_tools(registry) -> int:
    """Register all core tools with the registry."""
    from src.tools.schemas import ToolSchema
    
    count = 0
    for name, handler in CORE_TOOLS.items():
        meta = CORE_TOOL_METADATA.get(name, {})
        
        # Get schema from built-ins
        from src.tools.schemas import get_builtin_schema
        schema = get_builtin_schema(name)
        
        if not schema:
            # Create basic schema
            schema = ToolSchema(
                name=name,
                description=handler.__doc__ or "",
                parameters={"type": "object", "properties": {}},
            )
        
        registry.register(
            name=name,
            description=schema.description,
            schema=schema,
            handler=handler,
            category=meta.get("category", "general"),
            requires_sandbox=meta.get("requires_sandbox", False),
            requires_approval=meta.get("requires_approval", False),
        )
        count += 1
    
    logger.info(f"Registered {count} core tools")
    return count