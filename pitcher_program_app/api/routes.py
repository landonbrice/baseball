"""API routes — read + action endpoints for the pitcher dashboard."""

import json
import logging
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, Request

from bot.config import KNOWLEDGE_DIR, CONTEXT_WINDOW_CHARS, DISABLE_AUTH
from bot.services.context_manager import (
    load_profile, load_log, load_context, update_exercise_completion,
    append_context, increment_days_since_outing,
)
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


@router.get("/pitcher/{pitcher_id}/profile")
async def get_profile(pitcher_id: str, request: Request):
    """Return pitcher profile."""
    _require_pitcher_auth(request, pitcher_id)
    try:
        return load_profile(pitcher_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")


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
    current_day = profile.get("active_flags", {}).get("days_since_outing", 0)
    upcoming = get_upcoming_days(pitcher_id, current_day)
    return {"upcoming": upcoming}


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


@router.post("/pitcher/{pitcher_id}/checkin")
async def post_checkin(pitcher_id: str, request: Request):
    """Process a daily check-in: triage + plan generation."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    arm_feel = body.get("arm_feel")
    sleep_hours = body.get("sleep_hours")
    if arm_feel is None or sleep_hours is None:
        raise HTTPException(status_code=400, detail="arm_feel and sleep_hours required")

    # Increment rotation day (same as Telegram's start_checkin)
    increment_days_since_outing(pitcher_id)

    try:
        result = await process_checkin(
            pitcher_id,
            int(arm_feel),
            float(sleep_hours),
            int(body.get("energy", 3)),
        )
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

    # Build context
    context_md = load_context(pitcher_id)
    flags = profile.get("active_flags", {})
    pitcher_context = "\n".join([
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'starter')}",
        f"Arm feel: {flags.get('current_arm_feel', 'N/A')}/5",
        f"Days since outing: {flags.get('days_since_outing', 'N/A')}",
    ])
    if context_md:
        pitcher_context += f"\n\nRecent context:\n{context_md[-CONTEXT_WINDOW_CHARS:]}"

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
        append_context(pitcher_id, "interaction", f"Q: {question[:100]}")
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Ask error for {pitcher_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate answer")


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
            # msg is { arm_feel, sleep_hours, soreness? }
            data = msg if isinstance(msg, dict) else {}
            arm_feel = data.get("arm_feel")
            sleep_hours = data.get("sleep_hours")
            if arm_feel is None or sleep_hours is None:
                return {"messages": [{"type": "text", "content": "I need your arm feel and sleep hours to check in."}]}

            increment_days_since_outing(pitcher_id)
            result = await process_checkin(pitcher_id, int(arm_feel), float(sleep_hours))

            messages = []
            flag = result["flag_level"].upper()
            messages.append({"type": "text", "content": f"{flag} flag. {result.get('triage_reasoning', '')}"})

            for alert in result.get("alerts", []):
                messages.append({"type": "text", "content": f"⚠️ {alert}"})

            brief = result.get("morning_brief") or result.get("plan_narrative", "")
            if brief:
                messages.append({"type": "text", "content": brief})

            if result.get("soreness_response"):
                messages.append({"type": "text", "content": result["soreness_response"]})

            messages.append({"type": "status", "content": "plan_loaded"})

            if result.get("notes"):
                messages.append({"type": "text", "content": "Anything else you want to know about today's plan?"})

            return {"messages": messages}

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
            return {"messages": messages}

        else:
            # Free-text Q&A
            question = msg if isinstance(msg, str) else str(msg)
            if not question.strip():
                return {"messages": [{"type": "text", "content": "What's on your mind?"}]}

            profile = load_profile(pitcher_id)
            context_md = load_context(pitcher_id)
            flags = profile.get("active_flags", {})
            pitcher_context = "\n".join([
                f"Name: {profile.get('name', 'Unknown')}",
                f"Role: {profile.get('role', 'starter')}",
                f"Arm feel: {flags.get('current_arm_feel', 'N/A')}/5",
                f"Days since outing: {flags.get('days_since_outing', 'N/A')}",
            ])
            if context_md:
                pitcher_context += f"\n\nRecent context:\n{context_md[-CONTEXT_WINDOW_CHARS:]}"

            system_prompt = load_prompt("system_prompt.md")
            qa_prompt = load_prompt("qa_prompt.md")
            knowledge = retrieve_knowledge(question)

            user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
            user_prompt = user_prompt.replace("{question}", question)
            user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

            answer = await call_llm(system_prompt, user_prompt)
            append_context(pitcher_id, "interaction", f"Q: {question[:100]}")
            return {"messages": [{"type": "text", "content": answer}]}

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    except Exception as e:
        logger.error(f"Chat error for {pitcher_id}: {e}", exc_info=True)
        return {"messages": [{"type": "text", "content": "Something went wrong. Try again or rephrase your question."}]}


@lru_cache(maxsize=1)
def _load_exercise_library() -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/exercises")
async def get_exercises():
    """Return full exercise library."""
    return _load_exercise_library()


@router.get("/exercises/slugs")
async def get_slug_map():
    """Return slug→id mapping for template exercise resolution."""
    library = _load_exercise_library()
    slug_map = {}
    for ex in library["exercises"]:
        slug_map[ex["id"]] = ex["id"]
        if "slug" in ex:
            slug_map[ex["slug"]] = ex["id"]
    return slug_map
