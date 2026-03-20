"""Pitcher Training Bot — Telegram bot entry point.

Uses python-telegram-bot v20+ (async) with long-polling for development.
Includes scheduled morning check-ins and weekly alerts via APScheduler.
"""

import logging
import os
import sys
from datetime import datetime, time as dt_time

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.config import TELEGRAM_BOT_TOKEN, MINI_APP_URL, PITCHERS_DIR
from bot.handlers.daily_checkin import get_checkin_handler, plan_completion_callback, skip_details_handler
from bot.handlers.post_outing import get_outing_handler
from bot.handlers.qa import handle_question
from bot.services.context_manager import load_profile, get_pitcher_id_by_telegram

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context) -> None:
    """Handle /start command."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    first_name = update.effective_user.first_name or "there"
    if pitcher_id:
        try:
            profile = load_profile(pitcher_id)
            first_name = profile.get("name", first_name).split()[0]
        except Exception:
            pass

    await update.message.reply_text(
        f"Hey {first_name}. Here's what I've got:\n\n"
        "/checkin — arm feel, sleep → today's plan\n"
        "/outing — log a post-outing report\n"
        "/status — current flags and rotation day\n"
        "/gamestart — game today? I'll remind you after\n\n"
        "Or just ask me anything."
    )


async def help_command(update: Update, context) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "Here's what I do:\n\n"
        "Daily check-in (/checkin): I'll ask how your arm feels, sleep, "
        "and energy. Then I run triage and build your training plan for the day.\n\n"
        "Post-outing (/outing): Log your pitch count, arm feel, and notes "
        "after you throw.\n\n"
        "Set rotation day (/setday <N>): Manually correct your rotation day. "
        "Example: /setday 3\n\n"
        "Q&A: Ask me anything about your program — why you're doing an exercise, "
        "whether you can swap something, what to do on an off day, etc.\n\n"
        "I flag concerns but I don't diagnose. If something feels off, "
        "talk to your trainer."
    )


async def status(update: Update, context) -> None:
    """Handle /status command — show current flags and rotation day."""
    from bot.services.context_manager import load_profile, get_pitcher_id_by_telegram

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
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


async def setday(update: Update, context) -> None:
    """Handle /setday command — manually set rotation day."""
    from bot.services.context_manager import update_active_flags, get_pitcher_id_by_telegram

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /setday <number>\nExample: /setday 3")
        return

    day = int(args[0])
    update_active_flags(pitcher_id, {"days_since_outing": day})
    await update.message.reply_text(f"Rotation day set to Day {day}.")


async def gamestart(update: Update, context) -> None:
    """Handle /gamestart — schedule a 2hr post-outing reminder."""
    from bot.services.context_manager import get_pitcher_id_by_telegram

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return

    job_queue = context.application.job_queue
    if job_queue is None:
        await update.message.reply_text("Scheduling isn't available right now.")
        return

    # Remove any existing game reminder for this pitcher
    job_name = f"post_outing_reminder_{pitcher_id}"
    current_jobs = job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    # Schedule 2-hour delayed reminder
    job_queue.run_once(
        _send_post_outing_reminder,
        when=7200,  # 2 hours in seconds
        data={"pitcher_id": pitcher_id, "chat_id": update.effective_chat.id},
        name=job_name,
    )

    await update.message.reply_text(
        "Got it — game starting. I'll remind you to log your outing in about 2 hours.\n\n"
        "You can always use /outing any time to log it earlier."
    )


async def _send_post_outing_reminder(context) -> None:
    """Send a reminder to log outing data ~2hrs after game start."""
    from bot.services.context_manager import load_log

    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    # Check if they already logged an outing today
    log = load_log(pitcher_id)
    today = datetime.now().strftime("%Y-%m-%d")
    has_outing = any(
        entry.get("date") == today and entry.get("outing") is not None
        for entry in log.get("entries", [])
    )

    if not has_outing:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Game should be wrapping up. Ready to log your outing?\n\n"
                 "Type /outing to record your pitch count, arm feel, and notes.",
        )


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


# --- Scheduled jobs ---

async def _send_morning_checkin(context) -> None:
    """Send a morning check-in prompt to a pitcher."""
    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    from bot.utils import build_rating_keyboard
    reply_markup = build_rating_keyboard("arm_feel")

    await context.bot.send_message(
        chat_id=chat_id,
        text="Morning check-in time. How's the arm feel today? (1-5)\n\n"
             "Or type /checkin to start the full flow.",
        reply_markup=reply_markup,
    )


async def _send_evening_followup(context) -> None:
    """Send 6pm nudge if morning check-in was sent but not completed today."""
    from bot.services.context_manager import load_log

    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    log = load_log(pitcher_id)
    today = datetime.now().strftime("%Y-%m-%d")

    # Check if there's a check-in entry for today
    has_checkin = any(
        entry.get("date") == today and entry.get("pre_training") is not None
        for entry in log.get("entries", [])
    )

    if not has_checkin:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Hey — you didn't check in this morning. Still want to get today's plan?\n\n"
                 "Type /checkin to start, or skip if you're resting today.",
        )


async def _send_weekly_summary(context) -> None:
    """Send Sunday evening weekly summary to all pitchers."""
    from bot.services.context_manager import load_profile
    from bot.services.progression import analyze_progression

    if not os.path.exists(PITCHERS_DIR):
        return

    for entry in os.listdir(PITCHERS_DIR):
        profile_path = os.path.join(PITCHERS_DIR, entry, "profile.json")
        if not os.path.exists(profile_path):
            continue

        try:
            profile = load_profile(entry)
            chat_id = profile.get("telegram_id")
            if not chat_id:
                continue

            progression = analyze_progression(entry)
            summary = progression.get("weekly_summary")
            if summary:
                await context.bot.send_message(chat_id=chat_id, text=summary)
        except Exception as e:
            logger.error(f"Error sending weekly summary to {entry}: {e}")


def _schedule_jobs(application: Application) -> None:
    """Set up scheduled jobs for morning check-ins and weekly summaries."""
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue not available — scheduled jobs disabled")
        return

    # Schedule morning check-ins for each pitcher
    if os.path.exists(PITCHERS_DIR):
        import json
        for entry in os.listdir(PITCHERS_DIR):
            profile_path = os.path.join(PITCHERS_DIR, entry, "profile.json")
            if not os.path.exists(profile_path):
                continue
            try:
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                chat_id = profile.get("telegram_id")
                if not chat_id:
                    continue

                # Parse notification time (default 08:00)
                time_str = profile.get("preferences", {}).get("notification_time", "08:00")
                hour, minute = map(int, time_str.split(":"))
                notify_time = dt_time(hour=hour, minute=minute)

                job_queue.run_daily(
                    _send_morning_checkin,
                    time=notify_time,
                    data={"pitcher_id": entry, "chat_id": chat_id},
                    name=f"morning_checkin_{entry}",
                )
                logger.info(f"Scheduled morning check-in for {entry} at {time_str}")

                # Phase 3a: 6pm follow-up if check-in unanswered
                job_queue.run_daily(
                    _send_evening_followup,
                    time=dt_time(hour=18, minute=0),
                    data={"pitcher_id": entry, "chat_id": chat_id},
                    name=f"evening_followup_{entry}",
                )
                logger.info(f"Scheduled 6pm follow-up for {entry}")
            except Exception as e:
                logger.error(f"Error scheduling job for {entry}: {e}")

    # Schedule Sunday 6pm weekly summary
    job_queue.run_daily(
        _send_weekly_summary,
        time=dt_time(hour=18, minute=0),
        days=(6,),  # Sunday = 6
        name="weekly_summary",
    )
    logger.info("Scheduled Sunday 6pm weekly summary")


async def post_init(application: Application) -> None:
    """Set bot commands and schedule jobs after startup."""
    commands = [
        BotCommand("checkin", "Morning check-in → today's plan"),
        BotCommand("outing", "Log a post-outing report"),
        BotCommand("status", "Current flags and rotation day"),
        BotCommand("setday", "Set rotation day manually"),
        BotCommand("gamestart", "Start game — get outing reminder in 2hrs"),
        BotCommand("dashboard", "Open training dashboard"),
        BotCommand("help", "What I can do"),
    ]
    await application.bot.set_my_commands(commands)

    _schedule_jobs(application)


async def _text_dispatcher(update: Update, context) -> None:
    """Route free-text to skip details handler if awaiting, else Q&A."""
    if context.user_data.get("awaiting_skip_details"):
        await skip_details_handler(update, context)
    else:
        await handle_question(update, context)


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
    application.add_handler(CommandHandler("setday", setday))
    application.add_handler(CommandHandler("gamestart", gamestart))
    application.add_handler(CommandHandler("dashboard", dashboard))

    # Fix 3: Plan completion callbacks (outside conversation handler)
    application.add_handler(CallbackQueryHandler(
        plan_completion_callback, pattern=r"^plan_(done|skipped|dashboard)$"
    ))

    # Fallback: free-text → skip details (if awaiting) or Q&A handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text_dispatcher))

    logger.info("Bot starting in long-polling mode...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
