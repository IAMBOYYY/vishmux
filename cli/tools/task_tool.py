#!/usr/bin/env python3
"""
VISHMUX TaskTool – schedule recurring AI tasks stored in Supabase.
"""
import re
import httpx
from typing import Dict, Any


class TaskTool:
    """Manages scheduled tasks via Supabase REST API."""

    def __init__(self, config):
        self.config = config

    def is_configured(self) -> bool:
        """True if Supabase URL and key are both set."""
        return self.config.is_supabase_configured()

    def _headers(self) -> dict:
        """Build request headers for Supabase REST API."""
        key = self.config.data["supabase"]["key"]
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _base_url(self) -> str:
        """Return the base URL for the tasks table."""
        url = self.config.data["supabase"]["url"].rstrip("/")
        return f"{url}/rest/v1/tasks"

    async def create_task(self, user_tg_id: str, task_type: str,
                           task_query: str, schedule: str) -> Dict[str, Any]:
        """Create a new task row."""
        # Input validation
        if not user_tg_id:
            return {"success": False, "error": "Telegram Chat ID required. Run /tg setup first."}
        if not task_type:
            return {"success": False, "error": "task_type is required"}
        if not task_query:
            return {"success": False, "error": "task_query is required"}
        if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', schedule):
            return {"success": False, "error": "schedule must be in HH:MM 24-hour format, e.g. 20:00"}

        payload = {
            "user_tg_id": user_tg_id,
            "task_type": task_type,
            "task_query": task_query,
            "schedule": schedule,
            "is_active": True,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._base_url(),
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code >= 400:
                    error_detail = resp.text
                    return {"success": False, "error": f"Server error {resp.status_code}: {error_detail}"}
                data = resp.json()
                # Supabase with Prefer: return=representation returns array
                task_row = data[0] if isinstance(data, list) else data
                return {"success": True, "task": task_row}
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out. Check your Supabase URL."}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_tasks(self, user_tg_id: str = None) -> Dict[str, Any]:
        """List tasks, optionally filtered by user."""
        params = "?order=created_at.desc"
        if user_tg_id:
            params += f"&user_tg_id=eq.{user_tg_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url()}{params}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                tasks = resp.json()
                return {"success": True, "tasks": tasks}
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out."}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task by ID."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{self._base_url()}?id=eq.{task_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return {"success": True}
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out."}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_connection(self) -> str:
        """Verify the Supabase connection by fetching one row."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url()}?limit=1",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                count = len(data)
                return f"✅ Supabase connected — {count} task(s) found"
        except httpx.TimeoutException:
            return "❌ Connection failed: Request timed out."
        except httpx.HTTPStatusError as e:
            return f"❌ Connection failed: HTTP {e.response.status_code}"
        except Exception as e:
            return f"❌ Connection failed: {e}"
