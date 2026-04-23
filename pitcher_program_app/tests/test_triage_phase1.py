"""Phase 1 triage tests — golden snapshots + new category scoring."""

import pytest


def _make_profile(
    role="starter", rotation_length=7, days_since_outing=3,
    injury_areas=None, active_modifications=None, grip_drop=False,
):
    injuries = []
    if injury_areas:
        for area in injury_areas:
            injuries.append({"area": area, "flag_level": "green"})
    return {
        "role": role, "rotation_length": rotation_length,
        "active_flags": {
            "days_since_outing": days_since_outing, "current_arm_feel": None,
            "active_modifications": active_modifications or [],
            "grip_drop_reported": grip_drop,
        },
        "injury_history": injuries,
    }


# ═══════════════════════════════════════════════════════════════════════
# GOLDEN SNAPSHOTS — must pass against BOTH old and new triage
# ═══════════════════════════════════════════════════════════════════════

class TestGoldenSnapshots:
    def test_instant_red_arm_feel_1(self):
        from bot.services.triage import triage
        result = triage(arm_feel=1, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_arm_feel_2(self):
        from bot.services.triage import triage
        result = triage(arm_feel=2, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_arm_feel_4(self):
        from bot.services.triage import triage
        result = triage(arm_feel=4, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_arm_feel_3(self):
        from bot.services.triage import triage
        result = triage(arm_feel=3, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_instant_red_ucl_with_history(self):
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["medial_elbow"])
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=profile, ucl_sensation=True)
        assert result["flag_level"] == "red"

    def test_instant_red_ucl_with_forearm_history(self):
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["forearm"])
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=profile, ucl_sensation=True)
        assert result["flag_level"] == "red"

    def test_instant_red_significant_tightness_with_history(self):
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["forearm"])
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=profile, forearm_tightness="significant")
        assert result["flag_level"] == "red"

    def test_instant_red_significant_tightness_medial_elbow(self):
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["medial_elbow"])
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=profile, forearm_tightness="significant")
        assert result["flag_level"] == "red"

    def test_two_yellows_produce_red(self):
        from bot.services.triage import triage
        result = triage(arm_feel=6, sleep_hours=5.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "red"

    def test_two_yellows_arm_feel_and_energy(self):
        from bot.services.triage import triage
        result = triage(arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile(), energy=4)
        assert result["flag_level"] == "red"

    def test_two_yellows_sleep_and_energy(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=5.0, pitcher_profile=_make_profile(), energy=3)
        assert result["flag_level"] == "red"

    def test_two_yellows_arm_feel_and_whoop_recovery(self):
        from bot.services.triage import triage
        result = triage(arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile(), whoop_recovery=20.0)
        assert result["flag_level"] == "red"

    def test_single_yellow_arm_feel(self):
        from bot.services.triage import triage
        result = triage(arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "yellow"

    def test_single_yellow_arm_feel_5(self):
        from bot.services.triage import triage
        result = triage(arm_feel=5, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "yellow"

    def test_single_yellow_low_sleep(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=5.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "yellow"

    def test_single_yellow_low_energy(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), energy=4)
        assert result["flag_level"] == "yellow"

    def test_single_yellow_low_whoop_recovery(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), whoop_recovery=20.0)
        assert result["flag_level"] == "yellow"

    def test_single_yellow_mild_tightness(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), forearm_tightness="mild")
        assert result["flag_level"] == "yellow"

    def test_single_yellow_moderate_tightness(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), forearm_tightness="moderate")
        assert result["flag_level"] == "yellow"

    def test_single_yellow_high_pitch_count(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), pitch_count=85)
        assert result["flag_level"] == "yellow"

    def test_single_yellow_grip_drop(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(grip_drop=True))
        assert result["flag_level"] == "yellow"

    def test_single_yellow_hrv_drop(self):
        from bot.services.triage import triage
        result = triage(
            arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(),
            whoop_hrv=40.0, whoop_hrv_7day_avg=60.0,
        )
        assert result["flag_level"] == "yellow"

    def test_single_yellow_sleep_perf(self):
        from bot.services.triage import triage
        result = triage(
            arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(),
            whoop_sleep_perf=40,
        )
        assert result["flag_level"] == "yellow"

    def test_modified_green_borderline_sleep(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=6.2, pitcher_profile=_make_profile())
        assert result["flag_level"] == "modified_green"

    def test_modified_green_moderate_whoop(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), whoop_recovery=40.0)
        assert result["flag_level"] == "modified_green"

    def test_modified_green_moderate_pitch_count(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(), pitch_count=65)
        assert result["flag_level"] == "modified_green"

    def test_modified_green_hrv_moderate_drop(self):
        from bot.services.triage import triage
        result = triage(
            arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(),
            whoop_hrv=50.0, whoop_hrv_7day_avg=60.0,  # ~16.7% drop but within 10-15 range... no
        )
        # 16.7% is > 15% so this is yellow trigger, not modified_green
        # Use 12% drop instead: hrv=52.8, avg=60 -> drop = 12%
        pass  # This test needs recalculation, see below

    def test_modified_green_hrv_moderate_drop_corrected(self):
        from bot.services.triage import triage
        # 12% drop: (60-52.8)/60 = 12%  -> in the 10-15% range -> modified_green
        result = triage(
            arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(),
            whoop_hrv=52.8, whoop_hrv_7day_avg=60.0,
        )
        assert result["flag_level"] == "modified_green"

    def test_modified_green_moderate_sleep_perf(self):
        from bot.services.triage import triage
        result = triage(
            arm_feel=7, sleep_hours=8.0, pitcher_profile=_make_profile(),
            whoop_sleep_perf=55,
        )
        assert result["flag_level"] == "modified_green"

    def test_green_all_good(self):
        from bot.services.triage import triage
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert result["flag_level"] == "green"

    def test_green_start_proximity(self):
        from bot.services.triage import triage
        profile = _make_profile(days_since_outing=5, rotation_length=7)
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile)
        assert result["flag_level"] == "green"
        assert "primer_session" in result["modifications"]

    def test_green_start_proximity_exact(self):
        from bot.services.triage import triage
        # days_to_start = 7 - 7 = 0
        profile = _make_profile(days_since_outing=7, rotation_length=7)
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile)
        assert result["flag_level"] == "green"
        assert "primer_session" in result["modifications"]

    def test_green_no_start_proximity(self):
        from bot.services.triage import triage
        # days_to_start = 7 - 3 = 4 (not within 0-2)
        profile = _make_profile(days_since_outing=3, rotation_length=7)
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile)
        assert result["flag_level"] == "green"
        assert "primer_session" not in result["modifications"]

    def test_output_shape_has_required_keys(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=7.0, pitcher_profile=_make_profile())
        for key in ("flag_level", "modifications", "alerts", "protocol_adjustments", "reasoning"):
            assert key in result

    def test_protocol_adjustments_shape(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=7.0, pitcher_profile=_make_profile())
        pa = result["protocol_adjustments"]
        for key in ("lifting_intensity_cap", "remove_exercises", "add_exercises", "arm_care_template", "plyocare_allowed", "throwing_adjustments"):
            assert key in pa

    def test_red_protocol_adjustments(self):
        from bot.services.triage import triage
        result = triage(arm_feel=1, sleep_hours=8.0, pitcher_profile=_make_profile())
        pa = result["protocol_adjustments"]
        assert pa["lifting_intensity_cap"] == "none"
        assert pa["plyocare_allowed"] is False
        assert pa["arm_care_template"] == "light"

    def test_yellow_protocol_adjustments(self):
        from bot.services.triage import triage
        result = triage(arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile())
        pa = result["protocol_adjustments"]
        assert pa["lifting_intensity_cap"] == "RPE 6-7"
        assert pa["plyocare_allowed"] is False

    def test_modified_green_protocol_adjustments(self):
        from bot.services.triage import triage
        result = triage(arm_feel=7, sleep_hours=6.2, pitcher_profile=_make_profile())
        pa = result["protocol_adjustments"]
        assert pa["lifting_intensity_cap"] == "RPE 7-8"

    def test_red_has_no_lifting_no_throwing_mods(self):
        from bot.services.triage import triage
        result = triage(arm_feel=1, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert "no_lifting" in result["modifications"]
        assert "no_throwing" in result["modifications"]

    def test_ucl_no_history_not_red(self):
        """UCL sensation without medial elbow/forearm history is NOT instant red."""
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["shoulder"])
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile, ucl_sensation=True)
        assert result["flag_level"] != "red"

    def test_significant_tightness_no_history_not_red(self):
        """Significant tightness without medial elbow/forearm history is NOT instant red."""
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["shoulder"])
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=profile, forearm_tightness="significant")
        assert result["flag_level"] != "red"

    def test_consecutive_low_arm_feel_alert(self):
        """Two consecutive days arm_feel <= 4 produces an urgent alert."""
        from bot.services.triage import triage
        profile = _make_profile()
        profile["active_flags"]["current_arm_feel"] = 4
        result = triage(arm_feel=4, sleep_hours=8.0, pitcher_profile=profile)
        assert result["flag_level"] == "red"
        assert any("2+ days" in a for a in result["alerts"])

    def test_fpm_volume_mod_with_tightness_and_history(self):
        """Mild/moderate tightness with forearm/medial elbow history adds fpm_volume."""
        from bot.services.triage import triage
        profile = _make_profile(injury_areas=["forearm"])
        result = triage(arm_feel=7, sleep_hours=8.0, pitcher_profile=profile, forearm_tightness="mild")
        assert "fpm_volume" in result["modifications"]

    def test_new_output_shape(self):
        """New triage returns category_scores, trajectory_context, baseline_tier."""
        from bot.services.triage import triage
        result = triage(arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile())
        assert "category_scores" in result
        assert "trajectory_context" in result
        assert "baseline_tier" in result
        cs = result["category_scores"]
        for key in ("tissue", "load", "recovery"):
            assert key in cs
        tc = result["trajectory_context"]
        for key in ("recovery_curve_status", "chronic_drift", "pace_below_floor",
                     "pace_deficit", "late_rotation_concern", "trend_flags"):
            assert key in tc


# ═══════════════════════════════════════════════════════════════════════════
# TISSUE SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestTissueScoring:
    """Test _compute_tissue_score point values."""

    def _get_tissue(self, **kwargs):
        from bot.services.triage import _compute_tissue_score
        defaults = dict(
            arm_feel=8, forearm_tightness="", ucl_sensation=False,
            grip_drop=False, arm_clarification=None, days_since_outing=3,
            injury_areas=[], arm_feel_history=[], pitcher_baseline=None,
            recovery_curve_expected=None,
        )
        defaults.update(kwargs)
        return _compute_tissue_score(**defaults)

    def test_arm_feel_8_is_zero(self):
        assert self._get_tissue(arm_feel=8) == 0.0

    def test_arm_feel_7_is_zero(self):
        assert self._get_tissue(arm_feel=7) == 0.0

    def test_arm_feel_6_is_1(self):
        assert self._get_tissue(arm_feel=6) == 1.0

    def test_arm_feel_5_is_2(self):
        assert self._get_tissue(arm_feel=5) == 2.0

    def test_arm_feel_4_is_3(self):
        assert self._get_tissue(arm_feel=4) == 3.0

    def test_arm_feel_3_is_5(self):
        assert self._get_tissue(arm_feel=3) == 5.0

    def test_arm_feel_2_is_8(self):
        assert self._get_tissue(arm_feel=2) == 8.0

    def test_arm_feel_1_is_8(self):
        assert self._get_tissue(arm_feel=1) == 8.0

    def test_forearm_mild_adds_1(self):
        assert self._get_tissue(forearm_tightness="mild") == 1.0

    def test_forearm_moderate_adds_3(self):
        assert self._get_tissue(forearm_tightness="moderate") == 3.0

    def test_forearm_significant_adds_6(self):
        assert self._get_tissue(forearm_tightness="significant") == 6.0

    def test_ucl_with_history_adds_8(self):
        score = self._get_tissue(ucl_sensation=True, injury_areas=["medial_elbow"])
        assert score == 8.0

    def test_ucl_without_history_adds_0(self):
        score = self._get_tissue(ucl_sensation=True, injury_areas=["shoulder"])
        assert score == 0.0

    def test_grip_drop_adds_2(self):
        assert self._get_tissue(grip_drop=True) == 2.0

    def test_arm_clarification_concerned_adds_3(self):
        assert self._get_tissue(arm_clarification="concerned") == 3.0

    def test_arm_clarification_expected_soreness_day0_subtracts_2(self):
        score = self._get_tissue(arm_feel=5, arm_clarification="expected_soreness", days_since_outing=0)
        # arm_feel=5 gives +2, expected_soreness day 0 gives -2 = 0
        assert score == 0.0

    def test_arm_clarification_expected_soreness_day1_subtracts_2(self):
        score = self._get_tissue(arm_feel=5, arm_clarification="expected_soreness", days_since_outing=1)
        assert score == 0.0

    def test_arm_clarification_expected_soreness_day2_subtracts_2(self):
        score = self._get_tissue(arm_feel=5, arm_clarification="expected_soreness", days_since_outing=2)
        assert score == 0.0

    def test_arm_clarification_expected_soreness_day3_no_effect(self):
        score = self._get_tissue(arm_feel=5, arm_clarification="expected_soreness", days_since_outing=3)
        # arm_feel=5 gives +2, day 3 means no subtraction
        assert score == 2.0

    def test_consecutive_low_2_days_adds_1(self):
        score = self._get_tissue(arm_feel=5, arm_feel_history=[5])
        # arm_feel=5: +2, consecutive_low=2: +1, persistence(<=6, 2 days): 0 (need 3+)
        assert score == 3.0

    def test_consecutive_low_3_days_adds_3(self):
        score = self._get_tissue(arm_feel=5, arm_feel_history=[4, 5])
        # arm_feel=5: +2, consecutive_low=3: +3, persistence(<=6, 3 days): +1
        assert score == 6.0

    def test_rate_of_change_3_point_drop_adds_2(self):
        score = self._get_tissue(arm_feel=5, arm_feel_history=[8])
        # arm_feel=5: +2, drop 8->5 = 3 points: +2
        assert score == 4.0

    def test_rate_of_change_2_point_drop_no_effect(self):
        score = self._get_tissue(arm_feel=6, arm_feel_history=[8])
        # arm_feel=6: +1, drop 8->6 = 2 points: no effect
        assert score == 1.0

    def test_persistence_3_days_adds_1(self):
        score = self._get_tissue(arm_feel=6, arm_feel_history=[6, 6])
        # arm_feel=6: +1, persistence=3: +1
        assert score == 2.0

    def test_persistence_2_days_no_effect(self):
        score = self._get_tissue(arm_feel=6, arm_feel_history=[6])
        # arm_feel=6: +1, persistence=2: no bonus (need 3+)
        assert score == 1.0

    def test_negative_slope_adds_half(self):
        # 7 values with declining trend: 9,8,7,7,6,6,5
        # values list is [most recent, ..., oldest] so: [5,6,6,7,7,8,9]
        # _compute_slope reverses, x=0 oldest, x=6 newest, so time order: 9,8,7,7,6,6,5
        # This is a negative slope (declining over time)
        history = [6, 6, 7, 7, 8, 9]  # previous 6 days, newest first
        score = self._get_tissue(arm_feel=5, arm_feel_history=history)
        # arm_feel=5: +2, consecutive_low(5, [6,6,7...]): 1 (only today), persistence(6, [6,6,7,7,8,9]): 3 days -> +1
        # slope negative: +0.5
        assert score == 3.5

    def test_combined_tissue_scoring(self):
        """Multiple signals stack."""
        score = self._get_tissue(
            arm_feel=5, forearm_tightness="moderate", grip_drop=True,
        )
        # arm_feel=5: +2, moderate: +3, grip_drop: +2 = 7
        assert score == 7.0


# ═══════════════════════════════════════════════════════════════════════════
# LOAD SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadScoring:
    def _get_load(self, **kwargs):
        from bot.services.triage import _compute_load_score
        defaults = dict(
            pitch_count=None, days_since_outing=3, rotation_length=7,
            whoop_strain_yesterday=None, reliever_appearances_7d=None,
        )
        defaults.update(kwargs)
        return _compute_load_score(**defaults)

    def test_no_inputs_is_zero(self):
        assert self._get_load() == 0.0

    def test_pitch_count_59_is_zero(self):
        assert self._get_load(pitch_count=59) == 0.0

    def test_pitch_count_60_adds_1(self):
        assert self._get_load(pitch_count=60) == 1.0

    def test_pitch_count_79_adds_1(self):
        assert self._get_load(pitch_count=79) == 1.0

    def test_pitch_count_80_adds_2(self):
        assert self._get_load(pitch_count=80) == 2.0

    def test_pitch_count_99_adds_2(self):
        assert self._get_load(pitch_count=99) == 2.0

    def test_pitch_count_100_adds_3(self):
        assert self._get_load(pitch_count=100) == 3.0

    def test_days_since_outing_0_adds_2(self):
        # days_since_outing=0, rotation_length=7 -> days_to_start=7 (no start prox)
        assert self._get_load(days_since_outing=0) == 2.0

    def test_days_since_outing_1_adds_2(self):
        assert self._get_load(days_since_outing=1) == 2.0

    def test_days_since_outing_2_adds_1(self):
        assert self._get_load(days_since_outing=2) == 1.0

    def test_days_since_outing_3_adds_0(self):
        assert self._get_load(days_since_outing=3) == 0.0

    def test_start_proximity_0_days(self):
        # days_since_outing=7, rotation_length=7 -> days_to_start=0 -> +2
        assert self._get_load(days_since_outing=7, rotation_length=7) == 2.0

    def test_start_proximity_1_day(self):
        # days_since_outing=6, rotation_length=7 -> days_to_start=1 -> +2
        assert self._get_load(days_since_outing=6, rotation_length=7) == 2.0

    def test_start_proximity_2_days(self):
        # days_since_outing=5, rotation_length=7 -> days_to_start=2 -> +1
        assert self._get_load(days_since_outing=5, rotation_length=7) == 1.0

    def test_start_proximity_3_days_no_effect(self):
        # days_since_outing=4, rotation_length=7 -> days_to_start=3 -> no effect
        assert self._get_load(days_since_outing=4, rotation_length=7) == 0.0

    def test_whoop_strain_14_no_effect(self):
        assert self._get_load(whoop_strain_yesterday=14.0) == 0.0

    def test_whoop_strain_15_adds_1(self):
        assert self._get_load(whoop_strain_yesterday=15.0) == 1.0

    def test_whoop_strain_18_adds_1(self):
        assert self._get_load(whoop_strain_yesterday=18.0) == 1.0

    def test_whoop_strain_19_adds_2(self):
        assert self._get_load(whoop_strain_yesterday=19.0) == 2.0

    def test_reliever_appearances_1_no_effect(self):
        assert self._get_load(reliever_appearances_7d=1) == 0.0

    def test_reliever_appearances_2_adds_1(self):
        assert self._get_load(reliever_appearances_7d=2) == 1.0

    def test_reliever_appearances_3_adds_3(self):
        assert self._get_load(reliever_appearances_7d=3) == 3.0

    def test_combined_load_scoring(self):
        """Multiple load signals stack."""
        score = self._get_load(
            pitch_count=100, days_since_outing=0, whoop_strain_yesterday=20.0,
        )
        # pitch 100: +3, days 0: +2, strain 20: +2 = 7
        assert score == 7.0


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERY SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRecoveryScoring:
    def _get_recovery(self, **kwargs):
        from bot.services.triage import _compute_recovery_score
        defaults = dict(
            sleep_hours=8.0, whoop_recovery=None, whoop_hrv=None,
            whoop_hrv_7day_avg=None, whoop_sleep_perf=None, energy=None,
        )
        defaults.update(kwargs)
        return _compute_recovery_score(**defaults)

    def test_no_signals_is_zero(self):
        assert self._get_recovery() == 0.0

    def test_sleep_under_5_adds_3(self):
        assert self._get_recovery(sleep_hours=4.5) == 3.0

    def test_sleep_5_to_6_adds_2(self):
        assert self._get_recovery(sleep_hours=5.5) == 2.0

    def test_sleep_6_to_7_adds_1(self):
        assert self._get_recovery(sleep_hours=6.5) == 1.0

    def test_sleep_7_plus_adds_0(self):
        assert self._get_recovery(sleep_hours=7.0) == 0.0

    def test_whoop_recovery_under_33_adds_2(self):
        assert self._get_recovery(whoop_recovery=20.0) == 2.0

    def test_whoop_recovery_33_to_50_adds_1(self):
        assert self._get_recovery(whoop_recovery=40.0) == 1.0

    def test_whoop_recovery_50_plus_adds_0(self):
        assert self._get_recovery(whoop_recovery=60.0) == 0.0

    def test_hrv_drop_over_15_adds_2(self):
        # (60-40)/60 = 33% drop
        assert self._get_recovery(whoop_hrv=40.0, whoop_hrv_7day_avg=60.0) == 2.0

    def test_hrv_drop_10_to_15_adds_1(self):
        # (60-52.8)/60 = 12% drop
        assert self._get_recovery(whoop_hrv=52.8, whoop_hrv_7day_avg=60.0) == 1.0

    def test_hrv_drop_under_10_adds_0(self):
        # (60-55)/60 = 8.3% drop
        assert self._get_recovery(whoop_hrv=55.0, whoop_hrv_7day_avg=60.0) == 0.0

    def test_sleep_perf_under_50_adds_1(self):
        assert self._get_recovery(whoop_sleep_perf=40) == 1.0

    def test_sleep_perf_50_plus_adds_0(self):
        assert self._get_recovery(whoop_sleep_perf=60) == 0.0

    def test_energy_3_or_less_adds_2(self):
        assert self._get_recovery(energy=3) == 2.0

    def test_energy_4_adds_1(self):
        assert self._get_recovery(energy=4) == 1.0

    def test_energy_5_plus_adds_0(self):
        assert self._get_recovery(energy=5) == 0.0

    def test_combined_recovery_scoring(self):
        """Multiple recovery signals stack."""
        score = self._get_recovery(
            sleep_hours=4.0, whoop_recovery=20.0, energy=3,
        )
        # sleep <5: +3, recovery <33: +2, energy <=3: +2 = 7
        assert score == 7.0


# ═══════════════════════════════════════════════════════════════════════════
# INTERACTION RULES TESTS (new path with pitcher_baseline)
# ═══════════════════════════════════════════════════════════════════════════

def _make_baseline(tier=3, drift_flagged=False):
    """Minimal baseline dict for testing the new path."""
    return {
        "tier": tier,
        "rotation_day_baselines": {},
        "overall_mean": 7.5,
        "overall_sd": 1.2,
        "rotations_completed": 3 if tier == 3 else 1 if tier == 2 else 0,
        "total_check_ins": 30 if tier == 3 else 10 if tier == 2 else 0,
        "rolling_14d_mean": None,
        "prior_14d_mean": None,
        "chronic_drift": 0.0,
        "drift_threshold": 1.0,
        "drift_flagged": drift_flagged,
        "computed_at": "2026-04-18T09:00:00-05:00",
    }


class TestInteractionRules:
    """Test the new interaction-rules path (pitcher_baseline provided, tier 3 = tb=0)."""

    def test_red_tissue_alone(self):
        """tissue >= 7 alone -> RED."""
        from bot.services.triage import triage
        # arm_feel=5 (+2) + moderate tightness (+3) + grip_drop (+2) = tissue 7
        profile = _make_profile(grip_drop=True)
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            forearm_tightness="moderate",
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "red"
        assert result["category_scores"]["tissue"] >= 7.0

    def test_red_tissue_plus_load(self):
        """tissue >= 4 AND load >= 4 -> RED."""
        from bot.services.triage import triage
        # arm_feel=5 (+2) + grip_drop (+2) = tissue 4
        # pitch_count=100 (+3) + days_since_outing=1 (+2) = load 5
        profile = _make_profile(grip_drop=True, days_since_outing=1)
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            pitch_count=100,
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "red"
        assert result["category_scores"]["tissue"] >= 4.0
        assert result["category_scores"]["load"] >= 4.0

    def test_yellow_tissue_alone(self):
        """tissue >= 3 (but < 7) alone -> YELLOW."""
        from bot.services.triage import triage
        # arm_feel=5 (+2) + mild tightness (+1) = tissue 3
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=_make_profile(),
            forearm_tightness="mild",
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "yellow"
        assert result["category_scores"]["tissue"] >= 3.0

    def test_yellow_load_plus_recovery(self):
        """load >= 4 AND recovery >= 4 -> YELLOW."""
        from bot.services.triage import triage
        # load: pitch_count=100 (+3) + days_since_outing=1 (+2) = 5
        # recovery: sleep <5h (+3) + energy=3 (+2) = 5
        profile = _make_profile(days_since_outing=1)
        result = triage(
            arm_feel=8, sleep_hours=4.0, pitcher_profile=profile,
            pitch_count=100, energy=3,
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "yellow"
        assert result["category_scores"]["load"] >= 4.0
        assert result["category_scores"]["recovery"] >= 4.0

    def test_yellow_chronic_drift(self):
        """chronic_drift flagged -> YELLOW."""
        from bot.services.triage import triage
        result = triage(
            arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3, drift_flagged=True),
        )
        assert result["flag_level"] == "yellow"
        assert result["trajectory_context"]["chronic_drift"] is True

    def test_yellow_recovery_stall(self):
        """Recovery curve stall -> YELLOW."""
        from bot.services.triage import triage
        # Arm feel at floor and not improving (stall)
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=_make_profile(days_since_outing=2),
            pitcher_baseline=_make_baseline(tier=3),
            recovery_curve_expected={"floor": 5, "expected": 7},
            arm_feel_history=[5],  # same as yesterday -> stall at floor
        )
        assert result["flag_level"] in ("yellow", "red")  # tissue also >= 3 from arm_feel=5

    def test_modified_green_recovery_alone(self):
        """recovery >= 3 alone -> MODIFIED_GREEN."""
        from bot.services.triage import triage
        # recovery: sleep <5h (+3) = 3
        result = triage(
            arm_feel=8, sleep_hours=4.5, pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "modified_green"
        assert result["category_scores"]["recovery"] >= 3.0

    def test_modified_green_load_alone(self):
        """load >= 3 alone -> MODIFIED_GREEN."""
        from bot.services.triage import triage
        # load: pitch_count=100 (+3) = 3
        result = triage(
            arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile(),
            pitch_count=100,
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "modified_green"
        assert result["category_scores"]["load"] >= 3.0

    def test_modified_green_tissue_1_2(self):
        """tissue 1-2 -> MODIFIED_GREEN."""
        from bot.services.triage import triage
        # arm_feel=6 -> tissue=1
        result = triage(
            arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "modified_green"
        assert 1 <= result["category_scores"]["tissue"] < 3

    def test_green_all_below(self):
        """All scores below thresholds -> GREEN."""
        from bot.services.triage import triage
        result = triage(
            arm_feel=8, sleep_hours=8.0, pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "green"

    def test_two_recovery_signals_modified_green_not_red(self):
        """Two recovery signals sum to modified_green, not red."""
        from bot.services.triage import triage
        # recovery: sleep 5-6h (+2) + whoop_recovery 33-50 (+1) = 3 -> modified_green
        result = triage(
            arm_feel=8, sleep_hours=5.5, pitcher_profile=_make_profile(),
            whoop_recovery=40.0,
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert result["flag_level"] == "modified_green"
        assert result["category_scores"]["recovery"] >= 3.0

    def test_tolerance_band_tier1_shifts_thresholds(self):
        """Tier 1 (tolerance_band=2) shifts thresholds up."""
        from bot.services.triage import triage
        # tissue=3 normally triggers YELLOW at tier 3 (tb=0)
        # At tier 1 (tb=2), threshold becomes 3+2=5, so tissue=3 -> MODIFIED_GREEN
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=_make_profile(),
            forearm_tightness="mild",
            pitcher_baseline=_make_baseline(tier=1),
        )
        # tissue = arm_feel=5 (+2) + mild (+1) = 3. tb=2, so YELLOW needs >=5, gets modified_green (3 >= 1+2=3)
        assert result["flag_level"] == "modified_green"

    def test_tolerance_band_tier2(self):
        """Tier 2 (tolerance_band=1) partially shifts thresholds."""
        from bot.services.triage import triage
        # tissue=3, tb=1, YELLOW needs >=4 -> tissue 3 not enough
        # modified_green: tissue 1+1=2 <= 3 < 3+1=4 -> yes
        result = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=_make_profile(),
            forearm_tightness="mild",
            pitcher_baseline=_make_baseline(tier=2),
        )
        assert result["flag_level"] == "modified_green"


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERY CURVE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRecoveryCurve:
    def test_stall_at_floor(self):
        """Arm feel at floor and not improving -> stall (requires days_since_outing >= 3 per I2 fix)."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=5, days_since_outing=3, rotation_length=7,
            recovery_curve_expected={"floor": 5, "expected": 7},
            arm_feel_history=[5],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["recovery_curve_status"] == "stall"

    def test_stall_at_floor_day2_returns_on_track(self):
        """I2 fix: stall detection requires N>=3. days_since_outing=2 -> on_track."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=5, days_since_outing=2, rotation_length=7,
            recovery_curve_expected={"floor": 5, "expected": 7},
            arm_feel_history=[5],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["recovery_curve_status"] == "on_track"

    def test_reversal_below_floor(self):
        """Arm feel below floor and declining -> reversal (requires days_since_outing >= 3 per I2 fix)."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=4, days_since_outing=3, rotation_length=7,
            recovery_curve_expected={"floor": 5, "expected": 7},
            arm_feel_history=[5],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["recovery_curve_status"] == "reversal"
        assert ctx["pace_below_floor"] is True
        assert ctx["pace_deficit"] == 1

    def test_on_track_above_floor(self):
        """Arm feel above floor -> on_track."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=7, days_since_outing=2, rotation_length=7,
            recovery_curve_expected={"floor": 5, "expected": 7},
            arm_feel_history=[6],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["recovery_curve_status"] == "on_track"

    def test_late_rotation_concern(self):
        """Day 5-6 with arm_feel < 6 -> late_rotation_concern."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=5, days_since_outing=5, rotation_length=7,
            recovery_curve_expected={"floor": 6, "expected": 9},
            arm_feel_history=[6],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["late_rotation_concern"] is True

    def test_no_late_rotation_concern_day3(self):
        """Day 3 -> no late_rotation_concern even with low arm feel."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=5, days_since_outing=3, rotation_length=7,
            recovery_curve_expected={"floor": 6, "expected": 8},
            arm_feel_history=[6],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["late_rotation_concern"] is False

    def test_chronic_drift_propagated(self):
        """drift_flagged from baseline propagates to trajectory context."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=7, days_since_outing=3, rotation_length=7,
            recovery_curve_expected=None, arm_feel_history=[],
            pitcher_baseline=_make_baseline(drift_flagged=True),
        )
        assert ctx["chronic_drift"] is True

    def test_no_baseline_returns_empty(self):
        """No baseline and no recovery curve -> empty context."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=7, days_since_outing=3, rotation_length=7,
            recovery_curve_expected=None, arm_feel_history=[],
            pitcher_baseline=None,
        )
        assert ctx["recovery_curve_status"] is None
        assert ctx["chronic_drift"] is False

    def test_rapid_drop_trend_flag(self):
        """3+ point drop sets rapid_drop trend flag."""
        from bot.services.triage import _evaluate_recovery_curve
        ctx = _evaluate_recovery_curve(
            arm_feel=5, days_since_outing=3, rotation_length=7,
            recovery_curve_expected=None, arm_feel_history=[8],
            pitcher_baseline=_make_baseline(),
        )
        assert ctx["trend_flags"].get("rapid_drop") is True


# ═══════════════════════════════════════════════════════════════════════════
# ARM CLARIFICATION INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestArmClarification:
    def test_concerned_increases_severity(self):
        """arm_clarification='concerned' should push tissue higher."""
        from bot.services.triage import triage
        base = triage(
            arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3),
        )
        with_concern = triage(
            arm_feel=6, sleep_hours=8.0, pitcher_profile=_make_profile(),
            arm_clarification="concerned",
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert with_concern["category_scores"]["tissue"] > base["category_scores"]["tissue"]

    def test_expected_soreness_decreases_severity_day1(self):
        """arm_clarification='expected_soreness' on day 1 should reduce tissue."""
        from bot.services.triage import triage
        profile = _make_profile(days_since_outing=1)
        base = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            pitcher_baseline=_make_baseline(tier=3),
        )
        with_expected = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            arm_clarification="expected_soreness",
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert with_expected["category_scores"]["tissue"] < base["category_scores"]["tissue"]

    def test_expected_soreness_no_reduction_day4(self):
        """arm_clarification='expected_soreness' on day 4 has no reduction."""
        from bot.services.triage import triage
        profile = _make_profile(days_since_outing=4)
        base = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            pitcher_baseline=_make_baseline(tier=3),
        )
        with_expected = triage(
            arm_feel=5, sleep_hours=8.0, pitcher_profile=profile,
            arm_clarification="expected_soreness",
            pitcher_baseline=_make_baseline(tier=3),
        )
        assert with_expected["category_scores"]["tissue"] == base["category_scores"]["tissue"]


class TestArmAssessmentTriage:
    def test_red_flag_assessment_forces_protective_result(self):
        from bot.services.triage import triage

        result = triage(
            arm_feel=8,
            sleep_hours=8.0,
            pitcher_profile=_make_profile(),
            pitcher_baseline=_make_baseline(tier=3),
            arm_assessment={
                "arm_feel": 8,
                "areas": ["elbow"],
                "sensations": ["sharp_pain"],
                "red_flags": ["sharp_pain"],
                "contradictions": ["high_arm_feel_with_red_flag"],
                "needs_followup": True,
                "followup_prompt": "Did that show up while throwing?",
                "summary": "High overall arm rating but sharp elbow pain reported.",
            },
        )

        assert result["flag_level"] == "red"
        assert "no_throwing" in result["modifications"]
        assert any("sharp pain" in a or "sharp_pain" in a for a in result["alerts"])

    def test_expected_soreness_assessment_softens_only_with_area_no_red_flags(self):
        from bot.services.triage import triage

        profile = _make_profile(days_since_outing=1)
        base = triage(
            arm_feel=5,
            sleep_hours=8.0,
            pitcher_profile=profile,
            pitcher_baseline=_make_baseline(tier=3),
        )
        expected = triage(
            arm_feel=5,
            sleep_hours=8.0,
            pitcher_profile=profile,
            pitcher_baseline=_make_baseline(tier=3),
            arm_assessment={
                "arm_feel": 5,
                "areas": ["forearm"],
                "sensations": [],
                "expected_soreness": True,
                "red_flags": [],
                "contradictions": [],
                "needs_followup": False,
                "summary": "Expected forearm soreness.",
            },
        )

        assert expected["category_scores"]["tissue"] < base["category_scores"]["tissue"]

    def test_low_score_no_issues_stays_conservative(self):
        from bot.services.triage import triage

        result = triage(
            arm_feel=4,
            sleep_hours=8.0,
            pitcher_profile=_make_profile(),
            arm_assessment={
                "arm_feel": 4,
                "detail_tags": ["no_issues"],
                "red_flags": [],
                "contradictions": ["low_arm_feel_with_no_issues"],
                "needs_followup": True,
                "summary": "Arm 4/10 with no issues reported.",
            },
        )

        assert result["flag_level"] == "red"
        assert result["arm_assessment"]["needs_followup"] is True
