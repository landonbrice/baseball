# Coach Dashboard v0 — Design Specification

> Created: 2026-04-09
> Status: Approved (brainstorming complete)
> Target: May 2026 demo
> Scope: Pitcher-only, single-team (UChicago), schema-only multi-tenancy
> Implementation skills: writing-plans, frontend-design, test-driven-development, verification-before-completion

---

## Table of Contents

1. [Context & Decisions](#1-context--decisions)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Model Deltas](#3-data-model-deltas)
4. [API Endpoints](#4-api-endpoints)
5. [Screens & Interaction Design](#5-screens--interaction-design)
6. [Auth & Onboarding](#6-auth--onboarding)
7. [Demo Flow & Exit Criteria](#7-demo-flow--exit-criteria)
8. [Risk Register](#8-risk-register)
9. [v1 Backlog Reference](#9-v1-backlog-reference)

---

## 1. Context & Decisions

### What exists today

The pitcher training platform is deployed and functional for UChicago's pitching staff (11 active pitchers). Phases 1–15 are complete: Telegram bot, React Mini App (Telegram), FastAPI backend, Supabase data layer, two-pass plan generation, dynamic exercise pool (159 exercises), exercise swap UI, WHOOP integration, coach mutation bridge, game detection, weekly model, and pitcher training model consolidation.

### What doesn't exist

No coach-facing surface. Coaches interact with the system only through the Telegram bot's free-text chat. No compliance visibility, no override UI, no schedule management, no team-wide program assignment.

### Decisions locked during brainstorming

| Decision | Choice | Rationale |
|---|---|---|
| Athlete scope | Pitcher-only | Demo uses real UChicago pitching staff; position players deferred to v1 |
| Multi-tenancy | Schema-only (team_id FK + backfill, no UI) | 1.5 days of insurance avoids 3-5 day retrofit when team #2 arrives |
| Override model | Two verbs: "Adjust today" + "Add restriction per athlete" | Matches coaching mental model; team-wide rules deferred to v1 |
| Schedule input | Hand-seeded + coach-editable + starter assignment | Auto-scraper deferred to v1; starter assignment is the demo's magic moment |
| Off-season model | Phase blocks as foundation, bullpens/scrimmages layered in v1 | Phase emphasis drives exercise_pool selection; structured events add scope |
| Forward-looking engine | `days_until_next_start` using existing `starter_7day.json` template | Template already indexed relative to game day; direction of lookup is the only new concept |
| Team programs | Coach assigns pre-loaded throwing blocks to team; AI individualizes per pitcher | AI always generates, coach always has optionality; triage modifications override team block baseline |
| Coach insights | v0 ships one category: pre-start nudges | Validates the plumbing; multi-category expansion in v1 |
| Hosting | Monorepo sibling app (`coach-app/` alongside `mini-app/`), separate Vercel project | Clean auth separation, independent deploy, no conditional routing |
| Backend | Single shared FastAPI backend, new `/api/coach/*` router | No service duplication; existing mutation plumbing reused |
| Team scoping | Application-layer filtering in v0, RLS in v1 | Sufficient for single-team demo; avoids backend refactor |
| Auth | Supabase Auth email/password, manual account creation | Zero coach setup; self-serve signup deferred to v1 |
| Frontend implementation | Use `superpowers:frontend-design` skill during build | Per user request for better structure and visual implementation |

---

## 2. Architecture Overview

### System diagram

```
+----------------------------+  +----------------------------+  +-----------------------+
|  Coach Dashboard (NEW)     |  |  Athlete Mini App          |  |  Telegram Bot          |
|  React + Vite + Tailwind   |  |  React + Vite + Tailwind   |  |  Python PTB            |
|  Supabase Auth             |  |  Telegram initData HMAC    |  |  Long-polling          |
|  Vercel (new project)      |  |  Vercel (existing)         |  |  Railway (existing)    |
|  pitcher_program_app/      |  |  pitcher_program_app/      |  |  pitcher_program_app/  |
|    coach-app/              |  |    mini-app/               |  |    bot/                |
+-------------+--------------+  +-------------+--------------+  +-----------+-----------+
              |                               |                             |
              +-------------------------------+-----------------------------+
                                              |
                                +-----------  v  -----------+
                                |   FastAPI Backend (shared)|
                                |   pitcher_program_app/api/|
                                |   Railway (existing)      |
                                |                           |
                                |   New in v0:              |
                                |   - /api/coach/* routes   |
                                |   - Supabase Auth midware |
                                |   - team_id filter layer  |
                                |   - Coach Insights svc    |
                                |   - Team Programs svc     |
                                +-------------+-------------+
                                              |
                                +-----------  v  -----------+
                                |   Supabase (existing)     |
                                |   + 7 new tables          |
                                |   + team_id FK backfill   |
                                +---------------------------+
```

### New backend components

| Component | File | Purpose |
|---|---|---|
| Auth middleware | `api/coach_auth.py` | Validates Supabase JWT, extracts coach_id + team_id, attaches to request |
| Coach routes | `api/coach_routes.py` | All `/api/coach/*` endpoints, registered as a FastAPI router |
| Coach Insights service | `bot/services/coach_insights.py` | Generates structured suggestions per pitcher, stores in coach_suggestions table |
| Team Programs service | `bot/services/team_programs.py` | Resolves active team block for a pitcher on a given date, feeds plan generator |
| Team scope helper | `bot/services/team_scope.py` | Wraps DB queries with `.eq("team_id", team_id)` for coach-initiated queries |

### What does NOT change

- Existing `/api/*` pitcher-facing routes are untouched (additive `team_id` column backfill only)
- Telegram bot continues unchanged; `team_id` defaults to `'uchicago_baseball'`
- Mini App is untouched except for one small addition: DailyCard renders a "Team Block — Week N, Day M" tag when a team block is active (~20 lines JSX)
- Plan generator is extended (not rewritten) to check for active team blocks and compute `days_until_next_start`
- Existing Supabase tables keep current schema; multi-tenancy is additive

### Deployment

- **Vercel:** `mini-app` (existing) + `coach-app` (new) — two separate projects from the same monorepo
- **Railway:** `baseball-production-9d28` (existing, bot + API, unchanged)
- **Supabase:** `pitcher-training-intel` (existing, new tables via migration)

No new infrastructure vendors. No new services to run.

---

## 3. Data Model Deltas

### Principle: additive only

Every change is additive. No column renames, no type changes, no dropped fields. Existing bot/mini-app code continues to work without modification.

### New tables (7)

#### 3.1 `teams`

```sql
CREATE TABLE IF NOT EXISTS teams (
    team_id         text PRIMARY KEY,
    name            text NOT NULL,
    level           text,                          -- 'd3_college' | 'hs_varsity' | 'travel_ball' | 'd2_college' | 'naia'
    training_phase  text DEFAULT 'offseason',      -- 'offseason' | 'preseason' | 'in_season' | 'postseason'
    timezone        text DEFAULT 'America/Chicago',
    settings        jsonb DEFAULT '{}',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);
```

Seed: `('uchicago_baseball', 'UChicago Baseball', 'd3_college', 'offseason', 'America/Chicago')`

#### 3.2 `coaches`

```sql
CREATE TABLE IF NOT EXISTS coaches (
    coach_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    email            text UNIQUE NOT NULL,
    name             text NOT NULL,
    role             text,                          -- 'head' | 'assistant' | 'volunteer' | 'sc'
    supabase_user_id uuid UNIQUE,
    created_at       timestamptz DEFAULT now()
);
```

#### 3.3 `team_games`

Replaces the existing `schedule` table. Existing `schedule` rows are migrated into `team_games`; `schedule` table is deprecated.

```sql
CREATE TABLE IF NOT EXISTS team_games (
    game_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id              text NOT NULL REFERENCES teams(team_id),
    game_date            date NOT NULL,
    game_time            time,
    opponent             text,
    home_away            text,                      -- 'home' | 'away'
    is_doubleheader_g2   boolean DEFAULT false,
    starting_pitcher_id  text REFERENCES pitchers(pitcher_id),
    status               text DEFAULT 'scheduled',  -- 'scheduled' | 'completed' | 'cancelled'
    source               text DEFAULT 'manual',     -- 'manual' | 'scraped'
    notes                text,
    created_at           timestamptz DEFAULT now(),
    updated_at           timestamptz DEFAULT now(),
    UNIQUE (team_id, game_date, is_doubleheader_g2)
);
```

#### 3.4 `block_library`

```sql
CREATE TABLE IF NOT EXISTS block_library (
    block_template_id   text PRIMARY KEY,
    name                text NOT NULL,
    description         text,
    block_type          text NOT NULL,              -- 'throwing' in v0
    duration_days       integer NOT NULL,
    content             jsonb NOT NULL,
    source              text,
    created_at          timestamptz DEFAULT now()
);
```

Content shape:

```json
{
  "days": [
    {
      "day_index": 1,
      "label": "Week 1, Day 1 — Base",
      "distances": ["45ft", "60ft", "75ft"],
      "total_throws": 40,
      "intent_notes": "Build base. Light effort.",
      "drills": ["high_pec_load_x10_at_30ft", "snap_snap_rocker_x5"],
      "effort_pct": 50
    }
  ],
  "rest_days_pattern": [3, 7],
  "post_session_recovery": "medium"
}
```

Hand-seeded with 3–4 blocks extracted from `past_arm_programs/` xlsx files and `data/templates/throwing_ramp_up.md`.

#### 3.5 `team_assigned_blocks`

```sql
CREATE TABLE IF NOT EXISTS team_assigned_blocks (
    block_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    block_type            text NOT NULL,
    block_template_id     text NOT NULL,
    start_date            date NOT NULL,
    duration_days         integer NOT NULL,
    assigned_by_coach_id  uuid REFERENCES coaches(coach_id),
    notes                 text,
    status                text DEFAULT 'active',    -- 'active' | 'completed' | 'cancelled'
    created_at            timestamptz DEFAULT now()
);
```

v0 enforces at most one active throwing block per team (application-level).

#### 3.6 `coach_suggestions`

```sql
CREATE TABLE IF NOT EXISTS coach_suggestions (
    suggestion_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    pitcher_id            text NOT NULL REFERENCES pitchers(pitcher_id),
    category              text NOT NULL,             -- 'pre_start_nudge' in v0
    title                 text NOT NULL,
    reasoning             text NOT NULL,
    proposed_action       jsonb,
    status                text DEFAULT 'pending',    -- 'pending' | 'accepted' | 'dismissed' | 'expired'
    expires_at            timestamptz,
    created_at            timestamptz DEFAULT now(),
    resolved_at           timestamptz,
    resolved_by_coach_id  uuid REFERENCES coaches(coach_id)
);
```

#### 3.7 `training_phase_blocks`

```sql
CREATE TABLE IF NOT EXISTS training_phase_blocks (
    phase_block_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    phase_name       text NOT NULL,
    start_date       date NOT NULL,
    end_date         date NOT NULL,
    emphasis         text,                           -- 'hypertrophy' | 'strength' | 'power' | 'maintenance' | 'gpp'
    notes            text,
    created_at       timestamptz DEFAULT now(),
    CHECK (end_date >= start_date)
);
```

### Columns added to existing tables

All additive. All have safe defaults or are nullable. All backfilled in migration.

| Table | New Column | Type | Default | Backfill |
|---|---|---|---|---|
| `pitchers` | `team_id` | text FK → teams | `'uchicago_baseball'` | All existing rows |
| `daily_entries` | `team_id` | text | — | From pitcher's team_id |
| `daily_entries` | `active_team_block_id` | uuid FK → team_assigned_blocks | null | null (no blocks existed) |
| `saved_plans` | `team_id` | text | — | From pitcher's team_id |
| `weekly_summaries` | `team_id` | text | — | From pitcher's team_id |
| `chat_messages` | `team_id` | text | — | From pitcher's team_id |

### Migration

Single file: `scripts/migrations/006_coach_dashboard_foundation.sql`

Execution order:
1. Create `teams` + seed UChicago row
2. Create `coaches`
3. Create `team_games` + migrate rows from existing `schedule` table
4. Create `block_library` + seed 3–4 blocks
5. Create `team_assigned_blocks`
6. Create `coach_suggestions`
7. Create `training_phase_blocks` + seed current offseason phases
8. ALTER pitchers ADD team_id + backfill
9. ALTER daily_entries ADD team_id + backfill + ADD active_team_block_id
10. ALTER saved_plans ADD team_id + backfill
11. ALTER weekly_summaries ADD team_id + backfill
12. ALTER chat_messages ADD team_id + backfill

Idempotent (`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`). Safe to re-run.

---

## 4. API Endpoints

### Auth

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/coach/auth/exchange` | Validate Supabase JWT, return domain identity (coach_id, team_id, name, role) |
| GET | `/api/coach/me` | Session restoration on page reload |

Login happens client-side via Supabase JS SDK. Backend never sees the password. Frontend gets JWT from Supabase, then calls `/auth/exchange` once to get domain identity.

### Team overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/team/overview` | Single call populates entire Team Overview screen: team info, compliance stats, full roster with status/flags/streaks/7-day strips, insights summary |

Single endpoint for the homepage. No N+1 queries on the frontend.

Response shape:

```json
{
  "team": { "id": "...", "name": "...", "training_phase": "...", "today_schedule_summary": "..." },
  "compliance": { "checked_in_today": 9, "total": 11, "flags": { "red": 1, "yellow": 2 } },
  "roster": [
    {
      "pitcher_id": "...", "name": "...", "role": "...",
      "today_status": "checked_in|not_yet|rest_day|missed",
      "flag_level": "green|yellow|red",
      "last_7_days": [ { "date": "...", "status": "..." } ],
      "streak": 4,
      "active_injury_flags": ["UCL history"],
      "next_scheduled_start": "2026-04-12"
    }
  ],
  "insights_summary": { "pending_count": 3, "high_priority_count": 1 }
}
```

### Player detail

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/pitcher/{pitcher_id}` | Full pitcher detail: profile, current week, forward strip, check-ins, flags, modifications, WHOOP, team block status, pending suggestions |
| GET | `/api/coach/pitcher/{pitcher_id}/day/{date}` | Drill down into a specific day's prescribed + logged program |

### Overrides

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/coach/pitcher/{pitcher_id}/adjust-today` | Verb 1: one-time mutations to today's plan. Delegates to existing apply-mutations path with coach_id audit trail |
| POST | `/api/coach/pitcher/{pitcher_id}/restriction` | Verb 2: persistent restriction on pitcher (exercise/equipment/movement blocked + optional expiry). Writes to pitcher_training_model.exercise_preferences |
| DELETE | `/api/coach/pitcher/{pitcher_id}/restriction/{key}` | Lift a previously-added restriction |

Adjust-today mutation format (same as Phase 15):

```json
{
  "date": "2026-04-10",
  "mutations": [
    { "action": "swap", "from_exercise_id": "ex_022", "to_exercise_id": "ex_018", "reason": "hamstring" },
    { "action": "modify", "exercise_id": "ex_015", "rx_override": { "sets": 2, "reps": "8" } }
  ]
}
```

### Schedule & starter assignment

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/schedule` | Game list with optional date range filter |
| POST | `/api/coach/schedule/game` | Add a game |
| PATCH | `/api/coach/schedule/game/{game_id}` | Edit game details; most commonly assign starter. Side effect: recomputes `days_until_next_start` for affected pitcher |
| DELETE | `/api/coach/schedule/game/{game_id}` | Cancel/remove a game |

### Team programs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/team-programs/library` | Pre-loaded block library |
| GET | `/api/coach/team-programs/active` | Currently active team blocks |
| POST | `/api/coach/team-programs/assign` | Assign a block to the team. v0 enforces max one active throwing block (409 if one exists) |
| POST | `/api/coach/team-programs/{block_id}/end` | End a block early |
| GET | `/api/coach/team-programs/{block_id}/compliance` | Per-pitcher compliance for a specific block today/this week |

### Off-season phases

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/phases` | All phase blocks ordered by start_date |
| POST | `/api/coach/phases` | Create a phase block |
| PATCH | `/api/coach/phases/{id}` | Edit phase dates/emphasis |
| DELETE | `/api/coach/phases/{id}` | Remove a phase block |

Engine reads the phase containing today's date and uses `emphasis` to bias exercise_pool prescription mode.

### Coach insights

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/coach/insights` | Pending suggestions sorted by priority |
| POST | `/api/coach/insights/{id}/accept` | Execute proposed action via mutation apply path, resolve suggestion |
| POST | `/api/coach/insights/{id}/dismiss` | Mark dismissed with optional reason, suppress re-emission |

### Internal / scheduled

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/internal/insights/run` | Cron-triggered after morning check-ins; generates suggestions for all teams. Protected by shared secret |

### Error shape

All coach endpoints return errors consistently:

```json
{
  "error": {
    "code": "TEAM_SCOPE_VIOLATION|BLOCK_ALREADY_ACTIVE|UNKNOWN_PITCHER|...",
    "message": "Human-readable explanation",
    "details": {}
  }
}
```

Team scope violations return 403 (not 404) — deliberate security posture.

---

## 5. Screens & Interaction Design

### Navigation shell

**Top bar (persistent):** Team name + training phase badge | Today's date | Coach name + logout

**Left sidebar (collapsible, ~200px):**
- Team Overview (homepage)
- Schedule
- Team Programs
- Phases
- Insights (with pending count badge)
- Settings (v1 stub)

### Screen 1 — Team Overview

**Question:** "Did my guys train, and is anyone hurt?"

**Left column (~25%):**
- Compliance ring: "9/11 checked in today" — green/amber/red based on percentage. Clickable filter.
- Readiness summary: "1 red, 2 yellow" — clickable segment filters.
- Today's schedule card: game info or "no games today."
- Active team block card: block name, day, compliance summary.
- Insights badge: pending count.

**Main area (~75%):** dense roster table.

| Player | Pos | Status | Last 7 | Streak | Flags | Next Start |
|---|---|---|---|---|---|---|
| Rows for all pitchers, sortable by any column |

- Click row → slide-over opens (Screen 2)
- Filter chips: Position, Flag level, Check-in status
- 7-day strip is the most scannable column

### Screen 2 — Player Detail (slide-over)

**Question:** "What's going on with this specific pitcher?"

Right-side slide-over, ~60% screen width. Roster stays visible. Coach can rapid-fire through players.

**Header:** Name, position, age, year | Injury flag pills | Next start | Team block status

**Tab 1: Today (default)**
- Full program: warmup → arm care → lifting → throwing → post-throw
- Two action buttons: "Adjust Today" | "Add Restriction"
- Check-in summary: arm feel, sleep, WHOOP recovery

**Tab 2: This Week**
- 7-day strip (back 3, today, forward 3)
- Each day: session type, completion, flags
- Forward days highlight pre-start ramp if a start is assigned
- Click any day → jump to that day's detail

**Tab 3: History**
- 4-week compliance calendar (GitHub-style heatmap)
- Arm feel trend line (30 days)
- Volume trend (prescribed vs. completed, 4 weeks)
- Recent modifications list

**Tab 4: Flags & Notes** (only shown if flags exist)
- Active injury flags with context
- Coach notes from overrides
- WHOOP 7-day trend if linked

### Screen 3 — Schedule

**Question:** "When are we playing and who's starting?"

Full-width month calendar. Game days show opponent + starter initials. Click game → side panel with details + starter dropdown. Click empty day → "Add game" form.

**Starter assignment flow:**
1. Click game cell → side panel
2. Starter dropdown (eligible starters, relievers in secondary section)
3. Select → toast: "Jake assigned to 4/12. His week will adjust."
4. Side effect: days_until_next_start recomputation + plan regeneration queue

Below calendar: "Upcoming starts this week" strip showing assigned vs. unassigned games.

### Screen 4 — Team Programs

**Question:** "What am I running across the team, and can I roll out a program?"

**Top: Active Programs** — cards for active blocks with compliance summary. Empty state if none.

**Bottom: Block Library** — 3–4 pre-loaded cards:
- Velocity Program (12 weeks)
- Long-Toss Ramp Up (6 weeks)
- Offseason Throwing Base (4 weeks)
- Return-to-Mound Progression (8 weeks) — marked "individual use recommended"

Assign flow: click → preview slide-over → "Assign to team" → start date → confirm.

Block compliance drill-down: per-pitcher status (full / modified / skipped) with modification reasons.

### Screen 5 — Phases

**Question:** "What periodization block are we in?"

Horizontal timeline with colored phase blocks. Click → edit form (name, dates, emphasis, notes). "Add phase" button. Current phase highlighted. v0 uses click-to-edit forms; v1 gets drag-drop.

### Screen 6 — Insights

**Question:** "What does the AI think I should look at?"

List of suggestion cards grouped by priority.

Each card: pitcher name | category tag | title | reasoning | proposed action | **Accept** / **Dismiss** / **Open player detail** buttons.

v0 has one category: Pre-Start Nudge.

### Cross-screen conventions

1. **Slide-overs for drill-downs, modals for destructive/form actions**
2. **Toasts for success, inline for errors**
3. **Optimistic UI for coach actions** — immediate visual update, background API call, revert on failure
4. **Provenance badges on adjusted exercises** — "coach adjusted" vs. "auto-modified (arm feel)"
5. **No empty states requiring setup** — everything pre-seeded

### Design language

| Token | Value |
|---|---|
| Background | `#f5f1eb` (warm cream) |
| Primary | `#5c1020` (deep maroon) |
| Accent | `#e8a0aa` (rose blush) |
| Success | `#2d5a3d` (forest green) |
| Warning | `#d4a017` (amber) |
| Danger | `#c0392b` (crimson) |
| Text | `#2c2c2c` (charcoal) |
| Subtle text | `#7a7a7a` |
| Font | Inter or similar clean sans-serif |
| Base size | 14px (dashboard), 16px (mini-app) |
| Spacing | 8px grid |

---

## 6. Auth & Onboarding

### Auth flow

1. **Pre-demo:** Script creates Supabase Auth user + `coaches` row (`scripts/seed_demo_coach.py`)
2. **Login:** Coach enters email/password → Supabase JS SDK → JWT returned → frontend calls `POST /api/coach/auth/exchange` → backend validates JWT, looks up coach, returns domain identity
3. **Every request:** `Authorization: Bearer <access_token>` → middleware validates, attaches coach_id + team_id
4. **Token refresh:** Handled silently by Supabase SDK (1hr access, 7-day refresh)
5. **Logout:** `supabase.auth.signOut()` + clear React Context → redirect to login
6. **Password reset:** Supabase's built-in email flow via "Forgot password" link

### JWT validation

Validate against Supabase JWKS (preferred) or shared secret (fallback). Extract `sub` → lookup `coaches.supabase_user_id`. Team_id comes from DB lookup, NOT from JWT claims — prevents token forgery.

### Onboarding (v0)

There is no onboarding flow. The coach logs in and sees a fully populated dashboard. Zero setup, zero configuration, zero empty states.

**Coach's first experience:**
1. Receive email with URL + credentials
2. Enter email/password on login page
3. Land on Team Overview with 11 pitchers, real data, everything pre-populated
4. Start coaching

### Anti-goals for v0

- No self-serve signup
- No organization / multi-team accounts
- No role-based access within a team
- No invite links for additional coaches
- No OAuth (Google/Apple)
- No 2FA
- No session device tracking

### Security posture

- `@require_coach_auth` decorator on every coach route
- `team_scope.py` is the only way to query pitcher data in coach code paths
- Team_id validated before every query; missing team_id → 500 (fail loudly)
- HTTPS enforced by Vercel + Railway defaults
- No CSRF concern (JWT in Authorization header, not cookies)

---

## 7. Demo Flow & Exit Criteria

### Scripted demo (10 minutes, 8 moments)

**Moment 1 — "Here's your team." (0:00–0:45)**
Login → Team Overview. 11 pitchers, compliance ring, flags visible. Full picture in one screen.

**Moment 2 — "Let's check on Carter." (0:45–2:00)**
Click Carter → slide-over → TJ recovery flag, arm feel 2/5, auto-reduced throwing. System is protecting him automatically.

**Moment 3 — "Jake starts Saturday." (2:00–3:30)**
Schedule → click Saturday → assign Jake as starter → toast confirms → Next Start column updates.

**Moment 4 — "What does Jake's week look like?" (3:30–5:00)**
Click Jake → This Week → forward strip shows ramp to Saturday (normal → normal → pre-start light → light catch → GAME).

**Moment 5 — "The AI flagged something." (5:00–6:30)**
Insights → pre-start nudge: "Heavy Tuesday may hurt Jake's Saturday." Accept → Tuesday auto-lightened.

**Moment 6 — "Matthew can't deadlift this week." (6:30–7:30)**
Matthew slide-over → Adjust Today (swap trap bar → RDL) → Add Restriction (trap bar blocked, expires Monday).

**Moment 7 — "Roll out the velocity program." (7:30–9:00)**
Team Programs → Velocity Program → preview → Assign → 11 pitchers affected.

**Moment 8 — "Here's what the pitcher sees." (9:00–10:00)**
Switch to Mini App → Jake's plan shows coach adjustments + "Velocity Block — Week 1, Day 1" tag. Loop closed.

### Exit criteria (24 items)

**Functional:**
1. Coach logs in and lands on populated Team Overview within 3 seconds
2. Compliance ring accurately reflects today's check-in count
3. Roster shows all 11 pitchers with correct status, flags, 7-day strips, streaks
4. Click pitcher → slide-over with profile, today's plan, week strip, history, flags
5. "Adjust Today" writes to daily_entries, immediately visible in slide-over and Mini App
6. "Add Restriction" writes to pitcher_training_model, affects next plan generation
7. Schedule shows hand-seeded games; coach can assign starter via dropdown
8. Starter assignment triggers days_until_next_start computation; upcoming plans reflect pre-start ramp
9. Team Programs shows block library; coach can assign a throwing block
10. Active team block content appears as throwing-section baseline in plan generation
11. DailyCard in Mini App renders "Team Block — Week N, Day M" tag when block active
12. Phase blocks visible and editable on Phases screen; engine reads current phase emphasis
13. Insights shows at least one pre-start nudge with Accept/Dismiss
14. Accepting an insight applies the proposed mutation and resolves the suggestion
15. All data is team_id-scoped; no endpoint returns cross-team data

**Non-functional:**
16. Team Overview loads < 2 seconds (single API round-trip)
17. Player detail slide-over loads < 1 second
18. Override actions complete < 1 second (optimistic UI)
19. No visual regressions in existing Mini App
20. Dashboard usable at 1440px, doesn't break at 1024px

**Data safety:**
21. All new tables created via single idempotent migration
22. Existing tables have team_id backfilled; no orphaned FKs
23. Existing bot/mini-app flows unaffected
24. Coach auth isolated from pitcher auth

### Pre-demo checklist

- [ ] Migration 006 applied to production Supabase
- [ ] Demo coach account created and login tested
- [ ] UChicago schedule hand-seeded into team_games
- [ ] 3–4 block templates seeded into block_library
- [ ] Off-season phase blocks seeded into training_phase_blocks
- [ ] coach-app deployed to Vercel at demo URL
- [ ] All 24 exit criteria verified manually against production data
- [ ] One dry-run of 10-minute demo with real data, end to end

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Supabase Auth JWT validation setup is fiddly | Medium | Blocks all coach endpoints | Fall back to shared-secret validation |
| `days_until_next_start` edge cases (reliever as emergency starter, game cancelled) | Medium | Incorrect ramp programs | Scope to starters only; ignore edge cases; cancellation clears starting_pitcher_id |
| Coach Insights generates low-quality suggestions | Low | Undermines "AI coaches the coach" moment | Kill switch: disable cron, hand-seed 2–3 curated suggestions for demo |
| Team block + triage + injury flag interaction creates weird plans | Medium | Unexpected programs | Test with Carter Heron (TJ recovery + team block) as stress case; triage always wins |
| Frontend build takes longer than expected (6 screens + slide-over) | High | Dashboard not polished | Prioritize in demo order: Team Overview + Player Detail first, Schedule second, Team Programs third, Insights fourth, Phases last. Phases can be hand-seeded without UI. |

---

## 9. v1 Backlog Reference

Full v1 backlog is maintained in `docs/superpowers/specs/2026-04-09-coach-dashboard-v1-backlog.md` (20+ items with rationales). Key deferred features:

1. Pitcher usage timeline / drag-rotation view
2. Structured bullpens/scrimmages entry
3. Real athletics page scraper
4. Coach Insights v1 — multi-category
5. Return-to-mound integration
6. Coach-editable templates
7. Team-wide rules
8. Native app (React Native)
9. Weight logging UI
10. Custom video library
11. Self-serve coach onboarding
12. Lifting team-blocks
13. Coach-authored custom blocks
14. Multiple concurrent team blocks
15. Per-position-group block assignment

That backlog is a living document — items are added during implementation and struck through (not deleted) when promoted to v0.
