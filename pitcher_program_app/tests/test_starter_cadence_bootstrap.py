"""Smoke test: every 7-day starter has exactly one active throwing program after bootstrap.

This test is a snapshot in time — it'll drift the next morning when days_since_outing
increments. Marked skip after the bootstrap merges; preserved for one-shot validation."""

import os
import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")),
    reason="Bootstrap smoke test requires live Supabase credentials",
)


# 7-day starters as of 2026-04-30 bootstrap. Update if the roster changes.
STARTERS = ["landon_brice", "pitcher_benner_001", "pitcher_kwinter_001", "test_pitcher_001"]


@pytest.mark.integration
@pytest.mark.parametrize("pitcher_id", STARTERS)
def test_starter_has_active_throwing_program(pitcher_id):
    from bot.services import db
    program = db.get_active_program(pitcher_id, "throwing")
    assert program is not None, f"{pitcher_id} should have an active throwing program after bootstrap"
    assert program["parent_template_id"] == "tpl_starter_7day_cadence_v1", \
        f"{pitcher_id} bootstrap pointed at wrong template: {program['parent_template_id']}"


@pytest.mark.integration
@pytest.mark.parametrize("pitcher_id", STARTERS)
def test_starter_program_schedule_has_84_days(pitcher_id):
    from bot.services import db
    program = db.get_active_program(pitcher_id, "throwing")
    days = (program.get("generated_schedule_json") or {}).get("days") or []
    assert len(days) == 84, f"{pitcher_id} schedule has {len(days)} days, expected 84"
