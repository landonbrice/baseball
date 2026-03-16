import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "anthropic"),
    "model": os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"),
    "max_tokens": 1000,
    "temperature": 0.3,
}

MINI_APP_URL = os.getenv("MINI_APP_URL", "")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PITCHERS_DIR = os.path.join(DATA_DIR, "pitchers")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
