"""
Stdio MCP Lifecycle - Server registration and lifecycle management.
"""
import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.mcp.stdio_models import StdioMCPServer, ServerStatus
from src.services.mcp.stdio_messages import MCPProtocolError
from src.services.mcp.stdio_spawner import initialize_server
from src.tools.stdio_adapter import stdio_adapter_registry
from src.infrastructure.runtime.paths import workspace_root

logger = logging.getLogger(__name__)


class StdioMCPLifecycleMixin:
    def _get_persistence_path(self: Any, tenant_id: str) -> Path:
        """Get the persistence file path for a specific tenant."""
        tenant_root = workspace_root() / f"tenant_{tenant_id}"
        tenant_root.mkdir(parents=True, exist_ok=True)
        return tenant_root / "stdio_servers.json"

    def _save_tenant_servers(self: Any, tenant_id: str) -> None:
        """Persist the registered servers for a tenant to a JSON file."""
        servers = self._get_tenant_servers(tenant_id)
        path = self._get_persistence_path(tenant_id)
        
        data = []
        for name, server in servers.items():
            data.append({
                "name": server.name,
                "command": server.command,
                "args": server.args,
                "working_dir": server.working_dir,
                "description": server.description,
                "tenant_id": server.tenant_id,
            })
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[StdioMCP] Failed to persist servers for tenant {tenant_id}: {e}")
    async def register_server(
        self: Any,
        tenant_id: str,
        name: str,
        command: str,
        args: List[str],
        working_dir: Optional[str] = None,
        description: str = "",
    ) -> StdioMCPServer:
        servers = self._get_tenant_servers(tenant_id)
        if name in servers:
            raise ValueError(f"Server '{name}' already registered for tenant '{tenant_id}'")

        server = StdioMCPServer(
            name=name,
            command=command,
            args=args,
            working_dir=working_dir,
            description=description,
            tenant_id=tenant_id,
            status=ServerStatus.STARTING,
        )
        servers[name] = server

        try:
            await self._start_server(server)
        except Exception as e:
            server.status = ServerStatus.ERROR
            server.error_message = str(e)
            del servers[name]
            raise

        self._start_health_check_loop()
        self._save_tenant_servers(tenant_id)
        return server

    async def _start_server(self: Any, server: StdioMCPServer) -> None:
        client_info = {
            "name": "project-kernel-runtime",
            "version": "3.0.0",
            "capabilities": {"tools": {}},
        }

        try:
            protocol, server_info = await initialize_server(
                command=server.command,
                args=server.args,
                client_info=client_info,
                cwd=server.working_dir,
            )
            server.protocol = protocol
            server.status = ServerStatus.RUNNING

            tools = await protocol.list_tools()
            server.tools = tools

            self._register_mcp_tools(server)

            logger.info(
                f"[StdioMCP] Started server '{server.name}' for tenant '{server.tenant_id}' "
                f"with {len(tools)} tools"
            )

        except Exception as e:
            server.status = ServerStatus.ERROR
            server.error_message = f"Failed to start: {e}"
            if server.process and server.process.returncode is None:
                try:
                    server.process.terminate()
                except Exception:
                    pass
            raise MCPProtocolError(f"Failed to start server '{server.name}': {e}") from e

    def _register_mcp_tools(self: Any, server: StdioMCPServer) -> None:
        adapters = stdio_adapter_registry.register_adapters(
            tenant_id=server.tenant_id,
            server_name=server.name,
            tools=server.tools,
        )
        for adapter in adapters:
            stdio_adapter_registry.register_with_tool_registry(adapter)
        for tool in server.tools:
            adapter_name = f"mcp_{server.name}_{tool.name}"
            self._tool_name_to_server[adapter_name] = f"{server.tenant_id}:{server.name}"

    async def unregister_server(self: Any, tenant_id: str, name: str) -> bool:
        servers = self._get_tenant_servers(tenant_id)
        server = servers.get(name)

        if not server:
            return False

        server.status = ServerStatus.STOPPING

        if server.protocol:
            try:
                await server.protocol.close()
            except Exception as e:
                logger.warning(f"[StdioMCP] Error closing server '{name}': {e}")

        if server.process and server.process.returncode is None:
            try:
                server.process.terminate()
                await asyncio.wait_for(server.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                server.process.kill()
                await server.process.wait()
            except Exception as e:
                logger.warning(f"[StdioMCP] Error terminating server '{name}': {e}")

        self._unregister_mcp_tools(server)

        del servers[name]
        logger.info(f"[StdioMCP] Stopped server '{name}' for tenant '{tenant_id}'")

        if not servers and tenant_id in self._tenant_servers:
            del self._tenant_servers[tenant_id]

        self._save_tenant_servers(tenant_id)
        return True

    def _unregister_mcp_tools(self: Any, server: StdioMCPServer) -> None:
        for tool in server.tools:
            adapter_name = f"mcp_{server.name}_{tool.name}"
            stdio_adapter_registry.unregister_from_tool_registry(adapter_name)
        stdio_adapter_registry.unregister_adapters(server.tenant_id, server.name)
        for tool in server.tools:
            adapter_name = f"mcp_{server.name}_{tool.name}"
            self._tool_name_to_server.pop(adapter_name, None)

    async def restore_persisted_servers(self: Any) -> None:
        """Restore all persisted servers across all tenants on boot."""
        root = workspace_root()
        for tenant_dir in root.glob("tenant_*"):
            if not tenant_dir.is_dir():
                continue
                
            tenant_id = tenant_dir.name.replace("tenant_", "")
            path = tenant_dir / "stdio_servers.json"
            
            if not path.exists():
                continue
                
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                for srv in data:
                    try:
                        # Register handles the start automatically
                        await self.register_server(
                            tenant_id=srv.get("tenant_id", tenant_id),
                            name=srv["name"],
                            command=srv["command"],
                            args=srv["args"],
                            working_dir=srv.get("working_dir"),
                            description=srv.get("description", "")
                        )
                        logger.info(f"[StdioMCP] Successfully restored server '{srv['name']}'")
                    except Exception as e:
                        logger.error(f"[StdioMCP] Failed to restore server '{srv['name']}': {e}")
            except Exception as e:
                logger.error(f"[StdioMCP] Failed to load persistence file for {tenant_id}: {e}")
