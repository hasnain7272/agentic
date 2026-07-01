"""Registry for stdio MCP tool adapters."""
import logging
from typing import Any, Dict, List, Optional

from src.services.mcp.stdio_protocol import ToolManifest
from src.tools.stdio_adapter import StdioMCPToolAdapter

logger = logging.getLogger(__name__)


class StdioMCPAdapterRegistry:
    """Tracks adapters per tenant and mirrors them into the tool registry."""

    _instance: Optional["StdioMCPAdapterRegistry"] = None

    def __new__(cls) -> "StdioMCPAdapterRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._adapters: Dict[str, Dict[str, StdioMCPToolAdapter]] = {}

    def _get_tenant_adapters(self, tenant_id: str) -> Dict[str, StdioMCPToolAdapter]:
        if tenant_id not in self._adapters:
            self._adapters[tenant_id] = {}
        return self._adapters[tenant_id]

    def register_adapters(self, tenant_id: str, server_name: str, tools: List[ToolManifest]) -> List[StdioMCPToolAdapter]:
        adapters = self._get_tenant_adapters(tenant_id)
        created = []
        for tool in tools:
            adapter_name = f"mcp_{server_name}_{tool.name}"
            if adapter_name in adapters:
                continue
            adapters[adapter_name] = StdioMCPToolAdapter(server_name, tenant_id, tool)
            created.append(adapters[adapter_name])
            logger.info("[StdioMCPAdapterRegistry] Registered adapter '%s'", adapter_name)
        return created

    def unregister_adapters(self, tenant_id: str, server_name: str) -> int:
        adapters = self._get_tenant_adapters(tenant_id)
        names = [name for name in adapters if name.startswith(f"mcp_{server_name}_")]
        for name in names:
            del adapters[name]
        return len(names)

    def get_adapter(self, tenant_id: str, adapter_name: str) -> Optional[StdioMCPToolAdapter]:
        return self._get_tenant_adapters(tenant_id).get(adapter_name)

    def list_adapters(self, tenant_id: str) -> List[Dict[str, Any]]:
        return [adapter.get_adapter_info() for adapter in self._get_tenant_adapters(tenant_id).values()]

    def register_with_tool_registry(self, adapter: StdioMCPToolAdapter) -> None:
        from src.tools.registry import _tool_instances

        if adapter.name not in _tool_instances:
            _tool_instances[adapter.name] = adapter
            logger.info("[StdioMCPAdapterRegistry] Added '%s' to tool registry", adapter.name)

    def unregister_from_tool_registry(self, adapter_name: str) -> None:
        from src.tools.registry import _tool_instances

        if adapter_name in _tool_instances:
            del _tool_instances[adapter_name]
            logger.info("[StdioMCPAdapterRegistry] Removed '%s' from tool registry", adapter_name)


stdio_adapter_registry = StdioMCPAdapterRegistry()
