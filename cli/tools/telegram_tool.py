#!/usr/bin/env python3
"""
VISHMUX TelegramTool – send messages and notifications via Telegram.
"""

import httpx
import asyncio


class TelegramTool:
    """Handles Telegram bot communication."""

    def __init__(self, config):
        self.config = config

    def is_configured(self) -> bool:
        """Check if both bot token and chat id are set."""
        tg = self.config.data.get("telegram", {})
        return bool(tg.get("bot_token", "").strip() and tg.get("chat_id", "").strip())

    async def send_message(self, text: str) -> bool:
        """Send a text message to the configured chat."""
        if not self.is_configured():
            return False
        tg = self.config.data["telegram"]
        url = f"https://api.telegram.org/bot{tg['bot_token']}/sendMessage"
        payload = {
            "chat_id": tg["chat_id"],
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return True
                return False
        except Exception:
            return False

    async def send_result(self, title: str, content: str) -> bool:
        """Send a formatted result message."""
        message = f"*{title}*\n\n{content}\n\n_Sent by VISHMUX_"
        return await self.send_message(message)

    async def test_connection(self) -> str:
        """Send a test message and return status string."""
        if not self.is_configured():
            return "❌ Telegram not configured. Run /tg setup."
        success = await self.send_message("🤖 VISHMUX connected successfully!")
        if success:
            return "✅ Telegram working!"
        else:
            return "❌ Telegram failed: could not send message. Check token and chat ID."

    async def setup_interactive(self, display) -> None:
        """
        Walk the user through Telegram setup:
        1. Get bot token from @BotFather
        2. Auto‑detect chat ID by waiting for a message
        3. Save to config and test
        """
        # Step 1: instructions
        display.show_info("To set up Telegram:")
        display.show_info("1. Open Telegram → search @BotFather")
        display.show_info("2. Send /newbot and follow instructions")
        display.show_info("3. Copy the bot token BotFather gives you")

        token = input("Enter your bot token: ").strip()
        if not token:
            return

        # Step 2: get chat id automatically
        display.show_info("Now send ANY message to your new bot in Telegram")
        display.show_info("Then press Enter here...")
        input()  # wait for user to send a message

        chat_id = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getUpdates")
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    chat_id = data["result"][0]["message"]["chat"]["id"]
        except Exception:
            pass

        if chat_id is None:
            display.show_info("Could not auto‑detect chat ID.")
            user_chat_id = input("Please enter your Chat ID manually: ").strip()
            if not user_chat_id:
                return
            chat_id = user_chat_id

        # Step 3: save
        self.config.data["telegram"]["bot_token"] = token
        self.config.data["telegram"]["chat_id"] = str(chat_id)
        self.config.data["telegram"]["enabled"] = True
        self.config.save()

        # Step 4: test
        result = await self.test_connection()
        display.show_success(result)