"""Team-scoped query helper for coach-initiated data access.

Every coach-initiated query MUST go through these helpers to ensure team_id
filtering is applied. Direct .table() queries without team_id in coach
code paths are a code review blocker.
"""

from bot.services.db import get_client
from bot.services.team_daily_status import (
    get_team_daily_status,
    has_checkin,
    to_coach_compliance,
    to_coach_roster,
)


class TeamScopeViolation(Exception):
    """Raised when a coach query is attempted without a team_id."""
    pass


def _require_team_id(team_id: str) -> str:
    if not team_id:
        raise TeamScopeViolation("team_id must be set for all coach queries")
    return team_id


def _has_checkin(entry: dict | None) -> bool:
    """A submitted arm-feel check-in is the cross-app attendance signal."""
    return has_checkin(entry)


def list_team_pitchers(team_id: str) -> list:
    """Return all pitchers for a team."""
    team_id = _require_team_id(team_id)
    resp = (get_client().table("pitchers")
            .select("*")
            .eq("team_id", team_id)
            .execute())
    return resp.data or []


def get_team_roster_overview(team_id: str, today_str: str) -> list:
    """Return roster with today's check-in status and recent history.

    Combines pitchers + today's daily_entries + 7-day entry history
    into a pre-aggregated list for the Team Overview screen.
    """
    status = get_team_daily_status(_require_team_id(team_id), today_str, client=get_client())
    return to_coach_roster(status)


def get_team_compliance(team_id: str, today_str: str, roster: list) -> dict:
    """Compute compliance stats from pre-assembled roster."""
    _require_team_id(team_id)
    return to_coach_compliance({
        "summary": {
            "checked_in": sum(1 for r in roster if r["today_status"] == "checked_in"),
            "total": len(roster),
            "flags": {
                "red": sum(1 for r in roster if r.get("flag_level") == "red"),
                "yellow": sum(1 for r in roster if r.get("flag_level") == "yellow"),
                "green": sum(1 for r in roster if r.get("flag_level", "green") == "green"),
            },
        }
    })


def get_team_games(team_id: str, start_date: str = None, end_date: str = None) -> list:
    """Return team_games for a date range."""
    team_id = _require_team_id(team_id)
    q = (get_client().table("team_games")
         .select("*")
         .eq("team_id", team_id)
         .order("game_date"))
    if start_date:
        q = q.gte("game_date", start_date)
    if end_date:
        q = q.lte("game_date", end_date)
    return q.execute().data or []


def get_pitcher_next_start(pitcher_id: str, team_id: str, from_date: str) -> dict | None:
    """Return the next game where this pitcher is the assigned starter."""
    team_id = _require_team_id(team_id)
    resp = (get_client().table("team_games")
            .select("game_id, game_date, opponent, home_away")
            .eq("team_id", team_id)
            .eq("starting_pitcher_id", pitcher_id)
            .gte("game_date", from_date)
            .eq("status", "scheduled")
            .order("game_date")
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None
