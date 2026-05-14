"""Plan 7 / A4 — drift insight tests.

Covers the rule-based generator + the suggestion_exists_for_today dedup gate
+ a small integration-style smoke test that drives
_generate_coach_insights_for_team end-to-end with mocked DB layer.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from bot.services import coach_insights
from bot.services import db as _db
from bot.services import health_monitor


# ---------------------------------------------------------------------------
# generate_drift_insight_for_program — direct unit tests
# ---------------------------------------------------------------------------

def test_drift_insight_fires_when_more_than_5_days_behind():
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-01",       # 30 days before "today"
        "current_day_index": 20,           # should be ~30; drift = 10
        "held_days_count": 4,
    }
    today = date(2026, 5, 1)
    out = coach_insights.generate_drift_insight_for_program(program, today=today)
    assert out is not None
    assert out["category"] == "program_drift"
    assert out["proposed_action"]["drift_days"] == 10
    assert out["proposed_action"]["program_id"] == "p1"
    assert out["status"] == "pending"
    assert out["pitcher_id"] == "landon_brice"
    # team_id is filled by caller
    assert out["team_id"] is None


def test_drift_insight_does_not_fire_within_grace_window():
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-25",       # 6 days before "today"
        "current_day_index": 3,            # drift = 3, inside grace
        "held_days_count": 1,
    }
    today = date(2026, 5, 1)
    out = coach_insights.generate_drift_insight_for_program(program, today=today)
    assert out is None


def test_drift_insight_exactly_at_threshold_no_insight():
    """Drift == 5 is still inside the grace window (>5 required)."""
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-21",       # 10 days before "today"
        "current_day_index": 5,            # drift = 5 exactly
        "held_days_count": 0,
    }
    today = date(2026, 5, 1)
    out = coach_insights.generate_drift_insight_for_program(program, today=today)
    assert out is None


def test_drift_insight_no_start_date_returns_none():
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": None,
        "current_day_index": 0,
    }
    out = coach_insights.generate_drift_insight_for_program(
        program, today=date(2026, 5, 1)
    )
    # When start_date is missing _expected_day_index returns 0, so drift = 0 <= 5 → None.
    assert out is None


# ---------------------------------------------------------------------------
# Idempotency — suggestion_exists_for_today causes caller to skip insert
# ---------------------------------------------------------------------------

def test_drift_insight_dedup_skips_insert_when_today_row_exists():
    """When suggestion_exists_for_today returns True the digest pipeline must
    NOT call insert_coach_suggestion for the same (pitcher, category, program)."""
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-01",
        "current_day_index": 20,
        "held_days_count": 4,
    }

    roster = [{"pitcher_id": "landon_brice", "name": "Landon Brice"}]
    inserted = []

    with patch.object(health_monitor, "_today_iso", return_value="2026-05-01"), \
         patch("bot.services.team_scope.get_team_roster_overview", return_value=roster), \
         patch.object(_db, "list_programs_for_pitcher_summary", return_value=[program]), \
         patch.object(_db, "get_active_flags", return_value={"current_flag_level": "green"}), \
         patch.object(_db, "list_team_assigned_blocks", return_value=[]), \
         patch.object(_db, "suggestion_exists_for_today", return_value=True), \
         patch.object(_db, "insert_coach_suggestion",
                      side_effect=lambda row: inserted.append(row) or row), \
         patch.object(coach_insights, "generate_drift_insight_for_program",
                      return_value={
                          "team_id": None,
                          "pitcher_id": "landon_brice",
                          "category": "program_drift",
                          "title": "drift",
                          "reasoning": "...",
                          "proposed_action": {"program_id": "p1"},
                          "status": "pending",
                      }):
        new_count = health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    assert new_count == 0
    assert inserted == []


# ---------------------------------------------------------------------------
# Integration smoke — drift + mismatch + completion all flow through the
# generator pipeline once, with dedup checks fired per type.
# ---------------------------------------------------------------------------

def test_generate_coach_insights_for_team_drives_all_three_generators():
    """End-to-end smoke for the digest wiring with mocked DB.

    Verifies that:
      - one drift suggestion is inserted (program drifted 10 days),
      - one mismatch suggestion is inserted (yellow flag + velocity template),
      - one team completion suggestion is inserted (block at 30% completion),
      - suggestion_exists_for_today is consulted once per insight type.
    """
    program = {
        "program_id": "p1",
        "pitcher_id": "landon_brice",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-01",
        "current_day_index": 20,    # drift = 10
        "held_days_count": 4,
        "generated_schedule_json": {"days": [{} for _ in range(84)]},
    }
    roster = [{"pitcher_id": "landon_brice", "name": "Landon Brice"}]
    team_block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
        "status": "active",
        "start_date": "2026-02-01",
    }

    inserted = []
    dedup_calls = []

    def fake_dedup(pitcher_id, category, **kw):
        dedup_calls.append((pitcher_id, category, kw))
        return False

    with patch.object(health_monitor, "_today_iso", return_value="2026-05-01"), \
         patch("bot.services.team_scope.get_team_roster_overview", return_value=roster), \
         patch.object(_db, "list_programs_for_pitcher_summary", return_value=[program]), \
         patch.object(_db, "get_active_flags",
                      return_value={"current_flag_level": "yellow"}), \
         patch.object(_db, "list_team_assigned_blocks", return_value=[team_block]), \
         patch.object(_db, "list_member_programs_for_team_block",
                      return_value=[program]), \
         patch.object(_db, "suggestion_exists_for_today", side_effect=fake_dedup), \
         patch.object(_db, "insert_coach_suggestion",
                      side_effect=lambda row: inserted.append(row) or row), \
         patch("bot.services.coach_insights.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 1)
        mock_date.fromisoformat.side_effect = date.fromisoformat
        new_count = health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    categories = sorted(row["category"] for row in inserted)
    assert categories == [
        "program_drift",
        "program_flag_mismatch",
        "team_program_lagging",
    ], f"unexpected insight types: {categories}"
    # team_id must be filled by the wiring before insert
    assert all(row.get("team_id") == "uchicago_baseball" for row in inserted)
    assert new_count == 3

    dedup_categories = sorted({c for _, c, _ in dedup_calls})
    assert dedup_categories == [
        "program_drift",
        "program_flag_mismatch",
        "team_program_lagging",
    ]
