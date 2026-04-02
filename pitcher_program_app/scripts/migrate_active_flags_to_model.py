"""One-time migration: copy active_flags rows into pitcher_training_model.

Safe to re-run (upserts). Does not delete active_flags data.

Usage:
    python -m scripts.migrate_active_flags_to_model [--dry-run]
"""

import argparse
import logging

from bot.services.db import get_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def migrate(dry_run: bool = False):
    sb = get_client()

    # Fetch all active_flags rows
    resp = sb.table("active_flags").select("*").execute()
    rows = resp.data or []
    log.info(f"Found {len(rows)} active_flags rows to migrate")

    if not rows:
        log.info("Nothing to migrate.")
        return

    for row in rows:
        pitcher_id = row.get("pitcher_id")
        if not pitcher_id:
            log.warning(f"Skipping row with no pitcher_id: {row}")
            continue

        model_row = {
            "pitcher_id": pitcher_id,
            "current_arm_feel": row.get("current_arm_feel"),
            "current_flag_level": row.get("current_flag_level"),
            "days_since_outing": row.get("days_since_outing", 0),
            "last_outing_date": row.get("last_outing_date"),
            "last_outing_pitches": row.get("last_outing_pitches"),
            "phase": row.get("phase"),
            "active_modifications": row.get("active_modifications", []),
            "next_outing_days": row.get("next_outing_days"),
            "grip_drop_reported": row.get("grip_drop_reported", False),
            # New fields initialized empty
            "working_weights": {},
            "exercise_preferences": {},
            "equipment_constraints": [],
            "recent_swap_history": [],
            "current_week_state": {},
        }

        if dry_run:
            log.info(f"  [DRY RUN] Would upsert {pitcher_id}: "
                     f"arm_feel={model_row['current_arm_feel']}, "
                     f"flag={model_row['current_flag_level']}, "
                     f"days_since={model_row['days_since_outing']}")
        else:
            sb.table("pitcher_training_model").upsert(
                model_row, on_conflict="pitcher_id"
            ).execute()
            log.info(f"  Migrated {pitcher_id}")

    log.info(f"Migration complete. {len(rows)} rows {'would be ' if dry_run else ''}migrated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
