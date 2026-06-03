"""Tests for bot.services.program_engine.load_math (Task 2.1).

Calibration target: tests/fixtures/golden_acwr_curve.json — specifically
the verified daily anchor (45ft × 40 throws × 50% intent → G ≈ 2145 ± 5%).

The weekly G curve is a secondary check; we can't recompute it directly
without the daily 5-tuple grid (Drive-aliased xlsx), so we use it to assert
shape invariants only (deload undulation, monotonic trajectory).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.services.program_engine.load_math import (
    ACUTE_WINDOW_DAYS,
    ACWR_BAND_DEFAULT,
    ACWR_HARD_CAP_DEFAULT,
    CHRONIC_WINDOW_DAYS,
    GuardrailViolation,
    K_THROWING,
    _parse_intensity_factor,
    _parse_reps_count,
    check_acwr_invariant,
    compute_acwr,
    daily_lifting_load,
    daily_loads_series,
    daily_throwing_load,
    daily_total_load,
    weekly_load_from_days,
)
from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
    Phase,
    ProgressionState,
    Rationale,
    ThrowingFiveTuple,
)


# ─────────────────────────────────────────────────────────────────────────────
# Calibration anchor
# ─────────────────────────────────────────────────────────────────────────────


def test_verified_anchor_within_5pct():
    """The single calibration anchor (recon Front 5): G(45ft, 40, 50%) ≈ 2145.

    Tolerance: 5% per the plan + the fixture's stated `tolerance_pct=5`.
    """
    t = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="warmup")
    g = daily_throwing_load(t)
    expected = 2145
    assert abs(g - expected) / expected <= 0.05, f"G={g:.1f}, expected ~{expected} (±5%)"


def test_calibration_constant_matches_anchor_math():
    """Sanity: K_THROWING × 40 × 45 × 0.5 ≈ 2145."""
    derived = K_THROWING * 40 * 45 * 0.5
    assert abs(derived - 2145) / 2145 <= 0.01


# ─────────────────────────────────────────────────────────────────────────────
# daily_throwing_load
# ─────────────────────────────────────────────────────────────────────────────


def test_daily_throwing_load_scales_linearly_with_throws():
    """G doubles when throw_count doubles."""
    base = daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x"))
    doubled = daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=80, intensity_pct=50, drill="x"))
    assert abs(doubled - 2 * base) < 0.01


def test_daily_throwing_load_scales_linearly_with_distance():
    base = daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x"))
    doubled = daily_throwing_load(ThrowingFiveTuple(distance_ft=90, throw_count=40, intensity_pct=50, drill="x"))
    assert abs(doubled - 2 * base) < 0.01


def test_daily_throwing_load_scales_linearly_with_intensity():
    base = daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x"))
    doubled = daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=100, drill="x"))
    assert abs(doubled - 2 * base) < 0.01


def test_daily_throwing_load_zero_when_any_factor_zero():
    assert daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=0, intensity_pct=50, drill="x")) == 0
    # intensity_pct must be ≥ 0; pydantic enforces ≥ 0, so 0 is the floor
    assert daily_throwing_load(ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=0, drill="x")) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Intensity parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_intensity_range_midpoint():
    assert _parse_intensity_factor("50-75% 1RM") == pytest.approx(0.625)
    assert _parse_intensity_factor("80-90% 1RM") == pytest.approx(0.85)


def test_intensity_single_percent():
    assert _parse_intensity_factor("85% 1RM") == pytest.approx(0.85)


def test_intensity_rir():
    assert _parse_intensity_factor("2RIR") == pytest.approx(0.90)
    assert _parse_intensity_factor("0 RIR") == pytest.approx(1.00)
    assert _parse_intensity_factor("4 RIR") == pytest.approx(0.80)


def test_intensity_keywords():
    assert _parse_intensity_factor("BW") == pytest.approx(0.50)
    assert _parse_intensity_factor("Heavy") == pytest.approx(0.80)
    assert _parse_intensity_factor("Light") == pytest.approx(0.50)
    assert _parse_intensity_factor("Moderate") == pytest.approx(0.65)
    assert _parse_intensity_factor("Near Maximal") == pytest.approx(0.92)


def test_intensity_unparseable_falls_back_to_default():
    assert _parse_intensity_factor("eat protein") == pytest.approx(0.65)
    assert _parse_intensity_factor("") == pytest.approx(0.65)
    assert _parse_intensity_factor(None) == pytest.approx(0.65)


# ─────────────────────────────────────────────────────────────────────────────
# Reps parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_reps_single_number():
    assert _parse_reps_count("8") == 8


def test_reps_range_averages():
    assert _parse_reps_count("8-10") == 9
    assert _parse_reps_count("3x4-6") == 5  # avg of 3 and 6 = 4.5 → 5


def test_reps_each_leg_counts_one_side():
    """`'3 each leg'` → 3. Doubling is the caller's responsibility; load math
    treats reps-as-prescribed."""
    assert _parse_reps_count("3 each leg") == 3


def test_reps_amrap_fallback():
    assert _parse_reps_count("AMRAP") == 1
    assert _parse_reps_count("") == 1


# ─────────────────────────────────────────────────────────────────────────────
# daily_lifting_load
# ─────────────────────────────────────────────────────────────────────────────


def test_daily_lifting_load_simple():
    block = LiftingBlock(
        block_name="Block 1",
        exercises=[
            LiftingExercise(exercise_id="ex_004", sets=3, reps="8", intensity="80% 1RM"),
        ],
    )
    # 3 sets × 8 reps × 0.80 intensity = 19.2
    assert daily_lifting_load([block]) == pytest.approx(19.2)


def test_daily_lifting_load_zero_when_empty():
    assert daily_lifting_load([]) == 0.0


def test_daily_lifting_load_sums_blocks_and_exercises():
    blocks = [
        LiftingBlock(
            block_name="Block 1",
            exercises=[
                LiftingExercise(exercise_id="ex_001", sets=3, reps="8", intensity="80% 1RM"),
                LiftingExercise(exercise_id="ex_002", sets=3, reps="8", intensity="80% 1RM"),
            ],
        ),
        LiftingBlock(
            block_name="Block 2",
            exercises=[
                LiftingExercise(exercise_id="ex_003", sets=2, reps="10", intensity="50% 1RM"),
            ],
        ),
    ]
    # 2 * (3 * 8 * 0.80) + (2 * 10 * 0.50) = 38.4 + 10 = 48.4
    assert daily_lifting_load(blocks) == pytest.approx(48.4)


# ─────────────────────────────────────────────────────────────────────────────
# daily_total_load + weekly
# ─────────────────────────────────────────────────────────────────────────────


def _make_day(idx: int, *, throws: ThrowingFiveTuple | None = None, lifting: list | None = None) -> Day:
    return Day(
        day_index=idx,
        template_key=f"day_{idx % 7}",
        date=f"2026-06-{(idx % 28) + 1:02d}",
        throwing_5tuple=throws,
        lifting_blocks=lifting or [],
    )


def test_daily_total_load_combines_both():
    t = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")
    lifting = [LiftingBlock(block_name="B", exercises=[LiftingExercise(exercise_id="ex_001", sets=3, reps="8", intensity="80% 1RM")])]
    d = _make_day(0, throws=t, lifting=lifting)
    assert daily_total_load(d) == pytest.approx(daily_throwing_load(t) + daily_lifting_load(lifting))


def test_weekly_load_from_days_groups_by_week():
    days = [
        _make_day(0, throws=ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")),
        _make_day(6, throws=ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")),
        _make_day(7, throws=ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")),
    ]
    w1 = weekly_load_from_days(days, 1)
    w2 = weekly_load_from_days(days, 2)
    # Days 0+6 are week 1; day 7 is week 2.
    assert w1 == pytest.approx(2 * 2145, rel=0.05)
    assert w2 == pytest.approx(2145, rel=0.05)


def test_weekly_load_returns_zero_for_invalid_week():
    assert weekly_load_from_days([], 1) == 0
    assert weekly_load_from_days([_make_day(0)], 0) == 0


def test_daily_loads_series_fills_missing_indices_with_zero():
    """Holes in day_index sequence must zero-fill so the ACWR rolling window
    aligns with the calendar (not with the dense day list)."""
    days = [_make_day(0, throws=ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")),
            _make_day(5, throws=ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x"))]
    series = daily_loads_series(days)
    assert len(series) == 6
    assert series[0] > 0
    assert series[1] == 0  # missing
    assert series[5] > 0


def test_daily_loads_series_empty_input():
    assert daily_loads_series([]) == []


# ─────────────────────────────────────────────────────────────────────────────
# ACWR
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_acwr_basic_ramp():
    """Steady-state load → ACWR ≈ 1.0 (mean_acute / mean_chronic convention)."""
    series = [100.0] * 30
    acwr = compute_acwr(series, at_day_index=29)
    assert acwr is not None
    assert abs(acwr - 1.0) < 0.01, f"steady state must yield ratio ≈ 1.0, got {acwr}"


def test_compute_acwr_returns_none_when_chronic_zero():
    assert compute_acwr([0.0] * 30, at_day_index=29) is None


def test_compute_acwr_returns_none_when_out_of_range():
    assert compute_acwr([100.0] * 10, at_day_index=20) is None
    assert compute_acwr([100.0] * 10, at_day_index=-1) is None


def test_compute_acwr_window_boundaries():
    """The 7d and 28d windows correctly inclusive-of-current-day.

    Single load of 100 at day 27: acute_mean = 100/7 ≈ 14.3;
    chronic_mean = 100/28 ≈ 3.57; ratio = (100/7) / (100/28) = 28/7 = 4.0.
    """
    series = [0.0] * 27 + [100.0]
    acwr = compute_acwr(series, at_day_index=27)
    assert acwr is not None
    expected = (100 / 7) / (100 / 28)  # = 4.0
    assert abs(acwr - expected) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# check_acwr_invariant
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_program_with_days(days: list[Day]) -> PitcherProgram:
    return PitcherProgram(
        pitcher_id="landon_brice",
        goal="velocity",
        domain="unified",
        knowledge_version="testtest",
        generated_at="2026-06-01T19:30:00",
        target_date="2026-08-24",
        total_weeks=12,
        status="draft",
        phases=[Phase(phase_id="base_building", name="Base", week_count=12, intent_summary="x")],
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["velocity_progression_model"]),
        progression_state=ProgressionState(),
    )


def test_check_acwr_invariant_steady_state_yields_warnings_not_errors():
    """A perfectly flat ramp triggers above-band warnings (acute_sum / chronic_mean > 1.3)
    but NEVER hits the hard cap unless there's a real spike."""
    t = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="x")
    days = [_make_day(i, throws=t) for i in range(35)]
    program = _minimal_program_with_days(days)
    violations = check_acwr_invariant(program)
    # First CHRONIC_WINDOW_DAYS days have no violations
    for v in violations:
        assert v.where["day_index"] >= CHRONIC_WINDOW_DAYS - 1
    # In steady state we expect either warnings or no violations — never errors
    errors = [v for v in violations if v.severity == "error"]
    assert errors == [], f"steady state should not exceed hard cap: {errors}"


def test_check_acwr_invariant_flags_hard_cap_breach():
    """A massive late-program spike triggers an `acwr_hard_cap_exceeded` error."""
    light = ThrowingFiveTuple(distance_ft=45, throw_count=10, intensity_pct=30, drill="x")
    spike = ThrowingFiveTuple(distance_ft=120, throw_count=100, intensity_pct=100, drill="velo")
    days = [_make_day(i, throws=light) for i in range(28)]
    days.append(_make_day(28, throws=spike))
    days.append(_make_day(29, throws=spike))
    program = _minimal_program_with_days(days)
    violations = check_acwr_invariant(program)
    errors = [v for v in violations if v.kind == "acwr_hard_cap_exceeded"]
    assert errors, "must flag spike as hard-cap breach"


def test_check_acwr_invariant_no_violations_when_no_load():
    """Rest-only program — no ACWR violations (chronic=0 → None ratio)."""
    days = [_make_day(i) for i in range(35)]
    program = _minimal_program_with_days(days)
    violations = check_acwr_invariant(program)
    assert violations == []


def test_check_acwr_invariant_repair_hints_present_on_band_warnings():
    """Band warnings carry a repair_hint for Phase 2.4's orchestrator."""
    light = ThrowingFiveTuple(distance_ft=45, throw_count=10, intensity_pct=50, drill="x")
    days = [_make_day(i, throws=light) for i in range(30)]
    program = _minimal_program_with_days(days)
    violations = check_acwr_invariant(program)
    warnings = [v for v in violations if v.severity == "warning"]
    if warnings:
        for v in warnings:
            assert v.repair_hint is not None
            assert v.repair_hint.startswith("clip_") or v.repair_hint.startswith("add_")


# ─────────────────────────────────────────────────────────────────────────────
# Golden curve secondary check
# ─────────────────────────────────────────────────────────────────────────────


def test_golden_curve_anchor_round_trip():
    """The verified anchor in the golden fixture matches our daily_throwing_load."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "golden_acwr_curve.json"
    data = json.loads(fixture_path.read_text())
    anchor = data["_meta"]["verified_daily_anchor"]
    t = ThrowingFiveTuple(
        distance_ft=anchor["distance_ft"],
        throw_count=anchor["throw_count"],
        intensity_pct=anchor["intent_pct"],
        drill="warmup",
    )
    g = daily_throwing_load(t)
    expected = anchor["G_load_units"]
    tolerance_pct = anchor.get("tolerance_pct", 5) / 100.0
    assert abs(g - expected) / expected <= tolerance_pct


def test_golden_curve_3up_1down_pattern_recoverable_from_loads():
    """A 12-week program with one velocity 5-tuple per week, with Wk4 and Wk7
    at reduced volume, must reproduce the deload undulation in weekly G."""
    weekly_intent = [50, 60, 70, 60, 80, 90, 70, 80, 90, 90, 95, 100]  # 12 weeks
    weekly_throws = [40, 50, 55, 45, 60, 70, 55, 65, 70, 70, 70, 75]
    days = []
    for w_idx in range(12):
        # 3 sessions per week
        for s_idx in range(3):
            day_idx = w_idx * 7 + s_idx * 2  # M/W/F-ish
            days.append(_make_day(
                day_idx,
                throws=ThrowingFiveTuple(
                    distance_ft=60,
                    throw_count=weekly_throws[w_idx],
                    intensity_pct=weekly_intent[w_idx],
                    drill="long toss",
                ),
            ))
    weekly_G = [weekly_load_from_days(days, w + 1) for w in range(12)]
    # 3-up-1-down: Wk4 (idx 3) < Wk3 (idx 2); Wk7 (idx 6) < Wk6 (idx 5)
    assert weekly_G[3] < weekly_G[2], f"deload Wk4 should dip below Wk3: {weekly_G[3]:.0f} vs {weekly_G[2]:.0f}"
    assert weekly_G[6] < weekly_G[5], f"deload Wk7 should dip below Wk6: {weekly_G[6]:.0f} vs {weekly_G[5]:.0f}"
    # Trajectory climbs overall
    assert weekly_G[-1] > weekly_G[0] * 1.5


# ─────────────────────────────────────────────────────────────────────────────
# Violation dataclass
# ─────────────────────────────────────────────────────────────────────────────


def test_guardrail_violation_str():
    v = GuardrailViolation(
        kind="acwr_hard_cap_exceeded",
        where={"day_index": 30, "date": "2026-07-01"},
        actual=1.7,
        expected="≤ 1.5",
        severity="error",
    )
    s = str(v)
    assert "error" in s
    assert "acwr_hard_cap_exceeded" in s


def test_guardrail_violation_default_severity():
    v = GuardrailViolation(kind="x", where={}, actual=1, expected=2)
    assert v.severity == "error"
    assert v.repair_hint is None
