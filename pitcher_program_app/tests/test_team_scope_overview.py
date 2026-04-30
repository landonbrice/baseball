"""Spec 2: get_team_roster_overview returns af_7d + today object per roster row."""
from unittest.mock import MagicMock, patch


def _mock_exec(data):
    class _R:
        def __init__(self, d): self.data = d
    return _R(data)


@patch("bot.services.team_scope.get_client")
def test_roster_includes_af_7d_and_today(mock_client):
    today = "2026-04-19"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Alpha", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([{
            "pitcher_id": "p1",
            "pre_training": {"arm_feel": 8, "overall_energy": 7},
            "plan_generated": {
                "day_focus": "lift",
                "lifting": {"block_name": "Upper push"},
                "modifications_applied": [],
            },
            "completed_exercises": {},
            "warmup": {},
            "lifting": {"exercises": [{"name": "Bench press"}, {"name": "DB row"}]},
            "throwing": None,
            "plan_narrative": None,
        }]),
        _mock_exec([
            {"pitcher_id": "p1", "date": "2026-04-13", "completed_exercises": {"a": 1}, "pre_training": {"arm_feel": 7}},
            {"pitcher_id": "p1", "date": "2026-04-14", "completed_exercises": {"a": 1}, "pre_training": {"arm_feel": 8}},
            {"pitcher_id": "p1", "date": "2026-04-15", "completed_exercises": {"a": 1}, "pre_training": {"arm_feel": 8}},
            {"pitcher_id": "p1", "date": "2026-04-16", "completed_exercises": {}, "pre_training": {"arm_feel": 6}},
            {"pitcher_id": "p1", "date": "2026-04-17", "completed_exercises": {"a": 1}, "pre_training": {"arm_feel": 7}},
            {"pitcher_id": "p1", "date": "2026-04-18", "completed_exercises": {"a": 1}, "pre_training": {"arm_feel": 8}},
            {"pitcher_id": "p1", "date": "2026-04-19", "completed_exercises": {}, "pre_training": {"arm_feel": 8}},
        ]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "green", "active_modifications": [], "days_since_outing": 3}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)

    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert len(roster) == 1
    r = roster[0]

    assert r["af_7d"] == 7.4
    assert "today" in r
    t = r["today"]
    assert t["day_focus"] == "lift"
    assert t["lifting_summary"] == "Upper push"
    assert t["bullpen"] is None
    assert t["throwing"] is None
    assert t["modifications"] == []


@patch("bot.services.team_scope.get_client")
def test_af_7d_is_none_when_no_arm_feel_entries(mock_client):
    today = "2026-04-19"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Beta", "role": "Reliever (short)", "telegram_username": None}]),
        _mock_exec([]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "green", "active_modifications": [], "days_since_outing": 1}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["af_7d"] is None
    assert roster[0]["today"]["day_focus"] is None
    assert roster[0]["today"]["lifting_summary"] is None


@patch("bot.services.team_scope.get_client")
def test_today_carries_modifications(mock_client):
    today = "2026-04-19"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Gamma", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([{
            "pitcher_id": "p1",
            "pre_training": {"arm_feel": 6},
            "plan_generated": {
                "day_focus": "lift",
                "lifting": {"block_name": "Lower pull"},
                "modifications_applied": [{"tag": "light_lifting", "reason": "forearm tight"}],
            },
            "completed_exercises": {},
            "warmup": {},
            "lifting": {"exercises": []},
            "throwing": None,
            "plan_narrative": None,
        }]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "yellow", "active_modifications": ["light_lifting"], "days_since_outing": 2}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["today"]["modifications"] == [{"tag": "light_lifting", "reason": "forearm tight"}]


@patch("bot.services.team_scope.get_client")
def test_today_derives_day_focus_and_normalizes_string_mods(mock_client):
    """Production path: plan_generator doesn't write day_focus; triage emits string modifications."""
    today = "2026-04-19"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Delta", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([{
            "pitcher_id": "p1",
            "pre_training": {"arm_feel": 7},
            # NOTE: plan_generated has NO day_focus key — matches production
            "plan_generated": {
                "lifting": {"block_name": "Upper push"},
                "modifications_applied": ["rpe_cap_56", "no_high_intent_throw"],
            },
            "completed_exercises": {},
            "warmup": {},
            "lifting": {"exercises": [{"name": "Bench"}]},
            "throwing": None,
            "plan_narrative": None,
        }]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "yellow", "active_modifications": [], "days_since_outing": 2}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["today"]["day_focus"] == "lift"
    assert roster[0]["today"]["modifications"] == [
        {"tag": "rpe_cap_56", "reason": None},
        {"tag": "no_high_intent_throw", "reason": None},
    ]


@patch("bot.services.team_scope.get_client")
def test_today_includes_rationale_short_from_entry(mock_client):
    """F4: today.rationale_short pulled from daily_entries.rationale.rationale_short."""
    today = "2026-04-22"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Echo", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([{
            "pitcher_id": "p1",
            "pre_training": {"arm_feel": 5},
            "plan_generated": {
                "day_focus": "lift",
                "lifting": {"block_name": "Upper push"},
                "modifications_applied": ["light_lifting"],
            },
            "completed_exercises": {},
            "warmup": {},
            "lifting": {"exercises": []},
            "throwing": None,
            "plan_narrative": None,
            "rationale": {
                "rationale_short": "Yellow — arm feel 5.",
                "rationale_detail": {"summary": "..."},
            },
        }]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "yellow", "active_modifications": ["light_lifting"], "days_since_outing": 2}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["today"]["rationale_short"] == "Yellow — arm feel 5."
    # modifications stays in payload for slide-over / legacy fallback
    assert roster[0]["today"]["modifications"] == [{"tag": "light_lifting", "reason": None}]


@patch("bot.services.team_scope.get_client")
def test_today_rationale_short_none_for_legacy_rows(mock_client):
    """F4: legacy rows without rationale field → rationale_short is None."""
    today = "2026-04-22"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Foxtrot", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([{
            "pitcher_id": "p1",
            "pre_training": {"arm_feel": 8},
            "plan_generated": {
                "day_focus": "lift",
                "lifting": {"block_name": "Upper push"},
                "modifications_applied": [],
            },
            "completed_exercises": {},
            "warmup": {},
            "lifting": {"exercises": []},
            "throwing": None,
            "plan_narrative": None,
            # no `rationale` key
        }]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "green", "active_modifications": [], "days_since_outing": 3}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["today"]["rationale_short"] is None


@patch("bot.services.team_scope.get_client")
def test_baseline_state_threaded_from_training_model(mock_client):
    """F4: baseline_state + total_check_ins surface from pitcher_training_model.baseline_snapshot."""
    today = "2026-04-22"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Golf", "role": "Starter (7-day)", "telegram_username": None}]),
        _mock_exec([]),
        _mock_exec([]),
        _mock_exec([{
            "pitcher_id": "p1",
            "current_flag_level": "yellow",
            "active_modifications": [],
            "days_since_outing": 1,
            "baseline_snapshot": {"baseline_state": "no_baseline", "total_check_ins": 3},
        }]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["baseline_state"] == "no_baseline"
    assert roster[0]["total_check_ins"] == 3


@patch("bot.services.team_scope.get_client")
def test_baseline_state_none_when_snapshot_missing(mock_client):
    """F4: legacy training_model rows without baseline_snapshot → None values."""
    today = "2026-04-22"
    client = MagicMock()
    mock_client.return_value = client

    table_calls = [
        _mock_exec([{"pitcher_id": "p1", "name": "Hotel", "role": "Reliever (short)", "telegram_username": None}]),
        _mock_exec([]),
        _mock_exec([]),
        _mock_exec([{"pitcher_id": "p1", "current_flag_level": "green", "active_modifications": [], "days_since_outing": 0}]),
        _mock_exec([]),
        _mock_exec([]),
    ]
    exec_seq = iter(table_calls)
    chain = MagicMock()
    chain.execute.side_effect = lambda: next(exec_seq)
    for m in ("table", "select", "eq", "gte", "lte", "in_", "order", "limit", "not_"):
        getattr(chain, m).return_value = chain
    chain.not_.is_.return_value = chain
    client.table.return_value = chain

    from bot.services.team_scope import get_team_roster_overview

    roster = get_team_roster_overview("team_x", today)
    assert roster[0]["baseline_state"] is None
    assert roster[0]["total_check_ins"] is None
