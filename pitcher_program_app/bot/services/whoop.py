"""WHOOP OAuth 2.0 client with PKCE — multi-pitcher, Supabase-backed.

Adapted from arm-care-bot/whoop_client.py for the pitcher training system.
Each pitcher has their own OAuth tokens stored in Supabase.
"""

import hashlib
import secrets
import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
import base64

import httpx

from bot.config import WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET, WHOOP_REDIRECT_URI
from bot.services import db

logger = logging.getLogger(__name__)

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v1"
SCOPES = "read:recovery read:sleep read:cycles offline"


class WHOOPAuthRequired(Exception):
    """Raised when tokens are missing/expired and manual re-auth is needed."""

    def __init__(self, message: str, pitcher_id: str = None):
        super().__init__(message)
        self.pitcher_id = pitcher_id


# In-memory PKCE state: maps state_token -> {pitcher_id, verifier}
_pending_auth: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------

def build_auth_url(pitcher_id: str) -> str:
    """Generate an OAuth authorization URL with PKCE for a specific pitcher.

    Returns the URL the pitcher should open in a browser.
    """
    if not WHOOP_CLIENT_ID:
        raise WHOOPAuthRequired("WHOOP_CLIENT_ID not configured.", pitcher_id)

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    _pending_auth[state] = {"pitcher_id": pitcher_id, "verifier": verifier}

    params = {
        "response_type": "code",
        "client_id": WHOOP_CLIENT_ID,
        "redirect_uri": WHOOP_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{WHOOP_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, state: str) -> str:
    """Exchange an authorization code for tokens. Returns the pitcher_id on success."""
    pending = _pending_auth.get(state)
    if not pending:
        raise ValueError("Invalid or expired state parameter. Try linking again.")

    pitcher_id = pending["pitcher_id"]
    verifier = pending["verifier"]

    resp = httpx.post(WHOOP_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": WHOOP_REDIRECT_URI,
        "client_id": WHOOP_CLIENT_ID,
        "client_secret": WHOOP_CLIENT_SECRET,
        "code_verifier": verifier,
    }, timeout=15.0)
    resp.raise_for_status()

    token_data = resp.json()
    db.upsert_whoop_tokens(pitcher_id, {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_in": token_data.get("expires_in"),
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "scopes": SCOPES,
    })

    _pending_auth.pop(state, None)
    logger.info("WHOOP linked for pitcher %s", pitcher_id)
    return pitcher_id


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _token_expired(tokens: dict) -> bool:
    obtained = tokens.get("obtained_at")
    if not obtained:
        return True
    if isinstance(obtained, str):
        obtained = datetime.fromisoformat(obtained.replace("Z", "+00:00"))
    expires_in = tokens.get("expires_in") or 0
    return datetime.now(timezone.utc) > obtained + timedelta(seconds=expires_in - 60)


def _refresh_access_token(pitcher_id: str, tokens: dict) -> dict:
    resp = httpx.post(WHOOP_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": WHOOP_CLIENT_ID,
        "client_secret": WHOOP_CLIENT_SECRET,
    }, timeout=15.0)
    resp.raise_for_status()

    new_data = resp.json()
    updated = {
        "access_token": new_data["access_token"],
        "refresh_token": new_data.get("refresh_token", tokens["refresh_token"]),
        "expires_in": new_data.get("expires_in"),
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "scopes": SCOPES,
    }
    db.upsert_whoop_tokens(pitcher_id, updated)
    return updated


def get_access_token(pitcher_id: str) -> str:
    """Return a valid access token for a pitcher, refreshing if needed.

    Raises WHOOPAuthRequired if tokens are missing or refresh fails.
    """
    tokens = db.get_whoop_tokens(pitcher_id)
    if not tokens:
        raise WHOOPAuthRequired("No WHOOP connection found. Use /whoop to link.", pitcher_id)

    if _token_expired(tokens):
        try:
            tokens = _refresh_access_token(pitcher_id, tokens)
        except Exception as e:
            logger.error("WHOOP token refresh failed for %s: %s", pitcher_id, e)
            raise WHOOPAuthRequired(
                "WHOOP connection expired. Use /whoop to reconnect.", pitcher_id
            ) from e

    return tokens["access_token"]


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def _api_get(pitcher_id: str, endpoint: str, params=None) -> dict:
    token = get_access_token(pitcher_id)
    resp = httpx.get(
        f"{WHOOP_API_BASE}{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def _pull_recovery(pitcher_id: str) -> dict | None:
    data = _api_get(pitcher_id, "/recovery", params={"limit": 1})
    if data and data.get("records"):
        rec = data["records"][0]
        score = rec.get("score", {})
        return {
            "recovery_score": score.get("recovery_score"),
            "hrv_rmssd": score.get("hrv_rmssd_milli"),
        }
    return None


def _pull_sleep(pitcher_id: str) -> dict | None:
    data = _api_get(pitcher_id, "/activity/sleep", params={"limit": 1})
    if data and data.get("records"):
        rec = data["records"][0]
        score = rec.get("score", {})
        total_ms = score.get("stage_summary", {}).get("total_in_bed_time_milli")
        sleep_hours = round(total_ms / 3_600_000, 1) if total_ms else None
        return {
            "sleep_performance": score.get("sleep_performance_percentage"),
            "sleep_hours": sleep_hours,
        }
    return None


def _pull_cycles(pitcher_id: str) -> dict | None:
    data = _api_get(pitcher_id, "/cycle", params={"limit": 1})
    if data and data.get("records"):
        rec = data["records"][0]
        score = rec.get("score", {})
        return {"yesterday_strain": score.get("strain")}
    return None


# ---------------------------------------------------------------------------
# Public data functions
# ---------------------------------------------------------------------------

def is_linked(pitcher_id: str) -> bool:
    """Check if a pitcher has WHOOP tokens stored."""
    return db.get_whoop_tokens(pitcher_id) is not None


def pull_whoop_data(pitcher_id: str) -> dict | None:
    """Pull all WHOOP data for a pitcher and cache in Supabase.

    Returns combined dict or None if no data available.
    Raises WHOOPAuthRequired if tokens are missing/expired.
    """
    from bot.config import CHICAGO_TZ
    today = datetime.now(CHICAGO_TZ).date().isoformat()

    # Return cached if already pulled today
    cached = db.get_whoop_daily(pitcher_id, today)
    if cached:
        return cached

    # Pull from WHOOP API (let WHOOPAuthRequired propagate)
    recovery = sleep = cycles = None
    try:
        recovery = _pull_recovery(pitcher_id)
    except WHOOPAuthRequired:
        raise
    except Exception as e:
        logger.warning("WHOOP recovery pull failed for %s: %s", pitcher_id, e)

    try:
        sleep = _pull_sleep(pitcher_id)
    except WHOOPAuthRequired:
        raise
    except Exception as e:
        logger.warning("WHOOP sleep pull failed for %s: %s", pitcher_id, e)

    try:
        cycles = _pull_cycles(pitcher_id)
    except WHOOPAuthRequired:
        raise
    except Exception as e:
        logger.warning("WHOOP cycle pull failed for %s: %s", pitcher_id, e)

    if not any([recovery, sleep, cycles]):
        logger.warning("WHOOP: no data for %s", pitcher_id)
        return None

    result = {
        "date": today,
        "recovery_score": (recovery or {}).get("recovery_score"),
        "hrv_rmssd": (recovery or {}).get("hrv_rmssd"),
        "sleep_performance": (sleep or {}).get("sleep_performance"),
        "sleep_hours": (sleep or {}).get("sleep_hours"),
        "yesterday_strain": (cycles or {}).get("yesterday_strain"),
        "hrv_7day_avg": get_hrv_7day_avg(pitcher_id),
        "raw_data": {"recovery": recovery, "sleep": sleep, "cycles": cycles},
    }

    db.upsert_whoop_daily(pitcher_id, result)
    return result


def get_today_whoop(pitcher_id: str) -> dict | None:
    """Return cached WHOOP data for today (no API call). Returns None if not available."""
    from bot.config import CHICAGO_TZ
    today = datetime.now(CHICAGO_TZ).date().isoformat()
    return db.get_whoop_daily(pitcher_id, today)


def get_hrv_7day_avg(pitcher_id: str) -> float | None:
    """Compute rolling 7-day HRV average from whoop_daily table."""
    rows = db.get_whoop_daily_range(pitcher_id, days=7)
    hrv_values = [r["hrv_rmssd"] for r in rows if r.get("hrv_rmssd") is not None]
    if hrv_values:
        return round(sum(hrv_values) / len(hrv_values), 2)
    return None
