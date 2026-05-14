"""Integration shape tests for /api/favorites endpoints (Plan 6 / A2).

Mocks the service layer; exercises only the FastAPI wiring (request/response
shape, auth, status codes). Matches the test_program_builder_endpoints style.
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
SNAPSHOT = {"exercises": [{"name": "Bench", "sets": 3, "reps": 5}]}


def test_post_favorite_happy_path(client):
    from bot.services import favorites as favorites_svc
    inserted = {
        "favorite_id": "fav-1",
        "pitcher_id": PID,
        "source_pitcher_id": PID,
        "source_entry_date": "2026-05-12",
        "block_type": "lifting",
        "block_snapshot_json": SNAPSHOT,
    }
    with patch.object(favorites_svc, "create_favorite", return_value=inserted) as cf:
        resp = client.post(
            "/api/favorites",
            json={
                "block_type": "lifting",
                "source_entry_date": "2026-05-12",
                "block_snapshot": SNAPSHOT,
            },
            headers={"X-Test-Pitcher-Id": PID},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == inserted
    kwargs = cf.call_args.kwargs
    assert kwargs["pitcher_id"] == PID
    assert kwargs["block_type"] == "lifting"
    assert kwargs["source_entry_date"] == "2026-05-12"
    assert kwargs["block_snapshot"] == SNAPSHOT
    assert kwargs["note"] is None


def test_post_favorite_accepts_note(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "create_favorite", return_value={"favorite_id": "fav-1"}) as cf:
        resp = client.post(
            "/api/favorites",
            json={
                "block_type": "arm_care",
                "source_entry_date": "2026-05-12",
                "block_snapshot": SNAPSHOT,
                "note": "loved this one",
            },
            headers={"X-Test-Pitcher-Id": PID},
        )
    assert resp.status_code == 200
    assert cf.call_args.kwargs["note"] == "loved this one"


def test_post_favorite_rejects_bad_block_type_at_pydantic_layer(client):
    resp = client.post(
        "/api/favorites",
        json={
            "block_type": "mobility",
            "source_entry_date": "2026-05-12",
            "block_snapshot": SNAPSHOT,
        },
        headers={"X-Test-Pitcher-Id": PID},
    )
    assert resp.status_code == 422


def test_post_favorite_rejects_bad_date_format_at_pydantic_layer(client):
    resp = client.post(
        "/api/favorites",
        json={
            "block_type": "lifting",
            "source_entry_date": "5/12/2026",
            "block_snapshot": SNAPSHOT,
        },
        headers={"X-Test-Pitcher-Id": PID},
    )
    assert resp.status_code == 422


def test_post_favorite_service_validation_returns_400(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "create_favorite",
                      side_effect=favorites_svc.FavoritesError("block_snapshot must be a non-empty object")):
        resp = client.post(
            "/api/favorites",
            json={
                "block_type": "lifting",
                "source_entry_date": "2026-05-12",
                "block_snapshot": {"any": "shape"},  # passes pydantic; service rejects
            },
            headers={"X-Test-Pitcher-Id": PID},
        )
    assert resp.status_code == 400
    assert "block_snapshot" in resp.json()["detail"]


def test_post_favorite_requires_auth(client, monkeypatch):
    # Flip DISABLE_AUTH back off for this test only
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", False)
    resp = client.post(
        "/api/favorites",
        json={
            "block_type": "lifting",
            "source_entry_date": "2026-05-12",
            "block_snapshot": SNAPSHOT,
        },
        # No initData, no test header
    )
    assert resp.status_code == 401


def test_get_favorites_returns_list(client):
    from bot.services import favorites as favorites_svc
    rows = [
        {"favorite_id": "f1", "block_type": "lifting", "favorited_at": "2026-05-12T10:00:00Z"},
        {"favorite_id": "f2", "block_type": "arm_care", "favorited_at": "2026-05-11T10:00:00Z"},
    ]
    with patch.object(favorites_svc, "list_favorites", return_value=rows) as lst:
        resp = client.get("/api/favorites", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"favorites": rows}
    lst.assert_called_once_with(PID, block_type=None)


def test_get_favorites_passes_type_filter(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "list_favorites", return_value=[]) as lst:
        resp = client.get("/api/favorites?type=lifting", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    lst.assert_called_once_with(PID, block_type="lifting")


def test_get_favorites_bad_type_returns_400(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "list_favorites",
                      side_effect=favorites_svc.FavoritesError("block_type must be one of …")):
        resp = client.get("/api/favorites?type=cardio", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 400


def test_delete_favorite_happy_path(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "delete_favorite", return_value=None) as dl:
        resp = client.delete("/api/favorites/fav-1", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    dl.assert_called_once_with(PID, "fav-1")


def test_delete_favorite_not_found_returns_404(client):
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "delete_favorite",
                      side_effect=favorites_svc.FavoriteNotFound("favorite not found")):
        resp = client.delete("/api/favorites/missing", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "favorite not found"


def test_delete_favorite_owned_by_another_returns_404(client):
    """Cross-pitcher delete attempt also yields 404 — keeps existence opaque."""
    from bot.services import favorites as favorites_svc
    with patch.object(favorites_svc, "delete_favorite",
                      side_effect=favorites_svc.FavoriteNotFound("favorite not found")):
        resp = client.delete("/api/favorites/someone-elses", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 404
