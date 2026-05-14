"""Plan 7 / A4 — team completion insight tests."""
from datetime import date
from unittest.mock import patch

from bot.services import coach_insights
from bot.services import db as _db
from bot.services import health_monitor


# ---------------------------------------------------------------------------
# generate_team_completion_insight — direct unit tests
# ---------------------------------------------------------------------------

def test_team_completion_fires_when_mean_below_50_pct():
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
        "start_date": "2026-02-01",
    }
    # Two pitchers — both at ~25% on an 84-day program (= drift, well under 50%)
    members = [
        {
            "pitcher_id": "p1",
            "current_day_index": 21,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
        {
            "pitcher_id": "p2",
            "current_day_index": 21,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
    ]
    out = coach_insights.generate_team_completion_insight(
        block, members, today=date(2026, 5, 1),
    )
    assert out is not None
    assert out["category"] == "team_program_lagging"
    assert out["team_id"] == "uchicago_baseball"
    # Representative pitcher — first lagger by member-program order. Required
    # because coach_suggestions.pitcher_id is NOT NULL + FK on pitchers.
    assert out["pitcher_id"] == "p1"
    assert out["proposed_action"]["scope"] == "team"
    assert out["proposed_action"]["mean_completion_pct"] < 0.5
    laggers = out["proposed_action"]["lagger_pitcher_ids"]
    assert set(laggers) == {"p1", "p2"}
    assert "2 pitchers <50%" in out["title"]


def test_team_completion_pitcher_id_is_real_member_pitcher_never_none():
    """C1 contract: pitcher_id on a team_program_lagging insight must be a real
    pitcher_id drawn from member_programs, never None — coach_suggestions has
    NOT NULL + FK constraints that would reject the row otherwise.
    """
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
    }
    member_ids = ["pitcher_alpha", "pitcher_beta", "pitcher_gamma"]
    members = [
        {
            "pitcher_id": pid,
            "current_day_index": 5,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        }
        for pid in member_ids
    ]
    out = coach_insights.generate_team_completion_insight(
        block, members, today=date(2026, 5, 1),
    )
    assert out is not None
    assert out["pitcher_id"] is not None
    assert out["pitcher_id"] in member_ids
    # Stable: first lagger in input order.
    assert out["pitcher_id"] == "pitcher_alpha"


def test_team_completion_does_not_fire_when_mean_at_or_above_50_pct():
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
        "start_date": "2026-02-01",
    }
    members = [
        # day 50 / 84 ≈ 60%
        {
            "pitcher_id": "p1",
            "current_day_index": 50,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
        # day 60 / 84 ≈ 71%
        {
            "pitcher_id": "p2",
            "current_day_index": 60,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
    ]
    out = coach_insights.generate_team_completion_insight(
        block, members, today=date(2026, 5, 1),
    )
    assert out is None


def test_team_completion_does_not_fire_with_empty_members():
    """Edge case: team-assigned block has no member programs at all."""
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
    }
    out = coach_insights.generate_team_completion_insight(
        block, [], today=date(2026, 5, 1),
    )
    assert out is None


def test_team_completion_only_fires_when_at_least_one_lagger():
    """If the mean is below 50% but no individual pitcher is below 50% (e.g.
    all clustered at 49%), still fire — the "at least one lagger" guard exists
    so we don't fire on a perfectly aligned slow team. Verify the boundary."""
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
    }
    # Both pitchers at exactly 49.99% (< 0.5) — both should lag.
    members = [
        {
            "pitcher_id": "p1",
            "current_day_index": 41,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
        {
            "pitcher_id": "p2",
            "current_day_index": 41,
            "start_date": "2026-02-01",
            "generated_schedule_json": {"days": [{} for _ in range(84)]},
        },
    ]
    out = coach_insights.generate_team_completion_insight(
        block, members, today=date(2026, 5, 1),
    )
    assert out is not None
    assert set(out["proposed_action"]["lagger_pitcher_ids"]) == {"p1", "p2"}


def test_team_completion_falls_back_to_84_when_days_missing():
    """When `generated_schedule_json.days` is empty (the summary projection
    trims that JSONB body), the generator uses 84 as a default length so it
    still produces a sane percent.
    """
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
    }
    members = [
        {
            "pitcher_id": "p1",
            "current_day_index": 10,
            "start_date": "2026-02-01",
            # no generated_schedule_json — common in summary-projection responses
        },
    ]
    out = coach_insights.generate_team_completion_insight(
        block, members, today=date(2026, 5, 1),
    )
    assert out is not None
    # 10 / 84 ≈ 0.119
    assert out["proposed_action"]["mean_completion_pct"] < 0.2


# ---------------------------------------------------------------------------
# Idempotency — wired through the health_monitor pipeline
# ---------------------------------------------------------------------------

def test_team_completion_dedup_skips_insert_when_today_row_exists():
    """Even though the team block + members would otherwise fire, the dedup
    gate must prevent a duplicate insert when a matching insight already
    exists for today.
    """
    block = {
        "block_id": "tab1",
        "block_template_id": "velocity_12wk_v1",
        "team_id": "uchicago_baseball",
        "status": "active",
        "start_date": "2026-02-01",
    }
    member = {
        "pitcher_id": "p1",
        "current_day_index": 5,
        "start_date": "2026-02-01",
        "generated_schedule_json": {"days": [{} for _ in range(84)]},
        "parent_template_id": "velocity_12wk_v1",
    }
    inserted = []

    def dedup(pitcher_id, category, **kw):
        if category == "team_program_lagging":
            return True
        return False

    with patch.object(health_monitor, "_today_iso", return_value="2026-05-01"), \
         patch("bot.services.team_scope.get_team_roster_overview", return_value=[]), \
         patch.object(_db, "list_team_assigned_blocks", return_value=[block]), \
         patch.object(_db, "list_member_programs_for_team_block",
                      return_value=[member]), \
         patch.object(_db, "suggestion_exists_for_today", side_effect=dedup), \
         patch.object(_db, "insert_coach_suggestion",
                      side_effect=lambda row: inserted.append(row) or row):
        new_count = health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    assert new_count == 0
    assert inserted == []
