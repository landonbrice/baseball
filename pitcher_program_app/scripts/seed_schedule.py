"""Seed team_games with UChicago 2026 spring schedule.

Usage: python -m scripts.seed_schedule
Idempotent — uses ON CONFLICT DO NOTHING on (team_id, game_date, is_doubleheader_g2).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

TEAM_ID = "uchicago_baseball"

# UChicago 2026 spring schedule — fill in from athletics page
# Format: (game_date, opponent, home_away, is_doubleheader_g2)
GAMES = [
    # March
    ("2026-03-07", "Wheaton", "away", False),
    ("2026-03-08", "Wheaton", "away", False),
    ("2026-03-14", "North Central", "home", False),
    ("2026-03-15", "North Central", "home", False),
    ("2026-03-21", "Wash U", "away", False),
    ("2026-03-22", "Wash U", "away", False),
    ("2026-03-28", "Case Western", "home", False),
    ("2026-03-29", "Case Western", "home", False),
    # April
    ("2026-04-04", "Emory", "away", False),
    ("2026-04-05", "Emory", "away", False),
    ("2026-04-11", "Carnegie Mellon", "home", False),
    ("2026-04-12", "Carnegie Mellon", "home", False),
    ("2026-04-18", "NYU", "home", False),
    ("2026-04-19", "NYU", "home", False),
    ("2026-04-25", "Brandeis", "away", False),
    ("2026-04-26", "Brandeis", "away", False),
    # May
    ("2026-05-02", "Rochester", "home", False),
    ("2026-05-03", "Rochester", "home", False),
    ("2026-05-09", "UAA Tournament", "away", False),
    ("2026-05-10", "UAA Tournament", "away", False),
]


def seed():
    client = get_client()
    rows = [
        {
            "team_id": TEAM_ID,
            "game_date": date,
            "opponent": opp,
            "home_away": ha,
            "is_doubleheader_g2": dh,
            "source": "manual",
            "status": "scheduled",
        }
        for date, opp, ha, dh in GAMES
    ]
    resp = client.table("team_games").upsert(
        rows,
        on_conflict="team_id,game_date,is_doubleheader_g2"
    ).execute()
    print(f"Seeded {len(resp.data)} games into team_games")


if __name__ == "__main__":
    seed()
