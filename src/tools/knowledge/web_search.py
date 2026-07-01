from typing import Any
from src.tools.core.base import BaseTool, ToolParameter

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Perform a genuine web search to find current information, documentation, or news using DuckDuckGo."
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="The search query."
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of results to return (integer, default 5).",
            required=False
        )
    ]

    async def execute(self, session_id: str, **kwargs) -> Any:
        query = kwargs.get("query", "")
        max_results = int(kwargs.get("max_results", 5))

        if not query:
            return "Error: no query provided."

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return "No results found for this query."

            formatted = []
            for r in results:
                formatted.append(f"Title: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}\n")

            return "Web Search Results:\n\n" + "\n".join(formatted)
        except ImportError:
            return "Error: duckduckgo_search library is not installed."
        except Exception as e:
            return f"Web search failed: {str(e)}"
