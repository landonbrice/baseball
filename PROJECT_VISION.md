# Project Vision — Pitcher Training Intelligence

> Rewritten 2026-07-13 (PM session with Landon). This is the **light brief**: goals,
> conventions, and problems in one read. Deep reference = `CLAUDE.md`. Live status =
> `MISSION_CONTROL.html`. Sprint plans = `docs/sprints/`. The March 2026 version of this
> file is superseded; git history has it.

## The product in one paragraph (ratified by Landon 2026-07-13)

An app that authors a genuinely individualized **multi-week program** — for a team or an
individual chasing a goal — and structures **each day out of that program**: dynamic
throwing, lifting, and mobility routines, generated from the player's full context
(profile, injury history, readiness, biometrics) through **research-based LLM calls
blended with authored deterministic pathways**. The program is the primary artifact; the
day is a projection of it. It must beat both a Google Sheet and a raw LLM chat.

## Where we are, and where we're going

- **Landon's #1 training goal right now: return to play healthy** (not velocity). The
  first knowledge pack and the v1 demo target the return-to-mound arc. The engine stays
  goal-agnostic underneath.
- **Summer 2026 = development phase.** Landon is the only daily user. The team is off the
  system. This is the cheapest time we will ever have to rework foundations.
- **September–October 2026 = team onboarding.** Everyone re-onboarded, system fully
  running, engine-authored programs live. All sequencing points at this.
- **Sprint queue (primed, gated on Landon's go): `docs/sprints/2026-07-sprint-queue.md`**
  — A: prove the engine core with a live-LLM return-to-play demo → B: collapse three
  generation pipelines into one spine + full dead-code/dead-table cleanup → C: implement
  the drive + Landon's daily plans go live on the engine → D: fall onboarding.

## The generation constitution (division of authority)

| Plane | Owns | Runs |
|---|---|---|
| **LLM** (research-grounded) | Program *authoring*: phase structure, progression, exercise selection, the "why" | Once per program, at creation / explicit regenerate. Model: DeepSeek reasoner for now (decision 07-13; revisit after first real output) |
| **Deterministic** | Safety + math + the day: ACWR/load math, contraindications, deload cadence, ramps, day *projection*, triage | Every day, every check-in — no model in the loop |
| **Authored knowledge** | The tunable content both planes read: research docs, templates, golden programs | Resolved at generation time; edit a doc → next generation changes, no code change |

**Rules:** the LLM decides *what the program is*; determinism decides *whether it's safe*
and *what today is*. Daily output must never depend on a live LLM call succeeding.
**The drive** (bad-readiness day → program impact) is **propose-and-confirm**: today
shrinks deterministically, the reschedule is proposed, the player confirms (decision
07-13; bounds and intricacies in Sprint C).

## The problems, honestly (agent-visible; Landon ratified 2026-07-13)

1. **Three generation pipelines coexist** — legacy slot-filler (live for all),
   Builder's rotation-repeat (live behind flag), Engine v1 (built on PR #34, dormant,
   LLM path never run against a real model). The slop is the coexistence. Endgame: one
   spine — engine authors, projection produces the day, legacy survives only as the
   deterministic fallback floor.
2. **The engine's thesis is unproven** — every green test runs the fallback.
   Highest-leverage hour in the project: the live-LLM run on Landon's real context.
3. **Landon's real pain as the daily user** (aim robustness work here):
   plan quality/repetitiveness (the engine's job to fix), slow/failing check-ins
   (latency path), and **distrust of stored state** (rotation day / phases / week state
   sometimes look wrong → the one-spine convergence and state audits address this).
   Silent breakage is NOT a top pain — Guardian covers it adequately.
4. **Dead weight approved for full removal** (decision 07-13, cheapest-ever window):
   legacy `programs.py` engine still running per check-in, `saved_plans` (post-audit),
   orphan tables `training_programs`/`program_templates`/`schedule` + blocking FK,
   ~400 lines of orphaned frontend, 3,062-line `api/routes.py`, duplicated phase
   vocabularies.

## Conventions that keep agents out of trouble (distilled — full detail in CLAUDE.md)

1. **Update `MISSION_CONTROL.html`** (JSON island only) after meaningful work; validate
   with the one-liner in its header. This is the shared memory across Claude/Codex/Gemini.
2. **Tests stay green**: `cd pitcher_program_app && python -m pytest tests/ -q` (use a
   venv; system pip fights PyJWT/cryptography). 880+ pass as of 07-12.
3. **Supabase is source of truth**; access via `bot/services/db.py` with `service_role`
   only; column whitelists guard upserts; new tables ship RLS-locked (010/012/017 idiom);
   migrations via Supabase MCP. `pitchers` PK is `pitcher_id`.
4. **All dates Chicago**: `datetime.now(CHICAGO_TZ)` server-side, `en-CA` + timeZone
   client-side.
5. **Check-in semantics live in `team_daily_status.py`** — never re-derive them.
   `checked_in` == `pre_training.arm_feel is not null`.
6. **Two-pass lesson is law**: Python builds a complete valid thing first; LLM enriches
   after; timeout → the deterministic result ships.
7. **Plans have two lifting homes** (`lifting` top-level + `plan_generated.lifting`) —
   swap/mutation code must handle both (CLAUDE.md "Dual-Write" gotcha).
8. **Coach-app brand tokens are locked** (`tokens.css`); brand colors ≠ alert colors;
   Scoreboard takes exactly 5 cells.
9. **Knowledge is content, not code**: research docs carry YAML frontmatter under
   `data/knowledge/research/`; golden programs under `data/knowledge/golden_programs/`;
   the resolver (`research_resolver.py`) is the single door.
10. **Don't start a new workstream lane without logging it** in Mission Control; sprints
    don't start without Landon's explicit go.

## Product scope

*Deliberately thin — Landon is taking the product side in a dedicated session; this
section gets filled there. Until then: pitcher mini-app + coach dashboard exist and work;
the product question is how program-first generation reshapes them for fall onboarding.*
