from unittest.mock import patch


def test_load_profile_includes_team_id_for_team_scoped_clients():
    from bot.services.context_manager import load_profile

    pitcher = {
        "pitcher_id": "p1",
        "team_id": "team_a",
        "telegram_id": 123,
        "telegram_username": "alpha",
        "name": "Alpha Arm",
        "role": "starter",
    }

    with patch("bot.services.context_manager._db.get_pitcher", return_value=pitcher), \
            patch("bot.services.context_manager._db.get_injury_history", return_value=[]), \
            patch("bot.services.context_manager._db.get_active_flags", return_value={}):
        profile = load_profile("p1")

    assert profile["team_id"] == "team_a"
