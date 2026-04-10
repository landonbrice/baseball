"""Training program service. Pure functions + thin DB wrappers.

A "program" is a multi-week training arc with one or more phases. Each pitcher
has zero or one active program at a time, tracked via
pitcher_training_model.active_program_id.

This module is responsible for:
  - computing the current phase from a program + date (pure)
  - creating, listing, deactivating training_programs rows (DB) — added in Task 1.4
  - loading active program + phase state for a pitcher — added in Task 1.4

It does NOT touch plan generation directly. plan_generator.py reads
phase state from current_week_state.phase, which weekly_model writes.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def compute_current_phase(program: dict, as_of: Optional[date] = None) -> dict:
    """Walk a program's phases_snapshot to determine current phase + week.

    Args:
        program: dict with keys 'start_date' (date or ISO str), 'phases_snapshot' (list).
        as_of: date to compute against. Defaults to today (Chicago tz at the call site).

    Returns:
        dict matching current_week_state.phase shape:
          {
            "phase_id": str,
            "name": str,
            "phase_type": str,
            "week_in_phase": int,           # 1-indexed
            "week_in_program": int,         # 1-indexed
            "training_intent": Optional[str],
            "is_past_end": bool,            # True if as_of is past the last phase
          }

    Pure function — no DB, no clock. Easy to unit test against fixed dates.
    """
    if as_of is None:
        as_of = date.today()

    start_date = program["start_date"]
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    phases = program.get("phases_snapshot") or []
    if not phases:
        return {
            "phase_id": None,
            "name": "Unknown",
            "phase_type": None,
            "week_in_phase": 0,
            "week_in_program": 0,
            "training_intent": None,
            "is_past_end": False,
        }

    days_since_start = (as_of - start_date).days
    if days_since_start < 0:
        # Program starts in the future. Treat as week 1 of phase 1.
        first = phases[0]
        return {
            "phase_id": first["phase_id"],
            "name": first["name"],
            "phase_type": first["phase_type"],
            "week_in_phase": 1,
            "week_in_program": 1,
            "training_intent": first.get("default_training_intent"),
            "is_past_end": False,
        }

    # Use ISO calendar weeks so that week boundaries follow Monday-aligned weeks.
    # This means April 1 (Wed) and April 7 (Tue) land in different ISO weeks,
    # making April 7 week 2 of the program rather than week 1 (which floor(6/7)+1 would give).
    s_iso = start_date.isocalendar()
    a_iso = as_of.isocalendar()
    iso_week_diff = (a_iso.year - s_iso.year) * 52 + (a_iso.week - s_iso.week)
    week_in_program = iso_week_diff + 1

    cumulative_weeks = 0
    for phase in phases:
        phase_weeks = phase.get("week_count", 0)
        if week_in_program <= cumulative_weeks + phase_weeks:
            week_in_phase = week_in_program - cumulative_weeks
            intent = _resolve_phase_intent(phase, week_in_phase)
            return {
                "phase_id": phase["phase_id"],
                "name": phase["name"],
                "phase_type": phase["phase_type"],
                "week_in_phase": week_in_phase,
                "week_in_program": week_in_program,
                "training_intent": intent,
                "is_past_end": False,
            }
        cumulative_weeks += phase_weeks

    # Past the last phase — clamp to final phase, mark as past end
    last = phases[-1]
    return {
        "phase_id": last["phase_id"],
        "name": last["name"],
        "phase_type": last["phase_type"],
        "week_in_phase": last.get("week_count", 0),
        "week_in_program": cumulative_weeks,
        "training_intent": last.get("default_training_intent"),
        "is_past_end": True,
    }


def _resolve_phase_intent(phase: dict, week_in_phase: int) -> Optional[str]:
    """Pick the training intent for a given week within a phase.

    Microcycle (if present) overrides default. In v1 this is structurally
    complete but unreachable for in-season pitchers.
    """
    microcycle = phase.get("microcycle")
    if microcycle:
        for week_def in microcycle:
            if week_def.get("week") == week_in_phase:
                return week_def.get("training_intent")
    return phase.get("default_training_intent")
