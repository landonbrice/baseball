"""Weighted multi-factor triage system.

Evaluates check-in + outing data against profile-driven decision rules.
Returns one of 4 flags: red, yellow, modified_green, green.

Derived from arm-care-bot's determine_protocol_flag() with adaptations:
- 1-5 arm feel scale (not 1-10)
- Profile-driven instant-RED triggers based on injury history
- Modified Green tier for borderline states
- Weighted yellow trigger accumulation
"""

import logging

logger = logging.getLogger(__name__)


def triage(
    arm_feel: int, sleep_hours: float, pitcher_profile: dict,
    energy: int = None, whoop_recovery: float = None,
    forearm_tightness: str = None, ucl_sensation: bool = False,
    pitch_count: int = None,
) -> dict:
    """Run weighted triage on a pitcher's data.

    Args:
        arm_feel: 1-5 scale (1=severe pain, 5=great)
        sleep_hours: Hours of sleep last night
        pitcher_profile: Full pitcher profile dict
        energy: Optional 1-5 energy rating
        whoop_recovery: Optional WHOOP recovery percentage
        forearm_tightness: None, "mild", "moderate", "significant"
        ucl_sensation: Whether UCL-area sensation is present
        pitch_count: Pitch count (for post-outing triage)

    Returns:
        Dict with flag_level, modifications, alerts, protocol_adjustments, reasoning
    """
    active_flags = pitcher_profile.get("active_flags", {})
    injury_history = pitcher_profile.get("injury_history", [])
    days_since_outing = active_flags.get("days_since_outing", 99)
    rotation_length = pitcher_profile.get("rotation_length", 7)
    injury_areas = [i.get("area", "") for i in injury_history]

    modifications = []
    alerts = []
    protocol_adjustments = {
        "lifting_intensity_cap": None,
        "remove_exercises": [],
        "add_exercises": [],
        "arm_care_template": "heavy",
        "plyocare_allowed": True,
    }

    tightness = (forearm_tightness or "").lower()

    # ── INSTANT RED FLAGS ──

    # Universal: severe arm feel
    if arm_feel <= 1:
        return _red_result(
            "Arm feel critically low (1/5). No training. Trainer evaluation required.",
            active_flags, modifications, alerts, protocol_adjustments,
        )

    # Profile-driven: UCL sensation for medial elbow/forearm history
    if ucl_sensation and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        alerts.append("UCL-area sensation detected — immediate RED per your injury history.")
        return _red_result(
            "UCL sensation present with medial elbow history. Shutdown — trainer eval.",
            active_flags, modifications, alerts, protocol_adjustments,
        )

    # Profile-driven: significant tightness for forearm/elbow history
    if tightness == "significant" and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        alerts.append("Significant forearm tightness with elbow history — RED.")
        return _red_result(
            "Significant forearm tightness + medial elbow history. Conservative protocol.",
            active_flags, modifications, alerts, protocol_adjustments,
        )

    # Universal: arm feel ≤ 2
    if arm_feel <= 2:
        prev_feel = active_flags.get("current_arm_feel")
        if prev_feel is not None and prev_feel <= 2:
            alerts.append("URGENT: 2+ days with arm feel ≤ 2. Strongly recommend in-person trainer evaluation.")
        return _red_result(
            f"Arm feel {arm_feel}/5 triggers RED protocol. No training stress until cleared.",
            active_flags, modifications, alerts, protocol_adjustments,
        )

    # ── WEIGHTED YELLOW TRIGGERS ──

    yellow_triggers = 0
    trigger_reasons = []

    if arm_feel <= 3:
        yellow_triggers += 1
        trigger_reasons.append(f"arm feel {arm_feel}/5")

    if tightness in ("mild", "moderate"):
        yellow_triggers += 1
        trigger_reasons.append(f"forearm tightness ({tightness})")
        if "medial_elbow" in injury_areas or "forearm" in injury_areas:
            modifications.append("Elevated FPM volume — tightness flagged with elbow history")

    if pitch_count is not None and pitch_count >= 80:
        yellow_triggers += 1
        trigger_reasons.append(f"high pitch count ({pitch_count})")

    if sleep_hours < 6:
        yellow_triggers += 1
        trigger_reasons.append(f"low sleep ({sleep_hours}h)")

    if energy is not None and energy <= 2:
        yellow_triggers += 1
        trigger_reasons.append(f"low energy ({energy}/5)")

    if whoop_recovery is not None and whoop_recovery < 33:
        yellow_triggers += 1
        trigger_reasons.append(f"WHOOP recovery {whoop_recovery}%")

    # Grip drop (from active flags)
    if active_flags.get("grip_drop_reported"):
        yellow_triggers += 1
        trigger_reasons.append("grip drop reported")

    # ── EVALUATE TRIGGERS ──

    if yellow_triggers >= 2:
        alerts.append(f"Multiple risk factors: {', '.join(trigger_reasons)}.")
        modifications.append("Reduce all loads to RPE 5-6")
        modifications.append("No high-intent throwing")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 5-6"
        protocol_adjustments["remove_exercises"].extend(["med_ball", "plyometrics"])
        protocol_adjustments["plyocare_allowed"] = False
        protocol_adjustments["arm_care_template"] = "light"
        return _build_result(
            "red", modifications, alerts, protocol_adjustments,
            f"2+ yellow triggers ({', '.join(trigger_reasons)}). RED — dial back significantly.",
        )

    if yellow_triggers == 1:
        modifications.append("Reduce loads to RPE 6-7")
        modifications.append("Maintain compounds at reduced intensity")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 6-7"
        protocol_adjustments["remove_exercises"].append("med_ball")
        protocol_adjustments["plyocare_allowed"] = False
        if arm_feel >= 4:
            protocol_adjustments["arm_care_template"] = "heavy"
        return _build_result(
            "yellow", modifications, alerts, protocol_adjustments,
            f"Yellow trigger: {trigger_reasons[0]}. Train but dial back.",
        )

    # ── MODIFIED GREEN CHECKS ──

    modified_green_reasons = []

    if pitch_count is not None and 60 <= pitch_count < 80:
        modified_green_reasons.append(f"moderate pitch count ({pitch_count})")

    if 6 <= sleep_hours < 6.5:
        modified_green_reasons.append(f"borderline sleep ({sleep_hours}h)")

    if whoop_recovery is not None and 33 <= whoop_recovery < 50:
        modified_green_reasons.append(f"moderate WHOOP recovery ({whoop_recovery}%)")

    if modified_green_reasons:
        modifications.append("Modified green — proceed with awareness")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 7-8"
        return _build_result(
            "modified_green", modifications, alerts, protocol_adjustments,
            f"Modified green: {', '.join(modified_green_reasons)}. Full protocol with awareness.",
        )

    # ── GREEN: start proximity check ──

    days_to_start = rotation_length - days_since_outing
    if 0 <= days_to_start <= 2:
        modifications.append("Primer session only — start within 48h")
        modifications.append("Low volume, activation focus")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 5-6"
        protocol_adjustments["remove_exercises"].extend(["med_ball", "heavy_compounds"])
        protocol_adjustments["arm_care_template"] = "light"
        protocol_adjustments["plyocare_allowed"] = False
        return _build_result(
            "green", modifications, alerts, protocol_adjustments,
            f"Start in {days_to_start} day(s). Primer protocol to stay fresh.",
        )

    # ── FULL GREEN ──

    active_mods = active_flags.get("active_modifications", [])
    if "elevated_fpm_volume" in active_mods:
        modifications.append("Elevated FPM volume per injury history flag")

    for injury in injury_history:
        if injury.get("flag_level") == "yellow":
            ongoing = injury.get("ongoing_considerations", "")
            if ongoing:
                modifications.append(f"Ongoing: {ongoing}")

    if days_since_outing in [2, 3, 4]:
        protocol_adjustments["arm_care_template"] = "heavy"
    else:
        protocol_adjustments["arm_care_template"] = "light"

    return _build_result(
        "green", modifications, alerts, protocol_adjustments,
        f"All systems green. Arm feel {arm_feel}/5, sleep {sleep_hours}h. Full protocol.",
    )


def _red_result(reasoning, active_flags, modifications, alerts, protocol_adjustments):
    """Build a RED flag result with shutdown protocol."""
    modifications.extend([
        "No lifting today — mobility and recovery only",
        "No high-intent throwing",
    ])
    alerts.append("Recommend trainer evaluation.")
    protocol_adjustments["lifting_intensity_cap"] = "none"
    protocol_adjustments["remove_exercises"] = ["all_lifting", "med_ball", "plyometrics"]
    protocol_adjustments["arm_care_template"] = "light"
    protocol_adjustments["plyocare_allowed"] = False
    return _build_result("red", modifications, alerts, protocol_adjustments, reasoning)


def _build_result(flag_level, modifications, alerts, protocol_adjustments, reasoning):
    return {
        "flag_level": flag_level,
        "modifications": modifications,
        "alerts": alerts,
        "protocol_adjustments": protocol_adjustments,
        "reasoning": reasoning,
    }
