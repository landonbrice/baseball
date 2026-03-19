"""Q&A handler. Routes free-text questions to the LLM with context."""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import (
    load_profile,
    load_context,
    get_pitcher_id_by_telegram,
    append_context,
    update_active_flags,
    load_saved_plans,
)
from bot.config import CONTEXT_WINDOW_CHARS
from bot.services.knowledge_retrieval import retrieve_knowledge
from bot.services.web_research import web_search_fallback

logger = logging.getLogger(__name__)

# Pattern to detect "I'm on day X" or "I am on day X"
_ROTATION_DAY_PATTERN = re.compile(
    r"(?:i'?m|i\s+am)\s+on\s+day\s+(\d+)", re.IGNORECASE
)


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a free-text question from a pitcher."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return

    question = update.message.text
    if not question or len(question.strip()) < 3:
        return

    # Phase 3c: Detect natural language rotation day updates
    day_match = _ROTATION_DAY_PATTERN.search(question)
    if day_match:
        day = int(day_match.group(1))
        update_active_flags(pitcher_id, {"days_since_outing": day})
        await update.message.reply_text(f"Got it — updated your rotation day to Day {day}.")
        append_context(pitcher_id, "status", f"Rotation day manually set to {day} via chat")
        # If there's more to the message beyond the day statement, continue to Q&A
        stripped = _ROTATION_DAY_PATTERN.sub("", question).strip(" .,;-")
        if len(stripped) < 3:
            return
        question = stripped

    try:
        profile = load_profile(pitcher_id)
        pitcher_context = _build_qa_context(profile, pitcher_id)

        system_prompt = load_prompt("system_prompt.md")
        qa_prompt = load_prompt("qa_prompt.md")

        # Knowledge retrieval
        knowledge = retrieve_knowledge(question)

        # Web research fallback if knowledge is empty
        if not knowledge:
            knowledge = web_search_fallback(question, pitcher_id)

        user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
        user_prompt = user_prompt.replace("{question}", question)
        user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

        # Multi-turn conversation history from Telegram user_data
        history = context.user_data.get("conversation_history", [])

        response = await call_llm(system_prompt, user_prompt, history=history)
        await update.message.reply_text(response)

        # Update conversation history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": response})
        context.user_data["conversation_history"] = history[-6:]

        append_context(pitcher_id, "interaction", f"Q: {question[:100]}")

    except Exception as e:
        logger.error(f"Error handling question: {e}", exc_info=True)
        await update.message.reply_text(
            "I hit an error trying to answer that. Try again, or ask your coach."
        )


def _build_qa_context(profile: dict, pitcher_id: str) -> str:
    """Build a brief context string for Q&A."""
    context_md = load_context(pitcher_id)
    flags = profile.get("active_flags", {})

    parts = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'starter')}",
        f"Arm feel: {flags.get('current_arm_feel', 'N/A')}/5",
        f"Days since outing: {flags.get('days_since_outing', 'N/A')}",
    ]

    if context_md:
        parts.append(f"""
## Conversation history & known context
The following is a log of this pitcher's recent interactions and persistent facts about their situation. Use it to:
- Avoid repeating information or plans you've already given
- Reference prior conversations naturally ("when we talked about your hotel lift...")
- Apply persistent modifications and injury history proactively

{context_md[-CONTEXT_WINDOW_CHARS:]}""")

    # Include active saved plans (parity with /chat API endpoint)
    active_plans = [p for p in load_saved_plans(pitcher_id) if p.get("active")]
    if active_plans:
        plans_text = "\n".join(f"- {p['title']}: {p.get('summary', '')}" for p in active_plans)
        parts.append(f"\nActive saved plans:\n{plans_text}")

    return "\n".join(parts)
