"""Pitcher Training Bot — Telegram bot entry point.

Uses python-telegram-bot v20+ (async) with long-polling for development.
"""

import logging
import sys
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from bot.config import TELEGRAM_BOT_TOKEN, MINI_APP_URL
from bot.handlers.daily_checkin import get_checkin_handler
from bot.handlers.post_outing import get_outing_handler
from bot.handlers.qa import handle_question

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Hey — I'm your training bot. I manage your lifting, arm care, "
        "plyocare, and recovery programming.\n\n"
        "Commands:\n"
        "/checkin — Morning check-in (arm feel, sleep, energy → today's plan)\n"
        "/outing — Log a post-outing report\n"
        "/status — See your current flags and rotation day\n"
        "/help — What I can do\n\n"
        "Or just ask me a question about your program."
    )


async def help_command(update: Update, context) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "Here's what I do:\n\n"
        "Daily check-in (/checkin): I'll ask how your arm feels, sleep, "
        "and energy. Then I run triage and build your training plan for the day.\n\n"
        "Post-outing (/outing): Log your pitch count, arm feel, and notes "
        "after you throw.\n\n"
        "Q&A: Ask me anything about your program — why you're doing an exercise, "
        "whether you can swap something, what to do on an off day, etc.\n\n"
        "I flag concerns but I don't diagnose. If something feels off, "
        "talk to your trainer."
    )


async def status(update: Update, context) -> None:
    """Handle /status command — show current flags and rotation day."""
    from bot.services.context_manager import load_profile, get_pitcher_id_by_telegram

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return

    profile = load_profile(pitcher_id)
    flags = profile.get("active_flags", {})

    msg = (
        f"Current status:\n"
        f"  Arm feel: {flags.get('current_arm_feel', 'N/A')}/5\n"
        f"  Flag level: {flags.get('current_flag_level', 'unknown').upper()}\n"
        f"  Days since outing: {flags.get('days_since_outing', 'N/A')}\n"
        f"  Last outing: {flags.get('last_outing_pitches', 'N/A')} pitches "
        f"on {flags.get('last_outing_date', 'N/A')}\n"
    )

    mods = flags.get("active_modifications", [])
    if mods:
        msg += f"  Active modifications: {', '.join(mods)}\n"

    await update.message.reply_text(msg)


async def dashboard(update: Update, context) -> None:
    """Handle /dashboard command — open the Mini App."""
    if not MINI_APP_URL:
        await update.message.reply_text(
            "Dashboard isn't configured yet. Set MINI_APP_URL in your environment."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Open Dashboard",
            web_app=WebAppInfo(url=MINI_APP_URL),
        )]
    ])
    await update.message.reply_text(
        "Tap below to open your training dashboard:",
        reply_markup=keyboard,
    )


async def post_init(application: Application) -> None:
    """Set bot commands after startup."""
    commands = [
        BotCommand("checkin", "Morning check-in → today's plan"),
        BotCommand("outing", "Log a post-outing report"),
        BotCommand("status", "Current flags and rotation day"),
        BotCommand("dashboard", "Open training dashboard"),
        BotCommand("help", "What I can do"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Add it to .env")
        sys.exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Handlers — order matters (ConversationHandlers first, then commands, then fallback)
    application.add_handler(get_checkin_handler())
    application.add_handler(get_outing_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("dashboard", dashboard))

    # Fallback: free-text → Q&A handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    logger.info("Bot starting in long-polling mode...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
