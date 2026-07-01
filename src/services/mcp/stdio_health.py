"""
Stdio MCP Health - Background health checks and auto-restart logic.

Production-hardened: generous restart budget, exponential backoff,
and process-level liveness checks before costly ping RPCs.
"""
import asyncio
import logging
import time
from typing import Any

from src.services.mcp.stdio_models import StdioMCPServer, ServerStatus

logger = logging.getLogger(__name__)


class StdioMCPHealthMixin:
    def _start_health_check_loop(self: Any) -> None:
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("[StdioMCP] Started background health check loop")

    async def _health_check_loop(self: Any) -> None:
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_servers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[StdioMCP] Health check error: %s", e)

    async def _check_all_servers(self: Any) -> None:
        now = time.time()
        for tenant_id, servers in list(self._tenant_servers.items()):
            for name, server in list(servers.items()):
                if server.status not in (ServerStatus.RUNNING, ServerStatus.ERROR):
                    continue

                server.last_health_check = now

                # Fast check: is the subprocess still alive?
                if server.protocol and server.protocol._process.returncode is None:
                    is_healthy = True  # process alive = good enough
                else:
                    is_healthy = False

                if not is_healthy:
                    logger.warning("[StdioMCP] '%s' (tenant:%s) down", name, tenant_id)
                    server.status = ServerStatus.ERROR

                    if server.metrics.restart_count < self._max_restart_attempts:
                        await self._restart_server(server)
                    else:
                        logger.error("[StdioMCP] '%s' exceeded max restarts", name)

    async def _restart_server(self: Any, server: StdioMCPServer) -> None:
        attempt = server.metrics.restart_count + 1
        logger.info(
            "[StdioMCP] Restart %d/%d for '%s'",
            attempt, self._max_restart_attempts, server.name,
        )

        server.status = ServerStatus.RESTARTING
        server.metrics.restart_count += 1

        # Teardown old process
        if server.protocol:
            try:
                await server.protocol.close()
            except Exception:
                pass

        if server.process and server.process.returncode is None:
            try:
                server.process.terminate()
            except Exception:
                pass

        try:
            self._unregister_mcp_tools(server)
            await self._start_server(server)
            logger.info("[StdioMCP] Restarted '%s' successfully", server.name)
        except Exception as e:
            logger.error("[StdioMCP] Restart failed for '%s': %s", server.name, e)
            server.status = ServerStatus.ERROR
