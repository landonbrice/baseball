"""LLM-driven triage refinement for ambiguous cases."""

import json
import logging
from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import load_context, get_recent_entries
from bot.config import CONTEXT_WINDOW_CHARS

logger = logging.getLogger(__name__)


async def llm_triage_refinement(
    arm_feel: int,
    sleep_hours: float,
    energy: int,
    profile: dict,
    pitcher_id: str,
):
    """Call LLM for nuanced triage when rule-based logic hits an ambiguous zone.

    Returns dict with 'modifications' and 'reasoning', or None on failure.
    """
    system_prompt = load_prompt("system_prompt.md")
    triage_prompt = load_prompt("triage_prompt.md")

    # Build context
    flags = profile.get("active_flags", {})
    injury = profile.get("injury_history", [])
    context_md = load_context(pitcher_id)

    pitcher_context = (
        f"Name: {profile.get('name', 'Unknown')}\n"
        f"Role: {profile.get('role', 'starter')}\n"
        f"Days since outing: {flags.get('days_since_outing', 'N/A')}\n"
        f"Active modifications: {', '.join(flags.get('active_modifications', []))}\n"
    )
    if injury:
        latest = injury[-1]
        pitcher_context += f"Injury note: {latest.get('area', '')} — {latest.get('ongoing_considerations', '')}\n"

    checkin_data = (
        f"Arm feel: {arm_feel}/5\n"
        f"Sleep: {sleep_hours}h\n"
        f"Energy: {energy}/5\n"
    )

    recent_entries = get_recent_entries(pitcher_id, n=5)
    recent_trend = json.dumps(recent_entries, indent=2) if recent_entries else "No recent entries"

    user_prompt = triage_prompt.replace("{pitcher_context}", pitcher_context)
    user_prompt = user_prompt.replace("{checkin_data}", checkin_data)
    user_prompt = user_prompt.replace("{recent_trend}", recent_trend)

    response = await call_llm(system_prompt, user_prompt, max_tokens=500)

    # Try to parse JSON from the response
    try:
        # Handle markdown code blocks
        text = response.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        return {
            "modifications": result.get("modifications", []),
            "reasoning": result.get("reasoning", ""),
        }
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"Could not parse LLM triage response: {response[:200]}")
        return None
