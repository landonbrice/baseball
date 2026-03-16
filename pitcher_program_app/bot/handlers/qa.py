"""Q&A handler. Routes free-text questions to the LLM with context."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import (
    load_profile,
    load_context,
    get_pitcher_id_by_telegram,
    append_context,
)
from bot.services.knowledge_retrieval import retrieve_knowledge
from bot.services.web_research import web_search_fallback

logger = logging.getLogger(__name__)


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

        response = await call_llm(system_prompt, user_prompt)
        await update.message.reply_text(response)

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
        parts.append(f"\nRecent context:\n{context_md[-300:]}")

    return "\n".join(parts)
