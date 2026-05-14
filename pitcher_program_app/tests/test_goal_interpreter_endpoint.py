"""Endpoint tests for /api/programs/builder/interpret-goal (Plan 7 / A11)."""
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


def test_interpret_goal_endpoint_returns_tag(client):
    from bot.services import goal_interpreter
    with patch.object(goal_interpreter, "interpret_goal",
                      new=AsyncMock(return_value="velocity")):
        resp = client.post(
            "/api/programs/builder/interpret-goal",
            json={"text": "I want to throw harder", "domain": "throwing"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"tag": "velocity", "confidence": "matched"}


def test_interpret_goal_endpoint_unknown_confidence(client):
    from bot.services import goal_interpreter
    with patch.object(goal_interpreter, "interpret_goal",
                      new=AsyncMock(return_value="unknown")):
        resp = client.post(
            "/api/programs/builder/interpret-goal",
            json={"text": "blah", "domain": "throwing"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.json()["confidence"] == "unknown"


def test_interpret_goal_endpoint_validates_request(client):
    resp = client.post(
        "/api/programs/builder/interpret-goal",
        json={"text": "", "domain": "throwing"},  # empty text fails min_length
        headers={"X-Test-Pitcher-Id": "landon_brice"},
    )
    assert resp.status_code == 422
