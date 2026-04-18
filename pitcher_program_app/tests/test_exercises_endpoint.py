"""D2, D7: /api/exercises reads Supabase live (no @lru_cache)."""
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_exercises_endpoint_returns_supabase_rows(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    fresh_rows = [
        {"id": "ex_new", "slug": "brand_new", "name": "Brand New Exercise",
         "category": "upper_body_pull", "modification_flags": {}, "rotation_day_usage": [],
         "contraindications": [], "youtube_url": None, "muscles_primary": ["lats"],
         "prescription": {"strength": {"sets": 3, "reps": 8}}},
    ]
    monkeypatch.setattr("bot.services.db.get_exercises", lambda: fresh_rows)

    from api.main import app
    client = TestClient(app)
    res = client.get("/api/exercises")
    assert res.status_code == 200
    body = res.json()
    # Shape: { exercises: [...] } matching JSON contract
    assert "exercises" in body
    names = [e["name"] for e in body["exercises"]]
    assert "Brand New Exercise" in names


def test_exercises_endpoint_not_cached(monkeypatch):
    """Two calls with different underlying data should return different results (no lru_cache)."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    call_state = {"rows": [{"id": "a", "name": "A"}]}
    monkeypatch.setattr("bot.services.db.get_exercises", lambda: call_state["rows"])

    from api.main import app
    client = TestClient(app)
    res1 = client.get("/api/exercises")
    call_state["rows"] = [{"id": "b", "name": "B"}]
    res2 = client.get("/api/exercises")
    names1 = [e["name"] for e in res1.json()["exercises"]]
    names2 = [e["name"] for e in res2.json()["exercises"]]
    assert names1 == ["A"]
    assert names2 == ["B"]
