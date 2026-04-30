from unittest.mock import MagicMock, patch


def test_upsert_daily_entry_inherits_pitcher_team_id():
    from bot.services import db

    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

    with patch("bot.services.db.get_client", return_value=client), \
         patch("bot.services.db.get_pitcher", return_value={"pitcher_id": "p1", "team_id": "team_x"}):
        db.upsert_daily_entry("p1", {
            "date": "2026-04-19",
            "pre_training": {"arm_feel": 8},
        })

    payload = client.table.return_value.upsert.call_args.args[0]
    assert payload["team_id"] == "team_x"


def test_upsert_daily_entry_preserves_explicit_team_id():
    from bot.services import db

    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

    with patch("bot.services.db.get_client", return_value=client), \
         patch("bot.services.db.get_pitcher") as get_pitcher:
        db.upsert_daily_entry("p1", {
            "date": "2026-04-19",
            "team_id": "team_y",
            "pre_training": {"arm_feel": 8},
        })

    get_pitcher.assert_not_called()
    payload = client.table.return_value.upsert.call_args.args[0]
    assert payload["team_id"] == "team_y"
