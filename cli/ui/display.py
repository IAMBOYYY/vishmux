#!/usr/bin/env python3
"""
VISHMUX Display – rich terminal output manager.
"""

import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text
from rich import box

console = Console()


class Display:
    """Handles all terminal output for VISHMUX CLI."""

    def welcome_banner(self):
        """Print ASCII art banner with session info."""
        ascii_art = (
            "[bold yellow]"
            "██╗   ██╗██╗███████╗██╗  ██╗███╗   ███╗██╗   ██╗██╗  ██╗\n"
            "██║   ██║██║██╔════╝██║  ██║████╗ ████║██║   ██║╚██╗██╔╝\n"
            "██║   ██║██║███████╗███████║██╔████╔██║██║   ██║ ╚███╔╝ \n"
            "╚██╗ ██╔╝██║╚════██║██╔══██║██║╚██╔╝██║██║   ██║ ██╔██╗ \n"
            " ╚████╔╝ ██║███████║██║  ██║██║ ╚═╝ ██║╚██████╔╝██╔╝ ██╗\n"
            "  ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝"
            "[/bold yellow]"
        )
        console.print(
            Panel(
                ascii_art,
                border_style="bold cyan",
                padding=(1, 2),
            )
        )
        console.print("[dim]Local AI Agent — Like Claude Code, but yours[/dim]")
        console.print("[dim]Type 'help' for commands, 'exit /s' to quit[/dim]")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[dim]Session started: {now}[/dim]")
        console.print()

    def show_provider_status(self, provider_name: str, model: str):
        """Print current provider and model on one line."""
        console.print(f"[green]●[/green] {provider_name} [dim]→[/dim] [cyan]{model}[/cyan]")

    def show_previous_session(self, summary: str):
        """Display last session summary panel."""
        console.print(
            Panel(
                f"[dim]{summary}[/dim]",
                title="📋 Last Session Summary",
                border_style="yellow",
            )
        )
        console.print("Continue where you left off? Type 'resume' or just start chatting.\n")

    def user_prompt(self) -> str:
        """Print styled prompt and return user input."""
        console.print("[bold cyan]You[/bold cyan] [dim]›[/dim] ", end="")
        return input().strip()

    def thinking_indicator(self):
        """Show thinking dots."""
        console.print("[dim]VISHMUX is thinking...[/dim]", end="", highlight=False)

    def clear_thinking(self):
        """Erase the thinking line."""
        console.print("\r" + " " * 40 + "\r", end="")

    def stream_start(self):
        """Begin streaming area."""
        console.print("[bold green]VISHMUX[/bold green] [dim]›[/dim] ", end="", highlight=False)

    def stream_chunk(self, chunk: str):
        """Print a single chunk during streaming."""
        console.print(chunk, end="", highlight=False)

    def stream_end(self):
        """Finalize streaming output."""
        console.print()
        console.print(Rule(style="dim"))

    def show_error(self, message: str):
        """Print error message."""
        console.print(f"[red]✗ Error:[/red] {message}")

    def show_success(self, message: str):
        """Print success message."""
        console.print(f"[green]✓[/green] {message}")

    def show_info(self, message: str):
        """Print informational message."""
        console.print(f"[cyan]ℹ[/cyan] {message}")

    def show_help(self):
        """Print full help panel."""
        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Command", style="yellow", no_wrap=True)
        table.add_column("Description", style="dim")
        rows = [
            ("exit /s", "Quit and delete temp files (clean exit)"),
            ("exit /ss", "Quit and SAVE all files for next session"),
            ("help", "Show this help menu"),
            ("clear", "Clear the screen"),
            ("switch", "Switch AI provider or model"),
            ("status", "Show current provider and session info"),
            ("vishmux setup", "Re-run setup wizard"),
            ("/file <path>", "Send a file to the AI for analysis"),
            ("/web <query>", "Search the web"),
            ("/skill <url>", "Download and load a skill file"),
            ("/tg setup", "Set up or reconnect Telegram"),
        ]
        for cmd, desc in rows:
            table.add_row(cmd, desc)
        console.print(
            Panel(table, title="VISHMUX Commands", border_style="cyan")
        )

    def show_status(self, provider: str, model: str, session_id: str,
                    files_count: int, skills: list):
        """Print session status panel."""
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="dim")
        table.add_row("Provider", provider)
        table.add_row("Model", model)
        table.add_row("Session ID", session_id)
        table.add_row("Temp Files", f"{files_count} files")
        table.add_row("Skills", ", ".join(skills) if skills else "None loaded")
        console.print(
            Panel(table, title="Session Status", border_style="blue")
        )

    def show_exit_menu(self) -> str:
        """Show exit options and return user choice."""
        console.print()
        console.print(
            Panel(
                "  [1] exit /s  — Clean exit (temp files deleted)\n"
                "  [2] exit /ss — Save exit (files kept for next session)\n"
                "  [3] Cancel   — Go back",
                title="How do you want to quit?",
                border_style="yellow",
            )
        )
        choice = input("Choice: ").strip()
        return choice

    def print_markdown(self, text: str):
        """Render text as markdown."""
        console.print(Markdown(text))

    def confirm_action(self, description: str) -> bool:
        """
        Ask the user to confirm a risky action (like running a shell command).
        Shows `description` inside a yellow warning-styled Panel titled
        "⚠ Confirmation needed" and prompts with Run it? [y/N].
        Returns True only if user enters 'y' or 'yes'.
        """
        console.print(
            Panel(
                description,
                title="⚠ Confirmation needed",
                border_style="yellow"
            )
        )
        choice = input("Run it? [y/N]: ").strip().lower()
        return choice in ("y", "yes")

    def show_tool_call(self, name: str, arguments: dict):
        """
        Print a single compact dim line showing a tool is being called.
        """
        preview = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        if len(preview) > 80:
            preview = preview[:77] + "..."
        console.print(f"[dim]🔧 {name}({preview})[/dim]")
