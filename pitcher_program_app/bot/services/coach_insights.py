"""Coach Insights Engine — generates structured suggestions for coaches.

v0 ships with one category: pre_start_nudge.
Runs on a schedule after morning check-ins complete.
"""

import logging
from datetime import datetime, date, timedelta

from bot.config import CHICAGO_TZ
from bot.services.db import (
    get_client, get_training_model, get_daily_entry,
    get_pending_suggestions, upsert_suggestion,
)
from bot.services.team_scope import list_team_pitchers, get_pitcher_next_start

logger = logging.getLogger(__name__)


def run_insights_for_team(team_id: str) -> list:
    """Generate all insight categories for a team. Returns list of new suggestions."""
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    new_suggestions = []

    # Category 1: Pre-start nudges
    new_suggestions.extend(_generate_pre_start_nudges(team_id, today_str))

    return new_suggestions


def _generate_pre_start_nudges(team_id: str, today_str: str) -> list:
    """Generate pre-start nudge suggestions for pitchers starting in the next 3 days.

    Checks if the pitcher's plan in the days leading up to the start
    looks heavier than typical pre-start ramp. If so, suggests lightening.
    """
    suggestions = []
    pitchers = list_team_pitchers(team_id)
    today = date.fromisoformat(today_str)

    # Expire old pre_start_nudge suggestions
    existing = get_pending_suggestions(team_id)
    for s in existing:
        if s.get("category") == "pre_start_nudge":
            if s.get("expires_at"):
                exp = datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00"))
                if exp < datetime.now(CHICAGO_TZ):
                    s["status"] = "expired"
                    upsert_suggestion(s)

    for pitcher in pitchers:
        pid = pitcher["pitcher_id"]
        role = pitcher.get("role", "")
        if "starter" not in role:
            continue

        next_start = get_pitcher_next_start(pid, team_id, today_str)
        if not next_start:
            continue

        game_date = date.fromisoformat(next_start["game_date"])
        days_until = (game_date - today).days

        # Only nudge for starts 1-3 days away
        if days_until < 1 or days_until > 3:
            continue

        # Check if there's already a pending nudge for this pitcher + game
        already_exists = any(
            s.get("pitcher_id") == pid
            and s.get("category") == "pre_start_nudge"
            and s.get("status") == "pending"
            for s in existing
        )
        if already_exists:
            continue

        # Check today's plan — is it heavier than expected for a pre-start day?
        entry = get_daily_entry(pid, today_str)
        if not entry:
            continue

        plan = entry.get("plan_generated") or {}
        lifting = plan.get("exercise_blocks") or entry.get("lifting", {}).get("exercises", [])

        # Simple heuristic: count total sets in today's lifting
        total_sets = 0
        if isinstance(lifting, list):
            for block in lifting:
                exercises = block.get("exercises", []) if isinstance(block, dict) else []
                for ex in exercises:
                    total_sets += ex.get("sets", 0) if isinstance(ex, dict) else 0

        # Pre-start day (1-2 days out) should be light: < 12 total sets
        if days_until <= 2 and total_sets > 12:
            pitcher_name = pitcher.get("name", pid)
            opponent = next_start.get("opponent", "")

            suggestion = {
                "team_id": team_id,
                "pitcher_id": pid,
                "category": "pre_start_nudge",
                "title": f"Review {pitcher_name}'s lift before {game_date.strftime('%A')}'s start{' vs ' + opponent if opponent else ''}",
                "reasoning": (
                    f"{pitcher_name} starts {'tomorrow' if days_until == 1 else 'in 2 days'} "
                    f"but today's lift has {total_sets} total sets. "
                    f"Pre-start days typically have < 12 sets to preserve freshness. "
                    f"Consider reducing volume or swapping to lighter alternatives."
                ),
                "proposed_action": {
                    "type": "reduce_volume",
                    "description": f"Reduce today's lifting volume to pre-start level",
                },
                "status": "pending",
                "expires_at": (
                    datetime.combine(game_date, datetime.min.time())
                    .replace(tzinfo=CHICAGO_TZ)
                    .isoformat()
                ),
            }
            upsert_suggestion(suggestion)
            suggestions.append(suggestion)
            logger.info(f"Generated pre-start nudge for {pid} (starts {game_date})")

    return suggestions
