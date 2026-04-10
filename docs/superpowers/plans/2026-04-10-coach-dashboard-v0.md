# Coach Dashboard v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a coach-facing web dashboard that provides compliance visibility, player drill-down, schedule/starter management, team program assignment, off-season phase blocks, and AI-generated coaching insights for the UChicago pitching staff.

**Architecture:** Monorepo sibling React app (`coach-app/` alongside `mini-app/`), sharing the existing FastAPI backend via new `/api/coach/*` routes. Supabase Auth for coach login, application-layer team_id scoping. 7 new DB tables + additive columns on 5 existing tables.

**Tech Stack:** React 18 + Vite + Tailwind CSS (coach-app), FastAPI + python-telegram-bot (existing backend), Supabase (Postgres + Auth), Vercel (frontend deploy), Railway (backend deploy).

**Design spec:** `docs/superpowers/specs/2026-04-09-coach-dashboard-v0-design.md`

**Frontend implementation note:** Use `superpowers:frontend-design` skill when building coach-app screens.

---

## File Structure

### New files — Backend

| File | Responsibility |
|---|---|
| `api/coach_auth.py` | Supabase JWT validation middleware, coach identity resolution, `@require_coach_auth` decorator |
| `api/coach_routes.py` | All `/api/coach/*` endpoints (FastAPI router) |
| `bot/services/team_scope.py` | Team-scoped DB query helper — wraps queries with `.eq("team_id", team_id)` |
| `bot/services/coach_insights.py` | Generates pre-start nudge suggestions, writes to `coach_suggestions` table |
| `bot/services/team_programs.py` | Resolves active team block for a pitcher/date, provides content to plan generator |
| `scripts/migrations/006_coach_dashboard_foundation.sql` | Single idempotent migration: 7 new tables + column additions + backfill |
| `scripts/seed_demo_coach.py` | Creates Supabase Auth user + coaches row for demo |
| `scripts/seed_schedule.py` | Populates `team_games` with UChicago 2026 schedule |
| `scripts/seed_block_library.py` | Populates `block_library` with 3-4 throwing program templates |

### New files — Frontend (coach-app)

| File | Responsibility |
|---|---|
| `coach-app/package.json` | Dependencies: react, react-router-dom, @supabase/supabase-js, tailwindcss |
| `coach-app/vite.config.js` | Vite config with React plugin |
| `coach-app/tailwind.config.js` | Design tokens matching spec (maroon, cream, etc.) |
| `coach-app/index.html` | SPA entry point |
| `coach-app/src/main.jsx` | React DOM render + providers |
| `coach-app/src/App.jsx` | Router + auth context + layout shell |
| `coach-app/src/api.js` | Coach API client (fetchCoachApi, postCoachApi) with Supabase JWT |
| `coach-app/src/hooks/useCoachAuth.jsx` | Supabase Auth hook: login, logout, token management, coach identity |
| `coach-app/src/hooks/useApi.jsx` | Generic data-fetching hook with loading/error/refetch |
| `coach-app/src/components/Shell.jsx` | Top bar + left sidebar + main content area layout |
| `coach-app/src/components/ComplianceRing.jsx` | SVG compliance circle |
| `coach-app/src/components/RosterTable.jsx` | Dense roster table with sorting/filtering |
| `coach-app/src/components/PlayerSlideOver.jsx` | Right-side slide-over panel for player detail |
| `coach-app/src/components/PlayerToday.jsx` | Tab 1: today's program + override actions |
| `coach-app/src/components/PlayerWeek.jsx` | Tab 2: 7-day forward/back strip |
| `coach-app/src/components/PlayerHistory.jsx` | Tab 3: compliance calendar + trends |
| `coach-app/src/components/AdjustTodayModal.jsx` | Override verb 1: mutation builder |
| `coach-app/src/components/AddRestrictionModal.jsx` | Override verb 2: restriction form |
| `coach-app/src/components/GamePanel.jsx` | Side panel for game detail + starter assignment |
| `coach-app/src/components/BlockCard.jsx` | Block library card + preview |
| `coach-app/src/components/InsightCard.jsx` | Coach suggestion card with Accept/Dismiss |
| `coach-app/src/components/PhaseTimeline.jsx` | Horizontal phase block timeline |
| `coach-app/src/components/Toast.jsx` | Toast notification component |
| `coach-app/src/pages/Login.jsx` | Email/password login page |
| `coach-app/src/pages/TeamOverview.jsx` | Screen 1: roster + compliance + summary cards |
| `coach-app/src/pages/Schedule.jsx` | Screen 3: month calendar + game management |
| `coach-app/src/pages/TeamPrograms.jsx` | Screen 4: active blocks + library |
| `coach-app/src/pages/Phases.jsx` | Screen 5: off-season phase timeline |
| `coach-app/src/pages/Insights.jsx` | Screen 6: AI suggestion feed |

### Modified files

| File | Change |
|---|---|
| `api/main.py` | Add CORS origins for coach-app, include coach_routes router, allow PATCH/DELETE methods |
| `bot/services/db.py` | Add team_games CRUD functions, update schedule functions to read from team_games, add `_DAILY_ENTRY_COLUMNS` update for `active_team_block_id` and `team_id` |
| `bot/services/plan_generator.py` | Hook team block resolution into throwing template selection, add `days_until_next_start` computation |
| `bot/services/exercise_pool.py` | Read current training phase emphasis from `training_phase_blocks`, bias prescription mode |
| `mini-app/src/components/DailyCard.jsx` | Add "Team Block — Week N, Day M" tag when active (~20 lines) |

---

## Task Breakdown

### Task 1: Database Migration

**Files:**
- Create: `pitcher_program_app/scripts/migrations/006_coach_dashboard_foundation.sql`

This is the foundation everything else depends on. Run via Supabase MCP.

- [ ] **Step 1: Write the migration SQL**

```sql
-- 006_coach_dashboard_foundation.sql
-- Coach Dashboard v0: 7 new tables + additive columns + backfill
-- Idempotent: uses IF NOT EXISTS and ON CONFLICT DO NOTHING

-- 1. teams
CREATE TABLE IF NOT EXISTS teams (
    team_id         text PRIMARY KEY,
    name            text NOT NULL,
    level           text,
    training_phase  text DEFAULT 'offseason',
    timezone        text DEFAULT 'America/Chicago',
    settings        jsonb DEFAULT '{}',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

INSERT INTO teams (team_id, name, level, training_phase, timezone)
VALUES ('uchicago_baseball', 'UChicago Baseball', 'd3_college', 'in_season', 'America/Chicago')
ON CONFLICT (team_id) DO NOTHING;

-- 2. coaches
CREATE TABLE IF NOT EXISTS coaches (
    coach_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    email            text UNIQUE NOT NULL,
    name             text NOT NULL,
    role             text,
    supabase_user_id uuid UNIQUE,
    created_at       timestamptz DEFAULT now()
);

-- 3. team_games (replaces schedule table)
CREATE TABLE IF NOT EXISTS team_games (
    game_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id              text NOT NULL REFERENCES teams(team_id),
    game_date            date NOT NULL,
    game_time            time,
    opponent             text,
    home_away            text,
    is_doubleheader_g2   boolean DEFAULT false,
    starting_pitcher_id  text REFERENCES pitchers(pitcher_id),
    status               text DEFAULT 'scheduled',
    source               text DEFAULT 'manual',
    notes                text,
    created_at           timestamptz DEFAULT now(),
    updated_at           timestamptz DEFAULT now(),
    UNIQUE (team_id, game_date, is_doubleheader_g2)
);

-- Migrate existing schedule rows into team_games
INSERT INTO team_games (team_id, game_date, opponent, home_away, game_time, is_doubleheader_g2, source)
SELECT
    'uchicago_baseball',
    game_date,
    opponent,
    home_away,
    start_time::time,
    COALESCE(is_doubleheader, false),
    'scraped'
FROM schedule
ON CONFLICT (team_id, game_date, is_doubleheader_g2) DO NOTHING;

-- 4. block_library
CREATE TABLE IF NOT EXISTS block_library (
    block_template_id   text PRIMARY KEY,
    name                text NOT NULL,
    description         text,
    block_type          text NOT NULL,
    duration_days       integer NOT NULL,
    content             jsonb NOT NULL,
    source              text,
    created_at          timestamptz DEFAULT now()
);

-- 5. team_assigned_blocks
CREATE TABLE IF NOT EXISTS team_assigned_blocks (
    block_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    block_type            text NOT NULL,
    block_template_id     text NOT NULL,
    start_date            date NOT NULL,
    duration_days         integer NOT NULL,
    assigned_by_coach_id  uuid REFERENCES coaches(coach_id),
    notes                 text,
    status                text DEFAULT 'active',
    created_at            timestamptz DEFAULT now()
);

-- 6. coach_suggestions
CREATE TABLE IF NOT EXISTS coach_suggestions (
    suggestion_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    pitcher_id            text NOT NULL REFERENCES pitchers(pitcher_id),
    category              text NOT NULL,
    title                 text NOT NULL,
    reasoning             text NOT NULL,
    proposed_action       jsonb,
    status                text DEFAULT 'pending',
    expires_at            timestamptz,
    created_at            timestamptz DEFAULT now(),
    resolved_at           timestamptz,
    resolved_by_coach_id  uuid REFERENCES coaches(coach_id)
);

-- 7. training_phase_blocks
CREATE TABLE IF NOT EXISTS training_phase_blocks (
    phase_block_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    phase_name       text NOT NULL,
    start_date       date NOT NULL,
    end_date         date NOT NULL,
    emphasis         text,
    notes            text,
    created_at       timestamptz DEFAULT now(),
    CHECK (end_date >= start_date)
);

-- Seed current UChicago offseason phases
INSERT INTO training_phase_blocks (team_id, phase_name, start_date, end_date, emphasis)
VALUES
    ('uchicago_baseball', 'Fall GPP', '2025-10-01', '2025-10-28', 'hypertrophy'),
    ('uchicago_baseball', 'Strength Block', '2025-10-29', '2025-12-15', 'strength'),
    ('uchicago_baseball', 'Power Block', '2026-01-05', '2026-02-07', 'power'),
    ('uchicago_baseball', 'Preseason Ramp', '2026-02-08', '2026-02-28', 'maintenance'),
    ('uchicago_baseball', 'In-Season', '2026-03-01', '2026-05-31', 'maintenance')
ON CONFLICT DO NOTHING;

-- 8. Add team_id to existing tables
ALTER TABLE pitchers ADD COLUMN IF NOT EXISTS team_id text DEFAULT 'uchicago_baseball' REFERENCES teams(team_id);
UPDATE pitchers SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS team_id text;
UPDATE daily_entries SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS active_team_block_id uuid;

ALTER TABLE saved_plans ADD COLUMN IF NOT EXISTS team_id text;
UPDATE saved_plans SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS team_id text;
UPDATE weekly_summaries SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS team_id text;
UPDATE chat_messages SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;
```

- [ ] **Step 2: Apply via Supabase MCP**

Run each statement via `mcp__claude_ai_Supabase__execute_sql`. Execute in order. Verify each table is created before moving to ALTER statements.

- [ ] **Step 3: Verify migration**

Run: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('teams', 'coaches', 'team_games', 'block_library', 'team_assigned_blocks', 'coach_suggestions', 'training_phase_blocks');`

Expected: 7 rows returned.

Run: `SELECT column_name FROM information_schema.columns WHERE table_name = 'pitchers' AND column_name = 'team_id';`

Expected: 1 row returned.

Run: `SELECT count(*) FROM team_games;`

Expected: count matching the existing `schedule` table row count.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/scripts/migrations/006_coach_dashboard_foundation.sql
git commit -m "feat: add migration 006 — coach dashboard foundation tables + team_id backfill"
```

---

### Task 2: Seed Scripts (Schedule, Block Library, Demo Coach)

**Files:**
- Create: `pitcher_program_app/scripts/seed_schedule.py`
- Create: `pitcher_program_app/scripts/seed_block_library.py`
- Create: `pitcher_program_app/scripts/seed_demo_coach.py`

These populate the database with demo-ready data. Run after migration.

- [ ] **Step 1: Write seed_schedule.py**

```python
"""Seed team_games with UChicago 2026 spring schedule.

Usage: python -m scripts.seed_schedule
Idempotent — uses ON CONFLICT DO NOTHING on (team_id, game_date, is_doubleheader_g2).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

TEAM_ID = "uchicago_baseball"

# UChicago 2026 spring schedule — fill in from athletics page
# Format: (game_date, opponent, home_away, is_doubleheader_g2)
GAMES = [
    # March
    ("2026-03-07", "Wheaton", "away", False),
    ("2026-03-08", "Wheaton", "away", False),
    ("2026-03-14", "North Central", "home", False),
    ("2026-03-15", "North Central", "home", False),
    ("2026-03-21", "Wash U", "away", False),
    ("2026-03-22", "Wash U", "away", False),
    ("2026-03-28", "Case Western", "home", False),
    ("2026-03-29", "Case Western", "home", False),
    # April
    ("2026-04-04", "Emory", "away", False),
    ("2026-04-05", "Emory", "away", False),
    ("2026-04-11", "Carnegie Mellon", "home", False),
    ("2026-04-12", "Carnegie Mellon", "home", False),
    ("2026-04-18", "NYU", "home", False),
    ("2026-04-19", "NYU", "home", False),
    ("2026-04-25", "Brandeis", "away", False),
    ("2026-04-26", "Brandeis", "away", False),
    # May
    ("2026-05-02", "Rochester", "home", False),
    ("2026-05-03", "Rochester", "home", False),
    ("2026-05-09", "UAA Tournament", "away", False),
    ("2026-05-10", "UAA Tournament", "away", False),
]


def seed():
    client = get_client()
    rows = [
        {
            "team_id": TEAM_ID,
            "game_date": date,
            "opponent": opp,
            "home_away": ha,
            "is_doubleheader_g2": dh,
            "source": "manual",
            "status": "scheduled",
        }
        for date, opp, ha, dh in GAMES
    ]
    resp = client.table("team_games").upsert(
        rows,
        on_conflict="team_id,game_date,is_doubleheader_g2"
    ).execute()
    print(f"Seeded {len(resp.data)} games into team_games")


if __name__ == "__main__":
    seed()
```

**Note:** The GAMES list above is a placeholder — Landon should replace with the real UChicago 2026 schedule before the demo. The script structure is correct regardless.

- [ ] **Step 2: Write seed_block_library.py**

```python
"""Seed block_library with 3-4 throwing program templates.

Sources: data/templates/throwing_ramp_up.md, past_arm_programs/*.xlsx
Usage: python -m scripts.seed_block_library
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

BLOCKS = [
    {
        "block_template_id": "velocity_12wk_v1",
        "name": "Velocity Development Program",
        "description": "12-week progressive velocity program. Builds from base throwing through max-intent pulldowns. 3 throwing days per week.",
        "block_type": "throwing",
        "duration_days": 84,
        "source": "landon_starters.xlsx + throwing_ramp_up.md",
        "content": {
            "weeks": 12,
            "throws_per_week": 3,
            "rest_days_pattern": [3, 7],
            "phases": [
                {
                    "name": "Base Building",
                    "weeks": [1, 2, 3],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [40, 60],
                    "effort_pct": 50,
                    "intent_notes": "Build base. Groove mechanics. Light effort.",
                    "drills": ["high_pec_load_x10_at_30ft", "snap_snap_rocker_x5", "self_toss_x5"]
                },
                {
                    "name": "Distance Extension",
                    "weeks": [4, 5, 6],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft"],
                    "total_throws_range": [50, 66],
                    "effort_pct": 70,
                    "intent_notes": "Add distance progressively. Work back in at 60ft.",
                    "drills": ["qb_drop_back_50pct", "lateral_bound_50pct"]
                },
                {
                    "name": "Compression + Pulldowns",
                    "weeks": [7, 8, 9],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft", "120ft"],
                    "total_throws_range": [55, 70],
                    "effort_pct": 80,
                    "intent_notes": "80% on-a-line at 90/75. Introduce pulldowns at 105/90.",
                    "drills": ["compression_on_a_line", "pulldowns_at_105_90"]
                },
                {
                    "name": "Max Intent + Mound",
                    "weeks": [10, 11, 12],
                    "distances": ["full_progression", "mound_work"],
                    "total_throws_range": [60, 75],
                    "effort_pct": 90,
                    "intent_notes": "Full progression with pulldowns. Add mound work at 50ft progressing to 60.5ft.",
                    "drills": ["pulldowns_100pct", "mound_fastball_only"]
                }
            ],
            "post_session_recovery": "medium"
        }
    },
    {
        "block_template_id": "longtoss_ramp_6wk_v1",
        "name": "Long-Toss Ramp Up",
        "description": "6-week progressive throwing ramp-up. From 45ft to 120ft with structured drill progressions. Source: throwing_ramp_up.md.",
        "block_type": "throwing",
        "duration_days": 42,
        "source": "throwing_ramp_up.md",
        "content": {
            "weeks": 6,
            "throws_per_week": 3,
            "rest_days_pattern": [3, 7],
            "phases": [
                {
                    "name": "Week 1 — Base",
                    "weeks": [1],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [40, 50],
                    "effort_pct": 50,
                    "intent_notes": "Build base. Pre-throw: uphill wall, sock throws, high pec load at 30ft.",
                    "drills": ["high_pec_load_x10_at_30ft", "snap_snap_rocker_x5", "self_toss_x5"]
                },
                {
                    "name": "Week 2 — Add 90ft",
                    "weeks": [2],
                    "distances": ["45ft", "60ft", "75ft", "90ft"],
                    "total_throws_range": [45, 60],
                    "effort_pct": 60,
                    "intent_notes": "Add 90ft. Work back in at 60ft on days 2-3.",
                    "drills": ["figure_8_rocker_25pct", "half_kneel_start_25pct", "step_back_25pct"]
                },
                {
                    "name": "Week 3 — Add 105ft",
                    "weeks": [3],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft"],
                    "total_throws_range": [60, 66],
                    "effort_pct": 70,
                    "intent_notes": "Add 105ft. Work back in at 90/75/60ft.",
                    "drills": ["qb_drop_back_50pct", "lateral_bound_50pct"]
                },
                {
                    "name": "Weeks 4-6 — 120ft + Compression",
                    "weeks": [4, 5, 6],
                    "distances": ["45ft", "60ft", "75ft", "90ft", "105ft", "120ft"],
                    "total_throws_range": [48, 65],
                    "effort_pct": 80,
                    "intent_notes": "Add 120ft. Introduce 80% on-a-line compression at 90/75.",
                    "drills": ["compression_on_a_line"]
                }
            ],
            "post_session_recovery": "medium"
        }
    },
    {
        "block_template_id": "offseason_base_4wk_v1",
        "name": "Offseason Throwing Base",
        "description": "4-week light throwing program for early offseason. Maintains arm health without intensity. 2-3 days per week.",
        "block_type": "throwing",
        "duration_days": 28,
        "source": "starter_7day template + coaching knowledge",
        "content": {
            "weeks": 4,
            "throws_per_week": 2,
            "rest_days_pattern": [3, 4, 7],
            "phases": [
                {
                    "name": "Weeks 1-4 — Maintenance Catch",
                    "weeks": [1, 2, 3, 4],
                    "distances": ["45ft", "60ft", "75ft"],
                    "total_throws_range": [30, 40],
                    "effort_pct": 40,
                    "intent_notes": "Light catch play. Focus on feel and arm health. No intent.",
                    "drills": ["light_catch_play"]
                }
            ],
            "post_session_recovery": "light"
        }
    }
]


def seed():
    client = get_client()
    resp = client.table("block_library").upsert(
        BLOCKS, on_conflict="block_template_id"
    ).execute()
    print(f"Seeded {len(resp.data)} blocks into block_library")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 3: Write seed_demo_coach.py**

```python
"""Create a demo coach account in Supabase Auth + coaches table.

Usage: python -m scripts.seed_demo_coach
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

TEAM_ID = "uchicago_baseball"
COACH_EMAIL = os.getenv("DEMO_COACH_EMAIL", "coach@uchicago.example.com")
COACH_NAME = os.getenv("DEMO_COACH_NAME", "Coach Krause")
COACH_ROLE = "head"


def seed():
    client = get_client()

    # Create Supabase Auth user via admin API
    # Note: supabase-py's auth.admin requires the service role key (already used)
    try:
        auth_resp = client.auth.admin.create_user({
            "email": COACH_EMAIL,
            "password": os.getenv("DEMO_COACH_PASSWORD", "changeme2026!"),
            "email_confirm": True,
        })
        supabase_user_id = auth_resp.user.id
        print(f"Created Supabase Auth user: {supabase_user_id}")
    except Exception as e:
        if "already been registered" in str(e).lower() or "duplicate" in str(e).lower():
            # User exists — look up their ID
            users = client.auth.admin.list_users()
            supabase_user_id = None
            for u in users:
                if hasattr(u, 'email') and u.email == COACH_EMAIL:
                    supabase_user_id = u.id
                    break
            if not supabase_user_id:
                print(f"ERROR: Auth user exists but couldn't find ID: {e}")
                return
            print(f"Auth user already exists: {supabase_user_id}")
        else:
            print(f"ERROR creating auth user: {e}")
            return

    # Upsert coaches row
    coach_row = {
        "team_id": TEAM_ID,
        "email": COACH_EMAIL,
        "name": COACH_NAME,
        "role": COACH_ROLE,
        "supabase_user_id": str(supabase_user_id),
    }
    resp = client.table("coaches").upsert(
        coach_row, on_conflict="email"
    ).execute()
    print(f"Upserted coach row: {resp.data}")
    print(f"\nLogin credentials:")
    print(f"  Email: {COACH_EMAIL}")
    print(f"  Password: (set via DEMO_COACH_PASSWORD env var)")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 4: Run all seed scripts**

```bash
cd pitcher_program_app
python -m scripts.seed_schedule
python -m scripts.seed_block_library
python -m scripts.seed_demo_coach
```

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/seed_schedule.py pitcher_program_app/scripts/seed_block_library.py pitcher_program_app/scripts/seed_demo_coach.py
git commit -m "feat: add seed scripts for schedule, block library, and demo coach"
```

---

### Task 3: Team Scope Helper + DB Functions

**Files:**
- Create: `pitcher_program_app/bot/services/team_scope.py`
- Modify: `pitcher_program_app/bot/services/db.py`

- [ ] **Step 1: Write team_scope.py**

```python
"""Team-scoped query helper for coach-initiated data access.

Every coach-initiated query MUST go through these helpers to ensure team_id
filtering is applied. Direct .table() queries without team_id in coach
code paths are a code review blocker.
"""

import logging
from bot.services.db import get_client

logger = logging.getLogger(__name__)


class TeamScopeViolation(Exception):
    """Raised when a coach query is attempted without a team_id."""
    pass


def _require_team_id(team_id: str) -> str:
    if not team_id:
        raise TeamScopeViolation("team_id must be set for all coach queries")
    return team_id


def list_team_pitchers(team_id: str) -> list:
    """Return all pitchers for a team."""
    team_id = _require_team_id(team_id)
    resp = (get_client().table("pitchers")
            .select("*")
            .eq("team_id", team_id)
            .execute())
    return resp.data or []


def get_team_roster_overview(team_id: str, today_str: str) -> list:
    """Return roster with today's check-in status and recent history.

    Combines pitchers + today's daily_entries + 7-day entry history
    into a pre-aggregated list for the Team Overview screen.
    """
    team_id = _require_team_id(team_id)
    client = get_client()

    # All pitchers on the team
    pitchers = (client.table("pitchers")
                .select("pitcher_id, name, role, telegram_username, physical, pitching")
                .eq("team_id", team_id)
                .execute()).data or []

    # Today's entries for the team
    today_entries = (client.table("daily_entries")
                    .select("pitcher_id, pre_training, plan_generated, completed_exercises, warmup")
                    .eq("team_id", team_id)
                    .eq("date", today_str)
                    .execute()).data or []
    today_map = {e["pitcher_id"]: e for e in today_entries}

    # Last 7 days of entries for streak/history
    from datetime import date as _date, timedelta
    week_ago = (_date.fromisoformat(today_str) - timedelta(days=6)).isoformat()
    week_entries = (client.table("daily_entries")
                    .select("pitcher_id, date, completed_exercises")
                    .eq("team_id", team_id)
                    .gte("date", week_ago)
                    .lte("date", today_str)
                    .execute()).data or []

    # Group week entries by pitcher
    week_map = {}
    for e in week_entries:
        pid = e["pitcher_id"]
        week_map.setdefault(pid, []).append(e)

    # Training models for flag info
    models = (client.table("pitcher_training_model")
              .select("pitcher_id, flag_level, active_modifications, days_since_outing")
              .in_("pitcher_id", [p["pitcher_id"] for p in pitchers])
              .execute()).data or []
    model_map = {m["pitcher_id"]: m for m in models}

    # Injury flags
    injuries = (client.table("injury_history")
                .select("pitcher_id, area, status, flag_level")
                .in_("pitcher_id", [p["pitcher_id"] for p in pitchers])
                .execute()).data or []
    injury_map = {}
    for inj in injuries:
        injury_map.setdefault(inj["pitcher_id"], []).append(inj)

    # Next scheduled starts
    upcoming_starts = (client.table("team_games")
                       .select("starting_pitcher_id, game_date")
                       .eq("team_id", team_id)
                       .gte("game_date", today_str)
                       .eq("status", "scheduled")
                       .not_.is_("starting_pitcher_id", "null")
                       .order("game_date")
                       .execute()).data or []
    # First upcoming start per pitcher
    next_start_map = {}
    for g in upcoming_starts:
        pid = g["starting_pitcher_id"]
        if pid not in next_start_map:
            next_start_map[pid] = g["game_date"]

    # Assemble roster
    roster = []
    for p in pitchers:
        pid = p["pitcher_id"]
        today = today_map.get(pid)
        model = model_map.get(pid, {})
        week = week_map.get(pid, [])

        has_checked_in = bool(today and today.get("plan_generated"))

        # Build 7-day strip
        last_7 = []
        for i in range(6, -1, -1):
            d = (_date.fromisoformat(today_str) - timedelta(days=i)).isoformat()
            day_entry = next((e for e in week if e["date"] == d), None)
            if day_entry and day_entry.get("completed_exercises"):
                last_7.append({"date": d, "status": "checked_in"})
            elif day_entry:
                last_7.append({"date": d, "status": "partial"})
            else:
                last_7.append({"date": d, "status": "none"})

        # Streak count
        streak = 0
        for day in reversed(last_7):
            if day["status"] == "checked_in":
                streak += 1
            else:
                break

        # Active injury flags
        active_flags = []
        for inj in injury_map.get(pid, []):
            if inj.get("status") in ("active", "monitoring"):
                active_flags.append(f"{inj.get('area', 'unknown')} ({inj.get('flag_level', '')})")

        roster.append({
            "pitcher_id": pid,
            "name": p.get("name", ""),
            "role": p.get("role", ""),
            "today_status": "checked_in" if has_checked_in else "not_yet",
            "flag_level": model.get("flag_level", "green"),
            "last_7_days": last_7,
            "streak": streak,
            "active_injury_flags": active_flags,
            "next_scheduled_start": next_start_map.get(pid),
        })

    return roster


def get_team_compliance(team_id: str, today_str: str, roster: list) -> dict:
    """Compute compliance stats from pre-assembled roster."""
    total = len(roster)
    checked_in = sum(1 for r in roster if r["today_status"] == "checked_in")
    flags = {"red": 0, "yellow": 0, "green": 0}
    for r in roster:
        fl = r.get("flag_level", "green")
        if fl in flags:
            flags[fl] += 1
    return {
        "checked_in_today": checked_in,
        "total": total,
        "flags": flags,
    }


def get_team_games(team_id: str, start_date: str = None, end_date: str = None) -> list:
    """Return team_games for a date range."""
    team_id = _require_team_id(team_id)
    q = (get_client().table("team_games")
         .select("*")
         .eq("team_id", team_id)
         .order("game_date"))
    if start_date:
        q = q.gte("game_date", start_date)
    if end_date:
        q = q.lte("game_date", end_date)
    return q.execute().data or []


def get_pitcher_next_start(pitcher_id: str, team_id: str, from_date: str) -> dict | None:
    """Return the next game where this pitcher is the assigned starter."""
    team_id = _require_team_id(team_id)
    resp = (get_client().table("team_games")
            .select("game_id, game_date, opponent, home_away")
            .eq("team_id", team_id)
            .eq("starting_pitcher_id", pitcher_id)
            .gte("game_date", from_date)
            .eq("status", "scheduled")
            .order("game_date")
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None
```

- [ ] **Step 2: Add team_games CRUD to db.py**

Add these functions to the end of `pitcher_program_app/bot/services/db.py`:

```python
# --- team_games ---

def get_team_game(game_id: str) -> dict:
    """Return a single team_games row by game_id."""
    resp = (get_client().table("team_games")
            .select("*")
            .eq("game_id", game_id)
            .single()
            .execute())
    return resp.data or {}


def upsert_team_game(game: dict) -> dict:
    """Insert or update a team_games row."""
    resp = (get_client().table("team_games")
            .upsert(game, on_conflict="game_id")
            .execute())
    return resp.data[0] if resp.data else {}


def delete_team_game(game_id: str) -> None:
    """Delete a team_games row."""
    get_client().table("team_games").delete().eq("game_id", game_id).execute()


# --- block_library ---

def list_block_library() -> list:
    """Return all block_library rows."""
    resp = (get_client().table("block_library")
            .select("*")
            .order("name")
            .execute())
    return resp.data or []


# --- team_assigned_blocks ---

def get_active_team_blocks(team_id: str) -> list:
    """Return active team_assigned_blocks for a team."""
    resp = (get_client().table("team_assigned_blocks")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", "active")
            .execute())
    return resp.data or []


def upsert_team_block(block: dict) -> dict:
    resp = (get_client().table("team_assigned_blocks")
            .upsert(block, on_conflict="block_id")
            .execute())
    return resp.data[0] if resp.data else {}


# --- coach_suggestions ---

def get_pending_suggestions(team_id: str) -> list:
    """Return pending coach_suggestions for a team."""
    resp = (get_client().table("coach_suggestions")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute())
    return resp.data or []


def upsert_suggestion(suggestion: dict) -> dict:
    resp = (get_client().table("coach_suggestions")
            .upsert(suggestion, on_conflict="suggestion_id")
            .execute())
    return resp.data[0] if resp.data else {}


# --- training_phase_blocks ---

def get_phase_blocks(team_id: str) -> list:
    """Return training_phase_blocks for a team, ordered by start_date."""
    resp = (get_client().table("training_phase_blocks")
            .select("*")
            .eq("team_id", team_id)
            .order("start_date")
            .execute())
    return resp.data or []


def get_current_phase(team_id: str, today_str: str) -> dict | None:
    """Return the phase block containing today's date."""
    resp = (get_client().table("training_phase_blocks")
            .select("*")
            .eq("team_id", team_id)
            .lte("start_date", today_str)
            .gte("end_date", today_str)
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None


def upsert_phase_block(block: dict) -> dict:
    resp = (get_client().table("training_phase_blocks")
            .upsert(block, on_conflict="phase_block_id")
            .execute())
    return resp.data[0] if resp.data else {}


def delete_phase_block(phase_block_id: str) -> None:
    get_client().table("training_phase_blocks").delete().eq("phase_block_id", phase_block_id).execute()


# --- coaches ---

def get_coach_by_supabase_id(supabase_user_id: str) -> dict | None:
    """Look up coach by Supabase Auth user ID."""
    resp = (get_client().table("coaches")
            .select("*")
            .eq("supabase_user_id", supabase_user_id)
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None
```

- [ ] **Step 3: Update schedule functions to read from team_games**

In `db.py`, update the three existing schedule functions to read from `team_games` instead of `schedule`. This preserves the function signatures so all existing callers (game_scraper.py, progression.py, routes.py) continue working:

```python
def get_schedule(limit: int = 50) -> list:
    """Return team_games rows ordered by game_date (backward-compat with schedule table)."""
    resp = (get_client().table("team_games")
            .select("*")
            .order("game_date", desc=False)
            .limit(limit)
            .execute())
    return resp.data or []


def get_schedule_by_dates(dates: list) -> dict:
    """Return team_games rows keyed by game_date for a list of date strings."""
    if not dates:
        return {}
    resp = (get_client().table("team_games")
            .select("game_date,opponent,home_away,game_time,is_doubleheader_g2")
            .in_("game_date", dates)
            .execute())
    return {row["game_date"]: row for row in (resp.data or [])}


def get_upcoming_games(from_date: str, days: int = 30) -> list:
    """Return team_games rows for the next N days from a given date."""
    from datetime import date as _date, timedelta
    end_date = (_date.fromisoformat(from_date) + timedelta(days=days)).isoformat()
    resp = (get_client().table("team_games")
            .select("game_date,opponent,home_away,game_time,is_doubleheader_g2")
            .gte("game_date", from_date)
            .lte("game_date", end_date)
            .order("game_date")
            .execute())
    return resp.data or []
```

- [ ] **Step 4: Update _DAILY_ENTRY_COLUMNS whitelist**

In `db.py`, add `"team_id"` and `"active_team_block_id"` to the `_DAILY_ENTRY_COLUMNS` set.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/team_scope.py pitcher_program_app/bot/services/db.py
git commit -m "feat: add team_scope helper + team_games/block/phase/coach DB functions"
```

---

### Task 4: Coach Auth Middleware

**Files:**
- Create: `pitcher_program_app/api/coach_auth.py`
- Modify: `pitcher_program_app/api/main.py`

- [ ] **Step 1: Write coach_auth.py**

```python
"""Supabase JWT validation for coach endpoints.

Validates the JWT from the Authorization: Bearer header, looks up the
coach record, and attaches coach_id + team_id to request.state.
"""

import os
import logging
from functools import wraps

import jwt
from fastapi import Request, HTTPException

from bot.services.db import get_coach_by_supabase_id

logger = logging.getLogger(__name__)

# Supabase JWT secret — same one used by Supabase Auth to sign JWTs
# Found in Supabase dashboard → Settings → API → JWT Secret
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


def _validate_coach_jwt(request: Request) -> dict:
    """Extract and validate Supabase JWT from Authorization header.

    Returns the coach DB row if valid.
    Raises HTTPException(401) if invalid or missing.
    Raises HTTPException(403) if JWT is valid but coach not found.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header[7:]  # strip "Bearer "

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid coach JWT: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    supabase_user_id = payload.get("sub")
    if not supabase_user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    coach = get_coach_by_supabase_id(supabase_user_id)
    if not coach:
        raise HTTPException(
            status_code=403,
            detail="No coach account found for this user"
        )

    return coach


async def require_coach_auth(request: Request) -> None:
    """FastAPI dependency that validates coach auth and attaches identity to request.state.

    Usage in route:
        @router.get("/api/coach/something")
        async def something(request: Request):
            await require_coach_auth(request)
            team_id = request.state.team_id
    """
    # Allow bypassing auth in dev
    if os.getenv("DISABLE_AUTH", "").lower() == "true":
        request.state.coach_id = "dev_coach"
        request.state.team_id = "uchicago_baseball"
        request.state.coach_name = "Dev Coach"
        request.state.coach_role = "head"
        return

    coach = _validate_coach_jwt(request)
    request.state.coach_id = coach["coach_id"]
    request.state.team_id = coach["team_id"]
    request.state.coach_name = coach["name"]
    request.state.coach_role = coach.get("role", "")
```

- [ ] **Step 2: Update api/main.py — CORS + coach router + methods**

Replace the contents of `api/main.py` with these changes:

```python
# After existing imports, add:
from api.coach_routes import coach_router

# Update ALLOWED_ORIGINS — add coach-app origins:
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev (mini-app)
    "http://localhost:4173",   # Vite preview
    "http://localhost:5174",   # Vite dev (coach-app — second port)
    "https://uchi-baseball-app.vercel.app",
]

# Add coach app URL from env
coach_app_url = os.getenv("COACH_APP_URL", "").rstrip("/")
if coach_app_url:
    ALLOWED_ORIGINS.append(coach_app_url)

# Update CORSMiddleware — add PATCH and DELETE methods:
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# After app.include_router(router), add:
app.include_router(coach_router)
```

- [ ] **Step 3: Add PyJWT to requirements.txt**

Add `PyJWT>=2.8.0` to `pitcher_program_app/requirements.txt`.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/api/coach_auth.py pitcher_program_app/api/main.py pitcher_program_app/requirements.txt
git commit -m "feat: add coach JWT auth middleware + CORS for coach-app"
```

---

### Task 5: Coach API Routes

**Files:**
- Create: `pitcher_program_app/api/coach_routes.py`

This is the largest backend task. All `/api/coach/*` endpoints.

- [ ] **Step 1: Write coach_routes.py — auth, overview, player detail**

```python
"""Coach dashboard API routes.

All endpoints require coach auth via require_coach_auth().
Team scoping is enforced by reading team_id from request.state (set by auth).
"""

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request, HTTPException

from api.coach_auth import require_coach_auth
from bot.config import CHICAGO_TZ
from bot.services import db as _db
from bot.services.team_scope import (
    get_team_roster_overview,
    get_team_compliance,
    get_team_games,
    get_pitcher_next_start,
    list_team_pitchers,
)

logger = logging.getLogger(__name__)

coach_router = APIRouter(prefix="/api/coach")


# ---- Auth ----

@coach_router.post("/auth/exchange")
async def auth_exchange(request: Request):
    """Validate Supabase JWT and return domain identity."""
    await require_coach_auth(request)
    return {
        "coach_id": request.state.coach_id,
        "team_id": request.state.team_id,
        "coach_name": request.state.coach_name,
        "role": request.state.coach_role,
    }


@coach_router.get("/me")
async def coach_me(request: Request):
    """Session restoration — same as auth/exchange but GET."""
    await require_coach_auth(request)
    return {
        "coach_id": request.state.coach_id,
        "team_id": request.state.team_id,
        "coach_name": request.state.coach_name,
        "role": request.state.coach_role,
    }


# ---- Team Overview ----

@coach_router.get("/team/overview")
async def team_overview(request: Request):
    """Single call for the entire Team Overview screen."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    roster = get_team_roster_overview(team_id, today_str)
    compliance = get_team_compliance(team_id, today_str, roster)

    # Today's schedule
    today_games = get_team_games(team_id, start_date=today_str, end_date=today_str)
    if today_games:
        g = today_games[0]
        starter_name = ""
        if g.get("starting_pitcher_id"):
            p = _db.get_pitcher(g["starting_pitcher_id"])
            starter_name = p.get("name", "") if p else ""
        schedule_summary = f"{'vs' if g.get('home_away') == 'home' else '@'} {g.get('opponent', 'TBD')}{'  Starter: ' + starter_name if starter_name else ''}"
    else:
        schedule_summary = "No games today"

    # Active team blocks
    active_blocks = _db.get_active_team_blocks(team_id)

    # Pending insights count
    pending = _db.get_pending_suggestions(team_id)

    # Team info
    team_resp = (
        _db.get_client().table("teams")
        .select("*")
        .eq("team_id", team_id)
        .single()
        .execute()
    )
    team = team_resp.data or {}

    return {
        "team": {
            "id": team_id,
            "name": team.get("name", ""),
            "training_phase": team.get("training_phase", ""),
            "today_schedule_summary": schedule_summary,
        },
        "compliance": compliance,
        "roster": roster,
        "active_blocks": [
            {
                "block_id": b["block_id"],
                "name": b.get("block_template_id", ""),
                "block_type": b.get("block_type", ""),
                "start_date": b.get("start_date", ""),
                "status": b.get("status", ""),
            }
            for b in active_blocks
        ],
        "insights_summary": {
            "pending_count": len(pending),
            "high_priority_count": sum(1 for s in pending if s.get("category") == "pre_start_nudge"),
        },
    }


# ---- Player Detail ----

@coach_router.get("/pitcher/{pitcher_id}")
async def coach_pitcher_detail(pitcher_id: str, request: Request):
    """Full pitcher detail for the slide-over panel."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    # Verify pitcher belongs to this team
    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    from bot.services.context_manager import load_profile
    profile = load_profile(pitcher_id)

    # Current week (back 3, today, forward 3)
    week_start = (date.fromisoformat(today_str) - timedelta(days=3)).isoformat()
    week_end = (date.fromisoformat(today_str) + timedelta(days=3)).isoformat()
    week_entries = (
        _db.get_client().table("daily_entries")
        .select("date, rotation_day, pre_training, plan_generated, completed_exercises, lifting, throwing, arm_care, warmup, plan_narrative, morning_brief, active_team_block_id")
        .eq("pitcher_id", pitcher_id)
        .gte("date", week_start)
        .lte("date", week_end)
        .order("date")
        .execute()
    ).data or []

    # Recent check-ins (last 10)
    recent_checkins = (
        _db.get_client().table("daily_entries")
        .select("date, pre_training, completed_exercises")
        .eq("pitcher_id", pitcher_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    ).data or []

    # Training model
    model = _db.get_training_model(pitcher_id)

    # Injuries
    injuries = (
        _db.get_client().table("injury_history")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .execute()
    ).data or []

    # WHOOP today
    whoop_today = None
    try:
        whoop_resp = (
            _db.get_client().table("whoop_daily")
            .select("*")
            .eq("pitcher_id", pitcher_id)
            .eq("date", today_str)
            .limit(1)
            .execute()
        )
        whoop_today = whoop_resp.data[0] if whoop_resp.data else None
    except Exception:
        pass

    # Next start
    next_start = get_pitcher_next_start(pitcher_id, team_id, today_str)

    # Active team block
    active_blocks = _db.get_active_team_blocks(team_id)
    active_block_info = None
    for b in active_blocks:
        if b.get("status") == "active":
            start = date.fromisoformat(b["start_date"])
            today_d = date.fromisoformat(today_str)
            day_in_block = (today_d - start).days + 1
            if 0 < day_in_block <= b.get("duration_days", 999):
                week = (day_in_block - 1) // 7 + 1
                day_of_week = (day_in_block - 1) % 7 + 1
                active_block_info = {
                    "block_id": b["block_id"],
                    "template_id": b["block_template_id"],
                    "week": week,
                    "day": day_of_week,
                    "day_in_block": day_in_block,
                }
            break

    # Pending suggestions for this pitcher
    all_suggestions = _db.get_pending_suggestions(team_id)
    pitcher_suggestions = [s for s in all_suggestions if s["pitcher_id"] == pitcher_id]

    return {
        "profile": profile,
        "current_week": week_entries,
        "recent_check_ins": recent_checkins,
        "training_model": model,
        "injuries": injuries,
        "whoop_today": whoop_today,
        "next_start": next_start,
        "active_team_block": active_block_info,
        "pending_suggestions": pitcher_suggestions,
    }


@coach_router.get("/pitcher/{pitcher_id}/day/{day_date}")
async def coach_pitcher_day(pitcher_id: str, day_date: str, request: Request):
    """Full daily entry for a specific date."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    entry = _db.get_daily_entry(pitcher_id, day_date)
    if not entry:
        raise HTTPException(status_code=404, detail="No entry for this date")
    return entry


# ---- Overrides ----

@coach_router.post("/pitcher/{pitcher_id}/adjust-today")
async def adjust_today(pitcher_id: str, request: Request):
    """Apply one-time mutations to today's plan (verb 1)."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    body = await request.json()
    mutations = body.get("mutations", [])
    target_date = body.get("date", datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d"))

    if not mutations:
        raise HTTPException(status_code=400, detail="No mutations provided")

    # Reuse existing mutation apply logic from routes.py
    from api.routes import _apply_mutations_to_entry
    entry = _db.get_daily_entry(pitcher_id, target_date)
    if not entry:
        raise HTTPException(status_code=404, detail="No plan exists for this date")

    updated_entry = _apply_mutations_to_entry(entry, mutations, source=f"coach:{coach_id}")
    _db.upsert_daily_entry(updated_entry)

    return {"status": "ok", "modifications_applied": mutations}


@coach_router.post("/pitcher/{pitcher_id}/restriction")
async def add_restriction(pitcher_id: str, request: Request):
    """Add a persistent restriction for an athlete (verb 2)."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    body = await request.json()
    restriction_type = body.get("restriction_type", "exercise_blocked")
    target = body.get("target", "")
    reason = body.get("reason", "")
    expires_at = body.get("expires_at")

    if not target:
        raise HTTPException(status_code=400, detail="Restriction target required")

    model = _db.get_training_model(pitcher_id)
    prefs = model.get("exercise_preferences") or {}
    prefs[target] = {
        "status": "blocked",
        "reason": reason,
        "restriction_type": restriction_type,
        "expires_at": expires_at,
        "set_by": "coach",
    }
    _db.upsert_training_model(pitcher_id, {"exercise_preferences": prefs})

    return {"status": "ok", "restriction": prefs[target]}


@coach_router.delete("/pitcher/{pitcher_id}/restriction/{restriction_key}")
async def remove_restriction(pitcher_id: str, restriction_key: str, request: Request):
    """Lift a previously-added restriction."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    pitcher = _db.get_pitcher(pitcher_id)
    if not pitcher or pitcher.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Pitcher not on your team")

    model = _db.get_training_model(pitcher_id)
    prefs = model.get("exercise_preferences") or {}
    if restriction_key in prefs:
        del prefs[restriction_key]
        _db.upsert_training_model(pitcher_id, {"exercise_preferences": prefs})

    return {"status": "ok"}


# ---- Schedule ----

@coach_router.get("/schedule")
async def coach_schedule(request: Request, start: str = None, end: str = None):
    """Return games for the team within a date range."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    games = get_team_games(team_id, start_date=start, end_date=end)
    return {"games": games}


@coach_router.post("/schedule/game")
async def add_game(request: Request):
    """Add a game to the schedule."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    game = {
        "team_id": team_id,
        "game_date": body["game_date"],
        "opponent": body.get("opponent"),
        "home_away": body.get("home_away"),
        "game_time": body.get("game_time"),
        "is_doubleheader_g2": body.get("is_doubleheader_g2", False),
        "starting_pitcher_id": body.get("starting_pitcher_id"),
        "notes": body.get("notes"),
        "source": "manual",
    }
    result = _db.upsert_team_game(game)
    return result


@coach_router.patch("/schedule/game/{game_id}")
async def update_game(game_id: str, request: Request):
    """Update game details — most commonly starter assignment."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    existing = _db.get_team_game(game_id)
    if not existing or existing.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Game not on your team")

    # Merge updates
    for key in ["game_date", "opponent", "home_away", "game_time",
                "is_doubleheader_g2", "starting_pitcher_id", "status", "notes"]:
        if key in body:
            existing[key] = body[key]

    existing["updated_at"] = datetime.now(CHICAGO_TZ).isoformat()
    result = _db.upsert_team_game(existing)
    return result


@coach_router.delete("/schedule/game/{game_id}")
async def delete_game(game_id: str, request: Request):
    """Remove a game."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    existing = _db.get_team_game(game_id)
    if not existing or existing.get("team_id") != team_id:
        raise HTTPException(status_code=403, detail="Game not on your team")

    _db.delete_team_game(game_id)
    return {"status": "ok"}


# ---- Team Programs ----

@coach_router.get("/team-programs/library")
async def block_library(request: Request):
    """Return pre-loaded block library."""
    await require_coach_auth(request)
    blocks = _db.list_block_library()
    return {"blocks": blocks}


@coach_router.get("/team-programs/active")
async def active_blocks(request: Request):
    """Return active team blocks."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    blocks = _db.get_active_team_blocks(team_id)
    return {"blocks": blocks}


@coach_router.post("/team-programs/assign")
async def assign_block(request: Request):
    """Assign a block to the team."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    body = await request.json()

    block_template_id = body.get("block_template_id")
    start_date = body.get("start_date")

    if not block_template_id or not start_date:
        raise HTTPException(status_code=400, detail="block_template_id and start_date required")

    # Check no active throwing block already
    active = _db.get_active_team_blocks(team_id)
    throwing_active = [b for b in active if b.get("block_type") == "throwing" and b.get("status") == "active"]
    if throwing_active:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BLOCK_ALREADY_ACTIVE",
                "message": "A throwing block is already active. End it first.",
                "active_block_id": throwing_active[0]["block_id"],
            }
        )

    # Look up template
    templates = _db.list_block_library()
    template = next((t for t in templates if t["block_template_id"] == block_template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Block template not found")

    block = {
        "team_id": team_id,
        "block_type": template["block_type"],
        "block_template_id": block_template_id,
        "start_date": start_date,
        "duration_days": body.get("duration_days", template["duration_days"]),
        "assigned_by_coach_id": coach_id,
        "notes": body.get("notes"),
        "status": "active",
    }
    result = _db.upsert_team_block(block)

    pitchers = list_team_pitchers(team_id)
    return {
        "block": result,
        "affected_pitchers_count": len(pitchers),
    }


@coach_router.post("/team-programs/{block_id}/end")
async def end_block(block_id: str, request: Request):
    """End a team block early."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    active = _db.get_active_team_blocks(team_id)
    block = next((b for b in active if b["block_id"] == block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="Active block not found")

    block["status"] = "completed"
    _db.upsert_team_block(block)
    return {"status": "ok"}


# ---- Phases ----

@coach_router.get("/phases")
async def list_phases(request: Request):
    """Return training phase blocks."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    phases = _db.get_phase_blocks(team_id)
    return {"phases": phases}


@coach_router.post("/phases")
async def create_phase(request: Request):
    """Create a new phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    phase = {
        "team_id": team_id,
        "phase_name": body["phase_name"],
        "start_date": body["start_date"],
        "end_date": body["end_date"],
        "emphasis": body.get("emphasis"),
        "notes": body.get("notes"),
    }
    result = _db.upsert_phase_block(phase)
    return result


@coach_router.patch("/phases/{phase_block_id}")
async def update_phase(phase_block_id: str, request: Request):
    """Update a phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    body = await request.json()

    phases = _db.get_phase_blocks(team_id)
    phase = next((p for p in phases if p["phase_block_id"] == phase_block_id), None)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    for key in ["phase_name", "start_date", "end_date", "emphasis", "notes"]:
        if key in body:
            phase[key] = body[key]

    result = _db.upsert_phase_block(phase)
    return result


@coach_router.delete("/phases/{phase_block_id}")
async def delete_phase(phase_block_id: str, request: Request):
    """Delete a phase block."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    phases = _db.get_phase_blocks(team_id)
    phase = next((p for p in phases if p["phase_block_id"] == phase_block_id), None)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    _db.delete_phase_block(phase_block_id)
    return {"status": "ok"}


# ---- Insights ----

@coach_router.get("/insights")
async def list_insights(request: Request, status: str = "pending"):
    """Return coach suggestions."""
    await require_coach_auth(request)
    team_id = request.state.team_id

    if status == "pending":
        suggestions = _db.get_pending_suggestions(team_id)
    else:
        suggestions = (
            _db.get_client().table("coach_suggestions")
            .select("*")
            .eq("team_id", team_id)
            .eq("status", status)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        ).data or []

    return {"suggestions": suggestions}


@coach_router.post("/insights/{suggestion_id}/accept")
async def accept_insight(suggestion_id: str, request: Request):
    """Accept a suggestion — execute the proposed action."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    suggestions = _db.get_pending_suggestions(team_id)
    suggestion = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already resolved")

    # Apply the proposed action if it exists
    proposed = suggestion.get("proposed_action")
    if proposed and proposed.get("mutations"):
        pitcher_id = suggestion["pitcher_id"]
        today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
        entry = _db.get_daily_entry(pitcher_id, today_str)
        if entry:
            from api.routes import _apply_mutations_to_entry
            updated = _apply_mutations_to_entry(entry, proposed["mutations"], source=f"insight:{suggestion_id}")
            _db.upsert_daily_entry(updated)

    # Mark resolved
    suggestion["status"] = "accepted"
    suggestion["resolved_at"] = datetime.now(CHICAGO_TZ).isoformat()
    suggestion["resolved_by_coach_id"] = coach_id
    _db.upsert_suggestion(suggestion)

    return {"status": "ok", "suggestion": suggestion}


@coach_router.post("/insights/{suggestion_id}/dismiss")
async def dismiss_insight(suggestion_id: str, request: Request):
    """Dismiss a suggestion."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}

    suggestions = _db.get_pending_suggestions(team_id)
    suggestion = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already resolved")

    suggestion["status"] = "dismissed"
    suggestion["resolved_at"] = datetime.now(CHICAGO_TZ).isoformat()
    suggestion["resolved_by_coach_id"] = coach_id
    _db.upsert_suggestion(suggestion)

    return {"status": "ok"}
```

- [ ] **Step 2: Verify _apply_mutations_to_entry exists in routes.py**

Check `pitcher_program_app/api/routes.py` for `_apply_mutations_to_entry` function. If it doesn't exist as a standalone function (it may be inline in the `/apply-mutations` endpoint), extract it into a function that `coach_routes.py` can import. The function should take `(entry: dict, mutations: list, source: str)` and return the modified entry dict.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/api/coach_routes.py
git commit -m "feat: add all coach API routes — overview, detail, overrides, schedule, programs, phases, insights"
```

---

### Task 6: Engine Integration — days_until_next_start + Team Blocks + Phase Emphasis

**Files:**
- Create: `pitcher_program_app/bot/services/team_programs.py`
- Modify: `pitcher_program_app/bot/services/plan_generator.py`
- Modify: `pitcher_program_app/bot/services/exercise_pool.py`

- [ ] **Step 1: Write team_programs.py**

```python
"""Team program resolution — resolves active team blocks for plan generation.

Called by plan_generator to determine if a team-assigned throwing block
should override the default rotation throwing template for a given pitcher/date.
"""

import logging
from datetime import date as _date

from bot.services.db import get_client, get_active_team_blocks

logger = logging.getLogger(__name__)


def resolve_team_block(pitcher_id: str, team_id: str, target_date: str) -> dict | None:
    """Return the active team block content for a pitcher on a given date.

    Returns None if no block covers this date, or the pitcher's team
    has no active blocks.

    Returns:
        {
            "block_id": "...",
            "template_id": "...",
            "day_in_block": 14,
            "week": 2,
            "day_of_week": 7,
            "content": { ...block_library.content... },
            "day_content": { ...single day from content.phases... }
        }
    """
    if not team_id:
        return None

    active = get_active_team_blocks(team_id)
    if not active:
        return None

    target = _date.fromisoformat(target_date)

    for block in active:
        if block.get("status") != "active":
            continue
        if block.get("block_type") != "throwing":
            continue

        start = _date.fromisoformat(block["start_date"])
        duration = block.get("duration_days", 0)
        end = start + __import__("datetime").timedelta(days=duration - 1)

        if start <= target <= end:
            day_in_block = (target - start).days + 1
            week = (day_in_block - 1) // 7 + 1
            day_of_week = (day_in_block - 1) % 7 + 1

            # Load full template content from block_library
            template_id = block["block_template_id"]
            lib_resp = (get_client().table("block_library")
                        .select("content")
                        .eq("block_template_id", template_id)
                        .limit(1)
                        .execute())
            content = lib_resp.data[0]["content"] if lib_resp.data else {}

            # Find the relevant phase for this week
            day_content = None
            phases = content.get("phases", [])
            for phase in phases:
                if week in phase.get("weeks", []):
                    day_content = phase
                    break

            # Check if today is a rest day
            rest_pattern = content.get("rest_days_pattern", [])
            is_rest = day_of_week in rest_pattern

            return {
                "block_id": block["block_id"],
                "template_id": template_id,
                "day_in_block": day_in_block,
                "week": week,
                "day_of_week": day_of_week,
                "content": content,
                "day_content": day_content,
                "is_rest_day": is_rest,
                "post_session_recovery": content.get("post_session_recovery", "medium"),
            }

    return None


def compute_days_until_next_start(pitcher_id: str, team_id: str, from_date: str) -> int | None:
    """Return the number of days until this pitcher's next assigned start.

    Returns None if no upcoming start is assigned.
    Returns 0 on game day.
    """
    from bot.services.team_scope import get_pitcher_next_start

    next_game = get_pitcher_next_start(pitcher_id, team_id, from_date)
    if not next_game:
        return None

    game_date = _date.fromisoformat(next_game["game_date"])
    today = _date.fromisoformat(from_date)
    delta = (game_date - today).days
    return max(0, delta)
```

- [ ] **Step 2: Hook into plan_generator.py**

In `plan_generator.py`, after the throwing template is selected (around line 116 where `today_template` is set), add the team block + days_until_next_start resolution:

```python
# After: today_template = rotation_template["days"].get(template_day, {})
# Add:

# --- Team block + forward-looking start resolution ---
from bot.services.team_programs import resolve_team_block, compute_days_until_next_start

team_id = pitcher_profile.get("team_id", "uchicago_baseball")
today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

# Check for team-assigned throwing block
team_block = resolve_team_block(pitcher_id, team_id, today_str)

# Check for upcoming start assignment
days_until_start = compute_days_until_next_start(pitcher_id, team_id, today_str)

# If pitcher has an assigned start coming up, override rotation_day
# to align with starter_7day template's game-day-relative indexing
if days_until_start is not None and days_until_start <= 7:
    effective_rotation_day = days_until_start
    template_day = f"day_{effective_rotation_day}"
    today_template = rotation_template["days"].get(template_day, today_template)
    logger.info(f"{pitcher_id}: days_until_start={days_until_start}, overriding to {template_day}")
```

Then, in `_build_throwing_plan()`, if a team block is active and it's not a rest day, use the block's day_content as the throwing baseline instead of the default template:

```python
# At the top of _build_throwing_plan, add team_block parameter:
def _build_throwing_plan(
    today_template: dict,
    rotation_day: int = None,
    role: str = "starter",
    throwing_adjustments: dict = None,
    throw_intent: str = "",
    team_block: dict = None,  # NEW
) -> dict:

# After loading day_types/rotation_map but before applying triage overrides:
if team_block and not team_block.get("is_rest_day"):
    phase = team_block.get("day_content") or {}
    return {
        "day_type": f"team_block_{team_block['template_id']}",
        "day_label": phase.get("name", "Team Program"),
        "week": team_block.get("week"),
        "day_of_week": team_block.get("day_of_week"),
        "intensity": f"{phase.get('effort_pct', 50)}% effort",
        "distances": phase.get("distances", []),
        "total_throws": phase.get("total_throws_range", [0, 0]),
        "intent_notes": phase.get("intent_notes", ""),
        "drills": phase.get("drills", []),
        "recovery": team_block.get("post_session_recovery", "medium"),
        "team_block_id": team_block.get("block_id"),
        "team_block_tag": f"Week {team_block['week']}, Day {team_block['day_of_week']}",
    }
```

Pass `team_block=team_block` when calling `_build_throwing_plan()` from the main `generate_plan()` function.

- [ ] **Step 3: Hook phase emphasis into exercise_pool.py**

In `build_exercise_pool()`, after `training_intent` is determined, check for a phase emphasis override:

```python
# After training_intent is set, add:
from bot.services.db import get_current_phase

team_id = pitcher_profile.get("team_id", "uchicago_baseball")
today_str = __import__("datetime").datetime.now(
    __import__("bot.config", fromlist=["CHICAGO_TZ"]).CHICAGO_TZ
).strftime("%Y-%m-%d")

current_phase = get_current_phase(team_id, today_str)
if current_phase and current_phase.get("emphasis"):
    phase_emphasis = current_phase["emphasis"]
    # Map phase emphasis to training_intent if not overridden by triage
    emphasis_to_intent = {
        "hypertrophy": "hypertrophy",
        "strength": "strength",
        "power": "power",
        "maintenance": "endurance",
        "gpp": "hypertrophy",
    }
    if training_intent != "endurance":  # triage override (red/yellow) always wins
        training_intent = emphasis_to_intent.get(phase_emphasis, training_intent)
```

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/team_programs.py pitcher_program_app/bot/services/plan_generator.py pitcher_program_app/bot/services/exercise_pool.py
git commit -m "feat: engine integration — days_until_next_start, team block resolution, phase emphasis"
```

---

### Task 7: Coach Insights Service

**Files:**
- Create: `pitcher_program_app/bot/services/coach_insights.py`

- [ ] **Step 1: Write coach_insights.py**

```python
"""Coach Insights Engine — generates structured suggestions for coaches.

v0 ships with one category: pre_start_nudge.
Runs on a schedule after morning check-ins complete.
"""

import logging
from datetime import datetime, date, timedelta

from bot.config import CHICAGO_TZ
from bot.services.db import (
    get_client, get_training_model, get_daily_entry,
    get_pending_suggestions, upsert_suggestion,
)
from bot.services.team_scope import list_team_pitchers, get_pitcher_next_start

logger = logging.getLogger(__name__)


def run_insights_for_team(team_id: str) -> list:
    """Generate all insight categories for a team. Returns list of new suggestions."""
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    new_suggestions = []

    # Category 1: Pre-start nudges
    new_suggestions.extend(_generate_pre_start_nudges(team_id, today_str))

    return new_suggestions


def _generate_pre_start_nudges(team_id: str, today_str: str) -> list:
    """Generate pre-start nudge suggestions for pitchers starting in the next 3 days.

    Checks if the pitcher's plan in the days leading up to the start
    looks heavier than typical pre-start ramp. If so, suggests lightening.
    """
    suggestions = []
    pitchers = list_team_pitchers(team_id)
    today = date.fromisoformat(today_str)

    # Expire old pre_start_nudge suggestions
    existing = get_pending_suggestions(team_id)
    for s in existing:
        if s.get("category") == "pre_start_nudge":
            if s.get("expires_at"):
                exp = datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00"))
                if exp < datetime.now(CHICAGO_TZ):
                    s["status"] = "expired"
                    upsert_suggestion(s)

    for pitcher in pitchers:
        pid = pitcher["pitcher_id"]
        role = pitcher.get("role", "")
        if "starter" not in role:
            continue

        next_start = get_pitcher_next_start(pid, team_id, today_str)
        if not next_start:
            continue

        game_date = date.fromisoformat(next_start["game_date"])
        days_until = (game_date - today).days

        # Only nudge for starts 1-3 days away
        if days_until < 1 or days_until > 3:
            continue

        # Check if there's already a pending nudge for this pitcher + game
        already_exists = any(
            s.get("pitcher_id") == pid
            and s.get("category") == "pre_start_nudge"
            and s.get("status") == "pending"
            for s in existing
        )
        if already_exists:
            continue

        # Check today's plan — is it heavier than expected for a pre-start day?
        entry = get_daily_entry(pid, today_str)
        if not entry:
            continue

        plan = entry.get("plan_generated") or {}
        lifting = plan.get("exercise_blocks") or entry.get("lifting", {}).get("exercises", [])

        # Simple heuristic: count total sets in today's lifting
        total_sets = 0
        if isinstance(lifting, list):
            for block in lifting:
                exercises = block.get("exercises", []) if isinstance(block, dict) else []
                for ex in exercises:
                    total_sets += ex.get("sets", 0) if isinstance(ex, dict) else 0

        # Pre-start day (1-2 days out) should be light: < 12 total sets
        # If heavier, suggest lightening
        if days_until <= 2 and total_sets > 12:
            model = get_training_model(pid)
            pitcher_name = pitcher.get("name", pid)
            opponent = next_start.get("opponent", "")

            suggestion = {
                "team_id": team_id,
                "pitcher_id": pid,
                "category": "pre_start_nudge",
                "title": f"Review {pitcher_name}'s lift before {game_date.strftime('%A')}'s start{' vs ' + opponent if opponent else ''}",
                "reasoning": (
                    f"{pitcher_name} starts {'tomorrow' if days_until == 1 else 'in 2 days'} "
                    f"but today's lift has {total_sets} total sets. "
                    f"Pre-start days typically have < 12 sets to preserve freshness. "
                    f"Consider reducing volume or swapping to lighter alternatives."
                ),
                "proposed_action": {
                    "type": "reduce_volume",
                    "description": f"Reduce today's lifting volume to pre-start level",
                },
                "status": "pending",
                "expires_at": (
                    datetime.combine(game_date, datetime.min.time())
                    .replace(tzinfo=CHICAGO_TZ)
                    .isoformat()
                ),
            }
            upsert_suggestion(suggestion)
            suggestions.append(suggestion)
            logger.info(f"Generated pre-start nudge for {pid} (starts {game_date})")

    return suggestions
```

- [ ] **Step 2: Add internal trigger endpoint to coach_routes.py**

```python
# At the bottom of coach_routes.py, add:

@coach_router.post("/internal/insights/run")
async def run_insights(request: Request):
    """Cron-triggered insight generation. Protected by shared secret."""
    auth_header = request.headers.get("X-Internal-Secret", "")
    expected = os.getenv("INTERNAL_API_SECRET", "")
    if not expected or auth_header != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from bot.services.coach_insights import run_insights_for_team
    # Run for all teams
    teams = _db.get_client().table("teams").select("team_id").execute().data or []
    total = 0
    for team in teams:
        new = run_insights_for_team(team["team_id"])
        total += len(new)

    return {"status": "ok", "new_suggestions": total}
```

Add `import os` at the top of coach_routes.py if not already present.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/services/coach_insights.py pitcher_program_app/api/coach_routes.py
git commit -m "feat: coach insights service — pre-start nudge generation + internal trigger endpoint"
```

---

### Task 8: Mini-App Team Block Tag

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

- [ ] **Step 1: Add team block tag to the throwing section**

In `DailyCard.jsx`, find the ThrowingBlock header area (around line 433 where the intensity/duration pills render). Add a team block tag:

```jsx
{/* Inside ThrowingBlock, in the pills/badges row */}
{throwing?.team_block_tag && (
  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
        style={{ backgroundColor: 'rgba(92, 16, 32, 0.1)', color: '#5c1020' }}>
    {throwing.team_block_tag}
  </span>
)}
```

The `team_block_tag` field (e.g., "Week 3, Day 2") is added by `_build_throwing_plan()` in Task 6 when a team block is active.

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/DailyCard.jsx
git commit -m "feat: add team block tag to DailyCard throwing section"
```

---

### Task 9: Coach App — Project Scaffold + Auth + Shell

**Files:**
- Create: `pitcher_program_app/coach-app/` (full project scaffold)

**Note:** Use `superpowers:frontend-design` skill for this task and all subsequent frontend tasks.

- [ ] **Step 1: Initialize the project**

```bash
cd pitcher_program_app
npm create vite@latest coach-app -- --template react
cd coach-app
npm install react-router-dom @supabase/supabase-js
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configure Vite**

Write `coach-app/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5174 },
})
```

- [ ] **Step 3: Configure Tailwind**

Write `coach-app/src/index.css`:

```css
@import "tailwindcss";

@theme {
  --color-cream: #f5f1eb;
  --color-cream-dark: #e4dfd8;
  --color-maroon: #5c1020;
  --color-maroon-light: #7a1a2e;
  --color-rose: #e8a0aa;
  --color-forest: #2d5a3d;
  --color-amber: #d4a017;
  --color-crimson: #c0392b;
  --color-charcoal: #2c2c2c;
  --color-subtle: #7a7a7a;
}
```

- [ ] **Step 4: Write auth hook — useCoachAuth.jsx**

```jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [coach, setCoach] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) exchangeToken(session.access_token)
      else setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) exchangeToken(session.access_token)
      else { setCoach(null); setLoading(false) }
    })

    return () => subscription.unsubscribe()
  }, [])

  async function exchangeToken(accessToken) {
    try {
      const res = await fetch(`${API_BASE}/api/coach/auth/exchange`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      })
      if (!res.ok) throw new Error(`Auth exchange failed: ${res.status}`)
      const data = await res.json()
      setCoach(data)
    } catch (err) {
      console.error('Auth exchange error:', err)
      setCoach(null)
    } finally {
      setLoading(false)
    }
  }

  async function login(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function logout() {
    await supabase.auth.signOut()
    setCoach(null)
    setSession(null)
  }

  function getAccessToken() {
    return session?.access_token || ''
  }

  return (
    <AuthContext.Provider value={{ coach, session, loading, login, logout, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useCoachAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useCoachAuth must be used within AuthProvider')
  return ctx
}
```

- [ ] **Step 5: Write API client — api.js**

```javascript
const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

export async function fetchCoachApi(path, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Authorization': `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.error?.message || body?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function postCoachApi(path, body, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function patchCoachApi(path, body, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function deleteCoachApi(path, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 6: Write useApi hook**

```jsx
import { useState, useEffect, useCallback } from 'react'
import { fetchCoachApi } from '../api'
import { useCoachAuth } from './useCoachAuth'

export function useCoachApi(path) {
  const { getAccessToken } = useCoachAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    setError(null)
    try {
      const result = await fetchCoachApi(path, getAccessToken())
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [path, getAccessToken])

  useEffect(() => { load() }, [load])

  return { data, loading, error, refetch: load }
}
```

- [ ] **Step 7: Write Shell layout + App router**

Write `coach-app/src/components/Shell.jsx`:

```jsx
import { NavLink, Outlet } from 'react-router-dom'
import { useCoachAuth } from '../hooks/useCoachAuth'

const NAV = [
  { to: '/', label: 'Team Overview' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/programs', label: 'Team Programs' },
  { to: '/phases', label: 'Phases' },
  { to: '/insights', label: 'Insights' },
]

export default function Shell() {
  const { coach, logout } = useCoachAuth()

  return (
    <div className="flex h-screen bg-cream">
      {/* Sidebar */}
      <aside className="w-52 bg-white border-r border-cream-dark flex flex-col">
        <div className="p-4 border-b border-cream-dark">
          <h1 className="text-sm font-bold text-maroon">{coach?.team_name || 'Dashboard'}</h1>
          <p className="text-xs text-subtle mt-0.5">{coach?.coach_name}</p>
        </div>
        <nav className="flex-1 py-2">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm ${isActive ? 'bg-cream text-maroon font-medium' : 'text-charcoal hover:bg-cream/50'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-cream-dark">
          <button onClick={logout} className="text-xs text-subtle hover:text-charcoal">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
```

Write `coach-app/src/App.jsx`:

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useCoachAuth } from './hooks/useCoachAuth'
import Shell from './components/Shell'
import Login from './pages/Login'
import TeamOverview from './pages/TeamOverview'
import Schedule from './pages/Schedule'
import TeamPrograms from './pages/TeamPrograms'
import Phases from './pages/Phases'
import Insights from './pages/Insights'

function ProtectedRoutes() {
  const { coach, loading } = useCoachAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream">
        <p className="text-subtle">Loading...</p>
      </div>
    )
  }

  if (!coach) return <Navigate to="/login" replace />

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<TeamOverview />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/programs" element={<TeamPrograms />} />
        <Route path="/phases" element={<Phases />} />
        <Route path="/insights" element={<Insights />} />
      </Routes>
    </Shell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<ProtectedRoutes />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

Write `coach-app/src/main.jsx`:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 8: Write Login page**

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCoachAuth } from '../hooks/useCoachAuth'

export default function Login() {
  const { login, coach } = useCoachAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Redirect if already logged in
  if (coach) { navigate('/', { replace: true }); return null }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-maroon flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-lg p-8 w-full max-w-sm">
        <h1 className="text-xl font-bold text-maroon text-center mb-6">Coach Dashboard</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-charcoal mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm focus:outline-none focus:ring-2 focus:ring-maroon/30"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-charcoal mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm focus:outline-none focus:ring-2 focus:ring-maroon/30"
              required
            />
          </div>
          {error && <p className="text-sm text-crimson">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-maroon text-white rounded font-medium text-sm hover:bg-maroon-light disabled:opacity-50"
          >
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="text-xs text-subtle text-center mt-4">
          <a href="#" className="underline">Forgot password?</a>
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 9: Write .env files**

Write `coach-app/.env`:

```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://beyolhukpbvvoxvjnwtd.supabase.co
VITE_SUPABASE_ANON_KEY=
```

Write `coach-app/.env.production`:

```
VITE_API_URL=https://baseball-production-9d28.up.railway.app
VITE_SUPABASE_URL=https://beyolhukpbvvoxvjnwtd.supabase.co
VITE_SUPABASE_ANON_KEY=
```

**Note:** Fill in the `VITE_SUPABASE_ANON_KEY` from the Supabase dashboard (Settings → API → anon/public key).

- [ ] **Step 10: Commit**

```bash
git add pitcher_program_app/coach-app/
git commit -m "feat: coach-app scaffold — auth, shell, login, API client, routing"
```

---

### Task 10: Team Overview Screen

**Files:**
- Create: `pitcher_program_app/coach-app/src/pages/TeamOverview.jsx`
- Create: `pitcher_program_app/coach-app/src/components/ComplianceRing.jsx`
- Create: `pitcher_program_app/coach-app/src/components/RosterTable.jsx`
- Create: `pitcher_program_app/coach-app/src/components/PlayerSlideOver.jsx`

Use `superpowers:frontend-design` skill for this task. This is the highest-priority screen — the demo opens here.

Implement the Team Overview per the design spec Section 5, Screen 1. Key elements:

- [ ] **Step 1: Build ComplianceRing component** — SVG circle, check-in count, color-coded
- [ ] **Step 2: Build RosterTable component** — dense table with columns: Player, Pos, Status, Last 7, Streak, Flags, Next Start. Sortable headers, filter chips.
- [ ] **Step 3: Build PlayerSlideOver component** — right-side slide-over (~60% width), tabs: Today, This Week, History, Flags. Renders over the roster.
- [ ] **Step 4: Build TeamOverview page** — left column (ComplianceRing, readiness summary, schedule card, active block card, insights badge) + main area (RosterTable). Click row opens PlayerSlideOver.
- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/coach-app/src/
git commit -m "feat: Team Overview screen — compliance ring, roster table, player slide-over"
```

---

### Task 11: Player Detail Tabs (Today, Week, History)

**Files:**
- Create: `pitcher_program_app/coach-app/src/components/PlayerToday.jsx`
- Create: `pitcher_program_app/coach-app/src/components/PlayerWeek.jsx`
- Create: `pitcher_program_app/coach-app/src/components/PlayerHistory.jsx`
- Create: `pitcher_program_app/coach-app/src/components/AdjustTodayModal.jsx`
- Create: `pitcher_program_app/coach-app/src/components/AddRestrictionModal.jsx`

Use `superpowers:frontend-design` skill. This is the second-highest priority — the demo drills into players here.

- [ ] **Step 1: Build PlayerToday** — today's full program rendered by section (warmup, arm care, lifting, throwing, post-throw). Check-in summary at top. Two action buttons: "Adjust Today" + "Add Restriction".
- [ ] **Step 2: Build AdjustTodayModal** — mutation builder: swap/remove/add/modify exercise. Calls `POST /api/coach/pitcher/{id}/adjust-today`.
- [ ] **Step 3: Build AddRestrictionModal** — form: restriction type, target (exercise/equipment/movement), reason, optional expiry. Calls `POST /api/coach/pitcher/{id}/restriction`.
- [ ] **Step 4: Build PlayerWeek** — 7-day strip (back 3, today, forward 3). Each day shows session type + completion status. Forward days highlight pre-start ramp.
- [ ] **Step 5: Build PlayerHistory** — 4-week compliance calendar, arm feel trend line, volume trend, recent modifications list.
- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/coach-app/src/components/
git commit -m "feat: player detail tabs — today's program, week strip, history, override modals"
```

---

### Task 12: Schedule Screen

**Files:**
- Create: `pitcher_program_app/coach-app/src/pages/Schedule.jsx`
- Create: `pitcher_program_app/coach-app/src/components/GamePanel.jsx`

Use `superpowers:frontend-design` skill.

- [ ] **Step 1: Build Schedule page** — month calendar view. Game days show opponent + starter initials. Click game → GamePanel side panel. Click empty day → add game form. Month navigation.
- [ ] **Step 2: Build GamePanel** — game detail + starter dropdown. Dropdown lists eligible pitchers (starters first, then relievers). Assignment calls `PATCH /api/coach/schedule/game/{id}`. Toast on success.
- [ ] **Step 3: Add "Upcoming starts this week" strip below calendar** — shows which pitchers have assignments this week.
- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/coach-app/src/pages/Schedule.jsx pitcher_program_app/coach-app/src/components/GamePanel.jsx
git commit -m "feat: Schedule screen — month calendar, game panel, starter assignment"
```

---

### Task 13: Team Programs Screen

**Files:**
- Create: `pitcher_program_app/coach-app/src/pages/TeamPrograms.jsx`
- Create: `pitcher_program_app/coach-app/src/components/BlockCard.jsx`

Use `superpowers:frontend-design` skill.

- [ ] **Step 1: Build BlockCard** — block name, duration, description, "Preview" and "Assign" buttons. Preview opens a slide-over with week-by-week phase breakdown from block_library.content.
- [ ] **Step 2: Build TeamPrograms page** — top: active programs (cards with compliance summary). Bottom: block library grid. Assign flow: click → preview → "Assign to team" → start date modal → confirm. Calls `POST /api/coach/team-programs/assign`.
- [ ] **Step 3: Add compliance drill-down view** — when coach clicks "View compliance" on an active block, shows per-pitcher status (full/modified/skipped) with reasons. Calls `GET /api/coach/team-programs/{block_id}/compliance`.
- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/coach-app/src/pages/TeamPrograms.jsx pitcher_program_app/coach-app/src/components/BlockCard.jsx
git commit -m "feat: Team Programs screen — block library, assign flow, compliance view"
```

---

### Task 14: Phases Screen

**Files:**
- Create: `pitcher_program_app/coach-app/src/pages/Phases.jsx`
- Create: `pitcher_program_app/coach-app/src/components/PhaseTimeline.jsx`

Use `superpowers:frontend-design` skill. This is the lowest-priority screen — if it doesn't ship, phases are hand-seeded and the engine reads them without a UI.

- [ ] **Step 1: Build PhaseTimeline** — horizontal timeline of colored blocks. Each block: phase name, date range, emphasis tag. Current phase highlighted. Click → edit form.
- [ ] **Step 2: Build Phases page** — PhaseTimeline + "Add phase" button. Edit form: name, start/end date pickers, emphasis dropdown, notes. CRUD calls to `/api/coach/phases/*`.
- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/coach-app/src/pages/Phases.jsx pitcher_program_app/coach-app/src/components/PhaseTimeline.jsx
git commit -m "feat: Phases screen — off-season phase timeline with CRUD"
```

---

### Task 15: Insights Screen

**Files:**
- Create: `pitcher_program_app/coach-app/src/pages/Insights.jsx`
- Create: `pitcher_program_app/coach-app/src/components/InsightCard.jsx`

Use `superpowers:frontend-design` skill.

- [ ] **Step 1: Build InsightCard** — pitcher name, category tag, title, reasoning, proposed action description, Accept/Dismiss buttons. Accept calls `POST /api/coach/insights/{id}/accept`. Dismiss calls `POST /api/coach/insights/{id}/dismiss`.
- [ ] **Step 2: Build Insights page** — list of InsightCards. Empty state: "No pending suggestions." Filtered to pending by default.
- [ ] **Step 3: Add pending count badge to sidebar nav** — Shell.jsx reads insights count from TeamOverview data (or a lightweight polling endpoint).
- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/coach-app/src/pages/Insights.jsx pitcher_program_app/coach-app/src/components/InsightCard.jsx pitcher_program_app/coach-app/src/components/Shell.jsx
git commit -m "feat: Insights screen — suggestion cards with accept/dismiss + sidebar badge"
```

---

### Task 16: Toast Component + Polish

**Files:**
- Create: `pitcher_program_app/coach-app/src/components/Toast.jsx`
- Modify: various pages to wire in toast notifications

- [ ] **Step 1: Build Toast component** — bottom-right positioned, auto-dismiss after 3.5s, success/error variants. Context-based (ToastProvider pattern matching mini-app's useToast).
- [ ] **Step 2: Wire toasts into all mutation actions** — assign starter, adjust today, add restriction, assign block, accept insight, dismiss insight. Success → green toast. Error → red toast with message.
- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/coach-app/src/
git commit -m "feat: toast notifications for all coach actions"
```

---

### Task 17: Block Compliance Endpoint

**Files:**
- Modify: `pitcher_program_app/api/coach_routes.py`

- [ ] **Step 1: Add compliance endpoint**

```python
@coach_router.get("/team-programs/{block_id}/compliance")
async def block_compliance(block_id: str, request: Request):
    """Per-pitcher compliance for an active team block."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    # Verify block belongs to team
    active = _db.get_active_team_blocks(team_id)
    block = next((b for b in active if b["block_id"] == block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    pitchers = list_team_pitchers(team_id)
    today_entries = (
        _db.get_client().table("daily_entries")
        .select("pitcher_id, active_team_block_id, completed_exercises, plan_generated, throwing")
        .eq("team_id", team_id)
        .eq("date", today_str)
        .execute()
    ).data or []
    entry_map = {e["pitcher_id"]: e for e in today_entries}

    compliance = []
    for p in pitchers:
        pid = p["pitcher_id"]
        entry = entry_map.get(pid)
        status = "skipped"
        modification_reason = None

        if entry:
            throwing = entry.get("throwing") or (entry.get("plan_generated") or {}).get("throwing_plan") or {}
            if throwing.get("team_block_id") == block_id:
                status = "full"
            elif entry.get("active_team_block_id") == block_id:
                status = "modified"
                # Check for triage modifications
                mods = (entry.get("plan_generated") or {}).get("modifications_applied") or []
                if mods:
                    modification_reason = "; ".join(str(m) for m in mods[:3])

        compliance.append({
            "pitcher_id": pid,
            "name": p.get("name", ""),
            "status": status,
            "modification_reason": modification_reason,
        })

    full = sum(1 for c in compliance if c["status"] == "full")
    modified = sum(1 for c in compliance if c["status"] == "modified")
    skipped = sum(1 for c in compliance if c["status"] == "skipped")

    return {
        "block": block,
        "today": {
            "prescribed": len(pitchers),
            "full": full,
            "modified": modified,
            "skipped": skipped,
            "details": compliance,
        },
    }
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/api/coach_routes.py
git commit -m "feat: add block compliance endpoint for team programs"
```

---

### Task 18: Vercel Deployment Config

**Files:**
- Create: `pitcher_program_app/coach-app/vercel.json`

- [ ] **Step 1: Write vercel.json**

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

This ensures client-side routing works on Vercel (all paths resolve to the SPA entry point).

- [ ] **Step 2: Create Vercel project**

Via Vercel dashboard or CLI:
- Root directory: `pitcher_program_app/coach-app`
- Framework: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Environment variables: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

- [ ] **Step 3: Add COACH_APP_URL to Railway env vars**

In Railway dashboard, add `COACH_APP_URL` pointing to the Vercel deployment URL. This gets picked up by `api/main.py` for CORS.

- [ ] **Step 4: Add SUPABASE_JWT_SECRET to Railway env vars**

In Railway dashboard, add `SUPABASE_JWT_SECRET` from Supabase dashboard (Settings → API → JWT Secret).

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/coach-app/vercel.json
git commit -m "feat: add Vercel deployment config for coach-app"
```

---

### Task 19: End-to-End Verification

No new files. Verification against the 24 exit criteria from the design spec.

- [ ] **Step 1: Apply migration to production Supabase**
- [ ] **Step 2: Run seed scripts against production**
- [ ] **Step 3: Deploy coach-app to Vercel**
- [ ] **Step 4: Deploy updated backend to Railway (push to main)**
- [ ] **Step 5: Verify all 24 exit criteria** (see design spec Section 7)
- [ ] **Step 6: Run dry-run of 10-minute demo script end-to-end**
- [ ] **Step 7: Fix any issues found, re-verify**

---

## Task Dependency Graph

```
Task 1 (Migration)
  |
  v
Task 2 (Seeds) -----> Task 3 (team_scope + DB functions)
                           |
                           v
                      Task 4 (Coach Auth)
                           |
                           v
                      Task 5 (Coach Routes) -----> Task 17 (Block Compliance)
                           |
                      Task 6 (Engine Integration)
                           |
                      Task 7 (Insights Service)
                           |
                      Task 8 (Mini-App Tag)
                           |
                           v
                      Task 9 (Coach App Scaffold)
                           |
              +------------+-------------+
              |            |             |
              v            v             v
         Task 10      Task 12       Task 13
       (Overview)    (Schedule)   (Programs)
              |
              v
         Task 11          Task 14      Task 15
       (Player Tabs)     (Phases)    (Insights)
              |
              v
         Task 16 (Toast + Polish)
              |
              v
         Task 18 (Vercel Deploy)
              |
              v
         Task 19 (E2E Verification)
```

Tasks 10-15 (frontend screens) can be parallelized across subagents after Task 9 completes.
