# Programs Tab + Periodization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Plans tab with a Programs tab that surfaces multi-week training programs, the UChicago game schedule, and self-reported throwing events. Ship the data scaffolding for off-season periodization without firing any of that logic for in-season pitchers.

**Architecture:** New `program_templates` and `training_programs` tables behind an `active_program_id` FK on `pitcher_training_model`. Daily plan generation gets a phase-aware gate in `_get_training_intent` that falls through to the existing legacy code path when `phase_type == in_season` (every current pitcher). Frontend: Programs.jsx rewrite with maroon hero, emoji-bubble week arc, navy schedule card, today detail card. Self-reported throws via both chat parsing and an explicit modal, both writing to `current_week_state.scheduled_throws[]`.

**Tech Stack:** Python 3.11 / FastAPI / supabase-py / React 18 + Vite / Postgres / Telegram Bot

**Spec:** `docs/superpowers/specs/2026-04-09-programs-tab-periodization-design.md`

**Critical guardrail:** The in-season code path must produce byte-identical plan generation output before and after this change. Phase 2 ends with a diff harness that proves it.

**No-test-framework note:** This codebase has zero pytest infrastructure. Verification uses one-off scripts (`scripts/verify_*.py`) that print expected output to stdout. The diff harness (`scripts/verify_plan_gen_unchanged.py`) is the critical safety net — it must be implemented and passing before any plan-generator code is modified.

---

## Phase 1 — Schemas, Templates, and Service Layer

Goal: All new data structures exist, the seed library populates `program_templates`, and `programs.py` can compute current phase from a program + date. Zero code paths in plan generation are touched. Backfill is dry-run only.

### Task 1.1: Migration SQL — new tables and FK

**Files:**
- Create: `pitcher_program_app/scripts/migrations/006_program_tables.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- Migration: Programs tab + periodization scaffolding
-- Adds program_templates (seed library) and training_programs (per-pitcher instances).
-- Adds pitcher_training_model.active_program_id FK.
-- Applied: 2026-04-09

CREATE TABLE IF NOT EXISTS program_templates (
  id                      TEXT PRIMARY KEY,
  name                    TEXT NOT NULL,
  role                    TEXT NOT NULL,           -- 'starter' | 'short_relief' | 'long_relief' | 'any'
  phase_type              TEXT NOT NULL,           -- 'in_season' | 'off_season' | 'pre_season' | 'return_to_throwing'
  rotation_length         INTEGER NOT NULL,
  default_total_weeks     INTEGER,
  description             TEXT,
  phases                  JSONB NOT NULL,
  rotation_template_keys  JSONB,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS training_programs (
  id                      BIGSERIAL PRIMARY KEY,
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  template_id             TEXT NOT NULL REFERENCES program_templates(id),
  name                    TEXT NOT NULL,
  start_date              DATE NOT NULL,
  end_date                DATE,
  total_weeks             INTEGER,
  phases_snapshot         JSONB NOT NULL,
  deactivated_at          TIMESTAMPTZ,
  deactivation_reason     TEXT,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_training_programs_pitcher
  ON training_programs(pitcher_id);

CREATE INDEX IF NOT EXISTS idx_training_programs_active
  ON training_programs(pitcher_id, deactivated_at)
  WHERE deactivated_at IS NULL;

ALTER TABLE pitcher_training_model
  ADD COLUMN IF NOT EXISTS active_program_id BIGINT REFERENCES training_programs(id);
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Use the Supabase MCP `apply_migration` tool with name `006_program_tables` and the SQL above. Note: do NOT run this as `execute_sql` — migrations should be tracked in `supabase_migrations.schema_migrations`.

- [ ] **Step 3: Verify tables exist**

Use Supabase MCP `list_tables` and confirm `program_templates`, `training_programs` appear, and that `pitcher_training_model` has the new `active_program_id` column.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/scripts/migrations/006_program_tables.sql
git commit -m "Add migration 006: program_templates + training_programs tables"
```

---

### Task 1.2: Seed template JSON files

**Files:**
- Create: `pitcher_program_app/data/program_templates/in_season_starter.json`
- Create: `pitcher_program_app/data/program_templates/in_season_short_relief.json`
- Create: `pitcher_program_app/data/program_templates/in_season_long_relief.json`
- Create: `pitcher_program_app/data/program_templates/return_to_throwing.json`

- [ ] **Step 1: Write `in_season_starter.json`**

```json
{
  "id": "in_season_starter",
  "name": "In-Season Starter Protocol",
  "role": "starter",
  "phase_type": "in_season",
  "rotation_length": 7,
  "default_total_weeks": 12,
  "description": "7-day rotation for in-season starting pitchers. Phase is descriptive only; daily plan generation continues to use rotation day + triage.",
  "phases": [
    {
      "phase_id": "in_season_main",
      "name": "Maintenance",
      "phase_type": "in_season",
      "week_count": 12,
      "default_training_intent": null,
      "microcycle": null
    }
  ],
  "rotation_template_keys": ["starter_7day"]
}
```

- [ ] **Step 2: Write `in_season_short_relief.json`**

```json
{
  "id": "in_season_short_relief",
  "name": "In-Season Short Relief Protocol",
  "role": "short_relief",
  "phase_type": "in_season",
  "rotation_length": 3,
  "default_total_weeks": 12,
  "description": "Flexible 3-day cycle for short relievers. Anchored to last appearance, not calendar.",
  "phases": [
    {
      "phase_id": "in_season_main",
      "name": "Maintenance",
      "phase_type": "in_season",
      "week_count": 12,
      "default_training_intent": null,
      "microcycle": null
    }
  ],
  "rotation_template_keys": ["reliever_flexible"]
}
```

- [ ] **Step 3: Write `in_season_long_relief.json`**

```json
{
  "id": "in_season_long_relief",
  "name": "In-Season Long Relief Protocol",
  "role": "long_relief",
  "phase_type": "in_season",
  "rotation_length": 4,
  "default_total_weeks": 12,
  "description": "4-day cycle for multi-inning relievers. Slightly longer recovery window than short relief.",
  "phases": [
    {
      "phase_id": "in_season_main",
      "name": "Maintenance",
      "phase_type": "in_season",
      "week_count": 12,
      "default_training_intent": null,
      "microcycle": null
    }
  ],
  "rotation_template_keys": ["reliever_flexible"]
}
```

- [ ] **Step 4: Write `return_to_throwing.json`**

```json
{
  "id": "return_to_throwing",
  "name": "Return to Throwing",
  "role": "any",
  "phase_type": "return_to_throwing",
  "rotation_length": 7,
  "default_total_weeks": 6,
  "description": "Six-week ramp for pitchers returning from injury. Phase progression drives training_intent. Not assigned to any pitcher in v1; coach must swap a pitcher to it explicitly.",
  "phases": [
    {
      "phase_id": "rtt_acclimation",
      "name": "Acclimation",
      "phase_type": "return_to_throwing",
      "week_count": 2,
      "default_training_intent": "endurance",
      "microcycle": null
    },
    {
      "phase_id": "rtt_build",
      "name": "Build",
      "phase_type": "return_to_throwing",
      "week_count": 2,
      "default_training_intent": "hypertrophy",
      "microcycle": null
    },
    {
      "phase_id": "rtt_intent",
      "name": "Intent",
      "phase_type": "return_to_throwing",
      "week_count": 2,
      "default_training_intent": "strength",
      "microcycle": null
    }
  ],
  "rotation_template_keys": ["starter_7day"]
}
```

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/data/program_templates/
git commit -m "Add seed JSON for 4 program templates (in-season starter/relief, RTT)"
```

---

### Task 1.3: `programs.py` — `compute_current_phase` (pure function)

**Files:**
- Create: `pitcher_program_app/bot/services/programs.py`

- [ ] **Step 1: Write the module skeleton with `compute_current_phase`**

```python
"""Training program service. Pure functions + thin DB wrappers.

A "program" is a multi-week training arc with one or more phases. Each pitcher
has zero or one active program at a time, tracked via
pitcher_training_model.active_program_id.

This module is responsible for:
  - computing the current phase from a program + date (pure)
  - creating, listing, deactivating training_programs rows (DB)
  - loading active program + phase state for a pitcher

It does NOT touch plan generation directly. plan_generator.py reads
phase state from current_week_state.phase, which weekly_model writes.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from bot.services import db


def compute_current_phase(program: dict, as_of: Optional[date] = None) -> dict:
    """Walk a program's phases_snapshot to determine current phase + week.

    Args:
        program: dict with keys 'start_date' (date or ISO str), 'phases_snapshot' (list).
        as_of: date to compute against. Defaults to today (Chicago tz at the call site).

    Returns:
        dict matching current_week_state.phase shape:
          {
            "phase_id": str,
            "name": str,
            "phase_type": str,
            "week_in_phase": int,           # 1-indexed
            "week_in_program": int,         # 1-indexed
            "training_intent": Optional[str],
            "is_past_end": bool,            # True if as_of is past the last phase
          }

    Pure function — no DB, no clock. Easy to unit test against fixed dates.
    """
    if as_of is None:
        as_of = date.today()

    start_date = program["start_date"]
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    phases = program.get("phases_snapshot") or []
    if not phases:
        return {
            "phase_id": None,
            "name": "Unknown",
            "phase_type": None,
            "week_in_phase": 0,
            "week_in_program": 0,
            "training_intent": None,
            "is_past_end": False,
        }

    days_since_start = (as_of - start_date).days
    if days_since_start < 0:
        # Program starts in the future. Treat as week 1 of phase 1.
        first = phases[0]
        return {
            "phase_id": first["phase_id"],
            "name": first["name"],
            "phase_type": first["phase_type"],
            "week_in_phase": 1,
            "week_in_program": 1,
            "training_intent": first.get("default_training_intent"),
            "is_past_end": False,
        }

    week_in_program = (days_since_start // 7) + 1

    cumulative_weeks = 0
    for phase in phases:
        phase_weeks = phase.get("week_count", 0)
        if week_in_program <= cumulative_weeks + phase_weeks:
            week_in_phase = week_in_program - cumulative_weeks
            intent = _resolve_phase_intent(phase, week_in_phase)
            return {
                "phase_id": phase["phase_id"],
                "name": phase["name"],
                "phase_type": phase["phase_type"],
                "week_in_phase": week_in_phase,
                "week_in_program": week_in_program,
                "training_intent": intent,
                "is_past_end": False,
            }
        cumulative_weeks += phase_weeks

    # Past the last phase — clamp to final phase, mark as past end
    last = phases[-1]
    return {
        "phase_id": last["phase_id"],
        "name": last["name"],
        "phase_type": last["phase_type"],
        "week_in_phase": last.get("week_count", 0),
        "week_in_program": cumulative_weeks,
        "training_intent": last.get("default_training_intent"),
        "is_past_end": True,
    }


def _resolve_phase_intent(phase: dict, week_in_phase: int) -> Optional[str]:
    """Pick the training intent for a given week within a phase.

    Microcycle (if present) overrides default. In v1 this is structurally
    complete but unreachable for in-season pitchers.
    """
    microcycle = phase.get("microcycle")
    if microcycle:
        for week_def in microcycle:
            if week_def.get("week") == week_in_phase:
                return week_def.get("training_intent")
    return phase.get("default_training_intent")
```

- [ ] **Step 2: Write the verification script**

Create `pitcher_program_app/scripts/verify_compute_current_phase.py`:

```python
#!/usr/bin/env python3
"""Verification: compute_current_phase against fixed dates.

Prints PASS/FAIL for each case. Exits non-zero if any fail.
Run: python -m scripts.verify_compute_current_phase
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services.programs import compute_current_phase


IN_SEASON_PROGRAM = {
    "start_date": "2026-02-15",
    "phases_snapshot": [
        {
            "phase_id": "in_season_main",
            "name": "Maintenance",
            "phase_type": "in_season",
            "week_count": 12,
            "default_training_intent": None,
            "microcycle": None,
        }
    ],
}

RTT_PROGRAM = {
    "start_date": "2026-04-01",
    "phases_snapshot": [
        {"phase_id": "rtt_acclimation", "name": "Acclimation", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "endurance", "microcycle": None},
        {"phase_id": "rtt_build", "name": "Build", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "hypertrophy", "microcycle": None},
        {"phase_id": "rtt_intent", "name": "Intent", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "strength", "microcycle": None},
    ],
}

CASES = [
    # (label, program, as_of, expected_phase_id, expected_week_in_phase, expected_week_in_program, expected_intent)
    ("In-season week 1 (start day)",       IN_SEASON_PROGRAM, date(2026, 2, 15), "in_season_main", 1, 1, None),
    ("In-season week 6",                   IN_SEASON_PROGRAM, date(2026, 3, 22), "in_season_main", 6, 6, None),
    ("In-season past end (week 13)",       IN_SEASON_PROGRAM, date(2026, 5, 10), "in_season_main", 12, 12, None),
    ("In-season before start",             IN_SEASON_PROGRAM, date(2026, 2, 1),  "in_season_main", 1, 1, None),
    ("RTT week 1 (acclimation start)",     RTT_PROGRAM,       date(2026, 4, 1),  "rtt_acclimation", 1, 1, "endurance"),
    ("RTT week 2 (acclimation end)",       RTT_PROGRAM,       date(2026, 4, 7),  "rtt_acclimation", 2, 2, "endurance"),
    ("RTT week 3 (build start)",           RTT_PROGRAM,       date(2026, 4, 15), "rtt_build", 1, 3, "hypertrophy"),
    ("RTT week 5 (intent start)",          RTT_PROGRAM,       date(2026, 4, 29), "rtt_intent", 1, 5, "strength"),
    ("RTT past end",                       RTT_PROGRAM,       date(2026, 6, 1),  "rtt_intent", 2, 6, "strength"),
]


def main() -> int:
    fails = 0
    for label, program, as_of, exp_pid, exp_wip, exp_wprog, exp_intent in CASES:
        result = compute_current_phase(program, as_of=as_of)
        ok = (
            result["phase_id"] == exp_pid
            and result["week_in_phase"] == exp_wip
            and result["week_in_program"] == exp_wprog
            and result["training_intent"] == exp_intent
        )
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}: got phase={result['phase_id']} wip={result['week_in_phase']} wprog={result['week_in_program']} intent={result['training_intent']}")
        if not ok:
            print(f"           expected phase={exp_pid} wip={exp_wip} wprog={exp_wprog} intent={exp_intent}")
            fails += 1

    print(f"\n{len(CASES) - fails}/{len(CASES)} cases passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run verification**

```bash
cd pitcher_program_app && python -m scripts.verify_compute_current_phase
```

Expected: `9/9 cases passed`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/programs.py pitcher_program_app/scripts/verify_compute_current_phase.py
git commit -m "Add programs.compute_current_phase + verification harness"
```

---

### Task 1.4: `programs.py` — DB wrappers

**Files:**
- Modify: `pitcher_program_app/bot/services/programs.py`
- Modify: `pitcher_program_app/bot/services/db.py`

- [ ] **Step 1: Add CRUD functions to `db.py`**

Append to `pitcher_program_app/bot/services/db.py`:

```python
# === Program templates + training programs ===

def get_program_template(template_id: str) -> Optional[dict]:
    """Load a program template by id, or None if not found."""
    resp = (
        get_client()
        .table("program_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_program_templates() -> list[dict]:
    """All program templates, ordered by id."""
    resp = (
        get_client()
        .table("program_templates")
        .select("*")
        .order("id")
        .execute()
    )
    return resp.data or []


def upsert_program_template(template: dict) -> None:
    """Insert or update a template by id."""
    get_client().table("program_templates").upsert(template, on_conflict="id").execute()


def insert_training_program(row: dict) -> int:
    """Insert a training_programs row, returning the new id."""
    resp = get_client().table("training_programs").insert(row).execute()
    return resp.data[0]["id"]


def get_training_program(program_id: int) -> Optional[dict]:
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("id", program_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_active_training_program(pitcher_id: str) -> Optional[dict]:
    """Return the pitcher's currently active program (deactivated_at IS NULL)."""
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .is_("deactivated_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_training_programs_for_pitcher(pitcher_id: str) -> list[dict]:
    """All programs for a pitcher, newest first."""
    resp = (
        get_client()
        .table("training_programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def deactivate_training_program(program_id: int, reason: str) -> None:
    from datetime import datetime, timezone
    get_client().table("training_programs").update(
        {
            "deactivated_at": datetime.now(timezone.utc).isoformat(),
            "deactivation_reason": reason,
        }
    ).eq("id", program_id).execute()


def set_active_program_id(pitcher_id: str, program_id: Optional[int]) -> None:
    get_client().table("pitcher_training_model").update(
        {"active_program_id": program_id}
    ).eq("pitcher_id", pitcher_id).execute()
```

If `Optional` is not yet imported at the top of `db.py`, add `from typing import Optional`.

- [ ] **Step 2: Add `programs.py` orchestration functions**

Append to `pitcher_program_app/bot/services/programs.py`:

```python
def create_program_for_pitcher(
    pitcher_id: str,
    template_id: str,
    start_date: date,
    *,
    deactivate_existing: bool = True,
    deactivation_reason: str = "switched",
) -> int:
    """Instantiate a training_programs row from a template, set as active.

    Returns the new program id.
    """
    template = db.get_program_template(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")

    if deactivate_existing:
        existing = db.get_active_training_program(pitcher_id)
        if existing:
            db.deactivate_training_program(existing["id"], deactivation_reason)

    row = {
        "pitcher_id": pitcher_id,
        "template_id": template_id,
        "name": template["name"],
        "start_date": start_date.isoformat(),
        "total_weeks": template.get("default_total_weeks"),
        "phases_snapshot": template["phases"],
    }
    new_id = db.insert_training_program(row)
    db.set_active_program_id(pitcher_id, new_id)
    return new_id


def get_active_program(pitcher_id: str) -> Optional[dict]:
    """Returns the active program dict, or None."""
    return db.get_active_training_program(pitcher_id)


def list_program_history(pitcher_id: str) -> list[dict]:
    """All programs for a pitcher, newest first, with computed phase for the active one."""
    rows = db.list_training_programs_for_pitcher(pitcher_id)
    for row in rows:
        if row.get("deactivated_at") is None:
            row["_current_phase"] = compute_current_phase(row)
    return rows


def deactivate_program(program_id: int, reason: str) -> None:
    db.deactivate_training_program(program_id, reason)
```

- [ ] **Step 3: Verify imports compile**

```bash
cd pitcher_program_app && python -c "from bot.services import programs; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/programs.py pitcher_program_app/bot/services/db.py
git commit -m "Add programs.py orchestration + db.py CRUD for training_programs"
```

---

### Task 1.5: Seed templates into Supabase

**Files:**
- Create: `pitcher_program_app/scripts/seed_program_templates.py`

- [ ] **Step 1: Write the seed script**

```python
#!/usr/bin/env python3
"""Seed program_templates from data/program_templates/*.json.

Idempotent — safe to re-run. Uses upsert on id.
Run: python -m scripts.seed_program_templates
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import db


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "program_templates",
)


def main() -> int:
    if not os.path.isdir(TEMPLATES_DIR):
        print(f"ERROR: templates dir not found: {TEMPLATES_DIR}")
        return 1

    files = sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".json"))
    if not files:
        print(f"ERROR: no .json files in {TEMPLATES_DIR}")
        return 1

    for fname in files:
        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path) as fp:
            template = json.load(fp)
        required = {"id", "name", "role", "phase_type", "rotation_length", "phases"}
        missing = required - set(template.keys())
        if missing:
            print(f"  [SKIP] {fname}: missing fields {missing}")
            continue
        db.upsert_program_template(template)
        print(f"  [OK]   upserted {template['id']} ({template['name']})")

    print(f"\nSeeded {len(files)} templates from {TEMPLATES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the seed**

```bash
cd pitcher_program_app && python -m scripts.seed_program_templates
```

Expected: 4 `[OK]` lines, one per template, ending with `Seeded 4 templates`.

- [ ] **Step 3: Verify in DB via Supabase MCP**

Use `execute_sql` with `SELECT id, name, role, phase_type FROM program_templates ORDER BY id;`. Confirm all 4 rows appear.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/scripts/seed_program_templates.py
git commit -m "Add seed_program_templates script"
```

---

### Task 1.6: Diff harness — plan generator behavior baseline

**Files:**
- Create: `pitcher_program_app/scripts/verify_plan_gen_unchanged.py`

This script captures plan generation output for every active pitcher and compares it against a baseline snapshot. It runs twice in this plan: once now (to capture the baseline) and once after the phase gate is added (to verify zero behavioral change).

- [ ] **Step 1: Write the harness**

```python
#!/usr/bin/env python3
"""Diff test for plan generation — proves the in-season code path is byte-identical
before and after the periodization phase gate is added.

Usage:
  python -m scripts.verify_plan_gen_unchanged --capture   # capture baseline
  python -m scripts.verify_plan_gen_unchanged             # diff against baseline

The baseline file lives at scripts/.plan_gen_baseline.json (gitignored).
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import db
from bot.services.plan_generator import _get_training_intent

# Lock the random seeds and "today" so the diff is deterministic
FIXED_TODAY = date(2026, 4, 9)

BASELINE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".plan_gen_baseline.json",
)


def fingerprint_pitcher(pitcher_id: str) -> dict:
    """Capture the inputs and outputs of _get_training_intent for a pitcher.

    We probe the function across all rotation days and both flag levels —
    that exercises every branch of the in-season legacy code path.
    """
    fp = {"pitcher_id": pitcher_id, "intents": {}}
    for rotation_day in range(0, 8):
        for flag in ("green", "yellow", "red"):
            triage = {"flag_level": flag}
            try:
                intent = _get_training_intent(rotation_day, triage)
            except Exception as exc:
                intent = f"ERROR:{type(exc).__name__}:{exc}"
            fp["intents"][f"d{rotation_day}_{flag}"] = intent
    return fp


def list_active_pitchers() -> list[str]:
    resp = db.get_client().table("pitchers").select("pitcher_id").execute()
    return sorted(row["pitcher_id"] for row in (resp.data or []))


def capture(out_path: str) -> int:
    pitcher_ids = list_active_pitchers()
    if not pitcher_ids:
        print("ERROR: no pitchers found in DB")
        return 1
    fps = [fingerprint_pitcher(pid) for pid in pitcher_ids]
    digest = hashlib.sha256(json.dumps(fps, sort_keys=True).encode()).hexdigest()
    with open(out_path, "w") as fp:
        json.dump({"digest": digest, "fingerprints": fps}, fp, indent=2)
    print(f"Captured baseline for {len(pitcher_ids)} pitchers → {out_path}")
    print(f"Digest: {digest}")
    return 0


def diff(baseline_path: str) -> int:
    if not os.path.exists(baseline_path):
        print(f"ERROR: baseline missing at {baseline_path}. Run with --capture first.")
        return 1
    with open(baseline_path) as fp:
        baseline = json.load(fp)
    expected = baseline["fingerprints"]

    pitcher_ids = list_active_pitchers()
    actual = [fingerprint_pitcher(pid) for pid in pitcher_ids]

    actual_digest = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    if actual_digest == baseline["digest"]:
        print(f"PASS — plan generation byte-identical for {len(pitcher_ids)} pitchers")
        print(f"Digest: {actual_digest}")
        return 0

    print(f"FAIL — plan generation drifted")
    print(f"  Expected digest: {baseline['digest']}")
    print(f"  Actual digest:   {actual_digest}")

    expected_by_id = {fp["pitcher_id"]: fp for fp in expected}
    for fp in actual:
        exp = expected_by_id.get(fp["pitcher_id"])
        if not exp:
            print(f"  NEW pitcher (not in baseline): {fp['pitcher_id']}")
            continue
        for key, value in fp["intents"].items():
            if exp["intents"].get(key) != value:
                print(f"  {fp['pitcher_id']} {key}: was {exp['intents'].get(key)!r} now {value!r}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="capture baseline instead of diffing")
    args = parser.parse_args()
    if args.capture:
        return capture(BASELINE_PATH)
    return diff(BASELINE_PATH)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Add `.plan_gen_baseline.json` to gitignore**

```bash
echo "pitcher_program_app/scripts/.plan_gen_baseline.json" >> .gitignore
```

- [ ] **Step 3: Capture the baseline**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged --capture
```

Expected: `Captured baseline for N pitchers` (N = current count of active pitchers, ~12).

- [ ] **Step 4: Run the diff to confirm it matches itself**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: `PASS — plan generation byte-identical for N pitchers`.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/verify_plan_gen_unchanged.py .gitignore
git commit -m "Add plan generator diff harness — captures baseline for in-season pitchers"
```

---

### Task 1.7: Backfill script (dry-run mode)

**Files:**
- Create: `pitcher_program_app/scripts/backfill_active_programs.py`

- [ ] **Step 1: Write the backfill script**

```python
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


def template_for_pitcher(pitcher: dict) -> str:
    role = (pitcher.get("role") or "").lower()
    if role in ROLE_TO_TEMPLATE:
        return ROLE_TO_TEMPLATE[role]
    if role == "reliever":
        # Reliever subtypes may live in pitching JSONB
        pitching = pitcher.get("pitching") or {}
        subrole = (pitching.get("relief_role") or "").lower()
        if subrole in ROLE_TO_TEMPLATE:
            return ROLE_TO_TEMPLATE[subrole]
    return "in_season_starter"  # default fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE.isoformat())
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    print(f"Backfill mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Start date: {start_date.isoformat()}\n")

    pitchers = db.get_client().table("pitchers").select("pitcher_id, name, role, pitching").execute().data or []
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
```

- [ ] **Step 2: Run dry-run**

```bash
cd pitcher_program_app && python -m scripts.backfill_active_programs
```

Expected: ~12 `[DRY]` lines, one per pitcher with the correct template assignment, ending with `12 pitchers to backfill, 0 skipped`. **Eyeball every pitcher's template assignment** — Russell, Kwinter, Benner, Brice → starter; Hartrick, Kamat, Lazar, Reed, Sosna, Wilson → short_relief; Heron, Richert → long_relief.

- [ ] **Step 3: Apply the backfill**

```bash
cd pitcher_program_app && python -m scripts.backfill_active_programs --apply
```

Expected: same output as dry-run but with `[WRITE]` and `created program id=N`.

- [ ] **Step 4: Verify in DB**

Use Supabase MCP `execute_sql`:
```sql
SELECT p.pitcher_id, p.name, tp.template_id, tp.start_date, ptm.active_program_id
FROM pitchers p
LEFT JOIN training_programs tp ON tp.pitcher_id = p.pitcher_id AND tp.deactivated_at IS NULL
LEFT JOIN pitcher_training_model ptm ON ptm.pitcher_id = p.pitcher_id
ORDER BY p.pitcher_id;
```

Every row should show a template_id and matching `active_program_id`.

- [ ] **Step 5: Re-run diff harness — must still pass (no plan-gen code touched yet)**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: `PASS — plan generation byte-identical for N pitchers`.

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/scripts/backfill_active_programs.py
git commit -m "Add backfill_active_programs script + run against all current pitchers"
```

---

## Phase 2 — Plan Generator Phase Gate (Critical Guardrail)

Goal: Add the phase-aware kwarg to `_get_training_intent` with a gate that falls through to the legacy path for in-season pitchers. Diff harness must pass byte-identical after this phase.

### Task 2.1: Add the phase gate to `_get_training_intent`

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py:829`

- [ ] **Step 1: Replace the function body**

Find `def _get_training_intent(rotation_day: int, triage_result: dict) -> str:` at line 829 and replace the entire function with:

```python
def _get_training_intent(
    rotation_day: int,
    triage_result: dict,
    *,
    pitcher_model: dict | None = None,
) -> str:
    """Map rotation day + triage to training intent (prescription phase).

    Phase-aware gate (added 2026-04-09): if the pitcher has an active program
    whose phase_type is NOT in_season, consult the phase's training_intent.
    For in-season pitchers (every current UChicago pitcher), this function
    returns from the legacy code path below — byte-identical to pre-phase-gate
    behavior. Verified by scripts/verify_plan_gen_unchanged.py.
    """
    # === Phase gate ===
    if pitcher_model:
        phase_state = (pitcher_model.get("current_week_state") or {}).get("phase") or {}
        phase_type = phase_state.get("phase_type")
        if phase_type and phase_type != "in_season":
            phase_intent = phase_state.get("training_intent")
            if phase_intent:
                return _blend_phase_with_rotation(phase_intent, rotation_day, triage_result)

    # === Legacy in-season path — UNCHANGED from pre-2026-04-09 ===
    flag = triage_result.get("flag_level", "green")
    if flag in ("red", "yellow"):
        return "endurance"
    day_intent = {
        1: "endurance",
        2: "power",
        3: "strength",
        4: "strength",
        5: "endurance",
    }
    return day_intent.get(rotation_day, "strength")


def _blend_phase_with_rotation(
    phase_intent: str,
    rotation_day: int,
    triage_result: dict,
) -> str:
    """Blend phase intent with rotation-day context. v1 stub: phase wins.

    Triage flags still suppress to endurance — safety first.
    Full blending logic ships in the off-season activation spec.
    """
    flag = triage_result.get("flag_level", "green")
    if flag in ("red", "yellow"):
        return "endurance"
    return phase_intent
```

- [ ] **Step 2: Run diff harness — must still pass byte-identical**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: `PASS — plan generation byte-identical for N pitchers`. The diff harness calls `_get_training_intent(rotation_day, triage)` *without* the new kwarg, exercising the legacy path. This proves the existing call sites are untouched in behavior.

If this fails, STOP. Do not proceed. Inspect the diff output, fix the legacy path drift, re-run.

- [ ] **Step 3: Audit existing call sites**

```bash
cd pitcher_program_app && grep -rn "_get_training_intent" bot/ api/
```

Confirm every call site uses positional args `(rotation_day, triage_result)` only — none yet pass `pitcher_model`. Existing callers must work unchanged.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/plan_generator.py
git commit -m "Add phase-aware gate to _get_training_intent — in-season unchanged"
```

---

## Phase 3 — weekly_model Extension: Phase Recompute + Scheduled Throws

Goal: `current_week_state.phase` is recomputed on every check-in, and `scheduled_throws[]` can be appended/pruned. No plan-gen behavior change.

### Task 3.1: Add `update_phase_state` and `add_scheduled_throw` to weekly_model

**Files:**
- Modify: `pitcher_program_app/bot/services/weekly_model.py`

- [ ] **Step 1: Add the new functions**

Append to `pitcher_program_app/bot/services/weekly_model.py`:

```python
from datetime import date, datetime, timedelta, timezone
from bot.services import db
from bot.services.programs import compute_current_phase, get_active_program

SCHEDULED_THROW_TYPES = {"catch", "long_toss", "bullpen", "side", "game"}
SCHEDULED_THROW_RETENTION_DAYS = 14


def update_phase_state(pitcher_id: str, as_of: date | None = None) -> dict | None:
    """Recompute current_week_state.phase from the active program. Returns the new phase dict.

    Called from checkin_service after each check-in. Safe to call when no active program
    exists — returns None and does not write.
    """
    program = get_active_program(pitcher_id)
    if not program:
        return None
    phase = compute_current_phase(program, as_of=as_of or date.today())

    # Read-modify-write current_week_state
    model = db.get_client().table("pitcher_training_model").select("current_week_state").eq("pitcher_id", pitcher_id).execute()
    if not model.data:
        return None
    state = model.data[0].get("current_week_state") or {}
    state["phase"] = phase
    db.get_client().table("pitcher_training_model").update({"current_week_state": state}).eq("pitcher_id", pitcher_id).execute()
    return phase


def add_scheduled_throw(pitcher_id: str, throw: dict) -> dict:
    """Append a scheduled throw to current_week_state.scheduled_throws.

    `throw` must contain: date (ISO str), type (one of SCHEDULED_THROW_TYPES),
    source ('chat'|'button'|'template'|'scraper'). Optional: notes.

    Auto-prunes entries older than 14 days. Returns the appended throw with
    a generated id and logged_at.
    """
    if throw.get("type") not in SCHEDULED_THROW_TYPES:
        raise ValueError(f"Invalid throw type: {throw.get('type')}")
    if not throw.get("date"):
        raise ValueError("throw missing 'date'")
    if not throw.get("source"):
        raise ValueError("throw missing 'source'")

    import uuid
    enriched = {
        "id": str(uuid.uuid4()),
        "date": throw["date"],
        "type": throw["type"],
        "source": throw["source"],
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "notes": throw.get("notes"),
    }

    model = db.get_client().table("pitcher_training_model").select("current_week_state").eq("pitcher_id", pitcher_id).execute()
    if not model.data:
        raise KeyError(f"pitcher_training_model not found for {pitcher_id}")

    state = model.data[0].get("current_week_state") or {}
    throws = state.get("scheduled_throws") or []

    cutoff = (date.today() - timedelta(days=SCHEDULED_THROW_RETENTION_DAYS)).isoformat()
    throws = [t for t in throws if t.get("date", "9999") >= cutoff]
    throws.append(enriched)

    state["scheduled_throws"] = throws
    db.get_client().table("pitcher_training_model").update({"current_week_state": state}).eq("pitcher_id", pitcher_id).execute()
    return enriched


def remove_scheduled_throw(pitcher_id: str, throw_id: str) -> bool:
    """Remove a scheduled throw by id. Returns True if removed."""
    model = db.get_client().table("pitcher_training_model").select("current_week_state").eq("pitcher_id", pitcher_id).execute()
    if not model.data:
        return False
    state = model.data[0].get("current_week_state") or {}
    throws = state.get("scheduled_throws") or []
    filtered = [t for t in throws if t.get("id") != throw_id]
    if len(filtered) == len(throws):
        return False
    state["scheduled_throws"] = filtered
    db.get_client().table("pitcher_training_model").update({"current_week_state": state}).eq("pitcher_id", pitcher_id).execute()
    return True
```

- [ ] **Step 2: Verify imports compile**

```bash
cd pitcher_program_app && python -c "from bot.services.weekly_model import update_phase_state, add_scheduled_throw, remove_scheduled_throw; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Smoke-test against a real pitcher**

```bash
cd pitcher_program_app && python -c "
from bot.services.weekly_model import update_phase_state
phase = update_phase_state('landon_brice')
print('Phase:', phase)
"
```

Expected: prints a phase dict with `phase_id='in_season_main'`, `name='Maintenance'`, `phase_type='in_season'`, `week_in_phase=N`, `training_intent=None`.

- [ ] **Step 4: Diff harness still passes**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/weekly_model.py
git commit -m "Add update_phase_state + scheduled throw mutations to weekly_model"
```

---

### Task 3.2: Wire phase recompute into checkin_service

**Files:**
- Modify: `pitcher_program_app/bot/services/checkin_service.py`

- [ ] **Step 1: Find the after-checkin hook**

```bash
cd pitcher_program_app && grep -n "compute_next_day_suggestion\|update_active_flags\|weekly_model" bot/services/checkin_service.py
```

Identify where weekly state is updated after a successful check-in (likely calls `compute_next_day_suggestion` or `update_active_flags`).

- [ ] **Step 2: Add phase recompute call**

After the existing weekly state update (just before the function returns the entry), add:

```python
        # Recompute phase state from active program
        try:
            from bot.services.weekly_model import update_phase_state
            update_phase_state(pitcher_id)
        except Exception as exc:
            logger.warning(f"update_phase_state failed for {pitcher_id}: {exc}")
```

**Important:** wrap in try/except. Phase recompute must NEVER block a check-in — if it fails, log and move on.

- [ ] **Step 3: Diff harness still passes**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/checkin_service.py
git commit -m "Recompute phase state after each check-in (non-blocking)"
```

---

## Phase 4 — Throw Intent Parser

Goal: Detect throwing intent in chat messages and append to `scheduled_throws[]`. Regex-only in v1 (LLM fallback deferred).

### Task 4.1: Create the parser module

**Files:**
- Create: `pitcher_program_app/bot/services/throw_intent_parser.py`

- [ ] **Step 1: Write the parser**

```python
"""Detect throwing intent in chat messages.

Regex-only in v1 — high precision, modest recall. Returns None when ambiguous.
False-positives are recoverable via the bot's confirmation reply ("Got it —
bullpen Thursday added. Wrong? Tell me 'cancel'").
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

THROW_TYPE_PATTERNS = {
    "bullpen": re.compile(r"\b(bullpen|bull\s*pen|pen)\b", re.IGNORECASE),
    "side":    re.compile(r"\b(side|side\s*work|side\s*session)\b", re.IGNORECASE),
    "long_toss": re.compile(r"\b(long\s*toss|long-toss|longtoss)\b", re.IGNORECASE),
    "catch":   re.compile(r"\b(play\s*catch|catch\s*play|just\s*catch)\b", re.IGNORECASE),
}

DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

RELATIVE_DAYS = {
    "today": 0,
    "tomorrow": 1,
    "tmrw": 1,
    "tmw": 1,
}

INTENT_VERBS = re.compile(
    r"\b("
    r"throwing|throw|gonna throw|going to throw|"
    r"have a|got a|got my|i\s*'?\s*ve got|i have|"
    r"planning|planned|scheduled|set up|setting up|"
    r"doing|do my"
    r")\b",
    re.IGNORECASE,
)


def parse_throw_intent(message: str, today: date) -> Optional[dict]:
    """Detect throwing intent. Returns {date, type, notes} or None.

    `today` is the reference date for relative day resolution.
    """
    if not message:
        return None

    # Must have at least one throw-type keyword
    throw_type = None
    for ttype, pattern in THROW_TYPE_PATTERNS.items():
        if pattern.search(message):
            throw_type = ttype
            break
    if throw_type is None:
        return None

    # Must have at least one intent verb (filters out "I threw a bullpen yesterday")
    if not INTENT_VERBS.search(message):
        return None

    # Filter out past tense
    past_tense = re.compile(r"\b(threw|thrown|did|was|were|had)\b", re.IGNORECASE)
    if past_tense.search(message):
        return None

    # Resolve date
    target_date = _resolve_date(message, today)
    if target_date is None:
        return None

    return {
        "date": target_date.isoformat(),
        "type": throw_type,
        "notes": None,
    }


def _resolve_date(message: str, today: date) -> Optional[date]:
    msg = message.lower()

    for keyword, offset in RELATIVE_DAYS.items():
        if re.search(rf"\b{keyword}\b", msg):
            return today + timedelta(days=offset)

    for name, weekday in DAY_NAMES.items():
        if re.search(rf"\b{name}\b", msg):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "throwing Wednesday" said on a Wednesday → next Wednesday
            return today + timedelta(days=days_ahead)

    return None
```

- [ ] **Step 2: Write the verification script**

Create `pitcher_program_app/scripts/verify_throw_intent_parser.py`:

```python
#!/usr/bin/env python3
"""Verification: throw intent parser against a corpus of real-ish messages."""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services.throw_intent_parser import parse_throw_intent

# Reference today: Wednesday April 8 2026
TODAY = date(2026, 4, 8)

CASES = [
    # (message, expected dict or None)
    ("I'm throwing a bullpen Thursday",          {"date": "2026-04-09", "type": "bullpen"}),
    ("got a side session tomorrow",              {"date": "2026-04-09", "type": "side"}),
    ("planning long toss Friday",                {"date": "2026-04-10", "type": "long_toss"}),
    ("gonna throw a pen tmrw",                   {"date": "2026-04-09", "type": "bullpen"}),
    ("have a bullpen scheduled for Sat",         {"date": "2026-04-11", "type": "bullpen"}),
    ("doing my side work today",                 {"date": "2026-04-08", "type": "side"}),
    # Should NOT trigger
    ("I threw a bullpen yesterday",              None),  # past tense
    ("how's your bullpen looking",               None),  # no intent verb
    ("my arm feels good",                        None),  # no throw keyword
    ("had a side yesterday, arm sore",           None),  # past tense
    ("",                                          None),
]


def main() -> int:
    fails = 0
    for msg, expected in CASES:
        result = parse_throw_intent(msg, TODAY)
        if expected is None:
            ok = result is None
        else:
            ok = (
                result is not None
                and result["date"] == expected["date"]
                and result["type"] == expected["type"]
            )
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg!r:60} → {result}")
        if not ok:
            fails += 1
    print(f"\n{len(CASES) - fails}/{len(CASES)} cases passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run verification**

```bash
cd pitcher_program_app && python -m scripts.verify_throw_intent_parser
```

Expected: `11/11 cases passed`. If any FAIL, refine the regex patterns until they pass.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/throw_intent_parser.py pitcher_program_app/scripts/verify_throw_intent_parser.py
git commit -m "Add throw intent parser + verification corpus"
```

---

### Task 4.2: Wire parser into qa.py chat handler

**Files:**
- Modify: `pitcher_program_app/bot/handlers/qa.py`

- [ ] **Step 1: Find the message handling entry point**

```bash
cd pitcher_program_app && grep -n "async def\|process_message\|reply_text" bot/handlers/qa.py | head -30
```

Identify the function that handles inbound text messages (likely `handle_message` or similar) and the variable holding the bot reply text before it's sent.

- [ ] **Step 2: Add parser hook**

Inside the message handler, AFTER pitcher_id is resolved and BEFORE the LLM Q&A reply is generated, add:

```python
    # Detect throwing intent
    try:
        from bot.services.throw_intent_parser import parse_throw_intent
        from bot.services.weekly_model import add_scheduled_throw
        from datetime import datetime
        from bot.config import CHICAGO_TZ

        today = datetime.now(CHICAGO_TZ).date()
        throw_intent = parse_throw_intent(message_text, today)
        if throw_intent:
            try:
                add_scheduled_throw(
                    pitcher_id,
                    {**throw_intent, "source": "chat"},
                )
                throw_confirmation = f"Got it — {throw_intent['type'].replace('_', ' ')} on {throw_intent['date']} added to your week. (Reply 'cancel last' to undo.)"
            except Exception as exc:
                logger.warning(f"add_scheduled_throw failed: {exc}")
                throw_confirmation = None
        else:
            throw_confirmation = None
    except Exception as exc:
        logger.warning(f"throw intent detection failed: {exc}")
        throw_confirmation = None
```

Then, where the reply is sent, prepend `throw_confirmation` if it's not None:

```python
    if throw_confirmation:
        reply_text = f"{throw_confirmation}\n\n{reply_text}"
```

The exact lines depend on the existing handler shape — preserve all existing logic, only add this hook.

- [ ] **Step 3: Smoke test by running the bot locally if possible, or manually verify the import path resolves**

```bash
cd pitcher_program_app && python -c "from bot.handlers import qa; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/handlers/qa.py
git commit -m "Wire throw intent parser into qa chat handler"
```

---

## Phase 5 — API Endpoints

Goal: Six new endpoints powering the Programs tab. Each is independent and can be tested with `curl` against a local FastAPI dev server.

### Task 5.1: `GET /api/pitcher/{id}/program`

**Files:**
- Modify: `pitcher_program_app/api/routes.py`

This is the workhorse — returns the entire payload the Programs tab needs in one fetch.

- [ ] **Step 1: Add the endpoint**

Append to `pitcher_program_app/api/routes.py`:

```python
from datetime import date, datetime, timedelta
from bot.services import programs as programs_svc
from bot.services.weekly_model import (
    add_scheduled_throw,
    remove_scheduled_throw,
    update_phase_state,
)


def _build_week_arc(pitcher_id: str, program: dict, training_model: dict) -> dict:
    """Build the week arc payload for a pitcher's active program.

    Window anchoring (per spec):
      - starter: [last_outing_date, last_outing_date + rotation_length - 1]
      - reliever: [last_appearance_date, last_appearance_date + 6]
      - new pitcher (no last outing): current calendar week (Sun-Sat, Chicago tz)

    For v1, we treat all in-season as the calendar-week fallback unless
    last_outing_date is populated. Reliever-specific anchoring (days_since_appearance
    label rendering) is handled by the role check.
    """
    from bot.config import CHICAGO_TZ

    template = programs_svc.db.get_program_template(program["template_id"])
    role = (template or {}).get("role", "starter")
    rotation_length = (template or {}).get("rotation_length", 7)

    last_outing = training_model.get("last_outing_date")
    today_chicago = datetime.now(CHICAGO_TZ).date()

    if last_outing:
        anchor_date = date.fromisoformat(last_outing) if isinstance(last_outing, str) else last_outing
        window_start = anchor_date
        window_end = anchor_date + timedelta(days=rotation_length - 1 if role == "starter" else 6)
        anchor_type = "calendar" if role == "starter" else "appearance"
    else:
        # Calendar fallback: Sunday → Saturday containing today
        window_start = today_chicago - timedelta(days=(today_chicago.weekday() + 1) % 7)
        window_end = window_start + timedelta(days=6)
        anchor_type = "calendar"

    state = training_model.get("current_week_state") or {}
    scheduled_throws = state.get("scheduled_throws") or []
    throws_by_date = {t["date"]: t for t in scheduled_throws}

    days = []
    for offset in range((window_end - window_start).days + 1):
        d = window_start + timedelta(days=offset)
        rotation_day = (d - window_start).days  # 0-indexed; day 0 = anchor (outing day)
        is_today = d == today_chicago
        is_past = d < today_chicago
        scheduled = throws_by_date.get(d.isoformat())

        # Derive emoji + label from rotation day or scheduled throw
        emoji, label = _day_emoji_and_label(rotation_day, scheduled, is_anchor=(offset == 0))
        state_key = "outing" if offset == 0 else ("today" if is_today else ("done" if is_past else "upcoming"))

        days.append({
            "date": d.isoformat(),
            "day_label": d.strftime("%a").upper(),
            "rotation_day": rotation_day,
            "state": state_key,
            "emoji": emoji,
            "label": label,
            "logged": bool(scheduled and scheduled.get("source") in ("chat", "button")),
            "has_game": False,  # filled in by schedule overlay
        })

    return {"anchor_type": anchor_type, "days": days}


def _day_emoji_and_label(rotation_day: int, scheduled: dict | None, *, is_anchor: bool) -> tuple[str, str]:
    """Pick the bubble emoji + label for a day."""
    if is_anchor:
        return ("⚾", "Start")
    if scheduled:
        type_to_emoji = {"bullpen": "🎯", "side": "🎯", "long_toss": "🎯", "catch": "🧢", "game": "⚾"}
        type_to_label = {"bullpen": "Bullpen", "side": "Side", "long_toss": "Long toss", "catch": "Catch", "game": "Game"}
        return (type_to_emoji.get(scheduled["type"], "🎯"), type_to_label.get(scheduled["type"], "Throw"))
    # Fallback by rotation day
    rotation_emoji = {1: "🛁", 2: "🏋️", 3: "🎯", 4: "🏋️", 5: "🎯", 6: "💪"}
    rotation_label = {1: "Recovery", 2: "Heavy lift", 3: "Bullpen", 4: "Strength", 5: "Side", 6: "Prep"}
    return (rotation_emoji.get(rotation_day, "·"), rotation_label.get(rotation_day, ""))


def _overlay_schedule_on_arc(arc: dict, schedule: list[dict]) -> None:
    """Mutate arc.days[*].has_game based on schedule entries."""
    game_dates = {g["date"] for g in schedule}
    for day in arc["days"]:
        if day["date"] in game_dates:
            day["has_game"] = True


@router.get("/pitcher/{pitcher_id}/program")
async def get_pitcher_program(pitcher_id: str, request: Request):
    """Return the active program with computed phase, week arc, schedule, and today detail."""
    _require_pitcher_auth(request, pitcher_id)

    program = programs_svc.get_active_program(pitcher_id)
    if not program:
        return {"program": None, "week_arc": None, "schedule": [], "today_detail": None}

    phase = programs_svc.compute_current_phase(program)

    training_model_resp = (
        db.get_client()
        .table("pitcher_training_model")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .execute()
    )
    training_model = (training_model_resp.data or [{}])[0]

    arc = _build_week_arc(pitcher_id, program, training_model)
    schedule = _fetch_schedule_for_window(arc["days"][0]["date"], arc["days"][-1]["date"], pitcher_id)
    _overlay_schedule_on_arc(arc, schedule)

    program_payload = {
        "id": program["id"],
        "name": program["name"],
        "current_phase": phase,
        "phase_progress": {
            "week": phase["week_in_program"],
            "total": program.get("total_weeks") or sum(p.get("week_count", 0) for p in program.get("phases_snapshot", [])),
        },
    }

    return {
        "program": program_payload,
        "week_arc": arc,
        "schedule": schedule,
        "today_detail": _build_today_detail(arc, training_model),
    }


def _fetch_schedule_for_window(start_iso: str, end_iso: str, pitcher_id: str) -> list[dict]:
    """Read UChicago games in the window from the schedule table."""
    try:
        resp = (
            db.get_client()
            .table("schedule")
            .select("*")
            .gte("date", start_iso)
            .lte("date", end_iso)
            .order("date")
            .execute()
        )
    except Exception:
        return []
    games = resp.data or []
    return [
        {
            "date": g["date"],
            "opponent": g.get("opponent", "TBD"),
            "home": g.get("home", True),
            "time": g.get("time"),
            "result": g.get("result"),
            "doubleheader": g.get("doubleheader", False),
            "is_your_start": False,  # populated by caller via training_model.last_outing_date match
        }
        for g in games
    ]


def _build_today_detail(arc: dict, training_model: dict) -> dict | None:
    today_day = next((d for d in arc["days"] if d["state"] == "today"), None)
    if not today_day:
        return None
    return {
        "rotation_day": today_day["rotation_day"],
        "label": f"{today_day['label']} day",
        "title": today_day["label"],
        "subtitle": "",
        "pills": [],
    }
```

- [ ] **Step 2: Smoke test the endpoint locally**

Start the API:
```bash
cd pitcher_program_app && DISABLE_AUTH=true python -m api.main
```

In another terminal:
```bash
curl -s http://localhost:8000/api/pitcher/landon_brice/program | python -m json.tool
```

Expected: a JSON payload with `program.name = "In-Season Starter Protocol"`, `current_phase.week_in_program = 7` (or similar), `week_arc.days` with 7 entries, `schedule` array (possibly empty), `today_detail` object.

If any field is missing or errors, fix before commit. The week arc must have exactly 7 days for a starter and exactly 7 days for a reliever (rotation_length capped at 7 in `_build_week_arc`).

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/api/routes.py
git commit -m "Add GET /api/pitcher/{id}/program endpoint with week arc + schedule overlay"
```

---

### Task 5.2: Remaining program endpoints

**Files:**
- Modify: `pitcher_program_app/api/routes.py`

- [ ] **Step 1: Add the program history, detail, and schedule endpoints**

Append to `pitcher_program_app/api/routes.py`:

```python
@router.get("/pitcher/{pitcher_id}/program/history")
async def get_program_history(pitcher_id: str, request: Request):
    _require_pitcher_auth(request, pitcher_id)
    history = programs_svc.list_program_history(pitcher_id)
    return {"programs": [
        {
            "id": p["id"],
            "name": p["name"],
            "template_id": p["template_id"],
            "start_date": p["start_date"],
            "end_date": p.get("end_date"),
            "deactivated_at": p.get("deactivated_at"),
            "deactivation_reason": p.get("deactivation_reason"),
            "current_phase": p.get("_current_phase"),
        }
        for p in history
    ]}


@router.get("/program/{program_id}")
async def get_program_detail(program_id: int, request: Request):
    """Program detail. No auth on this endpoint — anyone with the id can read."""
    program = db.get_training_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    template = db.get_program_template(program["template_id"])
    phase = programs_svc.compute_current_phase(program)
    return {
        "program": program,
        "template": template,
        "current_phase": phase,
    }


@router.get("/schedule/this-week")
async def get_schedule_this_week(pitcher_id: str, request: Request):
    """UChicago games for the pitcher's current rotation week, with is_your_start flag."""
    _require_pitcher_auth(request, pitcher_id)

    program = programs_svc.get_active_program(pitcher_id)
    if not program:
        return {"games": []}

    training_model_resp = (
        db.get_client()
        .table("pitcher_training_model")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .execute()
    )
    training_model = (training_model_resp.data or [{}])[0]
    arc = _build_week_arc(pitcher_id, program, training_model)
    schedule = _fetch_schedule_for_window(arc["days"][0]["date"], arc["days"][-1]["date"], pitcher_id)

    last_outing = training_model.get("last_outing_date")
    if last_outing:
        for game in schedule:
            if game["date"] == (last_outing if isinstance(last_outing, str) else last_outing.isoformat()):
                game["is_your_start"] = True

    return {"games": schedule}


@router.post("/pitcher/{pitcher_id}/scheduled-throw")
async def post_scheduled_throw(pitcher_id: str, request: Request):
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be an object")
    try:
        throw = add_scheduled_throw(
            pitcher_id,
            {
                "date": body.get("date"),
                "type": body.get("type"),
                "source": "button",
                "notes": body.get("notes"),
            },
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"throw": throw}


@router.delete("/pitcher/{pitcher_id}/scheduled-throw/{throw_id}")
async def delete_scheduled_throw(pitcher_id: str, throw_id: str, request: Request):
    _require_pitcher_auth(request, pitcher_id)
    removed = remove_scheduled_throw(pitcher_id, throw_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Throw not found")
    return {"removed": True}
```

- [ ] **Step 2: Smoke test each endpoint**

```bash
cd pitcher_program_app && DISABLE_AUTH=true python -m api.main &
sleep 1
curl -s http://localhost:8000/api/pitcher/landon_brice/program/history | python -m json.tool
curl -s "http://localhost:8000/api/schedule/this-week?pitcher_id=landon_brice" | python -m json.tool
curl -s -X POST http://localhost:8000/api/pitcher/landon_brice/scheduled-throw \
  -H 'content-type: application/json' \
  -d '{"date":"2026-04-10","type":"bullpen"}' | python -m json.tool
```

Each must return a 200 with the expected shape. The POST should return the new throw with an id and `source: "button"`.

Then:
```bash
# Pull out the throw id and delete it
THROW_ID=$(curl -s http://localhost:8000/api/pitcher/landon_brice/program | python -c "import json,sys; data=json.load(sys.stdin); throws=[d for d in data['week_arc']['days'] if d.get('logged')]; print(throws[0] if throws else '')")
echo "Throw id from arc (logged dates): $THROW_ID"
```

Confirm the logged-mark dot will render on the day where the POST landed.

- [ ] **Step 3: Stop the dev server**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/api/routes.py
git commit -m "Add program history, detail, schedule, and scheduled-throw endpoints"
```

---

## Phase 6 — Frontend: Programs Tab Rewrite

Goal: New components matching the approved mockup, Plans.jsx replaced by Programs.jsx, ProgramDetail page added, nav updated.

**Mockup reference:** `.superpowers/brainstorm/70775-1775777250/content/schedule-blend-v3.html` is the locked visual. Each component below should match its section of that mockup pixel-by-pixel where the spec defines exact values.

### Task 6.1: ProgramHero component

**Files:**
- Create: `pitcher_program_app/mini-app/src/components/ProgramHero.jsx`

- [ ] **Step 1: Write the component**

```jsx
export default function ProgramHero({ program }) {
  if (!program) return null;
  const { name, current_phase, phase_progress } = program;
  const totalWeeks = phase_progress?.total || 1;
  const currentWeek = phase_progress?.week || 1;
  const completionPct = Math.min(currentWeek / totalWeeks, 1);
  const dashLength = 125.7;
  const filled = (completionPct * dashLength).toFixed(1);

  return (
    <div style={{
      margin: '14px 14px 0', borderRadius: 16,
      background: 'linear-gradient(165deg, var(--color-maroon) 0%, var(--color-maroon-mid) 100%)',
      padding: '16px 18px 18px',
      color: '#fff',
      boxShadow: '0 4px 20px rgba(92,16,32,0.18)',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: -30, right: -30, width: 110, height: 110, borderRadius: 55, background: 'rgba(255,255,255,0.04)' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative' }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.4, color: 'var(--color-rose-blush)' }}>
            Active Program · Week {currentWeek}
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{name}</div>
          <div style={{ fontSize: 11, color: 'var(--color-rose-blush)', marginTop: 3 }}>
            {current_phase?.name}
          </div>
        </div>
        <div style={{ width: 48, height: 48, position: 'relative', flexShrink: 0 }}>
          <svg width="48" height="48" viewBox="0 0 48 48">
            <circle cx="24" cy="24" r="20" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="4" />
            <circle cx="24" cy="24" r="20" fill="none" stroke="#e8a0aa" strokeWidth="4" strokeLinecap="round"
              strokeDasharray={`${filled} ${dashLength}`}
              transform="rotate(-90 24 24)" />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#fff' }}>
            {Math.round(completionPct * 100)}%
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 3, marginTop: 14 }}>
        {Array.from({ length: totalWeeks }).map((_, i) => (
          <div key={i} style={{
            flex: 1, height: 4, borderRadius: 2,
            background: i < currentWeek - 1
              ? 'var(--color-rose-blush)'
              : i === currentWeek - 1
                ? '#fff'
                : 'rgba(255,255,255,0.18)',
            boxShadow: i === currentWeek - 1 ? '0 0 10px rgba(255,255,255,0.5)' : 'none',
          }} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/ProgramHero.jsx
git commit -m "Add ProgramHero component"
```

---

### Task 6.2: DayBubble + WeekArc components

**Files:**
- Create: `pitcher_program_app/mini-app/src/components/DayBubble.jsx`
- Create: `pitcher_program_app/mini-app/src/components/WeekArc.jsx`

- [ ] **Step 1: Write DayBubble**

```jsx
export default function DayBubble({ day }) {
  const { day_label, state, emoji, label, logged, has_game } = day;
  const isToday = state === 'today';
  const isOuting = state === 'outing';
  const isDone = state === 'done';
  const isPast = state === 'done' || state === 'outing';

  const dlabelColor = isToday || isOuting
    ? 'var(--color-maroon)'
    : (has_game ? '#1a2942' : 'var(--color-ink-muted)');

  let bubbleStyle = {
    width: 30, height: 30, borderRadius: '50%',
    background: '#fff', border: '1.5px solid var(--color-cream-border)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 14, position: 'relative', zIndex: 1,
  };
  if (isDone) Object.assign(bubbleStyle, { background: 'var(--color-flag-green)', borderColor: 'var(--color-flag-green)', color: '#fff', fontSize: 13, fontWeight: 700 });
  if (isOuting) Object.assign(bubbleStyle, { background: '#f5e0e4', borderColor: 'var(--color-rose-blush)', color: 'var(--color-maroon)' });
  if (isToday) Object.assign(bubbleStyle, {
    width: 44, height: 44, background: 'var(--color-maroon)',
    border: '2px solid var(--color-rose-blush)', color: '#fff', fontSize: 18,
    boxShadow: '0 5px 16px rgba(92,16,32,0.35)', marginTop: -7,
  });

  if (has_game) {
    const baseShadow = isToday ? '0 5px 16px rgba(92,16,32,0.35)' : '';
    bubbleStyle.boxShadow = `0 0 0 2.5px var(--color-cream-bg), 0 0 0 4px #1a2942${baseShadow ? ', ' + baseShadow : ''}`;
  }

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative', padding: '4px 0' }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: dlabelColor, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
        {day_label}
      </div>
      <div style={bubbleStyle}>
        {isDone ? '✓' : emoji}
      </div>
      <div style={{
        fontSize: 10, fontWeight: isToday ? 700 : 500,
        color: isToday ? 'var(--color-ink-primary)' : 'var(--color-ink-muted)',
        marginTop: 12, textAlign: 'center', lineHeight: 1.25,
        opacity: isPast ? 0.5 : 1,
      }}>
        {label}
        {logged && (
          <span style={{
            display: 'inline-block', width: 5, height: 5, borderRadius: '50%',
            background: 'var(--color-flag-yellow)', marginLeft: 3,
            verticalAlign: 'middle',
            boxShadow: '0 0 0 2px rgba(186,117,23,0.15)',
          }} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write WeekArc**

```jsx
import DayBubble from './DayBubble';
import SetNextThrowButton from './SetNextThrowButton';

export default function WeekArc({ arc, onAddThrow }) {
  if (!arc) return null;
  return (
    <div style={{ padding: '18px 14px 14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px 12px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          This Week
        </div>
        <SetNextThrowButton onAdd={onAddThrow} />
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 2, padding: '6px 2px 2px', position: 'relative' }}>
        <div style={{ position: 'absolute', left: 30, right: 30, top: 38, height: 1.5, background: 'var(--color-cream-border)', zIndex: 0 }} />
        {arc.days.map(day => <DayBubble key={day.date} day={day} />)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 14, fontSize: 9, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
        <span style={{
          width: 12, height: 12, borderRadius: '50%', background: '#fff',
          boxShadow: '0 0 0 1.5px var(--color-cream-border), 0 0 0 3px #1a2942',
          marginRight: 2,
        }} />
        ring = game day
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/DayBubble.jsx pitcher_program_app/mini-app/src/components/WeekArc.jsx
git commit -m "Add DayBubble and WeekArc components"
```

---

### Task 6.3: ScheduleCard, TodayDetailCard, SetNextThrowButton, SetThrowModal

**Files:**
- Create: `pitcher_program_app/mini-app/src/components/ScheduleCard.jsx`
- Create: `pitcher_program_app/mini-app/src/components/TodayDetailCard.jsx`
- Create: `pitcher_program_app/mini-app/src/components/SetNextThrowButton.jsx`
- Create: `pitcher_program_app/mini-app/src/components/SetThrowModal.jsx`

- [ ] **Step 1: Write SetNextThrowButton**

```jsx
import { useState } from 'react';
import SetThrowModal from './SetThrowModal';

export default function SetNextThrowButton({ onAdd }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{
          fontSize: 10, fontWeight: 600, color: 'var(--color-maroon)',
          background: 'rgba(92,16,32,0.06)',
          border: '1px solid rgba(92,16,32,0.15)',
          borderRadius: 14, padding: '4px 10px', cursor: 'pointer',
        }}
      >
        ＋ Set next throw
      </button>
      {open && (
        <SetThrowModal
          onClose={() => setOpen(false)}
          onSave={async (data) => {
            await onAdd(data);
            setOpen(false);
          }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: Write SetThrowModal**

```jsx
import { useState } from 'react';

const TYPES = [
  { value: 'catch', label: 'Catch' },
  { value: 'long_toss', label: 'Long toss' },
  { value: 'bullpen', label: 'Bullpen' },
  { value: 'side', label: 'Side' },
];

function next4Days() {
  const out = [];
  const today = new Date();
  for (let i = 1; i <= 4; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    out.push({
      iso: d.toISOString().slice(0, 10),
      label: d.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase(),
      n: d.getDate(),
    });
  }
  return out;
}

export default function SetThrowModal({ onClose, onSave }) {
  const [type, setType] = useState('bullpen');
  const [date, setDate] = useState(next4Days()[0].iso);
  const dates = next4Days();

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'flex-end', zIndex: 100,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', background: 'var(--color-cream-bg)',
          borderRadius: '18px 18px 0 0', padding: '20px 18px 24px',
        }}
      >
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          Log a throwing session
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>
            Type
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => setType(t.value)}
                style={{
                  fontSize: 11, fontWeight: 600,
                  padding: '6px 11px', borderRadius: 14,
                  border: '1px solid var(--color-cream-border)',
                  background: type === t.value ? 'var(--color-maroon)' : '#fff',
                  color: type === t.value ? '#fff' : 'var(--color-ink-secondary)',
                  cursor: 'pointer',
                }}
              >{t.label}</button>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>
            When
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            {dates.map((d) => (
              <button
                key={d.iso}
                onClick={() => setDate(d.iso)}
                style={{
                  flex: 1, padding: '8px 4px', borderRadius: 10,
                  border: '1px solid var(--color-cream-border)',
                  background: date === d.iso ? 'var(--color-maroon)' : '#fff',
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'block', fontSize: 9, color: date === d.iso ? '#fff' : 'var(--color-ink-muted)' }}>{d.label}</span>
                <span style={{ display: 'block', fontSize: 13, fontWeight: 700, color: date === d.iso ? '#fff' : 'var(--color-ink-primary)', marginTop: 1 }}>{d.n}</span>
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button onClick={onClose} style={{ fontSize: 12, fontWeight: 600, padding: '8px 16px', borderRadius: 10, border: 'none', background: 'transparent', color: 'var(--color-ink-muted)', cursor: 'pointer' }}>Cancel</button>
          <button onClick={() => onSave({ date, type })} style={{ fontSize: 12, fontWeight: 600, padding: '8px 16px', borderRadius: 10, border: 'none', background: 'var(--color-maroon)', color: '#fff', cursor: 'pointer' }}>Save</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write ScheduleCard**

```jsx
function GameItem({ game, isFeatured }) {
  const yourStart = game.is_your_start;
  const isPast = new Date(game.date) < new Date(new Date().toISOString().slice(0, 10));
  const dateLabel = new Date(game.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase();

  let style = {
    flex: 1, minWidth: 0,
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10, padding: '9px 9px 10px',
    borderTop: '2px solid rgba(255,255,255,0.25)',
  };
  if (isPast) Object.assign(style, { opacity: 0.5, borderTopColor: 'rgba(255,255,255,0.15)' });
  if (isFeatured) Object.assign(style, { background: 'rgba(255,255,255,0.13)', borderColor: 'rgba(255,255,255,0.2)', borderTop: '2px solid #fff' });
  if (yourStart) Object.assign(style, { borderTop: '2px solid var(--color-rose-blush)', background: 'rgba(232,160,170,0.12)', borderColor: 'rgba(232,160,170,0.25)' });

  return (
    <div style={style}>
      <div style={{ fontSize: 9, fontWeight: 700, color: yourStart ? 'var(--color-rose-blush)' : 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {dateLabel}
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#fff', marginTop: 4, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {!game.home && <span style={{ fontSize: 10, opacity: 0.6 }}>@ </span>}
        {game.opponent}
      </div>
      <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.6)', marginTop: 4, fontWeight: 500 }}>
        {yourStart && <span style={{ fontWeight: 700, color: 'var(--color-rose-blush)', textTransform: 'uppercase', letterSpacing: 0.4, fontSize: 8, background: 'rgba(232,160,170,0.18)', padding: '1px 5px', borderRadius: 4 }}>YOUR START</span>}
        {!yourStart && (game.time || '') + (game.result ? ` · ${game.result}` : '')}
      </div>
    </div>
  );
}

export default function ScheduleCard({ schedule }) {
  if (!schedule || schedule.length === 0) return null;
  const today = new Date().toISOString().slice(0, 10);
  const featuredIdx = schedule.findIndex(g => g.date >= today);
  return (
    <div style={{
      margin: '16px 14px 0', background: '#1a2942',
      borderRadius: 14, padding: '14px 16px 16px',
      boxShadow: '0 4px 16px rgba(26,41,66,0.18)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.7)', textTransform: 'uppercase', letterSpacing: 1.3 }}>
          ⚾ Maroons · This Week
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {schedule.map((g, i) => <GameItem key={g.date} game={g} isFeatured={i === featuredIdx} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write TodayDetailCard**

```jsx
export default function TodayDetailCard({ today }) {
  if (!today) return null;
  return (
    <div style={{
      margin: '16px 14px 14px', background: '#fff',
      borderRadius: 14, border: '1.5px solid var(--color-maroon)',
      padding: '14px 16px 14px',
      boxShadow: '0 4px 16px rgba(92,16,32,0.08)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          {today.label}
        </div>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-ink-primary)', marginTop: 5, letterSpacing: -0.2 }}>
        {today.title}
      </div>
      {today.subtitle && (
        <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 6, lineHeight: 1.5 }}>
          {today.subtitle}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/ScheduleCard.jsx pitcher_program_app/mini-app/src/components/TodayDetailCard.jsx pitcher_program_app/mini-app/src/components/SetNextThrowButton.jsx pitcher_program_app/mini-app/src/components/SetThrowModal.jsx
git commit -m "Add ScheduleCard, TodayDetailCard, SetNextThrowButton, SetThrowModal"
```

---

### Task 6.4: Programs.jsx page (replaces Plans.jsx contents)

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Plans.jsx`

The file stays at the same path and is renamed via the route, but its contents are completely replaced. The default export is renamed `Programs`.

- [ ] **Step 1: Replace Plans.jsx contents**

```jsx
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import ProgramHero from '../components/ProgramHero';
import WeekArc from '../components/WeekArc';
import ScheduleCard from '../components/ScheduleCard';
import TodayDetailCard from '../components/TodayDetailCard';

export default function Programs() {
  const { pitcherId, initData } = useAuth();
  const { data, loading, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/program` : null,
    initData
  );

  async function handleAddThrow(throwData) {
    const resp = await fetch(`/api/pitcher/${pitcherId}/scheduled-throw`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'X-Telegram-Init-Data': initData || '',
      },
      body: JSON.stringify(throwData),
    });
    if (!resp.ok) {
      console.error('Failed to add throw:', await resp.text());
      return;
    }
    refetch();
  }

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ height: 24, background: 'var(--color-cream-border)', borderRadius: 6, width: '40%', marginBottom: 16 }} />
        <div style={{ height: 120, background: 'var(--color-cream-border)', borderRadius: 16, marginBottom: 16 }} />
        <div style={{ height: 200, background: 'var(--color-cream-border)', borderRadius: 16 }} />
      </div>
    );
  }

  if (!data?.program) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-ink-muted)' }}>
        No active program. Ask your coach to set one up.
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 100 }}>
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-rose-blush)', textTransform: 'uppercase', letterSpacing: 1.5 }}>
          My Program
        </div>
        <div style={{ fontSize: 19, fontWeight: 700, color: '#fff', marginTop: 4, letterSpacing: -0.3 }}>
          {data.program.name}
        </div>
      </div>
      <ProgramHero program={data.program} />
      <WeekArc arc={data.week_arc} onAddThrow={handleAddThrow} />
      <ScheduleCard schedule={data.schedule} />
      <TodayDetailCard today={data.today_detail} />
    </div>
  );
}
```

- [ ] **Step 2: Run the dev server and visually verify**

```bash
cd pitcher_program_app/mini-app && npm install && npm run dev
```

Open the dev URL in a browser. Confirm the page renders with the hero card, week arc, schedule card, and today card. Errors show in console — fix any prop type / null guard issues before committing.

- [ ] **Step 3: Stop the dev server (Ctrl+C)**

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/mini-app/src/pages/Plans.jsx
git commit -m "Replace Plans.jsx with Programs page wired to /api/pitcher/{id}/program"
```

---

### Task 6.5: ProgramHistoryTimeline component

**Files:**
- Create: `pitcher_program_app/mini-app/src/components/ProgramHistoryTimeline.jsx`

A vertical timeline of past programs. Renders below the today card on the Programs page when history exists. Tap a row to navigate to its detail view.

- [ ] **Step 1: Write the component**

```jsx
import { useNavigate } from 'react-router-dom';

export default function ProgramHistoryTimeline({ programs }) {
  const navigate = useNavigate();
  if (!programs || programs.length === 0) return null;

  return (
    <div style={{ padding: '8px 16px 24px' }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Program History
      </div>
      {programs.map((p, i) => {
        const isActive = !p.deactivated_at;
        return (
          <div key={p.id} style={{ display: 'flex', gap: 12, marginBottom: i < programs.length - 1 ? 0 : 0 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20, flexShrink: 0 }}>
              <div style={{
                width: isActive ? 12 : 8, height: isActive ? 12 : 8, borderRadius: '50%',
                background: isActive ? 'var(--color-maroon)' : 'var(--color-cream-border)',
                border: isActive ? '2px solid var(--color-rose-blush)' : 'none',
                flexShrink: 0,
              }} />
              {i < programs.length - 1 && (
                <div style={{ width: 1.5, flex: 1, minHeight: 40, background: 'var(--color-cream-border)' }} />
              )}
            </div>
            <div
              onClick={() => navigate(`/programs/${p.id}`)}
              style={{ flex: 1, cursor: 'pointer', paddingBottom: 16 }}
            >
              <div style={{
                padding: '10px 14px', borderRadius: 10,
                background: isActive ? 'rgba(92,16,32,0.04)' : '#fff',
                border: `1px solid ${isActive ? 'rgba(92,16,32,0.2)' : 'var(--color-cream-border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 2 }}>
                      {p.start_date}{p.end_date ? ` — ${p.end_date}` : (isActive ? ' — Present' : '')}
                    </div>
                  </div>
                  {isActive && (
                    <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: 'rgba(29,158,117,0.15)', color: 'var(--color-flag-green)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      Active
                    </span>
                  )}
                </div>
                {p.deactivation_reason && (
                  <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 4 }}>
                    {p.deactivation_reason}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Wire it into Programs.jsx**

In `pitcher_program_app/mini-app/src/pages/Plans.jsx`, add:
```jsx
import ProgramHistoryTimeline from '../components/ProgramHistoryTimeline';
```
And add a second `useApi` call right after the existing one:
```jsx
const { data: historyData } = useApi(
  pitcherId ? `/api/pitcher/${pitcherId}/program/history` : null,
  initData
);
```
Then render it at the bottom of the page, after `<TodayDetailCard ... />`:
```jsx
<ProgramHistoryTimeline programs={historyData?.programs} />
```

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/ProgramHistoryTimeline.jsx pitcher_program_app/mini-app/src/pages/Plans.jsx
git commit -m "Add ProgramHistoryTimeline component to Programs page"
```

---

### Task 6.6: ProgramDetail page

**Files:**
- Create: `pitcher_program_app/mini-app/src/pages/ProgramDetail.jsx`
- Modify: `pitcher_program_app/mini-app/src/App.jsx`

- [ ] **Step 1: Write the ProgramDetail page**

```jsx
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';

export default function ProgramDetail() {
  const { programId } = useParams();
  const navigate = useNavigate();
  const { initData } = useAuth();
  const { data, loading } = useApi(programId ? `/api/program/${programId}` : null, initData);

  if (loading) return <div style={{ padding: 16 }}>Loading...</div>;
  if (!data?.program) return <div style={{ padding: 16 }}>Program not found.</div>;

  const { program, template, current_phase } = data;
  const phases = program.phases_snapshot || [];

  return (
    <div style={{ paddingBottom: 100 }}>
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: 'transparent', border: 'none', color: 'var(--color-rose-blush)', fontSize: 12, cursor: 'pointer', padding: 0 }}
        >‹ Back</button>
        <div style={{ fontSize: 19, fontWeight: 700, color: '#fff', marginTop: 4, letterSpacing: -0.3 }}>
          {program.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--color-rose-blush)', marginTop: 4 }}>
          {program.start_date}{program.end_date ? ` — ${program.end_date}` : ' — ongoing'} · {template?.role}
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
          Phases
        </div>
        {phases.map((phase, i) => {
          const isCurrent = current_phase?.phase_id === phase.phase_id && !current_phase?.is_past_end;
          return (
            <div key={phase.phase_id} style={{
              padding: '12px 14px', borderRadius: 10,
              background: isCurrent ? 'rgba(92,16,32,0.05)' : '#fff',
              border: `1px solid ${isCurrent ? 'rgba(92,16,32,0.25)' : 'var(--color-cream-border)'}`,
              marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>
                  {i + 1}. {phase.name}
                </div>
                <div style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>
                  {phase.week_count} week{phase.week_count === 1 ? '' : 's'}
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 4 }}>
                Type: {phase.phase_type}
                {phase.default_training_intent && ` · Intent: ${phase.default_training_intent}`}
              </div>
              {isCurrent && (
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-maroon)', marginTop: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Current · week {current_phase.week_in_phase} of {phase.week_count}
                </div>
              )}
            </div>
          );
        })}

        {template && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginTop: 20, marginBottom: 10 }}>
              Template
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 10, background: '#fff', border: '1px solid var(--color-cream-border)' }}>
              <div style={{ fontSize: 12, color: 'var(--color-ink-secondary)' }}>{template.description}</div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 6 }}>
                Rotation length: {template.rotation_length} days · Templates: {(template.rotation_template_keys || []).join(', ')}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Register the route in App.jsx**

```bash
cd pitcher_program_app && grep -n "Routes\|Route path" mini-app/src/App.jsx
```

In `pitcher_program_app/mini-app/src/App.jsx`, add the import:
```jsx
import ProgramDetail from './pages/ProgramDetail';
```
And add the route inside the `<Routes>` block (sibling to existing routes):
```jsx
<Route path="/programs/:programId" element={<ProgramDetail />} />
```

- [ ] **Step 3: Verify the route compiles**

```bash
cd pitcher_program_app/mini-app && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/mini-app/src/pages/ProgramDetail.jsx pitcher_program_app/mini-app/src/App.jsx
git commit -m "Add ProgramDetail page + route registration"
```

---

### Task 6.7: Update nav label

**Files:**
- Modify: `pitcher_program_app/mini-app/src/Layout.jsx`

- [ ] **Step 1: Find the bottom nav label**

```bash
cd pitcher_program_app && grep -n "Plans\|My Program\|/plans" mini-app/src/Layout.jsx
```

- [ ] **Step 2: Change the label**

In `Layout.jsx`, find the nav item pointing to `/plans` and change its label from "Plans" (or "Plan", or whatever currently shows) to "Programs". Leave the route path `/plans` unchanged in v1 — no broken bookmarks.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/mini-app/src/Layout.jsx
git commit -m "Rename nav label Plans → Programs"
```

---

## Phase 7 — Final Verification + Deploy

Goal: Diff harness one more time, smoke test the full path, deploy to Railway and Vercel.

### Task 7.1: Final diff harness

- [ ] **Step 1: Run the diff harness**

```bash
cd pitcher_program_app && python -m scripts.verify_plan_gen_unchanged
```

Expected: `PASS — plan generation byte-identical for N pitchers`. If FAIL, STOP and investigate before proceeding.

- [ ] **Step 2: Run the phase compute verification**

```bash
cd pitcher_program_app && python -m scripts.verify_compute_current_phase
```

Expected: `9/9 cases passed`.

- [ ] **Step 3: Run the throw intent parser verification**

```bash
cd pitcher_program_app && python -m scripts.verify_throw_intent_parser
```

Expected: `11/11 cases passed`.

---

### Task 7.2: Smoke test against staging API

- [ ] **Step 1: Start API locally**

```bash
cd pitcher_program_app && DISABLE_AUTH=true python -m api.main &
sleep 1
```

- [ ] **Step 2: Smoke endpoints for Russell, Hartrick, Lazar**

```bash
for pid in landon_brice pitcher_hartrick_001 pitcher_lazar_001; do
  echo "=== $pid ==="
  curl -s http://localhost:8000/api/pitcher/$pid/program | python -m json.tool | head -40
done
```

Each must return a populated program. Russell should show "In-Season Starter Protocol", Hartrick "In-Season Short Relief", Lazar "In-Season Short Relief".

- [ ] **Step 3: Stop API**

```bash
kill %1 2>/dev/null || true
```

---

### Task 7.3: Deploy

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

Railway and Vercel auto-deploy on push.

- [ ] **Step 2: Wait for deploys to complete**

Check Railway dashboard and Vercel dashboard. Wait for both to go green.

- [ ] **Step 3: Smoke test production**

```bash
curl -s https://baseball-production-9d28.up.railway.app/api/staff/pulse | python -m json.tool
```

Expected: 200 response (or the existing known 500 — that's a separate issue, not introduced by this change).

- [ ] **Step 4: Open the mini-app in Telegram and verify the Programs tab renders for landon_brice**

Expected: hero card with "In-Season Starter Protocol · Week N", week arc with day bubbles, schedule card (may be empty if no games scraped), today card.

---

### Task 7.4: Post-deploy verification

- [ ] **Step 1: Check production logs for errors**

Railway dashboard → service → logs. Look for any new exceptions in the past hour.

- [ ] **Step 2: Trigger a check-in for one pitcher**

Via the bot: `/checkin` against test_pitcher_001. Confirm:
- Check-in completes
- `current_week_state.phase` is updated in DB (verify via Supabase MCP)
- Plan generation still produces a plan (no regression)

- [ ] **Step 3: Tag the deploy**

```bash
git tag programs-tab-v1
git push origin programs-tab-v1
```

---

## Post-Deployment Next Steps

These are explicitly out of scope for v1 but listed in the spec's "Post-Deployment Next Steps" section. Each becomes its own brainstorm + spec + plan cycle:

1. Off-season periodization logic activation (`_blend_phase_with_rotation` full implementation)
2. Build New program wizard
3. Coach-facing template editor
4. Exercise progression curves
5. Weight logging UI
6. Ledger / modification history
7. Schedule-driven rotation auto-shift
8. Coach dashboard
9. Reliever appearance projection
10. Self-reported throws → bot proactive suggestions
11. `saved_plans` cleanup

End of plan.
