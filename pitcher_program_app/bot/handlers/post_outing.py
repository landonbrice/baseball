"""Post-outing logging flow using ConversationHandler.

States: PITCH_COUNT → ARM_FEEL → TIGHTNESS → UCL_SENSATION → NOTES → process.
Collects forearm tightness and UCL sensation for weighted triage.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.services.outing_service import process_outing
from bot.services.context_manager import get_pitcher_id_by_telegram
from bot.utils import build_rating_keyboard

logger = logging.getLogger(__name__)

# Conversation states
PITCH_COUNT, ARM_FEEL, TIGHTNESS, UCL_SENSATION, NOTES = range(5)


async def start_outing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the post-outing logging flow."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return ConversationHandler.END

    context.user_data["pitcher_id"] = pitcher_id
    context.user_data["conversation_history"] = []
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

    reply_markup = build_rating_keyboard("outing_feel")
    await update.message.reply_text(
        f"Got it — {count} pitches. How's the arm feel right now? (1-10)",
        reply_markup=reply_markup,
    )
    return ARM_FEEL


async def arm_feel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel selection, then ask about tightness."""
    query = update.callback_query
    await query.answer()

    arm_feel = int(query.data.split("_")[-1])
    context.user_data["outing_arm_feel"] = arm_feel

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("None", callback_data="tightness_none"),
            InlineKeyboardButton("Mild", callback_data="tightness_mild"),
        ],
        [
            InlineKeyboardButton("Moderate", callback_data="tightness_moderate"),
            InlineKeyboardButton("Significant", callback_data="tightness_significant"),
        ],
    ])
    await query.edit_message_text(f"Arm feel: {arm_feel}/10.")
    await query.message.reply_text(
        "Any forearm tightness?",
        reply_markup=keyboard,
    )
    return TIGHTNESS


async def tightness_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle tightness selection, then ask about UCL sensation."""
    query = update.callback_query
    await query.answer()

    tightness = query.data.replace("tightness_", "")
    context.user_data["forearm_tightness"] = tightness

    label = tightness.title()
    await query.edit_message_text(f"Forearm tightness: {label}.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("None", callback_data="ucl_none"),
            InlineKeyboardButton("Present", callback_data="ucl_present"),
        ],
    ])
    await query.message.reply_text(
        "Any UCL-area sensation on elbow extension?",
        reply_markup=keyboard,
    )
    return UCL_SENSATION


async def ucl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle UCL sensation selection, then ask for notes."""
    query = update.callback_query
    await query.answer()

    ucl = query.data == "ucl_present"
    context.user_data["ucl_sensation"] = ucl

    label = "Present" if ucl else "None"
    await query.edit_message_text(f"UCL sensation: {label}.")

    await query.message.reply_text(
        "Any notes? (mechanics, how you felt, anything notable)\n\n"
        "Type your notes or send 'none' to skip."
    )
    return NOTES


async def notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle notes input, then process the outing."""
    notes = update.message.text.strip()
    if notes.lower() in ("none", "n/a", "no", "skip", "-"):
        notes = ""

    await update.message.reply_text("Processing your outing report...")

    try:
        pitcher_id = context.user_data["pitcher_id"]
        pitch_count = context.user_data["pitch_count"]
        arm_feel = context.user_data["outing_arm_feel"]
        tightness = context.user_data.get("forearm_tightness", "none")
        ucl = context.user_data.get("ucl_sensation", False)

        result = await process_outing(
            pitcher_id, pitch_count, arm_feel, notes,
            forearm_tightness=tightness, ucl_sensation=ucl,
        )

        await update.message.reply_text(result["recovery_plan"])

        for alert in result["alerts"]:
            await update.message.reply_text(f"⚠️ {alert}")

        context.user_data["conversation_history"] = [
            {"role": "assistant", "content": result["recovery_plan"]}
        ]
        await update.message.reply_text(
            "Any questions about recovery, or want me to save this protocol?"
        )

    except Exception as e:
        logger.error(f"Error processing outing: {e}", exc_info=True)
        await update.message.reply_text(
            "Something went wrong processing your outing. Try /outing again or let your coach know."
        )

    return ConversationHandler.END


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
            ARM_FEEL: [CallbackQueryHandler(arm_feel_callback, pattern=r"^outing_feel_\d+$")],
            TIGHTNESS: [CallbackQueryHandler(tightness_callback, pattern=r"^tightness_")],
            UCL_SENSATION: [CallbackQueryHandler(ucl_callback, pattern=r"^ucl_")],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_outing)],
    )
