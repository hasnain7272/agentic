"""Filesystem MCP — Read, write, list, search, create, delete local files."""
import os
import glob
import asyncio
from pathlib import Path
from agentcore.mcps import register_mcp


@register_mcp
class FilesystemMCP:
    name = "filesystem-mcp"
    description = "Read, write, search, patch, and manage local files and directories"
    TOOLS = {
        "read_file": {
            "params": {"path": "string"},
            "desc": "Read file contents at given path. Optionally supports start_line and end_line parameters."
        },
        "patch_file": {
            "params": {"path": "string", "target": "string", "replacement": "string"},
            "desc": "Replace a specific contiguous block of text (target) in a file with new content (replacement). The target text must match exactly."
        },
        "grep_search": {
            "params": {"pattern": "string"},
            "desc": "Search recursively for a text pattern in files across the workspace."
        },
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
                start_line = args.get("start_line", 1)
                end_line = args.get("end_line")
                
                content = p.read_text(encoding="utf-8", errors="replace")
                
                # If optional line ranges are requested or defined
                if start_line != 1 or end_line is not None:
                    lines = content.splitlines()
                    total_lines = len(lines)
                    start = max(1, int(start_line))
                    end = min(total_lines, int(end_line)) if end_line is not None else total_lines
                    
                    selected_lines = lines[start - 1 : end]
                    formatted = "\n".join(f"{start + i}: {line}" for i, line in enumerate(selected_lines))
                    return {
                        "content": formatted,
                        "start_line": start,
                        "end_line": end,
                        "total_lines": total_lines
                    }
                
                # Cap reads at 500KB
                stat = p.stat()
                if stat.st_size > 500000:
                    raise ValueError(f"File too large: {stat.st_size} bytes (limit 500KB)")
                return {"content": content}

            elif name == "patch_file":
                target = args["target"]
                replacement = args["replacement"]
                
                if not p.exists():
                    raise FileNotFoundError(f"File not found: {p}")
                
                content = p.read_text(encoding="utf-8", errors="replace")
                
                occurrences = content.count(target)
                if occurrences == 0:
                    raise ValueError("Error: Target content not found in the file. Make sure leading spaces, indentation, and newlines match exactly.")
                elif occurrences > 1:
                    raise ValueError(f"Error: Target content is not unique; found {occurrences} occurrences in the file. Please specify a larger, unique block of lines.")
                
                new_content = content.replace(target, replacement, 1)
                p.write_text(new_content, encoding="utf-8")
                return {"success": True, "message": f"Successfully patched file {p}"}

            elif name == "grep_search":
                pattern = args["pattern"]
                search_dir = Path(args.get("path", "."))
                
                results = []
                for root, dirs, files in os.walk(search_dir):
                    dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist")]
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            stat = file_path.stat()
                            if stat.st_size > 1000000:
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

            elif name == "write_file":
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args["content"], encoding="utf-8")
                return {"written_bytes": len(args["content"]), "path": str(p)}
            elif name == "list_dir":
                entries = []
                for item in sorted(p.iterdir()):
                    entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file",
                                    "size": item.stat().st_size if item.is_file() else None})
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
