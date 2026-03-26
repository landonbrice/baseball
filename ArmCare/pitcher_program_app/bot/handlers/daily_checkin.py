"""Daily check-in flow using ConversationHandler.

Guided open check-in: arm report (free text) → lift preference → throw intent → schedule → plan.
"""

import logging
import json
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
    update_active_flags,
)
from bot.utils import build_rating_keyboard, build_completion_keyboard

logger = logging.getLogger(__name__)

# Conversation states
ARM_REPORT, LIFT_PREF, THROW_INTENT, SCHEDULE, RELIEVER_THREW = range(5)


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
        profile = load_profile(pitcher_id)
    flags = profile.get("active_flags", {})
    days_since = flags.get("days_since_outing", 0)
    role = profile.get("role", "starter")

    # 8+ days without outing for starters
    if role == "starter" and days_since > 8:
        await update.message.reply_text(
            f"It's been {days_since} days since your last logged outing. "
            "Did you pitch recently? If so, use /outing to log it."
        )

    # Reliever "Did you throw?" branch
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

    # Open question — free text
    first_name = profile.get("name", "").split()[0] if profile.get("name") else "there"
    await update.message.reply_text(
        f"Morning {first_name}. How's the arm feeling?"
    )
    return ARM_REPORT


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
    await query.message.reply_text("How's the arm feeling?")
    return ARM_REPORT


async def arm_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel — accepts free text or a number 1-5."""
    text = update.message.text.strip()

    # If it's a plain number 1-5, use directly
    try:
        num = int(text)
        if 1 <= num <= 5:
            context.user_data["arm_feel"] = num
            context.user_data["arm_report"] = ""
        else:
            context.user_data["arm_report"] = text
            context.user_data["arm_feel"] = None  # classify later
    except ValueError:
        # Free text — store for LLM classification
        context.user_data["arm_report"] = text
        context.user_data["arm_feel"] = None

    # Move to lift preference
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Upper", callback_data="lift_upper"),
            InlineKeyboardButton("Lower", callback_data="lift_lower"),
            InlineKeyboardButton("Full body", callback_data="lift_full"),
        ],
        [
            InlineKeyboardButton("Rest day", callback_data="lift_rest"),
            InlineKeyboardButton("Your call", callback_data="lift_auto"),
        ],
    ])
    await update.message.reply_text(
        "Got it. What are you thinking for a lift today?",
        reply_markup=keyboard,
    )
    return LIFT_PREF


async def lift_pref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle lift preference selection."""
    query = update.callback_query
    await query.answer()

    pref = query.data.replace("lift_", "")
    context.user_data["lift_preference"] = pref

    pref_labels = {"upper": "Upper body", "lower": "Lower body", "full": "Full body", "rest": "Rest day", "auto": "I'll pick"}
    await query.edit_message_text(f"Lift: {pref_labels.get(pref, pref)}.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Flat ground", callback_data="throw_flat_ground"),
            InlineKeyboardButton("Bullpen", callback_data="throw_bullpen"),
        ],
        [
            InlineKeyboardButton("Long toss", callback_data="throw_long_toss"),
            InlineKeyboardButton("Light catch", callback_data="throw_light_catch"),
            InlineKeyboardButton("No", callback_data="throw_none"),
        ],
    ])
    await query.message.reply_text(
        "Throwing today?",
        reply_markup=keyboard,
    )
    return THROW_INTENT


async def throw_intent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle throwing intent selection."""
    query = update.callback_query
    await query.answer()

    intent = query.data.replace("throw_", "")
    context.user_data["throw_intent"] = intent

    label = intent.replace("_", " ").title()
    if intent == "none":
        label = "No throwing"
    await query.edit_message_text(f"Throwing: {label}.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Tomorrow", callback_data="schedule_1"),
            InlineKeyboardButton("2 days", callback_data="schedule_2"),
            InlineKeyboardButton("3+ days", callback_data="schedule_3"),
            InlineKeyboardButton("Not sure", callback_data="schedule_0"),
        ],
    ])
    await query.message.reply_text(
        "When do you pitch next?",
        reply_markup=keyboard,
    )
    return SCHEDULE


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle schedule selection, classify arm, run triage, generate plan."""
    query = update.callback_query
    await query.answer()

    next_days = int(query.data.replace("schedule_", ""))
    context.user_data["next_pitch_days"] = next_days if next_days > 0 else None

    if next_days > 0:
        await query.edit_message_text(f"Next pitch: {next_days} day{'s' if next_days > 1 else ''}.")
    else:
        await query.edit_message_text("Next pitch: not sure.")

    await query.message.reply_text("Building your plan...")

    pitcher_id = context.user_data["pitcher_id"]
    arm_report = context.user_data.get("arm_report", "")
    arm_feel = context.user_data.get("arm_feel")
    lift_preference = context.user_data.get("lift_preference", "auto")
    throw_intent = context.user_data.get("throw_intent", "none")
    next_pitch_days = context.user_data.get("next_pitch_days")

    # Classify arm report if free text was given
    if arm_feel is None and arm_report:
        arm_feel, concern_areas = await _classify_arm_report(arm_report)
        context.user_data["arm_feel"] = arm_feel
    elif arm_feel is None:
        arm_feel = 4  # default if nothing provided

    # Update schedule/rotation if pitcher specified next pitch
    if next_pitch_days and next_pitch_days > 0:
        profile = load_profile(pitcher_id)
        rotation = profile.get("rotation_length", 7)
        new_day = max(0, rotation - next_pitch_days)
        update_active_flags(pitcher_id, {
            "days_since_outing": new_day,
            "next_outing_days": next_pitch_days,
        })

    # Default sleep to profile baseline (WHOOP integration will replace this)
    profile = load_profile(pitcher_id)
    sleep_hours = profile.get("biometric_integration", {}).get("avg_sleep_hours") or 7.0

    try:
        result = await process_checkin(
            pitcher_id, arm_feel, sleep_hours,
            arm_report=arm_report,
            lift_preference=lift_preference,
            throw_intent=throw_intent,
            next_pitch_days=next_pitch_days,
        )

        # Send triage + brief
        flag = result["flag_level"].upper()
        brief = result.get("morning_brief") or result.get("triage_reasoning", "")
        await query.message.reply_text(f"{flag} flag. {brief}")

        for alert in result["alerts"]:
            await query.message.reply_text(f"⚠️ {alert}")

        # Dashboard link
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
            reply_markup = build_completion_keyboard()
            await query.message.reply_text(result["plan_narrative"], reply_markup=reply_markup)

        if result["weekly_summary"]:
            await query.message.reply_text(result["weekly_summary"])

    except Exception as e:
        logger.error(f"Error in check-in flow: {e}", exc_info=True)
        await query.message.reply_text(
            "Something went wrong generating your plan. Try /checkin again, "
            "or let your coach know."
        )

    return ConversationHandler.END


async def _classify_arm_report(arm_report: str) -> tuple[int, list[str]]:
    """Classify free-text arm report into arm_feel (1-5) and concern areas."""
    report_lower = arm_report.lower()

    # Quick rule-based for obvious cases
    if any(w in report_lower for w in ["great", "perfect", "amazing", "100", "feel good", "feels good", "no issues"]):
        return 5, []
    if any(w in report_lower for w in ["sharp", "shooting", "numb", "tingling", "swelling", "can't"]):
        return 1, ["immediate_concern"]
    if any(w in report_lower for w in ["terrible", "really bad", "awful"]):
        return 2, ["significant_concern"]

    # For nuanced reports, use LLM classification
    try:
        from bot.services.llm import call_llm
        response = await call_llm(
            "You classify pitcher arm reports. Return ONLY valid JSON, no other text.",
            f'Classify this arm report on a 1-5 scale (1=severe pain, 5=feels great). '
            f'Return: {{"arm_feel": <1-5>, "areas": ["area1"], "trend": "better|same|worse|unknown"}}\n\n'
            f'Report: "{arm_report}"',
            max_tokens=80,
        )
        data = json.loads(response.strip())
        return int(data.get("arm_feel", 4)), data.get("areas", [])
    except Exception as e:
        logger.warning(f"Arm report classification failed, defaulting to 4: {e}")
        # Default to 4 with mild concern if they mentioned specific areas
        concern = []
        if any(w in report_lower for w in ["tight", "sore", "forearm", "elbow", "shoulder"]):
            concern = ["mild_concern"]
            return 3, concern
        return 4, []


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
                [InlineKeyboardButton("Open Dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await query.message.reply_text("Tap to open:", reply_markup=keyboard)
        else:
            await query.message.reply_text("Dashboard not configured yet.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if pitcher_id:
        _update_log_completion(pitcher_id, action)

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "plan_done":
        await query.message.reply_text("Logged as completed. Nice work.")
    elif action == "plan_skipped":
        context.user_data["awaiting_skip_details"] = True
        await query.message.reply_text(
            "Logged as partially completed. What did you skip or modify?\n\n"
            "Just a quick note — e.g., 'skipped plyocare, cut lifting short'"
        )


async def skip_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text response about what was skipped."""
    if not context.user_data.get("awaiting_skip_details"):
        return
    context.user_data["awaiting_skip_details"] = False

    pitcher_id = context.user_data.get("pitcher_id")
    details = update.message.text.strip()

    if pitcher_id and details:
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
    today = datetime.now().strftime("%Y-%m-%d")
    for entry in reversed(log.get("entries", [])):
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
            ARM_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, arm_report_handler)],
            LIFT_PREF: [CallbackQueryHandler(lift_pref_callback, pattern=r"^lift_")],
            THROW_INTENT: [CallbackQueryHandler(throw_intent_callback, pattern=r"^throw_")],
            SCHEDULE: [CallbackQueryHandler(schedule_callback, pattern=r"^schedule_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin)],
    )
