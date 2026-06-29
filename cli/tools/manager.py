#!/usr/bin/env python3
"""
VISHMUX ToolManager – central hub for all tools, wired into the agent loop.
"""

from typing import Callable, Coroutine, Any

from .web_search import WebSearchTool
from .file_tool import FileTool
from .telegram_tool import TelegramTool


class ToolManager:
    """Holds tool instances and routes commands to the appropriate handler."""

    def __init__(self, config):
        self.config = config
        self.web = WebSearchTool(config)
        self.files = FileTool(config)
        self.telegram = TelegramTool(config)

    async def handle_web_command(
        self,
        query: str,
        display,
        agent_chat_fn: Callable[[str], Coroutine[Any, Any, None]]
    ) -> None:
        """
        Handle /web <query> command:
        - Perform search
        - Display results
        - Feed results to AI for summarisation
        """
        if not self.web.is_configured():
            display.show_info("Web search not configured.")
            display.show_info("Options:")
            display.show_info("  • Tavily (1000 free/month): https://tavily.com")
            display.show_info("  • Brave (2000 free/month): https://brave.com/search/api")
            display.show_info("  • Or set provider to 'duckduckgo' (no key needed, limited)")
            display.show_info("Add to config: web_search_key + web_search_provider")
            return

        if not query.strip():
            display.show_info("Usage: /web <your search query>")
            return

        display.show_info(f"🔍 Searching: {query}")
        results = await self.web.search(query)

        # Show results in terminal
        display.print_markdown(results)

        # Send results to AI so it can reason about them
        context_message = (
            f"I searched the web for: '{query}'\n\n"
            f"Here are the results:\n\n{results}\n\n"
            f"Please summarise the key findings."
        )
        await agent_chat_fn(context_message)

    async def handle_tg_command(self, subcmd: str, display) -> None:
        """Route /tg subcommands."""
        subcmd = subcmd.strip().lower()

        if subcmd == "setup":
            await self.telegram.setup_interactive(display)

        elif subcmd == "test":
            if not self.telegram.is_configured():
                display.show_error("Telegram not configured. Run: /tg setup")
                return
            result = await self.telegram.test_connection()
            display.show_info(result)

        elif subcmd.startswith("send "):
            if not self.telegram.is_configured():
                display.show_error("Telegram not configured. Run: /tg setup")
                return
            message = subcmd[5:].strip()
            success = await self.telegram.send_message(message)
            if success:
                display.show_success("Message sent to Telegram!")
            else:
                display.show_error("Failed to send message.")

        else:
            display.show_info("Telegram commands:")
            display.show_info("  /tg setup  → Configure your Telegram bot")
            display.show_info("  /tg test   → Test the connection")
            display.show_info("  /tg send <message> → Send a message now")

    def get_status(self) -> dict:
        """Return a dict describing the state of all tools."""
        return {
            "web_search": self.web.is_configured(),
            "telegram": self.telegram.is_configured(),
            "workspace": str(self.files.get_workspace_path()),
        }