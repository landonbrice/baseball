"""Post-outing logging flow using ConversationHandler.

States: PITCH_COUNT → ARM_FEEL → NOTES → process and respond.
"""

import logging
from telegram import Update
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
    context.user_data["conversation_history"] = []  # reset on structured flow
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
        pitcher_id = context.user_data["pitcher_id"]
        pitch_count = context.user_data["pitch_count"]
        arm_feel = context.user_data["outing_arm_feel"]

        result = await process_outing(pitcher_id, pitch_count, arm_feel, notes)

        await update.message.reply_text(result["recovery_plan"])

        for alert in result["alerts"]:
            await update.message.reply_text(f"⚠️ {alert}")

        # Seed conversation history so follow-up Q&A has outing context
        context.user_data["conversation_history"] = [
            {"role": "assistant", "content": result["recovery_plan"]}
        ]

        await update.message.reply_text(
            "Questions about tomorrow's plan, or want me to save this recovery protocol?"
        )

    except Exception as e:
        logger.error(f"Error processing outing: {e}", exc_info=True)
        await update.message.reply_text(
            "Something went wrong processing your outing. I logged the raw data — "
            "try /outing again or let your coach know."
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
            ARM_FEEL: [CallbackQueryHandler(arm_feel_callback, pattern=r"^outing_feel_\d$")],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_outing)],
    )
