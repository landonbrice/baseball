#!/usr/bin/env python3
"""Intake script: Google Form CSV/JSON → pitcher profile files.

Usage:
    python scripts/intake_to_profile.py --csv intake.csv
    python scripts/intake_to_profile.py --json data/intake_responses.json
"""

import argparse
import csv
import json
import os
import re
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot.config import PITCHERS_DIR


# Maps partial column name matches to normalized field names.
# Order matters — first match wins.
COLUMN_PATTERNS = [
    ("Name", "name"),
    ("Telegram username", "telegram_username"),
    ("Year", "year"),
    ("Throws", "throws"),
    ("role", "role"),
    ("how many days between starts", "rotation_length"),
    ("How many pitches", "typical_pitch_count"),
    ("What pitches do you throw", "pitch_arsenal"),
    ("current or past arm/shoulder injuries", "has_injuries"),
    ("If yes:", "injury_checkboxes"),
    ("most significant injury", "injury_history_text"),
    ("currently managing or keeping an eye on", "ongoing_considerations"),
    ("Lifting experience", "lifting_experience"),
    ("Trap bar", "trap_bar_dl"),
    ("Front squat", "front_squat"),
    ("DB bench", "db_bench"),
    ("Pull-up", "pullup"),
    ("When do you usually lift", "lift_timing"),
    ("time constraints", "time_constraints"),
    ("#1 thing you want", "primary_goal"),
    ("information delivered", "detail_level"),
    ("daily check-in notification", "notification_time"),
    ("Average sleep", "avg_sleep_hours"),
    ("whoop", "whoop_connected"),
    ("mechanical focus", "mechanical_focus_areas"),
    ("Anything else the bot", "additional_notes"),
]


def _match_column(col_name: str) -> str | None:
    """Match a Google Form column header to a normalized field name."""
    col_lower = col_name.lower().strip()
    # "Name" must match exactly (not partial, to avoid matching "username")
    if col_lower == "name":
        return "name"
    for pattern, field in COLUMN_PATTERNS:
        if field == "name":
            continue  # handled above
        if pattern.lower() in col_lower:
            return field
    return None


def normalize_row(row: dict) -> dict:
    """Map raw Google Form column names to normalized field names."""
    result = {}
    for key, value in row.items():
        field = _match_column(key)
        if field:
            result[field] = str(value).strip() if value else ""
    return result


def generate_pitcher_id(name: str) -> str:
    """Generate a pitcher ID from a name. e.g. 'John Smith' -> 'pitcher_smith_001'."""
    parts = name.strip().lower().split()
    if not parts:
        return "pitcher_unknown_001"

    last = re.sub(r"[^a-z]", "", parts[-1])
    if not last:
        last = re.sub(r"[^a-z]", "", parts[0]) or "unknown"

    base = f"pitcher_{last}"

    # Check for existing IDs and increment
    suffix = 1
    while True:
        pitcher_id = f"{base}_{suffix:03d}"
        if not os.path.exists(os.path.join(PITCHERS_DIR, pitcher_id)):
            return pitcher_id
        suffix += 1


def parse_injury_checkboxes(checkboxes: str) -> list[str]:
    """Parse checkbox selections into normalized area names."""
    if not checkboxes:
        return []

    area_map = {
        "ucl": "medial_elbow",
        "medial elbow": "medial_elbow",
        "tommy john": "medial_elbow",
        "shoulder impingement": "shoulder",
        "shoulder": "shoulder",
        "rotator cuff": "shoulder",
        "biceps tendon": "biceps",
        "bicep": "biceps",
        "lat": "lat",
        "oblique": "oblique",
        "forearm tightness": "forearm",
        "forearm": "forearm",
        "wrist": "wrist",
        "low back": "lower_back",
        "lower back": "lower_back",
        "hip": "hip",
        "knee": "knee",
    }

    raw_areas = [a.strip().lstrip("- ").lower() for a in checkboxes.split(",") if a.strip()]
    mapped = []
    for area in raw_areas:
        matched = None
        for pattern, normalized in area_map.items():
            if pattern in area:
                matched = normalized
                break
        if matched and matched not in mapped:
            mapped.append(matched)
        elif not matched:
            cleaned = area.replace(" ", "_")
            if cleaned not in mapped:
                mapped.append(cleaned)

    return mapped


def parse_injury_history(text: str, checkboxes: str, ongoing: str) -> list[dict]:
    """Parse injury history from free text, checkbox selections, and ongoing considerations."""
    areas = parse_injury_checkboxes(checkboxes)

    if not areas and not text:
        return []

    injuries = []

    # Create one entry per area from checkboxes
    for i, area in enumerate(areas):
        injury = {
            "date": "unknown",
            "area": area,
            "description": text if i == 0 else f"Reported via intake: {area}",
            "severity": "unknown",
            "resolution": "unknown",
            "ongoing_considerations": ongoing if i == 0 else "",
            "flag_level": "yellow",
        }
        injuries.append(injury)

    # If we have text but no checkbox areas
    if not injuries and text:
        injuries.append({
            "date": "unknown",
            "area": "unspecified",
            "description": text,
            "severity": "unknown",
            "resolution": "unknown",
            "ongoing_considerations": ongoing,
            "flag_level": "yellow",
        })

    return injuries


def _default_modifications(injuries: list[dict]) -> list[str]:
    """Auto-set modifications based on injury history."""
    mods = []
    areas = [inj.get("area", "") for inj in injuries]

    if "medial_elbow" in areas or "forearm" in areas:
        mods.append("elevated_fpm_volume")

    if "shoulder" in areas:
        mods.append("neutral_grip_pressing")

    if "lower_back" in areas:
        mods.append("reduced_axial_loading")

    return mods


def _parse_list(value: str) -> list[str]:
    """Parse a comma-separated string into a cleaned list."""
    if not value:
        return []
    items = []
    for item in value.split(","):
        cleaned = item.strip().lstrip("- ").strip()
        if cleaned:
            items.append(cleaned)
    return items


def _parse_int(value: str, default: int = 0) -> int:
    """Parse a string to int with default. Takes first number found."""
    if not value:
        return default
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else default


def _parse_role(value: str) -> str:
    """Normalize role to 'starter' or 'reliever'."""
    v = value.lower().strip()
    if "start" in v:
        return "starter"
    return "reliever"


def _parse_rotation_length(value: str, role: str) -> int:
    """Parse rotation length from form value like '- 7 days'."""
    if role == "reliever":
        return 3
    match = re.search(r"(\d+)", value)
    if match:
        return int(match.group(1))
    return 7


def _parse_notification_time(value: str) -> str:
    """Parse notification time from '- 8:00 AM' -> '08:00'."""
    match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", value, re.IGNORECASE)
    if not match:
        return "08:00"
    hour = int(match.group(1))
    minute = match.group(2)
    ampm = (match.group(3) or "").upper()
    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _parse_detail_level(value: str) -> str:
    """Parse detail level preference."""
    v = value.lower()
    if "just tell me" in v or "short" in v or "bullet" in v:
        return "concise"
    elif "explain" in v or "reasoning" in v or "why" in v:
        return "detailed"
    return "moderate"


def _parse_sleep_hours(value: str) -> float:
    """Parse avg sleep from '- 6-7 hours' -> 6.5."""
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)", value)
    if match:
        return (int(match.group(1)) + int(match.group(2))) / 2
    match = re.search(r"(\d+)", value)
    if match:
        return float(match.group(1))
    return 7.0


def _parse_lifting_experience(value: str) -> str:
    """Parse lifting experience from '- Advanced (3+ years...)'."""
    v = value.lower()
    if "advanced" in v:
        return "advanced"
    elif "beginner" in v or "new" in v:
        return "beginner"
    return "intermediate"


def _parse_throws(value: str) -> str:
    """Parse throwing hand."""
    v = value.lower().strip()
    if v.startswith("l"):
        return "left"
    return "right"


def _parse_whoop(value: str) -> bool:
    """Parse whoop connection preference."""
    return value.lower().strip() in ("yes", "- yes")


def _parse_pitch_count(value: str) -> int:
    """Parse pitch count, handling ranges like '15-30' by taking midpoint."""
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)", value)
    if match:
        return (int(match.group(1)) + int(match.group(2))) // 2
    return _parse_int(value, 85)


def row_to_profile(row: dict) -> dict:
    """Map a form response row to the pitcher profile schema."""
    n = normalize_row(row)

    name = n.get("name", "Unknown").strip()
    pitcher_id = generate_pitcher_id(name)

    # Core fields
    role = _parse_role(n.get("role", "starter"))
    rotation_length = _parse_rotation_length(n.get("rotation_length", ""), role)
    throws = _parse_throws(n.get("throws", "right"))

    # Telegram username — strip @ prefix
    tg_username = n.get("telegram_username", "").lstrip("@").strip() or None

    # Injuries
    injuries = parse_injury_history(
        text=n.get("injury_history_text", ""),
        checkboxes=n.get("injury_checkboxes", ""),
        ongoing=n.get("ongoing_considerations", ""),
    )
    mods = _default_modifications(injuries)

    # Pitch arsenal — clean up leading dashes
    arsenal = _parse_list(n.get("pitch_arsenal", "4-seam"))
    if not arsenal:
        arsenal = ["4-seam"]

    # Maxes
    trap_bar_dl = _parse_int(n.get("trap_bar_dl", ""))
    front_squat = _parse_int(n.get("front_squat", ""))
    db_bench = _parse_int(n.get("db_bench", ""))
    pullup_raw = n.get("pullup", "")

    # Mechanical focus
    mech_focus_raw = n.get("mechanical_focus_areas", "")
    mechanical_focus_areas = [mech_focus_raw] if mech_focus_raw else []

    profile = {
        "pitcher_id": pitcher_id,
        "telegram_id": None,
        "telegram_username": tg_username,
        "name": name,
        "role": role,
        "rotation_length": rotation_length,
        "throws": throws,
        "year": n.get("year", ""),
        "physical_profile": {
            "height_in": 72,
            "weight_lbs": 185,
            "body_comp_goal": "maintain",
            "known_mobility_limitations": [],
            "movement_screen_notes": "",
        },
        "injury_history": injuries,
        "current_training": {
            "lifting_experience": _parse_lifting_experience(n.get("lifting_experience", "")),
            "current_maxes": {
                "trap_bar_dl": trap_bar_dl,
                "front_squat": front_squat,
                "db_bench": db_bench,
                "pullup": pullup_raw,
            },
            "preferred_exercises": [],
            "disliked_or_avoided": [],
            "current_split": "upper_lower_2x",
            "lift_timing": n.get("lift_timing", "").lstrip("- ").strip(),
            "time_constraints": n.get("time_constraints", ""),
        },
        "pitching_profile": {
            "avg_velocity_fb": 0,
            "pitch_arsenal": arsenal,
            "typical_pitch_count": _parse_pitch_count(n.get("typical_pitch_count", "85")),
            "avg_outing_innings": 0,
            "mechanical_focus_areas": mechanical_focus_areas,
            "mechanical_notes": "",
        },
        "biometric_integration": {
            "whoop_connected": _parse_whoop(n.get("whoop_connected", "no")),
            "baseline_hrv": None,
            "baseline_rhr": None,
            "avg_sleep_hours": _parse_sleep_hours(n.get("avg_sleep_hours", "7")),
        },
        "goals": {
            "primary": n.get("primary_goal", "Stay healthy"),
            "secondary": "",
            "tertiary": "",
        },
        "preferences": {
            "notification_time": _parse_notification_time(n.get("notification_time", "08:00")),
            "log_style": "conversational",
            "detail_level": _parse_detail_level(n.get("detail_level", "moderate")),
            "wants_youtube_links": True,
        },
        "active_flags": {
            "current_arm_feel": 4,
            "current_flag_level": "green",
            "last_outing_date": None,
            "last_outing_pitches": None,
            "days_since_outing": 99,
            "active_modifications": mods,
        },
    }

    return profile


def create_pitcher_files(profile: dict, additional_notes: str = "") -> str:
    """Create pitcher directory with profile.json, context.md, and daily_log.json."""
    pitcher_id = profile["pitcher_id"]
    pitcher_dir = os.path.join(PITCHERS_DIR, pitcher_id)
    os.makedirs(pitcher_dir, exist_ok=True)

    # Write profile
    profile_path = os.path.join(pitcher_dir, "profile.json")
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    # Write context
    context_path = os.path.join(pitcher_dir, "context.md")
    name = profile.get("name", "Unknown")
    role = profile.get("role", "starter")
    injuries = profile.get("injury_history", [])
    mods = profile.get("active_flags", {}).get("active_modifications", [])

    context = f"# Pitcher Context: {name} ({pitcher_id})\n\n"
    context += "## Profile Summary\n"
    context += f"- Role: {role.title()}"
    if role == "starter":
        context += f", {profile.get('rotation_length', 7)}-day rotation"
    context += f"\n- Throws: {profile.get('throws', 'right').title()}\n"
    context += f"- Year: {profile.get('year', 'Unknown')}\n"

    if injuries:
        context += "\n## Injury History\n"
        for inj in injuries:
            context += f"- {inj.get('area', 'unspecified')}: {inj.get('description', '')}\n"
            if inj.get("ongoing_considerations"):
                context += f"  - Currently managing: {inj['ongoing_considerations']}\n"

    if mods:
        context += f"\n## Active Modifications\n- {', '.join(mods)}\n"

    if additional_notes:
        context += f"\n## Additional Notes\n{additional_notes}\n"

    context += "\n## Interaction Log\n"

    with open(context_path, "w") as f:
        f.write(context)

    # Write empty log
    log_path = os.path.join(pitcher_dir, "daily_log.json")
    with open(log_path, "w") as f:
        json.dump({"pitcher_id": pitcher_id, "entries": []}, f, indent=2)

    return pitcher_dir


def process_csv(csv_path: str) -> None:
    """Process a CSV of intake form responses."""
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = normalize_row(row)
            profile = row_to_profile(row)
            pitcher_dir = create_pitcher_files(profile, additional_notes=n.get("additional_notes", ""))
            print(f"Created: {profile['pitcher_id']} ({profile['name']}) -> {pitcher_dir}")


def process_json(json_path: str) -> None:
    """Process a single JSON intake response."""
    with open(json_path, "r") as f:
        data = json.load(f)

    # Handle both single object and list
    rows = data if isinstance(data, list) else [data]

    for row in rows:
        n = normalize_row(row)
        profile = row_to_profile(row)
        pitcher_dir = create_pitcher_files(profile, additional_notes=n.get("additional_notes", ""))
        print(f"Created: {profile['pitcher_id']} ({profile['name']}) -> {pitcher_dir}")


def main():
    parser = argparse.ArgumentParser(description="Convert intake form responses to pitcher profiles")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Path to CSV file from Google Form export")
    group.add_argument("--json", help="Path to JSON file (single response or array)")
    args = parser.parse_args()

    os.makedirs(PITCHERS_DIR, exist_ok=True)

    if args.csv:
        process_csv(args.csv)
    elif args.json:
        process_json(args.json)

    print("\nDone. Telegram IDs left null -- resolved on first bot message via username matching.")


if __name__ == "__main__":
    main()
