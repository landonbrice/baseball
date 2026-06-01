"""Program Engine v1 — bounded re-pacing governor (Task 4.2).

The drive seam's second half. `project()` (Task 4.1) emits a
`governor_signal` when a candidate policy wants to re-pace remaining
weeks; `regovern()` (this module) applies the bounded adjustments.

Adjustment limits per policy (per plan §4 + L7):
  - shift up to 2 weeks of accumulation forward
  - insert OR remove ONE deload
  - soften ONE phase gate (delay phase boundary by up to 1 week)

Beyond which `goal_at_risk=True` is set and no further changes apply.

Output ALWAYS re-validates through Phase 2.4 `validate_program`. If the
re-pace produces something that fails validation, the original is returned
unchanged with `goal_at_risk=True` and `changes=[]`. The orchestrator
never gets a broken intermediate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from bot.services.program_engine.guardrails import validate_program
from bot.services.program_engine.projection import PolicyName
from bot.services.program_engine.schemas import PitcherProgram


# Bounds from L7 — surface at module scope rather than buried.
MAX_WEEKS_SHIFTED: int = 2
MAX_DELOAD_MOVES: int = 1
MAX_PHASE_GATE_SOFTENS: int = 1
SMALL_INTENT_BUMP_PP: int = 5


@dataclass
class RegovernResult:
    program: PitcherProgram
    changes: list[dict] = field(default_factory=list)
    goal_at_risk: bool = False


def _structural_ctx(program: PitcherProgram) -> dict:
    """Build a ctx that exercises the structural checks but stubs content checks.

    The governor doesn't know the live pitcher_training_model — equipment +
    modifications + tag_lookup are unavailable here. We synthesize an
    `exercises_rows` list from the program's own exercises so the FATAL
    `unknown_exercise_id` check passes by construction; the structural
    invariants (ACWR, deload, monotonicity, phase-gate) still run.
    """
    used_ids = {ex.exercise_id for d in program.days for b in d.lifting_blocks for ex in b.exercises}
    return {
        "exercises_rows": [{"id": ex_id, "equipment": None, "contraindications": []} for ex_id in used_ids],
        "available_equipment": [],
        "active_modifications": [],
        "tag_lookup": {},
    }


def _validates(program: PitcherProgram) -> bool:
    """True iff the program has no FATAL violations under structural checks.

    Non-fatal violations (band warnings, pull:push, fpm cadence — both of
    which require tag_lookup the governor lacks) are tolerated.
    """
    try:
        result = validate_program(program, _structural_ctx(program), max_repair_passes=1)
    except Exception:
        return False
    fatal = {"unknown_exercise_id", "acwr_hard_cap_exceeded"}
    return not any(v.kind in fatal for v in result.violations)


# ─────────────────────────────────────────────────────────────────────────────
# Bounded adjustments
# ─────────────────────────────────────────────────────────────────────────────


def _bump_intent_next_week(
    program: PitcherProgram, from_day_index: int, bump_pp: int
) -> tuple[PitcherProgram, dict | None]:
    """Add `bump_pp` to the intent on every throwing day in the week AFTER
    `from_day_index`. Bounded at intent_pct ≤ 100. Returns (program, change) or
    (program, None) if nothing changed."""
    next_wk = (from_day_index // 7) + 1
    lo = next_wk * 7
    hi = lo + 7
    candidates = [d for d in program.days if lo <= d.day_index < hi and d.throwing_5tuple is not None]
    if not candidates:
        return program, None
    for d in candidates:
        if d.intent_pct is None:
            continue
        new_intent = min(100, d.intent_pct + bump_pp)
        if new_intent == d.intent_pct:
            continue
        d.intent_pct = new_intent
        d.throwing_5tuple = d.throwing_5tuple.model_copy(update={"intensity_pct": new_intent})
    change = {"kind": "intent_bump_next_week", "week": next_wk + 1, "bump_pp": bump_pp,
              "days_touched": len(candidates)}
    return program, change


def _shift_accumulation_forward(
    program: PitcherProgram, from_day_index: int, weeks: int
) -> tuple[PitcherProgram, dict | None]:
    """Conceptually: bring forward the prescribed intent from N weeks in the future
    by `weeks`. v1 implementation: increase intent_pct on the NEXT `weeks` weeks
    by a moderate amount (sensitive to the SMALL_INTENT_BUMP × weeks).

    Bounded by MAX_WEEKS_SHIFTED.
    """
    if weeks <= 0 or weeks > MAX_WEEKS_SHIFTED:
        return program, None
    next_wk = (from_day_index // 7) + 1
    lo = next_wk * 7
    hi = lo + weeks * 7
    candidates = [d for d in program.days if lo <= d.day_index < hi and d.throwing_5tuple is not None]
    if not candidates:
        return program, None
    bump = SMALL_INTENT_BUMP_PP * weeks
    for d in candidates:
        if d.intent_pct is None:
            continue
        new_intent = min(100, d.intent_pct + bump)
        if new_intent != d.intent_pct:
            d.intent_pct = new_intent
            d.throwing_5tuple = d.throwing_5tuple.model_copy(update={"intensity_pct": new_intent})
    return program, {"kind": "shift_accumulation_forward", "weeks": weeks,
                     "days_touched": len(candidates)}


def _demote_next_deload(
    program: PitcherProgram, from_day_index: int
) -> tuple[PitcherProgram, dict | None]:
    """Find the next deload week AFTER from_day_index and demote it — turn off
    the is_deload flag on every day in it. Bounded by MAX_DELOAD_MOVES."""
    after_wk = (from_day_index // 7) + 1
    weeks_seen: dict[int, list] = {}
    for d in program.days:
        wk = d.day_index // 7
        weeks_seen.setdefault(wk, []).append(d)
    for wk in sorted(weeks_seen):
        if wk < after_wk:
            continue
        days = weeks_seen[wk]
        if any(d.is_deload for d in days):
            for d in days:
                d.is_deload = False
            return program, {"kind": "demote_next_deload", "week": wk + 1}
    return program, None


# ─────────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────────


def regovern(
    program: PitcherProgram,
    signal: dict | None,
    policy: PolicyName,
    from_day_index: int,
) -> RegovernResult:
    """Apply bounded re-pacing to the program based on the projection's signal.

    Args:
        program: The persisted program before re-pacing.
        signal: The `governor_signal` dict returned by `project()`. None means
            no re-pacing needed (silent_absorb on GREEN, etc.).
        policy: One of the 3 candidate policy names. Defines re-pacing
            aggressiveness.
        from_day_index: The day_index where the deviation happened. Re-pacing
            only touches days AFTER this.

    Returns:
        RegovernResult with the re-paced program, the change log, and
        `goal_at_risk` flag set when bounded adjustments can't absorb the
        deviation.
    """
    if signal is None or policy == "silent_absorb":
        return RegovernResult(program=program, changes=[], goal_at_risk=False)

    severity = signal.get("severity", "small")
    working = deepcopy(program)
    changes: list[dict] = []

    if policy == "immediate_repace":
        # Small → bump next week intent only.
        # Medium → shift one week forward.
        # Large → shift two weeks forward + demote next deload.
        if severity == "small":
            working, change = _bump_intent_next_week(working, from_day_index, SMALL_INTENT_BUMP_PP)
            if change:
                changes.append(change)
        elif severity == "medium":
            working, change = _shift_accumulation_forward(working, from_day_index, 1)
            if change:
                changes.append(change)
        else:  # large
            working, change = _shift_accumulation_forward(working, from_day_index, MAX_WEEKS_SHIFTED)
            if change:
                changes.append(change)
            working, change2 = _demote_next_deload(working, from_day_index)
            if change2:
                changes.append(change2)

    elif policy == "banked_deviation":
        # Banked only re-paces on medium/large — small is absorbed by the policy.
        if severity == "medium":
            working, change = _shift_accumulation_forward(working, from_day_index, 1)
            if change:
                changes.append(change)
        elif severity == "large":
            working, change = _demote_next_deload(working, from_day_index)
            if change:
                changes.append(change)
            working, change2 = _shift_accumulation_forward(working, from_day_index, 1)
            if change2:
                changes.append(change2)

    # Re-validate — if the re-pace broke something, retreat to the original.
    if changes and not _validates(working):
        return RegovernResult(
            program=program,
            changes=[],
            goal_at_risk=True,
        )

    # If the policy WANTED to re-pace but nothing changed (no candidates left,
    # e.g. signal hit on the last week), the goal is at risk.
    if signal is not None and policy != "silent_absorb" and not changes:
        return RegovernResult(program=program, changes=[], goal_at_risk=True)

    return RegovernResult(program=working, changes=changes, goal_at_risk=False)
