"""Tests for bot.services.program_engine.structural_invariants (Task 2.2)."""
from __future__ import annotations

import pytest

from bot.services.program_engine.load_math import GuardrailViolation
from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    Phase,
    PitcherProgram,
    ProgressionState,
    Rationale,
    ThrowingFiveTuple,
)
from bot.services.program_engine.structural_invariants import (
    DELOAD_MAX_ACCUMULATION_WEEKS,
    FPM_MIN_DAYS_PER_WEEK,
    PULL_PUSH_RATIO_MIN,
    check_deload_cadence,
    check_fpm_cadence,
    check_intent_monotonicity,
    check_phase_gates,
    check_pull_push_ratio,
)


def _make_day(idx: int, *, throws=None, lifting=None, is_deload=False, intent_pct=None, phase_name=None) -> Day:
    return Day(
        day_index=idx,
        template_key=f"day_{idx % 7}",
        date=f"2026-06-{(idx % 28) + 1:02d}",
        throwing_5tuple=throws,
        lifting_blocks=lifting or [],
        is_deload=is_deload,
        intent_pct=intent_pct,
        phase_name=phase_name,
    )


def _minimal_program(days, *, total_weeks=4, phase_week_count=2):
    phases = [Phase(phase_id="base", name="Base", week_count=phase_week_count, intent_summary="x", phase_type="base")]
    if total_weeks - phase_week_count > 0:
        phases.append(Phase(phase_id="build", name="Build", week_count=total_weeks - phase_week_count, intent_summary="x"))
    return PitcherProgram(
        pitcher_id="p", goal="velocity", domain="unified",
        knowledge_version="testtest",
        generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01", total_weeks=total_weeks, status="draft",
        phases=phases,
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )


# ─────────── Deload cadence ───────────


def test_deload_cadence_clean_program_no_violations():
    """4 accumulation weeks → deload → 4 accumulation → deload. Exactly at limit."""
    days = []
    for wk in range(8):
        is_deload = wk in (4, 7)  # deload Wk5 (after 4 accum) and Wk8
        for dow in range(7):
            days.append(_make_day(wk * 7 + dow, is_deload=is_deload))
    program = _minimal_program(days, total_weeks=8, phase_week_count=4)
    violations = check_deload_cadence(program)
    assert violations == []


def test_deload_cadence_violation_when_too_many_accum():
    """5 consecutive accumulation weeks → violation."""
    days = []
    for wk in range(6):
        for dow in range(7):
            days.append(_make_day(wk * 7 + dow, is_deload=False))
    program = _minimal_program(days, total_weeks=6, phase_week_count=3)
    violations = check_deload_cadence(program)
    assert len(violations) == 1
    v = violations[0]
    assert v.kind == "deload_cadence_missing"
    assert v.severity == "error"
    assert v.repair_hint == "demote_oldest_accumulation_week_to_deload"


def test_deload_cadence_with_more_strict_max():
    days = [_make_day(i, is_deload=False) for i in range(21)]   # 3 weeks
    program = _minimal_program(days, total_weeks=3, phase_week_count=2)
    # Strict: max 2 accumulation weeks → 3rd week violates
    violations = check_deload_cadence(program, max_accumulation_weeks=2)
    assert any(v.kind == "deload_cadence_missing" for v in violations)


# ─────────── Phase gates ───────────


def test_phase_gates_clean_when_base_phase_low_intent():
    base_t = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="warmup")
    days = [_make_day(i, throws=base_t, intent_pct=50, phase_name="Base") for i in range(14)]
    program = _minimal_program(days, total_weeks=4, phase_week_count=2)
    assert check_phase_gates(program) == []


def test_phase_gates_violation_when_high_intent_in_base():
    velo_t = ThrowingFiveTuple(distance_ft=120, throw_count=20, intensity_pct=100, drill="velo")
    days = [_make_day(i, throws=velo_t, intent_pct=100, phase_name="Base") for i in range(14)]
    program = _minimal_program(days, total_weeks=4, phase_week_count=2)
    violations = check_phase_gates(program)
    assert len(violations) == 14
    assert all(v.kind == "phase_gate_violation_high_intent_in_base" for v in violations)


def test_phase_gates_ok_outside_base():
    """High intent in week 3+ (post-base) is fine."""
    base = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="warmup")
    velo = ThrowingFiveTuple(distance_ft=120, throw_count=20, intensity_pct=100, drill="velo")
    days = [_make_day(i, throws=base, intent_pct=50, phase_name="Base") for i in range(14)]  # Base = wks 1-2
    days += [_make_day(i + 14, throws=velo, intent_pct=100, phase_name="Build") for i in range(7)]
    program = _minimal_program(days, total_weeks=3, phase_week_count=2)
    assert check_phase_gates(program) == []


# ─────────── Intent monotonicity ───────────


def test_intent_monotonicity_smooth_ramp():
    """50% → 60% → 70% → 80% (10pp jumps; under 20pp default)."""
    intents = [50, 60, 70, 80]
    days = []
    for wk_idx, intent in enumerate(intents):
        for dow in range(7):
            t = ThrowingFiveTuple(distance_ft=60, throw_count=40, intensity_pct=intent, drill="x")
            days.append(_make_day(wk_idx * 7 + dow, throws=t, intent_pct=intent))
    program = _minimal_program(days, total_weeks=4, phase_week_count=2)
    assert check_intent_monotonicity(program) == []


def test_intent_monotonicity_jump_violation():
    """50% → 95% in consecutive weeks (45pp jump)."""
    days = []
    for dow in range(7):
        t = ThrowingFiveTuple(distance_ft=60, throw_count=40, intensity_pct=50, drill="x")
        days.append(_make_day(dow, throws=t, intent_pct=50))
    for dow in range(7):
        t = ThrowingFiveTuple(distance_ft=60, throw_count=40, intensity_pct=95, drill="x")
        days.append(_make_day(7 + dow, throws=t, intent_pct=95))
    program = _minimal_program(days, total_weeks=2, phase_week_count=1)
    violations = check_intent_monotonicity(program)
    assert any(v.kind == "intent_monotonicity_jump_exceeded" for v in violations)


def test_intent_monotonicity_deload_week_exempt():
    """deload week may dip; the post-deload week recovers to prior peak — no violation."""
    intents = [70, 50, 75]  # deload Wk2 dips to 50; Wk3 returns to 75 (5pp above Wk1)
    days = []
    for wk_idx, intent in enumerate(intents):
        is_deload = wk_idx == 1
        for dow in range(7):
            t = ThrowingFiveTuple(distance_ft=60, throw_count=40, intensity_pct=intent, drill="x")
            days.append(_make_day(wk_idx * 7 + dow, throws=t, intent_pct=intent, is_deload=is_deload))
    program = _minimal_program(days, total_weeks=3, phase_week_count=1)
    violations = check_intent_monotonicity(program)
    assert violations == []


# ─────────── Pull:push ratio ───────────


def _ex(ex_id):
    return LiftingExercise(exercise_id=ex_id, sets=3, reps="8", intensity="80% 1RM")


def test_pull_push_ratio_2_to_1_passes():
    blocks = [
        LiftingBlock(block_name="B1", exercises=[_ex("ex_020"), _ex("ex_022")]),  # 2 pulls
        LiftingBlock(block_name="B2", exercises=[_ex("ex_025")]),                 # 1 push
    ]
    days = [_make_day(0, lifting=blocks)] + [_make_day(i) for i in range(1, 7)]
    program = _minimal_program(days, total_weeks=1, phase_week_count=1)
    tag_lookup = {
        "ex_020": {"pull"},
        "ex_022": {"pull"},
        "ex_025": {"push"},
    }
    # 6 pull sets / 3 push sets = 2.0 — exactly at the floor
    assert check_pull_push_ratio(program, tag_lookup) == []


def test_pull_push_ratio_violation():
    blocks = [
        LiftingBlock(block_name="B1", exercises=[_ex("ex_020")]),  # 1 pull
        LiftingBlock(block_name="B2", exercises=[_ex("ex_025"), _ex("ex_027")]),  # 2 pushes
    ]
    days = [_make_day(0, lifting=blocks)] + [_make_day(i) for i in range(1, 7)]
    program = _minimal_program(days, total_weeks=1, phase_week_count=1)
    tag_lookup = {"ex_020": {"pull"}, "ex_025": {"push"}, "ex_027": {"push"}}
    violations = check_pull_push_ratio(program, tag_lookup)
    assert len(violations) == 1
    assert violations[0].kind == "pull_push_ratio_low"
    assert violations[0].actual == 0.5


def test_pull_push_ratio_skips_zero_push_week():
    """Pull-only weeks pass (no push to divide by)."""
    blocks = [LiftingBlock(block_name="B1", exercises=[_ex("ex_020"), _ex("ex_022")])]
    days = [_make_day(0, lifting=blocks)] + [_make_day(i) for i in range(1, 7)]
    program = _minimal_program(days, total_weeks=1, phase_week_count=1)
    tag_lookup = {"ex_020": {"pull"}, "ex_022": {"pull"}}
    assert check_pull_push_ratio(program, tag_lookup) == []


# ─────────── FPM cadence ───────────


def test_fpm_cadence_4_of_7_passes():
    blocks_fpm = [LiftingBlock(block_name="B", exercises=[_ex("ex_041")])]
    blocks_no = [LiftingBlock(block_name="B", exercises=[_ex("ex_025")])]
    days = []
    for dow in range(7):
        # FPM on days 0, 1, 3, 5 → 4/7
        if dow in (0, 1, 3, 5):
            days.append(_make_day(dow, lifting=blocks_fpm))
        else:
            days.append(_make_day(dow, lifting=blocks_no))
    program = _minimal_program(days, total_weeks=1, phase_week_count=1)
    tag_lookup = {"ex_041": {"fpm"}, "ex_025": {"push"}}
    assert check_fpm_cadence(program, tag_lookup) == []


def test_fpm_cadence_violation_below_floor():
    blocks_fpm = [LiftingBlock(block_name="B", exercises=[_ex("ex_041")])]
    blocks_no = [LiftingBlock(block_name="B", exercises=[_ex("ex_025")])]
    days = []
    for dow in range(7):
        # FPM only on day 0 → 1/7
        if dow == 0:
            days.append(_make_day(dow, lifting=blocks_fpm))
        else:
            days.append(_make_day(dow, lifting=blocks_no))
    program = _minimal_program(days, total_weeks=1, phase_week_count=1)
    tag_lookup = {"ex_041": {"fpm"}, "ex_025": {"push"}}
    violations = check_fpm_cadence(program, tag_lookup)
    assert len(violations) == 1
    assert violations[0].actual == 1
    assert violations[0].kind == "fpm_cadence_insufficient"
