"""Plan 8 / A1 — saved_plans deprecation audit.

Prints a report of saved_plans rows created since the Plan 7 A15
deprecation logging landed (2026-04-30). Zero rows in the window means
the table is safe to drop (Plan 8 B1). Any rows means we have a caller
still writing — fix that first.

Usage:
    cd pitcher_program_app && PYTHONPATH=. python -m scripts.verify_saved_plans_deprecated [--since 2026-04-30]

Exit codes:
    0 — zero writes in the window (drop is safe)
    1 — non-zero writes (drop is NOT safe)
    2 — Supabase connection / query failed
"""
import argparse
import sys

DEFAULT_SINCE = "2026-04-30"  # Plan 7 A15 ship date


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help="ISO date — count rows where created_at >= this",
    )
    args = p.parse_args()

    try:
        from bot.services import db
    except Exception as exc:
        print(f"FAILED to import db client: {exc}", file=sys.stderr)
        return 2

    try:
        resp = (
            db.get_client().table("saved_plans")
            .select("plan_id, pitcher_id, plan_name, created_at")
            .gte("created_at", args.since)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        print(f"FAILED Supabase query: {exc}", file=sys.stderr)
        return 2

    rows = resp.data or []
    if not rows:
        print(f"OK — zero saved_plans writes since {args.since}.")
        print("Plan 8 B1 (drop migration) is SAFE to proceed.")
        return 0

    print(f"BLOCKED — found {len(rows)} saved_plans writes since {args.since}:")
    for r in rows[:20]:
        print(
            f"  - {r.get('created_at')} | pitcher={r.get('pitcher_id')} | "
            f"plan={r.get('plan_name') or '<no-name>'} | id={r.get('plan_id')}"
        )
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more")
    print("Find the caller(s) and remove the write path before B1.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
