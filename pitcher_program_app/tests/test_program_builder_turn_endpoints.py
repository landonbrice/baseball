"""Integration shape tests for /api/programs/builder/{turn,finalize} endpoints.

Mocks the service layer; exercises FastAPI wiring (request shape, auth,
session ownership, response shape). Mirrors the patterns in
test_program_builder_endpoints.py and test_coach_program_builder_endpoints.py.
"""
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


@pytest.fixture
def coach_client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setattr(
        "api.coach_auth.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    return TestClient(app)


# ---------- Pitcher /turn ----------

def test_post_builder_turn_returns_question(client):
    """When the LLM responds with a question, /turn returns it directly."""
    from bot.services import program_builder_socratic
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "landon_brice",
        "candidate_template_ids": ["tpl_a"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    advance_result = {"kind": "question", "text": "How many days per week do you throw?"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(program_builder_socratic, "advance",
                      new=AsyncMock(return_value=advance_result)):
        resp = client.post(
            "/api/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "I want to add velocity."},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "question"
    assert body["text"].startswith("How many days")


def test_post_builder_turn_returns_ready(client):
    """When the LLM signals READY_TO_GENERATE, /turn returns the ready payload."""
    from bot.services import program_builder_socratic
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "landon_brice",
        "candidate_template_ids": ["tpl_a", "tpl_b"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    advance_result = {
        "kind": "ready",
        "chosen_template_id": "tpl_a",
        "tuned_spec": {"weeks": 12},
    }

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(program_builder_socratic, "advance",
                      new=AsyncMock(return_value=advance_result)):
        resp = client.post(
            "/api/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "Sounds good."},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "ready"
    assert body["chosen_template_id"] == "tpl_a"
    assert body["tuned_spec"] == {"weeks": 12}


def test_post_builder_turn_session_off_pitcher_404(client):
    """Session owned by another pitcher -> 404 (opaque, not 403)."""
    from bot.services import db as _db

    session_row = {"session_id": "sess-1", "pitcher_id": "someone_else"}
    with patch.object(_db, "get_builder_session", return_value=session_row):
        resp = client.post(
            "/api/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "hi"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 404


def test_post_builder_turn_lookuperror_maps_to_404(client):
    from bot.services import program_builder_socratic
    from bot.services import db as _db

    session_row = {"session_id": "sess-1", "pitcher_id": "landon_brice",
                   "candidate_template_ids": ["tpl_a"], "constraint_envelope_json": {}}
    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(program_builder_socratic, "advance",
                      new=AsyncMock(side_effect=LookupError("expired"))):
        resp = client.post(
            "/api/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "hi"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 404


def test_post_builder_turn_valueerror_maps_to_400(client):
    from bot.services import program_builder_socratic
    from bot.services import db as _db

    session_row = {"session_id": "sess-1", "pitcher_id": "landon_brice",
                   "candidate_template_ids": ["tpl_a"], "constraint_envelope_json": {}}
    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(program_builder_socratic, "advance",
                      new=AsyncMock(side_effect=ValueError("already completed"))):
        resp = client.post(
            "/api/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "hi"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 400


# ---------- Pitcher /finalize ----------

def test_post_builder_finalize_calls_generate_and_completes(client):
    from bot.services import program_generator
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "landon_brice",
        "candidate_template_ids": ["tpl_a"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    program_row = {"program_id": "prog-1", "status": "draft"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "update_builder_session") as update_mock, \
         patch.object(program_generator, "generate_program", return_value=program_row) as gen_mock:
        resp = client.post(
            "/api/programs/builder/finalize",
            json={
                "session_id": "sess-1",
                "chosen_template_id": "tpl_a",
                "tuned_spec": {"weeks": 12},
            },
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["program"]["program_id"] == "prog-1"
    kwargs = gen_mock.call_args.kwargs
    assert kwargs["pitcher_id"] == "landon_brice"
    assert kwargs["template_id"] == "tpl_a"
    assert kwargs["tuned_spec"] == {"weeks": 12}
    assert kwargs["session_id"] == "sess-1"
    update_mock.assert_called_once()
    patch_arg = update_mock.call_args[0][1]
    assert patch_arg["chosen_template_id"] == "tpl_a"
    assert patch_arg["status"] == "completed"
    assert patch_arg["generated_program_id"] == "prog-1"
    assert patch_arg["tuned_spec_json"] == {"weeks": 12}


def test_post_builder_finalize_session_off_pitcher_404(client):
    from bot.services import db as _db
    session_row = {"session_id": "sess-1", "pitcher_id": "someone_else"}
    with patch.object(_db, "get_builder_session", return_value=session_row):
        resp = client.post(
            "/api/programs/builder/finalize",
            json={"session_id": "sess-1", "chosen_template_id": "tpl_a", "tuned_spec": {}},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 404


# ---------- Coach mirrors ----------

def test_coach_post_builder_turn_team_scope(coach_client):
    """Session belongs to a pitcher on a different team -> 404."""
    from bot.services import db as _db
    session_row = {"session_id": "sess-1", "pitcher_id": "p_other"}
    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p_other", "team_id": "rival"}):
        resp = coach_client.post(
            "/api/coach/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "hi"},
        )
    assert resp.status_code == 404


def test_coach_post_builder_turn_happy_path(coach_client):
    from bot.services import program_builder_socratic
    from bot.services import db as _db

    session_row = {"session_id": "sess-1", "pitcher_id": "p1",
                   "candidate_template_ids": ["tpl_a"], "constraint_envelope_json": {}}
    advance_result = {"kind": "question", "text": "How many sessions per week?"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(program_builder_socratic, "advance",
                      new=AsyncMock(return_value=advance_result)):
        resp = coach_client.post(
            "/api/coach/programs/builder/turn",
            json={"session_id": "sess-1", "user_message": "go"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "question"


def test_coach_post_builder_finalize_stamps_coach_authorship(coach_client):
    from bot.services import program_generator
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "p1",
        "candidate_template_ids": ["tpl_a"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    program_row = {"program_id": "prog-1", "status": "draft"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(_db, "update_builder_session"), \
         patch.object(program_generator, "generate_program", return_value=program_row) as gen_mock:
        resp = coach_client.post(
            "/api/coach/programs/builder/finalize",
            json={"session_id": "sess-1", "chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 12}},
        )
    assert resp.status_code == 200, resp.text
    kwargs = gen_mock.call_args.kwargs
    assert kwargs["template_id"] == "tpl_a"
    assert kwargs["pitcher_id"] == "p1"
    assert kwargs["constraint_envelope"]["created_by"] == "dev_coach"
    assert kwargs["constraint_envelope"]["created_by_role"] == "coach"
