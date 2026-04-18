# Coach Dashboard Redesign — Spec 3: Secondary Pages + Nudge Backend

> Status: Design-approved 2026-04-18
> Phasing: Spec 3 of 3. Depends on Spec 1 (Brand System & Shell). May proceed in parallel with Spec 2 (Team Overview) after Spec 1 lands.

## Context

With Team Overview redesigned in Spec 2, the remaining four coach-app pages (Schedule, Team Programs, Phases, Insights) need the same editorial treatment — tailored scoreboards, serif mastheads, and page-specific layouts that match their primary job-to-be-done. Spec 3 also ships the real Nudge endpoint that backs the "Nudge →" button introduced in Spec 2's Pending strip.

Programs and Phases additionally get authoring UIs (Create New Program, editable phase blocks) that are **render-only in v1** — the backend wiring follows in a future sprint, but the user interface is designed, built, and visible now.

## Goals

- All 5 coach-app pages share the same visual language and shell.
- Each secondary page has its own 5-cell scoreboard tuned to its context.
- Nudge button on Team Overview and anywhere else becomes functional: real Telegram DM via the bot.
- Programs page supports creating a new program (UI stubbed to backend).
- Phases page supports editing existing phases and adding new ones (UI stubbed to backend).

## Non-goals

- Backend implementation of "Create New Program" save (UI-only in v1).
- Backend implementation of phase editing save (UI-only in v1).
- Bulk actions (nudge all pending, advance all phases, etc.)
- Role-based filtering of scoreboard content.

## Schedule page

### Scoreboard
| # | Label | Value | Sub | Source |
|---|---|---|---|---|
| 1 | Next Start | weekday | `{pitcher} · vs {opponent}` | `team_games` earliest future |
| 2 | Next Game | date | `{opponent} · {home/away}` | `team_games` next |
| 3 | Week BPs | count | `{starter_bps} starter · {reliever_bps} reliever` | derived from `daily_entries` this week where `day_focus=bullpen` |
| 4 | Week Throws | count | `{target} target · {percent}%` | derived from completed throwing blocks |
| 5 | 14-day slate | `{games}g` | `{home}h · {away}a · {rest}r` | `team_games` next 14 days |

### Layout
1. Masthead with actionSlot empty.
2. Scoreboard.
3. **Week strip** — 7-day horizontal row. Each day cell: weekday kicker, date, compliance dot-strip (one dot per pitcher, color-coded flag), day label ("BP day" / "Game vs X" / "Rest"). Today is highlighted with 2px maroon bottom-border.
4. **Upcoming games list** — vertical stack of game cards. Each card: opponent (serif h2), date/time, home/away pill, starter assignment (serif name + photo-avatar placeholder), bullpen schedule adjacent.
5. Click a game card → `GamePanel.jsx` restyled as a right-edge slide-over (same pattern as PlayerSlideOver).

### Data
- `GET /api/coach/schedule` (existing endpoint; verify response shape matches Week strip + games list needs. If not, extend.)

## Team Programs page

### Scoreboard
| # | Label | Value | Sub | Source |
|---|---|---|---|---|
| 1 | Active Blocks | count | `{starter_blocks} starter · {reliever_blocks} reliever` | `team_assigned_blocks` where active |
| 2 | Avg Completion | `{pct}%` | `across {n} pitchers` | derived from per-pitcher compliance on block exercises |
| 3 | Weeks Remaining | `{weeks}w` | `ends {date}` | min end_date across active blocks |
| 4 | Pitchers Enrolled | `{n}/{total}` | `{unassigned} unassigned` | distinct pitcher_id in active blocks |
| 5 | Next Milestone | `{event}` | `{date} · {block_name}` | derived from block structure (e.g., "Transition to high-intent phase") |

### Masthead actionSlot
Primary CTA button: **`+ New Program`**, maroon fill, Inter 600 13px, 3px radius, Inter white text. Click → opens "Create New Program" slide-over (spec below).

### Layout
1. Masthead + scoreboard.
2. **Active programs grid** — 2-column grid of `<BlockCard>` (existing component, restyled).
3. **Library section** — below the active grid, kicker header "Library", compact grid of available blocks from `block_library` that aren't currently assigned. Click → preview + assign action.

### `<BlockCard>` restyle
- Background: `--color-bone`. 1px border `--color-cream-dark`. 3px radius. 14px padding.
- Header: block name (Source Serif 700 17px) + phase tag (Inter 9px caps maroon) right-aligned.
- Progress bar: `--color-cream-dark` track, `--color-maroon` fill, 3px height.
- Below: `{weeks_elapsed}w elapsed · {weeks_remaining}w remaining` meta.
- Enrolled pitchers: horizontal row of chips with initials (Source Serif 600 10px on `--color-parchment`).
- Foot: "View details" button → right-edge slide-over with full block structure and per-pitcher completion.

### Create New Program slide-over (UI-only)
Right-edge slide-over, 560px wide (wider than PlayerSlideOver). Header: serif title "New Program", close button.

Form fields (top to bottom):
1. **Program name** — text input, required.
2. **Base block** — dropdown of `block_library` entries. Shows block name + duration + phase.
3. **Start date** — date picker, default today.
4. **Duration (weeks)** — number input, defaults from base block but overridable.
5. **Target pitchers** — multi-select chip list. Shows all roster pitchers as unselected chips; click to add. Selected chips show forest check mark.
6. **Notes** — textarea, optional.

Below the form: **Weekly structure preview** panel. Once a base block is chosen, renders a read-only weekly view — each day of week 1 shows the block's prescription. Serif block-name header, Inter meta. Scrollable.

Footer (sticky): `Cancel` (text-only button) + `Create Program` (maroon fill button).

Submit behavior:
- `console.log({ name, baseBlockId, startDate, durationWeeks, pitcherIds, notes })` + toast "Program created (preview mode — backend pending)".
- Slide-over closes.
- Calls stub `createTeamProgram(payload)` in `coach-app/src/api.js` that currently returns `Promise.resolve({ status: 'stub' })`. Real endpoint follows in future sprint.

### Data
- `GET /api/coach/programs` (existing). Extend to include `avg_completion`, `next_milestone` derived fields.

## Phases page

### Scoreboard
| # | Label | Value | Sub | Source |
|---|---|---|---|---|
| 1 | Current Phase | name | `started {date}` | `training_phase_blocks` where today in range |
| 2 | Week X / Y | `{week}/{total}` | `of current phase` | derived |
| 3 | Days to Next | `{days}d` | `{next_phase_name}` | derived |
| 4 | Target Load | `{throws}` | throws/week | `training_phase_blocks.target_weekly_load` |
| 5 | Deviation | `{pct}%` | `vs target` | actual throws / target, 7-day rolling |

### Masthead actionSlot
**`+ Add Phase`** button. Same styling as New Program. Click → opens phase editor slide-over with empty fields.

### Layout
1. Masthead + scoreboard.
2. **Phase timeline** (`PhaseTimeline.jsx`, restyled) — full-width horizontal timeline. 5 phase blocks laid out by date range. Current phase highlighted with maroon underline + bold serif name. Hover any phase → edit affordance appears (pencil icon). Click → opens phase editor slide-over pre-filled.
3. **Current phase detail** section: kicker "Current Phase" + serif h1 name + italic lede describing phase intent, followed by 3-stat readout (duration / emphasis / markers) and a "Key workouts" list.
4. **Upcoming phase preview** section: kicker "Next Up" + compact card for the next phase.

### Phase editor slide-over (UI-only)
Same slide-over shell as Create New Program. Header: serif title (either "New Phase" or "Edit Phase — {name}").

Form fields:
1. **Phase name** — text input.
2. **Start date** / **End date** — paired date pickers.
3. **Target weekly load** — number input (throws/week).
4. **Training emphasis** — multi-select chip list (pre-defined tags: "strength", "power", "velocity", "longtoss", "recovery", etc.).
5. **Notes** — textarea.

Footer: `Cancel` + `Save Phase` (maroon fill).

Additional action on edit-mode: **"Advance to Next Phase"** button (when this phase is current). Inline action, below the form. Click → confirmation modal "End {current} and start {next}? This shifts all phase blocks forward." → `console.log({ action: 'advance_phase' })` + toast "Phases updated (preview mode)".

Submit behavior:
- `console.log({ phaseId, ...payload })` + toast "Phase updated (preview mode — backend pending)".
- Stub functions: `updatePhase(payload)` / `createPhase(payload)` / `advancePhase()` in `coach-app/src/api.js`.

### Data
- `GET /api/coach/phases` (existing if exists; otherwise new). Returns `training_phase_blocks` rows scoped to team.

## Insights page

### Scoreboard
| # | Label | Value | Sub | Source |
|---|---|---|---|---|
| 1 | Pending | count | `{oldest_days}d oldest` | `coach_suggestions` where status=pending |
| 2 | Accepted 7d | count | `{pct}% acceptance` | last 7 days |
| 3 | Dismissed 7d | count | `{pct}% dismissed` | last 7 days |
| 4 | Acceptance Rate | `{pct}%` | `rolling 30d` | 30-day average |
| 5 | Oldest Pending | date | `{suggestion_type}` | oldest pending suggestion |

### Layout
1. Masthead + scoreboard.
2. **Pending section** — kicker header "Pending · {n}". Hero cards for each pending suggestion.
3. **Recent Actions section** — kicker "Recent · last 7 days". Compact cards for accepted/dismissed in the past week.

### `<InsightCard>` restyle (hero variant for pending)
- 4px left border, color-coded by `suggestion_type`:
  - `pre_start_nudge` → `--color-amber`
  - `trend_warning` → `--color-crimson`
  - `suggestion` (general) → `--color-maroon`
- Header: target pitcher chip (Source Serif 600 on `--color-parchment`, 2px radius) + suggestion type label (Inter 9px caps).
- Title: suggestion headline (Source Serif 700 17px).
- Body: suggestion text as a `<Lede>` (italic serif with maroon left border).
- Foot: actions — `Accept` (forest fill button), `Dismiss` (text-only), `Defer 1 day` (text-only).

### `<InsightCard>` restyle (compact variant for recent)
- 3px left border (forest for accepted, muted gray for dismissed).
- Single-line summary: pitcher · suggestion type · action · timestamp.

### Data
- `GET /api/coach/insights` (existing). Extend response with per-type counts + acceptance rate.

## Nudge backend

### Endpoint
`POST /api/coach/pitcher/{pitcher_id}/nudge`
- In `api/coach_routes.py`.
- Auth: `require_coach_auth` dependency (existing). After auth, validate `pitcher_id` belongs to `coach.team_id` — reject with 403 otherwise.
- Request body: none in v1. (Future: `{ message?: string }` for custom copy.)
- Idempotency / rate limit: query `coach_actions` for last nudge to this `pitcher_id`. If `created_at > now - 2 hours`, return 429 with `{sent: false, reason: "rate_limited", retry_after_seconds}`.

### Bot DM action
- Import bot instance from a new module: `bot/services/coach_actions.py::send_nudge(pitcher_id, coach_name)`.
- This module wraps a Telegram `bot.send_message` call.
- Message copy: `"Hey {first_name}, {coach_name} wants a quick check-in — hit /checkin when you get a sec."`
- Uses the existing bot application from `bot.main`. API process imports it via the same pattern used elsewhere in `api/routes.py`.
- Captures `telegram_message_id` from bot's response for audit.

### Audit table
New Supabase migration: `coach_actions`
```sql
create table coach_actions (
  id bigserial primary key,
  coach_id uuid references coaches(supabase_user_id),
  pitcher_id text references pitchers(pitcher_id),
  action_type text not null,
  message_text text,
  telegram_message_id bigint,
  metadata jsonb,
  created_at timestamptz default now()
);
create index coach_actions_pitcher_type_time_idx
  on coach_actions(pitcher_id, action_type, created_at desc);
```

### Response shapes
- Success: `200 { sent: true, sent_at: ISO8601, telegram_message_id: 123 }`
- Rate limited: `429 { sent: false, reason: "rate_limited", retry_after_seconds: N }`
- Team-scope violation: `403 { sent: false, reason: "not_your_pitcher" }`
- Telegram error: `502 { sent: false, reason: "telegram_error", error_code: "..." }`
- Pitcher not found: `404 { sent: false, reason: "pitcher_not_found" }`

### Frontend wiring
- Pending strip in Team Overview (from Spec 2) hooks up: on click, optimistic toast "Nudging {name}...", then success toast (forest, 3s TTL) "Nudge sent · 9:42am" OR error toast (crimson) "Couldn't reach {name}. Try again?" with retry affordance.
- Button disabled state: after successful send, button is disabled for 2 hours per-pitcher (tracked in local state + re-checked on page refresh via server).
- `POST` call lives in `coach-app/src/api.js::nudgePitcher(pitcherId)`.

## Component inventory

New / modified under `coach-app/src/components/`:

- `schedule/`
  - `WeekStrip.jsx` — 7-day horizontal strip with per-pitcher dots
  - `GameCard.jsx` — vertical game-list card
  - `GamePanel.jsx` — restyled as slide-over
- `programs/`
  - `BlockCard.jsx` — restyled
  - `LibraryCard.jsx` — compact block-library card
  - `CreateProgramSlideOver.jsx` — new
  - `WeeklyStructurePreview.jsx` — new, used inside CreateProgramSlideOver
- `phases/`
  - `PhaseTimeline.jsx` — restyled with hover edit affordance
  - `PhaseEditorSlideOver.jsx` — new
  - `PhaseDetailSection.jsx` — new, current-phase detail block
- `insights/`
  - `InsightCard.jsx` — restyled with hero + compact variants
  - `InsightActions.jsx` — Accept / Dismiss / Defer buttons

New stub functions in `coach-app/src/api.js`:
- `createTeamProgram(payload)` → `Promise.resolve({ status: 'stub', payload })`
- `updatePhase(payload)` → `Promise.resolve({ status: 'stub', payload })`
- `createPhase(payload)` → `Promise.resolve({ status: 'stub', payload })`
- `advancePhase()` → `Promise.resolve({ status: 'stub' })`
- `nudgePitcher(pitcherId)` → real `POST /api/coach/pitcher/{id}/nudge`

## Testing

### Backend
- Unit test `coach_actions` insert + rate-limit query logic.
- Unit test team-scope auth rejection (403 when pitcher belongs to another team).
- Integration test the endpoint with a mocked bot instance — assert message copy, audit row insertion, 429 on second call within 2h.

### Frontend
- Component tests for each secondary page's scoreboard (props → rendered cells).
- Component tests for `CreateProgramSlideOver` — form validation, submit fires stub + toast + closes.
- Component tests for `PhaseEditorSlideOver` — new vs. edit mode, Advance-to-Next modal flow.
- Component test for `InsightCard` — all three suggestion types render correct border color + actions.
- Integration test for Nudge flow on Team Overview: click → optimistic toast → API resolves → success toast → button disabled.

## Acceptance criteria

1. Schedule / Programs / Phases / Insights pages render with Masthead + tailored 5-cell Scoreboard + page-specific layout.
2. Programs page has a visible `+ New Program` button that opens a functional (UI-only) slide-over; submit logs payload and shows toast.
3. Phases page supports clicking any phase to edit; `+ Add Phase` and "Advance to Next Phase" both fire stubs + toasts.
4. Insights page renders pending hero cards with color-coded borders and functional Accept / Dismiss / Defer buttons (these DO hit backend — existing endpoints).
5. `POST /api/coach/pitcher/{id}/nudge` works end-to-end: authorized coaches can send a Telegram DM to a pitcher on their team; unauthorized returns 403; rate-limited returns 429.
6. Pending strip on Team Overview (from Spec 2) is fully wired to the real endpoint.
7. `coach_actions` table exists in Supabase and audits every nudge.
8. All editorial loading / empty / error states present on every page.

## Open questions (pre-plan)

None. All design decisions locked via brainstorming.
