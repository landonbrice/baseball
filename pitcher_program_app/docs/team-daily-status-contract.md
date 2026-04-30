# Team Daily Status Contract

## Purpose

Create one shared backend contract for a team's daily pitcher status so the mini app and coach app read the same truth.

This is a handoff/spec for the next implementation session. The immediate goal is to scaffold and adopt a `team_daily_status` service that owns:

- check-in status
- plan generation status
- workout/exercise completion status
- team/date scoping
- shared roster daily summary data used by both staff pulse and coach overview

The product goal is simple: when a player checks in through the mini app, Coach Bryce should see that same check-in state in the coach app without relying on a separate interpretation of the data.

## Current Problem

The ecosystem currently has multiple definitions for the same real-world events.

- Mini app staff pulse treats a pitcher as checked in when today's `daily_entries.pre_training.arm_feel` exists.
- Coach app team overview previously treated a pitcher as checked in only when today's `daily_entries.plan_generated` exists.
- Coach app seven-day strip previously used `completed_exercises` as the signal for checked-in history.
- Coach overview filters `daily_entries` by `team_id`, while the check-in write path did not guarantee `team_id` was populated on new rows.
- Mini app player-specific reads use `pitcher_id`, so players could see check-ins while coach-scoped reads missed the same rows.

Recent hotfix work addressed the immediate bug:

- `bot/services/db.py::upsert_daily_entry()` now inherits `team_id` from the pitcher row when missing.
- `bot/services/team_scope.py` now has `_has_checkin()` based on `pre_training.arm_feel`.
- `scripts/migrations/009_daily_entries_team_id_sync.sql` backfills `daily_entries.team_id` and adds a DB trigger.

This spec is for the next cleanup: move those conventions into one explicit team daily status service instead of letting each endpoint keep its own version.

## Canonical Definitions

These meanings should be owned by backend service code, not duplicated in frontend components or individual route handlers.

### Check-In Status

A pitcher has checked in for a date when the daily entry has a submitted arm feel:

```py
daily_entry.pre_training.arm_feel is not None
```

Compatibility fallback:

```py
daily_entry.arm_feel is not None
```

Statuses:

- `checked_in`: check-in input exists.
- `not_yet`: no check-in input exists for the date.

Do not use `plan_generated` to determine check-in status.

### Plan Status

Plan status describes whether the system produced today's training prescription.

Statuses:

- `generated`: `plan_generated` exists.
- `pending`: check-in exists, but `plan_generated` does not.
- `not_applicable`: no check-in exists yet.

This lets the coach app distinguish "player has checked in, plan is still missing" from "player has not checked in."

### Work Status

Work status describes whether the player has logged execution/completion.

Possible first-pass statuses:

- `not_started`: no completed exercises.
- `in_progress`: some completed exercises.
- `completed`: all known planned exercises completed, if the planned count can be calculated confidently.
- `unknown`: plan shape is not sufficient to calculate completion.

Important: work status is not check-in status.

### Date Convention

All team daily status queries should use Chicago local date unless a date is explicitly provided.

Use:

```py
datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
```

Avoid:

```py
date.today().isoformat()
```

The existing `/api/staff/pulse` endpoint currently uses server-local `date.today()`. This should be corrected during the service migration.

### Team Scoping

All coach/team reads must be scoped by `team_id`.

Daily entries used by team endpoints must have `team_id`. The code and DB should both protect this:

- App layer: `upsert_daily_entry()` should populate `team_id` if omitted.
- DB layer: `daily_entries_set_team_id` trigger should populate `team_id` from `pitchers`.
- Migration: backfill existing null/empty `daily_entries.team_id`.

## Proposed Service

Create:

```txt
bot/services/team_daily_status.py
```

Suggested public API:

```py
def get_team_daily_status(team_id: str, today_str: str | None = None) -> dict:
    ...
```

Suggested helper API:

```py
def has_checkin(entry: dict | None) -> bool:
    ...

def derive_checkin_status(entry: dict | None) -> str:
    ...

def derive_plan_status(entry: dict | None) -> str:
    ...

def derive_work_status(entry: dict | None) -> str:
    ...
```

The service should perform the core data joins currently spread across:

- `bot/services/team_scope.py`
- `api/routes.py::staff_pulse`
- `api/coach_routes.py::team_overview`

It should return a backend-owned model that both endpoint surfaces can adapt.

## Suggested Return Shape

First pass:

```py
{
    "team_id": "uchicago_baseball",
    "date": "2026-04-30",
    "summary": {
        "total": 12,
        "checked_in": 8,
        "not_yet": 4,
        "plans_generated": 7,
        "plans_pending": 1,
    },
    "pitchers": [
        {
            "pitcher_id": "pitcher_example_001",
            "name": "Example Pitcher",
            "first_name": "Example",
            "role": "Starter (7-day)",
            "team_id": "uchicago_baseball",
            "checkin_status": "checked_in",
            "plan_status": "generated",
            "work_status": "not_started",
            "checked_in": True,
            "today_entry": {
                "date": "2026-04-30",
                "pre_training": {...},
                "plan_generated": {...},
                "completed_exercises": {...},
                "lifting": {...},
                "throwing": {...},
                "warmup": {...},
                "plan_narrative": "...",
            },
            "flag_level": "green",
            "rotation_info": "Day 3",
            "last_7_days": [
                {"date": "2026-04-24", "checkin_status": "checked_in", "work_status": "completed"}
            ],
            "af_7d": 7.8,
            "next_scheduled_start": "2026-05-02",
            "today": {
                "day_focus": "lift",
                "lifting_summary": "Upper push",
                "bullpen": None,
                "throwing": None,
                "modifications": [],
            },
        }
    ],
}
```

Compatibility note: routes do not have to expose this exact full shape immediately. The service can return this richer shape, while each route adapts it to its existing frontend contract.

## Endpoint Migration Plan

### Phase 1: Backend Service Behind Existing Contracts

Keep frontend payloads stable.

Refactor:

- `GET /api/coach/team/overview`
- `GET /api/staff/pulse`

Both should call `get_team_daily_status(...)`.

`/api/coach/team/overview` should adapt service output back into:

- `team`
- `compliance`
- `roster`
- `active_blocks`
- `insights_summary`

`/api/staff/pulse` should adapt service output back into:

- `checked_in_count`
- `total_pitchers`
- `pitchers[]`

This phase should not require major React changes.

### Phase 2: Make Staff Pulse Team-Aware

Current staff pulse is public and unscoped:

```txt
GET /api/staff/pulse
```

Options:

- Keep it public but default to `uchicago_baseball`.
- Add `team_id` query param with a safe default.
- Prefer a protected/team-scoped endpoint if staff pulse starts showing more sensitive detail.

For now, the simplest path is probably:

```txt
GET /api/staff/pulse?team_id=uchicago_baseball
```

with default fallback to the current team.

### Phase 3: Frontend Naming Cleanup

Once both endpoints share backend truth, update frontend names to stop overloading "checked in."

Coach app should eventually render from:

- `checkin_status`
- `plan_status`
- `work_status`

Mini app `StaffPulse` can keep its compact display, but the data should still originate from the same service.

## Dependency Map

Primary backend files:

- `api/routes.py`
  - `staff_pulse`
  - mini app chat/check-in route
- `api/coach_routes.py`
  - `team_overview`
  - coach player detail routes
- `bot/services/checkin_service.py`
  - writes partial and full daily entries
- `bot/services/context_manager.py`
  - `append_log_entry()`
  - `load_log()`
- `bot/services/db.py`
  - `upsert_daily_entry()`
  - daily entry reads
  - pitcher/team reads
- `bot/services/team_scope.py`
  - current coach overview roster aggregation
- `bot/services/team_daily_status.py`
  - proposed shared service

Primary frontend files:

- `mini-app/src/pages/Home.jsx`
  - fetches staff pulse
- `mini-app/src/components/StaffPulse.jsx`
  - renders who has checked in
- `mini-app/src/pages/Coach.jsx`
  - submits check-in through `/api/pitcher/{id}/chat`
- `mini-app/src/api.js`
  - `sendChat()`
  - `fetchStaffPulse()`
- `coach-app/src/pages/TeamOverview.jsx`
  - fetches `/api/coach/team/overview`
  - partitions roster into attention/pending/on-track
- `coach-app/src/components/team-overview/*`
  - renders daily team status

Database tables:

- `pitchers`
- `daily_entries`
- `pitcher_training_model`
- `team_games`
- `injury_history`
- `teams`

## Implementation Checklist

1. Create `bot/services/team_daily_status.py`.
2. Move `has_checkin()` semantics out of `team_scope.py` into the new service.
3. Add plan/work status helpers.
4. Implement `get_team_daily_status(team_id, today_str=None)`.
5. Refactor `api/routes.py::staff_pulse` to call the service.
6. Refactor `api/coach_routes.py::team_overview` or `team_scope.py` to call the service.
7. Preserve existing route response shapes initially.
8. Add contract tests that prove staff pulse and coach overview agree.
9. Run focused backend tests.
10. Later: update frontend payload naming and UI semantics.

## Required Tests

Add or extend tests for these cases:

- A daily entry with `pre_training.arm_feel` and `plan_generated = None` counts as checked in.
- The same row produces `plan_status = pending`.
- A daily entry with completed exercises does not affect check-in status unless `pre_training.arm_feel` exists.
- `/api/staff/pulse` and `/api/coach/team/overview` agree on checked-in counts for the same team/date.
- Service uses Chicago date when no date is passed.
- Rows missing `team_id` are not silently invisible after migration/app-layer population.
- Multi-team data does not leak across `team_id`.

Existing related tests:

- `tests/test_team_scope_overview.py`
- `tests/test_db_daily_entries.py`
- `tests/test_checkin_service_phase1.py`
- `tests/test_checkin_energy_threading.py`

## Open Questions

- Should `/api/staff/pulse` remain public, or should it become team-authenticated as the data gets richer?
- Should `work_status = completed` require all planned exercises, or is "some completion" enough for the first coach dashboard version?
- Should coach overview expose both "checked in" and "plan pending" visually, instead of treating plan-pending as on-track?
- Should player detail routes also consume `team_daily_status`, or remain direct daily-entry reads for now?

## Recommended Next Session Prompt

Use this prompt to continue implementation:

```txt
Read pitcher_program_app/docs/team-daily-status-contract.md. Implement Phase 1: create bot/services/team_daily_status.py, move canonical check-in/plan/work status helpers there, and refactor /api/staff/pulse and /api/coach/team/overview to use the service while preserving current frontend response shapes. Add contract tests proving staff pulse and coach overview agree for the same team/date, including a check-in row with pre_training.arm_feel but no plan_generated.
```
