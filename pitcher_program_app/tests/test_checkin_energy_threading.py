"""Regression: energy field posted to /chat reaches process_checkin (D3).

Pre-fix, the /chat checkin handler did not pass `energy` to process_checkin,
so every mini-app check-in stored overall_energy=3 (the default param value).
"""
from fastapi.testclient import TestClient


def _install_common_stubs(monkeypatch):
    """Mirror the stubbing pattern used in test_chat_content_shape.py."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    import api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)

    monkeypatch.setattr(
        "api.routes.load_profile",
        lambda pitcher_id: {
            "active_flags": {"phase": "normal"},
            "biometric_integration": {"avg_sleep_hours": 7.0},
            "rotation_length": 7,
        },
    )
    monkeypatch.setattr(
        "api.routes.load_log",
        lambda pitcher_id: {"entries": []},
    )
    monkeypatch.setattr(
        "api.routes.increment_days_since_outing",
        lambda pitcher_id: None,
    )
    monkeypatch.setattr(
        "api.routes._persist_chat",
        lambda pitcher_id, user_content, bot_messages, source="mini_app": None,
    )


def test_energy_from_chat_reaches_process_checkin(monkeypatch):
    _install_common_stubs(monkeypatch)

    calls = []

    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        calls.append({"pitcher_id": pitcher_id, "arm_feel": arm_feel, "sleep_hours": sleep_hours, **kwargs})
        return {
            "morning_brief": "",
            "plan_narrative": "ok",
            "flag_level": "green",
            "triage_reasoning": "",
            "source": "llm_enriched",
            "plan_generated": {"lifting": {"exercises": []}, "exercise_blocks": []},
        }

    monkeypatch.setattr("api.routes.process_checkin", fake_process_checkin)

    from api.main import app
    client = TestClient(app)

    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={
            "message": {"arm_feel": 8, "sleep_hours": 7.0, "energy": 9},
            "type": "checkin",
        },
    )
    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0].get("energy") == 9, (
        f"energy was not threaded to process_checkin; got kwargs={calls[0]}"
    )


def test_energy_defaults_when_absent(monkeypatch):
    """Backwards compat: clients that don't send energy still work."""
    _install_common_stubs(monkeypatch)

    calls = []

    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        calls.append(kwargs)
        return {
            "morning_brief": "",
            "plan_narrative": "",
            "flag_level": "green",
            "triage_reasoning": "",
            "source": "llm_enriched",
            "plan_generated": {"lifting": {"exercises": []}, "exercise_blocks": []},
        }

    monkeypatch.setattr("api.routes.process_checkin", fake_process_checkin)

    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={"message": {"arm_feel": 7, "sleep_hours": 7}, "type": "checkin"},
    )
    assert res.status_code == 200
    # When client doesn't send energy, we shouldn't FORCE 3 — pass None / omit
    # and let process_checkin default-handle it
    assert "energy" not in calls[0] or calls[0]["energy"] in (None, 3)
