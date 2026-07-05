"""Web Fetch MCP — Fetch content from any public URL and convert to Markdown/Text."""
import urllib.request
import urllib.error
import re
from bs4 import BeautifulSoup
from agentcore.mcps import register_mcp


@register_mcp
class WebFetchMCP:
    name = "web-fetch-mcp"
    description = "Fetch, download, and extract text/markdown content from a URL"
    TOOLS = {
        "fetch_url": {"params": {"url": "string"}, "desc": "Fetch raw HTML/text from a URL"},
        "extract_text": {"params": {"html_content": "string"}, "desc": "Clean HTML and extract main text content"},
    }

    async def call_tool(self, name: str, args: dict) -> dict:
        if name == "fetch_url":
            url = args["url"]
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    return {"content": body[:200000], "truncated": len(body) > 200000}
            except Exception as e:
                return {"error": str(e), "success": False}
        elif name == "extract_text":
            soup = BeautifulSoup(args["html_content"], "html.parser")
            # Remove scripts and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()
            text = soup.get_text()
            # break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # drop blank lines
            cleaned_text = "\n".join(chunk for chunk in chunks if chunk)
            return {"text": cleaned_text[:10000]}
        raise ValueError(f"Unknown tool: {name}")
