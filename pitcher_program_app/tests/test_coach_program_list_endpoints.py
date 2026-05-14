"""Plan 7 / A3-coach integration tests.

Mirrors test_program_list_endpoints.py (pitcher-side A3) for the coach
mirror routes added in Plan 7. Mocks the service layer; exercises FastAPI
wiring + coach team-scoping.

NOTE on the spec's "403 on cross-team" acceptance criterion: this codebase's
canonical `_require_team_pitcher` helper raises 404 (not 403) on team
mismatch to keep ownership opaque — see `api/coach_routes.py:902` and
existing Plan 2 Task 6 coverage in `test_coach_program_builder_endpoints.py`.
The new coach mirror endpoints reuse `_require_team_pitcher`, so the
behaviour is 404 not 403. We follow the codebase pattern.

NOTE on the spec's `X-Test-Coach-Id` / `X-Test-Team-Id` headers: those don't
exist in this codebase. `DISABLE_AUTH=true` in `api/coach_auth.py` hardcodes
the dev coach identity (`coach_id=dev_coach`, `team_id=uchicago_baseball`).
We use the canonical fixture from test_coach_program_builder_endpoints.py.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # Stub team enrichment so coach auth dependency can resolve team_name in dev mode.
    monkeypatch.setattr(
        "api.coach_auth.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    return TestClient(app)


PID = "landon_brice"


# ----------------------------- /programs -----------------------------

def test_coach_programs_team_scoping_blocks_off_team_pitcher(client):
    """Cross-team pitcher → 404 (opaque per _require_team_pitcher contract)."""
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "outsider", "team_id": "other_team"}):
        resp = client.get("/api/coach/pitcher/outsider/programs")
    assert resp.status_code == 404


def test_coach_programs_returns_team_pitcher_list(client):
    from bot.services import db as _db
    rows = [{"program_id": "p1", "domain": "throwing", "status": "active"}]
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": PID,
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_programs_for_pitcher_summary",
                      return_value=rows) as lst:
        resp = client.get(f"/api/coach/pitcher/{PID}/programs")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"programs": rows}
    lst.assert_called_once_with(PID, status=None)


def test_coach_programs_status_filter_passes_through(client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": PID,
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_programs_for_pitcher_summary",
                      return_value=[]) as lst:
        resp = client.get(f"/api/coach/pitcher/{PID}/programs?status=draft")
    assert resp.status_code == 200, resp.text
    assert lst.call_args.kwargs["status"] == "draft"


# ----------------------------- /drafts -----------------------------

def test_coach_drafts_only_returns_completed_session_drafts(client):
    """D14 locked: in-flight Socratic sessions are NOT in the coach drafts view."""
    from bot.services import db as _db
    drafts = [{"program_id": "p1", "domain": "throwing", "status": "draft"}]
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": PID,
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_completed_session_drafts_for_pitcher",
                      return_value=drafts) as lst:
        resp = client.get(f"/api/coach/pitcher/{PID}/drafts")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"drafts": drafts}
    lst.assert_called_once_with(PID)
