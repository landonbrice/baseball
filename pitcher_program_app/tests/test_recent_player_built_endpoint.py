"""Plan 7 / C3 — coach recent-player-built programs endpoint.

Tests the new `GET /api/coach/programs/recent-player-built` route:
- happy path returns the row list under `{"programs": [...]}`
- the endpoint forwards team_id from the authenticated coach (not from the
  query string) and forwards `limit` to the db helper

NOTE: `DISABLE_AUTH=true` in `api/coach_auth.py` hardcodes the dev coach
identity (`coach_id=dev_coach`, `team_id=uchicago_baseball`). Same fixture
shape as `test_coach_program_list_endpoints.py`.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setattr(
        "api.coach_auth.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    return TestClient(app)


def test_recent_player_built_happy_path(client):
    from bot.services import db as _db

    rows = [
        {
            "program_id": "p1",
            "pitcher_id": "landon_brice",
            "pitcher_name": "Landon Brice",
            "parent_template_id": "velocity_12wk_v1",
            "domain": "throwing",
            "status": "active",
            "current_day_index": 5,
            "held_days_count": 0,
            "created_by": "landon_brice",
            "created_by_role": "pitcher",
            "created_at": "2026-05-12T10:00:00Z",
            "activated_at": "2026-05-12T10:01:00Z",
            "archived_at": None,
        },
    ]
    with patch.object(_db, "list_recent_player_built_programs", return_value=rows):
        resp = client.get("/api/coach/programs/recent-player-built")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"programs": rows}


def test_recent_player_built_uses_team_id_from_auth(client):
    """team_id comes from `request.state.team_id` (set by coach auth), and
    `limit` is forwarded from the query string."""
    from bot.services import db as _db

    with patch.object(
        _db, "list_recent_player_built_programs", return_value=[]
    ) as lst:
        resp = client.get("/api/coach/programs/recent-player-built?limit=5")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"programs": []}
    kwargs = lst.call_args.kwargs
    assert kwargs.get("team_id") == "uchicago_baseball"
    assert kwargs.get("limit") == 5
