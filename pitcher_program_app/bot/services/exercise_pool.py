"""Dynamic exercise pool builder — selects exercises from the library based on
day focus, training intent, injury history, and recent usage.

Replaces static template-based exercise selection. The LLM receives
pre-selected exercises and personalizes prescriptions/narrative.
"""

import logging
import random
from bot.services.db import get_exercises

logger = logging.getLogger(__name__)

# Cached exercise library (loaded once per process)
_EXERCISE_CACHE = None


def _load_exercises() -> list:
    global _EXERCISE_CACHE
    if _EXERCISE_CACHE is None:
        _EXERCISE_CACHE = get_exercises()
        logger.info("Exercise library loaded: %d exercises", len(_EXERCISE_CACHE))
    return _EXERCISE_CACHE


# Map injury areas from pitcher profiles to modification_flags keys
INJURY_TO_FLAG = {
    "medial_elbow": "ucl_history",
    "ucl": "ucl_history",
    "forearm": "ucl_history",
    "shoulder": "shoulder_impingement",
    "shoulder_impingement": "shoulder_impingement",
    "low_back": "low_back_history",
    "lumbar": "low_back_history",
    "hip": "poor_hip_mobility",
    "knee": "knee_history",
    "oblique": "oblique_strain",
}

# Categories that match each day focus
FOCUS_CATEGORIES = {
    "lower": {"lower_body_compound", "plyometric_power"},
    "upper": {"upper_body_pull", "upper_body_push"},
    "full": {"lower_body_compound", "upper_body_pull", "upper_body_push", "plyometric_power"},
    "recovery": set(),  # no lifting on recovery
}

# Session structure: (compounds, accessories, core_stability) counts
SESSION_STRUCTURE = {
    "full":     (2, 3, 2),  # full training day
    "lower":    (2, 3, 2),
    "upper":    (2, 3, 2),
    "light":    (1, 2, 1),  # light/recovery day
    "recovery": (0, 0, 0),
}

# Prescription phase defaults for display
PRESCRIPTION_DEFAULTS = {
    "power": "3x5 explosive",
    "strength": "3x5",
    "hypertrophy": "3x8-12",
    "endurance": "3x15-20 light",
    "warmup": "2x10",
}


def build_exercise_pool(
    rotation_day: int,
    day_focus: str,
    training_intent: str,
    pitcher_profile: dict,
    recent_exercise_ids: set,
    triage_result: dict,
) -> list[dict]:
    """Select exercises from the library for today's session.

    Args:
        rotation_day: Current rotation day (0-6)
        day_focus: "lower", "upper", "full", or "recovery"
        training_intent: "power", "strength", "hypertrophy", or "endurance"
        pitcher_profile: Full pitcher profile with injury_history
        recent_exercise_ids: exercise_ids used in last 7 days
        triage_result: Triage output with flag_level, protocol_adjustments

    Returns:
        List of exercise block dicts matching the UI's expected structure:
        [{"block_name": "...", "exercises": [{"exercise_id", "name", "prescribed"}, ...]}]
    """
    if day_focus == "recovery":
        return []  # no lifting on recovery — arm care template handles it

    all_exercises = _load_exercises()
    day_key = f"day_{rotation_day}"
    injuries = pitcher_profile.get("injury_history", [])
    injury_areas = [i.get("area", "") for i in injuries]
    flag_level = triage_result.get("flag_level", "green")

    # Step 1: Filter eligible exercises
    eligible = []
    for ex in all_exercises:
        # Skip arm care / throwing / mobility / conditioning (handled separately)
        cat = ex.get("category", "")
        if cat in ("throwing_warmup", "plyo_throwing", "mobility", "conditioning",
                    "forearm_fpm", "scapular_stability"):
            continue

        # Skip if contraindicated
        contras = ex.get("contraindications") or []
        pitcher_conditions = set()
        for area in injury_areas:
            if "low_back" in area or "lumbar" in area:
                pitcher_conditions.add("acute_low_back")
                pitcher_conditions.add("lumbar_disk_issues")
            if "oblique" in area:
                pitcher_conditions.add("oblique_strain")
        if pitcher_conditions & set(contras):
            continue

        # Skip if exercise avoids this rotation day
        usage = ex.get("rotation_day_usage") or {}
        avoid = usage.get("avoid") or []
        if day_key in avoid:
            continue

        # Check modification flags — skip if "skip_entirely"
        skip = False
        mods = ex.get("modification_flags") or {}
        for area in injury_areas:
            flag_key = INJURY_TO_FLAG.get(area)
            if flag_key and flag_key in mods:
                action = mods[flag_key]
                if action == "skip_entirely":
                    skip = True
                    break
        if skip:
            continue

        eligible.append(ex)

    # Step 2: Categorize
    focus_cats = FOCUS_CATEGORIES.get(day_focus, set())
    compounds = [ex for ex in eligible
                 if ex.get("category") in focus_cats
                 and "compound" in (ex.get("tags") or [])]
    accessories = [ex for ex in eligible
                   if ex.get("category") in focus_cats
                   and "compound" not in (ex.get("tags") or [])]
    core = [ex for ex in eligible if ex.get("category") == "core"]
    # Include plyometric_power as compounds for lower days
    if day_focus in ("lower", "full"):
        plyo = [ex for ex in eligible if ex.get("category") == "plyometric_power"]
        compounds = compounds + plyo

    # Step 3: Select with variety (prefer fresh exercises)
    n_compound, n_accessory, n_core = SESSION_STRUCTURE.get(
        "light" if flag_level in ("red", "yellow") else day_focus,
        (2, 3, 2)
    )

    selected_compounds = _pick(compounds, n_compound, recent_exercise_ids, day_key)
    selected_accessories = _pick(accessories, n_accessory, recent_exercise_ids, day_key)
    selected_core = _pick(core, n_core, recent_exercise_ids, day_key)

    # Step 4: Build blocks with prescriptions
    blocks = []

    if selected_compounds:
        blocks.append({
            "block_name": "Power" if training_intent == "power" else "Strength",
            "exercises": [
                _format_exercise(ex, training_intent, injuries)
                for ex in selected_compounds
            ],
        })

    if selected_accessories:
        blocks.append({
            "block_name": "Accessories",
            "exercises": [
                _format_exercise(ex, training_intent, injuries)
                for ex in selected_accessories
            ],
        })

    if selected_core:
        blocks.append({
            "block_name": "Core + Stability",
            "exercises": [
                _format_exercise(ex, _core_intent(training_intent), injuries)
                for ex in selected_core
            ],
        })

    total = sum(len(b["exercises"]) for b in blocks)
    logger.info("Exercise pool built: %d exercises (%d compounds, %d accessories, %d core) for day_%d %s/%s",
                total, len(selected_compounds), len(selected_accessories), len(selected_core),
                rotation_day, day_focus, training_intent)

    return blocks


def _pick(pool: list, n: int, recent_ids: set, day_key: str) -> list:
    """Pick n exercises from pool, preferring fresh (not recently used) and recommended for this day."""
    if not pool or n <= 0:
        return []

    # Score: recommended > acceptable, fresh > stale
    def score(ex):
        usage = ex.get("rotation_day_usage") or {}
        recommended = day_key in (usage.get("recommended") or [])
        fresh = ex["id"] not in recent_ids
        return (fresh, recommended, random.random())  # random tiebreak for variety

    ranked = sorted(pool, key=score, reverse=True)
    return ranked[:n]


def _format_exercise(ex: dict, intent: str, injuries: list) -> dict:
    """Format an exercise for the plan with prescription from the requested intent."""
    rx = ex.get("prescription") or {}
    phase = rx.get(intent) or rx.get("strength") or rx.get("endurance") or {}

    if phase.get("sets") and phase.get("reps"):
        prescribed = f"{phase['sets']}x{phase['reps']}"
        if phase.get("intensity"):
            prescribed += f" @ {phase['intensity']}"
    else:
        prescribed = PRESCRIPTION_DEFAULTS.get(intent, "3x8")

    note = phase.get("note", "")

    # Apply modification flags as notes
    mods = ex.get("modification_flags") or {}
    for injury in injuries:
        area = injury.get("area", "")
        flag_key = INJURY_TO_FLAG.get(area)
        if flag_key and flag_key in mods:
            action = mods[flag_key]
            if action != "no_modification_needed" and action != "skip_entirely":
                note = (note + " " + action.replace("_", " ")).strip() if note else action.replace("_", " ")

    result = {
        "exercise_id": ex["id"],
        "name": ex.get("name", ex["id"]),
        "prescribed": prescribed,
    }
    if note:
        result["note"] = note

    return result


def _core_intent(intent: str) -> str:
    """Core exercises use endurance mode unless it's a strength day."""
    return "endurance" if intent in ("power", "hypertrophy") else intent


def get_recent_exercise_ids(pitcher_id: str, days: int = 7) -> set:
    """Return exercise_ids from the last N days of daily_entries."""
    from bot.services.db import get_daily_entries
    entries = get_daily_entries(pitcher_id, limit=days)
    ids = set()
    for entry in entries:
        for block in ((entry.get("plan_generated") or {}).get("exercise_blocks") or []):
            for ex in (block.get("exercises") or []):
                if ex.get("exercise_id"):
                    ids.add(ex["exercise_id"])
        for ex_id in (entry.get("completed_exercises") or {}):
            ids.add(ex_id)
    return ids
