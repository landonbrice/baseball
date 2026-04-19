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
