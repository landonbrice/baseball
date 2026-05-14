"""Plan 7 / C2: phase-override + program-holds endpoint tests.

Mirrors the patterns in test_coach_program_list_endpoints.py:
- DISABLE_AUTH=true with a stubbed team enrichment so coach auth resolves
  to coach_id=dev_coach, team_id=uchicago_baseball.
- _require_team_pitcher cross-team check returns 404 (not 403) per the
  codebase's "opaque ownership" pattern. We follow that.
- DB layer is patched at module scope; we don't hit Supabase.
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


PID = "landon_brice"
TEAM_PITCHER = {"pitcher_id": PID, "team_id": "uchicago_baseball"}


# ----------------------- /phase-override -----------------------


def test_phase_override_writes_both_phases_and_audits(client):
    """Happy path: both phases set, audit row inserted, response is canonical envelope."""
    from bot.services import db as _db
    new_overrides = {"throwing_phase": "off_season", "lifting_phase": "strength"}
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "update_coach_phase_overrides", return_value=new_overrides) as upd, \
         patch.object(_db, "insert_coach_action", return_value={"id": 1}) as audit:
        resp = client.patch(
            f"/api/coach/pitcher/{PID}/phase-override",
            json={"throwing_phase": "off_season", "lifting_phase": "strength"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"coach_phase_overrides": new_overrides}
    upd.assert_called_once_with(PID, throwing_phase="off_season", lifting_phase="strength")
    # Audit row inserted with action_type=phase_override and the request metadata.
    audit.assert_called_once()
    arg = audit.call_args[0][0]
    assert arg["coach_id"] == "dev_coach"
    assert arg["pitcher_id"] == PID
    assert arg["action_type"] == "phase_override"
    assert arg["metadata"]["team_id"] == "uchicago_baseball"
    assert arg["metadata"]["new_overrides"] == new_overrides
    assert arg["metadata"]["source_request"] == {
        "throwing_phase": "off_season",
        "lifting_phase": "strength",
    }


def test_phase_override_one_phase_only_passes_through(client):
    """Partial update — only throwing_phase. lifting_phase stays None in the request."""
    from bot.services import db as _db
    new_overrides = {"throwing_phase": "preseason", "lifting_phase": None}
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "update_coach_phase_overrides", return_value=new_overrides) as upd, \
         patch.object(_db, "insert_coach_action", return_value={"id": 2}):
        resp = client.patch(
            f"/api/coach/pitcher/{PID}/phase-override",
            json={"throwing_phase": "preseason"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["coach_phase_overrides"] == new_overrides
    upd.assert_called_once_with(PID, throwing_phase="preseason", lifting_phase=None)


def test_phase_override_422_when_both_phases_none(client):
    """Spec: at least one of throwing_phase / lifting_phase must be set."""
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "update_coach_phase_overrides") as upd, \
         patch.object(_db, "insert_coach_action") as audit:
        resp = client.patch(f"/api/coach/pitcher/{PID}/phase-override", json={})
    assert resp.status_code == 422, resp.text
    upd.assert_not_called()
    audit.assert_not_called()


def test_phase_override_blocks_cross_team_pitcher(client):
    """_require_team_pitcher returns 404 (opaque) on team mismatch."""
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "outsider", "team_id": "other_team"}), \
         patch.object(_db, "update_coach_phase_overrides") as upd, \
         patch.object(_db, "insert_coach_action") as audit:
        resp = client.patch(
            "/api/coach/pitcher/outsider/phase-override",
            json={"throwing_phase": "off_season"},
        )
    assert resp.status_code == 404
    upd.assert_not_called()
    audit.assert_not_called()


def test_phase_override_succeeds_when_audit_insert_fails(client):
    """Audit insert is best-effort — the override is the canonical write."""
    from bot.services import db as _db
    new_overrides = {"throwing_phase": "in_season", "lifting_phase": None}
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "update_coach_phase_overrides", return_value=new_overrides), \
         patch.object(_db, "insert_coach_action", side_effect=RuntimeError("supabase down")):
        resp = client.patch(
            f"/api/coach/pitcher/{PID}/phase-override",
            json={"throwing_phase": "in_season"},
        )
    assert resp.status_code == 200
    assert resp.json()["coach_phase_overrides"] == new_overrides


# ----------------------- /program-holds -----------------------


def test_program_holds_returns_pitcher_events(client):
    from bot.services import db as _db
    events = [
        {"hold_event_id": "h1", "program_id": "p1", "hold_date": "2026-05-10",
         "triage_result": {}, "reason_code": "red", "created_at": "2026-05-10T12:00:00Z"},
    ]
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "list_program_holds_for_pitcher", return_value=events) as lst:
        resp = client.get(f"/api/coach/pitcher/{PID}/program-holds")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"events": events}
    lst.assert_called_once_with(PID, days=30)


def test_program_holds_days_query_passes_through(client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher", return_value=TEAM_PITCHER), \
         patch.object(_db, "list_program_holds_for_pitcher", return_value=[]) as lst:
        resp = client.get(f"/api/coach/pitcher/{PID}/program-holds?days=7")
    assert resp.status_code == 200
    lst.assert_called_once_with(PID, days=7)


def test_program_holds_blocks_cross_team_pitcher(client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "outsider", "team_id": "other_team"}), \
         patch.object(_db, "list_program_holds_for_pitcher") as lst:
        resp = client.get("/api/coach/pitcher/outsider/program-holds")
    assert resp.status_code == 404
    lst.assert_not_called()
