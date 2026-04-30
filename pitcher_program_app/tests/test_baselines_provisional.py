from bot.services.baselines import compute_pitcher_baseline


def _entry(date, arm_feel, rd=0):
    return {"date": date, "pre_training": {"arm_feel": arm_feel}, "rotation_day": rd}


def test_zero_checkins_state_is_no_baseline():
    b = compute_pitcher_baseline([])
    assert b["baseline_state"] == "no_baseline"
    assert b["total_check_ins"] == 0


def test_four_checkins_state_is_no_baseline():
    entries = [_entry(f"2026-04-{10+i:02d}", 7) for i in range(4)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "no_baseline"
    assert b["total_check_ins"] == 4


def test_five_checkins_state_is_provisional():
    entries = [_entry(f"2026-04-{10+i:02d}", 7) for i in range(5)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "provisional"


def test_thirteen_checkins_state_is_provisional():
    entries = [_entry(f"2026-04-{i:02d}", 7) for i in range(1, 14)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "provisional"


def test_fourteen_checkins_state_is_full():
    entries = [_entry(f"2026-04-{i:02d}", 7) for i in range(1, 15)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "full"


def test_provisional_blends_population_and_observed_70_30():
    # Pitcher observed mean = 6.0 (low), population default = 7.5
    # At check-ins 5-13: blended = 0.7*7.5 + 0.3*6.0 = 5.25 + 1.8 = 7.05
    entries = [_entry(f"2026-04-{10+i:02d}", 6) for i in range(7)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "provisional"
    assert b["overall_mean"] == 7.05  # blended
    assert b["observed_mean"] == 6.0  # raw observed exposed separately


def test_full_baseline_uses_observed_only():
    entries = [_entry(f"2026-04-{i:02d}", 6) for i in range(1, 15)]
    b = compute_pitcher_baseline(entries)
    assert b["baseline_state"] == "full"
    assert b["overall_mean"] == 6.0
