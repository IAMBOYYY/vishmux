import httpx
from ai_settings import get_ai_settings

VISHMUX_IDENTITY_PROMPT = (
    "You are VISHMUX, a personal AI agent. Right now you are answering on "
    "VISHMUX's behalf through Telegram — either because the user scheduled "
    "this as a recurring task, or because they messaged their bot while "
    "their main device (running VISHMUX locally) was offline or slow to "
    "respond. You are the remote fallback, not the user's full local agent, "
    "so you have no file or shell access here — just answer using your "
    "knowledge and any search context given. Be direct, concise, and "
    "telegram-friendly: plain text, occasional *bold*, no markdown headers."
)

async def generate_answer(task_query: str, search_context: str) -> str:
    try:
        settings = await get_ai_settings()
        if search_context:
            user_message = (
                f'The user asked/scheduled this: "{task_query}"\n\n'
                f"Here is fresh web search context to help answer accurately:\n\n{search_context}\n\n"
                f"Write a concise, well-organized answer suitable for a Telegram "
                f"message. Do not use markdown headers (#) since Telegram doesn't "
                f"render them — plain text with occasional *bold* is fine."
            )
        else:
            user_message = (
                f'The user asked/scheduled this: "{task_query}"\n\n'
                f"No live web search is available, so answer from general "
                f"knowledge. If this needs current or real-time information you "
                f"can't verify (like today's news), say so honestly instead of "
                f"guessing. Keep it concise, plain text, suitable for a Telegram "
                f"message, no markdown headers."
            )
        payload = {
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": VISHMUX_IDENTITY_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 1024,
            "temperature": 0.5
        }
        headers = {
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings['base_url']}/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data["choices"][0]["message"].get("content", "").strip()
            if not answer:
                return "(empty response)"
            return answer
    except Exception as e:
        return f"⚠️ Couldn't generate a response right now ({e})."
