import pytest
from bot.services.rationale import (
    generate_triage_rationale,
    generate_exercise_rationale,
    generate_day_rationale,
    sanitize_for_llm,
)


# ---------- sanitizer ----------

COACH_ONLY_WORDS = ["Tier 1", "Tier 2", "Tier 3", "Sensitive", "Standard", "Resilient",
                    "provisional", "baseline"]


def test_sanitizer_strips_all_coach_vocabulary():
    detail = {
        "status_line": "Modified green — tissue concern (Sensitive baseline)",
        "signal_line": "Arm feel 8 → 7 → 6 over three check-ins.",
        "response_line": "Holding compounds. Tier 2 tolerance band exceeded.",
    }
    out = sanitize_for_llm(detail)
    joined = " ".join(out.values())
    for word in COACH_ONLY_WORDS:
        assert word not in joined, f"{word} leaked through sanitizer: {out}"


def test_sanitizer_preserves_signal_content():
    detail = {
        "status_line": "Yellow — tissue concern (Sensitive, provisional)",
        "signal_line": "Arm feel 5 two days running.",
        "response_line": "Trimmed accessories 20%.",
    }
    out = sanitize_for_llm(detail)
    assert "Arm feel 5" in out["signal_line"]
    assert "Trimmed accessories 20%" in out["response_line"]


def test_sanitizer_handles_none_and_empty():
    assert sanitize_for_llm(None) == {"status_line": "", "signal_line": "", "response_line": ""}
    assert sanitize_for_llm({}) == {"status_line": "", "signal_line": "", "response_line": ""}


# ---------- structural invariants ----------

def _skeleton_triage_result(flag="green"):
    return {
        "flag_level": flag,
        "category_scores": {"tissue": 8.0, "load": 8.0, "recovery": 8.0},
        "baseline_tier": 2,
        "modifications": [],
        "protocol_adjustments": {},
        "trajectory_context": {},
    }


def _skeleton_pitcher_context(role="starter", baseline_state="full", check_ins=20):
    return {
        "pitcher_id": "test_001",
        "name": "Test",
        "role": role,
        "baseline": {"baseline_state": baseline_state, "total_check_ins": check_ins,
                     "tier": 2},
        "arm_feel": 7,
        "sleep_hours": 7.0,
        "days_since_outing": 3,
        "whoop_data": None,
        "plan_source": "llm_enriched",
    }


def test_rationale_short_never_exceeds_120_chars():
    for flag in ["green", "modified_green", "yellow", "red"]:
        out = generate_triage_rationale(_skeleton_triage_result(flag), _skeleton_pitcher_context())
        assert len(out["short"]) <= 120, f"{flag}: {len(out['short'])} chars — {out['short']}"


def test_rationale_detail_has_three_lines():
    out = generate_triage_rationale(_skeleton_triage_result("yellow"), _skeleton_pitcher_context())
    assert set(out["detail"].keys()) == {"status_line", "signal_line", "response_line"}


def test_exercise_rationale_never_exceeds_60_chars():
    ex = {"name": "Trap-bar deadlift", "sets": 3, "reps": 5, "load": 185}
    out = generate_exercise_rationale(ex, constraints_applied=[], plan_context={})
    assert out is None or len(out) <= 60, f"{len(out)} chars — {out}"


def test_day_rationale_is_one_sentence():
    plan = {"lifting": {"block_name": "Lower pull"}}
    triage = _skeleton_triage_result("green")
    ctx = _skeleton_pitcher_context()
    out = generate_day_rationale(plan, triage, ctx)
    assert out is not None
    # Exactly one terminal punctuation at the end
    assert out.rstrip()[-1] in ".!?", f"No terminal punctuation: {out!r}"
    # Not multiple sentences
    core = out.rstrip()[:-1]
    assert all(c not in core for c in ".!?"), f"Multiple sentences: {out!r}"
