from bot.services.db import _DAILY_ENTRY_COLUMNS


def test_rationale_in_whitelist():
    assert "rationale" in _DAILY_ENTRY_COLUMNS, (
        "rationale column must be in _DAILY_ENTRY_COLUMNS or upsert will strip it silently"
    )
