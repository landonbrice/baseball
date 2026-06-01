# Program Engine — Session Handoff (2026-05-31)

> Cross-machine / new-session handoff. Read this first, then the spec.

## Where everything is
- **Branch:** `program-engine-design` (pushed to origin). Base: `main`.
- **Design spec (read this):** `pitcher_program_app/docs/superpowers/specs/2026-05-31-program-engine-design.md` — Rev 3. Contains the architecture, data model, §13 decision log, and §14 reconciliation with the shipped Program Builder.
- **Recon evidence:** `pitcher_program_app/docs/superpowers/research/2026-05-31-program-engine-recon.md` — 7 fronts with file:line refs, extracted numbers, the live Supabase state.
- **Discovery pointer:** the ★ callout at the top of `CLAUDE.md` "What's Next".

## On the new machine
```
git fetch origin
git checkout program-engine-design
# confirm:
ls pitcher_program_app/docs/superpowers/specs/2026-05-31-program-engine-design.md
```
⚠️ Uncommitted WIP on the OLD machine does NOT travel via git (e.g. modified `pitcher_program_app/bot/services/triage.py`, untracked `PRODUCT_VISION_DRAFT.md`, `PRODUCT_BUILD_PLAN.md`, `DIRECTION_*.md`, `ARCHITECTURE_AUDIT.md`). If any of that matters, commit/stash/copy it before leaving the old machine. It is unrelated to this program-engine work.

## The idea in one paragraph
Turn "here's a pitcher with XYZ context who wants velocity + a healthy arm" into a genuinely individualized **multi-week program** authored **LLM-forward** (brilliant-coach LLM reasons over context + goal + *current* research/templates), kept honest by a **deterministic, content-independent guardrail plane** (ACWR band, deload cadence, monotonic intensity, pull:push, contraindications, exercise-ID resolution), with **living/editable knowledge** (edit a doc → next generation reflects it, no code change). The **program is the primary artifact**; the **day is a projection** of it (locally adjustable by in-the-moment feel but oriented under the goal). v1 = **clean-room demo on `landon_brice`**, goal = velocity, lifting+throwing unified. Goal-agnostic engine underneath.

## The key strategic finding (Rev 3)
The Program Builder is **already shipped** (Plans 1–8). The slop is ONE function: `program_generator._build_schedule_from_scaffold` (a dumb 7-day repeat) + its delegation to the legacy `exercise_pool` slot-filler. **Do NOT build greenfield** (it would fork a shipped feature). Instead: **replace the generation core + guardrails + day-authoring in place; reuse the funnel/lifecycle/projection-seam/feature-flag/UI; populate the empty `block_library` knowledge columns.** Persist on the **`programs` table** (NOT `training_programs` — that's orphaned legacy). Full reuse/replace/conflict map = spec §14.

## Settled decisions + recommended answers to the open questions (§14 Q-A…Q-F)
- Architecture: LLM-forward + deterministic guardrails + living knowledge. ✅
- v1: `landon_brice`, velocity, lifting+throwing unified, **standalone clean-room** (no live `plan_generated` wiring yet). ✅
- Cheapest UI: conform to existing contracts + reuse `BuilderSlideOver`; the real pitcher UI is a **separate parallel effort** consuming a documented API. ✅
- **Q-A** persist on `programs` table → **YES** · **Q-B** reuse `program_aware_plan_gen`+`_select_plan_path` seam → **YES** · **Q-C** leave legacy `training_programs`/`team_assigned_blocks` **dormant** · **Q-D** `prohibited_throw_kinds` **deferred** · **Q-E** golden-xlsx extraction is source-of-truth, existing `velocity_12wk_v1` arc is a scaffold to enrich · **Q-F** living-knowledge layer populates `research_doc_ids` (citations). *(These were recommended; confirm or override in the new session.)*

## OPEN design question #1 — "the drive" (deliberately not decided)
Program→day projection + feel-based override + re-pacing. Leading hypothesis: re-pace remaining weeks to defend the goal. The seam ALREADY EXISTS (`program_runtime.get_active_program_day` → `program_aware_planner.compose_program_aware_plan`) — reuse and deepen it. Decide the policy with fresh thought; sequence as a designed spike.

## Prereqs / first workstreams (for the plan)
0. **Exercise canonical key / alias map** (blocking — research/golden names ↔ 159-row `exercises` table).
1. **Copy the two Drive-alias xlsx into the repo** (`Return to mound…`, `Ramp up w/ Bullpen…` — currently macOS aliases to Google Drive; openpyxl can't read them). Real paths: `~/Library/CloudStorage/GoogleDrive-landonbrice2005@gmail.com/My Drive/`.
2. **Author the velocity knowledge pack as content** (extract from golden xlsx + research; populate `block_library` content/tunable/research columns).
3. **Replace generation core + guardrails**; deepen the projection seam; populate citations.

## NEXT ACTION
Brainstorming is complete and the spec is approved-in-principle. On green light, invoke the **`writing-plans`** skill to turn the spec into a phased, checkpointed implementation plan. (Then `executing-plans`.)

---
### Paste this into the fresh session to resume
> Resuming the Program Engine redesign. Read `pitcher_program_app/docs/superpowers/specs/2026-05-31-program-engine-design.md` (Rev 3, esp. §13 decision log + §14 reconciliation) and `pitcher_program_app/docs/superpowers/research/2026-05-31-program-engine-recon.md`. We're on branch `program-engine-design`. Brainstorming is done; I'm giving green light — invoke the writing-plans skill to produce the phased implementation plan. Use the recommended answers to §14 Q-A…Q-F unless I say otherwise. Keep "the drive" (OPEN #1) as a designed spike. v1 is the clean-room velocity demo on landon_brice; replace the shipped Program Builder's generation core in place (don't greenfield).
