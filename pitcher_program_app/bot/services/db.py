"""Supabase database client — all CRUD operations for pitcher data.

Provides a synchronous Supabase client (service role) used by context_manager
and any other module that needs persistent data access.
"""

import logging
import os

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client = None


def get_client() -> Client:
    """Return a cached Supabase client (service role)."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _client = create_client(url, key)
        logger.info("Supabase client initialized")
    return _client


# ---------------------------------------------------------------------------
# Pitchers
# ---------------------------------------------------------------------------

def get_pitcher(pitcher_id: str) -> dict:
    """Load a pitcher row as a dict. Raises KeyError if not found."""
    resp = get_client().table("pitchers").select("*").eq("pitcher_id", pitcher_id).execute()
    if not resp.data:
        raise KeyError(f"Pitcher not found: {pitcher_id}")
    return resp.data[0]


def get_pitcher_by_telegram_id(telegram_id: int) -> dict:
    """Look up pitcher by telegram_id. Returns None if not found."""
    resp = get_client().table("pitchers").select("*").eq("telegram_id", telegram_id).execute()
    return resp.data[0] if resp.data else None


def get_pitcher_by_username(username: str) -> dict:
    """Look up pitcher by telegram_username (case-insensitive). Returns None if not found."""
    resp = get_client().table("pitchers").select("*").ilike("telegram_username", username).execute()
    return resp.data[0] if resp.data else None


def update_pitcher(pitcher_id: str, updates: dict) -> None:
    """Partial update of pitcher fields."""
    get_client().table("pitchers").update(updates).eq("pitcher_id", pitcher_id).execute()


def list_pitchers() -> list:
    """Return all pitcher rows."""
    resp = get_client().table("pitchers").select("*").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Injury History
# ---------------------------------------------------------------------------

def get_injury_history(pitcher_id: str) -> list:
    resp = get_client().table("injury_history").select("*").eq("pitcher_id", pitcher_id).order("created_at").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Active Flags
# ---------------------------------------------------------------------------

def get_active_flags(pitcher_id: str) -> dict:
    """Return active_flags for a pitcher. Returns empty dict if none."""
    resp = get_client().table("active_flags").select("*").eq("pitcher_id", pitcher_id).execute()
    return resp.data[0] if resp.data else {}


def upsert_active_flags(pitcher_id: str, flags: dict) -> None:
    """Insert or update active_flags for a pitcher."""
    flags["pitcher_id"] = pitcher_id
    get_client().table("active_flags").upsert(flags, on_conflict="pitcher_id").execute()


# ---------------------------------------------------------------------------
# Daily Entries
# ---------------------------------------------------------------------------

def get_daily_entries(pitcher_id: str, limit: int = 30) -> list:
    """Return recent daily entries for a pitcher, newest first."""
    resp = (get_client().table("daily_entries")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .order("date", desc=True)
            .limit(limit)
            .execute())
    return resp.data or []


def get_daily_entry(pitcher_id: str, date: str) -> dict:
    """Return a single daily entry by pitcher + date. Returns None if not found."""
    resp = (get_client().table("daily_entries")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .eq("date", date)
            .execute())
    return resp.data[0] if resp.data else None


# Columns that exist in daily_entries table — prevents PostgREST 400 on unknown fields
_DAILY_ENTRY_COLUMNS = {
    "pitcher_id", "date", "rotation_day", "days_since_outing", "pre_training",
    "plan_narrative", "morning_brief", "plan_generated", "actual_logged",
    "bot_observations", "arm_care", "lifting", "throwing", "notes",
    "completed_exercises", "soreness_response",
}


def upsert_daily_entry(pitcher_id: str, entry: dict) -> None:
    """Insert or update a daily entry (upsert on pitcher_id + date)."""
    row = {k: v for k, v in entry.items() if k in _DAILY_ENTRY_COLUMNS}
    row["pitcher_id"] = pitcher_id
    get_client().table("daily_entries").upsert(row, on_conflict="pitcher_id,date").execute()


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------

def insert_chat_message(pitcher_id: str, source: str, role: str, content: str, metadata: dict = None) -> None:
    """Insert a chat message."""
    row = {
        "pitcher_id": pitcher_id,
        "source": source,
        "role": role,
        "content": content,
        "metadata": metadata or {},
    }
    get_client().table("chat_messages").insert(row).execute()


def get_chat_history(pitcher_id: str, limit: int = 30) -> list:
    """Return recent chat messages, oldest first."""
    resp = (get_client().table("chat_messages")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute())
    rows = resp.data or []
    rows.reverse()  # oldest first
    return rows


# ---------------------------------------------------------------------------
# Saved Plans
# ---------------------------------------------------------------------------

def get_saved_plans(pitcher_id: str) -> list:
    """Return all saved plans for a pitcher."""
    resp = (get_client().table("saved_plans")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .order("created_at", desc=True)
            .execute())
    return resp.data or []


def insert_saved_plan(pitcher_id: str, plan: dict) -> dict:
    """Insert a new saved plan. Returns the inserted row."""
    plan["pitcher_id"] = pitcher_id
    resp = get_client().table("saved_plans").insert(plan).execute()
    return resp.data[0] if resp.data else plan


def update_saved_plan(plan_id: int, updates: dict) -> None:
    """Update a saved plan by id."""
    get_client().table("saved_plans").update(updates).eq("id", plan_id).execute()


def get_saved_plan(plan_id) -> dict:
    """Get a single saved plan by id."""
    resp = get_client().table("saved_plans").select("*").eq("id", int(plan_id)).execute()
    return resp.data[0] if resp.data else None


# ---------------------------------------------------------------------------
# Weekly Summaries
# ---------------------------------------------------------------------------

def upsert_weekly_summary(pitcher_id: str, week_start: str, summary: dict) -> None:
    row = {
        "pitcher_id": pitcher_id,
        "week_start": week_start,
        "summary": summary,
    }
    get_client().table("weekly_summaries").upsert(row, on_conflict="pitcher_id,week_start").execute()


def get_weekly_summaries(pitcher_id: str, limit: int = 10) -> list:
    resp = (get_client().table("weekly_summaries")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .order("week_start", desc=True)
            .limit(limit)
            .execute())
    return resp.data or []


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------

def get_exercises() -> list:
    """Return the full exercise library."""
    resp = get_client().table("exercises").select("*").execute()
    return resp.data or []


def get_exercise(exercise_id: str) -> dict:
    resp = get_client().table("exercises").select("*").eq("id", exercise_id).execute()
    return resp.data[0] if resp.data else None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def get_template(template_id: str) -> dict:
    resp = get_client().table("templates").select("*").eq("id", template_id).execute()
    return resp.data[0] if resp.data else None


def get_templates() -> list:
    resp = get_client().table("templates").select("*").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# WHOOP Tokens
# ---------------------------------------------------------------------------

def get_whoop_tokens(pitcher_id: str) -> dict | None:
    """Return WHOOP tokens for a pitcher, or None if not linked."""
    resp = get_client().table("whoop_tokens").select("*").eq("pitcher_id", pitcher_id).execute()
    return resp.data[0] if resp.data else None


def upsert_whoop_tokens(pitcher_id: str, tokens: dict) -> None:
    """Insert or update WHOOP tokens for a pitcher."""
    tokens["pitcher_id"] = pitcher_id
    get_client().table("whoop_tokens").upsert(tokens, on_conflict="pitcher_id").execute()


def delete_whoop_tokens(pitcher_id: str) -> None:
    """Remove WHOOP tokens (unlink)."""
    get_client().table("whoop_tokens").delete().eq("pitcher_id", pitcher_id).execute()


def list_whoop_linked_pitchers() -> list:
    """Return pitcher_ids that have WHOOP tokens."""
    resp = get_client().table("whoop_tokens").select("pitcher_id").execute()
    return [r["pitcher_id"] for r in (resp.data or [])]


# ---------------------------------------------------------------------------
# WHOOP Daily
# ---------------------------------------------------------------------------

def get_whoop_daily(pitcher_id: str, date: str) -> dict | None:
    """Return WHOOP daily data for a specific date, or None."""
    resp = (get_client().table("whoop_daily")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .eq("date", date)
            .execute())
    return resp.data[0] if resp.data else None


def upsert_whoop_daily(pitcher_id: str, data: dict) -> None:
    """Insert or update WHOOP daily data (upsert on pitcher_id + date)."""
    data["pitcher_id"] = pitcher_id
    get_client().table("whoop_daily").upsert(data, on_conflict="pitcher_id,date").execute()


def get_whoop_daily_range(pitcher_id: str, days: int = 7) -> list:
    """Return recent WHOOP daily rows, newest first."""
    resp = (get_client().table("whoop_daily")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .order("date", desc=True)
            .limit(days)
            .execute())
    return resp.data or []


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def get_schedule(limit: int = 50) -> list:
    """Return schedule rows ordered by game_date."""
    resp = (get_client().table("schedule")
            .select("*")
            .order("game_date", desc=False)
            .limit(limit)
            .execute())
    return resp.data or []


def get_schedule_by_dates(dates: list) -> dict:
    """Return schedule rows keyed by game_date for a list of date strings."""
    if not dates:
        return {}
    resp = (get_client().table("schedule")
            .select("game_date,opponent,home_away,location,start_time,is_doubleheader")
            .in_("game_date", dates)
            .execute())
    result = {}
    for row in (resp.data or []):
        result[row["game_date"]] = row
    return result


def get_upcoming_games(from_date: str, days: int = 30) -> list:
    """Return schedule rows for the next N days from a given date."""
    from datetime import date as _date, timedelta
    end_date = (_date.fromisoformat(from_date) + timedelta(days=days)).isoformat()
    resp = (get_client().table("schedule")
            .select("game_date,opponent,home_away,location,start_time,is_doubleheader")
            .gte("game_date", from_date)
            .lte("game_date", end_date)
            .order("game_date", desc=False)
            .execute())
    return resp.data or []
