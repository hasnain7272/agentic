"""Archival Memory Retrieval Tool."""
from typing import Any, Dict
from src.tools.core.base import BaseTool, ToolParameter
from src.services.memory.semantic_memory import semantic_memory

class SearchArchivalMemoryTool(BaseTool):
    name = "search_past_decisions"
    description = "Search the agent's long-term semantic memory for past decisions, code implementations, or context. Use this when you are confused about how something was done previously."
    parameters = [
        ToolParameter(name="query", type="string", description="The search query or concept to look for."),
        ToolParameter(name="max_results", type="integer", description="Maximum number of results to return.", required=False, default=5),
    ]
    requires_sandbox = False

    async def execute(self, session_id: str, query: str, **kwargs) -> Dict[str, Any]:
        tenant_id = kwargs.get("tenant_id", "local")
        max_results = kwargs.get("max_results", 5)
        
        results = await semantic_memory.query_memory(
            session_id=session_id,
            tenant_id=tenant_id,
            query_text=query,
            n_results=max_results
        )
        
        if not results:
            return {"success": True, "message": "No relevant past memory found."}
            
        return {
            "success": True,
            "results": results
        }
