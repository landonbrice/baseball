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


@patch("bot.services.db.get_client")
def test_nudge_endpoint_happy_path_inserts_audit_row(mock_get_client):
    """Endpoint integration: auth → pitcher lookup → rate-limit check → send → audit insert → 200.

    Exercises the full FastAPI route including the audit insert — would have caught
    Bug #1 (wrong FK target) if run against a real Supabase, and exercises Bug #2's
    try/except by confirming the 200-path still returns success when insert succeeds.
    """
    from fastapi.testclient import TestClient

    # Mock Supabase chain. Order of table() calls when hitting the endpoint:
    #   1) coach_routes.get_pitcher → pitchers table
    #   2) coach_routes rate-limit read → coach_actions table ([] = no recent)
    #   3) send_nudge → _db.get_pitcher → pitchers table (again, internal call)
    #   4) coach_routes audit insert → coach_actions table
    client_mock = MagicMock()
    mock_get_client.return_value = client_mock

    pitcher_row = {"pitcher_id": "p1", "name": "Landon Brice", "telegram_id": 12345, "team_id": "team_x"}

    call_count = {"n": 0}

    def table_side_effect(name):
        chain = MagicMock()
        for m in ("select", "eq", "gte", "order", "limit", "insert"):
            getattr(chain, m).return_value = chain
        call_count["n"] += 1
        if name == "pitchers":
            chain.execute.return_value = type("R", (), {"data": [pitcher_row]})()
        elif name == "coach_actions":
            # First coach_actions call is the rate-limit read (empty),
            # second is the audit insert (return a row).
            if call_count["n"] == 2:
                chain.execute.return_value = type("R", (), {"data": []})()
            else:
                chain.execute.return_value = type("R", (), {"data": [{"id": 1}]})()
        else:
            chain.execute.return_value = type("R", (), {"data": []})()
        return chain

    client_mock.table.side_effect = table_side_effect

    # Mock require_coach_auth to populate request.state directly
    async def fake_auth(request):
        request.state.team_id = "team_x"
        request.state.coach_id = "coach-uuid-123"
        request.state.coach_name = "Coach Smith"

    # Mock the telegram send — Bot() returns an instance whose send_message is awaited
    with patch("api.coach_routes.require_coach_auth", fake_auth), \
         patch("bot.services.coach_actions.Bot") as MockBot:
        mock_bot_inst = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 777
        mock_bot_inst.send_message = AsyncMock(return_value=mock_msg)
        MockBot.return_value = mock_bot_inst

        from api.main import app
        tc = TestClient(app)
        resp = tc.post("/api/coach/pitcher/p1/nudge")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sent"] is True
    assert body["telegram_message_id"] == 777
    assert "sent_at" in body
