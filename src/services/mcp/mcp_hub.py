"""
MCP (Model Context Protocol) Hub - Premium Production Grade

Central registry for MCP plugins with:
- Capability negotiation and validation
- Defense-in-depth security
- Tenant isolation
- Observability integration
"""
import logging
from typing import Any, Dict, List, Optional, Set

from src.tools.registry import _tool_instances
from src.services.mcp.mcp_capabilities import MCPServerCapabilities
from src.services.mcp.mcp_validation import validate_plugin_definition, validate_endpoint_url
from src.services.mcp.mcp_rate_limiter import check_plugin_registration_rate_limit
from src.services.mcp.mcp_proxy import MCPProxyTool
from src.services.mcp.mcp_models import ToolStatus
from src.infrastructure.observability.tracing import milestones

logger = logging.getLogger(__name__)


class MCPHub:
    """Central registry for dynamic MCP plugins with premium security."""

    def __init__(self):
        self._plugins: Dict[str, MCPProxyTool] = {}
        self._tenant_plugins: Dict[str, Set[str]] = {}

    def register_plugin(
        self,
        plugin_def: Dict[str, Any],
        tenant_id: str,
        allowed_hosts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        validation_errors = validate_plugin_definition(plugin_def)
        if validation_errors:
            raise ValueError(f"Validation failed: {'; '.join(validation_errors)}")

        allowed, wait_time = check_plugin_registration_rate_limit(tenant_id)
        if not allowed:
            raise ValueError(f"Rate limited, retry after {wait_time}s")

        name = plugin_def["name"]
        endpoint_url = plugin_def["endpoint_url"]
        description = plugin_def.get("description", "MCP Tool")
        parameters = plugin_def.get("parameters", [])

        url_errors = validate_endpoint_url(endpoint_url, allowed_hosts)
        if url_errors:
            raise ValueError(f"URL validation failed: {'; '.join(url_errors)}")

        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' already registered")

        from src.services.mcp.mcp_capabilities import MCPConnectionConfig
        config = MCPConnectionConfig(
            endpoint_url=endpoint_url,
            timeout_seconds=plugin_def.get("timeout_seconds", 30.0),
            max_retries=plugin_def.get("max_retries", 3),
            verify_ssl=plugin_def.get("verify_ssl", True),
            allowed_hosts=allowed_hosts,
        )

        proxy = MCPProxyTool(
            name=name,
            description=description,
            parameters=parameters,
            endpoint_url=endpoint_url,
            tenant_id=tenant_id,
            config=config,
            allowed_hosts=allowed_hosts,
        )

        self._plugins[name] = proxy
        if tenant_id not in self._tenant_plugins:
            self._tenant_plugins[tenant_id] = set()
        self._tenant_plugins[tenant_id].add(name)
        _tool_instances[name] = proxy

        milestones.milestone(f"MCP plugin registered: {name}", {"tenant_id": tenant_id})
        logger.info(f"[MCP Hub] Hot-loaded plugin: {name} for tenant: {tenant_id}")

        return {"name": name, "status": "registered", "tools": [name]}

    def unregister_plugin(self, name: str, tenant_id: str) -> bool:
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]
        if plugin.tenant_id != tenant_id:
            raise PermissionError("Cannot unregister plugin from different tenant")

        del self._plugins[name]
        self._tenant_plugins[tenant_id].discard(name)
        if name in _tool_instances:
            del _tool_instances[name]

        logger.info(f"[MCP Hub] Unregistered plugin: {name}")
        return True

    def list_plugins(self, tenant_id: Optional[str] = None) -> List[str]:
        if tenant_id:
            return list(self._tenant_plugins.get(tenant_id, set()))
        return list(self._plugins.keys())

    def get_plugin(self, name: str) -> Optional[MCPProxyTool]:
        return self._plugins.get(name)

    def get_plugin_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        plugin = self._plugins.get(name)
        if plugin:
            return plugin.get_metrics()
        return None

    def get_all_metrics(self) -> Dict[str, Any]:
        return {name: plugin.get_metrics() for name, plugin in self._plugins.items()}

    def validate_capabilities(self, server_capabilities: MCPServerCapabilities) -> Dict[str, Any]:
        errors = server_capabilities.validate()
        if errors:
            return {"valid": False, "errors": errors}

        existing_tools = set(self._plugins.keys())
        new_tools = server_capabilities.get_tool_names()

        conflicts = existing_tools & new_tools
        if conflicts:
            return {"valid": False, "errors": [f"Tool name conflicts: {', '.join(conflicts)}"]}

        return {"valid": True, "tool_count": len(new_tools)}


mcp_hub = MCPHub()