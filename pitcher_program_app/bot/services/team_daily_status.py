"""Canonical team daily status service.

Owns team/date-scoped check-in, plan, and work status semantics shared by
staff pulse and coach overview surfaces.
"""

from __future__ import annotations

import logging
from datetime import date as _date, datetime, timedelta
from typing import Any

from bot.config import CHICAGO_TZ
from bot.services.db import get_client
from bot.services.day_focus import derive_day_focus as _derive_day_focus

logger = logging.getLogger(__name__)


class TeamDailyStatusViolation(Exception):
    """Raised when a team daily status query is attempted without a team_id."""
    pass


def _require_team_id(team_id: str) -> str:
    if not team_id:
        raise TeamDailyStatusViolation("team_id must be set for all team daily status queries")
    return team_id


def chicago_today_str() -> str:
    return datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")


def has_checkin(entry: dict | None) -> bool:
    """A submitted arm-feel check-in is the cross-app attendance signal."""
    if not entry:
        return False
    pre = entry.get("pre_training")
    if isinstance(pre, dict) and pre.get("arm_feel") is not None:
        return True
    return entry.get("arm_feel") is not None


def derive_checkin_status(entry: dict | None) -> str:
    return "checked_in" if has_checkin(entry) else "not_yet"


def derive_plan_status(entry: dict | None) -> str:
    if not has_checkin(entry):
        return "not_applicable"
    if entry and entry.get("plan_generated"):
        return "generated"
    return "pending"


def _planned_exercise_ids(entry: dict | None) -> set[str] | None:
    """Return planned exercise ids/names when plan shape is confidently readable."""
    if not entry:
        return set()

    planned: set[str] = set()

    def add_exercises(exercises: Any) -> None:
        if not isinstance(exercises, list):
            return
        for ex in exercises:
            if isinstance(ex, dict):
                ex_id = ex.get("id") or ex.get("exercise_id") or ex.get("name")
                if ex_id:
                    planned.add(str(ex_id))
            elif ex:
                planned.add(str(ex))

    for block_name in ("warmup", "lifting", "throwing", "arm_care", "mobility"):
        block = entry.get(block_name)
        if isinstance(block, dict):
            add_exercises(block.get("exercises"))

    plan = entry.get("plan_generated") or {}
    if isinstance(plan, dict):
        lifting = plan.get("lifting")
        if isinstance(lifting, dict):
            add_exercises(lifting.get("exercises"))
        for block in plan.get("exercise_blocks") or []:
            if isinstance(block, dict):
                add_exercises(block.get("exercises"))

    return planned if planned else None


def derive_work_status(entry: dict | None) -> str:
    if not entry:
        return "not_started"
    completed = entry.get("completed_exercises") or {}
    if isinstance(completed, list):
        completed_count = len(completed)
        completed_ids = {str(i) for i in completed}
    elif isinstance(completed, dict):
        completed_ids = {str(k) for k, v in completed.items() if v is not False and v is not None}
        completed_count = len(completed_ids)
    else:
        completed_ids = set()
        completed_count = 0

    if completed_count == 0:
        return "not_started"

    planned = _planned_exercise_ids(entry)
    if planned is None:
        return "unknown"
    if planned and planned.issubset(completed_ids):
        return "completed"
    return "in_progress"


def _first_name(name: str, fallback: str) -> str:
    return name.split()[0] if name else fallback


def _staff_role(role: str) -> str:
    role_raw = (role or "").lower()
    return "RP" if role_raw in ("reliever", "rp", "closer", "cl") or "reliever" in role_raw else "SP"


def _rotation_info(role: str, days_since: Any) -> str:
    staff_role = _staff_role(role)
    if staff_role == "SP":
        return "Day %d" % int(days_since) if days_since is not None else "Day 0"
    if days_since is not None and int(days_since) <= 1:
        return "Day after"
    return "Available"


def _normalize_modifications(plan: dict) -> list[dict]:
    raw_mods = plan.get("modifications_applied") or []
    return [
        m if isinstance(m, dict) else {"tag": m, "reason": None}
        for m in raw_mods
    ]


def _today_summary(today: dict | None) -> dict:
    plan = (today.get("plan_generated") if today else None) or {}

    lifting_block = today.get("lifting") if today else None
    lifting_summary = None
    if isinstance(lifting_block, dict):
        lifting_summary = lifting_block.get("block_name") or lifting_block.get("name")
    if not lifting_summary:
        nested = plan.get("lifting") if isinstance(plan, dict) else None
        if isinstance(nested, dict):
            lifting_summary = nested.get("block_name")

    throwing_val = today.get("throwing") if today else None
    if throwing_val is None and isinstance(plan, dict):
        throwing_val = plan.get("throwing_plan")

    bullpen_val = plan.get("bullpen") if isinstance(plan, dict) else None
    if isinstance(plan, dict) and plan.get("day_focus"):
        day_focus = plan.get("day_focus")
    elif isinstance(plan, dict):
        day_focus = _derive_day_focus(plan, plan.get("modifications_applied") or [])
    else:
        day_focus = None

    rationale = today.get("rationale") if today else None
    rationale_short = rationale.get("rationale_short") if isinstance(rationale, dict) else None

    return {
        "day_focus": day_focus,
        "lifting_summary": lifting_summary,
        "bullpen": bullpen_val,
        "throwing": throwing_val,
        "modifications": _normalize_modifications(plan) if isinstance(plan, dict) else [],
        "rationale_short": rationale_short,
    }


def get_team_daily_status(team_id: str, today_str: str | None = None, *, client=None) -> dict:
    """Return canonical team daily status for one Chicago date."""
    team_id = _require_team_id(team_id)
    today_str = today_str or chicago_today_str()
    client = client or get_client()

    pitchers = (client.table("pitchers")
                .select("pitcher_id, name, role, telegram_username, team_id")
                .eq("team_id", team_id)
                .execute()).data or []

    today_entries = (client.table("daily_entries")
                    .select("pitcher_id, date, team_id, pre_training, arm_feel, plan_generated, completed_exercises, warmup, lifting, throwing, arm_care, mobility, plan_narrative, rationale")
                    .eq("team_id", team_id)
                    .eq("date", today_str)
                    .execute()).data or []
    today_map = {e["pitcher_id"]: e for e in today_entries}

    week_ago = (_date.fromisoformat(today_str) - timedelta(days=6)).isoformat()
    week_entries = (client.table("daily_entries")
                    .select("pitcher_id, date, team_id, completed_exercises, pre_training, arm_feel")
                    .eq("team_id", team_id)
                    .gte("date", week_ago)
                    .lte("date", today_str)
                    .execute()).data or []

    week_map: dict[str, list[dict]] = {}
    for e in week_entries:
        week_map.setdefault(e["pitcher_id"], []).append(e)

    pitcher_ids = [p["pitcher_id"] for p in pitchers]
    if pitcher_ids:
        models = (client.table("pitcher_training_model")
                  .select("pitcher_id, current_flag_level, active_modifications, days_since_outing, baseline_snapshot")
                  .in_("pitcher_id", pitcher_ids)
                  .execute()).data or []
        injuries = (client.table("injury_history")
                    .select("pitcher_id, area, flag_level")
                    .in_("pitcher_id", pitcher_ids)
                    .execute()).data or []
    else:
        models = []
        injuries = []
    model_map = {m["pitcher_id"]: m for m in models}

    injury_map: dict[str, list[dict]] = {}
    for inj in injuries:
        injury_map.setdefault(inj["pitcher_id"], []).append(inj)

    upcoming_starts = (client.table("team_games")
                       .select("starting_pitcher_id, game_date")
                       .eq("team_id", team_id)
                       .gte("game_date", today_str)
                       .eq("status", "scheduled")
                       .not_.is_("starting_pitcher_id", "null")
                       .order("game_date")
                       .execute()).data or []
    next_start_map = {}
    for game in upcoming_starts:
        pid = game["starting_pitcher_id"]
        if pid not in next_start_map:
            next_start_map[pid] = game["game_date"]

    roster = []
    for p in pitchers:
        pid = p["pitcher_id"]
        today = today_map.get(pid)
        model = model_map.get(pid, {})
        week = week_map.get(pid, [])
        checkin_status = derive_checkin_status(today)
        plan_status = derive_plan_status(today)
        work_status = derive_work_status(today)

        last_7 = []
        for i in range(6, -1, -1):
            d = (_date.fromisoformat(today_str) - timedelta(days=i)).isoformat()
            day_entry = next((e for e in week if e["date"] == d), None)
            if has_checkin(day_entry):
                status = "checked_in"
            elif day_entry:
                status = "partial"
            else:
                status = "none"
            last_7.append({
                "date": d,
                "status": status,
                "checkin_status": derive_checkin_status(day_entry),
                "work_status": derive_work_status(day_entry),
            })

        streak = 0
        for day in reversed(last_7):
            if day["status"] == "checked_in":
                streak += 1
            else:
                break

        active_flags = []
        for inj in injury_map.get(pid, []):
            if inj.get("flag_level") in ("yellow", "red"):
                active_flags.append(f"{inj.get('area', 'unknown')} ({inj.get('flag_level', '')})")

        arm_feel_values = []
        for e in week:
            pt = e.get("pre_training") or {}
            af = pt.get("arm_feel") if isinstance(pt, dict) else None
            if af is None:
                af = e.get("arm_feel")
            if isinstance(af, (int, float)):
                arm_feel_values.append(float(af))
        af_7d = round(sum(arm_feel_values) / len(arm_feel_values), 1) if arm_feel_values else None

        snapshot = model.get("baseline_snapshot") or {}
        baseline_state = snapshot.get("baseline_state") if isinstance(snapshot, dict) else None
        total_check_ins = snapshot.get("total_check_ins") if isinstance(snapshot, dict) else None

        full_name = p.get("name") or pid
        role = p.get("role", "")
        roster.append({
            "pitcher_id": pid,
            "name": full_name,
            "first_name": _first_name(full_name, pid),
            "role": role,
            "staff_role": _staff_role(role),
            "team_id": p.get("team_id") or team_id,
            "checkin_status": checkin_status,
            "plan_status": plan_status,
            "work_status": work_status,
            "checked_in": checkin_status == "checked_in",
            "today_status": checkin_status,
            "today_entry": today,
            "flag_level": model.get("current_flag_level", "green"),
            "rotation_info": _rotation_info(role, model.get("days_since_outing")),
            "last_7_days": last_7,
            "streak": streak,
            "active_injury_flags": active_flags,
            "next_scheduled_start": next_start_map.get(pid),
            "af_7d": af_7d,
            "today": _today_summary(today),
            "baseline_state": baseline_state,
            "total_check_ins": total_check_ins,
        })

    checked_in = sum(1 for r in roster if r["checkin_status"] == "checked_in")
    plans_generated = sum(1 for r in roster if r["plan_status"] == "generated")
    plans_pending = sum(1 for r in roster if r["plan_status"] == "pending")

    flags = {"red": 0, "yellow": 0, "green": 0}
    for r in roster:
        flag = r.get("flag_level", "green")
        if flag in flags:
            flags[flag] += 1

    return {
        "team_id": team_id,
        "date": today_str,
        "summary": {
            "total": len(roster),
            "checked_in": checked_in,
            "not_yet": len(roster) - checked_in,
            "plans_generated": plans_generated,
            "plans_pending": plans_pending,
            "flags": flags,
        },
        "pitchers": roster,
    }


def to_coach_roster(status: dict) -> list[dict]:
    """Adapt canonical pitcher rows to the existing coach overview roster shape."""
    return [
        {
            "pitcher_id": p["pitcher_id"],
            "name": p.get("name", ""),
            "role": p.get("role", ""),
            "checkin_status": p.get("checkin_status", "not_yet"),
            "plan_status": p.get("plan_status", "not_applicable"),
            "work_status": p.get("work_status", "not_started"),
            "checked_in": bool(p.get("checked_in")),
            "today_status": p.get("today_status", p.get("checkin_status", "not_yet")),
            "flag_level": p.get("flag_level", "green"),
            "last_7_days": [
                {
                    "date": d.get("date"),
                    "status": d.get("status", "none"),
                    "checkin_status": d.get("checkin_status", "not_yet"),
                    "work_status": d.get("work_status", "not_started"),
                }
                for d in p.get("last_7_days", [])
            ],
            "streak": p.get("streak", 0),
            "active_injury_flags": p.get("active_injury_flags", []),
            "next_scheduled_start": p.get("next_scheduled_start"),
            "af_7d": p.get("af_7d"),
            "today": p.get("today", {}),
            "baseline_state": p.get("baseline_state"),
            "total_check_ins": p.get("total_check_ins"),
        }
        for p in status.get("pitchers", [])
    ]


def to_coach_compliance(status: dict) -> dict:
    summary = status.get("summary", {})
    return {
        "checked_in_today": summary.get("checked_in", 0),
        "total": summary.get("total", 0),
        "flags": summary.get("flags", {"red": 0, "yellow": 0, "green": 0}),
    }


def to_staff_pulse(status: dict) -> dict:
    pitchers = [
        {
            "first_name": p.get("first_name") or _first_name(p.get("name", ""), p.get("pitcher_id", "")),
            "checkin_status": p.get("checkin_status", "not_yet"),
            "checked_in": bool(p.get("checked_in")),
            "rotation_info": p.get("rotation_info", "Day 0"),
            "role": p.get("staff_role") or _staff_role(p.get("role", "")),
        }
        for p in status.get("pitchers", [])
        if p.get("pitcher_id") != "test_pitcher_001"
    ]
    return {
        "checked_in_count": sum(1 for p in pitchers if p["checked_in"]),
        "total_pitchers": len(pitchers),
        "pitchers": pitchers,
    }
