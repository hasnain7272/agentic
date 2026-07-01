"""Database query tool with safety controls."""
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter


class DatabaseQueryTool(BaseTool):
    """Execute read-only database queries."""
    name = "database_query"
    description = "Execute safe read-only SQL queries against configured databases"
    parameters = [
        ToolParameter(name="connection_id", type="string", description="Pre-configured connection ID"),
        ToolParameter(name="query", type="string", description="SELECT query only"),
        ToolParameter(name="limit", type="integer", description="Max rows to return", default=100),
    ]
    requires_sandbox = True

    # Block write operations
    BLOCKED_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXECUTE', 'MERGE', 'UPSERT'
    ]

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        connection_id = kwargs.get("connection_id")
        query = kwargs.get("query", "").strip()
        limit = kwargs.get("limit", 100)

        # Safety: Only SELECT allowed
        query_upper = query.upper()
        for keyword in self.BLOCKED_KEYWORDS:
            if keyword in query_upper:
                return {
                    "success": False,
                    "error": f"Write operations blocked. Use database_migrate tool for {keyword}",
                    "blocked_keyword": keyword,
                }

        if not query.upper().startswith("SELECT"):
            return {
                "success": False,
                "error": "Only SELECT queries allowed",
            }

        # Add LIMIT if not present
        if "LIMIT" not in query_upper:
            query = f"{query} LIMIT {limit}"

        # Execute via sandbox
        from src.infrastructure.sandbox.kubernetes import get_sandbox_executor
        executor = await get_sandbox_executor()

        # Use connection from secure store
        command = f"""psql "$(cat /secrets/{connection_id})" -c "{query}" --csv 2>&1"""

        result = await executor.execute(command=command)

        return {
            "success": result.exit_code == 0,
            "connection_id": connection_id,
            "query": query,
            "results": result.stdout if result.exit_code == 0 else None,
            "error": result.stderr if result.exit_code != 0 else None,
            "row_count": len(result.stdout.splitlines()) - 1 if result.exit_code == 0 else 0,
        }
