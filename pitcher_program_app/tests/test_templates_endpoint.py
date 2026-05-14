"""Plan 7 / A12 — templates list endpoint tests.

Covers:
- response shape with no filters
- domain query param passes through to the helper
- phase query param passes through to the helper
- both filters compose
- domain regex enforces 'throwing|lifting' (422 on garbage)
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


def test_templates_endpoint_returns_all_when_no_filter(client):
    from bot.services import db as _db
    fake_rows = [
        {"block_template_id": "tpl_a", "name": "A", "domain": "throwing",
         "goal_tags": ["velocity"], "compatible_phases": ["off_season"]},
        {"block_template_id": "tpl_b", "name": "B", "domain": "lifting",
         "goal_tags": ["hypertrophy"], "compatible_phases": ["off_season"]},
    ]
    with patch.object(_db, "list_block_library_templates", return_value=fake_rows) as lst:
        resp = client.get(
            "/api/programs/templates",
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"templates": fake_rows}
    lst.assert_called_once_with(domain=None, phase=None)


def test_templates_endpoint_domain_filter(client):
    from bot.services import db as _db
    with patch.object(_db, "list_block_library_templates", return_value=[]) as lst:
        resp = client.get(
            "/api/programs/templates?domain=throwing",
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert lst.call_args.kwargs == {"domain": "throwing", "phase": None}


def test_templates_endpoint_phase_filter(client):
    from bot.services import db as _db
    with patch.object(_db, "list_block_library_templates", return_value=[]) as lst:
        resp = client.get(
            "/api/programs/templates?phase=off_season",
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert lst.call_args.kwargs == {"domain": None, "phase": "off_season"}


def test_templates_endpoint_domain_and_phase_filter(client):
    from bot.services import db as _db
    with patch.object(_db, "list_block_library_templates", return_value=[]) as lst:
        resp = client.get(
            "/api/programs/templates?domain=throwing&phase=off_season",
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert lst.call_args.kwargs == {"domain": "throwing", "phase": "off_season"}


def test_templates_endpoint_invalid_domain_returns_422(client):
    resp = client.get(
        "/api/programs/templates?domain=garbage",
        headers={"X-Test-Pitcher-Id": "landon_brice"},
    )
    assert resp.status_code == 422
