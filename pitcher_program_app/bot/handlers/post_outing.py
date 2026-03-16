"""Post-outing logging flow using ConversationHandler.

States: PITCH_COUNT → ARM_FEEL → NOTES → process and respond.
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
from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import (
    load_profile,
    load_context,
    append_context,
    append_log_entry,
    get_pitcher_id_by_telegram,
    get_recent_entries,
    update_active_flags,
)
from bot.config import TEMPLATES_DIR

logger = logging.getLogger(__name__)

# Conversation states
PITCH_COUNT, ARM_FEEL, NOTES = range(3)


async def start_outing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the post-outing logging flow."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return ConversationHandler.END

    context.user_data["pitcher_id"] = pitcher_id
    await update.message.reply_text("Post-outing report. How many pitches did you throw?")
    return PITCH_COUNT


async def pitch_count_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pitch count input."""
    try:
        count = int(update.message.text.strip())
        if count < 0 or count > 200:
            await update.message.reply_text("That doesn't look right. Give me a number between 0 and 200.")
            return PITCH_COUNT
    except ValueError:
        await update.message.reply_text("Just the number. Like '78' or '95'.")
        return PITCH_COUNT

    context.user_data["pitch_count"] = count

    # Arm feel keyboard (1-5)
    keyboard = [
        [
            InlineKeyboardButton("1 💀", callback_data="outing_feel_1"),
            InlineKeyboardButton("2", callback_data="outing_feel_2"),
            InlineKeyboardButton("3", callback_data="outing_feel_3"),
            InlineKeyboardButton("4", callback_data="outing_feel_4"),
            InlineKeyboardButton("5 💪", callback_data="outing_feel_5"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Got it — {count} pitches. How's the arm feel right now? (1-5)",
        reply_markup=reply_markup,
    )
    return ARM_FEEL


async def arm_feel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel selection."""
    query = update.callback_query
    await query.answer()

    arm_feel = int(query.data.split("_")[-1])
    context.user_data["outing_arm_feel"] = arm_feel

    await query.edit_message_text(
        f"Arm feel: {arm_feel}/5. Any notes? (mechanics, how you felt, anything notable)\n\n"
        "Type your notes or send 'none' to skip."
    )
    return NOTES


async def notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle notes input, then process the outing."""
    notes = update.message.text.strip()
    if notes.lower() in ("none", "n/a", "no", "skip", "-"):
        notes = ""

    context.user_data["outing_notes"] = notes

    await update.message.reply_text("Processing your outing report...")

    try:
        await _process_outing(update, context)
    except Exception as e:
        logger.error(f"Error processing outing: {e}", exc_info=True)
        await update.message.reply_text(
            "Something went wrong processing your outing. I logged the raw data — "
            "try /outing again or let your coach know."
        )

    return ConversationHandler.END


async def _process_outing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the outing: update flags, load templates, call LLM, log entry."""
    pitcher_id = context.user_data["pitcher_id"]
    pitch_count = context.user_data["pitch_count"]
    arm_feel = context.user_data["outing_arm_feel"]
    notes = context.user_data.get("outing_notes", "")

    profile = load_profile(pitcher_id)
    today = datetime.now().strftime("%Y-%m-%d")

    # Update active flags
    update_active_flags(pitcher_id, {
        "days_since_outing": 0,
        "last_outing_date": today,
        "last_outing_pitches": pitch_count,
        "current_arm_feel": arm_feel,
    })

    # Load recovery templates
    recovery_templates = _load_recovery_templates()

    # Build outing data string
    typical = profile.get("pitching_profile", {}).get("typical_pitch_count", 85)
    outing_data = (
        f"Date: {today}\n"
        f"Pitch count: {pitch_count} (typical: {typical})\n"
        f"Arm feel: {arm_feel}/5\n"
    )
    if notes:
        outing_data += f"Notes: {notes}\n"
    if pitch_count > typical + 15:
        outing_data += "⚠️ Pitch count significantly above typical — extended recovery recommended\n"
    if arm_feel <= 2:
        outing_data += "⚠️ Low arm feel — recommend trainer evaluation before tomorrow's work\n"

    # Build pitcher context
    pitcher_context = _build_outing_context(profile, pitcher_id)

    # Recent logs
    recent = get_recent_entries(pitcher_id, n=3)
    recent_logs = json.dumps(recent, indent=2) if recent else "No recent entries"

    # Call LLM for recovery plan
    system_prompt = load_prompt("system_prompt.md")
    recovery_prompt = load_prompt("post_outing_recovery.md")

    user_prompt = recovery_prompt.replace("{pitcher_context}", pitcher_context)
    user_prompt = user_prompt.replace("{outing_data}", outing_data)
    user_prompt = user_prompt.replace("{recovery_templates}", recovery_templates)
    user_prompt = user_prompt.replace("{recent_logs}", recent_logs)

    response = await call_llm(system_prompt, user_prompt)
    await update.message.reply_text(response)

    # Send alert if arm feel is low
    if arm_feel <= 2:
        await update.message.reply_text(
            "⚠️ I'd flag that arm feel for your trainer before doing anything tomorrow."
        )

    # Log the outing entry
    entry = {
        "date": today,
        "outing": {
            "pitch_count": pitch_count,
            "arm_feel": arm_feel,
            "notes": notes,
        },
        "pre_training": None,
        "actual_logged": None,
        "bot_observations": None,
    }
    append_log_entry(pitcher_id, entry)

    # Update context
    append_context(
        pitcher_id, "outing",
        f"Outing: {pitch_count} pitches, arm_feel={arm_feel}/5"
        + (f", notes: {notes[:80]}" if notes else "")
    )


def _load_recovery_templates() -> str:
    """Load post-throw stretch and arm care light templates as formatted strings."""
    templates = []

    for filename in ["post_throw_stretch.json", "arm_care_light.json"]:
        path = f"{TEMPLATES_DIR}/{filename}"
        try:
            with open(path, "r") as f:
                data = json.load(f)
            name = data.get("name", filename)
            exercises = []
            # Handle both flat and blocked structures
            if "sequence" in data:
                for item in data["sequence"]:
                    if "exercises" in item:
                        exercises.append(f"\n{item.get('block_name', '')}:")
                        for ex in item["exercises"]:
                            exercises.append(f"  - {ex['name']}: {ex.get('prescription', '')}")
                    else:
                        exercises.append(f"  - {item['name']}: {item.get('prescription', '')}")
            templates.append(f"### {name}\n" + "\n".join(exercises))
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load template {filename}: {e}")

    return "\n\n".join(templates) if templates else "No recovery templates available"


def _build_outing_context(profile: dict, pitcher_id: str) -> str:
    """Build context string for outing recovery prompt."""
    context_md = load_context(pitcher_id)
    flags = profile.get("active_flags", {})
    injury = profile.get("injury_history", [])

    parts = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'starter')}",
        f"Typical pitch count: {profile.get('pitching_profile', {}).get('typical_pitch_count', 'N/A')}",
    ]

    if injury:
        latest = injury[-1]
        parts.append(f"Injury note: {latest.get('area', '')} — {latest.get('ongoing_considerations', '')}")

    active_mods = flags.get("active_modifications", [])
    if active_mods:
        parts.append(f"Active modifications: {', '.join(active_mods)}")

    if context_md:
        parts.append(f"\nRecent context:\n{context_md[-300:]}")

    return "\n".join(parts)


async def cancel_outing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the outing flow."""
    await update.message.reply_text("Outing report cancelled.")
    return ConversationHandler.END


def get_outing_handler() -> ConversationHandler:
    """Build and return the ConversationHandler for post-outing logging."""
    return ConversationHandler(
        entry_points=[CommandHandler("outing", start_outing)],
        states={
            PITCH_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pitch_count_handler)],
            ARM_FEEL: [CallbackQueryHandler(arm_feel_callback, pattern=r"^outing_feel_\d$")],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_outing)],
    )
