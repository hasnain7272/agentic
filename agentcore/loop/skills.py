"""
AgentCore Native Skills — Zero-latency local filesystem tools
"""
import os
import glob
import asyncio
from pathlib import Path
from typing import Dict, Any, List

def _resolve_path(path_str: str) -> Path:
    return Path(path_str).absolute()

async def read_file(path: str, start_line: int = 1, end_line: int = None) -> Dict[str, Any]:
    def _read():
        p = _resolve_path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        content = p.read_text(encoding="utf-8", errors="replace")
        if start_line != 1 or end_line is not None:
            lines = content.splitlines()
            total_lines = len(lines)
            start = max(1, int(start_line))
            end = min(total_lines, int(end_line)) if end_line is not None else total_lines
            selected = lines[start - 1 : end]
            formatted = "\n".join(f"{start + i}: {line}" for i, line in enumerate(selected))
            return {"content": formatted, "start_line": start, "end_line": end, "total_lines": total_lines}
        
        stat = p.stat()
        if stat.st_size > 500000:
            raise ValueError(f"File too large: {stat.st_size} bytes (limit 500KB)")
        return {"content": content}
    return await asyncio.to_thread(_read)

async def write_file(path: str, content: str) -> Dict[str, Any]:
    def _write():
        p = _resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"written_bytes": len(content), "path": str(p)}
    return await asyncio.to_thread(_write)

async def patch_file(path: str, target: str, replacement: str) -> Dict[str, Any]:
    def _patch():
        p = _resolve_path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        content = p.read_text(encoding="utf-8", errors="replace")
        occurrences = content.count(target)
        if occurrences == 0:
            raise ValueError("Error: Target content not found. Make sure indentation and newlines match exactly.")
        elif occurrences > 1:
            raise ValueError(f"Error: Target content not unique; found {occurrences} occurrences. Specify a larger, unique block.")
        new_content = content.replace(target, replacement, 1)
        p.write_text(new_content, encoding="utf-8")
        return {"success": True, "message": f"Successfully patched file {path}"}
    return await asyncio.to_thread(_patch)

async def grep_search(pattern: str, path: str = ".") -> Dict[str, Any]:
    def _grep():
        search_dir = _resolve_path(path)
        results = []
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist")]
            for file in files:
                file_path = Path(root) / file
                try:
                    if file_path.stat().st_size > 1000000:
                        continue
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                    if pattern in text:
                        for idx, line in enumerate(text.splitlines()):
                            if pattern in line:
                                results.append({
                                    "file": str(file_path),
                                    "line": idx + 1,
                                    "content": line.strip()
                                })
                                if len(results) >= 50:
                                    break
                except Exception:
                    pass
                if len(results) >= 50:
                    break
            if len(results) >= 50:
                break
        return {"matches": results[:50], "total": len(results)}
    return await asyncio.to_thread(_grep)

async def list_dir(path: str) -> Dict[str, Any]:
    def _list():
        p = _resolve_path(path)
        entries = []
        for item in sorted(p.iterdir()):
            entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else None})
        return {"entries": entries[:200], "count": len(entries), "truncated": len(entries) > 200}
    return await asyncio.to_thread(_list)

async def create_dir(path: str) -> Dict[str, Any]:
    def _create():
        p = _resolve_path(path)
        p.mkdir(parents=True, exist_ok=True)
        return {"created": str(p)}
    return await asyncio.to_thread(_create)

async def delete_file(path: str) -> Dict[str, Any]:
    def _delete():
        p = _resolve_path(path)
        p.unlink(missing_ok=True)
        return {"deleted": str(p)}
    return await asyncio.to_thread(_delete)

# Direct tool dispatch mapping for high-performance internal skills
NATIVE_SKILLS = {
    "read_file": read_file,
    "write_file": write_file,
    "patch_file": patch_file,
    "grep_search": grep_search,
    "list_dir": list_dir,
    "create_dir": create_dir,
    "delete_file": delete_file,
}

NATIVE_SKILLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents. Optionally supports start_line and end_line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to file"},
                    "start_line": {"type": "integer", "description": "1-indexed starting line number", "default": 1},
                    "end_line": {"type": "integer", "description": "1-indexed ending line number (inclusive)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write entire content to a file. Overwrites existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to target file"},
                    "content": {"type": "string", "description": "Full file content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Replace a unique, contiguous block of lines in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to modify"},
                    "target": {"type": "string", "description": "Exact text block to replace"},
                    "replacement": {"type": "string", "description": "New replacement text"}
                },
                "required": ["path", "target", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search recursively for a text pattern in files across the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text pattern to search for"},
                    "path": {"type": "string", "description": "Search root directory", "default": "."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories inside a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "Create a new directory recursively.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file. Destructive operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to delete"}
                },
                "required": ["path"]
            }
        }
    }
]
