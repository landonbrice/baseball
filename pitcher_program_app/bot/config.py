import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "deepseek"),
    "model": os.getenv("LLM_MODEL", "deepseek-chat"),
    "max_tokens": 1000,
    "temperature": 0.7,
}

MINI_APP_URL = os.getenv("MINI_APP_URL", "").rstrip("/")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PITCHERS_DIR = os.environ.get(
    "PITCHERS_VOLUME_DIR",
    os.path.join(DATA_DIR, "pitchers"),
)
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")

CONTEXT_WINDOW_CHARS = 12000  # ~3000 tokens, full context.md untruncated for 12 pitchers

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "").lower() == "true"
