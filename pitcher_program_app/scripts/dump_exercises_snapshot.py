"""Program Engine Task 0.1 — dump the live `exercises` table to a JSON snapshot.

The snapshot at `tests/fixtures/exercises_snapshot.json` lets the alias audit
script (and any future offline tooling) work without Supabase credentials.

When the live `exercises.aliases` column is edited in Supabase, re-run this
script to keep the snapshot in sync.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python -m scripts.dump_exercises_snapshot

Exit codes:
    0 — wrote snapshot
    2 — Supabase connection / query failed
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


def main() -> int:
    try:
        from bot.services.db import get_exercises
    except Exception as exc:
        print(f"FAILED to import db client: {exc}", file=sys.stderr)
        return 2

    try:
        rows = get_exercises()
    except Exception as exc:
        print(f"FAILED Supabase query: {exc}", file=sys.stderr)
        print("  hint: requires SUPABASE_URL + SUPABASE_SERVICE_KEY in env", file=sys.stderr)
        return 2

    # Only keep what the alias index needs. Drops 14+ unrelated columns and
    # keeps the snapshot at a few hundred KB instead of MBs.
    trimmed = [
        {"id": r.get("id"), "name": r.get("name"), "aliases": r.get("aliases") or []}
        for r in rows
        if r.get("id")
    ]

    payload = {
        "_meta": {
            "captured_at": date.today().isoformat(),
            "source": "bot.services.db.get_exercises()",
            "row_count": len(trimmed),
            "regenerate_via": "python -m scripts.dump_exercises_snapshot (requires SUPABASE_URL + SUPABASE_SERVICE_KEY env)",
        },
        "rows": trimmed,
    }

    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "exercises_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {len(trimmed)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
