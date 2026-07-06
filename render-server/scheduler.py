from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import config
from supabase_client import get_active_tasks, update_next_run, update_prefetched
from search_client import search
from ai_client import generate_answer
from telegram_sender import send_message

def compute_next_occurrence(schedule_hhmm: str, tz_name: str, now_utc: datetime) -> datetime:
    """
    Given a "HH:MM" string and an IANA timezone name, return the next UTC
    datetime at or after now_utc when that local time next occurs
    (today if it hasn't passed yet in that timezone, otherwise tomorrow).
    Falls back to UTC and 00:00 on errors.
    """
    # Parse schedule
    try:
        parts = schedule_hhmm.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        hour = int(parts[0])
        minute = int(parts[1])
    except Exception:
        hour, minute = 0, 0

    # Get timezone object, fallback to UTC
    try:
        tz = ZoneInfo(tz_name) if tz_name else dt_timezone.utc
    except (ZoneInfoNotFoundError, KeyError):
        tz = dt_timezone.utc

    # Convert now_utc to target timezone
    now_tz = now_utc.astimezone(tz)
    # Build candidate today at the given time
    candidate = now_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # If candidate is in the past (or exactly now), move to tomorrow
    if candidate <= now_tz:
        candidate += timedelta(days=1)
    # Convert back to UTC
    return candidate.astimezone(dt_timezone.utc)

async def run_check_cycle() -> None:
    now_utc = datetime.now(dt_timezone.utc)
    tasks = await get_active_tasks()
    print(f"[scheduler] Checking {len(tasks)} active task(s) at {now_utc.isoformat()}")
    for task in tasks:
        try:
            await _process_task(task, now_utc)
        except Exception as e:
            task_id = task.get("id", "?")
            print(f"[scheduler] Error processing task {task_id}: {e}")

async def _process_task(task: dict, now_utc: datetime) -> None:
    task_id = task.get("id", "?")
    schedule = task.get("schedule", "00:00")
    tz_name = task.get("timezone") or "UTC"
    next_run_str = task.get("next_run_at")

    try:
        # If next_run_at missing: initialize it
        if not next_run_str:
            next_utc = compute_next_occurrence(schedule, tz_name, now_utc)
            await update_next_run(task_id, next_utc.isoformat())
            return

        # Parse next_run_at string
        cleaned = next_run_str.replace("Z", "+00:00")
        try:
            next_run_at = datetime.fromisoformat(cleaned)
            if next_run_at.tzinfo is None:
                next_run_at = next_run_at.replace(tzinfo=dt_timezone.utc)
        except Exception:
            # Fallback: recompute
            next_utc = compute_next_occurrence(schedule, tz_name, now_utc)
            await update_next_run(task_id, next_utc.isoformat())
            return

        # Ensure both are UTC-aware for comparison
        if next_run_at.tzinfo is None:
            next_run_at = next_run_at.replace(tzinfo=dt_timezone.utc)

        # Not due yet
        if now_utc < next_run_at:
            return

        # Too late (missed window)?
        tolerance_limit = next_run_at + timedelta(minutes=config.TOLERANCE_MINUTES)
        if now_utc > tolerance_limit:
            new_next = compute_next_occurrence(schedule, tz_name, now_utc)
            await update_next_run(task_id, new_next.isoformat())
            print(f"[scheduler] Task {task_id} missed its window — rescheduled to {new_next.isoformat()}")
            return

        # Due now — deliver
        print(f"[scheduler] Delivering task {task_id}: {task['task_query']}")
        # Wrap search in try/except just in case
        try:
            search_context = await search(task.get("task_query", ""))
        except Exception:
            search_context = ""
        answer = await generate_answer(task["task_query"], search_context)
        sent = await send_message(task["user_tg_id"], answer)
        if not sent:
            print(f"[scheduler] Failed to deliver task {task_id} via Telegram")

        # Advance to tomorrow's occurrence
        tomorrow = next_run_at + timedelta(days=1)
        await update_next_run(task_id, tomorrow.isoformat())
        await update_prefetched(task_id, answer)

    except Exception as e:
        print(f"[scheduler] Error processing task {task_id}: {e}")