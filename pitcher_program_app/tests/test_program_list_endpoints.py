"""Integration tests for /api/programs/{drafts,history,active} (Plan 6 / A3).

Covers:
- response shape per endpoint (list vs domain-keyed object)
- db helper called with the right status + order_by
- auth required
- empty results return well-formed payloads (no nulls/missing keys)
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


# ----------------------------- /drafts -----------------------------

def test_get_drafts_returns_list(client):
    from bot.services import db as _db
    rows = [
        {"program_id": "p1", "status": "draft", "domain": "throwing",
         "created_at": "2026-05-12T10:00:00Z"},
        {"program_id": "p2", "status": "draft", "domain": "lifting",
         "created_at": "2026-05-11T10:00:00Z"},
    ]
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=rows) as lst:
        resp = client.get("/api/programs/drafts", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"drafts": rows}
    lst.assert_called_once_with(PID, status="draft")


def test_get_drafts_empty(client):
    from bot.services import db as _db
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=[]):
        resp = client.get("/api/programs/drafts", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"drafts": []}


def test_get_drafts_requires_auth(client, monkeypatch):
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", False)
    resp = client.get("/api/programs/drafts")  # no auth header
    assert resp.status_code == 401


# ----------------------------- /history -----------------------------

def test_get_history_orders_by_archived_at(client):
    from bot.services import db as _db
    rows = [
        {"program_id": "p1", "status": "archived", "archived_at": "2026-05-01T10:00:00Z"},
        {"program_id": "p2", "status": "archived", "archived_at": "2026-04-15T10:00:00Z"},
    ]
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=rows) as lst:
        resp = client.get("/api/programs/history", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"history": rows}
    lst.assert_called_once_with(PID, status="archived", order_by="archived_at")


def test_get_history_empty(client):
    from bot.services import db as _db
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=[]):
        resp = client.get("/api/programs/history", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"history": []}


# ----------------------------- /active -----------------------------

def test_get_active_buckets_both_domains(client):
    from bot.services import db as _db
    throwing = {"program_id": "p1", "status": "active", "domain": "throwing",
                "current_day_index": 22, "held_days_count": 1}
    lifting = {"program_id": "p2", "status": "active", "domain": "lifting",
               "current_day_index": 8, "held_days_count": 0}
    with patch.object(_db, "list_programs_for_pitcher_summary",
                      return_value=[throwing, lifting]) as lst:
        resp = client.get("/api/programs/active", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"throwing": throwing, "lifting": lifting}
    lst.assert_called_once_with(PID, status="active")


def test_get_active_one_domain_only_other_is_null(client):
    """Throwing active, lifting absent — payload still has both keys."""
    from bot.services import db as _db
    throwing = {"program_id": "p1", "status": "active", "domain": "throwing"}
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=[throwing]):
        resp = client.get("/api/programs/active", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"throwing": throwing, "lifting": None}
    # Both keys present so the UI can `data.lifting === null` safely
    assert "lifting" in body


def test_get_active_no_active_programs(client):
    from bot.services import db as _db
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=[]):
        resp = client.get("/api/programs/active", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"throwing": None, "lifting": None}


def test_get_active_ignores_unknown_domain(client):
    """Defensive: if the DB ever returns an unexpected domain value, we don't blow up."""
    from bot.services import db as _db
    weird = {"program_id": "p1", "status": "active", "domain": "mobility"}
    with patch.object(_db, "list_programs_for_pitcher_summary", return_value=[weird]):
        resp = client.get("/api/programs/active", headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json() == {"throwing": None, "lifting": None}
