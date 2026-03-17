"""Plan generator. Builds daily training protocols from templates + triage + pitcher context."""

import json
import os
import logging
from bot.config import TEMPLATES_DIR, KNOWLEDGE_DIR, CONTEXT_WINDOW_CHARS
from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import load_profile, load_context, get_recent_entries

logger = logging.getLogger(__name__)


def load_template(filename: str) -> dict:
    """Load a JSON template from the templates directory."""
    path = os.path.join(TEMPLATES_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


def load_exercise_library() -> dict:
    """Load the exercise library, indexed by exercise_id."""
    path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    with open(path, "r") as f:
        data = json.load(f)
    exercises = data.get("exercises", data) if isinstance(data, dict) else data
    return {ex["id"]: ex for ex in exercises}


def get_rotation_day(pitcher_profile: dict) -> int:
    """Calculate current rotation day from active_flags."""
    return pitcher_profile.get("active_flags", {}).get("days_since_outing", 0)


async def generate_plan(pitcher_id: str, triage_result: dict) -> dict:
    """Generate today's training protocol for a pitcher.

    Args:
        pitcher_id: The pitcher's ID
        triage_result: Output from triage()

    Returns:
        Dict with keys: narrative (str), exercise_blocks (list),
        throwing_plan (dict|None), estimated_duration_min (int|None),
        modifications_applied (list), template_day (str)
    """
    profile = load_profile(pitcher_id)
    context = load_context(pitcher_id)
    recent_logs = get_recent_entries(pitcher_id, n=3)
    rotation_day = get_rotation_day(profile)
    flag_level = triage_result["flag_level"]

    # Load templates
    rotation_template = load_template("starter_7day.json")
    day_key = f"day_{rotation_day}"
    today_template = rotation_template["days"].get(day_key, {})

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

    # Build structured exercise blocks from template data
    exercise_blocks = _build_exercise_blocks(today_template, arm_care, plyocare)

    # Build throwing plan from template
    throwing_plan = _build_throwing_plan(today_template)

    # Estimated duration
    estimated_duration_min = None
    if today_template.get("lifting"):
        estimated_duration_min = today_template["lifting"].get("duration_min")

    # Build context for LLM
    templates_context = _format_templates(today_template, arm_care, plyocare)

    # Build the pitcher context summary (keep under ~2000 tokens)
    pitcher_context = _build_pitcher_context(profile, context)

    # Load and fill the plan generation prompt
    prompt_template = load_prompt("plan_generation.md")
    system_prompt = load_prompt("system_prompt.md")

    user_prompt = prompt_template.replace("{pitcher_context}", pitcher_context)
    user_prompt = user_prompt.replace("{rotation_day}", f"Day {rotation_day} ({today_template.get('label', 'Unknown')})")
    user_prompt = user_prompt.replace("{triage_result}", json.dumps(triage_result, indent=2))
    user_prompt = user_prompt.replace("{templates}", templates_context)
    user_prompt = user_prompt.replace("{recent_logs}", json.dumps(recent_logs, indent=2))

    narrative = await call_llm(system_prompt, user_prompt, max_tokens=1500)

    return {
        "narrative": narrative,
        "exercise_blocks": exercise_blocks,
        "throwing_plan": throwing_plan,
        "estimated_duration_min": estimated_duration_min,
        "modifications_applied": triage_result.get("modifications", []),
        "template_day": day_key,
    }


def _select_plyocare(routines: dict, rotation_day: int, flag_level: str) -> dict | None:
    """Select the appropriate plyocare routine for the rotation day."""
    routines_list = routines.get("routines", [])
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


def _format_templates(today_template: dict, arm_care: dict, plyocare: dict | None) -> str:
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
    for injury in profile.get("injury_history", []):
        parts.append(f"Injury history: {injury.get('area', '')} ({injury.get('date', '')}) — {injury.get('description', '')}")

    # Training level
    training = profile.get("current_training", {})
    parts.append(f"Lifting experience: {training.get('lifting_experience', 'unknown')}")

    # Recent context (last 500 chars)
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


def _build_exercise_blocks(today_template: dict, arm_care: dict, plyocare: dict | None) -> list:
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


def _build_throwing_plan(today_template: dict) -> dict | None:
    """Extract throwing plan from the rotation day template."""
    throwing = today_template.get("throwing")
    if not throwing or throwing == "none":
        return None
    # Template stores throwing as a string key
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
    """Return preview data for the next n rotation days."""
    template = load_template("starter_7day.json")
    upcoming = []
    for i in range(1, n + 1):
        day_num = (current_rotation_day + i) % 7
        day_key = f"day_{day_num}"
        day_data = template["days"].get(day_key, {})

        # Build exercise summary from template blocks
        exercise_names = []
        lifting = day_data.get("lifting")
        if lifting and lifting.get("blocks"):
            for block in lifting["blocks"]:
                for ex in block.get("exercises", [])[:2]:
                    exercise_names.append(ex.get("exercise_id", ""))

        upcoming.append({
            "rotation_day": day_num,
            "label": day_data.get("label", f"Day {day_num}"),
            "training_intent": day_data.get("training_intent", "none"),
            "exercise_preview": ", ".join(exercise_names[:4]),
            "duration_min": lifting.get("duration_min") if lifting else None,
            "throwing": day_data.get("throwing", ""),
        })
    return upcoming
