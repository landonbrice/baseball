"""Read/write pitcher profile, context, and log data — Supabase-backed.

All function signatures are preserved from the filesystem version so that
existing callers (handlers, services, API routes) need zero changes.

Fallback: if SUPABASE_URL is not set, falls back to JSON files (read-only
during transition). Set USE_JSON_FALLBACK=true to force filesystem mode.
"""

import json
import logging
import os
from datetime import datetime

from bot.config import PITCHERS_DIR, CHICAGO_TZ

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

_USE_SUPABASE = bool(os.environ.get("SUPABASE_URL"))
_FORCE_JSON = os.environ.get("USE_JSON_FALLBACK", "").lower() == "true"

if _USE_SUPABASE and not _FORCE_JSON:
    from bot.services import db as _db
    logger.info("context_manager: using Supabase backend")
else:
    _db = None
    logger.info("context_manager: using JSON filesystem backend (fallback)")


def _using_supabase() -> bool:
    return _db is not None


# ---------------------------------------------------------------------------
# Helpers — reconstruct profile dict from Supabase rows
# ---------------------------------------------------------------------------

def _profile_from_row(row: dict) -> dict:
    """Convert a pitchers table row back into the profile.json shape
    that all existing code expects."""
    profile = {
        "pitcher_id": row["pitcher_id"],
        "telegram_id": row.get("telegram_id"),
        "telegram_username": row.get("telegram_username"),
        "name": row["name"],
        "role": row["role"],
        "rotation_length": row.get("rotation_length"),
        "throws": row.get("throws"),
        "year": row.get("year"),
        "physical_profile": row.get("physical_profile") or {},
        "pitching_profile": row.get("pitching_profile") or {},
        "current_training": row.get("current_training") or {},
        "goals": row.get("goals") or {},
        "preferences": row.get("preferences") or {},
        "biometric_integration": row.get("biometric_integration") or {},
    }

    # Attach injury_history
    injuries = _db.get_injury_history(row["pitcher_id"])
    profile["injury_history"] = injuries

    # Attach active_flags
    flags = _db.get_active_flags(row["pitcher_id"])
    # Remove the pitcher_id and updated_at keys that the table adds
    flags.pop("pitcher_id", None)
    flags.pop("updated_at", None)
    profile["active_flags"] = flags

    return profile


def _log_from_entries(pitcher_id: str, entries: list) -> dict:
    """Reconstruct the daily_log.json shape from Supabase rows."""
    # Clean up DB-only fields
    cleaned = []
    for e in entries:
        entry = dict(e)
        entry.pop("id", None)
        entry.pop("pitcher_id", None)
        entry.pop("created_at", None)
        cleaned.append(entry)
    # Sort oldest first (DB returns newest first)
    cleaned.sort(key=lambda e: e.get("date", ""))
    return {"pitcher_id": pitcher_id, "entries": cleaned}


# ---------------------------------------------------------------------------
# JSON filesystem fallback (original implementation)
# ---------------------------------------------------------------------------

def _json_get_pitcher_dir(pitcher_id: str) -> str:
    return os.path.join(PITCHERS_DIR, pitcher_id)


def _json_load_profile(pitcher_id: str) -> dict:
    path = os.path.join(_json_get_pitcher_dir(pitcher_id), "profile.json")
    with open(path, "r") as f:
        return json.load(f)


def _json_save_profile(pitcher_id: str, profile: dict) -> None:
    path = os.path.join(_json_get_pitcher_dir(pitcher_id), "profile.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)


def _json_load_log(pitcher_id: str) -> dict:
    path = os.path.join(_json_get_pitcher_dir(pitcher_id), "daily_log.json")
    if not os.path.exists(path):
        return {"pitcher_id": pitcher_id, "entries": []}
    with open(path, "r") as f:
        return json.load(f)


def _json_save_log(pitcher_id: str, log: dict) -> None:
    path = os.path.join(_json_get_pitcher_dir(pitcher_id), "daily_log.json")
    with open(path, "w") as f:
        json.dump(log, f, indent=2)


def _json_load_saved_plans(pitcher_id: str) -> list:
    path = os.path.join(_json_get_pitcher_dir(pitcher_id), "saved_plans.json")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Public API — same signatures as before
# ---------------------------------------------------------------------------

def get_pitcher_dir(pitcher_id: str) -> str:
    """Return the directory for a pitcher's files (filesystem path).
    Still needed for some edge cases (e.g. saved_plans.json direct writes in routes.py).
    """
    return os.path.join(PITCHERS_DIR, pitcher_id)


def load_profile(pitcher_id: str) -> dict:
    """Load a pitcher's profile."""
    if _using_supabase():
        try:
            row = _db.get_pitcher(pitcher_id)
            return _profile_from_row(row)
        except KeyError:
            raise FileNotFoundError(f"Pitcher not found: {pitcher_id}")
    return _json_load_profile(pitcher_id)


def save_profile(pitcher_id: str, profile: dict) -> None:
    """Save a pitcher's profile."""
    if _using_supabase():
        updates = {
            "name": profile.get("name"),
            "role": profile.get("role"),
            "rotation_length": profile.get("rotation_length"),
            "throws": profile.get("throws"),
            "year": profile.get("year"),
            "physical_profile": profile.get("physical_profile", {}),
            "pitching_profile": profile.get("pitching_profile", {}),
            "current_training": profile.get("current_training", {}),
            "goals": profile.get("goals", {}),
            "preferences": profile.get("preferences", {}),
            "biometric_integration": profile.get("biometric_integration", {}),
        }
        # Filter out None values
        updates = {k: v for k, v in updates.items() if v is not None}
        _db.update_pitcher(pitcher_id, updates)

        # Update active_flags if present
        if "active_flags" in profile:
            flags = dict(profile["active_flags"])
            _db.upsert_active_flags(pitcher_id, flags)
        return
    _json_save_profile(pitcher_id, profile)


def load_context(pitcher_id: str) -> str:
    """Load pitcher context as a text string for LLM prompts.

    Supabase version: builds context from recent chat messages + active flags
    instead of maintaining a context.md file.
    """
    if _using_supabase():
        try:
            profile = load_profile(pitcher_id)
        except FileNotFoundError:
            return ""

        flags = profile.get("active_flags", {})
        injuries = profile.get("injury_history", [])

        # Build persistent facts
        injury_str = "; ".join(
            f"{i.get('area', '')} — {i.get('description', '')}"
            for i in injuries
        ) if injuries else "none"
        mods = flags.get("active_modifications", [])
        mods_str = ", ".join(mods) if mods else "none"

        lines = [
            "## Persistent facts",
            f"- Role: {profile.get('role', 'starter')}, "
            f"{profile.get('rotation_length', 7)}-day rotation, "
            f"throws {profile.get('throws', 'R')}",
            f"- Injury history: {injury_str}",
            f"- Active program modifications: {mods_str}",
            "",
            "## Current Status",
            f"- Arm Feel: {flags.get('current_arm_feel', 'N/A')}/5",
            f"- Flag Level: {(flags.get('current_flag_level') or 'unknown').upper()}",
            f"- Days Since Outing: {flags.get('days_since_outing', 'N/A')}",
        ]
        if flags.get("last_outing_date"):
            lines.append(f"- Last Outing: {flags['last_outing_date']} "
                         f"({flags.get('last_outing_pitches', '?')} pitches)")
        if flags.get("phase"):
            lines.append(f"- Phase: {flags['phase'].replace('_', ' ')}")

        # Recent interactions from chat_messages
        messages = _db.get_chat_history(pitcher_id, limit=15)
        if messages:
            lines.append("")
            lines.append("## Recent interactions")
            for msg in messages:
                ts = msg.get("created_at", "")[:16].replace("T", " ")
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                lines.append(f"- [{ts}] ({role}) {content}")

        return "\n".join(lines)

    # Filesystem fallback
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


def append_context(pitcher_id: str, update_type: str, content: str) -> None:
    """Record an interaction. Supabase: inserts a chat_message.
    Filesystem: appends to context.md."""
    if _using_supabase():
        _db.insert_chat_message(
            pitcher_id=pitcher_id,
            source="telegram",
            role="system",
            content=content,
            metadata={"update_type": update_type},
        )
        return

    # Filesystem fallback (original logic)
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")
    timestamp = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] ({update_type}) {content}\n"
    with open(path, "a") as f:
        f.write(entry)


def load_log(pitcher_id: str) -> dict:
    """Load a pitcher's daily log."""
    if _using_supabase():
        entries = _db.get_daily_entries(pitcher_id, limit=60)
        return _log_from_entries(pitcher_id, entries)
    return _json_load_log(pitcher_id)


def save_log(pitcher_id: str, log: dict) -> None:
    """Save a pitcher's daily log."""
    if _using_supabase():
        for entry in log.get("entries", []):
            if not entry.get("date"):
                continue
            row = dict(entry)
            row.pop("id", None)
            row.pop("created_at", None)
            _db.upsert_daily_entry(pitcher_id, row)
        return
    _json_save_log(pitcher_id, log)


def append_log_entry(pitcher_id: str, entry: dict) -> None:
    """Append a new entry to a pitcher's daily log."""
    if _using_supabase():
        if not entry.get("date"):
            entry["date"] = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
        row = dict(entry)
        row.pop("id", None)
        row.pop("created_at", None)
        _db.upsert_daily_entry(pitcher_id, row)

        # Summarize old entries (> 7 training days)
        all_entries = _db.get_daily_entries(pitcher_id, limit=60)
        training_entries = [e for e in all_entries if e.get("pre_training")]
        if len(training_entries) > 7:
            to_summarize = training_entries[7:]  # oldest beyond 7 (entries are newest-first)
            for old in to_summarize:
                summary_text = _summarize_entry(old)
                week_start = old["date"][:10]  # rough grouping
                _db.upsert_weekly_summary(pitcher_id, week_start, {"summary": summary_text})
        return

    # Filesystem fallback
    log = _json_load_log(pitcher_id)
    log["entries"].append(entry)

    training_entries = [e for e in log["entries"] if e.get("pre_training")]
    if len(training_entries) > 7:
        to_summarize = training_entries[:-7]
        for old in to_summarize:
            summary_text = _summarize_entry(old)
            profile = _json_load_profile(pitcher_id)
            if "weekly_summaries" not in profile:
                profile["weekly_summaries"] = []
            profile["weekly_summaries"].append(summary_text)
            _json_save_profile(pitcher_id, profile)

        dates_to_remove = {e["date"] for e in to_summarize}
        log["entries"] = [e for e in log["entries"] if e.get("date") not in dates_to_remove]

    _json_save_log(pitcher_id, log)


def _summarize_entry(entry: dict) -> str:
    """Distill a log entry into a 1-line summary for long-term memory."""
    pt = entry.get("pre_training", {}) or {}
    date = entry.get("date", "?")
    arm = pt.get("arm_feel", "?")
    sleep = pt.get("sleep_hours", "?")
    flag = (pt.get("flag_level") or "?").upper()

    parts = [f"{date}: Arm {arm}/5, sleep {sleep}h, {flag}"]

    lifting = entry.get("lifting", {}) or {}
    if lifting and lifting.get("intent"):
        parts.append(lifting["intent"])
    elif lifting and lifting.get("exercises"):
        names = [ex.get("name", "") for ex in lifting["exercises"][:3]]
        parts.append(f"Lift: {', '.join(names)}")

    throwing = entry.get("throwing", {}) or {}
    if throwing and throwing.get("type", "none") != "none":
        parts.append(f"Threw: {throwing['type']}")

    if entry.get("skip_notes"):
        parts.append(f"Skipped: {entry['skip_notes']}")

    if entry.get("outing"):
        o = entry["outing"]
        parts.append(f"OUTING: {o.get('pitch_count', '?')}pc, post-feel {o.get('post_arm_feel', '?')}/5")

    return ". ".join(parts)


def get_recent_entries(pitcher_id: str, n: int = 5) -> list:
    """Return the last n log entries for a pitcher."""
    if _using_supabase():
        entries = _db.get_daily_entries(pitcher_id, limit=n)
        # Clean and return oldest-first
        cleaned = []
        for e in entries:
            entry = dict(e)
            entry.pop("id", None)
            entry.pop("pitcher_id", None)
            entry.pop("created_at", None)
            cleaned.append(entry)
        cleaned.reverse()
        return cleaned
    log = _json_load_log(pitcher_id)
    return log["entries"][-n:]


def update_active_flags(pitcher_id: str, updates: dict) -> None:
    """Partial update of active_flags."""
    if _using_supabase():
        # Read current, merge, write back
        current = _db.get_active_flags(pitcher_id)
        current.update(updates)
        current.pop("updated_at", None)
        _db.upsert_active_flags(pitcher_id, current)
        return

    profile = _json_load_profile(pitcher_id)
    flags = profile.get("active_flags", {})
    flags.update(updates)
    profile["active_flags"] = flags
    _json_save_profile(pitcher_id, profile)


def increment_days_since_outing(pitcher_id: str) -> None:
    """Increment days_since_outing by 1."""
    if _using_supabase():
        flags = _db.get_active_flags(pitcher_id)
        days = (flags.get("days_since_outing") or 0) + 1
        _db.upsert_active_flags(pitcher_id, {
            "pitcher_id": pitcher_id,
            "days_since_outing": days,
        })
        return

    profile = _json_load_profile(pitcher_id)
    flags = profile.get("active_flags", {})
    flags["days_since_outing"] = flags.get("days_since_outing", 0) + 1
    profile["active_flags"] = flags
    _json_save_profile(pitcher_id, profile)


def update_exercise_completion(pitcher_id: str, date: str, exercise_id: str, completed: bool) -> None:
    """Mark an exercise as completed or uncompleted in a specific day's log entry."""
    if _using_supabase():
        entry = _db.get_daily_entry(pitcher_id, date)
        if entry:
            completed_exercises = entry.get("completed_exercises") or {}
            if isinstance(completed_exercises, list):
                completed_exercises = {}
            completed_exercises[exercise_id] = completed
            _db.upsert_daily_entry(pitcher_id, {
                "date": date,
                "completed_exercises": completed_exercises,
            })
        return

    log = _json_load_log(pitcher_id)
    for entry in log["entries"]:
        if entry["date"] == date:
            if "completed_exercises" not in entry:
                entry["completed_exercises"] = {}
            entry["completed_exercises"][exercise_id] = completed
            break
    _json_save_log(pitcher_id, log)


def update_throwing_feel(pitcher_id: str, date: str, post_throw_feel: int) -> None:
    """Store post-throw arm feel rating in a specific day's throwing data."""
    if _using_supabase():
        entry = _db.get_daily_entry(pitcher_id, date)
        if entry:
            throwing = entry.get("throwing") or {}
            if isinstance(throwing, str):
                throwing = {"type": throwing}
            throwing["post_throw_feel"] = post_throw_feel
            _db.upsert_daily_entry(pitcher_id, {
                "date": date,
                "throwing": throwing,
            })
        return

    log = _json_load_log(pitcher_id)
    for entry in log["entries"]:
        if entry["date"] == date:
            throwing = entry.get("throwing") or {}
            if isinstance(throwing, str):
                throwing = {"type": throwing}
            throwing["post_throw_feel"] = post_throw_feel
            entry["throwing"] = throwing
            break
    _json_save_log(pitcher_id, log)


def load_saved_plans(pitcher_id: str) -> list:
    """Load saved plans for a pitcher."""
    if _using_supabase():
        plans = _db.get_saved_plans(pitcher_id)
        # Convert DB rows to the shape callers expect
        result = []
        for p in plans:
            plan = dict(p.get("plan_data") or {})
            plan["id"] = str(p["id"])  # callers expect string id like "plan_001"
            plan["active"] = p.get("active", False)
            plan["created_date"] = str(p.get("date_created") or p.get("created_at", "")[:10])
            plan["rotation_day"] = p.get("rotation_day")
            plan["template_used"] = p.get("template_used")
            result.append(plan)
        return result
    return _json_load_saved_plans(pitcher_id)


def save_plan(pitcher_id: str, plan: dict) -> dict:
    """Save a new plan for a pitcher. Returns the plan with generated id."""
    if _using_supabase():
        row = {
            "pitcher_id": pitcher_id,
            "plan_data": plan,
            "active": plan.pop("active", True),
            "date_created": plan.pop("created_date", None) or datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d"),
            "rotation_day": plan.pop("rotation_day", None),
            "template_used": plan.pop("template_used", None),
        }
        result = _db.insert_saved_plan(pitcher_id, row)
        plan["id"] = str(result.get("id", ""))
        plan["active"] = row["active"]
        plan["created_date"] = str(row["date_created"])
        return plan

    # Filesystem fallback
    plans = _json_load_saved_plans(pitcher_id)
    plan_id = f"plan_{len(plans) + 1:03d}"
    plan["id"] = plan_id
    if "active" not in plan:
        plan["active"] = True
    if "created_date" not in plan:
        plan["created_date"] = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    plans.append(plan)
    path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
    with open(path, "w") as f:
        json.dump(plans, f, indent=2)
    return plan


def deactivate_plan(pitcher_id: str, plan_id: str) -> bool:
    """Mark a saved plan as inactive. Returns True if found."""
    if _using_supabase():
        try:
            _db.update_saved_plan(int(plan_id), {"active": False})
            return True
        except (ValueError, Exception):
            return False

    plans = _json_load_saved_plans(pitcher_id)
    for plan in plans:
        if plan["id"] == plan_id:
            plan["active"] = False
            path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
            with open(path, "w") as f:
                json.dump(plans, f, indent=2)
            return True
    return False


def activate_plan(pitcher_id: str, plan_id: str) -> bool:
    """Mark a saved plan as active. Returns True if found."""
    if _using_supabase():
        try:
            _db.update_saved_plan(int(plan_id), {"active": True})
            return True
        except (ValueError, Exception):
            return False

    plans = _json_load_saved_plans(pitcher_id)
    for plan in plans:
        if plan["id"] == plan_id:
            plan["active"] = True
            path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
            with open(path, "w") as f:
                json.dump(plans, f, indent=2)
            return True
    return False


def update_plan_data(pitcher_id: str, plan_id: str, updates: dict) -> bool:
    """Update fields within a saved plan's plan_data. Returns True if found."""
    if _using_supabase():
        try:
            plan_row = _db.get_saved_plan(int(plan_id))
            if not plan_row:
                return False
            plan_data = plan_row.get("plan_data") or {}
            plan_data.update(updates)
            _db.update_saved_plan(int(plan_id), {"plan_data": plan_data})
            return True
        except (ValueError, Exception):
            return False

    plans = _json_load_saved_plans(pitcher_id)
    for plan in plans:
        if plan["id"] == plan_id:
            plan.update(updates)
            path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
            with open(path, "w") as f:
                json.dump(plans, f, indent=2)
            return True
    return False


def get_pitcher_id_by_telegram(telegram_id: int, username: str = None) -> str:
    """Look up pitcher_id from a Telegram user ID."""
    if _using_supabase():
        # Try telegram_id first
        row = _db.get_pitcher_by_telegram_id(telegram_id)
        if row:
            return row["pitcher_id"]

        # Username fallback
        if username:
            row = _db.get_pitcher_by_username(username)
            if row and not row.get("telegram_id"):
                # Backfill telegram_id
                _db.update_pitcher(row["pitcher_id"], {"telegram_id": telegram_id})
                logger.info(f"Matched {row['pitcher_id']} via username '{username}', "
                            f"backfilled telegram_id={telegram_id}")
                return row["pitcher_id"]

        logger.warning(f"No pitcher found for telegram_id={telegram_id}, username={username}")
        return None

    # Filesystem fallback
    if not os.path.exists(PITCHERS_DIR):
        return None

    username_match = None
    for entry in os.listdir(PITCHERS_DIR):
        profile_path = os.path.join(PITCHERS_DIR, entry, "profile.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                stored_id = profile.get("telegram_id")
                if stored_id == telegram_id:
                    return profile["pitcher_id"]
                if (username and not username_match
                        and profile.get("telegram_username", "").lower() == username.lower()
                        and not stored_id):
                    username_match = profile
            except (json.JSONDecodeError, KeyError):
                continue

    if username_match:
        pitcher_id = username_match["pitcher_id"]
        username_match["telegram_id"] = telegram_id
        _json_save_profile(pitcher_id, username_match)
        return pitcher_id

    return None
