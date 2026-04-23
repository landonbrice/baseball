import asyncio


def _classify(*args, **kwargs):
    from bot.services.arm_assessment import classify_arm_assessment

    return asyncio.run(classify_arm_assessment(*args, **kwargs))


def test_no_issues_high_score_green_assessment():
    result = _classify(8, ["no_issues"], "")

    assert result["arm_feel"] == 8
    assert result["severity"] == "none"
    assert result["red_flags"] == []
    assert result["needs_followup"] is False


def test_high_score_with_sharp_elbow_pain_is_contradiction():
    result = _classify(8, ["elbow", "sharp_pain"])

    assert result["areas"] == ["elbow"]
    assert "sharp_pain" in result["red_flags"]
    assert "high_arm_feel_with_red_flag" in result["contradictions"]
    assert result["needs_followup"] is True


def test_low_score_no_issues_is_contradiction():
    result = _classify(4, ["no_issues"])

    assert "low_arm_feel_with_no_issues" in result["contradictions"]
    assert result["needs_followup"] is True


def test_expected_soreness_with_area_day_one_is_expected():
    result = _classify(
        5, ["expected_soreness", "forearm"], days_since_outing=1
    )

    assert result["expected_soreness"] is True
    assert result["contradictions"] == []


def test_expected_soreness_without_area_needs_followup():
    result = _classify(5, ["expected_soreness"])

    assert result["expected_soreness"] is False
    assert "expected_soreness_without_area" in result["contradictions"]
    assert result["needs_followup"] is True


def test_area_without_sensation_needs_followup():
    result = _classify(7, ["forearm"])

    assert "area_without_sensation" in result["contradictions"]
    assert result["needs_followup"] is True


def test_sensation_without_area_needs_followup():
    result = _classify(7, ["sharp_pain"])

    assert "sensation_without_area" in result["contradictions"]
    assert result["needs_followup"] is True


def test_numb_tingling_high_severity():
    result = _classify(9, ["numb_tingling", "elbow"])

    assert result["severity"] == "high"
    assert "numb_tingling" in result["red_flags"]


def test_expected_soreness_with_red_flag_red_wins():
    result = _classify(
        4, ["expected_soreness", "elbow", "sharp_pain"]
    )

    assert result["expected_soreness"] is False
    assert "sharp_pain" in result["red_flags"]
    assert "expected_soreness_with_red_flag" in result["contradictions"]


def test_negated_soreness_text_does_not_trigger_tight_sore():
    result = _classify(7, [], "not sore, no tightness")

    assert "tight_sore" not in result["sensations"]
    assert result["red_flags"] == []


def test_text_forearm_tight_better_than_yesterday():
    result = _classify(7, [], "forearm tight but better than yesterday")

    assert "forearm" in result["areas"]
    assert "tight_sore" in result["sensations"]
    assert result["trend"] == "better"


def test_text_dead_arm_maps_heavy_dead():
    result = _classify(6, [], "dead arm")

    assert "heavy_dead" in result["sensations"]


def test_negated_sharp_text_does_not_trigger_red_flag():
    result = _classify(8, [], "nothing sharp")

    assert "sharp_pain" not in result["red_flags"]
