"""
Fetches the active AI provider config from Supabase's ai_config table
(pushed there by the CLI's render_sync.py), with a short in-memory cache
and a safe fallback to the static env-var config if Supabase has nothing
yet, is unreachable, or isn't configured at all.
"""
import time
import httpx
import config

_cache = {"data": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 60


def _fallback() -> dict:
    return {
        "api_key": config.AI_API_KEY,
        "base_url": config.AI_BASE_URL,
        "model": config.AI_MODEL,
        "mode": "hybrid",
    }


async def get_ai_settings() -> dict:
    """Returns {"api_key": ..., "base_url": ..., "model": ..., "mode": ...}, preferring
    Supabase's ai_config row if present and fetchable, else the static
    env-var defaults. Cached for _CACHE_TTL_SECONDS to avoid hitting
    Supabase on every single message."""
    now = time.time()
    if _cache["data"] is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["data"]

    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        return _fallback()

    try:
        url = f"{config.SUPABASE_URL}/rest/v1/ai_config?id=eq.1"
        headers = {
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_KEY}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            rows = resp.json()

        if not rows:
            settings = _fallback()
        else:
            row = rows[0]
            settings = {
                "api_key": row.get("api_key") or config.AI_API_KEY,
                "base_url": row.get("base_url") or config.AI_BASE_URL,
                "model": row.get("model") or config.AI_MODEL,
                "mode": row.get("mode") or "hybrid",
            }

        _cache["data"] = settings
        _cache["fetched_at"] = now
        return settings
    except Exception as e:
        print(f"[ai_settings] Failed to fetch ai_config, using env-var fallback: {e}")
        return _fallback()