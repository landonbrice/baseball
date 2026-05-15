# Program Builder v1 → Cleanup + Roster Rollout (Plan 8)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the v1 cleanup carryovers from Plan 7 (saved_plans hard-drop, phase vocabulary convergence, drift insight CTAs, A4 LLM polish, coach-authored research workflow) and roll the program-aware plan-gen fork out to the full pitching staff with the observability + per-pitcher kill-switch needed to survive the next "structural debt surfaces on first live fire" moment.

**Architecture:** Four phases, ordered for safety.
- **Phase A** — Observability + safety nets. Must land 100% green before Phase D. Adds the structured logging + per-pitcher feature-flag kill-switch that makes the roster rollout reversible per-pitcher in seconds.
- **Phase B** — Schema cleanup. Drops `saved_plans` (after verification gate) + converges the two phase vocabularies via a new `template_phase_key` column.
- **Phase C** — Coach-app feature work. Drift insight Archive/Accept CTAs, A4 insight body LLM polish, coach-authored research doc workflow.
- **Phase D** — Full-roster rollout + 1-week monitoring + tag.

**Tech Stack:** Python 3.11 / FastAPI (backend); React 18 / Vite mini-app; React 19 / Vite / Tailwind v4 coach-app; Supabase Postgres; DeepSeek LLM. Builds on tag `program-builder-v1-complete` + commit `e1cb657` (PR #29 hotfix making the program-aware path return the full plan shape).

---

## 2026-05-15 — Locked decisions (from Plan 8 brainstorm)

| # | Decision | Why |
|---|---|---|
| L1 | **`saved_plans` zero-writes verification BEFORE drop** | Plan 7 A15 set the canary (`saved_plans_deprecated_write` WARN log). Plan 8 starts by greping Railway logs over a 2-week window. If non-zero, find + fix the caller before the drop migration. Avoids a 500-class regression in prod. |
| L2 | **Full-roster expansion of `program_aware_plan_gen` this plan** | Faster signal-to-noise on remaining structural gaps. PR #29 caught one (`plan_result["narrative"]` KeyError); more bugs probably exist on paths landon_brice doesn't exercise (reliever templates, YELLOW flag with recovery curve, etc.). Phase A's structured logging + per-pitcher kill-switch limits blast radius. |
| L3 | **Schema-level phase convergence** | New `template_phase_key` column on `training_phase_blocks` holding the canonical 4-value enum (`off_season`/`preseason`/`in_season`/`in_season_active`). Backfill the 5 existing rows. Delete `phaseToTemplatePhaseIds()` once data migrates. Authoritative + future-proof; anyone adding a new `phase_name` writes the canonical token at create-time, no client-side regex maintenance. |
| L4 | **Prohibited-day conflict logic explicitly NOT in scope** | Deferred to Plan 9 if/when it becomes blocking. Players currently build whenever (Plan 6 A5's v1 stance); zero in-prod conflicts reported. Pure feature addition vs the cleanup theme of Plan 8. |
| L5 | **A4 LLM polish keeps the rule-based gate** | LLM only rewrites `reasoning` body text — the drift/mismatch/lag thresholds + insight generation rules stay synchronous + rule-based. Cost-bounded; failure falls back to the rule-based body. |
| L6 | **Coach-authored research = attach-existing, not write-new** | v1: coach picks from existing `data/knowledge/research/` docs to attach to a template via a new `block_library.research_doc_ids` editor. Writing new research docs (authoring + frontmatter validation + git/Supabase choice) defers to v2. Saves ~3 tasks of design work. |
| L7 | **Per-pitcher kill-switch is THE rollback story** | No env-var-level feature flag for "program path globally off". If the entire path needs to die, we flip every pitcher's `pitcher_training_model.feature_flags.program_aware_plan_gen` to `false` (admin endpoint, audited). Avoids the deployment-vs-config split that bit System Guardian PR-21. |

## Carryovers from Plan 7 (addressed here)

- Hard-drop `saved_plans` → Phase B (B1)
- Drift insight Archive/Accept CTA wiring → Phase C (C1)
- LLM-polish A4 insight bodies → Phase C (C2)
- Coach-authored research doc workflow → Phase C (C3, scoped per L6)
- Converge phase vocabularies → Phase B (B2)
- Roll out `program_aware_plan_gen` past landon_brice → Phase D (D1)

## Plan 9 backlog (defer)

- Prohibited-day conflict logic (declarative `prohibited_throw_kinds` template field + 409 + `?confirm=true` retry)
- Cross-pitcher favorite copy ("I want what Reed did Tuesday")
- Brand-shell workspace package (`packages/shell`) — extract `coach-app/src/components/shell/` into a workspace-shared package both apps consume
- Coach-authored NEW research doc workflow (authoring, not just attaching — v2 of C3)
- WHOOP token rotation (post-2026-04-30 lockdown action item — Kamat / Kwinter / Richert)
- The Ledger (modification history timeline on Profile)
- Weight logging UI + exercise progression curves

---

# Phase A — Observability + safety nets

Phase A MUST land 100% green before Phase D. Adds the visibility + kill-switch that makes the full-roster rollout reversible.

### Task A1: `saved_plans` zero-writes verification + report

**Files:**
- Create: `pitcher_program_app/scripts/verify_saved_plans_deprecated.py`
- Create: `docs/runbooks/saved_plans_deprecation_audit.md`

**Approach:** A small script that (a) queries Supabase for any `saved_plans` rows whose `created_at >= '2026-04-30'` (when A15 deprecation logging landed) and (b) prints a human-readable summary. **No Railway log integration** — that requires the `RAILWAY_TOKEN` env var that Guardian Phase 2 introduces, and we don't have it yet. The Supabase `created_at` filter is sufficient because every `insert_saved_plan` write touches the table.

The report is the gate for B1: if it shows zero rows in the deprecation window, B1 proceeds. If it shows rows, B1 blocks until we identify + remove the caller.

**Key signature:**

```python
# scripts/verify_saved_plans_deprecated.py
"""Plan 8 / A1 — saved_plans deprecation audit.

Prints a report of saved_plans rows created since the Plan 7 A15
deprecation logging landed (2026-04-30). Zero rows in the window means
the table is safe to drop (Plan 8 B1). Any rows means we have a caller
still writing — fix that first.

Usage:
    python -m scripts.verify_saved_plans_deprecated [--since 2026-04-30]

Exit codes:
    0 — zero writes in the window (drop is safe)
    1 — non-zero writes (drop is NOT safe)
    2 — Supabase connection / query failed
"""
import argparse
import os
import sys
from datetime import datetime

DEFAULT_SINCE = "2026-04-30"  # Plan 7 A15 ship date


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--since", default=DEFAULT_SINCE,
                   help="ISO date — count rows where created_at >= this")
    args = p.parse_args()

    try:
        from bot.services import db
    except Exception as exc:
        print(f"FAILED to import db client: {exc}", file=sys.stderr)
        return 2

    try:
        resp = (
            db.get_client().table("saved_plans")
            .select("plan_id, pitcher_id, plan_name, created_at")
            .gte("created_at", args.since)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        print(f"FAILED Supabase query: {exc}", file=sys.stderr)
        return 2

    rows = resp.data or []
    if not rows:
        print(f"OK — zero saved_plans writes since {args.since}.")
        print("Plan 8 B1 (drop migration) is SAFE to proceed.")
        return 0

    print(f"BLOCKED — found {len(rows)} saved_plans writes since {args.since}:")
    for r in rows[:20]:
        print(f"  - {r.get('created_at')} | pitcher={r.get('pitcher_id')} | "
              f"plan={r.get('plan_name') or '<no-name>'} | id={r.get('plan_id')}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more")
    print("Find the caller(s) and remove the write path before B1.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

```markdown
<!-- docs/runbooks/saved_plans_deprecation_audit.md -->
# saved_plans deprecation audit runbook

Plan 7 A15 added `saved_plans_deprecated_write` WARN logs on every write.
Plan 8 A1 audits the Supabase table directly (no Railway log integration
yet — Guardian Phase 2 will add that).

## Run the audit

```
cd pitcher_program_app
python -m scripts.verify_saved_plans_deprecated
```

Exit 0 → safe to run Plan 8 B1 (drop migration).
Exit 1 → block on B1, investigate.

## If the audit fails

Find the writer:

```
git log --all --oneline --since='2026-04-30' -S 'insert_saved_plan'
git log --all --oneline --since='2026-04-30' -S 'save_plan'
grep -rn "save_plan\|insert_saved_plan" pitcher_program_app/api pitcher_program_app/bot
```

Plan 7 B16 removed the mini-app caller; the remaining `save_plan` call
inside `api/routes.py:1257` (custom-plan generator path) is the most
likely culprit. Either remove that call or migrate to `favorited_blocks`.
```

**Steps:**
- [ ] Create `scripts/verify_saved_plans_deprecated.py`
- [ ] Run it locally: `cd pitcher_program_app && python -m scripts.verify_saved_plans_deprecated` — capture output
- [ ] Create the runbook doc
- [ ] Commit: `feat(plan-8/a1): saved_plans deprecation audit script`
- [ ] Attach the script output to the PR body before merge so reviewer sees the count

**Acceptance:** Script runs cleanly against prod Supabase. Output is human-readable + exit code is correct. The runbook explains what to do on a non-zero result.

**Note:** No tests. This is a one-shot ops script, not production-path code.

---

### Task A2: Program-aware path structured logging + per-pitcher kill-switch

**Files:**
- Modify: `pitcher_program_app/bot/services/program_aware_planner.py` (add structured logging)
- Modify: `pitcher_program_app/bot/services/checkin_service.py` (log `_select_plan_path` decision)
- Create: `pitcher_program_app/api/admin_program_flag.py` (new tiny admin router)
- Modify: `pitcher_program_app/api/main.py` (mount the new router)
- Modify: `pitcher_program_app/bot/services/db.py` (add `set_feature_flag` helper)
- Create: `pitcher_program_app/tests/test_admin_program_flag_endpoint.py`
- Create: `pitcher_program_app/tests/test_program_aware_logging.py`

**Approach:** Two changes that are independent but ship together because they're both kill-switch infrastructure.

**(1) Structured logging on every program-aware fire.** `compose_program_aware_plan` (added in PR #29) already logs at a few points but the log shape is ad-hoc. Add ONE structured log event at the end of every program-aware composition with these fields, so Guardian / health_monitor / future ad-hoc grep can answer "did the program path run for pitcher X today, and what did it produce?":

```python
# bot/services/program_aware_planner.py — at the end of compose_program_aware_plan
logger.info(
    "program_aware_compose",
    extra={
        "event": "program_aware_compose",
        "pitcher_id": pitcher_id,
        "program_id": program["program_id"],
        "current_day_index": program.get("current_day_index"),
        "rotation_day_resolved": rotation_day,
        "domain": program.get("domain"),
        "template_key": template_key,
        "hold_event_kind": hold_event.get("kind") if hold_event else None,
        "plan_source": plan.get("source"),  # 'program_prescribed' if all good
        "plan_source_reason": plan.get("source_reason"),
        "narrative_present": bool(plan.get("narrative")),
        "lifting_exercises_count": len((plan.get("lifting") or {}).get("exercises") or []),
    },
)
```

Match the same shape on the fall-through path in `_select_plan_path` so dashboards can compare program-path vs legacy-path per pitcher.

**(2) Per-pitcher kill-switch endpoint.** New tiny admin router gated by `GUARDIAN_ADMIN_TOKEN` (reuse the existing shared-secret rather than introduce a new one — same shape as Guardian admin routes):

```python
# api/admin_program_flag.py
"""Plan 8 / A2 — per-pitcher kill-switch for the program-aware fork.

Mounted at /admin/program-flag/*. Shares the GUARDIAN_ADMIN_TOKEN
shared-secret with /admin/guardian/* (same operator audience, same threat
model). When the program-aware path misbehaves for a specific pitcher,
flip them off in <5s without a redeploy.
"""
import os
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/admin/program-flag", tags=["admin"])

ADMIN_TOKEN_ENV = "GUARDIAN_ADMIN_TOKEN"


def _require_admin_token(token: str | None) -> None:
    expected = os.environ.get(ADMIN_TOKEN_ENV)
    if not expected:
        raise HTTPException(503, "admin token not configured")
    if not token or token != expected:
        raise HTTPException(401, "admin token invalid or missing")


@router.post("/{pitcher_id}/{value}")
async def set_pitcher_program_aware_flag(
    pitcher_id: str, value: str, request: Request,
    x_guardian_admin_token: str | None = Header(default=None),
):
    """Set pitcher_training_model.feature_flags.program_aware_plan_gen.

    value ∈ {"on", "off"}. Audited via system_observations sentinel-style row
    so the change shows up in the next 9am Guardian digest.
    """
    _require_admin_token(x_guardian_admin_token)
    if value not in ("on", "off"):
        raise HTTPException(422, "value must be 'on' or 'off'")
    from bot.services import db
    new_value = value == "on"
    db.set_feature_flag(pitcher_id, "program_aware_plan_gen", new_value)
    # Best-effort audit; do not fail the request on observation insert failure.
    try:
        from bot.services.system_guardian import insert_observation
        insert_observation({
            "category": "guardian_self",
            "severity": "info",
            "signature": "program_aware_flag_changed",
            "title": f"program_aware_plan_gen={value} for {pitcher_id}",
            "message": (
                f"Admin flipped program_aware_plan_gen={value} for {pitcher_id} "
                f"via /admin/program-flag/{pitcher_id}/{value}"
            ),
            "details": {"pitcher_id": pitcher_id, "new_value": new_value},
        })
    except Exception:  # pragma: no cover - audit best-effort
        pass
    return {"pitcher_id": pitcher_id, "program_aware_plan_gen": new_value}


@router.get("/{pitcher_id}")
async def get_pitcher_program_aware_flag(
    pitcher_id: str,
    x_guardian_admin_token: str | None = Header(default=None),
):
    _require_admin_token(x_guardian_admin_token)
    from bot.services import db
    return {
        "pitcher_id": pitcher_id,
        "program_aware_plan_gen": db.get_feature_flag(
            pitcher_id, "program_aware_plan_gen"
        ),
    }
```

```python
# bot/services/db.py — new helper
def set_feature_flag(pitcher_id: str, key: str, value: bool) -> None:
    """Set a single key inside pitcher_training_model.feature_flags.

    Read-modify-write because feature_flags is JSONB — we never overwrite
    other flags by accident. Raises KeyError if the pitcher row doesn't
    exist (no auto-create — caller should bootstrap explicitly).
    """
    model = get_training_model(pitcher_id)
    if not model:
        raise KeyError(f"no pitcher_training_model row for {pitcher_id}")
    flags = dict(model.get("feature_flags") or {})
    flags[key] = bool(value)
    update_training_model_partial(pitcher_id, {"feature_flags": flags})
```

**Mount the router** in `api/main.py`:

```python
# api/main.py — after existing router mounts
from api.admin_program_flag import router as admin_program_flag_router
app.include_router(admin_program_flag_router)
```

**Tests** (`tests/test_admin_program_flag_endpoint.py`):

```python
"""Plan 8 / A2 — admin program-flag endpoint."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GUARDIAN_ADMIN_TOKEN", "test-token-xyz")
    from api.main import app
    return TestClient(app)


def test_set_flag_on_writes_true_and_returns_state(client):
    from bot.services import db
    with patch.object(db, "set_feature_flag") as set_flag:
        resp = client.post(
            "/admin/program-flag/landon_brice/on",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "pitcher_id": "landon_brice",
        "program_aware_plan_gen": True,
    }
    set_flag.assert_called_once_with("landon_brice", "program_aware_plan_gen", True)


def test_set_flag_off_writes_false(client):
    from bot.services import db
    with patch.object(db, "set_feature_flag"):
        resp = client.post(
            "/admin/program-flag/landon_brice/off",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.json()["program_aware_plan_gen"] is False


def test_set_flag_invalid_value_422(client):
    resp = client.post(
        "/admin/program-flag/landon_brice/garbage",
        headers={"X-Guardian-Admin-Token": "test-token-xyz"},
    )
    assert resp.status_code == 422


def test_set_flag_requires_admin_token(client):
    resp = client.post("/admin/program-flag/landon_brice/on")
    assert resp.status_code == 401


def test_set_flag_503_when_admin_token_not_configured(monkeypatch):
    monkeypatch.delenv("GUARDIAN_ADMIN_TOKEN", raising=False)
    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/admin/program-flag/landon_brice/on",
        headers={"X-Guardian-Admin-Token": "anything"},
    )
    assert resp.status_code == 503


def test_get_flag_returns_current_value(client):
    from bot.services import db
    with patch.object(db, "get_feature_flag", return_value=True):
        resp = client.get(
            "/admin/program-flag/landon_brice",
            headers={"X-Guardian-Admin-Token": "test-token-xyz"},
        )
    assert resp.json()["program_aware_plan_gen"] is True
```

**Tests** (`tests/test_program_aware_logging.py`):

```python
"""Plan 8 / A2 — structured logging contract on program-aware compose."""
import pytest
import logging
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_compose_program_aware_plan_emits_structured_log(caplog):
    """Every compose call must emit a `program_aware_compose` event with the
    full schema so Guardian / health_monitor can aggregate them.
    """
    from bot.services import program_aware_planner

    # Minimal happy-path mock — real shape verification belongs to existing
    # test_program_aware_planner.py; here we only assert the log event.
    fake_plan = {
        "source": "program_prescribed",
        "source_reason": "llm_enriched",
        "narrative": "test",
        "lifting": {"exercises": [{"name": "squat"}]},
    }
    with patch.object(program_aware_planner, "generate_plan",
                      new=AsyncMock(return_value=fake_plan)), \
         caplog.at_level(logging.INFO):
        # ... call compose_program_aware_plan with a stub program ...
        # Implementer fills in the exact stub call shape based on the
        # signature in PR #29.
        pass

    events = [r for r in caplog.records
              if getattr(r, "event", None) == "program_aware_compose"]
    assert len(events) == 1
    ev = events[0]
    assert ev.pitcher_id  # populated
    assert ev.plan_source == "program_prescribed"
    assert ev.narrative_present is True
    assert ev.lifting_exercises_count == 1
```

**Steps:**
- [ ] Add structured logging to `compose_program_aware_plan` end
- [ ] Add `db.set_feature_flag` helper
- [ ] Create `api/admin_program_flag.py` with set + get endpoints
- [ ] Mount router in `api/main.py`
- [ ] Write 6 endpoint tests + 1 logging test
- [ ] `pytest -q` (from `pitcher_program_app/`) → expected ~840 passed
- [ ] Commit: `feat(plan-8/a2): program-aware structured logging + per-pitcher kill-switch`

**Acceptance:** `POST /admin/program-flag/{pitcher_id}/on|off` flips the per-pitcher flag in <1s. `GET /admin/program-flag/{pitcher_id}` reads current value. Wrong token → 401; unset env → 503. Every program-aware compose call emits a single `program_aware_compose` structured log event.

**Open question for executor:** does `system_observations` insert work cleanly inside a sync FastAPI handler? Plan 7 used `insert_observation` (sync) from health_monitor; A2 does the same. If it doesn't, fall back to `logger.info` only and document.

---

# Phase B — Schema cleanup

Phase B depends on A1 (saved_plans audit) but is otherwise independent of A2.

### Task B1: Drop `saved_plans` table + `pitcher_training_model.active_program_id` FK

**Gate:** A1 must report zero writes since 2026-04-30. If non-zero, fix the writer first.

**Files:**
- Create: `pitcher_program_app/scripts/migrations/030_drop_saved_plans.sql`
- Modify: `pitcher_program_app/bot/services/db.py` (remove `insert_saved_plan` + `get_saved_plans` + `get_saved_plan`)
- Modify: `pitcher_program_app/api/routes.py` (remove `POST /api/pitcher/{id}/plans` endpoint + the `GET /api/pitcher/{id}/plans/{plan_id}` reader + remove `save_plan` import)
- Modify: `pitcher_program_app/bot/services/context_manager.py` (remove `save_plan` if defined there)
- Modify: `pitcher_program_app/mini-app/src/App.jsx` (remove `/plans/:planId` route + `PlanDetail` import)
- Delete: `pitcher_program_app/mini-app/src/pages/PlanDetail.jsx`
- Modify: `pitcher_program_app/mini-app/src/api.js` (remove `savePlan` export)
- Update tests: remove `tests/test_saved_plans_deprecation.py`, drop any other saved_plans test
- Apply migration via Supabase MCP

**Approach:** Two artifacts.

**(1) The migration** drops the `active_program_id` FK first (it references `training_programs` — also orphan since 2026-04-10), then drops the `saved_plans` table:

```sql
-- Plan 8 / B1 — hard-drop saved_plans (Plan 7 A15 deprecated; A1 verified
-- zero writes since 2026-04-30) + pitcher_training_model.active_program_id FK.
--
-- Idempotent: IF EXISTS guards every drop.
--
-- BEFORE running this migration, A1's verify_saved_plans_deprecated.py
-- must report exit 0. The PR body should include the script output.

BEGIN;

-- (1) Drop the FK on pitcher_training_model.active_program_id
--     The column references training_programs(id) (orphan table since 2026-04-10).
--     Column itself stays — dropping it cleanly requires checking for any
--     legacy reads, deferred to a separate cleanup commit.
ALTER TABLE pitcher_training_model
  DROP CONSTRAINT IF EXISTS pitcher_training_model_active_program_id_fkey;

-- (2) Drop the saved_plans table
DROP TABLE IF EXISTS saved_plans CASCADE;

COMMIT;
```

**(2) Code removals.** Strip every reference. The mini-app's `/plans/:planId` route + `PlanDetail.jsx` was the only consumer of the `GET /api/pitcher/{id}/plans/{plan_id}` reader; both go. Plan 7 B16 already removed the mini-app save-button caller; the last server-side caller is the custom-plan generator path at `api/routes.py:1257` (the `save_plan` call after generation). Remove that call.

**Steps:**
- [ ] Verify A1 output is exit 0 (capture script output in PR body)
- [ ] Apply migration `030_drop_saved_plans.sql` via Supabase MCP
- [ ] Verify post-apply: `SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='saved_plans')` → false
- [ ] Remove `insert_saved_plan` + `get_saved_plans` + `get_saved_plan` from `db.py`
- [ ] Remove `save_plan` from `context_manager.py` (if defined there)
- [ ] Remove `POST /api/pitcher/{id}/plans` + the saved-plan reader endpoint from `routes.py`
- [ ] Remove the `save_plan` call inside the custom-plan generator path at `routes.py:1257`
- [ ] Remove `/plans/:planId` route + `PlanDetail` import from mini-app `App.jsx`
- [ ] Delete `mini-app/src/pages/PlanDetail.jsx`
- [ ] Remove `savePlan` export from `mini-app/src/api.js`
- [ ] Delete `tests/test_saved_plans_deprecation.py`
- [ ] Run `grep -rn "saved_plans\|save_plan\|PlanDetail" pitcher_program_app/` and remove anything that's truly dead. Comments referring to the historical table for context may stay if rare.
- [ ] `pytest -q` → expected suite stays ≥ 832 passed (removed ~2 tests + lots of dead code)
- [ ] `cd mini-app && npm run test:run` → still 68 passed (PlanDetail wasn't under vitest)
- [ ] Commit: `feat(plan-8/b1): drop saved_plans table + dead code`

**Acceptance:** Table gone in Supabase. `grep -rn "saved_plans" pitcher_program_app/ --include='*.py' --include='*.js' --include='*.jsx'` returns ≤ 5 hits (CLAUDE.md historical references only). Mini-app `/plans/anything` route 404s in dev mode (route deleted).

**Risk:** Any pitcher who has a Telegram chat history containing an `inline_keyboard` button URL pointing at `/plans/<id>` will get a 404 if they tap it. Acceptable — those buttons were generated months ago and have no functional value today (the linked plan was a frozen snapshot, not a live training plan).

---

### Task B2: Phase vocabulary schema migration

**Files:**
- Create: `pitcher_program_app/scripts/migrations/031_template_phase_key.sql`
- Modify: `pitcher_program_app/bot/services/team_phase_split_compat.py` (if exists — find the home of phase translation logic on the backend)
- Modify: `pitcher_program_app/coach-app/src/components/phases/PhaseTimeline.jsx` (use the new column directly; drop `phaseToTemplatePhaseIds` import)
- Delete (if unused after the above): `pitcher_program_app/coach-app/src/components/phases/phaseToTemplatePhaseIds.js` (or wherever the helper lives)
- Modify: tests that reference the deleted helper

**Approach:** Three steps.

**(1) Schema migration** adds the canonical column + backfills the 5 existing UChicago rows:

```sql
-- Plan 8 / B2 — converge the two phase vocabularies.
-- training_phase_blocks.phase_name is freeform display text; block_library.compatible_phases
-- is a fixed 4-value enum. Plan 7 C5 bridged them client-side via phaseToTemplatePhaseIds().
-- This migration makes the canonical token authoritative at write time so the bridge dies.

BEGIN;

-- (1) Add the column (nullable; backfill below; future writers must populate).
ALTER TABLE training_phase_blocks
  ADD COLUMN IF NOT EXISTS template_phase_key text;

-- (2) Constrain to the canonical 4-value enum used by block_library.compatible_phases.
--     NULL allowed during transition; once all rows are non-null we can NOT NULL it
--     in a follow-up. Skip the NOT NULL for v1 to keep this migration idempotent.
ALTER TABLE training_phase_blocks
  DROP CONSTRAINT IF EXISTS training_phase_blocks_template_phase_key_check;
ALTER TABLE training_phase_blocks
  ADD CONSTRAINT training_phase_blocks_template_phase_key_check
  CHECK (
    template_phase_key IS NULL
    OR template_phase_key IN ('off_season','preseason','in_season','in_season_active')
  );

-- (3) Backfill the 5 existing rows via the same mapping the Plan 7 C5 helper used.
UPDATE training_phase_blocks
   SET template_phase_key = CASE
     WHEN phase_name ~* 'in[-\s]?season'                       THEN 'in_season'
     WHEN phase_name ~* 'preseason'                            THEN 'preseason'
     WHEN phase_name ~* 'postseason|off[-\s]?season'           THEN 'off_season'
     WHEN emphasis = 'maintenance'                             THEN 'in_season'
     WHEN emphasis = 'power'                                   THEN 'preseason'
     WHEN emphasis IN ('hypertrophy','strength','gpp')         THEN 'off_season'
     ELSE NULL
   END
 WHERE template_phase_key IS NULL;

COMMIT;
```

After apply: verify `SELECT phase_name, emphasis, template_phase_key FROM training_phase_blocks` shows the 5 rows with non-null keys.

**(2) Frontend cutover.** `PhaseTimeline.jsx` currently calls `phaseToTemplatePhaseIds()` per row. Replace with direct read of `row.template_phase_key` (single value, not a list). For the one phase that maps to TWO keys (`in_season` → `[in_season, in_season_active]`), keep that one-off in the matcher (a second migration of the data would need a UX-level decision about which `in_season_*` value a coach picks; for v1 the regex still rules in-season templates).

Actually — re-thinking. Since `in_season` template_phase_key won't match an `in_season_active` block_library template via exact equality, we either (a) widen the column to be an array (`text[]`) so a single phase can correspond to two enum values, or (b) keep the simple TEXT + lookup `compatible_phases CONTAINS template_phase_key OR (template_phase_key = 'in_season' AND 'in_season_active' = ANY(compatible_phases))` — gross.

**Cleaner**: make the column `text[]` (matching the type of `block_library.compatible_phases`):

```sql
-- (Revised) — column type is text[] so a single phase row can map to
-- multiple compatible_phases enum values when the team's phase semantics
-- straddle two template buckets (e.g. "In-Season" → both 'in_season'
-- and 'in_season_active').
ALTER TABLE training_phase_blocks
  ADD COLUMN IF NOT EXISTS template_phase_keys text[];

UPDATE training_phase_blocks
   SET template_phase_keys = CASE
     WHEN phase_name ~* 'in[-\s]?season'                       THEN ARRAY['in_season','in_season_active']
     WHEN phase_name ~* 'preseason'                            THEN ARRAY['preseason']
     WHEN phase_name ~* 'postseason|off[-\s]?season'           THEN ARRAY['off_season']
     WHEN emphasis = 'maintenance'                             THEN ARRAY['in_season','in_season_active']
     WHEN emphasis = 'power'                                   THEN ARRAY['preseason']
     WHEN emphasis IN ('hypertrophy','strength','gpp')         THEN ARRAY['off_season']
     ELSE ARRAY[]::text[]
   END
 WHERE template_phase_keys IS NULL;
```

Use that shape. Plural name, `text[]`.

**(3) Backend update.** `team_scope.py` or wherever the roster row is built — surface `template_phase_keys` so coach-app reads it without a second hop.

Frontend:

```jsx
// coach-app/src/components/phases/PhaseTimeline.jsx
// BEFORE
const templatePhaseIds = phaseToTemplatePhaseIds(phase);

// AFTER
const templatePhaseIds = phase.template_phase_keys || [];
```

Then drop `phaseToTemplatePhaseIds` import + delete the helper file + remove its test file.

**Steps:**
- [ ] Apply migration `031_template_phase_keys.sql` (text[] flavor) via Supabase MCP
- [ ] Verify 5 rows all have non-empty `template_phase_keys` array
- [ ] Surface `template_phase_keys` in the team/phases payload (likely `team_scope.py` or wherever PhaseTimeline data is read)
- [ ] Update PhaseTimeline.jsx to read `phase.template_phase_keys` directly
- [ ] Drop `phaseToTemplatePhaseIds()` import + delete the helper file + delete its tests
- [ ] `pytest -q` → expected suite unchanged or +1 (depends on backend test add)
- [ ] `cd coach-app && npm run test:run` → expected 191 - 4 (helper tests deleted) = 187 passed
- [ ] Commit: `feat(plan-8/b2): canonical template_phase_keys column + drop client-side bridge`

**Acceptance:** `SELECT phase_name, template_phase_keys FROM training_phase_blocks` shows all 5 rows populated. `phaseToTemplatePhaseIds()` helper gone. Phases page chips render correctly (regression: pull up `/phases` in dev and verify each phase still shows its templates).

**Open question for executor:** is there a Python-side caller of the phase mapping that also needs updating? Grep `pitcher_program_app/` for `compatible_phases` + `template_phase_key` and verify. Most likely there isn't — the bridge was UI-only — but worth a 30-second check.

---

# Phase C — Coach-app feature work

Phase C is parallel-safe after Phase A lands. Three tasks; each independent of the others.

### Task C1: Drift insight Archive / Accept CTAs

**Files:**
- Modify: `pitcher_program_app/coach-app/src/components/insights/InsightCard.jsx`
- Modify: `pitcher_program_app/coach-app/src/api.js` (add `archiveProgramByInsight` + `dismissInsight`)
- Modify: `pitcher_program_app/api/coach_routes.py` (add `POST /api/coach/insights/{insight_id}/accept` + `POST /api/coach/insights/{insight_id}/dismiss`)
- Modify: `pitcher_program_app/bot/services/db.py` (add `update_coach_suggestion_status`)
- Modify: `pitcher_program_app/coach-app/src/components/insights/__tests__/InsightCard.test.jsx`
- Create: `pitcher_program_app/tests/test_coach_insights_action_endpoints.py`

**Approach:** Plan 7 C6 shipped no-op Archive / Accept buttons on `program_drift` insights. C1 wires them to real backend actions:

- **Archive program** → calls existing `POST /api/coach/programs/{program_id}/archive` (already exists from Plan 2 + Plan 7 coach-mirror). On success, also dismiss the insight (status='dismissed'). This is the "yes, archive and rebuild" decision.
- **Accept new pace** → DOES NOT archive the program. Just dismisses the insight (status='accepted'). The program continues at its drifted pace. Future drift insights for the SAME program are suppressed for 14 days (a new `accepted_at` timestamp on `coach_suggestions` + a check in A4's dedup logic).

New endpoints:

```python
# api/coach_routes.py
class InsightActionRequest(_BaseModel):
    action: str = _Field(..., pattern="^(accept|dismiss)$")


@coach_router.post("/insights/{insight_id}/action")
async def coach_post_insight_action(insight_id: str, req: InsightActionRequest, request: Request):
    """Plan 8 / C1 — accept or dismiss an insight row.

    'accept' = "yes, this is the new normal" — sets status='accepted' and
    accepted_at=now. A4's dedup logic suppresses re-firing the same signature
    for 14 days when accepted_at is recent.

    'dismiss' = "I've seen it, do whatever" — sets status='dismissed'.
    The insight may re-fire tomorrow if the underlying condition persists.

    Archiving a program is a SEPARATE action — coach calls the existing
    /programs/{program_id}/archive endpoint, then dismisses this insight.
    Kept separate so a coach can dismiss without archiving and vice versa.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    suggestion = _db.get_coach_suggestion(insight_id)
    if not suggestion:
        raise HTTPException(404, "insight not found")
    if suggestion.get("team_id") != team_id:
        raise HTTPException(404, "insight not found")
    new_status = "accepted" if req.action == "accept" else "dismissed"
    updated = _db.update_coach_suggestion_status(
        insight_id,
        status=new_status,
        accepted_at=datetime.now(timezone.utc).isoformat() if req.action == "accept" else None,
    )
    # Audit via existing coach_actions table
    _db.insert_coach_action({
        "coach_id": coach_id,
        "pitcher_id": suggestion.get("pitcher_id"),
        "action_type": f"insight_{new_status}",
        "metadata": {
            "team_id": team_id,
            "insight_id": insight_id,
            "category": suggestion.get("category"),
        },
    })
    return {"insight": updated}
```

Update A4's dedup check to skip recently-accepted insights:

```python
# bot/services/db.py — modify suggestion_exists_for_today
def suggestion_exists_for_today(pitcher_id, suggestion_type, ...) -> bool:
    """... existing docstring ...

    Plan 8 / C1: also returns True if a matching insight was accepted in
    the last 14 days. 'accepted' means "coach acknowledged this is the
    new normal" — don't re-fire daily noise.
    """
    # ... existing logic ...
    # Additionally check for accepted insights within 14 days
    accepted_cutoff = (datetime.now(CHICAGO_TZ).date() - timedelta(days=14)).isoformat()
    accepted_q = (get_client().table("coach_suggestions")
                  .select("id")
                  .eq("category", suggestion_type)
                  .eq("status", "accepted")
                  .gte("accepted_at", accepted_cutoff))
    if pitcher_id:
        accepted_q = accepted_q.eq("pitcher_id", pitcher_id)
    if context_program_id:
        # ... same proposed_action filter as today's logic ...
    accepted_resp = accepted_q.execute()
    if accepted_resp.data:
        return True
    return False
```

Schema: `coach_suggestions` needs an `accepted_at` timestamptz column. Add via migration:

```sql
-- Plan 8 / C1 — track when a coach accepted an insight to suppress re-firing.
ALTER TABLE coach_suggestions
  ADD COLUMN IF NOT EXISTS accepted_at timestamptz;
```

Frontend: wire the existing C6 buttons to actual handlers.

**Steps:**
- [ ] Apply migration `032_coach_suggestions_accepted_at.sql` via Supabase MCP
- [ ] Add `db.update_coach_suggestion_status` + `db.get_coach_suggestion` helpers
- [ ] Add `POST /api/coach/insights/{id}/action` endpoint
- [ ] Update `suggestion_exists_for_today` to honor `accepted_at` (14d suppression)
- [ ] Add `archiveProgramByInsight` (composite: archive program + dismiss insight) and `actOnInsight(id, action)` to coach-app api.js
- [ ] Wire C6's Archive/Accept buttons in `InsightCard.jsx`
- [ ] +4 backend tests (endpoint accept / dismiss / 404 cross-team / dedup skips accepted-recent)
- [ ] +3 coach-app vitest tests (click handlers + api calls + suppress-on-accept)
- [ ] `pytest -q` → expected ~847 passed
- [ ] `cd coach-app && npm run test:run` → expected ~190 passed
- [ ] Commit: `feat(plan-8/c1): drift insight Archive/Accept CTAs wired`

**Acceptance:** Coach taps Archive → program archived + insight gone from feed. Coach taps Accept → insight gone from feed + does NOT re-fire on the next 9am digest for 14 days. Audit row in `coach_actions`.

---

### Task C2: A4 insight body LLM polish

**Files:**
- Modify: `pitcher_program_app/bot/services/coach_insights.py` (add `polish_insight_body` async wrapper)
- Modify: `pitcher_program_app/bot/services/health_monitor.py` (call polish before insert)
- Modify: `pitcher_program_app/bot/prompts/insight_drift.md` (now actually used)
- Modify: `pitcher_program_app/bot/prompts/insight_mismatch.md`
- Modify: `pitcher_program_app/bot/prompts/insight_completion.md`
- Create: `pitcher_program_app/tests/test_coach_insights_polish.py`

**Approach:** Per L5, LLM polish only rewrites the `reasoning` body text — the rule-based gates + thresholds + insight selection unchanged.

```python
# bot/services/coach_insights.py
async def polish_insight_body(suggestion: dict, *, timeout: int = 30) -> dict:
    """Run a tight LLM polish over the rule-based body. Returns the suggestion
    dict with `reasoning` rewritten (more natural, same facts). Falls back to
    the original on timeout/error so the digest still ships.

    Polish is a single deterministic LLM call per insight, ~150 tokens out.
    Budget tight: 30s timeout matches A11.
    """
    from bot.services.llm import call_llm, load_prompt
    category = suggestion.get("category")
    prompt_file = {
        "program_drift": "insight_drift.md",
        "program_flag_mismatch": "insight_mismatch.md",
        "team_program_lagging": "insight_completion.md",
    }.get(category)
    if not prompt_file:
        return suggestion  # Unknown category — leave alone.

    system = load_prompt(prompt_file)
    user = (
        f"Title: {suggestion.get('title')}\n"
        f"Current body: {suggestion.get('reasoning')}\n"
        f"Facts (JSON): {suggestion.get('proposed_action')}\n\n"
        "Rewrite the body in 2-3 sentences. Same facts. More natural. "
        "Output ONLY the rewritten body — no quotes, no preamble."
    )
    try:
        polished = await call_llm(system_prompt=system, user_message=user,
                                  history=[], timeout=timeout)
    except Exception:
        logger.warning("insight polish failed; keeping rule-based body",
                       extra={"category": category, "insight_title": suggestion.get("title")},
                       exc_info=True)
        return suggestion
    if not polished or not polished.strip():
        return suggestion
    out = dict(suggestion)
    out["reasoning"] = polished.strip()
    out.setdefault("proposed_action", {})["polished"] = True  # audit flag
    return out
```

Wire into `_generate_coach_insights_for_team` so polish happens before insert:

```python
# bot/services/health_monitor.py — inside the loop, after generator returns
sug = coach_insights.generate_drift_insight_for_program(p)
if sug and not _db.suggestion_exists_for_today(...):
    sug["team_id"] = team_id
    sug = await coach_insights.polish_insight_body(sug)  # NEW
    _db.insert_coach_suggestion(sug)
```

Three prompt files updated from "Plan 8 placeholder" markers to real prompts. Each ~10 lines, locking the polish style.

**Steps:**
- [ ] Add `polish_insight_body` to coach_insights.py
- [ ] Wire it into the digest loop (3 insertion sites — one per category)
- [ ] Replace 3 placeholder prompt files with real polish prompts
- [ ] +4 tests (polish success, LLM timeout fallback, LLM empty fallback, unknown category passthrough)
- [ ] `pytest -q` → expected ~851 passed
- [ ] Commit: `feat(plan-8/c2): A4 insight body LLM polish`

**Acceptance:** Insights generated by the 9am digest now have natural-sounding bodies. On LLM failure, the rule-based body still ships. Audit flag `proposed_action.polished=true` lets Plan 9 measure adoption.

**Cost note:** 3 categories × ~12 active pitchers × 1 polish call/day = ~36 LLM calls/day max. Well inside budget.

---

### Task C3: Coach-authored research doc workflow (attach-existing)

**Files:**
- Modify: `pitcher_program_app/api/coach_routes.py` (add `GET /api/coach/research-docs` + `PATCH /api/coach/block-library/{template_id}/research-docs`)
- Modify: `pitcher_program_app/bot/services/db.py` (add `list_research_docs` + `update_template_research_doc_ids`)
- Create: `pitcher_program_app/coach-app/src/components/team-programs/TemplateResearchEditor.jsx`
- Modify: `pitcher_program_app/coach-app/src/pages/TeamPrograms.jsx` (add "Edit" affordance on each Library row that opens the editor)
- Modify: `pitcher_program_app/coach-app/src/api.js` (add `fetchResearchDocs` + `patchTemplateResearchDocs`)
- Create: `pitcher_program_app/tests/test_coach_research_doc_endpoints.py`
- Create: `pitcher_program_app/coach-app/src/components/team-programs/__tests__/TemplateResearchEditor.test.jsx`

**Approach:** Per L6, v1 is **attach-existing**, not author-new. The coach sees the existing `data/knowledge/research/*.md` docs (~14 of them) and can pick which to attach to a template.

```python
# bot/services/db.py
def list_research_docs() -> list[dict]:
    """Return all research docs metadata: {id, title, summary, applies_to,
    priority}. Reads from disk — research docs are git-checked-in markdown
    with YAML frontmatter, not Supabase rows.
    """
    from bot.services.research_resolver import _list_all_docs  # reuse loader
    docs = _list_all_docs()
    return [
        {
            "id": d.get("id"),
            "title": d.get("title", d.get("id")),
            "summary": d.get("summary", ""),
            "applies_to": d.get("applies_to", []),
            "priority": d.get("priority", "standard"),
        }
        for d in docs
    ]


def update_template_research_doc_ids(template_id: str, doc_ids: list[str]) -> dict:
    """Update block_library.research_doc_ids for a template. Returns the
    updated row. Raises KeyError if template doesn't exist.
    """
    resp = (get_client().table("block_library")
            .update({"research_doc_ids": doc_ids})
            .eq("block_template_id", template_id)
            .execute())
    if not resp.data:
        raise KeyError(f"template not found: {template_id}")
    return resp.data[0]
```

```python
# api/coach_routes.py
@coach_router.get("/research-docs")
async def coach_get_research_docs(request: Request):
    """Plan 8 / C3 — list all available research docs the coach can attach to templates."""
    await require_coach_auth(request)
    return {"docs": _db.list_research_docs()}


class TemplateResearchDocsRequest(_BaseModel):
    research_doc_ids: list[str]


@coach_router.patch("/block-library/{template_id}/research-docs")
async def coach_patch_template_research_docs(
    template_id: str, req: TemplateResearchDocsRequest, request: Request,
):
    """Plan 8 / C3 — set block_library.research_doc_ids for a template.

    Coaches scoped: any coach on any team can edit any template right now
    (templates are global). Plan 9 may add team-ownership for templates;
    until then this is intentionally permissive among coaches.
    """
    await require_coach_auth(request)
    coach_id = request.state.coach_id
    # Validate that every doc_id resolves
    valid_ids = {d["id"] for d in _db.list_research_docs()}
    bad = [i for i in req.research_doc_ids if i not in valid_ids]
    if bad:
        raise HTTPException(422, f"unknown research doc ids: {bad}")
    try:
        updated = _db.update_template_research_doc_ids(template_id, req.research_doc_ids)
    except KeyError:
        raise HTTPException(404, "template not found")
    _db.insert_coach_action({
        "coach_id": coach_id,
        "action_type": "template_research_docs_edit",
        "metadata": {"template_id": template_id, "doc_ids": req.research_doc_ids},
    })
    return {"template": updated}
```

Frontend `TemplateResearchEditor`: dual-column picker (available docs left, attached docs right, drag/click to move). Lives inside a small modal opened from each Library row in TeamPrograms. Existing brand tokens.

**Steps:**
- [ ] Add db helpers (`list_research_docs`, `update_template_research_doc_ids`)
- [ ] Add 2 endpoints + 5 backend tests (list, patch happy, 422 unknown id, 404 template, audit row)
- [ ] Build `TemplateResearchEditor.jsx` component
- [ ] Wire "Edit research" button on each TeamPrograms Library row
- [ ] +3 vitest tests
- [ ] `pytest -q` → expected ~856 passed
- [ ] `cd coach-app && npm run test:run` → expected ~193 passed
- [ ] Commit: `feat(plan-8/c3): coach attaches research docs to templates`

**Acceptance:** Coach opens TeamPrograms → Library section → Edit Research → picks 2 docs → saves. Next time anyone runs a build interview on that template, the picked docs appear in the Preview research citations.

**Out of scope (per L6):** authoring new research docs, editing existing ones, deleting docs, team-ownership of templates.

---

# Phase D — Roster rollout + verification + tag

Phase D depends on Phases A + B + C all green. This is the live-fire moment.

### Task D1: Flip `program_aware_plan_gen` for all pitchers

**Files:**
- Create: `pitcher_program_app/scripts/enable_program_aware_for_team.py`

**Approach:** Script that sets `feature_flags.program_aware_plan_gen=true` for every pitcher on a team. Uses A2's `db.set_feature_flag` helper. Idempotent.

```python
# scripts/enable_program_aware_for_team.py
"""Plan 8 / D1 — flip program_aware_plan_gen=true for every pitcher on a team.

Idempotent. Reads the roster from `pitchers` table filtered by team_id.
Prints a per-pitcher status line. Exit 0 on success, 1 if any pitcher failed.
"""
import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--team-id", default="uchicago_baseball")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would change without writing")
    args = p.parse_args()

    from bot.services import db
    roster = [
        row for row in db.list_pitchers()
        if row.get("team_id") == args.team_id
    ]
    if not roster:
        print(f"No pitchers found for team {args.team_id}")
        return 1

    failures = []
    for pitcher in roster:
        pid = pitcher["pitcher_id"]
        current = db.get_feature_flag(pid, "program_aware_plan_gen")
        if current is True:
            print(f"  {pid}: already ON — skip")
            continue
        if args.dry_run:
            print(f"  {pid}: WOULD set ON (currently {current})")
            continue
        try:
            db.set_feature_flag(pid, "program_aware_plan_gen", True)
            print(f"  {pid}: set ON")
        except Exception as exc:
            print(f"  {pid}: FAILED — {exc}")
            failures.append(pid)

    print(f"\nDone. {len(roster)} pitchers processed, {len(failures)} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Steps:**
- [ ] Create the script
- [ ] Dry-run first: `python -m scripts.enable_program_aware_for_team --dry-run`
- [ ] Verify dry-run output is sensible
- [ ] Real run: `python -m scripts.enable_program_aware_for_team`
- [ ] Verify via Supabase: `SELECT pitcher_id, feature_flags->'program_aware_plan_gen' FROM pitcher_training_model` shows `true` for all roster pitchers
- [ ] Capture the script output in the PR body
- [ ] Commit the script: `feat(plan-8/d1): roster enablement script`

**Acceptance:** All 12 UChicago pitchers have `feature_flags.program_aware_plan_gen=true` in `pitcher_training_model`.

**Rollback:** Per L7, if anything breaks on a per-pitcher basis, use the A2 admin endpoint:

```
curl -X POST -H "X-Guardian-Admin-Token: $TOKEN" \
  https://baseball-production-9d28.up.railway.app/admin/program-flag/{pitcher_id}/off
```

To roll back the entire team:

```
python -m scripts.enable_program_aware_for_team --team-id uchicago_baseball --revert
```

(Add `--revert` flag to the script if not already present — sets `False` instead of `True`.)

---

### Task D2: 1-week monitoring + canary metric in 9am digest

**Files:**
- Modify: `pitcher_program_app/bot/services/health_monitor.py`
- Modify: `pitcher_program_app/bot/services/system_guardian/collectors/existing_health.py` (add Phase 1 metric)
- Create: `pitcher_program_app/tests/test_program_aware_canary_metric.py`

**Approach:** Read the structured logs / DB rows from A2's logging contract and compute a daily "program-path enrichment ratio" — % of pitcher check-ins routed through `compose_program_aware_plan` that produced a `program_prescribed` source (not a fallback to `python_fallback` or `llm_enriched` via the legacy path).

```python
# bot/services/health_monitor.py — add new helper
def compute_program_aware_canary(days: int = 7) -> dict:
    """Plan 8 / D2 — canary metric for the program-aware rollout.

    Reads daily_entries.plan_generated.source over the last N days. Returns
    {total_program_path_attempts, successful_program_prescribed, rate}.
    `rate < 0.8` means something is regressing — the existing 9am digest
    should call this out.

    Sourced from daily_entries because every successful program-aware
    compose writes source='program_prescribed' (PR #29's fix promotes
    source explicitly). Legacy fallbacks write source='python_fallback'
    or 'llm_enriched' — those count as ATTEMPTS that fell through.
    """
    from bot.services import db
    cutoff = (datetime.now(CHICAGO_TZ).date() - timedelta(days=days)).isoformat()
    # Only count pitchers with the flag ON
    flag_on_ids = [
        p["pitcher_id"] for p in db.list_pitchers()
        if db.get_feature_flag(p["pitcher_id"], "program_aware_plan_gen")
    ]
    if not flag_on_ids:
        return {"total": 0, "program_prescribed": 0, "rate": None}
    rows = (db.get_client().table("daily_entries")
            .select("plan_generated")
            .in_("pitcher_id", flag_on_ids)
            .gte("date", cutoff)
            .execute()).data or []
    total = len(rows)
    prescribed = sum(
        1 for r in rows
        if (r.get("plan_generated") or {}).get("source") == "program_prescribed"
    )
    rate = prescribed / total if total else None
    return {"total": total, "program_prescribed": prescribed, "rate": rate}
```

Wire into `format_digest_message`:

```python
# After existing health summary
canary = compute_program_aware_canary(days=7)
if canary["total"] > 0:
    rate = canary["rate"]
    msg += f"\n📊 Program-path canary (7d): {canary['program_prescribed']}/{canary['total']} → {rate:.0%}"
    if rate < 0.8:
        msg += " ⚠️ regressing"
```

**Steps:**
- [ ] Add `compute_program_aware_canary` to health_monitor
- [ ] Wire into the 9am digest message
- [ ] +3 tests (zero pitchers flagged → None rate, all pitchers flagged + all prescribed → 1.0 rate, mixed sources → correct ratio)
- [ ] `pytest -q` → expected ~859 passed
- [ ] Commit: `feat(plan-8/d2): program-aware canary metric in 9am digest`

**Acceptance:** Next 9am digest after rollout shows the program-path canary line. If rate drops below 80% on any single morning, the digest visually flags it.

**Monitoring window:** 1 calendar week of digests after D1 fires. If the canary holds ≥80% for 7 days, the rollout is considered stable. If it dips, dispatch a fix (likely another structural gap like PR #29 caught).

---

### Task D3: Update CLAUDE.md + tag

**Files:**
- Modify: `CLAUDE.md` (masthead row + What's Next refresh)

**Steps:**
- [ ] Add Plan 8 row to CLAUDE.md Completed Phases table (between Plan 7 and Plan 6 Phase B)
- [ ] Update masthead "Sprint status" line to include Plan 8
- [ ] Trim "What's Next" items: drop saved_plans drop (done), drop phase vocab convergence (done), drop drift CTA wiring (done), drop A4 LLM polish (done), drop coach-authored research workflow (done in attach-form). Add Plan 9 backlog inline (prohibited-day, authoring research workflow, brand-shell package, etc.).
- [ ] Commit + push docs
- [ ] Open PR titled `Program Builder v1 Cleanup + Roster Rollout (Plan 8)`
- [ ] After 1-week monitoring window passes per D2, tag:
  ```
  git tag program-builder-v1-cleanup-complete
  git push origin program-builder-v1-cleanup-complete
  ```

---

## Acceptance Criteria (top-level)

1. ✅ `saved_plans` table dropped from Supabase; mini-app `/plans/:planId` route gone; no callers of `insert_saved_plan` remain (B1, gated by A1).
2. ✅ `training_phase_blocks.template_phase_keys` column populated for all rows; `phaseToTemplatePhaseIds()` helper deleted (B2).
3. ✅ Drift insight Archive button archives the program + dismisses the insight; Accept button suppresses the insight for 14 days; both write audit rows (C1).
4. ✅ A4 insight bodies are LLM-polished; LLM failure falls back to rule-based body (C2).
5. ✅ Coach can attach existing research docs to a template via TeamPrograms Library Edit Research modal (C3).
6. ✅ `program_aware_plan_gen` flag is `true` for every UChicago pitcher (D1).
7. ✅ Per-pitcher kill-switch (`POST /admin/program-flag/{id}/{on|off}`) works (A2).
8. ✅ 9am digest shows the program-path canary metric; ratio holds ≥80% for 7 consecutive days post-D1 (D2).
9. ✅ All test suites green; tag `program-builder-v1-cleanup-complete` pushed after monitoring window.

## Open questions to revisit during execution

- **A2 audit observation insertion**: does `system_observations` insert work cleanly inside a sync FastAPI handler? If not, fall back to `logger.info` and document.
- **B2 `template_phase_keys` type**: confirmed `text[]` (plural). Verify the migration's CHECK constraint syntax for array element validation — PostgreSQL doesn't natively support per-element CHECK constraints; may need to use a domain or skip the constraint and validate in application code.
- **B2 backend caller of `compatible_phases`**: 30-second grep — is there a non-frontend caller of the bridge? Almost certainly not but verify.
- **C1 14-day suppression window**: locked at 14 days. If a coach genuinely wants to know about drift sooner, they can manually dismiss + re-accept after the suppression expires. Tune in Plan 9 if 14d feels wrong in practice.
- **C2 LLM cost ceiling**: ~36 calls/day current cap. If we onboard a second team in v2, multiply by team count. Worth a re-think at 100+ calls/day.
- **D1 rollout signal**: do we flip everyone simultaneously (script-driven) or stagger (manual via the admin endpoint over a day)? Script-driven is faster but means all 12 pitchers' next check-in is the live-fire test. Staggered means we catch a per-pitcher bug before it scales. Plan brief says full-roster — interpreting as "in one operation."

## Branch + push strategy

Plan 8 lands as **one PR** (matching Plans 6 + 7). Approximate size: ~2K LOC across backend + coach-app + scripts. No new env vars. Migrations: 3 (drop `saved_plans`, add `template_phase_keys`, add `accepted_at`) — apply via Supabase MCP in order before opening the PR.

**Rollout cadence after merge:** D1 fires immediately after merge. D2 monitoring window runs for 7 days post-merge before the tag is pushed. If the canary dips, dispatch a follow-up fix on a separate branch (don't bake into the Plan 8 commit).
