"""Find alternative exercises for inline swapping.

Given an exercise and a pitcher's context, returns 3-4 alternatives
from the same category with overlapping muscle groups, filtered by
injury contraindications, equipment constraints, and preferences.
"""

import logging
from bot.services.db import get_exercises, get_training_model, get_daily_entry, get_daily_entries

logger = logging.getLogger(__name__)

# Cache exercise library in memory (same pattern as exercise_pool.py)
_EXERCISE_CACHE = None


def _load_exercises() -> list:
    global _EXERCISE_CACHE
    if _EXERCISE_CACHE is None:
        _EXERCISE_CACHE = get_exercises()
    return _EXERCISE_CACHE


def find_alternatives(
    exercise_id: str,
    pitcher_id: str,
    date: str,
    rotation_day: int = 0,
    max_results: int = 4,
) -> list[dict]:
    """Find alternative exercises for the given exercise.

    Returns up to max_results alternatives sorted by match quality.
    Each result is a dict with: exercise_id, name, rx, match_reason, tag, youtube_url.
    """
    library = _load_exercises()
    model = get_training_model(pitcher_id)
    preferences = model.get("exercise_preferences") or {}
    equipment = set(model.get("equipment_constraints") or [])

    # Find the source exercise
    source = None
    for ex in library:
        if ex["id"] == exercise_id:
            source = ex
            break
    if not source:
        return []

    source_category = source.get("category", "")
    source_muscles = set(source.get("muscles_primary") or [])
    day_key = f"day_{rotation_day}"

    # Get today's plan to exclude exercises already in it
    today_entry = get_daily_entry(pitcher_id, date) or {}
    plan = today_entry.get("plan_generated") or {}
    today_ids = set()
    for block_key in ("arm_care", "lifting"):
        block = plan.get(block_key) or {}
        for ex in (block.get("exercises") or []):
            today_ids.add(ex.get("exercise_id", ""))
    # Also check exercise_blocks (legacy format)
    for block in (plan.get("exercise_blocks") or []):
        for ex in (block.get("exercises") or []):
            today_ids.add(ex.get("exercise_id", ""))

    # Get recent exercise IDs (last 7 days) for freshness scoring
    recent_entries = get_daily_entries(pitcher_id, limit=7)
    recent_ids = set()
    for ent in recent_entries:
        for eid in (ent.get("completed_exercises") or {}).keys():
            recent_ids.add(eid)

    # Get injury areas for contraindication filtering
    from bot.services.context_manager import load_profile
    profile = load_profile(pitcher_id)
    injuries = profile.get("injury_history") or []
    injury_areas = set()
    for inj in injuries:
        area = (inj.get("area") or "").lower()
        if area:
            injury_areas.add(area)

    # Build contraindication set from injury areas
    conditions = set()
    for area in injury_areas:
        if "elbow" in area or "forearm" in area or "ucl" in area:
            conditions.update(["acute_low_back", "ucl_history"])
        if "back" in area or "lumbar" in area:
            conditions.update(["acute_low_back", "lumbar_disk_issues"])
        if "oblique" in area:
            conditions.add("oblique_strain")
        if "shoulder" in area or "labrum" in area:
            conditions.add("shoulder_impingement")

    # Filter candidates
    candidates = []
    for ex in library:
        eid = ex["id"]
        if ex.get("category") != source_category:
            continue
        if eid == exercise_id:
            continue
        if eid in today_ids:
            continue
        contras = set(ex.get("contraindications") or [])
        if contras & conditions:
            continue
        usage = ex.get("rotation_day_usage") or {}
        if day_key in (usage.get("avoid") or []):
            continue
        # Equipment constraint check
        ex_name_lower = (ex.get("name") or "").lower()
        skip_equip = False
        for constraint in equipment:
            equip_word = constraint.replace("no_", "").replace("_", " ")
            if equip_word in ex_name_lower:
                skip_equip = True
                break
        if skip_equip:
            continue

        candidates.append(ex)

    # Score candidates
    def score_candidate(ex):
        eid = ex["id"]
        ex_muscles = set(ex.get("muscles_primary") or [])
        muscle_overlap = len(source_muscles & ex_muscles)
        pref = preferences.get(eid, "neutral")
        pref_score = 2 if pref == "prefer" else (1 if pref == "neutral" else 0)
        fresh = eid not in recent_ids
        usage = ex.get("rotation_day_usage") or {}
        recommended = day_key in (usage.get("recommended") or [])
        return (muscle_overlap, pref_score, fresh, recommended)

    candidates.sort(key=score_candidate, reverse=True)
    top = candidates[:max_results]

    # Format results
    results = []
    for i, ex in enumerate(top):
        ex_muscles = set(ex.get("muscles_primary") or [])
        overlap = source_muscles & ex_muscles
        if overlap:
            match_reason = f"Same muscles — {', '.join(sorted(overlap))}"
        else:
            match_reason = f"Same category — {source_category.replace('_', ' ')}"

        rx_data = ex.get("prescription") or {}
        phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
        if phase.get("sets") and phase.get("reps"):
            rx = f"{phase['sets']}x{phase['reps']}"
        else:
            rx = "3x8"

        results.append({
            "exercise_id": ex["id"],
            "name": ex.get("name", ex["id"]),
            "rx": rx,
            "match_reason": match_reason,
            "tag": "Best match" if i == 0 else None,
            "youtube_url": ex.get("youtube_url"),
        })

    return results
