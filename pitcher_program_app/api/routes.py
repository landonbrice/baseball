"""API routes — read + action endpoints for the pitcher dashboard."""

import json
import logging
import os
import re
from datetime import date, timedelta, datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, Request

from bot.config import KNOWLEDGE_DIR, CONTEXT_WINDOW_CHARS, DISABLE_AUTH, CHICAGO_TZ
from bot.services.context_manager import (
    load_profile, save_profile, load_log, save_log, load_context,
    update_exercise_completion,
    append_context, increment_days_since_outing, load_saved_plans,
    save_plan, deactivate_plan, update_active_flags, get_recent_entries,
    get_pitcher_dir, activate_plan, update_plan_data, update_throwing_feel,
)
from bot.services.db import get_daily_entries
from bot.services.progression import analyze_progression
from bot.services.plan_generator import get_upcoming_days
from bot.services.checkin_service import process_checkin
from bot.services.outing_service import process_outing
from bot.services.llm import call_llm, load_prompt
from bot.services.knowledge_retrieval import retrieve_knowledge
from api.auth import validate_init_data, resolve_pitcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _require_pitcher_auth(request: Request, pitcher_id: str) -> None:
    """Validate that the request is authenticated and authorized for this pitcher.

    Checks X-Telegram-Init-Data header, validates via HMAC, resolves the
    telegram user to a pitcher_id, and verifies it matches the requested resource.
    Raises HTTPException(401/403) on failure.
    """
    if DISABLE_AUTH:
        return

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing authentication")

    user = validate_init_data(init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    resolved_id = resolve_pitcher(user["id"], user.get("username"))
    if not resolved_id or resolved_id != pitcher_id:
        raise HTTPException(status_code=403, detail="Not authorized for this pitcher")


@router.get("/auth/resolve")
async def auth_resolve(initData: str = Query(default="")):
    """Resolve Telegram initData to pitcher_id."""
    try:
        user = validate_init_data(initData)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"HMAC error: {e}")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    pitcher_id = resolve_pitcher(user["id"], user.get("username"))
    if not pitcher_id:
        raise HTTPException(status_code=404, detail="No pitcher profile linked")

    return {"pitcher_id": pitcher_id}


@router.get("/admin/health")
async def admin_health(request: Request):
    """Admin-only health endpoint. Returns the full daily digest as JSON.

    Auth: requires the Telegram initData to resolve to ADMIN_TELEGRAM_CHAT_ID.
    Bypassed when DISABLE_AUTH=true (dev only).
    """
    from bot.config import ADMIN_TELEGRAM_CHAT_ID
    from bot.services.health_monitor import compute_daily_digest

    if not DISABLE_AUTH:
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        try:
            user = validate_init_data(init_data)
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"HMAC error: {e}")
        if not user:
            raise HTTPException(status_code=401, detail="Invalid initData")
        if user.get("id") != ADMIN_TELEGRAM_CHAT_ID:
            raise HTTPException(status_code=403, detail="Admin only")

    return compute_daily_digest()


@router.get("/pitcher/{pitcher_id}/profile")
async def get_profile(pitcher_id: str, request: Request):
    """Return pitcher profile."""
    _require_pitcher_auth(request, pitcher_id)
    try:
        return load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")


def _deep_merge(base: dict, update: dict) -> dict:
    """Recursively merge *update* into *base*. Non-dict values in update overwrite base."""
    merged = dict(base)
    for key, val in update.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


@router.patch("/pitcher/{pitcher_id}/profile")
async def patch_profile(pitcher_id: str, request: Request):
    """Partially update a pitcher profile via deep-merge."""
    _require_pitcher_auth(request, pitcher_id)

    body = await request.json()
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="Request body must be a non-empty JSON object")

    # Block computed fields
    if "active_flags" in body:
        raise HTTPException(status_code=400, detail="active_flags cannot be updated via profile PATCH")

    # Validate physical_profile numeric fields when present
    phys = body.get("physical_profile")
    if isinstance(phys, dict):
        for field in ("height_in", "weight_lbs"):
            if field in phys:
                v = phys[field]
                if not isinstance(v, (int, float)) or v <= 0:
                    raise HTTPException(status_code=400, detail=f"physical_profile.{field} must be a positive number")

    # Validate current_training.current_maxes when present
    ct = body.get("current_training")
    if isinstance(ct, dict):
        maxes = ct.get("current_maxes")
        if isinstance(maxes, dict):
            for k, v in maxes.items():
                if not isinstance(v, (int, float)):
                    raise HTTPException(status_code=400, detail=f"current_training.current_maxes.{k} must be numeric")

    try:
        profile = load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    updated = _deep_merge(profile, body)
    save_profile(pitcher_id, updated)

    return load_profile(pitcher_id)


@router.get("/pitcher/{pitcher_id}/training-load")
async def get_training_load(pitcher_id: str, request: Request):
    """Return 4-week exercise completion breakdown and current streak."""
    _require_pitcher_auth(request, pitcher_id)

    entries = get_daily_entries(pitcher_id, limit=28)
    if not entries:
        return {
            "weeks": [],
            "streak": 0,
            "current_week_pct": 0,
        }

    today = datetime.now(CHICAGO_TZ).date()

    # Build a date-indexed map of completion data
    completion_by_date: dict[date, tuple[int, int]] = {}
    for entry in entries:
        d = date.fromisoformat(entry["date"])
        ce = entry.get("completed_exercises") or {}
        total = len(ce)
        completed = sum(1 for v in ce.values() if v)
        completion_by_date[d] = (completed, total)

    # Group into ISO weeks (Mon-Sun), looking at last 4 weeks
    this_monday = today - timedelta(days=today.weekday())
    week_labels = ["This week", "1 wk ago", "2 wks ago", "3 wks ago"]
    weeks = []
    for i in range(4):
        week_start = this_monday - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        total = 0
        completed = 0
        for day_offset in range(7):
            d = week_start + timedelta(days=day_offset)
            if d in completion_by_date:
                c, t = completion_by_date[d]
                completed += c
                total += t
        pct = round(completed / total * 100) if total > 0 else 0
        weeks.append({
            "week_label": week_labels[i],
            "completed": completed,
            "total": total,
            "pct": pct,
        })

    # Streak: consecutive days backwards from today with >= 1 completed exercise
    streak = 0
    check_date = today
    while True:
        if check_date in completion_by_date:
            c, _ = completion_by_date[check_date]
            if c > 0:
                streak += 1
                check_date -= timedelta(days=1)
                continue
        break

    current_week_pct = weeks[0]["pct"] if weeks else 0

    return {
        "weeks": weeks,
        "streak": streak,
        "current_week_pct": current_week_pct,
    }


@router.get("/pitcher/{pitcher_id}/log")
async def get_log(pitcher_id: str, request: Request):
    """Return pitcher daily log."""
    _require_pitcher_auth(request, pitcher_id)
    return load_log(pitcher_id)


@router.get("/pitcher/{pitcher_id}/progression")
async def get_progression(pitcher_id: str, request: Request):
    """Return progression analysis."""
    _require_pitcher_auth(request, pitcher_id)
    try:
        return analyze_progression(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")


@router.get("/pitcher/{pitcher_id}/upcoming")
async def get_upcoming(pitcher_id: str, request: Request):
    """Return preview of next 3 rotation days."""
    _require_pitcher_auth(request, pitcher_id)
    try:
        profile = load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    current_day = (profile.get("active_flags") or {}).get("days_since_outing", 0)
    upcoming = get_upcoming_days(pitcher_id, current_day)
    return {"upcoming": upcoming}


@router.get("/pitcher/{pitcher_id}/week-summary")
async def get_week_summary(pitcher_id: str, request: Request):
    """Return Mon-Sun of the current calendar week with per-day status."""
    _require_pitcher_auth(request, pitcher_id)
    from datetime import date, timedelta

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]

    try:
        profile = load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    log = load_log(pitcher_id)
    flags = profile.get("active_flags", {})

    days_until = flags.get("next_outing_days")
    upcoming_date = (today + timedelta(days=int(days_until))).isoformat() if days_until is not None else None

    entries_by_date = {e["date"]: e for e in log.get("entries", [])}

    result = []
    for d in week_days:
        d_str = d.isoformat()
        entry = entries_by_date.get(d_str)

        flag_level = None
        had_outing = False
        if entry:
            pt = entry.get("pre_training") or {}
            flag_level = pt.get("flag_level")
            had_outing = entry.get("outing") is not None

        result.append({
            "date": d_str,
            "day_label": d.strftime("%a")[0],
            "day_number": d.day,
            "is_today": d_str == today.isoformat(),
            "is_past": d < today,
            "flag_level": flag_level,
            "had_outing": had_outing,
            "is_upcoming_outing": d_str == upcoming_date,
        })

    return {"week": result, "today": today.isoformat()}


@router.get("/pitcher/{pitcher_id}/morning-status")
async def morning_status(pitcher_id: str, request: Request):
    """Return unified pitcher state: check-in status, arm feel trend, last interaction, schedule."""
    _require_pitcher_auth(request, pitcher_id)
    from datetime import datetime, date, timedelta

    log = load_log(pitcher_id)
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    entries = log.get("entries", [])
    today_entry = next((e for e in entries if e.get("date") == today_str), None)

    # Check-in status — explicit from active_flags phase, or inferred from log
    checked_in = bool(today_entry and (today_entry.get("pre_training") or {}).get("arm_feel"))

    # Arm feel trend — last 7 entries with arm_feel data
    arm_feels = []
    for e in reversed(entries):
        af = (e.get("pre_training") or {}).get("arm_feel")
        if af is not None:
            arm_feels.append({"date": e.get("date"), "arm_feel": af})
        if len(arm_feels) >= 7:
            break
    arm_feels.reverse()

    # Trend direction
    trend = "stable"
    if len(arm_feels) >= 3:
        recent_avg = sum(a["arm_feel"] for a in arm_feels[-3:]) / 3
        older_avg = sum(a["arm_feel"] for a in arm_feels[:min(3, len(arm_feels))]) / min(3, len(arm_feels))
        if recent_avg - older_avg >= 0.5:
            trend = "improving"
        elif older_avg - recent_avg >= 0.5:
            trend = "declining"

    # Last interaction timestamp from chat_messages
    last_interaction = None
    try:
        from bot.services.context_manager import _using_supabase
        if _using_supabase():
            from bot.services import db as _db
            history = _db.get_chat_history(pitcher_id, limit=1)
            if history:
                last_interaction = history[-1].get("created_at")
    except Exception:
        pass

    # Days until outing from active_flags
    try:
        profile = load_profile(pitcher_id)
        flags = profile.get("active_flags", {})
    except FileNotFoundError:
        flags = {}

    return {
        "checked_in_today": checked_in,
        "has_briefing": bool(today_entry and today_entry.get("morning_brief")),
        "morning_brief": today_entry.get("morning_brief") if today_entry else None,
        "last_interaction": last_interaction,
        "arm_feel_trend": arm_feels,
        "trend_direction": trend,
        "days_until_outing": flags.get("next_outing_days"),
        "days_since_outing": flags.get("days_since_outing"),
        "current_flag_level": flags.get("current_flag_level", "green"),
        "current_arm_feel": flags.get("current_arm_feel"),
    }


@router.get("/pitcher/{pitcher_id}/chat-history")
async def get_chat_history(pitcher_id: str, request: Request, limit: int = Query(default=30)):
    """Return recent chat messages for cross-platform conversation persistence."""
    _require_pitcher_auth(request, pitcher_id)

    try:
        from bot.services.context_manager import _using_supabase
        if _using_supabase():
            from bot.services import db as _db
            messages = _db.get_chat_history(pitcher_id, limit=limit)
            return {"messages": messages}
    except Exception as e:
        logger.warning(f"Chat history fetch failed: {e}")

    return {"messages": []}


@router.post("/pitcher/{pitcher_id}/complete-exercise")
async def complete_exercise(pitcher_id: str, request: Request):
    """Toggle exercise completion from dashboard."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    date = body.get("date")
    exercise_id = body.get("exercise_id")
    completed = body.get("completed", True)
    if not date or not exercise_id:
        raise HTTPException(status_code=400, detail="date and exercise_id required")
    update_exercise_completion(pitcher_id, date, exercise_id, completed)
    return {"status": "ok"}


@router.post("/pitcher/{pitcher_id}/throw-feel")
async def post_throw_feel(pitcher_id: str, request: Request):
    """Log post-throw arm feel rating for a throwing session."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    date = body.get("date")
    post_throw_feel = body.get("post_throw_feel")
    if not date or post_throw_feel is None:
        raise HTTPException(status_code=400, detail="date and post_throw_feel required")
    post_throw_feel = int(post_throw_feel)
    if not 1 <= post_throw_feel <= 5:
        raise HTTPException(status_code=400, detail="post_throw_feel must be 1-5")
    update_throwing_feel(pitcher_id, date, post_throw_feel)
    return {"status": "ok", "post_throw_feel": post_throw_feel}


@router.post("/pitcher/{pitcher_id}/checkin")
async def post_checkin(pitcher_id: str, request: Request):
    """Process a daily check-in: triage + plan generation."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    arm_feel = body.get("arm_feel")
    sleep_hours = body.get("sleep_hours")
    if arm_feel is None or sleep_hours is None:
        raise HTTPException(status_code=400, detail="arm_feel and sleep_hours required")

    try:
        result = await process_checkin(
            pitcher_id,
            int(arm_feel),
            float(sleep_hours),
            int(body.get("energy", 3)),
        )

        # Increment rotation day AFTER check-in (skip for return-to-throwing phase)
        profile_check = load_profile(pitcher_id)
        if (profile_check.get("active_flags") or {}).get("phase") != "return_to_throwing":
            increment_days_since_outing(pitcher_id)

        return {"status": "ok", **result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    except Exception as e:
        logger.error(f"Checkin error for {pitcher_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Check-in processing failed")


@router.post("/pitcher/{pitcher_id}/outing")
async def post_outing(pitcher_id: str, request: Request):
    """Process a post-outing report: reset rotation, generate recovery."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    pitch_count = body.get("pitch_count")
    post_arm_feel = body.get("post_arm_feel")
    if pitch_count is None or post_arm_feel is None:
        raise HTTPException(status_code=400, detail="pitch_count and post_arm_feel required")

    try:
        result = await process_outing(
            pitcher_id,
            int(pitch_count),
            int(post_arm_feel),
            str(body.get("notes", "")),
        )
        return {"status": "ok", **result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    except Exception as e:
        logger.error(f"Outing error for {pitcher_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Outing processing failed")


@router.post("/pitcher/{pitcher_id}/ask")
async def post_ask(pitcher_id: str, request: Request):
    """Answer a free-text question with LLM + pitcher context."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")

    try:
        profile = load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    # Build context (shared with Telegram Q&A)
    from bot.handlers.qa import _build_qa_context
    pitcher_context = _build_qa_context(profile, pitcher_id)

    # Include last generated plan for continuity
    recent = get_recent_entries(pitcher_id, n=1)
    if recent:
        last = recent[0]
        lifting = last.get("lifting", {})
        if lifting and lifting.get("exercises"):
            exercise_names = [ex.get("name", "") for ex in lifting["exercises"]]
            pitcher_context += f"\n\nLast prescribed lift ({last.get('date', '?')}, Day {last.get('rotation_day', '?')}): {', '.join(exercise_names)}"

    # Build conversation history for multi-turn
    history = body.get("history", [])
    history_text = ""
    for msg in history[-4:]:  # max 4 prior exchanges
        role = msg.get("role", "user")
        history_text += f"\n{role.upper()}: {msg.get('content', '')}"

    try:
        system_prompt = load_prompt("system_prompt.md")
        qa_prompt = load_prompt("qa_prompt.md")
        knowledge = retrieve_knowledge(question)

        user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
        user_prompt = user_prompt.replace("{question}", question)
        user_prompt = user_prompt.replace("{knowledge_context}", knowledge)
        if history_text:
            user_prompt += f"\n\nConversation so far:{history_text}\n\nLatest question: {question}"

        answer = await call_llm(system_prompt, user_prompt)
        append_context(pitcher_id, "interaction", f"Q: {question[:80]} | A: {answer[:200]}")
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Ask error for {pitcher_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate answer")


@router.post("/pitcher/{pitcher_id}/set-next-outing")
async def set_next_outing(pitcher_id: str, request: Request):
    """Set when the pitcher expects to pitch next. Recalculates rotation position.

    Body: { days_until_outing: int }  (0 = today, 1 = tomorrow, etc.)
    The system sets days_since_outing = rotation_length - days_until_outing
    so the plan generator produces the correct day's programming.
    """
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    days_until = body.get("days_until_outing")
    if days_until is None:
        raise HTTPException(status_code=400, detail="days_until_outing required")

    try:
        profile = load_profile(pitcher_id)
        rotation = profile.get("rotation_length", 7)
        # days_since_outing is the inverse: if outing is in 3 days and rotation is 7,
        # we're on day 4 (rotation_length - days_until)
        new_day = max(0, rotation - int(days_until))
        update_active_flags(pitcher_id, {
            "days_since_outing": new_day,
            "next_outing_days": int(days_until),
        })
        return {"status": "ok", "days_since_outing": new_day, "next_outing_days": int(days_until)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")


def _persist_chat(pitcher_id: str, user_content: str, bot_messages: list, source: str = "mini_app"):
    """Persist user message and bot response to chat_messages table."""
    try:
        from bot.services.context_manager import _using_supabase
        if _using_supabase():
            from bot.services import db as _db
            if user_content:
                _db.insert_chat_message(pitcher_id, source, "user", user_content)
            for m in bot_messages:
                if m.get("type") == "text" and m.get("content"):
                    _db.insert_chat_message(pitcher_id, source, "assistant", m["content"])
    except Exception as e:
        logger.debug(f"Chat persistence failed (non-critical): {e}")


@router.post("/pitcher/{pitcher_id}/chat")
async def post_chat(pitcher_id: str, request: Request):
    """Unified chat endpoint. Handles structured check-ins, outings, and free-text Q&A.

    Body: { message: str|dict, type: "text"|"checkin"|"outing"|"soreness" }
    Returns: { messages: [{ type: "text"|"buttons"|"status", content: str, buttons?: [...] }] }
    """
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    msg = body.get("message", "")
    msg_type = body.get("type", "text")

    try:
        if msg_type == "checkin":
            # msg is { arm_report?, arm_feel?, sleep_hours?, lift_preference?, throw_intent?, next_pitch_days? }
            data = msg if isinstance(msg, dict) else {}
            arm_feel = data.get("arm_feel")
            arm_report = data.get("arm_report", "")
            lift_preference = data.get("lift_preference", "")
            throw_intent = data.get("throw_intent", "")
            next_pitch_days = data.get("next_pitch_days")

            # Classify arm report if no numeric arm_feel provided
            if arm_feel is None and arm_report:
                from bot.handlers.daily_checkin import _classify_arm_report
                arm_feel, _ = await _classify_arm_report(arm_report)
            elif arm_feel is None:
                arm_feel = 4  # default

            # Default sleep from profile baseline
            profile_chk = load_profile(pitcher_id)
            sleep_hours = data.get("sleep_hours") or (profile_chk.get("biometric_integration") or {}).get("avg_sleep_hours") or 7.0

            # Update schedule if next_pitch_days specified
            if next_pitch_days and int(next_pitch_days) > 0:
                rotation = profile_chk.get("rotation_length", 7)
                new_day = max(0, rotation - int(next_pitch_days))
                update_active_flags(pitcher_id, {"days_since_outing": new_day, "next_outing_days": int(next_pitch_days)})

            try:
                result = await process_checkin(
                    pitcher_id, int(arm_feel), float(sleep_hours),
                    arm_report=arm_report, lift_preference=lift_preference,
                    throw_intent=throw_intent, next_pitch_days=next_pitch_days,
                )
            except Exception as checkin_err:
                logger.error(f"Check-in processing error for {pitcher_id}: {checkin_err}", exc_info=True)
                return {
                    "messages": [
                        {"type": "text", "content": "Something went wrong with your check-in. Please try again."},
                    ],
                    "morning_brief": None,
                    "flag_level": "green",
                }

            # Assemble response messages from checkin result
            try:
                messages = []
                flag = result["flag_level"].upper()
                plan_source = result.get("source")

                # Hard failure: process_checkin returned with no plan at all
                if plan_source is None:
                    messages.append({"type": "text", "content":
                        f"{flag} flag. Your check-in data has been saved. "
                        "Plan generation had an issue. Tap \"Retry plan\" to try again."})
                    messages.append({"type": "status", "content": "plan_failed"})
                    _persist_chat(pitcher_id, f"Check-in: arm {arm_feel}/5 (plan gen failed)", messages)
                    return {"messages": messages, "morning_brief": None, "flag_level": result.get("flag_level", "green")}

                # Increment rotation day only on first successful check-in today (not re-check-in)
                today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
                existing = load_log(pitcher_id)
                already_had_plan = any(
                    e.get("date") == today_str and (e.get("plan_narrative") or (e.get("plan_generated") or {}).get("exercise_blocks"))
                    for e in existing.get("entries", [])
                )
                if not already_had_plan and (profile_chk.get("active_flags") or {}).get("phase") != "return_to_throwing":
                    increment_days_since_outing(pitcher_id)

                messages.append({"type": "text", "content": f"{flag} flag. {result.get('triage_reasoning', '')}"})

                for alert in result.get("alerts", []):
                    messages.append({"type": "text", "content": f"⚠️ {alert}"})

                brief = result.get("morning_brief") or result.get("plan_narrative", "")
                if isinstance(brief, dict):
                    brief = brief.get("coaching_note", "") or str(brief)
                brief = str(brief) if brief else ""
                if brief:
                    messages.append({"type": "text", "content": brief})

                if result.get("soreness_response"):
                    messages.append({"type": "text", "content": result["soreness_response"]})

                # Degraded path: python_fallback shipped because LLM review failed.
                # Plan is complete and usable, but no coaching commentary.
                if plan_source == "python_fallback":
                    messages.append({"type": "status", "content": "plan_degraded",
                                     "reason": result.get("source_reason")})
                else:
                    messages.append({"type": "status", "content": "plan_loaded"})

                if result.get("notes"):
                    messages.append({"type": "text", "content": "Anything else you want to know about today's plan?"})

                # Persist to chat_messages
                checkin_summary = f"Check-in: arm {arm_feel}/5, lift {lift_preference or 'auto'}, throw {throw_intent or 'none'}"
                _persist_chat(pitcher_id, checkin_summary, messages)

                return {
                    "messages": messages,
                    "morning_brief": brief or None,
                    "flag_level": result.get("flag_level", "green"),
                }
            except Exception as assembly_err:
                logger.error(f"Check-in response assembly failed for {pitcher_id}: {assembly_err}", exc_info=True)
                # Plan was already saved by process_checkin — return success with minimal info
                return {
                    "messages": [
                        {"type": "text", "content": f"Plan saved. Response assembly error: {assembly_err}"},
                        {"type": "status", "content": "plan_loaded"},
                    ],
                    "morning_brief": None,
                    "flag_level": result.get("flag_level", "green"),
                }

        elif msg_type == "outing":
            # msg is { pitch_count, post_arm_feel, notes? }
            data = msg if isinstance(msg, dict) else {}
            pitch_count = data.get("pitch_count")
            post_arm_feel = data.get("post_arm_feel")
            if pitch_count is None or post_arm_feel is None:
                return {"messages": [{"type": "text", "content": "I need your pitch count and arm feel to log the outing."}]}

            result = await process_outing(pitcher_id, int(pitch_count), int(post_arm_feel), str(data.get("notes", "")))

            messages = []
            messages.append({"type": "text", "content": result.get("recovery_plan", "Outing logged.")})
            for alert in result.get("alerts", []):
                messages.append({"type": "text", "content": f"⚠️ {alert}"})
            messages.append({"type": "status", "content": "rotation_reset"})

            # Persist to chat_messages
            outing_summary = f"Outing: {pitch_count} pitches, arm feel {post_arm_feel}/5"
            _persist_chat(pitcher_id, outing_summary, messages)

            return {
                "messages": messages,
                "flag_level": result.get("flag_level", "green"),
            }

        else:
            # Free-text Q&A
            question = msg if isinstance(msg, str) else str(msg)
            if not question.strip():
                return {"messages": [{"type": "text", "content": "What's on your mind?"}]}

            profile = load_profile(pitcher_id)
            flags = profile.get("active_flags", {})

            # Build context (shared with Telegram Q&A — includes injuries, goals, phase, etc.)
            from bot.handlers.qa import _build_qa_context
            pitcher_context = _build_qa_context(profile, pitcher_id)

            # Include last generated plan for continuity
            recent = get_recent_entries(pitcher_id, n=1)
            if recent:
                last = recent[0]
                lifting = last.get("lifting", {})
                if lifting and lifting.get("exercises"):
                    exercise_names = [ex.get("name", "") for ex in lifting["exercises"]]
                    pitcher_context += f"\n\nLast prescribed lift ({last.get('date', '?')}, Day {last.get('rotation_day', '?')}): {', '.join(exercise_names)}"

            # Include plan_context if pitcher is viewing a specific plan
            plan_context = body.get("plan_context")
            if plan_context:
                plan_data = plan_context.get("plan_data", {})
                pc_lifting = plan_data.get("lifting", {})
                pc_exercises = pc_lifting.get("exercises", [])
                if pc_exercises:
                    exercise_list = ", ".join(f"{ex['name']} {ex.get('rx','')}" for ex in pc_exercises)
                    pitcher_context += f"\n\nThe pitcher is viewing and asking about this specific plan:\n"
                    pitcher_context += f"Title: {plan_data.get('title', '')}\n"
                    pitcher_context += f"Exercises: {exercise_list}\n"
                    pitcher_context += "When making modifications, return a program_modification JSON block with the updated exercise list."

            system_prompt = load_prompt("system_prompt.md")
            qa_prompt = load_prompt("qa_prompt.md")
            knowledge = retrieve_knowledge(question)

            user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
            user_prompt = user_prompt.replace("{question}", question)
            user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

            history = body.get("history", [])

            # Route complex protocol requests to reasoning model
            from bot.handlers.qa import _REASONING_KEYWORDS
            from bot.services.llm import call_llm_reasoning
            q_lower = question.lower()
            if any(kw in q_lower for kw in _REASONING_KEYWORDS):
                answer = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
            else:
                answer = await call_llm(system_prompt, user_prompt, history=history)

            messages = []

            # Try to parse save_plan or program_modification from LLM response
            clean_answer = answer
            plan_data = _extract_json_block(answer, "save_plan")
            mod_data = _extract_json_block(answer, "program_modification")
            mutation_data = _extract_json_block(answer, "plan_mutation")

            if mutation_data and mutation_data.get("mutations"):
                # Coach suggested plan mutations — return for preview
                clean_answer = _strip_json_block(answer, "plan_mutation")
                messages.append({"type": "text", "content": clean_answer.strip()})
                messages.append({
                    "type": "plan_mutation",
                    "content": "Coach suggests changes to your plan",
                    "mutations": mutation_data["mutations"],
                })
            elif plan_data:
                # Strip the JSON block from the displayed answer
                clean_answer = _strip_json_block(answer, "save_plan")
                messages.append({"type": "text", "content": clean_answer.strip()})
                messages.append({
                    "type": "save_plan",
                    "content": plan_data.get("title", "Suggested plan"),
                    "plan": plan_data,
                })
            elif mod_data:
                clean_answer = _strip_json_block(answer, "program_modification")
                messages.append({"type": "text", "content": clean_answer.strip()})

                # Log if exercises array is missing from modification
                if not mod_data.get("exercises"):
                    logger.warning(f"program_modification missing exercises array — changes: {mod_data.get('changes', [])}")

                # Auto-save as plan if requested
                if mod_data.get("save_as_plan"):
                    plan_context = body.get("plan_context")
                    if plan_context and plan_context.get("plan_id"):
                        # Update existing plan in place
                        plan_updates = {}
                        if mod_data.get("exercises"):
                            plan_updates["lifting"] = {"exercises": mod_data["exercises"]}
                        if mod_data.get("title"):
                            plan_updates["title"] = mod_data["title"]
                        plan_updates["summary"] = ", ".join(mod_data.get("changes", []))
                        update_plan_data(pitcher_id, plan_context["plan_id"], plan_updates)
                        messages.append({
                            "type": "text",
                            "content": f"Updated plan: {mod_data.get('title', 'Program modification')}.",
                        })
                        messages.append({"type": "status", "content": "plan_updated"})
                    else:
                        saved = save_plan(pitcher_id, {
                            "title": mod_data.get("title", "Program modification"),
                            "category": "program_modification",
                            "summary": ", ".join(mod_data.get("changes", [])),
                            "content": "\n".join(mod_data.get("changes", [])),
                            "structured_changes": mod_data.get("exercises", []),
                            "modifies_daily_plan": True,
                            "active": True,
                        })
                        messages.append({
                            "type": "text",
                            "content": f"Saved as active plan: {saved['title']}. This will influence your daily programming.",
                        })

                    # If mod has exercises, directly update today's log (fast path)
                    if mod_data.get("exercises"):
                        from datetime import datetime as _dt_fast
                        today_fast = _dt_fast.now().strftime("%Y-%m-%d")
                        log_fast = load_log(pitcher_id)
                        for entry in log_fast["entries"]:
                            if entry.get("date") == today_fast:
                                if "lifting" not in entry:
                                    entry["lifting"] = {}
                                entry["lifting"]["exercises"] = mod_data["exercises"]
                                break
                        save_log(pitcher_id, log_fast)
                        messages.append({"type": "status", "content": "plan_loaded"})
                    else:
                        # No exercises — regenerate today's plan (slow path)
                        try:
                            from bot.services.plan_generator import generate_plan
                            from bot.services.triage import triage
                            from datetime import datetime as _dt

                            profile = load_profile(pitcher_id)
                            arm_feel = flags.get("current_arm_feel", 4)
                            triage_result = triage(
                                arm_feel=arm_feel, sleep_hours=7.0,
                                pitcher_profile=profile, energy=3,
                            )
                            new_plan = await generate_plan(pitcher_id, triage_result)

                            today = _dt.now().strftime("%Y-%m-%d")
                            log = load_log(pitcher_id)
                            for entry in log["entries"]:
                                if entry.get("date") == today:
                                    if new_plan.get("arm_care"):
                                        entry["arm_care"] = new_plan["arm_care"]
                                    if new_plan.get("lifting"):
                                        entry["lifting"] = new_plan["lifting"]
                                    if new_plan.get("throwing"):
                                        entry["throwing"] = new_plan["throwing"]
                                    if new_plan.get("warmup"):
                                        entry["warmup"] = new_plan["warmup"]
                                    if new_plan.get("notes"):
                                        entry["notes"] = new_plan["notes"]
                                    entry["morning_brief"] = new_plan.get("morning_brief")
                                    entry["plan_narrative"] = new_plan.get("narrative")
                                    break
                            save_log(pitcher_id, log)
                            messages.append({"type": "status", "content": "plan_loaded"})
                        except Exception as e:
                            logger.warning(f"Failed to regenerate plan after modification: {e}")

                # Update active_modifications in profile
                mod_title = mod_data.get("title", "")
                if mod_title:
                    current_mods = flags.get("active_modifications", [])
                    if mod_title not in current_mods:
                        current_mods.append(mod_title)
                        update_active_flags(pitcher_id, {"active_modifications": current_mods})

                messages.append({"type": "status", "content": "profile_updated"})
            else:
                messages.append({"type": "text", "content": answer})

            # Append context summary — always include answer excerpt
            summary = f"Q: {question[:80]} | A: {clean_answer[:200]}"
            if plan_data:
                summary += f" | Saved plan: {plan_data.get('title', '')}"
            if mod_data:
                summary += f" | Mod: {', '.join(mod_data.get('changes', [])[:2])}"
            append_context(pitcher_id, "interaction", summary)

            # Persist user question and bot response to chat_messages
            _persist_chat(pitcher_id, question, messages)

            # Record Q&A success for health monitoring (never raises)
            try:
                from bot.services.health_monitor import record_qa_success
                record_qa_success(pitcher_id)
            except Exception:
                pass

            return {"messages": messages}

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    except Exception as e:
        logger.error(f"Chat error for {pitcher_id}: {e}", exc_info=True)
        # Record Q&A error for health monitoring (never raises)
        try:
            from bot.services.health_monitor import record_qa_error
            record_qa_error(pitcher_id, type(e).__name__)
        except Exception:
            pass
        return {"messages": [{"type": "text", "content": "Something went wrong. Try again or rephrase your question."}]}


@router.get("/pitcher/{pitcher_id}/plans")
async def get_plans(pitcher_id: str, request: Request):
    """Return saved plans for a pitcher."""
    _require_pitcher_auth(request, pitcher_id)
    plans = load_saved_plans(pitcher_id)
    return {"plans": plans}


@router.post("/pitcher/{pitcher_id}/plans")
async def post_plan(pitcher_id: str, request: Request):
    """Save a new plan."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    if not body.get("title"):
        raise HTTPException(status_code=400, detail="title required")
    plan = save_plan(pitcher_id, body)
    return {"status": "ok", "plan": plan}


@router.post("/pitcher/{pitcher_id}/plans/{plan_id}/deactivate")
async def post_deactivate_plan(pitcher_id: str, plan_id: str, request: Request):
    """Deactivate a saved plan."""
    _require_pitcher_auth(request, pitcher_id)
    found = deactivate_plan(pitcher_id, plan_id)
    if not found:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "ok"}


@router.post("/pitcher/{pitcher_id}/plans/{plan_id}/activate")
async def post_activate_plan(pitcher_id: str, plan_id: str, request: Request):
    """Activate a saved plan."""
    _require_pitcher_auth(request, pitcher_id)
    found = activate_plan(pitcher_id, plan_id)
    if not found:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "ok"}


@router.post("/pitcher/{pitcher_id}/apply-plan/{plan_id}")
async def apply_plan_to_today(pitcher_id: str, plan_id: str, request: Request):
    """Apply a saved plan's exercises to today's daily log entry."""
    _require_pitcher_auth(request, pitcher_id)
    from datetime import datetime as _dt

    # Load the plan
    plans = load_saved_plans(pitcher_id)
    plan = None
    for p in plans:
        if p["id"] == plan_id:
            plan = p
            break
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Activate it and mark as modifies_daily_plan
    activate_plan(pitcher_id, plan_id)
    update_plan_data(pitcher_id, plan_id, {"modifies_daily_plan": True})

    # Update today's log entry with the plan's exercises
    today = _dt.now().strftime("%Y-%m-%d")
    log = load_log(pitcher_id)

    today_entry = None
    for entry in log["entries"]:
        if entry.get("date") == today:
            today_entry = entry
            break

    if today_entry is None:
        today_entry = {
            "date": today,
            "rotation_day": (load_profile(pitcher_id).get("active_flags") or {}).get("days_since_outing", 0),
            "pre_training": None,
            "plan_generated": {},
            "completed_exercises": {},
        }
        log["entries"].append(today_entry)

    if plan.get("arm_care"):
        today_entry["arm_care"] = plan["arm_care"]
    if plan.get("lifting"):
        today_entry["lifting"] = plan["lifting"]
    if plan.get("throwing"):
        today_entry["throwing"] = plan["throwing"]
    if plan.get("warmup"):
        today_entry["warmup"] = plan["warmup"]
    if plan.get("notes"):
        today_entry["notes"] = plan["notes"]
    today_entry["morning_brief"] = f"Applied plan: {plan.get('title', 'Custom plan')}"
    today_entry["plan_generated"] = {
        "template_day": f"plan_{plan_id}",
        "exercise_blocks": [],
        "modifications_applied": [f"Applied plan: {plan.get('title', '')}"],
    }

    save_log(pitcher_id, log)
    append_context(pitcher_id, "plan_applied", f"Applied '{plan.get('title', '')}' to today's training")

    return {"status": "ok", "applied_plan": plan.get("title", "")}


def _relaxed_parse_custom_plan(raw: str, fallback_brief: str = "Custom plan") -> dict | None:
    """Relaxed JSON parser for the custom-plan endpoint only.

    The shared `_parse_plan_json` in plan_generator requires a top-level
    `morning_brief` key — load-bearing for the daily check-in path where that
    field drives the mini-app's morning brief UI. The custom-plan path has no
    morning context, so the LLM frequently omits it. This helper accepts JSON
    without `morning_brief` and injects a default so downstream code (which
    reads arm_care/lifting/throwing/notes) works unchanged.

    Returns the parsed dict or None. Must never raise — caller handles None.
    """
    import re as _re
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown code fences if present
    fence_match = _re.search(r"```(?:json)?\s*\n?(.*?)```", text, _re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    def _finalize(parsed):
        if not isinstance(parsed, dict):
            return None
        if "morning_brief" not in parsed:
            parsed["morning_brief"] = fallback_brief
        return parsed

    # Try direct parse
    try:
        return _finalize(json.loads(text))
    except json.JSONDecodeError:
        pass

    # Try to find a balanced JSON object in the text
    brace_start = text.find("{")
    if brace_start < 0:
        return None
    depth = 0
    for i in range(brace_start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return _finalize(json.loads(text[brace_start:i + 1]))
                except json.JSONDecodeError:
                    return None
    return None


@router.post("/pitcher/{pitcher_id}/generate-plan")
async def generate_custom_plan(pitcher_id: str, request: Request):
    """Generate a custom plan from user selections and save it."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()

    plan_type = body.get("plan_type", "full_body")
    duration_min = body.get("duration_min", 45)
    emphasis = body.get("emphasis", [])
    notes = body.get("notes", "")

    profile = load_profile(pitcher_id)
    context_md = load_context(pitcher_id)

    # Map plan_type to template day
    type_to_template = {
        "lower_power": "day_2", "lower_strength": "day_4",
        "upper_pull": "day_3", "upper_push": "day_3",
        "full_body": "day_2", "recovery": "day_1", "arm_care": "day_1",
    }
    type_labels = {
        "lower_power": "Lower body — power focus",
        "lower_strength": "Lower body — strength focus",
        "upper_pull": "Upper body — pull emphasis",
        "upper_push": "Upper body — push emphasis",
        "full_body": "Full body",
        "recovery": "Recovery / mobility",
        "arm_care": "Arm care focused session",
    }
    emphasis_labels = {
        "heavy_compounds": "Prioritize heavy compound movements",
        "hypertrophy": "Hypertrophy rep ranges (3x8-12), moderate weight",
        "explosive": "Explosive/power emphasis — med ball, jumps",
        "fpm": "Extra flexor-pronator mass and arm health work",
        "pre_game": "Keep intensity low, activation focused",
    }

    template_key = type_to_template.get(plan_type, "day_2")
    from bot.services.plan_generator import load_template, _build_pitcher_context, _parse_plan_json
    template = load_template("starter_7day.json")
    day_data = template["days"].get(template_key, {})

    request_text = f"Generate a {type_labels.get(plan_type, plan_type)} plan."
    if duration_min:
        request_text += f" Target duration: {duration_min} minutes."
    if emphasis:
        emph_text = "; ".join(emphasis_labels.get(e, e) for e in emphasis)
        request_text += f" Emphasis: {emph_text}."
    if notes:
        request_text += f" Additional: {notes}"

    pitcher_context = _build_pitcher_context(profile, context_md)
    system_prompt = load_prompt("system_prompt.md")
    plan_prompt = load_prompt("plan_generation_structured.md")

    user_prompt = plan_prompt.replace("{pitcher_context}", pitcher_context)
    user_prompt = user_prompt.replace("{rotation_day}", f"Custom plan: {type_labels.get(plan_type, plan_type)}")
    user_prompt = user_prompt.replace("{triage_result}", '{"flag_level": "green", "modifications": [], "protocol_adjustments": {"arm_care_template": "heavy"}}')
    user_prompt = user_prompt.replace("{templates}", json.dumps(day_data, indent=2))
    user_prompt = user_prompt.replace("{recent_logs}", "[]")
    # Fill the two placeholders the custom-plan path doesn't use, so they don't
    # leak as literal "{relevant_research}" / "{checkin_inputs}" into the LLM prompt.
    user_prompt = user_prompt.replace("{relevant_research}", "No specific research loaded for this custom plan request.")
    user_prompt = user_prompt.replace("{checkin_inputs}", "No check-in inputs — this is a custom plan request, not a daily check-in.")
    user_prompt += (
        f"\n\n## CUSTOM PLAN REQUEST\n{request_text}\n\n"
        "Generate a complete plan matching this request. "
        "Ensure appropriate exercise count (6-8 for 45min, 4-5 for 25min, 8-10 for 60min).\n\n"
        "IMPORTANT — RESPONSE FORMAT:\n"
        "Return a single JSON object. You MUST include a top-level `morning_brief` key "
        "(a one-line string describing this session — it can be as simple as the plan title). "
        "Also include `arm_care`, `lifting`, `throwing`, and `notes` keys as described above. "
        "Do not wrap the JSON in markdown code fences unless necessary."
    )

    try:
        response = await call_llm(system_prompt, user_prompt, max_tokens=2000)
    except TimeoutError:
        logger.warning(f"Custom plan generation LLM timeout for {pitcher_id}")
        raise HTTPException(
            status_code=504,
            detail="Plan generation is taking longer than expected. Please try again in a moment.",
        )
    except Exception as e:
        logger.error(f"Custom plan LLM call failed for {pitcher_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Upstream AI service is unavailable. Please try again shortly.",
        )

    plan_data = _parse_plan_json(response)

    # Fallback: _parse_plan_json strictly requires a top-level `morning_brief` key,
    # which the custom-plan path doesn't actually need (there's no morning here).
    # If the strict parse failed, try a relaxed local parse that injects a default
    # morning_brief so the shared parser isn't touched (it's load-bearing for the
    # daily check-in path).
    if not plan_data and response:
        plan_data = _relaxed_parse_custom_plan(response, fallback_brief=type_labels.get(plan_type, "Custom plan"))
        if plan_data:
            logger.info(f"Custom plan: relaxed parse succeeded for {pitcher_id} (strict parser rejected response)")

    if not plan_data:
        # Log the first 500 chars of the raw response so we can diagnose prompt/LLM drift
        raw_preview = (response or "")[:500].replace("\n", " ")
        logger.error(
            f"Custom plan parse failed for {pitcher_id}. "
            f"plan_type={plan_type} duration={duration_min} emphasis={emphasis}. "
            f"Raw response preview: {raw_preview!r}"
        )
        raise HTTPException(
            status_code=502,
            detail="The AI returned an unexpected format. Please try again, or adjust your emphasis selections.",
        )

    title = type_labels.get(plan_type, "Custom plan")
    if emphasis:
        title += f" — {', '.join(emphasis[:2])}"

    saved = save_plan(pitcher_id, {
        "title": title,
        "category": "custom_program",
        "summary": request_text[:200],
        "arm_care": plan_data.get("arm_care", {}),
        "lifting": plan_data.get("lifting", {}),
        "throwing": plan_data.get("throwing", {"type": "none"}),
        "notes": plan_data.get("notes", []),
        "modifies_daily_plan": False,
        "active": True,
        "generation_request": {
            "plan_type": plan_type, "duration_min": duration_min,
            "emphasis": emphasis, "notes": notes,
        },
    })

    return {"plan": saved}


@lru_cache(maxsize=1)
def _load_exercise_library() -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/exercises")
async def get_exercises():
    """Return full exercise library."""
    return _load_exercise_library()


def _extract_json_block(text: str, key: str):
    """Try to extract a JSON object containing `key` from LLM response text."""
    # Look for ```json blocks first
    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL):
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, dict) and key in data:
                return data[key] if isinstance(data[key], dict) else data
        except json.JSONDecodeError:
            continue

    # Look for inline { "key": ... } pattern
    pattern = rf'"{key}"\s*:\s*\{{'
    match = re.search(pattern, text)
    if match:
        # Find the enclosing object
        start = text.rfind("{", 0, match.start())
        if start < 0:
            start = match.start() + len(f'"{key}":')
            # Find opening brace of the value
            start = text.index("{", start)
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict) and key in data:
                            return data[key] if isinstance(data[key], dict) else data
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def _strip_json_block(text: str, key: str) -> str:
    """Remove JSON blocks containing `key` from text."""
    # Remove ```json blocks containing the key
    result = re.sub(r"```(?:json)?\s*\n?.*?" + re.escape(key) + r".*?```", "", text, flags=re.DOTALL)

    # Remove inline JSON objects containing the key
    pattern = rf'\{{\s*"' + re.escape(key) + r'".*?\}\}'
    result = re.sub(pattern, "", result, flags=re.DOTALL)

    return result.strip()


# Legacy slug-style IDs found in existing daily_entries → proper exercise IDs
_SLUG_ORPHAN_MAP = {
    "ex_broad_jump": "ex_018",
    "ex_front_squat": "ex_002",
    "ex_hip_circle": "ex_095",
    "ex_hip_thrust": "ex_003",
    "ex_lateral_lunge": "ex_009",
    "ex_med_ball_rotational": "ex_014",
    "ex_nordic_curl": "ex_013",
    "ex_rdl": "ex_005",
    "ex_romanian_deadlift": "ex_005",
    "ex_wrist_roller": "ex_039",
    "ex_band_er_90": "ex_032",
    "ex_band_er_ir": "ex_033",
    "ex_band_pull_apart": "ex_036",
    "ex_banded_monster_walk": "ex_095",
    "ex_db_bench": "ex_025",
    "ex_db_row": "ex_020",
    "ex_dead_bug": "ex_046",
    "ex_dumbbell_bench_press": "ex_025",
    "ex_face_pull": "ex_023",
    "ex_farmers_carry": "ex_049",
    "ex_goblet_squat": "ex_007",
    "ex_j_band_routine": "ex_055",
    "ex_landmine_press": "ex_026",
    "ex_med_ball_overhead_slam": "ex_016",
    "ex_med_ball_rotational_throw": "ex_014",
    "ex_modified_side_plank_er_pressout_ball_drop": "ex_081",
    "ex_pallof_press": "ex_045",
    "ex_pronator_supinator_band": "ex_041",
    "ex_pullup": "ex_019",
    "ex_push_up": "ex_024",
    "ex_radial_ulnar": "ex_073",
    "ex_sa_db_bench": "ex_025",
    "ex_side_plank": "ex_048",
    "ex_trx_row": "ex_022",
    "ex_weighted_pullup": "ex_019",
    "ex_wrist_extension": "ex_040",
    "ex_wrist_flexion": "ex_039",
    "ex_wrist_flexion_extension": "ex_039",
}


@router.get("/exercises/slugs")
async def get_slug_map():
    """Return slug→id mapping for template exercise resolution."""
    library = _load_exercise_library()
    slug_map = dict(_SLUG_ORPHAN_MAP)
    for ex in library["exercises"]:
        slug_map[ex["id"]] = ex["id"]
        if "slug" in ex:
            slug_map[ex["slug"]] = ex["id"]
        for alias in ex.get("aliases", []):
            normalized = alias.lower().replace(" ", "_").replace("-", "_")
            slug_map[f"ex_{normalized}"] = ex["id"]
    return slug_map


# ---------------------------------------------------------------------------
# Exercise Swap
# ---------------------------------------------------------------------------

@router.get("/exercises/{exercise_id}/alternatives")
async def get_exercise_alternatives(
    exercise_id: str,
    request: Request,
    pitcher_id: str = Query(...),
    date: str = Query(None),
):
    """Return 3-4 alternative exercises for inline swapping."""
    _require_pitcher_auth(request, pitcher_id)
    from bot.services.exercise_alternatives import find_alternatives

    profile = load_profile(pitcher_id)
    flags = profile.get("active_flags") or {}
    rotation_day = flags.get("days_since_outing", 0)

    if not date:
        from datetime import datetime
        date = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    alternatives = find_alternatives(
        exercise_id=exercise_id,
        pitcher_id=pitcher_id,
        date=date,
        rotation_day=rotation_day,
    )
    return {"alternatives": alternatives}


@router.post("/pitcher/{pitcher_id}/swap-exercise")
async def swap_exercise(pitcher_id: str, request: Request):
    """Swap an exercise in today's plan and record in pitcher model."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()

    date = body.get("date")
    from_id = body.get("from_exercise_id")
    to_id = body.get("to_exercise_id")
    reason = body.get("reason", "preference")
    source = body.get("source", "inline_swap")

    logger.info(
        "swap_exercise REQUEST: pitcher=%s date=%s from=%s to=%s reason=%s",
        pitcher_id, date, from_id, to_id, reason,
    )

    if not all([date, from_id, to_id]):
        raise HTTPException(status_code=400, detail="date, from_exercise_id, to_exercise_id required")

    from bot.services.db import (
        get_daily_entry, upsert_daily_entry, get_training_model,
        upsert_training_model, get_exercise,
    )

    # 1. Update daily_entries — replace exercise in plan_generated
    entry = get_daily_entry(pitcher_id, date)
    if not entry:
        logger.warning("swap_exercise: no entry for pitcher=%s date=%s", pitcher_id, date)
        raise HTTPException(status_code=404, detail="No entry for this date")

    plan = entry.get("plan_generated") or {}
    replacement_ex = get_exercise(to_id)
    if not replacement_ex:
        logger.warning("swap_exercise: replacement exercise not found: to_id=%s", to_id)
        raise HTTPException(status_code=404, detail=f"Replacement exercise {to_id} not in library")

    # Find and replace in lifting block
    swapped = False
    lifting = plan.get("lifting") or {}
    for ex in (lifting.get("exercises") or []):
        if ex.get("exercise_id") == from_id:
            ex["exercise_id"] = to_id
            ex["name"] = replacement_ex.get("name", to_id)
            rx_data = replacement_ex.get("prescription") or {}
            phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
            if phase.get("sets") and phase.get("reps"):
                ex["prescribed"] = f"{phase['sets']}x{phase['reps']}"
                if phase.get("intensity"):
                    ex["prescribed"] += f" @ {phase['intensity']}"
            ex["rx"] = ex.get("prescribed", ex.get("rx", "3x8"))
            ex["swapped_from"] = from_id
            swapped = True
            break

    # Also check exercise_blocks (legacy format)
    if not swapped:
        for block in (plan.get("exercise_blocks") or []):
            for ex in (block.get("exercises") or []):
                if ex.get("exercise_id") == from_id:
                    ex["exercise_id"] = to_id
                    ex["name"] = replacement_ex.get("name", to_id)
                    rx_data = replacement_ex.get("prescription") or {}
                    phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
                    if phase.get("sets") and phase.get("reps"):
                        ex["prescribed"] = f"{phase['sets']}x{phase['reps']}"
                    ex["rx"] = ex.get("prescribed", ex.get("rx", "3x8"))
                    ex["swapped_from"] = from_id
                    swapped = True
                    break
            if swapped:
                break

    if not swapped:
        # Diagnostic: log what's actually in the plan so we can compare with from_id
        plan_lifting_ids = [
            ex.get("exercise_id", "?") for ex in (plan.get("lifting", {}).get("exercises") or [])
        ]
        plan_block_ids = [
            ex.get("exercise_id", "?")
            for block in (plan.get("exercise_blocks") or [])
            for ex in (block.get("exercises") or [])
        ]
        logger.warning(
            "swap_exercise: from_id=%s NOT FOUND in plan. "
            "lifting.exercises ids=%s | exercise_blocks ids=%s",
            from_id, plan_lifting_ids, plan_block_ids,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Exercise {from_id} not found in today's plan (have: {plan_lifting_ids + plan_block_ids})",
        )

    logger.info("swap_exercise: SUCCESS pitcher=%s from=%s to=%s", pitcher_id, from_id, to_id)

    # Save updated plan
    entry["plan_generated"] = plan
    upsert_daily_entry(pitcher_id, entry)

    # 2. Update pitcher_training_model
    model = get_training_model(pitcher_id)

    # Append to swap history (keep last 30)
    swap_history = list(model.get("recent_swap_history") or [])
    swap_history.append({
        "date": date,
        "from_id": from_id,
        "to_id": to_id,
        "reason": reason,
        "source": source,
    })
    if len(swap_history) > 30:
        swap_history = swap_history[-30:]

    # Update equipment constraints if reason is no_equipment
    equipment = list(model.get("equipment_constraints") or [])
    if reason == "no_equipment":
        from_ex = get_exercise(from_id)
        if from_ex:
            ex_name = (from_ex.get("name") or "").lower().replace(" ", "_")
            constraint = f"no_{ex_name}"
            if constraint not in equipment:
                equipment.append(constraint)

    # Check if exercise has been swapped away 3+ times → dislike
    preferences = dict(model.get("exercise_preferences") or {})
    swap_away_count = sum(1 for s in swap_history if s.get("from_id") == from_id)
    if swap_away_count >= 3 and preferences.get(from_id) != "dislike":
        preferences[from_id] = "dislike"

    # Update weekly state
    week_state = dict(model.get("current_week_state") or {})
    days = list(week_state.get("days") or [])
    for d in days:
        if d.get("date") == date:
            swaps = list(d.get("exercises_swapped") or [])
            swaps.append({"from": from_id, "to": to_id})
            d["exercises_swapped"] = swaps
            break

    model["recent_swap_history"] = swap_history
    model["equipment_constraints"] = equipment
    model["exercise_preferences"] = preferences
    model["current_week_state"] = week_state
    upsert_training_model(pitcher_id, model)

    return {
        "status": "swapped",
        "from_exercise_id": from_id,
        "to_exercise_id": to_id,
        "updated_plan": plan,
    }


@router.post("/pitcher/{pitcher_id}/apply-mutations")
async def apply_mutations(pitcher_id: str, request: Request):
    """Apply coach-suggested mutations to today's plan."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()

    date = body.get("date")
    mutations = body.get("mutations", [])
    source = body.get("source", "coach_suggestion")

    if not date or not mutations:
        raise HTTPException(status_code=400, detail="date and mutations required")

    from bot.services.db import (
        get_daily_entry, upsert_daily_entry, get_training_model,
        upsert_training_model, get_exercise,
    )

    entry = get_daily_entry(pitcher_id, date)
    if not entry:
        raise HTTPException(status_code=404, detail="No entry for this date")

    plan = entry.get("plan_generated") or {}
    model = get_training_model(pitcher_id)
    swap_history = list(model.get("recent_swap_history") or [])

    for m in mutations:
        action = m.get("action")
        lifting = plan.get("lifting") or {}
        exercises = lifting.get("exercises") or []

        if action == "swap":
            from_id = m.get("from_exercise_id")
            to_id = m.get("to_exercise_id")
            replacement = get_exercise(to_id) if to_id else None
            for ex in exercises:
                if ex.get("exercise_id") == from_id:
                    if replacement:
                        ex["exercise_id"] = to_id
                        ex["name"] = replacement.get("name", to_id)
                    if m.get("rx"):
                        ex["prescribed"] = m["rx"]
                        ex["rx"] = m["rx"]
                    ex["swapped_from"] = from_id
                    break
            swap_history.append({"date": date, "from_id": from_id, "to_id": to_id, "reason": "coach", "source": source})

        elif action == "add":
            ex_id = m.get("exercise_id")
            new_ex = get_exercise(ex_id) if ex_id else None
            new_entry = {
                "exercise_id": ex_id,
                "name": new_ex.get("name", ex_id) if new_ex else ex_id,
                "prescribed": m.get("rx", "3x8"),
                "rx": m.get("rx", "3x8"),
            }
            if m.get("note"):
                new_entry["note"] = m["note"]
            # Insert after a specific exercise if specified
            after_id = m.get("after_exercise_id")
            inserted = False
            if after_id:
                for i, ex in enumerate(exercises):
                    if ex.get("exercise_id") == after_id:
                        exercises.insert(i + 1, new_entry)
                        inserted = True
                        break
            if not inserted:
                exercises.append(new_entry)

        elif action == "remove":
            ex_id = m.get("exercise_id")
            exercises[:] = [ex for ex in exercises if ex.get("exercise_id") != ex_id]

        elif action == "modify":
            ex_id = m.get("exercise_id")
            for ex in exercises:
                if ex.get("exercise_id") == ex_id:
                    if m.get("rx"):
                        ex["prescribed"] = m["rx"]
                        ex["rx"] = m["rx"]
                    if m.get("note"):
                        ex["note"] = m["note"]
                    break

        lifting["exercises"] = exercises
        plan["lifting"] = lifting

    # Save updated plan
    entry["plan_generated"] = plan
    upsert_daily_entry(pitcher_id, entry)

    # Update swap history and preferences in model
    if len(swap_history) > 30:
        swap_history = swap_history[-30:]
    model["recent_swap_history"] = swap_history

    # Apply preference learning from swap mutations (same as inline swap logic)
    preferences = dict(model.get("exercise_preferences") or {})
    for m in mutations:
        if m.get("action") == "swap" and m.get("from_exercise_id"):
            from_id = m["from_exercise_id"]
            swap_away_count = sum(1 for s in swap_history if s.get("from_id") == from_id)
            if swap_away_count >= 3 and preferences.get(from_id) != "dislike":
                preferences[from_id] = "dislike"
    model["exercise_preferences"] = preferences

    upsert_training_model(pitcher_id, model)

    return {"status": "mutations_applied", "mutation_count": len(mutations), "updated_plan": plan}


# ---------------------------------------------------------------------------
# Staff / Team endpoints
# ---------------------------------------------------------------------------

@router.get("/staff/pulse")
async def staff_pulse():
    """Team check-in status — public staff view (no auth required).

    Returns which pitchers have checked in today, their rotation info, and role.
    """
    from datetime import date as _date

    from bot.services import db as _db

    today_str = _date.today().isoformat()

    all_pitchers = _db.list_pitchers()

    # Exclude test accounts
    pitchers = [p for p in all_pitchers if p.get("pitcher_id") != "test_pitcher_001"]

    pitcher_results = []
    checked_in_count = 0

    for p in pitchers:
        pid = p.get("pitcher_id", "")
        full_name = p.get("name") or pid
        first_name = full_name.split()[0] if full_name else pid

        # Determine role
        role_raw = (p.get("role") or "").lower()
        if role_raw in ("reliever", "rp", "closer", "cl"):
            role = "RP"
        else:
            role = "SP"

        # Get active flags for rotation info
        flags = _db.get_active_flags(pid)
        days_since = flags.get("days_since_outing")

        if role == "SP":
            if days_since is not None:
                rotation_info = "Day %d" % int(days_since)
            else:
                rotation_info = "Day 0"
        else:
            # Relievers: Day 0 or 1 means "Day after", otherwise "Available"
            if days_since is not None and int(days_since) <= 1:
                rotation_info = "Day after"
            else:
                rotation_info = "Available"

        # Check if pitcher has a daily entry for today
        today_entry = _db.get_daily_entries(pid, limit=1)
        checked_in = False
        if today_entry and today_entry[0].get("date") == today_str:
            entry = today_entry[0]
            # Consider checked-in if the entry has pre_training arm_feel
            pre = entry.get("pre_training")
            if isinstance(pre, dict) and pre.get("arm_feel") is not None:
                checked_in = True
            elif entry.get("arm_feel") is not None:
                checked_in = True

        if checked_in:
            checked_in_count += 1

        pitcher_results.append({
            "first_name": first_name,
            "checked_in": checked_in,
            "rotation_info": rotation_info,
            "role": role,
        })

    return {
        "checked_in_count": checked_in_count,
        "total_pitchers": len(pitchers),
        "pitchers": pitcher_results,
    }


@router.get("/pitcher/{pitcher_id}/weekly-narrative")
async def get_weekly_narrative(pitcher_id: str, request: Request):
    """Return the most recent weekly coaching narrative."""
    _require_pitcher_auth(request, pitcher_id)
    from bot.services import db as _db
    summaries = _db.get_weekly_summaries(pitcher_id, limit=1)
    if not summaries:
        return {"narrative": None, "headline": None, "week_start": None}
    latest = summaries[0]
    summary = latest.get("summary") or {}
    return {
        "narrative": summary.get("narrative"),
        "headline": summary.get("headline"),
        "week_start": latest.get("week_start"),
    }


@router.get("/pitcher/{pitcher_id}/trend")
async def pitcher_trend(pitcher_id: str, request: Request):
    """4-week arm feel trend for a pitcher.

    Returns weekly aggregations, a sparkline of recent arm_feel values,
    outing-day markers, and current consecutive check-in streak.
    """
    _require_pitcher_auth(request, pitcher_id)

    from datetime import date as _date, timedelta

    from bot.services import db as _db

    entries = _db.get_daily_entries(pitcher_id, limit=30)

    # Entries come newest-first; reverse for chronological order
    entries.sort(key=lambda e: e.get("date", ""))

    today_str = _date.today().isoformat()

    # --- Sparkline (last 15 arm_feel values) ---
    arm_feel_entries = []
    for e in entries:
        af = None
        pre = e.get("pre_training")
        if isinstance(pre, dict):
            af = pre.get("arm_feel")
        if af is None:
            af = e.get("arm_feel")
        if af is not None:
            arm_feel_entries.append({"date": e.get("date"), "arm_feel": af, "entry": e})

    sparkline_data = arm_feel_entries[-15:] if len(arm_feel_entries) > 15 else arm_feel_entries
    sparkline = [d["arm_feel"] for d in sparkline_data]

    # --- Outing day indices (which sparkline positions had an outing) ---
    outing_day_indices = []
    for idx, d in enumerate(sparkline_data):
        entry = d["entry"]
        if entry.get("outing") is not None:
            outing_day_indices.append(idx)

    # --- Current streak (consecutive days with a check-in ending at today) ---
    current_streak = 0
    check_dates = set()
    for e in entries:
        d = e.get("date")
        if d:
            # Count as checked-in if there is pre_training arm_feel or arm_feel
            pre = e.get("pre_training")
            has_checkin = False
            if isinstance(pre, dict) and pre.get("arm_feel") is not None:
                has_checkin = True
            elif e.get("arm_feel") is not None:
                has_checkin = True
            if has_checkin:
                check_dates.add(d)

    day = _date.today()
    while day.isoformat() in check_dates:
        current_streak += 1
        day = day - timedelta(days=1)

    # --- Weeks (group by ISO week, compute avg/high/low arm_feel) ---
    week_buckets = {}  # type: dict
    for d in arm_feel_entries:
        entry_date = _date.fromisoformat(d["date"])
        iso_year, iso_week, _ = entry_date.isocalendar()
        key = (iso_year, iso_week)
        if key not in week_buckets:
            # Monday of this ISO week
            monday = entry_date - timedelta(days=entry_date.weekday())
            week_buckets[key] = {
                "start_date": monday.isoformat(),
                "values": [],
            }
        week_buckets[key]["values"].append(d["arm_feel"])

    # Sort by week key and take last 4 weeks
    sorted_keys = sorted(week_buckets.keys())[-4:]
    weeks = []
    for i, key in enumerate(sorted_keys, start=1):
        bucket = week_buckets[key]
        vals = bucket["values"]
        weeks.append({
            "week_label": "Wk %d" % i,
            "start_date": bucket["start_date"],
            "avg": round(sum(vals) / len(vals), 1),
            "high": max(vals),
            "low": min(vals),
            "days_logged": len(vals),
        })

    return {
        "weeks": weeks,
        "sparkline": sparkline,
        "outing_day_indices": outing_day_indices,
        "current_streak": current_streak,
    }


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@router.get("/schedule")
async def get_schedule():
    """Public endpoint — return the full UChicago baseball schedule."""
    from bot.services import db as _db
    return {"games": _db.get_schedule(limit=100)}


# ---------------------------------------------------------------------------
# Season Summary
# ---------------------------------------------------------------------------

@router.get("/pitcher/{pitcher_id}/season-summary")
async def season_summary(pitcher_id: str, request: Request):
    """Full-season data for the Season tab: stats, timeline, rotation
    signature, outing recovery curves, sleep correlation, weekly narratives."""
    _require_pitcher_auth(request, pitcher_id)
    from bot.services.progression import build_season_summary
    return build_season_summary(pitcher_id)


# ---------------------------------------------------------------------------
# WHOOP OAuth Callback
# ---------------------------------------------------------------------------

@router.get("/pitcher/{pitcher_id}/mobility-today")
async def get_mobility_today(pitcher_id: str, request: Request):
    """Return today's mobility videos from the 10-week rotation."""
    from bot.services.mobility import get_today_mobility
    return get_today_mobility()


@router.get("/pitcher/{pitcher_id}/whoop-today")
async def whoop_today(pitcher_id: str, request: Request):
    """Return today's WHOOP data for a pitcher, or linked=false if not connected."""
    _require_pitcher_auth(request, pitcher_id)
    from bot.services.whoop import is_linked, get_today_whoop
    from bot.services.db import get_whoop_daily_range

    if not is_linked(pitcher_id):
        return {"linked": False, "data": None, "averages": None}

    data = get_today_whoop(pitcher_id)
    avg_data = None
    if data:
        rows = get_whoop_daily_range(pitcher_id, days=7)
        recoveries = [r["recovery_score"] for r in rows if r.get("recovery_score") is not None]
        strains = [r["yesterday_strain"] for r in rows if r.get("yesterday_strain") is not None]
        sleeps = [r["sleep_hours"] for r in rows if r.get("sleep_hours") is not None]
        avg_data = {
            "avg_recovery": round(sum(recoveries) / len(recoveries), 1) if recoveries else None,
            "avg_strain": round(sum(strains) / len(strains), 1) if strains else None,
            "avg_sleep_hours": round(sum(sleeps) / len(sleeps), 1) if sleeps else None,
        }

    return {"linked": True, "data": data, "averages": avg_data}


@router.get("/whoop/callback")
async def whoop_callback(code: str = Query(...), state: str = Query(...)):
    """Handle WHOOP OAuth redirect — exchange code for tokens."""
    from bot.services.whoop import exchange_code
    from fastapi.responses import HTMLResponse

    try:
        pitcher_id = exchange_code(code, state)
        return HTMLResponse(
            "<html><body style='font-family:system-ui;text-align:center;padding:60px'>"
            "<h2>WHOOP Connected!</h2>"
            f"<p>Linked to <b>{pitcher_id}</b>. You can close this tab.</p>"
            "</body></html>"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("WHOOP callback failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to connect WHOOP. Try again.")
