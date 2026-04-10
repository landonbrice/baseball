# Programs Tab Redesign + Periodization Layer

> Design spec — 2026-04-09
> Status: Approved for implementation planning
> Targets: April 2026 in-season rollout (zero behavioral risk to current pitchers)

## Problem Statement

The current "Plans" tab in the mini-app (`Plans.jsx`) treats a "plan" as a frozen snapshot of one day's exercises — a personal bookmark, not a program. There is no first-class concept of a multi-week training program, no phase tracking, no week-of-phase progression, and no surface for the UChicago game schedule. The UI is a flat active/past list with activate/deactivate toggles.

Meanwhile, the backend has the *raw materials* for periodization but no orchestration:

- Every exercise in the library has per-phase prescriptions (`strength`, `hypertrophy`, `power`, `endurance`) — already used by `exercise_pool._format_exercise()`
- `pitcher_training_model` has a `phase` column — unused
- `current_week_state` JSONB exists for weekly arc tracking — has no phase fields
- `_get_training_intent(rotation_day, triage_result)` decides daily intent from rotation day + triage flag only — completely unaware of where a pitcher is in any larger training block

The chasm: there is no entity that says "Russell is in week 6 of an in-season starter program" or "Lazar is in week 2 of return-to-throwing." The system cannot show the pitcher their week ahead in the context of a larger arc, cannot overlay the team's actual game schedule, and cannot enforce phase-progressive prescription selection in off-season.

This spec adds that orchestration layer + the UI to surface it, with strict scope discipline so the in-season April rollout carries zero behavioral risk.

## Goals

1. **Replace the Plans tab with a Programs tab** rendering an active multi-week program, a week arc with rotation-day content, the UChicago game schedule, and a today detail card.
2. **Introduce training programs as a first-class entity** — multi-week, phase-aware, role-specific, coach-authored from a seed template library.
3. **Surface the UChicago game schedule** as a visual layer on the week arc and as a standalone "Maroons · This Week" card. Read-only overlay; no auto-shift of rotation.
4. **Capture self-reported throwing events** (bullpens, sides, long toss, catch) via both chat parsing and an explicit UI button. Both write to one shared field that the week arc reads.
5. **Lay the data scaffolding for periodization** that off-season phase logic can plug into later, without firing any of that logic for in-season pitchers in v1.
6. **Ship to the existing UChicago staff with zero behavioral change to daily plan generation.** The Programs tab is purely additive UI + new tables. `_get_training_intent` is gated by phase type and only consults phase data when the pitcher is NOT in-season.

## Non-Goals (v1)

- **Off-season periodization logic firing.** Data structures exist (`phase`, `week_of_phase`, `phase_microcycle`) but `_get_training_intent` will only consult them when phase type ∈ {off-season, pre-season, return-to-throwing}. No current pitcher will hit this path.
- **Build New program wizard.** Coach swaps a pitcher's program via existing chat ("switch Russell to In-Season Starter B") which writes to `active_program_id`. No UI builder.
- **Coach-facing template editor.** Templates are seed JSON committed to the repo, applied via migration script. Coach edits = code change in v1.
- **Schedule-driven rotation auto-shift.** Pitchers and coach manually anchor next outings via `/set-next-outing`. The schedule is shown but doesn't reassign rotation days.
- **Exercise progression curves.** No tracking of "Russell's deadlift week-over-week" — that's a separate concern.
- **Weight logging UI.** `working_weights` column stays unused in v1.
- **Coach dashboard.** Out of scope.
- **Migration of existing `saved_plans` records.** The table stays as-is, gets hidden from the Programs tab UI, and is left to die quietly or get repurposed later. No data migration.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              Seed Template Library                    │
│  data/program_templates/*.json  (committed to repo)  │
│  in_season_starter, in_season_short_relief,          │
│  in_season_long_relief, return_to_throwing           │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│           program_templates (Supabase)                │
│  Reference data, seeded via scripts/seed_programs.py │
│  Phase definitions, weekly microcycles, role         │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│           training_programs (Supabase)                │
│  Per-pitcher instance of a template                  │
│  start_date, current_week, phases (JSONB)            │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│   pitcher_training_model.active_program_id (FK)      │
│   pitcher_training_model.current_week_state extends: │
│     phase, week_of_phase, scheduled_throws[]          │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│   Daily Plan Generation (plan_generator.py)          │
│   _get_training_intent() — phase-aware GATE:         │
│     if phase_type == in_season → existing logic      │
│     else → consult phase + week_of_phase microcycle  │
└──────────────────────────────────────────────────────┘
```

## Data Model

### New Table: `program_templates`

Reference data — the seed library that coach-authored programs are instantiated from. One row per template type. Seeded from JSON files committed to the repo via `scripts/seed_program_templates.py`.

```sql
CREATE TABLE program_templates (
    id TEXT PRIMARY KEY,                      -- 'in_season_starter', 'return_to_throwing', etc.
    name TEXT NOT NULL,                       -- 'In-Season Starter Protocol'
    role TEXT NOT NULL,                       -- 'starter' | 'short_relief' | 'long_relief' | 'any'
    phase_type TEXT NOT NULL,                 -- 'in_season' | 'off_season' | 'pre_season' | 'return_to_throwing'
    rotation_length INTEGER NOT NULL,         -- 7 for starters, 3 for relievers
    default_total_weeks INTEGER,              -- e.g. 12 for a season
    description TEXT,
    phases JSONB NOT NULL,                    -- see phases JSONB shape below
    rotation_template_keys JSONB,             -- array of template file names from data/templates/ for each rotation day
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**`phases` JSONB shape:**
```json
[
  {
    "phase_id": "in_season_main",
    "name": "Maintenance",
    "phase_type": "in_season",
    "week_count": 12,
    "default_training_intent": null,
    "microcycle": null
  }
]
```

For an off-season template, the same structure looks like:
```json
[
  {
    "phase_id": "off_hyp",
    "name": "Hypertrophy Block",
    "phase_type": "off_season",
    "week_count": 4,
    "default_training_intent": "hypertrophy",
    "microcycle": [
      {"week": 1, "training_intent": "hypertrophy", "deload": false},
      {"week": 2, "training_intent": "hypertrophy", "deload": false},
      {"week": 3, "training_intent": "hypertrophy", "deload": false},
      {"week": 4, "training_intent": "endurance", "deload": true}
    ]
  },
  {
    "phase_id": "off_str",
    "name": "Strength Block",
    "phase_type": "off_season",
    "week_count": 3,
    "default_training_intent": "strength",
    "microcycle": null
  }
]
```

The `microcycle` array, when present, lets a phase override its `default_training_intent` per week. When `null`, the default applies to all weeks of that phase. **`microcycle` is unused by `_get_training_intent` in v1** — it's data scaffolding for off-season behavior that ships later.

### New Table: `training_programs`

A per-pitcher instance of a template. One pitcher can have multiple programs in their history, but only one is active at a time (enforced by `pitcher_training_model.active_program_id`).

```sql
CREATE TABLE training_programs (
    id BIGSERIAL PRIMARY KEY,
    pitcher_id TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
    template_id TEXT NOT NULL REFERENCES program_templates(id),
    name TEXT NOT NULL,                       -- copied from template at creation, can be customized later
    start_date DATE NOT NULL,
    end_date DATE,                            -- nullable; ongoing programs have no end
    total_weeks INTEGER,                      -- copied from template, can override
    phases_snapshot JSONB NOT NULL,           -- frozen copy of template.phases at creation time
    deactivated_at TIMESTAMPTZ,               -- when this program was switched off; null = currently active
    deactivation_reason TEXT,                 -- 'switched_to_X', 'season_end', 'injury', etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_training_programs_pitcher ON training_programs(pitcher_id);
CREATE INDEX idx_training_programs_active ON training_programs(pitcher_id, deactivated_at) WHERE deactivated_at IS NULL;
```

**Why a snapshot of phases instead of FK reference?** Templates can evolve (the coach updates the seed JSON, we re-run the migration), but a pitcher's in-flight program should reflect the phases as they were when the program was assigned. The snapshot pattern avoids retroactive surprises.

### Modify: `pitcher_training_model`

Add an FK to the active program:

```sql
ALTER TABLE pitcher_training_model
  ADD COLUMN active_program_id BIGINT REFERENCES training_programs(id);
```

The existing `phase` text column is repurposed: it becomes a denormalized cache of the active program's *current* phase name (computed from program start date + today's date + phases array). Updated whenever the cron job rolls weekly state forward, and on demand by the API.

### Modify: `current_week_state` (JSONB on `pitcher_training_model`)

The existing JSONB gets two new keys:

```json
{
  "days": [...],               // existing
  "phase": {                    // NEW
    "phase_id": "in_season_main",
    "name": "Maintenance",
    "week_in_phase": 6,
    "week_in_program": 6,
    "training_intent": null,
    "phase_type": "in_season"
  },
  "scheduled_throws": [         // NEW
    {
      "id": "uuid-or-int",
      "date": "2026-04-08",
      "type": "bullpen",        // 'catch' | 'long_toss' | 'bullpen' | 'side' | 'game'
      "source": "chat",         // 'chat' | 'button' | 'template' | 'scraper'
      "logged_at": "2026-04-06T18:42:00Z",
      "notes": "30-pitch focus on slider"
    }
  ]
}
```

**`source` field is critical** — it's what powers the yellow logged-mark dot in the UI. `source ∈ {chat, button}` → pitcher logged it explicitly → render the dot. `source ∈ {template, scraper}` → derived → no dot.

### Existing Table Untouched: `schedule`

`game_scraper.py` already populates this. The Programs tab reads from it via a new endpoint. No schema changes.

### Existing Table Hidden: `saved_plans`

Stays in the database. Gets removed from the Programs tab UI. The `/api/plans` endpoints continue to function for any internal use. No migration, no deprecation warning, no behavior change.

## Backend Changes

### New Module: `bot/services/programs.py`

Service layer for training programs. Pure functions, no LLM calls.

```python
def create_program_for_pitcher(
    pitcher_id: str,
    template_id: str,
    start_date: date,
    *,
    deactivate_existing: bool = True,
) -> int:
    """Instantiate a training_programs row from a template, set as active.
    Returns the new program id."""

def get_active_program(pitcher_id: str) -> Optional[dict]:
    """Returns the active program with phases_snapshot, or None."""

def compute_current_phase(program: dict, as_of: date = None) -> dict:
    """Walk phases_snapshot using start_date and as_of to determine
    current phase, week_in_phase, week_in_program. Returns dict matching
    current_week_state.phase shape. Pure function, no DB."""

def deactivate_program(program_id: int, reason: str) -> None:
    """Set deactivated_at + reason. Does NOT touch active_program_id —
    caller is responsible for setting a new active program or nulling FK."""

def list_program_history(pitcher_id: str) -> list[dict]:
    """All programs for a pitcher, newest first, with computed date ranges."""
```

### Modify: `bot/services/weekly_model.py`

Extend `update_week_state()` to also recompute `phase` (via `compute_current_phase()`) on every check-in. Phase data lives in `current_week_state.phase`.

Add `add_scheduled_throw(pitcher_id, throw_dict)` — appends to `current_week_state.scheduled_throws[]`. Used by both the chat parser path and the explicit button endpoint.

### Modify: `bot/services/plan_generator.py`

**`_get_training_intent()` changes — the only behavioral fork in v1:**

```python
def _get_training_intent(rotation_day, triage_result, *, pitcher_model=None):
    # NEW: phase-aware gate
    phase_state = (pitcher_model or {}).get("current_week_state", {}).get("phase") or {}
    phase_type = phase_state.get("phase_type")

    if phase_type and phase_type != "in_season":
        # Off-season / pre-season / return-to-throwing path.
        # In v1 this branch is structurally complete but UNREACHABLE
        # because all current pitchers have phase_type == "in_season".
        phase_intent = phase_state.get("training_intent")
        if phase_intent:
            return _blend_phase_with_rotation(phase_intent, rotation_day, triage_result)

    # In-season path — EXISTING LOGIC, byte-for-byte unchanged.
    return _legacy_intent_from_rotation_and_triage(rotation_day, triage_result)
```

`_blend_phase_with_rotation()` is a new helper but its body can be a stub (`return phase_intent`) in v1 since no pitcher will reach it. The full blend logic ships in the off-season spec.

**Critical guardrail:** the in-season branch must be reachable via the *exact same code path* it uses today. The refactor adds a fork, it does not move the existing logic. Plan generator behavior for any existing pitcher must be byte-identical.

### New Module: `bot/services/throw_intent_parser.py`

A small NLP utility. Called from the chat handler when a pitcher sends a free-text message.

```python
def parse_throw_intent(message: str, today: date) -> Optional[dict]:
    """Detect throwing intent in a chat message.
    Returns {date, type, notes} or None if no intent detected."""
```

Cheap pattern matching first (regex for "bullpen Thursday", "throwing Tuesday", "side tomorrow"), LLM fallback only when patterns are ambiguous. Returns None on no-detect — never blocks the chat response.

The chat handler calls this on every inbound message, and if a throw intent is detected, calls `add_scheduled_throw()` and surfaces a confirmation toast in the bot reply ("Got it — bullpen Thursday added to your week").

### New API Endpoints (`api/routes.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/pitcher/{id}/program` | Active program with computed phase + week-in-phase, week arc data, schedule overlay, scheduled_throws |
| GET | `/api/pitcher/{id}/program/history` | All past programs for the timeline |
| GET | `/api/program/{program_id}` | Program detail (full structure, phases, rotation template) |
| POST | `/api/pitcher/{id}/scheduled-throw` | Add a scheduled throw (button path) |
| DELETE | `/api/pitcher/{id}/scheduled-throw/{throw_id}` | Remove a scheduled throw |
| GET | `/api/schedule/this-week?pitcher_id={id}` | UChicago games for the current rotation week, with `is_your_start` annotation for the pitcher |

### Migration & Seed

1. **Migration script** (`scripts/migrations/2026_04_09_program_tables.sql`) creates `program_templates`, `training_programs`, alters `pitcher_training_model`.
2. **Seed script** (`scripts/seed_program_templates.py`) reads `data/program_templates/*.json` and upserts into `program_templates`. Idempotent.
3. **Backfill script** (`scripts/backfill_active_programs.py`) — for every pitcher in `pitchers` table, picks the role-matched template, creates a `training_programs` row with `start_date` set to **today (or season start, configurable)**, sets `pitcher_training_model.active_program_id`. Idempotent.

Initial seed templates (v1):
- `in_season_starter` — 7-day rotation, references existing `data/templates/day_1.json` ... `day_7.json`, single 12-week "Maintenance" phase, `phase_type: in_season`
- `in_season_short_relief` — 3-day flexible, references reliever templates, single 12-week phase
- `in_season_long_relief` — variant for multi-inning relievers
- `return_to_throwing` — 6-week ramp, `phase_type: return_to_throwing`. **In v1 this exists in the seed library but no current pitcher is assigned to it** — it's there so the structure is exercised end-to-end and a coach can manually swap a pitcher to it via chat.

## Frontend Changes

### Rename: `Plans.jsx` → `Programs.jsx`

Same file gets gutted and rewritten. Route stays `/plans` initially with a redirect to `/programs` for any deep links. Bottom nav label changes to "Programs".

### Component Tree (new + modified)

```
Programs.jsx                          (rewrite — was Plans.jsx)
├── ProgramHero.jsx                   (NEW — maroon gradient hero card)
│   ├── completion ring
│   └── phase progress bar
├── WeekArc.jsx                       (NEW — emoji bubbles + connector + legend)
│   ├── DayBubble.jsx                 (NEW — handles all states: today, done, outing, upcoming, has-game)
│   └── SetNextThrowButton.jsx        (NEW — opens SetThrowModal)
├── ScheduleCard.jsx                  (NEW — navy card with game items)
├── TodayDetailCard.jsx               (NEW — focused today rendering)
└── ProgramHistoryTimeline.jsx        (NEW — vertical timeline of past programs)

ProgramDetail.jsx                     (NEW — route /programs/{id})
├── full phase breakdown
├── rotation template preview
└── all weeks with intent labels

SetThrowModal.jsx                     (NEW — type chips + date picker)
```

`DailyCard.jsx` is **untouched**. The Programs tab does NOT render daily plan exercises — that's still the Home page's job. The Programs tab is purely about the program-level view.

### Data fetching

`Programs.jsx` calls `GET /api/pitcher/{id}/program`, which returns a single payload. The week window is **anchored to the pitcher's last outing**: for a starter, the window is `[last_outing_date, last_outing_date + rotation_length - 1]` which produces the 7-day arc from outing day forward; for a reliever, it's `[last_appearance_date, last_appearance_date + 6]` regardless of rotation length so the visualization always shows a full week. If no last outing exists yet (new pitcher, pre-season), the window defaults to the current calendar week (Sun–Sat, Chicago tz).

```json
{
  "program": { "id": 17, "name": "In-Season Starter Protocol", "current_phase": {...}, "phase_progress": {"week": 6, "total": 9}, "completion_pct": 0.60 },
  "week_arc": {
    "anchor_type": "calendar",
    "days": [
      {"date": "2026-04-05", "day_label": "SUN", "rotation_day": 7, "state": "outing", "emoji": "⚾", "label": "Start", "logged": false, "has_game": true},
      {"date": "2026-04-08", "day_label": "WED", "rotation_day": 3, "state": "today", "emoji": "🎯", "label": "Bullpen", "logged": true, "has_game": false}
    ]
  },
  "schedule": [
    {"date": "2026-04-05", "opponent": "Wash U", "home": true, "time": "12:00", "result": null, "is_your_start": true},
    {"date": "2026-04-07", "opponent": "Lake Forest", "home": true, "time": "15:00", "result": "L 4-2"},
    {"date": "2026-04-11", "opponent": "Carthage", "home": false, "time": "13:00", "doubleheader": true}
  ],
  "today_detail": { "rotation_day": 3, "label": "Bullpen day", "title": "Upper push + 30-pitch bullpen", "subtitle": "...", "pills": [...] }
}
```

One fetch, one render. No N+1 component fetches.

### Reliever week arc

When `anchor_type === "appearance"`, the `WeekArc` component renders the same DOM structure but the `day_label` slot reads "+1", "+2", "READY", "+1 Rec" etc., and the anchor bubble is the last appearance. The component is role-agnostic — it just renders what the API gives it. The decision happens server-side in the program endpoint based on the active program's `rotation_template_keys` and the pitcher's `days_since_outing`.

## In-Season vs Off-Season Behavior — The Critical Gate

**This is the spec's most important guardrail.**

For every current pitcher (Russell, Lazar, Hartrick, all of them), the active program after migration will have `phase_type: in_season`. The `_get_training_intent` gate checks `phase_type` first; if it's `in_season`, the function returns from its existing legacy code path without ever consulting `phase`, `week_of_phase`, or `microcycle`.

This means:

- ✅ Plan generation behavior for in-season pitchers is byte-identical to today
- ✅ Exercise pool selection unchanged
- ✅ Templates unchanged
- ✅ Triage unchanged
- ✅ The Programs tab is purely additive — new tables, new UI, new endpoints. It reads from `pitcher_training_model` and computes views, but it does not write back into anything that influences `_get_training_intent`'s legacy branch.

**Test plan:** before deploying, run the full plan generation pipeline against every current pitcher with the new code. Diff the output against the legacy code's output. They must match exactly.

## Self-Reported Throwing Events — Flow

Two write paths, one shared field (`current_week_state.scheduled_throws[]`):

**Path 1 — Chat parsing:**
```
Pitcher message → qa.py handler
  → throw_intent_parser.parse_throw_intent(text)
  → if detected: add_scheduled_throw(pitcher_id, {date, type, source: "chat"})
  → confirmation appended to bot reply
  → continue normal Q&A flow
```

**Path 2 — Explicit button:**
```
"+ Set next throw" tap → SetThrowModal opens
  → user picks type + date → POST /api/pitcher/{id}/scheduled-throw
  → add_scheduled_throw(pitcher_id, {date, type, source: "button"})
  → Programs.jsx refetches, week arc re-renders with new logged dot
```

**Read path** (the week arc):
```
GET /api/pitcher/{id}/program
  → for each day in the week window:
      check if current_week_state.scheduled_throws has an entry for this date
      if yes: override the day's emoji + label from the throw type, set logged=true
      if no: derive from rotation template
```

**Conflict resolution:** scheduled_throws override template. If the pitcher logs "bullpen Wednesday" but the template said Wednesday is "Recovery", the week arc shows Bullpen with the yellow logged dot. Daily plan generation on Wednesday morning will respect the scheduled_throw and shift training_intent accordingly via existing logic in `triage.py` (which already considers reported throws for triage).

## Schedule Overlay — Flow

`game_scraper.py` already runs and populates `schedule`. The new endpoint `/api/schedule/this-week?pitcher_id={id}` returns games whose date falls in the pitcher's current week window with `is_your_start` annotation.

The Programs tab uses this in two places:
1. **Navy rings on day bubbles** in the WeekArc — the API marks each day with `has_game: true/false`
2. **Maroons · This Week navy card** below the arc — full game items with opponent, time, result (if past), and "YOUR START" callout

The schedule **does not influence rotation assignment**. If Russell's rotation says day 7 = start, and the next Sunday game is the next Sunday on the calendar, the system aligns them by calendar coincidence, not by reverse-counting from the game.

## UI Spec Reference

The visual direction is locked. Reference mockup files in `.superpowers/brainstorm/70775-1775777250/content/`:

- `timeline-ac-blend-v2.html` — base hero card + emoji week arc + today card
- `schedule-blend-v3.html` — final integration with navy rings and navy schedule card

Color palette: existing maroon/cream/rose-blush + navy (`#1a2942`) as the schedule layer accent. No other new colors.

## Migration Plan

1. Apply schema migration (`2026_04_09_program_tables.sql`)
2. Run `seed_program_templates.py` to populate `program_templates` from JSON
3. Run `backfill_active_programs.py` to assign every existing pitcher a role-matched in-season program with `start_date` set to season-start (configurable; for the April rollout, set to a date in early February so "Week 6 of 9" reads correctly)
4. Deploy backend (Railway)
5. Deploy frontend (Vercel)
6. Run plan-generation diff test against all 12 pitchers — verify zero behavioral change
7. Smoke test the Programs tab on Russell, Hartrick (reliever), and Lazar (return-to-throwing candidate)

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Plan generation behavior changes for in-season pitchers | The phase gate in `_get_training_intent` falls through to the legacy code path byte-for-byte. Pre-deploy diff test catches any drift. |
| `compute_current_phase` returns wrong week | Pure function, easy to unit test against fixed dates. Backfill script logs computed phase for every pitcher so we can eyeball before deploying. |
| Schedule overlay breaks for pitchers with no `schedule` data | Endpoint returns empty array, week arc renders without rings, schedule card hides. Graceful degradation. |
| `scheduled_throws` array grows unbounded | Prune entries older than 14 days on every write. Check via test. |
| `throw_intent_parser` false-positives ("I threw a chair") | Confirmation in bot reply lets pitcher correct ("nope, no bullpen"). False-positives become a UX annoyance, not a data corruption issue. |
| Existing `saved_plans` records visible somewhere | Audit `Plans.jsx` consumers — confirm no other component depends on the route or data. The `/api/plans` endpoints stay live. |
| Reliever week arc anchor confuses pitchers | First-launch tooltip on reliever accounts: "Your week starts from your last appearance." |

## Testing

- **Unit:** `compute_current_phase` against fixed dates, `parse_throw_intent` against a corpus of real bot messages, `_get_training_intent` phase gate with both `in_season` and `off_season` fixtures
- **Integration:** plan generation diff test (every pitcher, before vs after) — must be byte-identical for in-season
- **API:** snapshot tests for `/api/pitcher/{id}/program` against seeded fixtures
- **Manual smoke:** Russell (starter, mid-rotation), Hartrick (reliever, recent appearance), Lazar (reliever, no recent appearance), Heron (yellow flag), test_pitcher_001 (edge cases)

## Post-Deployment Next Steps

The deferred items below are intentionally NOT in v1, but the v1 data structures support them. Each becomes its own spec when prioritized:

1. **Off-season periodization logic activation** — wire `_get_training_intent`'s phase branch to actually consult `microcycle` and blend with rotation-day intent. Required when any pitcher transitions out of in-season (typically post-season).
2. **Build New program wizard** — UI flow for the coach (or pitchers themselves) to create a custom program: pick template, set start date, customize phases, save. v1 forces JSON-based template authoring; this lifts that to a UI workflow.
3. **Coach-facing template editor** — beyond instantiation, allow editing template definitions (phase counts, training intents, rotation template keys) without a code change.
4. **Exercise progression curves** — track weight/volume per exercise per pitcher across weeks, surface as a trend on the Profile page or Program Detail. Requires `working_weights` to actually be populated.
5. **Weight logging UI** — DailyCard exercise rows get a "+ log weight" affordance that writes to `pitcher_training_model.working_weights`.
6. **Ledger / modification history** — vertical timeline of program-level modifications over time (program switches, coach mutations, swap streaks). Sister spec to this one.
7. **Schedule-driven rotation auto-shift** — when a starter's next outing is set, reverse-count the rotation. Requires careful handling of doubleheaders, multi-game weeks, and rain-outs.
8. **Coach dashboard** — staff-facing roll-up of every pitcher's program, week-in-phase, and week arc. Reuses the same `/api/pitcher/{id}/program` endpoint per pitcher.
9. **Reliever appearance projection** — light prediction of when a reliever is most likely to appear next, surfaced as a "you'll probably appear in" hint in the schedule card.
10. **Self-reported throws → bot proactive suggestions** — when a pitcher logs a bullpen 2 days out, the bot pings the morning of "ready for your bullpen tomorrow?" and includes prep-specific notes.
11. **`saved_plans` cleanup** — once it's been hidden for a few months and confirmed unused, drop the table or repurpose for a different feature.

## Files Touched

**New:**
- `pitcher_program_app/scripts/migrations/2026_04_09_program_tables.sql`
- `pitcher_program_app/scripts/seed_program_templates.py`
- `pitcher_program_app/scripts/backfill_active_programs.py`
- `pitcher_program_app/data/program_templates/in_season_starter.json`
- `pitcher_program_app/data/program_templates/in_season_short_relief.json`
- `pitcher_program_app/data/program_templates/in_season_long_relief.json`
- `pitcher_program_app/data/program_templates/return_to_throwing.json`
- `pitcher_program_app/bot/services/programs.py`
- `pitcher_program_app/bot/services/throw_intent_parser.py`
- `pitcher_program_app/mini-app/src/pages/Programs.jsx` (replaces `Plans.jsx`)
- `pitcher_program_app/mini-app/src/pages/ProgramDetail.jsx`
- `pitcher_program_app/mini-app/src/components/ProgramHero.jsx`
- `pitcher_program_app/mini-app/src/components/WeekArc.jsx`
- `pitcher_program_app/mini-app/src/components/DayBubble.jsx`
- `pitcher_program_app/mini-app/src/components/ScheduleCard.jsx`
- `pitcher_program_app/mini-app/src/components/TodayDetailCard.jsx`
- `pitcher_program_app/mini-app/src/components/ProgramHistoryTimeline.jsx`
- `pitcher_program_app/mini-app/src/components/SetThrowModal.jsx`
- `pitcher_program_app/mini-app/src/components/SetNextThrowButton.jsx`

**Modified:**
- `pitcher_program_app/bot/services/plan_generator.py` — `_get_training_intent` phase gate
- `pitcher_program_app/bot/services/weekly_model.py` — phase recompute on check-in, `add_scheduled_throw`
- `pitcher_program_app/bot/services/db.py` — CRUD for new tables
- `pitcher_program_app/bot/handlers/qa.py` — throw intent parser hook
- `pitcher_program_app/api/routes.py` — new endpoints
- `pitcher_program_app/mini-app/src/Layout.jsx` — nav label "Plans" → "Programs", route redirect
- `pitcher_program_app/mini-app/src/App.jsx` — route registration

**Untouched (critical):**
- `pitcher_program_app/bot/services/exercise_pool.py`
- `pitcher_program_app/bot/services/triage.py`
- `pitcher_program_app/bot/services/triage_llm.py`
- `pitcher_program_app/data/templates/*.json`
- `pitcher_program_app/data/knowledge/exercise_library.json`
- `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

## Open Questions for Implementation Plan

These are deferred to the implementation planning step (writing-plans), not blocking spec approval:

- Exact phase gate diff-test harness — runtime fixture vs. snapshot file
- Whether `Programs.jsx` and `Plans.jsx` cohabitate during deployment or get swapped atomically
- Throw intent parser: regex-only in v1 or LLM fallback from day one
- Backfill `start_date` — single global date, or per-pitcher based on first check-in
- Whether the week window roll-over happens server-side on `compute_current_phase` invocation or via a cron job at midnight Chicago time

End of design.
