"""Supabase JWT validation for coach endpoints.

Validates the JWT from the Authorization: Bearer header, looks up the
coach record, and attaches coach_id + team_id to request.state.
"""

import os
import logging
from functools import wraps

import jwt
from jwt import PyJWKClient
from fastapi import Request, HTTPException

from bot.services.db import get_coach_by_supabase_id, get_team

logger = logging.getLogger(__name__)

# Supabase issues asymmetric (ES256/RS256) JWTs on newer projects and symmetric
# (HS256) JWTs on legacy projects. We accept both: JWKS for asymmetric,
# SUPABASE_JWT_SECRET for the legacy path.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""

# PyJWKClient caches keys in-memory; safe at module scope.
_jwks_client = PyJWKClient(_JWKS_URL) if _JWKS_URL else None


def _decode_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")

    if alg in ("ES256", "RS256"):
        if not _jwks_client:
            raise HTTPException(status_code=500, detail="SUPABASE_URL not configured for JWKS")
        signing_key = _jwks_client.get_signing_key_from_jwt(token).key
        return jwt.decode(token, signing_key, algorithms=[alg], audience="authenticated")

    if alg == "HS256":
        if not SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET not configured")
        return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")

    raise jwt.InvalidTokenError(f"Unsupported alg: {alg}")


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
        payload = _decode_token(token)
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
        team = get_team(request.state.team_id) or {}
        request.state.team_name = team.get("name", "")
        return

    coach = _validate_coach_jwt(request)
    request.state.coach_id = coach["coach_id"]
    request.state.team_id = coach["team_id"]
    request.state.coach_name = coach["name"]
    request.state.coach_role = coach.get("role", "")
    team = get_team(coach["team_id"]) or {}
    request.state.team_name = team.get("name", "")
