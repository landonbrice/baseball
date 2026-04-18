# Coach Dashboard Redesign — Spec 2: Team Overview

> Status: Design-approved 2026-04-18
> Phasing: Spec 2 of 3. Depends on Spec 1 (Brand System & Shell). Spec 3 may proceed in parallel after Spec 1 lands.

## Context

Team Overview is the dashboard's front door. The brand discussion in Spec 1 was driven by what this page needs to be: a morning triage tool that answers, in three seconds, *who's checked in, who's hurting, and what is each pitcher doing today*.

Today's Team Overview (`pitcher_program_app/coach-app/src/pages/TeamOverview.jsx`) is a left-sidebar-of-cards + a table. It works, but the table row doesn't show today's objective, the compliance ring competes with the roster, and the flat visual hierarchy means flagged pitchers don't pop.

This spec rebuilds the page around the editorial + numbers-first language from Spec 1. The roster table is replaced with a **triage feed**: hero cards for flagged pitchers, a compact grid for on-track greens, and a pending check-in strip at the bottom.

## Goals

- First 3 seconds: coach knows check-in compliance, flag distribution, and who needs attention.
- Every pitcher card surfaces today's objective as a first-class piece of information.
- Flagged pitchers get visual weight proportional to their risk; greens stay dense and scannable.
- Slide-over retained and redesigned — coaches can peek deep without losing context.

## Non-goals

- Mobile phone layout (<768px)
- Search / keyboard shortcuts
- Role-based content filters (HC / PC / S&C see the same Team Overview)
- Changes to `GET /api/coach/team/overview` endpoint shape (consume what's already returned)

## Page layout

Top to bottom within the main content area (right of Sidebar from Spec 1):

1. **Masthead** — `kicker="Chicago · Pitching Staff"`, `title="Team Overview"`, `date` in Inter, `week` line shows training phase context (e.g., "Week 12 of 16 · Preseason"). No actionSlot.
2. **Scoreboard** — 5 cells as specified below.
3. **Lede** — italic serif summary of the morning. Dynamic copy (see "Lede generator").
4. **"Needs Attention" section** — kicker section-header, hero-card 3-column grid.
5. **"On Track" section** — kicker section-header, compact-card 4-column grid.
6. **Pending check-in strip** — horizontal amber-dashed strip at bottom.
7. **PlayerSlideOver** — right-edge slide-over, opens on any card click.

## Scoreboard — 5 cells

Pulled from `GET /api/coach/team/overview` response (`{ team, compliance, roster, active_blocks, insights_summary }`) plus derived computations.

| # | Label | Value | Sub | Source |
|---|---|---|---|---|
| 1 | Check-ins | `{checked}/{total}` | `{outstanding} outstanding · avg {avg_time}am` | `compliance.checked_in_today`, `compliance.total`, derived |
| 2 | Flags | `{green} · {yellow} · {red}` (colored) | `Green · Yellow · Red` | `compliance.flags` |
| 3 | Avg Arm Feel | `{avg_7d}` (one decimal) | `↑/↓{delta} vs last week` (forest up / crimson down) | derived from `roster[].af_7d` |
| 4 | Today's Work | `{bp_count} bp` | `+ {sim_count} sim · {recov_count} recovery` | derived from `roster[].day_focus` |
| 5 | Next Start | weekday abbrev | `{pitcher_name} · vs {opponent}` | earliest `roster[].next_scheduled_start` + `team_games` (already joined) |

Delta arrows in Check-ins avg-time and Avg Arm Feel use Unicode arrows (`↑`, `↓`) in `forest` / `crimson` to match flag semantics.

## Lede generator

`buildTeamLede(roster, compliance)` → string with optional `<b>` tags for emphasized names.

Priority:
1. **Any RED pitchers** → "One arm needs close attention today: <b>Heron</b> (TJ, 12mo post-op) logged red..."
2. **Any YELLOW pitchers** → "<b>Wilson</b>'s ulnar symptoms ticked up overnight, and <b>Sosna</b>'s oblique is still active."
3. **All green + ≥ 90% checked in** → "A clean morning — {checked}/{total} in before practice, staff averaging {af} arm feel."
4. **Low check-in compliance (<75%)** → "Quiet morning so far — only {checked}/{total} checked in. Consider a nudge."

Lives in `coach-app/src/utils/teamLede.js`. Unit-tested against fixtures.

## "Needs Attention" — hero cards

### Inclusion rule
Every pitcher where `flag_level ∈ {yellow, red}` OR `active_injury_flags` non-empty AND trending worse (7d AF delta < -0.5).

### Sort order
1. Red first (by AF ascending)
2. Yellow (by AF ascending)
3. At 0 flagged: section + header hidden; Lede absorbs "clean morning" state.

### Card structure (`<HeroCard pitcher>`)
- 4px left border — `crimson` if red, `amber` if yellow.
- Background: `--color-bone`.
- Header row: name (Source Serif 700 17px) + role/jersey meta beneath (Inter 10px muted) | `<FlagPill>` right-aligned.
- Injury chip: single line (e.g., "TJ+olecranon · 1yr post-op · trending down") in Inter 10px maroon on `--color-parchment` background, 2px radius, inline-block.
- Objective block: bordered-bottom 1px dashed `--color-cream-dark`, 10px bottom padding. Inside: kicker "Today · {mark}" + body text, body in Inter 13px charcoal.
- Stats foot: 3-column grid — AF 7d / Last 7 strip / Next Start. Labels in eyebrow, values in serif h2 with Inter meta.

### Grid
- 3 columns `>= 1280px`, 2 columns `>= 768px`, 1 column below (for tablet portrait).
- Gap: 12px.
- At 6+ flagged, render first 6 and add a "View all flagged" expand button — performance guard even though 6+ flagged means the team has bigger problems than rendering.

## "On Track" — compact cards

### Inclusion rule
Every pitcher where `flag_level === 'green'` AND today's check-in is complete. (Pending greens go to the Pending strip.)

### Card structure (`<CompactCard pitcher>`)
- 3px left border — `--color-forest`.
- Background: `--color-bone`.
- Row 1: name (Source Serif 700 14px) | AF value (Inter 700 12px forest) right-aligned.
- Row 2: role meta (Inter 9px muted).
- Row 3: objective — kicker "{mark}" + single-line body, Inter 12px graphite.
- Foot row: Last 7 strip | "Next: {date}" meta.

### Grid
- 4 columns `>= 1280px`, 3 columns `>= 1024px`, 2 columns `>= 768px`.
- Gap: 10px.

## Pending check-in strip

- Position: below "On Track" section.
- Styling: 1px dashed `--color-cream-dark`, subtle `rgba(0,0,0,0.03)` background, 3px radius, 12px vertical padding, 14px horizontal, flex-row layout.
- Left: eyebrow label "Awaiting check-in" in amber.
- Middle: space-separated list of pitcher names with "last {Nh} ago" meta.
- Right: **"Nudge →"** action button per-pitcher.
  - In Spec 2: button is disabled with tooltip "Backend pending (Spec 3)". Visual only.
  - In Spec 3: hooks to `POST /api/coach/pitcher/{id}/nudge` endpoint.
- Hidden if 0 pending.

## "Today's Objective" formatter

`buildTodayObjective(dailyEntry)` → `{ mark: string, text: string }`

Lives in `coach-app/src/utils/todayObjective.js`. Uses `daily_entries` row for today (included in `roster[].today` from the overview endpoint — extend endpoint to include `lifting_summary`, `bullpen`, `throwing`, `modifications` fields from the entry).

### Priority
1. `modifications` non-empty → mark = "Recovery" / "Light" / "Modified" (derived from severity); text = modification description.
2. `day_focus === 'bullpen'` → mark = "Bullpen"; text = `${pitches}p · ${intent}% · ${mix}`.
3. `day_focus === 'lift'` → mark = "Lift"; text = lifting block summary (e.g., "Upper push — bench, DB row, rotary med-ball").
4. `day_focus === 'throw'` → mark = "Throw"; text = `Long toss · ${target_distance}ft cap`.
5. `day_focus === 'plyocare'` → mark = "Plyocare"; text = top exercise names.
6. `day_focus === 'recovery'` → mark = "Recovery"; text = mobility video name.
7. Fallback: mark = "Rest"; text = "Off day — light mobility optional".

### Fixtures for unit tests
10 plan shapes — one per day_focus × flag_level combination. Cover edge cases: empty lifting, bullpen without mix, modifications without day_focus override.

## PlayerSlideOver redesign

Keep the shell from existing `PlayerSlideOver.jsx` — right-edge panel, 480px wide, backdrop click to dismiss, ESC to close. Redesign the internals.

### Header (always visible)
- Pitcher name (Source Serif 700 24px) + role meta + FlagPill.
- Injury context line (from `pitcher_training_model.current_flag_level` + `injury_history` summary).
- 3-stat mini-scoreboard: AF 7d / Streak / Next Start. Styled same as main scoreboard but smaller (cells 80px).

### Tab nav
Existing tabs: **Today / Week / History**. Inter 11px caps letter-spaced, 2px bottom-border-active in maroon.

### Today tab
- Sections: Warmup, Arm Care, Lift, Throw, Recovery. Each section: kicker header + item list.
- Each item: name (serif 13px) + prescription meta (Inter 11px muted). Completed items: strikethrough + forest check.
- Tap an item → expands to show full prescription (sets × reps, YouTube link if present).

### Week tab
- 7-day calendar strip — one cell per day, 60×80px. Each cell: day name (Inter caps 9px) / flag dot / day_focus label / completion ring (derived from completed_exercises count).
- Below: "Weekly arc" editorial summary — kicker + lede-style italic paragraph pulled from `weekly_summaries` table or `pitcher_training_model.current_week_state.summary`.

### History tab
- 30-day sparkline chart: arm feel + energy overlaid (uses existing Chart.js config from mini-app).
- Below: chronological check-in log — scrollable list. Each entry: date, flag pill, arm_feel, note. Filter chips at top: All / Flagged / With notes.

## Data flow

- Mount: `GET /api/coach/team/overview` → populates scoreboard, roster sections, pending strip. (Endpoint must be extended to include lifting/bullpen/throwing/modifications inside each `roster[].today` so the frontend formatter has what it needs. See "Backend deltas" below.)
- Slide-over open: `GET /api/coach/pitcher/{id}` → populates tabs.
- Auto-refresh: Team Overview refetches every 90 seconds when tab is visible (use `document.visibilityState` to pause when hidden). Slide-over data stays static until reopened.

### Backend deltas
`GET /api/coach/team/overview` currently returns `{ team, compliance, roster, active_blocks, insights_summary }`. Extend `roster[]` shape to include:
```json
{
  "pitcher_id": "...",
  "name": "...",
  "role": "...",
  "flag_level": "green",
  "today_status": "checked_in",
  "last_7_days": [...],
  "streak": 9,
  "af_7d": 7.4,        // NEW — computed from last 7 daily_entries pre_training.arm_feel
  "next_scheduled_start": "2026-04-22",
  "active_injury_flags": [...],
  "today": {           // NEW — today's plan summary
    "day_focus": "lift",
    "lifting_summary": "Upper push — bench, DB row, rotary med-ball",
    "bullpen": null,
    "throwing": null,
    "modifications": []
  }
}
```
Route this through `bot/services/team_scope.py::get_team_roster_overview` — extend the select to include today's `daily_entries` row joined on `pitcher_id + date = today`.

## States

### Loading
Skeleton scoreboard (5 cells, pulse animation on value lines) + skeleton hero-card row + italic caption beneath: *"Gathering the morning check-ins..."*

### Empty (no pitchers on team)
Editorial message: *"No pitchers on this staff yet."* Link: "Set up your roster →" → docs / admin page.

### Error
Editorial message: *"Something's off on our end. We couldn't load the roster. Try again in a moment."* Retry button (reuses `<EditorialState retry>`).

### Zero-flagged (all green, normal)
Lede copy: *"A clean morning — all {n} checked in, no flags, staff averaging {af} arm feel. Programming continues as scheduled."* "Needs Attention" section hidden. "On Track" becomes the full roster.

## Interactions

- Hover hero card → background shifts to `--color-hover`, cursor pointer, subtle 1px shadow lift.
- Hover compact card → same hover background, no shadow.
- Click card anywhere → opens `PlayerSlideOver` for that pitcher.
- Scoreboard cells: non-interactive in v1. (Future: click "Flags" to filter roster — tracked as open question for v2.)
- Filter chips from old `RosterTable` ("All / Checked In / Not Yet / Flagged") are **removed**. The two-section layout is the filter.

## Component inventory

New components (in `coach-app/src/components/team-overview/`):
- `<HeroCard pitcher>`
- `<CompactCard pitcher>`
- `<PendingStrip pending nudgeEnabled>`
- `<TeamLede roster compliance>` — reads, calls `buildTeamLede`, renders `<Lede>`.

New utils (in `coach-app/src/utils/`):
- `buildTodayObjective(dailyEntry)` — formatter
- `buildTeamLede(roster, compliance)` — lede copy generator

Redesigned (internals only, shells retained):
- `PlayerSlideOver.jsx` — new header + new tab internals
- `PlayerToday.jsx` / `PlayerWeek.jsx` / `PlayerHistory.jsx` — rebuilt per tab spec above

Removed:
- `RosterTable.jsx` — no longer needed (hero + compact grids replace it)
- `ComplianceRing.jsx` — compliance now lives in the scoreboard, not a standalone widget

Retained unchanged:
- `AddRestrictionModal.jsx`, `AdjustTodayModal.jsx` — still triggered from PlayerSlideOver Today tab

## Testing

- **Unit tests**:
  - `buildTodayObjective` — 10-fixture suite, one per day_focus × flag_level combo.
  - `buildTeamLede` — 6 fixtures: all-red, some-yellow, all-green-high-compliance, all-green-low-compliance, mixed, single-pitcher edge case.
- **Component tests**:
  - `<HeroCard>` — renders correct left border color per flag, correct stats, handles missing AF gracefully.
  - `<CompactCard>` — same for green layout.
  - `<PendingStrip>` — hidden when pending list is empty, shows disabled Nudge button when `nudgeEnabled=false`.
- **Integration test** (React Testing Library + MSW):
  - Mount TeamOverview with mocked API response covering all card types; assert scoreboard values, section visibility, slide-over trigger.
- **Visual regression**: Percy snapshot of TeamOverview in three states (normal / all-green / 6+ flagged).
- **Accessibility**: keyboard-only navigation through all cards and into slide-over; axe-core passes.

## Acceptance criteria

1. Opening `/` shows Masthead + Scoreboard + Lede + (if any flagged) Needs Attention hero grid + On Track compact grid + (if any pending) Pending strip.
2. Every card displays today's objective with the correct mark kicker and formatted text.
3. Clicking any card opens PlayerSlideOver with the redesigned header and functioning tabs.
4. Scoreboard auto-refreshes every 90s without layout shift.
5. All loading / empty / error states match editorial voice.
6. Removed `RosterTable.jsx` and `ComplianceRing.jsx` from `pages/TeamOverview.jsx` imports — no dead code.
7. Backend `GET /api/coach/team/overview` response includes `roster[].af_7d` and `roster[].today` as specified.
8. All component tests pass; unit fixtures for `buildTodayObjective` cover all day_focus values.

## Open questions (pre-plan)

None. All design decisions locked via brainstorming.
