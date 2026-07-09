#!/usr/bin/env python3
"""
Background Telegram message listener for VISHMUX.
Polls Supabase incoming_messages, claims, answers via local provider,
sends reply via Telegram, then deletes the row. Runs in a daemon thread.
"""
import time
import threading
import asyncio
from datetime import datetime, timezone as dt_timezone

import httpx

from ..config import Config
from ..providers import get_provider
from .web_search import WebSearchTool
from .telegram_tool import TelegramTool

LOCAL_IDENTITY_PROMPT = (
    "You are VISHMUX, answering a Telegram message directly from the user's own device, "
    "using their own configured provider. You have full context that this is the user's real "
    "local agent, not a remote fallback. Be direct, concise, telegram-friendly: plain text, "
    "occasional *bold*, no markdown headers."
)

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

                active = config.get_active_provider()
                if not active:
                    continue

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
                    continue

                try:
                    search_context = ""
                    web_tool = WebSearchTool(config)
                    if web_tool.is_configured():
                        try:
                            search_context = asyncio.run(web_tool.search(text))
                        except Exception:
                            pass

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
                        {"role": "system", "content": LOCAL_IDENTITY_PROMPT},
                        {"role": "user", "content": user_msg}
                    ]

                    provider_name, model = active
                    api_key = config.data["providers"][provider_name]["api_key"]
                    provider = get_provider(provider_name, api_key, model)

                    async def _chat():
                        async for chunk in provider.chat(messages, stream=False):
                            return chunk
                        return ""
                    answer = asyncio.run(_chat()) + "\n\n_(sent by your device)_"

                    telegram = TelegramTool(config)
                    configured_chat = config.data["telegram"]["chat_id"]
                    if chat_id != configured_chat:
                        print(f"[telegram_listener] Warning: incoming chat_id {chat_id} differs from configured {configured_chat}")
                    sent = asyncio.run(telegram.send_message(answer))
                    if sent:
                        client.delete(
                            f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}",
                            headers=headers
                        )
                    else:
                        client.patch(
                            f"{supabase_url}/rest/v1/incoming_messages?id=eq.{msg_id}",
                            headers=headers,
                            json={"status": "pending", "claimed_by": None, "claimed_at": None}
                        )
                        print(f"[telegram_listener] Failed to send answer for msg {msg_id}, reverted to pending")
                except Exception as e:
                    print(f"[telegram_listener] Error processing msg {msg_id}: {e}")
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
