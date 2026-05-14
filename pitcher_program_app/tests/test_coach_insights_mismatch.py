"""Plan 7 / A4 — flag mismatch insight tests."""
from unittest.mock import patch

from bot.services import coach_insights
from bot.services import db as _db
from bot.services import health_monitor


# ---------------------------------------------------------------------------
# Positive cases — yellow/red + high-intent template → insight fires
# ---------------------------------------------------------------------------

def test_mismatch_fires_when_yellow_flag_and_velocity_program():
    profile = {"pitcher_id": "pitcher_heron_001", "name": "Carter Heron"}
    programs = [{
        "program_id": "abc",
        "parent_template_id": "velocity_12wk_v1",
        "pitcher_id": "pitcher_heron_001",
        "domain": "throwing",
    }]
    out = coach_insights.generate_mismatch_insight_for_pitcher(
        profile, "yellow", programs
    )
    assert out is not None
    assert out["category"] == "program_flag_mismatch"
    assert out["pitcher_id"] == "pitcher_heron_001"
    assert "Carter Heron" in out["title"]
    assert "YELLOW" in out["title"]
    assert out["proposed_action"]["program_id"] == "abc"
    assert out["proposed_action"]["flag_level"] == "yellow"
    assert out["proposed_action"]["template"] == "velocity_12wk_v1"
    assert out["status"] == "pending"
    # team_id is filled by caller.
    assert out["team_id"] is None


def test_mismatch_fires_for_red_and_critical_red():
    profile = {"pitcher_id": "p2", "name": "P2"}
    programs = [{
        "program_id": "x",
        "parent_template_id": "offseason_base_4wk_v1",
        "pitcher_id": "p2",
    }]
    for flag in ("red", "critical_red"):
        out = coach_insights.generate_mismatch_insight_for_pitcher(
            profile, flag, programs
        )
        assert out is not None, f"expected insight for flag={flag}"
        assert out["proposed_action"]["flag_level"] == flag


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------

def test_mismatch_does_not_fire_when_green_flag():
    profile = {"pitcher_id": "p1", "name": "P1"}
    programs = [{
        "program_id": "x",
        "parent_template_id": "velocity_12wk_v1",
        "pitcher_id": "p1",
    }]
    out = coach_insights.generate_mismatch_insight_for_pitcher(
        profile, "green", programs
    )
    assert out is None


def test_mismatch_does_not_fire_when_flag_level_missing():
    profile = {"pitcher_id": "p1", "name": "P1"}
    programs = [{
        "program_id": "x",
        "parent_template_id": "velocity_12wk_v1",
        "pitcher_id": "p1",
    }]
    out = coach_insights.generate_mismatch_insight_for_pitcher(
        profile, None, programs
    )
    assert out is None


def test_mismatch_does_not_fire_on_low_intent_template():
    """Maintenance / starter cadence templates are not high-intent."""
    profile = {"pitcher_id": "p1", "name": "P1"}
    programs = [{
        "program_id": "x",
        "parent_template_id": "tpl_starter_7day_cadence_v1",
        "pitcher_id": "p1",
    }]
    out = coach_insights.generate_mismatch_insight_for_pitcher(
        profile, "yellow", programs
    )
    assert out is None


def test_mismatch_does_not_fire_with_no_active_programs():
    """Edge case: pitcher is yellow but has no active programs at all."""
    profile = {"pitcher_id": "p1", "name": "P1"}
    out = coach_insights.generate_mismatch_insight_for_pitcher(
        profile, "yellow", []
    )
    assert out is None


# ---------------------------------------------------------------------------
# Idempotency — exact same pitcher won't double-insert in the same day
# ---------------------------------------------------------------------------

def test_mismatch_dedup_skips_insert_when_today_row_exists():
    """When suggestion_exists_for_today returns True for the pitcher /
    category combo, the digest pipeline must NOT call insert_coach_suggestion
    for that pitcher's mismatch even though a fresh insight is generated."""
    program = {
        "program_id": "v1",
        "pitcher_id": "p_red",
        "parent_template_id": "velocity_12wk_v1",
        "domain": "throwing",
        "start_date": "2026-04-30",   # 1 day before "today" — no drift
        "current_day_index": 1,
        "held_days_count": 0,
        "generated_schedule_json": {"days": []},
    }
    roster = [{"pitcher_id": "p_red", "name": "Red Pitcher"}]
    inserted = []

    def dedup(pitcher_id, category, **kw):
        # Allow drift dedup to return False, mismatch dedup to return True.
        return category == "program_flag_mismatch"

    with patch.object(health_monitor, "_today_iso", return_value="2026-05-01"), \
         patch("bot.services.team_scope.get_team_roster_overview", return_value=roster), \
         patch.object(_db, "list_programs_for_pitcher_summary", return_value=[program]), \
         patch.object(_db, "get_active_flags",
                      return_value={"current_flag_level": "red"}), \
         patch.object(_db, "list_team_assigned_blocks", return_value=[]), \
         patch.object(_db, "suggestion_exists_for_today", side_effect=dedup), \
         patch.object(_db, "insert_coach_suggestion",
                      side_effect=lambda row: inserted.append(row) or row):
        new_count = health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    # No mismatch insert despite the criteria being met.
    categories = [row["category"] for row in inserted]
    assert "program_flag_mismatch" not in categories
    assert new_count == 0


def test_mismatch_inserts_when_dedup_clean_and_flag_yellow():
    """Smoke that the pipeline does fire a mismatch insert when dedup is clean."""
    program = {
        "program_id": "v1",
        "pitcher_id": "p_yellow",
        "parent_template_id": "velocity_12wk_v1",
        "domain": "throwing",
        "start_date": "2026-04-30",
        "current_day_index": 1,
        "held_days_count": 0,
        "generated_schedule_json": {"days": []},
    }
    roster = [{"pitcher_id": "p_yellow", "name": "Yellow Pitcher"}]
    inserted = []

    with patch.object(health_monitor, "_today_iso", return_value="2026-05-01"), \
         patch("bot.services.team_scope.get_team_roster_overview", return_value=roster), \
         patch.object(_db, "list_programs_for_pitcher_summary", return_value=[program]), \
         patch.object(_db, "get_active_flags",
                      return_value={"current_flag_level": "yellow"}), \
         patch.object(_db, "list_team_assigned_blocks", return_value=[]), \
         patch.object(_db, "suggestion_exists_for_today", return_value=False), \
         patch.object(_db, "insert_coach_suggestion",
                      side_effect=lambda row: inserted.append(row) or row):
        new_count = health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    assert new_count == 1
    assert inserted[0]["category"] == "program_flag_mismatch"
    assert inserted[0]["pitcher_id"] == "p_yellow"
    assert inserted[0]["team_id"] == "uchicago_baseball"
