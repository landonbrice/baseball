"""Dynamic exercise pool builder — selects exercises from the library based on
day focus, training intent, injury history, and recent usage.

Replaces static template-based exercise selection. The LLM receives
pre-selected exercises and personalizes prescriptions/narrative.
"""

import logging
import random
from bot.services.db import get_exercises, get_exercise
from bot.services.vocabulary import INJURY_AREAS

logger = logging.getLogger(__name__)

# Snapshot cache (D5): indexed by id AND slug for dual lookup (plan_generator.py:22 pattern).
# Refreshed periodically (D6) by APScheduler job in bot/main.py.
# Lazy-miss (D6): get_exercise() falls through to Supabase when exercise_id missing.
_EXERCISE_SNAPSHOT: dict = {}
_SNAPSHOT_ROWS: list = []


def _refresh_snapshot(force: bool = False) -> None:
    """Reload exercise snapshot from Supabase. Keep last-good on transient failure (D5)."""
    global _EXERCISE_SNAPSHOT, _SNAPSHOT_ROWS
    try:
        rows = get_exercises()
    except Exception as e:
        logger.warning("Snapshot refresh failed, keeping last-good: %s", e)
        return
    new_index = {}
    for ex in rows:
        ex_id = ex.get("id")
        if ex_id:
            new_index[ex_id] = ex
        slug = ex.get("slug")
        if slug:
            new_index[slug] = ex
    _EXERCISE_SNAPSHOT = new_index
    _SNAPSHOT_ROWS = rows
    logger.info("Exercise snapshot refreshed: %d exercises", len(rows))


def _load_exercises() -> list:
    """Return the snapshot row list, refreshing lazily on first call."""
    if not _SNAPSHOT_ROWS:
        _refresh_snapshot()
    return _SNAPSHOT_ROWS


def _get_from_snapshot(exercise_id: str) -> dict | None:
    """Look up by id or slug in the snapshot, with lazy-miss fallback to Supabase (D6)."""
    if not exercise_id:
        return None
    hit = _EXERCISE_SNAPSHOT.get(exercise_id)
    if hit:
        return hit
    # Lazy miss — hit Supabase directly, then stash into snapshot so subsequent lookups are cached
    fresh = get_exercise(exercise_id)
    if fresh:
        _EXERCISE_SNAPSHOT[exercise_id] = fresh
        if fresh.get("slug"):
            _EXERCISE_SNAPSHOT[fresh["slug"]] = fresh
    return fresh


def hydrate_exercises(items: list) -> list:
    """Stamp `name` onto each item by looking up its exercise_id in the snapshot (D17).

    Leaves all other fields on each item untouched. Safe to call repeatedly.
    If an exercise_id is not found, the item is returned unchanged so callers
    can still emit their plan without crashing.
    """
    if not items:
        return items
    for item in items:
        ex_id = item.get("exercise_id")
        if not ex_id:
            continue
        if item.get("name"):
            continue  # already hydrated
        lib = _get_from_snapshot(ex_id)
        if lib and lib.get("name"):
            item["name"] = lib["name"]
    return items


# Build INJURY_TO_FLAG from vocabulary for exercise library compatibility
# The exercise library uses modification_flags keys like "ucl_history", "shoulder_impingement"
# These map from vocabulary injury areas to exercise library flag keys
# NOTE: INJURY_TO_FLAG stays because exercise library modification_flags use different
# keys than vocabulary.py. The vocabulary unifies research routing; this dict maps
# to exercise library schema. They coexist intentionally.
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
    "upper": {"upper_body_pull", "upper_body_push", "plyometric_power"},
    "full": {"lower_body_compound", "upper_body_pull", "upper_body_push", "plyometric_power"},
    "recovery": set(),  # no lifting on recovery
}

# Session structure: (compounds, accessories, core_stability, explosive) counts
SESSION_STRUCTURE = {
    "full":     (2, 3, 2, 1),  # full training day
    "lower":    (2, 3, 2, 1),
    "upper":    (2, 3, 2, 1),
    "light":    (1, 2, 1, 0),  # no explosive on light days
    "recovery": (0, 0, 0, 0),
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

    # Phase emphasis override — team periodization phase shifts training intent
    # Triage overrides (red/yellow → endurance) always take precedence
    try:
        from bot.services.db import get_current_phase
        import datetime as _dt
        import importlib as _il
        _cfg = _il.import_module("bot.config")
        _today_str = _dt.datetime.now(_cfg.CHICAGO_TZ).strftime("%Y-%m-%d")
        _team_id = pitcher_profile.get("team_id", "uchicago_baseball")
        current_phase = get_current_phase(_team_id, _today_str)
        if current_phase and current_phase.get("emphasis"):
            phase_emphasis = current_phase["emphasis"]
            emphasis_to_intent = {
                "hypertrophy": "hypertrophy",
                "strength": "strength",
                "power": "power",
                "maintenance": "endurance",
                "gpp": "hypertrophy",
            }
            if training_intent != "endurance":  # triage override (red/yellow) always wins
                training_intent = emphasis_to_intent.get(phase_emphasis, training_intent)
    except Exception as _e:
        logger.debug("Phase emphasis lookup failed (%s), using default intent", _e)

    # Load pitcher training model for preferences and equipment constraints
    from bot.services.db import get_training_model
    pitcher_id = pitcher_profile.get("pitcher_id", "")
    training_model = get_training_model(pitcher_id) if pitcher_id else {}
    preferences = training_model.get("exercise_preferences") or {}
    equipment_constraints = set(training_model.get("equipment_constraints") or [])

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

        # Skip if equipment constraint matches
        if equipment_constraints:
            ex_name_lower = (ex.get("name") or "").lower()
            skip_equip = False
            for constraint in equipment_constraints:
                equip_word = constraint.replace("no_", "").replace("_", " ")
                if equip_word in ex_name_lower:
                    skip_equip = True
                    break
            if skip_equip:
                continue

        eligible.append(ex)

    # Step 2: Categorize
    focus_cats = FOCUS_CATEGORIES.get(day_focus, set())
    # Exclude plyometric_power from compound/accessory pools — gets its own block
    lift_cats = focus_cats - {"plyometric_power"}
    compounds = [ex for ex in eligible
                 if ex.get("category") in lift_cats
                 and "compound" in (ex.get("tags") or [])]
    accessories = [ex for ex in eligible
                   if ex.get("category") in lift_cats
                   and "compound" not in (ex.get("tags") or [])]
    core = [ex for ex in eligible if ex.get("category") == "core"]

    # Step 3: Select with variety (prefer fresh exercises)
    # Flag-level volume adjustment:
    # - RED: full shutdown → light structure (1 compound + 2 accessories + 1 core, no explosive)
    # - YELLOW: caution, not shutdown → normal day_focus minus 1 accessory (keeps explosive + core)
    # - GREEN: full day_focus structure
    # This avoids the prior behavior where yellow pitchers (a large share of the
    # roster with chronic but managed conditions) got a 4-exercise plan every day.
    if flag_level == "red":
        structure = SESSION_STRUCTURE["light"]
    elif flag_level == "yellow":
        base = SESSION_STRUCTURE.get(day_focus, SESSION_STRUCTURE["full"])
        structure = (base[0], max(1, base[1] - 1), base[2], base[3])
    else:
        structure = SESSION_STRUCTURE.get(day_focus, SESSION_STRUCTURE["full"])
    n_compound, n_accessory, n_core = structure[0], structure[1], structure[2]

    selected_compounds = _pick(compounds, n_compound, recent_exercise_ids, day_key, preferences)
    selected_accessories = _pick(accessories, n_accessory, recent_exercise_ids, day_key, preferences)
    selected_core = _pick(core, n_core, recent_exercise_ids, day_key, preferences)

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

    # Step 5: Select explosive/plyometric exercise and prepend to first lift block
    explosive_count = structure[3] if len(structure) > 3 else 0
    selected_explosive = []
    if explosive_count > 0:
        used_ids = {ex["exercise_id"] for block in blocks for ex in block.get("exercises", [])}
        plyo_candidates = [
            e for e in eligible
            if e.get("category") == "plyometric_power"
            and e["id"] not in used_ids
        ]
        selected_explosive = _pick(plyo_candidates, explosive_count, recent_exercise_ids, day_key, preferences)
        if selected_explosive and blocks:
            # Insert at top of first block (Power/Strength) — explosive before heavy lifts
            formatted = [_format_exercise(ex, "power", injuries) for ex in selected_explosive]
            blocks[0]["exercises"] = formatted + blocks[0]["exercises"]

    total = sum(len(b["exercises"]) for b in blocks)
    logger.info(
        "Exercise pool built: %d exercises (%d explosive, %d compounds, %d accessories, %d core) for day_%d %s/%s",
        total, len(selected_explosive), len(selected_compounds), len(selected_accessories), len(selected_core),
        rotation_day, day_focus, training_intent
    )

    return blocks


def _pick(pool: list, n: int, recent_ids: set, day_key: str,
          preferences: dict = None) -> list:
    """Pick n exercises from pool, preferring preferred, fresh, and recommended."""
    if not pool or n <= 0:
        return []
    prefs = preferences or {}

    def score(ex):
        usage = ex.get("rotation_day_usage") or {}
        recommended = day_key in (usage.get("recommended") or [])
        fresh = ex["id"] not in recent_ids
        pref = prefs.get(ex["id"], "neutral")
        pref_score = 2 if pref == "prefer" else (1 if pref == "neutral" else 0)
        return (pref_score, fresh, recommended, random.random())

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
