"""BaseTool adapter for stdio MCP tools."""
import logging
from typing import Any, Dict, List

from src.services.mcp.stdio_protocol import ToolManifest
from src.tools.core.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class StdioMCPToolAdapter(BaseTool):
    """Wraps one stdio MCP tool so the agent can execute it like any BaseTool."""

    def __init__(self, server_name: str, tenant_id: str, tool_manifest: ToolManifest):
        self._server_name = server_name
        self._tenant_id = tenant_id
        self._manifest = tool_manifest
        self.name = f"mcp_{server_name}_{tool_manifest.name}"
        self.description = tool_manifest.description or f"MCP tool '{tool_manifest.name}' from server '{server_name}'"
        self.parameters = self._convert_schema(tool_manifest.input_schema)
        self.requires_sandbox = False

    def _convert_schema(self, input_schema: Dict[str, Any]) -> List[ToolParameter]:
        properties = input_schema.get("properties", {}) if input_schema else {}
        required = input_schema.get("required", []) if input_schema else []
        return [
            ToolParameter(
                name=name,
                type="string" if spec.get("type", "string") == "object" else spec.get("type", "string"),
                description=spec.get("description", ""),
                required=name in required,
            )
            for name, spec in properties.items()
        ]

    async def execute(self, session_id: str, **kwargs) -> Any:
        from src.services.mcp.stdio_manager import stdio_mcp_manager

        try:
            return await stdio_mcp_manager.execute_tool(
                tenant_id=self._tenant_id,
                server_name=self._server_name,
                tool_name=self._manifest.name,
                arguments=kwargs,
            )
        except Exception as exc:
            logger.error("[StdioMCPToolAdapter] Failed to execute '%s': %s", self._manifest.name, exc)
            return {"success": False, "error": str(exc), "tool": self._manifest.name, "server": self._server_name}

    def get_adapter_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "server_name": self._server_name,
            "tenant_id": self._tenant_id,
            "tool_name": self._manifest.name,
            "description": self.description,
            "parameters": [param.model_dump() for param in self.parameters],
        }


from src.tools.stdio_adapter_registry import stdio_adapter_registry  # noqa: E402
