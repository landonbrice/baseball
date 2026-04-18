"""Coach dashboard API routes.

All endpoints require coach auth via require_coach_auth().
Team scoping is enforced by reading team_id from request.state (set by auth).
"""

import os
import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request, HTTPException

from api.coach_auth import require_coach_auth
from bot.config import CHICAGO_TZ
from bot.services import db as _db
from bot.services.team_scope import (
    get_team_roster_overview,
    get_team_compliance,
    get_team_games,
    get_pitcher_next_start,
    list_team_pitchers,
)

logger = logging.getLogger(__name__)

coach_router = APIRouter(prefix="/api/coach")


# ---- Auth ----

@coach_router.post("/auth/exchange")
async def auth_exchange(request: Request):
    """Validate Supabase JWT and return domain identity."""
    await require_coach_auth(request)
    return {
        "coach_id": request.state.coach_id,
        "team_id": request.state.team_id,
        "coach_name": request.state.coach_name,
        "role": request.state.coach_role,
        "team_name": request.state.team_name,
    }


@coach_router.get("/me")
async def coach_me(request: Request):
    """Session restoration — same as auth/exchange but GET."""
    await require_coach_auth(request)
    return {
        "coach_id": request.state.coach_id,
        "team_id": request.state.team_id,
        "coach_name": request.state.coach_name,
        "role": request.state.coach_role,
    }


# ---- Team Overview ----

@coach_router.get("/team/overview")
async def team_overview(request: Request):
    """Single call for the entire Team Overview screen."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    roster = get_team_roster_overview(team_id, today_str)
    compliance = get_team_compliance(team_id, today_str, roster)

    # Today's schedule
    today_games = get_team_games(team_id, start_date=today_str, end_date=today_str)
    if today_games:
        g = today_games[0]
        starter_name = ""
        if g.get("starting_pitcher_id"):
            p = _db.get_pitcher(g["starting_pitcher_id"])
            starter_name = p.get("name", "") if p else ""
        schedule_summary = f"{'vs' if g.get('home_away') == 'home' else '@'} {g.get('opponent', 'TBD')}{'  Starter: ' + starter_name if starter_name else ''}"
    else:
        schedule_summary = "No games today"

    # Active team blocks
    active_blocks = _db.get_active_team_blocks(team_id)

    # Pending insights count
    pending = _db.get_pending_suggestions(team_id)

    # Team info
    team_resp = (
        _db.get_client().table("teams")
        .select("*")
        .eq("team_id", team_id)
        .single()
        .execute()
    )
    team = team_resp.data or {}

    return {
        "team": {
            "id": team_id,
            "name": team.get("name", ""),
            "training_phase": team.get("training_phase", ""),
            "today_schedule_summary": schedule_summary,
        },
        "compliance": compliance,
        "roster": roster,
        "active_blocks": [
            {
                "block_id": b["block_id"],
                "name": b.get("block_template_id", ""),
                "block_type": b.get("block_type", ""),
                "start_date": b.get("start_date", ""),
                "status": b.get("status", ""),
            }
            for b in active_blocks
        ],
        "insights_summary": {
            "pending_count": len(pending),
            "high_priority_count": sum(1 for s in pending if s.get("category") == "pre_start_nudge"),
        },
    }


# ---- Player Detail ----

@coach_router.get("/pitcher/{pitcher_id}")
async def coach_pitcher_detail(pitcher_id: str, request: Request):
    """Full pitcher detail for the slide-over panel."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    # Verify pitcher belongs to this team
    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    from bot.services.context_manager import load_profile
    profile = load_profile(pitcher_id)

    # Current week (back 3, today, forward 3)
    week_start = (date.fromisoformat(today_str) - timedelta(days=3)).isoformat()
    week_end = (date.fromisoformat(today_str) + timedelta(days=3)).isoformat()
    week_entries = (
        _db.get_client().table("daily_entries")
        .select("date, rotation_day, pre_training, plan_generated, completed_exercises, lifting, throwing, arm_care, warmup, plan_narrative, morning_brief, active_team_block_id")
        .eq("pitcher_id", pitcher_id)
        .gte("date", week_start)
        .lte("date", week_end)
        .order("date")
        .execute()
    ).data or []

    # Recent check-ins (last 10)
    recent_checkins = (
        _db.get_client().table("daily_entries")
        .select("date, pre_training, completed_exercises")
        .eq("pitcher_id", pitcher_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    ).data or []

    # Training model
    model = _db.get_training_model(pitcher_id)

    # Injuries
    injuries = (
        _db.get_client().table("injury_history")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .execute()
    ).data or []

    # WHOOP today
    whoop_today = None
    try:
        whoop_resp = (
            _db.get_client().table("whoop_daily")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .eq("date", today_str)
            .limit(1)
            .execute()
        )
        whoop_today = whoop_resp.data[0] if whoop_resp.data else None
    except Exception:
        pass

    # Next start
    next_start = get_pitcher_next_start(pitcher_id, team_id, today_str)

    # Active team block
    active_blocks = _db.get_active_team_blocks(team_id)
    active_block_info = None
    for b in active_blocks:
        if b.get("status") == "active":
            start = date.fromisoformat(b["start_date"])
            today_d = date.fromisoformat(today_str)
            day_in_block = (today_d - start).days + 1
            if 0 < day_in_block <= b.get("duration_days", 999):
                week = (day_in_block - 1) // 7 + 1
                day_of_week = (day_in_block - 1) % 7 + 1
                active_block_info = {
                    "block_id": b["block_id"],
                    "template_id": b["block_template_id"],
                    "week": week,
                    "day": day_of_week,
                    "day_in_block": day_in_block,
                }
            break

    # Pending suggestions for this pitcher
    all_suggestions = _db.get_pending_suggestions(team_id)
    pitcher_suggestions = [s for s in all_suggestions if s["pitcher_id"] == pitcher_id]

    return {
        "profile": profile,
        "current_week": week_entries,
        "recent_check_ins": recent_checkins,
        "training_model": model,
        "injuries": injuries,
        "whoop_today": whoop_today,
        "next_start": next_start,
        "active_team_block": active_block_info,
        "pending_suggestions": pitcher_suggestions,
    }


@coach_router.get("/pitcher/{pitcher_id}/day/{day_date}")
async def coach_pitcher_day(pitcher_id: str, day_date: str, request: Request):
    """Full daily entry for a specific date."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    entry = _db.get_daily_entry(pitcher_id, day_date)
    if not entry:
        raise HTTPException(status_code=404, detail="No entry for this date")
    return entry


# ---- Overrides ----

@coach_router.post("/pitcher/{pitcher_id}/adjust-today")
async def adjust_today(pitcher_id: str, request: Request):
    """Apply one-time mutations to today's plan (verb 1)."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    body = await request.json()
    mutations = body.get("mutations", [])
    target_date = body.get("date", datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d"))

    if not mutations:
        raise HTTPException(status_code=400, detail="No mutations provided")

    # Reuse existing mutation apply logic from routes.py
    from api.routes import _apply_mutations_to_entry
    entry = _db.get_daily_entry(pitcher_id, target_date)
    if not entry:
        raise HTTPException(status_code=404, detail="No plan exists for this date")

    updated_entry = _apply_mutations_to_entry(entry, mutations, source=f"coach:{coach_id}")
    _db.upsert_daily_entry(pitcher_id, updated_entry)

    return {"status": "ok", "modifications_applied": mutations}


@coach_router.post("/pitcher/{pitcher_id}/restriction")
async def add_restriction(pitcher_id: str, request: Request):
    """Add a persistent restriction for an athlete (verb 2)."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    body = await request.json()
    restriction_type = body.get("restriction_type", "exercise_blocked")
    target = body.get("target", "")
    reason = body.get("reason", "")
    expires_at = body.get("expires_at")

    if not target:
        raise HTTPException(status_code=400, detail="Restriction target required")

    model = _db.get_training_model(pitcher_id)
    prefs = model.get("exercise_preferences") or {}
    prefs[target] = {
        "status": "blocked",
        "reason": reason,
        "restriction_type": restriction_type,
        "expires_at": expires_at,
        "set_by": "coach",
    }
    _db.upsert_training_model(pitcher_id, {"exercise_preferences": prefs})

    return {"status": "ok", "restriction": prefs[target]}


@coach_router.delete("/pitcher/{pitcher_id}/restriction/{restriction_key}")
async def remove_restriction(pitcher_id: str, restriction_key: str, request: Request):
    """Lift a previously-added restriction."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    model = _db.get_training_model(pitcher_id)
    prefs = model.get("exercise_preferences") or {}
    if restriction_key in prefs:
        del prefs[restriction_key]
        _db.upsert_training_model(pitcher_id, {"exercise_preferences": prefs})

    return {"status": "ok"}


# ---- Schedule ----

@coach_router.get("/schedule")
async def coach_schedule(request: Request, start: str = None, end: str = None):
    """Return games for the team within a date range."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    games = get_team_games(team_id, start_date=start, end_date=end)
    return {"games": games}


@coach_router.post("/schedule/game")
async def add_game(request: Request):
    """Add a game to the schedule."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    game = {
        "team_id": team_id,
        "game_date": body["game_date"],
        "opponent": body.get("opponent"),
        "home_away": body.get("home_away"),
        "game_time": body.get("game_time"),
        "is_doubleheader_g2": body.get("is_doubleheader_g2", False),
        "starting_pitcher_id": body.get("starting_pitcher_id"),
        "notes": body.get("notes"),
        "source": "manual",
    }
    result = _db.upsert_team_game(game)
    return result


@coach_router.patch("/schedule/game/{game_id}")
async def update_game(game_id: str, request: Request):
    """Update game details — most commonly starter assignment."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    existing = _db.get_team_game(game_id)
    if not existing or existing.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Game not on your team")

    for key in ["game_date", "opponent", "home_away", "game_time",
                "is_doubleheader_g2", "starting_pitcher_id", "status", "notes"]:
        if key in body:
            existing[key] = body[key]

    existing["updated_at"] = datetime.now(CHICAGO_TZ).isoformat()
    result = _db.upsert_team_game(existing)
    return result


@coach_router.delete("/schedule/game/{game_id}")
async def delete_game(game_id: str, request: Request):
    """Remove a game."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    existing = _db.get_team_game(game_id)
    if not existing or existing.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Game not on your team")

    _db.delete_team_game(game_id)
    return {"status": "ok"}


# ---- Team Programs ----

@coach_router.get("/team-programs/library")
async def block_library(request: Request):
    """Return pre-loaded block library."""
    await require_coach_auth(request)
    blocks = _db.list_block_library()
    return {"blocks": blocks}


@coach_router.get("/team-programs/active")
async def active_blocks(request: Request):
    """Return active team blocks."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    blocks = _db.get_active_team_blocks(team_id)
    return {"blocks": blocks}


@coach_router.post("/team-programs/assign")
async def assign_block(request: Request):
    """Assign a block to the team."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    body = await request.json()

    block_template_id = body.get("block_template_id")
    start_date = body.get("start_date")

    if not block_template_id or not start_date:
        raise HTTPException(status_code=400, detail="block_template_id and start_date required")

    # Check no active throwing block already
    active = _db.get_active_team_blocks(team_id)
    throwing_active = [b for b in active if b.get("block_type") == "throwing" and b.get("status") == "active"]
    if throwing_active:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BLOCK_ALREADY_ACTIVE",
                "message": "A throwing block is already active. End it first.",
                "active_block_id": throwing_active[0]["block_id"],
            }
        )

    # Look up template
    templates = _db.list_block_library()
    template = next((t for t in templates if t["block_template_id"] == block_template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Block template not found")

    block = {
        "team_id": team_id,
        "block_type": template["block_type"],
        "block_template_id": block_template_id,
        "start_date": start_date,
        "duration_days": body.get("duration_days", template["duration_days"]),
        "assigned_by_coach_id": coach_id,
        "notes": body.get("notes"),
        "status": "active",
    }
    result = _db.upsert_team_block(block)

    pitchers = list_team_pitchers(team_id)
    return {
        "block": result,
        "affected_pitchers_count": len(pitchers),
    }


@coach_router.post("/team-programs/{block_id}/end")
async def end_block(block_id: str, request: Request):
    """End a team block early."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    active = _db.get_active_team_blocks(team_id)
    block = next((b for b in active if b["block_id"] == block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="Active block not found")

    block["status"] = "completed"
    _db.upsert_team_block(block)
    return {"status": "ok"}


# ---- Phases ----

@coach_router.get("/phases")
async def list_phases(request: Request):
    """Return training phase blocks."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    phases = _db.get_phase_blocks(team_id)
    return {"phases": phases}


@coach_router.post("/phases")
async def create_phase(request: Request):
    """Create a new phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    phase = {
        "team_id": team_id,
        "phase_name": body["phase_name"],
        "start_date": body["start_date"],
        "end_date": body["end_date"],
        "emphasis": body.get("emphasis"),
        "notes": body.get("notes"),
    }
    result = _db.upsert_phase_block(phase)
    return result


@coach_router.patch("/phases/{phase_block_id}")
async def update_phase(phase_block_id: str, request: Request):
    """Update a phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    phases = _db.get_phase_blocks(team_id)
    phase = next((p for p in phases if p["phase_block_id"] == phase_block_id), None)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    for key in ["phase_name", "start_date", "end_date", "emphasis", "notes"]:
        if key in body:
            phase[key] = body[key]

    result = _db.upsert_phase_block(phase)
    return result


@coach_router.delete("/phases/{phase_block_id}")
async def delete_phase(phase_block_id: str, request: Request):
    """Delete a phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    phases = _db.get_phase_blocks(team_id)
    phase = next((p for p in phases if p["phase_block_id"] == phase_block_id), None)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    _db.delete_phase_block(phase_block_id)
    return {"status": "ok"}


# ---- Insights ----

@coach_router.get("/insights")
async def list_insights(request: Request, status: str = "pending"):
    """Return coach suggestions."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    if status == "pending":
        suggestions = _db.get_pending_suggestions(team_id)
    else:
        suggestions = (
            _db.get_client().table("coach_suggestions")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", status)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        ).data or []

    return {"suggestions": suggestions}


@coach_router.post("/insights/{suggestion_id}/accept")
async def accept_insight(suggestion_id: str, request: Request):
    """Accept a suggestion — execute the proposed action."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    suggestions = _db.get_pending_suggestions(team_id)
    suggestion = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already resolved")

    # Apply the proposed action if it exists
    proposed = suggestion.get("proposed_action")
    if proposed and proposed.get("mutations"):
        pitcher_id = suggestion["pitcher_id"]
        today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
        entry = _db.get_daily_entry(pitcher_id, today_str)
        if entry:
            from api.routes import _apply_mutations_to_entry
            updated = _apply_mutations_to_entry(entry, proposed["mutations"], source=f"insight:{suggestion_id}")
            _db.upsert_daily_entry(pitcher_id, updated)

    # Mark resolved
    suggestion["status"] = "accepted"
    suggestion["resolved_at"] = datetime.now(CHICAGO_TZ).isoformat()
    suggestion["resolved_by_coach_id"] = coach_id
    _db.upsert_suggestion(suggestion)

    return {"status": "ok", "suggestion": suggestion}


@coach_router.post("/insights/{suggestion_id}/dismiss")
async def dismiss_insight(suggestion_id: str, request: Request):
    """Dismiss a suggestion."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}

    suggestions = _db.get_pending_suggestions(team_id)
    suggestion = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already resolved")

    suggestion["status"] = "dismissed"
    suggestion["resolved_at"] = datetime.now(CHICAGO_TZ).isoformat()
    suggestion["resolved_by_coach_id"] = coach_id
    _db.upsert_suggestion(suggestion)

    return {"status": "ok"}


# ---- Block Compliance ----

@coach_router.get("/team-programs/{block_id}/compliance")
async def block_compliance(block_id: str, request: Request):
    """Per-pitcher compliance for an active team block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    # Verify block belongs to team
    active = _db.get_active_team_blocks(team_id)
    block = next((b for b in active if b["block_id"] == block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    pitchers = list_team_pitchers(team_id)
    today_entries = (
        _db.get_client().table("daily_entries")
        .select("pitcher_id, active_team_block_id, completed_exercises, plan_generated, throwing")
        .eq("team_id", team_id)
        .eq("date", today_str)
        .execute()
    ).data or []
    entry_map = {e["pitcher_id"]: e for e in today_entries}

    compliance = []
    for p in pitchers:
        pid = p["pitcher_id"]
        entry = entry_map.get(pid)
        status = "skipped"
        modification_reason = None

        if entry:
            throwing = entry.get("throwing") or (entry.get("plan_generated") or {}).get("throwing_plan") or {}
            if throwing.get("team_block_id") == block_id:
                status = "full"
            elif entry.get("active_team_block_id") == block_id:
                status = "modified"
                mods = (entry.get("plan_generated") or {}).get("modifications_applied") or []
                if mods:
                    modification_reason = "; ".join(str(m) for m in mods[:3])

        compliance.append({
            "pitcher_id": pid,
            "name": p.get("name", ""),
            "status": status,
            "modification_reason": modification_reason,
        })

    full = sum(1 for c in compliance if c["status"] == "full")
    modified = sum(1 for c in compliance if c["status"] == "modified")
    skipped = sum(1 for c in compliance if c["status"] == "skipped")

    return {
        "block": block,
        "today": {
            "prescribed": len(pitchers),
            "full": full,
            "modified": modified,
            "skipped": skipped,
            "details": compliance,
        },
    }


# ---- Internal ----

@coach_router.post("/internal/insights/run")
async def run_insights(request: Request):
    """Cron-triggered insight generation. Protected by shared secret."""
    auth_header = request.headers.get("X-Internal-Secret", "")
    expected = os.getenv("INTERNAL_API_SECRET", "")
    if not expected or auth_header != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from bot.services.coach_insights import run_insights_for_team
    # Run for all teams
    teams = _db.get_client().table("teams").select("team_id").execute().data or []
    total = 0
    for team in teams:
        new = run_insights_for_team(team["team_id"])
        total += len(new)

    return {"status": "ok", "new_suggestions": total}
