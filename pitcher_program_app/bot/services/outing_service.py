"""Shared post-outing business logic, usable by both Telegram bot and API."""

import json
import logging
from datetime import datetime

from bot.services.llm import call_llm, load_prompt
from bot.services.context_manager import (
    load_profile,
    load_context,
    append_context,
    append_log_entry,
    get_recent_entries,
    update_active_flags,
)
from bot.config import TEMPLATES_DIR, CONTEXT_WINDOW_CHARS

logger = logging.getLogger(__name__)


async def process_outing(pitcher_id: str, pitch_count: int, post_arm_feel: int, notes: str = "") -> dict:
    """Process a post-outing report: update flags, generate recovery plan, log entry.

    Returns dict with: recovery_plan, flag_level, alerts, rotation_reset, outing_date.
    """
    profile = load_profile(pitcher_id)
    today = datetime.now().strftime("%Y-%m-%d")

    # Update active flags
    update_active_flags(pitcher_id, {
        "days_since_outing": 0,
        "last_outing_date": today,
        "last_outing_pitches": pitch_count,
        "current_arm_feel": post_arm_feel,
    })

    # Load recovery templates
    recovery_templates = _load_recovery_templates()

    # Build outing data string
    typical = profile.get("pitching_profile", {}).get("typical_pitch_count", 85)
    outing_data = (
        f"Date: {today}\n"
        f"Pitch count: {pitch_count} (typical: {typical})\n"
        f"Arm feel: {post_arm_feel}/5\n"
    )
    if notes:
        outing_data += f"Notes: {notes}\n"
    if pitch_count > typical + 15:
        outing_data += "⚠️ Pitch count significantly above typical — extended recovery recommended\n"
    if post_arm_feel <= 2:
        outing_data += "⚠️ Low arm feel — recommend trainer evaluation before tomorrow's work\n"

    # Build pitcher context
    pitcher_context = _build_outing_context(profile, pitcher_id)

    # Recent logs
    recent = get_recent_entries(pitcher_id, n=3)
    recent_logs = json.dumps(recent, indent=2) if recent else "No recent entries"

    # Call LLM for recovery plan
    system_prompt = load_prompt("system_prompt.md")
    recovery_prompt = load_prompt("post_outing_recovery.md")

    user_prompt = recovery_prompt.replace("{pitcher_context}", pitcher_context)
    user_prompt = user_prompt.replace("{outing_data}", outing_data)
    user_prompt = user_prompt.replace("{recovery_templates}", recovery_templates)
    user_prompt = user_prompt.replace("{recent_logs}", recent_logs)

    recovery_plan = await call_llm(system_prompt, user_prompt)

    # Build alerts
    alerts = []
    if post_arm_feel <= 2:
        alerts.append("I'd flag that arm feel for your trainer before doing anything tomorrow.")

    # Determine flag level based on arm feel
    if post_arm_feel <= 2:
        flag_level = "red"
    elif post_arm_feel == 3:
        flag_level = "yellow"
    else:
        flag_level = "green"

    # Log the outing entry
    entry = {
        "date": today,
        "outing": {
            "pitch_count": pitch_count,
            "arm_feel": post_arm_feel,
            "notes": notes,
        },
        "pre_training": None,
        "actual_logged": None,
        "bot_observations": None,
    }
    append_log_entry(pitcher_id, entry)

    # Update context
    append_context(
        pitcher_id, "outing",
        f"Outing: {pitch_count} pitches, arm_feel={post_arm_feel}/5"
        + (f", notes: {notes[:80]}" if notes else "")
    )

    return {
        "recovery_plan": recovery_plan,
        "flag_level": flag_level,
        "alerts": alerts,
        "rotation_reset": True,
        "outing_date": today,
    }


def _load_recovery_templates() -> str:
    """Load post-throw stretch and arm care light templates as formatted strings."""
    templates = []

    for filename in ["post_throw_stretch.json", "arm_care_light.json"]:
        path = f"{TEMPLATES_DIR}/{filename}"
        try:
            with open(path, "r") as f:
                data = json.load(f)
            name = data.get("name", filename)
            exercises = []
            # Handle both flat and blocked structures
            if "sequence" in data:
                for item in data["sequence"]:
                    if "exercises" in item:
                        exercises.append(f"\n{item.get('block_name', '')}:")
                        for ex in item["exercises"]:
                            exercises.append(f"  - {ex['name']}: {ex.get('prescription', '')}")
                    else:
                        exercises.append(f"  - {item['name']}: {item.get('prescription', '')}")
            templates.append(f"### {name}\n" + "\n".join(exercises))
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load template {filename}: {e}")

    return "\n\n".join(templates) if templates else "No recovery templates available"


def _build_outing_context(profile: dict, pitcher_id: str) -> str:
    """Build context string for outing recovery prompt."""
    context_md = load_context(pitcher_id)
    flags = profile.get("active_flags", {})
    injury = profile.get("injury_history", [])

    parts = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'starter')}",
        f"Typical pitch count: {profile.get('pitching_profile', {}).get('typical_pitch_count', 'N/A')}",
    ]

    if injury:
        latest = injury[-1]
        parts.append(f"Injury note: {latest.get('area', '')} — {latest.get('ongoing_considerations', '')}")

    active_mods = flags.get("active_modifications", [])
    if active_mods:
        parts.append(f"Active modifications: {', '.join(active_mods)}")

    if context_md:
        parts.append(f"\nRecent context:\n{context_md[-CONTEXT_WINDOW_CHARS:]}")

    return "\n".join(parts)
