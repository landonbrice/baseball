"""Program Engine v1 — validate→repair→reject orchestrator (Task 2.4).

Public surface:
- `validate_program(program, pitcher_context, max_repair_passes=3) → ValidationResult`

Runs all guardrails (Tasks 2.1, 2.2, 2.3) in one pass, classifies violations,
attempts up to N deterministic repair passes, and returns:
  - status: "valid" | "repaired" | "reject"
  - program: the (possibly repaired) program
  - violations: remaining violations
  - repair_log: list of {pass, kind, where, applied}

`pitcher_context` shape:
  {
    "exercises_rows": list[dict],          # live exercises table snapshot
    "available_equipment": list[str],      # from pitcher_training_model
    "active_modifications": list[str],     # from pitcher_training_model
    "tag_lookup": dict[ex_id, set[str]],   # for structural lifting checks
  }

Repair strategies are bounded + conservative; non-repairable categories
(`unknown_exercise_id`, `acwr_hard_cap_exceeded`) skip the repair loop and
land in the reject bucket immediately.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from bot.services.program_engine.content_invariants import (
    check_contraindications,
    check_equipment,
    check_exercise_ids_resolve,
)
from bot.services.program_engine.load_math import (
    GuardrailViolation,
    check_acwr_invariant,
)
from bot.services.program_engine.schemas import (
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
)
from bot.services.program_engine.structural_invariants import (
    check_deload_cadence,
    check_fpm_cadence,
    check_intent_monotonicity,
    check_phase_gates,
    check_pull_push_ratio,
)


# Non-repairable kinds — orchestrator skips the repair loop for these and
# returns `reject` (so the caller's re-prompt path runs).
FATAL_KINDS: frozenset[str] = frozenset({
    "unknown_exercise_id",
    "acwr_hard_cap_exceeded",
})


@dataclass
class ValidationResult:
    status: Literal["valid", "repaired", "reject"]
    program: PitcherProgram
    violations: list[GuardrailViolation]
    repair_log: list[dict] = field(default_factory=list)


def _run_all_guardrails(program: PitcherProgram, ctx: dict) -> list[GuardrailViolation]:
    """Run every Phase 2.1/2.2/2.3 checker and concatenate violations."""
    exercises_rows = ctx.get("exercises_rows") or []
    available_equipment = ctx.get("available_equipment") or []
    active_modifications = ctx.get("active_modifications") or []
    tag_lookup = ctx.get("tag_lookup") or {}
    return [
        *check_acwr_invariant(program),
        *check_deload_cadence(program),
        *check_phase_gates(program),
        *check_intent_monotonicity(program),
        *check_pull_push_ratio(program, tag_lookup),
        *check_fpm_cadence(program, tag_lookup),
        *check_equipment(program, exercises_rows, available_equipment),
        *check_contraindications(program, exercises_rows, active_modifications),
        *check_exercise_ids_resolve(program, exercises_rows or None),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Repair strategies — keyed by violation.kind, dispatched in the loop
# ─────────────────────────────────────────────────────────────────────────────


def _repair_deload_cadence(program: PitcherProgram, violation: GuardrailViolation) -> bool:
    """Demote the oldest accumulation week within the violating window to deload.

    Heuristic: find the week with the lowest current intent and flip is_deload=True
    on every day in it. Conservative — doesn't change exercises, just the flag,
    which Phase 4's projection consumes.
    """
    target_week = violation.where.get("week")
    if not target_week:
        return False
    # Search backwards from the violating week for the most-recent non-deload
    # week with the lowest max intent.
    weeks: dict[int, list] = {}
    for d in program.days:
        wk = d.day_index // 7 + 1
        weeks.setdefault(wk, []).append(d)
    candidates = [(wk, ds) for wk, ds in weeks.items() if wk <= target_week and not any(d.is_deload for d in ds)]
    if not candidates:
        return False
    # Pick the week with the lowest max intent (already softest).
    def _wk_max(ds):
        intents = [d.intent_pct or 0 for d in ds]
        return max(intents) if intents else 0
    candidates.sort(key=lambda wd: _wk_max(wd[1]))
    chosen_wk, chosen_days = candidates[0]
    for d in chosen_days:
        d.is_deload = True
    return True


def _repair_intent_monotonicity(program: PitcherProgram, violation: GuardrailViolation) -> bool:
    """Clip every intent in the violating week to the prior week's max + max_jump_pp."""
    target_week = violation.where.get("week")
    if not target_week or target_week < 2:
        return False
    weeks: dict[int, list] = {}
    for d in program.days:
        wk = d.day_index // 7 + 1
        weeks.setdefault(wk, []).append(d)
    prior_days = weeks.get(target_week - 1) or []
    current_days = weeks.get(target_week) or []
    if not prior_days or not current_days:
        return False
    prior_intents = [d.intent_pct or 0 for d in prior_days]
    prior_max = max(prior_intents) if prior_intents else 0
    ceiling = prior_max + 20  # the INTENSITY_JUMP_MAX_PP default
    changed = False
    for d in current_days:
        if d.intent_pct is not None and d.intent_pct > ceiling:
            d.intent_pct = ceiling
            # Sync the 5tuple intensity too
            if d.throwing_5tuple is not None:
                d.throwing_5tuple = d.throwing_5tuple.model_copy(update={"intensity_pct": ceiling})
            changed = True
    return changed


def _repair_phase_gate(program: PitcherProgram, violation: GuardrailViolation) -> bool:
    """Clip high-intent base-phase day to <85%."""
    target_day_idx = violation.where.get("day_index")
    if target_day_idx is None:
        return False
    ceiling = 84  # HIGH_INTENT_THRESHOLD - 1
    for d in program.days:
        if d.day_index == target_day_idx and d.intent_pct is not None and d.intent_pct >= 85:
            d.intent_pct = ceiling
            if d.throwing_5tuple is not None:
                d.throwing_5tuple = d.throwing_5tuple.model_copy(update={"intensity_pct": ceiling})
            return True
    return False


def _repair_acwr_above_band(program: PitcherProgram, violation: GuardrailViolation) -> bool:
    """Shave 10% off intent_pct on the violating day."""
    target_day_idx = violation.where.get("day_index")
    if target_day_idx is None:
        return False
    for d in program.days:
        if d.day_index == target_day_idx:
            if d.intent_pct is not None and d.intent_pct > 10:
                new_intent = int(d.intent_pct * 0.90)
                d.intent_pct = new_intent
                if d.throwing_5tuple is not None:
                    d.throwing_5tuple = d.throwing_5tuple.model_copy(update={"intensity_pct": new_intent})
                return True
    return False


_REPAIR_DISPATCH = {
    "deload_cadence_missing": _repair_deload_cadence,
    "intent_monotonicity_jump_exceeded": _repair_intent_monotonicity,
    "phase_gate_violation_high_intent_in_base": _repair_phase_gate,
    "acwr_above_band": _repair_acwr_above_band,
    # acwr_below_band, pull_push_ratio_low, fpm_cadence_insufficient,
    # equipment_unavailable, contraindicated_exercise have no in-place
    # repair in v1 — they go to re-prompt. Adding more repairs is Plan v2 work.
}


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def validate_program(
    program: PitcherProgram,
    pitcher_context: dict,
    *,
    max_repair_passes: int = 3,
) -> ValidationResult:
    """Run all guardrails; attempt up to N repair passes; return the result.

    Repairable violations: those with a registered strategy in `_REPAIR_DISPATCH`
    AND `kind not in FATAL_KINDS`.

    Fatal violations (unknown_exercise_id, acwr_hard_cap_exceeded) skip the
    repair loop entirely — orchestrator returns `reject` so Task 3.3 can
    re-prompt the LLM with the offending detail.
    """
    repair_log: list[dict] = []
    working = deepcopy(program)

    for pass_idx in range(max_repair_passes + 1):
        violations = _run_all_guardrails(working, pitcher_context)
        if not violations:
            status: Literal["valid", "repaired", "reject"] = "repaired" if repair_log else "valid"
            return ValidationResult(status=status, program=working, violations=[], repair_log=repair_log)

        # Fatal violations short-circuit the loop
        fatal = [v for v in violations if v.kind in FATAL_KINDS]
        if fatal:
            return ValidationResult(
                status="reject",
                program=working,
                violations=violations,
                repair_log=repair_log,
            )

        if pass_idx == max_repair_passes:
            # Out of repair budget
            break

        any_repair_applied = False
        for v in violations:
            strat = _REPAIR_DISPATCH.get(v.kind)
            if strat is None:
                continue
            applied = strat(working, v)
            if applied:
                repair_log.append(
                    {
                        "pass": pass_idx + 1,
                        "kind": v.kind,
                        "where": v.where,
                        "applied": strat.__name__,
                    }
                )
                any_repair_applied = True
                break  # restart the loop after one repair so cascading violations resolve cleanly
        if not any_repair_applied:
            # No repair strategy matched any violation — exit the loop
            break

    # Out of budget or no progress
    violations = _run_all_guardrails(working, pitcher_context)
    return ValidationResult(
        status="reject" if violations else ("repaired" if repair_log else "valid"),
        program=working,
        violations=violations,
        repair_log=repair_log,
    )
