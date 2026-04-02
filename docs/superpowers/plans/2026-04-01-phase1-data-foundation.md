# Phase 1: Data Foundation — Pitcher Training Model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `active_flags` table with a consolidated `pitcher_training_model` table, enrich `weekly_summaries` with structured data, and add new exercise intelligence fields — without breaking any existing functionality.

**Architecture:** The migration uses a compatibility layer: `_profile_from_row()` continues to attach data as `profile["active_flags"]` but reads from the new `pitcher_training_model` table. All existing code that reads `profile.get("active_flags", {})` works unchanged. Write functions (`update_active_flags`, `increment_days_since_outing`) are redirected to the new table. Once all reads/writes are confirmed working, the old `active_flags` table is dropped.

**Tech Stack:** Supabase (Postgres), Python 3.11, Supabase MCP or dashboard SQL editor for migrations.

**Spec:** `docs/superpowers/specs/2026-04-01-pitcher-model-plan-quality-design.md` (System 1)

---

### Task 1: Create `pitcher_training_model` Table in Supabase

**Files:**
- Execute SQL via Supabase MCP or dashboard

- [ ] **Step 1: Run the migration SQL**

```sql
CREATE TABLE IF NOT EXISTS pitcher_training_model (
  pitcher_id TEXT PRIMARY KEY REFERENCES pitchers(id),

  -- Absorbed from active_flags --
  current_arm_feel        INTEGER,
  current_flag_level      TEXT,
  days_since_outing       INTEGER DEFAULT 0,
  last_outing_date        DATE,
  last_outing_pitches     INTEGER,
  phase                   TEXT,
  active_modifications    TEXT[] DEFAULT '{}',
  next_outing_days        INTEGER,
  grip_drop_reported      BOOLEAN DEFAULT FALSE,

  -- Exercise intelligence (new) --
  working_weights         JSONB DEFAULT '{}',
  exercise_preferences    JSONB DEFAULT '{}',
  equipment_constraints   TEXT[] DEFAULT '{}',
  recent_swap_history     JSONB DEFAULT '[]',

  -- Weekly arc (new) --
  current_week_state      JSONB DEFAULT '{}',

  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_pitcher_training_model_updated_at
  BEFORE UPDATE ON pitcher_training_model
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS (match active_flags pattern)
ALTER TABLE pitcher_training_model ENABLE ROW LEVEL SECURITY;

-- Service role bypass (same as other tables)
CREATE POLICY "Service role full access" ON pitcher_training_model
  FOR ALL USING (true) WITH CHECK (true);
```

Run: via Supabase MCP `execute_sql` or Supabase dashboard SQL editor.

- [ ] **Step 2: Verify the table exists**

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'pitcher_training_model' ORDER BY ordinal_position;
```

Expected: All columns listed above with correct types.

- [ ] **Step 3: Commit migration record**

Create `pitcher_program_app/scripts/migrations/003_pitcher_training_model.sql` with the SQL above for version control.

```bash
mkdir -p pitcher_program_app/scripts/migrations
```

```bash
git add pitcher_program_app/scripts/migrations/003_pitcher_training_model.sql
git commit -m "feat: add pitcher_training_model table migration SQL"
```

---

### Task 2: Add `pitcher_training_model` CRUD Functions to `db.py`

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py` (after line 87, replacing the Active Flags section)

- [ ] **Step 1: Add the new functions to db.py**

Add these functions after the Injury History section (line 72). Keep the existing `get_active_flags` and `upsert_active_flags` functions for now — they'll be removed in Task 6.

```python
# ---------------------------------------------------------------------------
# Pitcher Training Model
# ---------------------------------------------------------------------------

def get_training_model(pitcher_id: str) -> dict:
    """Return pitcher_training_model row. Returns empty dict if none."""
    resp = get_client().table("pitcher_training_model").select("*").eq("pitcher_id", pitcher_id).execute()
    return resp.data[0] if resp.data else {}


def upsert_training_model(pitcher_id: str, data: dict) -> None:
    """Insert or update pitcher_training_model row."""
    data["pitcher_id"] = pitcher_id
    data.pop("updated_at", None)  # Let Postgres DEFAULT handle timestamp
    get_client().table("pitcher_training_model").upsert(data, on_conflict="pitcher_id").execute()


def update_training_model_partial(pitcher_id: str, updates: dict) -> None:
    """Partial update of pitcher_training_model fields (PATCH semantics).
    
    For top-level columns, merges updates into existing row.
    For JSONB fields, use upsert_training_model with the full field value.
    """
    current = get_training_model(pitcher_id)
    if not current:
        updates["pitcher_id"] = pitcher_id
        get_client().table("pitcher_training_model").insert(updates).execute()
        return
    current.update(updates)
    current.pop("updated_at", None)  # Let Postgres DEFAULT handle timestamp
    get_client().table("pitcher_training_model").upsert(current, on_conflict="pitcher_id").execute()
```

- [ ] **Step 2: Verify the functions work**

Run a quick sanity check in the Python REPL or a test script:

```bash
cd pitcher_program_app && python -c "
from bot.services.db import get_training_model, upsert_training_model
# Should return empty dict for non-existent pitcher
result = get_training_model('test_pitcher_001')
print('get_training_model:', result)
print('OK' if isinstance(result, dict) else 'FAIL')
"
```

Expected: Returns empty dict `{}` (no data migrated yet) or the row if test_pitcher_001 already has data.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/services/db.py
git commit -m "feat: add pitcher_training_model CRUD functions to db.py"
```

---

### Task 3: Migrate Data from `active_flags` → `pitcher_training_model`

**Files:**
- Create: `pitcher_program_app/scripts/migrate_active_flags_to_model.py`

- [ ] **Step 1: Write the migration script**

```python
"""One-time migration: copy active_flags rows into pitcher_training_model.

Safe to re-run (upserts). Does not delete active_flags data.

Usage:
    python -m scripts.migrate_active_flags_to_model [--dry-run]
"""

import argparse
import logging
import sys

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
```

- [ ] **Step 2: Run dry-run to verify**

```bash
cd pitcher_program_app && python -m scripts.migrate_active_flags_to_model --dry-run
```

Expected: Lists all 12 pitchers with their current arm_feel, flag_level, days_since_outing.

- [ ] **Step 3: Run the actual migration**

```bash
cd pitcher_program_app && python -m scripts.migrate_active_flags_to_model
```

Expected: `Migration complete. 12 rows migrated.`

- [ ] **Step 4: Verify data in Supabase**

```sql
SELECT pitcher_id, current_arm_feel, current_flag_level, days_since_outing
FROM pitcher_training_model ORDER BY pitcher_id;
```

Expected: 12 rows matching the active_flags data.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/migrate_active_flags_to_model.py
git commit -m "feat: migrate active_flags data to pitcher_training_model"
```

---

### Task 4: Redirect `db.py` Active Flags Functions to New Table

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py:78-87`

This is the key compatibility step. The existing `get_active_flags()` and `upsert_active_flags()` functions are called from 15+ files. Instead of updating all callers, redirect these functions to read/write `pitcher_training_model`.

- [ ] **Step 1: Update `get_active_flags` to read from `pitcher_training_model`**

Replace the Active Flags section (lines 74-87) in `db.py`:

```python
# ---------------------------------------------------------------------------
# Active Flags (compatibility — reads from pitcher_training_model)
# ---------------------------------------------------------------------------

# Columns that map to the old active_flags shape.
_ACTIVE_FLAGS_COLUMNS = (
    "pitcher_id, current_arm_feel, current_flag_level, days_since_outing, "
    "last_outing_date, last_outing_pitches, phase, active_modifications, "
    "next_outing_days, grip_drop_reported"
)


def get_active_flags(pitcher_id: str) -> dict:
    """Return active_flags-shaped dict from pitcher_training_model.
    
    Compatibility wrapper — all existing callers continue to work.
    """
    resp = (get_client().table("pitcher_training_model")
            .select(_ACTIVE_FLAGS_COLUMNS)
            .eq("pitcher_id", pitcher_id)
            .execute())
    return resp.data[0] if resp.data else {}


def upsert_active_flags(pitcher_id: str, flags: dict) -> None:
    """Write active_flags-shaped dict to pitcher_training_model.
    
    Compatibility wrapper — filters to only active_flags columns
    to prevent accidental overwrites of new model fields.
    """
    allowed = {
        "pitcher_id", "current_arm_feel", "current_flag_level",
        "days_since_outing", "last_outing_date", "last_outing_pitches",
        "phase", "active_modifications", "next_outing_days", "grip_drop_reported",
    }
    filtered = {k: v for k, v in flags.items() if k in allowed}
    filtered["pitcher_id"] = pitcher_id
    get_client().table("pitcher_training_model").upsert(
        filtered, on_conflict="pitcher_id"
    ).execute()
```

- [ ] **Step 2: Run the bot locally to verify nothing breaks**

```bash
cd pitcher_program_app && python -c "
from bot.services.db import get_active_flags, upsert_active_flags
# Test read
flags = get_active_flags('landon_brice')
print('Read flags:', flags)
assert 'current_arm_feel' in flags or flags == {}, f'Unexpected: {flags}'
print('Read OK')

# Test write (safe — just re-upserts existing data)
if flags:
    upsert_active_flags('landon_brice', flags)
    print('Write OK')
else:
    print('No flags to re-write (pitcher not in model yet)')
"
```

Expected: Read and write succeed, data matches.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/services/db.py
git commit -m "refactor: redirect active_flags functions to pitcher_training_model table"
```

---

### Task 5: Enrich `weekly_summaries` Table

**Files:**
- Execute SQL via Supabase MCP or dashboard
- Modify: `pitcher_program_app/bot/services/db.py:196-212`

- [ ] **Step 1: Add structured columns to weekly_summaries**

```sql
ALTER TABLE weekly_summaries
  ADD COLUMN IF NOT EXISTS avg_arm_feel FLOAT,
  ADD COLUMN IF NOT EXISTS avg_sleep FLOAT,
  ADD COLUMN IF NOT EXISTS exercise_completion_rate FLOAT,
  ADD COLUMN IF NOT EXISTS exercises_skipped JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS throwing_sessions INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_throws INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS flag_distribution JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS movement_pattern_balance JSONB DEFAULT '{}';
```

Run via Supabase MCP or dashboard.

- [ ] **Step 2: Update `upsert_weekly_summary` to accept structured fields**

Replace the function in `db.py` (lines 196-202):

```python
def upsert_weekly_summary(pitcher_id: str, week_start: str, summary: dict,
                          structured: dict = None) -> None:
    """Upsert a weekly summary row.
    
    Args:
        pitcher_id: Pitcher ID
        week_start: ISO date string (Monday of week)
        summary: Dict with narrative, headline, generated_at (stored as JSONB)
        structured: Optional dict with enriched fields:
            avg_arm_feel, avg_sleep, exercise_completion_rate,
            exercises_skipped, throwing_sessions, total_throws,
            flag_distribution, movement_pattern_balance
    """
    row = {
        "pitcher_id": pitcher_id,
        "week_start": week_start,
        "summary": summary,
    }
    if structured:
        for key in ("avg_arm_feel", "avg_sleep", "exercise_completion_rate",
                     "exercises_skipped", "throwing_sessions", "total_throws",
                     "flag_distribution", "movement_pattern_balance"):
            if key in structured:
                row[key] = structured[key]
    get_client().table("weekly_summaries").upsert(row, on_conflict="pitcher_id,week_start").execute()
```

- [ ] **Step 3: Verify the enriched upsert works**

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'weekly_summaries' ORDER BY ordinal_position;
```

Expected: Original columns plus the 8 new columns.

- [ ] **Step 4: Save migration SQL and commit**

Create `pitcher_program_app/scripts/migrations/004_enrich_weekly_summaries.sql` with the ALTER TABLE SQL.

```bash
git add pitcher_program_app/scripts/migrations/004_enrich_weekly_summaries.sql pitcher_program_app/bot/services/db.py
git commit -m "feat: enrich weekly_summaries with structured aggregation columns"
```

---

### Task 6: Update `context_manager.py` — Training Model Awareness

**Files:**
- Modify: `pitcher_program_app/bot/services/context_manager.py`

The key change: `update_active_flags()` and `increment_days_since_outing()` now write to `pitcher_training_model`. The `_profile_from_row()` function already works via the compatibility layer (Task 4), but we'll also add a helper to access the full model (including new fields like `exercise_preferences`).

- [ ] **Step 1: Add `get_training_model` import and helper**

At the top of `context_manager.py`, update the import from db:

Find the existing import line (should be something like `from bot.services import db as _db`) and after it, add:

```python
def load_training_model(pitcher_id: str) -> dict:
    """Load the full pitcher_training_model row.
    
    Returns the complete model including exercise intelligence
    and weekly state fields. For active_flags-compatible access,
    use load_profile() which attaches flags via _profile_from_row().
    """
    return _db.get_training_model(pitcher_id)
```

- [ ] **Step 2: Update `update_active_flags` to also touch `updated_at`**

The existing `update_active_flags` function at line 263 uses `_db.get_active_flags` + `_db.upsert_active_flags`. Since Task 4 already redirected those to `pitcher_training_model`, this function works as-is. No code change needed — just verify:

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import update_active_flags
# Verify it writes to pitcher_training_model (not active_flags)
update_active_flags('test_pitcher_001', {'current_arm_feel': 4})
print('update_active_flags OK')
"
```

Expected: Writes to `pitcher_training_model` table (confirmed by checking Supabase).

- [ ] **Step 3: Verify `increment_days_since_outing` works through compatibility layer**

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import increment_days_since_outing
from bot.services.db import get_training_model
before = get_training_model('test_pitcher_001')
print(f'Before: days_since_outing = {before.get(\"days_since_outing\", \"N/A\")}')
# increment_days_since_outing('test_pitcher_001')  # Uncomment to test write
print('increment_days_since_outing: reads OK')
"
```

Expected: Reads `days_since_outing` from `pitcher_training_model`.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/context_manager.py
git commit -m "feat: add load_training_model helper to context_manager"
```

---

### Task 7: Update `progression.py` — Write Structured Weekly Data

**Files:**
- Modify: `pitcher_program_app/bot/services/progression.py`

Currently `build_week_snapshot()` computes weekly aggregates on-the-fly and returns them. `generate_weekly_narrative()` calls it, sends the snapshot to the LLM, and stores only the narrative. We now also store the structured data.

- [ ] **Step 1: Update `generate_weekly_narrative` to store structured data**

Find the `generate_weekly_narrative()` function (around line 431). Locate where it calls `_db.upsert_weekly_summary()` (around line 470). The current call looks like:

```python
_db.upsert_weekly_summary(pitcher_id, week_start, {
    "narrative": result.get("narrative", ""),
    "headline": result.get("headline", ""),
    "generated_at": datetime.now(CHICAGO_TZ).isoformat(),
})
```

Replace that call with:

```python
# Build structured summary from the snapshot
structured = {
    "avg_arm_feel": snapshot.get("week", {}).get("arm_feel", {}).get("avg"),
    "avg_sleep": snapshot.get("week", {}).get("sleep", {}).get("avg"),
    "exercise_completion_rate": snapshot.get("week", {}).get("exercise_completion", {}).get("rate"),
    "exercises_skipped": snapshot.get("week", {}).get("skipped_exercises", {}),
    "throwing_sessions": len(snapshot.get("week", {}).get("throwing", [])),
    "total_throws": sum(
        t.get("throw_count", 0) for t in snapshot.get("week", {}).get("throwing", [])
    ),
    "flag_distribution": snapshot.get("week", {}).get("flag_levels", {}),
    "movement_pattern_balance": {},  # Phase 2 will populate this
}

_db.upsert_weekly_summary(
    pitcher_id, week_start,
    {
        "narrative": result.get("narrative", ""),
        "headline": result.get("headline", ""),
        "generated_at": datetime.now(CHICAGO_TZ).isoformat(),
    },
    structured=structured,
)
```

Note: You need to capture the `snapshot` variable. Find where `build_week_snapshot(pitcher_id)` is called earlier in the function (around line 440) and make sure the variable name matches. It's likely already called `snapshot` or `week_snapshot` — use the existing variable name.

- [ ] **Step 2: Verify the narrative generation still works**

```bash
cd pitcher_program_app && python -c "
from bot.services.progression import build_week_snapshot
snapshot = build_week_snapshot('landon_brice')
print('Snapshot keys:', list(snapshot.keys()) if snapshot else 'None')
week = snapshot.get('week', {}) if snapshot else {}
print('Week keys:', list(week.keys()) if week else 'None')
print('arm_feel:', week.get('arm_feel'))
print('exercise_completion:', week.get('exercise_completion'))
print('throwing:', len(week.get('throwing', [])), 'sessions')
"
```

Expected: Snapshot builds successfully with arm_feel, exercise_completion, and throwing data.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/services/progression.py
git commit -m "feat: store structured weekly data alongside narrative in weekly_summaries"
```

---

### Task 8: Verify Full System Compatibility

**Files:**
- No file changes — verification only

This task confirms that all existing code paths work through the compatibility layer.

- [ ] **Step 1: Verify profile loading includes active_flags from new table**

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import load_profile
profile = load_profile('landon_brice')
flags = profile.get('active_flags', {})
print('Profile loaded:', profile.get('name'))
print('active_flags keys:', list(flags.keys()))
print('arm_feel:', flags.get('current_arm_feel'))
print('flag_level:', flags.get('current_flag_level'))
print('days_since_outing:', flags.get('days_since_outing'))
assert 'current_arm_feel' in flags or flags == {}, 'active_flags not loaded'
print('PASS')
"
```

Expected: Profile loads with active_flags populated from pitcher_training_model.

- [ ] **Step 2: Verify triage reads active_flags correctly**

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import load_profile
from bot.services.triage import triage
profile = load_profile('landon_brice')
result = triage(
    arm_feel=4,
    sleep_hours=7.5,
    pitcher_profile=profile,
)
print('Triage result:', result.get('flag_level'))
print('Reasoning:', result.get('reasoning', '')[:100])
print('PASS')
"
```

Expected: Triage completes with a flag_level, using active_flags from the new table.

- [ ] **Step 3: Verify context building for LLM**

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import load_context
ctx = load_context('landon_brice')
print('Context length:', len(ctx), 'chars')
print('Has arm feel:', 'Arm Feel' in ctx)
print('Has flag level:', 'Flag Level' in ctx)
print('Has days since:', 'Days Since' in ctx)
print('PASS' if 'Arm Feel' in ctx else 'FAIL')
"
```

Expected: Context string includes arm feel, flag level, days since outing — all read from pitcher_training_model.

- [ ] **Step 4: Verify API profile endpoint returns active_flags**

```bash
cd pitcher_program_app && python -c "
from bot.services.context_manager import load_profile
profile = load_profile('landon_brice')
# Simulate what routes.py does
flags = profile.get('active_flags', {})
rotation_day = flags.get('days_since_outing', 0)
flag_level = flags.get('current_flag_level', 'unknown')
print(f'rotation_day={rotation_day}, flag_level={flag_level}')
print('PASS')
"
```

Expected: Reads rotation_day and flag_level from the new table.

- [ ] **Step 5: Spot-check the mini-app profile endpoint**

Start the API locally and hit the profile endpoint:

```bash
cd pitcher_program_app && timeout 5 python -m api.main &
sleep 2
curl -s http://localhost:8000/api/pitcher/landon_brice/profile?DISABLE_AUTH=true | python -m json.tool | head -30
kill %1 2>/dev/null
```

Expected: Profile JSON includes `active_flags` with data from pitcher_training_model.

---

### Task 9: Drop `active_flags` Table

**Files:**
- Execute SQL via Supabase MCP or dashboard
- Modify: `pitcher_program_app/bot/services/db.py` (remove old comment)

**IMPORTANT:** Only proceed with this task after Task 8 passes all verification steps.

- [ ] **Step 1: Verify no direct `active_flags` table references remain in runtime code**

Search for any code that directly references the `active_flags` *table name* (not the `profile["active_flags"]` dict key):

```bash
cd pitcher_program_app && grep -rn '"active_flags"' bot/ api/ --include="*.py" | grep -v "__pycache__" | grep "table("
```

Expected: Only `db.py` should reference `table("active_flags")` — and after Task 4, those lines were replaced to use `pitcher_training_model`. If any other file directly queries the `active_flags` table, fix it first.

- [ ] **Step 2: Rename the table as a soft delete (reversible)**

```sql
ALTER TABLE active_flags RENAME TO active_flags_deprecated;
```

- [ ] **Step 3: Run verification suite again (Task 8 steps 1-4)**

Re-run the verification from Task 8 to confirm nothing broke with the table renamed.

- [ ] **Step 4: If all passes, drop the deprecated table**

```sql
DROP TABLE IF EXISTS active_flags_deprecated;
```

- [ ] **Step 5: Update the db.py comment header**

In `db.py`, update the Active Flags section comment:

```python
# ---------------------------------------------------------------------------
# Active Flags (compatibility layer — backed by pitcher_training_model)
# ---------------------------------------------------------------------------
```

- [ ] **Step 6: Save migration SQL and commit**

Create `pitcher_program_app/scripts/migrations/005_drop_active_flags.sql`:

```sql
-- Step 1: Rename (soft delete) -- run first, verify, then step 2
-- ALTER TABLE active_flags RENAME TO active_flags_deprecated;

-- Step 2: Drop (after verification)
-- DROP TABLE IF EXISTS active_flags_deprecated;

-- Note: active_flags data was migrated to pitcher_training_model
-- via scripts/migrate_active_flags_to_model.py
```

```bash
git add pitcher_program_app/scripts/migrations/005_drop_active_flags.sql pitcher_program_app/bot/services/db.py
git commit -m "refactor: drop active_flags table, fully backed by pitcher_training_model"
```

---

### Task 10: Update `CLAUDE.md` and Migration Script References

**Files:**
- Modify: `CLAUDE.md`
- Modify: `pitcher_program_app/scripts/migrate_to_supabase.py`

- [ ] **Step 1: Update Supabase Schema table in CLAUDE.md**

Find the Supabase Schema section in `CLAUDE.md`. Replace the `active_flags` row and add the `pitcher_training_model` row:

Replace:
```
| `active_flags` | Current state per pitcher — arm_feel, flag_level, days_since_outing, modifications |
```

With:
```
| `pitcher_training_model` | Consolidated pitcher state — arm_feel, flag_level, days_since_outing, modifications, exercise preferences, equipment constraints, swap history, weekly arc |
```

- [ ] **Step 2: Update Context System section in CLAUDE.md**

Find the line that mentions `active_flags` in the Context System section:
```
Supabase-only. `context_manager.py` queries recent `chat_messages` + `daily_entries` + `active_flags` from Supabase to build LLM context.
```

Replace with:
```
Supabase-only. `context_manager.py` queries recent `chat_messages` + `daily_entries` + `pitcher_training_model` from Supabase to build LLM context. The `pitcher_training_model` table consolidates what was previously `active_flags` plus exercise intelligence (preferences, equipment constraints, swap history) and weekly training arc state.
```

- [ ] **Step 3: Add Pitcher Training Model section to CLAUDE.md Key Patterns**

After the DB Column Whitelist section, add:

```markdown
### Pitcher Training Model
- Consolidates the old `active_flags` table + new exercise intelligence fields
- `profile["active_flags"]` dict is still populated via compatibility layer in `_profile_from_row()` — reads from `pitcher_training_model` table
- New fields (exercise_preferences, equipment_constraints, working_weights, recent_swap_history, current_week_state) accessed via `load_training_model(pitcher_id)` in context_manager
- `update_active_flags()` writes to `pitcher_training_model` (filtered to flag columns only)
- `weekly_summaries` table enriched with structured columns (avg_arm_feel, exercise_completion_rate, flag_distribution, etc.) alongside LLM narrative
```

- [ ] **Step 4: Update the `migrate_active_flags` function reference in migrate_to_supabase.py**

In `pitcher_program_app/scripts/migrate_to_supabase.py`, find `migrate_active_flags()` (around line 162). Add a deprecation comment:

```python
def migrate_active_flags(sb: Client, dry_run: bool):
    """DEPRECATED: active_flags table replaced by pitcher_training_model.
    
    Use scripts/migrate_active_flags_to_model.py instead.
    Kept for reference only.
    """
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md pitcher_program_app/scripts/migrate_to_supabase.py
git commit -m "docs: update CLAUDE.md for pitcher_training_model migration, deprecate old migration"
```

---

## Summary: What This Phase Achieves

After completing all 10 tasks:

1. **`pitcher_training_model` table exists** with all absorbed `active_flags` columns + new exercise intelligence + weekly state fields
2. **`active_flags` table is dropped** — no longer exists
3. **All existing code works unchanged** — `profile["active_flags"]` still populated via compatibility layer
4. **`weekly_summaries` enriched** with structured aggregation columns (avg_arm_feel, exercise_completion_rate, etc.)
5. **New access path available** — `load_training_model(pitcher_id)` returns the full model including new fields
6. **Foundation ready** for Phase 2 (swap UI reads exercise_preferences/equipment_constraints) and Phase 3 (LLM review reads current_week_state)

## What NOT to Do in This Phase

- Do not change any frontend code — `profile.active_flags` shape is unchanged
- Do not populate `current_week_state` yet — that's Phase 2/3
- Do not add exercise swap endpoints — that's Phase 2
- Do not change the plan generation flow — that's Phase 3
- Do not change triage.py, plan_generator.py, or any handler code — the compatibility layer handles it
