"""D9, D13, D14, D22: telemetry endpoint inserts + rate-limits admin DM per 24h."""
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

_FAKE_EXERCISE = {"id": "ex_missing", "name": "Fake Exercise"}


def _setup(monkeypatch, count_recent):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    inserts = []
    monkeypatch.setattr(
        "bot.services.db.insert_ui_fallback_log",
        lambda **kw: inserts.append(kw),
    )
    monkeypatch.setattr(
        "bot.services.db.count_recent_ui_fallback",
        lambda exercise_id, hours: count_recent,
    )
    # I1: stub get_exercise so the endpoint accepts the test exercise_id
    monkeypatch.setattr(
        "bot.services.db.get_exercise",
        lambda exercise_id: _FAKE_EXERCISE,
    )

    dms = []
    async def fake_send(text):
        dms.append(text)
    monkeypatch.setattr(
        "api.routes._send_admin_dm",
        fake_send,
    )
    return inserts, dms


def test_fallback_logs_row_and_dms_on_cold_exercise(monkeypatch):
    inserts, dms = _setup(monkeypatch, count_recent=1)  # count==1 → first event in window
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_missing", "surface": "mini-app", "component": "ExerciseRow", "pitcher_id": "p1"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1
    assert inserts[0]["exercise_id"] == "ex_missing"
    assert len(dms) == 1  # count==1 → DM fires


def test_fallback_logs_row_but_rate_limits_dm(monkeypatch):
    inserts, dms = _setup(monkeypatch, count_recent=5)  # count>1 → already DM'd this window
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_missing", "surface": "coach-app"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1  # still records every miss
    assert len(dms) == 0  # rate-limited — no DM


def test_fallback_rejects_unknown_exercise_id(monkeypatch):
    """I1 (Option C): unknown exercise_id returns 400 without inserting or DMing."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    inserts = []
    monkeypatch.setattr("bot.services.db.insert_ui_fallback_log", lambda **kw: inserts.append(kw))
    monkeypatch.setattr("bot.services.db.count_recent_ui_fallback", lambda *a, **kw: 0)
    monkeypatch.setattr("bot.services.db.get_exercise", lambda exercise_id: None)
    dms = []
    async def fake_send(text):
        dms.append(text)
    monkeypatch.setattr("api.routes._send_admin_dm", fake_send)

    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "totally_fake_id", "surface": "mini-app"},
    )
    assert res.status_code == 400
    assert "unknown exercise_id" in res.json()["detail"]
    assert len(inserts) == 0
    assert len(dms) == 0
