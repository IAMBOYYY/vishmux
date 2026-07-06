import httpx
import config

async def generate_answer(task_query: str, search_context: str) -> str:
    try:
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
            "model": config.AI_MODEL,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 1024,
            "temperature": 0.5
        }
        headers = {
            "Authorization": f"Bearer {config.AI_API_KEY}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{config.AI_BASE_URL}/chat/completions",
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