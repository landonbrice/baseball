"""Sprint D — bot-handler harness for the drive path (2026-07-13 incident).

Prod evidence: the morning-notification check-in ran, the engine-projected
entry PERSISTED correctly (source=engine_projected, proposal attached), and
the bot then showed the generic failure text — twice (manual retry). The
exception is therefore in `_generate_plan_and_respond` AFTER process_checkin
returns, or inside process_checkin after the entry upsert.

This harness drives the real handler with the real drive-shaped response
dict (copied field-for-field from the prod entry of 2026-07-13) and a fake
Telegram message that records every reply. Any exception in the handler's
post-checkin section fails these tests loudly.
"""

import pytest

from bot.handlers import daily_checkin as dc


class FakeMessage:
    """Records reply_text calls; mimics the telegram Message surface used."""

    def __init__(self):
        self.replies: list[tuple[str, object]] = []

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.replies.append((text, reply_markup))
        return FakeStatusMsg()


class FakeStatusMsg:
    async def delete(self):
        return None

    async def reply_text(self, text, reply_markup=None, **kwargs):
        return FakeStatusMsg()


class FakeContext:
    def __init__(self, arm_feel=10):
        self.user_data = {
            "pitcher_id": "landon_brice",
            "arm_feel": arm_feel,
            "arm_report": "",
            "arm_detail_tags": ["no_issues"],
            "lift_preference": "auto",
            "throw_intent": "none",
            "next_pitch_days": None,
            "arm_clarification": "",
        }


def _drive_checkin_result():
    """The response dict shape process_checkin returned on 2026-07-13,
    reconstructed from the persisted prod entry."""
    return {
        "flag_level": "modified_green",
        "triage_reasoning": "Arm feel 10/10. WHOOP recovery 19 (avg 50), HRV -51% — modified green.",
        "alerts": [],
        "observations": [],
        "weekly_summary": None,
        "plan_narrative": "Week 1, day 1 of your program — Base Throwing.",
        "morning_brief": (
            "Week 1, day 1 of your program — Base Throwing. Base flat-ground throwing "
            "with moderate lower-body lift. Your check-in came back YELLOW, so today is "
            "adjusted: Throws 60 → 48; Intent 60% → 50%; Lifting trimmed 6 → 5 exercises. "
            "Confirm or adjust below."
        ),
        "arm_care": None,
        "lifting": {"exercises": [
            {"exercise_id": "ex_002", "name": "Front Squat", "sets": 3, "reps": "5-7"},
            {"exercise_id": "ex_010", "name": "Romanian Deadlift", "sets": 3, "reps": "8"},
        ]},
        "throwing": {
            "type": "program_throwing",
            "intent": "50%",
            "volume_summary": "48 throws @ 60ft · 50% intent",
            "phases": [{"name": "Program throwing", "exercises": [{"name": "Flat Ground Throws"}]}],
        },
        "notes": ["Throws 60 → 48", "Intent 60% → 50%", "Lifting trimmed 6 → 5 exercises"],
        "soreness_response": None,
        "exercise_blocks": [{"block_name": "Block 1: Lower Strength", "exercises": []}],
        "throwing_plan": None,
        "proposal": {
            "status": "proposed",
            "auto_accept": True,
            "readiness_class": "yellow",
            "changes": ["Throws 60 → 48", "Intent 60% → 50%", "Lifting trimmed 6 → 5 exercises"],
        },
        "estimated_duration_min": None,
        "modifications_applied": [],
        "template_day": "wk1_d1",
        "rotation_day": 0,
        "source": "engine_projected",
        "source_reason": None,
        "arm_assessment": {"summary": "Arm 10/10 with no issues reported."},
    }


@pytest.fixture
def wired(monkeypatch):
    async def fake_checkin(*a, **k):
        return _drive_checkin_result()

    monkeypatch.setattr(dc, "process_checkin", fake_checkin)
    monkeypatch.setattr(dc, "load_profile", lambda pid: {"pitcher_id": pid, "active_flags": {}, "rotation_length": 7})
    monkeypatch.setattr(dc, "increment_days_since_outing", lambda pid: None)
    return None


@pytest.mark.asyncio
async def test_handler_completes_on_drive_result_with_proposal(wired):
    msg = FakeMessage()
    ctx = FakeContext()
    ret = await dc._generate_plan_and_respond(msg, ctx)

    texts = [t for t, _ in msg.replies]
    # The generic failure text must NOT appear — that's the prod incident.
    assert not any("issue generating your plan" in t for t in texts), texts
    # Triage + brief message sent
    assert any("MODIFIED_GREEN flag." in t for t in texts), texts
    # Proposal confirm message with buttons sent (distinct from the brief,
    # which also contains the word "adjusted")
    proposal_replies = [(t, kb) for t, kb in msg.replies if "already your plan" in t]
    assert proposal_replies, texts
    assert proposal_replies[0][1] is not None  # keyboard attached


@pytest.mark.asyncio
async def test_handler_completes_on_green_drive_result_no_proposal(wired, monkeypatch):
    result = _drive_checkin_result()
    result["proposal"] = None
    result["flag_level"] = "green"
    result["morning_brief"] = "Week 1, day 1 — Base Throwing. You're green — the day ships as written."

    async def fake_checkin(*a, **k):
        return result

    monkeypatch.setattr(dc, "process_checkin", fake_checkin)
    msg = FakeMessage()
    ret = await dc._generate_plan_and_respond(msg, FakeContext())
    texts = [t for t, _ in msg.replies]
    assert not any("issue generating your plan" in t for t in texts), texts
    assert not any("already your plan" in t for t in texts)  # green: no proposal message
