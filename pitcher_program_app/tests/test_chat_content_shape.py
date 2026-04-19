"""Regression: /chat checkin response never contains a raw JSON-string envelope
as message content (D1). Surfaced 2026-04-18 when normalize_brief started
emitting JSON-string briefs and the chat response assembler leaked them
into user-visible chat bubbles.
"""
import json
from fastapi.testclient import TestClient


def _install_common_stubs(monkeypatch):
    """Shared setup: disable auth + stub DB/profile reads so the handler
    never hits Supabase. Callers still supply their own process_checkin.
    """
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # DISABLE_AUTH resolves at import time via `from bot.config import DISABLE_AUTH`
    # in api.routes, so setenv alone doesn't affect an already-imported module.
    # Patch the module-level attribute directly.
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


def test_chat_checkin_content_is_plain_text(monkeypatch):
    _install_common_stubs(monkeypatch)

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


def test_chat_checkin_falls_back_to_parsing_morning_brief_when_narrative_absent(monkeypatch):
    """When plan_narrative is empty, the handler must parse morning_brief's
    coaching_note rather than leaking the raw JSON envelope. This exercises
    the fallback branch at api/routes.py lines 662-672.
    """
    _install_common_stubs(monkeypatch)

    # Fake process_checkin returns ONLY a JSON-string morning_brief —
    # no plan_narrative. Forces the handler down the fallback parse path.
    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        return {
            "morning_brief": json.dumps({
                "arm_verdict": {"value": "8/10", "status": "green"},
                "coaching_note": "Solid arm, standard rotation today.",
            }),
            "plan_narrative": "",  # absent — forces fallback path
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

    text_contents = [
        m.get("content", "")
        for m in body.get("messages", [])
        if m.get("type") == "text"
    ]

    # The fallback must extract coaching_note verbatim
    assert any("Solid arm, standard rotation today." in c for c in text_contents), (
        f"fallback did not extract coaching_note; got text messages: {text_contents}"
    )
    # And no leaked envelope in any text message
    for c in text_contents:
        assert not (c.startswith("{") and '"coaching_note"' in c), (
            f"JSON envelope leaked: {c[:200]}"
        )
