"""Mobility video rotation service.

Returns today's mobility videos based on a 10-week cycling program.
Each week has 4 videos (3 P/R + 1 targeted). The program cycles
endlessly — week 11 = week 1, etc.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge" / "mobility_videos.json"

_MOBILITY_CACHE = None


def _load_mobility_data() -> dict:
    global _MOBILITY_CACHE
    if _MOBILITY_CACHE is None:
        with open(DATA_FILE) as f:
            _MOBILITY_CACHE = json.load(f)
        logger.info("Mobility videos loaded: %d videos, %d weeks",
                     len(_MOBILITY_CACHE["videos"]),
                     len(_MOBILITY_CACHE["weekly_rotation"]))
    return _MOBILITY_CACHE


def get_today_mobility(anchor_date: date | None = None) -> dict:
    """Return today's mobility video(s).

    The 10-week program cycles based on ISO week number:
        current_week = (iso_week % 10) + 1  (1-indexed, cycles 1-10)

    Returns:
        {
            "week": 3,
            "videos": [
                {"id": "mob_009", "title": "P/R Routine G", "youtube_url": "...", "type": "P/R"},
                ...
            ]
        }
    """
    data = _load_mobility_data()
    today = anchor_date or date.today()
    iso_week = today.isocalendar()[1]
    cycle_week = (iso_week % 10) + 1  # 1-10

    week_data = None
    for w in data["weekly_rotation"]:
        if w["week"] == cycle_week:
            week_data = w
            break

    if not week_data:
        logger.warning("No mobility rotation found for cycle week %d", cycle_week)
        return {"week": cycle_week, "videos": []}

    # Pick 1 video per day: weekday mod number of slots
    slots = week_data["slots"]
    slot_index = today.weekday() % len(slots)  # Mon=0..Sun=6 → cycles through 4 slots
    vid_id = slots[slot_index]

    video_map = {v["id"]: v for v in data["videos"]}
    video = video_map.get(vid_id)
    if not video:
        return {"week": cycle_week, "videos": []}

    return {"week": cycle_week, "videos": [{
        "id": video["id"],
        "title": video["title"],
        "youtube_url": video["youtube_url"],
        "type": video["type"],
    }]}
