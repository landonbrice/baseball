"""Plan 8 / A2 — admin program-flag endpoint.

Auth contract mirrors `/admin/guardian/*`:

* env unset → 503 (misconfigured deploy must surface visibly)
* header missing/wrong → 401
* path value invalid → 422
* pitcher row missing → 404
* otherwise → flips and returns the new value
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GUARDIAN_ADMIN_TOKEN", "test-token-xyz")
    from api.main import app
    return TestClient(app)


def test_set_flag_on_writes_true_and_returns_state(client):
    from bot.services import db
    with patch.object(db, "set_feature_flag") as set_flag, \
         patch("api.admin_program_flag._emit_flag_change_audit"):
        resp = client.post(
            "/admin/program-flag/landon_brice/on",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "pitcher_id": "landon_brice",
        "program_aware_plan_gen": True,
    }
    set_flag.assert_called_once_with(
        "landon_brice", "program_aware_plan_gen", True
    )


def test_set_flag_off_writes_false(client):
    from bot.services import db
    with patch.object(db, "set_feature_flag") as set_flag, \
         patch("api.admin_program_flag._emit_flag_change_audit"):
        resp = client.post(
            "/admin/program-flag/landon_brice/off",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json()["program_aware_plan_gen"] is False
    set_flag.assert_called_once_with(
        "landon_brice", "program_aware_plan_gen", False
    )


def test_set_flag_invalid_value_422(client):
    resp = client.post(
        "/admin/program-flag/landon_brice/garbage",
        headers={"X-Guardian-Admin-Token": "test-token-xyz"},
    )
    assert resp.status_code == 422


def test_set_flag_requires_admin_token(client):
    resp = client.post("/admin/program-flag/landon_brice/on")
    assert resp.status_code == 401


def test_set_flag_wrong_token_returns_401(client):
    resp = client.post(
        "/admin/program-flag/landon_brice/on",
        headers={"X-Guardian-Admin-Token": "WRONG"},
    )
    assert resp.status_code == 401


def test_set_flag_missing_pitcher_row_returns_404(client):
    from bot.services import db
    with patch.object(db, "set_feature_flag",
                      side_effect=KeyError("no pitcher_training_model row")):
        resp = client.post(
            "/admin/program-flag/ghost_pitcher/on",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 404
    assert "ghost_pitcher" in resp.json()["detail"]


def test_set_flag_503_when_admin_token_not_configured(monkeypatch):
    monkeypatch.delenv("GUARDIAN_ADMIN_TOKEN", raising=False)
    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/admin/program-flag/landon_brice/on",
        headers={"X-Guardian-Admin-Token": "anything"},
    )
    assert resp.status_code == 503


def test_get_flag_returns_current_value(client):
    from bot.services import db
    with patch.object(db, "get_feature_flag", return_value=True):
        resp = client.get(
            "/admin/program-flag/landon_brice",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "pitcher_id": "landon_brice",
        "program_aware_plan_gen": True,
    }


def test_get_flag_requires_admin_token(client):
    resp = client.get("/admin/program-flag/landon_brice")
    assert resp.status_code == 401


def test_set_flag_audit_failure_does_not_break_write(client):
    """Audit insert is best-effort — flag write must succeed even if Guardian
    Supabase insert raises. The endpoint wraps ``_emit_flag_change_audit`` in
    its own try/except, and ``_emit_flag_change_audit`` itself wraps the
    Supabase call. Patching the underlying store function exercises that
    real swallow path.
    """
    from bot.services import db
    with patch.object(db, "set_feature_flag") as set_flag, \
         patch(
             "bot.services.system_guardian.store.insert_observation",
             side_effect=RuntimeError("supabase down"),
         ):
        resp = client.post(
            "/admin/program-flag/landon_brice/on",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json()["program_aware_plan_gen"] is True
    set_flag.assert_called_once()
