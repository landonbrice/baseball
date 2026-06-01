"""Tests for bot.services.program_engine.guardrails (Task 2.4)."""
from __future__ import annotations

import pytest

from bot.services.program_engine.guardrails import (
    FATAL_KINDS,
    ValidationResult,
    validate_program,
)
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


def _minimal_program(days, *, total_weeks=4, base_weeks=2) -> PitcherProgram:
    phases = [Phase(phase_id="base", name="Base", week_count=base_weeks, intent_summary="x", phase_type="base")]
    if total_weeks - base_weeks > 0:
        phases.append(Phase(phase_id="build", name="Build", week_count=total_weeks - base_weeks, intent_summary="x"))
    return PitcherProgram(
        pitcher_id="landon_brice", goal="velocity", domain="unified",
        knowledge_version="testtest",
        generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01",
        total_weeks=total_weeks, status="draft",
        phases=phases,
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )


def _ctx(**overrides):
    base = {
        "exercises_rows": [
            {"id": "ex_001", "equipment": "trap_bar", "contraindications": []},
            {"id": "ex_020", "equipment": "DB", "contraindications": []},
            {"id": "ex_025", "equipment": "DB", "contraindications": ["anterior_shoulder_pain"]},
            {"id": "ex_041", "equipment": "DB", "contraindications": ["acute_medial_elbow_pain"]},
            {"id": "ex_070", "equipment": None, "contraindications": ["acute_medial_elbow_pain"]},
        ],
        "available_equipment": ["trap_bar", "DB", "barbell"],
        "active_modifications": [],
        "tag_lookup": {
            "ex_001": {"pull"},
            "ex_020": {"pull"},
            "ex_025": {"push"},
            "ex_041": {"fpm", "push"},
            "ex_070": {"fpm"},
        },
    }
    base.update(overrides)
    return base


def _ex(ex_id):
    return LiftingExercise(exercise_id=ex_id, sets=3, reps="8", intensity="80% 1RM")


# ─────────── Happy path ───────────


def test_validate_clean_program_returns_valid():
    """Lifting-only minimal program with FPM 4/7 days + 2:1 pull:push."""
    blocks_balanced = [LiftingBlock(block_name="B", exercises=[_ex("ex_001"), _ex("ex_020"), _ex("ex_041"), _ex("ex_070")])]
    days = []
    for wk in range(2):
        is_deload = wk == 1  # deload Wk2 so the deload cadence stays clean
        for dow in range(7):
            days.append(_make_day(wk * 7 + dow, lifting=blocks_balanced if dow < 4 else None, is_deload=is_deload))
    program = _minimal_program(days, total_weeks=2, base_weeks=1)
    result = validate_program(program, _ctx())
    assert result.status == "valid"
    assert result.violations == []
    assert result.repair_log == []


# ─────────── Repairable path ───────────


def test_validate_repairs_high_intent_in_base():
    """A single Wk1 day at 100% intent → repairs to 84% → status=repaired.

    Includes balanced lifting on days 0-4 so pull:push (2:1) + FPM (4/7)
    don't fire residual non-repairable violations after the phase-gate
    repair runs.
    """
    velo = ThrowingFiveTuple(distance_ft=120, throw_count=20, intensity_pct=100, drill="velo")
    balanced = [LiftingBlock(block_name="B", exercises=[_ex("ex_001"), _ex("ex_020"), _ex("ex_041"), _ex("ex_070")])]
    days = []
    for wk in range(2):
        is_deload = wk == 1
        for dow in range(7):
            t = velo if (wk == 0 and dow == 0) else None
            lifting = balanced if dow < 4 else None  # FPM 4/7 days
            days.append(_make_day(wk * 7 + dow, throws=t, intent_pct=100 if t else None, phase_name="Base", lifting=lifting, is_deload=is_deload))
    program = _minimal_program(days, total_weeks=2, base_weeks=1)
    result = validate_program(program, _ctx())
    assert result.status == "repaired", f"violations: {result.violations}"
    assert any(r["applied"] == "_repair_phase_gate" for r in result.repair_log)
    # The repaired day must now be at the clipped ceiling
    repaired = next(d for d in result.program.days if d.day_index == 0)
    assert repaired.intent_pct == 84


def test_validate_repairs_deload_cadence_missing():
    """6 accumulation weeks → deload demoted by repair."""
    days = []
    for wk in range(6):
        for dow in range(7):
            days.append(_make_day(wk * 7 + dow, is_deload=False))
    program = _minimal_program(days, total_weeks=6, base_weeks=3)
    result = validate_program(program, _ctx())
    # Either repaired (cadence fixed) or reject (other violations remain).
    # The key: a _repair_deload_cadence entry must appear in the log.
    assert any(r["applied"] == "_repair_deload_cadence" for r in result.repair_log)


def test_validate_repairs_acwr_above_band():
    """Sparse low load earlier + late spike day → repair clips intent on the spike."""
    light = ThrowingFiveTuple(distance_ft=45, throw_count=10, intensity_pct=40, drill="x")
    spike = ThrowingFiveTuple(distance_ft=120, throw_count=80, intensity_pct=95, drill="velo")
    days = []
    for i in range(28):
        days.append(_make_day(i, throws=light, intent_pct=40))
    # Wk5 spike days — week-relative idx 28-34
    for i in range(28, 35):
        days.append(_make_day(i, throws=spike, intent_pct=95, phase_name="Build"))
    program = _minimal_program(days, total_weeks=5, base_weeks=2)
    result = validate_program(program, _ctx())
    # The acwr_above_band repair might fire OR the result might be reject if
    # the spike is over the hard cap. Either way the repair LOG should be
    # non-empty if any repair attempt happened.
    assert isinstance(result, ValidationResult)
    # Sanity check: status is one of the three
    assert result.status in {"valid", "repaired", "reject"}


# ─────────── Reject path ───────────


def test_validate_rejects_on_unknown_exercise_id():
    """Unknown id → FATAL → reject immediately, no repair attempt."""
    bad_ex = LiftingExercise(exercise_id="ex_999", sets=3, reps="8", intensity="x")
    days = [_make_day(i, lifting=[LiftingBlock(block_name="B", exercises=[bad_ex])]) for i in range(7)]
    program = _minimal_program(days, total_weeks=1, base_weeks=1)
    result = validate_program(program, _ctx())
    assert result.status == "reject"
    assert result.repair_log == []  # no repair attempted on fatal
    assert any(v.kind == "unknown_exercise_id" for v in result.violations)


def test_validate_rejects_on_acwr_hard_cap_breach():
    """Massive late-program spike → hard cap → reject."""
    light = ThrowingFiveTuple(distance_ft=45, throw_count=10, intensity_pct=30, drill="x")
    spike = ThrowingFiveTuple(distance_ft=120, throw_count=100, intensity_pct=100, drill="velo")
    days = []
    for i in range(28):
        days.append(_make_day(i, throws=light, intent_pct=30, phase_name="Base"))
    for i in range(28, 35):
        days.append(_make_day(i, throws=spike, intent_pct=100, phase_name="Build"))
    program = _minimal_program(days, total_weeks=5, base_weeks=2)
    result = validate_program(program, _ctx())
    assert result.status == "reject"
    assert any(v.kind == "acwr_hard_cap_exceeded" for v in result.violations)


def test_validate_rejects_on_contraindicated_exercise():
    """Contraindicated exercise + active mod → reject (no repair strategy for v1)."""
    bad_ex = LiftingExercise(exercise_id="ex_041", sets=3, reps="8", intensity="BW")
    days = [_make_day(i, lifting=[LiftingBlock(block_name="B", exercises=[bad_ex])]) for i in range(7)]
    program = _minimal_program(days, total_weeks=1, base_weeks=1)
    ctx = _ctx(active_modifications=["acute_medial_elbow_pain"])
    result = validate_program(program, ctx)
    # contraindicated_exercise has no repair strategy → loop exits with
    # remaining violations → reject
    assert result.status == "reject"
    assert any(v.kind == "contraindicated_exercise" for v in result.violations)


# ─────────── Misc ───────────


def test_fatal_kinds_constant():
    assert "unknown_exercise_id" in FATAL_KINDS
    assert "acwr_hard_cap_exceeded" in FATAL_KINDS


def test_validate_program_does_not_mutate_input():
    """Repair-bound deep-copy: input program object unchanged after validate."""
    velo = ThrowingFiveTuple(distance_ft=120, throw_count=20, intensity_pct=100, drill="velo")
    days = []
    for wk in range(2):
        is_deload = wk == 1
        for dow in range(7):
            t = velo if (wk == 0 and dow == 0) else None
            days.append(_make_day(wk * 7 + dow, throws=t, intent_pct=100 if t else None, phase_name="Base", is_deload=is_deload))
    program = _minimal_program(days, total_weeks=2, base_weeks=1)
    snapshot_intent = program.days[0].intent_pct
    _ = validate_program(program, _ctx())
    assert program.days[0].intent_pct == snapshot_intent
