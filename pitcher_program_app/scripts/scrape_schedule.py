"""Scrape UChicago baseball schedule from Sidearm Sports JSON-LD.

Usage:
    python -m scripts.scrape_schedule

Fetches https://athletics.uchicago.edu/sports/baseball/schedule, parses
JSON-LD SportsEvent objects, and upserts into the Supabase `schedule` table.
"""

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser

from dotenv import load_dotenv
load_dotenv()

import httpx

from bot.services.db import get_client

logger = logging.getLogger(__name__)

SCHEDULE_URL = "https://athletics.uchicago.edu/sports/baseball/schedule"
TEAM_NAME = "University of Chicago"


class _JSONLDExtractor(HTMLParser):
    """Extract JSON-LD script contents from HTML."""

    def __init__(self):
        super().__init__()
        self._in_jsonld = False
        self._buf = ""
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            attr_dict = dict(attrs)
            if attr_dict.get("type") == "application/ld+json":
                self._in_jsonld = True
                self._buf = ""

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf += data

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            if self._buf.strip():
                self.blocks.append(self._buf.strip())


def _parse_events(html: str) -> list[dict]:
    """Parse SportsEvent JSON-LD from HTML into game dicts."""
    extractor = _JSONLDExtractor()
    extractor.feed(html)

    events = []
    for block in extractor.blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "SportsEvent":
                events.append(item)

    games = []
    for ev in events:
        start_date = ev.get("startDate", "")
        if not start_date or len(start_date) < 10:
            continue

        game_date = start_date[:10]  # YYYY-MM-DD

        # Extract time
        start_time = None
        if len(start_date) > 10:
            try:
                dt = datetime.fromisoformat(start_date)
                start_time = dt.strftime("%-I:%M %p")
            except (ValueError, TypeError):
                pass

        # Determine opponent and home/away
        home_team = (ev.get("homeTeam") or {}).get("name", "")
        away_team = (ev.get("awayTeam") or {}).get("name", "")

        if TEAM_NAME.lower() in home_team.lower():
            opponent = away_team
            home_away = "home"
        elif TEAM_NAME.lower() in away_team.lower():
            opponent = home_team
            home_away = "away"
        else:
            continue  # Neither team is UChicago

        if not opponent:
            continue

        # Location
        loc = ev.get("location") or {}
        location = loc.get("name") or (loc.get("address") or {}).get("streetAddress")

        games.append({
            "game_date": game_date,
            "opponent": opponent.strip(),
            "home_away": home_away,
            "location": location,
            "start_time": start_time,
        })

    # Detect doubleheaders (same date + same opponent)
    date_opponent_counts = Counter((g["game_date"], g["opponent"]) for g in games)
    for g in games:
        g["is_doubleheader"] = date_opponent_counts[(g["game_date"], g["opponent"])] > 1

    return games


def scrape_and_store() -> int:
    """Fetch schedule, parse, and upsert into Supabase. Returns game count."""
    resp = httpx.get(SCHEDULE_URL, timeout=15, follow_redirects=True)
    resp.raise_for_status()

    games = _parse_events(resp.text)
    if not games:
        logger.warning("No games parsed from schedule page")
        return 0

    client = get_client()

    # Deduplicate on (game_date, opponent) — doubleheaders produce duplicates
    seen = {}
    for g in games:
        key = (g["game_date"], g["opponent"])
        if key not in seen:
            seen[key] = g
        else:
            seen[key]["is_doubleheader"] = True

    deduped = list(seen.values())
    for g in deduped:
        g["updated_at"] = datetime.utcnow().isoformat()

    # Upsert on (game_date, opponent) unique constraint
    client.table("schedule").upsert(
        deduped, on_conflict="game_date,opponent"
    ).execute()

    logger.info("Upserted %d games into schedule table", len(deduped))
    return len(deduped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = scrape_and_store()
    print(f"Done — {count} games upserted.")
