"""Daily check-in flow using ConversationHandler.

Morning check-in: arm feel → sleep → triage → plan generation → send protocol.
"""

import json
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
from bot.services.triage import triage
from bot.services.plan_generator import generate_plan
from bot.services.progression import analyze_progression
from bot.services.context_manager import (
    load_profile,
    append_context,
    append_log_entry,
    get_pitcher_id_by_telegram,
)

logger = logging.getLogger(__name__)

# Conversation states
ARM_FEEL, SLEEP_HOURS, ENERGY = range(3)


async def start_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the daily check-in flow."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return ConversationHandler.END

    context.user_data["pitcher_id"] = pitcher_id

    # Arm feel keyboard (1-5)
    keyboard = [
        [
            InlineKeyboardButton("1 💀", callback_data="arm_feel_1"),
            InlineKeyboardButton("2", callback_data="arm_feel_2"),
            InlineKeyboardButton("3", callback_data="arm_feel_3"),
            InlineKeyboardButton("4", callback_data="arm_feel_4"),
            InlineKeyboardButton("5 💪", callback_data="arm_feel_5"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Morning check-in. How's the arm feel today? (1-5)",
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

    # Energy keyboard (1-5)
    keyboard = [
        [
            InlineKeyboardButton("1 😴", callback_data="energy_1"),
            InlineKeyboardButton("2", callback_data="energy_2"),
            InlineKeyboardButton("3", callback_data="energy_3"),
            InlineKeyboardButton("4", callback_data="energy_4"),
            InlineKeyboardButton("5 ⚡", callback_data="energy_5"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
        # Load profile and run triage
        profile = load_profile(pitcher_id)
        triage_result = triage(
            arm_feel=arm_feel,
            sleep_hours=sleep_hours,
            pitcher_profile=profile,
            energy=energy,
        )

        # Run progression analysis
        progression = analyze_progression(pitcher_id)

        # Add progression flags to triage result for plan generator
        if progression["flags"]:
            triage_result.setdefault("progression_flags", []).extend(progression["flags"])

        flag = triage_result["flag_level"].upper()
        await query.message.reply_text(f"Triage: {flag}\n{triage_result['reasoning']}")

        # Send alerts if any
        for alert in triage_result.get("alerts", []):
            await query.message.reply_text(f"⚠️ {alert}")

        # Send progression observations
        for obs in progression.get("observations", []):
            await query.message.reply_text(f"Pattern note: {obs}")

        # Generate plan
        plan = await generate_plan(pitcher_id, triage_result)
        await query.message.reply_text(plan)

        # Send weekly summary on Sundays
        if progression.get("weekly_summary"):
            await query.message.reply_text(progression["weekly_summary"])

        # Log the check-in
        bot_observations = progression.get("observations") or None
        _log_checkin(pitcher_id, arm_feel, sleep_hours, energy, triage_result, bot_observations)

        # Update context
        append_context(
            pitcher_id, "status",
            f"Check-in: arm_feel={arm_feel}, sleep={sleep_hours}h, energy={energy}, flag={flag}"
        )

    except Exception as e:
        logger.error(f"Error in check-in flow: {e}", exc_info=True)
        await query.message.reply_text(
            "Something went wrong generating your plan. Try /checkin again, "
            "or let your coach know."
        )

    return ConversationHandler.END


async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the check-in flow."""
    await update.message.reply_text("Check-in cancelled.")
    return ConversationHandler.END


def _log_checkin(pitcher_id: str, arm_feel: int, sleep_hours: float,
                 energy: int, triage_result: dict,
                 bot_observations: list[str] = None) -> None:
    """Write the check-in to the daily log."""
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "pre_training": {
            "arm_feel": arm_feel,
            "overall_energy": energy,
            "sleep_hours": sleep_hours,
            "flag_level": triage_result["flag_level"],
        },
        "plan_generated": {
            "triage_result": triage_result,
            "modifications_applied": triage_result.get("modifications", []),
        },
        "actual_logged": None,
        "bot_observations": bot_observations,
    }
    append_log_entry(pitcher_id, entry)


def get_checkin_handler() -> ConversationHandler:
    """Build and return the ConversationHandler for daily check-in."""
    return ConversationHandler(
        entry_points=[CommandHandler("checkin", start_checkin)],
        states={
            ARM_FEEL: [CallbackQueryHandler(arm_feel_callback, pattern=r"^arm_feel_\d$")],
            SLEEP_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, sleep_hours_handler)],
            ENERGY: [CallbackQueryHandler(energy_callback, pattern=r"^energy_\d$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin)],
    )
