#!/usr/bin/env python3
"""
VISHMUX WebSearchTool – query the web via Tavily, Brave, or DuckDuckGo.
"""

from typing import Optional
import httpx


class WebSearchTool:
    """Searches the web using the configured provider."""

    def __init__(self, config):
        self.config = config
        self.provider = config.data.get("web_search_provider", "").strip().lower()
        self.api_key = config.data.get("web_search_key", "").strip()

    def is_configured(self) -> bool:
        """Return True if a provider is ready to use."""
        if self.provider == "duckduckgo":
            return True
        return bool(self.api_key and self.provider in ("tavily", "brave"))

    async def search(self, query: str) -> str:
        """Perform a search and return formatted results."""
        if not query.strip():
            return "No search query provided."

        try:
            if self.provider == "tavily":
                return await self._search_tavily(query)
            elif self.provider == "brave":
                return await self._search_brave(query)
            elif self.provider == "duckduckgo":
                return await self._search_duckduckgo(query)
            else:
                return f"Unknown search provider: {self.provider}"
        except Exception as e:
            return f"Search failed: {e}. Try a different query."

    async def _search_tavily(self, query: str) -> str:
        """Search using Tavily API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            return self._format_results(query, results, "title", "url", "content")

    async def _search_brave(self, query: str) -> str:
        """Search using Brave Search API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("web", {}).get("results", [])
            return self._format_results(query, results, "title", "url", "description")

    async def _search_duckduckgo(self, query: str) -> str:
        """Search using DuckDuckGo Instant Answer API (limited, no key)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            resp.raise_for_status()
            data = resp.json()
            abstract = data.get("AbstractText", "")
            related = data.get("RelatedTopics", [])
            lines = [f"## Search Results for: {query}\n"]
            if abstract:
                lines.append(f"**Instant Answer:**\n{abstract}\n")
            else:
                lines.append("*No instant answer available. Results are limited with DuckDuckGo.*\n")
            for i, topic in enumerate(related[:5], 1):
                text = topic.get("Text", "")
                url = topic.get("FirstURL", "")
                lines.append(f"{i}. **{text}**\n   {url}\n")
            return "\n".join(lines)

    def _format_results(self, query: str, results: list, title_key: str, url_key: str, snippet_key: str) -> str:
        """Format search results into a markdown string."""
        lines = [f"## Search Results for: {query}\n"]
        if not results:
            lines.append("No results found.")
            return "\n".join(lines)
        for i, item in enumerate(results, 1):
            title = item.get(title_key, "Untitled")
            url = item.get(url_key, "")
            snippet = item.get(snippet_key, "").strip()
            lines.append(f"{i}. **{title}**\n   {url}\n   {snippet[:200]}\n")
        return "\n".join(lines)
