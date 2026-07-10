#!/usr/bin/env python3
"""
VISHMUX Setup Wizard — beautiful terminal assistant for first-run configuration.
"""

import sys

# WINDOWS FIX: Windows terminals default to the legacy cp1252 codepage, which
# cannot encode the Unicode box-drawing characters (██╗ etc.) used in the
# VISHMUX banner and rich's UI elements. This forces UTF-8 output on stdout
# and stderr before any rich Console is created, fixing
# "UnicodeEncodeError: 'charmap' codec can't encode characters" on Windows.
# No effect on Linux/macOS/Termux, where UTF-8 is already the default.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
from typing import List, Dict, Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from config import Config
from tools.render_sync import sync_ai_config_to_render

console = Console()

# Provider mapping: number -> key
PROVIDER_MAP = {
    "1": "openrouter",
    "2": "groq",
    "3": "nvidia",
    "4": "gemini",
    "5": "together",
    "6": "mistral",
    "7": "anthropic",
    "8": "perplexity",
}

# Display descriptions
PROVIDER_DESCRIPTIONS = {
    "openrouter": "OpenRouter — 100+ models with one key",
    "groq": "Groq — Fastest free inference",
    "nvidia": "Nvidia NIM — Nemotron + premium models",
    "gemini": "Google Gemini — Vision + generous free tier",
    "together": "Together AI — Open source models",
    "mistral": "Mistral — European AI models",
    "anthropic": "Anthropic — Claude models",
    "perplexity": "Perplexity — Built-in web search",
}

HARDCODED_MODELS = {
    "anthropic": [
        "claude-opus-4-6",
        "claude-opus-4-7",
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ],
    "perplexity": [
        "llama-3.1-sonar-large-128k-online",
        "llama-3.1-sonar-small-128k-online",
        "llama-3.1-sonar-huge-128k-online",
    ],
}


async def fetch_models(provider_key: str, api_key: str) -> List[str]:
    """Fetch model list for a provider, applying provider-specific filters."""
    # Hardcoded providers
    if provider_key in HARDCODED_MODELS:
        return HARDCODED_MODELS[provider_key]

    url = ""
    headers = {}
    timeout = 15.0

    if provider_key == "groq":
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider_key == "openrouter":
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider_key == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider_key == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    elif provider_key == "together":
        url = "https://api.together.xyz/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider_key == "mistral":
        url = "https://api.mistral.ai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        raise ValueError(f"Unknown provider: {provider_key}")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    models: List[str] = []

    if provider_key == "groq":
        # data["data"] list of objects with "id"
        for item in data.get("data", []):
            mid = item.get("id", "")
            if "whisper" not in mid.lower() and "guard" not in mid.lower():
                models.append(mid)
    elif provider_key == "openrouter":
        # data["data"] list, show first 30
        for item in data.get("data", [])[:30]:
            models.append(item.get("id", ""))
    elif provider_key == "nvidia":
        for item in data.get("data", []):
            models.append(item.get("id", ""))
    elif provider_key == "gemini":
        for item in data.get("models", []):
            name = item.get("name", "")
            if name.startswith("models/"):
                name = name[7:]
            if "gemini" in name.lower():
                models.append(name)
    elif provider_key == "together":
        # data is a list of model objects (or list)
        items = data if isinstance(data, list) else []
        for item in items[:25]:
            models.append(item.get("id", ""))
    elif provider_key == "mistral":
        for item in data.get("data", []):
            models.append(item.get("id", ""))

    return models


async def setup_supabase(config: Config) -> None:
    """Optional Supabase setup for scheduled task delivery (/task commands)."""
    from tools.task_tool import TaskTool

    try:
        console.print(Panel(
            "[dim]Supabase powers scheduled tasks — VISHMUX writes tasks to a table, "
            "and a small server delivers them via Telegram at the right time.[/dim]",
            title="Supabase Setup (Optional — for scheduled tasks)",
            border_style="blue"
        ))
        if not Confirm.ask("Set up scheduled tasks via Supabase?", default=False):
            console.print("[dim]Skipped Supabase.[/dim]")
            return

        console.print("Find these under Project Settings → API in your Supabase dashboard.")
        url = Prompt.ask("Supabase Project URL").strip()
        key = Prompt.ask("Supabase anon/public key", password=True).strip()
        if not url or not key:
            console.print("[yellow]Skipping Supabase setup (both URL and key are required).[/yellow]")
            return

        config.data["supabase"]["url"] = url
        config.data["supabase"]["key"] = key
        config.data["supabase"]["configured"] = True
        config.save()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Testing Supabase connection...", total=None)
            task_tool = TaskTool(config)
            result = await task_tool.test_connection()
            progress.update(task, description="")
            progress.stop()

        if result.startswith("✅"):
            console.print(f"[green]{result}[/green]")
        else:
            console.print(f"[yellow]{result}[/yellow]")
            console.print("[yellow]Settings were saved anyway — you can fix and retest with /task test.[/yellow]")
    except Exception as e:
        console.print(f"[red]Supabase setup error: {e}[/red]")
        console.print("[dim]Skipping Supabase setup.[/dim]")


async def setup_timezone(config: Config) -> None:
    """Set the IANA timezone used to interpret scheduled task times."""
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        console.print("[yellow]Timezone support needs Python 3.9+. Skipping — tasks will use UTC.[/yellow]")
        return

    try:
        console.print(Panel(
            "[dim]This is only used for scheduled tasks (/task add) — so '8pm' means "
            "YOUR 8pm, not a server's. Uses IANA format, e.g. Asia/Kolkata, "
            "America/New_York, Europe/London. If unsure, search "
            "'IANA timezone <your city>'.[/dim]",
            title="Timezone Setup (for scheduled tasks)",
            border_style="blue"
        ))
        if not Confirm.ask("Set your timezone now?", default=True):
            console.print("[dim]Skipped — scheduled tasks will default to UTC.[/dim]")
            return

        for _ in range(3):
            tz_input = Prompt.ask("Your IANA timezone", default="UTC").strip()
            try:
                ZoneInfo(tz_input)
                config.data["timezone"] = tz_input
                config.save()
                console.print(f"[green]✓ Timezone set to {tz_input}[/green]")
                return
            except ZoneInfoNotFoundError:
                console.print(f"[red]'{tz_input}' isn't a recognized IANA timezone. Try again (e.g. Asia/Kolkata).[/red]")

        console.print("[yellow]Too many invalid attempts — defaulting to UTC. You can fix this later by re-running setup.[/yellow]")
        config.data["timezone"] = "UTC"
        config.save()
    except Exception as e:
        console.print(f"[red]Timezone setup error: {e}[/red]")
        console.print("[dim]Skipping — scheduled tasks will default to UTC.[/dim]")


async def run_setup():
    # Instantiate and load existing config
    config = Config()
    config.load()

    # ========================================================================
    # STEP 1 — Welcome Banner
    # ========================================================================
    console.clear()
    banner_text = (
        "[bold yellow]██╗   ██╗██╗███████╗██╗  ██╗███╗   ███╗██╗   ██╗██╗  ██╗[/bold yellow]\n"
        "[bold yellow]██║   ██║██║██╔════╝██║  ██║████╗ ████║██║   ██║╚██╗██╔╝[/bold yellow]\n"
        "[bold yellow]██║   ██║██║███████╗███████║██╔████╔██║██║   ██║ ╚███╔╝ [/bold yellow]\n"
        "[bold yellow]╚██╗ ██╔╝██║╚════██║██╔══██║██║╚██╔╝██║██║   ██║ ██╔██╗ [/bold yellow]\n"
        "[bold yellow] ╚████╔╝ ██║███████║██║  ██║██║ ╚═╝ ██║╚██████╔╝██╔╝ ██╗[/bold yellow]\n"
        "[bold yellow]  ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/bold yellow]"
    )
    console.print(
        Panel(
            banner_text,
            title="[bold cyan]VISHMUX[/bold cyan]",
            subtitle="AI Agent Setup Wizard",
            border_style="bold cyan",
            padding=(1, 2),
        )
    )
    console.print("[dim]v1.0.0[/dim]\n")
    console.print("Welcome! Let's get you set up in a few minutes.\n", style="italic")

    # ========================================================================
    # STEP 2 — Provider Selection Loop
    # ========================================================================
    selected_providers: List[str] = []
    while True:
        panel_content = ""
        for num, key in PROVIDER_MAP.items():
            desc = PROVIDER_DESCRIPTIONS[key]
            panel_content += f"  [{num}] {desc}\n"
        panel_content += "  [0] Done — finish adding providers"

        console.print(Panel(panel_content, title="Select AI Providers", border_style="blue"))

        choice = Prompt.ask("Enter your choice", choices=["0","1","2","3","4","5","6","7","8"], default="0")
        if choice == "0":
            if not selected_providers:
                console.print("[red]You must select at least one provider.[/red]")
                continue
            break

        provider_key = PROVIDER_MAP[choice]
        if provider_key in selected_providers:
            console.print(f"[yellow]⚠ {PROVIDER_DESCRIPTIONS[provider_key]} already added.[/yellow]")
        else:
            selected_providers.append(provider_key)
            console.print(f"[green]✓ Added {PROVIDER_DESCRIPTIONS[provider_key]}[/green]")
        console.print()

    # ========================================================================
    # STEP 3 — Configure each selected provider
    # ========================================================================
    configured_providers: List[str] = []

    for provider_key in list(selected_providers):  # iterate over copy
        console.rule(f"[bold cyan]Setting up [underline]{PROVIDER_DESCRIPTIONS[provider_key]}[/underline][/bold cyan]")

        while True:
            api_key = Prompt.ask("Enter API key", password=True)
            if not api_key.strip():
                console.print("[red]API key cannot be empty.[/red]")
                continue

            # Spinner while fetching
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Fetching available models...", total=None)
                try:
                    models = await fetch_models(provider_key, api_key)
                except Exception:
                    progress.update(task, description="")
                    progress.stop()
                    console.print("[red]✗ Failed to fetch models. Invalid API key or network error.[/red]")
                    retry = Confirm.ask("Retry with a different key?", default=True)
                    if not retry:
                        console.print(f"[yellow]Skipping {PROVIDER_DESCRIPTIONS[provider_key]}.[/yellow]")
                        break  # skip this provider
                    continue  # try again with new key

                progress.update(task, description="")
                progress.stop()

            if not models:
                console.print("[red]No models found for this provider.[/red]")
                retry = Confirm.ask("Retry with a different key?", default=True)
                if not retry:
                    break
                continue

            console.print(f"[green]✓ Connected! Found {len(models)} models[/green]")

            # Show models in a table
            model_table = Table(show_header=True, header_style="bold magenta")
            model_table.add_column("#", style="dim", width=4)
            model_table.add_column("Model ID")
            for idx, model in enumerate(models, 1):
                model_table.add_row(str(idx), model)
            console.print(model_table)

            # Model selection — free input to avoid Rich printing all choices for large lists
            while True:
                model_choice = Prompt.ask("Select default model number", default="1")
                if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
                    break
                console.print(f"[red]Please enter a number between 1 and {len(models)}[/red]")
            selected_model = models[int(model_choice) - 1]

            # Store in config
            config.data["providers"][provider_key]["api_key"] = api_key
            config.data["providers"][provider_key]["default_model"] = selected_model
            config.data["providers"][provider_key]["enabled"] = True
            configured_providers.append(provider_key)

            console.print(f"[green]✓ {PROVIDER_DESCRIPTIONS[provider_key]} configured with {selected_model}[/green]\n")
            break  # exit retry loop for this provider

    # Re‑load configured list from config (in case some were skipped)
    configured_providers = [p for p in PROVIDER_MAP.values() if config.data["providers"][p]["api_key"]]
    if not configured_providers:
        console.print("[red]No providers configured. Setup aborted.[/red]")
        return

    # ========================================================================
    # STEP 4 — Active Provider Selection
    # ========================================================================
    console.rule("[bold]Select Active Provider[/bold]")

    if len(configured_providers) == 1:
        provider_key = configured_providers[0]
        model = config.data["providers"][provider_key]["default_model"]
        config.set_active_provider(provider_key, model)
        console.print(f"Active provider auto-set to [bold]{PROVIDER_DESCRIPTIONS[provider_key]}[/bold] with model {model}")
    else:
        # Show list
        for idx, p in enumerate(configured_providers, 1):
            model = config.data["providers"][p]["default_model"]
            console.print(f"  [{idx}] {PROVIDER_DESCRIPTIONS[p]} — {model}")
        choice = Prompt.ask(
            "Choose active provider number",
            choices=[str(i) for i in range(1, len(configured_providers)+1)],
            default="1"
        )
        provider_key = configured_providers[int(choice)-1]
        model = config.data["providers"][provider_key]["default_model"]
        config.set_active_provider(provider_key, model)
        console.print(f"[green]✓ Active provider set to {PROVIDER_DESCRIPTIONS[provider_key]}[/green]\n")

    # ========================================================================
    # STEP 5 — Web Search Setup
    # ========================================================================
    console.print(Panel(
        "[dim]Web search lets VISHMUX search Google in real-time when answering your questions.[/dim]",
        title="Web Search Setup (Optional but Recommended)",
        border_style="blue"
    ))
    want_search = Confirm.ask("Add web search capability?", default=True)
    if want_search:
        console.print("  [1] Serper.dev    — 2,500 free searches (one-time) → https://serper.dev")
        console.print("  [2] Tavily        — 1,000 free searches/month → https://tavily.com")
        console.print("  [3] DuckDuckGo    — no key needed, but noticeably lower-quality/less relevant results — best as a quick fallback, not for anything important")
        console.print("  [4] Skip for now")
        search_choice = Prompt.ask("Choose option", choices=["1","2","3","4"], default="1")
        if search_choice in ["1", "2"]:
            provider_name = "serper" if search_choice == "1" else "tavily"
            search_key = Prompt.ask(f"Enter {provider_name} API key", password=True)
            config.data["web_search_key"] = search_key
            config.data["web_search_provider"] = provider_name
            console.print(f"[green]✓ Web search enabled with {provider_name.title()}[/green]")
        elif search_choice == "3":
            config.data["web_search_key"] = ""
            config.data["web_search_provider"] = "duckduckgo"
            console.print("[yellow]✓ Web search enabled with DuckDuckGo (no key) — expect rougher results.[/yellow]")
        else:
            console.print("[dim]Skipped web search.[/dim]")
    else:
        console.print("[dim]Skipped web search.[/dim]")

    # ========================================================================
    # STEP 6 — Telegram Setup
    # ========================================================================
    console.print(Panel(
        "[dim]Connect Telegram so VISHMUX can send you scheduled updates, news, reminders and task results.[/dim]",
        title="Telegram Setup (For scheduled tasks & notifications)",
        border_style="blue"
    ))
    want_telegram = Confirm.ask("Connect Telegram?", default=False)
    if want_telegram:
        console.print("Instructions:")
        console.print("  1. Message @BotFather on Telegram and create a new bot")
        console.print("  2. Copy the bot token it gives you")
        console.print("  3. Message @userinfobot to get your Chat ID\n")

        while True:
            bot_token = Prompt.ask("Bot Token", password=True)
            chat_id = Prompt.ask("Chat ID")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Testing Telegram connection...", total=None)
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        payload = {
                            "chat_id": chat_id,
                            "text": "✅ VISHMUX connected successfully! Your AI agent is ready."
                        }
                        resp = await client.post(url, json=payload)
                        resp.raise_for_status()
                        result = resp.json()
                        if not result.get("ok"):
                            raise ValueError("Telegram API returned not ok")
                except Exception:
                    progress.update(task, description="")
                    progress.stop()
                    console.print("[red]✗ Telegram connection failed. Check your token and chat ID.[/red]")
                    retry_tg = Confirm.ask("Try again?", default=True)
                    if not retry_tg:
                        console.print("[dim]Skipping Telegram setup.[/dim]")
                        break
                    continue

                progress.update(task, description="")
                progress.stop()

            console.print("[green]✓ Telegram connected! Check your messages.[/green]")
            config.data["telegram"]["bot_token"] = bot_token
            config.data["telegram"]["chat_id"] = chat_id
            config.data["telegram"]["enabled"] = True
            break
    else:
        console.print("[dim]Skipped Telegram.[/dim]")

    # ========================================================================
    # STEP 6.5 — Supabase Setup (Scheduled Tasks)
    # ========================================================================
    await setup_supabase(config)

    # ========================================================================
    # STEP 6.7 — Timezone Setup (Scheduled Tasks)
    # ========================================================================
    await setup_timezone(config)

    # ========================================================================
    # STEP 7 — Summary Screen
    # ========================================================================
    console.print()
    summary_table = Table(show_header=True, header_style="bold green")
    summary_table.add_column("Component", style="cyan")
    summary_table.add_column("Status")

    # All 8 providers
    for p in PROVIDER_MAP.values():
        prov_data = config.data["providers"][p]
        status = ""
        if prov_data["api_key"]:
            model = prov_data["default_model"]
            status = f"[green]✓ Configured ({model})[/green]"
            if p == config.data["active_provider"]:
                status += " [bold yellow]★ACTIVE[/bold yellow]"
        else:
            status = "[dim]✗ Skipped[/dim]"
        summary_table.add_row(PROVIDER_DESCRIPTIONS[p].split(" —")[0], status)

    # Active provider detail
    active = config.get_active_provider()
    if active:
        summary_table.add_row("Active Provider", f"[bold]{active[0]} / {active[1]}[/bold]")
    else:
        summary_table.add_row("Active Provider", "[dim]Not set[/dim]")

    # Web search
    ws_provider = config.data.get("web_search_provider", "")
    if ws_provider:
        summary_table.add_row("Web Search", f"[green]✓ {ws_provider.title()}[/green]")
    else:
        summary_table.add_row("Web Search", "[dim]✗ Not configured[/dim]")

    # Timezone
    tz = config.data.get("timezone", "")
    if tz:
        summary_table.add_row("Timezone", f"[green]✓ {tz}[/green]")
    else:
        summary_table.add_row("Timezone", "[dim]✗ Not set (defaults to UTC)[/dim]")

    # Telegram
    if config.data["telegram"].get("enabled"):
        summary_table.add_row("Telegram", "[green]✓ Connected[/green]")
    else:
        summary_table.add_row("Telegram", "[dim]✗ Not connected[/dim]")

    # Supabase (scheduled tasks)
    if config.data["supabase"].get("configured"):
        summary_table.add_row("Scheduled Tasks", "[green]✓ Supabase connected[/green]")
    else:
        summary_table.add_row("Scheduled Tasks", "[dim]✗ Not configured[/dim]")

    console.print(
        Panel(
            summary_table,
            title="[bold green]✅ VISHMUX Setup Complete![/bold green]",
            border_style="green",
            padding=(1,2),
        )
    )

    # ========================================================================
    # STEP 8 — Save and Exit
    # ========================================================================
    config.save()
    await sync_ai_config_to_render(config)
    console.print()
    console.print("[bold green]🚀 Setup complete! Run 'vishmux' to start chatting![/bold green]")
    console.print("[dim]To reconfigure anytime, run: vishmux setup[/dim]")


if __name__ == "__main__":
    asyncio.run(run_setup())
