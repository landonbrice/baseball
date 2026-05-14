"""Integration shape tests for /api/coach/programs/builder/* endpoints.

Mocks the service layer; exercises FastAPI wiring + coach team-scoping. Mirrors
test_program_builder_endpoints.py but for the coach-facing routes added in
Plan 2 Task 6.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient

import pytest


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


def test_coach_candidates_team_scope_check(client):
    """Pitcher on a different team -> 404 (opaque, not 403)."""
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher", return_value={"pitcher_id": "x", "team_id": "other_team"}):
        resp = client.post(
            "/api/coach/programs/builder/candidates",
            json={
                "pitcher_id": "x",
                "domain": "throwing",
                "goal": "velocity",
                "duration_weeks": 12,
                "effective_phase": "preseason",
                "hard_constraints": [],
            },
        )
    assert resp.status_code == 404


def test_coach_candidates_happy_path(client):
    from bot.services import program_builder
    from bot.services import db as _db
    candidates = [
        {"block_template_id": "tpl_a", "name": "A"},
        {"block_template_id": "tpl_b", "name": "B"},
    ]
    with patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(program_builder, "match_candidates", return_value=candidates), \
         patch.object(_db, "create_builder_session", return_value="sess-1") as create_mock:
        resp = client.post(
            "/api/coach/programs/builder/candidates",
            json={
                "pitcher_id": "p1",
                "domain": "throwing",
                "goal": "velocity",
                "duration_weeks": 12,
                "effective_phase": "preseason",
                "hard_constraints": [],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "sess-1"
    assert len(body["candidates"]) == 2
    payload = create_mock.call_args[0][0]
    assert payload["pitcher_id"] == "p1"
    assert payload["initiator_id"] == "dev_coach"
    assert payload["initiator_role"] == "coach"
    assert payload["interview_mode"] == "personalize"
    assert payload["candidate_template_ids"] == ["tpl_a", "tpl_b"]


def test_coach_generate_stamps_coach_authorship(client):
    from bot.services import program_generator
    from bot.services import db as _db

    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "p1",
        "candidate_template_ids": ["tpl_a", "tpl_b"],
        "constraint_envelope_json": {"domain": "throwing"},
    }
    program_row = {"program_id": "prog-1", "status": "draft"}

    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(_db, "update_builder_session"), \
         patch.object(program_generator, "generate_program", return_value=program_row) as gen_mock:
        resp = client.post(
            "/api/coach/programs/builder/generate",
            json={"session_id": "sess-1", "tuned_spec": {"weeks": 12}},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["program"]["program_id"] == "prog-1"
    kwargs = gen_mock.call_args.kwargs
    assert kwargs["pitcher_id"] == "p1"
    assert kwargs["template_id"] == "tpl_a"
    assert kwargs["constraint_envelope"]["created_by"] == "dev_coach"
    assert kwargs["constraint_envelope"]["created_by_role"] == "coach"


def test_coach_generate_session_pitcher_off_team_404(client):
    from bot.services import db as _db
    session_row = {
        "session_id": "sess-1",
        "pitcher_id": "p_other",
        "candidate_template_ids": ["tpl_a"],
        "constraint_envelope_json": {},
    }
    with patch.object(_db, "get_builder_session", return_value=session_row), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p_other", "team_id": "rival"}):
        resp = client.post(
            "/api/coach/programs/builder/generate",
            json={"session_id": "sess-1", "tuned_spec": {}},
        )
    assert resp.status_code == 404


def test_coach_activate_team_scope(client):
    from bot.services import program_lifecycle
    from bot.services import db as _db
    with patch.object(_db, "get_program", return_value={"program_id": "prog-1", "pitcher_id": "p1"}), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(program_lifecycle, "activate", return_value={"program_id": "prog-1", "status": "active"}) as act:
        resp = client.post("/api/coach/programs/prog-1/activate")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "active"
    act.assert_called_once_with("prog-1")


def test_coach_archive_passes_reason(client):
    from bot.services import program_lifecycle
    from bot.services import db as _db
    with patch.object(_db, "get_program", return_value={"program_id": "prog-1", "pitcher_id": "p1"}), \
         patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(program_lifecycle, "archive", return_value={"program_id": "prog-1", "status": "archived"}) as arc:
        resp = client.post(
            "/api/coach/programs/prog-1/archive",
            json={"reason": "superseded"},
        )
    assert resp.status_code == 200, resp.text
    arc.assert_called_once_with("prog-1", reason="superseded")


# ---------- Plan 7 / C4: three-mode candidates + interpret-goal mirror ----------


def test_coach_candidates_authoring_mode_no_pitcher(client):
    """interview_mode='authoring' has no associated pitcher. Session row stores
    pitcher_id=None and the matcher gets called with the bare envelope."""
    from bot.services import program_builder
    from bot.services import db as _db
    with patch.object(program_builder, "match_candidates", return_value=[{"block_template_id": "tpl_a"}]), \
         patch.object(_db, "create_builder_session", return_value="sess-auth") as create_mock:
        resp = client.post(
            "/api/coach/programs/builder/candidates",
            json={
                "interview_mode": "authoring",
                "domain": "lifting",
                "goal": "hypertrophy",
                "duration_weeks": 8,
                "effective_phase": "off_season",
                "hard_constraints": [],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "sess-auth"
    payload = create_mock.call_args[0][0]
    assert payload["pitcher_id"] is None
    assert payload["interview_mode"] == "authoring"


def test_coach_candidates_personalize_requires_pitcher(client):
    """interview_mode='personalize' without a pitcher_id → 422."""
    resp = client.post(
        "/api/coach/programs/builder/candidates",
        json={
            "interview_mode": "personalize",
            "domain": "throwing",
            "goal": "velocity",
            "duration_weeks": 12,
            "effective_phase": "preseason",
            "hard_constraints": [],
        },
    )
    assert resp.status_code == 422


def test_coach_candidates_personalize_with_personalize_pitcher_id(client):
    """personalize mode accepts `personalize_pitcher_id` as the canonical key.
    Session row records the pitcher_id and the mode."""
    from bot.services import program_builder
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher", return_value={"pitcher_id": "p1", "team_id": "uchicago_baseball"}), \
         patch.object(program_builder, "match_candidates", return_value=[]), \
         patch.object(_db, "create_builder_session", return_value="sess-p") as create_mock:
        resp = client.post(
            "/api/coach/programs/builder/candidates",
            json={
                "interview_mode": "personalize",
                "personalize_pitcher_id": "p1",
                "domain": "throwing",
                "goal": "velocity",
                "duration_weeks": 12,
                "effective_phase": "preseason",
                "hard_constraints": [],
            },
        )
    assert resp.status_code == 200, resp.text
    payload = create_mock.call_args[0][0]
    assert payload["pitcher_id"] == "p1"
    assert payload["interview_mode"] == "personalize"
    # Envelope-forwarded personalize_pitcher_id survives for the matcher / server prompts.
    assert payload["constraint_envelope_json"]["personalize_pitcher_id"] == "p1"


def test_coach_candidates_authoring_rejects_pitcher(client):
    """interview_mode='authoring' with a pitcher_id → 422 (pure template only)."""
    resp = client.post(
        "/api/coach/programs/builder/candidates",
        json={
            "interview_mode": "authoring",
            "personalize_pitcher_id": "p1",
            "domain": "lifting",
            "goal": "hypertrophy",
            "duration_weeks": 8,
            "effective_phase": "off_season",
            "hard_constraints": [],
        },
    )
    assert resp.status_code == 422


def test_coach_interpret_goal_mirrors_pitcher_endpoint(client):
    """Coach mirror of /programs/builder/interpret-goal — coach auth, same shape."""
    async def _stub(_text, _domain):
        return "velocity"
    with patch("bot.services.goal_interpreter.interpret_goal", new=_stub):
        resp = client.post(
            "/api/coach/programs/builder/interpret-goal",
            json={"text": "add a few miles to my fastball", "domain": "throwing"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"tag": "velocity", "confidence": "matched"}


def test_coach_interpret_goal_returns_unknown_confidence(client):
    """When interpreter returns 'unknown', confidence is 'unknown'."""
    async def _stub(_text, _domain):
        return "unknown"
    with patch("bot.services.goal_interpreter.interpret_goal", new=_stub):
        resp = client.post(
            "/api/coach/programs/builder/interpret-goal",
            json={"text": "make me a sandwich", "domain": "lifting"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"tag": "unknown", "confidence": "unknown"}
