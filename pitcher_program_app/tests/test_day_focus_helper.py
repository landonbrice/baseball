from bot.services.day_focus import derive_day_focus


def test_bullpen_when_bullpen_present():
    plan = {"bullpen": {"pitches": 35}, "throwing_plan": None}
    assert derive_day_focus(plan, modifications=[]) == "bullpen"


def test_throw_when_throwing_plan_present_no_bullpen():
    plan = {"bullpen": None, "throwing_plan": "hybrid A 60%"}
    assert derive_day_focus(plan, modifications=[]) == "throw"


def test_lift_when_only_lifting():
    plan = {"bullpen": None, "throwing_plan": None, "lifting": {"block_name": "Lower pull"}}
    assert derive_day_focus(plan, modifications=[]) == "lift"


def test_recovery_when_rest_day_mod():
    plan = {"bullpen": None, "throwing_plan": None, "lifting": None}
    assert derive_day_focus(plan, modifications=["rest_day"]) == "recovery"


def test_recovery_when_no_throw_mod():
    plan = {"bullpen": None, "throwing_plan": None, "lifting": None}
    assert derive_day_focus(plan, modifications=["no_throw"]) == "recovery"


def test_none_when_nothing():
    assert derive_day_focus({}, modifications=[]) is None


def test_honors_explicit_day_focus_on_plan():
    plan = {"day_focus": "bullpen", "bullpen": None, "throwing_plan": None}
    assert derive_day_focus(plan, modifications=[]) == "bullpen"


def test_accepts_dict_modifications():
    plan = {"bullpen": None, "throwing_plan": None, "lifting": None}
    assert derive_day_focus(plan, modifications=[{"tag": "rest_day", "reason": None}]) == "recovery"
