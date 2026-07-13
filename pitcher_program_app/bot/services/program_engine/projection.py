"""Program Engine v1 — the drive seam (Task 4.1).

A pure projection function `project(program, date, readiness, *, policy)`
returning what the pitcher sees today, given:
  - the persisted program (the intent),
  - today's date (the calendar lookup),
  - a readiness signal from the Phase 1 trajectory triage,
  - and a candidate POLICY for how deviations propagate.

This is the OPEN-#1 "drive" seam as a designed spike, per locked decision L7:
  - Build the seam + tested infrastructure for ≥3 candidate policies.
  - Record the comparison harness output to inform v2.
  - DO NOT pick a policy here; DO NOT wire into the live check-in pipeline.

No DB writes. No LLM calls. Reads `program` + `readiness` (dict) and returns
a `ProjectedDay`.

Policies
========
"silent_absorb"
    Take today's hit; the remaining weeks are unchanged. Never emits a
    governor_signal — the deviation is absorbed, no re-pacing requested.

"immediate_repace"
    Every reduction (intent_pct dialed down OR a throwing day downgraded
    to recovery-only OR cancelled) emits a governor_signal so the
    governor re-paces the remaining weeks toward the goal.

"banked_deviation"
    Track cumulative missed load. Only emit governor_signal when a
    single-day reduction is severe (>50%) OR the cumulative bank
    crosses a threshold (5000 G units). Small day-to-day variance
    silently absorbs; structural deviation triggers re-pacing.

Readiness signal shape
======================
    {
        "flag_level": "GREEN" | "YELLOW" | "RED" | "CRITICAL_RED",
        "category_scores": {"tissue": float 0-10, "load": float 0-10, "recovery": float 0-10},
        "modifications": list[str],          # active modification tags
        "arm_feel": int 1-10 (optional),
        "energy": int 1-10 (optional),
        "banked_missed_g": float (optional, for banked_deviation policy),
    }

All optional fields default to neutral values when missing.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date as _date
from typing import Literal, Optional

from bot.services.program_engine.load_math import daily_throwing_load
from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
    ThrowingFiveTuple,
)

# Policies — string literal type so callers can be checked statically.
PolicyName = Literal["silent_absorb", "immediate_repace", "banked_deviation"]
_VALID_POLICIES: tuple[str, ...] = ("silent_absorb", "immediate_repace", "banked_deviation")


# Tunable thresholds for the candidate policies. Conservative defaults; the
# Phase 4.3 harness lives or dies on these numbers, so they're surfaced at
# module scope rather than buried.
YELLOW_INTENT_DROP_PP: int = 10            # YELLOW: drop intent by 10pp
YELLOW_THROW_REDUCTION_FACTOR: float = 0.80  # YELLOW: throws ×0.80 (20% drop)
RED_RECOVERY_INTENT_PCT: int = 50           # RED: drop to 50% recovery throwing
RED_RECOVERY_THROW_COUNT: int = 20          # RED: 20 throws
RED_RECOVERY_DISTANCE_FT: int = 45          # RED: 45ft

BANKED_DEVIATION_G_THRESHOLD: float = 5000.0
LARGE_SINGLE_DAY_REDUCTION_FRACTION: float = 0.5  # >50% drop counts as "large"
SIGNAL_SMALL_MAX_G: float = 1000.0
SIGNAL_MEDIUM_MAX_G: float = 4000.0


@dataclass
class ProjectedDay:
    """The drive seam's return shape.

    `intended` is the program's prescription for this day (unchanged copy).
    `delivered` is what the projection emits after readiness modulation.
    `modulation` records the factor + reason + severity for observability.
    `governor_signal` is non-None when the active policy wants to re-pace
    remaining weeks — the governor (Task 4.2) consumes it.
    """

    day_index: int
    intended: Day
    delivered: Day
    modulation: dict
    governor_signal: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Readiness classification
# ─────────────────────────────────────────────────────────────────────────────


def _classify_readiness(readiness: dict) -> str:
    """Return one of 'green' | 'yellow' | 'red' | 'critical_red'.

    Logic (deterministic, content-independent):
      - CRITICAL_RED: explicit flag, OR arm_feel ≤ 2.
      - RED:          explicit flag, OR arm_feel ≤ 4, OR any modification tag present.
      - YELLOW:       explicit flag, OR arm_feel in 5-6, OR any category score ≤ 4.
      - GREEN:        otherwise.

    `flag_level` if explicitly passed takes precedence over inferred classification
    EXCEPT when the inferred class is more severe (we don't downgrade RED to GREEN
    because someone forgot to set the flag).
    """
    flag_raw = (readiness.get("flag_level") or "").upper()
    arm_feel = readiness.get("arm_feel")
    modifications = readiness.get("modifications") or []
    scores = readiness.get("category_scores") or {}
    tissue = scores.get("tissue")
    load = scores.get("load")
    recovery = scores.get("recovery")

    # Infer from atoms (the more severe of explicit-flag vs inferred wins)
    inferred = "green"
    if arm_feel is not None and arm_feel <= 2:
        inferred = "critical_red"
    elif arm_feel is not None and arm_feel <= 4:
        inferred = "red"
    elif modifications:
        inferred = "red"
    elif (arm_feel is not None and 5 <= arm_feel <= 6) or any(
        s is not None and s <= 4 for s in (tissue, load, recovery)
    ):
        inferred = "yellow"

    flag_map = {
        "GREEN": "green",
        "YELLOW": "yellow",
        "RED": "red",
        "CRITICAL_RED": "critical_red",
    }
    severity_rank = {"green": 0, "yellow": 1, "red": 2, "critical_red": 3}

    explicit = flag_map.get(flag_raw, inferred)
    if severity_rank[inferred] > severity_rank[explicit]:
        return inferred
    return explicit


# ─────────────────────────────────────────────────────────────────────────────
# Modulation helpers
# ─────────────────────────────────────────────────────────────────────────────


def _modulate_yellow(intended: Day) -> Day:
    """YELLOW: drop intent 10pp, throws by 20%, drop one accessory lift.

    Mutates the deep-copy `delivered` (caller's responsibility to pass a copy).
    Returns the SAME object for chaining clarity.
    """
    delivered = deepcopy(intended)
    if delivered.intent_pct is not None:
        delivered.intent_pct = max(20, delivered.intent_pct - YELLOW_INTENT_DROP_PP)
    if delivered.throwing_5tuple is not None:
        five = delivered.throwing_5tuple
        new_throws = max(1, int(round(five.throw_count * YELLOW_THROW_REDUCTION_FACTOR)))
        new_intent = (
            delivered.intent_pct
            if delivered.intent_pct is not None
            else max(20, five.intensity_pct - YELLOW_INTENT_DROP_PP)
        )
        delivered.throwing_5tuple = five.model_copy(update={
            "throw_count": new_throws,
            "intensity_pct": new_intent,
        })
    # Drop one accessory: pop the last exercise off the last lifting block.
    # A "block" needs ≥1 exercise per schema, so if there's exactly one, drop
    # the whole block instead.
    if delivered.lifting_blocks:
        last_block = delivered.lifting_blocks[-1]
        if len(last_block.exercises) > 1:
            new_exercises = list(last_block.exercises[:-1])
            delivered.lifting_blocks[-1] = last_block.model_copy(update={"exercises": new_exercises})
        else:
            delivered.lifting_blocks = list(delivered.lifting_blocks[:-1])
    return delivered


def _modulate_red(intended: Day) -> Day:
    """RED: recovery-only throwing (50% / 20 throws / 45ft); minimal lifting.

    Lifting: 1 compound + 2 accessories + 1 core (4 total exercises across 1
    block). If there's already a lifting block, trim it; if not, leave empty
    (recovery-mobility day).
    """
    delivered = deepcopy(intended)
    if delivered.throwing_5tuple is not None:
        five = delivered.throwing_5tuple
        delivered.throwing_5tuple = five.model_copy(update={
            "distance_ft": RED_RECOVERY_DISTANCE_FT,
            "throw_count": RED_RECOVERY_THROW_COUNT,
            "intensity_pct": RED_RECOVERY_INTENT_PCT,
            "note": "RECOVERY (RED day)",
        })
        delivered.intent_pct = RED_RECOVERY_INTENT_PCT

    if delivered.lifting_blocks:
        # Keep first block but cap at 4 exercises; drop additional blocks
        first = delivered.lifting_blocks[0]
        trimmed = list(first.exercises[:4]) if len(first.exercises) > 4 else list(first.exercises)
        delivered.lifting_blocks = [first.model_copy(update={"exercises": trimmed})]
    return delivered


def _modulate_critical_red(intended: Day) -> Day:
    """CRITICAL_RED: no throwing, no lifting. Mobility-only / rest."""
    delivered = deepcopy(intended)
    delivered.throwing_5tuple = None
    delivered.lifting_blocks = []
    delivered.intent_pct = None
    delivered.is_rest = True
    return delivered


# ─────────────────────────────────────────────────────────────────────────────
# Governor signal — policy-aware
# ─────────────────────────────────────────────────────────────────────────────


def _missed_throwing_g(intended: Day, delivered: Day) -> float:
    """Compute the G load that the deviation cost on the throwing side.

    intended_G - delivered_G. Zero or negative → no miss.
    """
    intended_g = (
        daily_throwing_load(intended.throwing_5tuple)
        if intended.throwing_5tuple is not None
        else 0.0
    )
    delivered_g = (
        daily_throwing_load(delivered.throwing_5tuple)
        if delivered.throwing_5tuple is not None
        else 0.0
    )
    return max(0.0, intended_g - delivered_g)


def _severity_label(missed_g: float) -> str:
    if missed_g < SIGNAL_SMALL_MAX_G:
        return "small"
    if missed_g < SIGNAL_MEDIUM_MAX_G:
        return "medium"
    return "large"


def _decide_signal(
    intended: Day,
    delivered: Day,
    policy: PolicyName,
    banked_missed_g: float,
    severity_class: str,
) -> Optional[dict]:
    """Return governor_signal dict per policy semantics, or None to absorb."""
    # silent_absorb never re-paces.
    if policy == "silent_absorb":
        return None

    # Compute the load delta if we modulated.
    missed_g = _missed_throwing_g(intended, delivered)
    intended_throwing_dropped = (
        intended.throwing_5tuple is not None and delivered.throwing_5tuple is None
    )
    intent_dropped = (
        intended.intent_pct is not None
        and delivered.intent_pct is not None
        and delivered.intent_pct < intended.intent_pct
    )

    if policy == "immediate_repace":
        # Any reduction → signal.
        if missed_g > 0 or intended_throwing_dropped or intent_dropped:
            return {
                "kind": "missed_load",
                "missed_g": round(missed_g, 2),
                "severity": _severity_label(missed_g),
                "policy": policy,
                "readiness_class": severity_class,
            }
        return None

    if policy == "banked_deviation":
        # Bank threshold OR single-day large reduction.
        cumulative = banked_missed_g + missed_g
        if cumulative > BANKED_DEVIATION_G_THRESHOLD:
            return {
                "kind": "missed_load",
                "missed_g": round(missed_g, 2),
                "banked_total_g": round(cumulative, 2),
                "severity": _severity_label(cumulative),
                "policy": policy,
                "reason": "bank_threshold_crossed",
                "readiness_class": severity_class,
            }
        # Single-day large: reduction crossed 50% of intended throwing G.
        intended_g_for_pct = (
            daily_throwing_load(intended.throwing_5tuple)
            if intended.throwing_5tuple is not None
            else 0.0
        )
        if intended_g_for_pct > 0:
            reduction_fraction = missed_g / intended_g_for_pct
            if reduction_fraction > LARGE_SINGLE_DAY_REDUCTION_FRACTION:
                return {
                    "kind": "missed_load",
                    "missed_g": round(missed_g, 2),
                    "banked_total_g": round(cumulative, 2),
                    "severity": _severity_label(missed_g),
                    "policy": policy,
                    "reason": "single_day_large_reduction",
                    "readiness_class": severity_class,
                }
        return None

    return None  # unknown policy treated as silent_absorb


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def project(
    program: PitcherProgram,
    date: _date,
    readiness: dict,
    *,
    policy: PolicyName = "silent_absorb",
) -> ProjectedDay:
    """Project the program's matching day onto today's reality.

    Pure function. Looks up `program.days` for the matching ISO date string,
    classifies readiness, modulates the intended day deterministically, and
    emits a `ProjectedDay` whose `governor_signal` is policy-dependent.

    `delivered.phase_name == intended.phase_name` always — we never re-orient
    the program away from its goal mid-day.

    Raises:
        ValueError: if no Day in `program.days` matches `date`.
        ValueError: if `policy` is not one of the valid policies.
    """
    if policy not in _VALID_POLICIES:
        raise ValueError(
            f"unknown policy {policy!r}; expected one of {_VALID_POLICIES}"
        )
    iso_date = date.isoformat()
    intended_day: Optional[Day] = next((d for d in program.days if d.date == iso_date), None)
    if intended_day is None:
        raise ValueError(
            f"date {iso_date} does not correspond to any program day (program covers "
            f"{program.days[0].date}..{program.days[-1].date if program.days else 'n/a'})"
        )

    readiness_class = _classify_readiness(readiness)

    # Apply modulation per readiness class.
    if readiness_class == "green":
        delivered = deepcopy(intended_day)
        applied_factor = 1.0
    elif readiness_class == "yellow":
        delivered = _modulate_yellow(intended_day)
        applied_factor = 1.0 - (YELLOW_INTENT_DROP_PP / 100.0)  # rough load factor
    elif readiness_class == "red":
        delivered = _modulate_red(intended_day)
        applied_factor = 0.5
    else:  # critical_red
        delivered = _modulate_critical_red(intended_day)
        applied_factor = 0.0

    # Invariants: delivered keeps phase + day_index alignment with intended.
    delivered.phase_name = intended_day.phase_name
    delivered.day_index = intended_day.day_index

    modulation = {
        "applied_factor": applied_factor,
        "reason": readiness_class,
        "severity": readiness_class,
    }

    banked_missed_g = float(readiness.get("banked_missed_g") or 0.0)
    governor_signal = _decide_signal(
        intended_day,
        delivered,
        policy,
        banked_missed_g,
        readiness_class,
    )

    return ProjectedDay(
        day_index=intended_day.day_index,
        intended=intended_day,
        delivered=delivered,
        modulation=modulation,
        governor_signal=governor_signal,
    )
