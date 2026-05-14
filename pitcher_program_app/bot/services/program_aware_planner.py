"""Program-aware daily-plan composition (Plan 4 → Plan 6/A1 → hotfix).

Three responsibilities, layered:

  1. ``compose_prescribed_plan`` — pure composition of throwing_rx + lifting_rx
     + profile into a SNAPSHOT envelope. Useful for audit/persistence and as
     the input to ``apply_triage_to_program_plan``. Does NOT produce a
     plan_result shaped like ``plan_generator.generate_plan``.

  2. ``apply_triage_to_program_plan`` — pure triage adjustment of a snapshot.
     Used by callers that only need the slim shape; tests live here.

  3. ``compose_program_aware_plan`` (new, hotfix) — async, calls
     ``plan_generator.generate_plan`` with ``rotation_day_override`` set from
     the program prescription so the legacy enrichment pipeline (warmup,
     mobility, arm care, exercise pool, LLM brief, throwing template, day_focus)
     runs end-to-end. The result is tagged ``source='program_prescribed'`` and
     carries ``program_prescription_snapshot`` so downstream surfaces can
     see what the program prescribed for today.

     Counter-hold semantics (Red / Critical Red → hold instead of advance) are
     extracted into ``derive_hold_event`` and computed independently from plan
     content. ``checkin_service`` consumes that hold_event to route persistence
     through ``db.write_daily_entry_with_counter_advance``.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

# Top-level import is safe — plan_generator does not import this module or
# checkin_service at module load. Putting it here (instead of lazy-importing
# inside compose_program_aware_plan) lets tests patch via
# ``patch.object(program_aware_planner, "generate_plan", ...)``, mirroring the
# pattern used in checkin_service tests.
from bot.services.plan_generator import generate_plan


def compose_prescribed_plan(
    throwing_rx: Optional[dict],
    lifting_rx: Optional[dict],
    profile: dict,
    target_date: date,
) -> Optional[dict]:
    """Compose today's prescribed plan SNAPSHOT from active program(s).

    Returns None when neither domain has an active program prescription
    (caller falls back to legacy plan_generator). The returned shape is the
    slim snapshot envelope — it is NOT a plan_result. For a full
    plan_result with all legacy enrichment, use ``compose_program_aware_plan``.
    """
    if throwing_rx is None and lifting_rx is None:
        return None
    return {
        "source": "program_prescribed",
        "target_date": target_date.isoformat(),
        "throwing": throwing_rx,
        "lifting": lifting_rx,
        "program_prescription_snapshot": {
            "throwing": throwing_rx,
            "lifting": lifting_rx,
        },
    }


def apply_triage_to_program_plan(
    prescribed: dict,
    triage_result: dict,
) -> tuple[dict, Optional[dict]]:
    """Apply triage flag to a program-prescribed plan SNAPSHOT.

    Returns ``(final_plan, hold_event)``. ``hold_event`` is None when the
    counter advances (Green/Yellow); populated dict when the counter holds
    (Red / Critical Red). Approach B: program holds, triage pauses the
    counter rather than modifying the program in place.

    Operates on the slim snapshot shape from ``compose_prescribed_plan`` —
    NOT on the full plan_result from ``compose_program_aware_plan``. The
    live check-in pipeline uses ``derive_hold_event`` directly and lets
    triage flow into ``generate_plan`` via its normal channels instead.
    """
    flag = (triage_result or {}).get("flag_level", "green")
    modification_flags = list((triage_result or {}).get("modification_flags") or [])
    arm_feel = (triage_result or {}).get("arm_feel")
    is_critical_red = flag == "red" and (
        "arm_shutdown" in modification_flags or (arm_feel is not None and arm_feel <= 2)
    )

    final = dict(prescribed or {})
    final["triage_flag"] = flag
    final["modification_flags"] = modification_flags

    if flag == "green":
        return final, None

    if flag == "yellow":
        # Modification tags carried; downstream exercise_pool applies YELLOW logic.
        return final, None

    # red / critical_red
    if final.get("throwing"):
        if is_critical_red:
            final["throwing"] = {"shutdown": True, "original": prescribed.get("throwing")}
            final["auto_alert_coach"] = True
        else:
            final["throwing"] = {"recovery_only": True, "original": prescribed.get("throwing")}
    if final.get("lifting"):
        final["lifting"] = {**final["lifting"], "intensity": "light"}

    hold_event = {
        "reason_code": "critical_red" if is_critical_red else "red",
        "triage_result": triage_result,
    }
    return final, hold_event


def derive_hold_event(triage_result: dict) -> Optional[dict]:
    """Counter-hold decision for the program-aware path.

    Red and Critical Red triage pause the program counter (Approach B): the
    daily entry still writes, but ``write_daily_entry_with_counter_advance``
    logs a hold_event instead of advancing ``current_day_index``. Green and
    Yellow let the counter advance.
    """
    flag = (triage_result or {}).get("flag_level", "green")
    if flag != "red":
        return None
    modification_flags = list((triage_result or {}).get("modification_flags") or [])
    arm_feel = (triage_result or {}).get("arm_feel")
    is_critical_red = (
        "arm_shutdown" in modification_flags
        or (arm_feel is not None and arm_feel <= 2)
    )
    return {
        "reason_code": "critical_red" if is_critical_red else "red",
        "triage_result": triage_result,
    }


def resolve_program_rotation_day(
    throwing_rx: Optional[dict],
    lifting_rx: Optional[dict],
) -> Optional[int]:
    """Map a program-day prescription to an integer rotation day.

    The schedule rows store ``template_key`` (e.g. ``"day_3"``) plus
    ``day_index``. We prefer ``template_key`` because it maps directly to the
    7-day rotation template; ``day_index`` is the fallback. Throwing wins on
    tie because throwing is the dominant cadence driver.
    """
    rx = throwing_rx or lifting_rx
    if not rx:
        return None
    template_key = rx.get("template_key") or ""
    if isinstance(template_key, str) and template_key.startswith("day_"):
        try:
            return int(template_key.split("_", 1)[1])
        except (ValueError, IndexError):
            pass
    day_index = rx.get("day_index")
    if isinstance(day_index, int):
        return day_index
    return None


async def compose_program_aware_plan(
    pitcher_id: str,
    triage_result: dict,
    throwing_rx: Optional[dict],
    lifting_rx: Optional[dict],
    profile: dict,
    target_date: date,
    *,
    checkin_inputs: Optional[dict] = None,
    triage_rationale_detail: Optional[dict] = None,
) -> Optional[dict]:
    """Compose a fully-enriched daily plan anchored on the active program.

    Returns a ``plan_result`` shaped identically to ``generate_plan`` —
    warmup, mobility, arm_care, lifting (from exercise_pool), throwing,
    morning_brief, narrative, exercise_blocks, day_focus, all present — but
    with ``rotation_day`` driven by the program's ``template_key`` /
    ``day_index`` instead of the legacy ``days_since_outing`` derivation.

    Tagged ``source='program_prescribed'``. ``source_reason`` retains its
    legacy meaning: None on LLM-enriched success, populated string on Python
    fallback (e.g. ``llm_timeout:TimeoutError: ...``). The slim prescription
    envelope is preserved under ``program_prescription_snapshot`` so audit
    surfaces and the coach UI can see what the program prescribed for today.

    Returns None when neither domain has an active program prescription
    (caller falls back to legacy plan_generator).
    """
    if throwing_rx is None and lifting_rx is None:
        return None

    rotation_day_override = resolve_program_rotation_day(throwing_rx, lifting_rx)

    plan = await generate_plan(
        pitcher_id,
        triage_result,
        checkin_inputs=checkin_inputs,
        triage_rationale_detail=triage_rationale_detail,
        rotation_day_override=rotation_day_override,
    )
    if plan is None:
        return None

    # Promote source lineage. Keep source_reason as-is so the enrichment
    # observability (LLM timeout / parse failure) still surfaces.
    plan["source"] = "program_prescribed"
    plan["program_prescription_snapshot"] = {
        "throwing": throwing_rx,
        "lifting": lifting_rx,
    }
    return plan
