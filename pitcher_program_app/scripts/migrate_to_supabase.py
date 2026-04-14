"""
migrate_to_supabase.py — Phase 1 Data Migration
Reads all existing JSON data from data/ and inserts into Supabase.

Usage:
    cd pitcher_program_app
    SUPABASE_URL=https://beyolhukpbvvoxvjnwtd.supabase.co \
    SUPABASE_SERVICE_KEY=your_key \
    python -m scripts.migrate_to_supabase

    Add --dry-run to preview without writing.
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

try:
    from supabase import create_client, Client
except ImportError:
    print("Install supabase-py first: pip install supabase")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PITCHERS_DIR = DATA_DIR / "pitchers"
TEMPLATES_DIR = DATA_DIR / "templates"
EXERCISE_LIBRARY = DATA_DIR / "knowledge" / "exercise_library.json"

PITCHER_DIRS = [
    d for d in PITCHERS_DIR.iterdir()
    if d.is_dir() and (d / "profile.json").exists()
]


def get_client(dry_run=False):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        if dry_run:
            return None
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
        sys.exit(1)
    return create_client(url, key)


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  WARN: Could not parse {path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------

def migrate_pitchers(sb: Client, dry_run: bool):
    """Migrate pitcher profiles. Returns list of migrated pitcher_ids."""
    migrated = []
    print(f"\n{'='*60}")
    print(f"PITCHERS — {len(PITCHER_DIRS)} found")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            print(f"  SKIP: {pitcher_dir.name} — no valid profile.json")
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)

        # Normalize role
        role = profile.get("role", "reliever")
        if role not in ("starter", "reliever"):
            # Handle variants like "short reliever", "long inning reliever"
            role = "reliever" if "reliever" in role.lower() else "starter"

        # Normalize throws
        throws = profile.get("throws")
        if throws and throws.lower() not in ("right", "left"):
            throws = "right"  # default

        row = {
            "pitcher_id": pitcher_id,
            "telegram_id": profile.get("telegram_id"),
            "telegram_username": profile.get("telegram_username"),
            "name": profile.get("name", pitcher_dir.name),
            "role": role,
            "rotation_length": profile.get("rotation_length"),
            "throws": throws.lower() if throws else None,
            "year": profile.get("year"),
            "physical_profile": profile.get("physical_profile", {}),
            "pitching_profile": profile.get("pitching_profile", {}),
            "current_training": profile.get("current_training", {}),
            "goals": profile.get("goals", {}),
            "preferences": profile.get("preferences", {}),
            "biometric_integration": profile.get("biometric_integration", {}),
        }

        print(f"  {pitcher_id}: {row['name']} ({row['role']}, {row['throws']})")

        if not dry_run:
            sb.table("pitchers").upsert(row, on_conflict="pitcher_id").execute()

        migrated.append(pitcher_id)

    print(f"\n  Total: {len(migrated)} pitchers")
    return migrated


def migrate_injury_history(sb: Client, dry_run: bool):
    """Migrate injury_history arrays from each pitcher's profile."""
    total = 0
    print(f"\n{'='*60}")
    print("INJURY HISTORY")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)
        injuries = profile.get("injury_history", [])
        if not injuries:
            continue

        print(f"  {pitcher_id}: {len(injuries)} injuries")

        for injury in injuries:
            row = {
                "pitcher_id": pitcher_id,
                "date": injury.get("date"),
                "area": injury.get("area"),
                "severity": injury.get("severity"),
                "description": injury.get("description"),
                "resolution": injury.get("resolution"),
                "ongoing_considerations": injury.get("ongoing_considerations"),
                "flag_level": injury.get("flag_level"),
                "red_flags": injury.get("red_flags", []),
            }
            total += 1

            if not dry_run:
                sb.table("injury_history").insert(row).execute()

    print(f"\n  Total: {total} injury records")


def migrate_active_flags(sb: Client, dry_run: bool):
    """DEPRECATED: active_flags table replaced by pitcher_training_model.

    Use scripts/migrate_active_flags_to_model.py instead.
    Kept for reference only.
    """
    total = 0
    print(f"\n{'='*60}")
    print("ACTIVE FLAGS")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)
        flags = profile.get("active_flags")
        if not flags:
            continue

        # Clamp arm_feel to 1-10
        arm_feel = flags.get("current_arm_feel")
        if arm_feel is not None:
            arm_feel = max(1, min(10, int(arm_feel)))

        # Normalize flag_level
        flag_level = flags.get("current_flag_level")
        if flag_level and flag_level not in ("green", "yellow", "red"):
            flag_level = "green"

        # Parse last_outing_date
        last_outing_date = flags.get("last_outing_date")
        if last_outing_date in (None, "null", ""):
            last_outing_date = None

        row = {
            "pitcher_id": pitcher_id,
            "current_arm_feel": arm_feel,
            "current_flag_level": flag_level,
            "last_outing_date": last_outing_date,
            "last_outing_pitches": flags.get("last_outing_pitches"),
            "days_since_outing": flags.get("days_since_outing"),
            "phase": flags.get("phase"),
            "active_modifications": flags.get("active_modifications", []),
            "next_outing_days": flags.get("next_outing_days"),
        }

        print(f"  {pitcher_id}: flag={flag_level}, arm_feel={arm_feel}")
        total += 1

        if not dry_run:
            sb.table("active_flags").upsert(row, on_conflict="pitcher_id").execute()

    print(f"\n  Total: {total} active flag records")


def migrate_daily_entries(sb: Client, dry_run: bool):
    """Migrate daily_log.json entries for each pitcher."""
    total = 0
    print(f"\n{'='*60}")
    print("DAILY ENTRIES")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)
        log = load_json(pitcher_dir / "daily_log.json")
        if not log:
            continue

        entries = log.get("entries", []) if isinstance(log, dict) else log
        if not entries:
            continue

        print(f"  {pitcher_id}: {len(entries)} entries")

        for entry in entries:
            date = entry.get("date")
            if not date:
                continue

            row = {
                "pitcher_id": pitcher_id,
                "date": date,
                "rotation_day": entry.get("rotation_day"),
                "days_since_outing": entry.get("days_since_outing"),
                "pre_training": entry.get("pre_training", {}),
                "plan_narrative": entry.get("plan_narrative"),
                "morning_brief": entry.get("morning_brief"),
                "plan_generated": entry.get("plan_generated", {}),
                "actual_logged": entry.get("actual_logged", {}),
                "bot_observations": entry.get("bot_observations", {}),
                "arm_care": entry.get("arm_care", {}),
                "lifting": entry.get("lifting", {}),
                "throwing": entry.get("throwing", {}),
                "notes": entry.get("notes", {}),
                "completed_exercises": entry.get("completed_exercises", []),
            }
            total += 1

            if not dry_run:
                sb.table("daily_entries").upsert(
                    row, on_conflict="pitcher_id,date"
                ).execute()

    print(f"\n  Total: {total} daily entries")


def migrate_exercises(sb: Client, dry_run: bool):
    """Migrate exercise_library.json."""
    print(f"\n{'='*60}")
    print("EXERCISES")
    print(f"{'='*60}")

    data = load_json(EXERCISE_LIBRARY)
    if not data:
        print("  SKIP: exercise_library.json not found")
        return

    exercises = data.get("exercises", []) if isinstance(data, dict) else data
    print(f"  Found {len(exercises)} exercises")

    for ex in exercises:
        row = {
            "id": ex.get("id"),
            "name": ex.get("name"),
            "slug": ex.get("slug", ex.get("id")),
            "aliases": ex.get("aliases", []),
            "category": ex.get("category"),
            "subcategory": ex.get("subcategory"),
            "muscles_primary": ex.get("muscles_primary", []),
            "muscles_secondary": ex.get("muscles_secondary", []),
            "pitching_relevance": ex.get("pitching_relevance"),
            "prescription": ex.get("prescription", {}),
            "rotation_day_usage": ex.get("rotation_day_usage", {}),
            "tags": ex.get("tags", []),
            "contraindications": ex.get("contraindications", []),
            "modification_flags": ex.get("modification_flags", {}),
            "youtube_url": ex.get("youtube_url"),
            "evidence_level": ex.get("evidence_level"),
            "source_notes": ex.get("source_notes"),
        }

        if not row["id"]:
            continue

        if not dry_run:
            sb.table("exercises").upsert(row, on_conflict="id").execute()

    print(f"  Migrated: {len(exercises)} exercises")


def migrate_templates(sb: Client, dry_run: bool):
    """Migrate template JSON files."""
    print(f"\n{'='*60}")
    print("TEMPLATES")
    print(f"{'='*60}")

    total = 0
    for template_file in sorted(TEMPLATES_DIR.glob("*.json")):
        data = load_json(template_file)
        if not data:
            continue

        template_id = data.get("template_id", template_file.stem)

        row = {
            "id": template_id,
            "name": data.get("name", template_file.stem),
            "role": data.get("role"),
            "rotation_length": data.get("rotation_length"),
            "description": data.get("description") or data.get("$description"),
            "goal": data.get("goal"),
            "duration_min": data.get("duration_min"),
            "days": data.get("days", {}),
            "sequence": data.get("sequence", []),
            "global_rules": data.get("global_rules", {}),
            "source_notes": data.get("source_notes"),
        }

        print(f"  {template_id}: {row['name']}")
        total += 1

        if not dry_run:
            sb.table("templates").upsert(row, on_conflict="id").execute()

    print(f"\n  Total: {total} templates")


def migrate_saved_plans(sb: Client, dry_run: bool):
    """Migrate saved_plans.json for each pitcher."""
    total = 0
    print(f"\n{'='*60}")
    print("SAVED PLANS")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)
        plans = load_json(pitcher_dir / "saved_plans.json")
        if not plans or (isinstance(plans, list) and len(plans) == 0):
            continue

        if isinstance(plans, list):
            plan_list = plans
        else:
            plan_list = [plans]

        print(f"  {pitcher_id}: {len(plan_list)} plans")

        for plan in plan_list:
            row = {
                "pitcher_id": pitcher_id,
                "plan_data": plan if isinstance(plan, dict) else {"raw": plan},
                "active": plan.get("active", False) if isinstance(plan, dict) else False,
                "date_created": plan.get("date_created") if isinstance(plan, dict) else None,
                "rotation_day": plan.get("rotation_day") if isinstance(plan, dict) else None,
                "template_used": plan.get("template_used") if isinstance(plan, dict) else None,
            }
            total += 1

            if not dry_run:
                sb.table("saved_plans").insert(row).execute()

    print(f"\n  Total: {total} saved plans")


def migrate_weekly_summaries(sb: Client, dry_run: bool):
    """Migrate weekly_summaries from pitcher profiles if present."""
    total = 0
    print(f"\n{'='*60}")
    print("WEEKLY SUMMARIES")
    print(f"{'='*60}")

    for pitcher_dir in sorted(PITCHER_DIRS):
        profile = load_json(pitcher_dir / "profile.json")
        if not profile:
            continue

        pitcher_id = profile.get("pitcher_id", pitcher_dir.name)
        summaries = profile.get("weekly_summaries", [])
        if not summaries:
            continue

        print(f"  {pitcher_id}: {len(summaries)} summaries")

        for s in summaries:
            week_start = s.get("week_start")
            if not week_start:
                continue

            row = {
                "pitcher_id": pitcher_id,
                "week_start": week_start,
                "summary": s if isinstance(s, dict) else {"raw": s},
            }
            total += 1

            if not dry_run:
                sb.table("weekly_summaries").upsert(
                    row, on_conflict="pitcher_id,week_start"
                ).execute()

    print(f"\n  Total: {total} weekly summaries")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Migrate JSON data to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.dry_run:
        print("\n*** DRY RUN — no data will be written ***\n")

    sb = get_client(dry_run=args.dry_run)

    print(f"Data directory: {DATA_DIR}")
    print(f"Pitcher directories: {len(PITCHER_DIRS)}")
    print(f"Supabase URL: {os.environ.get('SUPABASE_URL', 'NOT SET')}")

    # Order matters: pitchers first (FK parent), then children
    migrate_pitchers(sb, args.dry_run)
    migrate_injury_history(sb, args.dry_run)
    migrate_active_flags(sb, args.dry_run)
    migrate_daily_entries(sb, args.dry_run)
    migrate_exercises(sb, args.dry_run)
    migrate_templates(sb, args.dry_run)
    migrate_saved_plans(sb, args.dry_run)
    migrate_weekly_summaries(sb, args.dry_run)

    print(f"\n{'='*60}")
    if args.dry_run:
        print("DRY RUN COMPLETE — re-run without --dry-run to write data")
    else:
        print("MIGRATION COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
