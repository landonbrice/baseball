"""Tests for bot.services.program_anchoring (Plan 5).

Covers `recompute_program_schedule` and the persistence helper
`db.update_program_schedule`.
"""
from unittest.mock import MagicMock, patch

import pytest

from bot.services import program_anchoring
from bot.services import db


# ---------- helpers ----------

def _calendar_program(start_date="2026-05-01", weeks=12, current_day_index=0):
    """Starter cadence (calendar-relative-repeating-7day) — recompute should be a no-op."""
    from datetime import date, timedelta
    sd = date.fromisoformat(start_date)
    days = []
    for i in range(weeks * 7):
        days.append({
            "day_index": i,
            "template_key": f"day_{i % 7}",
            "date": (sd + timedelta(days=i)).isoformat(),
        })
    return {
        "current_day_index": current_day_index,
        "generated_schedule_json": {
            "scaffold_kind": "calendar_relative_repeating_7day",
            "days": days,
        },
    }


def _anchor_program(start_date="2026-05-01", weeks=2, current_day_index=0):
    """Synthetic anchor-relative program: every day declares an anchor_kind."""
    from datetime import date, timedelta
    sd = date.fromisoformat(start_date)
    days = []
    # Pattern: day 0 = T-3 from next bullpen, day 1 = T-2, day 2 = T-1, day 3 = bullpen, repeat.
    pattern = [
        ("T-3_from_next_bullpen", "high_effort_plyo"),
        ("T-2_from_next_bullpen", "moderate_plyo"),
        ("T-1_from_next_bullpen", "rest"),
        ("bullpen_day", "bullpen"),
    ]
    for i in range(weeks * 7):
        ak, tk = pattern[i % len(pattern)]
        days.append({
            "day_index": i,
            "template_key": tk,
            "date": (sd + timedelta(days=i)).isoformat(),
            "anchor_kind": ak,
        })
    return {
        "current_day_index": current_day_index,
        "generated_schedule_json": {
            "scaffold_kind": "anchor_relative",
            "days": days,
        },
    }


# ---------- recompute_program_schedule ----------

def test_calendar_relative_template_is_noop():
    """Starter cadence schedule passes through unchanged regardless of throws."""
    program = _calendar_program()
    original_days = list(program["generated_schedule_json"]["days"])
    throws = [
        {"date": "2026-05-10", "kind": "bullpen"},
        {"date": "2026-05-15", "kind": "outing"},
    ]
    new_schedule = program_anchoring.recompute_program_schedule(program, throws)
    assert new_schedule == program["generated_schedule_json"]
    assert new_schedule["days"] == original_days


def test_past_days_are_frozen():
    """Days with day_index < current_day_index must be byte-identical in output."""
    program = _anchor_program(weeks=2, current_day_index=10)
    original = program["generated_schedule_json"]["days"]
    frozen_slice = [dict(d) for d in original[:10]]

    throws = [{"date": "2026-06-01", "kind": "bullpen"}]
    new_schedule = program_anchoring.recompute_program_schedule(program, throws)

    new_frozen = new_schedule["days"][:10]
    assert new_frozen == frozen_slice


def test_anchor_relative_repositions_future_days_around_next_bullpen():
    """T-3/T-2/T-1 days re-position to be 3/2/1 days before the next future bullpen."""
    program = _anchor_program(start_date="2026-05-01", weeks=2, current_day_index=0)
    # Coach scheduled a bullpen on 2026-05-10. The first three future T-N days
    # should anchor to that bullpen: T-3 = 05-07, T-2 = 05-08, T-1 = 05-09.
    throws = [{"date": "2026-05-10", "kind": "bullpen"}]
    new_schedule = program_anchoring.recompute_program_schedule(program, throws)
    days = new_schedule["days"]

    # Find the first T-3 day in the future
    t3 = next(d for d in days if d.get("anchor_kind") == "T-3_from_next_bullpen")
    t2 = next(d for d in days if d.get("anchor_kind") == "T-2_from_next_bullpen")
    t1 = next(d for d in days if d.get("anchor_kind") == "T-1_from_next_bullpen")
    assert t3["date"] == "2026-05-07"
    assert t2["date"] == "2026-05-08"
    assert t1["date"] == "2026-05-09"


def test_empty_throws_leaves_dates_unchanged():
    """No future scheduled throws → anchor-relative days fall back to original dates."""
    program = _anchor_program(weeks=2)
    original_dates = [d["date"] for d in program["generated_schedule_json"]["days"]]
    new_schedule = program_anchoring.recompute_program_schedule(program, [])
    new_dates = [d["date"] for d in new_schedule["days"]]
    assert new_dates == original_dates


def test_throw_before_current_day_index_is_ignored():
    """Throws in the past don't anchor future days."""
    program = _anchor_program(start_date="2026-05-01", weeks=2, current_day_index=7)
    # The "past" throw is on 2026-05-02 — well before current pointer.
    # The future throw on 2026-05-15 is what should anchor.
    throws = [
        {"date": "2026-05-02", "kind": "bullpen"},  # past, ignored
        {"date": "2026-05-15", "kind": "bullpen"},  # future, anchors
    ]
    new_schedule = program_anchoring.recompute_program_schedule(program, throws)
    days = new_schedule["days"]
    # Past T-3 (day_index < 7) must be untouched (frozen).
    assert days[0]["date"] == program["generated_schedule_json"]["days"][0]["date"]
    # First future T-3 should anchor to 2026-05-15 → 2026-05-12.
    future_t3 = next(
        d for d in days
        if d["day_index"] >= 7 and d.get("anchor_kind") == "T-3_from_next_bullpen"
    )
    assert future_t3["date"] == "2026-05-12"


# ---------- db.update_program_schedule ----------

def test_update_program_schedule_writes_program_and_inserts_revision():
    """Persistence helper updates programs row + inserts program_schedule_revisions row."""
    new_schedule = {"scaffold_kind": "anchor_relative", "days": [{"day_index": 0}]}
    old_schedule = {"scaffold_kind": "anchor_relative", "days": []}

    fake_program_row = [{"program_id": "abc-123", "generated_schedule_json": old_schedule}]

    client = MagicMock()
    # First call: select existing program (for old_schedule capture)
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=fake_program_row)
    # update programs ... eq ... execute()
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"program_id": "abc-123"}])
    # insert program_schedule_revisions ... execute()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"revision_id": "r1"}])

    with patch.object(db, "get_client", return_value=client):
        db.update_program_schedule("abc-123", new_schedule, trigger_type="anchor_recompute")

    # Verify update was called on `programs` table
    update_calls = [c for c in client.table.call_args_list if c.args and c.args[0] == "programs"]
    revision_calls = [c for c in client.table.call_args_list if c.args and c.args[0] == "program_schedule_revisions"]
    assert update_calls, "expected an update against the `programs` table"
    assert revision_calls, "expected an insert against `program_schedule_revisions`"
