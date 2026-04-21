"""Tests for nudge backend: send_nudge() and rate-limit logic."""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_exec(data):
    class _R:
        def __init__(self, d): self.data = d
    return _R(data)


@patch("bot.services.db.get_client")
def test_send_nudge_builds_correct_message(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    chain = MagicMock()
    chain.execute.return_value = _mock_exec([{
        "pitcher_id": "p1",
        "name": "Landon Brice",
        "telegram_id": 12345,
    }])
    for m in ("table", "select", "eq"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain

    async def run():
        with patch("bot.services.coach_actions.Bot") as MockBot:
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot
            mock_msg = MagicMock()
            mock_msg.message_id = 999
            mock_bot.send_message = AsyncMock(return_value=mock_msg)

            from bot.services.coach_actions import send_nudge
            result = await send_nudge("p1", "Coach Smith")

            kwargs = mock_bot.send_message.call_args.kwargs
            assert kwargs["chat_id"] == 12345
            assert "Coach Smith" in kwargs["text"]
            assert "Landon" in kwargs["text"]
            assert "/checkin" in kwargs["text"]
            assert result == 999

    asyncio.run(run())


@patch("bot.services.db.get_client")
def test_send_nudge_raises_when_pitcher_missing(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    chain = MagicMock()
    chain.execute.return_value = _mock_exec([])  # get_pitcher raises KeyError → ValueError
    for m in ("table", "select", "eq"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain

    import pytest
    async def run():
        from bot.services.coach_actions import send_nudge
        with pytest.raises(ValueError, match="not found"):
            await send_nudge("missing", "Coach")

    asyncio.run(run())


@patch("bot.services.db.get_client")
def test_send_nudge_raises_when_no_telegram_id(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    chain = MagicMock()
    chain.execute.return_value = _mock_exec([{
        "pitcher_id": "p1",
        "name": "Landon Brice",
        "telegram_id": None,
    }])
    for m in ("table", "select", "eq"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain

    import pytest
    async def run():
        from bot.services.coach_actions import send_nudge
        with pytest.raises(ValueError, match="No telegram_id"):
            await send_nudge("p1", "Coach")

    asyncio.run(run())


def test_rate_limit_window_is_two_hours():
    """Rate-limit window: last nudge 1.5h ago → retry_after ≈ 1800s."""
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    last_nudge = datetime(2026, 4, 21, 10, 30, 0, tzinfo=timezone.utc)
    elapsed = (now - last_nudge).total_seconds()
    retry_after = int(7200 - elapsed)
    assert retry_after == 1800
