"""D9, D13, D14: telemetry endpoint inserts + rate-limits admin DM per 24h."""
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def _setup(monkeypatch, has_recent):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    inserts = []
    monkeypatch.setattr(
        "bot.services.db.insert_ui_fallback_log",
        lambda **kw: inserts.append(kw),
    )
    monkeypatch.setattr(
        "bot.services.db.has_recent_ui_fallback",
        lambda exercise_id, hours: has_recent,
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
    inserts, dms = _setup(monkeypatch, has_recent=False)
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_missing", "surface": "mini-app", "component": "ExerciseRow", "pitcher_id": "p1"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1
    assert inserts[0]["exercise_id"] == "ex_missing"
    assert len(dms) == 1  # cold exercise → DM fires


def test_fallback_logs_row_but_rate_limits_dm(monkeypatch):
    inserts, dms = _setup(monkeypatch, has_recent=True)
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_repeated", "surface": "coach-app"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1  # still records every miss
    assert len(dms) == 0  # rate-limited — no DM
