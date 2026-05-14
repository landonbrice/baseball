"""Tests for program_aware_planner.compose_prescribed_plan and
apply_triage_to_program_plan (Plan 4 Tasks 4.1 + 4.2).

Pure functions — never call the LLM or DB; takes throwing_rx + lifting_rx +
profile (4.1) or prescribed plan + triage (4.2) as inputs.
"""
from datetime import date


def test_compose_with_throwing_and_lifting():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}}
    lifting_rx = {"day_index": 8, "template_key": "lower_strength"}
    profile = {"pitcher_id": "landon_brice"}
    plan = pap.compose_prescribed_plan(throwing_rx, lifting_rx, profile, target_date=date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is not None
    assert plan["throwing"]["template_key"] == "day_3"
    assert plan["lifting"]["template_key"] == "lower_strength"
    assert plan["source"] == "program_prescribed"


def test_compose_with_only_throwing():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is None
    assert plan["source"] == "program_prescribed"


def test_compose_with_neither_returns_none():
    """Caller is responsible for cold-start fallback when both rx are None."""
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan(None, None, {}, date(2026, 5, 1))
    assert plan is None


def test_compose_includes_target_date():
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan({"day_index": 0}, None, {}, date(2026, 5, 1))
    assert plan["target_date"] == "2026-05-01"


def test_compose_preserves_program_metadata():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}, "date": "2026-05-01"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    # Snapshot is preserved verbatim under program_prescription_snapshot
    assert plan["program_prescription_snapshot"]["throwing"] == throwing_rx


def test_apply_triage_green_returns_unmodified_with_advance():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "green", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "green"
    assert hold_event is None  # advance, no hold
    assert final["throwing"] == prescribed["throwing"]
    assert final["lifting"] == prescribed["lifting"]


def test_apply_triage_yellow_advances_with_modification_tags():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "yellow", "modification_flags": ["fatigue_general"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "yellow"
    assert hold_event is None
    assert final["modification_flags"] == ["fatigue_general"]


def test_apply_triage_red_holds_counter_and_replaces_throwing_with_recovery():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3", "session": {"intensity": "high"}},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_protect"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "red"
    assert hold_event is not None
    assert hold_event["reason_code"] == "red"
    # Throwing is replaced with a recovery shape
    assert final["throwing"]["recovery_only"] is True
    # Lifting trimmed to light
    assert final["lifting"]["intensity"] == "light"


def test_apply_triage_critical_red_shutdown_and_alert():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_shutdown"],
              "arm_feel": 2}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["throwing"]["shutdown"] is True
    assert hold_event["reason_code"] == "critical_red"
    assert final["auto_alert_coach"] is True


def test_apply_triage_red_with_no_throwing_still_holds():
    """Lifting-only program in Red still pauses the lifting counter."""
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": None,
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert hold_event is not None
    assert final["lifting"]["intensity"] == "light"
