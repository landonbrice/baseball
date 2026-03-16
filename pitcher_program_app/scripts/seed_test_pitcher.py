#!/usr/bin/env python3
"""Seed a test pitcher for development. Creates profile, context, and empty log."""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot.config import PITCHERS_DIR

TEST_PITCHER_ID = "test_pitcher_001"
TEST_TELEGRAM_ID = 123456789  # Placeholder — replace with real Telegram user ID

PROFILE = {
    "pitcher_id": TEST_PITCHER_ID,
    "telegram_id": TEST_TELEGRAM_ID,
    "name": "Test Pitcher",
    "role": "starter",
    "rotation_length": 7,
    "throws": "right",
    "physical_profile": {
        "height_in": 73,
        "weight_lbs": 190,
        "body_comp_goal": "maintain",
        "known_mobility_limitations": ["limited_left_hip_ir"],
        "movement_screen_notes": "Good overall mobility, slight anterior pelvic tilt"
    },
    "injury_history": [
        {
            "date": "2024-03",
            "area": "medial_elbow",
            "description": "Forearm tightness and UCL area discomfort",
            "severity": "mild",
            "resolution": "Pronator strengthening protocol, resolved in 3 weeks",
            "ongoing_considerations": "Increased FPM work frequency, monitor arm feel closely post-outing",
            "flag_level": "yellow"
        }
    ],
    "current_training": {
        "lifting_experience": "intermediate",
        "current_maxes": {
            "trap_bar_dl": 315,
            "front_squat": 225,
            "weighted_pullup": "BW+45",
            "db_bench": "80s x 8"
        },
        "preferred_exercises": ["trap_bar_deadlift", "rdl", "db_row"],
        "disliked_or_avoided": ["barbell_back_squat"],
        "current_split": "upper_lower_2x"
    },
    "pitching_profile": {
        "avg_velocity_fb": 88,
        "pitch_arsenal": ["4-seam", "slider", "changeup"],
        "typical_pitch_count": 85,
        "avg_outing_innings": 5.5,
        "mechanical_focus_areas": ["hip_shoulder_separation"],
        "mechanical_notes": "Tends to open early when fatigued"
    },
    "biometric_integration": {
        "whoop_connected": False,
        "baseline_hrv": 65,
        "baseline_rhr": 52,
        "avg_sleep_hours": 7.2
    },
    "goals": {
        "primary": "Stay healthy through full season",
        "secondary": "Add 2-3 mph by end of summer",
        "tertiary": "Improve changeup command"
    },
    "preferences": {
        "notification_time": "08:00",
        "log_style": "conversational",
        "detail_level": "moderate",
        "wants_youtube_links": True
    },
    "active_flags": {
        "current_arm_feel": 4,
        "current_flag_level": "green",
        "last_outing_date": "2026-03-10",
        "last_outing_pitches": 78,
        "days_since_outing": 5,
        "active_modifications": ["elevated_fpm_volume"]
    }
}

CONTEXT_MD = """# Pitcher Context: Test Pitcher (test_pitcher_001)

## Profile Summary
- Role: Starter, 7-day rotation
- Throws: Right
- Key history: Medial elbow tightness (2024-03), resolved with pronator strengthening
- Active modifications: Elevated FPM volume

## Interaction Log
"""

EMPTY_LOG = {
    "pitcher_id": TEST_PITCHER_ID,
    "entries": []
}


def main():
    pitcher_dir = os.path.join(PITCHERS_DIR, TEST_PITCHER_ID)
    os.makedirs(pitcher_dir, exist_ok=True)

    # Write profile
    profile_path = os.path.join(pitcher_dir, "profile.json")
    with open(profile_path, "w") as f:
        json.dump(PROFILE, f, indent=2)
    print(f"Created: {profile_path}")

    # Write context
    context_path = os.path.join(pitcher_dir, "context.md")
    with open(context_path, "w") as f:
        f.write(CONTEXT_MD)
    print(f"Created: {context_path}")

    # Write empty log
    log_path = os.path.join(pitcher_dir, "daily_log.json")
    with open(log_path, "w") as f:
        json.dump(EMPTY_LOG, f, indent=2)
    print(f"Created: {log_path}")

    print(f"\nTest pitcher '{TEST_PITCHER_ID}' seeded successfully.")
    print(f"Telegram ID placeholder: {TEST_TELEGRAM_ID}")
    print(f"Update TEST_TELEGRAM_ID in this script with your real Telegram user ID to test.")


if __name__ == "__main__":
    main()
