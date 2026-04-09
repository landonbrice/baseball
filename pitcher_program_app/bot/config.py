import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "deepseek"),
    "model": os.getenv("LLM_MODEL", "deepseek-chat"),
    "model_reasoning": os.getenv("LLM_MODEL_REASONING", "deepseek-reasoner"),
    "max_tokens": 1000,
    "temperature": 0.7,
}

MINI_APP_URL = os.getenv("MINI_APP_URL", "").rstrip("/")

# Admin Telegram chat_id for health monitoring alerts.
# Defaults to Landon Brice (8589499360) — override in Railway env if needed.
ADMIN_TELEGRAM_CHAT_ID = int(os.getenv("ADMIN_TELEGRAM_CHAT_ID", "8589499360"))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PITCHERS_DIR = os.environ.get(
    "PITCHERS_VOLUME_DIR",
    os.path.join(DATA_DIR, "pitchers"),
)
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")

CONTEXT_WINDOW_CHARS = 12000  # ~3000 tokens, full context.md untruncated for 12 pitchers

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "").lower() == "true"

# Timezone — all pitchers are in Chicago
CHICAGO_TZ = ZoneInfo("America/Chicago")

# WHOOP OAuth
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID", "")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET", "")
WHOOP_REDIRECT_URI = os.getenv(
    "WHOOP_REDIRECT_URI",
    "https://baseball-production-9d28.up.railway.app/api/whoop/callback",
)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
