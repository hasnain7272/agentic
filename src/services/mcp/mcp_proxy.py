"""
MCP Proxy Tool

Wraps external HTTP endpoints as local tools with:
- Circuit breaker pattern for fault tolerance
- Rate limiting enforcement
- Request sanitization and validation
- Comprehensive metrics collection
"""
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from src.tools.core.base import BaseTool, ToolParameter
from src.services.mcp.mcp_models import ToolStatus, MCPToolMetrics
from src.services.mcp.mcp_capabilities import MCPConnectionConfig
from src.services.mcp.mcp_validation import sanitize_request_payload, validate_request_size
from src.services.mcp.mcp_rate_limiter import check_tool_execution_rate_limit

logger = logging.getLogger(__name__)


class MCPProxyTool(BaseTool):
    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[Dict[str, Any]],
        endpoint_url: str,
        tenant_id: str,
        config: Optional[MCPConnectionConfig] = None,
        allowed_hosts: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.tenant_id = tenant_id
        self.endpoint_url = endpoint_url
        self.config = config or MCPConnectionConfig(endpoint_url=endpoint_url)
        self.allowed_hosts = allowed_hosts
        self.status = ToolStatus.ACTIVE
        self.metrics = MCPToolMetrics()
        self._circuit_open = False
        self._circuit_opened_at: Optional[float] = None
        self._consecutive_failures = 0
        self._circuit_break_threshold = 5
        self._circuit_recovery_timeout = 60.0

        self.parameters = []
        for p in parameters:
            self.parameters.append(
                ToolParameter(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                )
            )
        self.requires_sandbox = False

    def _check_circuit_breaker(self) -> bool:
        if self._circuit_open:
            if time.time() - self._circuit_opened_at > self._circuit_recovery_timeout:
                logger.info(f"[MCP] Circuit breaker reset for {self.name}")
                self._circuit_open = False
                self._consecutive_failures = 0
                return True
            return False
        return True

    def _trip_circuit_breaker(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_break_threshold:
            self._circuit_open = True
            self._circuit_opened_at = time.time()
            logger.warning(f"[MCP] Circuit breaker tripped for {self.name}")

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        if not self._check_circuit_breaker():
            return {"error": "Service temporarily unavailable (circuit open)", "tool": self.name}

        allowed, wait_time = check_tool_execution_rate_limit(self.name)
        if not allowed:
            self.status = ToolStatus.RATE_LIMITED
            return {"error": f"Rate limited, retry after {wait_time}s", "tool": self.name}

        start_time = time.time()
        sanitized_args = sanitize_request_payload(kwargs)

        if not validate_request_size({"session_id": session_id, "args": sanitized_args}):
            return {"error": "Request payload too large", "tool": self.name}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                verify=self.config.verify_ssl,
            ) as client:
                response = await client.post(
                    self.endpoint_url,
                    json={"session_id": session_id, "args": sanitized_args},
                )
                response.raise_for_status()
                result = response.json()
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_call(latency_ms, success=True)
                self._consecutive_failures = 0
                self.status = ToolStatus.ACTIVE
                return result

        except httpx.TimeoutException:
            self._trip_circuit_breaker()
            self.metrics.record_call((time.time() - start_time) * 1000, success=False)
            logger.error(f"[MCP] Timeout executing {self.name}")
            return {"error": "Request timed out", "tool": self.name}

        except httpx.HTTPStatusError as e:
            self._trip_circuit_breaker()
            self.metrics.record_call((time.time() - start_time) * 1000, success=False)
            logger.error(f"[MCP] HTTP error executing {self.name}: {e.response.status_code}")
            return {"error": f"HTTP {e.response.status_code}", "tool": self.name}

        except Exception as e:
            self._trip_circuit_breaker()
            self.metrics.record_call((time.time() - start_time) * 1000, success=False)
            logger.error(f"[MCP] Execution failed for {self.name}: {e}")
            return {"error": str(e), "tool": self.name}

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            **self.metrics.get_metrics(),
        }