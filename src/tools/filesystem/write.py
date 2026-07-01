"""Write file tool with path validation."""
import os
from typing import Any, Dict

import aiofiles

from src.domain.exceptions import ToolExecutionError
from src.infrastructure.runtime.paths import resolve_workspace_path
from src.infrastructure.security.path_validation import sanitize_path
from src.tools.core.base import BaseTool, ToolParameter


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file, overwriting if exists."
    parameters = [
        ToolParameter(name="filepath", type="string", description="Path to the file"),
        ToolParameter(name="content", type="string", description="Content to write"),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, filepath: str, content: str, **kwargs) -> Dict[str, Any]:
        try:
            # Resolve path with strict session isolation
            resolved_path = resolve_workspace_path(filepath, session_id=session_id, tenant_id=kwargs.get("tenant_id", "local"))
            
            # Ensure parent directory exists
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(resolved_path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            return {
                "success": True,
                "filepath": filepath,
                "bytes_written": len(content.encode("utf-8")),
            }
        except Exception as exc:
            raise ToolExecutionError(str(exc), self.name) from exc