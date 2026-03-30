"""Combined entry point: Telegram bot + FastAPI server in one process.

Railway runs a single service. The bot connects outbound to Telegram (no
port needed) while uvicorn serves the dashboard API on $PORT.
"""

import asyncio
import logging
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from telegram import Update
from telegram.ext import Application

from bot.config import TELEGRAM_BOT_TOKEN
from bot.main import register_handlers, post_init
from api.main import app
from scripts.seed_volume import seed_if_empty

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Seed persistent volume from repo data on first deploy
    seed_if_empty()

    port = int(os.getenv("PORT", 8000))

    # ── Build the Telegram application ──
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Single source of truth for handler registration (bot/main.py)
    register_handlers(application)

    # ── Start both concurrently ──
    await application.initialize()
    await post_init(application)  # post_init only auto-fires via run_polling(), not manual start
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Telegram bot polling started")

    # Run uvicorn on the same event loop
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"Starting API server on 0.0.0.0:{port}")

    try:
        await server.serve()
    finally:
        logger.info("Shutting down...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
