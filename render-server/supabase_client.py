import httpx
import config
from datetime import datetime, timedelta, timezone as dt_timezone

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

async def insert_incoming_message(chat_id: str, text: str) -> None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/incoming_messages"
        payload = {"chat_id": chat_id, "text": text, "status": "pending"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
    except Exception as e:
        print(f"[supabase] insert_incoming_message failed: {e}")

async def get_claimable_messages(stale_seconds: int) -> list:
    try:
        now_utc = datetime.now(dt_timezone.utc)
        cutoff = now_utc - timedelta(seconds=stale_seconds)
        cutoff_iso = cutoff.isoformat().replace("+", "%2B")
        or_filter = f"or=(status.eq.pending,and(status.eq.claimed,claimed_at.lt.{cutoff_iso}))"
        url = f"{config.SUPABASE_URL}/rest/v1/incoming_messages?{or_filter}&order=created_at.asc&limit=10"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[supabase] get_claimable_messages failed: {e}")
        return []

async def try_claim_message(msg_id, claimer: str, expected_status: str = "pending") -> dict | None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/incoming_messages?id=eq.{msg_id}&status=eq.{expected_status}"
        payload = {"status": "claimed", "claimed_by": claimer, "claimed_at": datetime.now(dt_timezone.utc).isoformat()}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
    except Exception as e:
        print(f"[supabase] try_claim_message failed for msg {msg_id}: {e}")
        return None

async def delete_message(msg_id) -> None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/incoming_messages?id=eq.{msg_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(url, headers=_headers())
            resp.raise_for_status()
    except Exception as e:
        print(f"[supabase] delete_message failed for msg {msg_id}: {e}")

async def revert_to_pending(msg_id) -> None:
    try:
        url = f"{config.SUPABASE_URL}/rest/v1/incoming_messages?id=eq.{msg_id}"
        payload = {"status": "pending", "claimed_by": None, "claimed_at": None}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=_headers(), json=payload)
            resp.raise_for_status()
    except Exception as e:
        print(f"[supabase] revert_to_pending failed for msg {msg_id}: {e}")
