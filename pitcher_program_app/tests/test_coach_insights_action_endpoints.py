"""Plan 8 / C1 — insight action endpoint tests.

Covers POST /api/coach/insights/{insight_id}/action — the unified
accept/dismiss CTA wired in by Plan 8 C1. Mocks the db layer; exercises
FastAPI wiring + team-scoping + audit-row shape.

NOTE: `DISABLE_AUTH=true` hardcodes the dev coach identity in
api/coach_auth.py (coach_id=dev_coach, team_id=uchicago_baseball);
X-Test-Coach-Id headers are not a thing in this codebase.

Also covers the suggestion_exists_for_today 14-day suppression extension
that powers the dedup gate on the 9am digest path.
"""
from unittest.mock import patch, MagicMock

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


SUG_BASE = {
    "suggestion_id": "sug-1",
    "category": "program_drift",
    "pitcher_id": "landon_brice",
    "team_id": "uchicago_baseball",
    "title": "drifted",
    "reasoning": "8d behind",
    "proposed_action": {"program_id": "prog_abc"},
    "status": "pending",
}


def test_accept_writes_accepted_status_and_timestamp(client):
    from bot.services import db as _db
    with patch.object(_db, "get_coach_suggestion", return_value=SUG_BASE), \
         patch.object(_db, "update_coach_suggestion_status",
                      return_value={**SUG_BASE, "status": "accepted",
                                    "accepted_at": "2026-05-15T00:00:00+00:00"}) as upd, \
         patch.object(_db, "insert_coach_action"):
        resp = client.post("/api/coach/insights/sug-1/action",
                           json={"action": "accept"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["insight"]["status"] == "accepted"
    _, kwargs = upd.call_args
    assert kwargs["status"] == "accepted"
    assert kwargs["accepted_at"] is not None


def test_dismiss_writes_dismissed_status_and_null_timestamp(client):
    from bot.services import db as _db
    with patch.object(_db, "get_coach_suggestion",
                      return_value={**SUG_BASE, "suggestion_id": "sug-2"}), \
         patch.object(_db, "update_coach_suggestion_status",
                      return_value={**SUG_BASE, "suggestion_id": "sug-2",
                                    "status": "dismissed"}) as upd, \
         patch.object(_db, "insert_coach_action"):
        resp = client.post("/api/coach/insights/sug-2/action",
                           json={"action": "dismiss"})
    assert resp.status_code == 200, resp.text
    _, kwargs = upd.call_args
    assert kwargs["status"] == "dismissed"
    assert kwargs["accepted_at"] is None


def test_cross_team_returns_404(client):
    from bot.services import db as _db
    other_team = {**SUG_BASE, "suggestion_id": "sug-3", "team_id": "other_team"}
    with patch.object(_db, "get_coach_suggestion", return_value=other_team):
        resp = client.post("/api/coach/insights/sug-3/action",
                           json={"action": "dismiss"})
    assert resp.status_code == 404


def test_unknown_insight_returns_404(client):
    from bot.services import db as _db
    with patch.object(_db, "get_coach_suggestion", return_value=None):
        resp = client.post("/api/coach/insights/nonexistent/action",
                           json={"action": "dismiss"})
    assert resp.status_code == 404


def test_invalid_action_returns_422(client):
    resp = client.post("/api/coach/insights/sug-1/action",
                       json={"action": "snooze"})
    assert resp.status_code == 422


def test_audit_row_inserted_on_accept(client):
    from bot.services import db as _db
    sug = {**SUG_BASE, "suggestion_id": "sug-5"}
    with patch.object(_db, "get_coach_suggestion", return_value=sug), \
         patch.object(_db, "update_coach_suggestion_status",
                      return_value={**sug, "status": "accepted"}), \
         patch.object(_db, "insert_coach_action") as audit:
        client.post("/api/coach/insights/sug-5/action",
                    json={"action": "accept"})
    audit.assert_called_once()
    payload = audit.call_args.args[0]
    assert payload["action_type"] == "insight_accepted"
    assert payload["pitcher_id"] == "landon_brice"
    assert payload["metadata"]["insight_id"] == "sug-5"
    assert payload["metadata"]["team_id"] == "uchicago_baseball"
    assert payload["metadata"]["category"] == "program_drift"


def test_audit_row_inserted_on_dismiss(client):
    from bot.services import db as _db
    sug = {**SUG_BASE, "suggestion_id": "sug-6"}
    with patch.object(_db, "get_coach_suggestion", return_value=sug), \
         patch.object(_db, "update_coach_suggestion_status",
                      return_value={**sug, "status": "dismissed"}), \
         patch.object(_db, "insert_coach_action") as audit:
        client.post("/api/coach/insights/sug-6/action",
                    json={"action": "dismiss"})
    audit.assert_called_once()
    payload = audit.call_args.args[0]
    assert payload["action_type"] == "insight_dismissed"


# -- Plan 8 / C1 dedup-suppression invariant ------------------------------

def _build_chain_mock(responses):
    """Build a chained-call mock for the Supabase fluent client.

    `responses` is a list of (.data, .data, ...) tuples returned by
    successive .execute() calls. The mock allows arbitrary .eq()/.gte()/
    .select() chaining and only intercepts the terminal .execute().
    """
    call_index = {"i": 0}

    def make_terminal():
        node = MagicMock()
        node.eq.return_value = node
        node.gte.return_value = node
        node.select.return_value = node
        node.lt.return_value = node

        def execute():
            i = call_index["i"]
            call_index["i"] += 1
            ret = MagicMock()
            ret.data = responses[i] if i < len(responses) else []
            return ret

        node.execute.side_effect = execute
        return node

    table_node = make_terminal()
    client = MagicMock()
    client.table.return_value = table_node
    return client


def test_suggestion_exists_for_today_suppresses_recently_accepted(monkeypatch):
    """A matching insight with status='accepted' AND accepted_at within
    the last 14d suppresses today's re-fire even when no row was inserted
    today."""
    from bot.services import db

    # First execute() call (today-check) returns empty; second (accepted-
    # cutoff check) returns a recently-accepted row with matching context.
    client = _build_chain_mock([
        [],  # today-window query → 0 rows
        [{"suggestion_id": "old-1",
          "proposed_action": {"program_id": "prog_abc"}}],  # accepted query
    ])
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.suggestion_exists_for_today(
        "landon_brice",
        "program_drift",
        context_program_id="prog_abc",
    )
    assert result is True


def test_suggestion_exists_for_today_does_not_suppress_when_no_match(monkeypatch):
    """When neither today nor accepted-14d has a row, returns False."""
    from bot.services import db

    client = _build_chain_mock([[], []])
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.suggestion_exists_for_today(
        "landon_brice",
        "program_drift",
        context_program_id="prog_abc",
    )
    assert result is False


def test_suggestion_exists_for_today_today_path_still_wins(monkeypatch):
    """A row found in the today window short-circuits (doesn't query the
    accepted-14d table). Existing Plan 7 A4 contract preserved."""
    from bot.services import db

    client = _build_chain_mock([
        [{"suggestion_id": "today-1",
          "proposed_action": {"program_id": "prog_abc"}}],
    ])
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.suggestion_exists_for_today(
        "landon_brice",
        "program_drift",
        context_program_id="prog_abc",
    )
    assert result is True
