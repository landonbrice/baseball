"""Readiness triage system. Evaluates check-in data against decision rules."""

import logging

logger = logging.getLogger(__name__)


def triage(arm_feel: int, sleep_hours: float, pitcher_profile: dict,
           energy: int = None, whoop_recovery: float = None) -> dict:
    """Run triage on a pitcher's check-in data.

    Args:
        arm_feel: 1-5 scale (1=injured, 5=great)
        sleep_hours: Hours of sleep last night
        pitcher_profile: Full pitcher profile dict
        energy: Optional 1-5 energy rating
        whoop_recovery: Optional WHOOP recovery percentage

    Returns:
        Dict with flag_level, modifications, alerts, protocol_adjustments, reasoning
    """
    active_flags = pitcher_profile.get("active_flags", {})
    injury_history = pitcher_profile.get("injury_history", [])
    days_since_outing = active_flags.get("days_since_outing", 99)
    rotation_length = pitcher_profile.get("rotation_length", 7)

    modifications = []
    alerts = []
    protocol_adjustments = {
        "lifting_intensity_cap": None,
        "remove_exercises": [],
        "add_exercises": [],
        "arm_care_template": "heavy",
        "plyocare_allowed": True,
    }

    # --- Step 1: Pain / severe arm feel ---
    if arm_feel <= 2:
        flag_level = "red"
        alerts.append("Arm feel is critically low. Recommend trainer evaluation.")
        modifications.append("No lifting today — mobility and recovery only")
        modifications.append("No high-intent throwing")
        protocol_adjustments["lifting_intensity_cap"] = "none"
        protocol_adjustments["remove_exercises"] = ["all_lifting", "med_ball", "plyometrics"]
        protocol_adjustments["arm_care_template"] = "light"
        protocol_adjustments["plyocare_allowed"] = False

        # Check for consecutive low days
        prev_feel = active_flags.get("current_arm_feel")
        if prev_feel is not None and prev_feel <= 2:
            alerts.append("URGENT: 2+ days with arm feel ≤ 2. Strongly recommend in-person trainer evaluation today.")

        return _build_result(flag_level, modifications, alerts, protocol_adjustments,
                             "Arm feel ≤ 2 triggers RED protocol. No training stress until cleared.")

    # --- Step 2: ROM red flags (if data available) ---
    # ROM data would come from biometric integration — placeholder for future
    # If implemented: check total rotation deficit >5°, flexion deficit ≥5°

    # --- Step 3: Grip/finger flexion drop ---
    grip_drop = active_flags.get("grip_drop_reported", False)
    if grip_drop:
        modifications.append("Reduce forearm load today — grip drop flagged")
        modifications.append("Emphasize recovery + capacity work later this week")
        protocol_adjustments["remove_exercises"].append("heavy_fpm")
        # Continue to further checks (YELLOW, not immediate return)

    # --- Step 4: Start within 48 hours ---
    days_to_start = rotation_length - days_since_outing
    if days_to_start <= 2 and days_to_start >= 0:
        flag_level = "yellow" if grip_drop else "green"
        modifications.append("Primer session only — start within 48h")
        modifications.append("Low volume, activation focus, no new exercises")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 5-6"
        protocol_adjustments["remove_exercises"].extend(["med_ball", "heavy_compounds"])
        protocol_adjustments["arm_care_template"] = "light"
        protocol_adjustments["plyocare_allowed"] = False
        reasoning = f"Start in {days_to_start} day(s). Primer protocol to stay fresh."
        if grip_drop:
            reasoning += " Grip drop also flagged — monitoring."
        return _build_result(flag_level, modifications, alerts, protocol_adjustments, reasoning)

    # --- Step 5: Low recovery indicators ---
    low_recovery = False
    if sleep_hours < 6:
        low_recovery = True
        modifications.append(f"Sleep was {sleep_hours}h (under 6h threshold) — reducing intensity")
    if whoop_recovery is not None and whoop_recovery < 33:
        low_recovery = True
        modifications.append(f"WHOOP recovery at {whoop_recovery}% (under 33% threshold) — reducing intensity")

    if low_recovery or grip_drop:
        flag_level = "yellow"
        modifications.append("Reduce all loads to RPE 6-7")
        modifications.append("Maintain compound movements at reduced intensity")
        protocol_adjustments["lifting_intensity_cap"] = "RPE 6-7"
        protocol_adjustments["remove_exercises"].append("med_ball")
        protocol_adjustments["plyocare_allowed"] = False

        # Arm care stays heavy on heavy days unless other flags
        if arm_feel >= 4:
            protocol_adjustments["arm_care_template"] = "heavy"

        reasoning_parts = []
        if low_recovery:
            reasoning_parts.append("Recovery indicators below threshold")
        if grip_drop:
            reasoning_parts.append("Grip drop reported")
        return _build_result(flag_level, modifications, alerts, protocol_adjustments,
                             ". ".join(reasoning_parts) + ". YELLOW protocol — train but dial back.")

    # --- Step 6: All clear → GREEN ---
    flag_level = "green"

    # Apply standing modifications from profile
    active_mods = active_flags.get("active_modifications", [])
    if "elevated_fpm_volume" in active_mods:
        modifications.append("Elevated FPM volume per UCL history flag")

    # Check injury history for ongoing considerations
    for injury in injury_history:
        if injury.get("flag_level") == "yellow":
            ongoing = injury.get("ongoing_considerations", "")
            if ongoing:
                modifications.append(f"Ongoing: {ongoing}")

    # Determine arm care template based on rotation day
    # Heavy days: Day 2, 3, 4 (further from outing). Light days: Day 0, 1, 5, 6
    if days_since_outing in [2, 3, 4]:
        protocol_adjustments["arm_care_template"] = "heavy"
    else:
        protocol_adjustments["arm_care_template"] = "light"

    return _build_result(flag_level, modifications, alerts, protocol_adjustments,
                         f"All systems green. Arm feel {arm_feel}/5, sleep {sleep_hours}h. Full protocol.")


def _build_result(flag_level, modifications, alerts, protocol_adjustments, reasoning):
    return {
        "flag_level": flag_level,
        "modifications": modifications,
        "alerts": alerts,
        "protocol_adjustments": protocol_adjustments,
        "reasoning": reasoning,
    }
