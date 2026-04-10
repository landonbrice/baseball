"""Team program resolution — resolves active team blocks for plan generation.

Called by plan_generator to determine if a team-assigned throwing block
should override the default rotation throwing template for a given pitcher/date.
"""

import logging
from datetime import date as _date, timedelta

from bot.services.db import get_client, get_active_team_blocks

logger = logging.getLogger(__name__)


def resolve_team_block(pitcher_id: str, team_id: str, target_date: str) -> dict | None:
    """Return the active team block content for a pitcher on a given date.

    Returns None if no block covers this date, or the pitcher's team
    has no active blocks.

    Returns:
        {
            "block_id": "...",
            "template_id": "...",
            "day_in_block": 14,
            "week": 2,
            "day_of_week": 7,
            "content": { ...block_library.content... },
            "day_content": { ...single day from content.phases... },
            "is_rest_day": bool,
            "post_session_recovery": "medium",
        }
    """
    if not team_id:
        return None

    active = get_active_team_blocks(team_id)
    if not active:
        return None

    target = _date.fromisoformat(target_date)

    for block in active:
        if block.get("status") != "active":
            continue
        if block.get("block_type") != "throwing":
            continue

        start = _date.fromisoformat(block["start_date"])
        duration = block.get("duration_days", 0)
        end = start + timedelta(days=duration - 1)

        if start <= target <= end:
            day_in_block = (target - start).days + 1
            week = (day_in_block - 1) // 7 + 1
            day_of_week = (day_in_block - 1) % 7 + 1

            # Load full template content from block_library
            template_id = block["block_template_id"]
            lib_resp = (get_client().table("block_library")
                        .select("content")
                        .eq("block_template_id", template_id)
                        .limit(1)
                        .execute())
            content = lib_resp.data[0]["content"] if lib_resp.data else {}

            # Find the relevant phase for this week
            day_content = None
            phases = content.get("phases", [])
            for phase in phases:
                if week in phase.get("weeks", []):
                    day_content = phase
                    break

            # Check if today is a rest day
            rest_pattern = content.get("rest_days_pattern", [])
            is_rest = day_of_week in rest_pattern

            return {
                "block_id": block["block_id"],
                "template_id": template_id,
                "day_in_block": day_in_block,
                "week": week,
                "day_of_week": day_of_week,
                "content": content,
                "day_content": day_content,
                "is_rest_day": is_rest,
                "post_session_recovery": content.get("post_session_recovery", "medium"),
            }

    return None


def compute_days_until_next_start(pitcher_id: str, team_id: str, from_date: str) -> int | None:
    """Return the number of days until this pitcher's next assigned start.

    Returns None if no upcoming start is assigned.
    Returns 0 on game day.
    """
    from bot.services.team_scope import get_pitcher_next_start

    next_game = get_pitcher_next_start(pitcher_id, team_id, from_date)
    if not next_game:
        return None

    game_date = _date.fromisoformat(next_game["game_date"])
    today = _date.fromisoformat(from_date)
    delta = (game_date - today).days
    return max(0, delta)
