"""Filesystem MCP — Read, write, list, search, create, delete local files."""
import os
import glob
import asyncio
from pathlib import Path
from agentcore.mcps import register_mcp


@register_mcp
class FilesystemMCP:
    name = "filesystem-mcp"
    description = "Read, write, search, and manage local files and directories"
    TOOLS = {
        "read_file":    {"params": {"path": "string"}, "desc": "Read file contents at given path"},
        "write_file":   {"params": {"path": "string", "content": "string"}, "desc": "Write content to a file (creates parent dirs)"},
        "list_dir":     {"params": {"path": "string"}, "desc": "List files and subdirectories in a directory"},
        "search_files": {"params": {"path": "string", "pattern": "string"}, "desc": "Glob search for files matching pattern"},
        "create_dir":   {"params": {"path": "string"}, "desc": "Create a directory (and parents)"},
        "delete_file":  {"params": {"path": "string"}, "desc": "Delete a file (destructive — requires approval)"},
    }
    DESTRUCTIVE = {"delete_file"}

    async def call_tool(self, name: str, args: dict, **kwargs) -> dict:
        p = Path(args.get("path", ""))
        
        def run_filesystem_op():
            if name == "read_file":
                # Cap reads at 500KB
                stat = p.stat()
                if stat.st_size > 500000:
                    raise ValueError(f"File too large: {stat.st_size} bytes (limit 500KB)")
                return {"content": p.read_text(encoding="utf-8", errors="replace")}
            elif name == "write_file":
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args["content"], encoding="utf-8")
                return {"written_bytes": len(args["content"]), "path": str(p)}
            elif name == "list_dir":
                entries = []
                for item in sorted(p.iterdir()):
                    entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file",
                                    "size": item.stat().st_size if item.is_file() else None})
                # Cap listing to 200 items
                return {"entries": entries[:200], "count": len(entries), "truncated": len(entries) > 200}
            elif name == "search_files":
                matches = glob.glob(str(p / args["pattern"]), recursive=True)
                return {"matches": matches[:50], "total": len(matches)}
            elif name == "create_dir":
                p.mkdir(parents=True, exist_ok=True)
                return {"created": str(p)}
            elif name == "delete_file":
                p.unlink(missing_ok=True)
                return {"deleted": str(p)}
            raise ValueError(f"Unknown tool: {name}")

        return await asyncio.to_thread(run_filesystem_op)
