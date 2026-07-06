from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import config
from scheduler import run_check_cycle
from search_client import search
from ai_client import generate_answer
from telegram_sender import send_message

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_check_cycle, "interval", seconds=config.POLL_INTERVAL_SECONDS)
    scheduler.start()
    print(f"[main] VISHMUX render-server started — polling every {config.POLL_INTERVAL_SECONDS}s")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"service": "vishmux-render-server", "status": "running"}

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        message = update.get("message")
        if not message:
            return {"ok": True}
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()
        if not chat_id or not text:
            return {"ok": True}
        if text.startswith("/"):
            return {"ok": True}
        search_context = await search(text)
        answer = await generate_answer(text, search_context)
        await send_message(chat_id, answer)
        return {"ok": True}
    except Exception as e:
        print(f"[webhook] Error handling update: {e}")
        return {"ok": True}