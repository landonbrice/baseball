#!/usr/bin/env python3
"""Backfill: assign every pitcher a role-matched in-season program.

Dry-run by default — prints what it would do. Pass --apply to write.
Idempotent: skips pitchers who already have an active program.

Run dry:    python -m scripts.backfill_active_programs
Run apply:  python -m scripts.backfill_active_programs --apply
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import db, programs

# Match this to season-start so "Week 6 of 12" reads correctly on April 9.
DEFAULT_START_DATE = date(2026, 2, 23)


ROLE_TO_TEMPLATE = {
    "starter": "in_season_starter",
    "reliever": "in_season_short_relief",
    "long_relief": "in_season_long_relief",
    "short_relief": "in_season_short_relief",
}

# Hardcoded subrole overrides for pitchers whose pitching_profile.relief_role
# is not populated in DB. Source of truth: CLAUDE.md pitcher table.
LONG_RELIEF_PITCHER_IDS = {
    "pitcher_heron_001",    # Carter Heron — reliever (long)
    "pitcher_richert_001",  # Matthew Richert — reliever (long)
}


def template_for_pitcher(pitcher: dict) -> str:
    role = (pitcher.get("role") or "").lower()
    pid = pitcher.get("pitcher_id") or ""

    if role in ROLE_TO_TEMPLATE:
        # Reliever subtypes: check hardcoded overrides first, then pitching JSONB
        if role == "reliever":
            if pid in LONG_RELIEF_PITCHER_IDS:
                return "in_season_long_relief"
            pitching = pitcher.get("pitching_profile") or {}
            subrole = (pitching.get("relief_role") or "").lower().replace(" ", "_")
            if "long" in subrole:
                return "in_season_long_relief"
            if "short" in subrole:
                return "in_season_short_relief"
            # Default relievers to short relief
            return "in_season_short_relief"
        return ROLE_TO_TEMPLATE[role]
    return "in_season_starter"  # default fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE.isoformat())
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    print(f"Backfill mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Start date: {start_date.isoformat()}\n")

    pitchers = (
        db.get_client()
        .table("pitchers")
        .select("pitcher_id, name, role, pitching_profile")
        .execute()
        .data
        or []
    )
    if not pitchers:
        print("ERROR: no pitchers in DB")
        return 1

    actions = 0
    skipped = 0
    for pitcher in sorted(pitchers, key=lambda p: p["pitcher_id"]):
        pid = pitcher["pitcher_id"]
        existing = db.get_active_training_program(pid)
        if existing:
            print(f"  [SKIP]  {pid} ({pitcher.get('name')}) — already has active program {existing['id']}")
            skipped += 1
            continue
        template_id = template_for_pitcher(pitcher)
        print(f"  [{'WRITE' if args.apply else 'DRY  '}] {pid} ({pitcher.get('name')}) → {template_id}")
        if args.apply:
            new_id = programs.create_program_for_pitcher(
                pid, template_id, start_date, deactivate_existing=False
            )
            print(f"            created program id={new_id}")
        actions += 1

    print(f"\n{actions} pitchers to {'apply' if args.apply else 'backfill'}, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
