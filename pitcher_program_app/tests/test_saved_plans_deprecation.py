"""Tests for saved_plans soft-deprecation (Plan 7 / A15).

Covers two contracts:
1. `bot.services.db.insert_saved_plan` still writes through to Supabase
   (behavior preserved) AND emits a WARN-level deprecation log on every call.
2. The `POST /api/pitcher/{pitcher_id}/plans` endpoint still returns 200 +
   the plan AND attaches `Deprecation: true` + `Sunset` headers so the bot
   and admin tooling can confirm zero-writes ahead of Plan 8's hard drop.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Unit test: db.insert_saved_plan logs deprecation WARN
# ---------------------------------------------------------------------------

def test_insert_saved_plan_logs_deprecation_warning(caplog):
    """A new write to saved_plans should log a WARN-level deprecation event
    and still pass the row through to Supabase (no behavior regression).
    """
    from bot.services import db

    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": 42, "pitcher_id": "landon_brice", "plan_name": "test"}
    ]

    with caplog.at_level(logging.WARNING, logger="bot.services.db"):
        with patch.object(db, "get_client", return_value=fake_client):
            result = db.insert_saved_plan(
                "landon_brice",
                {"plan_name": "test"},
            )

    # Behavior preserved — row still returned.
    assert result == {"id": 42, "pitcher_id": "landon_brice", "plan_name": "test"}
    # Supabase insert still called once with the row (pitcher_id injected).
    fake_client.table.assert_called_once_with("saved_plans")
    insert_call = fake_client.table.return_value.insert.call_args
    assert insert_call.args[0]["pitcher_id"] == "landon_brice"
    assert insert_call.args[0]["plan_name"] == "test"
    # Deprecation log emitted.
    assert "saved_plans_deprecated_write" in caplog.text
    assert "landon_brice" in caplog.text
    # Must be WARN level, not ERROR (recoverable, not a failure).
    warn_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("saved_plans_deprecated_write" in r.getMessage() for r in warn_records)


# ---------------------------------------------------------------------------
# Integration test: POST /api/pitcher/{id}/plans returns deprecation headers
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    """TestClient with auth disabled, identical to other routes tests."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


def test_save_plan_endpoint_includes_deprecation_headers(client):
    """POST /api/pitcher/{id}/plans should return 200 with the saved plan
    and attach Deprecation + Sunset response headers so callers can detect
    that the endpoint is on the retirement path.
    """
    from api import routes as routes_mod

    saved = {
        "id": "plan-1",
        "title": "My plan",
        "active": True,
        "created_date": "2026-05-13",
    }
    # routes.py does `from bot.services.context_manager import save_plan`, so
    # the function is bound into the routes namespace at import time — patch
    # it there, not on context_manager.
    with patch.object(routes_mod, "save_plan", return_value=saved) as mock_save:
        resp = client.post(
            "/api/pitcher/landon_brice/plans",
            json={"title": "My plan", "category": "custom"},
        )

    # Behavior preserved — 200 + the saved plan.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["plan"] == saved
    mock_save.assert_called_once()

    # Deprecation headers attached on every successful write.
    assert resp.headers.get("Deprecation") == "true"
    sunset = resp.headers.get("Sunset", "")
    assert "Plan 8" in sunset
