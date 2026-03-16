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
]

# Add production URL if set
mini_app_url = os.getenv("MINI_APP_URL")
if mini_app_url:
    ALLOWED_ORIGINS.append(mini_app_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)

import logging
from bot.config import PITCHERS_DIR

_logger = logging.getLogger(__name__)

@app.on_event("startup")
async def _log_pitcher_dirs():
    if os.path.exists(PITCHERS_DIR):
        contents = os.listdir(PITCHERS_DIR)
        _logger.info(f"Pitchers dir contents: {contents}")
    else:
        _logger.warning(f"Pitchers dir not found: {PITCHERS_DIR}")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
