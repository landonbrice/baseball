"""Dynamic pitcher baselines and recovery curve lookup.

Computes per-pitcher rotation-day baselines from check-in history,
manages the three-tier baseline system, and provides recovery curve
expected values from population defaults.

Part of Phase 1: Trajectory-Aware Triage.
"""

import logging
from datetime import datetime
from pathlib import Path

import yaml

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

_POPULATION_BASELINES = None

_PROVISIONAL_THRESHOLD = 5   # check-ins
_FULL_THRESHOLD = 14         # check-ins
_POP_PRIOR_WEIGHT = 0.70     # A31


def _baseline_state(total_check_ins: int) -> str:
    if total_check_ins < _PROVISIONAL_THRESHOLD:
        return "no_baseline"
    if total_check_ins < _FULL_THRESHOLD:
        return "provisional"
    return "full"


def _load_population_baselines() -> dict:
    global _POPULATION_BASELINES
    if _POPULATION_BASELINES is None:
        path = (
            Path(__file__).parent.parent.parent
            / "data"
            / "constraint_defaults"
            / "population_baselines.yaml"
        )
        with open(path) as f:
            _POPULATION_BASELINES = yaml.safe_load(f)
        logger.info("Loaded population baselines from %s", path)
    return _POPULATION_BASELINES


def get_recovery_curve_expected(role: str, rotation_day: int, pitch_count: int = None) -> dict:
    """Get [floor, expected] for a pitcher on this rotation day.
    Returns: {"floor": int|None, "expected": int|None}
    """
    pop = _load_population_baselines()
    if "starter" in role.lower():
        return _starter_curve_lookup(pop, rotation_day)
    else:
        return _reliever_curve_lookup(pop, rotation_day, pitch_count)


def _starter_curve_lookup(pop: dict, rotation_day: int) -> dict:
    curve = pop["starter_recovery_curve"]
    key = f"day_{rotation_day}"
    if key in curve:
        floor, expected = curve[key]
        return {"floor": floor, "expected": expected}
    if rotation_day > 6:
        floor, expected = curve["day_6"]
        return {"floor": floor, "expected": expected}
    return {"floor": None, "expected": None}


def _reliever_curve_lookup(pop: dict, rotation_day: int, pitch_count: int = None) -> dict:
    if rotation_day >= 5:
        vals = pop["reliever_extended_rest"]["any_day"]
        return {"floor": vals[0], "expected": vals[1]}
    heavy = pitch_count is None or pitch_count >= 25
    if heavy:
        curve = pop["reliever_recovery_heavy"]
        if rotation_day <= 1:
            vals = curve["day_1"]
        elif rotation_day == 2:
            vals = curve["day_2"]
        else:
            vals = curve["day_3_plus"]
    else:
        curve = pop["reliever_recovery_light"]
        if rotation_day <= 1:
            vals = curve["day_1"]
        else:
            vals = curve["day_2_plus"]
    return {"floor": vals[0], "expected": vals[1]}


def compute_pitcher_baseline(daily_entries: list, rotation_length: int = 7) -> dict:
    """Compute per-pitcher rotation-day baseline from check-in history."""
    entries_with_af = []
    for e in daily_entries:
        pt = e.get("pre_training") or {}
        af = pt.get("arm_feel")
        if af is not None:
            entries_with_af.append({
                "date": e.get("date", ""),
                "arm_feel": af,
                "rotation_day": e.get("rotation_day", 0),
            })

    total_check_ins = len(entries_with_af)
    if total_check_ins == 0:
        return _empty_baseline()

    sorted_entries = sorted(entries_with_af, key=lambda x: x["date"])
    rotations_completed = _count_rotations(sorted_entries)

    if rotations_completed < 1:
        tier = 1
    elif rotations_completed < 3:
        tier = 2
    else:
        tier = 3

    rd_groups = {}
    for e in sorted_entries:
        rd = str(e["rotation_day"])
        rd_groups.setdefault(rd, []).append(e["arm_feel"])

    rotation_day_baselines = {}
    for rd, values in rd_groups.items():
        n = len(values)
        mean = sum(values) / n
        sd = _sample_sd(values)
        rotation_day_baselines[rd] = {"mean": round(mean, 1), "sd": round(sd, 1), "n": n}

    all_af = [e["arm_feel"] for e in sorted_entries]
    overall_mean = sum(all_af) / len(all_af)
    overall_sd = _sample_sd(all_af)

    rolling_14d_mean, prior_14d_mean, chronic_drift, drift_threshold, drift_flagged = (
        _compute_chronic_drift(sorted_entries, overall_mean, overall_sd)
    )

    state = _baseline_state(total_check_ins)
    observed_mean = round(overall_mean, 1)

    if state == "provisional":
        pop = _load_population_baselines()
        pop_mean = pop.get("population_defaults", {}).get("arm_feel_mean", 7.5)
        blended = _POP_PRIOR_WEIGHT * pop_mean + (1 - _POP_PRIOR_WEIGHT) * overall_mean
        effective_overall_mean = round(blended, 2)
    else:
        effective_overall_mean = observed_mean

    return {
        "tier": tier,
        "baseline_state": state,
        "rotation_day_baselines": rotation_day_baselines,
        "overall_mean": effective_overall_mean,
        "observed_mean": observed_mean,
        "overall_sd": round(overall_sd, 1),
        "rotations_completed": rotations_completed,
        "total_check_ins": total_check_ins,
        "rolling_14d_mean": round(rolling_14d_mean, 1) if rolling_14d_mean is not None else None,
        "prior_14d_mean": round(prior_14d_mean, 1) if prior_14d_mean is not None else None,
        "chronic_drift": round(chronic_drift, 1),
        "drift_threshold": round(drift_threshold, 1),
        "drift_flagged": drift_flagged,
        "computed_at": datetime.now(CHICAGO_TZ).isoformat(),
    }


def _empty_baseline() -> dict:
    pop = _load_population_baselines()
    defaults = pop.get("population_defaults", {})
    return {
        "tier": 1,
        "baseline_state": "no_baseline",
        "rotation_day_baselines": {},
        "overall_mean": defaults.get("arm_feel_mean", 7.5),
        "observed_mean": None,
        "overall_sd": defaults.get("arm_feel_sd", 1.2),
        "rotations_completed": 0,
        "total_check_ins": 0,
        "rolling_14d_mean": None,
        "prior_14d_mean": None,
        "chronic_drift": 0.0,
        "drift_threshold": defaults.get("chronic_drift_floor", 1.0),
        "drift_flagged": False,
        "computed_at": datetime.now(CHICAGO_TZ).isoformat(),
    }


def _count_rotations(sorted_entries: list) -> int:
    """Count completed rotations by detecting rotation_day resets to 0.

    Each reset from a non-zero day back to day 0 marks the boundary between
    two rotations. The count includes both the completed rotation and the
    in-progress one whenever at least one boundary has been crossed (i.e.
    reset_count + 1 when reset_count > 0), so three distinct outing cycles
    separated by two resets yields 3.
    """
    reset_count = 0
    prev_rd = None
    for e in sorted_entries:
        rd = e["rotation_day"]
        if prev_rd is not None and prev_rd > 0 and rd == 0:
            reset_count += 1
        prev_rd = rd
    # If we've seen at least one reset the pitcher is into their second+ rotation;
    # count that in-progress rotation too.
    return reset_count + 1 if reset_count > 0 else 0


def _sample_sd(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5


def _compute_chronic_drift(sorted_entries, overall_mean, overall_sd):
    n = len(sorted_entries)
    if n < 14:
        threshold = max(1.0, 0.75 * overall_sd) if overall_sd > 0 else 1.0
        return None, None, 0.0, threshold, False

    rolling = sorted_entries[-14:]
    prior_start = max(0, n - 28)
    prior_end = n - 14
    prior = sorted_entries[prior_start:prior_end] if prior_end > prior_start else []

    rolling_14d_mean = sum(e["arm_feel"] for e in rolling) / len(rolling)
    prior_14d_mean = sum(e["arm_feel"] for e in prior) / len(prior) if prior else None

    drift = overall_mean - rolling_14d_mean
    threshold = max(1.0, 0.75 * overall_sd)
    flagged = drift > threshold

    return rolling_14d_mean, prior_14d_mean, drift, threshold, flagged


def get_tolerance_band(tier: int) -> int:
    pop = _load_population_baselines()
    bands = pop.get("tolerance_bands", {})
    return bands.get(f"tier_{tier}", 0)


# ---------------------------------------------------------------------------
# Cache-aware baseline refresh
# ---------------------------------------------------------------------------

_CACHE_TTL_HOURS = 24


def get_or_refresh_baseline(
    pitcher_id: str,
    cached_snapshot: dict | None,
    daily_entries: list,
    rotation_length: int = 7,
    last_outing_date: str = None,
) -> dict:
    """Return cached baseline or recompute if stale/missing.

    Recomputes when:
    - cached_snapshot is None or empty
    - computed_at is older than _CACHE_TTL_HOURS
    - last_outing_date is newer than the snapshot's last_outing_date

    Returns the baseline dict with an added "_recomputed" bool key.
    """
    if _should_recompute(cached_snapshot, last_outing_date):
        baseline = compute_pitcher_baseline(daily_entries, rotation_length)
        if last_outing_date:
            baseline["last_outing_date"] = last_outing_date
        baseline["_recomputed"] = True
        logger.info(
            "Recomputed baseline for %s: tier=%d, check-ins=%d",
            pitcher_id, baseline["tier"], baseline["total_check_ins"],
        )
        return baseline

    cached_snapshot["_recomputed"] = False
    return cached_snapshot


def _should_recompute(cached: dict | None, last_outing_date: str = None) -> bool:
    if not cached or not cached.get("computed_at"):
        return True
    try:
        computed_at = datetime.fromisoformat(cached["computed_at"])
        now = datetime.now(CHICAGO_TZ)
        age_hours = (now - computed_at).total_seconds() / 3600
        if age_hours > _CACHE_TTL_HOURS:
            return True
    except (ValueError, TypeError):
        return True
    if last_outing_date and cached.get("last_outing_date"):
        if last_outing_date > cached["last_outing_date"]:
            return True
    return False
