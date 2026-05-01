"""Plan 4: Program-aware daily-plan composition.

Three responsibilities:
  - compose_prescribed_plan: pure composition of throwing_rx + lifting_rx + profile
  - apply_triage_to_program_plan: pure adjustment of prescribed plan based on triage flag
  - advance_or_hold_counter: transactional counter update + hold event (Task 4.3)
"""
from __future__ import annotations

from datetime import date
from typing import Optional


def compose_prescribed_plan(
    throwing_rx: Optional[dict],
    lifting_rx: Optional[dict],
    profile: dict,
    target_date: date,
) -> Optional[dict]:
    """Compose today's prescribed plan from active program(s).

    Returns None when neither domain has an active program prescription
    (caller falls back to legacy plan_generator).
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
    """Apply triage flag to a program-prescribed plan. Returns (final_plan, hold_event).

    hold_event is None when counter advances (Green/Yellow); populated dict when
    counter holds (Red/Critical Red). Approach B: program holds, triage pauses
    the counter rather than modifying the program in place.
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
