"""Read file tool with path validation."""
import os
from typing import Any, Dict

import aiofiles

from src.domain.exceptions import ToolExecutionError
from src.infrastructure.runtime.paths import resolve_workspace_path
from src.infrastructure.security.path_validation import sanitize_path
from src.tools.core.base import BaseTool, ToolParameter


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file on the local filesystem."
    parameters = [
        ToolParameter(name="filepath", type="string", description="Path to the file"),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, filepath: str, **kwargs) -> Dict[str, Any]:
        try:
            # Resolve path with strict session isolation
            resolved_path = resolve_workspace_path(filepath, session_id=session_id, tenant_id=kwargs.get("tenant_id", "local"))
            
            if not resolved_path.exists():
                return {"success": False, "error": f"File not found: {filepath}"}
            
            if not resolved_path.is_file():
                return {"success": False, "error": f"Path is a directory: {filepath}"}

            async with aiofiles.open(resolved_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            return {
                "success": True,
                "content": content,
                "lines": len(content.splitlines()),
                "filepath": filepath,
            }
        except UnicodeDecodeError:
            return {"success": False, "error": f"Binary file not supported: {filepath}"}
        except Exception as exc:
            raise ToolExecutionError(str(exc), self.name) from exc