"""Plan 8 / C3 — coach research doc attach endpoint tests.

Mirrors the patterns in test_phase_override_endpoint.py:
- DISABLE_AUTH=true with a stubbed team enrichment so coach auth resolves
  to coach_id=dev_coach, team_id=uchicago_baseball.
- DB layer is patched at module scope; we don't hit Supabase.

Coverage:
1. List endpoint happy path
2. PATCH happy path (audit row written with correct shape)
3. PATCH 422 on unknown doc ids
4. PATCH 404 on unknown template
5. PATCH with empty list clears attachments
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


def test_list_research_docs_happy_path(client):
    """GET /api/coach/research-docs returns the on-disk doc list."""
    from bot.services import db as _db
    fake_docs = [
        {"id": "doc1", "title": "Doc 1", "summary": "s1",
         "applies_to": [], "priority": "high"},
        {"id": "doc2", "title": "Doc 2", "summary": "s2",
         "applies_to": ["elbow"], "priority": "standard"},
    ]
    with patch.object(_db, "list_research_docs", return_value=fake_docs):
        resp = client.get("/api/coach/research-docs")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"docs": fake_docs}


def test_patch_template_research_docs_happy(client):
    """PATCH validates ids, calls db.update_..., audits with action_type."""
    from bot.services import db as _db
    fake_docs = [{"id": "doc1"}, {"id": "doc2"}]
    updated = {"block_template_id": "tpl_a", "name": "Template A",
               "research_doc_ids": ["doc1", "doc2"]}
    with patch.object(_db, "list_research_docs", return_value=fake_docs), \
         patch.object(_db, "update_template_research_doc_ids",
                      return_value=updated) as upd, \
         patch.object(_db, "insert_coach_action") as audit:
        resp = client.patch(
            "/api/coach/block-library/tpl_a/research-docs",
            json={"research_doc_ids": ["doc1", "doc2"]},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"template": updated}
    upd.assert_called_once_with("tpl_a", ["doc1", "doc2"])
    audit.assert_called_once()
    arg = audit.call_args.args[0]
    assert arg["coach_id"] == "dev_coach"
    assert arg["action_type"] == "template_research_docs_edit"
    assert arg["metadata"] == {
        "template_id": "tpl_a",
        "doc_ids": ["doc1", "doc2"],
    }


def test_patch_unknown_doc_id_returns_422(client):
    """Any submitted id outside the canonical set → 422 with the bad ids surfaced."""
    from bot.services import db as _db
    with patch.object(_db, "list_research_docs",
                      return_value=[{"id": "doc1"}]), \
         patch.object(_db, "update_template_research_doc_ids") as upd, \
         patch.object(_db, "insert_coach_action") as audit:
        resp = client.patch(
            "/api/coach/block-library/tpl_a/research-docs",
            json={"research_doc_ids": ["doc1", "doc_nope"]},
        )
    assert resp.status_code == 422, resp.text
    assert "doc_nope" in resp.json()["detail"]
    upd.assert_not_called()
    audit.assert_not_called()


def test_patch_unknown_template_returns_404(client):
    """db raises KeyError on no-match → endpoint translates to 404."""
    from bot.services import db as _db
    with patch.object(_db, "list_research_docs",
                      return_value=[{"id": "doc1"}]), \
         patch.object(_db, "update_template_research_doc_ids",
                      side_effect=KeyError("nope")), \
         patch.object(_db, "insert_coach_action") as audit:
        resp = client.patch(
            "/api/coach/block-library/nonexistent/research-docs",
            json={"research_doc_ids": ["doc1"]},
        )
    assert resp.status_code == 404, resp.text
    audit.assert_not_called()


def test_patch_empty_list_clears_attachments(client):
    """Empty research_doc_ids is a valid request that clears the column."""
    from bot.services import db as _db
    updated = {"block_template_id": "tpl_a", "research_doc_ids": []}
    with patch.object(_db, "list_research_docs", return_value=[]), \
         patch.object(_db, "update_template_research_doc_ids",
                      return_value=updated) as upd, \
         patch.object(_db, "insert_coach_action"):
        resp = client.patch(
            "/api/coach/block-library/tpl_a/research-docs",
            json={"research_doc_ids": []},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["template"]["research_doc_ids"] == []
    upd.assert_called_once_with("tpl_a", [])
