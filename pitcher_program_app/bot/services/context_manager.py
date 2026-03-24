"""Read/write pitcher profile, context, and log files."""

import json
import os
import logging
from datetime import datetime
from bot.config import PITCHERS_DIR
from scripts.data_sync import mark_dirty

logger = logging.getLogger(__name__)


def get_pitcher_dir(pitcher_id: str) -> str:
    """Return the directory for a pitcher's files."""
    return os.path.join(PITCHERS_DIR, pitcher_id)


def load_profile(pitcher_id: str) -> dict:
    """Load a pitcher's profile JSON."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "profile.json")
    with open(path, "r") as f:
        return json.load(f)


def save_profile(pitcher_id: str, profile: dict) -> None:
    """Save a pitcher's profile JSON."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "profile.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
    mark_dirty(path)


def load_context(pitcher_id: str) -> str:
    """Load a pitcher's context.md as a string."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


def append_context(pitcher_id: str, update_type: str, content: str) -> None:
    """Append a timestamped entry under ## Recent interactions, auto-migrate if needed, trim to 15 lines."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")

    # Auto-migrate: if file doesn't have section headers, rebuild it
    existing = ""
    if os.path.exists(path):
        with open(path, "r") as f:
            existing = f.read()

    if "## Persistent facts" not in existing:
        # Build persistent facts from profile
        profile = load_profile(pitcher_id)
        injury_history = profile.get("injury_history", [])
        injury_str = "; ".join(
            f"{i.get('location', '')} — {i.get('description', '')}"
            for i in injury_history
        ) if injury_history else "none"
        mods = profile.get("active_flags", {}).get("active_modifications", [])
        mods_str = ", ".join(mods) if mods else "none"
        role = profile.get("role", "starter")
        rotation = profile.get("rotation_length", 7)
        throws = profile.get("throws", "R")

        persistent = f"""## Persistent facts
- Role: {role}, {rotation}-day rotation, throws {throws}
- Injury history: {injury_str}
- Active program modifications: {mods_str}

## Recent interactions
"""
        # Preserve any existing interaction lines
        if existing.strip():
            old_lines = [l for l in existing.splitlines() if l.startswith("- [")]
            persistent += "\n".join(old_lines) + "\n" if old_lines else ""

        with open(path, "w") as f:
            f.write(persistent)
        existing = persistent

    # Append new entry under Recent interactions
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] ({update_type}) {content}\n"
    with open(path, "a") as f:
        f.write(entry)

    # Trim: keep only last 30 interaction lines
    _trim_recent_interactions(path)

    # Rebuild Current Status section from profile flags
    _rebuild_current_status(path, pitcher_id)
    mark_dirty(path)


def _trim_recent_interactions(path: str) -> None:
    """Keep only the last 30 lines under ## Recent interactions."""
    with open(path, "r") as f:
        content = f.read()

    if "## Recent interactions" not in content:
        return

    parts = content.split("## Recent interactions")
    header = parts[0] + "## Recent interactions\n"
    interaction_lines = [l for l in parts[1].splitlines() if l.strip()]
    trimmed = interaction_lines[-30:] if len(interaction_lines) > 30 else interaction_lines

    with open(path, "w") as f:
        f.write(header + "\n".join(trimmed) + "\n")


def _rebuild_current_status(path: str, pitcher_id: str) -> None:
    """Rebuild the ## Current Status section from profile active_flags."""
    try:
        profile = load_profile(pitcher_id)
    except FileNotFoundError:
        return

    flags = profile.get("active_flags", {})
    today = datetime.now().strftime("%Y-%m-%d")

    status_lines = [
        f"- Last Updated: {today}",
        f"- Arm Feel: {flags.get('current_arm_feel', 'N/A')}/5",
        f"- Flag Level: {flags.get('current_flag_level', 'unknown').upper()}",
        f"- Days Since Outing: {flags.get('days_since_outing', 'N/A')}",
    ]
    if flags.get("last_outing_date"):
        status_lines.append(f"- Last Outing: {flags['last_outing_date']} ({flags.get('last_outing_pitches', '?')} pitches)")
    if flags.get("phase"):
        status_lines.append(f"- Phase: {flags['phase'].replace('_', ' ')}")
    mods = flags.get("active_modifications", [])
    if mods:
        status_lines.append(f"- Active Mods: {', '.join(mods)}")

    status_block = "## Current Status\n" + "\n".join(status_lines) + "\n"

    with open(path, "r") as f:
        content = f.read()

    # Replace or insert Current Status section
    if "## Current Status" in content:
        # Replace existing
        import re
        content = re.sub(
            r"## Current Status\n(?:- .*\n)*",
            status_block,
            content,
        )
    else:
        # Insert after Persistent facts, before Recent interactions
        if "## Recent interactions" in content:
            content = content.replace("## Recent interactions", status_block + "\n## Recent interactions")
        else:
            content += "\n" + status_block

    with open(path, "w") as f:
        f.write(content)


def load_log(pitcher_id: str) -> dict:
    """Load a pitcher's daily log."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "daily_log.json")
    if not os.path.exists(path):
        return {"pitcher_id": pitcher_id, "entries": []}
    with open(path, "r") as f:
        return json.load(f)


def save_log(pitcher_id: str, log: dict) -> None:
    """Save a pitcher's daily log."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "daily_log.json")
    with open(path, "w") as f:
        json.dump(log, f, indent=2)
    mark_dirty(path)


def append_log_entry(pitcher_id: str, entry: dict) -> None:
    """Append a new entry to a pitcher's daily log.

    Maintains a 7-day rolling window: entries older than 7 are
    summarized into profile.json weekly_summaries and removed.
    """
    log = load_log(pitcher_id)
    log["entries"].append(entry)

    # Summarize and remove entries beyond the 7-day window
    training_entries = [e for e in log["entries"] if e.get("pre_training")]
    if len(training_entries) > 7:
        to_summarize = training_entries[:-7]
        summaries = [_summarize_entry(e) for e in to_summarize]

        # Append summaries to profile
        profile = load_profile(pitcher_id)
        if "weekly_summaries" not in profile:
            profile["weekly_summaries"] = []
        profile["weekly_summaries"].extend(summaries)
        save_profile(pitcher_id, profile)

        # Remove old entries from log
        dates_to_remove = {e["date"] for e in to_summarize}
        log["entries"] = [e for e in log["entries"] if e.get("date") not in dates_to_remove]
        logger.info(f"Summarized {len(to_summarize)} old entries for {pitcher_id}")

    save_log(pitcher_id, log)


def _summarize_entry(entry: dict) -> str:
    """Distill a log entry into a 1-line summary for long-term memory."""
    pt = entry.get("pre_training", {})
    date = entry.get("date", "?")
    arm = pt.get("arm_feel", "?")
    sleep = pt.get("sleep_hours", "?")
    flag = (pt.get("flag_level") or "?").upper()

    parts = [f"{date}: Arm {arm}/5, sleep {sleep}h, {flag}"]

    lifting = entry.get("lifting", {})
    if lifting and lifting.get("intent"):
        parts.append(lifting["intent"])
    elif lifting and lifting.get("exercises"):
        names = [ex.get("name", "") for ex in lifting["exercises"][:3]]
        parts.append(f"Lift: {', '.join(names)}")

    throwing = entry.get("throwing", {})
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
    log = load_log(pitcher_id)
    return log["entries"][-n:]


def update_active_flags(pitcher_id: str, updates: dict) -> None:
    """Partial update of active_flags in a pitcher's profile."""
    profile = load_profile(pitcher_id)
    flags = profile.get("active_flags", {})
    flags.update(updates)
    profile["active_flags"] = flags
    save_profile(pitcher_id, profile)


def increment_days_since_outing(pitcher_id: str) -> None:
    """Increment days_since_outing by 1."""
    profile = load_profile(pitcher_id)
    flags = profile.get("active_flags", {})
    flags["days_since_outing"] = flags.get("days_since_outing", 0) + 1
    profile["active_flags"] = flags
    save_profile(pitcher_id, profile)


def update_exercise_completion(pitcher_id: str, date: str, exercise_id: str, completed: bool) -> None:
    """Mark an exercise as completed or uncompleted in a specific day's log entry."""
    log = load_log(pitcher_id)
    for entry in log["entries"]:
        if entry["date"] == date:
            if "completed_exercises" not in entry:
                entry["completed_exercises"] = {}
            entry["completed_exercises"][exercise_id] = completed
            break
    save_log(pitcher_id, log)


def load_saved_plans(pitcher_id: str) -> list:
    """Load saved plans for a pitcher."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_plan(pitcher_id: str, plan: dict) -> dict:
    """Save a new plan for a pitcher. Returns the plan with generated id."""
    plans = load_saved_plans(pitcher_id)
    # Generate plan ID
    plan_id = f"plan_{len(plans) + 1:03d}"
    plan["id"] = plan_id
    if "active" not in plan:
        plan["active"] = True
    if "created_date" not in plan:
        plan["created_date"] = datetime.now().strftime("%Y-%m-%d")
    plans.append(plan)
    path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
    with open(path, "w") as f:
        json.dump(plans, f, indent=2)
    mark_dirty(path)
    return plan


def deactivate_plan(pitcher_id: str, plan_id: str) -> bool:
    """Mark a saved plan as inactive. Returns True if found."""
    plans = load_saved_plans(pitcher_id)
    for plan in plans:
        if plan["id"] == plan_id:
            plan["active"] = False
            path = os.path.join(get_pitcher_dir(pitcher_id), "saved_plans.json")
            with open(path, "w") as f:
                json.dump(plans, f, indent=2)
            mark_dirty(path)
            return True
    return False


def get_pitcher_id_by_telegram(telegram_id: int, username: str = None) -> str | None:
    """Look up pitcher_id from a Telegram user ID.

    Scans pitcher profiles for a matching telegram_id field.
    If no match by telegram_id and username is provided, falls back to
    matching telegram_username (case-insensitive) and backfills the telegram_id.
    """
    if not os.path.exists(PITCHERS_DIR):
        logger.warning(f"Pitchers directory does not exist: {PITCHERS_DIR}")
        return None

    username_match = None
    entries = os.listdir(PITCHERS_DIR)
    logger.info(f"Pitcher lookup: telegram_id={telegram_id}, username={username}, dir={PITCHERS_DIR}, entries={len(entries)}")

    for entry in entries:
        profile_path = os.path.join(PITCHERS_DIR, entry, "profile.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                stored_id = profile.get("telegram_id")
                if stored_id == telegram_id:
                    return profile["pitcher_id"]
                # Username fallback (only if profile has no telegram_id yet)
                if (username and not username_match
                        and profile.get("telegram_username", "").lower() == username.lower()
                        and not stored_id):
                    username_match = profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error reading {profile_path}: {e}")
                continue

    # Username fallback: backfill telegram_id on first match
    if username_match:
        pitcher_id = username_match["pitcher_id"]
        username_match["telegram_id"] = telegram_id
        save_profile(pitcher_id, username_match)
        logger.info(f"Matched {pitcher_id} via username '{username}', backfilled telegram_id={telegram_id}")
        return pitcher_id

    logger.warning(f"No pitcher found for telegram_id={telegram_id}, username={username}")
    return None
