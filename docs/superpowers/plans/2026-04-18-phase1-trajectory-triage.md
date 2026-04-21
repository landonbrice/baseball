# Phase 1: Trajectory-Aware Triage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the triage engine to use three-category scoring (tissue/load/recovery), rotation-aware recovery curves, dynamic pitcher-specific baselines, and absorbed trend detection — replacing flat yellow-trigger counting.

**Architecture:** New `baselines.py` module computes per-pitcher baselines cached in `pitcher_training_model.baseline_snapshot` JSONB. Rewritten `triage.py` accepts recent history + baseline, scores three categories independently, applies interaction rules for flag_level. `checkin_service.py` assembles the new inputs and removes its arm_clarification override. Plan generator is untouched.

**Tech Stack:** Python 3.11, Supabase (Postgres), PyYAML, pytest

**Worktree:** `/Users/landonbrice/Desktop/Baseball-phase1` on branch `phase1-trajectory-triage`

**Design spec:** `docs/superpowers/specs/2026-04-18-phase1-trajectory-triage-design.md`

**Direction doc (source of truth for thresholds):** `DIRECTION_Phase1_Trajectory_Aware_Triage.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `data/constraint_defaults/population_baselines.yaml` | Create | Population recovery curves, baseline defaults |
| `bot/services/baselines.py` | Create | Baseline computation, caching, recovery curve lookup, chronic drift |
| `bot/services/triage.py` | Rewrite | 3-category scoring, interaction rules, recovery curve eval, trajectory |
| `bot/services/checkin_service.py` | Modify (L88-142, L172-173) | Assemble recent history, call new triage, remove arm_clarification override |
| `bot/services/db.py` | Modify (L79-89) | Read/write `baseline_snapshot` from training model |
| `tests/test_baselines.py` | Create | Baseline computation, tier classification, drift, recovery curves |
| `tests/test_triage_phase1.py` | Create | 3-category scoring, interaction rules, golden snapshots, recovery curve |

---

## Task 1: Population Baselines YAML

**Files:**
- Create: `data/constraint_defaults/population_baselines.yaml`

- [ ] **Step 1: Create constraint_defaults directory**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
mkdir -p data/constraint_defaults
```

- [ ] **Step 2: Write population_baselines.yaml**

Create `data/constraint_defaults/population_baselines.yaml`:

```yaml
# Population-level baseline values for trajectory-aware triage (Phase 1).
# These are starting defaults for new pitchers. Individual baselines
# override these after sufficient data (Tier 2+).
#
# Source of truth: DIRECTION_Phase1_Trajectory_Aware_Triage.md
# Values will be refined through Phase 4 science sessions.

# -- Starter Recovery Curve (7-day rotation) --
# [floor, expected] per rotation day after a normal outing (70-90 pitches)
starter_recovery_curve:
  day_0: [null, null]   # game day - no arm feel expected
  day_1: [4, 6]         # post-outing soreness normal
  day_2: [5, 7]         # should be improving
  day_3: [6, 8]         # should be "back to good"
  day_4: [7, 8]         # should feel good
  day_5: [6, 9]         # late-rotation readiness
  day_6: [6, 9]         # late-rotation readiness

# -- Reliever Recovery Curves --
# Indexed by appearance intensity, not rotation day
reliever_recovery_heavy:  # 25+ pitches
  day_1: [4, 6]
  day_2: [6, 8]
  day_3_plus: [7, 9]

reliever_recovery_light:  # <25 pitches
  day_1: [6, 8]
  day_2_plus: [7, 9]

reliever_extended_rest:   # 5+ days since last appearance
  any_day: [7, 9]

# -- Population defaults for new pitchers --
population_defaults:
  arm_feel_mean: 7.5
  arm_feel_sd: 1.2
  chronic_drift_floor: 1.0  # min drift threshold on 1-10 scale

# -- Tolerance bands by tier --
tolerance_bands:
  tier_1: 2   # +2 to all thresholds for population-only data
  tier_2: 1   # +1 for low-confidence individual
  tier_3: 0   # thresholds as specified
```

- [ ] **Step 3: Verify YAML parses**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -c "import yaml; d = yaml.safe_load(open('data/constraint_defaults/population_baselines.yaml')); print(f'Keys: {list(d.keys())}'); print(f'Day 3 starter: {d[\"starter_recovery_curve\"][\"day_3\"]}')"
```

Expected: `Keys: ['starter_recovery_curve', 'reliever_recovery_heavy', ...]` and `Day 3 starter: [6, 8]`

- [ ] **Step 4: Commit**

```bash
git add data/constraint_defaults/population_baselines.yaml
git commit -m "feat: add population baselines YAML for Phase 1 triage"
```

---

## Task 2: baselines.py — Recovery Curve Lookup

**Files:**
- Create: `bot/services/baselines.py`
- Create: `tests/test_baselines.py`

- [ ] **Step 1: Write failing tests for recovery curve lookup**

Create `tests/test_baselines.py`:

```python
"""Tests for baselines module — Phase 1 trajectory-aware triage."""


def test_starter_day1_recovery_curve():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="starter", rotation_day=1)
    assert result == {"floor": 4, "expected": 6}


def test_starter_day5_recovery_curve():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="starter", rotation_day=5)
    assert result == {"floor": 6, "expected": 9}


def test_starter_day0_returns_none():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="starter", rotation_day=0)
    assert result == {"floor": None, "expected": None}


def test_reliever_heavy_day1():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=1, pitch_count=30
    )
    assert result == {"floor": 4, "expected": 6}


def test_reliever_heavy_day3_plus():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=4, pitch_count=35
    )
    assert result == {"floor": 7, "expected": 9}


def test_reliever_light_day1():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=1, pitch_count=15
    )
    assert result == {"floor": 6, "expected": 8}


def test_reliever_light_day2_plus():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=3, pitch_count=20
    )
    assert result == {"floor": 7, "expected": 9}


def test_reliever_extended_rest():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=6, pitch_count=None
    )
    assert result == {"floor": 7, "expected": 9}


def test_reliever_no_pitch_count_defaults_heavy():
    """When pitch count is unknown, default to heavy bucket (safer)."""
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(
        role="reliever", rotation_day=1, pitch_count=None
    )
    # Heavy day 1
    assert result == {"floor": 4, "expected": 6}


def test_starter_day_beyond_rotation():
    """Day 7+ with no new outing — should return day_6 values (last known)."""
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="starter", rotation_day=8)
    assert result == {"floor": 6, "expected": 9}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'bot.services.baselines'`

- [ ] **Step 3: Implement recovery curve lookup**

Create `bot/services/baselines.py`:

```python
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

# ---------------------------------------------------------------------------
# Population baselines (loaded once from YAML)
# ---------------------------------------------------------------------------

_POPULATION_BASELINES = None


def _load_population_baselines() -> dict:
    """Load and cache population_baselines.yaml."""
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


# ---------------------------------------------------------------------------
# Recovery curve lookup
# ---------------------------------------------------------------------------


def get_recovery_curve_expected(
    role: str,
    rotation_day: int,
    pitch_count: int = None,
) -> dict:
    """Get expected [floor, expected] for a pitcher on this rotation day.

    Args:
        role: Pitcher role string (contains "starter" or "reliever")
        rotation_day: Days since last outing (0 = game day)
        pitch_count: Pitch count from last outing (for reliever intensity bucket).
                     None defaults to heavy bucket (safer assumption).

    Returns:
        {"floor": int|None, "expected": int|None}
    """
    pop = _load_population_baselines()

    if "starter" in role.lower():
        return _starter_curve_lookup(pop, rotation_day)
    else:
        return _reliever_curve_lookup(pop, rotation_day, pitch_count)


def _starter_curve_lookup(pop: dict, rotation_day: int) -> dict:
    """Look up starter recovery curve value for a rotation day."""
    curve = pop["starter_recovery_curve"]
    key = f"day_{rotation_day}"

    if key in curve:
        floor, expected = curve[key]
        return {"floor": floor, "expected": expected}

    # Beyond defined rotation (day 7+): use day_6 (last known)
    if rotation_day > 6:
        floor, expected = curve["day_6"]
        return {"floor": floor, "expected": expected}

    return {"floor": None, "expected": None}


def _reliever_curve_lookup(
    pop: dict, rotation_day: int, pitch_count: int = None
) -> dict:
    """Look up reliever recovery curve based on days since appearance + intensity."""
    # Extended rest: 5+ days since appearance
    if rotation_day >= 5:
        vals = pop["reliever_extended_rest"]["any_day"]
        return {"floor": vals[0], "expected": vals[1]}

    # Determine heavy vs light (default to heavy when unknown)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/services/baselines.py tests/test_baselines.py
git commit -m "feat: add recovery curve lookup in baselines module"
```

---

## Task 3: baselines.py — Baseline Computation + Tier Classification

**Files:**
- Modify: `bot/services/baselines.py`
- Modify: `tests/test_baselines.py`

- [ ] **Step 1: Write failing tests for baseline computation**

Append to `tests/test_baselines.py`:

```python
# ---------------------------------------------------------------------------
# Baseline computation tests
# ---------------------------------------------------------------------------


def _make_entry(date: str, arm_feel: int, rotation_day: int = 0) -> dict:
    """Helper to build a minimal daily_entry for testing."""
    return {
        "date": date,
        "rotation_day": rotation_day,
        "pre_training": {"arm_feel": arm_feel},
    }


def _make_entries_for_days(start_date: str, arm_feels: list, rotation_days: list = None):
    """Build a list of daily entries from a start date."""
    from datetime import datetime, timedelta
    base = datetime.strptime(start_date, "%Y-%m-%d")
    entries = []
    for i, af in enumerate(arm_feels):
        d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        rd = rotation_days[i] if rotation_days else i % 7
        entries.append(_make_entry(d, af, rd))
    return entries


def test_tier1_with_no_data():
    from bot.services.baselines import compute_pitcher_baseline
    result = compute_pitcher_baseline([], rotation_length=7)
    assert result["tier"] == 1
    assert result["total_check_ins"] == 0
    assert result["rotations_completed"] == 0


def test_tier1_with_partial_rotation():
    """Less than 1 full rotation of data = Tier 1."""
    from bot.services.baselines import compute_pitcher_baseline
    entries = _make_entries_for_days("2026-04-01", [7, 8, 7, 8, 9])
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 1
    assert result["total_check_ins"] == 5
    assert result["rotations_completed"] == 0


def test_tier2_with_one_rotation():
    """1-2 rotations = Tier 2."""
    from bot.services.baselines import compute_pitcher_baseline
    # Simulate 1 full rotation: rotation_day goes 0,1,2,3,4,5,6,0
    rotation_days = [0, 1, 2, 3, 4, 5, 6, 0]
    entries = _make_entries_for_days(
        "2026-04-01",
        [6, 6, 7, 8, 8, 9, 9, 6],
        rotation_days=rotation_days,
    )
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 2
    assert result["rotations_completed"] >= 1


def test_tier3_with_three_rotations():
    """3+ rotations = Tier 3."""
    from bot.services.baselines import compute_pitcher_baseline
    # 3 full rotations = 21 days + 1 day to start 4th
    rotation_days = [i % 7 for i in range(22)]
    arm_feels = [6, 6, 7, 8, 8, 9, 9] * 3 + [6]
    entries = _make_entries_for_days(
        "2026-03-15",
        arm_feels,
        rotation_days=rotation_days,
    )
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 3
    assert result["rotations_completed"] >= 3


def test_rotation_day_baselines_computed():
    from bot.services.baselines import compute_pitcher_baseline
    rotation_days = [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6]
    arm_feels = [6, 6, 7, 8, 8, 9, 9, 5, 6, 7, 8, 8, 9, 9]
    entries = _make_entries_for_days("2026-04-01", arm_feels, rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)

    # Day 0 should have mean of (6+5)/2 = 5.5
    assert result["rotation_day_baselines"]["0"]["mean"] == 5.5
    assert result["rotation_day_baselines"]["0"]["n"] == 2
    # Day 6 should have mean of (9+9)/2 = 9.0
    assert result["rotation_day_baselines"]["6"]["mean"] == 9.0


def test_chronic_drift_not_flagged_when_stable():
    from bot.services.baselines import compute_pitcher_baseline
    # 28 days of consistent 7s and 8s — no drift
    arm_feels = [7, 8] * 14
    entries = _make_entries_for_days("2026-03-15", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["drift_flagged"] is False


def test_chronic_drift_flagged_when_declining():
    from bot.services.baselines import compute_pitcher_baseline
    # First 14 days: 8s. Last 14 days: 5s. Clear drift.
    arm_feels = [8] * 14 + [5] * 14
    entries = _make_entries_for_days("2026-03-15", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["drift_flagged"] is True
    assert result["chronic_drift"] > 1.0


def test_chronic_drift_requires_14_checkins():
    from bot.services.baselines import compute_pitcher_baseline
    # Only 10 check-ins — drift should not be computed
    arm_feels = [8] * 5 + [4] * 5
    entries = _make_entries_for_days("2026-04-01", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["drift_flagged"] is False
    assert result["rolling_14d_mean"] is None


def test_overall_stats_computed():
    from bot.services.baselines import compute_pitcher_baseline
    arm_feels = [6, 7, 8, 9]
    entries = _make_entries_for_days("2026-04-01", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["overall_mean"] == 7.5
    assert result["overall_sd"] > 0
    assert result["total_check_ins"] == 4


def test_entries_with_missing_arm_feel_excluded():
    """Entries without arm_feel in pre_training are skipped."""
    from bot.services.baselines import compute_pitcher_baseline
    entries = [
        _make_entry("2026-04-01", 7, 0),
        {"date": "2026-04-02", "rotation_day": 1, "pre_training": {}},
        {"date": "2026-04-03", "rotation_day": 2, "pre_training": None},
        _make_entry("2026-04-04", 8, 3),
    ]
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["total_check_ins"] == 2


def test_reliever_appearance_counts_as_rotation():
    """For relievers, each appearance (rotation_day resets to 0) = 1 rotation."""
    from bot.services.baselines import compute_pitcher_baseline
    # Reliever: appears on day 0, rests 2 days, appears again, rests 3 days, appears again
    rotation_days = [0, 1, 2, 0, 1, 2, 3, 0, 1]
    arm_feels = [6, 7, 8, 6, 7, 8, 9, 5, 7]
    entries = _make_entries_for_days("2026-04-01", arm_feels, rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["rotations_completed"] >= 3
    assert result["tier"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py::test_tier1_with_no_data -v
```

Expected: `ImportError: cannot import name 'compute_pitcher_baseline'`

- [ ] **Step 3: Implement baseline computation**

Append to `bot/services/baselines.py` (after the recovery curve section):

```python
# ---------------------------------------------------------------------------
# Baseline computation
# ---------------------------------------------------------------------------


def compute_pitcher_baseline(
    daily_entries: list,
    rotation_length: int = 7,
) -> dict:
    """Compute per-pitcher rotation-day baseline from check-in history.

    Args:
        daily_entries: List of daily entry dicts (any order, will be sorted).
            Each must have "date", "rotation_day", and "pre_training.arm_feel".
        rotation_length: Pitcher's rotation length (7 for starters).

    Returns:
        Baseline snapshot dict with tier, rotation_day_baselines, stats, drift.
    """
    # Extract entries with valid arm_feel
    entries_with_af = []
    for e in daily_entries:
        pt = e.get("pre_training") or {}
        af = pt.get("arm_feel")
        if af is not None:
            entries_with_af.append(
                {
                    "date": e.get("date", ""),
                    "arm_feel": af,
                    "rotation_day": e.get("rotation_day", 0),
                }
            )

    total_check_ins = len(entries_with_af)

    if total_check_ins == 0:
        return _empty_baseline()

    # Sort by date ascending
    sorted_entries = sorted(entries_with_af, key=lambda x: x["date"])

    # Count completed rotations
    rotations_completed = _count_rotations(sorted_entries)

    # Determine tier
    if rotations_completed < 1:
        tier = 1
    elif rotations_completed < 3:
        tier = 2
    else:
        tier = 3

    # Compute per-rotation-day baselines
    rd_groups = {}
    for e in sorted_entries:
        rd = str(e["rotation_day"])
        rd_groups.setdefault(rd, []).append(e["arm_feel"])

    rotation_day_baselines = {}
    for rd, values in rd_groups.items():
        n = len(values)
        mean = sum(values) / n
        sd = _sample_sd(values)
        rotation_day_baselines[rd] = {
            "mean": round(mean, 1),
            "sd": round(sd, 1),
            "n": n,
        }

    # Overall stats
    all_af = [e["arm_feel"] for e in sorted_entries]
    overall_mean = sum(all_af) / len(all_af)
    overall_sd = _sample_sd(all_af)

    # Chronic drift
    rolling_14d_mean, prior_14d_mean, chronic_drift, drift_threshold, drift_flagged = (
        _compute_chronic_drift(sorted_entries, overall_mean, overall_sd)
    )

    return {
        "tier": tier,
        "rotation_day_baselines": rotation_day_baselines,
        "overall_mean": round(overall_mean, 1),
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
    """Return a Tier 1 baseline for pitchers with no data."""
    pop = _load_population_baselines()
    defaults = pop.get("population_defaults", {})
    return {
        "tier": 1,
        "rotation_day_baselines": {},
        "overall_mean": defaults.get("arm_feel_mean", 7.5),
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

    A rotation is completed when rotation_day goes from a non-zero value
    back to 0 (a new outing was logged). For relievers, each appearance
    (reset to 0) counts as one completed rotation.
    """
    rotations = 0
    prev_rd = None
    for e in sorted_entries:
        rd = e["rotation_day"]
        if prev_rd is not None and prev_rd > 0 and rd == 0:
            rotations += 1
        prev_rd = rd
    return rotations


def _sample_sd(values: list) -> float:
    """Compute sample standard deviation. Returns 0.0 for < 2 values."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5


def _compute_chronic_drift(
    sorted_entries: list,
    overall_mean: float,
    overall_sd: float,
) -> tuple:
    """Compute chronic drift from sorted entries.

    Returns: (rolling_14d_mean, prior_14d_mean, drift, threshold, flagged)
    """
    n = len(sorted_entries)

    # Minimum 14 check-in days to compute drift
    if n < 14:
        threshold = max(1.0, 0.75 * overall_sd) if overall_sd > 0 else 1.0
        return None, None, 0.0, threshold, False

    # Rolling 14d = last 14 entries; prior = 14 before that
    rolling = sorted_entries[-14:]
    prior_start = max(0, n - 28)
    prior_end = n - 14
    prior = sorted_entries[prior_start:prior_end] if prior_end > prior_start else []

    rolling_14d_mean = sum(e["arm_feel"] for e in rolling) / len(rolling)
    prior_14d_mean = (
        sum(e["arm_feel"] for e in prior) / len(prior) if prior else None
    )

    drift = overall_mean - rolling_14d_mean
    threshold = max(1.0, 0.75 * overall_sd)
    flagged = drift > threshold

    return rolling_14d_mean, prior_14d_mean, drift, threshold, flagged


def get_tolerance_band(tier: int) -> int:
    """Return the tolerance band for a baseline tier.

    Tier 1 (population): +2 to all thresholds
    Tier 2 (low-confidence): +1
    Tier 3 (high-confidence): +0
    """
    pop = _load_population_baselines()
    bands = pop.get("tolerance_bands", {})
    return bands.get(f"tier_{tier}", 0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py -v
```

Expected: All tests PASS (original 11 + new 12 = 23 total).

- [ ] **Step 5: Commit**

```bash
git add bot/services/baselines.py tests/test_baselines.py
git commit -m "feat: add baseline computation with tier classification and chronic drift"
```

---

## Task 4: baselines.py — Cache-Aware Refresh

**Files:**
- Modify: `bot/services/baselines.py`
- Modify: `bot/services/db.py` (lines 79-89)
- Modify: `tests/test_baselines.py`

- [ ] **Step 1: Write failing test for get_or_refresh_baseline**

Append to `tests/test_baselines.py`:

```python
# ---------------------------------------------------------------------------
# Cache-aware refresh tests
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


def test_get_or_refresh_returns_cached_when_fresh():
    from bot.services.baselines import get_or_refresh_baseline
    from bot.config import CHICAGO_TZ

    now = datetime.now(CHICAGO_TZ)
    cached = {
        "tier": 2,
        "computed_at": now.isoformat(),
        "total_check_ins": 10,
        "rotation_day_baselines": {},
        "overall_mean": 7.0,
        "overall_sd": 1.0,
        "rotations_completed": 1,
        "rolling_14d_mean": None,
        "prior_14d_mean": None,
        "chronic_drift": 0.0,
        "drift_threshold": 1.0,
        "drift_flagged": False,
    }

    result = get_or_refresh_baseline(
        pitcher_id="test_001",
        cached_snapshot=cached,
        daily_entries=[],
        rotation_length=7,
        last_outing_date=None,
    )
    # Should return cached since it's fresh
    assert result["tier"] == 2
    assert result["_recomputed"] is False


def test_get_or_refresh_recomputes_when_stale():
    from bot.services.baselines import get_or_refresh_baseline
    from bot.config import CHICAGO_TZ

    stale_time = (datetime.now(CHICAGO_TZ) - timedelta(hours=25)).isoformat()
    cached = {
        "tier": 1,
        "computed_at": stale_time,
        "total_check_ins": 0,
    }

    entries = _make_entries_for_days("2026-04-01", [7, 8, 7, 8, 9, 8, 7, 8])
    result = get_or_refresh_baseline(
        pitcher_id="test_001",
        cached_snapshot=cached,
        daily_entries=entries,
        rotation_length=7,
        last_outing_date=None,
    )
    assert result["_recomputed"] is True
    assert result["total_check_ins"] == 8


def test_get_or_refresh_recomputes_when_missing():
    from bot.services.baselines import get_or_refresh_baseline

    entries = _make_entries_for_days("2026-04-01", [7, 8])
    result = get_or_refresh_baseline(
        pitcher_id="test_001",
        cached_snapshot=None,
        daily_entries=entries,
        rotation_length=7,
        last_outing_date=None,
    )
    assert result["_recomputed"] is True


def test_get_or_refresh_recomputes_on_new_outing():
    from bot.services.baselines import get_or_refresh_baseline
    from bot.config import CHICAGO_TZ

    now = datetime.now(CHICAGO_TZ)
    cached = {
        "tier": 2,
        "computed_at": now.isoformat(),
        "total_check_ins": 10,
        "last_outing_date": "2026-04-10",
    }

    entries = _make_entries_for_days("2026-04-01", [7, 8, 7])
    result = get_or_refresh_baseline(
        pitcher_id="test_001",
        cached_snapshot=cached,
        daily_entries=entries,
        rotation_length=7,
        last_outing_date="2026-04-15",  # newer than cached
    )
    assert result["_recomputed"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py::test_get_or_refresh_returns_cached_when_fresh -v
```

Expected: `ImportError: cannot import name 'get_or_refresh_baseline'`

- [ ] **Step 3: Implement get_or_refresh_baseline**

Append to `bot/services/baselines.py`:

```python
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

    Returns the baseline dict with an added "_recomputed" bool
    (stripped by the caller before persisting).
    """
    if _should_recompute(cached_snapshot, last_outing_date):
        baseline = compute_pitcher_baseline(daily_entries, rotation_length)
        if last_outing_date:
            baseline["last_outing_date"] = last_outing_date
        baseline["_recomputed"] = True
        logger.info(
            "Recomputed baseline for %s: tier=%d, check-ins=%d",
            pitcher_id,
            baseline["tier"],
            baseline["total_check_ins"],
        )
        return baseline

    cached_snapshot["_recomputed"] = False
    return cached_snapshot


def _should_recompute(cached: dict | None, last_outing_date: str = None) -> bool:
    """Determine if baseline needs recomputation."""
    if not cached or not cached.get("computed_at"):
        return True

    # Check TTL
    try:
        computed_at = datetime.fromisoformat(cached["computed_at"])
        now = datetime.now(CHICAGO_TZ)
        age_hours = (now - computed_at).total_seconds() / 3600
        if age_hours > _CACHE_TTL_HOURS:
            return True
    except (ValueError, TypeError):
        return True

    # Check if new outing since last computation
    if last_outing_date and cached.get("last_outing_date"):
        if last_outing_date > cached["last_outing_date"]:
            return True

    return False
```

- [ ] **Step 4: Run all baseline tests**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_baselines.py -v
```

Expected: All tests PASS (27 total).

- [ ] **Step 5: Commit**

```bash
git add bot/services/baselines.py tests/test_baselines.py
git commit -m "feat: add cache-aware baseline refresh with TTL and outing invalidation"
```

---

## Task 5: Triage Rewrite — Golden Snapshot Tests

**Files:**
- Create: `tests/test_triage_phase1.py`

This captures current triage behavior BEFORE the rewrite. These tests must continue to pass after the rewrite when called without new arguments.

- [ ] **Step 1: Write golden snapshot tests**

Create `tests/test_triage_phase1.py`:

```python
"""Phase 1 triage tests — golden snapshots + new category scoring.

Golden snapshots capture current triage behavior. They MUST pass when
triage is called without Phase 1 arguments (backward compatibility).
"""


def _make_profile(
    role="starter",
    rotation_length=7,
    days_since_outing=3,
    injury_areas=None,
    active_modifications=None,
    grip_drop=False,
):
    """Build a minimal pitcher_profile for triage testing."""
    injuries = []
    if injury_areas:
        for area in injury_areas:
            injuries.append({"area": area, "flag_level": "green"})

    return {
        "role": role,
        "rotation_length": rotation_length,
        "active_flags": {
            "days_since_outing": days_since_outing,
            "current_arm_feel": None,
            "active_modifications": active_modifications or [],
            "grip_drop_reported": grip_drop,
        },
        "injury_history": injuries,
    }


# ---------------------------------------------------------------------------
# Golden snapshot tests — MUST pass with no new args (backward compat)
# ---------------------------------------------------------------------------


class TestGoldenSnapshots:
    """Current triage behavior that must be preserved when called without
    Phase 1 arguments."""

    def test_instant_red_arm_feel_1(self):
        from bot.services.triage import triage

        result = triage(arm_feel=1, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"
        assert "critically low" in result["reasoning"].lower()

    def test_instant_red_arm_feel_2(self):
        from bot.services.triage import triage

        result = triage(arm_feel=2, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_arm_feel_4(self):
        from bot.services.triage import triage

        result = triage(arm_feel=4, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_ucl_with_history(self):
        from bot.services.triage import triage

        profile = _make_profile(injury_areas=["medial_elbow"])
        result = triage(
            arm_feel=7,
            sleep_hours=8.0,
            pitcher_profile=profile,
            ucl_sensation=True,
        )
        assert result["flag_level"] == "red"

    def test_instant_red_significant_tightness_with_history(self):
        from bot.services.triage import triage

        profile = _make_profile(injury_areas=["forearm"])
        result = triage(
            arm_feel=7,
            sleep_hours=8.0,
            pitcher_profile=profile,
            forearm_tightness="significant",
        )
        assert result["flag_level"] == "red"

    def test_two_yellows_produce_red(self):
        from bot.services.triage import triage

        result = triage(
            arm_feel=6,
            sleep_hours=5.0,
            pitcher_profile=_make_profile(),
        )
        assert result["flag_level"] == "red"

    def test_single_yellow_arm_feel(self):
        from bot.services.triage import triage

        result = triage(arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "yellow"

    def test_single_yellow_low_sleep(self):
        from bot.services.triage import triage

        result = triage(arm_feel=7, sleep_hours=5.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "yellow"

    def test_modified_green_borderline_sleep(self):
        from bot.services.triage import triage

        result = triage(arm_feel=7, sleep_hours=6.2, pitcher_profile=_make_profile())
        assert result["flag_level"] == "modified_green"

    def test_modified_green_moderate_whoop(self):
        from bot.services.triage import triage

        result = triage(
            arm_feel=7,
            sleep_hours=8.0,
            pitcher_profile=_make_profile(),
            whoop_recovery=40.0,
        )
        assert result["flag_level"] == "modified_green"

    def test_green_all_good(self):
        from bot.services.triage import triage

        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "green"

    def test_green_start_proximity(self):
        from bot.services.triage import triage

        profile = _make_profile(days_since_outing=5, rotation_length=7)
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile)
        assert result["flag_level"] == "green"
        assert "primer_session" in result["modifications"]

    def test_output_shape_has_required_keys(self):
        from bot.services.triage import triage

        result = triage(arm_feel=7, sleep_hours=7.0, pitcher_profile=_make_profile())
        assert "flag_level" in result
        assert "modifications" in result
        assert "alerts" in result
        assert "protocol_adjustments" in result
        assert "reasoning" in result

    def test_protocol_adjustments_shape(self):
        from bot.services.triage import triage

        result = triage(arm_feel=7, sleep_hours=7.0, pitcher_profile=_make_profile())
        pa = result["protocol_adjustments"]
        assert "lifting_intensity_cap" in pa
        assert "remove_exercises" in pa
        assert "add_exercises" in pa
        assert "arm_care_template" in pa
        assert "plyocare_allowed" in pa
        assert "throwing_adjustments" in pa
```

- [ ] **Step 2: Run golden snapshot tests against current triage**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_triage_phase1.py -v
```

Expected: All 14 tests PASS. If any fail, the golden snapshot is wrong — fix the test to match current behavior (the test captures reality, not intent).

- [ ] **Step 3: Commit**

```bash
git add tests/test_triage_phase1.py
git commit -m "test: add golden snapshot tests for current triage behavior"
```

---

## Task 6: Triage Rewrite — Category Scoring Helpers

**Files:**
- Modify: `bot/services/triage.py`
- Modify: `tests/test_triage_phase1.py`

- [ ] **Step 1: Write failing tests for tissue scoring**

Append to `tests/test_triage_phase1.py`:

```python
# ---------------------------------------------------------------------------
# Category scoring tests — Phase 1
# ---------------------------------------------------------------------------


class TestTissueScore:
    """Tissue score (0-10) computation tests."""

    def test_arm_feel_2_scores_8(self):
        from bot.services.triage import _compute_tissue_score
        result = _compute_tissue_score(arm_feel=2)
        assert result["score"] >= 8

    def test_arm_feel_3_scores_5(self):
        from bot.services.triage import _compute_tissue_score
        result = _compute_tissue_score(arm_feel=3)
        assert result["score"] >= 5

    def test_arm_feel_7_scores_0(self):
        from bot.services.triage import _compute_tissue_score
        result = _compute_tissue_score(arm_feel=7)
        assert result["score"] == 0

    def test_forearm_mild_adds_1(self):
        from bot.services.triage import _compute_tissue_score
        base = _compute_tissue_score(arm_feel=7)
        with_ft = _compute_tissue_score(arm_feel=7, forearm_tightness="mild")
        assert with_ft["score"] == base["score"] + 1

    def test_forearm_significant_adds_6(self):
        from bot.services.triage import _compute_tissue_score
        result = _compute_tissue_score(arm_feel=7, forearm_tightness="significant")
        assert result["score"] >= 6

    def test_ucl_with_history_adds_8(self):
        from bot.services.triage import _compute_tissue_score
        result = _compute_tissue_score(
            arm_feel=7, ucl_sensation=True, injury_areas=["medial_elbow"]
        )
        assert result["score"] >= 8

    def test_grip_drop_adds_2(self):
        from bot.services.triage import _compute_tissue_score
        base = _compute_tissue_score(arm_feel=7)
        with_grip = _compute_tissue_score(arm_feel=7, grip_drop=True)
        assert with_grip["score"] == base["score"] + 2

    def test_concerned_adds_3(self):
        from bot.services.triage import _compute_tissue_score
        base = _compute_tissue_score(arm_feel=7)
        with_concern = _compute_tissue_score(arm_feel=7, arm_clarification="concerned")
        assert with_concern["score"] == base["score"] + 3

    def test_expected_soreness_day1_reduces_2(self):
        from bot.services.triage import _compute_tissue_score
        base = _compute_tissue_score(arm_feel=5)
        with_soreness = _compute_tissue_score(
            arm_feel=5, arm_clarification="expected_soreness", rotation_day=1
        )
        assert with_soreness["score"] == max(0, base["score"] - 2)

    def test_expected_soreness_day5_no_reduction(self):
        """Expected soreness only reduces on day 0-2."""
        from bot.services.triage import _compute_tissue_score
        base = _compute_tissue_score(arm_feel=5)
        with_soreness = _compute_tissue_score(
            arm_feel=5, arm_clarification="expected_soreness", rotation_day=5
        )
        assert with_soreness["score"] == base["score"]

    def test_consecutive_low_days_2_adds_1(self):
        from bot.services.triage import _compute_tissue_score
        recent_arm_feel = [
            {"date": "2026-04-17", "arm_feel": 5, "rotation_day": 3},
            {"date": "2026-04-16", "arm_feel": 5, "rotation_day": 2},
        ]
        result = _compute_tissue_score(arm_feel=5, recent_arm_feel=recent_arm_feel)
        # arm_feel 5 = +2 base, plus 2 consecutive days <=5 = +1
        assert result["score"] >= 3

    def test_rate_of_change_3_point_drop(self):
        """Sprint 1a absorbed: 3+ point drop in 1 day = +2."""
        from bot.services.triage import _compute_tissue_score
        recent_arm_feel = [
            {"date": "2026-04-17", "arm_feel": 8, "rotation_day": 3},
        ]
        result = _compute_tissue_score(arm_feel=5, recent_arm_feel=recent_arm_feel)
        # 8 -> 5 = 3 point drop = +2. Plus arm_feel 5 = +2. Total >= 4
        assert result["score"] >= 4


class TestLoadScore:
    """Load score (0-10) computation tests."""

    def test_no_load_scores_0(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score()
        assert result["score"] == 0

    def test_pitch_count_85_adds_2(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(pitch_count=85)
        assert result["score"] >= 2

    def test_pitch_count_100_adds_3(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(pitch_count=100)
        assert result["score"] >= 3

    def test_days_since_outing_0_adds_2(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(days_since_outing=0)
        assert result["score"] >= 2

    def test_days_since_outing_2_adds_1(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(days_since_outing=2)
        assert result["score"] >= 1

    def test_start_proximity_0_days_adds_2(self):
        """Start proximity folded into load: 0-1 days to start = +2."""
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(days_to_start=0)
        assert result["score"] >= 2

    def test_start_proximity_2_days_adds_1(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(days_to_start=2)
        assert result["score"] >= 1

    def test_whoop_strain_high(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(whoop_strain_yesterday=19.0)
        assert result["score"] >= 2

    def test_reliever_3_appearances(self):
        from bot.services.triage import _compute_load_score
        result = _compute_load_score(reliever_appearances_this_week=3)
        assert result["score"] >= 3


class TestRecoveryScore:
    """Recovery score (0-10) computation tests."""

    def test_no_recovery_data_scores_0(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=8.0)
        assert result["score"] == 0

    def test_sleep_under_5h(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=4.5)
        assert result["score"] >= 3

    def test_sleep_5_to_6h(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=5.5)
        assert result["score"] >= 2

    def test_whoop_recovery_low(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=8.0, whoop_recovery=25.0)
        assert result["score"] >= 2

    def test_energy_3_adds_2(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=8.0, energy=3)
        assert result["score"] >= 2

    def test_energy_4_adds_1(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(sleep_hours=8.0, energy=4)
        assert result["score"] >= 1

    def test_hrv_drop_over_15pct(self):
        from bot.services.triage import _compute_recovery_score
        result = _compute_recovery_score(
            sleep_hours=8.0, whoop_hrv=40.0, whoop_hrv_7day_avg=60.0
        )
        # Drop of 33% > 15% = +2
        assert result["score"] >= 2


class TestInteractionRules:
    """Interaction rules that replace flat yellow-trigger counting."""

    def test_tissue_7_is_red(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=7, load=0, recovery=0)
        assert result == "red"

    def test_tissue_4_load_4_is_red(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=4, load=4, recovery=0)
        assert result == "red"

    def test_tissue_3_is_yellow(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=3, load=0, recovery=0)
        assert result == "yellow"

    def test_load_4_recovery_4_is_yellow(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=0, load=4, recovery=4)
        assert result == "yellow"

    def test_recovery_3_alone_is_modified_green(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=0, load=0, recovery=3)
        assert result == "modified_green"

    def test_two_recovery_signals_not_red(self):
        """Critical difference: two recovery signals = modified_green, NOT red."""
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=0, load=0, recovery=6)
        assert result == "modified_green"

    def test_load_3_alone_is_modified_green(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=0, load=3, recovery=0)
        assert result == "modified_green"

    def test_tissue_1_is_modified_green(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=1, load=0, recovery=0)
        assert result == "modified_green"

    def test_all_below_is_green(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(tissue=0, load=0, recovery=0)
        assert result == "green"

    def test_chronic_drift_is_yellow(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(
            tissue=0, load=0, recovery=0, chronic_drift=True
        )
        assert result == "yellow"

    def test_recovery_curve_stall_is_yellow(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(
            tissue=0, load=0, recovery=0, recovery_stall=True
        )
        assert result == "yellow"

    def test_tissue_4_plus_stall_and_pace_is_red(self):
        from bot.services.triage import _apply_interaction_rules
        result = _apply_interaction_rules(
            tissue=4, load=0, recovery=0,
            recovery_stall=True, pace_below_floor=True,
        )
        assert result == "red"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_triage_phase1.py::TestTissueScore::test_arm_feel_7_scores_0 -v
```

Expected: `ImportError: cannot import name '_compute_tissue_score'`

- [ ] **Step 3: Implement category scoring helpers and interaction rules**

Rewrite `bot/services/triage.py` — keep existing `triage()` function signature working, add new helpers at top of file. The full file content:

```python
"""Weighted multi-factor triage system — Phase 1: Trajectory-Aware.

Three-category scoring (tissue/load/recovery) with interaction rules,
recovery curve evaluation, dynamic baselines, and absorbed trend detection.

Replaces flat yellow-trigger counting from pre-Phase-1.
Backward compatible: calling with no Phase 1 args produces identical output.
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category 1: Tissue Score (0-10, highest priority)
# ---------------------------------------------------------------------------


def _compute_tissue_score(
    arm_feel: int,
    forearm_tightness: str = None,
    ucl_sensation: bool = False,
    injury_areas: list = None,
    grip_drop: bool = False,
    arm_clarification: str = None,
    rotation_day: int = None,
    recent_arm_feel: list = None,
    baseline: dict = None,
    recovery_curve_result: dict = None,
) -> dict:
    """Compute tissue score from arm/body stress indicators.

    Returns: {"score": float, "reasons": list[str]}
    """
    score = 0.0
    reasons = []
    injury_areas = injury_areas or []
    tightness = (forearm_tightness or "").lower()

    # Absolute arm feel
    af_points = {1: 8, 2: 8, 3: 5, 4: 3, 5: 2, 6: 1}
    if arm_feel in af_points:
        pts = af_points[arm_feel]
        score += pts
        reasons.append(f"arm feel {arm_feel}/10 (+{pts})")

    # Deviation from rotation-day expected value
    if baseline and baseline.get("tier", 1) >= 2 and rotation_day is not None:
        rd_baselines = baseline.get("rotation_day_baselines", {})
        rd_data = rd_baselines.get(str(rotation_day))
        if rd_data and rd_data.get("mean"):
            deviation = rd_data["mean"] - arm_feel
            if deviation >= 1.0:
                pts = deviation
                score += pts
                reasons.append(
                    f"arm feel {deviation:.1f} below rotation-day expected "
                    f"{rd_data['mean']:.1f} (+{pts:.1f})"
                )

    # Recovery curve violations (injected from recovery curve evaluation)
    if recovery_curve_result:
        curve_pts = recovery_curve_result.get("tissue_points", 0)
        if curve_pts > 0:
            score += curve_pts
            for r in recovery_curve_result.get("reasons", []):
                reasons.append(r)

    # Chronic drift
    if baseline and baseline.get("drift_flagged"):
        score += 2
        reasons.append("chronic drift flagged — 14d average declining (+2)")

    # Forearm tightness
    ft_points = {"mild": 1, "moderate": 3, "significant": 6}
    if tightness in ft_points:
        pts = ft_points[tightness]
        score += pts
        reasons.append(f"forearm tightness {tightness} (+{pts})")

    # UCL sensation with medial elbow/forearm history
    if ucl_sensation and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        score += 8
        reasons.append("UCL sensation with medial elbow/forearm history (+8)")

    # Grip drop
    if grip_drop:
        score += 2
        reasons.append("grip drop reported (+2)")

    # Consecutive days arm_feel <= 5 (excluding expected post-outing days)
    if recent_arm_feel:
        consecutive = _count_consecutive_low_days(arm_feel, recent_arm_feel, rotation_day)
        if consecutive >= 3:
            score += 3
            reasons.append(f"{consecutive} consecutive days arm feel <= 5 (+3)")
        elif consecutive >= 2:
            score += 1
            reasons.append(f"{consecutive} consecutive days arm feel <= 5 (+1)")

    # arm_clarification
    if arm_clarification == "concerned":
        score += 3
        reasons.append("pitcher flagged subjective concern (+3)")
    elif arm_clarification == "expected_soreness" and rotation_day is not None and rotation_day <= 2:
        score = max(0, score - 2)
        reasons.append("expected soreness on day 0-2 (-2)")

    # Sprint 1a absorbed: rate of change
    if recent_arm_feel:
        roc_pts, roc_reason = _rate_of_change_signal(arm_feel, recent_arm_feel)
        if roc_pts > 0:
            score += roc_pts
            reasons.append(roc_reason)

        # Persistence: arm_feel <= 6 for 3+ consecutive check-in days
        persist_pts, persist_reason = _persistence_signal(arm_feel, recent_arm_feel)
        if persist_pts > 0:
            score += persist_pts
            reasons.append(persist_reason)

        # Negative slope over 7-day window
        slope_pts, slope_reason = _slope_signal(arm_feel, recent_arm_feel)
        if slope_pts > 0:
            score += slope_pts
            reasons.append(slope_reason)

    return {"score": min(score, 10), "reasons": reasons}


def _count_consecutive_low_days(
    current_arm_feel: int, recent_arm_feel: list, rotation_day: int = None
) -> int:
    """Count consecutive days with arm_feel <= 5, including today.

    Excludes expected post-outing days (rotation_day 0-1).
    recent_arm_feel is sorted newest-first.
    """
    if current_arm_feel > 5:
        return 0

    count = 1  # today counts
    for entry in recent_arm_feel:
        af = entry.get("arm_feel")
        rd = entry.get("rotation_day")
        if af is None:
            break
        # Skip expected post-outing days
        if rd is not None and rd <= 1:
            continue
        if af <= 5:
            count += 1
        else:
            break
    return count


def _rate_of_change_signal(current_arm_feel: int, recent_arm_feel: list) -> tuple:
    """Sprint 1a absorbed: >= 3 point drop in 1 day = +2."""
    if not recent_arm_feel:
        return 0, ""
    yesterday = recent_arm_feel[0]  # newest-first
    prev_af = yesterday.get("arm_feel")
    if prev_af is not None and (prev_af - current_arm_feel) >= 3:
        drop = prev_af - current_arm_feel
        return 2, f"rapid drop: {prev_af} -> {current_arm_feel} ({drop} points in 1 day, +2)"
    return 0, ""


def _persistence_signal(current_arm_feel: int, recent_arm_feel: list) -> tuple:
    """Sprint 1a absorbed: arm_feel <= 6 for 3+ consecutive check-in days = +1."""
    if current_arm_feel > 6:
        return 0, ""
    consecutive = 1  # today
    for entry in recent_arm_feel:
        af = entry.get("arm_feel")
        if af is not None and af <= 6:
            consecutive += 1
        else:
            break
    if consecutive >= 3:
        return 1, f"arm feel <= 6 for {consecutive} consecutive days (+1)"
    return 0, ""


def _slope_signal(current_arm_feel: int, recent_arm_feel: list) -> tuple:
    """Sprint 1a absorbed: negative slope over 7-day window = +0.5."""
    points = [current_arm_feel]
    for entry in recent_arm_feel:
        af = entry.get("arm_feel")
        if af is not None:
            points.append(af)
        if len(points) >= 7:
            break

    if len(points) < 3:
        return 0, ""

    # Simple linear regression slope (points are newest-first, so reverse)
    points = list(reversed(points))
    n = len(points)
    x_mean = (n - 1) / 2
    y_mean = sum(points) / n
    numerator = sum((i - x_mean) * (points[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0, ""

    slope = numerator / denominator
    if slope < -0.15:  # meaningful negative trend
        return 0.5, f"negative 7-day slope ({slope:.2f}, +0.5)"
    return 0, ""


# ---------------------------------------------------------------------------
# Category 2: Load Score (0-10)
# ---------------------------------------------------------------------------


def _compute_load_score(
    pitch_count: int = None,
    days_since_outing: int = None,
    days_to_start: int = None,
    whoop_strain_yesterday: float = None,
    reliever_appearances_this_week: int = None,
) -> dict:
    """Compute load score from training demand indicators.

    Returns: {"score": float, "reasons": list[str]}
    """
    score = 0.0
    reasons = []

    # Pitch count from last outing
    if pitch_count is not None:
        if pitch_count >= 100:
            score += 3
            reasons.append(f"pitch count {pitch_count} (+3)")
        elif pitch_count >= 80:
            score += 2
            reasons.append(f"pitch count {pitch_count} (+2)")
        elif pitch_count >= 60:
            score += 1
            reasons.append(f"pitch count {pitch_count} (+1)")

    # Days since outing
    if days_since_outing is not None:
        if days_since_outing <= 1:
            score += 2
            reasons.append(f"day {days_since_outing} post-outing (+2)")
        elif days_since_outing == 2:
            score += 1
            reasons.append(f"day {days_since_outing} post-outing (+1)")

    # Start proximity (folded into load)
    if days_to_start is not None:
        if days_to_start <= 1:
            score += 2
            reasons.append(f"start in {days_to_start} day(s) (+2)")
        elif days_to_start == 2:
            score += 1
            reasons.append(f"start in {days_to_start} day(s) (+1)")

    # WHOOP strain yesterday
    if whoop_strain_yesterday is not None:
        if whoop_strain_yesterday > 18:
            score += 2
            reasons.append(f"WHOOP strain {whoop_strain_yesterday:.1f} (+2)")
        elif whoop_strain_yesterday > 14:
            score += 1
            reasons.append(f"WHOOP strain {whoop_strain_yesterday:.1f} (+1)")

    # Reliever appearances this week
    if reliever_appearances_this_week is not None:
        if reliever_appearances_this_week >= 3:
            score += 3
            reasons.append(f"reliever: {reliever_appearances_this_week} appearances this week (+3)")
        elif reliever_appearances_this_week >= 2:
            score += 1
            reasons.append(f"reliever: {reliever_appearances_this_week} appearances this week (+1)")

    return {"score": min(score, 10), "reasons": reasons}


# ---------------------------------------------------------------------------
# Category 3: Recovery Score (0-10)
# ---------------------------------------------------------------------------


def _compute_recovery_score(
    sleep_hours: float,
    energy: int = None,
    whoop_recovery: float = None,
    whoop_hrv: float = None,
    whoop_hrv_7day_avg: float = None,
    whoop_sleep_perf: int = None,
) -> dict:
    """Compute recovery score from systemic readiness indicators.

    Returns: {"score": float, "reasons": list[str]}
    """
    score = 0.0
    reasons = []

    # Sleep hours
    if sleep_hours < 5:
        score += 3
        reasons.append(f"sleep {sleep_hours}h (+3)")
    elif sleep_hours < 6:
        score += 2
        reasons.append(f"sleep {sleep_hours}h (+2)")
    elif sleep_hours < 7:
        score += 1
        reasons.append(f"sleep {sleep_hours}h (+1)")

    # WHOOP recovery
    if whoop_recovery is not None:
        if whoop_recovery < 33:
            score += 2
            reasons.append(f"WHOOP recovery {whoop_recovery}% (+2)")
        elif whoop_recovery < 50:
            score += 1
            reasons.append(f"WHOOP recovery {whoop_recovery}% (+1)")

    # HRV drop from 7-day average
    if whoop_hrv is not None and whoop_hrv_7day_avg is not None and whoop_hrv_7day_avg > 0:
        hrv_drop_pct = (whoop_hrv_7day_avg - whoop_hrv) / whoop_hrv_7day_avg * 100
        if hrv_drop_pct > 15:
            score += 2
            reasons.append(f"HRV {whoop_hrv:.0f}ms, {hrv_drop_pct:.0f}% below 7d avg (+2)")
        elif hrv_drop_pct > 10:
            score += 1
            reasons.append(f"HRV {whoop_hrv:.0f}ms, {hrv_drop_pct:.0f}% below 7d avg (+1)")

    # WHOOP sleep performance
    if whoop_sleep_perf is not None and whoop_sleep_perf < 50:
        score += 1
        reasons.append(f"WHOOP sleep performance {whoop_sleep_perf}% (+1)")

    # Energy
    if energy is not None:
        if energy <= 3:
            score += 2
            reasons.append(f"energy {energy}/10 (+2)")
        elif energy == 4:
            score += 1
            reasons.append(f"energy {energy}/10 (+1)")

    return {"score": min(score, 10), "reasons": reasons}


# ---------------------------------------------------------------------------
# Interaction Rules
# ---------------------------------------------------------------------------


def _apply_interaction_rules(
    tissue: float,
    load: float,
    recovery: float,
    chronic_drift: bool = False,
    recovery_stall: bool = False,
    pace_below_floor: bool = False,
    tolerance_band: int = 0,
) -> str:
    """Apply category interaction rules to determine flag_level.

    Replaces flat yellow-trigger counting entirely.
    tolerance_band: added to thresholds for lower-tier baselines (0/1/2).

    Returns: "red" | "yellow" | "modified_green" | "green"
    """
    # Apply tolerance band (widens thresholds for low-data pitchers)
    t_red_standalone = 7 + tolerance_band
    t_red_compound = 4 + tolerance_band
    t_yellow = 3 + tolerance_band
    t_mg = 3 + tolerance_band
    t_load_recovery_yellow = 4 + tolerance_band

    # RED conditions
    if tissue >= t_red_standalone:
        return "red"
    if tissue >= t_red_compound and load >= t_red_compound:
        return "red"
    if tissue >= t_red_compound and recovery_stall and pace_below_floor:
        return "red"

    # YELLOW conditions
    if tissue >= t_yellow:
        return "yellow"
    if load >= t_load_recovery_yellow and recovery >= t_load_recovery_yellow:
        return "yellow"
    if chronic_drift:
        return "yellow"
    if recovery_stall:
        return "yellow"

    # MODIFIED GREEN conditions
    if recovery >= t_mg:
        return "modified_green"
    if load >= t_mg:
        return "modified_green"
    if 1 <= tissue <= 2:
        return "modified_green"

    return "green"


# ---------------------------------------------------------------------------
# Recovery Curve Evaluation
# ---------------------------------------------------------------------------


def _evaluate_recovery_curve(
    arm_feel: int,
    rotation_day: int,
    recent_arm_feel: list = None,
    role: str = "starter",
    pitch_count: int = None,
    baseline: dict = None,
) -> dict:
    """Evaluate recovery curve for stall, pace, late-rotation, cross-week.

    Returns: {
        "tissue_points": float,
        "reasons": list[str],
        "stall_detected": bool,
        "pace_below_floor": bool,
    }
    """
    from bot.services.baselines import get_recovery_curve_expected

    tissue_points = 0.0
    reasons = []
    stall_detected = False
    pace_below_floor = False

    curve = get_recovery_curve_expected(
        role=role, rotation_day=rotation_day, pitch_count=pitch_count
    )
    floor = curve.get("floor")

    # STALL DETECTION: Day N <= Day N-1 for N >= 3, AND value below floor
    if recent_arm_feel and rotation_day >= 2:
        prev_entry = recent_arm_feel[0] if recent_arm_feel else None
        if prev_entry:
            prev_af = prev_entry.get("arm_feel")
            prev_rd = prev_entry.get("rotation_day")
            if prev_af is not None and prev_rd is not None:
                # Reversal: got worse (any day)
                if arm_feel < prev_af and floor is not None and arm_feel < floor:
                    tissue_points += 3
                    reasons.append(
                        f"arm feel reversed: {prev_af} -> {arm_feel} (below floor {floor}, +3)"
                    )
                    stall_detected = True
                # Stall: flat at Day 3+ AND below floor
                elif (
                    arm_feel <= prev_af
                    and rotation_day >= 3
                    and floor is not None
                    and arm_feel < floor
                ):
                    tissue_points += 2
                    reasons.append(
                        f"arm feel stalled Day {prev_rd} -> Day {rotation_day} "
                        f"(below floor {floor}, +2)"
                    )
                    stall_detected = True

    # PACE DETECTION: arm_feel < floor for this rotation day
    if floor is not None and arm_feel < floor:
        pts = floor - arm_feel
        tissue_points += pts
        pace_below_floor = True
        reasons.append(
            f"Day {rotation_day} arm feel {arm_feel}/10, floor is {floor} (+{pts})"
        )

    # LATE-ROTATION READINESS: Day 5-6, arm_feel < 6
    if rotation_day in (5, 6) and arm_feel < 6:
        tissue_points += 2
        reasons.append(
            f"arm feel {arm_feel} < 6 on Day {rotation_day} — late-rotation readiness (+2)"
        )

    # CROSS-WEEK SLOPE comparison (needs 3+ rotations)
    if baseline and baseline.get("tier", 1) >= 3 and recent_arm_feel:
        slope_pts, slope_reason = _cross_week_slope(
            arm_feel, rotation_day, recent_arm_feel, baseline
        )
        if slope_pts > 0:
            tissue_points += slope_pts
            reasons.append(slope_reason)

    return {
        "tissue_points": tissue_points,
        "reasons": reasons,
        "stall_detected": stall_detected,
        "pace_below_floor": pace_below_floor,
    }


def _cross_week_slope(
    arm_feel: int,
    rotation_day: int,
    recent_arm_feel: list,
    baseline: dict,
) -> tuple:
    """Compare current rotation's recovery slope to average from prior rotations.

    If current slope < 0.7 * average slope, flags concern.
    """
    # Build current rotation's trajectory (day 0/1 -> current day)
    current_rotation = [arm_feel]
    for entry in recent_arm_feel:
        rd = entry.get("rotation_day", 0)
        if rd < rotation_day:
            current_rotation.append(entry.get("arm_feel", 0))
        else:
            break

    if len(current_rotation) < 3:
        return 0, ""

    # Current slope (simple: last - first / days)
    current_rotation.reverse()  # oldest-first
    current_slope = (current_rotation[-1] - current_rotation[0]) / max(len(current_rotation) - 1, 1)

    # Average slope from baseline rotation-day means
    rd_baselines = baseline.get("rotation_day_baselines", {})
    if len(rd_baselines) < 3:
        return 0, ""

    sorted_rds = sorted(rd_baselines.keys(), key=int)
    first_rd = rd_baselines[sorted_rds[0]]
    last_rd = rd_baselines[sorted_rds[-1]]
    avg_slope = (last_rd["mean"] - first_rd["mean"]) / max(int(sorted_rds[-1]) - int(sorted_rds[0]), 1)

    if avg_slope > 0 and current_slope < 0.7 * avg_slope:
        pct = int((current_slope / avg_slope) * 100) if avg_slope > 0 else 0
        return 2, f"recovery pace {pct}% of normal rate (+2)"

    return 0, ""


# ---------------------------------------------------------------------------
# Protocol adjustments builder
# ---------------------------------------------------------------------------


def _build_protocol_adjustments(flag_level: str, tissue_score: float, load_score: float, profile: dict) -> dict:
    """Build protocol_adjustments dict based on flag_level and scores.

    Preserves the same structure the plan generator expects.
    """
    active_flags = profile.get("active_flags", {})
    days_since_outing = active_flags.get("days_since_outing", 99)
    rotation_length = profile.get("rotation_length", 7)
    days_to_start = rotation_length - days_since_outing

    base = {
        "lifting_intensity_cap": None,
        "remove_exercises": [],
        "add_exercises": [],
        "arm_care_template": "heavy",
        "plyocare_allowed": True,
        "throwing_adjustments": {
            "max_day_type": None,
            "skip_phases": [],
            "intensity_cap_pct": None,
            "volume_modifier": 1.0,
            "override_to": None,
        },
    }

    if flag_level == "red":
        base["lifting_intensity_cap"] = "none"
        base["remove_exercises"] = ["all_lifting", "med_ball", "plyometrics"]
        base["arm_care_template"] = "light"
        base["plyocare_allowed"] = False
        base["throwing_adjustments"] = {
            "max_day_type": "no_throw",
            "skip_phases": ["compression", "bullpen", "long_toss_extension", "plyo_drills"],
            "intensity_cap_pct": 0,
            "volume_modifier": 0,
            "override_to": "no_throw",
        }
    elif flag_level == "yellow":
        if tissue_score >= 3:
            # Tissue-driven yellow: more conservative
            base["lifting_intensity_cap"] = "RPE 5-6"
            base["remove_exercises"].extend(["med_ball", "plyometrics"])
            base["plyocare_allowed"] = False
            base["arm_care_template"] = "light"
            base["throwing_adjustments"] = {
                "max_day_type": "recovery",
                "skip_phases": ["compression", "bullpen", "long_toss_extension"],
                "intensity_cap_pct": 50,
                "volume_modifier": 0.5,
                "override_to": "recovery",
            }
        else:
            # Load/recovery-driven yellow: moderate
            base["lifting_intensity_cap"] = "RPE 6-7"
            base["remove_exercises"].append("med_ball")
            base["plyocare_allowed"] = False
            base["throwing_adjustments"] = {
                "max_day_type": "hybrid_b",
                "skip_phases": ["compression", "pulldowns"],
                "intensity_cap_pct": 70,
                "volume_modifier": 0.7,
                "override_to": None,
            }
    elif flag_level == "modified_green":
        base["lifting_intensity_cap"] = "RPE 7-8"
        base["throwing_adjustments"] = {
            "max_day_type": "hybrid_a",
            "skip_phases": ["pulldowns"],
            "intensity_cap_pct": 85,
            "volume_modifier": 0.85,
            "override_to": None,
        }
    else:
        # Green
        if 0 <= days_to_start <= 2:
            # Start proximity primer
            base["lifting_intensity_cap"] = "RPE 5-6"
            base["remove_exercises"].extend(["med_ball", "heavy_compounds"])
            base["arm_care_template"] = "light"
            base["plyocare_allowed"] = False
            base["throwing_adjustments"] = {
                "max_day_type": "recovery_short_box",
                "skip_phases": ["compression", "long_toss_extension"],
                "intensity_cap_pct": 70,
                "volume_modifier": 0.6,
                "override_to": None,
            }
        elif days_since_outing in [2, 3, 4]:
            base["arm_care_template"] = "heavy"
        else:
            base["arm_care_template"] = "light"

    return base


# ---------------------------------------------------------------------------
# Main triage function
# ---------------------------------------------------------------------------


def triage(
    arm_feel: int,
    sleep_hours: float,
    pitcher_profile: dict,
    energy: int = None,
    whoop_recovery: float = None,
    whoop_hrv: float = None,
    whoop_hrv_7day_avg: float = None,
    whoop_sleep_perf: int = None,
    forearm_tightness: str = None,
    ucl_sensation: bool = False,
    pitch_count: int = None,
    # Phase 1 additions (all optional for backward compat)
    recent_arm_feel: list = None,
    recent_history: list = None,
    pitcher_baseline: dict = None,
    whoop_strain_yesterday: float = None,
    arm_clarification: str = None,
    reliever_appearances_this_week: int = None,
) -> dict:
    """Run weighted triage on a pitcher's data.

    Phase 1: Three-category scoring (tissue/load/recovery) with interaction
    rules, recovery curves, trajectory analysis, and dynamic baselines.

    When called without Phase 1 arguments, produces backward-compatible output.
    """
    active_flags = pitcher_profile.get("active_flags", {})
    injury_history = pitcher_profile.get("injury_history", [])
    days_since_outing = active_flags.get("days_since_outing", 99)
    rotation_length = pitcher_profile.get("rotation_length", 7)
    injury_areas = [i.get("area", "") for i in injury_history]
    role = pitcher_profile.get("role", "starter")
    grip_drop = active_flags.get("grip_drop_reported", False)
    days_to_start = rotation_length - days_since_outing

    # Determine baseline tier and tolerance band
    baseline = pitcher_baseline or {}
    tier = baseline.get("tier", 1)
    from bot.services.baselines import get_tolerance_band
    tolerance_band = get_tolerance_band(tier)

    # If no Phase 1 args, trajectory signals are null
    has_trajectory = recent_arm_feel is not None and len(recent_arm_feel or []) >= 3

    # ── Recovery Curve Evaluation ──
    recovery_curve_result = None
    if recent_arm_feel is not None and days_since_outing < 99:
        recovery_curve_result = _evaluate_recovery_curve(
            arm_feel=arm_feel,
            rotation_day=days_since_outing,
            recent_arm_feel=recent_arm_feel,
            role=role,
            pitch_count=active_flags.get("last_outing_pitches"),
            baseline=baseline if tier >= 3 else None,
        )

    # ── Category Scores ──
    tissue_result = _compute_tissue_score(
        arm_feel=arm_feel,
        forearm_tightness=forearm_tightness,
        ucl_sensation=ucl_sensation,
        injury_areas=injury_areas,
        grip_drop=grip_drop,
        arm_clarification=arm_clarification,
        rotation_day=days_since_outing if days_since_outing < 99 else None,
        recent_arm_feel=recent_arm_feel if has_trajectory else None,
        baseline=baseline if tier >= 2 else None,
        recovery_curve_result=recovery_curve_result,
    )

    load_result = _compute_load_score(
        pitch_count=pitch_count,
        days_since_outing=days_since_outing if days_since_outing < 99 else None,
        days_to_start=days_to_start if 0 <= days_to_start <= 2 else None,
        whoop_strain_yesterday=whoop_strain_yesterday,
        reliever_appearances_this_week=reliever_appearances_this_week,
    )

    recovery_result = _compute_recovery_score(
        sleep_hours=sleep_hours,
        energy=energy,
        whoop_recovery=whoop_recovery,
        whoop_hrv=whoop_hrv,
        whoop_hrv_7day_avg=whoop_hrv_7day_avg,
        whoop_sleep_perf=whoop_sleep_perf,
    )

    tissue = tissue_result["score"]
    load = load_result["score"]
    recovery = recovery_result["score"]

    # ── Interaction Rules ──
    flag_level = _apply_interaction_rules(
        tissue=tissue,
        load=load,
        recovery=recovery,
        chronic_drift=baseline.get("drift_flagged", False),
        recovery_stall=(recovery_curve_result or {}).get("stall_detected", False),
        pace_below_floor=(recovery_curve_result or {}).get("pace_below_floor", False),
        tolerance_band=tolerance_band,
    )

    # ── Build modifications ──
    modifications = _build_modifications(
        flag_level, tissue_result, load_result, recovery_result,
        injury_areas, forearm_tightness, active_flags, injury_history,
        days_since_outing, days_to_start,
    )

    # ── Build alerts ──
    alerts = _build_alerts(
        flag_level, tissue, arm_feel, active_flags, recovery_curve_result
    )

    # ── Protocol adjustments ──
    protocol_adjustments = _build_protocol_adjustments(
        flag_level, tissue, load, pitcher_profile
    )

    # ── Build reasoning ──
    all_reasons = tissue_result["reasons"] + load_result["reasons"] + recovery_result["reasons"]
    if flag_level == "red":
        reasoning = f"RED: tissue={tissue:.0f}, load={load:.0f}, recovery={recovery:.0f}. {'; '.join(all_reasons[:5])}"
    elif flag_level == "yellow":
        reasoning = f"Yellow: tissue={tissue:.0f}, load={load:.0f}, recovery={recovery:.0f}. {'; '.join(all_reasons[:4])}"
    elif flag_level == "modified_green":
        reasoning = f"Modified green: {'; '.join(all_reasons[:3])}. Full protocol with awareness."
    else:
        reasoning = f"All systems green. Arm feel {arm_feel}/10, sleep {sleep_hours}h. Full protocol."
        if 0 <= days_to_start <= 2:
            reasoning = f"Start in {days_to_start} day(s). Primer protocol to stay fresh."

    # ── Build result ──
    result = {
        "flag_level": flag_level,
        "modifications": modifications,
        "alerts": alerts,
        "protocol_adjustments": protocol_adjustments,
        "reasoning": reasoning,
        # Phase 1 additive fields
        "category_scores": {
            "tissue": round(tissue, 1),
            "load": round(load, 1),
            "recovery": round(recovery, 1),
        },
        "trajectory_context": {
            "recovery_curve_status": recovery_curve_result if recovery_curve_result else None,
            "chronic_drift": baseline.get("drift_flagged", False),
            "trend_flags": {
                "rate_of_change": any("rapid drop" in r for r in tissue_result["reasons"]),
                "persistence": any("consecutive days" in r for r in tissue_result["reasons"]),
                "negative_slope": any("slope" in r for r in tissue_result["reasons"]),
            } if has_trajectory else None,
        },
        "baseline_tier": tier,
    }

    return result


# ---------------------------------------------------------------------------
# Modification + alert builders
# ---------------------------------------------------------------------------


def _build_modifications(
    flag_level, tissue_result, load_result, recovery_result,
    injury_areas, forearm_tightness, active_flags, injury_history,
    days_since_outing, days_to_start,
) -> list:
    """Build the modifications list from scores and flag_level."""
    modifications = []
    tightness = (forearm_tightness or "").lower()

    if flag_level == "red":
        modifications.extend(["no_lifting", "no_throwing"])
        if tissue_result["score"] >= 4:
            modifications.append("rpe_cap_56")
            modifications.append("no_high_intent_throw")
    elif flag_level == "yellow":
        if tissue_result["score"] >= 3:
            modifications.append("rpe_cap_56")
            modifications.append("no_high_intent_throw")
        else:
            modifications.append("rpe_cap_67")
            modifications.append("maintain_compounds_reduced")
            modifications.append("cap_hybrid_b")

    if tightness in ("mild", "moderate"):
        if "medial_elbow" in injury_areas or "forearm" in injury_areas:
            modifications.append("fpm_volume")

    if flag_level == "modified_green":
        modifications.append("modified_green")

    if flag_level == "green" and 0 <= days_to_start <= 2:
        modifications.append("primer_session")
        modifications.append("low_volume_activation")

    # Carry forward ongoing modifications
    active_mods = active_flags.get("active_modifications", [])
    if "elevated_fpm_volume" in active_mods:
        modifications.append("elevated_fpm_history")

    for injury in injury_history:
        if injury.get("flag_level") == "yellow":
            ongoing = injury.get("ongoing_considerations", "")
            if ongoing:
                modifications.append(f"Ongoing: {ongoing}")

    return modifications


def _build_alerts(flag_level, tissue_score, arm_feel, active_flags, recovery_curve_result) -> list:
    """Build alerts list."""
    alerts = []

    if flag_level == "red":
        alerts.append("Recommend trainer evaluation.")
        if tissue_score >= 7:
            alerts.append(f"Tissue score critically high ({tissue_score:.0f}/10).")
        prev_feel = active_flags.get("current_arm_feel")
        if prev_feel is not None and prev_feel <= 4 and arm_feel <= 4:
            alerts.append("URGENT: 2+ days with arm feel <= 4. Strongly recommend in-person trainer evaluation.")

    if recovery_curve_result:
        for reason in recovery_curve_result.get("reasons", []):
            if "late-rotation" in reason.lower():
                alerts.append(reason)

    return alerts
```

- [ ] **Step 4: Run golden snapshot tests to verify backward compat**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_triage_phase1.py::TestGoldenSnapshots -v
```

Expected: All 14 golden snapshot tests PASS. If any fail, adjust the new triage logic until they match. Key areas likely to need tuning: the threshold mapping from old yellow-trigger counting to new category scoring.

- [ ] **Step 5: Run all new category scoring tests**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/test_triage_phase1.py -v
```

Expected: All tests PASS (golden snapshots + tissue + load + recovery + interaction rules).

- [ ] **Step 6: Run ALL tests to verify nothing else broke**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add bot/services/triage.py tests/test_triage_phase1.py
git commit -m "feat: rewrite triage with 3-category scoring, interaction rules, and recovery curves

Replaces flat yellow-trigger counting with tissue/load/recovery category
scoring and interaction rules. Recovery curve evaluation (stall, pace,
late-rotation readiness, cross-week slope). Absorbed Sprint 1a trend
signals (rate-of-change, persistence, slope).

Backward compatible: no-new-args call produces identical output (golden
snapshot tested)."
```

---

## Task 7: Wire Into checkin_service.py

**Files:**
- Modify: `bot/services/checkin_service.py` (lines 50-55, 88-142, 172-173)
- Modify: `bot/services/db.py` (lines 79-89)

- [ ] **Step 1: Add baseline_snapshot to db.py training model functions**

In `bot/services/db.py`, the `get_training_model` and `upsert_training_model` functions already work with the full row (`select("*")`), so `baseline_snapshot` will be included automatically after the DB migration. No code changes needed in db.py for basic read/write.

Add a convenience function. After line 89 in `bot/services/db.py`, add:

```python
def update_baseline_snapshot(pitcher_id: str, snapshot: dict) -> None:
    """Update just the baseline_snapshot JSONB field."""
    get_client().table("pitcher_training_model").update(
        {"baseline_snapshot": snapshot}
    ).eq("pitcher_id", pitcher_id).execute()
```

- [ ] **Step 2: Run Supabase migration for baseline_snapshot column**

**IMPORTANT: This migration MUST be applied before deploying any code that reads/writes baseline_snapshot.**

Using the Supabase MCP tool or SQL editor:

```sql
ALTER TABLE pitcher_training_model
ADD COLUMN IF NOT EXISTS baseline_snapshot JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pitcher_training_model.baseline_snapshot IS
'Cached per-pitcher baseline for trajectory-aware triage (Phase 1). Recomputed every 24h or on new outing.';
```

Verify: `SELECT column_name FROM information_schema.columns WHERE table_name = 'pitcher_training_model' AND column_name = 'baseline_snapshot';` should return 1 row.

- [ ] **Step 3: Build recent history assembler in checkin_service**

In `bot/services/checkin_service.py`, add a new helper function after `_build_recent_history_context` (after line 85):

```python
def _assemble_recent_arm_feel(pitcher_id: str, n: int = 7) -> list:
    """Assemble recent arm_feel entries for triage trajectory analysis.

    Returns list sorted newest-first:
    [{"date": "2026-04-17", "arm_feel": 7, "rotation_day": 3}, ...]
    """
    from bot.services.db import get_daily_entries

    entries = get_daily_entries(pitcher_id, limit=n)  # newest-first from DB
    result = []
    for e in entries:
        pt = e.get("pre_training") or {}
        af = pt.get("arm_feel")
        if af is not None:
            result.append({
                "date": e.get("date", ""),
                "arm_feel": af,
                "rotation_day": e.get("rotation_day", 0),
            })
    return result


def _get_reliever_appearances_this_week(pitcher_id: str) -> int:
    """Count reliever game appearances in the last 7 days.

    Uses daily_entries outing records + team_games starter assignments
    to detect appearances. game_scraper data is the primary source
    per design spec.
    """
    from datetime import timedelta
    from bot.config import CHICAGO_TZ
    from bot.services.db import get_daily_entries

    today = datetime.now(CHICAGO_TZ).date()
    week_ago = (today - timedelta(days=7)).isoformat()

    # Count from daily_entries where an outing was logged in last 7 days
    entries = get_daily_entries(pitcher_id, limit=10)
    count = 0
    for e in entries:
        entry_date = e.get("date", "")
        if entry_date < week_ago:
            break
        # Check for logged outing (from /outing flow or game_scraper)
        if e.get("outing"):
            count += 1
        # Also check throwing type = game
        throwing = e.get("throwing") or {}
        if throwing.get("type") in ("game", "appearance"):
            count += 1
    return count
```

- [ ] **Step 4: Modify process_checkin to pass new args to triage**

Replace lines 120-142 of `checkin_service.py` (the triage call + arm_clarification override) with:

```python
    # Phase 1: Assemble trajectory data for triage
    recent_arm_feel = _assemble_recent_arm_feel(pitcher_id, n=7)
    recent_entries_for_triage = get_recent_entries(pitcher_id, n=14)

    # Phase 1: Get or refresh baseline
    from bot.services.baselines import get_or_refresh_baseline
    from bot.services.db import get_training_model as _get_tm, update_baseline_snapshot

    model_for_baseline = _get_tm(pitcher_id)
    cached_baseline = model_for_baseline.get("baseline_snapshot") or None
    last_outing_date = (model_for_baseline.get("last_outing_date") or
                        (profile.get("active_flags") or {}).get("last_outing_date"))

    # Fetch full history for baseline computation (only runs if cache is stale)
    from bot.services.db import get_daily_entries as _get_entries
    full_history = _get_entries(pitcher_id, limit=60)  # ~56 days

    pitcher_baseline = get_or_refresh_baseline(
        pitcher_id=pitcher_id,
        cached_snapshot=cached_baseline,
        daily_entries=full_history,
        rotation_length=rotation_length,
        last_outing_date=last_outing_date,
    )

    # Persist refreshed baseline if recomputed
    if pitcher_baseline.pop("_recomputed", False):
        try:
            update_baseline_snapshot(pitcher_id, pitcher_baseline)
        except Exception as e:
            logger.warning("Failed to persist baseline for %s: %s", pitcher_id, e)

    # Reliever appearance count for load scoring
    reliever_appearances = None
    if "reliever" in (profile.get("role") or "").lower():
        try:
            reliever_appearances = _get_reliever_appearances_this_week(pitcher_id)
        except Exception as e:
            logger.warning("Failed to get reliever appearances for %s: %s", pitcher_id, e)

    triage_result = triage(
        arm_feel=arm_feel,
        sleep_hours=sleep_hours,
        pitcher_profile=profile,
        energy=energy,
        whoop_recovery=whoop_data.get("recovery_score") if whoop_data else None,
        whoop_hrv=whoop_data.get("hrv_rmssd") if whoop_data else None,
        whoop_hrv_7day_avg=whoop_data.get("hrv_7day_avg") if whoop_data else None,
        whoop_sleep_perf=whoop_data.get("sleep_performance") if whoop_data else None,
        forearm_tightness=None,  # populated by checkin flow when available
        ucl_sensation=False,     # populated by checkin flow when available
        pitch_count=None,        # populated by outing flow
        # Phase 1 additions
        recent_arm_feel=recent_arm_feel if recent_arm_feel else None,
        recent_history=recent_entries_for_triage if recent_entries_for_triage else None,
        pitcher_baseline=pitcher_baseline,
        whoop_strain_yesterday=whoop_data.get("yesterday_strain") if whoop_data else None,
        arm_clarification=arm_clarification or None,
        reliever_appearances_this_week=reliever_appearances,
    )

    # arm_clarification is now handled INSIDE triage — no post-hoc override needed
    # DELETE the old override block (previously at lines 131-142):
    #   if arm_clarification == "expected_soreness" and arm_feel is not None and arm_feel <= 4:
    #       if triage_result["flag_level"] == "red":
    #           triage_result["flag_level"] = "yellow"
    #           ...
    #   elif arm_clarification == "concerned":
    #       if triage_result["flag_level"] == "green":
    #           ...
    # This entire block is replaced by arm_clarification handling in _compute_tissue_score().
    # VERIFY: grep checkin_service.py for "expected_soreness" — should only appear in
    # the checkin_inputs dict assembly, NOT in any flag-level override logic.
```

- [ ] **Step 5: Add category_scores to daily_entries pre_training JSONB**

In `checkin_service.py`, update the `partial_entry` and `entry` blocks to include category_scores. In the partial_entry block (around line 179), update `pre_training`:

```python
    partial_entry = {
        "date": today_str,
        "rotation_day": rotation_day,
        "pre_training": {
            "arm_feel": arm_feel,
            "overall_energy": energy,
            "sleep_hours": sleep_hours,
            "flag_level": triage_result["flag_level"],
            "category_scores": triage_result.get("category_scores"),
            "baseline_tier": triage_result.get("baseline_tier"),
        },
        # ... rest unchanged
    }
```

Apply the same `category_scores` and `baseline_tier` addition to the `entry` dict (around line 239).

- [ ] **Step 6: Verify the full pipeline runs**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add bot/services/checkin_service.py bot/services/db.py
git commit -m "feat: wire Phase 1 triage into checkin_service

Assembles recent_arm_feel and recent_history from daily_entries.
Fetches/refreshes pitcher baseline (24h TTL + outing invalidation).
Passes all new args to triage. Removes arm_clarification post-hoc
override — triage now owns all flag decisions.
Logs category_scores and baseline_tier in pre_training JSONB."
```

---

## Task 8: Observability + Final Verification

**Files:**
- Modify: `bot/services/triage.py` (add logging)

- [ ] **Step 1: Add structured logging to triage**

At the end of the `triage()` function, before `return result`, add:

```python
    # Structured logging for observability
    logger.info(
        "Triage result: pitcher=%s flag=%s tissue=%.1f load=%.1f recovery=%.1f "
        "tier=%d drift=%s stall=%s",
        pitcher_profile.get("pitcher_id", "?"),
        flag_level,
        tissue,
        load,
        recovery,
        tier,
        baseline.get("drift_flagged", False),
        (recovery_curve_result or {}).get("stall_detected", False),
    )
```

- [ ] **Step 2: Run full test suite one final time**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1/pitcher_program_app
python -m pytest tests/ -v
```

Expected: ALL tests PASS.

- [ ] **Step 3: Commit**

```bash
git add bot/services/triage.py
git commit -m "feat: add structured observability logging to Phase 1 triage"
```

- [ ] **Step 4: Review the full diff**

```bash
cd /Users/landonbrice/Desktop/Baseball-phase1
git log --oneline main..phase1-trajectory-triage
git diff main..phase1-trajectory-triage --stat
```

Verify: 7 commits, touching expected files only.

---

## Summary of Commits

| # | Message | Files |
|---|---------|-------|
| 1 | `feat: add population baselines YAML for Phase 1 triage` | `data/constraint_defaults/population_baselines.yaml` |
| 2 | `feat: add recovery curve lookup in baselines module` | `bot/services/baselines.py`, `tests/test_baselines.py` |
| 3 | `feat: add baseline computation with tier classification and chronic drift` | `bot/services/baselines.py`, `tests/test_baselines.py` |
| 4 | `feat: add cache-aware baseline refresh with TTL and outing invalidation` | `bot/services/baselines.py`, `tests/test_baselines.py` |
| 5 | `test: add golden snapshot tests for current triage behavior` | `tests/test_triage_phase1.py` |
| 6 | `feat: rewrite triage with 3-category scoring, interaction rules, recovery curves` | `bot/services/triage.py`, `tests/test_triage_phase1.py` |
| 7 | `feat: wire Phase 1 triage into checkin_service` | `bot/services/checkin_service.py`, `bot/services/db.py` |
| 8 | `feat: add structured observability logging to Phase 1 triage` | `bot/services/triage.py` |

---

## Verification Checklist (run before merging)

- [ ] All tests pass: `python -m pytest tests/ -v`
- [ ] Golden snapshots still pass (backward compat)
- [ ] No import errors: `python -c "from bot.services.triage import triage; from bot.services.baselines import compute_pitcher_baseline; print('OK')"`
- [ ] YAML loads: `python -c "import yaml; yaml.safe_load(open('data/constraint_defaults/population_baselines.yaml')); print('OK')"`
- [ ] Supabase migration applied: `baseline_snapshot` column exists on `pitcher_training_model`
- [ ] Test with dev bot: check in as landon_brice, verify flag_level, check category_scores in daily_entry
