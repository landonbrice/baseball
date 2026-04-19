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
    result = get_recovery_curve_expected(role="reliever", rotation_day=1, pitch_count=30)
    assert result == {"floor": 4, "expected": 6}

def test_reliever_heavy_day3_plus():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="reliever", rotation_day=4, pitch_count=35)
    assert result == {"floor": 7, "expected": 9}

def test_reliever_light_day1():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="reliever", rotation_day=1, pitch_count=15)
    assert result == {"floor": 6, "expected": 8}

def test_reliever_light_day2_plus():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="reliever", rotation_day=3, pitch_count=20)
    assert result == {"floor": 7, "expected": 9}

def test_reliever_extended_rest():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="reliever", rotation_day=6, pitch_count=None)
    assert result == {"floor": 7, "expected": 9}

def test_reliever_no_pitch_count_defaults_heavy():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="reliever", rotation_day=1, pitch_count=None)
    assert result == {"floor": 4, "expected": 6}

def test_starter_day_beyond_rotation():
    from bot.services.baselines import get_recovery_curve_expected
    result = get_recovery_curve_expected(role="starter", rotation_day=8)
    assert result == {"floor": 6, "expected": 9}


# ---------------------------------------------------------------------------
# Baseline computation tests
# ---------------------------------------------------------------------------

def _make_entry(date: str, arm_feel: int, rotation_day: int = 0) -> dict:
    return {"date": date, "rotation_day": rotation_day, "pre_training": {"arm_feel": arm_feel}}

def _make_entries_for_days(start_date: str, arm_feels: list, rotation_days: list = None):
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

def test_tier1_with_partial_rotation():
    from bot.services.baselines import compute_pitcher_baseline
    entries = _make_entries_for_days("2026-04-01", [7, 8, 7, 8, 9])
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 1
    assert result["total_check_ins"] == 5

def test_tier2_with_one_rotation():
    from bot.services.baselines import compute_pitcher_baseline
    rotation_days = [0, 1, 2, 3, 4, 5, 6, 0]
    entries = _make_entries_for_days("2026-04-01", [6, 6, 7, 8, 8, 9, 9, 6], rotation_days=rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 2
    assert result["rotations_completed"] >= 1

def test_tier3_with_three_rotations():
    from bot.services.baselines import compute_pitcher_baseline
    rotation_days = [i % 7 for i in range(22)]
    arm_feels = [6, 6, 7, 8, 8, 9, 9] * 3 + [6]
    entries = _make_entries_for_days("2026-03-15", arm_feels, rotation_days=rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["tier"] == 3
    assert result["rotations_completed"] >= 3

def test_rotation_day_baselines_computed():
    from bot.services.baselines import compute_pitcher_baseline
    rotation_days = [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6]
    arm_feels = [6, 6, 7, 8, 8, 9, 9, 5, 6, 7, 8, 8, 9, 9]
    entries = _make_entries_for_days("2026-04-01", arm_feels, rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["rotation_day_baselines"]["0"]["mean"] == 5.5
    assert result["rotation_day_baselines"]["0"]["n"] == 2
    assert result["rotation_day_baselines"]["6"]["mean"] == 9.0

def test_chronic_drift_not_flagged_when_stable():
    from bot.services.baselines import compute_pitcher_baseline
    arm_feels = [7, 8] * 14
    entries = _make_entries_for_days("2026-03-15", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["drift_flagged"] is False

def test_chronic_drift_flagged_when_declining():
    from bot.services.baselines import compute_pitcher_baseline
    arm_feels = [8] * 14 + [5] * 14
    entries = _make_entries_for_days("2026-03-15", arm_feels)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["drift_flagged"] is True
    assert result["chronic_drift"] > 1.0

def test_chronic_drift_requires_14_checkins():
    from bot.services.baselines import compute_pitcher_baseline
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

def test_entries_with_missing_arm_feel_excluded():
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
    from bot.services.baselines import compute_pitcher_baseline
    rotation_days = [0, 1, 2, 0, 1, 2, 3, 0, 1]
    arm_feels = [6, 7, 8, 6, 7, 8, 9, 5, 7]
    entries = _make_entries_for_days("2026-04-01", arm_feels, rotation_days)
    result = compute_pitcher_baseline(entries, rotation_length=7)
    assert result["rotations_completed"] >= 3
    assert result["tier"] == 3
