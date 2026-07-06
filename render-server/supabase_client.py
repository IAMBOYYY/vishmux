import httpx
import config
from datetime import datetime, timezone as dt_timezone

def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

async def get_active_tasks() -> list:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/tasks?is_active=eq.true"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[supabase] get_active_tasks failed: {e}")
        return []

async def update_next_run(task_id: str, next_run_at_iso: str) -> None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/tasks?id=eq.{task_id}"
        payload = {"next_run_at": next_run_at_iso}
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.patch(url, headers=_headers(), json=payload)
    except Exception as e:
        print(f"[supabase] update_next_run failed for task {task_id}: {e}")

async def update_prefetched(task_id: str, content: str) -> None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/tasks?id=eq.{task_id}"
        truncated = content[:2000]
        payload = {
            "prefetched": truncated,
            "prefetched_at": datetime.now(dt_timezone.utc).isoformat()
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.patch(url, headers=_headers(), json=payload)
    except Exception as e:
        print(f"[supabase] update_prefetched failed for task {task_id}: {e}")