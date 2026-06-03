"""Tests for bot.services.program_engine.governor (Task 4.2)."""
from __future__ import annotations

import pytest

from bot.services.program_engine.governor import (
    MAX_WEEKS_SHIFTED,
    RegovernResult,
    regovern,
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


def _make_program(total_weeks: int = 4, with_deload_at_week: int | None = None) -> PitcherProgram:
    """Multi-week throwing-only program with consistent intent."""
    base_lifting = [LiftingBlock(block_name="B", exercises=[
        LiftingExercise(exercise_id="ex_001", sets=3, reps="8", intensity="80% 1RM"),  # pull
        LiftingExercise(exercise_id="ex_020", sets=3, reps="8", intensity="80% 1RM"),  # pull
        LiftingExercise(exercise_id="ex_025", sets=3, reps="8", intensity="80% 1RM"),  # push
        LiftingExercise(exercise_id="ex_041", sets=3, reps="10", intensity="BW"),      # fpm
    ])]
    days = []
    for wk in range(total_weeks):
        is_deload = with_deload_at_week is not None and (wk + 1) == with_deload_at_week
        for dow in range(7):
            t = ThrowingFiveTuple(distance_ft=60, throw_count=30, intensity_pct=60, drill="x")
            days.append(Day(
                day_index=wk * 7 + dow,
                template_key=f"d_{dow}",
                date=f"2026-06-{wk*7+dow+1:02d}" if wk*7+dow+1 < 32 else f"2026-07-{wk*7+dow-30:02d}",
                throwing_5tuple=t,
                lifting_blocks=base_lifting if dow < 4 else [],
                is_deload=is_deload,
                intent_pct=60,
            ))
    return PitcherProgram(
        pitcher_id="landon_brice", goal="velocity", domain="unified",
        knowledge_version="testtest_12345678",
        generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01", total_weeks=total_weeks, status="draft",
        phases=[Phase(phase_id="base", name="Base", week_count=total_weeks, intent_summary="x", phase_type="base")],
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )


def test_no_signal_returns_unchanged():
    program = _make_program(4)
    result = regovern(program, None, "immediate_repace", from_day_index=5)
    assert result.changes == []
    assert result.goal_at_risk is False
    assert result.program is program  # same object


def test_silent_absorb_never_changes():
    program = _make_program(4)
    signal = {"severity": "large", "kind": "missed_load", "missed_g": 9999}
    result = regovern(program, signal, "silent_absorb", from_day_index=5)
    assert result.changes == []
    assert result.goal_at_risk is False


def test_immediate_repace_small_bumps_next_week_intent():
    program = _make_program(4)
    signal = {"severity": "small", "kind": "missed_load", "missed_g": 500}
    result = regovern(program, signal, "immediate_repace", from_day_index=5)  # day 5 = Wk1
    assert result.goal_at_risk is False
    assert any(c["kind"] == "intent_bump_next_week" for c in result.changes)
    # Wk2 (days 7-13) intent should be 65 now (60 + 5)
    wk2_intents = [d.intent_pct for d in result.program.days if 7 <= d.day_index < 14]
    assert all(i == 65 for i in wk2_intents if i is not None)


def test_immediate_repace_medium_shifts_one_week():
    program = _make_program(4)
    signal = {"severity": "medium", "kind": "missed_load", "missed_g": 2500}
    result = regovern(program, signal, "immediate_repace", from_day_index=5)
    assert result.goal_at_risk is False
    assert any(c["kind"] == "shift_accumulation_forward" and c["weeks"] == 1 for c in result.changes)


def test_immediate_repace_large_shifts_two_weeks_and_demotes_deload():
    program = _make_program(4, with_deload_at_week=3)
    signal = {"severity": "large", "kind": "missed_load", "missed_g": 7000}
    result = regovern(program, signal, "immediate_repace", from_day_index=5)
    assert any(c["kind"] == "shift_accumulation_forward" and c["weeks"] == MAX_WEEKS_SHIFTED for c in result.changes)
    assert any(c["kind"] == "demote_next_deload" for c in result.changes)
    # Wk3 (days 14-20) should no longer be deload
    wk3_days = [d for d in result.program.days if 14 <= d.day_index < 21]
    assert not any(d.is_deload for d in wk3_days)


def test_banked_deviation_small_absorbs():
    program = _make_program(4)
    signal = {"severity": "small", "kind": "banked_deviation", "missed_g": 5500}
    result = regovern(program, signal, "banked_deviation", from_day_index=5)
    # No changes — banked absorbs small, only re-paces on medium+
    assert result.changes == []
    # But signal != None + policy != silent_absorb + no changes → goal_at_risk
    assert result.goal_at_risk is True


def test_banked_deviation_medium_shifts_one():
    program = _make_program(4)
    signal = {"severity": "medium", "kind": "banked_deviation", "missed_g": 6000}
    result = regovern(program, signal, "banked_deviation", from_day_index=5)
    assert any(c["kind"] == "shift_accumulation_forward" for c in result.changes)


def test_signal_on_last_week_sets_goal_at_risk():
    """No future weeks to re-pace into → goal_at_risk."""
    program = _make_program(4)
    signal = {"severity": "medium", "kind": "missed_load", "missed_g": 3000}
    # from_day_index in the LAST week — no weeks after
    result = regovern(program, signal, "immediate_repace", from_day_index=27)
    assert result.goal_at_risk is True
    assert result.changes == []


def test_repace_does_not_mutate_input_program():
    """Deep-copy invariant: caller's program unchanged."""
    program = _make_program(4)
    snapshot = program.days[10].intent_pct
    signal = {"severity": "small", "kind": "missed_load", "missed_g": 500}
    regovern(program, signal, "immediate_repace", from_day_index=5)
    assert program.days[10].intent_pct == snapshot


def test_invalid_policy_treated_as_silent_when_no_signal():
    """No signal → no-op regardless of policy."""
    program = _make_program(4)
    result = regovern(program, None, "immediate_repace", from_day_index=0)
    assert result.changes == []


def test_returns_regovern_result_dataclass():
    program = _make_program(4)
    result = regovern(program, None, "silent_absorb", from_day_index=0)
    assert isinstance(result, RegovernResult)
    assert hasattr(result, "program")
    assert hasattr(result, "changes")
    assert hasattr(result, "goal_at_risk")
