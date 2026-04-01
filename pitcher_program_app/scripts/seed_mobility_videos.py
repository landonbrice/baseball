"""
Seed mobility_videos and mobility_weekly_rotation tables from mobility_videos.json.

Usage:
    cd pitcher_program_app
    python -m scripts.seed_mobility_videos

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables (or a .env file).
Idempotent: uses upsert so it is safe to re-run.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    sys.exit(1)

DATA_FILE = Path(__file__).parent.parent / "data" / "knowledge" / "mobility_videos.json"


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    with open(DATA_FILE) as f:
        data = json.load(f)

    # --- Seed mobility_videos ---
    videos = [
        {
            "id": v["id"],
            "title": v["title"],
            "youtube_url": v["youtube_url"],
            "type": v["type"],
        }
        for v in data["videos"]
    ]

    result = supabase.table("mobility_videos").upsert(videos, on_conflict="id").execute()
    print(f"Upserted {len(videos)} videos into mobility_videos.")

    # --- Seed mobility_weekly_rotation ---
    rotation_rows = []
    for week_entry in data["weekly_rotation"]:
        week = week_entry["week"]
        for slot_index, video_id in enumerate(week_entry["slots"], start=1):
            rotation_rows.append({
                "week": week,
                "slot": slot_index,
                "video_id": video_id,
            })

    result = (
        supabase.table("mobility_weekly_rotation")
        .upsert(rotation_rows, on_conflict="week,slot")
        .execute()
    )
    print(f"Upserted {len(rotation_rows)} rows into mobility_weekly_rotation.")
    print("Done.")


if __name__ == "__main__":
    main()
