"""Team-scoped query helper for coach-initiated data access.

Every coach-initiated query MUST go through these helpers to ensure team_id
filtering is applied. Direct .table() queries without team_id in coach
code paths are a code review blocker.
"""

import logging
from bot.services.db import get_client
from bot.services.day_focus import derive_day_focus as _derive_day_focus

logger = logging.getLogger(__name__)


class TeamScopeViolation(Exception):
    """Raised when a coach query is attempted without a team_id."""
    pass


def _require_team_id(team_id: str) -> str:
    if not team_id:
        raise TeamScopeViolation("team_id must be set for all coach queries")
    return team_id


def _has_checkin(entry: dict | None) -> bool:
    """A submitted arm-feel check-in is the cross-app attendance signal."""
    if not entry:
        return False
    pre = entry.get("pre_training")
    if isinstance(pre, dict) and pre.get("arm_feel") is not None:
        return True
    return entry.get("arm_feel") is not None


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
    team_id = _require_team_id(team_id)
    client = get_client()

    # All pitchers on the team
    pitchers = (client.table("pitchers")
                .select("pitcher_id, name, role, telegram_username")
                .eq("team_id", team_id)
                .execute()).data or []

    # Today's entries for the team
    today_entries = (client.table("daily_entries")
                    .select("pitcher_id, pre_training, plan_generated, completed_exercises, warmup, lifting, throwing, plan_narrative")
                    .eq("team_id", team_id)
                    .eq("date", today_str)
                    .execute()).data or []
    today_map = {e["pitcher_id"]: e for e in today_entries}

    # Last 7 days of entries for streak/history
    from datetime import date as _date, timedelta
    week_ago = (_date.fromisoformat(today_str) - timedelta(days=6)).isoformat()
    week_entries = (client.table("daily_entries")
                    .select("pitcher_id, date, completed_exercises, pre_training")
                    .eq("team_id", team_id)
                    .gte("date", week_ago)
                    .lte("date", today_str)
                    .execute()).data or []

    # Group week entries by pitcher
    week_map = {}
    for e in week_entries:
        pid = e["pitcher_id"]
        week_map.setdefault(pid, []).append(e)

    # Training models for flag info
    models = (client.table("pitcher_training_model")
              .select("pitcher_id, current_flag_level, active_modifications, days_since_outing, baseline_snapshot")
              .in_("pitcher_id", [p["pitcher_id"] for p in pitchers])
              .execute()).data or []
    model_map = {m["pitcher_id"]: m for m in models}

    # Injury flags
    injuries = (client.table("injury_history")
                .select("pitcher_id, area, flag_level")
                .in_("pitcher_id", [p["pitcher_id"] for p in pitchers])
                .execute()).data or []
    injury_map = {}
    for inj in injuries:
        injury_map.setdefault(inj["pitcher_id"], []).append(inj)

    # Next scheduled starts
    upcoming_starts = (client.table("team_games")
                       .select("starting_pitcher_id, game_date")
                       .eq("team_id", team_id)
                       .gte("game_date", today_str)
                       .eq("status", "scheduled")
                       .not_.is_("starting_pitcher_id", "null")
                       .order("game_date")
                       .execute()).data or []
    # First upcoming start per pitcher
    next_start_map = {}
    for g in upcoming_starts:
        pid = g["starting_pitcher_id"]
        if pid not in next_start_map:
            next_start_map[pid] = g["game_date"]

    # Assemble roster
    roster = []
    for p in pitchers:
        pid = p["pitcher_id"]
        today = today_map.get(pid)
        model = model_map.get(pid, {})
        week = week_map.get(pid, [])

        has_checked_in = _has_checkin(today)

        # Build 7-day strip
        last_7 = []
        for i in range(6, -1, -1):
            d = (_date.fromisoformat(today_str) - timedelta(days=i)).isoformat()
            day_entry = next((e for e in week if e["date"] == d), None)
            if _has_checkin(day_entry):
                last_7.append({"date": d, "status": "checked_in"})
            elif day_entry:
                last_7.append({"date": d, "status": "partial"})
            else:
                last_7.append({"date": d, "status": "none"})

        # Streak count
        streak = 0
        for day in reversed(last_7):
            if day["status"] == "checked_in":
                streak += 1
            else:
                break

        # Active injury flags
        active_flags = []
        for inj in injury_map.get(pid, []):
            if inj.get("flag_level") in ("yellow", "red"):
                active_flags.append(f"{inj.get('area', 'unknown')} ({inj.get('flag_level', '')})")

        # af_7d — 7-day arm-feel mean from week entries (None if no entries)
        arm_feel_values = []
        for e in week:
            pt = e.get("pre_training") or {}
            af = pt.get("arm_feel")
            if isinstance(af, (int, float)) and af is not None:
                arm_feel_values.append(float(af))
        af_7d = round(sum(arm_feel_values) / len(arm_feel_values), 1) if arm_feel_values else None

        # today — compact plan summary for the triage feed
        plan = (today.get("plan_generated") if today else None) or {}
        lifting_block = today.get("lifting") if today else None
        lifting_summary = None
        if isinstance(lifting_block, dict):
            lifting_summary = lifting_block.get("block_name") or lifting_block.get("name")
        if not lifting_summary:
            nested = plan.get("lifting")
            if isinstance(nested, dict):
                lifting_summary = nested.get("block_name")

        # Derive day_focus — plan_generator doesn't persist it, but we can infer from content.
        throwing_val = today.get("throwing") if today else None
        if throwing_val is None:
            throwing_val = plan.get("throwing_plan")
        bullpen_val = plan.get("bullpen")
        # F4: read persisted day_focus; fall back to helper for legacy rows.
        persisted = plan.get("day_focus")
        if persisted:
            derived_day_focus = persisted
        else:
            derived_day_focus = _derive_day_focus(plan, plan.get("modifications_applied") or [])

        # Normalize modifications — triage emits strings, some paths emit dicts. Normalize to {tag, reason}.
        raw_mods = plan.get("modifications_applied") or []
        modifications = [
            m if isinstance(m, dict) else {"tag": m, "reason": None}
            for m in raw_mods
        ]

        # F4: rationale_short — primary subtitle source for HeroCard / TodayObjective.
        rationale = today.get("rationale") if today else None
        rationale_short = rationale.get("rationale_short") if isinstance(rationale, dict) else None

        today_obj = {
            "day_focus": derived_day_focus,
            "lifting_summary": lifting_summary,
            "bullpen": bullpen_val,
            "throwing": throwing_val,
            "modifications": modifications,  # keep for legacy clients / slide-over
            "rationale_short": rationale_short,
        }

        # F4: surface baseline state for HeroCard cold-start subscript.
        snapshot = model.get("baseline_snapshot") or {}
        baseline_state = snapshot.get("baseline_state") if isinstance(snapshot, dict) else None
        total_check_ins = snapshot.get("total_check_ins") if isinstance(snapshot, dict) else None

        roster.append({
            "pitcher_id": pid,
            "name": p.get("name", ""),
            "role": p.get("role", ""),
            "today_status": "checked_in" if has_checked_in else "not_yet",
            "flag_level": model.get("current_flag_level", "green"),
            "last_7_days": last_7,
            "streak": streak,
            "active_injury_flags": active_flags,
            "next_scheduled_start": next_start_map.get(pid),
            "af_7d": af_7d,
            "today": today_obj,
            "baseline_state": baseline_state,
            "total_check_ins": total_check_ins,
        })

    return roster


def get_team_compliance(team_id: str, today_str: str, roster: list) -> dict:
    """Compute compliance stats from pre-assembled roster."""
    total = len(roster)
    checked_in = sum(1 for r in roster if r["today_status"] == "checked_in")
    flags = {"red": 0, "yellow": 0, "green": 0}
    for r in roster:
        fl = r.get("flag_level", "green")
        if fl in flags:
            flags[fl] += 1
    return {
        "checked_in_today": checked_in,
        "total": total,
        "flags": flags,
    }


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
