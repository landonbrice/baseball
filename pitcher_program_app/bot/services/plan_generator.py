"""Plan generator. Builds daily training protocols from templates + triage + pitcher context."""

import json
import os
import logging
from bot.config import TEMPLATES_DIR, KNOWLEDGE_DIR, CONTEXT_WINDOW_CHARS
from bot.services.llm import call_llm, call_llm_reasoning, load_prompt
from bot.services.context_manager import load_profile, load_context, get_recent_entries, load_saved_plans
from bot.services.knowledge_retrieval import retrieve_research_for_plan

logger = logging.getLogger(__name__)


def load_template(filename: str) -> dict:
    """Load a JSON template from the templates directory."""
    path = os.path.join(TEMPLATES_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


def load_exercise_library() -> dict:
    """Load the exercise library, indexed by both id and slug for dual lookup."""
    path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    with open(path, "r") as f:
        data = json.load(f)
    exercises = data.get("exercises", data) if isinstance(data, dict) else data
    index = {}
    for ex in exercises:
        index[ex["id"]] = ex
        if "slug" in ex:
            index[ex["slug"]] = ex
    return index


def get_rotation_day(pitcher_profile: dict) -> int:
    """Calculate current rotation day from active_flags."""
    return (pitcher_profile.get("active_flags") or {}).get("days_since_outing", 0)


async def generate_plan(pitcher_id: str, triage_result: dict, checkin_inputs: dict = None) -> dict:
    """Generate today's training protocol for a pitcher.

    The LLM returns structured JSON with arm_care, lifting, throwing,
    notes, and superset_group fields.  Falls back to template-derived
    exercise blocks if the LLM response can't be parsed.

    Returns dict with keys:
        narrative, morning_brief, arm_care, lifting, throwing, notes,
        soreness_response, exercise_blocks, throwing_plan,
        estimated_duration_min, modifications_applied, template_day
    """
    profile = load_profile(pitcher_id)
    context = load_context(pitcher_id)
    recent_logs = get_recent_entries(pitcher_id, n=7)
    rotation_day = get_rotation_day(profile)
    rotation_length = profile.get("rotation_length", 7)
    phase = (profile.get("active_flags") or {}).get("phase", "")
    lift_pref = (checkin_inputs or {}).get("lift_preference", "")
    flag_level = triage_result["flag_level"]

    # Preference-to-template mapping
    pref_to_day = {
        "lower": "day_2",   # Lower Body — Power Focus
        "upper": "day_3",   # Upper Body — Pull Emphasis
        "full": "day_2",    # Use lower power as full body base
        "rest": "day_6",    # Rest day — arm care and mobility only
        "auto": None,       # Use rotation-based template
    }

    # Load templates
    rotation_template = load_template("starter_7day.json")

    # Determine which template to use:
    # 1. Rest day always wins — arm care/mobility only regardless of rotation
    # 2. Extended time off (past rotation cycle) or return-to-throwing: use lift preference
    # 3. Normal rotation: use rotation day
    use_preference = (
        lift_pref == "rest"
        or phase.startswith("return_to_throwing")
        or rotation_day >= rotation_length
        or not rotation_template["days"].get(f"day_{rotation_day}", {})
    )

    if use_preference and pref_to_day.get(lift_pref) is not None:
        template_day = pref_to_day[lift_pref]
        today_template = rotation_template["days"].get(template_day, {})
        # Keep actual rotation_day for context but note the override
        rotation_day = int(template_day.split("_")[1]) if "_" in template_day else rotation_day
    elif rotation_day >= rotation_length:
        # Extended time off, no specific preference — use mid-rotation template
        rotation_day = rotation_day % rotation_length
        today_template = rotation_template["days"].get(f"day_{rotation_day}", {})
    else:
        today_template = rotation_template["days"].get(f"day_{rotation_day}", {})

    # Arm care template
    arm_care_type = triage_result["protocol_adjustments"]["arm_care_template"]
    arm_care = load_template(f"arm_care_{arm_care_type}.json")

    # Plyocare (if allowed)
    plyocare = None
    if triage_result["protocol_adjustments"]["plyocare_allowed"]:
        try:
            plyocare_routines = load_template("plyocare_routines.json")
            plyocare = _select_plyocare(plyocare_routines, rotation_day, flag_level)
        except FileNotFoundError:
            logger.warning("Plyocare routines template not found")

    # Build template-derived fallback data
    fallback_exercise_blocks = _build_exercise_blocks(today_template, arm_care, plyocare)
    pitcher_role = (profile.get("pitching_profile") or {}).get("role_type", "starter")
    if "reliever" in pitcher_role.lower():
        pitcher_role = "reliever"
    else:
        pitcher_role = "starter"
    throwing_adjustments = (triage_result.get("protocol_adjustments") or {}).get("throwing_adjustments")
    throw_intent = (checkin_inputs or {}).get("throw_intent", "")
    fallback_throwing_plan = _build_throwing_plan(
        today_template, rotation_day=rotation_day, role=pitcher_role,
        throwing_adjustments=throwing_adjustments, throw_intent=throw_intent,
    )
    estimated_duration_min = None
    if today_template.get("lifting"):
        estimated_duration_min = today_template["lifting"].get("duration_min")

    # Build context for LLM
    templates_context = _format_templates(today_template, arm_care, plyocare)
    pitcher_context = _build_pitcher_context(profile, context)

    # Load research relevant to this pitcher's injury profile
    relevant_research = retrieve_research_for_plan(profile)

    # Load structured prompt and call LLM
    prompt_template = load_prompt("plan_generation_structured.md")
    system_prompt = load_prompt("system_prompt.md")

    user_prompt = prompt_template.replace("{relevant_research}", relevant_research or "No specific research loaded.")
    user_prompt = user_prompt.replace("{pitcher_context}", pitcher_context)
    actual_days_since = (profile.get("active_flags") or {}).get("days_since_outing", rotation_day)
    if actual_days_since > rotation_length:
        rotation_context = (
            f"Day {rotation_day} template ({today_template.get('label', 'Unknown')}), "
            f"but pitcher is actually {actual_days_since} days since last outing "
            f"(past normal {rotation_length}-day rotation). "
            f"Lift preference: {lift_pref or 'auto'}."
        )
    else:
        rotation_context = f"Day {rotation_day} ({today_template.get('label', 'Unknown')})"
    user_prompt = user_prompt.replace("{rotation_day}", rotation_context)
    user_prompt = user_prompt.replace("{triage_result}", json.dumps(triage_result, indent=2))
    user_prompt = user_prompt.replace("{templates}", templates_context)
    user_prompt = user_prompt.replace("{recent_logs}", json.dumps(recent_logs, indent=2))

    # Inject check-in inputs if available
    if checkin_inputs:
        inputs_text = "\n".join(
            f"{k.replace('_', ' ').title()}: {v}" for k, v in checkin_inputs.items() if v
        )
        user_prompt = user_prompt.replace("{checkin_inputs}", inputs_text)
    else:
        user_prompt = user_prompt.replace("{checkin_inputs}", "No check-in inputs provided.")

    # Use reasoning model for RTT pitchers or complex injury profiles
    use_reasoning = phase == "return_to_throwing" or flag_level == "red"
    try:
        if use_reasoning:
            raw = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000)
        else:
            raw = await call_llm(system_prompt, user_prompt, max_tokens=2000)
    except (TimeoutError, Exception) as e:
        logger.warning(f"LLM call failed for plan generation ({type(e).__name__}: {e}), using template fallback")
        return {
            "narrative": f"Your Day {rotation_day} plan is ready (built from your template).",
            "morning_brief": f"Day {rotation_day} — plan generated from template due to slow AI response.",
            "arm_care": None,
            "lifting": None,
            "throwing": fallback_throwing_plan,
            "notes": ["Plan was generated from your template. Check back later for a fully personalized version."],
            "soreness_response": None,
            "exercise_blocks": fallback_exercise_blocks,
            "throwing_plan": fallback_throwing_plan,
            "estimated_duration_min": estimated_duration_min,
            "modifications_applied": triage_result.get("modifications", []),
            "template_day": day_key,
        }

    # Parse structured JSON from LLM response
    plan = _parse_plan_json(raw)

    if plan:
        try:
            plan = _validate_plan(plan, today_template, rotation_day)

            # Structured plan parsed successfully
            morning_brief = plan.get("morning_brief", "")
            arm_care_data = plan.get("arm_care") or {}
            lifting_data = plan.get("lifting") or {}
            throwing_data = plan.get("throwing") or {}
            notes = plan.get("notes") or []
            soreness_response = plan.get("soreness_response")

            # Build narrative from structured data for backward compat
            narrative = morning_brief

            # Build exercise_blocks from structured data for backward compat
            exercise_blocks = []
            arm_exercises = arm_care_data.get("exercises") if isinstance(arm_care_data, dict) else None
            if arm_exercises and isinstance(arm_exercises, list):
                exercise_blocks.append({
                    "block_name": f"Arm Care ({arm_care_data.get('timing', 'pre-lift')})",
                    "exercises": [
                        {"exercise_id": ex.get("exercise_id", ""), "prescribed": ex.get("rx", "")}
                        for ex in arm_exercises if isinstance(ex, dict)
                    ],
                })
            lift_exercises = lifting_data.get("exercises") if isinstance(lifting_data, dict) else None
            if lift_exercises and isinstance(lift_exercises, list):
                exercise_blocks.append({
                    "block_name": f"Lifting — {lifting_data.get('intent', '')}",
                    "exercises": [
                        {"exercise_id": ex.get("exercise_id", ""), "prescribed": ex.get("rx", "")}
                        for ex in lift_exercises if isinstance(ex, dict)
                    ],
                })

            # Use structured template for throwing (phased exercises) instead of LLM text.
            # Merge any useful LLM detail/reasoning into the structured plan.
            structured_throwing = fallback_throwing_plan
            if structured_throwing and isinstance(throwing_data, dict):
                llm_detail = throwing_data.get("detail") or throwing_data.get("details") or ""
                if llm_detail and isinstance(structured_throwing, dict):
                    existing_reasoning = structured_throwing.get("reasoning", "")
                    structured_throwing["reasoning"] = f"{existing_reasoning} {llm_detail}".strip() if existing_reasoning else llm_detail

            return {
                "narrative": narrative,
                "morning_brief": morning_brief,
                "arm_care": arm_care_data,
                "lifting": lifting_data,
                "throwing": structured_throwing or throwing_data,
                "notes": notes,
                "soreness_response": soreness_response,
                "exercise_blocks": exercise_blocks,
                "throwing_plan": structured_throwing,
                "estimated_duration_min": (lifting_data or {}).get("estimated_duration_min", estimated_duration_min),
                "modifications_applied": triage_result.get("modifications", []),
                "template_day": day_key,
            }
        except Exception as e:
            logger.warning(f"Error assembling LLM plan ({type(e).__name__}: {e}), using template fallback")
            # Fall through to template fallback below

    # Fallback: LLM returned unparseable text, or plan assembly crashed
    if not plan:
        logger.warning("LLM returned non-JSON plan, using template fallback")
    return {
        "narrative": raw if raw else f"Your Day {rotation_day} plan is ready (built from your template).",
        "morning_brief": f"Day {rotation_day} plan from template.",
        "arm_care": None,
        "lifting": None,
        "throwing": fallback_throwing_plan,
        "notes": ["Plan was generated from your template."],
        "soreness_response": None,
        "exercise_blocks": fallback_exercise_blocks,
        "throwing_plan": fallback_throwing_plan,
        "estimated_duration_min": estimated_duration_min,
        "modifications_applied": triage_result.get("modifications", []),
        "template_day": day_key,
    }


def _parse_plan_json(raw: str):
    """Try to parse structured JSON from the LLM response.

    Handles responses that may have markdown fences or extra text.
    Returns the parsed dict or None if parsing fails.
    """
    import re

    text = raw.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse
    try:
        plan = json.loads(text)
        if isinstance(plan, dict) and "morning_brief" in plan:
            return plan
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    brace_start = text.find("{")
    if brace_start >= 0:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        plan = json.loads(text[brace_start:i + 1])
                        if isinstance(plan, dict) and "morning_brief" in plan:
                            return plan
                    except json.JSONDecodeError:
                        pass
                    break

    logger.warning(f"Could not parse plan JSON from LLM response (first 200 chars): {raw[:200]}")
    return None


# Exercise IDs by body focus for template adherence validation
_LOWER_BODY_IDS = {
    "ex_001", "ex_front_squat", "ex_rdl", "ex_hip_thrust", "ex_split_squat",
    "ex_goblet_squat", "ex_nordic_curl", "ex_calf_raise", "ex_lateral_lunge",
    "ex_lateral_bound", "ex_broad_jump",
}
_UPPER_BODY_IDS = {
    "ex_db_bench", "ex_landmine_press", "ex_weighted_pullup", "ex_db_row",
    "ex_face_pull", "ex_push_up_plus", "ex_ytw", "ex_band_pull_apart",
    "ex_med_ball_overhead_slam",
}
# Day-to-body-focus mapping
_DAY_BODY_FOCUS = {
    2: "lower", 4: "lower",
    3: "upper", 5: "upper",
}


def _validate_plan(plan: dict, template: dict, rotation_day: int) -> dict:
    """Post-LLM validation: enforce exercise minimums and body-part adherence."""
    lifting = plan.get("lifting") or {}
    if not lifting or not isinstance(lifting, dict):
        return plan
    exercises = lifting.get("exercises") or []
    if not isinstance(exercises, list):
        return plan

    # Full lifting days (2, 3, 4) need at least 6 exercises
    full_days = {2, 3, 4}
    if rotation_day in full_days and len(exercises) < 6:
        # Pull missing exercises from the template to fill
        template_exercises = []
        for block in (template.get("lifting") or {}).get("blocks", []):
            for ex in block.get("exercises", []):
                template_exercises.append(ex)

        existing_ids = {ex.get("exercise_id", "") for ex in exercises if isinstance(ex, dict)}
        for tex in template_exercises:
            if len(exercises) >= 7:
                break
            if tex.get("exercise_id", "") not in existing_ids:
                exercises.append({
                    "name": tex.get("exercise_id", "").replace("ex_", "").replace("_", " ").title(),
                    "exercise_id": tex.get("exercise_id", ""),
                    "rx": _PRESCRIPTION_DEFAULTS.get(tex.get("prescription_mode", "strength"), "3x8"),
                    "superset_group": None,
                    "note": "Added from template",
                })

        lifting["exercises"] = exercises

    # Body-part guardrails
    body_focus = _DAY_BODY_FOCUS.get(rotation_day)
    if body_focus == "upper":
        exercises = [ex for ex in exercises if ex.get("exercise_id") not in _LOWER_BODY_IDS]
    elif body_focus == "lower":
        exercises = [ex for ex in exercises if ex.get("exercise_id") not in _UPPER_BODY_IDS]
    lifting["exercises"] = exercises

    # Enforce duration estimate
    if not lifting.get("estimated_duration_min"):
        n = len(exercises)
        lifting["estimated_duration_min"] = max(25, n * 5)

    plan["lifting"] = lifting
    return plan


def _select_plyocare(routines: dict, rotation_day: int, flag_level: str):
    """Select the appropriate plyocare routine for the rotation day."""
    routines_data = routines.get("routines", {})
    # Handle both dict and list format
    if isinstance(routines_data, dict):
        routines_list = [{"routine_id": k, **v} for k, v in routines_data.items()]
    else:
        routines_list = routines_data
    if not routines_list:
        return None

    # Mapping rotation days to plyocare intent
    day_to_intent = {
        0: None,         # Game day — no plyo
        1: "recovery",   # Day after — recovery plyo
        2: "full",       # Heavy training day — full plyo
        3: "pre_bullpen", # Bullpen day
        4: "velo",       # Power day — velo plyo
        5: "half",       # Light day — half plyo
        6: None,         # Pre-start — no plyo
    }

    if flag_level == "yellow":
        # Downgrade to recovery or half plyo
        day_to_intent.update({2: "half", 4: "recovery"})

    intent = day_to_intent.get(rotation_day)
    if intent is None:
        return None

    # Find matching routine
    for routine in routines_list:
        routine_id = routine.get("routine_id", "").lower()
        if intent in routine_id:
            return routine

    # Fallback to first routine if no match
    return routines_list[0] if routines_list else None


def _format_templates(today_template: dict, arm_care: dict, plyocare) -> str:
    """Format templates into a readable string for the LLM prompt."""
    parts = []

    parts.append(f"### Lifting Template\n{json.dumps(today_template, indent=2)}")
    parts.append(f"### Arm Care ({arm_care.get('name', 'Unknown')})\n{json.dumps(arm_care.get('sequence', []), indent=2)}")

    if plyocare:
        parts.append(f"### Plyocare ({plyocare.get('routine_name', 'Unknown')})\n{json.dumps(plyocare, indent=2)}")
    else:
        parts.append("### Plyocare\nNot scheduled today.")

    return "\n\n".join(parts)


def _build_pitcher_context(profile: dict, context_md: str) -> str:
    """Build a concise pitcher context string for the LLM prompt."""
    parts = []
    parts.append(f"Name: {profile.get('name', 'Unknown')}")
    parts.append(f"Role: {profile.get('role', 'starter')}, {profile.get('rotation_length', 7)}-day rotation")
    parts.append(f"Throws: {profile.get('throws', 'unknown')}")

    # Active flags
    flags = profile.get("active_flags", {})
    parts.append(f"Current arm feel: {flags.get('current_arm_feel', 'N/A')}/5")
    parts.append(f"Flag level: {flags.get('current_flag_level', 'unknown')}")
    parts.append(f"Days since outing: {flags.get('days_since_outing', 'N/A')}")
    parts.append(f"Last outing: {flags.get('last_outing_pitches', 'N/A')} pitches on {flags.get('last_outing_date', 'N/A')}")

    # Active modifications
    mods = flags.get("active_modifications", [])
    if mods:
        parts.append(f"Active modifications: {', '.join(mods)}")

    # Injury history (brief)
    injury_areas = []
    for injury in profile.get("injury_history", []):
        area = injury.get("area", "")
        injury_areas.append(area)
        parts.append(f"Injury history: {area} ({injury.get('date', '')}) — {injury.get('description', '')}")
        if injury.get("ongoing_considerations"):
            parts.append(f"  Ongoing: {injury['ongoing_considerations']}")

    # Dynamic injury-specific rules (derived from THIS pitcher's profile)
    rules = []
    if "medial_elbow" in injury_areas or "forearm" in injury_areas:
        rules.append("Pronator/FPM work is non-negotiable — include in every protocol")
        rules.append("UCL-area sensation on elbow extension = immediate RED flag")
        rules.append("Forearm tightness is the primary warning sign — flag before it escalates")
    if "shoulder" in injury_areas or "labrum" in injury_areas:
        rules.append("Scapular stability work is non-negotiable — include in every protocol")
        rules.append("Neutral grip pressing only — no overhead barbell work")
        rules.append("Sharp anterior shoulder pain = immediate RED flag")
    if "lower_back" in injury_areas:
        rules.append("Reduced axial loading — prefer unilateral and supported variations")
    if "oblique" in injury_areas:
        rules.append("No rotational power work until cleared — protect the oblique")
    if "biceps" in injury_areas:
        rules.append("Monitor biceps tendon with heavy pulling — reduce chin-up volume if symptomatic")
    if rules:
        parts.append("\nPitcher-specific rules (from injury profile):")
        for r in rules:
            parts.append(f"  - {r}")

    # Training level and maxes
    training = profile.get("current_training", {})
    parts.append(f"Lifting experience: {training.get('lifting_experience', 'unknown')}")
    maxes = training.get("current_maxes", {})
    if maxes:
        maxes_str = ", ".join(f"{k}: {v}" for k, v in maxes.items())
        parts.append(f"Current maxes: {maxes_str}")

    # Physical profile for hydration/nutrition notes
    physical = profile.get("physical_profile", {})
    if physical.get("weight_lbs"):
        parts.append(f"Weight: {physical['weight_lbs']} lbs")

    # Goals
    goals = profile.get("goals", {})
    if goals.get("primary"):
        parts.append(f"Primary goal: {goals['primary']}")
    if goals.get("secondary"):
        parts.append(f"Secondary goal: {goals['secondary']}")

    # Preferences
    prefs = profile.get("preferences", {})
    detail = prefs.get("detail_level")
    if detail:
        parts.append(f"Communication preference: {detail}")
    if prefs.get("conservative_on_forearm_tightness"):
        parts.append("NOTE: Pitcher is conservative on forearm tightness — flag early")

    # Time constraints
    if training.get("time_constraints") and training["time_constraints"] not in ("", "N/A", "No"):
        parts.append(f"Time constraints: {training['time_constraints']}")
    if training.get("lift_timing"):
        parts.append(f"Usual lift timing: {training['lift_timing']}")

    # Mechanical focus (context, not coaching)
    mech = (profile.get("pitching_profile") or {}).get("mechanical_focus_areas", [])
    if mech:
        parts.append(f"Mechanical focus areas (context only): {', '.join(mech)}")

    # Phase (return-to-throwing, etc.)
    phase = flags.get("phase")
    if phase:
        parts.append(f"Current phase: {phase.replace('_', ' ')}")

    # Sleep baseline
    bio = profile.get("biometric_integration", {})
    if bio.get("avg_sleep_hours"):
        parts.append(f"Average sleep baseline: {bio['avg_sleep_hours']}h")

    # Active saved plans that modify daily programming
    try:
        pitcher_id = profile.get("pitcher_id", "")
        if pitcher_id:
            active_plans = [
                p for p in load_saved_plans(pitcher_id)
                if p.get("active") and p.get("modifies_daily_plan")
            ]
            if active_plans:
                parts.append("\nActive program modifications:")
                for p in active_plans:
                    parts.append(f"- {p['title']}: {p.get('summary', p.get('content', '')[:200])}")
    except Exception:
        pass  # Don't break plan generation if plans file missing

    # Recent training history (7-day rolling window)
    try:
        pitcher_id = profile.get("pitcher_id", "")
        if pitcher_id:
            recent_entries = get_recent_entries(pitcher_id, n=7)
            if recent_entries:
                parts.append("\nRecent training (7-day window):")
                for entry in recent_entries:
                    pt = entry.get("pre_training", {})
                    date = entry.get("date", "?")
                    arm = pt.get("arm_feel", "?")
                    flag = pt.get("flag_level", "?")

                    lifting = entry.get("lifting", {})
                    lift_str = ""
                    if lifting and lifting.get("exercises"):
                        names = [ex.get("name", "") for ex in lifting["exercises"][:4]]
                        lift_str = f" Lift: {', '.join(names)}"

                    throw_str = ""
                    throwing = entry.get("throwing", {})
                    if throwing and throwing.get("type", "none") != "none":
                        throw_str = f" Throw: {throwing['type']}"

                    skip_str = ""
                    if entry.get("skip_notes"):
                        skip_str = f" [Skipped: {entry['skip_notes']}]"

                    outing_str = ""
                    if entry.get("outing"):
                        o = entry["outing"]
                        outing_str = f" OUTING: {o.get('pitch_count','?')}pc"

                    parts.append(f"  {date}: Arm {arm}/5 {flag.upper()}.{lift_str}{throw_str}{skip_str}{outing_str}")
    except Exception:
        pass

    # Long-term memory (weekly summaries)
    summaries = profile.get("weekly_summaries", [])
    if summaries:
        recent_summaries = summaries[-14:]
        parts.append("\nPrevious session summaries:")
        for s in recent_summaries:
            parts.append(f"  {s}")

    # Recent context
    if context_md:
        recent = context_md[-CONTEXT_WINDOW_CHARS:]
        parts.append(f"\nRecent interactions:\n{recent}")

    return "\n".join(parts)


# --- Prescription mode → human-readable defaults ---
_PRESCRIPTION_DEFAULTS = {
    "power": "3×5 explosive",
    "strength": "3×5",
    "hypertrophy": "3×8-12",
    "endurance": "3×15-20 light",
    "warmup": "2×10",
}


def _build_exercise_blocks(today_template: dict, arm_care: dict, plyocare) -> list:
    """Build structured exercise_blocks from template data for the daily log."""
    blocks = []

    # Lifting blocks from rotation template
    lifting = today_template.get("lifting")
    if lifting and lifting.get("blocks"):
        for block in lifting["blocks"]:
            exercises = []
            for ex in block.get("exercises", []):
                prescribed = _PRESCRIPTION_DEFAULTS.get(ex.get("prescription_mode", ""), "")
                if ex.get("notes"):
                    prescribed = ex["notes"] if not prescribed else f"{prescribed} — {ex['notes']}"
                override = ex.get("override")
                if override:
                    parts = []
                    if "sets" in override:
                        parts.append(f"{override['sets']}×")
                    if "reps" in override:
                        parts[-1] = parts[-1] + str(override["reps"]) if parts else str(override["reps"])
                    if "intensity" in override:
                        parts.append(override["intensity"])
                    if parts:
                        prescribed = " ".join(parts)
                exercises.append({
                    "exercise_id": ex["exercise_id"],
                    "prescribed": prescribed,
                })
            blocks.append({
                "block_name": block["block_name"],
                "exercises": exercises,
            })

    # Arm care block
    arm_care_seq = arm_care.get("sequence", [])
    if arm_care_seq:
        exercises = []
        for ex in arm_care_seq:
            exercises.append({
                "exercise_id": ex.get("exercise_id", ex.get("id", "")),
                "prescribed": ex.get("prescription", ex.get("sets_reps", "")),
            })
        blocks.append({
            "block_name": f"Arm Care ({arm_care.get('name', 'Standard')})",
            "exercises": exercises,
        })

    # Plyocare block
    if plyocare:
        exercises = []
        for ex in plyocare.get("exercises", []):
            exercises.append({
                "exercise_id": ex.get("exercise_id", ex.get("id", "")),
                "prescribed": ex.get("prescription", ex.get("sets_reps", "")),
            })
        if exercises:
            blocks.append({
                "block_name": f"Plyocare ({plyocare.get('routine_name', 'Standard')})",
                "exercises": exercises,
            })

    return blocks


def _load_throwing_templates():
    """Load throwing day types, rotation map, and J-Band routine templates."""
    try:
        day_types = load_template("throwing_day_types.json")
        rotation_map = load_template("throwing_rotation_map.json")
        jband = load_template("jband_routine.json")
        return day_types, rotation_map, jband
    except FileNotFoundError as e:
        logger.warning(f"Throwing template not found: {e}")
        return None, None, None


def _resolve_throwing_phases(day_type_template: dict, jband: dict) -> list:
    """Resolve template_ref entries in phases to actual exercise lists."""
    if not day_type_template or not day_type_template.get("phases"):
        return []

    resolved_phases = []
    for phase in day_type_template["phases"]:
        template_ref = phase.get("template_ref")
        if template_ref and jband:
            # Resolve jband_routine_v1.pre_throw or jband_routine_v1.post_throw
            ref_parts = template_ref.split(".")
            if len(ref_parts) == 2 and ref_parts[0] == "jband_routine_v1":
                routine_key = ref_parts[1]
                routine = (jband or {}).get(routine_key)
                if routine:
                    # Flatten the J-Band routine phases into individual phases
                    for sub_phase in routine.get("phases", []):
                        resolved_phases.append({
                            "phase_name": sub_phase.get("phase_name", phase.get("phase_name", "")),
                            "description": sub_phase.get("description", ""),
                            "exercises": sub_phase.get("exercises", []),
                        })
                    continue
        # Non-ref phase — use directly
        resolved_phases.append({
            "phase_name": phase.get("phase_name", ""),
            "description": phase.get("description", ""),
            "exercises": phase.get("exercises", []),
        })
    return resolved_phases


def _build_throwing_plan(today_template: dict, rotation_day: int = None, role: str = "starter",
                         throwing_adjustments: dict = None, throw_intent: str = ""):
    """Build a structured throwing plan from templates.

    Returns a dict with type, label, intent, intensity_range, estimated_duration_min,
    reasoning, phases (list of exercise groups), and volume_summary.
    Falls back to legacy string mapping if new templates aren't available.

    Applies triage throwing_adjustments (max_day_type, skip_phases, override_to)
    and respects pitcher throw_intent (can downgrade but not upgrade past triage cap).
    """
    day_types, rotation_map, jband = _load_throwing_templates()
    adj = throwing_adjustments or {}

    # Triage override: force to specific day type (e.g., no_throw for RED)
    override = adj.get("override_to")

    # Try structured templates first
    if day_types and rotation_map and rotation_day is not None:
        role_key = "starter_7day" if role == "starter" else "reliever_3day"
        role_map = rotation_map.get(role_key, {})
        day_key = f"day_{rotation_day}"
        day_info = role_map.get(day_key)

        if day_info:
            day_type_key = day_info.get("day_type", "no_throw")
            original_day_type_key = day_type_key

            # Apply triage override
            if override:
                day_type_key = override

            # Apply triage max_day_type cap (downgrade if needed)
            max_day_type = adj.get("max_day_type")
            if max_day_type and not override:
                day_type_hierarchy = ["no_throw", "recovery", "recovery_short_box", "hybrid_b", "hybrid_a", "bullpen"]
                current_rank = day_type_hierarchy.index(day_type_key) if day_type_key in day_type_hierarchy else 0
                max_rank = day_type_hierarchy.index(max_day_type) if max_day_type in day_type_hierarchy else len(day_type_hierarchy)
                if current_rank > max_rank:
                    day_type_key = max_day_type

            # Apply pitcher throw_intent (can downgrade only)
            if throw_intent and not override:
                intent_map = {
                    "easy": "recovery", "light": "recovery", "catch": "recovery",
                    "long toss": "hybrid_b", "extension": "hybrid_b",
                    "pen": "bullpen", "bullpen": "bullpen",
                    "flat ground": "hybrid_b", "flatties": "hybrid_b",
                }
                for keyword, intent_type in intent_map.items():
                    if keyword in throw_intent.lower():
                        intent_hierarchy = ["no_throw", "recovery", "recovery_short_box", "hybrid_b", "hybrid_a", "bullpen"]
                        intent_rank = intent_hierarchy.index(intent_type) if intent_type in intent_hierarchy else 0
                        current_rank = intent_hierarchy.index(day_type_key) if day_type_key in intent_hierarchy else 0
                        # Pitcher intent can downgrade but not upgrade past triage cap
                        if intent_rank < current_rank:
                            day_type_key = intent_type
                        break

            day_type_template = day_types.get("day_types", {}).get(day_type_key)

            if day_type_template:
                phases = _resolve_throwing_phases(day_type_template, jband)

                # Apply triage skip_phases filter
                skip_phases = adj.get("skip_phases", [])
                if skip_phases:
                    phases = [
                        p for p in phases
                        if not any(skip.lower() in p.get("phase_name", "").lower() for skip in skip_phases)
                    ]

                # Build reasoning including triage modifications
                reasoning = day_info.get("notes", day_type_template.get("description", ""))
                if override:
                    reasoning = f"Triage override: {override}. " + reasoning
                elif max_day_type and max_day_type != day_type_key:
                    reasoning = f"Capped at {max_day_type} per triage. " + reasoning

                # Track whether triage or intent modified the plan
                triage_modified = (day_type_key != original_day_type_key)
                original_label = day_types.get("day_types", {}).get(original_day_type_key, {}).get("label", original_day_type_key)

                return {
                    "type": day_type_key,
                    "day_type_label": day_type_template.get("label", day_type_key),
                    "intent": day_type_template.get("intent"),
                    "intensity_range": adj.get("intensity_cap_pct", day_type_template.get("intensity_range", "")),
                    "estimated_duration_min": day_type_template.get("estimated_duration_min"),
                    "reasoning": reasoning,
                    "phases": phases,
                    "volume_summary": day_type_template.get("volume_summary", {}),
                    "triage_modified": triage_modified,
                    "original_day_type": original_label if triage_modified else None,
                }

    # Legacy fallback: simple string mapping from old rotation template
    throwing = today_template.get("throwing")
    if not throwing or throwing == "none":
        return None
    type_map = {
        "game_outing": ("game", "Game outing"),
        "none_or_light_catch": ("light_catch", "Light catch play only"),
        "light_long_toss_or_flat_ground": ("long_toss", "Light long toss or flat ground work"),
        "bullpen_or_long_toss": ("bullpen", "Bullpen or long toss session"),
        "flat_ground_or_light_catch": ("flat_ground", "Flat ground work or light catch"),
        "bullpen_day_or_sim": ("bullpen", "Bullpen day or simulated game"),
        "light_catch_only": ("light_catch", "Light catch play only"),
    }
    mapped = type_map.get(throwing, ("other", str(throwing)))
    return {"type": mapped[0], "details": mapped[1]}


def get_upcoming_days(pitcher_id: str, current_rotation_day: int, n: int = 3) -> list:
    """Return full exercise data for the next n rotation days."""
    template = load_template("starter_7day.json")
    exercise_lib = load_exercise_library()
    profile = load_profile(pitcher_id)
    pitcher_role = (profile.get("pitching_profile") or {}).get("role_type", "starter")
    if "reliever" in pitcher_role.lower():
        pitcher_role = "reliever"
    else:
        pitcher_role = "starter"
    upcoming = []
    for i in range(1, n + 1):
        day_num = (current_rotation_day + i) % 7
        day_key = f"day_{day_num}"
        day_data = template["days"].get(day_key, {})

        # Build full blocks with resolved exercise info
        blocks = []
        lifting = day_data.get("lifting")
        exercise_preview_names = []
        if lifting and lifting.get("blocks"):
            for block in lifting["blocks"]:
                resolved_exercises = []
                for ex in block.get("exercises", []):
                    ex_id = ex.get("exercise_id", "")
                    lib_entry = exercise_lib.get(ex_id, {})
                    resolved_exercises.append({
                        "exercise_id": ex_id,
                        "name": lib_entry.get("name", ex_id),
                        "prescribed": ex.get("prescription_mode", ""),
                        "youtube_url": lib_entry.get("youtube_url", ""),
                        "muscles_primary": lib_entry.get("muscles_primary", []),
                    })
                    if len(exercise_preview_names) < 4:
                        exercise_preview_names.append(lib_entry.get("name", ex_id))
                blocks.append({
                    "block_name": block.get("block_name", ""),
                    "exercises": resolved_exercises,
                })

        # Build structured throwing plan for this upcoming day
        throwing_plan = _build_throwing_plan(day_data, rotation_day=day_num, role=pitcher_role)

        upcoming.append({
            "rotation_day": day_num,
            "label": day_data.get("label", f"Day {day_num}"),
            "training_intent": day_data.get("training_intent", "none"),
            "exercise_preview": ", ".join(exercise_preview_names),
            "duration_min": lifting.get("duration_min") if lifting else None,
            "throwing": throwing_plan or day_data.get("throwing", ""),
            "blocks": blocks,
        })
    return upcoming
