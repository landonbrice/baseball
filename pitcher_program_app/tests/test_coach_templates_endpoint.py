"""Plan 7 / C3 hotfix — coach mirror of /api/programs/templates.

The pitcher-facing GET /api/programs/templates uses
`_resolve_pitcher_id_from_request`, which only accepts Telegram initData
or the `X-Test-Pitcher-Id` test header — it does NOT validate Supabase
Bearer JWTs. So coach-app's TeamPrograms Library section was silently
rendering an error state in prod.

The coach mirror at `GET /api/coach/programs/templates` uses
`require_coach_auth`. Same query params (`domain`, `phase`), same shape
(`{"templates": [...]}`), reuses `_db.list_block_library_templates`.

Auth conventions match `test_recent_player_built_endpoint.py`:
- `DISABLE_AUTH=true` short-circuits coach auth to the dev coach identity
- absence of `DISABLE_AUTH` + no Bearer token returns 401
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


@pytest.fixture
def authed_client(monkeypatch):
    """Client with auth NOT disabled — used to assert 401 on missing token."""
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    from api.main import app
    return TestClient(app)


def test_coach_templates_happy_path(client):
    """Coach JWT (via DISABLE_AUTH dev shim) → 200 with templates list."""
    from bot.services import db as _db

    fake_rows = [
        {
            "block_template_id": "velocity_12wk_v1",
            "name": "Velocity 12 Week",
            "domain": "throwing",
            "goal_tags": ["velocity"],
            "compatible_phases": ["off_season"],
            "duration_range_weeks": [10, 14],
            "implied_phase": "off_season",
        },
        {
            "block_template_id": "longtoss_6wk_v1",
            "name": "Long Toss 6 Week",
            "domain": "throwing",
            "goal_tags": ["arm_health", "endurance"],
            "compatible_phases": ["preseason"],
            "duration_range_weeks": [4, 8],
            "implied_phase": "preseason",
        },
    ]
    with patch.object(_db, "list_block_library_templates", return_value=fake_rows) as lst:
        resp = client.get("/api/coach/programs/templates")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"templates": fake_rows}
    lst.assert_called_once_with(domain=None, phase=None)


def test_coach_templates_domain_filter_passes_through(client):
    """`?domain=throwing` is forwarded to the db helper."""
    from bot.services import db as _db

    with patch.object(_db, "list_block_library_templates", return_value=[]) as lst:
        resp = client.get("/api/coach/programs/templates?domain=throwing")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"templates": []}
    assert lst.call_args.kwargs == {"domain": "throwing", "phase": None}


def test_coach_templates_phase_filter_passes_through(client):
    """`?phase=off_season` is forwarded to the db helper."""
    from bot.services import db as _db

    with patch.object(_db, "list_block_library_templates", return_value=[]) as lst:
        resp = client.get("/api/coach/programs/templates?phase=off_season")
    assert resp.status_code == 200, resp.text
    assert lst.call_args.kwargs == {"domain": None, "phase": "off_season"}


def test_coach_templates_invalid_domain_returns_422(client):
    """domain regex enforces `throwing|lifting`."""
    resp = client.get("/api/coach/programs/templates?domain=garbage")
    assert resp.status_code == 422


def test_coach_templates_requires_coach_auth(authed_client):
    """No Bearer header → 401. This is the exact failure mode the hotfix fixes."""
    resp = authed_client.get("/api/coach/programs/templates")
    assert resp.status_code == 401
