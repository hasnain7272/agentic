"""API testing tool with validation."""
import json
from typing import Any, Dict

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class APITestTool(BaseTool):
    """Generate and execute API tests."""
    name = "api_test"
    description = "Test API endpoints with generated requests and validations"
    parameters = [
        ToolParameter(name="endpoint", type="string", description="Full URL to test"),
        ToolParameter(name="method", type="string", description="HTTP method", default="GET"),
        ToolParameter(name="headers", type="object", description="Request headers", required=False),
        ToolParameter(name="body", type="string", description="Request body", required=False),
        ToolParameter(name="expected_status", type="integer", description="Expected status code", default=200),
    ]
    requires_sandbox = True

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        endpoint = kwargs.get("endpoint")
        method = kwargs.get("method", "GET").upper()
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        expected_status = kwargs.get("expected_status", 200)

        # Build curl command
        header_args = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
        body_arg = f'-d "{body}"' if body else ""

        executor = await get_sandbox_executor()
        command = f"curl -s -w '\\nHTTP_CODE:%{{http_code}}' -X {method} {header_args} {body_arg} '{endpoint}'"

        result = await executor.execute(command=command)

        # Parse response
        response_body = ""
        actual_status = 0

        if "HTTP_CODE:" in result.stdout:
            parts = result.stdout.split("HTTP_CODE:")
            response_body = parts[0].strip()
            actual_status = int(parts[1].strip())

        passed = actual_status == expected_status

        return {
            "success": passed and result.exit_code == 0,
            "endpoint": endpoint,
            "method": method,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "passed": passed,
            "response_body": response_body[:5000],
            "error": result.stderr if result.exit_code != 0 else None,
        }
