"""Program Engine v1 — content invariants (Task 2.3).

Implements §7 invariants 6–7 as pure functions on `PitcherProgram`:
  (6) Equipment hard-filter — every exercise's equipment present in
       `pitcher_training_model.equipment_constraints`.
       Injury contraindications — read `pitcher_training_model.active_modifications`
       and reject exercises whose `contraindications` tag matches the mod.
  (7) Exercise IDs resolve via `bot.services.exercise_alias.resolve_alias`
       (canonical ex_NNN already; alias resolution is for sanity check that
       the id exists in the live `exercises` table).

These are CONTENT invariants — they need the live `exercises` table and the
per-pitcher `pitcher_training_model`. Pure functions accept that data as
arguments; no DB I/O inside.
"""
from __future__ import annotations

from typing import Optional, Sequence

from bot.services.exercise_alias import UnknownExerciseAlias, try_resolve_alias
from bot.services.program_engine.load_math import GuardrailViolation
from bot.services.program_engine.schemas import LiftingExercise, PitcherProgram


# ─────────────────────────────────────────────────────────────────────────────
# Exercise context — what callers pass in
# ─────────────────────────────────────────────────────────────────────────────


def _build_exercise_index(exercises_rows: Sequence[dict]) -> dict[str, dict]:
    """Map ex_id → row dict for fast lookup."""
    return {r["id"]: r for r in exercises_rows if r.get("id")}


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 6a — Equipment hard-filter
# ─────────────────────────────────────────────────────────────────────────────


def check_equipment(
    program: PitcherProgram,
    exercises_rows: Sequence[dict],
    available_equipment: Sequence[str],
) -> list[GuardrailViolation]:
    """Every exercise's required equipment must be in `available_equipment`.

    `exercises.equipment` is either a string ("barbell") or a list. We tolerate
    both. An exercise missing the equipment field is treated as "no equipment
    required" (bodyweight) and never fails.

    `pitcher_training_model.equipment_constraints` is typically a list like
    `["barbell", "DB", "trap_bar", "bands", "j_band"]`.
    """
    index = _build_exercise_index(exercises_rows)
    available = set(s.lower() for s in available_equipment if s)
    if not available:
        # No constraints provided → no violations (open gym assumption)
        return []
    violations: list[GuardrailViolation] = []
    seen_misses: set[tuple[str, str]] = set()  # dedupe by (ex_id, equipment)
    for d in program.days:
        for block in d.lifting_blocks:
            for ex in block.exercises:
                row = index.get(ex.exercise_id)
                if not row:
                    continue
                required = row.get("equipment")
                if not required:
                    continue
                required_list = [required] if isinstance(required, str) else list(required or [])
                for req in required_list:
                    if not req:
                        continue
                    req_lower = str(req).lower()
                    if req_lower not in available:
                        key = (ex.exercise_id, req_lower)
                        if key in seen_misses:
                            continue
                        seen_misses.add(key)
                        violations.append(
                            GuardrailViolation(
                                kind="equipment_unavailable",
                                where={"day_index": d.day_index, "exercise_id": ex.exercise_id},
                                actual=req_lower,
                                expected=f"one of {sorted(available)}",
                                severity="error",
                                repair_hint="swap_exercise_for_equipment_compatible_alternative",
                            )
                        )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 6b — Injury contraindications
# ─────────────────────────────────────────────────────────────────────────────


def check_contraindications(
    program: PitcherProgram,
    exercises_rows: Sequence[dict],
    active_modifications: Sequence[str],
) -> list[GuardrailViolation]:
    """Reject any exercise whose `contraindications` overlaps `active_modifications`.

    `exercises.contraindications` is a jsonb list of modification-tag strings
    (e.g. `["acute_medial_elbow_pain"]`). `active_modifications` is the
    pitcher's current set from `pitcher_training_model.active_modifications`.
    """
    if not active_modifications:
        return []
    index = _build_exercise_index(exercises_rows)
    active = set(str(m).lower() for m in active_modifications)
    violations: list[GuardrailViolation] = []
    for d in program.days:
        for block in d.lifting_blocks:
            for ex in block.exercises:
                row = index.get(ex.exercise_id)
                if not row:
                    continue
                contras = row.get("contraindications") or []
                if not contras:
                    continue
                hit = active & set(str(c).lower() for c in contras)
                if hit:
                    violations.append(
                        GuardrailViolation(
                            kind="contraindicated_exercise",
                            where={"day_index": d.day_index, "exercise_id": ex.exercise_id},
                            actual=sorted(hit),
                            expected="none of the pitcher's active modifications",
                            severity="error",
                            repair_hint="swap_to_non_contraindicated_alternative",
                        )
                    )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 7 — Exercise IDs resolve
# ─────────────────────────────────────────────────────────────────────────────


def check_exercise_ids_resolve(
    program: PitcherProgram,
    exercises_rows: Optional[Sequence[dict]] = None,
) -> list[GuardrailViolation]:
    """Every `LiftingExercise.exercise_id` resolves against the live exercises table.

    If `exercises_rows` is provided, we check directly against it (fast path).
    Otherwise we fall back to `bot.services.exercise_alias` which lazy-builds
    from Supabase.

    This is the FATAL guardrail — unknown IDs cannot be repaired automatically;
    the orchestrator (Task 2.4) goes straight to re-prompt or fallback.
    """
    if exercises_rows is not None:
        index = _build_exercise_index(exercises_rows)
    else:
        index = None
    violations: list[GuardrailViolation] = []
    seen_bad: set[str] = set()
    for d in program.days:
        for block in d.lifting_blocks:
            for ex in block.exercises:
                if ex.exercise_id in seen_bad:
                    continue
                if index is not None:
                    if ex.exercise_id not in index:
                        seen_bad.add(ex.exercise_id)
                        violations.append(
                            GuardrailViolation(
                                kind="unknown_exercise_id",
                                where={"day_index": d.day_index, "exercise_id": ex.exercise_id},
                                actual=ex.exercise_id,
                                expected="canonical id in `exercises` table",
                                severity="error",
                                repair_hint=None,  # FATAL — no repair
                            )
                        )
                else:
                    # Use the alias resolver (live Supabase path)
                    if try_resolve_alias(ex.exercise_id) is None:
                        seen_bad.add(ex.exercise_id)
                        violations.append(
                            GuardrailViolation(
                                kind="unknown_exercise_id",
                                where={"day_index": d.day_index, "exercise_id": ex.exercise_id},
                                actual=ex.exercise_id,
                                expected="canonical id in `exercises` table",
                                severity="error",
                                repair_hint=None,
                            )
                        )
    return violations
