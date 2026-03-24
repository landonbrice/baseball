"""Daily check-in flow using ConversationHandler.

Morning check-in: arm feel → sleep → triage → plan generation → send protocol.
Includes reliever branching and 8+ day outing detection.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.services.checkin_service import process_checkin
from bot.services.context_manager import (
    load_profile,
    load_log,
    save_log,
    append_context,
    get_pitcher_id_by_telegram,
    increment_days_since_outing,
)
from bot.utils import build_rating_keyboard, build_completion_keyboard

logger = logging.getLogger(__name__)

# Conversation states
ARM_FEEL, SLEEP_HOURS, ENERGY, RELIEVER_THREW = range(4)


async def start_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the daily check-in flow."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return ConversationHandler.END

    context.user_data["pitcher_id"] = pitcher_id
    context.user_data["conversation_history"] = []

    # Increment rotation day (skip for return-to-throwing phase)
    profile = load_profile(pitcher_id)
    if profile.get("active_flags", {}).get("phase") != "return_to_throwing":
        increment_days_since_outing(pitcher_id)
        profile = load_profile(pitcher_id)  # Reload after increment
    flags = profile.get("active_flags", {})
    days_since = flags.get("days_since_outing", 0)
    role = profile.get("role", "starter")

    # Fix 7: 8+ days without outing for starters
    if role == "starter" and days_since > 8:
        await update.message.reply_text(
            f"It's been {days_since} days since your last logged outing. "
            "Did you pitch recently? If so, use /outing to log it."
        )

    # Fix 6: Reliever "Did you throw?" branch
    if role == "reliever":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes", callback_data="reliever_threw_yes"),
                InlineKeyboardButton("No", callback_data="reliever_threw_no"),
            ]
        ])
        await update.message.reply_text(
            "Did you throw in a game yesterday?",
            reply_markup=keyboard,
        )
        return RELIEVER_THREW

    # Standard flow: arm feel prompt
    reply_markup = build_rating_keyboard("arm_feel")
    await update.message.reply_text(
        "Morning check-in. How's the arm feel today? (1-5)",
        reply_markup=reply_markup,
    )
    return ARM_FEEL


async def reliever_threw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle reliever 'Did you throw?' response."""
    query = update.callback_query
    await query.answer()

    threw = query.data == "reliever_threw_yes"

    if threw:
        await query.edit_message_text(
            "Got it — use /outing to log your appearance, "
            "then come back and /checkin for today's plan."
        )
        return ConversationHandler.END

    await query.edit_message_text("No game appearance yesterday. Let's do your check-in.")

    reply_markup = build_rating_keyboard("arm_feel")
    await query.message.reply_text(
        "How's the arm feel today? (1-5)",
        reply_markup=reply_markup,
    )
    return ARM_FEEL


async def arm_feel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel selection."""
    query = update.callback_query
    await query.answer()

    arm_feel = int(query.data.split("_")[-1])
    context.user_data["arm_feel"] = arm_feel

    await query.edit_message_text(f"Arm feel: {arm_feel}/5. Got it.\n\nHow many hours of sleep last night?")
    return SLEEP_HOURS


async def sleep_hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle sleep hours input."""
    try:
        sleep = float(update.message.text.strip())
        if sleep < 0 or sleep > 24:
            await update.message.reply_text("That doesn't look right. Give me a number between 0 and 24.")
            return SLEEP_HOURS
    except ValueError:
        await update.message.reply_text("Just the number of hours. Like '7' or '6.5'.")
        return SLEEP_HOURS

    context.user_data["sleep_hours"] = sleep

    reply_markup = build_rating_keyboard("energy", emoji_low="😴", emoji_high="⚡")
    await update.message.reply_text(
        f"Sleep: {sleep}h. Overall energy level?",
        reply_markup=reply_markup,
    )
    return ENERGY


async def energy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle energy selection, run triage, generate plan."""
    query = update.callback_query
    await query.answer()

    energy = int(query.data.split("_")[-1])
    context.user_data["energy"] = energy

    pitcher_id = context.user_data["pitcher_id"]
    arm_feel = context.user_data["arm_feel"]
    sleep_hours = context.user_data["sleep_hours"]

    await query.edit_message_text("Running triage and building your plan...")

    try:
        result = await process_checkin(pitcher_id, arm_feel, sleep_hours, energy)

        # Send triage + brief summary
        flag = result["flag_level"].upper()
        brief = result.get("morning_brief") or result.get("triage_reasoning", "")
        await query.message.reply_text(f"{flag} flag. {brief}")

        # Send alerts if any
        for alert in result["alerts"]:
            await query.message.reply_text(f"⚠️ {alert}")

        # Send link to dashboard for full plan details
        from bot.config import MINI_APP_URL
        if MINI_APP_URL:
            from telegram import WebAppInfo
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Open full plan", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await query.message.reply_text(
                "Your plan is ready. Tap below for the full breakdown.",
                reply_markup=keyboard,
            )
        else:
            # Fallback: send narrative if no Mini App URL
            reply_markup = build_completion_keyboard()
            await query.message.reply_text(result["plan_narrative"], reply_markup=reply_markup)

        # Send weekly summary on Sundays
        if result["weekly_summary"]:
            await query.message.reply_text(result["weekly_summary"])

    except Exception as e:
        logger.error(f"Error in check-in flow: {e}", exc_info=True)
        await query.message.reply_text(
            "Something went wrong generating your plan. Try /checkin again, "
            "or let your coach know."
        )

    return ConversationHandler.END


async def plan_completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plan completion button presses (outside ConversationHandler)."""
    query = update.callback_query
    await query.answer()

    pitcher_id = context.user_data.get("pitcher_id")
    action = query.data

    if action == "plan_dashboard":
        from bot.config import MINI_APP_URL
        if MINI_APP_URL:
            from telegram import WebAppInfo
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Open Dashboard",
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )]
            ])
            await query.message.reply_text("Tap to open:", reply_markup=keyboard)
        else:
            await query.message.reply_text("Dashboard not configured yet.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Update today's log entry with completion status
    if pitcher_id:
        _update_log_completion(pitcher_id, action)

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "plan_done":
        await query.message.reply_text("Logged as completed. Nice work.")
    elif action == "plan_skipped":
        # Ask what was skipped for better tracking
        context.user_data["awaiting_skip_details"] = True
        await query.message.reply_text(
            "Logged as partially completed. What did you skip or modify?\n\n"
            "Just a quick note — e.g., 'skipped plyocare, cut lifting short'"
        )


async def skip_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text response about what was skipped after 'Skipped some'."""
    if not context.user_data.get("awaiting_skip_details"):
        return  # Not awaiting skip details — pass through to Q&A
    context.user_data["awaiting_skip_details"] = False

    pitcher_id = context.user_data.get("pitcher_id")
    details = update.message.text.strip()

    if pitcher_id and details:
        # Update today's log entry with skip details
        log = load_log(pitcher_id)
        today = datetime.now().strftime("%Y-%m-%d")
        for entry in reversed(log.get("entries", [])):
            if entry.get("date") == today:
                entry["skip_notes"] = details
                break
        save_log(pitcher_id, log)
        append_context(pitcher_id, "feedback", f"Skipped: {details[:100]}")

    await update.message.reply_text("Got it — noted for your log.")


def _update_log_completion(pitcher_id: str, action: str) -> None:
    """Update the most recent log entry with completion status."""
    log = load_log(pitcher_id)
    entries = log.get("entries", [])
    today = datetime.now().strftime("%Y-%m-%d")
    for entry in reversed(entries):
        if entry.get("date") == today:
            entry["actual_logged"] = "all_done" if action == "plan_done" else "skipped_some"
            break
    save_log(pitcher_id, log)


async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the check-in flow."""
    await update.message.reply_text("Check-in cancelled.")
    return ConversationHandler.END



def get_checkin_handler() -> ConversationHandler:
    """Build and return the ConversationHandler for daily check-in."""
    return ConversationHandler(
        entry_points=[CommandHandler("checkin", start_checkin)],
        states={
            RELIEVER_THREW: [CallbackQueryHandler(
                reliever_threw_callback, pattern=r"^reliever_threw_(yes|no)$"
            )],
            ARM_FEEL: [CallbackQueryHandler(arm_feel_callback, pattern=r"^arm_feel_\d$")],
            SLEEP_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, sleep_hours_handler)],
            ENERGY: [CallbackQueryHandler(energy_callback, pattern=r"^energy_\d$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin)],
    )
