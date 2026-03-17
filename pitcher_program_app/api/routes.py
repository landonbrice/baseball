"""API routes — all GET, read-only MVP."""

import json
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, Request

from bot.config import KNOWLEDGE_DIR, DISABLE_AUTH
from bot.services.context_manager import load_profile, load_log
from bot.services.progression import analyze_progression
from api.auth import validate_init_data, resolve_pitcher

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
