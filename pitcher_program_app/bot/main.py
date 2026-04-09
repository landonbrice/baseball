"""Pitcher Training Bot — Telegram bot entry point.

Uses python-telegram-bot v20+ (async) with long-polling for development.
Includes scheduled morning check-ins and weekly alerts via APScheduler.
"""

import logging
import sys
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

CHICAGO_TZ = ZoneInfo("America/Chicago")

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.config import TELEGRAM_BOT_TOKEN, MINI_APP_URL
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
    """Handle /start — personalized intro + check-in prompt."""
    from bot.services.context_manager import load_log
    from bot.utils import build_rating_keyboard

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)

    if not pitcher_id:
        await update.message.reply_text(
            "Hey! I'm the UChicago pitching staff bot. "
            "Ask your coach to set you up with a profile, then come back and send /start."
        )
        return

    try:
        profile = load_profile(pitcher_id)
    except Exception:
        await update.message.reply_text("Hey! Something went wrong loading your profile. Try again or ask your coach.")
        return

    first_name = profile.get("name", "").split()[0] or update.effective_user.first_name or "Hey"
    _ensure_pitcher_jobs(context.application, pitcher_id, profile)

    # Build personalized intro
    lines = [f"Hey {first_name}."]

    role = profile.get("role", "pitcher")
    rotation = profile.get("rotation_length", 7)
    throws = profile.get("throws", "")
    role_line = f"{'LHP' if throws == 'left' else 'RHP'} " if throws else ""
    role_line += f"{'starter' if role == 'starter' else 'reliever'}, {rotation}-day rotation"
    lines.append(role_line.capitalize() + ".")

    # Reference most relevant injury
    injuries = profile.get("injury_history", [])
    if injuries:
        primary = injuries[0]
        area = (primary.get("area") or "").replace("_", " ")
        ongoing = primary.get("ongoing_considerations", "")
        if area and ongoing:
            lines.append(f"Your {area} history is factored in — {ongoing.split('.')[0].lower()}.")
        elif area:
            lines.append(f"Your {area} history is on file and adjusted for.")

    # Current rotation position
    flags = profile.get("active_flags", {})
    days = flags.get("days_since_outing", 0)
    if days <= 1:
        lines.append("Day after outing — recovery focus today.")
    elif days > 0:
        lines.append(f"Day {days} of your rotation.")

    intro = " ".join(lines)

    # Check if already checked in today
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    log = load_log(pitcher_id)
    today_entry = next((e for e in log.get("entries", []) if e.get("date") == today_str), None)
    has_plan = today_entry and (
        today_entry.get("plan_narrative")
        or ((today_entry.get("plan_generated") or {}).get("exercise_blocks") or [])
    )

    if has_plan:
        await update.message.reply_text(
            f"{intro}\n\nYou're checked in for today. Ask me anything about your plan, or type /status to see where you're at."
        )
    else:
        await update.message.reply_text(
            f"{intro}\n\nLet's get today's plan — how's the arm feeling?",
            reply_markup=build_rating_keyboard("arm_feel"),
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


async def whoop_command(update: Update, context) -> None:
    """Handle /whoop — link WHOOP or show today's data."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    from bot.services.whoop import is_linked, build_auth_url, get_today_whoop, pull_whoop_data, WHOOPAuthRequired

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text("I don't have a profile for you yet.")
        return

    if not is_linked(pitcher_id):
        try:
            url = build_auth_url(pitcher_id)
            await update.message.reply_text(
                "Connect your WHOOP to get real biometric data in your daily triage.\n\n"
                f"Open this link to authorize:\n{url}"
            )
        except WHOOPAuthRequired as e:
            await update.message.reply_text(str(e))
        return

    # Already linked — show today's data
    try:
        data = get_today_whoop(pitcher_id)
        if not data:
            data = pull_whoop_data(pitcher_id)
        if data:
            lines = ["WHOOP — Today's Data:"]
            if data.get("recovery_score") is not None:
                lines.append(f"  Recovery: {data['recovery_score']}%")
            if data.get("hrv_rmssd") is not None:
                hrv_line = f"  HRV: {data['hrv_rmssd']:.1f}ms"
                if data.get("hrv_7day_avg"):
                    hrv_line += f" (7d avg: {data['hrv_7day_avg']:.1f}ms)"
                lines.append(hrv_line)
            if data.get("sleep_performance") is not None:
                sleep_line = f"  Sleep: {data['sleep_performance']}%"
                if data.get("sleep_hours"):
                    sleep_line += f" ({data['sleep_hours']}h)"
                lines.append(sleep_line)
            if data.get("yesterday_strain") is not None:
                lines.append(f"  Strain: {data['yesterday_strain']:.1f}")
            await update.message.reply_text("\n".join(lines))
        else:
            await update.message.reply_text("WHOOP is connected but no data available yet for today.")
    except WHOOPAuthRequired:
        url = build_auth_url(pitcher_id)
        await update.message.reply_text(
            "Your WHOOP connection expired. Re-authorize here:\n" + url
        )
    except Exception as e:
        logger.error("WHOOP data pull failed for %s: %s", pitcher_id, e)
        await update.message.reply_text("Couldn't pull WHOOP data right now. Try again later.")


async def test_notify(update: Update, context) -> None:
    """Handle /testnotify — manually trigger morning check-in notification."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text("No profile found.")
        return
    # Simulate the scheduled job by creating a fake job context
    class FakeJob:
        def __init__(self, data):
            self.data = data
    context.job = FakeJob({"pitcher_id": pitcher_id, "chat_id": update.effective_chat.id})
    await _send_morning_checkin(context)


async def whooptest(update: Update, context) -> None:
    """Handle /whooptest — force fresh WHOOP pull, show all raw results for debugging."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    from bot.services.whoop import is_linked, pull_whoop_data, WHOOPAuthRequired

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text("No profile found.")
        return

    if not is_linked(pitcher_id):
        await update.message.reply_text("WHOOP not linked. Use /whoop to connect.")
        return

    await update.message.reply_text("Pulling fresh WHOOP data (force_refresh)...")

    try:
        data = pull_whoop_data(pitcher_id, force_refresh=True)
        if not data:
            await update.message.reply_text("WHOOP returned no data. Check Railway logs for details.")
            return

        lines = ["WHOOP Force-Pull Results:"]
        fields = [
            ("recovery_score", "Recovery"),
            ("hrv_rmssd", "HRV"),
            ("hrv_7day_avg", "HRV 7d avg"),
            ("sleep_performance", "Sleep %"),
            ("sleep_hours", "Sleep hrs"),
            ("yesterday_strain", "Strain"),
        ]
        for key, label in fields:
            val = data.get(key)
            status = f"{val}" if val is not None else "NULL"
            lines.append(f"  {label}: {status}")

        # Show raw_data keys for debugging
        raw = data.get("raw_data") or {}
        raw_summary = []
        for endpoint in ("recovery", "sleep", "cycles"):
            raw_val = raw.get(endpoint)
            if raw_val:
                raw_summary.append(f"{endpoint}=OK")
            else:
                raw_summary.append(f"{endpoint}=None")
        lines.append(f"\n  Raw endpoints: {', '.join(raw_summary)}")

        await update.message.reply_text("\n".join(lines))
    except WHOOPAuthRequired:
        await update.message.reply_text("WHOOP auth expired. Use /whoop to reconnect.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        logger.error("whooptest failed for %s: %s", pitcher_id, e, exc_info=True)


async def reauth_whoop(update: Update, context) -> None:
    """Handle /reauth — force re-link WHOOP."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    from bot.services.whoop import build_auth_url, WHOOPAuthRequired

    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text("I don't have a profile for you yet.")
        return

    try:
        url = build_auth_url(pitcher_id)
        await update.message.reply_text(f"Re-authorize WHOOP here:\n{url}")
    except WHOOPAuthRequired as e:
        await update.message.reply_text(str(e))


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
    today = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
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


ADMIN_TELEGRAM_IDS = [8589499360]  # Landon


async def refresh_schedule(update: Update, context) -> None:
    """Handle /refreshschedule — scrape UChicago schedule and update DB."""
    if update.effective_user.id not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("Admin only.")
        return

    await update.message.reply_text("Scraping schedule...")
    try:
        from scripts.scrape_schedule import scrape_and_store
        count = scrape_and_store()
        await update.message.reply_text(f"Done — {count} games upserted.")
    except Exception as e:
        logger.error("Schedule scrape failed: %s", e)
        await update.message.reply_text(f"Failed: {e}")


async def backup_command(update: Update, context) -> None:
    """Handle /backup — admin only. Show data status from Supabase."""
    if update.effective_user.id not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("Admin only.")
        return

    try:
        from bot.services.db import list_pitchers, get_daily_entries
        pitchers = list_pitchers()
        pitcher_count = len(pitchers)
        pitchers_with_id = sum(1 for p in pitchers if p.get("telegram_id"))
        total_entries = 0
        for p in pitchers:
            entries = get_daily_entries(p["pitcher_id"], limit=100)
            total_entries += len(entries)
    except Exception as e:
        await update.message.reply_text(f"Error reading from Supabase: {e}")
        return

    await update.message.reply_text(
        f"Data status (Supabase):\n"
        f"  Pitchers: {pitcher_count} ({pitchers_with_id} with telegram_id)\n"
        f"  Total log entries: {total_entries}\n"
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
    """Send a contextual morning check-in — personal, not structural."""
    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    from bot.utils import build_rating_keyboard
    from bot.services.context_manager import load_profile, load_log
    reply_markup = build_rating_keyboard("arm_feel")

    try:
        profile = load_profile(pitcher_id)
        first_name = profile.get("name", "").split()[0] or "Hey"
        flags = profile.get("active_flags", {})
        days = flags.get("days_since_outing", 0)
        rotation_len = profile.get("rotation_length", 7)

        # Yesterday's data
        log = load_log(pitcher_id)
        entries = log.get("entries", [])
        yesterday = (datetime.now(CHICAGO_TZ).date() - timedelta(days=1)).isoformat()
        yesterday_entry = next((e for e in entries if e.get("date") == yesterday), None)

        lines = []

        # Line 1: Personal context
        if days <= 1:
            pitches = flags.get("last_outing_pitches")
            if pitches:
                lines.append(f"{first_name} — day after, {pitches} pitches yesterday. Recovery day.")
            else:
                lines.append(f"{first_name} — day after your outing. Recovery focus.")
        elif days == 2:
            lines.append(f"{first_name} — day 2 post-outing. Body should be bouncing back.")
        elif days >= rotation_len - 1:
            lines.append(f"{first_name} — start day approaching. Keeping it light.")
        elif yesterday_entry and (yesterday_entry.get("pre_training") or {}).get("arm_feel"):
            yest_feel = yesterday_entry["pre_training"]["arm_feel"]
            if yest_feel >= 4:
                lines.append(f"{first_name} — arm felt good yesterday ({yest_feel}/5). Let's keep it rolling.")
            elif yest_feel == 3:
                lines.append(f"{first_name} — arm was a 3 yesterday. Let's see where you're at today.")
            else:
                lines.append(f"{first_name} — arm was at {yest_feel} yesterday. Checking in on that.")
        else:
            lines.append(f"{first_name} — day {days}, let's get your plan set.")

        # Line 2: WHOOP context (conversational) — fresh pull, not just cache
        try:
            from bot.services.whoop import pull_whoop_data, is_linked
            wd = pull_whoop_data(pitcher_id) if is_linked(pitcher_id) else None
            if wd and wd.get("recovery_score") is not None:
                rec = wd["recovery_score"]
                if rec >= 67:
                    lines.append(f"WHOOP has you at {rec}% recovery — green light.")
                elif rec >= 34:
                    lines.append(f"WHOOP recovery at {rec}% — I'll factor that into your plan.")
                else:
                    lines.append(f"WHOOP recovery low at {rec}% — dialing things back today.")
            elif wd and wd.get("yesterday_strain") is not None:
                lines.append(f"Yesterday's strain: {wd['yesterday_strain']:.1f}")
        except Exception:
            pass

        # Next-day suggestion (proactive coaching)
        try:
            from bot.services.db import get_training_model
            model = get_training_model(pitcher_id)
            suggestion = (model.get("current_week_state") or {}).get("next_day_suggestion") or {}
            confidence = suggestion.get("confidence", "low")
            reasoning = suggestion.get("reasoning", "")
            if confidence == "high" and reasoning:
                lines.append(f"{reasoning}.")
            elif confidence == "medium" and reasoning:
                lines.append(f"Thinking {reasoning.lower()}.")
        except Exception:
            pass

        lines.append("")
        lines.append("How's the arm? (1-5)")
        msg = "\n".join(lines)
    except Exception:
        msg = "Morning — how's the arm? (1-5)"

    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup)


async def _send_evening_followup(context) -> None:
    """Send 6pm nudge if morning check-in was sent but not completed today."""
    from bot.services.context_manager import load_log

    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    log = load_log(pitcher_id)
    today = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    # Check if there's a check-in entry for today
    has_checkin = any(
        entry.get("date") == today and entry.get("pre_training") is not None
        for entry in log.get("entries", [])
    )

    if not has_checkin:
        await context.bot.send_message(
            chat_id=chat_id,
            text="No check-in today — resting or just busy? "
                 "Tap /checkin if you still want a plan, otherwise I'll catch you tomorrow.",
        )


async def _send_weekly_summary(context) -> None:
    """Send Sunday evening weekly summary to all pitchers."""
    from bot.services.db import list_pitchers
    from bot.services.progression import analyze_progression, generate_weekly_narrative

    try:
        pitchers = list_pitchers()
    except Exception as e:
        logger.error(f"Failed to load pitchers for weekly summary: {e}")
        return

    for pitcher in pitchers:
        pitcher_id = pitcher["pitcher_id"]
        chat_id = pitcher.get("telegram_id")
        if not chat_id:
            continue

        try:
            # Try LLM narrative first, fall back to stats summary
            result = await generate_weekly_narrative(pitcher_id)
            if result and result.get("narrative"):
                headline = result.get("headline", "")
                text = f"📊 {headline}\n\n{result['narrative']}" if headline else result["narrative"]
                await context.bot.send_message(chat_id=chat_id, text=text)
            else:
                # Fallback to stats-only summary
                progression = analyze_progression(pitcher_id)
                summary = progression.get("weekly_summary")
                if summary:
                    await context.bot.send_message(chat_id=chat_id, text=summary)
        except Exception as e:
            logger.error(f"Error sending weekly summary to {pitcher_id}: {e}")


def _ensure_pitcher_jobs(application: Application, pitcher_id: str, profile: dict) -> None:
    """Ensure morning check-in and evening follow-up jobs exist for a pitcher.

    Called on /start to handle newly backfilled telegram_ids without restart.
    """
    job_queue = application.job_queue
    if not job_queue:
        return

    chat_id = profile.get("telegram_id")
    if not chat_id:
        return

    # Check if jobs already scheduled
    existing = job_queue.get_jobs_by_name(f"morning_checkin_{pitcher_id}")
    if existing:
        return

    time_str = (profile.get("preferences") or {}).get("notification_time", "08:00")
    try:
        hour, minute = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 8, 0
    notify_time = dt_time(hour=hour, minute=minute, tzinfo=CHICAGO_TZ)

    job_queue.run_daily(
        _send_morning_checkin, time=notify_time,
        data={"pitcher_id": pitcher_id, "chat_id": chat_id},
        name=f"morning_checkin_{pitcher_id}",
    )
    job_queue.run_daily(
        _send_evening_followup, time=dt_time(hour=18, minute=0, tzinfo=CHICAGO_TZ),
        data={"pitcher_id": pitcher_id, "chat_id": chat_id},
        name=f"evening_followup_{pitcher_id}",
    )
    logger.info(f"Dynamically scheduled jobs for {pitcher_id} at {time_str} Chicago time")


async def _pull_all_whoop(context) -> None:
    """Daily 6am job: pull WHOOP data for all linked pitchers."""
    from bot.services.db import list_whoop_linked_pitchers, get_pitcher
    from bot.services.whoop import pull_whoop_data, WHOOPAuthRequired

    linked = list_whoop_linked_pitchers()
    if not linked:
        return

    for pitcher_id in linked:
        try:
            pull_whoop_data(pitcher_id)
            logger.info("WHOOP data pulled for %s", pitcher_id)
        except WHOOPAuthRequired:
            # Notify pitcher to re-link
            try:
                pitcher = get_pitcher(pitcher_id)
                chat_id = pitcher.get("telegram_id")
                if chat_id:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Your WHOOP connection has expired. Use /whoop to reconnect.",
                    )
            except Exception:
                pass
            logger.warning("WHOOP auth expired for %s", pitcher_id)
        except Exception as e:
            logger.error("WHOOP pull failed for %s: %s", pitcher_id, e)


async def _send_health_digest(context) -> None:
    """Daily 9am Chicago health digest sent to the admin chat_id.

    Queries degradation signals from Supabase and posts a formatted summary.
    Never raises — monitoring should never crash the scheduler.
    """
    try:
        from bot.services.health_monitor import compute_daily_digest, format_digest_message
        from bot.config import ADMIN_TELEGRAM_CHAT_ID

        digest = compute_daily_digest()
        message = format_digest_message(digest)

        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info("Health digest sent to admin chat_id=%s", ADMIN_TELEGRAM_CHAT_ID)
    except Exception as e:
        logger.error("Failed to send health digest: %s", e, exc_info=True)


async def health_digest_command(update, context):
    """Admin-only: force-send the health digest right now. Dev/test use."""
    from bot.config import ADMIN_TELEGRAM_CHAT_ID
    if update.effective_chat.id != ADMIN_TELEGRAM_CHAT_ID:
        await update.message.reply_text("This command is admin-only.")
        return
    await _send_health_digest(context)
    await update.message.reply_text("Digest sent.")


async def test_emergency_command(update, context):
    """Admin-only: simulate 3 matching failures and fire an emergency alert.

    Uses a TEST marker in the source_reason so it won't collide with real
    incidents. Respects dedup — call twice in a 2hr window and the second
    call is silently skipped (that's expected behavior).
    """
    from bot.config import ADMIN_TELEGRAM_CHAT_ID
    if update.effective_chat.id != ADMIN_TELEGRAM_CHAT_ID:
        await update.message.reply_text("This command is admin-only.")
        return

    from bot.services.health_monitor import (
        record_and_check_emergency, format_emergency_alert,
    )
    # Simulate 3 failures of the same pattern
    alert = None
    for _ in range(3):
        alert = record_and_check_emergency(
            "llm_assembly_error:APIStatusError: TEST emergency from /testemergency",
            "test_pitcher",
        )

    if alert:
        message = format_emergency_alert(alert)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text(
            "Emergency check returned None. "
            "Likely dedup — pattern was already alerted within the last 2h. "
            "Wait or restart the Railway deploy to clear in-memory state."
        )


def _schedule_jobs(application: Application) -> None:
    """Set up scheduled jobs for morning check-ins and weekly summaries.

    Reads pitcher data from Supabase (not filesystem) so newly added
    pitchers get notifications without needing JSON files on Railway.
    """
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue not available — scheduled jobs disabled")
        return

    # Schedule morning check-ins for each pitcher from Supabase
    try:
        from bot.services.db import list_pitchers
        pitchers = list_pitchers()
    except Exception as e:
        logger.error(f"Failed to load pitchers from Supabase for scheduling: {e}")
        pitchers = []

    scheduled_count = 0
    for pitcher in pitchers:
        pitcher_id = pitcher["pitcher_id"]
        chat_id = pitcher.get("telegram_id")
        if not chat_id:
            continue

        try:
            # Parse notification time (default 08:00) — all times in Chicago
            prefs = pitcher.get("preferences") or {}
            time_str = prefs.get("notification_time", "08:00")
            try:
                hour, minute = map(int, time_str.split(":"))
            except (ValueError, AttributeError):
                hour, minute = 8, 0
            notify_time = dt_time(hour=hour, minute=minute, tzinfo=CHICAGO_TZ)

            job_queue.run_daily(
                _send_morning_checkin,
                time=notify_time,
                data={"pitcher_id": pitcher_id, "chat_id": chat_id},
                name=f"morning_checkin_{pitcher_id}",
            )

            # 6pm follow-up if check-in unanswered (Chicago time)
            job_queue.run_daily(
                _send_evening_followup,
                time=dt_time(hour=18, minute=0, tzinfo=CHICAGO_TZ),
                data={"pitcher_id": pitcher_id, "chat_id": chat_id},
                name=f"evening_followup_{pitcher_id}",
            )
            scheduled_count += 1
        except Exception as e:
            logger.error(f"Error scheduling job for {pitcher_id}: {e}")

    logger.info(f"Scheduled morning + evening jobs for {scheduled_count} pitchers (from Supabase)")

    # Schedule Sunday 6pm weekly summary (Chicago time)
    job_queue.run_daily(
        _send_weekly_summary,
        time=dt_time(hour=18, minute=0, tzinfo=CHICAGO_TZ),
        days=(6,),  # Sunday = 6
        name="weekly_summary",
    )
    logger.info("Scheduled Sunday 6pm Chicago weekly summary")

    # Daily 6am WHOOP pull for all linked pitchers
    job_queue.run_daily(
        _pull_all_whoop,
        time=dt_time(hour=6, minute=0, tzinfo=CHICAGO_TZ),
        name="daily_whoop_pull",
    )
    logger.info("Scheduled daily 6am WHOOP pull")

    # Post-game reliever check — runs at 11pm on game days
    async def _post_game_reliever_check(context):
        """Check if relievers appeared in today's game and prompt if unreported."""
        try:
            from bot.services.game_scraper import prompt_relievers_after_game
            await prompt_relievers_after_game(context.bot)
        except Exception as e:
            logger.error(f"Post-game reliever check failed: {e}")

    job_queue.run_daily(
        _post_game_reliever_check,
        time=dt_time(hour=23, minute=0, tzinfo=CHICAGO_TZ),
        name="post_game_reliever_check",
    )
    logger.info("Scheduled daily 11pm post-game reliever check")

    # Daily health digest — 9am Chicago
    job_queue.run_daily(
        _send_health_digest,
        time=dt_time(hour=9, minute=0, tzinfo=CHICAGO_TZ),
        name="health_digest_daily",
    )
    logger.info("Scheduled daily health digest for 9:00 AM Chicago time")


async def post_init(application: Application) -> None:
    """Set bot commands and schedule jobs after startup."""
    commands = [
        BotCommand("checkin", "Morning check-in → today's plan"),
        BotCommand("outing", "Log a post-outing report"),
        BotCommand("status", "Current flags and rotation day"),
        BotCommand("setday", "Set rotation day manually"),
        BotCommand("gamestart", "Start game — get outing reminder in 2hrs"),
        BotCommand("whoop", "Link WHOOP or view today's biometrics"),
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


def register_handlers(application) -> None:
    """Register all bot handlers. Called by both main.py and run.py entry points.

    Order matters: ConversationHandlers first, then commands, then fallback.
    Add new commands HERE — this is the single source of truth.
    """
    application.add_handler(get_checkin_handler())
    application.add_handler(get_outing_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("setday", setday))
    application.add_handler(CommandHandler("whoop", whoop_command))
    application.add_handler(CommandHandler("reauth", reauth_whoop))
    application.add_handler(CommandHandler("whooptest", whooptest))
    application.add_handler(CommandHandler("testnotify", test_notify))
    application.add_handler(CommandHandler("healthdigest", health_digest_command))
    application.add_handler(CommandHandler("testemergency", test_emergency_command))
    application.add_handler(CommandHandler("gamestart", gamestart))
    application.add_handler(CommandHandler("dashboard", dashboard))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("refreshschedule", refresh_schedule))
    application.add_handler(CallbackQueryHandler(
        plan_completion_callback, pattern=r"^plan_(done|skipped|dashboard)$"
    ))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text_dispatcher))


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Add it to .env")
        sys.exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    register_handlers(application)

    logger.info("Bot starting in long-polling mode...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
