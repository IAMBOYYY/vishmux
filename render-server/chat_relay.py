import config
from supabase_client import get_claimable_messages, try_claim_message, delete_message, revert_to_pending
from search_client import search
from ai_client import generate_answer
from telegram_sender import send_message
from ai_settings import get_ai_settings

async def answer_stale_messages() -> None:
    """
    Fallback job: every CHAT_POLL_INTERVAL_SECONDS, check for messages
    that have been pending too long (or stuck claimed), then claim and answer.
    Respects the Telegram reply mode from ai_config:
    - hybrid: Termux first, Render falls back after a delay
    - render_only: Render answers immediately without waiting
    - termux_only: Render never answers — Termux is the sole responder
    """
    try:
        settings = await get_ai_settings()
        mode = settings.get("mode", "hybrid")

        # termux_only: Render must never claim or reply — Termux answers, however long it takes.
        if mode == "termux_only":
            return

        stale_seconds = 2 if mode == "render_only" else config.CHAT_FALLBACK_DELAY_SECONDS
        rows = await get_claimable_messages(stale_seconds)
        for row in rows:
            try:
                msg_id = row["id"]
                chat_id = row["chat_id"]
                text = row["text"]
                status = row.get("status", "pending")
                expected_status = status  # "pending" or "claimed"

                claimed = await try_claim_message(msg_id, "render", expected_status)
                if not claimed:
                    continue

                # Search + AI answer (render_only / hybrid paths)
                try:
                    search_context = await search(text)
                except Exception:
                    search_context = ""
                answer = await generate_answer(text, search_context)

                sent = await send_message(chat_id, answer)
                if sent:
                    await delete_message(msg_id)
                else:
                    print(f"[chat_relay] Telegram send failed for msg {msg_id}, reverting")
                    await revert_to_pending(msg_id)
            except Exception as e:
                print(f"[chat_relay] Error processing msg {row.get('id')}: {e}")
                try:
                    await revert_to_pending(msg_id)
                except Exception:
                    pass
    except Exception as e:
        print(f"[chat_relay] Cycle failed: {e}")
