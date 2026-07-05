"""Web Search MCP — Search the web using DuckDuckGo HTML scraping (no API keys required)."""
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from agentcore.mcps import register_mcp


@register_mcp
class WebSearchMCP:
    name = "web-search-mcp"
    description = "Search the web for queries using DuckDuckGo"
    TOOLS = {
        "search_web": {"params": {"query": "string"}, "desc": "Perform web search and return title, URL, snippets"},
    }

    async def call_tool(self, name: str, args: dict) -> dict:
        if name == "search_web":
            query = args["query"]
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read()
                soup = BeautifulSoup(html, "html.parser")
                results = []
                for a in soup.find_all("a", class_="result__snippet")[:8]:
                    parent = a.parent.parent
                    title_a = parent.find("a", class_="result__url")
                    if title_a:
                        results.append({
                            "title": title_a.get_text().strip(),
                            "url": title_a.get("href").strip(),
                            "snippet": a.get_text().strip()
                        })
                return {"results": results}
            except Exception as e:
                return {"error": str(e), "results": []}
        raise ValueError(f"Unknown tool: {name}")
