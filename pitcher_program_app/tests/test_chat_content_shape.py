"""Regression: /chat checkin response never contains a raw JSON-string envelope
as message content (D1). Surfaced 2026-04-18 when normalize_brief started
emitting JSON-string briefs and the chat response assembler leaked them
into user-visible chat bubbles.
"""
import json
from fastapi.testclient import TestClient


def test_chat_checkin_content_is_plain_text(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # DISABLE_AUTH resolves at import time via `from bot.config import DISABLE_AUTH`
    # in api.routes, so setenv alone doesn't affect an already-imported module.
    # Patch the module-level attribute directly.
    import api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)

    # Fake process_checkin returns the canonical post-Task-3b shape:
    # - morning_brief is a JSON-string envelope
    # - plan_narrative is the plain coaching note
    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        return {
            "morning_brief": json.dumps({
                "arm_verdict": {"value": "8/10", "status": "green"},
                "coaching_note": "Solid arm, standard rotation today.",
            }),
            "plan_narrative": "Solid arm, standard rotation today.",
            "flag_level": "green",
            "triage_reasoning": "",
            "source": "llm_enriched",
            "plan_generated": {"lifting": {"exercises": []}, "exercise_blocks": []},
        }

    monkeypatch.setattr("api.routes.process_checkin", fake_process_checkin)

    # Stub DB/profile reads the handler makes so we never hit Supabase in tests.
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

    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={
            "message": {
                "arm_feel": 8,
                "sleep_hours": 7.5,
                "arm_report": "feels good",
            },
            "type": "checkin",
        },
    )
    assert res.status_code == 200
    body = res.json()
    # Every text message content must be plain text — never a JSON envelope
    for msg in body.get("messages", []):
        if msg.get("type") == "text":
            content = msg.get("content", "")
            assert not (content.startswith("{") and '"coaching_note"' in content), (
                f"JSON envelope leaked into chat content: {content[:200]}"
            )
