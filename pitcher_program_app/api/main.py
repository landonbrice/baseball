"""FastAPI data API — lightweight sidecar reading the same data/ directory as the bot."""

import os
import sys

# Ensure project root is on path so bot.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router

app = FastAPI(title="Pitcher Dashboard API", version="0.1.0")

# CORS — allow mini-app origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev
    "http://localhost:4173",   # Vite preview
    "https://uchi-baseball-app.vercel.app",
]

# Add production URL if set
mini_app_url = os.getenv("MINI_APP_URL", "").rstrip("/")
if mini_app_url:
    ALLOWED_ORIGINS.append(mini_app_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)

from bot.config import TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, MINI_APP_URL, DISABLE_AUTH


@app.get("/health")
async def health():
    try:
        from bot.services.db import list_pitchers
        pitcher_count = len(list_pitchers())
        supabase_ok = True
    except Exception:
        pitcher_count = 0
        supabase_ok = False
    return {
        "status": "ok",
        "mini_app_url_set": bool(MINI_APP_URL),
        "disable_auth": DISABLE_AUTH,
        "supabase_connected": supabase_ok,
        "pitcher_count": pitcher_count,
        "bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "deepseek_key_set": bool(DEEPSEEK_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
