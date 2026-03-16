#!/usr/bin/env python3
"""Intake script: Google Form CSV/JSON → pitcher profile files.

Usage:
    python scripts/intake_to_profile.py --csv intake.csv
    python scripts/intake_to_profile.py --json single_response.json
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


# Expected CSV/JSON column mappings (Google Form field → profile field)
FIELD_MAP = {
    "name": "name",
    "full_name": "name",
    "telegram_username": "telegram_username",
    "telegram username": "telegram_username",
    "role": "role",
    "position": "role",
    "starter_or_reliever": "role",
    "throws": "throws",
    "throwing_hand": "throws",
    "height": "height_in",
    "height_inches": "height_in",
    "weight": "weight_lbs",
    "weight_lbs": "weight_lbs",
    "velocity": "avg_velocity_fb",
    "avg_velo": "avg_velocity_fb",
    "fastball_velo": "avg_velocity_fb",
    "pitch_arsenal": "pitch_arsenal",
    "pitches": "pitch_arsenal",
    "typical_pitch_count": "typical_pitch_count",
    "avg_pitch_count": "typical_pitch_count",
    "injury_history": "injury_history_text",
    "injuries": "injury_history_text",
    "past_injuries": "injury_history_text",
    "injury_checkboxes": "injury_checkboxes",
    "injury_areas": "injury_checkboxes",
    "lifting_experience": "lifting_experience",
    "training_experience": "lifting_experience",
    "trap_bar_dl": "trap_bar_dl",
    "deadlift_max": "trap_bar_dl",
    "front_squat": "front_squat",
    "squat_max": "front_squat",
    "preferred_exercises": "preferred_exercises",
    "exercises_i_like": "preferred_exercises",
    "avoided_exercises": "disliked_or_avoided",
    "exercises_i_avoid": "disliked_or_avoided",
    "goals": "goals",
    "primary_goal": "primary_goal",
    "secondary_goal": "secondary_goal",
    "mobility_limitations": "mobility_limitations",
    "movement_notes": "movement_screen_notes",
}


def generate_pitcher_id(name: str) -> str:
    """Generate a pitcher ID from a name. e.g. 'John Smith' → 'pitcher_smith_001'."""
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


def parse_injury_history(text: str = "", checkboxes: str = "") -> list[dict]:
    """Parse injury history from free text and/or checkbox selections."""
    injuries = []

    # Parse checkboxes (comma-separated areas)
    if checkboxes:
        areas = [a.strip().lower() for a in checkboxes.split(",") if a.strip()]
        area_map = {
            "ucl": "medial_elbow",
            "elbow": "medial_elbow",
            "medial elbow": "medial_elbow",
            "shoulder": "shoulder",
            "rotator cuff": "shoulder",
            "lat": "lat",
            "oblique": "oblique",
            "forearm": "forearm",
            "wrist": "wrist",
            "back": "lower_back",
            "lower back": "lower_back",
            "hip": "hip",
            "knee": "knee",
        }
        for area in areas:
            mapped = area_map.get(area, area.replace(" ", "_"))
            injuries.append({
                "date": "unknown",
                "area": mapped,
                "description": f"Reported via intake form: {area}",
                "severity": "unknown",
                "resolution": "unknown",
                "ongoing_considerations": "",
                "flag_level": "yellow",
            })

    # Parse free text — look for area mentions
    if text and text.strip().lower() not in ("none", "n/a", "no", ""):
        # If we already have checkbox injuries, add text as description to the first one
        if injuries:
            injuries[0]["description"] = text
        else:
            injuries.append({
                "date": "unknown",
                "area": "unspecified",
                "description": text,
                "severity": "unknown",
                "resolution": "unknown",
                "ongoing_considerations": "Review with trainer",
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

    return mods


def _parse_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int(value: str, default: int = 0) -> int:
    """Parse a string to int with default."""
    try:
        return int(re.sub(r"[^\d]", "", str(value)))
    except (ValueError, TypeError):
        return default


def row_to_profile(row: dict) -> dict:
    """Map a form response row to the pitcher profile schema."""
    # Normalize keys
    normalized = {}
    for key, value in row.items():
        norm_key = key.strip().lower().replace(" ", "_")
        mapped = FIELD_MAP.get(norm_key, FIELD_MAP.get(key.strip().lower()))
        if mapped:
            normalized[mapped] = str(value).strip() if value else ""

    name = normalized.get("name", "Unknown")
    pitcher_id = generate_pitcher_id(name)

    # Parse injury history
    injuries = parse_injury_history(
        text=normalized.get("injury_history_text", ""),
        checkboxes=normalized.get("injury_checkboxes", ""),
    )

    # Auto modifications
    mods = _default_modifications(injuries)

    # Parse pitch arsenal
    arsenal = _parse_list(normalized.get("pitch_arsenal", "4-seam"))
    if not arsenal:
        arsenal = ["4-seam"]

    # Role normalization
    role = normalized.get("role", "starter").lower()
    if role in ("sp", "start", "starting"):
        role = "starter"
    elif role in ("rp", "relief", "bullpen", "reliever"):
        role = "reliever"

    profile = {
        "pitcher_id": pitcher_id,
        "telegram_id": None,
        "telegram_username": normalized.get("telegram_username"),
        "name": name,
        "role": role,
        "rotation_length": 7 if role == "starter" else 3,
        "throws": normalized.get("throws", "right").lower(),
        "physical_profile": {
            "height_in": _parse_int(normalized.get("height_in"), 72),
            "weight_lbs": _parse_int(normalized.get("weight_lbs"), 185),
            "body_comp_goal": "maintain",
            "known_mobility_limitations": _parse_list(normalized.get("mobility_limitations", "")),
            "movement_screen_notes": normalized.get("movement_screen_notes", ""),
        },
        "injury_history": injuries,
        "current_training": {
            "lifting_experience": normalized.get("lifting_experience", "intermediate").lower(),
            "current_maxes": {
                "trap_bar_dl": _parse_int(normalized.get("trap_bar_dl")),
                "front_squat": _parse_int(normalized.get("front_squat")),
            },
            "preferred_exercises": _parse_list(normalized.get("preferred_exercises", "")),
            "disliked_or_avoided": _parse_list(normalized.get("disliked_or_avoided", "")),
            "current_split": "upper_lower_2x",
        },
        "pitching_profile": {
            "avg_velocity_fb": _parse_int(normalized.get("avg_velocity_fb")),
            "pitch_arsenal": arsenal,
            "typical_pitch_count": _parse_int(normalized.get("typical_pitch_count"), 85),
            "avg_outing_innings": 0,
            "mechanical_focus_areas": [],
            "mechanical_notes": "",
        },
        "biometric_integration": {
            "whoop_connected": False,
            "baseline_hrv": None,
            "baseline_rhr": None,
            "avg_sleep_hours": None,
        },
        "goals": {
            "primary": normalized.get("primary_goal", normalized.get("goals", "Stay healthy")),
            "secondary": normalized.get("secondary_goal", ""),
            "tertiary": "",
        },
        "preferences": {
            "notification_time": "08:00",
            "log_style": "conversational",
            "detail_level": "moderate",
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


def create_pitcher_files(profile: dict) -> str:
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

    if injuries:
        for inj in injuries:
            context += f"- Injury history: {inj.get('area', 'unspecified')} — {inj.get('description', '')}\n"

    if mods:
        context += f"- Active modifications: {', '.join(mods)}\n"

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
            profile = row_to_profile(row)
            pitcher_dir = create_pitcher_files(profile)
            print(f"Created: {profile['pitcher_id']} ({profile['name']}) → {pitcher_dir}")


def process_json(json_path: str) -> None:
    """Process a single JSON intake response."""
    with open(json_path, "r") as f:
        data = json.load(f)

    # Handle both single object and list
    rows = data if isinstance(data, list) else [data]

    for row in rows:
        profile = row_to_profile(row)
        pitcher_dir = create_pitcher_files(profile)
        print(f"Created: {profile['pitcher_id']} ({profile['name']}) → {pitcher_dir}")


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

    print("\nDone. Telegram IDs left null — resolved on first bot message via username matching.")


if __name__ == "__main__":
    main()
