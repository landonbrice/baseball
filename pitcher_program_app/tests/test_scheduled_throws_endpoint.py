"""Plan 7 / A14 — scheduled-throws read endpoint tests.

Verifies:
- happy path returns throws sorted by date ASC
- empty state returns {scheduled_throws: []}
- auth gate blocks unauthenticated requests
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


PID = "landon_brice"


def test_scheduled_throws_returns_sorted_list(client):
    from bot.services import db as _db
    throws = [
        {"throw_id": "t3", "date": "2026-05-20", "kind": "bullpen"},
        {"throw_id": "t1", "date": "2026-05-14", "kind": "long_toss"},
        {"throw_id": "t2", "date": "2026-05-17", "kind": "mound"},
    ]
    with patch.object(_db, "get_pitcher_scheduled_throws", return_value=throws):
        resp = client.get(
            f"/api/pitcher/{PID}/scheduled-throws",
            headers={"X-Test-Pitcher-Id": PID},
        )
    assert resp.status_code == 200
    out = resp.json()["scheduled_throws"]
    assert [t["date"] for t in out] == ["2026-05-14", "2026-05-17", "2026-05-20"]
    # Original metadata preserved
    assert out[0]["kind"] == "long_toss"
    assert out[0]["throw_id"] == "t1"


def test_scheduled_throws_empty_returns_empty_list(client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher_scheduled_throws", return_value=[]):
        resp = client.get(
            f"/api/pitcher/{PID}/scheduled-throws",
            headers={"X-Test-Pitcher-Id": PID},
        )
    assert resp.status_code == 200
    assert resp.json() == {"scheduled_throws": []}


def test_scheduled_throws_requires_auth(client, monkeypatch):
    """With auth on and no init data, the endpoint rejects with 401."""
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", False)
    resp = client.get(f"/api/pitcher/{PID}/scheduled-throws")
    assert resp.status_code == 401
