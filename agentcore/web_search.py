"""
AgentCore Web Search - Multi-provider Search Tool

Provides web search via DuckDuckGo (default), Brave, or Serper.
Integrates with the AgentCore tool registry.
"""
import logging
from typing import Any, Dict, List, Optional

from agentcore.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# SEARCH PROVIDERS
# =============================================================================

async def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using DuckDuckGo (no API key needed)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results
        ]
    except ImportError:
        logger.error("duckduckgo_search not installed")
        return []
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []


async def search_brave(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using Brave Search API."""
    import httpx

    api_key = settings.search_brave_api_key
    if not api_key:
        return [{"title": "Error", "url": "", "snippet": "Brave API key not configured"}]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])[:max_results]
        ]
    except Exception as e:
        logger.error(f"Brave search error: {e}")
        return []


async def search_serper(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using Serper.dev API (Google results)."""
    import httpx

    api_key = settings.search_serper_api_key
    if not api_key:
        return [{"title": "Error", "url": "", "snippet": "Serper API key not configured"}]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": max_results},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in data.get("organic", [])[:max_results]
        ]
    except Exception as e:
        logger.error(f"Serper search error: {e}")
        return []


# =============================================================================
# UNIFIED SEARCH INTERFACE
# =============================================================================

_PROVIDERS = {
    "duckduckgo": search_duckduckgo,
    "brave": search_brave,
    "serper": search_serper,
}

_cache: Dict[str, List[Dict[str, str]]] = {}


async def web_search(
    query: str,
    max_results: int = 5,
    provider: Optional[str] = None,
) -> str:
    """
    Perform a web search and return formatted results.

    Args:
        query: Search query string
        max_results: Maximum results to return
        provider: Override provider (duckduckgo, brave, serper)

    Returns:
        Formatted search results string
    """
    if not query:
        return "Error: no query provided."

    if not settings.search_enabled:
        return "Web search is disabled in configuration."

    # Check cache
    cache_key = f"{provider or settings.search_provider}:{query}:{max_results}"
    if cache_key in _cache:
        results = _cache[cache_key]
    else:
        # Select provider
        provider_name = provider or settings.search_provider
        search_fn = _PROVIDERS.get(provider_name, search_duckduckgo)
        results = await search_fn(query, max_results)

        # Cache results
        if results:
            _cache[cache_key] = results
            # Evict old cache entries if too many
            if len(_cache) > 100:
                oldest = next(iter(_cache))
                del _cache[oldest]

    if not results:
        return f"No results found for: {query}"

    # Format results
    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"{i}. **{r['title']}**\n"
            f"   URL: {r['url']}\n"
            f"   {r['snippet']}"
        )

    return f"Web Search Results for '{query}':\n\n" + "\n\n".join(formatted)


# =============================================================================
# TOOL REGISTRATION HELPER
# =============================================================================

def register_web_search_tool(registry):
    """Register web_search as a tool in the AgentCore tool registry."""
    from agentcore.tools import ToolSchema, ToolParameter, ToolResult

    schema = ToolSchema(
        name="web_search",
        description="Search the web for current information, documentation, or news.",
        category="knowledge",
        parameters=[
            ToolParameter(name="query", type="string", description="The search query"),
            ToolParameter(
                name="max_results", type="integer",
                description="Max results (default 5)", required=False, default=5,
            ),
        ],
    )

    async def handler(session_id: str = "", **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        max_results = int(kwargs.get("max_results", 5))
        result_text = await web_search(query, max_results)
        return ToolResult(success=True, data=result_text)

    registry.register_handler("web_search", schema, handler)
