"""Layer 3 of the Program Builder funnel: schedule generation + hard-invariant validation.

v1 implementation builds a deterministic schedule from the template's
week_scaffold_json (no LLM call). Plan 3 will replace _build_schedule_from_scaffold
with an LLM-driven path; the validation layer stays the same.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


_DEFAULT_WEEKS = 12  # default tuning when retry-with-defaults kicks in


def _load_template(template_id: str) -> Optional[dict]:
    from bot.services import db
    return db.get_block_library_row(template_id)


def _load_pitcher_profile(pitcher_id: str) -> Optional[dict]:
    from bot.services import db
    try:
        return db.get_pitcher(pitcher_id)
    except KeyError:
        return None


def _persist_program(row: dict) -> str:
    from bot.services import db
    return db.create_program(row)


def _record_failure(session_id: str | None, attempt_number: int, kind: str,
                     llm_response: dict | None = None) -> None:
    from bot.services import db
    db.record_generation_failure(
        session_id=session_id,
        attempt_number=attempt_number,
        validation_failure_kind=kind,
        llm_response=llm_response,
    )


def _build_schedule_from_scaffold(template: dict, tuned_spec: dict, start_date: date) -> dict:
    """Build a day-by-day schedule by repeating the template's rotation."""
    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    total_days = weeks * 7
    scaffold = (template.get("week_scaffold_json") or {})
    rotation = scaffold.get("rotation_template_keys") or []
    if not rotation:
        return {"days": [], "scaffold_kind": "empty"}

    days = []
    for i in range(total_days):
        rk = rotation[i % len(rotation)]
        days.append({
            "day_index": i,
            "template_key": rk["template_key"],
            "date": (start_date + timedelta(days=i)).isoformat(),
        })
    return {
        "scaffold_kind": scaffold.get("scaffold_kind", "calendar_relative_repeating_7day"),
        "days": days,
    }


def _validate_schedule(schedule: dict, tuned_spec: dict, template: dict, profile: dict) -> list[str]:
    """Return a list of validation_failure_kind strings; empty = valid."""
    failures: list[str] = []

    # Total duration matches chosen weeks
    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    expected_days = weeks * 7
    actual_days = len((schedule or {}).get("days") or [])
    if actual_days != expected_days:
        failures.append("duration_mismatch")

    # Per-week volume within template caps — v1: no caps declared, no-op.
    # Intensity ramp monotonic where required — v1: not declared in scaffold, no-op.
    # Every referenced exercise exists in `exercises` — v1: scaffold is template-key based,
    #   actual exercise binding happens at consume-time via exercise_pool, so no-op here.
    # No contraindicated exercise for active injuries — v1: same reasoning.

    return failures


def generate_program(pitcher_id: str, template_id: str, tuned_spec: dict,
                      constraint_envelope: dict, session_id: str | None) -> dict:
    """Layer 3: produce a draft program for the pitcher.

    Returns the persisted program row. Status will be 'draft' on success or 'error'
    after two consecutive validation failures (the second falls back to default tuning).
    """
    template = _load_template(template_id)
    if not template:
        raise ValueError(f"template not found: {template_id}")

    profile = _load_pitcher_profile(pitcher_id) or {}
    start_date_str = constraint_envelope.get("start_date") or date.today().isoformat()
    start_date = date.fromisoformat(start_date_str)

    # Attempt 1: with tuned_spec
    schedule = _build_schedule_from_scaffold(template, tuned_spec, start_date)
    failures = _validate_schedule(schedule, tuned_spec, template, profile)
    final_status = "draft"

    if failures:
        _record_failure(session_id, 1, ",".join(failures))
        # Attempt 2: default tuning
        default_spec = {"weeks": _DEFAULT_WEEKS}
        schedule = _build_schedule_from_scaffold(template, default_spec, start_date)
        failures2 = _validate_schedule(schedule, default_spec, template, profile)
        if failures2:
            _record_failure(session_id, 2, ",".join(failures2))
            final_status = "error"
        tuned_spec = default_spec

    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    nominal_end_date = start_date + timedelta(days=weeks * 7)

    row = {
        "pitcher_id": pitcher_id,
        "parent_template_id": template_id,
        "domain": template.get("domain"),
        "tuned_spec_json": tuned_spec,
        "generated_schedule_json": schedule,
        "start_date": start_date.isoformat(),
        "nominal_end_date": nominal_end_date.isoformat(),
        "current_day_index": 0,
        "held_days_count": 0,
        "status": final_status,
        "created_by": pitcher_id,  # caller may override via constraint_envelope
        "created_by_role": constraint_envelope.get("created_by_role", "pitcher"),
    }
    if "created_by" in constraint_envelope:
        row["created_by"] = constraint_envelope["created_by"]

    program_id = _persist_program(row)
    row["program_id"] = program_id
    return row
