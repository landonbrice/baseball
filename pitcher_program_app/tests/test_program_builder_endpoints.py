"""Integration shape tests for /api/programs/builder/* endpoints.

Mocks the service layer; exercises only the FastAPI wiring (request shape, auth,
response shape). End-to-end tests live elsewhere (Plan 6 or QA).
"""
from unittest.mock import patch
from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def client(monkeypatch):
    # routes.py imports DISABLE_AUTH at module load time; flip both env and
    # the imported symbol so _require_pitcher_auth + the resolver short-circuit.
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


def test_post_builder_candidates_happy_path(client):
    from bot.services import program_builder
    from bot.services import db as _db
    candidates = [
        {"block_template_id": "tpl_a", "name": "A"},
        {"block_template_id": "tpl_b", "name": "B"},
    ]
    with patch.object(program_builder, "match_candidates", return_value=candidates), \
         patch.object(_db, "create_builder_session", return_value="sess-1") as create_mock:
        resp = client.post(
            "/api/programs/builder/candidates",
            json={
                "domain": "throwing",
                "goal": "velocity",
                "duration_weeks": 12,
                "effective_phase": "preseason",
                "hard_constraints": [],
            },
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "candidates" in body
    assert "session_id" in body
    assert body["session_id"] == "sess-1"
    assert len(body["candidates"]) == 2
    create_mock.assert_called_once()
    payload = create_mock.call_args[0][0]
    assert payload["pitcher_id"] == "landon_brice"
    assert payload["candidate_template_ids"] == ["tpl_a", "tpl_b"]
    assert payload["status"] == "in_progress"


def test_post_builder_generate_uses_first_candidate_in_v1(client):
    """Layer 2 stub: picks candidates[0]. Plan 3 will replace with Socratic flow."""
    from bot.services import program_generator
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "landon_brice",
        "candidate_template_ids": ["tpl_a", "tpl_b"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    program_row = {"program_id": "prog-1", "status": "draft"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "update_builder_session") as update_mock, \
         patch.object(program_generator, "generate_program", return_value=program_row) as gen_mock:
        resp = client.post(
            "/api/programs/builder/generate",
            json={"session_id": "sess-1", "tuned_spec": {"weeks": 12}},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["program"]["program_id"] == "prog-1"
    assert body["program"]["status"] == "draft"
    # v1 stub: chosen template is candidates[0]
    gen_kwargs = gen_mock.call_args.kwargs
    assert gen_kwargs["template_id"] == "tpl_a"
    assert gen_kwargs["pitcher_id"] == "landon_brice"
    assert gen_kwargs["session_id"] == "sess-1"
    update_mock.assert_called_once()
    patch_arg = update_mock.call_args[0][1]
    assert patch_arg["chosen_template_id"] == "tpl_a"
    assert patch_arg["status"] == "completed"
    assert patch_arg["generated_program_id"] == "prog-1"


def test_post_program_activate_returns_activation_result(client):
    from bot.services import program_lifecycle
    from bot.services import db as _db
    program_row = {"program_id": "prog-1", "pitcher_id": "landon_brice", "status": "draft"}
    with patch.object(_db, "get_program", return_value=program_row), \
         patch.object(program_lifecycle, "activate",
                      return_value={"activated": "prog-1", "archived": "prog-old"}):
        resp = client.post(
            "/api/programs/prog-1/activate",
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"activated": "prog-1", "archived": "prog-old"}


def test_post_program_archive_returns_archive_result(client):
    from bot.services import program_lifecycle
    from bot.services import db as _db
    program_row = {"program_id": "prog-1", "pitcher_id": "landon_brice", "status": "draft"}
    with patch.object(_db, "get_program", return_value=program_row), \
         patch.object(program_lifecycle, "archive", return_value={"archived": "prog-1"}):
        resp = client.post(
            "/api/programs/prog-1/archive",
            json={"reason": "user_cancelled"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"archived": "prog-1"}
