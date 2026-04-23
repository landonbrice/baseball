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


# ---------- voice calibration fixtures (review with Lando before locking matrix) ----------

def _triage(flag, *, tissue=8.0, load=8.0, recovery=8.0, mods=None, tier=2,
            trajectory=None, pa=None):
    return {
        "flag_level": flag,
        "category_scores": {"tissue": tissue, "load": load, "recovery": recovery},
        "baseline_tier": tier,
        "modifications": mods or [],
        "protocol_adjustments": pa or {},
        "trajectory_context": trajectory or {},
    }


def _ctx(*, arm_feel=7, sleep=7.0, dso=3, whoop=None, role="starter",
         state="full", check_ins=30, plan_source="llm_enriched"):
    return {
        "pitcher_id": "x",
        "name": "X",
        "role": role,
        "baseline": {"baseline_state": state, "total_check_ins": check_ins, "tier": 2,
                     "overall_mean": 8.0},
        "arm_feel": arm_feel,
        "sleep_hours": sleep,
        "days_since_outing": dso,
        "whoop_data": whoop,
        "plan_source": plan_source,
    }


def test_green_static_phrase():
    out = generate_triage_rationale(_triage("green"), _ctx(arm_feel=8, sleep=7.5))
    assert out["short"] == "All systems good."
    assert out["detail"]["status_line"] == "Green"
    assert out["detail"]["response_line"] == "Full program today."
    # Signal line names strongest positive fact
    assert "arm feel" in out["detail"]["signal_line"].lower() or "8" in out["detail"]["signal_line"]


def test_modified_green_post_outing_starter():
    tri = _triage("modified_green", tissue=7.5, load=7.5, recovery=7.5,
                  mods=["maintain_compounds_reduced"], tier=2)
    out = generate_triage_rationale(tri, _ctx(arm_feel=7, dso=1))
    # Should reference post-outing and day-one
    assert "recovery" in out["short"].lower() or "post-outing" in out["short"].lower()


def test_yellow_tissue_concern_full_baseline():
    tri = _triage("yellow", tissue=5.2, load=7.0, recovery=7.0,
                  mods=["maintain_compounds_reduced"], tier=2,
                  trajectory={"recovery_curve_status": "on_track"})
    out = generate_triage_rationale(tri, _ctx(arm_feel=5))
    # tissue is dominant category (widest gap)
    assert "tissue" in out["detail"]["status_line"].lower() or "arm" in out["detail"]["status_line"].lower()
    # Response line names specific modification
    assert "compound" in out["detail"]["response_line"].lower()


def test_yellow_compound_stress_tissue_and_recovery():
    tri = _triage("yellow", tissue=5.2, load=7.0, recovery=5.0,
                  mods=["no_high_intent_throw"], tier=2)
    out = generate_triage_rationale(tri, _ctx(arm_feel=5, sleep=5.2))
    # Signal names the actual values
    assert "5" in out["detail"]["signal_line"]


def test_red_flag_full_baseline():
    tri = _triage("red", tissue=3.0, load=5.0, recovery=4.0,
                  mods=["no_lifting", "no_throwing"], tier=2)
    out = generate_triage_rationale(tri, _ctx(arm_feel=3))
    # Response line mentions shutdown or no-throwing
    assert "no throwing" in out["detail"]["response_line"].lower() or \
           "shutdown" in out["detail"]["response_line"].lower()


def test_tier_label_included_when_non_default():
    # Standard (tier 2) = default → omit from status line per A30 + spec
    tri_std = _triage("yellow", tissue=5.2, tier=2)
    out_std = generate_triage_rationale(tri_std, _ctx())
    assert "Standard" not in out_std["detail"]["status_line"]

    # Sensitive (tier 1) → included
    tri_sen = _triage("yellow", tissue=5.2, tier=1)
    out_sen = generate_triage_rationale(tri_sen, _ctx())
    assert "Sensitive" in out_sen["detail"]["status_line"]


def test_tiebreak_within_0_3_fixed_priority_tissue_over_recovery():
    # tissue 5.0, recovery 5.2, load 7.0 → within 0.3 → tissue wins (A12)
    tri = _triage("yellow", tissue=5.0, load=7.0, recovery=5.2, tier=2)
    out = generate_triage_rationale(tri, _ctx())
    # Dominant should be tissue
    assert "tissue" in out["detail"]["status_line"].lower() or \
           "arm" in out["detail"]["status_line"].lower()


def test_instant_red_arm_feel_2():
    tri = _triage("red", tissue=1.0, load=4.0, recovery=4.0,
                  mods=["no_lifting", "no_throwing"], tier=2)
    ctx = _ctx(arm_feel=2, sleep=6.0)
    out = generate_triage_rationale(tri, ctx)
    assert out["short"].startswith("Acute concern — ")
    assert "2" in out["short"]
    assert out["detail"]["status_line"] == "Red — acute concern"
    assert "no throwing" in out["detail"]["response_line"].lower() or \
           "trainer" in out["detail"]["response_line"].lower()


def test_instant_red_ucl_sensation():
    tri = _triage("red", tissue=2.0, load=4.0, recovery=4.0,
                  mods=["no_lifting", "no_throwing"], tier=2)
    ctx = _ctx(arm_feel=5)
    ctx["arm_clarification"] = "UCL sensation on inside of elbow this morning"
    out = generate_triage_rationale(tri, ctx)
    assert out["short"].startswith("Acute concern — ")
    assert "UCL" in out["short"]
    assert out["detail"]["status_line"] == "Red — acute concern"


def test_category_red_uses_category_framing_not_instant():
    # Red flag from category compound stress, NOT instant trigger
    tri = _triage("red", tissue=3.5, load=3.5, recovery=3.5,
                  mods=["no_high_intent_throw"], tier=2)
    ctx = _ctx(arm_feel=4)  # >2, no UCL clarification
    out = generate_triage_rationale(tri, ctx)
    assert not out["short"].startswith("Acute concern")
    assert out["detail"]["status_line"] != "Red — acute concern"
