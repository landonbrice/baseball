"""Program Engine v1 — the live drive (Sprint C).

Composes today's plan by PROJECTING the pitcher's active engine-authored
program through the readiness modulation in `projection.py`. This is the
"propose-and-confirm" drive ratified 2026-07-13:

  - GREEN morning  → the prescribed day ships silently (no proposal).
  - YELLOW/RED/CRITICAL_RED → the modulated day ships with a `proposal`
    envelope (`status="proposed"`, `auto_accept=True`): the conservative
    version is live immediately; the pitcher's Confirm is acknowledgment,
    not a gate. No response → the proposal stands.
  - No live LLM call anywhere in this path — mornings are instant and
    deterministic by constitution.

Feature gate: `pitcher_training_model.feature_flags.program_engine_v1`
(per-pitcher, same idiom as `program_aware_plan_gen`). The check-in fork in
`checkin_service._select_plan_path` tries this path FIRST; any failure or
non-coverage (no active engine program, date outside program span) returns
None and falls through to the existing program-aware / legacy paths.

Governor signals from the projection policy are LOGGED for v2 re-pacing but
not acted on — the program is never mutated by a morning check-in.
"""
from __future__ import annotations

import json
import logging
from datetime import date as _date
from pathlib import Path
from typing import Optional

from bot.services.program_engine.projection import ProjectedDay, project_days
from bot.services.program_engine.schemas import Day

logger = logging.getLogger(__name__)

# Projection policy for the live drive. banked_deviation gives the richest
# governor telemetry (bank crossings + single-day cliffs) while still
# absorbing small day-to-day variance — signals are logged, not acted on.
DRIVE_POLICY = "banked_deviation"


# ─────────────────────────────────────────────────────────────────────────────
# Exercise name resolution — id → display name (live table, snapshot fallback)
# ─────────────────────────────────────────────────────────────────────────────

_NAME_MAP_CACHE: Optional[dict] = None


def _exercise_name_map() -> dict:
    """id → name for rendering engine-prescribed exercises in the DailyCard."""
    global _NAME_MAP_CACHE
    if _NAME_MAP_CACHE is not None:
        return _NAME_MAP_CACHE
    rows: list[dict] = []
    try:
        from bot.services.db import get_client

        resp = get_client().table("exercises").select("id, name").execute()
        rows = resp.data or []
    except Exception as e:
        logger.warning("drive: live exercise name map unavailable (%s); using snapshot", e)
    if not rows:
        snapshot = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "exercises_snapshot.json"
        try:
            rows = json.loads(snapshot.read_text())
        except Exception:
            rows = []
    _NAME_MAP_CACHE = {r["id"]: r.get("name") or r["id"] for r in rows if r.get("id")}
    return _NAME_MAP_CACHE


# ─────────────────────────────────────────────────────────────────────────────
# Program loading
# ─────────────────────────────────────────────────────────────────────────────


def find_active_engine_program(pitcher_id: str, target_date: _date) -> Optional[dict]:
    """Return the active engine-authored program row covering `target_date`.

    Engine programs are identified by a non-null `engine_version` column.
    Returns None when there's no such program or the date falls outside its
    day span — the caller falls through to the next plan path.
    """
    from bot.services.db import get_client

    rows = (
        get_client()
        .table("programs")
        .select("program_id, domain, generated_schedule_json, start_date, nominal_end_date, engine_version")
        .eq("pitcher_id", pitcher_id)
        .eq("status", "active")
        .not_.is_("engine_version", "null")
        .execute()
        .data
        or []
    )
    iso = target_date.isoformat()
    for row in rows:
        days = (row.get("generated_schedule_json") or {}).get("days") or []
        if any(d.get("date") == iso for d in days):
            return row
    return None


def _load_days(row: dict) -> list[Day]:
    raw = (row.get("generated_schedule_json") or {}).get("days") or []
    return [Day.model_validate(d) for d in raw]


# ─────────────────────────────────────────────────────────────────────────────
# Readiness assembly
# ─────────────────────────────────────────────────────────────────────────────


def _build_readiness(triage_result: dict, checkin_inputs: Optional[dict]) -> dict:
    """Map triage output + raw check-in atoms onto the projection's readiness shape."""
    triage_result = triage_result or {}
    checkin_inputs = checkin_inputs or {}
    return {
        "flag_level": (triage_result.get("flag_level") or "").upper() or None,
        "category_scores": triage_result.get("category_scores") or {},
        "modifications": list(triage_result.get("modification_flags") or []),
        "arm_feel": checkin_inputs.get("arm_feel") or triage_result.get("arm_feel"),
        "energy": checkin_inputs.get("energy"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Day → plan_result conversion
# ─────────────────────────────────────────────────────────────────────────────


def _throwing_section(day: Day) -> Optional[dict]:
    """Engine 5-tuple → the throwing dict the DailyCard renders.

    `type` must be a non-'none' string for the section to show; `phases[*]
    .exercises[*]` items need `name`/`drill` keys for guided-flow tracking.
    """
    five = day.throwing_5tuple
    if day.is_rest or five is None or (five.throw_count or 0) <= 0:
        return None
    drill = (five.drill or "throwing").replace("_", " ")
    summary = f"{five.throw_count} throws @ {five.distance_ft}ft · {five.intensity_pct}% intent"
    return {
        "type": "program_throwing",
        "day_type": "program_throwing",
        "day_label": day.day_focus or drill.title(),
        "intent": f"{five.intensity_pct}%",
        "intensity_range": f"{five.intensity_pct}%",
        "distance_ft": five.distance_ft,
        "throw_count": five.throw_count,
        "volume_summary": summary,
        "phases": [
            {
                "name": "Program throwing",
                "exercises": [
                    {
                        "name": drill.title(),
                        "drill": five.drill,
                        "detail": summary,
                        "note": five.note,
                    }
                ],
            }
        ],
    }


def _lifting_sections(day: Day, name_map: dict) -> tuple[Optional[dict], list[dict]]:
    """Engine lifting_blocks → (flat `lifting` dict, `exercise_blocks` list).

    Both legacy locations are populated coherently — the DailyCard dual-source
    gotcha (top-level `lifting.exercises` vs `plan_generated.exercise_blocks`)
    demands they agree.
    """
    if not day.lifting_blocks:
        return None, []
    flat: list[dict] = []
    blocks: list[dict] = []
    for block in day.lifting_blocks:
        block_exs = []
        for ex in block.exercises:
            item = {
                "exercise_id": ex.exercise_id,
                "name": name_map.get(ex.exercise_id, ex.exercise_id),
                "sets": ex.sets,
                "reps": ex.reps,
                "intensity": ex.intensity,
                "superset_group": ex.superset_group,
                "note": ex.note,
            }
            block_exs.append(dict(item))
            flat.append(dict(item))
        blocks.append({"block_name": block.block_name, "exercises": block_exs})
    return {"exercises": flat}, blocks


def _describe_changes(projected: ProjectedDay) -> list[str]:
    """Human-readable delta between intended and delivered, for the proposal."""
    intended, delivered = projected.intended, projected.delivered
    changes: list[str] = []
    it, dt = intended.throwing_5tuple, delivered.throwing_5tuple
    if it is not None and dt is None:
        changes.append(f"Throwing pulled ({it.throw_count} throws → rest)")
    elif it is not None and dt is not None:
        if dt.throw_count != it.throw_count:
            changes.append(f"Throws {it.throw_count} → {dt.throw_count}")
        if dt.intensity_pct != it.intensity_pct:
            changes.append(f"Intent {it.intensity_pct}% → {dt.intensity_pct}%")
        if dt.distance_ft != it.distance_ft:
            changes.append(f"Distance {it.distance_ft}ft → {dt.distance_ft}ft")
    n_int = sum(len(b.exercises) for b in intended.lifting_blocks)
    n_del = sum(len(b.exercises) for b in delivered.lifting_blocks)
    if n_del < n_int:
        changes.append(f"Lifting trimmed {n_int} → {n_del} exercises")
    if delivered.is_rest and not intended.is_rest:
        changes.append("Full rest day (was a training day)")
    return changes


def _morning_brief(day: Day, projected: ProjectedDay, program_row: dict) -> str:
    cls = projected.modulation.get("reason", "green")
    week = day.day_index // 7 + 1
    base = f"Week {week}, day {day.day_index % 7 + 1} of your program"
    if day.phase_name:
        base += f" — {day.phase_name}"
    base += "."
    if day.day_focus:
        base += f" {day.day_focus}"
    if cls == "green":
        return base + " You're green — the day ships as written."
    changes = _describe_changes(projected)
    note = "; ".join(changes[:3]) if changes else "volume dialed back"
    return base + f" Your check-in came back {cls.upper()}, so today is adjusted: {note}. Confirm or adjust below."


def compose_drive_plan(
    pitcher_id: str,
    triage_result: dict,
    profile: dict,
    target_date: _date,
    *,
    checkin_inputs: Optional[dict] = None,
) -> Optional[dict]:
    """Compose today's plan by projecting the active engine program.

    Returns a legacy-shaped `plan_result` tagged `source='engine_projected'`,
    or None when no active engine program covers `target_date` (caller falls
    through). Raises nothing fatal by contract — callers wrap in try/except
    and fall through on any exception.
    """
    row = find_active_engine_program(pitcher_id, target_date)
    if row is None:
        return None

    days = _load_days(row)
    readiness = _build_readiness(triage_result, checkin_inputs)
    projected = project_days(days, target_date, readiness, policy=DRIVE_POLICY)
    delivered = projected.delivered
    modulated = projected.modulation.get("reason", "green") != "green"

    name_map = _exercise_name_map()
    lifting, exercise_blocks = _lifting_sections(delivered, name_map)
    throwing = _throwing_section(delivered)

    # Warmup rides along from the legacy builder — deterministic, no LLM.
    warmup = None
    try:
        from bot.services.plan_generator import _build_warmup_block

        warmup = _build_warmup_block(profile, delivered.day_index % 7, triage_result)
    except Exception:
        logger.warning("drive: warmup builder failed, shipping without warmup", exc_info=True)

    brief = _morning_brief(delivered, projected, row)
    changes = _describe_changes(projected) if modulated else []

    proposal = None
    if modulated:
        proposal = {
            "status": "proposed",
            "auto_accept": True,
            "readiness_class": projected.modulation.get("reason"),
            "changes": changes,
        }

    if projected.governor_signal:
        logger.info(
            "drive_governor_signal",
            extra={
                "pitcher_id": pitcher_id,
                "program_id": row.get("program_id"),
                "signal": projected.governor_signal,
            },
        )

    plan = {
        "source": "engine_projected",
        "source_reason": None,
        "day_focus": delivered.day_focus,
        "rotation_day": delivered.day_index % 7,
        "template_day": delivered.template_key,
        "morning_brief": brief,
        "narrative": brief,
        "warmup": warmup,
        "throwing": throwing,
        "lifting": lifting,
        "exercise_blocks": exercise_blocks,
        "arm_care": None,
        "notes": changes,
        "modifications_applied": list((triage_result or {}).get("modification_flags") or []),
        "proposal": proposal,
        "engine_projection": {
            "program_id": row.get("program_id"),
            "day_index": delivered.day_index,
            "phase_name": delivered.phase_name,
            "is_rest": delivered.is_rest,
            "is_deload": delivered.is_deload,
            "modulation": projected.modulation,
            "governor_signal": projected.governor_signal,
        },
    }

    logger.info(
        "engine_drive_compose",
        extra={
            "pitcher_id": pitcher_id,
            "program_id": row.get("program_id"),
            "day_index": delivered.day_index,
            "readiness_class": projected.modulation.get("reason"),
            "modulated": modulated,
            "plan_source": "engine_projected",
        },
    )
    return plan
