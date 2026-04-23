"""Three-category scoring triage system (Phase 1: Trajectory-Aware).

Computes three independent scores for every call:
  - Tissue (0-10): arm condition, injury signals, recovery curve violations
  - Load (0-10): pitch count, days since outing, start proximity, strain
  - Recovery (0-10): sleep, WHOOP recovery, HRV, energy

Flag-level determination:
  - WITHOUT Phase 1 args: legacy flat yellow-trigger counting (backward compat)
  - WITH Phase 1 args: interaction rules on the three category scores

Both paths return the same output shape including the new additive fields
(category_scores, trajectory_context, baseline_tier).
"""

import logging

logger = logging.getLogger(__name__)


def triage(
    arm_feel: int, sleep_hours: float, pitcher_profile: dict,
    energy: int = None, whoop_recovery: float = None,
    whoop_hrv: float = None, whoop_hrv_7day_avg: float = None,
    whoop_sleep_perf: int = None,
    forearm_tightness: str = None, ucl_sensation: bool = False,
    pitch_count: int = None,
    # ── Phase 1 args (all optional, backward compat when absent) ──
    pitcher_baseline: dict = None,
    arm_feel_history: list = None,
    recovery_curve_expected: dict = None,
    arm_clarification: str = None,
    arm_assessment: dict = None,
    reliever_appearances_7d: int = None,
    whoop_strain_yesterday: float = None,
) -> dict:
    """Run triage on a pitcher's data.

    When called without Phase 1 args (pitcher_baseline, arm_feel_history, etc.),
    produces identical flag_level to the original flat-counting triage.
    When called with Phase 1 args, uses three-category interaction rules.

    Returns:
        Dict with flag_level, modifications, alerts, protocol_adjustments,
        reasoning, category_scores, trajectory_context, baseline_tier
    """
    active_flags = pitcher_profile.get("active_flags", {})
    injury_history = pitcher_profile.get("injury_history", [])
    days_since_outing = active_flags.get("days_since_outing", 99)
    rotation_length = pitcher_profile.get("rotation_length", 7)
    injury_areas = [i.get("area", "") for i in injury_history]

    modifications = []
    alerts = []
    protocol_adjustments = _default_protocol_adjustments()

    tightness = (forearm_tightness or "").lower()
    assessment = arm_assessment or {}
    assessment_red_flags = set(assessment.get("red_flags") or [])
    assessment_contradictions = set(assessment.get("contradictions") or [])
    assessment_sensations = set(assessment.get("sensations") or [])
    high_priority_assessment = assessment_red_flags.intersection({
        "sharp_pain", "numb_tingling", "swelling", "felt_a_pop", "grip_weakness",
    })
    if not arm_clarification and assessment.get("expected_soreness"):
        arm_clarification = "expected_soreness"
    elif not arm_clarification and (
        assessment.get("needs_followup") or "different_than_normal" in assessment_sensations
    ):
        arm_clarification = "concerned"

    has_trajectory_data = pitcher_baseline is not None
    tier = _get_tier(pitcher_baseline)

    # ── INSTANT RED FLAGS (fire for both legacy and new paths) ──

    # Universal: severe arm feel (1-2)
    if arm_feel <= 2:
        return _red_result(
            "Arm feel critically low (1-2/10). No training. Trainer evaluation required.",
            active_flags, modifications, alerts, protocol_adjustments,
            _scores(tissue=8, load=0, recovery=0),
            _empty_trajectory_context(), tier, arm_assessment=assessment,
        )

    # Structured assessment red flags override a high numeric rating.
    if high_priority_assessment:
        red_flag_text = ", ".join(sorted(high_priority_assessment))
        alerts.append(f"Arm assessment red flag reported: {red_flag_text}.")
        if assessment.get("followup_prompt"):
            alerts.append(assessment["followup_prompt"])
        return _red_result(
            "Structured arm assessment red flag. Protective protocol until clarified.",
            active_flags, modifications, alerts, protocol_adjustments,
            _scores(tissue=8, load=0, recovery=0),
            _empty_trajectory_context(), tier, arm_assessment=assessment,
        )

    # Profile-driven: UCL sensation for medial elbow/forearm history
    if ucl_sensation and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        alerts.append("UCL-area sensation detected — immediate RED per your injury history.")
        return _red_result(
            "UCL sensation present with medial elbow history. Shutdown — trainer eval.",
            active_flags, modifications, alerts, protocol_adjustments,
            _scores(tissue=8, load=0, recovery=0),
            _empty_trajectory_context(), tier, arm_assessment=assessment,
        )

    # Profile-driven: significant tightness for forearm/elbow history
    if tightness == "significant" and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        alerts.append("Significant forearm tightness with elbow history — RED.")
        return _red_result(
            "Significant forearm tightness + medial elbow history. Conservative protocol.",
            active_flags, modifications, alerts, protocol_adjustments,
            _scores(tissue=6, load=0, recovery=0),
            _empty_trajectory_context(), tier, arm_assessment=assessment,
        )

    # C4 fix: arm_feel=4 + expected_soreness on day 0-2 post-outing bypasses
    # the instant RED shortcut and falls through to full category scoring.
    # arm_feel=3 is too severe for this exception — still shortcuts to RED.
    soreness_exception = (
        arm_clarification == "expected_soreness"
        and arm_feel == 4  # arm_feel 3 still short-circuits RED
        and 0 <= days_since_outing <= 2
    )

    # Universal: arm feel <= 4 (instant RED in both paths, unless soreness exception)
    if arm_feel <= 4 and not soreness_exception:
        prev_feel = active_flags.get("current_arm_feel")
        if prev_feel is not None and prev_feel <= 4:
            alerts.append("URGENT: 2+ days with arm feel ≤ 4. Strongly recommend in-person trainer evaluation.")
        tissue_score = {3: 5, 4: 3}.get(arm_feel, 7)
        return _red_result(
            f"Arm feel {arm_feel}/10 triggers RED protocol. No training stress until cleared.",
            active_flags, modifications, alerts, protocol_adjustments,
            _scores(tissue=tissue_score, load=0, recovery=0),
            _empty_trajectory_context(), tier, arm_assessment=assessment,
        )

    # ── Past instant REDs, arm_feel >= 5 ──

    # Always compute category scores (enrichment for both paths)
    tissue = _compute_tissue_score(
        arm_feel=arm_feel, forearm_tightness=tightness,
        ucl_sensation=ucl_sensation,
        grip_drop=active_flags.get("grip_drop_reported", False),
        arm_clarification=arm_clarification,
        days_since_outing=days_since_outing, injury_areas=injury_areas,
        arm_feel_history=arm_feel_history or [],
        pitcher_baseline=pitcher_baseline,
        recovery_curve_expected=recovery_curve_expected,
    )
    load = _compute_load_score(
        pitch_count=pitch_count, days_since_outing=days_since_outing,
        rotation_length=rotation_length,
        whoop_strain_yesterday=whoop_strain_yesterday,
        reliever_appearances_7d=reliever_appearances_7d,
    )
    recovery = _compute_recovery_score(
        sleep_hours=sleep_hours, whoop_recovery=whoop_recovery,
        whoop_hrv=whoop_hrv, whoop_hrv_7day_avg=whoop_hrv_7day_avg,
        whoop_sleep_perf=whoop_sleep_perf, energy=energy,
    )
    tissue = min(tissue, 10.0)
    load = min(load, 10.0)
    recovery = min(recovery, 10.0)
    # Note: scores is built after I1 trajectory contributions are applied below

    trajectory_ctx = _evaluate_recovery_curve(
        arm_feel=arm_feel, days_since_outing=days_since_outing,
        rotation_length=rotation_length,
        recovery_curve_expected=recovery_curve_expected,
        arm_feel_history=arm_feel_history or [],
        pitcher_baseline=pitcher_baseline,
    )

    # I1 fix: recovery curve contributions to tissue score
    curve_status = trajectory_ctx.get("recovery_curve_status")
    if curve_status == "stall":
        tissue += 2
    elif curve_status == "reversal":
        tissue += 3

    tissue += _assessment_tissue_adjustment(assessment, days_since_outing, injury_areas)

    # Pace below floor: +1 per point below
    if recovery_curve_expected and arm_feel < (recovery_curve_expected.get("floor") or 0):
        floor_val = recovery_curve_expected.get("floor")
        if floor_val is not None:
            tissue += (floor_val - arm_feel)

    # Late-rotation readiness: day 5-6 with arm_feel < 6
    if rotation_length == 7 and days_since_outing in (5, 6) and arm_feel < 6:
        tissue += 2

    tissue = max(0.0, min(tissue, 10.0))
    scores = _scores(tissue, load, recovery)

    # ── FLAG LEVEL DETERMINATION ──

    if has_trajectory_data:
        # New path: interaction rules on category scores
        from bot.services.baselines import get_tolerance_band
        tolerance_band = get_tolerance_band(tier)
        flag_level = _apply_interaction_rules(
            tissue=tissue, load=load, recovery=recovery,
            chronic_drift=trajectory_ctx.get("chronic_drift", False),
            recovery_stall=trajectory_ctx.get("recovery_curve_status") == "stall",
            pace_below_floor=trajectory_ctx.get("pace_below_floor", False),
            tolerance_band=tolerance_band,
        )
    else:
        # Legacy path: flat yellow-trigger counting (backward compat)
        flag_level = _legacy_flag_level(
            arm_feel=arm_feel, sleep_hours=sleep_hours,
            tightness=tightness, pitch_count=pitch_count,
            energy=energy, whoop_recovery=whoop_recovery,
            whoop_hrv=whoop_hrv, whoop_hrv_7day_avg=whoop_hrv_7day_avg,
            whoop_sleep_perf=whoop_sleep_perf,
            active_flags=active_flags, injury_areas=injury_areas,
        )

    flag_level = _apply_assessment_flag_floor(flag_level, assessment)

    # ── BUILD OUTPUTS ──

    modifications = _build_modifications(
        flag_level=flag_level, tightness=tightness,
        injury_areas=injury_areas, active_flags=active_flags,
        injury_history=injury_history,
        days_since_outing=days_since_outing, rotation_length=rotation_length,
    )
    alerts = _build_alerts(
        flag_level=flag_level, trajectory_ctx=trajectory_ctx,
        arm_feel=arm_feel, active_flags=active_flags,
        arm_assessment=assessment,
    )
    protocol_adjustments = _build_protocol_adjustments(
        flag_level=flag_level, arm_feel=arm_feel,
        days_since_outing=days_since_outing, rotation_length=rotation_length,
    )
    reasoning = _build_reasoning(
        flag_level, tissue, load, recovery, arm_feel, sleep_hours,
        trajectory_ctx, assessment,
    )

    return {
        "flag_level": flag_level,
        "modifications": modifications,
        "alerts": alerts,
        "protocol_adjustments": protocol_adjustments,
        "reasoning": reasoning,
        "category_scores": scores,
        "trajectory_context": trajectory_ctx,
        "baseline_tier": tier,
        "arm_assessment": assessment,
    }


# ═══════════════════════════════════════════════════════════════════════════
# LEGACY FLAG LEVEL (backward compat)
# ═══════════════════════════════════════════════════════════════════════════

def _legacy_flag_level(
    arm_feel, sleep_hours, tightness, pitch_count,
    energy, whoop_recovery, whoop_hrv, whoop_hrv_7day_avg,
    whoop_sleep_perf, active_flags, injury_areas,
):
    """Flat yellow-trigger counting — matches original triage behavior exactly."""
    yellow_triggers = 0
    trigger_reasons = []

    if arm_feel <= 6:
        yellow_triggers += 1
        trigger_reasons.append(f"arm feel {arm_feel}/10")

    if tightness in ("mild", "moderate"):
        yellow_triggers += 1
        trigger_reasons.append(f"forearm tightness ({tightness})")

    if pitch_count is not None and pitch_count >= 80:
        yellow_triggers += 1
        trigger_reasons.append(f"high pitch count ({pitch_count})")

    if sleep_hours < 6:
        yellow_triggers += 1
        trigger_reasons.append(f"low sleep ({sleep_hours}h)")

    if energy is not None and energy <= 4:
        yellow_triggers += 1
        trigger_reasons.append(f"low energy ({energy}/10)")

    if whoop_recovery is not None and whoop_recovery < 33:
        yellow_triggers += 1
        trigger_reasons.append(f"WHOOP recovery {whoop_recovery}%")

    if whoop_hrv is not None and whoop_hrv_7day_avg is not None and whoop_hrv_7day_avg > 0:
        hrv_drop_pct = (whoop_hrv_7day_avg - whoop_hrv) / whoop_hrv_7day_avg * 100
        if hrv_drop_pct > 15:
            yellow_triggers += 1
            trigger_reasons.append(f"HRV {whoop_hrv:.0f}ms, {hrv_drop_pct:.0f}% below 7d avg")

    if whoop_sleep_perf is not None and whoop_sleep_perf < 50:
        yellow_triggers += 1
        trigger_reasons.append(f"WHOOP sleep performance {whoop_sleep_perf}%")

    if active_flags.get("grip_drop_reported"):
        yellow_triggers += 1
        trigger_reasons.append("grip drop reported")

    if yellow_triggers >= 2:
        return "red"
    if yellow_triggers == 1:
        return "yellow"

    # Modified green checks
    if pitch_count is not None and 60 <= pitch_count < 80:
        return "modified_green"
    if 6 <= sleep_hours < 6.5:
        return "modified_green"
    if whoop_recovery is not None and 33 <= whoop_recovery < 50:
        return "modified_green"
    if whoop_hrv is not None and whoop_hrv_7day_avg is not None and whoop_hrv_7day_avg > 0:
        hrv_drop_pct = (whoop_hrv_7day_avg - whoop_hrv) / whoop_hrv_7day_avg * 100
        if 10 <= hrv_drop_pct <= 15:
            return "modified_green"
    if whoop_sleep_perf is not None and 50 <= whoop_sleep_perf < 70:
        return "modified_green"

    return "green"


# ═══════════════════════════════════════════════════════════════════════════
# TISSUE SCORE (0-10)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_tissue_score(
    arm_feel, forearm_tightness, ucl_sensation, grip_drop,
    arm_clarification, days_since_outing, injury_areas,
    arm_feel_history, pitcher_baseline, recovery_curve_expected,
):
    score = 0.0

    # Arm feel severity
    if arm_feel <= 2:
        score += 8
    elif arm_feel == 3:
        score += 5
    elif arm_feel == 4:
        score += 3
    elif arm_feel == 5:
        score += 2
    elif arm_feel == 6:
        score += 1
    # 7+ = 0

    # Forearm tightness
    if forearm_tightness == "mild":
        score += 1
    elif forearm_tightness == "moderate":
        score += 3
    elif forearm_tightness == "significant":
        score += 6

    # UCL sensation + relevant history
    if ucl_sensation and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
        score += 8

    # Grip drop
    if grip_drop:
        score += 2

    # Arm clarification
    if arm_clarification == "concerned":
        score += 3
    elif arm_clarification == "expected_soreness" and days_since_outing is not None and days_since_outing <= 2:
        score -= 2

    # ── Trajectory-dependent scoring (only when baseline present) ──

    # Deviation below rotation-day expected
    if recovery_curve_expected and pitcher_baseline is not None:
        expected = recovery_curve_expected.get("expected")
        if expected is not None and arm_feel < expected:
            deviation = expected - arm_feel
            if deviation >= 2:
                score += deviation

    # Recovery curve status scoring requires _evaluate_recovery_curve to be
    # called separately — those contributions are added in the main triage
    # function when trajectory data is present. The raw score from this
    # function covers the direct inputs only.

    # Consecutive low days (arm_feel <= 5)
    consecutive_low = _count_consecutive_low(arm_feel, arm_feel_history)
    if consecutive_low >= 3:
        score += 3
    elif consecutive_low == 2:
        score += 1

    # Rate of change (3+ point drop in 1 day)
    if arm_feel_history and len(arm_feel_history) >= 1:
        prev = arm_feel_history[0]
        if isinstance(prev, (int, float)) and prev - arm_feel >= 3:
            score += 2

    # Persistence (arm_feel <= 6 for 3+ consecutive days)
    persistence = _count_persistence(arm_feel, arm_feel_history)
    if persistence >= 3:
        score += 1

    # Negative slope over 7-day window
    if arm_feel_history and len(arm_feel_history) >= 6:
        slope = _compute_slope([arm_feel] + list(arm_feel_history[:6]))
        if slope < 0:
            score += 0.5

    return score


def _count_consecutive_low(current_feel, history, threshold=5):
    """Count consecutive days with arm_feel <= threshold, including today."""
    if current_feel > threshold:
        return 0
    count = 1
    for val in history:
        if isinstance(val, (int, float)) and val <= threshold:
            count += 1
        else:
            break
    return count


def _count_persistence(current_feel, history, threshold=6):
    """Count consecutive days with arm_feel <= threshold, including today."""
    if current_feel > threshold:
        return 0
    count = 1
    for val in history:
        if isinstance(val, (int, float)) and val <= threshold:
            count += 1
        else:
            break
    return count


def _compute_slope(values):
    """Simple linear regression slope over values (index 0 = most recent)."""
    n = len(values)
    if n < 2:
        return 0.0
    reversed_vals = list(reversed(values))
    x_mean = (n - 1) / 2.0
    y_mean = sum(reversed_vals) / n
    num = sum((i - x_mean) * (reversed_vals[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


# ═══════════════════════════════════════════════════════════════════════════
# LOAD SCORE (0-10)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_load_score(
    pitch_count, days_since_outing, rotation_length,
    whoop_strain_yesterday, reliever_appearances_7d,
):
    score = 0.0

    # Pitch count
    if pitch_count is not None:
        if pitch_count >= 100:
            score += 3
        elif pitch_count >= 80:
            score += 2
        elif pitch_count >= 60:
            score += 1

    # Days since outing (recent outing = higher load)
    if days_since_outing is not None:
        if days_since_outing <= 1:
            score += 2
        elif days_since_outing == 2:
            score += 1

    # Start proximity
    if days_since_outing is not None and rotation_length is not None:
        days_to_start = rotation_length - days_since_outing
        if 0 <= days_to_start <= 1:
            score += 2
        elif days_to_start == 2:
            score += 1

    # WHOOP strain yesterday
    if whoop_strain_yesterday is not None:
        if whoop_strain_yesterday > 18:
            score += 2
        elif whoop_strain_yesterday > 14:
            score += 1

    # Reliever appearances/week
    if reliever_appearances_7d is not None:
        if reliever_appearances_7d >= 3:
            score += 3
        elif reliever_appearances_7d == 2:
            score += 1

    return score


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERY SCORE (0-10)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_recovery_score(
    sleep_hours, whoop_recovery, whoop_hrv, whoop_hrv_7day_avg,
    whoop_sleep_perf, energy,
):
    score = 0.0

    # Sleep hours
    if sleep_hours < 5:
        score += 3
    elif sleep_hours < 6:
        score += 2
    elif sleep_hours < 7:
        score += 1

    # WHOOP recovery
    if whoop_recovery is not None:
        if whoop_recovery < 33:
            score += 2
        elif whoop_recovery < 50:
            score += 1

    # HRV drop
    if whoop_hrv is not None and whoop_hrv_7day_avg is not None and whoop_hrv_7day_avg > 0:
        hrv_drop_pct = (whoop_hrv_7day_avg - whoop_hrv) / whoop_hrv_7day_avg * 100
        if hrv_drop_pct > 15:
            score += 2
        elif hrv_drop_pct >= 10:
            score += 1

    # Sleep performance
    if whoop_sleep_perf is not None and whoop_sleep_perf < 50:
        score += 1

    # Energy
    if energy is not None:
        if energy <= 3:
            score += 2
        elif energy == 4:
            score += 1

    return score


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERY CURVE EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def _evaluate_recovery_curve(
    arm_feel, days_since_outing, rotation_length,
    recovery_curve_expected, arm_feel_history, pitcher_baseline,
):
    """Evaluate recovery curve status from trajectory data.

    Returns trajectory context dict with:
      recovery_curve_status: "on_track" | "stall" | "reversal" | None
      chronic_drift: bool
      pace_below_floor: bool
      pace_deficit: int
      late_rotation_concern: bool
      trend_flags: dict
    """
    ctx = _empty_trajectory_context()

    if not recovery_curve_expected and pitcher_baseline is None:
        return ctx

    floor = (recovery_curve_expected or {}).get("floor")
    expected = (recovery_curve_expected or {}).get("expected")

    # Recovery curve stall: arm_feel at or below floor and not improving.
    # I2 fix: stall detection requires N>=3 post-outing days of data.
    if floor is not None and arm_feel <= floor:
        if days_since_outing is not None and days_since_outing >= 3:
            if arm_feel_history and len(arm_feel_history) >= 1:
                prev = arm_feel_history[0]
                if isinstance(prev, (int, float)):
                    if arm_feel < prev:
                        ctx["recovery_curve_status"] = "reversal"
                    elif arm_feel <= prev:
                        ctx["recovery_curve_status"] = "stall"
                    else:
                        ctx["recovery_curve_status"] = "on_track"
                else:
                    ctx["recovery_curve_status"] = "stall"
            else:
                ctx["recovery_curve_status"] = "stall"
        else:
            # Too early to call stall — not enough post-outing data
            ctx["recovery_curve_status"] = "on_track"
    elif floor is not None and arm_feel > floor:
        ctx["recovery_curve_status"] = "on_track"

    # Pace below floor
    if floor is not None and arm_feel < floor:
        ctx["pace_below_floor"] = True
        ctx["pace_deficit"] = floor - arm_feel

    # Late-rotation readiness (day 5-6 starter, arm_feel < 6)
    if rotation_length is not None and days_since_outing is not None:
        days_to_start = rotation_length - days_since_outing
        if 1 <= days_to_start <= 2 and arm_feel < 6:
            ctx["late_rotation_concern"] = True

    # Chronic drift from baseline
    if pitcher_baseline is not None:
        ctx["chronic_drift"] = pitcher_baseline.get("drift_flagged", False)

    # Trend flags
    trend_flags = {}
    if arm_feel_history and len(arm_feel_history) >= 1:
        prev = arm_feel_history[0]
        if isinstance(prev, (int, float)) and prev - arm_feel >= 3:
            trend_flags["rapid_drop"] = True
    if arm_feel_history and len(arm_feel_history) >= 6:
        slope = _compute_slope([arm_feel] + list(arm_feel_history[:6]))
        if slope < 0:
            trend_flags["negative_slope"] = True
    ctx["trend_flags"] = trend_flags

    return ctx


def _empty_trajectory_context():
    return {
        "recovery_curve_status": None,
        "chronic_drift": False,
        "pace_below_floor": False,
        "pace_deficit": 0,
        "late_rotation_concern": False,
        "trend_flags": {},
    }


# ═══════════════════════════════════════════════════════════════════════════
# INTERACTION RULES (new path only)
# ═══════════════════════════════════════════════════════════════════════════

def _apply_interaction_rules(
    tissue, load, recovery,
    chronic_drift, recovery_stall, pace_below_floor,
    tolerance_band,
):
    """Map category scores to flag_level using interaction rules.

    tolerance_band shifts thresholds up for lower-confidence tiers.
    """
    tb = tolerance_band

    # RED: tissue alone
    if tissue >= 7 + tb:
        return "red"

    # RED: tissue + load compound
    if tissue >= 4 + tb and load >= 4 + tb:
        return "red"

    # RED: tissue + recovery stall + pace below floor
    if tissue >= 4 + tb and recovery_stall and pace_below_floor:
        return "red"

    # YELLOW: tissue alone
    if tissue >= 3 + tb:
        return "yellow"

    # YELLOW: load + recovery compound
    if load >= 4 + tb and recovery >= 4 + tb:
        return "yellow"

    # YELLOW: chronic drift
    if chronic_drift:
        return "yellow"

    # YELLOW: recovery stall
    if recovery_stall:
        return "yellow"

    # MODIFIED_GREEN: recovery alone
    if recovery >= 3 + tb:
        return "modified_green"

    # MODIFIED_GREEN: load alone
    if load >= 3 + tb:
        return "modified_green"

    # MODIFIED_GREEN: tissue 1-2 (adjusted for tolerance band)
    if 1 + tb <= tissue < 3 + tb:
        return "modified_green"

    # GREEN
    return "green"


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def _build_modifications(
    flag_level, tightness, injury_areas,
    active_flags, injury_history, days_since_outing, rotation_length,
):
    """Build modification tags from flag level."""
    mods = []

    if flag_level == "red":
        mods.extend(["no_lifting", "no_throwing"])
        mods.extend(["rpe_cap_56", "no_high_intent_throw"])
        if tightness in ("mild", "moderate") and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
            mods.append("fpm_volume")

    elif flag_level == "yellow":
        mods.extend(["rpe_cap_67", "maintain_compounds_reduced", "cap_hybrid_b"])
        if tightness in ("mild", "moderate") and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
            mods.append("fpm_volume")

    elif flag_level == "modified_green":
        mods.append("modified_green")
        if tightness in ("mild", "moderate") and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
            mods.append("fpm_volume")

    else:
        # Green
        if tightness in ("mild", "moderate") and ("medial_elbow" in injury_areas or "forearm" in injury_areas):
            mods.append("fpm_volume")

        days_to_start = rotation_length - days_since_outing if rotation_length and days_since_outing is not None else 99
        if 0 <= days_to_start <= 2:
            mods.extend(["primer_session", "low_volume_activation"])

        active_mods = active_flags.get("active_modifications", [])
        if "elevated_fpm_volume" in active_mods:
            mods.append("elevated_fpm_history")

        for injury in injury_history:
            if injury.get("flag_level") == "yellow":
                ongoing = injury.get("ongoing_considerations", "")
                if ongoing:
                    mods.append(f"Ongoing: {ongoing}")

    return mods


def _build_alerts(flag_level, trajectory_ctx, arm_feel, active_flags, arm_assessment=None):
    """Build alert strings."""
    alerts = []
    assessment = arm_assessment or {}

    if flag_level == "red":
        # Multiple risk factors alert
        alerts.append("Recommend trainer evaluation.")
        prev_feel = active_flags.get("current_arm_feel")
        if prev_feel is not None and prev_feel <= 4 and arm_feel <= 4:
            alerts.append("URGENT: 2+ days with arm feel ≤ 4. Strongly recommend in-person trainer evaluation.")

    if trajectory_ctx.get("chronic_drift"):
        alerts.append("Chronic drift detected — 14-day arm feel trending below baseline.")

    if trajectory_ctx.get("recovery_curve_status") == "stall":
        alerts.append("Recovery curve stall — arm feel not improving as expected.")
    elif trajectory_ctx.get("recovery_curve_status") == "reversal":
        alerts.append("Recovery curve reversal — arm feel declining when it should be improving.")

    if trajectory_ctx.get("late_rotation_concern"):
        alerts.append("Late-rotation readiness concern — arm feel below 6 with start approaching.")

    if trajectory_ctx.get("trend_flags", {}).get("rapid_drop"):
        alerts.append("Rapid drop detected — 3+ point decline in arm feel from previous day.")

    if assessment.get("needs_followup"):
        prompt = assessment.get("followup_prompt")
        if prompt:
            alerts.append(f"Arm follow-up needed: {prompt}")
        else:
            alerts.append("Arm follow-up needed based on assessment details.")

    for flag in assessment.get("red_flags") or []:
        if flag == "injury_history_area":
            alerts.append("Reported area overlaps injury history — staying conservative.")
            continue
        alerts.append(f"Arm assessment red flag: {flag.replace('_', ' ')}.")

    return alerts


def _build_protocol_adjustments(flag_level, arm_feel, days_since_outing, rotation_length):
    """Map flag level to protocol adjustments."""
    pa = _default_protocol_adjustments()

    if flag_level == "red":
        pa["lifting_intensity_cap"] = "none"
        pa["remove_exercises"] = ["all_lifting", "med_ball", "plyometrics"]
        pa["arm_care_template"] = "light"
        pa["plyocare_allowed"] = False
        pa["throwing_adjustments"] = {
            "max_day_type": "no_throw",
            "skip_phases": ["compression", "bullpen", "long_toss_extension", "plyo_drills"],
            "intensity_cap_pct": 0,
            "volume_modifier": 0,
            "override_to": "no_throw",
        }

    elif flag_level == "yellow":
        pa["lifting_intensity_cap"] = "RPE 6-7"
        pa["remove_exercises"].append("med_ball")
        pa["plyocare_allowed"] = False
        if arm_feel >= 7:
            pa["arm_care_template"] = "heavy"
        pa["throwing_adjustments"] = {
            "max_day_type": "hybrid_b",
            "skip_phases": ["compression", "pulldowns"],
            "intensity_cap_pct": 70,
            "volume_modifier": 0.7,
            "override_to": None,
        }

    elif flag_level == "modified_green":
        pa["lifting_intensity_cap"] = "RPE 7-8"
        pa["throwing_adjustments"] = {
            "max_day_type": "hybrid_a",
            "skip_phases": ["pulldowns"],
            "intensity_cap_pct": 85,
            "volume_modifier": 0.85,
            "override_to": None,
        }

    else:
        # Green
        days_to_start = rotation_length - days_since_outing if rotation_length and days_since_outing is not None else 99
        if 0 <= days_to_start <= 2:
            pa["lifting_intensity_cap"] = "RPE 5-6"
            pa["remove_exercises"].extend(["med_ball", "heavy_compounds"])
            pa["arm_care_template"] = "light"
            pa["plyocare_allowed"] = False
            pa["throwing_adjustments"] = {
                "max_day_type": "recovery_short_box",
                "skip_phases": ["compression", "long_toss_extension"],
                "intensity_cap_pct": 70,
                "volume_modifier": 0.6,
                "override_to": None,
            }
        else:
            if days_since_outing in [2, 3, 4]:
                pa["arm_care_template"] = "heavy"
            else:
                pa["arm_care_template"] = "light"

    return pa


def _build_reasoning(flag_level, tissue, load, recovery, arm_feel, sleep_hours, trajectory_ctx, arm_assessment=None):
    """Build human-readable reasoning string."""
    parts = []
    assessment = arm_assessment or {}

    if flag_level == "red":
        if tissue >= 7:
            parts.append(f"Tissue score {tissue:.1f}/10 alone triggers RED.")
        elif tissue >= 4 and load >= 4:
            parts.append(f"Tissue ({tissue:.1f}) + Load ({load:.1f}) compound triggers RED.")
        else:
            parts.append(f"Multiple risk factors (T:{tissue:.1f} L:{load:.1f} R:{recovery:.1f}) → RED.")
    elif flag_level == "yellow":
        if tissue >= 3:
            parts.append(f"Tissue score {tissue:.1f}/10 triggers YELLOW.")
        elif trajectory_ctx.get("chronic_drift"):
            parts.append("Chronic drift detected → YELLOW.")
        elif trajectory_ctx.get("recovery_curve_status") == "stall":
            parts.append("Recovery curve stall → YELLOW.")
        else:
            parts.append(f"Yellow trigger (T:{tissue:.1f} L:{load:.1f} R:{recovery:.1f}). Train but dial back.")
    elif flag_level == "modified_green":
        triggers = []
        if recovery >= 3:
            triggers.append(f"recovery {recovery:.1f}")
        if load >= 3:
            triggers.append(f"load {load:.1f}")
        if 1 <= tissue < 3:
            triggers.append(f"tissue {tissue:.1f}")
        if triggers:
            parts.append(f"Modified green: {', '.join(triggers)}. Full protocol with awareness.")
        else:
            parts.append("Modified green. Full protocol with awareness.")
    else:
        parts.append(f"All systems green. Arm feel {arm_feel}/10, sleep {sleep_hours}h. Full protocol.")

    if assessment.get("summary"):
        parts.append(f"Assessment: {assessment['summary']}")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _default_protocol_adjustments():
    return {
        "lifting_intensity_cap": None,
        "remove_exercises": [],
        "add_exercises": [],
        "arm_care_template": "heavy",
        "plyocare_allowed": True,
        "throwing_adjustments": {
            "max_day_type": None,
            "skip_phases": [],
            "intensity_cap_pct": None,
            "volume_modifier": 1.0,
            "override_to": None,
        },
    }


def _scores(tissue, load, recovery):
    return {"tissue": tissue, "load": load, "recovery": recovery}


def _assessment_tissue_adjustment(arm_assessment, days_since_outing, injury_areas):
    """Translate structured assessment signals into tissue-score pressure."""
    if not arm_assessment:
        return 0.0

    score = 0.0
    sensations = set(arm_assessment.get("sensations") or [])
    red_flags = set(arm_assessment.get("red_flags") or [])
    contradictions = set(arm_assessment.get("contradictions") or [])
    areas = set(arm_assessment.get("areas") or [])

    if "sharp_pain" in red_flags or "numb_tingling" in red_flags:
        score += 6
    if red_flags.intersection({"swelling", "felt_a_pop", "grip_weakness"}):
        score += 7
    if "different_than_normal" in red_flags or "different_than_normal" in sensations:
        score += 3
    if "heavy_dead" in sensations:
        score += 3
    if "tight_sore" in sensations:
        score += 1

    if "high_arm_feel_with_red_flag" in contradictions:
        score += 3
    if "low_arm_feel_with_no_issues" in contradictions:
        score += 2
    if "no_issues_with_concern_tags" in contradictions:
        score += 2
    if "expected_soreness_with_red_flag" in contradictions:
        score += 3

    injury_text = " ".join(injury_areas or [])
    if areas.intersection({"forearm", "elbow"}) and ("forearm" in injury_text or "medial_elbow" in injury_text):
        score += 1

    if arm_assessment.get("expected_soreness") and not red_flags:
        if days_since_outing is not None and 0 <= days_since_outing <= 2:
            score -= 1.5
        else:
            score += 1

    return score


def _apply_assessment_flag_floor(flag_level, arm_assessment):
    """Keep structured assessment concerns conservative on legacy triage path."""
    if not arm_assessment:
        return flag_level
    order = {"green": 0, "modified_green": 1, "yellow": 2, "red": 3}
    red_flags = set(arm_assessment.get("red_flags") or [])
    contradictions = set(arm_assessment.get("contradictions") or [])
    sensations = set(arm_assessment.get("sensations") or [])

    floor = "green"
    if red_flags.intersection({"sharp_pain", "numb_tingling", "swelling", "felt_a_pop", "grip_weakness"}):
        floor = "red"
    elif contradictions.intersection({
        "high_arm_feel_with_red_flag",
        "expected_soreness_with_red_flag",
        "no_issues_with_concern_tags",
    }) or "different_than_normal" in sensations:
        floor = "yellow"
    elif sensations.intersection({"tight_sore", "heavy_dead"}):
        floor = "modified_green"

    return floor if order[floor] > order.get(flag_level, 0) else flag_level


def _get_tier(pitcher_baseline):
    if pitcher_baseline is None:
        return 1
    return pitcher_baseline.get("tier", 1)


def _red_result(reasoning, active_flags, modifications, alerts, protocol_adjustments,
                category_scores=None, trajectory_context=None, baseline_tier=1,
                arm_assessment=None):
    """Build a RED flag result with shutdown protocol."""
    modifications.extend(["no_lifting", "no_throwing"])
    alerts.append("Recommend trainer evaluation.")
    protocol_adjustments["lifting_intensity_cap"] = "none"
    protocol_adjustments["remove_exercises"] = ["all_lifting", "med_ball", "plyometrics"]
    protocol_adjustments["arm_care_template"] = "light"
    protocol_adjustments["plyocare_allowed"] = False
    protocol_adjustments["throwing_adjustments"] = {
        "max_day_type": "no_throw",
        "skip_phases": ["compression", "bullpen", "long_toss_extension", "plyo_drills"],
        "intensity_cap_pct": 0,
        "volume_modifier": 0,
        "override_to": "no_throw",
    }
    result = {
        "flag_level": "red",
        "modifications": modifications,
        "alerts": alerts,
        "protocol_adjustments": protocol_adjustments,
        "reasoning": reasoning,
        "category_scores": category_scores or _scores(0, 0, 0),
        "trajectory_context": trajectory_context or _empty_trajectory_context(),
        "baseline_tier": baseline_tier,
        "arm_assessment": arm_assessment or {},
    }
    return result
