# Coach Dashboard — v1 Backlog (Living Document)

> Started: 2026-04-09
> Purpose: Track features and ideas that are out of v0 scope but should land in the post-demo summer build.
> Update continuously as new ideas surface during brainstorming and implementation. Do NOT silently drop items here even when v0 pressure mounts — deferring is fine, forgetting is not.

## How to use this file

- New idea comes up in a v0 conversation but doesn't fit May demo scope → add it here with a one-line rationale.
- Idea gets promoted into v0 → strike through here (do not delete) so the decision trail stays visible.
- After May demo ships → re-sequence this list into a v1 implementation plan.

## Core Deferred Features

### 1. Pitcher usage timeline / drag-rotation view
Multi-week rotation planning view. Coach sees rotation blocks across a horizon, drags pitchers between starting days, sees total pitches thrown + pitch-count timeline per pitcher. Bird's-eye view for rotation planning.
**Why deferred:** Highest-effort UI piece in the roadmap. v0 substitute is the 7-day forward strip on Player Detail.

### 2. Structured bullpens / scrimmages entry
Tue/Wed bullpen rhythm, weekend scrimmages, coach inputs these as non-game throwing events that feed the engine the same way games do. Layered on top of the off-season phase block system.
**Why deferred:** Adds a new event type to the data model and engine; v0 covers the same concept implicitly via rotation logic.

### 3. Real athletics page scraper
Automated ingestion from UChicago athletics (and equivalent feeds for other programs) to populate the `schedule` table. Replaces hand-seed for any program with a public schedule feed.
**Why deferred:** Hand-seeding takes 30 minutes and is fine for May demo. Scraper is brittle per-site.

### 4. Coach Insights Engine v1 — multi-category
Expand from "pre-start nudge only" to: volume deload warnings, readiness-trend alerts, injury precursor flags, rest-day recommendations, weekly progression review. Each is its own suggestion rule running off pitcher_training_model + weekly_model state.
**Why deferred:** v0 ships with one category to validate the plumbing before expanding.

### 5. Return-to-mound integration
When a pitcher is flagged as returning from injury, the engine pulls the 8-week `return_to_mound.md` progression into its context and generates programs against it. Coach sees a "returning from injury" banner on that pitcher's detail. Template already exists in `data/templates/return_to_mound.md`.
**Why deferred:** Requires injury-state machine and a coach-facing return trigger.

### 6. Coach-editable templates
Coach can view and modify starter/reliever/position templates for their team. Saved as team-scoped template overrides. Includes custom block authoring for team programs.
**Why deferred:** v0 uses pre-loaded templates only. Custom editor is a significant UI surface.

### 7. Team-wide rules (third override scope)
"No overhead pressing once in-season" applied across the entire roster. The scope we explicitly deferred from the two-verb override model.
**Why deferred:** Two-verb model (today / athlete) is cleaner for v0; team-wide rules can layer on.

### 8. Native app (React Native + Expo)
Port Mini App off Telegram. Proper auth, push notifications, App Store presence. Telegram dependency killed for new users.
**Why deferred:** Mini App works, is deployed, is in daily use. No infrastructure pain during demo period.

### 9. Weight logging UI
Replace binary completion with actual logged weights and RPE. Feeds auto-progression in the engine (week-over-week load increases).
**Why deferred:** Storage column `pitcher_training_model.working_weights` already exists; UI and progression logic do not. Not demo-critical.

### 10. Custom video library
Film demo videos for the full exercise library (159 exercises, plus new additions). Replace YouTube links with owned IP.
**Why deferred:** YouTube works for v0. Filming is a summer project.

### 11. Self-serve coach onboarding flow
Signup page, guided team creation, roster import (CSV or team-code self-enrollment), default template application, first-pitcher-activation pop. The thing a new coach experiences when they aren't UChicago.
**Why deferred:** v0 uses a manual handoff — I create the demo account myself. Self-serve is the unlock for team #2+.

### 12. Lifting team-blocks
Team Programs in v0 supports throwing blocks only. Lifting team-blocks (e.g., "offseason strength phase" applied to the whole roster) land in v1.
**Why deferred:** Throwing is where the demo's velocity-block moment lives. Lifting blocks add scope without adding demo narrative.

### 13. Coach-authored custom team blocks
v0 ships with a pre-loaded library of 3-4 throwing blocks. v1 adds a block editor — coach drags exercises, sets progression, saves as a new block template.
**Why deferred:** Editor UI is heavy. Pre-loaded library is enough for May.

### 14. Multiple concurrent team blocks
v0 supports one active team block at a time (throwing). v1 supports multiple overlapping blocks per type (e.g., "velocity for starters, long-toss for relievers").
**Why deferred:** Needs per-position-group assignment logic.

### 15. Per-position-group team block assignment
"Velocity program for starters only." Requires position-group tagging and assignment scoping UI.
**Why deferred:** Single-scope team assignment is enough for v0 demo.

### 16. Drag-to-adjust off-season phase boundaries
v0 ships with click-to-edit start/end dates on phase blocks. v1 adds a proper drag-drop timeline editor with visual feedback.
**Why deferred:** Form-based edit is fine for v0 MVP of off-season phases.

## Infrastructure / Architecture Backlog

### 17. RLS policies beyond team_id filter
v0 ships team_id multi-tenancy but enforces filtering in the application layer. v1 adds proper Supabase Row Level Security policies as a defense-in-depth.
**Why deferred:** Application-layer filtering is sufficient for a controlled demo; RLS requires auth-context propagation.

### 18. Coach audit trail
Log every coach override (who, when, what, why) in a dedicated `coach_audit` table. Expose on player detail as a "modification history" timeline.
**Why deferred:** `modifications_applied` on daily_entries partially covers this; proper audit trail is a v1 polish item.

### 19. Coach dashboard analytics
Team compliance trends over time, training volume summaries, injury correlation reports. Beyond the 7-day rollup that ships in v0.
**Why deferred:** Analytics without 3+ weeks of data are noise. Real value emerges post-demo usage.

### 20. Mobile-responsive coach dashboard
v0 is desktop-first. Mobile-responsive for "coach on the field" use case is a v1 polish item.
**Why deferred:** Coaches use the dashboard at a desk before/after practice, not on the field in v0 reality.

## Open Questions for v1 Planning

- Does the native app need its own dashboard app for coaches, or does the coach web app stay web-only?
- If multiple teams share an organization (travel ball with 8-12 teams), do we need an "organization" layer above "team"?
- Does the engine need a "pre-season ramp" concept distinct from offseason and in-season, or can phases cover it?
- How do we price custom block authoring (is it a premium feature, or core)?

---

*This file is maintained during design and implementation. Every idea that surfaces and doesn't make v0 lands here with a rationale. Do not delete items that were moved up into v0 — strike them through so the decision trail is visible.*
