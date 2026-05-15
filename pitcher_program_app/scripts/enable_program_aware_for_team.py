"""Plan 8 / D1 — flip program_aware_plan_gen=true for every pitcher on a team.

Idempotent. Reads the roster from `pitchers` table filtered by team_id.
Prints a per-pitcher status line. Exit 0 on success, 1 if any pitcher failed.

Usage:
    python -m scripts.enable_program_aware_for_team [--team-id uchicago_baseball]
    python -m scripts.enable_program_aware_for_team --dry-run
    python -m scripts.enable_program_aware_for_team --revert        # set OFF instead of ON

Rollback per-pitcher (preferred for surgical fixes): use the admin endpoint
from Plan 8 A2 instead:
    curl -X POST -H "X-Guardian-Admin-Token: $TOKEN" \\
      https://baseball-production-9d28.up.railway.app/admin/program-flag/{pitcher_id}/off

Exit codes:
    0 — clean (all targets already in desired state or successfully flipped)
    1 — at least one pitcher failed, or no roster matched the team_id filter
    2 — Supabase connection / import failure (env var likely missing)
"""
import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--team-id",
        default="uchicago_baseball",
        help="Roster filter (pitchers.team_id)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing",
    )
    p.add_argument(
        "--revert",
        action="store_true",
        help="Set program_aware_plan_gen=False instead of True (team-wide rollback)",
    )
    args = p.parse_args()

    try:
        from bot.services import db
    except Exception as exc:
        print(f"FAILED to import db client: {exc}", file=sys.stderr)
        return 2

    target_value = not args.revert  # True for normal run, False for --revert
    verb = "ON" if target_value else "OFF"

    try:
        all_pitchers = db.list_pitchers()
    except Exception as exc:
        print(f"FAILED to list pitchers: {exc}", file=sys.stderr)
        return 2

    roster = [row for row in all_pitchers if row.get("team_id") == args.team_id]
    if not roster:
        print(f"No pitchers found for team_id={args.team_id!r}")
        return 1

    print(
        f"Setting program_aware_plan_gen={verb} for {len(roster)} pitchers "
        f"on team {args.team_id!r}"
        + (" (DRY RUN)" if args.dry_run else "")
    )
    print()

    failures: list[str] = []
    skipped = 0
    flipped = 0

    for pitcher in roster:
        pid = pitcher.get("pitcher_id")
        if not pid:
            continue
        try:
            current = db.get_feature_flag(pid, "program_aware_plan_gen")
        except Exception as exc:
            print(f"  {pid}: FAILED to read current flag — {exc}")
            failures.append(pid)
            continue

        if current is target_value:
            print(f"  {pid}: already {verb} — skip")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  {pid}: WOULD set {verb} (currently {current})")
            continue

        try:
            db.set_feature_flag(pid, "program_aware_plan_gen", target_value)
            print(f"  {pid}: set {verb}")
            flipped += 1
        except KeyError:
            print(f"  {pid}: FAILED — no pitcher_training_model row")
            failures.append(pid)
        except Exception as exc:
            print(f"  {pid}: FAILED — {exc}")
            failures.append(pid)

    print()
    if args.dry_run:
        print(f"DRY RUN — no writes. {len(roster)} pitchers checked.")
    else:
        print(
            f"Done. {flipped} flipped, {skipped} already {verb}, "
            f"{len(failures)} failed."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
