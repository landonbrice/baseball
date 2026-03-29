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
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers.daily_checkin import get_checkin_handler, plan_completion_callback, skip_details_handler
from bot.handlers.post_outing import get_outing_handler
from bot.handlers.qa import handle_question
from bot.main import (
    start, help_command, status, setday, gamestart, dashboard,
    backup_command, whoop_command, reauth_whoop, post_init, _text_dispatcher,
)
from api.main import app
from scripts.seed_volume import seed_if_empty
# data_sync disabled — Supabase is now the source of truth (Phase 1 migration complete)
# from scripts.data_sync import start_sync

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

    # Data sync disabled — Supabase is now the source of truth
    # start_sync()

    port = int(os.getenv("PORT", 8000))

    # ── Build the Telegram application ──
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register handlers (same order as bot/main.py)
    application.add_handler(get_checkin_handler())
    application.add_handler(get_outing_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("setday", setday))
    application.add_handler(CommandHandler("whoop", whoop_command))
    application.add_handler(CommandHandler("reauth", reauth_whoop))
    application.add_handler(CommandHandler("gamestart", gamestart))
    application.add_handler(CommandHandler("dashboard", dashboard))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CallbackQueryHandler(
        plan_completion_callback, pattern=r"^plan_(done|skipped|dashboard)$"
    ))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text_dispatcher))

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
