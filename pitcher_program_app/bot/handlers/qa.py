"""Q&A handler. Routes free-text questions to the LLM with context."""

import json
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.services.llm import call_llm, call_llm_reasoning, load_prompt

# Keywords that signal a request needs deep reasoning (multi-day protocols, progressions)
_REASONING_KEYWORDS = [
    "return to throw", "rtt", "progression", "2 week", "2-week", "two week",
    "ramp up", "ramp-up", "build back", "protocol", "recovery plan",
    "multi-day", "week plan", "throwing program", "return to mound",
    "shut down", "come back from", "post-injury", "rehab",
]
from bot.services.context_manager import (
    load_profile,
    load_context,
    get_pitcher_id_by_telegram,
    append_context,
    update_active_flags,
    get_recent_entries,
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

        # Research generation fallback if no docs matched
        if not knowledge:
            from bot.services.knowledge_retrieval import classify_and_generate_research
            generated = await classify_and_generate_research(question)
            if generated:
                knowledge = generated

        # Web research fallback if still empty
        if not knowledge:
            knowledge = web_search_fallback(question, pitcher_id)

        user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
        user_prompt = user_prompt.replace("{question}", question)
        user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

        # F4: inject today's sanitized rationale context to ground the answer
        from bot.services.rationale import build_qa_rationale_context
        user_prompt = build_qa_rationale_context(pitcher_id) + user_prompt

        history = context.user_data.get("conversation_history", [])

        # Detect throwing intent (Task 4.2 — non-blocking)
        throw_confirmation = None
        try:
            from bot.services.throw_intent_parser import parse_throw_intent
            from bot.services.weekly_model import add_scheduled_throw
            from datetime import datetime
            from bot.config import CHICAGO_TZ

            today_chicago = datetime.now(CHICAGO_TZ).date()
            throw_intent = parse_throw_intent(question, today_chicago)
            if throw_intent:
                try:
                    add_scheduled_throw(
                        pitcher_id,
                        {**throw_intent, "source": "chat"},
                    )
                    type_label = throw_intent['type'].replace('_', ' ')
                    throw_confirmation = f"Got it — {type_label} on {throw_intent['date']} added to your week. (Reply 'cancel last' to undo.)"
                except Exception as exc:
                    logger.warning(f"add_scheduled_throw failed for {pitcher_id}: {exc}")
        except Exception as exc:
            logger.warning(f"throw intent detection failed for {pitcher_id}: {exc}")

        # Route complex protocol requests to reasoning model
        q_lower = question.lower()
        needs_reasoning = any(kw in q_lower for kw in _REASONING_KEYWORDS)
        if needs_reasoning:
            response = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
        else:
            response = await call_llm(system_prompt, user_prompt, history=history)

        if throw_confirmation:
            response = f"{throw_confirmation}\n\n{response}"
        await update.message.reply_text(response)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": response})
        context.user_data["conversation_history"] = history[-6:]

        append_context(pitcher_id, "interaction", f"Q: {question[:80]} | A: {response[:200]}")

        # Record Q&A success for health monitoring (never raises)
        try:
            from bot.services.health_monitor import record_qa_success
            record_qa_success(pitcher_id)
        except Exception:
            pass

    except TimeoutError:
        logger.error(f"LLM timeout answering Q&A for {pitcher_id}")
        try:
            from bot.services.health_monitor import record_qa_error
            record_qa_error(pitcher_id, "TimeoutError")
        except Exception:
            pass
        await update.message.reply_text(
            "That's taking too long to process right now. Try asking again in a moment."
        )
    except Exception as e:
        logger.error(f"Error handling question: {e}", exc_info=True)
        try:
            from bot.services.health_monitor import record_qa_error
            record_qa_error(pitcher_id, type(e).__name__)
        except Exception:
            pass
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
        f"Throws: {profile.get('throws', 'unknown')}",
        f"Arm feel: {flags.get('current_arm_feel', 'N/A')}/10",
        f"Days since outing: {flags.get('days_since_outing', 'N/A')}",
    ]

    # Injury history
    for injury in profile.get("injury_history", []):
        parts.append(f"Injury: {injury.get('area', '')} — {injury.get('description', '')}")

    # Goals and preferences
    goals = profile.get("goals", {})
    if goals.get("primary"):
        parts.append(f"Primary goal: {goals['primary']}")
    detail = (profile.get("preferences") or {}).get("detail_level")
    if detail:
        parts.append(f"Communication preference: {detail}")

    # Phase
    phase = flags.get("phase")
    if phase:
        parts.append(f"Current phase: {phase.replace('_', ' ')}")

    if context_md:
        parts.append(f"""
## Conversation history & known context
Use the following to avoid repeating plans already given, reference prior conversations naturally, and apply persistent modifications proactively.

{context_md[-CONTEXT_WINDOW_CHARS:]}""")

    from bot.services.context_manager import load_saved_plans
    active_plans = [p for p in load_saved_plans(pitcher_id) if p.get("active")]
    if active_plans:
        plans_text = "\n".join(f"- {p['title']}: {p.get('summary', '')}" for p in active_plans)
        parts.append(f"\nActive saved plans:\n{plans_text}")

    # Include last generated plan for continuity
    recent = get_recent_entries(pitcher_id, n=1)
    if recent:
        last = recent[0]
        lifting = last.get("lifting", {})
        if lifting and lifting.get("exercises"):
            exercise_names = [ex.get("name", "") for ex in lifting["exercises"]]
            parts.append(f"\nLast prescribed lift ({last.get('date', '?')}, Day {last.get('rotation_day', '?')}): {', '.join(exercise_names)}")

    # Long-term memory (weekly summaries)
    from bot.services.context_manager import load_profile as _load_profile
    try:
        full_profile = _load_profile(pitcher_id)
        summaries = full_profile.get("weekly_summaries", [])
        if summaries:
            recent_summaries = summaries[-14:]
            parts.append("\nPrevious session summaries:")
            for s in recent_summaries:
                parts.append(f"  {s}")
    except Exception:
        pass

    return "\n".join(parts)


def _parse_coach_response(raw: str) -> dict | None:
    """Parse structured JSON from the LLM's coach chat response.

    Returns dict with reply, mutation_card, lookahead or None if malformed.
    """
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        parsed = json.loads(cleaned)
        if "reply" in parsed:
            return parsed
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_reply_fallback(raw: str) -> str:
    """Best-effort extraction of the reply field from malformed JSON."""
    match = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if match:
        return match.group(1).replace('\\"', '"').replace('\\n', '\n')
    return raw[:500]
