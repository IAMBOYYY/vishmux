#!/usr/bin/env python3
"""
VISHMUX ToolManager – central hub for all tools, wired into the agent loop.
"""
import re
from typing import Callable, Coroutine, Any

from .web_search import WebSearchTool
from .file_tool import FileTool
from .telegram_tool import TelegramTool
from .task_tool import TaskTool


class ToolManager:
    """Holds tool instances and routes commands to the appropriate handler."""

    def __init__(self, config):
        self.config = config
        self.web = WebSearchTool(config)
        self.files = FileTool(config)
        self.telegram = TelegramTool(config)
        self.tasks = TaskTool(config)

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

    async def handle_task_command(self, subcmd: str, display) -> None:
        """Route /task subcommands for scheduling tasks."""
        subcmd = subcmd.strip()
        if not subcmd:
            display.show_info("Task commands:")
            display.show_info("  /task add <type> \"<query>\" <HH:MM>  → Schedule a task")
            display.show_info("  /task list                            → Show your tasks")
            display.show_info("  /task remove <id>                     → Delete a task")
            display.show_info("  /task test                            → Test Supabase connection")
            return

        if subcmd == "test":
            result = await self.tasks.test_connection()
            display.show_info(result)
            return

        if subcmd == "list":
            user_tg_id = self.config.data["telegram"]["chat_id"]
            if not user_tg_id:
                display.show_error("Link Telegram first: /tg setup")
                return
            result = await self.tasks.list_tasks(user_tg_id)
            if not result["success"]:
                display.show_error(result["error"])
                return
            tasks = result["tasks"]
            if not tasks:
                display.show_info("No scheduled tasks yet.")
                return
            # Format table
            lines = ["| ID | Type | Query | Schedule | Active |",
                     "|----|------|-------|----------|--------|"]
            for t in tasks:
                lines.append(
                    f"| {t.get('id','?')} | {t.get('task_type','')} | "
                    f"{t.get('task_query','')[:30]} | {t.get('schedule','')} | "
                    f"{'✅' if t.get('is_active') else '❌'} |"
                )
            display.print_markdown("\n".join(lines))
            return

        if subcmd.startswith("remove "):
            task_id = subcmd[7:].strip()
            if not task_id:
                display.show_info("Usage: /task remove <id>")
                return
            result = await self.tasks.delete_task(task_id)
            if result["success"]:
                display.show_success(f"Task {task_id} removed.")
            else:
                display.show_error(result["error"])
            return

        # Must be add command: /task add <type> "<query>" <HH:MM>
        match = re.match(r'add\s+(\S+)\s+"([^"]+)"\s+(\S+)', subcmd)
        if not match:
            display.show_info("Usage: /task add <type> \"<query>\" <HH:MM>")
            display.show_info("Example: /task add daily_news \"top 10 AI news\" 20:00")
            return

        task_type = match.group(1)
        task_query = match.group(2)
        schedule = match.group(3)
        user_tg_id = self.config.data["telegram"]["chat_id"]

        if not user_tg_id:
            display.show_error("Link Telegram first: /tg setup")
            return

        if not self.tasks.is_configured():
            display.show_error("Supabase not configured. Set up in the setup wizard.")
            return

        result = await self.tasks.create_task(user_tg_id, task_type, task_query, schedule)
        if result["success"]:
            task = result["task"]
            display.show_success(f"Task scheduled! ID: {task.get('id', 'unknown')}")
        else:
            display.show_error(result["error"])

    def get_status(self) -> dict:
        """Return a dict describing the state of all tools."""
        return {
            "web_search": self.web.is_configured(),
            "telegram": self.telegram.is_configured(),
            "supabase": self.tasks.is_configured(),
            "workspace": str(self.files.get_workspace_path()),
        }
