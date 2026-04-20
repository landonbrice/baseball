# Check-in Hotfix Plan (Regressions #1 + #3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two high-severity check-in flow bugs surfaced during Tier 1 Hardening smoke tests.

**Tech Stack:** Python 3.11, FastAPI, React 18 + Vite, Supabase (Postgres).

**Not in scope — Regression #2 (Telegram ConversationHandler stall):**
Railway logs on 2026-04-19 show:
```
telegram.error.Conflict: Conflict: terminated by other getUpdates request;
make sure that only one bot instance is running
```
This is an **operational/infrastructure issue**, not a code bug. Two processes are concurrently polling `getUpdates` with the same bot token. Root cause is one of:
1. Multiple active Railway deployments of the bot service (check Railway dashboard for duplicate replicas)
2. Local dev bot (`python -m bot.main`) still running on a developer laptop with the same `TELEGRAM_BOT_TOKEN`
3. A second Railway project configured with the same token
4. A Telegram webhook is set + polling is attempting (mutually exclusive — call `/deleteWebhook` to force polling-only)

Until only one `getUpdates` consumer exists, no Telegram message — including arm-feel responses — will reliably reach any handler. The earlier hypothesis that the stall was caused by an exception inside the ConversationHandler was wrong; the handler is never reached. **Resolving #2 requires ops action, not a code change.** Not in this plan.

---

## Design Rationale (Decisions)

**D1. Use `plan_narrative` (already-plain-text) as chat content source, not `morning_brief` (now JSON-string envelope).** `plan_generator.py:366` extracts `narrative = raw_brief.get("coaching_note", "") if isinstance(raw_brief, dict) else str(raw_brief or "")` and `process_checkin` surfaces it at `checkin_service.py:374` as `result["plan_narrative"]`. This field has always been the plain-string coaching note; inverting preference in `routes.py:660` is a one-line fix with zero shape migration.

**D2. Defensive parseBrief in the chat message render path** so the same bug can't recur from any future backend callsite. Frontend belt-and-suspenders.

**D3. Thread `energy` from `/chat` request body to `process_checkin`.** The parameter has existed on `process_checkin` since day one; the call site never wired it. Fix is additive and cannot break callers that don't pass energy (default stays `3`).

**D4. Migrate `Coach.jsx:218-232` quickClassify to 1-10 scale + expand keyword coverage.** Sprint 0.5 (2026-04-13) migrated the backend scale but missed this frontend classifier. Values should map: old `5 → 10`, `4 → 8`, `3 → 5` (neutral), `2 → 3`, `1 → 1` — preserving the rough semantic ordering while aligning thresholds.

**D4a. Include present-participle + auxiliary-verb variants of positive phrases in the "10" bucket.** Confirmed via 2026-04-19 Railway logs: user typed `"arm is feeling good"` → current classifier matched only `"good"` (line 5, legacy bucket 4) → backend received `arm_feel=4` → triage threshold `RED ≤4` → RED flag despite clearly-positive input. The keyword list must include both `"feels good"` AND `"feeling good"` (and analogous forms for other positive phrases). Without this, even after the 1-10 migration, "feeling good" falls through to the `"good"`-alone bucket (value 8) instead of the top bucket (value 10). This is the actual in-production failure mode.

**D5. Preserve existing `retryPlan` echo behavior.** Its `|| 3` fallback is a symptom, not a cause. Once D3 ships and `overall_energy` stops being deterministically 3, the echo accurately reflects prior state. Remove the hardcoded 3 default here too (fallback to null).

**D6. No migration for existing `daily_entries` rows.** Historical rows with `overall_energy: 3` from the D3 gap stay as-is — we don't know if 3 was genuine user input or the default. Triage logic already tolerates missing values (defaults to median). Fixing the inbound flow is sufficient.

**D7. Regression test each fix before shipping.** Each task below writes the failing test first (TDD), then the fix, then confirms green.

---

## File Structure

**Modified files:**
- `pitcher_program_app/api/routes.py` — `/chat` checkin handler: fix chat content source (D1), pass `energy` param (D3). Secondary: saved-plan subtitle builder (D2 applied defensively).
- `pitcher_program_app/mini-app/src/pages/Coach.jsx` — quickClassify 1-10 migration (D4), retryPlan cleanup (D5), defensive parseBrief on message content (D2).
- `pitcher_program_app/mini-app/src/api.js` — no change (sendChat already threads an arbitrary payload).

**New test files:**
- `pitcher_program_app/tests/test_chat_content_shape.py` — regression: chat `messages[].content` is never a JSON-stringified envelope.
- `pitcher_program_app/tests/test_checkin_energy_threading.py` — regression: energy posted to `/chat` reaches Supabase pre_training.
- `pitcher_program_app/tests/test_quick_classify.mjs` — regression: 1-10 output for representative inputs.

**Modified files:**
- `pitcher_program_app/CLAUDE.md` — add to Known Issues / tech-debt the retroactive `overall_energy: 3` data quality note. Update Sprint status.

---

## Task 1: Fix chat JSON leak at `routes.py:660` (D1)

**Severity:** HIGH — user-visible JSON garbage in Coach chat.

**Files:**
- Modify: `pitcher_program_app/api/routes.py:660-665`
- Test: `pitcher_program_app/tests/test_chat_content_shape.py` (new)

### Step 1: Write failing test

Create `pitcher_program_app/tests/test_chat_content_shape.py`:

```python
"""Regression: /chat checkin response never contains a raw JSON-string envelope
as message content (D1). Surfaced 2026-04-18 when normalize_brief started
emitting JSON-string briefs and the chat response assembler leaked them
into user-visible chat bubbles.
"""
import json
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_chat_checkin_content_is_plain_text(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    # Fake process_checkin returns the canonical post-Task-3b shape:
    # - morning_brief is a JSON-string envelope
    # - plan_narrative is the plain coaching note
    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        return {
            "morning_brief": json.dumps({
                "arm_verdict": {"value": "8/10", "status": "green"},
                "coaching_note": "Solid arm, standard rotation today.",
            }),
            "plan_narrative": "Solid arm, standard rotation today.",
            "flag_level": "green",
            "plan_generated": {"lifting": {"exercises": []}},
        }

    monkeypatch.setattr(
        "api.routes.process_checkin",
        fake_process_checkin,
    )

    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={
            "message": {
                "arm_feel": 8,
                "sleep_hours": 7.5,
                "arm_report": "feels good",
            },
            "type": "checkin",
        },
    )
    assert res.status_code == 200
    body = res.json()
    # Every text message content must be plain text — never a JSON envelope
    for msg in body.get("messages", []):
        if msg.get("type") == "text":
            content = msg.get("content", "")
            assert not (content.startswith("{") and '"coaching_note"' in content), (
                f"JSON envelope leaked into chat content: {content[:200]}"
            )
```

Run: `cd pitcher_program_app && python3 -m pytest tests/test_chat_content_shape.py -v`.
Expected: FAIL — current handler leaks the JSON envelope.

### Step 2: Apply the fix

In `pitcher_program_app/api/routes.py:660-665`, replace:

```python
                brief = result.get("morning_brief") or result.get("plan_narrative", "")
                if isinstance(brief, dict):
                    brief = brief.get("coaching_note", "") or str(brief)
                brief = str(brief) if brief else ""
                if brief:
                    messages.append({"type": "text", "content": brief})
```

with:

```python
                # D1: prefer plan_narrative (plain text) over morning_brief
                # (now a JSON-string envelope post-Task-3b). Fall through to
                # parseBrief-equivalent extraction if narrative is absent.
                narrative = result.get("plan_narrative") or ""
                if not narrative:
                    raw_brief = result.get("morning_brief")
                    if isinstance(raw_brief, dict):
                        narrative = raw_brief.get("coaching_note", "") or ""
                    elif isinstance(raw_brief, str) and raw_brief:
                        try:
                            parsed = json.loads(raw_brief)
                            if isinstance(parsed, dict):
                                narrative = parsed.get("coaching_note", "") or ""
                        except (json.JSONDecodeError, ValueError):
                            narrative = raw_brief  # legacy plain-string brief
                narrative = str(narrative) if narrative else ""
                if narrative:
                    messages.append({"type": "text", "content": narrative})
```

If `json` is not already imported at the top of `api/routes.py`, add it (or reuse existing import — grep first).

### Step 3: Run test — expect PASS

```bash
cd pitcher_program_app && python3 -m pytest tests/test_chat_content_shape.py -v
```

### Step 4: Apply defensive guard in `Coach.jsx` message render (D2)

In `pitcher_program_app/mini-app/src/pages/Coach.jsx`, find the `processResponse` function (around line 168). Locate the loop that iterates `res.messages` and pushes each into `newMsgs`.

Add a defensive parseBrief before pushing any `type: "text"` message. At the top of the file, confirm `parseBrief` is already imported (Task 3a added it). For each text message, if `content` looks like a JSON envelope, unwrap it:

```javascript
// D2: defensive — if backend ever leaks a JSON-string envelope as content,
// extract coaching_note before render. Belt-and-suspenders; no-op for plain text.
function sanitizeChatContent(raw) {
  if (typeof raw !== 'string' || !raw.trim().startsWith('{')) return raw;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed.coaching_note || '';
    }
  } catch (_) {}
  return raw;
}
```

Then in `processResponse` where text messages get spread (`Coach.jsx:168`-ish: `newMsgs.push({ role: 'bot', ...m })`), replace with:

```javascript
            newMsgs.push({
              role: 'bot',
              ...m,
              content: m.content ? sanitizeChatContent(m.content) : m.content,
            });
```

Also apply the same sanitization in `retryPlan` at Coach.jsx:471-473 where `res.messages` is iterated.

### Step 5: Commit

```bash
git add pitcher_program_app/api/routes.py pitcher_program_app/mini-app/src/pages/Coach.jsx pitcher_program_app/tests/test_chat_content_shape.py
git commit -m "fix(chat): prefer plan_narrative over morning_brief for chat content; defensive sanitizer on frontend (D1, D2)"
```

---

## Task 2: Secondary JSON leak — saved-plan subtitle (D2)

**Severity:** LOW — affects plan list subtitles only, not the hot path.

**Files:**
- Modify: `pitcher_program_app/api/routes.py:~2174-2186`

### Step 1: Inspect current code

Read `api/routes.py` around 2174-2186. Expected pattern:

```python
brief = plan.get("morning_brief") or ""
if isinstance(brief, dict):
    brief = brief.get("coaching_note", "") or str(brief)
```

Missing: the JSON-string unpack case.

### Step 2: Apply the fix

Replace with:

```python
# D2: unwrap JSON-string envelopes from normalize_brief
raw_brief = plan.get("morning_brief") or ""
if isinstance(raw_brief, dict):
    brief = raw_brief.get("coaching_note", "") or ""
elif isinstance(raw_brief, str) and raw_brief.strip().startswith("{"):
    try:
        parsed = json.loads(raw_brief)
        brief = parsed.get("coaching_note", "") if isinstance(parsed, dict) else raw_brief
    except (json.JSONDecodeError, ValueError):
        brief = raw_brief
else:
    brief = raw_brief
```

### Step 3: Commit (bundle with Task 1 if not yet committed)

```bash
git add pitcher_program_app/api/routes.py
git commit -m "fix(saved-plans): unwrap morning_brief JSON envelope in subtitle builder (D2)"
```

---

## Task 3: Thread `energy` from `/chat` checkin to Supabase (D3)

**Severity:** HIGH data-quality — every mini-app check-in silently stores `overall_energy: 3` since this code was written.

**Files:**
- Modify: `pitcher_program_app/api/routes.py:615-619` (the `process_checkin` call site in the `/chat` checkin branch)
- Test: `pitcher_program_app/tests/test_checkin_energy_threading.py` (new)

### Step 1: Write failing test

Create `pitcher_program_app/tests/test_checkin_energy_threading.py`:

```python
"""Regression: energy field posted to /chat reaches process_checkin (D3).

Pre-fix, the /chat checkin handler did not pass `energy` to process_checkin,
so every mini-app check-in stored overall_energy=3 (the default param value).
"""
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient


def test_energy_from_chat_reaches_process_checkin(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")

    calls = []

    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        calls.append({"pitcher_id": pitcher_id, "arm_feel": arm_feel, "sleep_hours": sleep_hours, **kwargs})
        return {
            "morning_brief": "",
            "plan_narrative": "ok",
            "flag_level": "green",
            "plan_generated": {"lifting": {"exercises": []}},
        }

    monkeypatch.setattr("api.routes.process_checkin", fake_process_checkin)

    from api.main import app
    client = TestClient(app)

    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={
            "message": {"arm_feel": 8, "sleep_hours": 7.0, "energy": 9},
            "type": "checkin",
        },
    )
    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0].get("energy") == 9, (
        f"energy was not threaded to process_checkin; got kwargs={calls[0]}"
    )


def test_energy_defaults_when_absent(monkeypatch):
    """Backwards compat: clients that don't send energy still work."""
    monkeypatch.setenv("DISABLE_AUTH", "true")

    calls = []

    async def fake_process_checkin(pitcher_id, arm_feel, sleep_hours, **kwargs):
        calls.append(kwargs)
        return {"morning_brief": "", "plan_narrative": "", "flag_level": "green", "plan_generated": {}}

    monkeypatch.setattr("api.routes.process_checkin", fake_process_checkin)

    from api.main import app
    client = TestClient(app)
    res = client.post(
        "/api/pitcher/test_pitcher_001/chat",
        json={"message": {"arm_feel": 7, "sleep_hours": 7}, "type": "checkin"},
    )
    assert res.status_code == 200
    # When client doesn't send energy, we shouldn't FORCE 3 — pass None / omit
    # and let process_checkin default-handle it
    assert "energy" not in calls[0] or calls[0]["energy"] in (None, 3)
```

Run: expect FAIL (energy isn't threaded).

### Step 2: Apply the fix

Read `api/routes.py:590-620` first to find the exact call site. Expected shape near line 615:

```python
result = await process_checkin(
    pitcher_id, int(arm_feel), float(sleep_hours),
    arm_report=arm_report, lift_preference=lift_preference,
    throw_intent=throw_intent, next_pitch_days=next_pitch_days,
)
```

Add `energy` extraction + threading. Near where `arm_feel`/`sleep_hours` are pulled from the request body:

```python
energy_raw = data.get("energy")
energy = int(energy_raw) if energy_raw is not None else None
```

Then in the call:

```python
result = await process_checkin(
    pitcher_id, int(arm_feel), float(sleep_hours),
    arm_report=arm_report, lift_preference=lift_preference,
    throw_intent=throw_intent, next_pitch_days=next_pitch_days,
    **({"energy": energy} if energy is not None else {}),
)
```

This conditional kwarg threading preserves the default (`energy: int = 3` at `checkin_service.py:114`) when the client doesn't send energy, but passes the real value when present.

### Step 3: Update `Coach.jsx:finalizeCheckin` to actually send energy

Read `Coach.jsx` around `finalizeCheckin` (line ~240). Currently the payload does NOT include an `energy` field. The check-in conversation flow asks the user about energy (find the state that captures it — grep for `energy` in Coach.jsx). Whatever state holds it, include it in the sendChat body:

```javascript
const payload = {
  arm_report: flowData.arm_report,
  arm_feel: flowData.arm_feel,
  sleep_hours: flowData.sleep_hours,
  energy: flowData.energy,  // D3: was silently dropped
  lift_preference: flowData.lift_preference,
  throw_intent: flowData.throw_intent,
  next_pitch_days: flowData.next_pitch_days,
};
```

If `flowData.energy` isn't currently captured (the UI never prompts for it), ADD an energy-capture state to the check-in conversation. Likely pattern: after sleep_hours capture, before lift_preference, add a step that asks "Energy today, 1-10?" with a numeric button row or slider. Follow the existing arm_feel capture pattern.

### Step 4: Run tests — expect PASS

```bash
cd pitcher_program_app && python3 -m pytest tests/test_checkin_energy_threading.py -v
```

### Step 5: Commit

```bash
git add pitcher_program_app/api/routes.py pitcher_program_app/mini-app/src/pages/Coach.jsx pitcher_program_app/tests/test_checkin_energy_threading.py
git commit -m "fix(checkin): thread energy from /chat to process_checkin; capture energy in mini-app flow (D3)"
```

---

## Task 4: Migrate `quickClassify` to 1-10 scale (D4)

**Severity:** MEDIUM — frontend scale drift from Sprint 0.5 migration.

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Coach.jsx:218-232`
- Test: `pitcher_program_app/tests/test_quick_classify.mjs` (new)

### Step 1: Write failing test

Create `pitcher_program_app/tests/test_quick_classify.mjs`:

```javascript
// Run with: node --test tests/test_quick_classify.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { quickClassify } from '../mini-app/src/lib/quickClassify.js';

test('positive phrases map to high end of 1-10 scale', () => {
  assert.ok(quickClassify('arm feels great today').feel >= 9);
  assert.ok(quickClassify('perfect, no issues').feel >= 9);
  assert.ok(quickClassify('arm feels good, no soreness').feel >= 9);
});

test('neutral phrases map to middle of 1-10 scale', () => {
  const r = quickClassify('arm feels fine');
  assert.ok(r.feel >= 6 && r.feel <= 8, `got ${r.feel}`);
});

test('mild-negative phrases (tight/sore) map to 4-5', () => {
  const r = quickClassify('arm feels a bit tight');
  assert.ok(r.feel >= 4 && r.feel <= 6, `got ${r.feel}`);
});

test('severe-negative phrases map to 1-3', () => {
  assert.ok(quickClassify('sharp pain when throwing').feel <= 3);
  assert.ok(quickClassify('shooting pain in elbow').feel <= 3);
});

test('unmatched text returns null feel (delegates to LLM)', () => {
  assert.equal(quickClassify('idk').feel, null);
});

test('"feels good" wins over substring "sore" in "no soreness"', () => {
  // Regression guard: order of keyword checks must not fire "sore" match
  // when the user is explicitly saying "no soreness"
  const r = quickClassify('arm feels good, no soreness');
  assert.ok(r.feel >= 9, `feels-good should win; got ${r.feel}`);
});

test('present-participle "feeling good" maps to top bucket (D4a regression)', () => {
  // Observed 2026-04-19 Railway logs: "arm is feeling good" → arm_feel=4 → RED flag
  // because legacy classifier only matched "good" (bucket 4, pre-migration).
  // After fix, both "feels good" and "feeling good" must land in the 10 bucket.
  assert.ok(quickClassify('arm is feeling good').feel >= 9);
  assert.ok(quickClassify("I'm feeling great today").feel >= 9);
  assert.ok(quickClassify('feeling amazing, no issues').feel >= 9);
});
```

### Step 2: Extract `quickClassify` to its own module

The classifier is currently inline in Coach.jsx. For testability, extract to `pitcher_program_app/mini-app/src/lib/quickClassify.js`:

```javascript
/**
 * Classify free-text arm-feel reports to a numeric 1-10 scale.
 * Returns { feel: number | null, ack: string }.
 *
 * Keyword ordering matters — checked top-to-bottom; first match wins.
 * "no soreness" regression: positive phrases are checked FIRST so
 * "feels good" wins before the "sore" substring check can fire.
 *
 * Migrated from 1-5 to 1-10 on 2026-04-19 (D4). Mapping:
 *   old 5 (great/perfect) → new 10
 *   old 4 (good/fine)     → new 8
 *   old 3 (tight/sore)    → new 5
 *   old 2 (terrible)      → new 2
 *   old 1 (sharp/numb)    → new 1
 */
export function quickClassify(text) {
  const lower = (text || '').toLowerCase();
  // Top bucket — explicitly positive. Include both "feels X" and "feeling X"
  // forms (D4a): observed production regression 2026-04-19 where
  // "arm is feeling good" missed the top bucket and landed in "good"-alone.
  const POSITIVE = [
    'great', 'perfect', 'amazing', 'no issues',
    'feels good', 'feeling good',
    'feels great', 'feeling great',
    'feels amazing', 'feeling amazing',
    'feels perfect', 'feeling perfect',
  ];
  if (POSITIVE.some(w => lower.includes(w))) {
    return { feel: 10, ack: 'Good to hear.' };
  }
  if (['sharp', 'shooting', 'numb', 'tingling'].some(w => lower.includes(w))) {
    return { feel: 1, ack: 'That sounds concerning — I\'ll factor that in.' };
  }
  if (['terrible', 'really bad', 'awful'].some(w => lower.includes(w))) {
    return { feel: 2, ack: 'Got it.' };
  }
  if (['tight', 'sore', 'stiff', 'tender'].some(w => lower.includes(w))) {
    return { feel: 5, ack: 'Got it — I\'ll factor that into your plan.' };
  }
  // Lukewarm bucket — "good" / "fine" without the explicit positive verb pairing.
  if (['good', 'fine', 'solid', 'normal', 'decent'].some(w => lower.includes(w))) {
    return { feel: 8, ack: 'Arm\'s feeling solid.' };
  }
  return { feel: null, ack: 'Got it.' };
}
```

### Step 3: Update `Coach.jsx` to use the imported function

Replace the inline `quickClassify` (lines 218-232) with:

```javascript
import { quickClassify } from '../lib/quickClassify.js';
```

Remove the inline definition.

### Step 4: Run test — expect PASS

```bash
cd pitcher_program_app && node --test tests/test_quick_classify.mjs
```

### Step 5: Commit

```bash
git add pitcher_program_app/mini-app/src/lib/quickClassify.js pitcher_program_app/mini-app/src/pages/Coach.jsx pitcher_program_app/tests/test_quick_classify.mjs
git commit -m "fix(checkin): migrate quickClassify to 1-10 scale; extract to testable module (D4)"
```

---

## Task 5: Clean up `retryPlan` default-3 echo (D5)

**Severity:** LOW — masked by D3 once energy flows through.

**Files:**
- Modify: `pitcher_program_app/mini-app/src/pages/Coach.jsx:461-479`

### Step 1: Apply the fix

Read the current `retryPlan` function. Replace the hardcoded `|| 3` fallback with `?? null` so retries pass through whatever was captured (or null if genuinely missing), letting the backend's `process_checkin` default handle it:

```javascript
const res = await sendChat(pitcherId, {
  arm_feel: todayEntry.pre_training?.arm_feel ?? null,
  sleep_hours: todayEntry.pre_training?.sleep_hours ?? null,
  energy: todayEntry.pre_training?.overall_energy ?? null,
}, 'checkin', initData);
```

### Step 2: Commit

```bash
git add pitcher_program_app/mini-app/src/pages/Coach.jsx
git commit -m "fix(retryPlan): pass through null instead of defaulting energy to 3 (D5)"
```

No test — behavior is now just "echo whatever's there," which is simple.

---

## Task 6: Full suite + frontend build verification

- [ ] `cd pitcher_program_app && python3 -m pytest tests/ -v 2>&1 | tail -20`
- [ ] `cd pitcher_program_app && node --test tests/test_parse_brief.mjs tests/test_quick_classify.mjs 2>&1 | tail -10`
- [ ] `cd pitcher_program_app/mini-app && npm run build 2>&1 | tail -10`
- [ ] `cd pitcher_program_app/coach-app && npm run build 2>&1 | tail -10`

Expected: all green. No new warnings.

---

## Task 7: Update CLAUDE.md

Add to "Known Issues & Tech Debt" section:

```markdown
- **Historical `overall_energy: 3` in daily_entries** (fixed 2026-04-19 for new rows): prior to the checkin-hotfix merge, the `/api/chat` checkin handler never threaded `energy` from the request body to `process_checkin`, so every mini-app check-in stored the parameter default `3`. Historical rows are not backfilled — triage tolerates missing/default values. New rows carry real energy values. If doing retrospective analytics on energy, filter `created_at >= <hotfix-deploy-timestamp>`.
```

Also update the Sprint status line at the top:

```markdown
> Last updated: 2026-04-19
> Sprint status: Phases 1-20.1 + Sprint 0.5 + Tier 1 Hardening + Check-in Hotfix complete. Next: address Regression #2 (Telegram ConversationHandler stall — blocked on Railway log capture).
```

Commit with all the other doc updates or standalone:

```bash
git add pitcher_program_app/CLAUDE.md
git commit -m "docs: note overall_energy data-quality gap; update sprint status (Tier 1 hotfix)"
```

---

## Deploy Sequence

Per D20 from the Tier 1 plan (reader-before-writer), but this change set doesn't have reader/writer ordering concerns — each task is internally consistent.

Recommended push strategy:
1. Push to `claude/checkin-hotfix-2026-04-19` branch
2. Merge-to-main via the same local merge pattern used for Tier 1 (`git merge --no-ff`)
3. Railway + Vercel auto-deploy
4. Smoke test immediately on both surfaces:
   - Mini-app: new check-in with "arm feels good, no soreness" → expect `arm_feel: 10`, `overall_energy: <whatever user entered>`, coaching note as plain text in chat (not JSON)
   - Coach tab: re-check-in → no JSON blob bubbles

---

## Watch-outs

- **The `energy` capture step in Coach.jsx check-in flow may not exist today.** If the UI never prompts for energy, Task 3 Step 3 needs to ADD that step. Follow the arm-feel state pattern. If this is a bigger UX change than a one-step addition, break it out as a separate task and ship the backend threading first (clients that send energy start working immediately).
- **`retryPlan` is called from degraded-plan UI.** Make sure the `?? null` doesn't regress existing behavior where `todayEntry.pre_training` is itself missing — guard with `todayEntry.pre_training?.`.
- **The sanitizeChatContent helper has overlap with parseBrief.js** — consider importing parseBrief and using `parseBrief(content).coaching_note || content` instead of duplicating the JSON-parse logic. Decided against for this plan to keep scope tight.
- **No backfill for `overall_energy: 3`** — D6 explicitly accepts this.
- **Do NOT fix Regression #2 (Telegram stall) in this plan.** Separate work, needs log capture first.

---

## Post-Plan Notes

- This plan is a reaction to Tier 1 Hardening smoke tests surfacing live bugs. Tier 1 is not being rolled back; these are additive fixes.
- Total estimated diff: ~60 lines production code + ~90 lines test + doc. Half a day of implementation with review cycles.
- Regression #2 (Telegram stall) is resolved via infrastructure — not this plan. Before opening another debug session on #2, confirm via Railway dashboard + `curl /getWebhookInfo` that only one `getUpdates` consumer exists. Once the `telegram.error.Conflict` loop clears, `/checkin` should resume functioning with no code change. If it still stalls AFTER the Conflict clears, reopen the handler-exception hypothesis.
- Empirical evidence guiding this plan:
  - 2026-04-19 Supabase `daily_entries` row: `arm_feel=3, overall_energy=3` from a mini-app check-in with input "arm feels good, no soreness" → confirmed D3 energy-default + possible LLM fallback path.
  - 2026-04-19 screenshot + Railway logs: input "arm is feeling good" produced `arm_feel=4/10` → confirmed D4a keyword-coverage gap (present-participle "feeling good" not in positive bucket).
  - 2026-04-18 Coach tab chat bubble: raw `normalize_brief` JSON envelope rendered verbatim → confirmed D1 chat content source bug.
