# cli/config.py
import json
from pathlib import Path
from typing import Optional, Tuple


class Config:
    """Manages the VISHMUX agent configuration file."""

    def __init__(self) -> None:
        self.config_dir = Path.home() / ".vishmux"
        self.config_path = self.config_dir / "config.json"
        self.data = self._defaults()

    def _defaults(self) -> dict:
        return {
            "providers": {
                "openrouter": {"api_key": "", "default_model": "", "enabled": False},
                "groq": {"api_key": "", "default_model": "", "enabled": False},
                "nvidia": {"api_key": "", "default_model": "", "enabled": False},
                "gemini": {"api_key": "", "default_model": "", "enabled": False},
                "together": {"api_key": "", "default_model": "", "enabled": False},
                "mistral": {"api_key": "", "default_model": "", "enabled": False},
                "anthropic": {"api_key": "", "default_model": "", "enabled": False},
                "perplexity": {"api_key": "", "default_model": "", "enabled": False},
            },
            "active_provider": "",
            "active_model": "",
            "telegram_provider": {"name": "", "model": ""},
            "telegram_mode": "hybrid",
            "telegram": {"bot_token": "", "chat_id": "", "enabled": False},
            "supabase": {"url": "", "key": "", "configured": False},
            "timezone": "",
            "workspace_dir": "~/vishmux-workspace",
            "skills_dir": "~/.vishmux/skills",
            "sessions_dir": "~/.vishmux/sessions",
            "web_search_key": "",
            "web_search_provider": "",
        }

    def load(self) -> None:
        """Load config from disk, falling back to defaults if missing or corrupt."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    loaded = json.load(f)
                self._update_dict(self.data, loaded)
            except (json.JSONDecodeError, Exception):
                pass
        else:
            self.save()

    def save(self) -> None:
        """Persist current config to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_active_provider(self) -> Optional[Tuple[str, str]]:
        """Return (provider_name, model) or None."""
        if self.data["active_provider"] and self.data["active_model"]:
            return self.data["active_provider"], self.data["active_model"]
        return None

    def set_active_provider(self, name: str, model: str) -> None:
        """Set the active provider and mark it enabled."""
        if name in self.data["providers"]:
            self.data["active_provider"] = name
            self.data["active_model"] = model
            self.data["providers"][name]["enabled"] = True
            self.save()

    def get_telegram_provider(self) -> Optional[Tuple[str, str]]:
        """Return the (provider_name, model) that should answer Telegram and
        scheduled-task messages. Falls back to the interactive active_provider
        if no separate Telegram provider has ever been explicitly set — so
        behavior is unchanged for anyone who never uses this feature."""
        tg = self.data.get("telegram_provider", {})
        if tg.get("name") and tg.get("model"):
            return tg["name"], tg["model"]
        return self.get_active_provider()

    def set_telegram_provider(self, name: str, model: str) -> None:
        """Explicitly set a provider for Telegram/scheduled replies, kept
        separate from whatever the user picks as their interactive chat
        provider via set_active_provider."""
        if name in self.data["providers"]:
            self.data["telegram_provider"] = {"name": name, "model": model}
            self.save()

    def get_telegram_mode(self) -> str:
        """Return how Telegram messages should be answered: 'hybrid' (Termux
        first, Render fallback — default), 'termux_only' (only Termux answers;
        a fixed offline message otherwise), or 'render_only' (Render always
        answers immediately, Termux never claims)."""
        return self.data.get("telegram_mode", "hybrid")

    def set_telegram_mode(self, mode: str) -> None:
        """Set the Telegram reply mode. Silently ignores invalid values."""
        if mode in ("hybrid", "termux_only", "render_only"):
            self.data["telegram_mode"] = mode
            self.save()

    def is_setup_done(self) -> bool:
        """True if at least one provider has an API key."""
        return any(p.get("api_key") for p in self.data["providers"].values())

    def is_supabase_configured(self) -> bool:
        """True if both Supabase URL and key are set."""
        return bool(self.data["supabase"]["url"] and self.data["supabase"]["key"])

    def _update_dict(self, target: dict, source: dict) -> None:
        """Recursively update target with values from source for matching keys."""
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._update_dict(target[key], value)
                else:
                    target[key] = value