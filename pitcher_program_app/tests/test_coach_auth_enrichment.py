"""Tests D1, D18: coach auth exchange returns team_name; /me stays identity-shaped."""
import os
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_auth_exchange_includes_team_name(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # Mock the team lookup
    monkeypatch.setattr(
        "bot.services.db.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.post("/api/coach/auth/exchange")
    assert res.status_code == 200
    body = res.json()
    assert body["team_name"] == "UChicago Baseball"
    assert body["coach_id"] == "dev_coach"
    assert body["team_id"] == "uchicago_baseball"


def test_coach_me_stays_identity_shaped(monkeypatch):
    """D18: /me does NOT include team_name."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setattr(
        "bot.services.db.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.get("/api/coach/me")
    assert res.status_code == 200
    body = res.json()
    assert "team_name" not in body
