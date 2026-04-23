"""Shared check-in business logic, usable by both Telegram bot and API."""

import json
import logging
from datetime import datetime

from bot.config import CHICAGO_TZ
from bot.services.arm_assessment import classify_arm_assessment
from bot.services.triage import triage
from bot.services.triage_llm import llm_triage_refinement
from bot.services.plan_generator import generate_plan
from bot.services.progression import analyze_progression
from bot.services.context_manager import (
    load_profile,
    load_training_model,
    append_context,
    append_log_entry,
    update_active_flags,
    get_recent_entries,
)
from bot.services.baselines import get_or_refresh_baseline
from bot.services.db import get_daily_entries, update_training_model_partial

logger = logging.getLogger(__name__)


def normalize_brief(raw) -> str:
    """D3: Canonical morning_brief on write is always a JSON-string.

    - None / empty → '{}'
    - dict → json.dumps(dict)
    - already-valid JSON string of an object → passed through
    - plain string or malformed JSON → wrapped as {coaching_note: <string>}
    """
    if raw is None or raw == "":
        return json.dumps({})
    if isinstance(raw, dict):
        return json.dumps(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return json.dumps(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return json.dumps({"coaching_note": raw})
    # Unknown types — coerce via str()
    return json.dumps({"coaching_note": str(raw)})


async def _send_emergency_alert_if_present(plan_result: dict) -> None:
    """If the plan_result carries an _emergency_alert, fire a Telegram message to admin.

    Uses .pop() so the key is stripped from plan_result before downstream consumers
    touch it — this guarantees _emergency_alert never reaches Supabase.

    Never raises — monitoring must never break the check-in flow.
    """
    alert = (plan_result or {}).pop("_emergency_alert", None)
    if not alert:
        return

    try:
        from bot.services.health_monitor import format_emergency_alert
        from bot.config import ADMIN_TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
        from telegram import Bot

        message = format_emergency_alert(alert)
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_TELEGRAM_CHAT_ID, text=message)
        logger.warning(
            f"Emergency alert fired: {alert.get('pattern')} "
            f"({alert.get('count')} failures)"
        )
    except Exception as e:
        logger.error(f"Failed to send emergency alert: {e}", exc_info=True)


def _build_recent_history_context(pitcher_id, n=5):
    """Build condensed recent history string for LLM context injection.

    Returns a short summary of the last N days so coaching responses
    can reference patterns (e.g. "forearm tightness again — third time this week").
    """
    try:
        entries = get_recent_entries(pitcher_id, n=n)
    except Exception:
        return ""

    if not entries:
        return ""

    lines = []
    for e in entries:
        date = e.get("date", "?")
        pt = e.get("pre_training") or {}
        arm = pt.get("arm_feel", "?")
        flag = (pt.get("flag_level") or "?").upper()
        soreness = pt.get("soreness_notes", "")

        parts = [f"{date}: arm {arm}/10, {flag}"]
        if soreness:
            parts.append(f"notes: {soreness[:80]}")
        if e.get("skip_notes"):
            parts.append(f"skipped: {e['skip_notes'][:60]}")

        # Throwing
        throwing = e.get("throwing") or {}
        if throwing and throwing.get("type", "none") != "none":
            parts.append(f"threw: {throwing['type']}")

        lines.append(". ".join(parts))

    return "Recent history (last {} days):\n{}".format(len(lines), "\n".join(lines))


async def process_checkin(
    pitcher_id: str, arm_feel: int, sleep_hours: float, energy: int = 3,
    arm_report: str = "", lift_preference: str = "",
    throw_intent: str = "", next_pitch_days=None,
    arm_detail_tags: list[str] | None = None,
    arm_clarification: str = "",
) -> dict:
    """Run triage, generate plan, log entry, and return structured results.

    Does NOT increment days_since_outing — callers handle that separately.

    Returns dict with: flag_level, triage_reasoning, alerts, observations,
    weekly_summary, plan_narrative, exercise_blocks, throwing_plan,
    estimated_duration_min, modifications_applied, template_day, rotation_day.
    """
    # Load profile (no longer clamping days_since_outing — plan_generator
    # handles extended time off by using lift preference for template selection)
    profile = load_profile(pitcher_id)
    rotation_length = profile.get("rotation_length", 7)

    # Pull WHOOP biometrics if pitcher is linked — force fresh pull
    # to avoid serving stale partial data (e.g. strain-only from 6am cache)
    whoop_data = None
    try:
        from bot.services.whoop import is_linked, pull_whoop_data
        if is_linked(pitcher_id):
            whoop_data = pull_whoop_data(pitcher_id, force_refresh=True)
            # Use WHOOP sleep hours if self-reported is the default
            if whoop_data and whoop_data.get("sleep_hours") and sleep_hours == 7.0:
                sleep_hours = whoop_data["sleep_hours"]
    except Exception as e:
        logger.warning("WHOOP pull skipped for %s: %s", pitcher_id, e)

    # Phase 1: assemble recent history + baseline for trajectory-aware triage
    recent_entries_full = []
    recent_arm_feel = []
    pitcher_baseline = None
    training_model = None
    try:
        recent_entries_full = get_daily_entries(pitcher_id, limit=14)
        recent_arm_feel = [
            (e.get("pre_training") or {}).get("arm_feel")
            for e in recent_entries_full[:7]
            if (e.get("pre_training") or {}).get("arm_feel") is not None
        ]

        training_model = load_training_model(pitcher_id)
        cached_snapshot = training_model.get("baseline_snapshot") or {}
        last_outing_date = training_model.get("last_outing_date")
        rotation_length = profile.get("rotation_length", 7)

        pitcher_baseline = get_or_refresh_baseline(
            pitcher_id=pitcher_id,
            cached_snapshot=cached_snapshot,
            daily_entries=recent_entries_full,
            rotation_length=rotation_length,
            last_outing_date=last_outing_date,
        )

        # Persist refreshed baseline (strip _recomputed marker before write)
        if pitcher_baseline.get("_recomputed"):
            snapshot_to_persist = {k: v for k, v in pitcher_baseline.items() if k != "_recomputed"}
            try:
                update_training_model_partial(
                    pitcher_id, {"baseline_snapshot": snapshot_to_persist}
                )
            except Exception as e:
                logger.warning("Failed to persist baseline snapshot for %s: %s", pitcher_id, e)
    except Exception as e:
        logger.warning("Phase 1 baseline/history assembly failed for %s: %s", pitcher_id, e)

    rotation_day = (profile.get("active_flags") or {}).get("days_since_outing", 0)

    # Canonical arm assessment. The athlete-provided number stays authoritative;
    # details modify interpretation but never replace the numeric rating.
    if isinstance(arm_detail_tags, str):
        assessment_tags = [arm_detail_tags]
    else:
        assessment_tags = list(arm_detail_tags or [])
    if arm_clarification == "expected_soreness" and "expected_soreness" not in assessment_tags:
        assessment_tags.append("expected_soreness")
    elif arm_clarification == "concerned" and "different_than_normal" not in assessment_tags:
        assessment_tags.append("different_than_normal")

    arm_assessment = await classify_arm_assessment(
        numeric_arm_feel=arm_feel,
        detail_tags=assessment_tags,
        arm_report=arm_report,
        pitcher_profile=profile,
        recent_entries=recent_entries_full,
        days_since_outing=rotation_day,
    )

    whoop_strain_yesterday = whoop_data.get("yesterday_strain") if whoop_data else None

    # C3 fix: compute recovery curve expected values for trajectory evaluation
    recovery_curve_expected = None
    try:
        from bot.services.baselines import get_recovery_curve_expected
        last_outing_pitches = (training_model or {}).get("last_outing_pitches")
        recovery_curve_expected = get_recovery_curve_expected(
            role=profile.get("role", "starter"),
            rotation_day=rotation_day,
            pitch_count=last_outing_pitches,
        )
    except Exception as e:
        logger.warning("Recovery curve lookup failed for %s: %s", pitcher_id, e)

    triage_result = triage(
        arm_feel=arm_feel,
        sleep_hours=sleep_hours,
        pitcher_profile=profile,
        energy=energy,
        whoop_recovery=whoop_data.get("recovery_score") if whoop_data else None,
        whoop_hrv=whoop_data.get("hrv_rmssd") if whoop_data else None,
        whoop_hrv_7day_avg=whoop_data.get("hrv_7day_avg") if whoop_data else None,
        whoop_sleep_perf=whoop_data.get("sleep_performance") if whoop_data else None,
        # Phase 1: trajectory-aware args (C1 fix: use correct param names)
        arm_feel_history=recent_arm_feel,
        recovery_curve_expected=recovery_curve_expected,
        pitcher_baseline=pitcher_baseline,
        arm_clarification=arm_clarification if arm_clarification else None,
        arm_assessment=arm_assessment,
        whoop_strain_yesterday=whoop_strain_yesterday,
    )

    # Phase 1 observability: log category scores + trajectory context
    logger.info(
        "triage_phase1 pitcher=%s flag=%s tissue=%.1f load=%.1f recovery=%.1f "
        "baseline_tier=%d chronic_drift=%s recovery_stall=%s",
        pitcher_id,
        triage_result.get("flag_level"),
        (triage_result.get("category_scores") or {}).get("tissue", 0.0),
        (triage_result.get("category_scores") or {}).get("load", 0.0),
        (triage_result.get("category_scores") or {}).get("recovery", 0.0),
        triage_result.get("baseline_tier", 1),
        (triage_result.get("trajectory_context") or {}).get("chronic_drift", False),
        (triage_result.get("trajectory_context") or {}).get("recovery_curve_status") == "stall",
    )

    # LLM-driven triage refinement for ambiguous cases
    if (triage_result.get("protocol_adjustments") or {}).get("needs_llm_triage"):
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
    chicago_now = datetime.now(CHICAGO_TZ)
    today_str = chicago_now.strftime("%Y-%m-%d")
    update_active_flags(pitcher_id, {
        "current_flag_level": triage_result["flag_level"],
        "current_arm_feel": arm_feel,
        "phase": f"checked_in_{today_str}",
    })

    # Run progression analysis
    progression = analyze_progression(pitcher_id)

    # Add progression flags to triage result for plan generator
    if progression["flags"]:
        triage_result.setdefault("progression_flags", []).extend(progression["flags"])

    # Build recent history context (Refinement 3)
    recent_history = _build_recent_history_context(pitcher_id, n=5)

    # Save partial entry BEFORE plan generation so check-in data persists
    # even if LLM/plan generation fails
    bot_observations = progression.get("observations") or None
    partial_entry = {
        "date": today_str,
        "rotation_day": rotation_day,
        "pre_training": {
            "arm_feel": arm_feel,
            "overall_energy": energy,
            "sleep_hours": sleep_hours,
            "flag_level": triage_result["flag_level"],
            "category_scores": triage_result.get("category_scores"),
            "baseline_tier": triage_result.get("baseline_tier"),
            "arm_report": arm_report,
            "arm_detail_tags": arm_assessment.get("detail_tags", []),
            "arm_assessment": arm_assessment,
        },
        "plan_narrative": None,
        "morning_brief": normalize_brief(None),
        "arm_care": None,
        "lifting": None,
        "throwing": None,
        "notes": [],
        "soreness_response": None,
        "plan_generated": None,
        "actual_logged": None,
        "completed_exercises": {},
        "bot_observations": bot_observations,
    }
    append_log_entry(pitcher_id, partial_entry)

    # Generate plan with check-in inputs + history
    checkin_inputs = {}
    if arm_report:
        checkin_inputs["arm_report"] = arm_report
    checkin_inputs["arm_detail_tags"] = arm_assessment.get("detail_tags", [])
    checkin_inputs["arm_assessment"] = arm_assessment
    if lift_preference:
        checkin_inputs["lift_preference"] = lift_preference
    if throw_intent:
        checkin_inputs["throw_intent"] = throw_intent
    if next_pitch_days is not None:
        checkin_inputs["next_pitch_days"] = f"{next_pitch_days} days"
    if arm_clarification:
        checkin_inputs["arm_clarification"] = arm_clarification
    if recent_history:
        checkin_inputs["recent_history"] = recent_history
    if whoop_data:
        checkin_inputs["whoop_biometrics"] = {
            "recovery": whoop_data.get("recovery_score"),
            "hrv": whoop_data.get("hrv_rmssd"),
            "hrv_7day_avg": whoop_data.get("hrv_7day_avg"),
            "sleep_perf": whoop_data.get("sleep_performance"),
            "sleep_hours": whoop_data.get("sleep_hours"),
            "strain": whoop_data.get("yesterday_strain"),
        }

    try:
        plan_result = await generate_plan(pitcher_id, triage_result, checkin_inputs=checkin_inputs)
    except Exception as e:
        logger.error(f"Plan generation failed for {pitcher_id}: {e}", exc_info=True)
        plan_result = None

    # Fire emergency alert if plan_result carries one. This MUST run before
    # the entry-build block below so the _emergency_alert key is stripped
    # from plan_result (via .pop) before any persistence path sees it.
    if plan_result:
        await _send_emergency_alert_if_present(plan_result)

    # Build full entry and upsert (same date = updates the partial entry)
    entry = {
        "date": today_str,
        "rotation_day": rotation_day,
        "pre_training": {
            "arm_feel": arm_feel,
            "overall_energy": energy,
            "sleep_hours": sleep_hours,
            "flag_level": triage_result["flag_level"],
            "category_scores": triage_result.get("category_scores"),
            "baseline_tier": triage_result.get("baseline_tier"),
            "arm_report": arm_report,
            "arm_detail_tags": arm_assessment.get("detail_tags", []),
            "arm_assessment": arm_assessment,
        },
        "plan_narrative": plan_result["narrative"] if plan_result else None,
        "morning_brief": normalize_brief(plan_result.get("morning_brief")) if plan_result else normalize_brief(None),
        "arm_care": plan_result.get("arm_care") if plan_result else None,
        "lifting": plan_result.get("lifting") if plan_result else None,
        "throwing": plan_result.get("throwing") if plan_result else None,
        "warmup": plan_result.get("warmup") if plan_result else None,
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
            "source": plan_result.get("source") if plan_result else None,
            "source_reason": plan_result.get("source_reason") if plan_result else None,
        },
        "actual_logged": None,
        "completed_exercises": {},
        "bot_observations": bot_observations,
    }
    append_log_entry(pitcher_id, entry)

    # Update weekly training state in pitcher model
    try:
        from bot.services.weekly_model import update_week_state_after_checkin, compute_next_day_suggestion
        from bot.services.db import get_training_model, upsert_training_model

        model = get_training_model(pitcher_id)
        threw = False
        throw_type_val = None
        throw_intent_val = (checkin_inputs or {}).get("throw_intent", "")
        if throw_intent_val and throw_intent_val not in ("no_throw", "none", ""):
            threw = True
            throw_type_val = throw_intent_val

        week_state = update_week_state_after_checkin(
            model, today_str,
            lifted=lift_preference not in ("rest", ""),
            lift_focus=lift_preference if lift_preference not in ("auto", "your_call", "") else None,
            threw=threw,
            throw_type=throw_type_val,
        )

        # Compute next-day suggestion
        suggestion = compute_next_day_suggestion(profile, {**model, "current_week_state": week_state})
        week_state["next_day_suggestion"] = suggestion

        model["current_week_state"] = week_state
        upsert_training_model(pitcher_id, model)
    except Exception as e:
        logger.warning(f"Failed to update weekly state for {pitcher_id}: {e}")

    # Recompute phase state from active program (non-blocking — must never fail a check-in)
    try:
        from bot.services.weekly_model import update_phase_state
        update_phase_state(pitcher_id)
    except Exception as exc:
        logger.warning(f"update_phase_state failed for {pitcher_id}: {exc}")

    # Write rich session note to context
    flag = triage_result["flag_level"].upper()
    lifting_summary = ""
    if plan_result and (plan_result.get("lifting") or {}).get("exercises"):
        names = [ex.get("name", "") for ex in plan_result["lifting"]["exercises"][:5]]
        lifting_summary = f"Lift: {', '.join(names)}"
    throwing_summary = ""
    throwing_data = (plan_result.get("throwing") or {}) if plan_result else {}
    if throwing_data.get("type", "none") != "none" and throwing_data.get("type") != "no_throw":
        day_label = throwing_data.get("day_type_label") or throwing_data.get("type", "")
        vol = (throwing_data.get("volume_summary") or {}).get("total_throws_estimate")
        intensity = throwing_data.get("intensity_range", "")
        parts = [f"Throwing: {day_label}"]
        if intensity:
            parts.append(f"({intensity})")
        if vol:
            parts.append(f"~{vol} throws")
        phases = throwing_data.get("phases") or []
        phase_names = [p.get("phase_name", "") for p in phases if p.get("exercises")]
        if phase_names:
            parts.append(f"[{' -> '.join(phase_names)}]")
        throwing_summary = " ".join(parts)
    mods = plan_result.get("modifications_applied", []) if plan_result else []
    mods_str = f" Mods: {', '.join(mods[:3])}" if mods else ""

    session_note = f"Arm {arm_feel}/10, sleep {sleep_hours}h, {flag} flag. {lifting_summary}. {throwing_summary}.{mods_str}".strip()
    if arm_report:
        session_note = f'Arm: "{arm_report}" ({arm_feel}/10). {session_note}'
    elif arm_assessment.get("summary"):
        session_note = f'{arm_assessment["summary"]} {session_note}'
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
        "source": plan_result.get("source") if plan_result else None,
        "source_reason": plan_result.get("source_reason") if plan_result else None,
        "arm_assessment": arm_assessment,
    }
