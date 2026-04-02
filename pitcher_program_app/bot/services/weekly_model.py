"""Weekly training model — proactive next-day suggestions.

Computes what tomorrow's training should be based on the pitcher's
week so far (throws, lifts, movement pattern balance). For relievers
without a fixed rotation, this replaces the rotation day template lookup.
"""

import logging
from datetime import datetime, timedelta
from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)


def compute_next_day_suggestion(pitcher_profile: dict, training_model: dict) -> dict:
    """Compute a suggested training focus for tomorrow.

    Returns dict with: focus, throw_suggestion, reasoning, confidence.
    Confidence: "high" (lead with suggestion), "medium" (suggest softly),
                "low" (fall back to asking).
    """
    role = pitcher_profile.get("role", "starter")
    week_state = training_model.get("current_week_state") or {}
    days = week_state.get("days") or []

    if role in ("reliever", "reliever_short", "reliever_long"):
        return _reliever_suggestion(days, pitcher_profile)
    else:
        return _starter_suggestion(days, pitcher_profile, training_model)


def _reliever_suggestion(days: list, profile: dict) -> dict:
    """Compute suggestion for relievers based on recent activity."""
    tomorrow = (datetime.now(CHICAGO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Find most recent throw
    threw_days = [d for d in days if d.get("threw")]
    last_throw = threw_days[-1] if threw_days else None

    if not last_throw:
        return {
            "focus": "full_body",
            "throw_suggestion": "hybrid_a",
            "reasoning": "No throwing load this week — full session available",
            "confidence": "medium",
        }

    last_throw_date = last_throw.get("date", "")
    throw_type = last_throw.get("throw_type", "")

    try:
        last_dt = datetime.strptime(last_throw_date, "%Y-%m-%d")
        tomorrow_dt = datetime.strptime(tomorrow, "%Y-%m-%d")
        days_since = (tomorrow_dt - last_dt).days
    except (ValueError, TypeError):
        days_since = 99

    if throw_type in ("game", "bullpen"):
        if days_since == 1:
            return {
                "focus": "recovery_upper",
                "throw_suggestion": "recovery",
                "reasoning": f"Day after {throw_type} — recovery mode",
                "confidence": "high",
            }
        elif days_since == 2:
            return {
                "focus": "lower_strength",
                "throw_suggestion": "hybrid_b",
                "reasoning": "2 days post-throw, rebuilding",
                "confidence": "medium",
            }
        elif days_since >= 3:
            return {
                "focus": "upper_strength",
                "throw_suggestion": "hybrid_a",
                "reasoning": f"{days_since} days since last appearance — full intensity available",
                "confidence": "medium",
            }

    if throw_type == "hybrid_a":
        return {
            "focus": "lower_power",
            "throw_suggestion": "recovery",
            "reasoning": "High-intent throw yesterday — lower body + recovery throw",
            "confidence": "medium",
        }

    # Default
    return {
        "focus": "full_body",
        "throw_suggestion": "hybrid_b",
        "reasoning": f"{days_since} days since last throw ({throw_type})",
        "confidence": "low",
    }


def _starter_suggestion(days: list, profile: dict, model: dict) -> dict:
    """Enhance existing rotation-day logic with weekly awareness for starters."""
    rotation_day = model.get("days_since_outing", 0)
    rotation_length = profile.get("rotation_length", 7)

    suggestion = {
        "focus": None,
        "throw_suggestion": None,
        "reasoning": f"Day {rotation_day} of {rotation_length}-day rotation",
        "confidence": "medium",
        "notes": [],
    }

    # Check weekly movement pattern gaps
    week_state = model.get("current_week_state") or {}
    patterns = week_state.get("movement_pattern_tally") or {}
    pull_count = patterns.get("pull", 0)
    push_count = patterns.get("push", 0)
    if pull_count < push_count and push_count > 0:
        suggestion["notes"].append("Pull deficit this week — emphasize pulls")

    return suggestion


def update_week_state_after_checkin(
    training_model: dict,
    date: str,
    lifted: bool,
    lift_focus: str = None,
    threw: bool = False,
    throw_type: str = None,
    throw_intensity: int = None,
) -> dict:
    """Update current_week_state.days with today's activity.

    Call after each check-in to maintain the weekly arc.
    Returns the updated current_week_state dict.
    """
    week_state = dict(training_model.get("current_week_state") or {})

    # Initialize week if needed (new week starts Monday)
    today = datetime.strptime(date, "%Y-%m-%d")
    monday = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    if week_state.get("week_start") != monday:
        week_state = {
            "week_start": monday,
            "days": [],
            "movement_pattern_tally": {},
            "throwing_load": {"total_throws": 0, "sessions": 0, "max_intensity": 0},
            "next_day_suggestion": {},
        }

    days = list(week_state.get("days") or [])

    # Find or create today's entry
    today_entry = None
    for d in days:
        if d.get("date") == date:
            today_entry = d
            break

    if not today_entry:
        today_entry = {
            "date": date,
            "threw": False,
            "throw_type": None,
            "throw_intensity": None,
            "lifted": False,
            "lift_focus": None,
            "exercises_completed": [],
            "exercises_skipped": [],
            "exercises_swapped": [],
        }
        days.append(today_entry)

    today_entry["lifted"] = lifted
    today_entry["lift_focus"] = lift_focus
    if threw:
        today_entry["threw"] = True
        today_entry["throw_type"] = throw_type
        today_entry["throw_intensity"] = throw_intensity
        load = week_state.get("throwing_load") or {}
        load["sessions"] = load.get("sessions", 0) + 1
        if throw_intensity:
            load["max_intensity"] = max(load.get("max_intensity", 0), throw_intensity)
        week_state["throwing_load"] = load

    week_state["days"] = days
    return week_state
