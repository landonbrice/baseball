"""Supabase JWT validation for coach endpoints.

Validates the JWT from the Authorization: Bearer header, looks up the
coach record, and attaches coach_id + team_id to request.state.
"""

import os
import logging
from functools import wraps

import jwt
from fastapi import Request, HTTPException

from bot.services.db import get_coach_by_supabase_id

logger = logging.getLogger(__name__)

# Supabase JWT secret — same one used by Supabase Auth to sign JWTs
# Found in Supabase dashboard → Settings → API → JWT Secret
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


def _validate_coach_jwt(request: Request) -> dict:
    """Extract and validate Supabase JWT from Authorization header.

    Returns the coach DB row if valid.
    Raises HTTPException(401) if invalid or missing.
    Raises HTTPException(403) if JWT is valid but coach not found.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header[7:]  # strip "Bearer "

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid coach JWT: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    supabase_user_id = payload.get("sub")
    if not supabase_user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    coach = get_coach_by_supabase_id(supabase_user_id)
    if not coach:
        raise HTTPException(
            status_code=403,
            detail="No coach account found for this user"
        )

    return coach


async def require_coach_auth(request: Request) -> None:
    """FastAPI dependency that validates coach auth and attaches identity to request.state.

    Usage in route:
        @router.get("/api/coach/something")
        async def something(request: Request):
            await require_coach_auth(request)
            team_id = request.state.team_id
    """
    # Allow bypassing auth in dev
    if os.getenv("DISABLE_AUTH", "").lower() == "true":
        request.state.coach_id = "dev_coach"
        request.state.team_id = "uchicago_baseball"
        request.state.coach_name = "Dev Coach"
        request.state.coach_role = "head"
        return

    coach = _validate_coach_jwt(request)
    request.state.coach_id = coach["coach_id"]
    request.state.team_id = coach["team_id"]
    request.state.coach_name = coach["name"]
    request.state.coach_role = coach.get("role", "")
