import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "openai/gpt-oss-120b")
WEB_SEARCH_PROVIDER = os.environ.get("WEB_SEARCH_PROVIDER", "").strip().lower()
WEB_SEARCH_KEY = os.environ.get("WEB_SEARCH_KEY", "")
TOLERANCE_MINUTES = int(os.environ.get("TOLERANCE_MINUTES", "10"))
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))