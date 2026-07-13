"""Program Engine v1 — structural invariants (Task 2.2).

Implements §7 invariants 2–5 as pure functions on `PitcherProgram`:
  (2) Deload cadence — ≥1 deload week per ~3–4 accumulation weeks
  (3) Phase gates — high-intensity / mound / pulldown phases follow base phase
  (4) Throwing intensity monotonicity — no >+20pp week-over-week max-intent jumps
  (5) Lifting invariants — pull:push ≥ 2:1 weekly; FPM ≥ 4/7 days

Each invariant is a stand-alone function returning `list[GuardrailViolation]`,
so the orchestrator (Task 2.4) can run them in parallel and partition by
severity/repairability.
"""
from __future__ import annotations

from typing import Optional, Sequence

from bot.services.program_engine.load_math import GuardrailViolation
from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
)

# Tag prefixes used by `exercises.tags` (jsonb) to classify lifts.
# These mirror the seed naming in `data/knowledge/exercise_library.json`.
TAG_PULL = "pull"
TAG_PUSH = "push"
TAG_FPM = "fpm"  # flexor-pronator-mass

# Defaults — overridable per-call so the velocity knowledge pack's
# `content.acwr_governor` / `lifting_integration` can tighten them.
DELOAD_MAX_ACCUMULATION_WEEKS = 4   # invariant: ≤4 accum weeks before a deload
DELOAD_DROP_PCT_MIN = 0.10          # deload week must drop ≥10% vs prior
INTENSITY_JUMP_MAX_PP = 20          # max +20pp week-over-week intent jump
PULL_PUSH_RATIO_MIN = 2.0           # weekly pull:push ≥ 2:1
FPM_MIN_DAYS_PER_WEEK = 4


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — week partitioning + classification
# ─────────────────────────────────────────────────────────────────────────────


def _days_by_week(days: Sequence[Day], total_weeks: int) -> list[list[Day]]:
    """Partition days into [week-1, week-2, …] lists of length `total_weeks`."""
    buckets: list[list[Day]] = [[] for _ in range(total_weeks)]
    for d in days:
        wk = d.day_index // 7
        if 0 <= wk < total_weeks:
            buckets[wk].append(d)
    return buckets


def _max_intent_in_week(week_days: Sequence[Day]) -> Optional[int]:
    intents = [d.intent_pct for d in week_days if d.intent_pct is not None and d.throwing_5tuple is not None]
    if not intents:
        return None
    return max(intents)


def _classify_exercise(ex: LiftingExercise, tag_lookup: dict[str, set[str]]) -> set[str]:
    """Return the set of tags (`{TAG_PULL}`, `{TAG_PUSH}`, `{TAG_FPM}`, ...)
    for an exercise by its canonical id. `tag_lookup` maps ex_id → set of tag strings."""
    return tag_lookup.get(ex.exercise_id, set())


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 2 — Deload cadence
# ─────────────────────────────────────────────────────────────────────────────


def check_deload_cadence(
    program: PitcherProgram,
    *,
    max_accumulation_weeks: int = DELOAD_MAX_ACCUMULATION_WEEKS,
) -> list[GuardrailViolation]:
    """Walks the week-by-week is_deload flags.

    Violation: more than `max_accumulation_weeks` consecutive non-deload weeks.
    Phase 2.4 repairs by demoting the oldest accumulation week to a deload.
    """
    weeks = _days_by_week(program.days, program.total_weeks)
    violations: list[GuardrailViolation] = []
    consecutive_accum = 0
    for w_idx, days in enumerate(weeks):
        is_deload_week = any(d.is_deload for d in days)
        if is_deload_week:
            consecutive_accum = 0
            continue
        consecutive_accum += 1
        if consecutive_accum > max_accumulation_weeks:
            violations.append(
                GuardrailViolation(
                    kind="deload_cadence_missing",
                    where={"week": w_idx + 1},
                    actual=consecutive_accum,
                    expected=f"≤ {max_accumulation_weeks} consecutive accumulation weeks",
                    severity="error",
                    repair_hint="demote_oldest_accumulation_week_to_deload",
                )
            )
            consecutive_accum = 0  # avoid cascading violations
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 3 — Phase gates (high-intent before base)
# ─────────────────────────────────────────────────────────────────────────────


HIGH_INTENT_THRESHOLD = 85  # intensities ≥ 85% count as "high-intent"


def check_phase_gates(program: PitcherProgram) -> list[GuardrailViolation]:
    """No high-intent throwing in Phase 1 / "Base".

    The velocity knowledge pack's `phase_gates.mound_introduction.default_week`
    is 7; this generic check fires when any day before week 4 carries
    intensity ≥85%.
    """
    violations: list[GuardrailViolation] = []
    # Base phase = first phase by ordinal position
    base_phase_week_count = program.phases[0].week_count
    base_phase_last_day = base_phase_week_count * 7 - 1
    for d in program.days:
        if d.day_index > base_phase_last_day:
            continue
        if d.intent_pct is not None and d.intent_pct >= HIGH_INTENT_THRESHOLD:
            violations.append(
                GuardrailViolation(
                    kind="phase_gate_violation_high_intent_in_base",
                    where={"day_index": d.day_index, "date": d.date, "phase": d.phase_name or program.phases[0].name},
                    actual=d.intent_pct,
                    expected=f"< {HIGH_INTENT_THRESHOLD}",
                    severity="error",
                    repair_hint="clip_intent_pct_to_base_phase_ceiling",
                )
            )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 4 — Throwing intensity monotonicity
# ─────────────────────────────────────────────────────────────────────────────


def check_intent_monotonicity(
    program: PitcherProgram,
    *,
    max_jump_pp: int = INTENSITY_JUMP_MAX_PP,
) -> list[GuardrailViolation]:
    """Weekly max-intent must not jump more than `max_jump_pp` percentage points
    between consecutive weeks. Deload weeks are exempt (a drop is fine; the
    NEXT week's recovery may be a big jump-from-deload, which we also tolerate
    by comparing against the pre-deload max).
    """
    weeks = _days_by_week(program.days, program.total_weeks)
    violations: list[GuardrailViolation] = []
    last_non_deload_max: Optional[int] = None
    for w_idx, days in enumerate(weeks):
        is_deload = any(d.is_deload for d in days)
        wk_max = _max_intent_in_week(days)
        if wk_max is None:
            continue
        if is_deload:
            # Deload weeks may dip below last_non_deload_max — that's fine.
            continue
        if last_non_deload_max is not None:
            jump = wk_max - last_non_deload_max
            if jump > max_jump_pp:
                violations.append(
                    GuardrailViolation(
                        kind="intent_monotonicity_jump_exceeded",
                        where={"week": w_idx + 1},
                        actual=f"+{jump}pp (from {last_non_deload_max} → {wk_max})",
                        expected=f"≤ +{max_jump_pp}pp",
                        severity="warning",
                        repair_hint="insert_bridge_week_between_phases_or_clip_intent",
                    )
                )
        last_non_deload_max = wk_max
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 5a — Pull:push ratio
# ─────────────────────────────────────────────────────────────────────────────


def check_pull_push_ratio(
    program: PitcherProgram,
    tag_lookup: dict[str, set[str]],
    *,
    ratio_min: float = PULL_PUSH_RATIO_MIN,
) -> list[GuardrailViolation]:
    """Weekly pull-set-volume / push-set-volume ≥ 2.0.

    "Volume" counted in sets (not weighted by reps/intensity — pull:push is a
    structural ratio, not a load ratio). Weeks with zero pushing are skipped
    (a pull-only week trivially satisfies the ratio).
    """
    weeks = _days_by_week(program.days, program.total_weeks)
    violations: list[GuardrailViolation] = []
    for w_idx, days in enumerate(weeks):
        pull_sets = 0
        push_sets = 0
        for d in days:
            for block in d.lifting_blocks:
                for ex in block.exercises:
                    tags = _classify_exercise(ex, tag_lookup)
                    if TAG_PULL in tags:
                        pull_sets += ex.sets
                    if TAG_PUSH in tags:
                        push_sets += ex.sets
        if push_sets == 0:
            continue
        ratio = pull_sets / push_sets
        if ratio < ratio_min:
            violations.append(
                GuardrailViolation(
                    kind="pull_push_ratio_low",
                    where={"week": w_idx + 1},
                    actual=round(ratio, 2),
                    expected=f"≥ {ratio_min}",
                    severity="error",
                    repair_hint="add_pull_set_or_drop_push_set",
                )
            )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 5b — FPM cadence
# ─────────────────────────────────────────────────────────────────────────────


def check_fpm_cadence(
    program: PitcherProgram,
    tag_lookup: dict[str, set[str]],
    *,
    min_days_per_week: int = FPM_MIN_DAYS_PER_WEEK,
) -> list[GuardrailViolation]:
    """At least `min_days_per_week` days per week carry an FPM exercise.

    FPM = flexor-pronator-mass (`bot.services.vocabulary.MODIFICATION_TAGS`-adjacent;
    the exercise has tag `fpm` in the live `exercises.tags` jsonb).
    """
    weeks = _days_by_week(program.days, program.total_weeks)
    violations: list[GuardrailViolation] = []
    for w_idx, days in enumerate(weeks):
        fpm_days = 0
        for d in days:
            has_fpm = any(
                TAG_FPM in _classify_exercise(ex, tag_lookup)
                for block in d.lifting_blocks
                for ex in block.exercises
            )
            if has_fpm:
                fpm_days += 1
        if fpm_days < min_days_per_week:
            violations.append(
                GuardrailViolation(
                    kind="fpm_cadence_insufficient",
                    where={"week": w_idx + 1},
                    actual=fpm_days,
                    expected=f"≥ {min_days_per_week} days/week",
                    severity="error",
                    repair_hint="add_fpm_exercise_to_underloaded_day",
                )
            )
    return violations
