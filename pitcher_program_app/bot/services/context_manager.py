"""Read/write pitcher profile, context, and log files."""

import json
import os
import logging
from datetime import datetime
from bot.config import PITCHERS_DIR

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


def load_context(pitcher_id: str) -> str:
    """Load a pitcher's context.md as a string."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


def append_context(pitcher_id: str, update_type: str, content: str) -> None:
    """Append a timestamped entry to a pitcher's context.md."""
    path = os.path.join(get_pitcher_dir(pitcher_id), "context.md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] ({update_type}) {content}\n"
    with open(path, "a") as f:
        f.write(entry)


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


def append_log_entry(pitcher_id: str, entry: dict) -> None:
    """Append a new entry to a pitcher's daily log."""
    log = load_log(pitcher_id)
    log["entries"].append(entry)
    save_log(pitcher_id, log)


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


def get_pitcher_id_by_telegram(telegram_id: int, username: str = None) -> str | None:
    """Look up pitcher_id from a Telegram user ID.

    Scans pitcher profiles for a matching telegram_id field.
    If no match by telegram_id and username is provided, falls back to
    matching telegram_username and backfills the telegram_id.
    """
    logger.info(f"Looking up telegram_id={telegram_id}, username={username}")

    if not os.path.exists(PITCHERS_DIR):
        logger.warning(f"Pitchers directory does not exist: {PITCHERS_DIR}")
        return None

    username_match = None

    for entry in os.listdir(PITCHERS_DIR):
        profile_path = os.path.join(PITCHERS_DIR, entry, "profile.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                logger.debug(
                    f"Scanning {entry}: telegram_id={profile.get('telegram_id')}, "
                    f"telegram_username={profile.get('telegram_username')}"
                )
                if profile.get("telegram_id") == telegram_id:
                    logger.info(f"Matched {profile['pitcher_id']} via telegram_id={telegram_id}")
                    return profile["pitcher_id"]
                # Check username fallback
                if (username and not username_match
                        and profile.get("telegram_username", "").lower() == username.lower()
                        and not profile.get("telegram_id")):
                    username_match = profile
            except (json.JSONDecodeError, KeyError):
                continue

    # Username fallback: backfill telegram_id on first match
    if username_match:
        pitcher_id = username_match["pitcher_id"]
        username_match["telegram_id"] = telegram_id
        save_profile(pitcher_id, username_match)
        logger.info(f"Matched {pitcher_id} via username fallback '{username}', backfilled telegram_id={telegram_id}")
        return pitcher_id

    logger.warning(f"No pitcher match for telegram_id={telegram_id}, username={username}")
    return None
