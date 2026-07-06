import httpx
import config

async def search(query: str) -> str:
    try:
        if not query:
            return ""
        provider = config.WEB_SEARCH_PROVIDER
        if provider == "serper" and config.WEB_SEARCH_KEY:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": config.WEB_SEARCH_KEY, "Content-Type": "application/json"},
                    json={"q": query, "num": 5}
                )
                resp.raise_for_status()
                data = resp.json()
                organic = data.get("organic", [])
                lines = []
                for item in organic:
                    title = item.get("title", "Untitled")
                    snippet = item.get("snippet", "").strip()
                    link = item.get("link", "")
                    lines.append(f"- {title}: {snippet} ({link})")
                return "\n".join(lines)
        elif provider == "duckduckgo":
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
                )
                resp.raise_for_status()
                data = resp.json()
                abstract = data.get("AbstractText", "")
                parts = []
                if abstract:
                    parts.append(f"- {abstract}")
                related = data.get("RelatedTopics", [])
                for topic in related[:5]:
                    text = topic.get("Text", "")
                    if text:
                        parts.append(f"- {text}")
                if not parts:
                    return ""
                return "\n".join(parts)
        else:
            return ""
    except Exception as e:
        print(f"[search] search failed: {e}")
        return ""