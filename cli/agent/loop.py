#!/usr/bin/env python3
"""
VISHMUX AgentLoop – main chat loop orchestrating the AI conversation.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from ..config import Config
from ..session.manager import SessionManager
from ..session.exit_handler import ExitHandler
from ..ui.display import Display
from ..ui.streaming import StreamHandler
from ..providers import get_provider, BaseProvider
from .planner import Planner
from .summarizer import Summarizer


class AgentLoop:
    """
    Core agent loop that manages conversation state, processes user input,
    routes commands, and streams AI responses to the terminal.
    """

    def __init__(
        self,
        config: Config,
        session: SessionManager,
        display: Display,
        stream_handler: StreamHandler,
        exit_handler: ExitHandler,
    ) -> None:
        self.config = config
        self.session = session
        self.display = display
        self.stream_handler = stream_handler
        self.exit_handler = exit_handler
        self.provider: Optional[BaseProvider] = None
        self.planner = Planner()
        self.summarizer = Summarizer()
        self.messages: list[dict] = []
        self.system_prompt = ""
        self._running = False

    async def initialize(self) -> bool:
        """Set up the AI provider and system prompt. Returns False if no provider available."""
        active = self.config.get_active_provider()
        if not active:
            return False

        provider_name, model = active
        api_key = self.config.data["providers"][provider_name]["api_key"]
        if not api_key:
            return False

        try:
            self.provider = get_provider(provider_name, api_key, model)
        except ValueError as e:
            self.display.show_error(str(e))
            return False

        self._build_system_prompt()
        return True

    def _build_system_prompt(self) -> None:
        """Construct the system prompt that defines VISHMUX's behavior."""
        session_ctx = self.session.get_session_context()
        self.system_prompt = f"""You are VISHMUX, a powerful local AI agent running directly on this device.

You are:
- Concise and direct – get straight to the point
- Helpful and friendly – explain things clearly when needed
- Technical when appropriate – use proper terminology
- Stream-aware – you are streaming responses token by token

CAPABILITIES:
- Full conversational AI with streaming responses
- Code generation and analysis with syntax highlighting
- File reading and creation in the workspace
- Web search (when enabled via /web)
- Telegram notifications (when configured via /tg)
- Skills system for extensible capabilities (via /skill)

SESSION CONTEXT:
{session_ctx}

AVAILABLE USER COMMANDS:
- help          → Show all commands
- clear         → Clear the screen
- status        → Show session info and provider
- switch        → Switch AI provider or model
- vishmux setup → Re-run setup wizard
- /file <path>  → Read and analyze a file
- /skill <url>  → Download and load a skill
- /web <query>  → Search the web
- /tg setup     → Configure Telegram
- exit /s       → Clean exit (delete temp files)
- exit /ss      → Save exit (keep all files)

GUIDELINES:
- Use markdown for code blocks with language tags (```python, ```bash, etc.)
- When creating files, mention the path clearly
- Keep responses focused – avoid unnecessary preamble
- If unsure about something, ask for clarification rather than guessing
- Remember you run locally on the user's device – feel at home there"""

    def _build_messages(self) -> list:
        """Return the full message list including system prompt."""
        return [{"role": "system", "content": self.system_prompt}] + self.messages

    async def run(self) -> None:
        """Main conversation loop."""
        self._running = True

        while self._running:
            try:
                user_input = self.display.user_prompt()
            except (KeyboardInterrupt, EOFError):
                self.display.show_info("\nUse 'exit /s' for clean exit.")
                continue

            if not user_input:
                continue

            # Check if it's a command first
            is_command = await self._handle_command(user_input)
            if is_command:
                continue

            # Regular chat message
            await self._chat(user_input)

    async def _chat(self, user_message: str) -> None:
        """Send a message to the AI and stream the response."""
        if self.provider is None:
            self.display.show_error("No provider configured. Use 'switch' to select one.")
            return

        # Append user message to history
        self.messages.append({"role": "user", "content": user_message})

        # BUG FIX 1: clear_thinking() must be called BEFORE stream_response(),
        # not after. stream_response() calls stream_start() internally which
        # prints "VISHMUX ›" — calling clear_thinking after would erase
        # already-printed output on the wrong line.
        self.display.thinking_indicator()

        try:
            self.display.clear_thinking()  # ← clear BEFORE streaming starts
            full_response = await self.stream_handler.stream_response(
                self.provider, self._build_messages()
            )
        except Exception as e:
            self.display.show_error(str(e))
            # Remove the failed user message from history so user can retry
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            return

        # Append AI response to history
        self.messages.append({"role": "assistant", "content": full_response})

        # Log the exchange to session summary
        self.summarizer.log_exchange(self.session, user_message, full_response)

        # Trim history if it gets too long
        self.messages = self.summarizer.compress_history(self.messages)

    async def _handle_command(self, cmd: str) -> bool:
        """
        Process a user command. Returns True if it WAS a command (skip chat),
        False if not a command (should be sent to AI).
        """
        cmd_lower = cmd.strip().lower()

        # Help
        if cmd_lower == "help":
            self.display.show_help()
            return True

        # Clear screen
        if cmd_lower == "clear":
            os.system("clear" if os.name != "nt" else "cls")
            return True

        # Status
        if cmd_lower == "status":
            active = self.config.get_active_provider()
            provider_name = active[0] if active else "None"
            model = active[1] if active else "None"
            file_count = self.session.get_temp_file_count()
            self.display.show_status(
                provider=provider_name,
                model=model,
                session_id=self.session.session_id,
                files_count=file_count,
                skills=self.session.loaded_skills,
            )
            return True

        # Switch provider
        if cmd_lower == "switch":
            await self._switch_provider()
            return True

        # Re-run setup wizard
        if cmd_lower == "vishmux setup":
            # BUG FIX 2: DeepSeek used `from ..setup_wizard import run_setup`
            # which doesn't exist. setup_wizard.py is a standalone script with
            # a SetupWizard class. Safest approach: run it as a subprocess.
            self.display.show_info("Launching setup wizard...")
            wizard_path = Path(__file__).parent.parent / "setup_wizard.py"
            try:
                subprocess.run([sys.executable, str(wizard_path)], check=True)
                self.config.load()
                if not await self.initialize():
                    self.display.show_error("No provider configured after setup.")
                else:
                    self.display.show_success("Setup complete! You can continue chatting.")
            except subprocess.CalledProcessError:
                self.display.show_error("Setup wizard exited with an error.")
            except FileNotFoundError:
                self.display.show_error(f"setup_wizard.py not found at: {wizard_path}")
            return True

        # Download and load a skill
        if cmd_lower.startswith("/skill"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                self.display.show_info("Usage: /skill <url>")
                return True
            url = parts[1].strip()
            try:
                skill_data = self.session.download_skill(url)
                self.display.show_success(f"Skill loaded: {skill_data.get('name', url)}")
            except Exception as e:
                self.display.show_error(str(e))
            return True

        # Read and analyze a file
        if cmd_lower.startswith("/file"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                self.display.show_info("Usage: /file <path>")
                return True
            path = parts[1].strip()
            try:
                expanded = os.path.expanduser(path)
                if not os.path.exists(expanded):
                    self.display.show_error(f"File not found: {path}")
                    return True
                with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                # BUG FIX 3: DeepSeek appended to self.messages directly AND
                # then called _chat() which appended ANOTHER user message — two
                # user messages in a row, causing broken conversation history.
                # Fix: just pass the file content directly into _chat() as one
                # single user message. _chat() handles the append itself.
                file_message = (
                    f"I'm sharing a file with you. Path: {path}\n\n"
                    f"```\n{content[:8000]}\n```\n\n"
                    f"Please analyze this file."
                )
                self.display.show_success(f"File loaded: {path} ({len(content)} chars)")
                await self._chat(file_message)

            except Exception as e:
                self.display.show_error(str(e))
            return True

        # Web search (placeholder — Module 5)
        if cmd_lower.startswith("/web"):
            self.display.show_info("Web search coming in Module 5.")
            return True

        # Telegram (placeholder — Module 5)
        if cmd_lower.startswith("/tg"):
            self.display.show_info("Telegram setup coming in Module 5.")
            return True

        # Exit commands
        if cmd_lower in ("exit", "quit", "q", "exit /s", "exit /ss"):
            should_exit = self.exit_handler.handle_exit(cmd)
            if should_exit:
                self._running = False
            return True

        return False

    async def _switch_provider(self) -> None:
        """Interactive provider switching."""
        # Collect providers that have an API key configured
        enabled = [
            name for name, data in self.config.data["providers"].items()
            if data.get("api_key")
        ]

        if not enabled:
            self.display.show_error("No providers with API keys configured. Run 'vishmux setup'.")
            return

        self.display.show_info("Configured providers:")
        for i, name in enumerate(enabled, 1):
            model = self.config.data["providers"][name]["default_model"]
            is_active = name == self.config.data["active_provider"]
            marker = " ← active" if is_active else ""
            self.display.show_info(f"  [{i}] {name} → {model}{marker}")

        try:
            choice = input("\nSelect provider number (or press Enter to cancel): ").strip()
            if not choice:
                return
            idx = int(choice) - 1
            if idx < 0 or idx >= len(enabled):
                self.display.show_error("Invalid selection.")
                return
        except ValueError:
            self.display.show_error("Invalid input.")
            return

        provider_name = enabled[idx]
        default_model = self.config.data["providers"][provider_name]["default_model"]

        self.display.show_info(f"Default model: {default_model}")
        model_input = input(
            f"Enter model name (or press Enter to use '{default_model}'): "
        ).strip()
        model = model_input if model_input else default_model

        try:
            self.config.set_active_provider(provider_name, model)
            api_key = self.config.data["providers"][provider_name]["api_key"]
            self.provider = get_provider(provider_name, api_key, model)
            self._build_system_prompt()
            self.display.show_success(f"Switched to {provider_name} / {model}")
        except Exception as e:
            self.display.show_error(f"Switch failed: {e}")
