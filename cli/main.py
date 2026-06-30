#!/usr/bin/env python3
"""
VISHMUX – Free local AI agent CLI, like Claude Code but self-hosted.
Entry point for the chat application.
"""

import asyncio
import os
import sys
from pathlib import Path

# WINDOWS FIX: Windows terminals default to the legacy cp1252 codepage, which
# cannot encode the Unicode box-drawing characters used in the VISHMUX banner
# and rich's UI elements. This forces UTF-8 output before any rich Console is
# created, fixing "UnicodeEncodeError: 'charmap' codec can't encode characters"
# on Windows. No effect on Linux/macOS/Termux, where UTF-8 is already default.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add parent directory to path so imports work from any location
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.config import Config
from cli.session.manager import SessionManager
from cli.session.exit_handler import ExitHandler
from cli.ui.display import Display
from cli.ui.streaming import StreamHandler
from cli.agent.loop import AgentLoop


async def main() -> None:
    """Initialize and start the VISHMUX chat session."""
    config = Config()
    config.load()
    display = Display()

    # Check if setup is needed
    if not config.is_setup_done():
        display.show_info("Welcome to VISHMUX! First-time setup required.")
        display.show_info("Run: python setup_wizard.py")
        display.show_info("Or run: vishmux setup")
        sys.exit(0)

    # Initialize session management
    session = SessionManager(config)
    session.initialize()

    # Show welcome banner
    display.welcome_banner()

    # Show active provider
    active = config.get_active_provider()
    if active:
        display.show_provider_status(active[0], active[1])

    # Load and display skills
    skills = session.load_skills()
    if skills:
        display.show_info(f"🔧 Loaded skills: {', '.join(skills)}")

    print()

    # Show last session summary if available
    last_summary = session.get_last_session_summary()
    if last_summary:
        display.show_previous_session(last_summary)

    # Build components
    stream_handler = StreamHandler(display)
    exit_handler = ExitHandler(session, display)

    # Create and start the agent loop
    loop = AgentLoop(
        config=config,
        session=session,
        display=display,
        stream_handler=stream_handler,
        exit_handler=exit_handler,
    )

    if not await loop.initialize():
        display.show_error("No AI provider configured. Run setup first.")
        display.show_info("Command: python setup_wizard.py")
        sys.exit(1)

    await loop.run()


def cli_entry() -> None:
    """Entry point for pip/pipx install."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Use 'exit /s' next time for a clean exit.")
        sys.exit(0)


if __name__ == "__main__":
    cli_entry()