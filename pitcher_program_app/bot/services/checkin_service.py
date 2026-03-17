"""Shared check-in business logic, usable by both Telegram bot and API."""

import logging
from datetime import datetime

from bot.services.triage import triage
from bot.services.triage_llm import llm_triage_refinement
from bot.services.plan_generator import generate_plan
from bot.services.progression import analyze_progression
from bot.services.context_manager import (
    load_profile,
    append_context,
    append_log_entry,
    update_active_flags,
)

logger = logging.getLogger(__name__)


async def process_checkin(pitcher_id: str, arm_feel: int, sleep_hours: float, energy: int = 3) -> dict:
    """Run triage, generate plan, log entry, and return structured results.

    Does NOT increment days_since_outing — callers handle that separately.

    Returns dict with: flag_level, triage_reasoning, alerts, observations,
    weekly_summary, plan_narrative, exercise_blocks, throwing_plan,
    estimated_duration_min, modifications_applied, template_day, rotation_day.
    """
    # Load profile and run triage
    profile = load_profile(pitcher_id)
    triage_result = triage(
        arm_feel=arm_feel,
        sleep_hours=sleep_hours,
        pitcher_profile=profile,
        energy=energy,
    )

    # LLM-driven triage refinement for ambiguous cases
    if triage_result.get("protocol_adjustments", {}).get("needs_llm_triage"):
        try:
            llm_refinement = await llm_triage_refinement(
                arm_feel, sleep_hours, energy, profile, pitcher_id
            )
            if llm_refinement:
                triage_result["modifications"].extend(llm_refinement.get("modifications", []))
                triage_result["reasoning"] += f" LLM note: {llm_refinement.get('reasoning', '')}"
        except Exception as e:
            logger.warning(f"LLM triage refinement failed, using rule-based result: {e}")

    # Persist flag_level and arm_feel
    update_active_flags(pitcher_id, {
        "current_flag_level": triage_result["flag_level"],
        "current_arm_feel": arm_feel,
    })

    # Run progression analysis
    progression = analyze_progression(pitcher_id)

    # Add progression flags to triage result for plan generator
    if progression["flags"]:
        triage_result.setdefault("progression_flags", []).extend(progression["flags"])

    # Generate plan
    plan_result = await generate_plan(pitcher_id, triage_result)

    # Build and append log entry
    rotation_day = profile.get("active_flags", {}).get("days_since_outing", 0)
    bot_observations = progression.get("observations") or None

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "rotation_day": rotation_day,
        "pre_training": {
            "arm_feel": arm_feel,
            "overall_energy": energy,
            "sleep_hours": sleep_hours,
            "flag_level": triage_result["flag_level"],
        },
        "plan_narrative": plan_result["narrative"] if plan_result else None,
        "plan_generated": {
            "template_day": plan_result.get("template_day") if plan_result else None,
            "exercise_blocks": plan_result.get("exercise_blocks", []) if plan_result else [],
            "throwing_plan": plan_result.get("throwing_plan") if plan_result else None,
            "modifications_applied": (
                plan_result.get("modifications_applied", []) if plan_result
                else triage_result.get("modifications", [])
            ),
            "estimated_duration_min": plan_result.get("estimated_duration_min") if plan_result else None,
        },
        "actual_logged": None,
        "completed_exercises": {},
        "bot_observations": bot_observations,
    }
    append_log_entry(pitcher_id, entry)

    # Update context
    flag = triage_result["flag_level"].upper()
    append_context(
        pitcher_id, "status",
        f"Check-in: arm_feel={arm_feel}, sleep={sleep_hours}h, energy={energy}, flag={flag}"
    )

    return {
        "flag_level": triage_result["flag_level"],
        "triage_reasoning": triage_result["reasoning"],
        "alerts": triage_result.get("alerts", []),
        "observations": progression.get("observations", []),
        "weekly_summary": progression.get("weekly_summary"),
        "plan_narrative": plan_result["narrative"] if plan_result else "",
        "exercise_blocks": plan_result.get("exercise_blocks", []) if plan_result else [],
        "throwing_plan": plan_result.get("throwing_plan") if plan_result else None,
        "estimated_duration_min": plan_result.get("estimated_duration_min") if plan_result else None,
        "modifications_applied": (
            plan_result.get("modifications_applied", []) if plan_result
            else triage_result.get("modifications", [])
        ),
        "template_day": plan_result.get("template_day") if plan_result else None,
        "rotation_day": rotation_day,
    }
