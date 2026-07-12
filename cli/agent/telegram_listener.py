#!/usr/bin/env python3
"""
Background Telegram message listener for VISHMUX.
Polls Supabase incoming_messages, claims, answers via local provider,
sends reply via Telegram, then deletes the row. Runs in a daemon thread.
"""
import time
import threading
import asyncio
import json
from datetime import datetime, timezone as dt_timezone

import httpx

from ..config import Config
from ..providers import get_provider
from .web_search import WebSearchTool
from .telegram_tool import TelegramTool
from .agent_tools import TOOL_SCHEMAS, execute_tool
from .manager import ToolManager

LOCAL_IDENTITY_PROMPT = (
    "You are VISHMUX, answering a Telegram message directly from the user's own device, "
    "using their own configured provider. You have full context that this is the user's real "
    "local agent, not a remote fallback. Be direct, concise, telegram-friendly: plain text, "
    "occasional *bold*, no markdown headers."
)

TELEGRAM_SAFE_TOOLS = [
    t for t in TOOL_SCHEMAS
    if t["function"]["name"] not in ("run_command", "run_background_command")
]

LOCAL_IDENTITY_PROMPT_WITH_TOOLS = (
    "You are VISHMUX, answering a Telegram message directly from the user's own device, "
    "using their own configured provider. You have full context that this is the user's real "
    "local agent, not a remote fallback. You CAN create real files here using your tools "
    "(write_file, create_project_folder, etc.) — if asked to build something like a website "
    "or script, actually create the files in a project folder rather than just describing them "
    "in text. For any files you create, ensure it's real, working code with proper design — "
    "CSS if it's a website, no lorem-ipsum placeholder content. Be direct and concise in your "
    "final text reply — telegram-friendly plain text, occasional *bold*, no markdown headers."
)

class _NoPromptDisplay:
    """Minimal stand-in for the interactive Display class, used only so
    execute_tool() has something to call — the restricted TELEGRAM_SAFE_TOOLS
    list means confirm_action should never actually be reached in practice."""
    def confirm_action(self, description: str) -> bool:
        return False
    def show_tool_call(self, name: str, arguments: dict) -> None:
        pass


def start_telegram_listener(config: Config) -> None:
    """Starts the background listener thread. Returns immediately (non-blocking)."""
    t = threading.Thread(target=_run_loop, args=(config,), daemon=True)
    t.start()

def _run_loop(config: Config) -> None:
    """Forever loop polling Supabase for pending incoming messages."""
    supabase_url = config.data["supabase"]["url"].rstrip("/")
    supabase_key = config.data["supabase"]["key"]
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    client = httpx.Client(timeout=15.0)

    while True:
        try:
            # If mode is render_only, skip all polling — Render always answers on its own.
            mode = config.get_telegram_mode()
            if mode == "render_only":
                time.sleep(3)
                continue

            # Fetch pending messages (oldest first)
            resp = client.get(
                f"{supabase_url}/rest/v1/incoming_messages?status=eq.pending&order=created_at.asc&limit=5",
                headers=headers
            )
            resp.raise_for_status()
            rows = resp.json()
            for row in rows:
                msg_id = row["id"]
                chat_id = row["chat_id"]
                text = row["text"]

                # Only claim if we have a Telegram provider configured (falls back to active_provider if none set explicitly)
                active = config.get_telegram_provider()
                if not active:
                    continue

                # Atomic claim
                claim_payload = {
                    "status": "claimed",
                    "claimed_by": "termux",
                    "claimed_at": datetime.now(dt_timezone.utc).isoformat()
                }
                claim_resp = client.patch(
                    f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}&status=eq.pending",
                    headers=headers,
                    json=claim_payload
                )
                if claim_resp.status_code != 200:
                    continue
                claimed_data = claim_resp.json()
                if not isinstance(claimed_data, list) or len(claimed_data) == 0:
                    # Already claimed by Render or another instance
                    continue

                # Generate answer
                try:
                    # Search if configured
                    search_context = ""
                    web_tool = WebSearchTool(config)
                    if web_tool.is_configured():
                        try:
                            search_context = asyncio.run(web_tool.search(text))
                        except Exception:
                            pass

                    # Prepare messages
                    if search_context:
                        user_msg = (
                            f'The user asked: "{text}"\n\n'
                            f"Here is fresh web search context:\n\n{search_context}\n\n"
                            f"Answer concisely, plain text, telegram style."
                        )
                    else:
                        user_msg = (
                            f'The user asked: "{text}"\n\n'
                            f"No web search available, answer from general knowledge. "
                            f"If you need real-time info you don't have, say so honestly. "
                            f"Concise, plain text, telegram style."
                        )
                    messages = [
                        {"role": "system", "content": LOCAL_IDENTITY_PROMPT_WITH_TOOLS},
                        {"role": "user", "content": user_msg}
                    ]

                    # Use local provider
                    provider_name, model = active
                    api_key = config.data["providers"][provider_name]["api_key"]
                    provider = get_provider(provider_name, api_key, model)

                    async def _generate_with_tools():
                        tool_manager = ToolManager(config)
                        fake_display = _NoPromptDisplay()
                        working_messages = list(messages)
                        max_iterations = 6

                        for iteration in range(max_iterations):
                            result = await provider.chat_with_tools(working_messages, TELEGRAM_SAFE_TOOLS)

                            if not result["success"]:
                                if iteration == 0:
                                    # Provider doesn't support tools at all (Anthropic/Gemini) —
                                    # fall back to plain chat, exactly like before this change.
                                    async for chunk in provider.chat(messages, stream=False):
                                        return chunk
                                    return ""
                                else:
                                    return f"⚠️ Couldn't finish that ({result['error']})."

                            tool_calls = result.get("tool_calls") or []
                            if not tool_calls:
                                return result.get("content") or ""

                            working_messages.append({
                                "role": "assistant",
                                "content": result.get("content"),
                                "tool_calls": [
                                    {
                                        "id": tc["id"],
                                        "type": "function",
                                        "function": {
                                            "name": tc["name"],
                                            "arguments": json.dumps(tc.get("arguments", {})),
                                        },
                                    }
                                    for tc in tool_calls
                                ],
                            })

                            for tc in tool_calls:
                                tool_output = await execute_tool(
                                    tc["name"], tc.get("arguments", {}), tool_manager, fake_display
                                )
                                working_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": tool_output,
                                })

                        return "⚠️ That task took too long — try it directly in Termux instead."

                    answer = asyncio.run(_generate_with_tools())

                    # Send via Telegram
                    telegram = TelegramTool(config)
                    # Confirm chat_id consistency (log warning if mismatch, but still send to configured)
                    configured_chat = config.data["telegram"]["chat_id"]
                    if chat_id != configured_chat:
                        print(f"[telegram_listener] Warning: incoming chat_id {chat_id} differs from configured {configured_chat}")
                    sent = asyncio.run(telegram.send_message(answer))
                    if sent:
                        # Delete message from Supabase
                        client.delete(
                            f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}",
                            headers=headers
                        )
                    else:
                        # Revert to pending
                        client.patch(
                            f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}",
                            headers=headers,
                            json={"status": "pending", "claimed_by": None, "claimed_at": None}
                        )
                        print(f"[telegram_listener] Failed to send answer for msg {msg_id}, reverted to pending")
                except Exception as e:
                    print(f"[telegram_listener] Error processing msg {msg_id}: {e}")
                    # Revert to pending so Render can pick it up
                    try:
                        client.patch(
                            f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}",
                            headers=headers,
                            json={"status": "pending", "claimed_by": None, "claimed_at": None}
                        )
                    except Exception:
                        pass
        except Exception as e:
            print(f"[telegram_listener] Poll cycle error: {e}")
        time.sleep(3)