# Program Builder v1 — Plan 7: Coach Complete + Pitcher Polish

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking. This plan follows the existing `docs/superpowers/plans/` repository style: per-task files+approach+acceptance, with concrete code/test code stubs on the tricky tasks. Hard TDD step-by-step expansion can be requested during execution.

**Goal:** Ship the coach half of Program Builder v1 and the remaining pitcher-side polish — coaches can build programs (for individuals or teams), surface program state on every coach screen, see AI-generated drift/mismatch/team-completion insights, and override phase per-pitcher; pitchers get natural-language goal interpretation, lifting templates, browse-templates surface, scheduled-throw anchors, Telegram BackButton wiring, and `saved_plans` soft-deprecation. Tag `program-builder-v1-complete` closes Program Builder v1.

**Architecture:** Four phases (Phase A = coach backend + pitcher backend fixes; Phase B = mini-app polish parallel-safe with late Phase A; Phase C = coach-app UX; Phase D = verification + tag). Phase A must be 100% green before Phase C consumers ship. **BuilderSlideOver is extracted from mini-app into a shared workspace location so the coach-app can reuse it with an `interview_mode` prop** — single component, three Socratic prompt variants the backend already supports (`personalize` / `team_personalize` / `authoring`). Coach-app Phase 1 surfacing (category scores 3-stat row + flagged-feed copy) folded into Phase C as task C7 since we're already in PlayerSlideOver for C2.

**Tech Stack:** Python 3.11 / FastAPI (backend); React 18 / Vite / Tailwind / Vitest + RTL (mini-app); React 19 / Vite / Tailwind v4 / Vitest + RTL (coach-app); Supabase Postgres; DeepSeek LLM. Builds on tag `program-builder-v1-pitcher-complete`.

---

## 2026-05-14 — Locked decisions (from Plan 7 brainstorm)

| # | Decision | Why |
|---|---|---|
| L1 | **Plan 7 anchor = ship coach-side end-to-end + fold pitcher polish in** | The whole point of Program Builder v1 is "pitcher + coach loop closes" — Plan 6 pitcher-only is half-built without coach surfaces. Don't drag the closing scope into Plan 8. |
| L2 | **Coach build UX = reuse BuilderSlideOver with `interview_mode` prop** | Backend already supports the 3 modes (`personalize` / `team_personalize` / `authoring`). One component, one set of tests, no duplicated state machine. Coach picks "who is this for?" as a State-A0 sub-step. |
| L3 | **Fold coach-app Phase 1 surfacing INTO Plan 7 (task C7)** | We're already in PlayerSlideOver for C2 (Programs tab) — adding the 3-stat row for category scores costs ~30 min and finally surfaces the triage subsystem we shipped in 04-21. |
| L4 | **Extract BuilderSlideOver to `shared/builder/` workspace location** | Coach-app needs the same component; copying breeds drift. The repo already has `shared/parseBrief.js` precedent (imported via `@shared/parseBrief.js` Vite alias in both apps). |
| L5 | **A4 coach insights run on the existing 9am admin digest schedule** | No new scheduler. Reuses the proven daily cadence. Insights write to existing `coach_suggestions` table with the new `insight_type` values surfaced on Insights page (C6). |
| L6 | **LLM goal interpreter (A11) on a 60-second timeout** | Tighter than `LLM_REVIEW_TIMEOUT=45s` because this fires synchronously on a Continue tap, not async during check-in. Fallback to `unknown` returns soft error in form. |
| L7 | **`saved_plans` soft-deprecation only — no table drop** | Stop new writes; existing rows stay for historical reference. Hard drop happens in Plan 8 after a quarter of zero-writes confirmed via Guardian. |
| L8 | **Lifting templates seed: 2 templates v1 (`hypertrophy_8wk`, `in_season_lifting_starter`)** | Keep content scope tight. Coach can author more via Authoring mode (C4) once flow ships. |
| L9 | **Coach app `BuilderSlideOver` mounts inside `CreateProgramSlideOver` (existing)** | We already have a slide-over container in coach-app for the legacy team-block create flow. Replace its body with `<BuilderSlideOver interview_mode="..." />` rather than build a new chrome. |

## Carryovers from Plan 6 (addressed in Plan 7)

These were flagged during Plan 6 execution. Plan 7 lands them:
- **LLM "Other" goal chip + interpreter** → Phase A (A11) + Phase B (B11)
- **Lifting templates seed + chips** → Phase A (A13) + Phase B (B12)
- **Browse Templates section** → Phase A (A12) + Phase B (B13)
- **Scheduled-throw anchors on Active cards** → Phase A (A14) + Phase B (B14)
- **Telegram BackButton wiring on slide-overs** → Phase B (B15)
- **Legacy `saved_plans` retirement** → Phase A (A15) + Phase B (B16)
- **Coach mirrors** (A3-coach / drafts / programs) → Phase A (A3-coach)

## Plan 8 backlog (defer here so it doesn't slip into Plan 7)

- Hard drop of `saved_plans` table + `pitcher_training_model.active_program_id` FK cleanup
- Brand-shell workspace package (`packages/shell`) extraction — both apps consume
- Coach-authored research doc workflow (right now `block_library.research_doc_ids` is curated by engineers only)
- Prohibited-day conflict logic (Plan 6 A5 deferred this — `prohibited_throw_kinds` template field + 409 + `?confirm=true` retry)
- Cross-pitcher favorite copy ("I want what Reed did Tuesday")
- WHOOP token rotation (post 010 lockdown action item)

---

# Phase A — Backend (must land 100% green before Phase C UI ships)

Phase A adds 6 endpoints + 1 LLM helper + 1 migration. All test-driven. Backend test target after Phase A: ~790 (currently 750).

### Task A3-coach: Coach mirror endpoints `/programs` + `/drafts`

**Files:**
- Modify: `pitcher_program_app/api/coach_routes.py` (add 2 endpoints near the existing builder mirrors at line ~1002)
- Modify: `pitcher_program_app/bot/services/db.py` (no change — existing helpers `list_programs_for_pitcher_summary` + a new `list_completed_session_program_ids_for_pitcher` are sufficient)
- Create: `pitcher_program_app/tests/test_coach_program_list_endpoints.py`

**Approach:** Mirror the pitcher endpoints `/api/programs/drafts` + `/api/programs/active` + `/api/programs/history` for coach access. Two new coach routes (drafts and programs); the per-domain "active" view is folded into the unified programs endpoint via a `status` query filter so coaches don't need a 4th endpoint. Drafts endpoint filters to D14's locked answer: `builder_session.status='completed' AND program.status='draft'`.

**Key signatures:**

```python
# api/coach_routes.py — add after existing coach builder routes

@coach_router.get("/pitcher/{pitcher_id}/programs")
async def coach_get_pitcher_programs(
    pitcher_id: str, request: Request,
    status: Optional[str] = Query(default=None, regex="^(draft|active|archived|error)$"),
):
    """List all programs for a pitcher on this coach's team. Optional status filter."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    _require_team_pitcher(pitcher_id, team_id)
    rows = _db.list_programs_for_pitcher_summary(pitcher_id, status=status)
    return {"programs": rows}


@coach_router.get("/pitcher/{pitcher_id}/drafts")
async def coach_get_pitcher_drafts(pitcher_id: str, request: Request):
    """List drafts visible to the coach: only programs whose builder_session
    has status='completed'. Per D14: an in-flight Socratic session does not
    show up as a draft on the coach view — only finalized drafts.
    """
    await require_coach_auth(request)
    team_id = request.state.team_id
    _require_team_pitcher(pitcher_id, team_id)
    rows = _db.list_completed_session_drafts_for_pitcher(pitcher_id)
    return {"drafts": rows}
```

```python
# bot/services/db.py — new helper

def list_completed_session_drafts_for_pitcher(pitcher_id: str) -> list[dict]:
    """Return draft programs whose generating builder_session.status='completed'.
    Per Plan 6 D14: coach sees finalized drafts only; in-flight Socratic
    sessions are private to the pitcher until they hit Save/Activate.
    """
    client = get_client()
    # Two-step: pull completed session IDs first, then join via generated_program_id.
    sess_resp = (
        client.table("program_builder_sessions")
        .select("generated_program_id")
        .eq("pitcher_id", pitcher_id)
        .eq("status", "completed")
        .execute()
    )
    program_ids = [r["generated_program_id"] for r in (sess_resp.data or [])
                   if r.get("generated_program_id")]
    if not program_ids:
        return []
    prog_resp = (
        client.table("programs")
        .select(_PROGRAM_SUMMARY_COLUMNS)
        .eq("pitcher_id", pitcher_id)
        .eq("status", "draft")
        .in_("program_id", program_ids)
        .order("created_at", desc=True)
        .execute()
    )
    return prog_resp.data or []
```

**Tests (`tests/test_coach_program_list_endpoints.py`):**

```python
"""Plan 7 / A3-coach integration tests."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def coach_client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import coach_routes as cr
    monkeypatch.setattr(cr, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app, headers={"X-Test-Coach-Id": "dev_coach",
                                     "X-Test-Team-Id": "uchicago_baseball"})


def test_coach_programs_team_scoping_blocks_off_team_pitcher(coach_client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "outsider", "team_id": "other_team"}):
        resp = coach_client.get("/api/coach/pitcher/outsider/programs")
    assert resp.status_code == 403


def test_coach_programs_returns_team_pitcher_list(coach_client):
    from bot.services import db as _db
    rows = [{"program_id": "p1", "domain": "throwing", "status": "active"}]
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "landon_brice",
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_programs_for_pitcher_summary",
                      return_value=rows) as lst:
        resp = coach_client.get("/api/coach/pitcher/landon_brice/programs")
    assert resp.status_code == 200
    assert resp.json() == {"programs": rows}
    lst.assert_called_once_with("landon_brice", status=None)


def test_coach_programs_status_filter_passes_through(coach_client):
    from bot.services import db as _db
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "landon_brice",
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_programs_for_pitcher_summary",
                      return_value=[]) as lst:
        coach_client.get("/api/coach/pitcher/landon_brice/programs?status=draft")
    assert lst.call_args.kwargs["status"] == "draft"


def test_coach_drafts_only_returns_completed_session_drafts(coach_client):
    """D14 locked: in-flight Socratic sessions are NOT in the coach drafts view."""
    from bot.services import db as _db
    drafts = [{"program_id": "p1", "domain": "throwing", "status": "draft"}]
    with patch.object(_db, "get_pitcher",
                      return_value={"pitcher_id": "landon_brice",
                                    "team_id": "uchicago_baseball"}), \
         patch.object(_db, "list_completed_session_drafts_for_pitcher",
                      return_value=drafts) as lst:
        resp = coach_client.get("/api/coach/pitcher/landon_brice/drafts")
    assert resp.status_code == 200
    assert resp.json() == {"drafts": drafts}
    lst.assert_called_once_with("landon_brice")
```

**Steps:**
- [ ] Add `list_completed_session_drafts_for_pitcher` to `db.py`
- [ ] Add 2 endpoints to `coach_routes.py`
- [ ] Write 4 tests in `test_coach_program_list_endpoints.py`, all PASS
- [ ] `pytest -q` → expected 754 passed
- [ ] Commit: `feat(plan-7/a3-coach): coach mirror /programs + /drafts endpoints`

**Acceptance:** Coach can fetch any team-scoped pitcher's programs (with optional status filter) + finalized drafts. Cross-team pitchers return 403, not 404 (we have team-scope auth, the coach knows they exist by listing roster — 403 is honest).

---

### Task A4: Coach insight types (LLM-driven, scheduled via 9am digest)

**Files:**
- Modify: `pitcher_program_app/bot/services/coach_insights.py` (add 3 new functions + scheduler hook)
- Create: `pitcher_program_app/bot/prompts/insight_drift.md`
- Create: `pitcher_program_app/bot/prompts/insight_mismatch.md`
- Create: `pitcher_program_app/bot/prompts/insight_completion.md`
- Modify: `pitcher_program_app/bot/services/health_monitor.py` (call new functions from `compute_daily_digest` so insights generate alongside the 9am digest run)
- Create: `pitcher_program_app/tests/test_coach_insights_drift.py`
- Create: `pitcher_program_app/tests/test_coach_insights_mismatch.py`
- Create: `pitcher_program_app/tests/test_coach_insights_completion.py`

**Approach:** Add three insight generators that detect:
1. **Drift**: programs whose `current_day_index` is >5 days behind `expected_day_index` (computed from start_date + elapsed_days). Indicates pitcher has stalled; coach should consider archiving or shifting.
2. **Mismatch**: pitcher built an off-season program while their `current_flag_level` is YELLOW or RED. Mismatched intensity → injury risk.
3. **Team completion**: For each `team_assigned_blocks` row, compute average `current_day_index / total_days` across pitchers; flag if <50%.

Each generates an `insight_type` row in `coach_suggestions` (existing table) with `suggestion_type` set to the new value. Surfaced by Insights page (C6) which we already rebuilt in Spec 3.

**Key signatures:**

```python
# bot/services/coach_insights.py — new functions

def _expected_day_index(program: dict, today: date) -> int:
    """Calendar days elapsed since program.start_date — what current_day_index
    SHOULD be if no holds had occurred.
    """
    if not program.get("start_date"):
        return 0
    start = date.fromisoformat(program["start_date"])
    return max(0, (today - start).days)


def generate_drift_insight_for_program(program: dict, today: Optional[date] = None) -> Optional[dict]:
    """Return a coach_suggestions row dict if the program has drifted >5 days.

    Drift = expected_day_index - current_day_index. Held days count toward drift
    only after the 5-day grace window so brief illnesses don't trigger alerts.
    """
    today = today or date.today()
    expected = _expected_day_index(program, today)
    actual = int(program.get("current_day_index") or 0)
    drift_days = expected - actual
    if drift_days <= 5:
        return None
    return {
        "team_id": None,  # filled in by caller
        "pitcher_id": program["pitcher_id"],
        "suggestion_type": "program_drift",
        "title": f"Program drifted {drift_days} days behind",
        "body": (
            f"{program['domain'].title()} program {program.get('parent_template_id')} "
            f"is on day {actual + 1} but should be on day {expected + 1}. "
            f"Held {program.get('held_days_count', 0)} days lifetime. "
            "Consider archiving and rebuilding, or accepting the new pace."
        ),
        "context_json": {
            "program_id": program["program_id"],
            "drift_days": drift_days,
            "expected_day": expected,
            "actual_day": actual,
        },
        "status": "pending",
    }


async def generate_mismatch_insight_for_pitcher(profile: dict,
                                                 active_programs: list[dict]) -> Optional[dict]:
    """Return a coach_suggestions row if the pitcher's flag level is yellow/red
    AND they are running an off-season or velocity program (high-intensity intent
    on an injured arm).
    """
    flag = (profile.get("active_flags") or {}).get("current_flag_level")
    if flag not in ("yellow", "red", "critical_red"):
        return None
    risky_phases = {"off_season", "preseason"}
    risky_program = next(
        (p for p in active_programs
         if (p.get("generated_schedule_json", {}).get("source_template") in
             ("velocity_12wk_v1", "offseason_base_4wk_v1"))
         or (p.get("parent_template_id") in
             ("velocity_12wk_v1", "offseason_base_4wk_v1"))),
        None
    )
    if not risky_program:
        return None
    return {
        "team_id": None,
        "pitcher_id": profile["pitcher_id"],
        "suggestion_type": "program_flag_mismatch",
        "title": f"{profile.get('name', profile['pitcher_id'])} on high-intent program while {flag.upper()}",
        "body": (
            f"Pitcher built {risky_program.get('parent_template_id')} (high-intent "
            f"phase) but current flag level is {flag.upper()}. Consider scaling "
            "intent down via mutation preview, or archiving and rebuilding with "
            "a more conservative goal."
        ),
        "context_json": {
            "program_id": risky_program["program_id"],
            "flag_level": flag,
            "template": risky_program.get("parent_template_id"),
        },
        "status": "pending",
    }


def generate_team_completion_insight(team_assigned_block_row: dict,
                                      member_programs: list[dict]) -> Optional[dict]:
    """For a team-assigned block, compute the average completion percent across
    member pitchers' programs. Flag if mean <50% AND at least 1 pitcher is <50%.
    """
    if not member_programs:
        return None
    completions = []
    laggers = []
    for p in member_programs:
        days = p.get("generated_schedule_json", {}).get("days") or []
        total = len(days) or 84  # fallback to a typical program length
        idx = int(p.get("current_day_index") or 0)
        pct = idx / total if total else 0
        completions.append(pct)
        if pct < 0.5:
            laggers.append(p.get("pitcher_id"))
    mean_pct = sum(completions) / len(completions)
    if mean_pct >= 0.5:
        return None
    weeks_in = round((sum(_expected_day_index(p, date.today()) for p in member_programs)
                      / len(member_programs)) / 7, 1)
    return {
        "team_id": team_assigned_block_row.get("team_id"),
        "pitcher_id": None,  # team-scoped
        "suggestion_type": "team_program_lagging",
        "title": (
            f"{len(laggers)} pitchers <50% on {team_assigned_block_row.get('block_id')}"
        ),
        "body": (
            f"Team is ~{weeks_in} weeks into {team_assigned_block_row.get('block_id')}. "
            f"Average completion {round(mean_pct * 100)}%. "
            f"Behind: {', '.join(laggers)}."
        ),
        "context_json": {
            "block_id": team_assigned_block_row.get("block_id"),
            "mean_completion_pct": round(mean_pct, 2),
            "lagger_pitcher_ids": laggers,
        },
        "status": "pending",
    }
```

```python
# bot/services/health_monitor.py — in compute_daily_digest after existing checks

async def _generate_coach_insights_for_team(team_id: str) -> int:
    """Plan 7 / A4: generate drift / mismatch / completion insights for every
    active program / pitcher / team_assigned_block in the team.

    Returns count of new coach_suggestions rows inserted. Idempotent within
    a day via suggestion_type + pitcher_id + program_id dedup at insert time.
    """
    from bot.services import coach_insights, db as _db, team_scope
    roster = team_scope.get_team_roster_overview(team_id)
    new_count = 0
    for row in roster:
        pitcher_id = row["pitcher_id"]
        programs = _db.list_programs_for_pitcher_summary(pitcher_id, status="active")
        profile = _db.get_pitcher(pitcher_id) or {}

        # Drift per active program
        for p in programs:
            sug = coach_insights.generate_drift_insight_for_program(p)
            if sug and not _db.suggestion_exists_for_today(
                pitcher_id, "program_drift",
                context_program_id=p["program_id"]
            ):
                sug["team_id"] = team_id
                _db.insert_coach_suggestion(sug)
                new_count += 1

        # Mismatch (per pitcher across all their active programs)
        mis = await coach_insights.generate_mismatch_insight_for_pitcher(profile, programs)
        if mis and not _db.suggestion_exists_for_today(
            pitcher_id, "program_flag_mismatch"
        ):
            mis["team_id"] = team_id
            _db.insert_coach_suggestion(mis)
            new_count += 1

    # Team completion rollups
    team_blocks = _db.list_team_assigned_blocks(team_id, status="active")
    for tab in team_blocks:
        members = _db.list_member_programs_for_team_block(tab)
        comp = coach_insights.generate_team_completion_insight(tab, members)
        if comp and not _db.suggestion_exists_for_today(
            None, "team_program_lagging", context_block_id=tab.get("block_id")
        ):
            _db.insert_coach_suggestion(comp)
            new_count += 1
    return new_count
```

**Tests:** see file split — 3 test files, one per insight type. Each tests: positive case (insight generated), negative case (criteria not met), idempotency check (suggestion_exists_for_today returns True → no double-insert). Total ~12 tests.

**Steps:**
- [ ] Add `_expected_day_index` + 3 generators to `coach_insights.py`
- [ ] Write 3 prompt files (small — coach_insights is rule-based today; the LLM is only used to softly polish the body if we want; v1 keeps it rule-based to ship faster)
- [ ] Add `suggestion_exists_for_today`, `insert_coach_suggestion`, `list_member_programs_for_team_block` helpers to `db.py`
- [ ] Wire `_generate_coach_insights_for_team` into `compute_daily_digest`
- [ ] Write 12 tests (4 per insight type — positive, negative, idempotent, edge), all PASS
- [ ] `pytest -q` → expected 766 passed
- [ ] Commit: `feat(plan-7/a4): coach insight types — drift / mismatch / team completion`

**Acceptance:** 9am admin digest generates new `coach_suggestions` rows when drift / mismatch / lag conditions are met. Existing Insights page (Spec 3) renders them via its existing reader. **v1 keeps insight bodies rule-based** (no LLM call); LLM polish is a Plan 8 follow-up if we want more natural language.

> **Note on L5/L6:** The L5 brainstorm answer locked "A4 insights run on 9am digest schedule" and L6 locked a 60s LLM timeout for goal interpretation (A11). These are NOT the same. A4 is rule-based; LLM is only for A11. We don't pay LLM cost for daily insight generation.

---

### Task A11: LLM goal interpreter endpoint

**Files:**
- Create: `pitcher_program_app/bot/services/goal_interpreter.py`
- Modify: `pitcher_program_app/api/routes.py` (add `POST /api/programs/builder/interpret-goal`)
- Create: `pitcher_program_app/bot/prompts/goal_interpreter.md`
- Create: `pitcher_program_app/tests/test_goal_interpreter.py`
- Create: `pitcher_program_app/tests/test_goal_interpreter_endpoint.py`

**Approach:** Accept `{text, domain}` from the form's "Other / describe…" chip. Call DeepSeek with a tight prompt that lists all current `goal_tags` for that domain. LLM returns ONE tag (or `unknown`). Frontend uses the returned tag in the subsequent `/candidates` call.

**Key signatures:**

```python
# bot/services/goal_interpreter.py
"""Plan 7 / A11: map a natural-language goal description to a canonical goal_tag.

Called synchronously from the Build form on a 60s budget when the pitcher picks
the "Other / describe..." chip. Returns one of the existing tags in the domain's
template pool, or "unknown" if the description doesn't match.
"""
from __future__ import annotations

import logging
from typing import Optional

INTERPRET_TIMEOUT = 60  # L6 locked
logger = logging.getLogger(__name__)


async def interpret_goal(text: str, domain: str) -> str:
    """Returns a goal_tag string, or "unknown" on no-match.

    LLM call is the slow path; if it times out or fails, returns "unknown" so
    the caller can show an inline error rather than a 500.
    """
    from bot.services import db
    from bot.services.llm import call_llm, load_prompt
    if not text or not text.strip():
        return "unknown"
    if domain not in ("throwing", "lifting"):
        raise ValueError(f"domain must be 'throwing' or 'lifting', got {domain!r}")

    # Build the candidate-tag list dynamically from block_library
    rows = (db.get_client().table("block_library")
            .select("goal_tags").eq("domain", domain).execute()).data or []
    candidate_tags = sorted({tag for row in rows
                              for tag in (row.get("goal_tags") or [])})
    if not candidate_tags:
        return "unknown"

    system = load_prompt("goal_interpreter.md")
    user = (
        f"Domain: {domain}\n"
        f"Available goal tags: {', '.join(candidate_tags)}\n"
        f"Pitcher described their goal as: \"{text}\"\n\n"
        "Return ONE tag from the list that best matches the description, "
        "or the literal string 'unknown' if no tag fits. "
        "Reply with ONLY the tag string — no quotes, no explanation."
    )
    try:
        raw = await call_llm(system_prompt=system, user_message=user, history=[],
                             timeout=INTERPRET_TIMEOUT)
    except Exception:
        logger.warning("goal_interpreter LLM call failed", exc_info=True)
        return "unknown"
    tag = (raw or "").strip().lower()
    # Soft guard against the LLM ignoring instructions
    return tag if tag in candidate_tags else "unknown"
```

```python
# api/routes.py — add to the Builder block

class InterpretGoalRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(..., pattern="^(throwing|lifting)$")


@router.post("/programs/builder/interpret-goal")
async def post_builder_interpret_goal(req: InterpretGoalRequest, request: Request):
    """Plan 7 / A11: free-text goal description → canonical goal_tag.

    Returns {"tag": "...", "confidence": "matched|unknown"}. UI uses the
    returned tag in the next /candidates call. "unknown" means the LLM
    couldn't map the text to any existing tag — caller should show inline
    error and let the pitcher pick a chip instead.
    """
    _resolve_pitcher_id_from_request(request)  # auth gate
    from bot.services.goal_interpreter import interpret_goal
    tag = await interpret_goal(req.text, req.domain)
    return {"tag": tag, "confidence": "matched" if tag != "unknown" else "unknown"}
```

**Tests:**

```python
# tests/test_goal_interpreter.py
import pytest
from unittest.mock import patch, AsyncMock
from bot.services import goal_interpreter


@pytest.mark.asyncio
async def test_interpret_goal_returns_matched_tag():
    rows = [{"goal_tags": ["velocity", "longtoss"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(return_value="velocity")):
            out = await goal_interpreter.interpret_goal("I want to throw harder", "throwing")
    assert out == "velocity"


@pytest.mark.asyncio
async def test_interpret_goal_returns_unknown_when_llm_fabricates():
    """LLM returns a tag that isn't in the candidate list → soft-guard to 'unknown'."""
    rows = [{"goal_tags": ["velocity"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(return_value="hypertrophy")):
            out = await goal_interpreter.interpret_goal("hyper", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_returns_unknown_on_llm_error():
    rows = [{"goal_tags": ["velocity"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(side_effect=TimeoutError("boom"))):
            out = await goal_interpreter.interpret_goal("anything", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_empty_text_returns_unknown():
    out = await goal_interpreter.interpret_goal("   ", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_rejects_bad_domain():
    with pytest.raises(ValueError):
        await goal_interpreter.interpret_goal("anything", "mobility")
```

```python
# tests/test_goal_interpreter_endpoint.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


def test_interpret_goal_endpoint_returns_tag(client):
    from bot.services import goal_interpreter
    with patch.object(goal_interpreter, "interpret_goal",
                      new=AsyncMock(return_value="velocity")):
        resp = client.post(
            "/api/programs/builder/interpret-goal",
            json={"text": "I want to throw harder", "domain": "throwing"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"tag": "velocity", "confidence": "matched"}


def test_interpret_goal_endpoint_unknown_confidence(client):
    from bot.services import goal_interpreter
    with patch.object(goal_interpreter, "interpret_goal",
                      new=AsyncMock(return_value="unknown")):
        resp = client.post(
            "/api/programs/builder/interpret-goal",
            json={"text": "blah", "domain": "throwing"},
            headers={"X-Test-Pitcher-Id": "landon_brice"},
        )
    assert resp.json()["confidence"] == "unknown"


def test_interpret_goal_endpoint_validates_request(client):
    resp = client.post(
        "/api/programs/builder/interpret-goal",
        json={"text": "", "domain": "throwing"},  # empty text fails min_length
        headers={"X-Test-Pitcher-Id": "landon_brice"},
    )
    assert resp.status_code == 422
```

**Prompt file (`bot/prompts/goal_interpreter.md`):**

```markdown
You map natural-language pitcher goal descriptions to canonical training program tags.

You will be given:
- A domain (throwing or lifting)
- A list of available goal tags for that domain
- A free-text description from a pitcher

Your job: pick ONE tag from the list that best matches the description.

Strict rules:
- Reply with ONLY the tag string (lowercase_with_underscores), no quotes, no punctuation, no explanation
- If no tag fits the description, reply with the literal string: unknown
- Never invent tags not in the provided list
- Prefer specificity: if the pitcher mentions "long toss specifically" pick longtoss over arm_health
```

**Steps:**
- [ ] Create `goal_interpreter.py`
- [ ] Create `bot/prompts/goal_interpreter.md`
- [ ] Add endpoint to `routes.py`
- [ ] Write 5 service tests + 3 endpoint tests, all PASS
- [ ] `pytest -q` → expected 774 passed
- [ ] Commit: `feat(plan-7/a11): LLM goal interpreter endpoint`

**Acceptance:** Free-text pitcher description ("I want to throw harder", "rebuild after surgery") → returns a real `goal_tag` the matcher accepts. LLM errors and unknown matches return `unknown` so the form can show inline error. 60s timeout configured.

---

### Task A12: Templates list endpoint

**Files:**
- Modify: `pitcher_program_app/api/routes.py` (add `GET /api/programs/templates`)
- Modify: `pitcher_program_app/bot/services/db.py` (add `list_block_library_templates` helper)
- Create: `pitcher_program_app/tests/test_templates_endpoint.py`

**Approach:** Read-only public list of all `block_library` rows that have the Plan-1-era fields populated. Used by mini-app Browse Templates section (B13) and coach-app template library views (C3, C5).

**Key signatures:**

```python
# bot/services/db.py
_TEMPLATE_SUMMARY_COLUMNS = (
    "block_template_id,name,description,domain,goal_tags,compatible_phases,"
    "duration_range_weeks,implied_phase,research_doc_ids"
)


def list_block_library_templates(domain: Optional[str] = None,
                                  phase: Optional[str] = None) -> list[dict]:
    """Return block_library rows with Plan-1 schema fields populated.
    Skips legacy stub rows (domain IS NULL).
    """
    q = (get_client().table("block_library")
         .select(_TEMPLATE_SUMMARY_COLUMNS)
         .not_.is_("domain", "null"))
    if domain:
        q = q.eq("domain", domain)
    resp = q.order("name").execute()
    rows = resp.data or []
    if phase:
        rows = [r for r in rows if phase in (r.get("compatible_phases") or [])]
    return rows


# api/routes.py
@router.get("/programs/templates")
async def get_program_templates(
    request: Request,
    domain: Optional[str] = Query(default=None, regex="^(throwing|lifting)$"),
    phase: Optional[str] = Query(default=None),
):
    """List canonical block_library templates. Optional filters: domain, phase."""
    _resolve_pitcher_id_from_request(request)
    rows = _db.list_block_library_templates(domain=domain, phase=phase)
    return {"templates": rows}
```

**Tests:** 5 tests — empty filter, domain filter, phase filter, both filters, auth required.

**Steps:**
- [ ] Add `list_block_library_templates` to `db.py`
- [ ] Add endpoint to `routes.py`
- [ ] Write 5 tests, all PASS
- [ ] `pytest -q` → expected 779 passed
- [ ] Commit: `feat(plan-7/a12): GET /api/programs/templates list endpoint`

**Acceptance:** Endpoint returns the 4 currently-seeded templates with `goal_tags` / `compatible_phases` / `duration_range_weeks` for client-side filtering. Lifting filter returns empty until A13 ships.

---

### Task A13: Lifting templates seed migration

**Files:**
- Create: `pitcher_program_app/scripts/migrations/029_seed_lifting_templates.sql`
- Apply via Supabase MCP

**Approach:** Insert 2 lifting templates per L8 lock: `hypertrophy_8wk` and `in_season_lifting_starter`. Same shape as the throwing templates (block_template_id, name, description, domain, duration_days, content, source, domain, goal_tags, duration_range_weeks, compatible_phases, tunable_parameters_schema, week_scaffold_json, research_doc_ids, implied_phase).

**Key content (the SQL):**

```sql
-- Plan 7 / A13 — seed lifting templates so the Build form's lifting domain
-- has candidates beyond the "coming soon" message.

INSERT INTO block_library (
  block_template_id, name, description, block_type, duration_days, content,
  source, domain, goal_tags, duration_range_weeks, compatible_phases,
  tunable_parameters_schema, week_scaffold_json, research_doc_ids, implied_phase
) VALUES (
  'hypertrophy_8wk_v1',
  '8-Week Hypertrophy Block',
  'Upper/Lower split 4x/week. Volume emphasis on compound + accessory pairings. Pitcher-specific volume caps to protect shoulder health.',
  'lifting', 56,
  '{"scaffold_ref": "hypertrophy_8wk_v1.week_scaffold_json", "source_template": "hypertrophy_8wk_v1"}'::jsonb,
  'spec_program_builder_v1',
  'lifting',
  ARRAY['hypertrophy','muscle_growth','size'],
  '[6,10]'::int4range,
  ARRAY['off_season','preseason'],
  '{}'::jsonb,
  $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Upper — Hypertrophy"},
      {"day_offset": 1, "template_key": "day_1", "label": "Lower — Hypertrophy"},
      {"day_offset": 2, "template_key": "day_2", "label": "Recovery + Mobility"},
      {"day_offset": 3, "template_key": "day_3", "label": "Upper — Accessory Volume"},
      {"day_offset": 4, "template_key": "day_4", "label": "Lower — Posterior Chain"},
      {"day_offset": 5, "template_key": "day_5", "label": "Active Recovery"},
      {"day_offset": 6, "template_key": "day_6", "label": "Off"}
    ],
    "source_template": "hypertrophy_8wk_v1",
    "notes": "Volume-focused 4-day split. Day-content via exercise_pool with hypertrophy intent tag."
  }$$::jsonb,
  ARRAY[]::TEXT[],
  'off_season'
), (
  'in_season_lifting_starter_v1',
  'In-Season Lifting — Starter Maintenance',
  '2x/week minimum-effective-dose lifting block. Preserves strength without compromising recovery between starts.',
  'lifting', 84,
  '{"scaffold_ref": "in_season_lifting_starter_v1.week_scaffold_json", "source_template": "in_season_lifting_starter_v1"}'::jsonb,
  'spec_program_builder_v1',
  'lifting',
  ARRAY['in_season_lifting','strength_maintain','minimum_effective_dose'],
  '[10,16]'::int4range,
  ARRAY['in_season_active','in_season'],
  '{}'::jsonb,
  $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Game / Rest"},
      {"day_offset": 1, "template_key": "day_1", "label": "Day-After — Light Recovery"},
      {"day_offset": 2, "template_key": "day_2", "label": "Lower — Power Maintain"},
      {"day_offset": 3, "template_key": "day_3", "label": "Upper — Pull Emphasis"},
      {"day_offset": 4, "template_key": "day_4", "label": "Recovery"},
      {"day_offset": 5, "template_key": "day_5", "label": "Light Upper + Mobility"},
      {"day_offset": 6, "template_key": "day_6", "label": "Pre-Game — Mobility Only"}
    ],
    "source_template": "in_season_lifting_starter_v1",
    "notes": "Pairs with tpl_starter_7day_cadence_v1 throwing block — same calendar shape."
  }$$::jsonb,
  ARRAY[]::TEXT[],
  'in_season_active'
)
ON CONFLICT (block_template_id) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    domain = EXCLUDED.domain,
    goal_tags = EXCLUDED.goal_tags,
    duration_range_weeks = EXCLUDED.duration_range_weeks,
    compatible_phases = EXCLUDED.compatible_phases,
    week_scaffold_json = EXCLUDED.week_scaffold_json,
    implied_phase = EXCLUDED.implied_phase;
```

**Steps:**
- [ ] Apply migration via `mcp__supabase__apply_migration` (idempotent UPSERT)
- [ ] Verify via SQL: `SELECT block_template_id, domain, goal_tags FROM block_library WHERE domain = 'lifting';`
- [ ] Commit the migration file: `feat(plan-7/a13): seed lifting templates`

**Acceptance:** `GET /api/programs/templates?domain=lifting` returns 2 templates. `/api/programs/builder/candidates` with `domain: 'lifting'`, `goal: 'hypertrophy'`, `duration_weeks: 8`, `effective_phase: 'off_season'` returns `hypertrophy_8wk_v1` as a candidate.

---

### Task A14: Scheduled-throws read endpoint

**Files:**
- Modify: `pitcher_program_app/api/routes.py` (add `GET /api/pitcher/{pitcher_id}/scheduled-throws`)
- Reuse: existing `db.get_pitcher_scheduled_throws` from Plan 6 A5
- Create: `pitcher_program_app/tests/test_scheduled_throws_endpoint.py`

**Approach:** Tiny endpoint that exposes `current_week_state.scheduled_throws` for the mini-app to read when rendering the Active card's "next throw" anchor. Already-existing db helper from A5; just needs HTTP exposure.

**Key signatures:**

```python
# api/routes.py
@router.get("/pitcher/{pitcher_id}/scheduled-throws")
async def get_scheduled_throws(pitcher_id: str, request: Request):
    """Plan 7 / A14: read-only view of scheduled_throws for UI anchor display.

    Pitcher's mini-app reads this when rendering the Programs tab Active card
    to show "Next bullpen: Wed May 14" inline.
    """
    _require_pitcher_auth(request, pitcher_id)
    throws = _db.get_pitcher_scheduled_throws(pitcher_id)
    # Sort by date ASC so "next" is index 0
    throws.sort(key=lambda t: t.get("date") or "9999")
    return {"scheduled_throws": throws}
```

**Tests:** 3 tests — happy path returns sorted throws, empty returns `{scheduled_throws: []}`, auth gate works.

**Steps:**
- [ ] Add endpoint to `routes.py`
- [ ] Write 3 tests, all PASS
- [ ] `pytest -q` → expected 782 passed
- [ ] Commit: `feat(plan-7/a14): GET /api/pitcher/{id}/scheduled-throws`

**Acceptance:** Endpoint returns the pitcher's scheduled throws sorted by date. Empty state is well-formed (`{scheduled_throws: []}`).

---

### Task A15: `saved_plans` soft-deprecation

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py` (`insert_saved_plan` logs a deprecation warning)
- Modify: `pitcher_program_app/api/routes.py` (the saved-plan write endpoint logs deprecation + adds `Deprecation` response header)
- Create: `pitcher_program_app/tests/test_saved_plans_deprecation.py`

**Approach:** Don't drop the table. Don't break reads. But every new write logs at WARN level + adds a response header so the bot/admin can confirm zero writes for a quarter before Plan 8 hard-retires.

**Key changes:**

```python
# bot/services/db.py — modify insert_saved_plan

def insert_saved_plan(pitcher_id: str, plan: dict) -> dict:
    """Insert a new saved plan. Returns the inserted row.

    DEPRECATED (Plan 7 / A15): saved_plans is being retired in favor of
    `favorited_blocks`. New writes are logged for monitoring. Plan 8 will
    hard-drop the table once a quarter of zero-writes is confirmed.
    """
    logger.warning(
        "saved_plans_deprecated_write | pitcher_id=%s | plan_name=%s | "
        "future Plan 8 retirement",
        pitcher_id, plan.get("plan_name") or plan.get("name")
    )
    plan["pitcher_id"] = pitcher_id
    resp = get_client().table("saved_plans").insert(plan).execute()
    return resp.data[0] if resp.data else plan
```

```python
# api/routes.py — modify the savePlan endpoint to add Deprecation header
# (Look up the existing endpoint and patch in:)
#   response.headers["Deprecation"] = "true"
#   response.headers["Sunset"] = "Plan 8 (Q3 2026)"
```

**Tests:** 2 tests — write still works (no behavior break), warning is logged.

**Steps:**
- [ ] Patch `insert_saved_plan` with deprecation log
- [ ] Patch saved-plan write endpoint with response headers
- [ ] Write 2 tests, all PASS
- [ ] `pytest -q` → expected 784 passed
- [ ] Commit: `feat(plan-7/a15): saved_plans soft-deprecation`

**Acceptance:** Writes still succeed (no regression). Bot logs show `saved_plans_deprecated_write` warnings on every new write. Response includes `Deprecation: true` + `Sunset` header.

---

# Phase B — Mini-app polish (parallel-safe after A11, A12, A13, A14 land)

Phase B is 6 small UI tasks. Mini-app test target after Phase B: ~70 (currently 55).

### Task B11: "Other / describe…" goal chip + LLM interpreter wiring

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/BuilderSlideOver.jsx`
- Modify: `pitcher_program_app/mini-app/src/api.js` (add `interpretGoal` client fn)
- Modify: `pitcher_program_app/mini-app/src/components/__tests__/BuilderSlideOver.test.jsx`

**Approach:** Add a 6th chip to `GOALS_THROWING` (and eventually `GOALS_LIFTING`): `{id: '__other__', label: 'Other / describe…'}`. Picking it reveals a text input below the chips. On Continue, if `__other__` is selected, call `interpretGoal(text, domain)` first; use the returned tag (or show inline error if `unknown`).

**Key signatures:**

```javascript
// mini-app/src/api.js
export async function interpretGoal(text, domain, initData = null) {
  return postApi('/api/programs/builder/interpret-goal', { text, domain }, initData);
}
```

```jsx
// In BuilderSlideOver.jsx, add to GOALS_THROWING:
const GOALS_THROWING = [
  // ... existing ...
  { id: '__other__', label: 'Other / describe…' },
];

// In InputsForm component, after the chip group:
{goal === '__other__' && (
  <input
    type="text" value={goalText}
    onChange={e => setGoalText(e.target.value)}
    placeholder="Describe your goal — e.g. add velocity post-surgery"
    style={{ /* same as old free-text style */ }}
    aria-label="Goal description"
  />
)}

// In handleContinue:
let resolvedGoal = goal;
if (goal === '__other__') {
  if (!goalText.trim()) { setError('Describe your goal to continue.'); return; }
  const res = await interpretGoal(goalText.trim(), domain, initData);
  if (res.confidence === 'unknown') {
    setError("I couldn't match that goal. Try a chip above or rephrase.");
    return;
  }
  resolvedGoal = res.tag;
}
// ... pass resolvedGoal to fetchBuilderCandidates ...
```

**Tests:** +3 vitest tests — Other chip reveals input, interpreter call wires correctly, unknown response shows inline error.

**Steps:**
- [ ] Add `interpretGoal` to `api.js`
- [ ] Add `__other__` chip + conditional input + handleContinue branch
- [ ] Write 3 vitest tests
- [ ] `npm run test:run` → expected 58 passed
- [ ] Commit: `feat(plan-7/b11): "Other / describe..." goal chip with LLM interpreter`

**Acceptance:** Pitcher types "I want to throw harder" → form returns a candidate. Pitcher types "abracadabra" → inline error, stay on form.

---

### Task B12: Lifting goal chips + remove "coming soon"

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/BuilderSlideOver.jsx`
- Modify: `pitcher_program_app/mini-app/src/components/__tests__/BuilderSlideOver.test.jsx`

**Approach:** Populate `GOALS_LIFTING` with the 3 tags from A13 templates. Remove the "Lifting programs coming soon" message. Default duration to 8 wk when switching to lifting (sits in both templates' ranges).

**Key change:**

```jsx
const GOALS_LIFTING = [
  { id: 'hypertrophy',          label: 'Hypertrophy' },
  { id: 'strength_maintain',    label: 'Strength maintenance' },
  { id: 'in_season_lifting',    label: 'In-season lifting' },
  { id: '__other__',            label: 'Other / describe…' },
];
```

**Tests:** Update existing lifting-coming-soon test to assert chips render instead. +1 test for hypertrophy chip → /candidates returns hypertrophy_8wk_v1.

**Steps:**
- [ ] Populate `GOALS_LIFTING`
- [ ] Remove `goal-domain-unsupported` test ID and replace with chip rendering
- [ ] Update 2 tests
- [ ] `npm run test:run` → expected 60 passed
- [ ] Commit: `feat(plan-7/b12): lifting goal chips, drop coming-soon banner`

**Acceptance:** Pitcher picks Lifting → 4 chips visible. Picking Hypertrophy + 8 wk + Off-season returns a candidate.

---

### Task B13: Browse Templates section

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Programs.jsx` (add 8th section)
- Modify: `pitcher_program_app/mini-app/src/api.js` (add `fetchTemplates` client fn)
- Modify: `pitcher_program_app/mini-app/src/pages/__tests__/Programs.test.jsx`

**Approach:** Bottom section, collapsed by default. Tap to expand → renders a list of templates from `/api/programs/templates`. Each row: name, domain, duration range, "Build with this template" button → opens BuilderSlideOver with the template's tags pre-selected.

**Key signatures:**

```javascript
// api.js
export async function fetchTemplates(domain, initData = null) {
  const qs = domain ? `?domain=${domain}` : '';
  return fetchApi(`/api/programs/templates${qs}`, initData);
}
```

```jsx
// In Programs.jsx, add section component:
function BrowseTemplatesSection() {
  const [open, setOpen] = useState(false);
  const { data, loading } = useApi(open ? '/api/programs/templates' : null, initData);
  return (
    <>
      <button data-testid="browse-templates-toggle"
        onClick={() => setOpen(!open)}
        style={sectionLabelStyle}>
        Browse Templates {open ? '▾' : '▸'}
      </button>
      {open && !loading && (data?.templates || []).map(t => (
        <TemplateRow key={t.block_template_id} template={t}
          onBuildWith={() => openBuilder(t.domain, t.goal_tags[0])} />
      ))}
    </>
  );
}
```

**Tests:** +2 vitest tests — section starts collapsed, expanding fetches templates.

**Steps:**
- [ ] Add `fetchTemplates` to api.js
- [ ] Add `BrowseTemplatesSection` to Programs.jsx
- [ ] Pass `openBuilder(domain, goal)` through (extend BuilderSlideOver to accept `initialGoal` prop)
- [ ] Update Programs page tests
- [ ] `npm run test:run` → expected 62 passed
- [ ] Commit: `feat(plan-7/b13): Browse Templates section on Programs tab`

**Acceptance:** Programs tab has 8th section at bottom. Tap to expand → templates list. "Build with this template" opens slide-over with template's domain + first goal_tag pre-set.

---

### Task B14: Scheduled-throw anchors on Active cards

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Programs.jsx` (ProgramCard sub-component)
- Modify: `pitcher_program_app/mini-app/src/pages/__tests__/Programs.test.jsx`

**Approach:** Fetch `/api/pitcher/{id}/scheduled-throws` in Programs page. Pass to ProgramCard. Card shows the next-future throw inline: "Next: bullpen Wed May 15".

**Key change:**

```jsx
// In Programs.jsx
const throws = useApi(pitcherId ? `/api/pitcher/${pitcherId}/scheduled-throws${bust}` : null, initData);

// In ActiveSection, pass throws.data?.scheduled_throws down

// In ProgramCard, after held line:
{nextThrow && (
  <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4 }}>
    Next {nextThrow.type}: <strong>{nextThrow.date}</strong>
  </div>
)}
```

**Tests:** +2 vitest tests — next throw renders, absence is graceful.

**Steps:**
- [ ] Add `scheduled-throws` fetch to Programs.jsx
- [ ] Thread to ProgramCard
- [ ] Filter for future-throws (date >= today)
- [ ] Update tests
- [ ] `npm run test:run` → expected 64 passed
- [ ] Commit: `feat(plan-7/b14): scheduled-throw anchors on Active cards`

**Acceptance:** Active card shows next future throw or nothing. Tomorrow's bullpen at the latest.

---

### Task B15: Telegram BackButton wiring on slide-overs

**Files:**
- Modify: `pitcher_program_app/mini-app/src/hooks/useTelegram.js` (add `useBackButton(onPress)` hook)
- Modify: `pitcher_program_app/mini-app/src/components/BuilderSlideOver.jsx`
- Create: `pitcher_program_app/mini-app/src/hooks/__tests__/useTelegram.test.js`

**Approach:** New `useBackButton(handler)` hook wraps `WebApp.BackButton.show()` + `onClick(handler)` on mount, `hide()` + `offClick` on unmount. BuilderSlideOver imports and calls with `onClose` as the handler. Future slide-overs (Plan 8 ProgramDetail etc.) reuse the hook.

**Key signatures:**

```javascript
// hooks/useTelegram.js — add to existing exports
import { useEffect } from 'react';

export function useBackButton(onPress) {
  useEffect(() => {
    if (typeof window === 'undefined' || !window.Telegram?.WebApp) return;
    const wa = window.Telegram.WebApp;
    if (!wa.BackButton) return;
    wa.BackButton.show();
    wa.BackButton.onClick(onPress);
    return () => {
      try { wa.BackButton.offClick(onPress); } catch (_) {}
      wa.BackButton.hide();
    };
  }, [onPress]);
}
```

```jsx
// In BuilderSlideOver, at top of component:
import { useBackButton } from '../hooks/useTelegram';
useBackButton(onClose);
```

**Tests:** +2 hook tests — BackButton.show called on mount, hide called on unmount.

**Steps:**
- [ ] Add `useBackButton` hook
- [ ] Wire into BuilderSlideOver
- [ ] Write 2 hook tests with mocked `window.Telegram.WebApp`
- [ ] `npm run test:run` → expected 66 passed
- [ ] Commit: `feat(plan-7/b15): Telegram BackButton wiring on slide-overs`

**Acceptance:** Hardware back inside the BuilderSlideOver closes the sheet instead of exiting the WebApp.

---

### Task B16: Remove "Save this plan" CTA in Coach.jsx

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Coach.jsx` (lines ~860-875 — the `m.type === 'save_plan'` branch)

**Approach:** Drop the "Save this plan" button rendering. Existing saved_plans rows continue to be readable via `/plans/{planId}` (legacy `PlanDetail`). New saves stop accumulating. Pair with A15's backend deprecation.

**Key change:** Delete the JSX block that renders the `m.type === 'save_plan'` button.

**Tests:** No mini-app test currently asserts the button exists (Coach.jsx wasn't covered by vitest in Plan 6). Skip new test; rely on user smoke.

**Steps:**
- [ ] Delete the save-plan button JSX
- [ ] Manual check: Coach chat no longer shows "Save this plan" after a plan is sent
- [ ] Commit: `feat(plan-7/b16): remove "Save this plan" CTA from Coach (deprecated)`

**Acceptance:** Save-plan button gone. `saved_plans` write log shows zero new writes from mini-app.

---

# Phase C — Coach-app UX (7 tasks)

Phase C builds on existing brand shell + Spec 3 component patterns. Coach-app test target after Phase C: ~110 (currently 81).

### Task C0 (prereq): Extract BuilderSlideOver to `shared/builder/`

**Files:**
- Create: `shared/builder/BuilderSlideOver.jsx` (move from `mini-app/src/components/BuilderSlideOver.jsx`)
- Create: `shared/builder/__tests__/BuilderSlideOver.test.jsx` (move tests)
- Modify: `pitcher_program_app/mini-app/src/pages/Programs.jsx` (import from `@shared/builder/BuilderSlideOver.jsx`)
- Modify: `pitcher_program_app/mini-app/vite.config.js` (already aliases `@shared`)
- Modify: `pitcher_program_app/mini-app/vitest.config.js` (already aliases `@shared`)
- Modify: `pitcher_program_app/coach-app/vite.config.js` (already aliases `@shared`)
- Modify: `pitcher_program_app/coach-app/vitest.config.js` (already aliases `@shared`)

**Approach:** Per L4. The repo already aliases `@shared` to `../shared/` in both apps (for `@shared/parseBrief.js`). The slide-over is currently mini-app-only; move it into the shared workspace so coach-app can import the same component with a `mode` prop.

**Constraint:** The component imports from `../App` (`useAuth`) and `../api` (`fetchBuilderCandidates`, etc.). These imports differ between mini-app and coach-app:
- Mini-app: `useAuth` returns `{pitcherId, initData}`
- Coach-app: `useCoachAuth` returns `{coach, getAccessToken}`
- Mini-app: `api.js` uses Telegram initData headers
- Coach-app: `api.js` uses Bearer JWT headers

**Solution:** Make the moved BuilderSlideOver **inject its API client + auth via props**, not via imports. Caller passes `{api, auth}`:

```jsx
// shared/builder/BuilderSlideOver.jsx
export default function BuilderSlideOver({
  api,        // {fetchCandidates, sendTurn, finalize, activateProgram, archiveProgram, interpretGoal}
  // ... existing props
  onClose, onProgramActivated, onDraftSaved,
  initialDomain = 'throwing', initialGoal = null,
  interview_mode = 'personalize',  // L2 — new prop
  pitcherIdForCoach = null,         // populated when coach builds for a specific pitcher
}) { ... }
```

```jsx
// mini-app/src/pages/Programs.jsx
import BuilderSlideOver from '@shared/builder/BuilderSlideOver.jsx';
import * as pitcherApi from '../api';
const minApi = {
  fetchCandidates: (env) => pitcherApi.fetchBuilderCandidates(env, initData),
  sendTurn:        (sid, msg) => pitcherApi.sendBuilderTurn(sid, msg, initData),
  finalize:        (sid, tid, spec) => pitcherApi.finalizeBuilder(sid, tid, spec, initData),
  activateProgram: (pid) => pitcherApi.activateProgram(pid, initData),
  archiveProgram:  (pid, reason) => pitcherApi.archiveProgram(pid, reason, initData),
  interpretGoal:   (text, domain) => pitcherApi.interpretGoal(text, domain, initData),
};
<BuilderSlideOver api={minApi} ... />
```

```jsx
// coach-app uses its own api.js + JWT
const coachApi = {
  fetchCandidates: (env) => coachPostApi('/api/coach/programs/builder/candidates', env),
  sendTurn:        (sid, msg) => coachPostApi('/api/coach/programs/builder/turn', {session_id: sid, user_message: msg}),
  // ...
};
<BuilderSlideOver api={coachApi} interview_mode="team_personalize" ... />
```

**Steps:**
- [ ] Move file + tests to `shared/builder/`
- [ ] Refactor to accept `api` + auth props
- [ ] Update mini-app Programs.jsx to pass `minApi`
- [ ] Update vite + vitest configs in both apps (verify `@shared` aliases work)
- [ ] `npm run test:run` in mini-app → expected 66 passed (no regression)
- [ ] Commit: `refactor(plan-7/c0): extract BuilderSlideOver to shared/builder/`

**Acceptance:** Mini-app behavior unchanged. Tests still green. Coach-app can now `import BuilderSlideOver from '@shared/builder/BuilderSlideOver.jsx'`.

---

### Task C1: Team Overview program strip per pitcher

**Files:**
- Modify: `pitcher_program_app/coach-app/src/components/team-overview/HeroCard.jsx`
- Modify: `pitcher_program_app/coach-app/src/components/team-overview/CompactCard.jsx`
- Modify: `pitcher_program_app/coach-app/src/pages/TeamOverview.jsx` (fetch active programs per pitcher)
- Modify: `pitcher_program_app/coach-app/src/api.js` (add `fetchPitcherActivePrograms`)
- Modify: `pitcher_program_app/coach-app/src/components/team-overview/__tests__/HeroCard.test.jsx`

**Approach:** HeroCard + CompactCard gain a 2-row program strip showing `[Throwing] velocity_12wk · Day 22/84` and `[Lifting] hypertrophy_8wk · Day 8/56`. Pulled from `/api/coach/pitcher/{id}/programs?status=active`. Phase divergence pill if throwing_phase ≠ lifting_phase (Plan 1 enabled the data).

**Key signatures:**

```javascript
// coach-app/src/api.js
export async function fetchPitcherActivePrograms(pitcherId, accessToken) {
  return fetchCoachApi(`/api/coach/pitcher/${pitcherId}/programs?status=active`, accessToken);
}
```

```jsx
// coach-app/src/components/team-overview/ProgramStrip.jsx (new)
export default function ProgramStrip({ programs }) {
  if (!programs || programs.length === 0) return null;
  return (
    <div data-testid="program-strip" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {programs.map(p => (
        <div key={p.program_id} style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>
          [{p.domain[0].toUpperCase()}{p.domain.slice(1)}] {p.parent_template_id} ·
          Day {(p.current_day_index ?? 0) + 1}
          {p.held_days_count > 0 && ` · Held ${p.held_days_count}`}
        </div>
      ))}
    </div>
  );
}
```

**Tests:** +3 coach-app vitest tests — strip renders both domains, omits when no programs, shows held days.

**Steps:**
- [ ] Create `ProgramStrip.jsx`
- [ ] Add `fetchPitcherActivePrograms` to api.js
- [ ] Render `<ProgramStrip>` inside HeroCard + CompactCard
- [ ] Fetch active programs per pitcher in TeamOverview.jsx (one parallel fetch per roster row — or fold into the existing `/team/overview` payload, see follow-up below)
- [ ] Write 3 vitest tests
- [ ] `npm run test:run` → expected 84 passed
- [ ] Commit: `feat(plan-7/c1): Team Overview program strip per pitcher`

**Acceptance:** Each pitcher card on Team Overview shows their active programs. Phase divergence pill shown when the two phases differ.

**Follow-up note:** Roster-wide per-pitcher fetch is N+1. If perf bites, add `active_programs` field to `/api/coach/team/overview` payload. Defer until measured.

---

### Task C2: PlayerSlideOver Programs tab (5th tab)

**Files:**
- Modify: `pitcher_program_app/coach-app/src/components/PlayerSlideOver.jsx` (add 5th tab)
- Create: `pitcher_program_app/coach-app/src/components/PlayerPrograms.jsx`
- Create: `pitcher_program_app/coach-app/src/components/PlayerPrograms.test.jsx`

**Approach:** Add a Programs tab alongside Today / Week / History / Profile. Content:
- **Active programs** (read-only via A3-coach)
- **Drafts** (D14 completed-only, via A3-coach)
- **History** (archived)
- **Hold event log** (last 30 days, signature read from `program_hold_events`)
- **Phase override controls** — coach can set per-pitcher `pitcher_training_model.coach_phase_overrides.{throwing_phase, lifting_phase}` (Plan 1 added this column). Writes are audited via existing `coach_actions` table.

**Key shape:**

```jsx
// coach-app/src/components/PlayerPrograms.jsx
export default function PlayerPrograms({ pitcherId, accessToken }) {
  const programs = useCoachApi(`/api/coach/pitcher/${pitcherId}/programs`, accessToken);
  const drafts = useCoachApi(`/api/coach/pitcher/${pitcherId}/drafts`, accessToken);
  // ... render sections
}
```

Phase override controls write via a new tiny endpoint:

```python
# api/coach_routes.py
@coach_router.patch("/pitcher/{pitcher_id}/phase-override")
async def coach_patch_phase_override(pitcher_id: str, req: PhaseOverrideRequest, request: Request):
    """Coach overrides per-pitcher phase. Audited."""
    await require_coach_auth(request)
    team_id = request.state.team_id
    coach_id = request.state.coach_id
    _require_team_pitcher(pitcher_id, team_id)
    # write override + insert coach_actions row
    ...
```

**Tests:** +5 coach-app vitest tests — Programs tab renders, drafts visible, hold log renders, phase override controls write + audit.

**Steps:**
- [ ] Create `PlayerPrograms.jsx` component
- [ ] Add 5th tab to PlayerSlideOver
- [ ] Add `PATCH /api/coach/pitcher/{id}/phase-override` endpoint + backend test
- [ ] Write 5 coach-app vitest tests
- [ ] `npm run test:run` → expected 89 passed
- [ ] Commit: `feat(plan-7/c2): PlayerSlideOver Programs tab + phase override`

**Acceptance:** Click PlayerSlideOver → Programs tab → see active/drafts/history. Override phase → row in `coach_actions` confirms audit.

---

### Task C3: Team Programs page rebuild

**Files:**
- Modify: `pitcher_program_app/coach-app/src/pages/TeamPrograms.jsx` (rebuild)
- Modify: `pitcher_program_app/coach-app/src/components/team-programs/CreateProgramSlideOver.jsx` (replace body with `<BuilderSlideOver>`)
- Create: `pitcher_program_app/coach-app/src/components/team-programs/PlayerBuiltProgramsStrip.jsx`

**Approach:** Per Plan 6 spec D10 coach side. Sections:
- Masthead with "+ Build Program" actionSlot
- Scoreboard (existing)
- Active Team Programs grid (existing BlockCard rebuild from Spec 3)
- Library of canonical templates (uses A12 endpoint)
- Player-built programs roster strip (new — shows recent pitcher-built programs across team)

**Key change:** Replace existing `CreateProgramSlideOver`'s body with `<BuilderSlideOver api={coachApi} interview_mode="..." />` driven by C4's entry-point selector.

**Steps:**
- [ ] Rebuild `TeamPrograms.jsx`
- [ ] Replace `CreateProgramSlideOver` body with shared BuilderSlideOver
- [ ] Add `PlayerBuiltProgramsStrip` reading from `/api/coach/programs/recent-player-built` (new tiny endpoint)
- [ ] Write 4 vitest tests
- [ ] `npm run test:run` → expected 93 passed
- [ ] Commit: `feat(plan-7/c3): Team Programs page rebuild`

**Acceptance:** TeamPrograms page lists active team programs + canonical templates library + recent player builds. "+ Build Program" opens C4's selector.

---

### Task C4: Build entry-point selector + BuilderSlideOver coach wiring

**Files:**
- Create: `pitcher_program_app/coach-app/src/components/BuildEntrypointSelector.jsx`
- Modify: `pitcher_program_app/coach-app/src/api.js` (add coach builder client fns)
- Modify: `pitcher_program_app/coach-app/src/components/team-programs/CreateProgramSlideOver.jsx`

**Approach:** Modal sheet from `+ Build Program`:
- "Build a team program" → opens BuilderSlideOver with `interview_mode="team_personalize"`
- "Build for a specific pitcher" → pitcher-picker first, then BuilderSlideOver with `interview_mode="personalize"` + `pitcherIdForCoach`
- "Author a new template" → BuilderSlideOver with `interview_mode="authoring"`

All three reuse the same `<BuilderSlideOver>` component from `shared/builder/`.

**Key shape:**

```jsx
// coach-app/src/components/BuildEntrypointSelector.jsx
export default function BuildEntrypointSelector({ onPick, onClose }) {
  return (
    <Modal onClose={onClose}>
      <button onClick={() => onPick({ mode: 'team_personalize' })}>Build a team program</button>
      <button onClick={() => onPick({ mode: 'personalize_for_pitcher' })}>Build for a specific pitcher</button>
      <button onClick={() => onPick({ mode: 'authoring' })}>Author a new template</button>
    </Modal>
  );
}
```

```jsx
// In CreateProgramSlideOver (the existing chrome from Spec 3):
const [pickedMode, setPickedMode] = useState(null);
const [pickedPitcher, setPickedPitcher] = useState(null);

return pickedMode === null ? (
  <BuildEntrypointSelector onPick={({mode}) => setPickedMode(mode)} onClose={onClose} />
) : pickedMode === 'personalize_for_pitcher' && !pickedPitcher ? (
  <PitcherPicker onPick={setPickedPitcher} onClose={onClose} />
) : (
  <BuilderSlideOver
    api={coachApi}
    interview_mode={pickedMode === 'personalize_for_pitcher' ? 'personalize' : pickedMode}
    pitcherIdForCoach={pickedPitcher?.pitcher_id}
    onClose={onClose}
    onProgramActivated={...}
  />
);
```

**Steps:**
- [ ] Create `BuildEntrypointSelector` + `PitcherPicker` components
- [ ] Wire CreateProgramSlideOver state machine
- [ ] Add coach api client fns for all 6 builder endpoints
- [ ] Write 6 vitest tests covering the 3 paths × mode propagation
- [ ] `npm run test:run` → expected 99 passed
- [ ] Commit: `feat(plan-7/c4): Build entry-point selector + BuilderSlideOver coach wiring`

**Acceptance:** Coach taps "+ Build Program" → picks entry point → Builder slide-over opens in correct mode. All 3 modes drive the existing Plan 3 backend prompt variants.

---

### Task C5: Phases page — Templates available column

**Files:**
- Modify: `pitcher_program_app/coach-app/src/pages/Phases.jsx`
- Modify: `pitcher_program_app/coach-app/src/components/phases/PhaseTimeline.jsx`

**Approach:** Each phase in the timeline gains a "Templates available in this phase" column. Read from A12 endpoint `?phase=...`. Display as inline chips next to phase block.

**Tests:** +2 vitest tests.

**Steps:**
- [ ] Fetch templates per phase
- [ ] Render chip group in PhaseTimeline
- [ ] Write 2 tests
- [ ] `npm run test:run` → expected 101 passed
- [ ] Commit: `feat(plan-7/c5): Phases page Templates column`

**Acceptance:** Each phase in the timeline shows applicable templates.

---

### Task C6: Insights page wired to A4 insight types

**Files:**
- Modify: `pitcher_program_app/coach-app/src/components/insights/InsightCard.jsx` (extend with new `suggestion_type` rendering)
- Modify: `pitcher_program_app/coach-app/src/pages/Insights.jsx`

**Approach:** Insights page already (Spec 3) reads from `coach_suggestions`. A4 writes new `suggestion_type` values. Update InsightCard to render the new types with appropriate copy/CTAs:
- `program_drift` → "Archive program" / "Accept new pace" buttons
- `program_flag_mismatch` → "Open program" → opens PlayerSlideOver Programs tab
- `team_program_lagging` → "Open team block" → navigates to TeamPrograms

**Tests:** +3 vitest tests.

**Steps:**
- [ ] Extend InsightCard to handle 3 new suggestion_types
- [ ] Wire CTA navigation
- [ ] Write 3 tests
- [ ] `npm run test:run` → expected 104 passed
- [ ] Commit: `feat(plan-7/c6): Insights page renders A4 insight types`

**Acceptance:** Drift/mismatch/lag insights surface on Insights page with appropriate CTAs.

---

### Task C7: Category scores 3-stat row + flagged-feed copy (folded adjacent)

**Files:**
- Modify: `pitcher_program_app/coach-app/src/components/PlayerToday.jsx` (add 3-stat row)
- Modify: `pitcher_program_app/coach-app/src/components/team-overview/CompactCard.jsx` (flag copy uses driving category)
- Modify: `pitcher_program_app/coach-app/src/components/team-overview/HeroCard.jsx` (same)

**Approach:** Backend persisted `category_scores` and `baseline_tier` since Phase 1 (2026-04-21). Surface them:
- **PlayerToday tab**: 3-stat row showing tissue / load / recovery scores (0-10 each), labeled with the lowest as "driving"
- **Flag pill copy**: instead of just "YELLOW", show "YELLOW · tissue 2.3" when the driving category is tissue. Lift from `daily_entries.pre_training.category_scores`.

**Steps:**
- [ ] Add 3-stat row to PlayerToday
- [ ] Add category to flag pill copy in Hero/Compact cards
- [ ] Write 4 vitest tests
- [ ] `npm run test:run` → expected 108 passed
- [ ] Commit: `feat(plan-7/c7): coach-app Phase 1 surfacing — category scores + flag copy`

**Acceptance:** Category scores visible on every coach surface. Flag copy cites the driving category.

---

# Phase D — Verification + tag

### Task D1: Full suites green

- [ ] `pytest -q` from `pitcher_program_app/` → target ~790 passed / 8 skipped
- [ ] `npm run test:run` from `pitcher_program_app/mini-app/` → target ~70 passed
- [ ] `npm run test:run` from `pitcher_program_app/coach-app/` → target ~110 passed
- [ ] Goldens: `pytest tests/test_legacy_plan_generator_golden.py -v` → 2/2

### Task D2: Manual smoke flow

- [ ] **Coach builds for a pitcher**: log into coach-app → TeamPrograms → + Build Program → "Build for a specific pitcher" → pick landon_brice → Inputs (Throwing / Velocity / 12wk / Off-season) → Socratic → Preview → Activate
- [ ] **Mini-app shows new program**: open mini-app as landon → Programs tab → see new active program → ribbon on Home
- [ ] **Coach fans out as team program**: + Build Program → "team program" → activates for full roster (verify in `programs` table that all team pitchers got rows)
- [ ] **Drift insight fires**: skip landon's check-in for 6 days → next 9am digest should generate a `program_drift` row visible on Insights
- [ ] **Phase override audited**: coach changes landon's `lifting_phase` to `preseason` → row in `coach_actions` with `action_type=phase_override`
- [ ] **Mini-app "Other" goal**: pitcher picks Other / describe… → types "I want to rebuild after rotator cuff surgery" → LLM returns `arm_health` → candidates flow continues
- [ ] **Browse Templates**: Programs tab → bottom section → expand → see 6 templates (4 throwing + 2 lifting) → tap "Build with this template" → opens slide-over pre-filled

### Task D3: Tag

```bash
git tag program-builder-v1-complete
git push origin program-builder-v1-complete
```

- [ ] Update CLAUDE.md masthead with Plan 7 row + flip "What's Next" to Plan 8 + Tier 2 + ongoing items
- [ ] Commit + push docs
- [ ] Open PR titled "Program Builder v1 Complete (Plan 7)"
- [ ] Merge after dogfood window

---

## Acceptance Criteria (top-level)

1. ✅ Coaches can build programs for individual pitchers via Socratic flow (C2/C4)
2. ✅ Coaches can build team programs that fan out across roster (C3/C4)
3. ✅ Coaches can author new templates via Socratic authoring mode (C4)
4. ✅ Drift / mismatch / team-lag insights generate daily and surface on Insights page (A4 / C6)
5. ✅ Coach can override per-pitcher phase with audit trail (C2)
6. ✅ Pitchers can describe goals in natural language, LLM maps to template tag (A11 / B11)
7. ✅ Pitchers have lifting templates available end-to-end (A13 / B12)
8. ✅ Pitchers can browse all canonical templates from Programs tab (A12 / B13)
9. ✅ Pitchers see next scheduled throw inline on Active program card (A14 / B14)
10. ✅ Telegram BackButton works on all slide-overs (B15)
11. ✅ Legacy `saved_plans` writes log deprecation warnings; mini-app "Save this plan" CTA removed (A15 / B16)
12. ✅ Coach-app surfaces tissue/load/recovery scores + driving category in flag copy (C7)
13. ✅ All test suites green; tag `program-builder-v1-complete` pushed (D)

## Open questions to revisit during execution

- **A4 insights frequency**: locked to daily (9am digest) per L5. If the volume is too low or too high after 1 week, adjust threshold params (drift days, completion %).
- **C0 BuilderSlideOver `api` prop shape**: 6 functions today. If new endpoints land in Plan 8, expand the prop interface — don't smuggle imports back in.
- **C1 N+1 perf**: if coach Team Overview gets slow with 12 pitchers, fold `active_programs` into the `/team/overview` payload.
- **C2 phase override UX**: the override controls write to `pitcher_training_model.coach_phase_overrides`. Currently this is read by `program_runtime.get_effective_phase` but only on read. Decide if we should also re-run any in-flight program's anchoring when phase changes (likely yes — fire A5 `/recompute` after override write).

## Branch + push strategy

Plan 7 lands as **one PR** (matching Plan 6 pattern). Approximate size: ~5K LOC across backend + mini-app + coach-app. Feature flag posture stays the same — `program_aware_plan_gen` controls which pitchers get the program-aware path. Coach-app changes are not behind a flag (read-only views are safe; mutations require coach auth which already gates blast radius).

Migration apply: **A13 lifting templates migration applied via MCP BEFORE PR opens** (idempotent UPSERT pattern proven by 028). All other migrations are documentation in this PR.

Rollout cadence after merge: 3-day dogfood on `landon_brice` (continued), 3-day expansion to all coach-app users, then full mini-app feature flag rollout.
