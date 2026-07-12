#!/usr/bin/env python3
"""
VISHMUX Render Sync – pushes the CLI's Telegram AI provider/key to Supabase's
ai_config table so the Render companion server automatically uses the same
provider, with no manual Render dashboard edits needed.
"""
import httpx

# Only these providers speak the OpenAI-compatible chat/completions format
# that Render's ai_client.py knows how to call. gemini and anthropic use a
# different request/response shape entirely, so they're intentionally
# excluded — if the active provider is one of those, we skip syncing and
# leave Render's ai_config value (or its env-var default) untouched.
PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "together": "https://api.together.xyz/v1",
    "mistral": "https://api.mistral.ai/v1",
    "perplexity": "https://api.perplexity.ai",
}


async def sync_ai_config_to_render(config) -> None:
    """
    Push the Telegram provider's key/base_url/model to Supabase's ai_config
    table (upsert, single row id=1). Always fails safe — never raises,
    silently no-ops if Supabase isn't configured, no Telegram provider is
    set (falls back to interactive provider), or it isn't OpenAI-compatible.
    """
    try:
        if not config.is_supabase_configured():
            return

        active = config.get_telegram_provider()
        if not active:
            return

        provider_name, model = active
        if provider_name not in PROVIDER_BASE_URLS:
            print(f"[render_sync] '{provider_name}' isn't OpenAI-compatible — Render keeps its current provider.")
            return

        api_key = config.data["providers"][provider_name]["api_key"]
        if not api_key:
            return

        supabase_url = config.data["supabase"]["url"].rstrip("/")
        supabase_key = config.data["supabase"]["key"]

        url = f"{supabase_url}/rest/v1/ai_config"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        payload = {
            "id": 1,
            "provider": provider_name,
            "api_key": api_key,
            "base_url": PROVIDER_BASE_URLS[provider_name],
            "model": model,
            "mode": config.get_telegram_mode(),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()

        print(f"[render_sync] Synced '{provider_name}' / {model} to Render (mode: {config.get_telegram_mode()}).")
    except Exception as e:
        print(f"[render_sync] Sync failed (non-fatal, Render keeps its last config): {e}")