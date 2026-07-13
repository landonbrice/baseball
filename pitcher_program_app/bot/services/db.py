"""Supabase database client — all CRUD operations for pitcher data.

Provides a synchronous Supabase client (service role) used by context_manager
and any other module that needs persistent data access.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Canonical set of valid `plan_generated.source` discriminator values.
# `plan_generated` is JSONB so there's no DB-level enum; this constant is the
# single source of truth. Future sources must be added here explicitly.
VALID_PLAN_SOURCES: frozenset = frozenset({
    "python_fallback",
    "llm_enriched",
    "program_prescribed",  # written by Plan 4 daily composition pipeline
})

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
# Pitcher Training Model
# ---------------------------------------------------------------------------

def get_training_model(pitcher_id: str) -> dict:
    """Return pitcher_training_model row. Returns empty dict if none."""
    resp = get_client().table("pitcher_training_model").select("*").eq("pitcher_id", pitcher_id).execute()
    return resp.data[0] if resp.data else {}


def get_pitcher_training_model(pitcher_id: str) -> dict | None:
    """Return pitcher_training_model row, or None if missing.

    Thin wrapper around get_training_model() that returns None (not {})
    on miss — matches the contract used by feature-flag/override readers
    that need to distinguish "no row" from "row with empty fields".
    """
    row = get_training_model(pitcher_id)
    return row or None


def get_feature_flag(pitcher_id: str, key: str) -> bool:
    """Read a per-pitcher feature flag from pitcher_training_model.feature_flags.

    Returns False on missing model row, missing/None feature_flags, missing key,
    or non-truthy value. Boolean coerced via bool() — explicit False stays False.
    """
    model = get_pitcher_training_model(pitcher_id)
    if not model:
        return False
    flags = model.get("feature_flags") or {}
    return bool(flags.get(key))


def set_feature_flag(pitcher_id: str, key: str, value: bool) -> None:
    """Set a single key inside pitcher_training_model.feature_flags.

    Read-modify-write because feature_flags is JSONB — we never overwrite
    other flags by accident. Raises KeyError if the pitcher row doesn't
    exist (no auto-create — caller should bootstrap explicitly).
    """
    model = get_training_model(pitcher_id)
    if not model:
        raise KeyError(f"no pitcher_training_model row for {pitcher_id}")
    flags = dict(model.get("feature_flags") or {})
    flags[key] = bool(value)
    update_training_model_partial(pitcher_id, {"feature_flags": flags})


def upsert_training_model(pitcher_id: str, data: dict) -> None:
    """Insert or update pitcher_training_model row."""
    data["pitcher_id"] = pitcher_id
    data.pop("updated_at", None)  # Let Postgres trigger handle timestamp
    get_client().table("pitcher_training_model").upsert(data, on_conflict="pitcher_id").execute()


def update_training_model_partial(pitcher_id: str, updates: dict) -> None:
    """Partial update of pitcher_training_model fields (PATCH semantics).

    For top-level columns, merges updates into existing row.
    For JSONB fields, use upsert_training_model with the full field value.
    """
    current = get_training_model(pitcher_id)
    if not current:
        updates["pitcher_id"] = pitcher_id
        get_client().table("pitcher_training_model").insert(updates).execute()
        return
    current.update(updates)
    current.pop("updated_at", None)  # Let Postgres trigger handle timestamp
    get_client().table("pitcher_training_model").upsert(current, on_conflict="pitcher_id").execute()


# ---------------------------------------------------------------------------
# Active Flags (compatibility layer — backed by pitcher_training_model)
# ---------------------------------------------------------------------------

# Columns that map to the old active_flags shape.
_ACTIVE_FLAGS_COLUMNS = (
    "pitcher_id, current_arm_feel, current_flag_level, days_since_outing, "
    "last_outing_date, last_outing_pitches, phase, active_modifications, "
    "next_outing_days, grip_drop_reported"
)


def get_active_flags(pitcher_id: str) -> dict:
    """Return active_flags-shaped dict from pitcher_training_model.

    Compatibility wrapper — all existing callers continue to work.
    """
    resp = (get_client().table("pitcher_training_model")
            .select(_ACTIVE_FLAGS_COLUMNS)
            .eq("pitcher_id", pitcher_id)
            .execute())
    return resp.data[0] if resp.data else {}


def upsert_active_flags(pitcher_id: str, flags: dict) -> None:
    """Write active_flags-shaped dict to pitcher_training_model.

    Compatibility wrapper — filters to only active_flags columns
    to prevent accidental overwrites of new model fields.
    """
    allowed = {
        "pitcher_id", "current_arm_feel", "current_flag_level",
        "days_since_outing", "last_outing_date", "last_outing_pitches",
        "phase", "active_modifications", "next_outing_days", "grip_drop_reported",
    }
    filtered = {k: v for k, v in flags.items() if k in allowed}
    filtered["pitcher_id"] = pitcher_id
    get_client().table("pitcher_training_model").upsert(
        filtered, on_conflict="pitcher_id"
    ).execute()


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
    "bot_observations", "arm_care", "lifting", "throwing", "warmup", "mobility", "notes",
    "completed_exercises", "soreness_response", "research_sources", "team_id", "active_team_block_id",
    "rationale",  # F4 — {rationale_short, rationale_detail}
}


def upsert_daily_entry(pitcher_id: str, entry: dict) -> None:
    """Insert or update a daily entry (upsert on pitcher_id + date)."""
    row = {k: v for k, v in entry.items() if k in _DAILY_ENTRY_COLUMNS}
    row["pitcher_id"] = pitcher_id
    if not row.get("team_id"):
        pitcher = get_pitcher(pitcher_id)
        team_id = pitcher.get("team_id")
        if team_id:
            row["team_id"] = team_id
    get_client().table("daily_entries").upsert(row, on_conflict="pitcher_id,date").execute()


def write_daily_entry_with_counter_advance(entry, program_id, hold_event, event_date):
    """Upsert daily_entries + atomically advance/hold the program counter via RPC.

    NOT cross-step atomic (Supabase REST limitation): if the RPC fails after the
    upsert succeeds, manual reconciliation may be needed. v2 follow-up could push
    the entry payload into the Postgres function. program_id=None skips the RPC
    entirely (cold-start parity for pitchers without an active program).
    """
    client = get_client()
    safe = {k: v for k, v in entry.items() if k in _DAILY_ENTRY_COLUMNS}
    client.table("daily_entries").upsert(safe, on_conflict="pitcher_id,date").execute()
    if program_id is None:
        return
    client.rpc("advance_program_counter", {
        "p_program_id": program_id,
        "p_hold_event": hold_event,
        "p_event_date": event_date.isoformat(),
    }).execute()


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
    """Insert a new saved plan. Returns the inserted row.

    DEPRECATED (Plan 7 / A15): saved_plans is being retired in favor of
    `favorited_blocks`. New writes are logged for monitoring. Plan 8 will
    hard-drop the table once a quarter of zero-writes is confirmed.
    """
    logger.warning(
        "saved_plans_deprecated_write | pitcher_id=%s | plan_name=%s | "
        "future Plan 8 retirement",
        pitcher_id, plan.get("plan_name") or plan.get("name")
    )
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

def upsert_weekly_summary(pitcher_id: str, week_start: str, summary: dict,
                          structured: dict = None) -> None:
    """Upsert a weekly summary row.

    Args:
        pitcher_id: Pitcher ID
        week_start: ISO date string (Monday of week)
        summary: Dict with narrative, headline, generated_at (stored as JSONB)
        structured: Optional dict with enriched fields:
            avg_arm_feel, avg_sleep, exercise_completion_rate,
            exercises_skipped, throwing_sessions, total_throws,
            flag_distribution, movement_pattern_balance
    """
    row = {
        "pitcher_id": pitcher_id,
        "week_start": week_start,
        "summary": summary,
    }
    if structured:
        for key in ("avg_arm_feel", "avg_sleep", "exercise_completion_rate",
                     "exercises_skipped", "throwing_sessions", "total_throws",
                     "flag_distribution", "movement_pattern_balance"):
            if key in structured:
                row[key] = structured[key]
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


def save_whoop_pending_auth(state: str, pitcher_id: str, verifier: str) -> None:
    """Store PKCE state for OAuth callback (survives Railway restarts)."""
    get_client().table("whoop_pending_auth").upsert({
        "state": state,
        "pitcher_id": pitcher_id,
        "verifier": verifier,
    }, on_conflict="state").execute()


def get_whoop_pending_auth(state: str) -> dict | None:
    """Retrieve PKCE state by state token."""
    resp = get_client().table("whoop_pending_auth").select("*").eq("state", state).execute()
    return resp.data[0] if resp.data else None


def delete_whoop_pending_auth(state: str) -> None:
    """Remove PKCE state after successful exchange."""
    get_client().table("whoop_pending_auth").delete().eq("state", state).execute()


def cleanup_stale_whoop_auth(max_age_hours: int = 1) -> None:
    """Remove pending auth entries older than max_age_hours."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    get_client().table("whoop_pending_auth").delete().lt("created_at", cutoff).execute()


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
    """Return team_games rows ordered by game_date (backward-compat with schedule table)."""
    resp = (get_client().table("team_games")
            .select("*")
            .order("game_date", desc=False)
            .limit(limit)
            .execute())
    return resp.data or []


def get_schedule_by_dates(dates: list) -> dict:
    """Return team_games rows keyed by game_date for a list of date strings."""
    if not dates:
        return {}
    resp = (get_client().table("team_games")
            .select("game_date,opponent,home_away,game_time,is_doubleheader_g2")
            .in_("game_date", dates)
            .execute())
    return {row["game_date"]: row for row in (resp.data or [])}


def get_upcoming_games(from_date: str, days: int = 30) -> list:
    """Return team_games rows for the next N days from a given date."""
    from datetime import date as _date, timedelta
    end_date = (_date.fromisoformat(from_date) + timedelta(days=days)).isoformat()
    resp = (get_client().table("team_games")
            .select("game_date,opponent,home_away,game_time,is_doubleheader_g2")
            .gte("game_date", from_date)
            .lte("game_date", end_date)
            .order("game_date")
            .execute())
    return resp.data or []


# === Program templates + training programs ===

def get_program_template(template_id: str) -> Optional[dict]:
    """Load a program template by id, or None if not found."""
    resp = (
        get_client()
        .table("program_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_program_templates() -> list[dict]:
    """All program templates, ordered by id."""
    resp = (
        get_client()
        .table("program_templates")
        .select("*")
        .order("id")
        .execute()
    )
    return resp.data or []


def upsert_program_template(template: dict) -> None:
    """Insert or update a template by id."""
    get_client().table("program_templates").upsert(template, on_conflict="id").execute()


def insert_training_program(row: dict) -> int:
    """Insert a training_programs row, returning the new id."""
    resp = get_client().table("training_programs").insert(row).execute()
    return resp.data[0]["id"]


def get_training_program(program_id: int) -> Optional[dict]:
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("id", program_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_active_training_program(pitcher_id: str) -> Optional[dict]:
    """Return the pitcher's currently active program (deactivated_at IS NULL)."""
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .is_("deactivated_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_training_programs_for_pitcher(pitcher_id: str) -> list[dict]:
    """All programs for a pitcher, newest first."""
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def deactivate_training_program(program_id: int, reason: str) -> None:
    from datetime import datetime, timezone
    get_client().table("training_programs").update(
        {
            "deactivated_at": datetime.now(timezone.utc).isoformat(),
            "deactivation_reason": reason,
        }
    ).eq("id", program_id).execute()


def set_active_program_id(pitcher_id: str, program_id: Optional[int]) -> None:
    get_client().table("pitcher_training_model").update(
        {"active_program_id": program_id}
    ).eq("pitcher_id", pitcher_id).execute()


# --- team_games ---

def get_team_game(game_id: str) -> dict:
    """Return a single team_games row by game_id."""
    resp = (get_client().table("team_games")
            .select("*")
            .eq("game_id", game_id)
            .single()
            .execute())
    return resp.data or {}


def upsert_team_game(game: dict) -> dict:
    """Insert or update a team_games row."""
    resp = (get_client().table("team_games")
            .upsert(game, on_conflict="game_id")
            .execute())
    return resp.data[0] if resp.data else {}


def delete_team_game(game_id: str) -> None:
    """Delete a team_games row."""
    get_client().table("team_games").delete().eq("game_id", game_id).execute()


# --- block_library ---

def list_block_library() -> list:
    """Return all block_library rows."""
    resp = (get_client().table("block_library")
            .select("*")
            .order("name")
            .execute())
    return resp.data or []


# --- team_assigned_blocks ---

def get_active_team_blocks(team_id: str) -> list:
    """Return active team_assigned_blocks for a team."""
    resp = (get_client().table("team_assigned_blocks")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", "active")
            .execute())
    return resp.data or []


def upsert_team_block(block: dict) -> dict:
    resp = (get_client().table("team_assigned_blocks")
            .upsert(block, on_conflict="block_id")
            .execute())
    return resp.data[0] if resp.data else {}


# --- coach_suggestions ---

def get_pending_suggestions(team_id: str) -> list:
    """Return pending coach_suggestions for a team."""
    resp = (get_client().table("coach_suggestions")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute())
    return resp.data or []


def upsert_suggestion(suggestion: dict) -> dict:
    resp = (get_client().table("coach_suggestions")
            .upsert(suggestion, on_conflict="suggestion_id")
            .execute())
    return resp.data[0] if resp.data else {}


def suggestion_exists_for_today(
    pitcher_id: str | None,
    category: str,
    *,
    context_program_id: str | None = None,
    context_block_id: str | None = None,
) -> bool:
    """Plan 7 / A4 — idempotency check for the daily insight generators.

    Returns True if a coach_suggestions row with the given category exists for
    the pitcher (or team-scoped for team_program_lagging when pitcher_id is None
    and context_block_id is provided) with `created_at >= today's Chicago-tz
    midnight`. Used by health_monitor._generate_coach_insights_for_team to avoid
    re-inserting the same insight across re-runs of the 9am digest.

    Optional context_program_id / context_block_id further scope the match by
    proposed_action JSONB so multiple programs/blocks for the same pitcher
    don't dedup against each other.
    """
    from bot.config import CHICAGO_TZ
    from datetime import datetime as _dt
    now_chicago = _dt.now(CHICAGO_TZ)
    start_of_day_chicago = now_chicago.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cutoff_iso = start_of_day_chicago.isoformat()

    q = (
        get_client().table("coach_suggestions")
        .select("suggestion_id, proposed_action")
        .eq("category", category)
        .gte("created_at", cutoff_iso)
    )
    if pitcher_id is not None:
        q = q.eq("pitcher_id", pitcher_id)
    resp = q.execute()
    rows = resp.data or []
    # Today-window check: short-circuit True when a contextless caller has
    # any row, or when context_program_id/context_block_id matches one of
    # today's rows. Otherwise fall through to the Plan 8 / C1 accepted-14d
    # suppression check so a recently-accepted "new pace" still suppresses
    # the daily re-fire.
    if rows:
        if context_program_id is None and context_block_id is None:
            return True
        for row in rows:
            action = row.get("proposed_action") or {}
            if context_program_id is not None and action.get("program_id") == context_program_id:
                return True
            if context_block_id is not None and action.get("block_id") == context_block_id:
                return True
            if context_block_id is not None and action.get("block_template_id") == context_block_id:
                return True

    # Plan 8 / C1: also suppress when a matching insight was recently accepted.
    # If a coach hit "Accept new pace" on a drift insight, we don't want the
    # same insight to re-fire the next morning — gate by accepted_at >=
    # today - 14d (calendar-bounded). Same (category, pitcher_id) context
    # rules as the today-check; optional program_id / block_id narrow it
    # further when the caller specified a context.
    from datetime import timedelta as _td
    accepted_cutoff = (now_chicago - _td(days=14)).date().isoformat()
    accepted_q = (
        get_client().table("coach_suggestions")
        .select("suggestion_id, proposed_action")
        .eq("category", category)
        .eq("status", "accepted")
        .gte("accepted_at", accepted_cutoff)
    )
    if pitcher_id is not None:
        accepted_q = accepted_q.eq("pitcher_id", pitcher_id)
    accepted_resp = accepted_q.execute()
    candidates = accepted_resp.data or []
    if not candidates:
        return False

    if context_program_id is None and context_block_id is None:
        return True

    for row in candidates:
        action = row.get("proposed_action") or {}
        if context_program_id is not None and action.get("program_id") == context_program_id:
            return True
        if context_block_id is not None and action.get("block_id") == context_block_id:
            return True
        if context_block_id is not None and action.get("block_template_id") == context_block_id:
            return True
    return False


def insert_coach_suggestion(row: dict) -> dict:
    """Plan 7 / A4 — insert a new coach_suggestions row. Returns the inserted
    row (Supabase echoes the row + generated suggestion_id).

    Plain insert (not upsert) because the A4 generators are dedup-gated by
    suggestion_exists_for_today before they reach this helper. Distinct from
    upsert_suggestion, which the pre_start_nudge path uses with an explicit
    suggestion_id for re-runs.
    """
    resp = get_client().table("coach_suggestions").insert(row).execute()
    return resp.data[0] if resp.data else {}


def get_coach_suggestion(suggestion_id: str) -> dict | None:
    """Plan 8 / C1 — return a single coach_suggestions row by suggestion_id,
    or None if missing. Used by the insight action endpoint to verify
    team_id ownership before updating status.
    """
    resp = (get_client().table("coach_suggestions")
            .select("*")
            .eq("suggestion_id", suggestion_id)
            .execute())
    return resp.data[0] if resp.data else None


def update_coach_suggestion_status(
    suggestion_id: str,
    *,
    status: str,
    accepted_at: str | None = None,
) -> dict:
    """Plan 8 / C1 — update status (and optionally accepted_at) for a
    coach_suggestions row. Returns the updated row. Raises KeyError if not
    found.
    """
    payload: dict = {"status": status}
    if accepted_at is not None:
        payload["accepted_at"] = accepted_at
    resp = (get_client().table("coach_suggestions")
            .update(payload)
            .eq("suggestion_id", suggestion_id)
            .execute())
    if not resp.data:
        raise KeyError(f"coach_suggestion not found: {suggestion_id}")
    return resp.data[0]


def list_team_assigned_blocks(team_id: str, status: str | None = None) -> list[dict]:
    """Plan 7 / A4 — list team_assigned_blocks for a team, optionally
    filtered by status. Mirrors get_active_team_blocks but exposes the status
    knob so the insight generator can scan any subset (active / archived).
    """
    q = get_client().table("team_assigned_blocks").select("*").eq("team_id", team_id)
    if status:
        q = q.eq("status", status)
    resp = q.execute()
    return resp.data or []


def list_member_programs_for_team_block(team_assigned_block: dict) -> list[dict]:
    """Plan 7 / A4 — return active programs across the team whose
    parent_template_id matches the team-assigned block's block_template_id.

    Programs are not formally FK'd to team_assigned_blocks; the link is by
    template ID convention. Selects the summary projection
    (no generated_schedule_json) — the team completion generator falls back to
    a typical-program-length default when the days array isn't present.
    """
    template_id = team_assigned_block.get("block_template_id")
    team_id = team_assigned_block.get("team_id")
    if not template_id or not team_id:
        return []

    client = get_client()
    pitchers_resp = (
        client.table("pitchers")
        .select("pitcher_id")
        .eq("team_id", team_id)
        .execute()
    )
    pitcher_ids = [r["pitcher_id"] for r in (pitchers_resp.data or []) if r.get("pitcher_id")]
    if not pitcher_ids:
        return []

    prog_resp = (
        client.table("programs")
        .select(_PROGRAM_SUMMARY_COLUMNS)
        .eq("parent_template_id", template_id)
        .eq("status", "active")
        .in_("pitcher_id", pitcher_ids)
        .execute()
    )
    return prog_resp.data or []


# --- training_phase_blocks ---

def get_phase_blocks(team_id: str) -> list:
    """Return training_phase_blocks for a team, ordered by start_date."""
    resp = (get_client().table("training_phase_blocks")
            .select("*")
            .eq("team_id", team_id)
            .order("start_date")
            .execute())
    return resp.data or []


def get_current_phase(team_id: str, today_str: str) -> dict | None:
    """Return the phase block containing today's date."""
    resp = (get_client().table("training_phase_blocks")
            .select("*")
            .eq("team_id", team_id)
            .lte("start_date", today_str)
            .gte("end_date", today_str)
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None


def upsert_phase_block(block: dict) -> dict:
    resp = (get_client().table("training_phase_blocks")
            .upsert(block, on_conflict="phase_block_id")
            .execute())
    return resp.data[0] if resp.data else {}


def delete_phase_block(phase_block_id: str) -> None:
    get_client().table("training_phase_blocks").delete().eq("phase_block_id", phase_block_id).execute()


# --- teams ---

def get_team(team_id: str) -> dict | None:
    """Look up a team row by its primary key."""
    resp = (
        get_client().table("teams")
        .select("*")
        .eq("team_id", team_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


# --- programs (new spec-defined `programs` table; coexists with legacy training_programs) ---

def get_active_program(pitcher_id: str, domain: str) -> dict | None:
    """Return the single row from `programs` where status='active' for (pitcher_id, domain), or None.

    The partial unique index idx_programs_one_active_per_domain guarantees at most one such row.
    """
    if domain not in ("throwing", "lifting"):
        raise ValueError(f"domain must be 'throwing' or 'lifting', got {domain!r}")
    resp = (
        get_client()
        .table("programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .eq("domain", domain)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def get_block_library_row(template_id: str) -> dict | None:
    """Fetch a single block_library row by its block_template_id (TEXT PK)."""
    resp = (
        get_client()
        .table("block_library")
        .select("*")
        .eq("block_template_id", template_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


# ---------------- Research docs (Plan 8 / C3) ----------------


def list_research_docs() -> list[dict]:
    """Return all research docs metadata read from disk.

    Research docs are git-checked-in markdown files in
    `data/knowledge/research/` with YAML frontmatter — NOT Supabase rows.
    Reuses the resolver's existing on-disk loader (`_load_index`) so there
    is one definition of "what is a doc" across the codebase.

    Used by Plan 8 / C3 to power the coach-app "Edit research" modal —
    coaches pick from this list to populate `block_library.research_doc_ids`.

    Returns a list of:
      {id, title, summary, applies_to, priority}
    Docs missing an `id` are dropped (warning is already logged inside
    `_load_index`).
    """
    from bot.services.research_resolver import _load_index

    index = _load_index()
    out: list[dict] = []
    for doc_id, (fm, _body) in index.items():
        if not doc_id:
            continue
        out.append({
            "id": doc_id,
            "title": fm.get("title") or doc_id,
            "summary": fm.get("summary") or "",
            "applies_to": fm.get("applies_to") or [],
            "priority": fm.get("priority") or "standard",
        })
    # Stable order by title for deterministic UI rendering.
    out.sort(key=lambda d: (d.get("title") or "").lower())
    return out


def update_template_research_doc_ids(template_id: str, doc_ids: list[str]) -> dict:
    """Set `block_library.research_doc_ids` for a template.

    Used by Plan 8 / C3 — coach-authored attach-existing flow.
    Returns the updated row. Raises `KeyError` if no row matches the
    given `block_template_id` so the caller can translate to a 404.

    Note: Supabase's REST `update` returns an empty `data` array when no
    rows match (it does NOT raise) — `block_template_id` is the TEXT PK
    on `block_library`, so an empty array unambiguously means "not found".
    """
    resp = (
        get_client()
        .table("block_library")
        .update({"research_doc_ids": doc_ids})
        .eq("block_template_id", template_id)
        .execute()
    )
    if not resp.data:
        raise KeyError(f"template not found: {template_id}")
    return resp.data[0]


# Summary columns for the canonical /api/programs/templates list endpoint
# (Plan 7 / A12). Skips heavy template_body JSON — clients use this list for
# filterable browse cards; full body is fetched on selection elsewhere.
_TEMPLATE_SUMMARY_COLUMNS = (
    "block_template_id,name,description,domain,goal_tags,compatible_phases,"
    "duration_range_weeks,implied_phase,research_doc_ids"
)


def list_block_library_templates(
    domain: Optional[str] = None,
    phase: Optional[str] = None,
) -> list[dict]:
    """Return block_library rows with Plan-1 schema fields populated.

    Skips legacy stub rows (`domain IS NULL`). Optional filters:
    - `domain` ('throwing' | 'lifting') applied at the DB layer.
    - `phase` (e.g. 'off_season') applied in Python because PostgREST
      doesn't expose a clean array-contains-text filter for text[] columns.

    Returns `[]` when no rows match.
    """
    q = (
        get_client()
        .table("block_library")
        .select(_TEMPLATE_SUMMARY_COLUMNS)
        .not_.is_("domain", "null")
    )
    if domain:
        q = q.eq("domain", domain)
    resp = q.order("name").execute()
    rows = resp.data or []
    if phase:
        rows = [r for r in rows if phase in (r.get("compatible_phases") or [])]
    return rows


# ---------------- Programs (spec v1) ----------------

_PROGRAM_COLUMNS = frozenset({
    "pitcher_id", "parent_template_id", "domain", "tuned_spec_json",
    "generated_schedule_json", "start_date", "nominal_end_date",
    "current_day_index", "held_days_count", "status", "created_by",
    "created_by_role", "activated_at", "archived_at", "archive_reason",
    # Migration 034 — Program Engine v1 additions
    "knowledge_version", "generation_provenance", "engine_version",
})


def create_program(row: dict) -> str:
    """Insert a programs row, return the new program_id.

    Whitelists keys to `_PROGRAM_COLUMNS` so unknown fields (e.g. callers
    accidentally passing `program_id`) don't break the insert.
    """
    payload = {k: v for k, v in row.items() if k in _PROGRAM_COLUMNS}
    resp = get_client().table("programs").insert(payload).execute()
    return (resp.data or [{}])[0].get("program_id")


def insert_program_generation_failure(
    *,
    pitcher_id: str,
    attempt_n: int,
    status: str,
    violations: list | None = None,
    reason: str | None = None,
) -> None:
    """Best-effort write to `program_generation_failures` for orchestrator
    observability. Called by `program_engine.orchestrator.author_validate_persist`
    on every attempt (valid/repaired/reject/generation_failure)."""
    payload = {
        "pitcher_id": pitcher_id,
        "attempt_number": attempt_n,
        "validation_failure_kind": status,
        "llm_response": {"violations": violations, "reason": reason} if (violations or reason) else None,
    }
    try:
        get_client().table("program_generation_failures").insert(payload).execute()
    except Exception:
        # observability write must never break authoring
        pass


def get_program(program_id: str) -> dict | None:
    resp = (
        get_client()
        .table("programs")
        .select("*")
        .eq("program_id", program_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def update_program_status(program_id: str, status: str, **extras) -> None:
    """Patch a programs row's status (and optional extra fields like activated_at, archived_at, archive_reason)."""
    valid = {"draft", "active", "archived", "error"}
    if status not in valid:
        raise ValueError(f"status must be one of {valid}, got {status!r}")
    payload = {"status": status, **extras}
    get_client().table("programs").update(payload).eq("program_id", program_id).execute()


def update_program_schedule(program_id: str, new_schedule: dict,
                             trigger_type: str = "anchor_recompute") -> None:
    """Persist a recomputed schedule and audit it.

    Two writes (not cross-step atomic; v2 will move to a single RPC):
    1. UPDATE programs SET generated_schedule_json = new_schedule
    2. INSERT INTO program_schedule_revisions (program_id, trigger_type,
       old_schedule, new_schedule)

    Reads the current row first to capture `old_schedule` for the revision.
    """
    client = get_client()
    existing = (
        client.table("programs")
        .select("generated_schedule_json")
        .eq("program_id", program_id)
        .limit(1)
        .execute()
    )
    old_schedule = ((existing.data or [{}])[0] or {}).get("generated_schedule_json") or {}

    client.table("programs").update(
        {"generated_schedule_json": new_schedule}
    ).eq("program_id", program_id).execute()

    client.table("program_schedule_revisions").insert({
        "program_id": program_id,
        "trigger_type": trigger_type,
        "old_schedule": old_schedule,
        "new_schedule": new_schedule,
    }).execute()


def list_programs_for_pitcher(pitcher_id: str, status: str | None = None) -> list[dict]:
    q = get_client().table("programs").select("*").eq("pitcher_id", pitcher_id)
    if status:
        q = q.eq("status", status)
    resp = q.order("created_at", desc=True).execute()
    return resp.data or []


# All columns except `generated_schedule_json` (the big JSONB body, ~10-50KB/row).
# tuned_spec_json is kept — it holds the Socratic answers, ~1-3KB, useful for cards.
_PROGRAM_SUMMARY_COLUMNS = (
    "program_id,pitcher_id,parent_template_id,domain,tuned_spec_json,"
    "start_date,nominal_end_date,current_day_index,held_days_count,status,"
    "created_by,created_by_role,approval_required,"
    "created_at,activated_at,archived_at,archive_reason"
)


def list_programs_for_pitcher_summary(
    pitcher_id: str,
    status: str | None = None,
    *,
    order_by: str = "created_at",
) -> list[dict]:
    """List programs without the heavy `generated_schedule_json` column.

    For Plan 6 / A3 list endpoints — cards only need scalars + tuned_spec.
    `order_by` accepts 'created_at' or 'archived_at' (history uses the latter).
    """
    if order_by not in ("created_at", "archived_at"):
        raise ValueError(f"order_by must be 'created_at' or 'archived_at', got {order_by!r}")
    q = (
        get_client()
        .table("programs")
        .select(_PROGRAM_SUMMARY_COLUMNS)
        .eq("pitcher_id", pitcher_id)
    )
    if status:
        q = q.eq("status", status)
    resp = q.order(order_by, desc=True).execute()
    return resp.data or []


def list_completed_session_drafts_for_pitcher(pitcher_id: str) -> list[dict]:
    """Return draft programs whose generating builder_session.status='completed'.

    Per Plan 6 D14: the coach sees finalized drafts only; in-flight Socratic
    sessions are private to the pitcher until they hit Save/Activate. Used by
    GET /api/coach/pitcher/{id}/drafts (Plan 7 / A3-coach).
    """
    client = get_client()
    # Two-step: pull completed session IDs first, then filter programs by them.
    sess_resp = (
        client.table("program_builder_sessions")
        .select("generated_program_id")
        .eq("pitcher_id", pitcher_id)
        .eq("status", "completed")
        .execute()
    )
    program_ids = [
        r["generated_program_id"]
        for r in (sess_resp.data or [])
        if r.get("generated_program_id")
    ]
    if not program_ids:
        return []
    prog_resp = (
        client.table("programs")
        .select(_PROGRAM_SUMMARY_COLUMNS)
        .eq("pitcher_id", pitcher_id)
        .eq("status", "draft")
        .in_("program_id", program_ids)
        .order("created_at", desc=True)
        .execute()
    )
    return prog_resp.data or []


# ---------------- Program Hold Events (Plan 6 / B2 read-side) ----------------

def list_program_holds_for_date(pitcher_id: str, event_date_iso: str) -> list[str]:
    """Return program_ids that were held for the pitcher on the given date.

    Used by GET /api/programs/holds-today to surface the "Program paused today"
    inline note on Home (B2). Empty list if no holds exist.

    `program_hold_events` has no `pitcher_id` column — it keys off `program_id`.
    Two-step query: pull the pitcher's program_ids first, then filter
    `program_hold_events` by `program_id IN (...)` AND `hold_date = event_date`.
    Early-returns `[]` when the pitcher has no programs so we don't issue a
    `.in_([])` against PostgREST (implementation-defined behavior).
    """
    client = get_client()
    prog_resp = (
        client.table("programs")
        .select("program_id")
        .eq("pitcher_id", pitcher_id)
        .execute()
    )
    program_ids = [r["program_id"] for r in (prog_resp.data or [])
                   if r.get("program_id")]
    if not program_ids:
        return []
    holds_resp = (
        client.table("program_hold_events")
        .select("program_id")
        .in_("program_id", program_ids)
        .eq("hold_date", event_date_iso)
        .execute()
    )
    rows = holds_resp.data or []
    return [r.get("program_id") for r in rows if r.get("program_id")]


def list_program_holds_for_pitcher(pitcher_id: str, days: int = 30) -> list[dict]:
    """Return program_hold_events rows for the pitcher in the last `days` days.

    program_hold_events has no pitcher_id column — joins through programs.
    Used by GET /api/coach/pitcher/{id}/program-holds (Plan 7 / C2).

    Each row: {hold_event_id, program_id, hold_date, triage_result, reason_code,
    created_at}. Ordered by hold_date DESC.
    """
    if days < 0:
        days = 30
    client = get_client()
    # Two-step: programs for the pitcher → hold events for those programs.
    prog_resp = (
        client.table("programs")
        .select("program_id")
        .eq("pitcher_id", pitcher_id)
        .execute()
    )
    program_ids = [r["program_id"] for r in (prog_resp.data or []) if r.get("program_id")]
    if not program_ids:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    resp = (
        client.table("program_hold_events")
        .select("hold_event_id,program_id,hold_date,triage_result,reason_code,created_at")
        .in_("program_id", program_ids)
        .gte("hold_date", cutoff)
        .order("hold_date", desc=True)
        .execute()
    )
    return resp.data or []


# ---------------- Recent player-built programs (Plan 7 / C3) ----------------

# Summary columns + the pitcher's display name for the team-wide
# `/api/coach/programs/recent-player-built` strip. The pitchers join is done
# in a second hop because PostgREST embeds add a `pitchers` object key that
# inflates the payload; a name-only lookup keeps the row shape flat.
_RECENT_PLAYER_BUILT_COLUMNS = (
    "program_id,pitcher_id,parent_template_id,domain,status,"
    "current_day_index,held_days_count,created_by,created_by_role,"
    "created_at,activated_at,archived_at"
)


def list_recent_player_built_programs(
    team_id: str,
    limit: int = 20,
) -> list[dict]:
    """Return the most recent N programs across a team, newest-first.

    Used by the coach Team Programs page (Plan 7 / C3) to render the
    "Recent player-built programs" roster strip. Each row carries the
    pitcher's display name (`pitcher_name`) joined from `pitchers` so the
    UI can render `{pitcher_name} · {domain} · {template_id} · {status}`
    without a second round-trip.

    Implementation: two-step join. (1) Pull team pitcher_ids from
    `pitchers`. (2) Select recent programs WHERE pitcher_id IN (those ids)
    ordered by created_at DESC limit N. (3) Backfill pitcher_name from the
    map built in step 1. Returns `[]` when the team has no pitchers.

    v1 does NOT filter on a `coach_built` flag — every program for the
    team surfaces here. The strip is a roster overview, not a feed.
    """
    if limit <= 0:
        return []
    client = get_client()
    pitchers_resp = (
        client.table("pitchers")
        .select("pitcher_id,name")
        .eq("team_id", team_id)
        .execute()
    )
    pitcher_rows = pitchers_resp.data or []
    if not pitcher_rows:
        return []
    name_by_id = {
        r.get("pitcher_id"): r.get("name") or r.get("pitcher_id")
        for r in pitcher_rows
        if r.get("pitcher_id")
    }
    pitcher_ids = list(name_by_id.keys())

    prog_resp = (
        client.table("programs")
        .select(_RECENT_PLAYER_BUILT_COLUMNS)
        .in_("pitcher_id", pitcher_ids)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = prog_resp.data or []
    for row in rows:
        pid = row.get("pitcher_id")
        row["pitcher_name"] = name_by_id.get(pid) or pid
    return rows


# ---------------- Coach Phase Overrides (Plan 7 / C2 write-side) ----------------

# Free-text phase strings. Validated only via this pattern at the API layer;
# the DB columns are unconstrained TEXT (migration 023). v1 doesn't pin to a
# closed vocabulary because the codebase already uses free-text phase names
# (`team_scope.get_team_phase`, training_phase_blocks rows, etc.).
_PHASE_PATTERN = r"^[a-zA-Z0-9_\- ]{1,60}$"


def update_coach_phase_overrides(
    pitcher_id: str,
    *,
    throwing_phase: str | None = None,
    lifting_phase: str | None = None,
) -> dict:
    """Patch coach_{throwing,lifting}_phase_override on pitcher_training_model.

    Only writes the keys that were explicitly provided (i.e. `None` means
    "don't touch this column"). To CLEAR an override, callers pass the
    empty string; this method maps "" → SQL NULL.

    Returns the canonical envelope used by the API:
      {"throwing_phase": str|None, "lifting_phase": str|None}
    representing the post-write state of both columns.
    """
    updates: dict = {}
    if throwing_phase is not None:
        updates["coach_throwing_phase_override"] = throwing_phase or None
    if lifting_phase is not None:
        updates["coach_lifting_phase_override"] = lifting_phase or None

    if updates:
        # update_training_model_partial inserts a row if none exists.
        update_training_model_partial(pitcher_id, updates)

    # Re-read so we always return the canonical envelope (including unchanged side).
    model = get_pitcher_training_model(pitcher_id) or {}
    return {
        "throwing_phase": model.get("coach_throwing_phase_override"),
        "lifting_phase": model.get("coach_lifting_phase_override"),
    }


def insert_coach_action(row: dict) -> dict:
    """Insert a coach_actions audit row. Returns the inserted row.

    Schema (migration 007_coach_actions.sql):
      id (bigserial), coach_id (uuid FK), pitcher_id (text FK),
      action_type (text NOT NULL), message_text, telegram_message_id,
      metadata (jsonb), created_at.

    Note: no team_id column exists on coach_actions. Callers that want to
    persist team scope should fold it into `metadata`.
    """
    resp = get_client().table("coach_actions").insert(row).execute()
    return (resp.data or [{}])[0]


# ---------------- Coach-visible Override Events (Plan 6 / A5) ----------------

def insert_override_event(
    pitcher_id: str,
    program_id: str | None,
    event_kind: str,
    event_date: str,
    details: dict | None = None,
) -> dict:
    """Insert a row into coach_visible_override_events. Returns the inserted row.

    `event_date` is an ISO date string (YYYY-MM-DD). `details` is opaque JSON for
    surfacing context to coaches later.
    """
    row = {
        "pitcher_id": pitcher_id,
        "program_id": program_id,
        "event_kind": event_kind,
        "event_date": event_date,
        "details": details or {},
    }
    resp = get_client().table("coach_visible_override_events").insert(row).execute()
    return (resp.data or [{}])[0]


def get_pitcher_scheduled_throws(pitcher_id: str) -> list[dict]:
    """Read `current_week_state.scheduled_throws` for a pitcher; returns [] if absent."""
    resp = (
        get_client()
        .table("pitcher_training_model")
        .select("current_week_state")
        .eq("pitcher_id", pitcher_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return []
    state = rows[0].get("current_week_state") or {}
    return state.get("scheduled_throws") or []


# ---------------- Favorited Blocks (Plan 6 / A2) ----------------

def insert_favorited_block(row: dict) -> dict:
    """Insert a new favorited_blocks row. Returns the inserted row (with favorite_id)."""
    resp = get_client().table("favorited_blocks").insert(row).execute()
    return (resp.data or [{}])[0]


def list_favorited_blocks(pitcher_id: str, block_type: str | None = None) -> list[dict]:
    """List favorited blocks for a pitcher, newest first. Optional block_type filter."""
    q = get_client().table("favorited_blocks").select("*").eq("pitcher_id", pitcher_id)
    if block_type:
        q = q.eq("block_type", block_type)
    resp = q.order("favorited_at", desc=True).execute()
    return resp.data or []


def get_favorited_block(favorite_id: str) -> dict | None:
    """Fetch a single favorite row by id (ownership check is the caller's job)."""
    resp = (
        get_client()
        .table("favorited_blocks")
        .select("*")
        .eq("favorite_id", favorite_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def delete_favorited_block(favorite_id: str) -> None:
    """Delete by favorite_id. Caller is responsible for ownership check."""
    get_client().table("favorited_blocks").delete().eq("favorite_id", favorite_id).execute()


# ---------------- Builder Sessions (spec v1) ----------------

def create_builder_session(row: dict) -> str:
    resp = get_client().table("program_builder_sessions").insert(row).execute()
    return (resp.data or [{}])[0].get("session_id")


def update_builder_session(session_id: str, patch: dict) -> None:
    get_client().table("program_builder_sessions").update(patch).eq("session_id", session_id).execute()


def get_builder_session(session_id: str) -> dict | None:
    resp = (
        get_client()
        .table("program_builder_sessions")
        .select("*")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


# ---------------- Generation Failures ----------------

def record_generation_failure(session_id: str | None, attempt_number: int,
                               validation_failure_kind: str, llm_response: dict | None = None) -> None:
    get_client().table("program_generation_failures").insert({
        "session_id": session_id,
        "attempt_number": attempt_number,
        "validation_failure_kind": validation_failure_kind,
        "llm_response": llm_response,
    }).execute()


# --- coaches ---

def get_coach_by_supabase_id(supabase_user_id: str) -> dict | None:
    """Look up coach by Supabase Auth user ID."""
    resp = (get_client().table("coaches")
            .select("*")
            .eq("supabase_user_id", supabase_user_id)
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None


# --- ui_fallback_log (D9, D13, D14) ---

def insert_ui_fallback_log(exercise_id: str, surface: str, component: str = None, pitcher_id: str = None) -> None:
    """Record a UI fallback event (exercise name missing on render)."""
    row = {"exercise_id": exercise_id, "surface": surface}
    if component:
        row["component"] = component
    if pitcher_id:
        row["pitcher_id"] = pitcher_id
    get_client().table("ui_fallback_log").insert(row).execute()


def count_recent_ui_fallback(exercise_id: str, hours: int = 24) -> int:
    """Return count of rows for this exercise_id within the last N hours (D13).

    Used post-insert so the caller can gate admin DMs on count == 1
    (first event in window) to close the pre-insert race (D22).
    """
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        get_client().table("ui_fallback_log")
        .select("id", count="exact")
        .eq("exercise_id", exercise_id)
        .gte("logged_at", cutoff)
        .execute()
    )
    return resp.count or 0


def prune_ui_fallback_log(older_than_days: int = 30) -> int:
    """Delete rows older than N days (D14). Returns number deleted."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    resp = (
        get_client().table("ui_fallback_log")
        .delete()
        .lt("logged_at", cutoff)
        .execute()
    )
    return len(resp.data or [])
