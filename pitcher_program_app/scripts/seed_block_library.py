"""Seed block_library with 3-4 throwing program templates.

Sources: data/templates/throwing_ramp_up.md, past_arm_programs/*.xlsx
Usage: python -m scripts.seed_block_library
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

BLOCKS = [
    {
        "block_template_id": "velocity_12wk_v1",
        "name": "Velocity Development Program",
        "description": "12-week progressive velocity program. Builds from base throwing through max-intent pulldowns. 3 throwing days per week.",
        "block_type": "throwing",
        "duration_days": 84,
        "source": "landon_starters.xlsx + throwing_ramp_up.md",
        "content": {
            "weeks": 12,
            "throws_per_week": 3,
            "rest_days_pattern": [3, 7],
            "phases": [
                {
                    "name": "Base Building",
                    "weeks": [1, 2, 3],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [40, 60],
                    "effort_pct": 50,
                    "intent_notes": "Build base. Groove mechanics. Light effort.",
                    "drills": ["high_pec_load_x10_at_30ft", "snap_snap_rocker_x5", "self_toss_x5"]
                },
                {
                    "name": "Distance Extension",
                    "weeks": [4, 5, 6],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft"],
                    "total_throws_range": [50, 66],
                    "effort_pct": 70,
                    "intent_notes": "Add distance progressively. Work back in at 60ft.",
                    "drills": ["qb_drop_back_50pct", "lateral_bound_50pct"]
                },
                {
                    "name": "Compression + Pulldowns",
                    "weeks": [7, 8, 9],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft", "120ft"],
                    "total_throws_range": [55, 70],
                    "effort_pct": 80,
                    "intent_notes": "80% on-a-line at 90/75. Introduce pulldowns at 105/90.",
                    "drills": ["compression_on_a_line", "pulldowns_at_105_90"]
                },
                {
                    "name": "Max Intent + Mound",
                    "weeks": [10, 11, 12],
                    "distances": ["full_progression", "mound_work"],
                    "total_throws_range": [60, 75],
                    "effort_pct": 90,
                    "intent_notes": "Full progression with pulldowns. Add mound work at 50ft progressing to 60.5ft.",
                    "drills": ["pulldowns_100pct", "mound_fastball_only"]
                }
            ],
            "post_session_recovery": "medium"
        }
    },
    {
        "block_template_id": "longtoss_ramp_6wk_v1",
        "name": "Long-Toss Ramp Up",
        "description": "6-week progressive throwing ramp-up. From 45ft to 120ft with structured drill progressions. Source: throwing_ramp_up.md.",
        "block_type": "throwing",
        "duration_days": 42,
        "source": "throwing_ramp_up.md",
        "content": {
            "weeks": 6,
            "throws_per_week": 3,
            "rest_days_pattern": [3, 7],
            "phases": [
                {
                    "name": "Week 1 — Base",
                    "weeks": [1],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [40, 50],
                    "effort_pct": 50,
                    "intent_notes": "Build base. Pre-throw: uphill wall, sock throws, high pec load at 30ft.",
                    "drills": ["high_pec_load_x10_at_30ft", "snap_snap_rocker_x5", "self_toss_x5"]
                },
                {
                    "name": "Week 2 — Add 90ft",
                    "weeks": [2],
                    "distances": ["45ft", "60ft", "75ft", "90ft"],
                    "total_throws_range": [45, 60],
                    "effort_pct": 60,
                    "intent_notes": "Add 90ft. Work back in at 60ft on days 2-3.",
                    "drills": ["figure_8_rocker_25pct", "half_kneel_start_25pct", "step_back_25pct"]
                },
                {
                    "name": "Week 3 — Add 105ft",
                    "weeks": [3],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft"],
                    "total_throws_range": [60, 66],
                    "effort_pct": 70,
                    "intent_notes": "Add 105ft. Work back in at 90/75/60ft.",
                    "drills": ["qb_drop_back_50pct", "lateral_bound_50pct"]
                },
                {
                    "name": "Weeks 4-6 — 120ft + Compression",
                    "weeks": [4, 5, 6],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft", "120ft"],
                    "total_throws_range": [48, 65],
                    "effort_pct": 80,
                    "intent_notes": "Add 120ft. Introduce 80% on-a-line compression at 90/75.",
                    "drills": ["compression_on_a_line"]
                }
            ],
            "post_session_recovery": "medium"
        }
    },
    {
        "block_template_id": "offseason_base_4wk_v1",
        "name": "Offseason Throwing Base",
        "description": "4-week light throwing program for early offseason. Maintains arm health without intensity. 2-3 days per week.",
        "block_type": "throwing",
        "duration_days": 28,
        "source": "starter_7day template + coaching knowledge",
        "content": {
            "weeks": 4,
            "throws_per_week": 2,
            "rest_days_pattern": [3, 4, 7],
            "phases": [
                {
                    "name": "Weeks 1-4 — Maintenance Catch",
                    "weeks": [1, 2, 3, 4],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [30, 40],
                    "effort_pct": 40,
                    "intent_notes": "Light catch play. Focus on feel and arm health. No intent.",
                    "drills": ["light_catch_play"]
                }
            ],
            "post_session_recovery": "light"
        }
    }
]


def seed():
    client = get_client()
    resp = client.table("block_library").upsert(
        BLOCKS, on_conflict="block_template_id"
    ).execute()
    print(f"Seeded {len(resp.data)} blocks into block_library")


if __name__ == "__main__":
    seed()
