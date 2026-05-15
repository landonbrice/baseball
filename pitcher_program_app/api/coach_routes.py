"""Coach dashboard API routes.

All endpoints require coach auth via require_coach_auth().
Team scoping is enforced by reading team_id from request.state (set by auth).
"""

import os
import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Query

from api.coach_auth import require_coach_auth
from bot.config import CHICAGO_TZ
from bot.services import db as _db
from bot.services.team_scope import (
    get_team_games,
    get_pitcher_next_start,
    list_team_pitchers,
)
from bot.services.team_daily_status import (
    get_team_daily_status,
    to_coach_compliance,
    to_coach_roster,
)

logger = logging.getLogger(__name__)

coach_router = APIRouter(prefix="/api/coach")


# ---- Auth ----

@coach_router.post("/auth/exchange")
async def auth_exchange(request: Request):
    """Validate Supabase JWT and return domain identity + team name (D1, D18)."""
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

    daily_status = get_team_daily_status(team_id, today_str)
    roster = to_coach_roster(daily_status)
    compliance = to_coach_compliance(daily_status)

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
            # Per-domain phases (migration 011). `training_phase` retained for
            # one cycle as a deprecated fallback; new readers should consume
            # throwing_phase / lifting_phase via team_scope.get_team_phase.
            "training_phase": team.get("training_phase", ""),
            "throwing_phase": team.get("throwing_phase") or team.get("training_phase", ""),
            "lifting_phase": team.get("lifting_phase") or team.get("training_phase", ""),
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

@coach_router.post("/pitcher/{pitcher_id}/preview-mutations")
async def coach_preview_mutations(pitcher_id: str, request: Request):
    """Dry-run one-time mutations to a pitcher plan without persisting."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    body = await request.json()
    target_date = body.get("date")
    mutations = body.get("mutations") or []
    if not target_date or not mutations:
        raise HTTPException(status_code=400, detail="date and mutations required")

    entry = _db.get_daily_entry(pitcher_id, target_date)
    if not entry:
        raise HTTPException(status_code=404, detail="No entry for this date")

    from api.routes import _preview_mutations_for_entry
    return _preview_mutations_for_entry(entry, mutations, source=f"coach_preview:{coach_id}")


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


# ---- Nudge ----

@coach_router.post("/pitcher/{pitcher_id}/nudge")
async def nudge_pitcher(pitcher_id: str, request: Request):
    """Send a Telegram DM nudge to a pitcher on the coach's team.

    Rate-limited to once per pitcher per 2 hours.
    """
    from datetime import timezone
    from bot.services.coach_actions import send_nudge

    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    coach_name = request.state.coach_name

    # Verify pitcher belongs to this team
    try:
        pitcher = _db.get_pitcher(pitcher_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="pitcher_not_found")
    if pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="not_your_pitcher")

    # Rate limit: max 1 nudge per 2h per pitcher
    window_start = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    recent = (
        _db.get_client().table("coach_actions")
        .select("created_at")
        .eq("pitcher_id", pitcher_id)
        .eq("action_type", "nudge")
        .gte("created_at", window_start)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    ).data
    if recent:
        last_dt = datetime.fromisoformat(recent[0]["created_at"].replace("Z", "+00:00"))
        retry_after = int(7200 - (datetime.now(timezone.utc) - last_dt).total_seconds())
        raise HTTPException(status_code=429, detail=f"rate_limited:{retry_after}")

    # Send the DM
    try:
        telegram_message_id = await send_nudge(pitcher_id, coach_name)
    except Exception as e:
        logger.error("Nudge DM failed for %s: %s", pitcher_id, e)
        raise HTTPException(status_code=502, detail="telegram_error")

    # Audit log — DM already sent, so audit failure must NOT fail the request.
    # If the insert raises, the rate limiter will be wrong for up to 2h, but
    # that's a softer failure than spamming the pitcher via a client retry.
    sent_at = datetime.now(timezone.utc)
    try:
        _db.get_client().table("coach_actions").insert({
            "coach_id": coach_id,
            "pitcher_id": pitcher_id,
            "action_type": "nudge",
            "telegram_message_id": telegram_message_id,
            "metadata": {},
        }).execute()
    except Exception as audit_err:
        logger.error(
            "Nudge audit insert failed: coach=%s pitcher=%s tmid=%s err=%s",
            coach_id, pitcher_id, telegram_message_id, audit_err,
        )

    return {
        "sent": True,
        "sent_at": sent_at.isoformat(),
        "telegram_message_id": telegram_message_id,
    }


# ---- Insights ----

@coach_router.get("/insights")
async def list_insights(request: Request, status: str = None):
    """Return coach suggestions.

    Without ?status=X: returns pending + recent 7d + stats (used by Insights page).
    With ?status=X: returns filtered list only (backward compat).
    """
    await require_coach_auth(request)
    team_id = request.state.team_id

    if status is not None:
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

    # Full summary: pending + recent 7d + stats
    pending = _db.get_pending_suggestions(team_id)

    seven_days_ago = (datetime.now(CHICAGO_TZ) - timedelta(days=7)).isoformat()
    recent_raw = (
        _db.get_client().table("coach_suggestions")
        .select("*")
        .eq("team_id", team_id)
        .in_("status", ["accepted", "dismissed"])
        .gte("created_at", seven_days_ago)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    ).data or []

    thirty_days_ago = (datetime.now(CHICAGO_TZ) - timedelta(days=30)).isoformat()
    resolved_30d = (
        _db.get_client().table("coach_suggestions")
        .select("status")
        .eq("team_id", team_id)
        .in_("status", ["accepted", "dismissed"])
        .gte("created_at", thirty_days_ago)
        .execute()
    ).data or []

    accepted_7d = [s for s in recent_raw if s["status"] == "accepted"]
    dismissed_7d = [s for s in recent_raw if s["status"] == "dismissed"]
    total_7d = len(accepted_7d) + len(dismissed_7d)
    accepted_30d = sum(1 for s in resolved_30d if s["status"] == "accepted")
    total_30d = len(resolved_30d)

    oldest = min(pending, key=lambda s: s.get("created_at", ""), default=None)
    oldest_days = None
    if oldest:
        try:
            dt = datetime.fromisoformat(oldest["created_at"].replace("Z", "+00:00"))
            oldest_days = (datetime.now(CHICAGO_TZ) - dt.astimezone(CHICAGO_TZ)).days
        except Exception:
            pass

    return {
        "pending": pending,
        "recent": recent_raw,
        "stats": {
            "pending_count": len(pending),
            "accepted_7d": len(accepted_7d),
            "dismissed_7d": len(dismissed_7d),
            "total_7d": total_7d,
            "acceptance_rate_7d": round(len(accepted_7d) / total_7d * 100) if total_7d else 0,
            "acceptance_rate_30d": round(accepted_30d / total_30d * 100) if total_30d else 0,
            "oldest_pending_days": oldest_days,
            "oldest_pending_type": oldest.get("category") if oldest else None,
        },
    }


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


# Plan 8 / C1 — unified accept/dismiss endpoint for insight CTAs.
# Lives alongside the legacy /insights/{id}/accept|dismiss routes (which
# embed mutation-execution logic for the pre_start_nudge category). This
# action endpoint is the canonical write surface for the program-builder
# A4 categories (drift, mismatch, team-lag); it persists `accepted_at`
# (new in migration 032) so suggestion_exists_for_today can suppress
# re-firing for 14 days on accept.

from datetime import timezone as _tz
from pydantic import BaseModel as _IABaseModel, Field as _IAField


class InsightActionRequest(_IABaseModel):
    action: str = _IAField(..., pattern="^(accept|dismiss)$")


@coach_router.post("/insights/{insight_id}/action")
async def coach_post_insight_action(
    insight_id: str, req: InsightActionRequest, request: Request,
):
    """Plan 8 / C1 — accept or dismiss an insight row.

    'accept' = "yes, this is the new normal" — sets status='accepted' and
    accepted_at=now. db.suggestion_exists_for_today suppresses re-firing
    for 14 days for the same (category, pitcher_id, program_id|block_id).

    'dismiss' = "I've seen it" — sets status='dismissed' (no accepted_at).
    The insight may re-fire tomorrow if the underlying condition persists.

    Archiving a program is a SEPARATE action — the coach calls the
    existing /api/coach/programs/{program_id}/archive endpoint and then
    posts here with action='dismiss'. Kept separate so a coach can
    dismiss without archiving and vice versa.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    suggestion = _db.get_coach_suggestion(insight_id)
    if not suggestion or suggestion.get("team_id") != team_id:
        raise HTTPException(status_code=404, detail="insight not found")

    new_status = "accepted" if req.action == "accept" else "dismissed"
    accepted_at_iso = (
        datetime.now(_tz.utc).isoformat()
        if req.action == "accept" else None
    )
    try:
        updated = _db.update_coach_suggestion_status(
            insight_id, status=new_status, accepted_at=accepted_at_iso,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="insight not found")

    # Audit via coach_actions. Schema has no team_id/context_json columns —
    # fold both into `metadata` jsonb per the existing pattern (see
    # Plan 7 C2 phase_override audit).
    _db.insert_coach_action({
        "coach_id": coach_id,
        "pitcher_id": suggestion.get("pitcher_id"),
        "action_type": f"insight_{new_status}",
        "metadata": {
            "team_id": team_id,
            "insight_id": insight_id,
            "category": suggestion.get("category"),
        },
    })
    return {"insight": updated}


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


# ---- Program Builder v1 (coach mirrors of /api/programs/builder/*) ----
# Same handlers as the pitcher-facing routes (see api/routes.py Plan 2 Task 5)
# with require_coach_auth + a team_id ownership check on the underlying pitcher.
# v1 is `interview_mode='personalize'`; team_personalize / authoring land in Plan 6.

from typing import Optional as _Optional
from pydantic import BaseModel as _BaseModel, Field as _Field
from bot.services import (
    program_builder as _program_builder,
    program_builder_socratic as _program_builder_socratic,
    program_generator as _program_generator,
    program_lifecycle as _program_lifecycle,
)


class CoachBuilderCandidatesRequest(_BaseModel):
    # Plan 7 / C4: pitcher_id + personalize_pitcher_id are both optional.
    #   - mode='personalize'        → personalize_pitcher_id REQUIRED (the target pitcher)
    #   - mode='team_personalize'   → personalize_pitcher_id optional (template baked from team defaults)
    #   - mode='authoring'          → personalize_pitcher_id MUST be None (pure template)
    # `pitcher_id` is kept for back-compat with the pre-C4 mirror (treated as
    # an alias for personalize_pitcher_id) and is folded into the latter at
    # validation time. Handler enforces the per-mode rules.
    pitcher_id: _Optional[str] = None
    personalize_pitcher_id: _Optional[str] = None
    domain: str = _Field(..., pattern="^(throwing|lifting)$")
    goal: str
    duration_weeks: int = _Field(..., gt=0, le=52)
    effective_phase: str
    hard_constraints: list[str] = []
    interview_mode: str = _Field(
        default="personalize",
        pattern="^(personalize|team_personalize|authoring)$",
    )


class CoachBuilderGenerateRequest(_BaseModel):
    session_id: str
    tuned_spec: dict
    chosen_template_id: _Optional[str] = None


class CoachProgramArchiveRequest(_BaseModel):
    reason: str


class CoachBuilderTurnRequest(_BaseModel):
    session_id: str
    user_message: str


class CoachBuilderFinalizeRequest(_BaseModel):
    session_id: str
    chosen_template_id: str
    tuned_spec: dict


class CoachInterpretGoalRequest(_BaseModel):
    text: str = _Field(..., min_length=1, max_length=500)
    domain: str = _Field(..., pattern="^(throwing|lifting)$")


# Plan 7 / C2: phase override write. Each field is optional individually but
# at least one MUST be present; enforced in the handler (422 otherwise).
# Empty-string value clears the override (column → NULL). Pattern guards
# against pathological inputs while keeping phase vocabulary free-form
# (the codebase doesn't pin a closed set of phase names — see Phases page).
class PhaseOverrideRequest(_BaseModel):
    throwing_phase: _Optional[str] = _Field(default=None, max_length=60)
    lifting_phase: _Optional[str] = _Field(default=None, max_length=60)


def _require_team_pitcher(pitcher_id: str, team_id: str) -> dict:
    """Load pitcher and verify team ownership. 404 (not 403) on mismatch to keep
    ownership opaque."""
    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=404, detail="pitcher not found")
    return pitcher


@coach_router.post("/programs/builder/candidates")
async def coach_post_builder_candidates(req: CoachBuilderCandidatesRequest, request: Request):
    """Layer 1 (coach): match candidate block templates from a constraint envelope.

    Plan 7 / C4: three modes are now supported. The session row is persisted
    with the chosen mode so the Socratic loop can pick the right prompt
    variant (see program_builder_socratic.advance).
      - 'personalize'      — coach builds FOR a specific pitcher; pitcher_id
                             required; ownership-checked.
      - 'team_personalize' — coach builds a team-wide program; pitcher_id
                             optional (when provided, used as a baseline
                             reference but the program still records the
                             coach as creator).
      - 'authoring'        — coach authors a new template; pitcher_id MUST
                             be omitted (pure template work).
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    # Fold legacy `pitcher_id` field into the canonical `personalize_pitcher_id`.
    target_pitcher_id = req.personalize_pitcher_id or req.pitcher_id

    if req.interview_mode == "personalize":
        if not target_pitcher_id:
            raise HTTPException(
                status_code=422,
                detail="personalize_pitcher_id required for interview_mode='personalize'",
            )
        _require_team_pitcher(target_pitcher_id, team_id)
    elif req.interview_mode == "team_personalize":
        if target_pitcher_id:
            _require_team_pitcher(target_pitcher_id, team_id)
    elif req.interview_mode == "authoring":
        if target_pitcher_id:
            raise HTTPException(
                status_code=422,
                detail="personalize_pitcher_id must be omitted for interview_mode='authoring'",
            )

    envelope = req.model_dump()
    # Envelope mirrors the pitcher-facing /candidates shape. Strip both
    # pitcher-key aliases before forwarding to the matcher.
    envelope.pop("pitcher_id", None)
    envelope.pop("personalize_pitcher_id", None)
    if target_pitcher_id:
        envelope["personalize_pitcher_id"] = target_pitcher_id

    candidates = _program_builder.match_candidates(envelope)
    session_id = _db.create_builder_session({
        "pitcher_id": target_pitcher_id,
        "initiator_id": coach_id,
        "initiator_role": "coach",
        "interview_mode": req.interview_mode,
        "constraint_envelope_json": envelope,
        "candidate_template_ids": [c["block_template_id"] for c in candidates],
        "status": "in_progress",
    })
    return {"session_id": session_id, "candidates": candidates}


@coach_router.post("/programs/builder/generate")
async def coach_post_builder_generate(req: CoachBuilderGenerateRequest, request: Request):
    """Layer 3 + Layer 2 stub (coach)."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    session = _db.get_builder_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    # Authoring mode sessions have no pitcher_id. Other modes must point at a
    # team-scoped pitcher.
    pitcher_id = session.get("pitcher_id")
    mode = session.get("interview_mode") or "personalize"
    if mode != "authoring":
        if not pitcher_id:
            raise HTTPException(status_code=404, detail="session not found")
        _require_team_pitcher(pitcher_id, team_id)

    template_id = req.chosen_template_id
    if not template_id:
        candidate_ids = session.get("candidate_template_ids") or []
        if not candidate_ids:
            raise HTTPException(status_code=400, detail="no candidates and no chosen_template_id")
        template_id = candidate_ids[0]

    # Stamp coach authorship into the constraint envelope (honored by generate_program).
    envelope = dict(session.get("constraint_envelope_json") or {})
    envelope["created_by"] = coach_id
    envelope["created_by_role"] = "coach"

    program = _program_generator.generate_program(
        pitcher_id=pitcher_id,
        template_id=template_id,
        tuned_spec=req.tuned_spec,
        constraint_envelope=envelope,
        session_id=req.session_id,
    )

    _db.update_builder_session(req.session_id, {
        "chosen_template_id": template_id,
        "tuned_spec_json": req.tuned_spec,
        "status": "completed",
        "generated_program_id": program["program_id"],
    })

    return {"program": program}


@coach_router.post("/programs/builder/turn")
async def coach_post_builder_turn(req: CoachBuilderTurnRequest, request: Request):
    """Layer 2 (coach): advance the Socratic conversation by one turn.

    Plan 7 / C4: authoring-mode sessions have no associated pitcher — auth is
    coach team membership only. personalize/team_personalize still require
    that the session's pitcher belongs to the coach's team.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id

    session = _db.get_builder_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    pitcher_id = session.get("pitcher_id")
    mode = session.get("interview_mode") or "personalize"
    if mode != "authoring":
        if not pitcher_id:
            raise HTTPException(status_code=404, detail="session not found")
        _require_team_pitcher(pitcher_id, team_id)

    try:
        return await _program_builder_socratic.advance(req.session_id, req.user_message)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@coach_router.post("/programs/builder/finalize")
async def coach_post_builder_finalize(req: CoachBuilderFinalizeRequest, request: Request):
    """Layer 3 (coach): finalize the interview and generate the draft program.

    Stamps coach authorship into the constraint envelope (honored by
    generate_program) so the program records `created_by` / `created_by_role`.

    Plan 7 / C4: returns `{program, citations}` to match the pitcher-facing
    /finalize shape — the shared BuilderSlideOver renders the "why this
    program" research cards from `citations`. Authoring-mode sessions skip
    the pitcher ownership check (no associated pitcher).
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    session = _db.get_builder_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    pitcher_id = session.get("pitcher_id")
    mode = session.get("interview_mode") or "personalize"
    if mode != "authoring":
        if not pitcher_id:
            raise HTTPException(status_code=404, detail="session not found")
        _require_team_pitcher(pitcher_id, team_id)

    envelope = dict(session.get("constraint_envelope_json") or {})
    envelope["created_by"] = coach_id
    envelope["created_by_role"] = "coach"

    program = _program_generator.generate_program(
        pitcher_id=pitcher_id,
        template_id=req.chosen_template_id,
        tuned_spec=req.tuned_spec,
        constraint_envelope=envelope,
        session_id=req.session_id,
    )

    _db.update_builder_session(req.session_id, {
        "chosen_template_id": req.chosen_template_id,
        "tuned_spec_json": req.tuned_spec,
        "status": "completed",
        "generated_program_id": program["program_id"],
    })

    template = _db.get_block_library_row(req.chosen_template_id) or {}
    doc_ids = template.get("research_doc_ids") or []
    from bot.services.research_resolver import get_citations_for_ids
    citations = get_citations_for_ids(doc_ids)

    return {"program": program, "citations": citations}


@coach_router.post("/programs/builder/interpret-goal")
async def coach_post_builder_interpret_goal(
    req: CoachInterpretGoalRequest,
    request: Request,
):
    """Plan 7 / C4 — coach mirror of POST /api/programs/builder/interpret-goal.

    The BuilderSlideOver's "Other / describe…" goal chip calls this when the
    coach types a free-text description. Same payload + same response as the
    pitcher-facing endpoint (api/routes.py::post_builder_interpret_goal),
    just gated by require_coach_auth instead of pitcher initData. No team
    scoping needed — the interpreter is read-only against a static set of
    canonical goal_tags.
    """
    await require_coach_auth(request)
    from bot.services.goal_interpreter import interpret_goal
    tag = await interpret_goal(req.text, req.domain)
    return {"tag": tag, "confidence": "matched" if tag != "unknown" else "unknown"}


@coach_router.post("/programs/{program_id}/activate")
async def coach_post_program_activate(program_id: str, request: Request):
    """Layer 4 (coach): activate a draft program."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    program = _db.get_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="program not found")
    _require_team_pitcher(program.get("pitcher_id") or "", team_id)
    return _program_lifecycle.activate(program_id)


@coach_router.post("/programs/{program_id}/archive")
async def coach_post_program_archive(program_id: str, req: CoachProgramArchiveRequest, request: Request):
    """Layer 4 (coach): archive a draft or active program with a reason."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    program = _db.get_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="program not found")
    _require_team_pitcher(program.get("pitcher_id") or "", team_id)
    return _program_lifecycle.archive(program_id, reason=req.reason)


# ---- Coach mirrors of /api/programs/{drafts,active,history} (Plan 7 / A3-coach) ----
# A unified /programs endpoint with optional ?status= covers active/draft/archived
# views in one route — coaches don't need a separate /active mirror. /drafts is
# split out because of D14: coach sees only finalized drafts (completed sessions).


@coach_router.get("/pitcher/{pitcher_id}/programs")
async def coach_get_pitcher_programs(
    pitcher_id: str,
    request: Request,
    status: _Optional[str] = Query(default=None, pattern="^(draft|active|archived|error)$"),
):
    """List all programs for a team-scoped pitcher. Optional status filter."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    _require_team_pitcher(pitcher_id, team_id)
    rows = _db.list_programs_for_pitcher_summary(pitcher_id, status=status)
    return {"programs": rows}


@coach_router.get("/pitcher/{pitcher_id}/drafts")
async def coach_get_pitcher_drafts(pitcher_id: str, request: Request):
    """List drafts visible to the coach: only programs whose builder_session
    has status='completed'. Per Plan 6 D14, an in-flight Socratic session does
    not show up as a draft on the coach view — only finalized drafts.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    _require_team_pitcher(pitcher_id, team_id)
    rows = _db.list_completed_session_drafts_for_pitcher(pitcher_id)
    return {"drafts": rows}


# ---- Plan 7 / C3: recent player-built programs (team roster strip) ---------


@coach_router.get("/programs/recent-player-built")
async def coach_get_recent_player_built_programs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return the most recent player-built programs across the coach's team.

    Used by the coach Team Programs page (Plan 7 / C3) "Recent player-built"
    roster strip. Each row carries the pitcher's display name so the UI can
    render `{pitcher_name} · {domain} · {template_id} · {status} · created
    {date}` without a second round-trip.

    Team scoping: `db.list_recent_player_built_programs` joins via the
    pitchers table filtered by `team_id` — cross-team rows are not
    reachable from this endpoint.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    rows = _db.list_recent_player_built_programs(team_id=team_id, limit=limit)
    return {"programs": rows}


# ---- Plan 7 / C3 hotfix: coach mirror of GET /api/programs/templates -------


@coach_router.get("/programs/templates")
async def coach_get_program_templates(
    request: Request,
    domain: _Optional[str] = Query(default=None, pattern="^(throwing|lifting)$"),
    phase: _Optional[str] = Query(default=None),
):
    """Plan 7 / C3 — coach mirror of GET /api/programs/templates.

    Same payload as the pitcher-facing endpoint (api/routes.py::get_program_templates),
    just authed via require_coach_auth instead of _resolve_pitcher_id_from_request.
    Without this, the coach-app's TeamPrograms Library section sends only the
    Supabase Bearer JWT and the pitcher-auth helper would reject it with 401,
    silently rendering the error state. Same query params (`domain`, `phase`),
    same response shape (`{"templates": [...]}`), reuses
    `_db.list_block_library_templates`.
    """
    await require_coach_auth(request)
    rows = _db.list_block_library_templates(domain=domain, phase=phase)
    return {"templates": rows}


# ---- Plan 7 / C2: program-holds log + phase override write -----------------


@coach_router.get("/pitcher/{pitcher_id}/program-holds")
async def coach_get_pitcher_program_holds(
    pitcher_id: str,
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
):
    """Return program_hold_events rows for a team-scoped pitcher (last N days)."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    _require_team_pitcher(pitcher_id, team_id)
    rows = _db.list_program_holds_for_pitcher(pitcher_id, days=days)
    return {"events": rows}


@coach_router.patch("/pitcher/{pitcher_id}/phase-override")
async def coach_patch_phase_override(
    pitcher_id: str,
    req: PhaseOverrideRequest,
    request: Request,
):
    """Coach overrides per-pitcher phase. Audited via coach_actions.

    v1 decision: writing the override does NOT trigger a program-schedule
    recompute. A future iteration can wire A5's recompute path; for now,
    the override only flows through `program_runtime.get_effective_phase`
    on the next plan-gen call.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    _require_team_pitcher(pitcher_id, team_id)

    if req.throwing_phase is None and req.lifting_phase is None:
        raise HTTPException(
            status_code=422, detail="must set at least one of throwing_phase / lifting_phase"
        )

    overrides = _db.update_coach_phase_overrides(
        pitcher_id,
        throwing_phase=req.throwing_phase,
        lifting_phase=req.lifting_phase,
    )

    # Audit row. coach_actions has no team_id / context_json columns; we
    # encode both into `metadata` per the schema in 007_coach_actions.sql.
    try:
        _db.insert_coach_action({
            "coach_id": coach_id,
            "pitcher_id": pitcher_id,
            "action_type": "phase_override",
            "metadata": {
                "team_id": team_id,
                "new_overrides": overrides,
                "source_request": req.model_dump(),
            },
        })
    except Exception as audit_err:
        # Override is already persisted; an audit failure is recoverable from
        # pitcher_training_model history. Surface the error in logs only.
        logger.error(
            "phase_override audit insert failed: coach=%s pitcher=%s err=%s",
            coach_id, pitcher_id, audit_err,
        )

    return {"coach_phase_overrides": overrides}


# ---- Plan 8 / C3: coach-authored research doc workflow (attach-existing) ----


class TemplateResearchDocsRequest(_BaseModel):
    """Plan 8 / C3 request body for setting a template's research_doc_ids.

    v1 is attach-existing only — coach picks from the on-disk research docs
    enumerated by `GET /api/coach/research-docs`. Authoring new docs +
    frontmatter validation + storage choice defer to Plan 9 (L6).
    """
    research_doc_ids: list[str]


@coach_router.get("/research-docs")
async def coach_get_research_docs(request: Request):
    """Plan 8 / C3 — list all research docs the coach can attach to templates.

    Reads from `data/knowledge/research/*.md` via the shared resolver loader
    (see `db.list_research_docs`). Returns:
      {"docs": [{id, title, summary, applies_to, priority}, ...]}
    """
    await require_coach_auth(request)
    return {"docs": _db.list_research_docs()}


@coach_router.patch("/block-library/{template_id}/research-docs")
async def coach_patch_template_research_docs(
    template_id: str,
    req: TemplateResearchDocsRequest,
    request: Request,
):
    """Plan 8 / C3 — set `block_library.research_doc_ids` for a template.

    v1 decision: templates are global — coaches are NOT team-scoped on
    template edits. Any authed coach may edit any template's research doc
    attachments. Plan 9 may add team-ownership; until then any cross-team
    safeguard is intentionally absent.

    Validates each submitted id against the live on-disk research doc list.
    422 on unknown ids; 404 on unknown template. Writes an audit row to
    `coach_actions` with action_type='template_research_docs_edit'.
    """
    await require_coach_auth(request)
    coach_id = request.state.coach_id

    valid_ids = {d["id"] for d in _db.list_research_docs()}
    bad = [i for i in req.research_doc_ids if i not in valid_ids]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"unknown research doc ids: {bad}",
        )

    try:
        updated = _db.update_template_research_doc_ids(
            template_id, req.research_doc_ids
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="template not found")

    # Audit. coach_actions has no team_id / context_json columns — fold any
    # extra context into `metadata` per 007_coach_actions.sql.
    try:
        _db.insert_coach_action({
            "coach_id": coach_id,
            "action_type": "template_research_docs_edit",
            "metadata": {
                "template_id": template_id,
                "doc_ids": req.research_doc_ids,
            },
        })
    except Exception as audit_err:
        # The template write is canonical; an audit failure is recoverable.
        logger.error(
            "template_research_docs_edit audit insert failed: coach=%s template=%s err=%s",
            coach_id, template_id, audit_err,
        )

    return {"template": updated}


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
