# Research-Aware Coaching Layer — Design Spec

> Date: 2026-04-10
> Status: Approved (pending final spec review)
> Sprint: 1 of 2 (elevation + fortification)
> Sprint 2 scope: Profile page "what we know about your body," weekly narrative research integration, embeddings (C layer), longitudinal chunk ledger

## Problem

The knowledge base (14 research MDs, exercise library JSON) is partially wired into the system but has three problem classes:

1. **Plumbing rot.** Three sets of files (`extended_knowledge.md`, top-level `FINAL_research_base.md`, entire repo-root `research/` dir) never reach the LLM because `_load_research_index()` only scans `data/knowledge/research/*.md`. Two parallel filter systems (`exercise_pool.py` on contraindications/modification_flags vs `knowledge_retrieval.py` on injury-area keywords) have no shared vocabulary and can drift silently.

2. **Retrieval is blunt.** Hardcoded keyword substring matching in `knowledge_retrieval.py:165-192`. New injury areas or modification strings added to triage get silently dropped. No coverage guarantees.

3. **Integration is narrow.** Research only enters through three doors: plan generation, Q&A handler, post-outing recovery. It does NOT reach: coach chat (unless the user happens to phrase a keyword-matching question), morning notification, daily plan page (no visibility into "why"), or triage itself.

## What We're Building

A research-aware coaching layer that wires the knowledge base into four surfaces through a single unified resolver. The system fires proactively whenever a pitcher is in a non-green state, has active modifications within the current rotation cycle, or mentions injury in free text.

### Surfaces (Sprint 1)

| Surface | Integration | LLM? |
|---------|------------|------|
| Coach chat | Research-aware reply + always-present mutation card | Yes |
| Plan generation | Upgrade existing retrieval to use unified resolver | Yes (existing) |
| Morning notification | Two-pass: Python template (instant) + LLM enrichment (15s deadline) | Yes, with fallback |
| Daily plan "why" | Info icon on lifting block → bottom sheet listing loaded docs + summaries | No (reads stored metadata) |

### Out of Scope (Sprint 2)

- Profile page "what we know about your body" section
- Weekly narrative research integration
- Embedding-based retrieval (C layer, on top of deterministic A layer)
- Longitudinal "chunks the pitcher has seen" ledger
- Section-level citation / passage quoting

## Guiding Principles

1. **Deterministic safety path.** Injury logic stays keyword-and-rule-driven. No probabilistic retrieval for safety-critical routing.
2. **One door.** Every surface pulls research through a single resolver function. No parallel keyword maps.
3. **Frontmatter is the contract.** Research docs declare applicability in their own YAML frontmatter. No hidden hardcoded routing tables.
4. **Function over polish.** Doc-level attribution ("per the FPM protocol"). No section quoting. Token budget is fine for now.
5. **Fortification ships with elevation.** Dead file cleanup, shared vocabulary, coverage test, and observability table land in the same sprint.

---

## Data Model

### Research Doc Frontmatter Schema

Every research MD in `data/knowledge/research/` must have this YAML frontmatter:

```yaml
---
id: ucl_flexor_pronator_protection        # unique, snake_case
title: UCL Flexor-Pronator Protection Protocol
applies_to:                                 # injury_areas this doc serves
  - medial_elbow
  - forearm
triggers:                                   # modification tags / pitcher states
  - fpm
  - flexor
  - pronator
  - ucl_history
phase: any                                  # in_season | off_season | any
priority: critical                          # critical | standard | reference
contexts:                                   # which surfaces may load this doc
  - plan_gen
  - coach_chat
  - morning
  - daily_plan_why
summary: >                                  # one-sentence description for citations + UI
  Protective protocol for pitchers with UCL or flexor-pronator history;
  defines yellow-day pressing restrictions and FPM addon prescription.
---
```

**Field semantics:**

- `applies_to` — matches against `pitcher_profile.injury_history[*].area`. Direct, deterministic.
- `triggers` — matches against `triage_result.modifications` tag keys AND free-text in coach messages. Replaces the brittle hardcoded substring map at `knowledge_retrieval.py:185-192`.
- `priority` — `critical` always loads when conditions match (safety docs); `standard` loads when budget allows; `reference` only loads on explicit Q&A. Safety docs never get crowded out.
- `contexts` — a doc can opt into specific surfaces. Triage framework loads everywhere; supplementation only loads in coach_chat.

### Supabase: `research_load_log` Table (NEW)

```sql
create table research_load_log (
  id bigserial primary key,
  ts timestamptz default now(),
  pitcher_id text references pitchers(pitcher_id),
  context text not null,           -- 'plan_gen' | 'coach_chat' | 'morning' | 'daily_plan_why'
  trigger_reason text,             -- 'flag_level=yellow' | 'recent_mod:fpm' | 'keyword:elbow'
  loaded_doc_ids text[],
  total_chars int,
  degraded boolean default false   -- true if LLM fallback kicked in
);
create index on research_load_log (pitcher_id, ts desc);
create index on research_load_log (context, ts desc);
```

Non-blocking insert (swallow errors). Read via Supabase MCP for auditing.

### Supabase: `daily_entries` Column Addition

Add `research_sources text[]` column to `daily_entries`. Populated by plan generator with the list of doc IDs that informed the plan. Read by the daily plan "why" affordance.

---

## Resolver — Single Door

### New File: `bot/services/research_resolver.py`

Replaces the routing logic currently split between `knowledge_retrieval.py:136-208` (plan path) and `knowledge_retrieval.py:99-133` (Q&A path). The old functions become thin wrappers during transition.

```python
@dataclass
class DocRef:
    id: str
    title: str
    summary: str
    priority: str

@dataclass
class ResearchPayload:
    combined_text: str          # concatenated doc content, ready for prompt injection
    loaded_docs: list[DocRef]   # for citation, observability, UI
    trigger_reason: str         # human-readable reason

def resolve_research(
    pitcher_profile: dict,
    context: Literal["plan_gen", "coach_chat", "morning", "daily_plan_why"],
    triage_result: dict | None = None,
    user_message: str | None = None,
    max_chars: int = 12000,
) -> ResearchPayload:
    """Single source of truth for research retrieval across all surfaces."""
```

### Doc Selection Algorithm (deterministic order)

1. Load all docs where `contexts` includes current `context` AND `priority == "critical"` AND `applies_to` intersects pitcher's injury_areas. **Always loaded.**
2. Add docs whose `triggers` intersect `triage_result.modifications` tag keys.
3. Add docs whose `triggers` substring-match `user_message` (coach chat path only).
4. Add `priority: "standard"` docs that match injury_areas, until `max_chars` is hit.
5. Always-load docs (tightness_triage_framework, recovery_physiology) get folded in via `priority: critical` + `applies_to: [any]` — no special-casing in code.

### Backward Compatibility

`retrieve_research_for_plan(profile)` and `retrieve_knowledge(question)` become 5-line wrappers:

```python
def retrieve_research_for_plan(pitcher_profile, max_chars=12000):
    payload = resolve_research(pitcher_profile, "plan_gen", max_chars=max_chars)
    return payload.combined_text

def retrieve_knowledge(question, pitcher_profile=None):
    payload = resolve_research(pitcher_profile or {}, "coach_chat", user_message=question)
    return payload.combined_text
```

Callsites in `plan_generator.py` and `outing_service.py` remain unchanged during transition (they only use `.combined_text`). `qa.py` transitions fully to the new flow (structured output + mutation card) — it already loads `profile` at line 63, so passing it to the resolver is a one-line change. New surfaces call `resolve_research()` directly.

---

## Trigger Logic

### Trigger Function

```python
def should_fire_research(
    pitcher_profile: dict,
    triage_result: dict | None = None,
    user_message: str | None = None,
) -> tuple[bool, str]:
    """Returns (should_fire, reason_string)."""
```

### Three OR'd Conditions

| # | Condition | Source | Reason string |
|---|-----------|--------|---------------|
| 1 | Non-green flag | `triage_result.flag_level in ("yellow", "red", "modified_green")` | `"flag_level={x}"` |
| 2 | Recent modification window | Any modification applied in last `rotation_length` days (from `daily_entries`) | `"recent_mod:{tag}"` |
| 3 | Injury keyword in free text | Coach chat only. Keyword set generated from union of all `triggers` arrays in loaded frontmatter (data-driven, not hardcoded) | `"keyword:{matched}"` |

Condition 2 catches the case the current system misses: a pitcher who was yellow Tuesday, green Friday, but still in a rehab arc. The coach still loads research context.

When no condition fires, the resolver still runs but with no triage/message filter — returns only `priority: critical` + `applies_to: [any]` docs (triage framework, recovery physiology). This is the "always helpful, never empty" baseline.

---

## Coach Chat Integration

### Flow (replaces current Q&A path for triggered turns)

```
1. Load pitcher profile + most recent daily_entry (last 24h)
2. should_fire, reason = should_fire_research(profile, triage, user_message)
3. payload = resolve_research(profile, "coach_chat", triage, user_message)
4. Build prompt from coach_chat_prompt.md (NEW prompt template)
   Inject: pitcher_state_block, payload.combined_text, recent_history, user_message
5. Single LLM call → structured JSON output
6. Render reply as chat bubble + mutation_card as MutationPreview component
7. Insert research_load_log row
```

### LLM Structured Output

The prompt instructs the LLM to always return:

```json
{
  "reply": "<conversational empathetic text>",
  "mutation_card": {
    "type": "swap | rest | hold | addition",
    "title": "<short title>",
    "rationale": "<one sentence, references loaded doc by name>",
    "actions": [
      {"action": "swap", "from_exercise_id": "ex_042", "to_exercise_id": "ex_087", "rx": "3x10"},
      {"action": "remove", "exercise_id": "ex_023"}
    ],
    "applies_to_date": "today | tomorrow"
  },
  "lookahead": "<optional sentence about next outing or next 2-3 days>"
}
```

**Mutation card always renders.** When the LLM determines no specific action:

```json
{
  "type": "rest",
  "title": "Rest today",
  "rationale": "Per the flexor-pronator protocol, the right move on a yellow elbow day is full rest.",
  "actions": [],
  "applies_to_date": "today"
}
```

Card renders with [Got it] and [Adjust] buttons. "Adjust" lets the pitcher push back in the next chat turn.

**`lookahead` field** — every triggered turn ends with the LLM thinking 2-3 days ahead: "You've got a start in 4 days — let's keep this quiet." / "Tomorrow's a planned light day anyway, this lines up well." This is what makes the coach feel like it holds the long arc.

### MutationPreview Reuse

The `MutationPreview` component and `POST /apply-mutations` endpoint from Phase 15 already handle swap/add/remove/modify rendering and application. The only change: coach chat now routes every triggered turn through mutation generation, instead of only when the LLM happens to emit a `plan_mutation` JSON block.

### Failure Modes

| Failure | Behavior |
|---------|----------|
| LLM timeout | Canned empathetic fallback text + triage-derived mutation card from Python | 
| Malformed JSON | Regex-extract `reply` if possible, drop card. Log `degraded: true` |
| Zero research docs loaded | Coach works normally, just no research grounding. Card still renders from triage alone |

---

## Plan Generation Integration

### Change to `bot/services/plan_generator.py`

Line 210 changes from:

```python
relevant_research = retrieve_research_for_plan(profile)
```

To:

```python
payload = resolve_research(profile, "plan_gen", triage_result)
relevant_research = payload.combined_text
```

Line 216 stays the same (`.replace("{relevant_research}", ...)`).

**New:** after plan is built, persist `research_sources` on the daily_entry:

```python
# In the plan_result dict, alongside existing fields:
"research_sources": [doc.id for doc in payload.loaded_docs],
```

This is what powers the daily plan "why" affordance.

### Python Fallback Morning Brief Enhancement

`_build_python_brief()` gets one new clause: when `payload.loaded_docs` is non-empty, append the most relevant doc title to the brief text. Even if the LLM review pass times out, the Python fallback brief is now research-aware.

---

## Morning Notification Integration

### Two-Pass Morning Composer

**Pass 1 — Python (instant, always exists):**
Build a deterministic templated morning message from:
- `should_fire_research()` output
- Yesterday's `daily_entry`
- WHOOP cache
- `payload.loaded_docs[0].title` + `payload.trigger_reason`

Template: `"Morning {name} — {trigger_reason_prose}. {doc_title_reference}. {arm_feel_buttons}"`

**Pass 2 — LLM (15s hard deadline):**
New prompt template `morning_message.md`. Inputs:
- Research `payload.combined_text`
- Yesterday's daily_entry
- WHOOP biometrics
- Lookahead (next outing date, rotation position)
- Pass 1 draft as seed

Instruction: "Rewrite this draft as natural prose, 2-4 sentences, conversational, lead with the most important thing. Do not reference docs not in the RESEARCH_LOADED list."

**Ship logic:**
- LLM returns within 15s and parses cleanly → ship LLM prose
- LLM fails or times out → ship Pass 1 templated message
- Pitcher always gets a message at notification_time. Never a delay, never missing.

**Button handling:** `[Tap to see why]` inline button is attached by Python after the LLM prose — the LLM never sees or generates the button. Opens mini-app daily plan page.

**Green-day behavior:** when `should_fire_research()` returns false, morning notification stays exactly as it is today. Zero regression.

---

## Daily Plan "Why" Affordance

### Frontend: `mini-app/src/components/DailyCard.jsx`

When `daily_entry.plan_generated.research_sources` is non-empty, render a small info icon next to the lifting block header. Tapping opens a bottom sheet:

```
Why today looks different
─────────────────────────
Your plan is informed by:

  UCL Flexor-Pronator Protection Protocol
  Yellow-day pressing restriction triggered by elbow tightness

  Tightness Triage Framework
  Always loaded for plan generation

[Open coach to ask more]
```

Each bullet: `{doc.title}` from frontmatter + `{doc.summary}` from frontmatter.

Button routes to Coach tab — closes the loop, sets up the next research-aware turn.

### Data Source

`GET /api/pitcher/{id}/log/{date}` already returns `daily_entry`. The new `research_sources` column is included in the response payload. No new endpoint needed.

Frontend reads `entry.research_sources`, maps IDs to doc metadata via a new lightweight endpoint `GET /api/research/docs?ids=doc1,doc2` that returns `[{id, title, summary}]` from frontmatter cache.

---

## Fortification Pass

### 5a — Dead File Audit & Relocation

Three sets of files currently outside the indexed `data/knowledge/research/` directory:

| File(s) | Location | Proposed fate |
|---------|----------|--------------|
| `extended_knowledge.md` | `data/knowledge/` | Assess content — likely **adopt** (move to `research/`, add frontmatter) or **archive** |
| `FINAL_research_base.md` | `data/knowledge/` (top-level) | Likely duplicate of `research/FINAL_research_base.md` — **archive** or **delete** |
| `00_INDEX.md` through `11_Gaps_to_Operationalize.md` (12 files) | Repo root `research/` | Earlier strategic series. Assess individually — **adopt** (move + frontmatter) or **archive** |

Implementation plan will propose a specific fate for each file after reading contents.

### 5b — Shared Vocabulary

New file: `bot/services/vocabulary.py`

Single source of truth for injury areas and modification tags:

```python
INJURY_AREAS = {
    "medial_elbow": {
        "keywords": ["ucl", "flexor", "pronator", "fpm", "medial"],
        "research_triggers": ["fpm", "ucl_history"],
    },
    "forearm": {
        "keywords": ["forearm", "flexor", "pronator"],
        "research_triggers": ["fpm"],
    },
    "shoulder": {
        "keywords": ["shoulder", "scapular", "external rotation"],
        "research_triggers": ["arm_care"],
    },
    "lower_back": {
        "keywords": ["back", "lumbar", "axial"],
        "research_triggers": ["workload"],
    },
    "oblique": {
        "keywords": ["oblique", "rotational"],
        "research_triggers": ["workload"],
    },
}

MODIFICATION_TAGS = {
    "fpm_volume":           {"description": "Elevated FPM volume", "research_triggers": ["fpm"]},
    "reduce_pressing":      {"description": "Drop pressing movements", "research_triggers": ["fpm", "shoulder_protection"]},
    "rpe_cap_67":           {"description": "Cap RPE at 6-7", "research_triggers": ["recovery"]},
    "no_high_intent_throw": {"description": "No high-intent throwing", "research_triggers": ["recovery"]},
}
```

`triage.py` emits tag keys from `MODIFICATION_TAGS`. `exercise_pool.py` and `research_resolver.py` both import from `vocabulary.py`.

### Coverage Test

`tests/test_research_coverage.py`:

```python
def test_every_modification_tag_has_research():
    """Every MODIFICATION_TAG must have at least one research doc whose triggers match."""

def test_every_injury_area_has_critical_research():
    """Every INJURY_AREA must have at least one priority:critical doc."""
```

Runs in CI. New injury area without matching research doc = CI failure. Silent-drop class of bug becomes structurally impossible.

### 5c — Observability

`research_load_log` table (defined in Data Model section above). Resolver inserts one row per call. Non-blocking.

Audit queries (run via Supabase MCP):
- "Yellow-day check-ins with zero research loaded" → keyword map gaps
- "Docs never loaded" → dead research candidates for archive
- "Pitchers with `degraded=true` mornings this week" → LLM reliability

---

## Failure Modes Summary

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Resolver finds zero matching docs | Surfaces work, no research context. Card still renders from triage. | Coverage test (5b) catches in CI. `research_load_log` surfaces post-deploy. |
| Coach LLM timeout | Reply text lost | Canned empathetic fallback + Python-derived mutation card |
| Coach LLM malformed JSON | Can't parse reply/card | Regex-extract reply, drop card. Log `degraded: true` |
| Morning LLM timeout | Pass 2 lost | Ship Pass 1 templated message. Pitcher never notices. |
| Frontmatter missing/malformed | Doc invisible to index | Startup validation warning. Coverage test catches by tag. |
| New injury area without research doc | Resolver fires, loads zero docs for that area | `test_every_injury_area_has_critical_research` fails CI |
| `research_load_log` insert fails | Non-blocking. Resolver returns payload regardless. | `try/except`, swallow error. Observability degrades, nothing user-facing breaks. |

**Every failure path degrades to the system working exactly as it does today.** The worst case is the pitcher doesn't get the elevation, not that they get a broken experience.

---

## Success Criteria

1. **Coverage:** `research_load_log` shows zero-doc loads < 5% of triggered turns within 2 weeks of deploy.
2. **Coach coherence:** when a pitcher says "my elbow is tight" on a yellow day, the coach reply references the same research docs that informed the morning notification and the daily plan. Verifiable by pulling logs and comparing `loaded_doc_ids` across surfaces for same pitcher + date.
3. **Mutation card adoption:** > 30% of rendered mutation cards are tapped (Apply or Got it) within the first week. If < 10%, prompt tuning needed.
4. **No regression:** green-day pitchers with no injury history see zero change in their coach, plan, or morning experience. Verify via `research_load_log` — these have `should_fire = false` and no research loaded.
5. **Silent-drop elimination:** coverage test passes in CI. No modification tag exists without a matching research trigger.

---

## New Files Summary

| File | Purpose |
|------|---------|
| `bot/services/research_resolver.py` | Unified resolver — single door for all surfaces |
| `bot/services/vocabulary.py` | Shared injury areas + modification tags |
| `bot/prompts/coach_chat_prompt.md` | New prompt template for research-aware coach turns |
| `bot/prompts/morning_message.md` | New prompt template for LLM-enriched morning notification |
| `tests/test_research_coverage.py` | CI coverage test for vocabulary ↔ research mapping |

## Modified Files Summary

| File | Change |
|------|--------|
| `bot/services/knowledge_retrieval.py` | Old functions become thin wrappers around `resolve_research()` |
| `bot/services/plan_generator.py` | L210: use `resolve_research()`, persist `research_sources` on daily_entry |
| `bot/handlers/qa.py` | Use `should_fire_research()` + `resolve_research()`, parse structured JSON, render mutation card |
| `bot/main.py` | Morning notification composer: two-pass with 15s deadline |
| `bot/services/triage.py` | Emit `MODIFICATION_TAGS` keys instead of freeform strings |
| `bot/services/exercise_pool.py` | Import injury area mapping from `vocabulary.py` |
| `api/routes.py` | Include `research_sources` in daily_entry response; add `GET /api/research/docs` |
| `mini-app/src/components/DailyCard.jsx` | Info icon + bottom sheet for "why today looks different" |
| `data/knowledge/research/*.md` (all 14) | Add YAML frontmatter |
