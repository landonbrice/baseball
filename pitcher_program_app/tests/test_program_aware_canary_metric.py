"""Plan 8 / D2 — program-aware canary metric tests."""
from unittest.mock import patch, MagicMock

from bot.services import health_monitor


def _stub_supabase_canary(client, daily_entries_rows):
    """Helper: stub the .in_().gte().execute() chain on daily_entries."""
    chain = (
        client.table.return_value
        .select.return_value
        .in_.return_value
        .gte.return_value
    )
    chain.execute.return_value = MagicMock(data=daily_entries_rows)


def test_canary_zero_pitchers_flagged_returns_none_rate():
    """When no pitchers have the flag ON, return total=0, rate=None.
    Don't query daily_entries — short-circuit."""
    fake_pitchers = [
        {"pitcher_id": "a", "team_id": "uchicago_baseball"},
        {"pitcher_id": "b", "team_id": "uchicago_baseball"},
    ]
    with patch("bot.services.db.list_pitchers", return_value=fake_pitchers), \
         patch("bot.services.db.get_feature_flag", return_value=False), \
         patch("bot.services.db.get_client") as gc:
        out = health_monitor.compute_program_aware_canary(days=7)
    assert out == {"total": 0, "program_prescribed": 0, "rate": None}
    gc.assert_not_called()  # short-circuit: no query when nobody is flagged


def test_canary_all_prescribed_returns_one():
    """All entries have source='program_prescribed' → rate=1.0."""
    fake_pitchers = [{"pitcher_id": "a", "team_id": "uchicago_baseball"}]
    daily_rows = [
        {"plan_generated": {"source": "program_prescribed"}},
        {"plan_generated": {"source": "program_prescribed"}},
        {"plan_generated": {"source": "program_prescribed"}},
    ]
    client = MagicMock()
    _stub_supabase_canary(client, daily_rows)
    with patch("bot.services.db.list_pitchers", return_value=fake_pitchers), \
         patch("bot.services.db.get_feature_flag", return_value=True), \
         patch("bot.services.db.get_client", return_value=client):
        out = health_monitor.compute_program_aware_canary(days=7)
    assert out["total"] == 3
    assert out["program_prescribed"] == 3
    assert out["rate"] == 1.0


def test_canary_mixed_sources_returns_ratio():
    """Mixed: 2 program_prescribed + 1 python_fallback + 1 llm_enriched = 2/4 = 0.5."""
    fake_pitchers = [{"pitcher_id": "a", "team_id": "uchicago_baseball"}]
    daily_rows = [
        {"plan_generated": {"source": "program_prescribed"}},
        {"plan_generated": {"source": "program_prescribed"}},
        {"plan_generated": {"source": "python_fallback"}},
        {"plan_generated": {"source": "llm_enriched"}},
    ]
    client = MagicMock()
    _stub_supabase_canary(client, daily_rows)
    with patch("bot.services.db.list_pitchers", return_value=fake_pitchers), \
         patch("bot.services.db.get_feature_flag", return_value=True), \
         patch("bot.services.db.get_client", return_value=client):
        out = health_monitor.compute_program_aware_canary(days=7)
    assert out["total"] == 4
    assert out["program_prescribed"] == 2
    assert out["rate"] == 0.5


def test_canary_missing_plan_generated_field_treated_as_non_program():
    """Rows with no plan_generated or no source field are NOT counted as
    program_prescribed (they count toward total but not the numerator)."""
    fake_pitchers = [{"pitcher_id": "a", "team_id": "uchicago_baseball"}]
    daily_rows = [
        {"plan_generated": {"source": "program_prescribed"}},
        {"plan_generated": None},
        {"plan_generated": {}},
        {},  # row with no plan_generated key at all
    ]
    client = MagicMock()
    _stub_supabase_canary(client, daily_rows)
    with patch("bot.services.db.list_pitchers", return_value=fake_pitchers), \
         patch("bot.services.db.get_feature_flag", return_value=True), \
         patch("bot.services.db.get_client", return_value=client):
        out = health_monitor.compute_program_aware_canary(days=7)
    assert out["total"] == 4
    assert out["program_prescribed"] == 1
    assert out["rate"] == 0.25
