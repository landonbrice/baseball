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


async def process_checkin(
    pitcher_id: str, arm_feel: int, sleep_hours: float, energy: int = 3,
    arm_report: str = "", lift_preference: str = "",
    throw_intent: str = "", next_pitch_days: int | None = None,
) -> dict:
    """Run triage, generate plan, log entry, and return structured results.

    Does NOT increment days_since_outing — callers handle that separately.

    Returns dict with: flag_level, triage_reasoning, alerts, observations,
    weekly_summary, plan_narrative, exercise_blocks, throwing_plan,
    estimated_duration_min, modifications_applied, template_day, rotation_day.
    """
    # Load profile and clamp unreasonable days_since_outing
    profile = load_profile(pitcher_id)
    rotation_length = profile.get("rotation_length", 7)
    if profile.get("active_flags", {}).get("days_since_outing", 0) > rotation_length * 2:
        update_active_flags(pitcher_id, {"days_since_outing": rotation_length - 1})
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

    # Persist flag_level, arm_feel, and explicit check-in timestamp
    from datetime import datetime as _dt
    update_active_flags(pitcher_id, {
        "current_flag_level": triage_result["flag_level"],
        "current_arm_feel": arm_feel,
        "phase": f"checked_in_{_dt.now().strftime('%Y-%m-%d')}",
    })

    # Run progression analysis
    progression = analyze_progression(pitcher_id)

    # Add progression flags to triage result for plan generator
    if progression["flags"]:
        triage_result.setdefault("progression_flags", []).extend(progression["flags"])

    # Generate plan with check-in inputs
    checkin_inputs = {}
    if arm_report:
        checkin_inputs["arm_report"] = arm_report
    if lift_preference:
        checkin_inputs["lift_preference"] = lift_preference
    if throw_intent:
        checkin_inputs["throw_intent"] = throw_intent
    if next_pitch_days is not None:
        checkin_inputs["next_pitch_days"] = f"{next_pitch_days} days"
    plan_result = await generate_plan(pitcher_id, triage_result, checkin_inputs=checkin_inputs)

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
        "morning_brief": plan_result.get("morning_brief") if plan_result else None,
        "arm_care": plan_result.get("arm_care") if plan_result else None,
        "lifting": plan_result.get("lifting") if plan_result else None,
        "throwing": plan_result.get("throwing") if plan_result else None,
        "notes": plan_result.get("notes", []) if plan_result else [],
        "soreness_response": plan_result.get("soreness_response") if plan_result else None,
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

    # Write rich session note to context
    flag = triage_result["flag_level"].upper()
    lifting_summary = ""
    if plan_result and plan_result.get("lifting", {}).get("exercises"):
        names = [ex.get("name", "") for ex in plan_result["lifting"]["exercises"][:5]]
        lifting_summary = f"Lift: {', '.join(names)}"
    throwing_summary = ""
    if plan_result and plan_result.get("throwing", {}).get("type", "none") != "none":
        throwing_summary = f"Throwing: {plan_result['throwing'].get('type', '')}"
    mods = plan_result.get("modifications_applied", []) if plan_result else []
    mods_str = f" Mods: {', '.join(mods[:3])}" if mods else ""

    session_note = f"Arm {arm_feel}/5, sleep {sleep_hours}h, {flag} flag. {lifting_summary}. {throwing_summary}.{mods_str}".strip()
    if arm_report:
        session_note = f'Arm: "{arm_report}" ({arm_feel}/5). {session_note}'
    if lift_preference:
        session_note += f" Requested: {lift_preference}."
    append_context(pitcher_id, "session", session_note)

    return {
        "flag_level": triage_result["flag_level"],
        "triage_reasoning": triage_result["reasoning"],
        "alerts": triage_result.get("alerts", []),
        "observations": progression.get("observations", []),
        "weekly_summary": progression.get("weekly_summary"),
        "plan_narrative": plan_result["narrative"] if plan_result else "",
        "morning_brief": plan_result.get("morning_brief") if plan_result else None,
        "arm_care": plan_result.get("arm_care") if plan_result else None,
        "lifting": plan_result.get("lifting") if plan_result else None,
        "throwing": plan_result.get("throwing") if plan_result else None,
        "notes": plan_result.get("notes", []) if plan_result else [],
        "soreness_response": plan_result.get("soreness_response") if plan_result else None,
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
