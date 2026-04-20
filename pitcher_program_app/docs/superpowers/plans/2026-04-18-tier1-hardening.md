# Tier 1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close four highest-leverage Tier 1 gaps: coach sidebar team name, exercise-library dual-source bug, `morning_brief` shape inconsistency, and latent TypeError at `context_manager.py:173`.

**Architecture:** Supabase `exercises` becomes canonical at runtime (15-min snapshot cache + lazy-miss); JSON demoted to seed-only via pre-commit hook. Exercise names are hydrated at every write boundary (plan gen, swap, mutation) so `daily_entries` rows always carry `name`. Shared `parseBrief` util replaces four scattered typeof checks; backend writes canonical JSON-string briefs. Belt-and-suspenders: frontend keeps `exerciseMap` fallback and logs misses to new `ui_fallback_log` + admin Telegram DM (24h rate limit per exercise_id).

**Tech Stack:** Python 3.11, FastAPI, APScheduler (via `python-telegram-bot` job_queue), Supabase (Postgres), React 18 + Vite, plain JS shared util.

**Companion spec:** [docs/superpowers/specs/2026-04-17-tier1-hardening-design.md](../specs/2026-04-17-tier1-hardening-design.md) — read this first for rationale behind each decision (D1–D24).

---

## File Structure

**New files:**
- `pitcher_program_app/shared/parseBrief.js` — tolerant brief parser used by mini-app + coach-app
- `pitcher_program_app/scripts/seed_exercises_from_json.py` — idempotent upsert seed
- `pitcher_program_app/scripts/hooks/pre-commit` — installable git hook (exits 0 on failure)
- `pitcher_program_app/tests/test_hydrate_exercises.py`
- `pitcher_program_app/tests/test_normalize_brief.py`
- `pitcher_program_app/tests/test_parse_brief.mjs` — node-run test for shared util
- Supabase migration: new `ui_fallback_log` table

**Modified files:**
- `pitcher_program_app/bot/services/context_manager.py:173` — str coercion
- `pitcher_program_app/api/coach_auth.py` — attach `team_name` to `request.state`
- `pitcher_program_app/bot/services/db.py` — add `get_team(team_id)` helper
- `pitcher_program_app/api/coach_routes.py:31` — enrich `/auth/exchange` response
- `pitcher_program_app/coach-app/src/hooks/useCoachAuth.jsx` — store team_name in ctx
- `pitcher_program_app/coach-app/src/components/Shell.jsx` — already reads `coach?.team_name`
- `pitcher_program_app/mini-app/vite.config.js` + `coach-app/vite.config.js` — `@shared` alias
- `pitcher_program_app/mini-app/src/pages/Coach.jsx:39,132,148` — use `parseBrief`
- `pitcher_program_app/mini-app/src/components/MorningBriefCard.jsx` — use `parseBrief`
- `pitcher_program_app/coach-app/src/components/PlayerToday.jsx:31` — use `parseBrief`
- `pitcher_program_app/coach-app/src/components/PlayerWeek.jsx:43` — use `parseBrief`
- `pitcher_program_app/bot/services/checkin_service.py` — add `normalize_brief`, apply at writes
- `pitcher_program_app/bot/services/plan_generator.py:353-360,373-386` — call `hydrate_exercises`, collapse brief logic
- `pitcher_program_app/api/routes.py:661,688,1001,1038,1205-1215,1377+,1651+` — apply `normalize_brief`, rewrite `/api/exercises`, hydrate in swap/mutations
- `pitcher_program_app/bot/services/exercise_pool.py` — snapshot cache + hydrate helper
- `pitcher_program_app/bot/main.py` — 15-min snapshot refresh job, 30-day prune in 9am digest
- `pitcher_program_app/mini-app/src/components/DailyCard.jsx`, `ExerciseRow.jsx`, `MutationPreview.jsx` — fallback telemetry
- `pitcher_program_app/coach-app/src/hooks/useCoachAuth.jsx` — fetch & expose `exerciseMap`
- `pitcher_program_app/coach-app/src/components/PlayerToday.jsx` / other exercise renderers — fallback telemetry + exerciseMap consumption
- `pitcher_program_app/data/knowledge/exercise_library.json` — seed-file header comment
- `pitcher_program_app/CLAUDE.md` — update Known Issues; document seed workflow

---

## Task 1: Fix latent TypeError in `context_manager.py:173`

**Files:**
- Modify: `pitcher_program_app/bot/services/context_manager.py:173`
- Test: `pitcher_program_app/tests/test_context_manager_coercion.py` (new)

- [ ] **Step 1: Write the failing test**

Create `pitcher_program_app/tests/test_context_manager_coercion.py`:

```python
"""Regression test: context_manager slices recent interactions safely.

Covers D4 — msg['content'] can theoretically be a dict from bad upstream data.
The line used [:200] on .get('content', '') which TypeErrors on dicts.
"""
from unittest.mock import patch
from bot.services import context_manager


def test_load_context_handles_non_string_content(monkeypatch):
    # Arrange: chat_history returns a message with dict content (bad data)
    bad_messages = [
        {"created_at": "2026-04-18T09:00:00", "role": "user", "content": {"text": "hi"}},
        {"created_at": "2026-04-18T09:01:00", "role": "bot", "content": None},
        {"created_at": "2026-04-18T09:02:00", "role": "user", "content": "normal string"},
    ]
    monkeypatch.setattr(
        "bot.services.context_manager._db.get_chat_history",
        lambda pid, limit=15: bad_messages,
    )
    monkeypatch.setattr(
        "bot.services.context_manager.load_profile",
        lambda pid: {"name": "Test", "pitcher_id": pid},
    )
    monkeypatch.setattr(
        "bot.services.context_manager.get_recent_entries",
        lambda pid, days=14: [],
    )

    # Act: must not raise TypeError
    result = context_manager.load_context("test_pitcher_001")

    # Assert: output is a string and contains all three messages in some form
    assert isinstance(result, str)
    assert "normal string" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_context_manager_coercion.py -v`
Expected: FAIL with `TypeError: unhashable type` or `TypeError: 'NoneType' object is not subscriptable` originating inside `load_context`.

- [ ] **Step 3: Apply the str coercion fix**

In [bot/services/context_manager.py:173](../../bot/services/context_manager.py:173), change:

```python
            content = msg.get("content", "")[:200]
```

to:

```python
            content = str(msg.get("content", "") or "")[:200]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd pitcher_program_app && python -m pytest tests/test_context_manager_coercion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/context_manager.py pitcher_program_app/tests/test_context_manager_coercion.py
git commit -m "fix(context-manager): coerce chat content to str before slicing (D4)"
```

---

## Task 2: Coach auth enrichment — `team_name` on `/auth/exchange`

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py` (add `get_team`)
- Modify: `pitcher_program_app/api/coach_auth.py` (attach `team_name` to request.state)
- Modify: `pitcher_program_app/api/coach_routes.py:31` (return `team_name`)
- Modify: `pitcher_program_app/coach-app/src/hooks/useCoachAuth.jsx` (context carries team_name)
- `coach-app/src/components/Shell.jsx` already reads `coach?.team_name` — verify no change needed
- Test: `pitcher_program_app/tests/test_coach_auth_enrichment.py` (new)

### Step 2a: Add `get_team` db helper

- [ ] **Step 1: Write the failing test**

Add to `pitcher_program_app/tests/test_coach_auth_enrichment.py`:

```python
"""Tests D1, D18: coach auth exchange returns team_name; /me stays identity-shaped."""
import os
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_auth_exchange_includes_team_name(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    # Mock the team lookup
    monkeypatch.setattr(
        "bot.services.db.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.post("/api/coach/auth/exchange")
    assert res.status_code == 200
    body = res.json()
    assert body["team_name"] == "UChicago Baseball"
    assert body["coach_id"] == "dev_coach"
    assert body["team_id"] == "uchicago_baseball"


def test_coach_me_stays_identity_shaped(monkeypatch):
    """D18: /me does NOT include team_name."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setattr(
        "bot.services.db.get_team",
        lambda team_id: {"team_id": team_id, "name": "UChicago Baseball"},
    )
    from api.main import app
    client = TestClient(app)

    res = client.get("/api/coach/me")
    assert res.status_code == 200
    body = res.json()
    assert "team_name" not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_coach_auth_enrichment.py -v`
Expected: FAIL — `get_team` does not exist AND response missing `team_name`.

- [ ] **Step 3: Add `get_team` to `bot/services/db.py`**

Append after `get_coach_by_supabase_id` (currently the last function around line 656):

```python
# --- teams ---

def get_team(team_id: str) -> dict | None:
    """Look up a team row by its primary key."""
    resp = (
        get_client().table("teams")
        .select("*")
        .eq("team_id", team_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None
```

- [ ] **Step 4: Attach `team_name` in `coach_auth.py`**

In [api/coach_auth.py](../../api/coach_auth.py), modify `require_coach_auth`:

```python
async def require_coach_auth(request: Request) -> None:
    """FastAPI dependency that validates coach auth and attaches identity to request.state."""
    # Allow bypassing auth in dev
    if os.getenv("DISABLE_AUTH", "").lower() == "true":
        request.state.coach_id = "dev_coach"
        request.state.team_id = "uchicago_baseball"
        request.state.coach_name = "Dev Coach"
        request.state.coach_role = "head"
        from bot.services.db import get_team
        team = get_team(request.state.team_id) or {}
        request.state.team_name = team.get("name", "")
        return

    coach = _validate_coach_jwt(request)
    request.state.coach_id = coach["coach_id"]
    request.state.team_id = coach["team_id"]
    request.state.coach_name = coach["name"]
    request.state.coach_role = coach.get("role", "")
    from bot.services.db import get_team
    team = get_team(coach["team_id"]) or {}
    request.state.team_name = team.get("name", "")
```

- [ ] **Step 5: Enrich `/auth/exchange` response (leave `/me` alone per D18)**

In [api/coach_routes.py:31](../../api/coach_routes.py:31) replace the `auth_exchange` body:

```python
@coach_router.post("/auth/exchange")
async def auth_exchange(request: Request):
    """Validate Supabase JWT and return domain identity + team name (D1, D18)."""
    await require_coach_auth(request)
    return {
        "coach_id": request.state.coach_id,
        "team_id": request.state.team_id,
        "coach_name": request.state.coach_name,
        "role": request.state.coach_role,
        "team_name": request.state.team_name,
    }
```

Do NOT modify `/me` (stays identity-shaped).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd pitcher_program_app && python -m pytest tests/test_coach_auth_enrichment.py -v`
Expected: both tests PASS.

### Step 2b: Wire into coach-app auth context

- [ ] **Step 7: Update `useCoachAuth.jsx` to carry `team_name`**

The existing hook already does `setCoach(data)` with whatever `/auth/exchange` returns — so `data.team_name` will flow through automatically. Add nothing; verify by reading [coach-app/src/hooks/useCoachAuth.jsx:43-44](../../coach-app/src/hooks/useCoachAuth.jsx:43). Confirm [Shell.jsx:20](../../coach-app/src/components/Shell.jsx:20) already uses `coach?.team_name || 'Dashboard'`. No frontend edit needed for this step — it "just works" once backend returns `team_name`.

- [ ] **Step 8: Commit**

```bash
git add pitcher_program_app/bot/services/db.py pitcher_program_app/api/coach_auth.py pitcher_program_app/api/coach_routes.py pitcher_program_app/tests/test_coach_auth_enrichment.py
git commit -m "feat(coach-auth): return team_name from /auth/exchange; sidebar shows team (D1, D18)"
```

---

## Task 3: Canonical `morning_brief` shape — frontend-first deploy

**Order per D20:** shared util + readers ship first (tolerant of old + new shapes), then backend writers.

### Step 3a: Shared `parseBrief` util + frontend readers

**Files:**
- Create: `pitcher_program_app/shared/parseBrief.js`
- Create: `pitcher_program_app/tests/test_parse_brief.mjs`
- Modify: `pitcher_program_app/mini-app/vite.config.js` (+ `@shared` alias)
- Modify: `pitcher_program_app/coach-app/vite.config.js` (+ `@shared` alias)
- Modify: `pitcher_program_app/mini-app/src/pages/Coach.jsx:40,132,148`
- Modify: `pitcher_program_app/mini-app/src/components/MorningBriefCard.jsx`
- Modify: `pitcher_program_app/coach-app/src/components/PlayerToday.jsx:31`
- Modify: `pitcher_program_app/coach-app/src/components/PlayerWeek.jsx:43`

- [ ] **Step 1: Write the failing node test for `parseBrief`**

Create `pitcher_program_app/tests/test_parse_brief.mjs`:

```javascript
// Run with: node --test tests/test_parse_brief.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseBrief } from '../shared/parseBrief.js';

test('null/undefined/empty → empty object', () => {
  assert.deepEqual(parseBrief(null), {});
  assert.deepEqual(parseBrief(undefined), {});
  assert.deepEqual(parseBrief(''), {});
});

test('plain string → { coaching_note: <string> }', () => {
  const res = parseBrief('Focus on recovery today.');
  assert.equal(res.coaching_note, 'Focus on recovery today.');
});

test('JSON stringified dict → parsed object with coaching_note passthrough', () => {
  const raw = JSON.stringify({ coaching_note: 'rest', arm_verdict: { status: 'green', value: '8/10' } });
  const res = parseBrief(raw);
  assert.equal(res.coaching_note, 'rest');
  assert.equal(res.arm_verdict.status, 'green');
});

test('garbage string that is not JSON → coaching_note falls back to raw', () => {
  const raw = '{not valid json';
  const res = parseBrief(raw);
  assert.equal(res.coaching_note, '{not valid json');
});

test('JSON of a non-object (array, number) → empty object', () => {
  assert.deepEqual(parseBrief('[1,2,3]'), {});
  assert.deepEqual(parseBrief('42'), {});
});

test('already-parsed object passed in → returned as-is', () => {
  const obj = { coaching_note: 'done' };
  assert.deepEqual(parseBrief(obj), obj);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd pitcher_program_app && node --test tests/test_parse_brief.mjs`
Expected: FAIL — module `../shared/parseBrief.js` does not exist.

- [ ] **Step 3: Create the shared util**

Create `pitcher_program_app/shared/parseBrief.js`:

```javascript
/**
 * parseBrief — tolerant morning_brief parser.
 *
 * Historically morning_brief could be any of:
 *   • a plain string ("Focus on recovery today.")
 *   • a JSON-stringified dict with coaching_note + other keys
 *   • null / undefined
 *   • malformed garbage
 *
 * parseBrief always returns an object so readers can destructure safely.
 * Per D8, the envelope is free-form — readers pick off keys they recognize.
 *
 * @param {unknown} raw
 * @returns {{ coaching_note?: string, [key: string]: unknown }}
 */
export function parseBrief(raw) {
  if (raw == null || raw === '') return {};
  if (typeof raw === 'object') return raw;
  if (typeof raw !== 'string') return {};

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed;
    }
    return {};
  } catch (_err) {
    // Legacy plain-string brief — wrap it as coaching_note
    return { coaching_note: raw };
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd pitcher_program_app && node --test tests/test_parse_brief.mjs`
Expected: PASS (6/6).

- [ ] **Step 5: Wire `@shared` alias in both Vite configs**

In `pitcher_program_app/mini-app/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  base: '/',
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
})
```

In `pitcher_program_app/coach-app/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5174 },
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
})
```

- [ ] **Step 6: Replace mini-app typeof checks**

In [mini-app/src/pages/Coach.jsx](../../mini-app/src/pages/Coach.jsx) near the top (alongside other imports), add:

```javascript
import { parseBrief } from '@shared/parseBrief.js';
```

Replace line 40:

```javascript
  const rawBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const morningBrief = typeof rawBrief === 'string' ? rawBrief : null;
```

with:

```javascript
  const rawBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const parsedBrief = parseBrief(rawBrief);
  const morningBrief = parsedBrief.coaching_note || (typeof rawBrief === 'string' && !rawBrief.trim().startsWith('{') ? rawBrief : null);
```

Replace line 132:

```javascript
            content: typeof res.morning_brief === 'string' ? res.morning_brief : 'Your plan is ready.',
```

with:

```javascript
            content: parseBrief(res.morning_brief).coaching_note || 'Your plan is ready.',
```

Replace line 148:

```javascript
            content: typeof res.morning_brief === 'string' ? res.morning_brief : 'Baseline plan ready.',
```

with:

```javascript
            content: parseBrief(res.morning_brief).coaching_note || 'Baseline plan ready.',
```

- [ ] **Step 7: Align `MorningBriefCard.jsx` to use shared util**

In [mini-app/src/components/MorningBriefCard.jsx](../../mini-app/src/components/MorningBriefCard.jsx), add import at top:

```javascript
import { parseBrief } from '@shared/parseBrief.js';
```

Replace the `parseStructuredBrief` function (lines 13-28) with:

```javascript
/**
 * Attempt to parse a structured morning brief. Returns the parsed object
 * if it looks like a structured brief (has arm_verdict), otherwise null.
 */
export function parseStructuredBrief(raw) {
  const obj = parseBrief(raw);
  if (obj && typeof obj.arm_verdict === 'object') return obj;
  return null;
}
```

- [ ] **Step 8: Replace coach-app typeof checks**

In [coach-app/src/components/PlayerToday.jsx](../../coach-app/src/components/PlayerToday.jsx), add import near top:

```javascript
import { parseBrief } from '@shared/parseBrief.js'
```

Replace lines 31-33:

```javascript
            {typeof todayEntry.morning_brief === 'string'
              ? todayEntry.morning_brief
              : todayEntry.morning_brief?.coaching_note || ''}
```

with:

```javascript
            {parseBrief(todayEntry.morning_brief).coaching_note || (typeof todayEntry.morning_brief === 'string' && !todayEntry.morning_brief.trim().startsWith('{') ? todayEntry.morning_brief : '')}
```

In [coach-app/src/components/PlayerWeek.jsx](../../coach-app/src/components/PlayerWeek.jsx), add import near top:

```javascript
import { parseBrief } from '@shared/parseBrief.js'
```

Replace lines 43-45:

```javascript
                {typeof e.morning_brief === 'string'
                  ? e.morning_brief
                  : e.morning_brief?.coaching_note || ''}
```

with:

```javascript
                {parseBrief(e.morning_brief).coaching_note || (typeof e.morning_brief === 'string' && !e.morning_brief.trim().startsWith('{') ? e.morning_brief : '')}
```

- [ ] **Step 9: Verify both frontends still build**

Run:
```bash
cd pitcher_program_app/mini-app && npm run build 2>&1 | tail -20
cd ../coach-app && npm run build 2>&1 | tail -20
```
Expected: both succeed. `@shared/parseBrief.js` resolves.

- [ ] **Step 10: Commit**

```bash
git add pitcher_program_app/shared/ pitcher_program_app/tests/test_parse_brief.mjs pitcher_program_app/mini-app/vite.config.js pitcher_program_app/coach-app/vite.config.js pitcher_program_app/mini-app/src/pages/Coach.jsx pitcher_program_app/mini-app/src/components/MorningBriefCard.jsx pitcher_program_app/coach-app/src/components/PlayerToday.jsx pitcher_program_app/coach-app/src/components/PlayerWeek.jsx
git commit -m "refactor(brief): centralize brief parsing in shared/parseBrief; tolerant readers (D3, D8, D15)"
```

### Step 3b: Backend canonical write

**Deploy Step 3a first, verify readers render existing briefs unchanged, THEN ship 3b (per D20).**

**Files:**
- Modify: `pitcher_program_app/bot/services/checkin_service.py` (add `normalize_brief`, apply at writes)
- Modify: `pitcher_program_app/bot/services/plan_generator.py:353-360` (delegate to `normalize_brief`)
- Modify: `pitcher_program_app/api/routes.py:661,688,1001,1038` (apply `normalize_brief`)
- Test: `pitcher_program_app/tests/test_normalize_brief.py` (new)

- [ ] **Step 1: Write the failing test**

Create `pitcher_program_app/tests/test_normalize_brief.py`:

```python
"""D3: morning_brief is always stored as a JSON-string with a stable envelope."""
import json
import pytest
from bot.services.checkin_service import normalize_brief


def test_normalize_none_returns_empty_json_object():
    assert normalize_brief(None) == json.dumps({})


def test_normalize_empty_string_returns_empty_json_object():
    assert normalize_brief("") == json.dumps({})


def test_normalize_plain_string_wraps_in_coaching_note():
    out = normalize_brief("Focus on recovery.")
    assert json.loads(out) == {"coaching_note": "Focus on recovery."}


def test_normalize_dict_serializes_verbatim():
    data = {"coaching_note": "rest", "arm_verdict": {"status": "green"}}
    out = normalize_brief(data)
    assert json.loads(out) == data


def test_normalize_already_json_string_passes_through():
    raw = json.dumps({"coaching_note": "already json"})
    out = normalize_brief(raw)
    assert json.loads(out) == {"coaching_note": "already json"}


def test_normalize_malformed_json_string_treated_as_plain_string():
    out = normalize_brief("{not valid json")
    assert json.loads(out) == {"coaching_note": "{not valid json"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_normalize_brief.py -v`
Expected: FAIL — `normalize_brief` not importable.

- [ ] **Step 3: Add `normalize_brief` to `checkin_service.py`**

At the top of [bot/services/checkin_service.py](../../bot/services/checkin_service.py) (alongside other helpers, below imports), add:

```python
def normalize_brief(raw) -> str:
    """D3: Canonical morning_brief on write is always a JSON-string.

    - None / empty → '{}'
    - dict → json.dumps(dict)
    - already-valid JSON string of an object → passed through
    - plain string or malformed JSON → wrapped as {coaching_note: <string>}
    """
    import json as _json

    if raw is None or raw == "":
        return _json.dumps({})
    if isinstance(raw, dict):
        return _json.dumps(raw)
    if isinstance(raw, str):
        try:
            parsed = _json.loads(raw)
            if isinstance(parsed, dict):
                return _json.dumps(parsed)
        except (_json.JSONDecodeError, ValueError):
            pass
        return _json.dumps({"coaching_note": raw})
    # Unknown types — coerce via str()
    return _json.dumps({"coaching_note": str(raw)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pitcher_program_app && python -m pytest tests/test_normalize_brief.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Apply at checkin_service write boundaries**

In [bot/services/checkin_service.py](../../bot/services/checkin_service.py), wrap both morning_brief writes. Search for the two `"morning_brief": plan_result.get("morning_brief") if plan_result else None,` lines (around 249 and 350). Replace each with:

```python
        "morning_brief": normalize_brief(plan_result.get("morning_brief")) if plan_result else normalize_brief(None),
```

Also update line 189 (`"morning_brief": None,`) to:

```python
        "morning_brief": normalize_brief(None),
```

- [ ] **Step 6: Collapse plan_generator's inline serialization into `normalize_brief`**

In [bot/services/plan_generator.py:353-360](../../bot/services/plan_generator.py:353), replace:

```python
            # Structured plan parsed successfully
            raw_brief = plan.get("morning_brief", "")
            # Serialize structured morning_brief dict to JSON string immediately
            if isinstance(raw_brief, dict):
                narrative = raw_brief.get("coaching_note", "")
                morning_brief = json.dumps(raw_brief)
            else:
                narrative = raw_brief
                morning_brief = raw_brief
```

with:

```python
            # Structured plan parsed successfully
            from bot.services.checkin_service import normalize_brief
            raw_brief = plan.get("morning_brief", "")
            narrative = raw_brief.get("coaching_note", "") if isinstance(raw_brief, dict) else str(raw_brief or "")
            morning_brief = normalize_brief(raw_brief)
```

Also normalize the Python-fallback brief. Find the line that constructs `python_plan` (around [plan_generator.py:293](../../bot/services/plan_generator.py:293)). Replace:

```python
        "morning_brief": _build_python_brief(rotation_day, flag_level, triage_result, checkin_inputs, day_key),
```

with:

```python
        "morning_brief": _build_python_brief(rotation_day, flag_level, triage_result, checkin_inputs, day_key),
```

(No change here yet — we do the normalize at write boundary only, so the plan dict in memory can carry either shape and the callers in `checkin_service` will stamp it.)

But the enrichment append on line 322 (`python_plan["morning_brief"] += f" Today's plan is informed by..."`) assumes string concatenation. Confirm by rereading. After the assignment at line 322, brief is a string — `normalize_brief` will wrap it as `coaching_note` at write time.

- [ ] **Step 7: Apply at `api/routes.py` write boundaries**

In [api/routes.py](../../api/routes.py), add at the top of the file (near other imports around line 20):

```python
from bot.services.checkin_service import normalize_brief
```

Replace line 627:

```python
                    "morning_brief": None,
```

with:

```python
                    "morning_brief": normalize_brief(None),
```

Replace line 644:

```python
                    return {"messages": messages, "morning_brief": None, "flag_level": result.get("flag_level", "green")}
```

with:

```python
                    return {"messages": messages, "morning_brief": normalize_brief(None), "flag_level": result.get("flag_level", "green")}
```

Replace lines 661 and 688 (the computed `brief` and its dict insertion):

```python
                brief = result.get("morning_brief") or result.get("plan_narrative", "")
```

(leave line 661 alone — this is a local variable used for the response payload, not a write to Supabase)

Replace line 688:

```python
                    "morning_brief": brief or None,
```

with:

```python
                    "morning_brief": normalize_brief(brief),
```

Replace line 699:

```python
                    "morning_brief": None,
```

with:

```python
                    "morning_brief": normalize_brief(None),
```

Replace line 1001:

```python
    today_entry["morning_brief"] = f"Applied plan: {plan.get('title', 'Custom plan')}"
```

with:

```python
    today_entry["morning_brief"] = normalize_brief(f"Applied plan: {plan.get('title', 'Custom plan')}")
```

Check line 1038-1039 (the `_parse_plan_json` fallback brief injection). Leave the in-memory shape alone — this dict feeds back to `checkin_service` which normalizes at write. Confirm no additional fix needed by reading the surrounding code.

- [ ] **Step 8: Run the full Python test suite to check for regressions**

Run: `cd pitcher_program_app && python -m pytest tests/ -v 2>&1 | tail -30`
Expected: all tests pass. If `test_plan_gen_unchanged.py` style snapshot tests flag brief-shape diffs, that's expected — update the snapshot.

- [ ] **Step 9: Commit**

```bash
git add pitcher_program_app/bot/services/checkin_service.py pitcher_program_app/bot/services/plan_generator.py pitcher_program_app/api/routes.py pitcher_program_app/tests/test_normalize_brief.py
git commit -m "refactor(brief): canonical JSON-string on write via normalize_brief (D3)"
```

---

## Task 4: Exercise library unification — 3 sub-commits, single deploy (D19)

### Step 4a: Snapshot cache + hydrate helper in `exercise_pool.py`

**Files:**
- Modify: `pitcher_program_app/bot/services/exercise_pool.py` (snapshot + hydrate)
- Modify: `pitcher_program_app/bot/main.py` (15-min refresh job)
- Test: `pitcher_program_app/tests/test_hydrate_exercises.py` (new)

- [ ] **Step 1: Write the failing test**

Create `pitcher_program_app/tests/test_hydrate_exercises.py`:

```python
"""D16, D17: hydrate_exercises stamps `name` onto exercise dicts using snapshot cache."""
from bot.services import exercise_pool


def test_hydrate_stamps_name(monkeypatch):
    fake_rows = [
        {"id": "ex_001", "slug": "goblet_squat", "name": "Goblet Squat"},
        {"id": "ex_002", "slug": "bench_press", "name": "Bench Press"},
    ]
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: fake_rows)
    exercise_pool._refresh_snapshot(force=True)

    items = [
        {"exercise_id": "ex_001", "prescribed": "3x8"},
        {"exercise_id": "ex_002", "prescribed": "3x5"},
    ]
    out = exercise_pool.hydrate_exercises(items)
    assert out[0]["name"] == "Goblet Squat"
    assert out[1]["name"] == "Bench Press"
    # Other fields untouched
    assert out[0]["prescribed"] == "3x8"


def test_hydrate_lazy_miss_falls_through_to_supabase(monkeypatch):
    snapshot_rows = [{"id": "ex_001", "slug": "a", "name": "A"}]
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: snapshot_rows)
    exercise_pool._refresh_snapshot(force=True)

    def fake_get_exercise(ex_id):
        if ex_id == "ex_new":
            return {"id": "ex_new", "slug": "new", "name": "Newly Added"}
        return None

    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", fake_get_exercise)
    items = [{"exercise_id": "ex_new", "prescribed": "2x10"}]
    out = exercise_pool.hydrate_exercises(items)
    assert out[0]["name"] == "Newly Added"
    # Subsequent call should hit snapshot (no new Supabase call)
    call_count = {"n": 0}
    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", lambda _: (call_count.update({"n": call_count["n"] + 1}), None)[1])
    exercise_pool.hydrate_exercises([{"exercise_id": "ex_new"}])
    assert call_count["n"] == 0  # served from snapshot after first-miss hydration


def test_hydrate_missing_exercise_leaves_name_absent(monkeypatch):
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: [])
    exercise_pool._refresh_snapshot(force=True)
    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", lambda _: None)

    items = [{"exercise_id": "truly_missing"}]
    out = exercise_pool.hydrate_exercises(items)
    assert "name" not in out[0] or out[0].get("name") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_hydrate_exercises.py -v`
Expected: FAIL — `hydrate_exercises` and `_refresh_snapshot` not defined.

- [ ] **Step 3: Replace the existing cache in `exercise_pool.py` with snapshot + hydrate helpers**

In [bot/services/exercise_pool.py](../../bot/services/exercise_pool.py), replace lines 15-24:

```python
# Cached exercise library (loaded once per process)
_EXERCISE_CACHE = None


def _load_exercises() -> list:
    global _EXERCISE_CACHE
    if _EXERCISE_CACHE is None:
        _EXERCISE_CACHE = get_exercises()
        logger.info("Exercise library loaded: %d exercises", len(_EXERCISE_CACHE))
    return _EXERCISE_CACHE
```

with:

```python
# Snapshot cache (D5): indexed by id AND slug for dual lookup (plan_generator.py:22 pattern).
# Refreshed periodically (D6) by APScheduler job in bot/main.py.
# Lazy-miss (D6): get_exercise() falls through to Supabase when exercise_id missing.
_EXERCISE_SNAPSHOT: dict[str, dict] = {}
_SNAPSHOT_ROWS: list = []


def _refresh_snapshot(force: bool = False) -> None:
    """Reload exercise snapshot from Supabase. Keep last-good on transient failure (D5)."""
    global _EXERCISE_SNAPSHOT, _SNAPSHOT_ROWS
    try:
        rows = get_exercises()
    except Exception as e:
        logger.warning("Snapshot refresh failed, keeping last-good: %s", e)
        return
    new_index = {}
    for ex in rows:
        ex_id = ex.get("id")
        if ex_id:
            new_index[ex_id] = ex
        slug = ex.get("slug")
        if slug:
            new_index[slug] = ex
    _EXERCISE_SNAPSHOT = new_index
    _SNAPSHOT_ROWS = rows
    logger.info("Exercise snapshot refreshed: %d exercises", len(rows))


def _load_exercises() -> list:
    """Return the snapshot row list, refreshing lazily on first call."""
    if not _SNAPSHOT_ROWS:
        _refresh_snapshot()
    return _SNAPSHOT_ROWS


def _get_from_snapshot(exercise_id: str) -> dict | None:
    """Look up by id or slug in the snapshot, with lazy-miss fallback to Supabase (D6)."""
    from bot.services.db import get_exercise  # local import keeps snapshot logic centralized
    if not exercise_id:
        return None
    hit = _EXERCISE_SNAPSHOT.get(exercise_id)
    if hit:
        return hit
    # Lazy miss — hit Supabase directly, then stash into snapshot so subsequent lookups are cached
    fresh = get_exercise(exercise_id)
    if fresh:
        _EXERCISE_SNAPSHOT[exercise_id] = fresh
        if fresh.get("slug"):
            _EXERCISE_SNAPSHOT[fresh["slug"]] = fresh
    return fresh


def hydrate_exercises(items: list[dict]) -> list[dict]:
    """Stamp `name` onto each item by looking up its exercise_id in the snapshot (D17).

    Leaves all other fields on each item untouched. Safe to call repeatedly.
    If an exercise_id is not found, the item is returned unchanged so callers
    can still emit their plan without crashing.
    """
    if not items:
        return items
    for item in items:
        ex_id = item.get("exercise_id")
        if not ex_id:
            continue
        if item.get("name"):
            continue  # already hydrated
        lib = _get_from_snapshot(ex_id)
        if lib and lib.get("name"):
            item["name"] = lib["name"]
    return items
```

Add `get_exercise` import at the top of the file (it's used in `_get_from_snapshot`):

```python
from bot.services.db import get_exercises, get_exercise
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd pitcher_program_app && python -m pytest tests/test_hydrate_exercises.py -v`
Expected: 3/3 PASS.

- [ ] **Step 5: Schedule 15-min snapshot refresh in `bot/main.py`**

In [bot/main.py `_schedule_jobs`](../../bot/main.py) (around line 890, before `post_init`), add:

```python
    async def _refresh_exercise_snapshot(context) -> None:
        try:
            from bot.services.exercise_pool import _refresh_snapshot
            _refresh_snapshot()
        except Exception as e:
            logger.error("Exercise snapshot refresh failed: %s", e)

    job_queue.run_repeating(
        _refresh_exercise_snapshot,
        interval=900,  # 15 min (D6)
        first=10,  # 10s after startup to warm cache
        name="exercise_snapshot_refresh",
    )
    logger.info("Scheduled 15-min exercise snapshot refresh")
```

- [ ] **Step 6: Commit 4a**

```bash
git add pitcher_program_app/bot/services/exercise_pool.py pitcher_program_app/bot/main.py pitcher_program_app/tests/test_hydrate_exercises.py
git commit -m "feat(exercise-pool): snapshot cache + hydrate helper (D5, D6, D16, D17)"
```

### Step 4b: Plan-gen emit, mutation/swap hydration, `/api/exercises` rewrite

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py:373-386` (hydrate at emit)
- Modify: `pitcher_program_app/api/routes.py:1205-1215` (rewrite `/api/exercises` to read Supabase, no cache)
- Modify: `pitcher_program_app/api/routes.py` `swap_exercise` (~1377) — hydrate replacement
- Modify: `pitcher_program_app/api/routes.py` `apply_mutations` (~1651) — hydrate new exercises

- [ ] **Step 1: Audit `/api/exercises` response shape**

Read [mini-app/src/api.js:211](../../mini-app/src/api.js:211) and [mini-app/src/pages/PlanDetail.jsx:24-31](../../mini-app/src/pages/PlanDetail.jsx:24) and [mini-app/src/pages/ExerciseLibrary.jsx](../../mini-app/src/pages/ExerciseLibrary.jsx). Confirm which fields the frontend consumes: `id`, `slug`, `name`, `modification_flags`, `rotation_day_usage`, `contraindications`, `youtube_url`, `muscles_primary`, `prescription`, `category`. Also confirm the JSON has a top-level `{ exercises: [...] }` wrapper; PlanDetail.jsx:25 iterates `exerciseData?.exercises`.

- [ ] **Step 2: Sample Supabase `exercises` schema to spot drift**

Run a quick sanity query (mcp or `supabase_mcp`):

```python
# In a scratch script or REPL:
from bot.services.db import get_exercises
rows = get_exercises()
print(sorted(rows[0].keys()))
```

Compare to the JSON's exercise object keys. If any column differs (e.g. Supabase stores `modification_flags` as JSONB vs JSON array), note it. Normalize in the route (see Step 4 below), not in Supabase.

- [ ] **Step 3: Write failing test for `/api/exercises`**

Add to `pitcher_program_app/tests/test_exercises_endpoint.py` (new):

```python
"""D2, D7: /api/exercises reads Supabase live (no @lru_cache)."""
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_exercises_endpoint_returns_supabase_rows(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    fresh_rows = [
        {"id": "ex_new", "slug": "brand_new", "name": "Brand New Exercise",
         "category": "upper_body_pull", "modification_flags": {}, "rotation_day_usage": [],
         "contraindications": [], "youtube_url": None, "muscles_primary": ["lats"],
         "prescription": {"strength": {"sets": 3, "reps": 8}}},
    ]
    monkeypatch.setattr("bot.services.db.get_exercises", lambda: fresh_rows)

    from api.main import app
    client = TestClient(app)
    res = client.get("/api/exercises")
    assert res.status_code == 200
    body = res.json()
    # Shape: { exercises: [...] } matching JSON contract
    assert "exercises" in body
    names = [e["name"] for e in body["exercises"]]
    assert "Brand New Exercise" in names


def test_exercises_endpoint_not_cached(monkeypatch):
    """Two calls with different underlying data should return different results (no lru_cache)."""
    monkeypatch.setenv("DISABLE_AUTH", "true")
    call_state = {"rows": [{"id": "a", "name": "A"}]}
    monkeypatch.setattr("bot.services.db.get_exercises", lambda: call_state["rows"])

    from api.main import app
    client = TestClient(app)
    res1 = client.get("/api/exercises")
    call_state["rows"] = [{"id": "b", "name": "B"}]
    res2 = client.get("/api/exercises")
    names1 = [e["name"] for e in res1.json()["exercises"]]
    names2 = [e["name"] for e in res2.json()["exercises"]]
    assert names1 == ["A"]
    assert names2 == ["B"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_exercises_endpoint.py -v`
Expected: FAIL — route reads JSON via `_load_exercise_library`, response shape may differ, `@lru_cache` means second test also fails.

- [ ] **Step 5: Rewrite `/api/exercises` to read Supabase live**

In [api/routes.py:1205-1215](../../api/routes.py:1205), replace:

```python
@lru_cache(maxsize=1)
def _load_exercise_library() -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/exercises")
async def get_exercises():
    """Return full exercise library."""
    return _load_exercise_library()
```

with:

```python
@router.get("/exercises")
async def get_exercises():
    """Return full exercise library from Supabase (D2, D7).

    Uncached — Supabase is canonical at runtime; JSON is seed-only.
    Response shape preserves the `{ exercises: [...] }` contract expected
    by mini-app/src/pages/PlanDetail.jsx:25 and ExerciseLibrary.jsx.
    """
    rows = _db.get_exercises()
    # Normalize field shape if Supabase has drifted from the JSON contract.
    # Known passthrough fields (from audit in Step 1): id, slug, name, category,
    # modification_flags, rotation_day_usage, contraindications, youtube_url,
    # muscles_primary, prescription. If Supabase returns any JSONB as string,
    # json.loads it here.
    normalized = []
    for row in rows:
        # Coerce any stringified JSONB back to native (belt-and-suspenders)
        for json_field in ("modification_flags", "rotation_day_usage",
                           "contraindications", "muscles_primary", "prescription"):
            v = row.get(json_field)
            if isinstance(v, str):
                try:
                    row[json_field] = json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
        normalized.append(row)
    return {"exercises": normalized}
```

If `_db` is not already imported, add at the top of the file:

```python
from bot.services import db as _db
```

(likely already present — verify first).

- [ ] **Step 6: Run test to verify it passes**

Run: `cd pitcher_program_app && python -m pytest tests/test_exercises_endpoint.py -v`
Expected: 2/2 PASS.

- [ ] **Step 7: Hydrate names in `plan_generator._finalize_plan` paths**

In [bot/services/plan_generator.py:368-386](../../bot/services/plan_generator.py:368), wrap both `exercise_blocks.append(...)` calls with `hydrate_exercises`. Add at top of the file:

```python
from bot.services.exercise_pool import hydrate_exercises
```

Replace the two list comprehensions on lines 373-376 and 382-385:

```python
            if arm_exercises and isinstance(arm_exercises, list):
                exercise_blocks.append({
                    "block_name": f"Arm Care ({arm_care_data.get('timing', 'pre-lift')})",
                    "exercises": hydrate_exercises([
                        {"exercise_id": ex.get("exercise_id", ""), "prescribed": ex.get("rx", "")}
                        for ex in arm_exercises if isinstance(ex, dict)
                    ]),
                })
            lift_exercises = lifting_data.get("exercises") if isinstance(lifting_data, dict) else None
            if lift_exercises and isinstance(lift_exercises, list):
                exercise_blocks.append({
                    "block_name": f"Lifting — {lifting_data.get('intent', '')}",
                    "exercises": hydrate_exercises([
                        {"exercise_id": ex.get("exercise_id", ""), "prescribed": ex.get("rx", "")}
                        for ex in lift_exercises if isinstance(ex, dict)
                    ]),
                })
```

Also hydrate the Python fallback path (line 317) — the block is already populated from `exercise_pool`'s dicts which already include `name` from the library. To be safe, wrap:

Find `python_plan["lifting"]["exercises"] = all_lifting_exercises` (around line 317). Change to:

```python
        python_plan["lifting"]["exercises"] = hydrate_exercises(all_lifting_exercises)
```

Also hydrate `fallback_exercise_blocks` where constructed (trace the variable — typically built in the same function). Safest: after constructing `python_plan`, run:

```python
    # Stamp names defensively on all lifting exercise lists in the plan
    for block in (python_plan.get("exercise_blocks") or []):
        hydrate_exercises(block.get("exercises") or [])
    if python_plan.get("lifting"):
        hydrate_exercises(python_plan["lifting"].get("exercises") or [])
```

Insert that right before `return python_plan` on the LLM-timeout path (around line 343) AND before `return python_plan` on the LLM-parse-failure path (wherever the function returns `python_plan` when structured parsing fails).

- [ ] **Step 8: Harden `swap_exercise` to use hydrate_exercises for consistency**

In [api/routes.py:1377+](../../api/routes.py:1377), the `_replace_in_exercise` helper already stamps `name` from `replacement_ex.get("name", to_id)` — good. But for consistency with mutations (D17) and to protect against `replacement_ex` lacking a name (shouldn't happen but defensive), after all three location-updates complete (around line 1470, before `upsert_daily_entry`), add:

```python
    # D17: hydrate any newly-mutated exercise lists to ensure `name` is stamped
    from bot.services.exercise_pool import hydrate_exercises
    if entry.get("lifting"):
        hydrate_exercises(entry["lifting"].get("exercises") or [])
    if plan.get("lifting"):
        hydrate_exercises(plan["lifting"].get("exercises") or [])
    for blk in (plan.get("exercise_blocks") or []):
        hydrate_exercises(blk.get("exercises") or [])
```

(Read lines 1450-1480 first to find the exact write-back point. Insert the hydration block immediately before the `upsert_daily_entry(...)` call.)

- [ ] **Step 9: Hydrate in `apply_mutations`**

In [api/routes.py](../../api/routes.py) find `apply_mutations` (~line 1651). The handler writes new exercises into `plan_generated.lifting.exercises` and `plan_generated.exercise_blocks`. Locate the place where each mutation is applied (look for `mutations = body.get("mutations", [])` and the loop that processes `action == "swap"` / `"add"`). Before the final `upsert_daily_entry(pitcher_id, updated_entry)`, add:

```python
    from bot.services.exercise_pool import hydrate_exercises
    plan = updated_entry.get("plan_generated") or {}
    if plan.get("lifting"):
        hydrate_exercises(plan["lifting"].get("exercises") or [])
    for blk in (plan.get("exercise_blocks") or []):
        hydrate_exercises(blk.get("exercises") or [])
    top_lift = updated_entry.get("lifting") or {}
    hydrate_exercises(top_lift.get("exercises") or [])
```

Read the function first to find the exact variable name (`updated_entry` vs `entry` vs `today_entry` — match what's there).

- [ ] **Step 10: Verify plan gen still passes existing tests**

Run: `cd pitcher_program_app && python -m pytest tests/ -v 2>&1 | tail -20`
Expected: all pass. `test_hydrate_exercises.py`, `test_exercises_endpoint.py`, `test_normalize_brief.py` included.

- [ ] **Step 11: Smoke-check `/checkin` locally**

Run a check-in against a dev pitcher (if local Supabase dev branch available) or inspect the test output for plan shape. The expected post-condition: `plan_generated.exercise_blocks[*].exercises[*]` each have a `name` field populated.

- [ ] **Step 12: Commit 4b**

```bash
git add pitcher_program_app/api/routes.py pitcher_program_app/bot/services/plan_generator.py pitcher_program_app/tests/test_exercises_endpoint.py
git commit -m "feat(plan-gen): hydrate exercise names at emit; unify /api/exercises on Supabase (D2, D7, D17)"
```

### Step 4c: JSON demote + seed script + pre-commit hook

**Files:**
- Create: `pitcher_program_app/scripts/seed_exercises_from_json.py`
- Create: `pitcher_program_app/scripts/hooks/pre-commit`
- Modify: `pitcher_program_app/data/knowledge/exercise_library.json` (header comment)
- Modify: `pitcher_program_app/CLAUDE.md` (update Known Issues + workflow)

- [ ] **Step 1: Write the seed script**

Create `pitcher_program_app/scripts/seed_exercises_from_json.py`:

```python
"""Seed Supabase `exercises` table from data/knowledge/exercise_library.json.

Upsert-only (D12): adds new rows, updates changed rows, never deletes. Idempotent.
Run automatically by pre-commit hook when exercise_library.json is staged.
On Supabase connection failure: logs a warning and exits 0 (D11 — warn + proceed).

Manual invocation:
    cd pitcher_program_app && python -m scripts.seed_exercises_from_json
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_exercises")

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "data" / "knowledge" / "exercise_library.json"


def main() -> int:
    if not JSON_PATH.exists():
        logger.warning("No exercise_library.json at %s — nothing to seed", JSON_PATH)
        return 0

    with JSON_PATH.open() as f:
        data = json.load(f)

    exercises = data.get("exercises", data) if isinstance(data, dict) else data
    if not isinstance(exercises, list):
        logger.warning("exercise_library.json: unexpected shape, aborting seed")
        return 0

    try:
        # Ensure repo root is on sys.path so bot.services imports resolve
        sys.path.insert(0, str(REPO_ROOT))
        from bot.services.db import get_client
    except Exception as e:
        logger.warning("Could not import db client (Supabase creds missing?): %s", e)
        return 0  # D11: warn + proceed

    client = get_client()
    if not client:
        logger.warning("Supabase client unavailable — skipping seed (D11)")
        return 0

    upserted = 0
    try:
        # Upsert in batches of 50 to avoid payload size surprises
        for i in range(0, len(exercises), 50):
            batch = exercises[i : i + 50]
            client.table("exercises").upsert(batch, on_conflict="id").execute()
            upserted += len(batch)
    except Exception as e:
        logger.warning("Seed failed mid-upsert after %d rows: %s", upserted, e)
        return 0  # warn + proceed

    logger.info("Seeded %d exercises (upsert, no deletes per D12)", upserted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Add header comment to `exercise_library.json`**

JSON doesn't support comments. Add a no-op key at the top instead. In [data/knowledge/exercise_library.json](../../data/knowledge/exercise_library.json), update the existing top keys. The file currently starts with:

```json
{
  "$schema": "exercise_library",
  "$description": "Complete exercise database for the pitcher training system. Each exercise tagged for contextual retrieval by the bot.",
```

Change to:

```json
{
  "$schema": "exercise_library",
  "$description": "Complete exercise database for the pitcher training system. Each exercise tagged for contextual retrieval by the bot.",
  "$seed_note": "SEED FILE. Supabase `exercises` is canonical at runtime. Edits here are picked up by the pre-commit hook running scripts/seed_exercises_from_json.py. See CLAUDE.md § Exercise library.",
```

Confirm the existing JSON reader in [bot/services/plan_generator.py:25-30](../../bot/services/plan_generator.py:25) tolerates the extra key — it does: the code skips non-exercise keys. Double-check by re-reading.

- [ ] **Step 3: Create the installable pre-commit hook**

Create `pitcher_program_app/scripts/hooks/pre-commit`:

```bash
#!/bin/sh
# Pre-commit hook: re-seed Supabase exercises when exercise_library.json is staged.
# D11: always exits 0 — warns + proceeds, never blocks a commit.
# Install with: ln -sf ../../pitcher_program_app/scripts/hooks/pre-commit .git/hooks/pre-commit

STAGED=$(git diff --cached --name-only)
if echo "$STAGED" | grep -q "pitcher_program_app/data/knowledge/exercise_library.json"; then
  echo ">>> exercise_library.json changed — running seed script (upsert-only)"
  if ! (cd "$(git rev-parse --show-toplevel)/pitcher_program_app" && python -m scripts.seed_exercises_from_json); then
    echo "!!! WARNING: seed script exited non-zero. Commit proceeding; rerun manually when Supabase is reachable:"
    echo "    cd pitcher_program_app && python -m scripts.seed_exercises_from_json"
  fi
fi
exit 0
```

Make it executable:

```bash
chmod +x pitcher_program_app/scripts/hooks/pre-commit
```

- [ ] **Step 4: Install the hook locally (one-time)**

Run from the repo root:

```bash
ln -sf ../../pitcher_program_app/scripts/hooks/pre-commit .git/hooks/pre-commit
ls -la .git/hooks/pre-commit
```

Expected: `pre-commit -> ../../pitcher_program_app/scripts/hooks/pre-commit`.

- [ ] **Step 5: Smoke-test the seed script**

```bash
cd pitcher_program_app && python -m scripts.seed_exercises_from_json
```

Expected output: `INFO: Seeded <N> exercises (upsert, no deletes per D12)` where N ≈ 159. If Supabase creds missing, expected: warning + exit 0.

- [ ] **Step 6: Update `CLAUDE.md`**

In [pitcher_program_app/CLAUDE.md](../../CLAUDE.md), in the "Known Issues & Tech Debt" section, remove this line:

```
- Exercise library has dual source: `exercise_library.json` (API endpoints) + Supabase `exercises` table (plan gen). **Both must be updated** when adding exercises.
```

Add a new section after "DB Patterns" titled "Exercise library workflow":

```markdown
### Exercise library workflow (2026-04-18)
- **Supabase `exercises` is canonical** at runtime. `/api/exercises`, plan gen, swap, and mutations all read live from Supabase via `exercise_pool` (15-min snapshot cache + lazy-miss).
- **JSON is seed-only.** `data/knowledge/exercise_library.json` is the source of truth in git for review/history. A pre-commit hook (`scripts/hooks/pre-commit`) runs `scripts/seed_exercises_from_json.py` on every commit that touches the JSON. Upsert-only — never deletes.
- **Hook install:** one-time `ln -sf ../../pitcher_program_app/scripts/hooks/pre-commit .git/hooks/pre-commit` from repo root.
- **Hook failure:** warns + proceeds (D11). Manual re-run: `cd pitcher_program_app && python -m scripts.seed_exercises_from_json`.
- **Removing an exercise:** delete from JSON for new plans, but historical `plan_generated` rows still reference it — orphans in Supabase are tolerated (D12).
```

Also update the "Last updated" line at the top of CLAUDE.md:

```markdown
> Last updated: 2026-04-18
> Sprint status: Phases 1-20.1 + Sprint 0.5 + Tier 1 Hardening complete. Coach sidebar shows team name, exercise names hydrated at write, canonical morning_brief shape, snapshot cache for exercises. Next: continue Tier 2 or pivot to next sprint.
```

- [ ] **Step 7: Run the full suite one more time**

```bash
cd pitcher_program_app && python -m pytest tests/ -v 2>&1 | tail -15
```

Expected: green. No regressions from JSON→Supabase unification.

- [ ] **Step 8: Commit 4c**

```bash
git add pitcher_program_app/scripts/seed_exercises_from_json.py pitcher_program_app/scripts/hooks/pre-commit pitcher_program_app/data/knowledge/exercise_library.json pitcher_program_app/CLAUDE.md
git commit -m "feat(exercise-library): demote JSON to seed-only; add seed script + pre-commit hook (D10, D11, D12)"
```

---

## Task 5: Coach-app exerciseMap safety net + `ui_fallback_log` telemetry

**Files:**
- Supabase migration (new table)
- Modify: `pitcher_program_app/api/routes.py` (POST `/api/telemetry/ui-fallback`)
- Modify: `pitcher_program_app/bot/services/db.py` (`insert_ui_fallback_log`, `has_recent_ui_fallback`, `prune_ui_fallback_log`)
- Modify: `pitcher_program_app/bot/main.py` (30-day prune in 9am digest job)
- Modify: `pitcher_program_app/coach-app/src/hooks/useCoachAuth.jsx` (fetch + expose `exerciseMap`)
- Modify: `pitcher_program_app/coach-app/src/components/PlayerToday.jsx` (+ any other exercise renderer) — use exerciseMap + log fallback
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`, `ExerciseRow.jsx`, `MutationPreview.jsx` — fire-and-forget log on fallback

### Step 5a: `ui_fallback_log` Supabase migration

- [ ] **Step 1: Apply the migration**

Use the Supabase MCP (`mcp__b746b04a-7b2a-4f10-bf3f-3ff7b82ee973__apply_migration`) to apply:

```sql
create table if not exists ui_fallback_log (
  id bigint generated by default as identity primary key,
  exercise_id text not null,
  surface text not null,
  component text,
  pitcher_id text,
  logged_at timestamptz not null default now()
);

create index if not exists ui_fallback_log_ex_time_idx
  on ui_fallback_log (exercise_id, logged_at desc);
```

Migration name: `20260418_ui_fallback_log`.

- [ ] **Step 2: Verify table exists**

Via MCP `execute_sql`: `select count(*) from ui_fallback_log;` — expected 0.

### Step 5b: Backend telemetry endpoint

- [ ] **Step 3: Write the failing test**

Add to `pitcher_program_app/tests/test_ui_fallback_telemetry.py` (new):

```python
"""D9, D13, D14: telemetry endpoint inserts + rate-limits admin DM per 24h."""
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def _setup(monkeypatch, has_recent):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    inserts = []
    monkeypatch.setattr(
        "bot.services.db.insert_ui_fallback_log",
        lambda **kw: inserts.append(kw),
    )
    monkeypatch.setattr(
        "bot.services.db.has_recent_ui_fallback",
        lambda exercise_id, hours: has_recent,
    )

    dms = []
    async def fake_send(text):
        dms.append(text)
    monkeypatch.setattr(
        "api.routes._send_admin_dm",
        fake_send,
    )
    return inserts, dms


def test_fallback_logs_row_and_dms_on_cold_exercise(monkeypatch):
    inserts, dms = _setup(monkeypatch, has_recent=False)
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_missing", "surface": "mini-app", "component": "ExerciseRow", "pitcher_id": "p1"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1
    assert inserts[0]["exercise_id"] == "ex_missing"
    assert len(dms) == 1  # cold exercise → DM fires


def test_fallback_logs_row_but_rate_limits_dm(monkeypatch):
    inserts, dms = _setup(monkeypatch, has_recent=True)
    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ui-fallback",
        json={"exercise_id": "ex_repeated", "surface": "coach-app"},
    )
    assert res.status_code == 200
    assert len(inserts) == 1  # still records every miss
    assert len(dms) == 0  # rate-limited — no DM
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_ui_fallback_telemetry.py -v`
Expected: FAIL — endpoint + db helpers don't exist.

- [ ] **Step 5: Add `db.py` helpers**

Append to [bot/services/db.py](../../bot/services/db.py):

```python
# --- ui_fallback_log (D9, D13, D14) ---

def insert_ui_fallback_log(exercise_id: str, surface: str, component: str = None, pitcher_id: str = None) -> None:
    """Record a UI fallback event (exercise name missing on render)."""
    row = {"exercise_id": exercise_id, "surface": surface}
    if component:
        row["component"] = component
    if pitcher_id:
        row["pitcher_id"] = pitcher_id
    get_client().table("ui_fallback_log").insert(row).execute()


def has_recent_ui_fallback(exercise_id: str, hours: int = 24) -> bool:
    """Return True if this exercise_id has been logged within the last N hours (D13)."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        get_client().table("ui_fallback_log")
        .select("id", count="exact")
        .eq("exercise_id", exercise_id)
        .gte("logged_at", cutoff)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def prune_ui_fallback_log(older_than_days: int = 30) -> int:
    """Delete rows older than N days (D14). Returns number deleted."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    resp = (
        get_client().table("ui_fallback_log")
        .delete()
        .lt("logged_at", cutoff)
        .execute()
    )
    return len(resp.data or [])
```

- [ ] **Step 6: Add the endpoint + admin DM helper to `api/routes.py`**

In [api/routes.py](../../api/routes.py), near the bottom (alongside other `@router.post` routes) add:

```python
async def _send_admin_dm(text: str) -> None:
    """Fire an admin Telegram DM. Best-effort — never raises."""
    try:
        from telegram import Bot
        from bot.config import ADMIN_TELEGRAM_CHAT_ID
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return
        bot = Bot(token=token)
        await bot.send_message(chat_id=ADMIN_TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logger.warning("admin DM failed: %s", e)


@router.post("/telemetry/ui-fallback")
async def ui_fallback_telemetry(request: Request):
    """Record a UI exercise-name fallback event (D9, D13).

    Always inserts a row for post-mortem analysis. Admin DM fires only if
    this exercise_id has not been seen in the last 24h (rate limit per D13).
    """
    body = await request.json()
    exercise_id = body.get("exercise_id")
    surface = body.get("surface")
    component = body.get("component")
    pitcher_id = body.get("pitcher_id")

    if not exercise_id or not surface:
        raise HTTPException(status_code=400, detail="exercise_id and surface required")

    recent = _db.has_recent_ui_fallback(exercise_id, hours=24)
    _db.insert_ui_fallback_log(
        exercise_id=exercise_id,
        surface=surface,
        component=component,
        pitcher_id=pitcher_id,
    )

    if not recent:
        msg = (
            f"⚠️ UI fallback: '{exercise_id}' missing name on {surface}"
            + (f" ({component})" if component else "")
            + (f" pitcher={pitcher_id}" if pitcher_id else "")
        )
        await _send_admin_dm(msg)

    return {"ok": True, "dmed": not recent}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd pitcher_program_app && python -m pytest tests/test_ui_fallback_telemetry.py -v`
Expected: 2/2 PASS.

### Step 5c: 30-day prune in 9am digest job

- [ ] **Step 8: Wire prune into existing `_send_health_digest`**

In [bot/main.py:723](../../bot/main.py:723) `_send_health_digest`, after the `digest = compute_daily_digest()` line and before `await context.bot.send_message(...)`, add:

```python
        # D14: prune ui_fallback_log older than 30 days
        try:
            pruned = _db.prune_ui_fallback_log(older_than_days=30)
            if pruned:
                logger.info("Pruned %d old ui_fallback_log rows", pruned)
        except Exception as e:
            logger.warning("ui_fallback_log prune failed: %s", e)
```

Add `from bot.services import db as _db` at the top of the file if not already imported (verify first; it's likely already imported via `from bot.services.db import ...` patterns).

### Step 5d: Coach-app fetches exerciseMap on login (mirror mini-app pattern per D22)

- [ ] **Step 9: Extend `useCoachAuth` to fetch exercise library on login**

In [coach-app/src/hooks/useCoachAuth.jsx](../../coach-app/src/hooks/useCoachAuth.jsx), modify the AuthProvider to also fetch `/api/exercises` once the coach is authenticated. Full replacement:

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
  const [exerciseMap, setExerciseMap] = useState({})
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
      else { setCoach(null); setExerciseMap({}); setLoading(false) }
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
      // D22: fetch exercise library once per login for name resolution
      fetchExerciseMap(accessToken).catch(err => console.warn('exerciseMap fetch failed:', err))
    } catch (err) {
      console.error('Auth exchange error:', err)
      setCoach(null)
    } finally {
      setLoading(false)
    }
  }

  async function fetchExerciseMap(accessToken) {
    const res = await fetch(`${API_BASE}/api/exercises`, {
      headers: { 'Authorization': `Bearer ${accessToken}` },
    })
    if (!res.ok) return
    const data = await res.json()
    const map = {}
    for (const ex of (data.exercises || [])) {
      if (ex.id) map[ex.id] = ex
      if (ex.slug) map[ex.slug] = ex
    }
    setExerciseMap(map)
  }

  async function login(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function logout() {
    await supabase.auth.signOut()
    setCoach(null)
    setExerciseMap({})
    setSession(null)
  }

  function getAccessToken() {
    return session?.access_token || ''
  }

  return (
    <AuthContext.Provider value={{ coach, exerciseMap, session, loading, login, logout, getAccessToken }}>
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

### Step 5e: Frontend fallback telemetry firing

- [ ] **Step 10: Add `logUiFallback` helper to mini-app/api.js**

At the bottom of [mini-app/src/api.js](../../mini-app/src/api.js):

```javascript
/**
 * Fire-and-forget telemetry when an exercise name falls back to ID/Unknown (D9).
 * Never throws; best-effort.
 */
export function logUiFallback({ exerciseId, surface, component, pitcherId }) {
  if (!exerciseId) return;
  try {
    fetch(`${API_BASE}/api/telemetry/ui-fallback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: exerciseId,
        surface,
        component,
        pitcher_id: pitcherId,
      }),
    }).catch(() => {});
  } catch (_e) {}
}
```

Note: confirm `API_BASE` is exported or defined at the top of the file. If not, reuse the existing base-URL constant (read the file).

- [ ] **Step 11: Wire mini-app fallback points**

In [mini-app/src/components/ExerciseRow.jsx](../../mini-app/src/components/ExerciseRow.jsx), import:

```javascript
import { useEffect } from 'react';
import { logUiFallback } from '../api';
```

Above the return statement in the component (around line 30), add:

```javascript
  useEffect(() => {
    if (!exercise?.name && exercise?.exercise_id) {
      logUiFallback({
        exerciseId: exercise.exercise_id,
        surface: 'mini-app',
        component: 'ExerciseRow',
      });
    }
  }, [exercise?.name, exercise?.exercise_id]);
```

In [mini-app/src/components/MutationPreview.jsx](../../mini-app/src/components/MutationPreview.jsx), near line 60 where `{m.name || m.to_exercise_id}` is rendered, add a one-line firing side-effect. Since MutationPreview is a functional component, add at the top of the component body:

```javascript
  useEffect(() => {
    (mutations || []).forEach(m => {
      if (m.action === 'swap' && !m.name && m.to_exercise_id) {
        logUiFallback({
          exerciseId: m.to_exercise_id,
          surface: 'mini-app',
          component: 'MutationPreview',
        });
      }
    });
  }, [mutations]);
```

Add imports `import { useEffect } from 'react'; import { logUiFallback } from '../api';` if missing.

In [mini-app/src/components/DailyCard.jsx](../../mini-app/src/components/DailyCard.jsx), the name fallback happens inside `SupersetList` / `ExerciseItem` rendering — `ExerciseRow` already covers the telemetry for the lifting block. No additional DailyCard wiring needed for this class of bug; ExerciseRow is the choke point.

- [ ] **Step 12: Wire coach-app fallback points**

In [coach-app/src/components/PlayerToday.jsx](../../coach-app/src/components/PlayerToday.jsx) or whichever coach-app component renders exercise names (audit first — likely PlayerSlideOver or PlayerToday). For each place that renders `ex.name || ex.exercise_id`, replace with exerciseMap resolution + fire-and-forget log.

Create a small helper hook `coach-app/src/hooks/useExerciseName.js`:

```javascript
import { useEffect } from 'react'
import { useCoachAuth } from './useCoachAuth'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

/**
 * Resolve an exercise's display name via the coach-app exerciseMap, falling back
 * to any name stamped on the item itself, then to the ID. Fires telemetry on fallback (D9).
 */
export function useExerciseName({ item, component }) {
  const { exerciseMap } = useCoachAuth()
  const ex = item || {}
  const mapHit = exerciseMap[ex.exercise_id] || null
  const name = ex.name || (mapHit && mapHit.name) || null

  useEffect(() => {
    if (!name && ex.exercise_id) {
      try {
        fetch(`${API_BASE}/api/telemetry/ui-fallback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            exercise_id: ex.exercise_id,
            surface: 'coach-app',
            component: component || 'unknown',
          }),
        }).catch(() => {})
      } catch (_e) {}
    }
  }, [name, ex.exercise_id, component])

  return name || ex.exercise_id || 'Unknown exercise'
}
```

Audit coach-app exercise renderers (grep for `.name` or `exercise_id` in JSX) and replace inline fallbacks with `useExerciseName({ item: ex, component: 'PlayerToday' })`.

- [ ] **Step 13: Build both frontends to verify compile**

```bash
cd pitcher_program_app/mini-app && npm run build 2>&1 | tail -15
cd ../coach-app && npm run build 2>&1 | tail -15
```

Expected: both succeed.

- [ ] **Step 14: Commit Task 5**

```bash
git add pitcher_program_app/bot/services/db.py pitcher_program_app/api/routes.py pitcher_program_app/bot/main.py pitcher_program_app/coach-app/src/hooks/useCoachAuth.jsx pitcher_program_app/coach-app/src/hooks/useExerciseName.js pitcher_program_app/mini-app/src/api.js pitcher_program_app/mini-app/src/components/ExerciseRow.jsx pitcher_program_app/mini-app/src/components/MutationPreview.jsx pitcher_program_app/coach-app/src/components/PlayerToday.jsx pitcher_program_app/tests/test_ui_fallback_telemetry.py
git commit -m "feat(telemetry): ui_fallback_log + admin DM (24h rate-limited) + coach-app exerciseMap (D9, D13, D14, D22)"
```

---

## Task 6: Verification & deploy

**Goal:** Confirm end-to-end correctness per D23 before calling this done. No new code — verification only.

- [ ] **Step 1: Pre-deploy — verify all tests pass**

```bash
cd pitcher_program_app && python -m pytest tests/ -v
cd pitcher_program_app && node --test tests/test_parse_brief.mjs
```

Expected: all green.

- [ ] **Step 2: Pre-deploy — lint/build both frontends**

```bash
cd pitcher_program_app/mini-app && npm run build
cd pitcher_program_app/coach-app && npm run build
```

Expected: both succeed, no new warnings about `@shared` or missing imports.

- [ ] **Step 3: Deploy sequence**

Per D20 + D19, pushing `main` auto-deploys everything. To stage correctly with a single push:
- Task 3a (frontend readers) is already tolerant of old backend shape → safe
- Task 3b (backend normalize_brief) produces canonical shape → readers handle both
- Task 4 (exercise hydration) touches plan gen → snapshot cache boots at startup
- Task 5 (telemetry) — `ui_fallback_log` table migration applied manually via MCP before push

```bash
git push origin main
```

Monitor Railway logs and both Vercel deploys to green.

- [ ] **Step 4: Post-deploy smoke — coach dashboard**

1. Open `https://baseball-self.vercel.app`
2. Log out and back in (existing sessions won't see `team_name` until re-login — D18)
3. Sidebar header should show real team name (e.g. "UChicago Baseball"), not "Dashboard"

- [ ] **Step 5: Post-deploy smoke — exercise names in new check-in**

1. From Telegram, run `/checkin` on a test pitcher
2. Open mini-app, view today's plan
3. All lifting, arm care, and mobility exercises should show human-readable names (e.g. "Goblet Squat"), not IDs (`ex_012`)
4. If any exercise renders as an ID, the fallback telemetry should fire — check Railway logs for the POST to `/api/telemetry/ui-fallback` and Telegram admin DM

- [ ] **Step 6: Post-deploy smoke — exercise library endpoint**

1. Open mini-app ExerciseLibrary page (or hit `GET /api/exercises` directly)
2. Confirm the response shape is `{ exercises: [...] }` with all 159 rows
3. Confirm new exercises added via JSON + pre-commit appear without a Railway redeploy (add a test exercise, commit, verify via MCP `list_migrations` or a direct `select * from exercises where id = 'ex_test'`)

- [ ] **Step 7: Post-deploy smoke — morning brief rendering**

1. Coach tab in mini-app: if today's brief exists, verify it renders without crashing (structured brief card OR plain coach-note)
2. Coach-app player detail view: same check for PlayerToday / PlayerWeek

- [ ] **Step 8: Post-deploy smoke — `ui_fallback_log` quietness**

Via Supabase MCP:

```sql
select count(*) as events, count(distinct exercise_id) as distinct_exercises
from ui_fallback_log
where logged_at > now() - interval '1 hour';
```

Expected: 0 or near-zero. A flood (>20 rows in an hour) means Task 4 hydration is broken — investigate and roll back Task 4c specifically (revert the seed changes; previous code path still reads the JSON).

- [ ] **Step 9: Post-deploy smoke — snapshot refresh job**

Check Railway logs for the line `Exercise snapshot refreshed: <N> exercises` — should appear at startup (~10s after boot) and every 15 min thereafter.

- [ ] **Step 10: Commit the verification log (optional)**

If verification uncovers follow-ups, capture them in `docs/superpowers/logs/2026-04-18-tier1-hardening-verify.md` and commit.

```bash
git add pitcher_program_app/docs/superpowers/logs/2026-04-18-tier1-hardening-verify.md
git commit -m "docs: log Tier 1 hardening post-deploy verification"
```

---

## Post-Plan Notes

- **Do not skip the smoke in Step 2 before Step 3a deploys.** The spec specifically calls out deploy-order risk (D20) — readers must be tolerant of both old and new brief shapes before the backend normalizes.
- **If the pre-commit hook fails on first run**, that's often a missing `SUPABASE_SERVICE_KEY` locally. Run the seed script manually with creds set, or just commit — it proceeds (D11).
- **Historical plans stay ID-only** (D21). The `ui_fallback_log` + rate-limited DM is the right signal; no backfill unless data shows a real problem.
- **"FastAPI 500 masquerading as CORS" watch:** if the coach app suddenly shows "Origin not allowed" after this ships, check Railway logs for a traceback first (per CLAUDE.md known-issues).
