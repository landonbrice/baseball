"""Tests D1, D18: coach auth exchange returns team_name; /me stays identity-shaped."""
from fastapi.testclient import TestClient


def test_auth_exchange_includes_team_name(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # Patch at the consumption site so the already-bound name in api.coach_auth is replaced.
    monkeypatch.setattr(
        "api.coach_auth.get_team",
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
        "api.coach_auth.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.get("/api/coach/me")
    assert res.status_code == 200
    body = res.json()
    assert "team_name" not in body


def test_auth_exchange_real_jwt_branch(monkeypatch):
    """D1, D18: real-JWT path (DISABLE_AUTH=false) enriches exchange response with team_name."""
    monkeypatch.setenv("DISABLE_AUTH", "false")
    # Stub _validate_coach_jwt so no real Supabase JWT verification happens.
    monkeypatch.setattr(
        "api.coach_auth._validate_coach_jwt",
        lambda request: {
            "coach_id": "c1",
            "team_id": "uchicago_baseball",
            "name": "Coach Test",
            "role": "head",
        },
    )
    # Stub get_team at the consumption site.
    monkeypatch.setattr(
        "api.coach_auth.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.post(
        "/api/coach/auth/exchange",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["team_name"] == "UChicago Baseball"
    assert body["coach_id"] == "c1"
    assert body["team_id"] == "uchicago_baseball"
