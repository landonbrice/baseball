# System Guardian - Ops Intelligence + Vision Drift Spec

> **Status:** Draft for dialectic/integration  
> **Created:** 2026-05-02  
> **Audience:** Lando, Claude Code, Codex, future implementation agent  
> **Purpose:** Turn runtime logs, platform signals, and product-vision constraints into a structured system-health and debugging loop.

---

## 1. Executive Summary

The current product already has first-party silent degradation monitoring: plan source tracking, 9am admin digest, WHOOP pull checks, Q&A counters, emergency LLM failure thresholds, `/admin/health`, and frontend fallback telemetry.

The missing layer is broader: a **System Guardian** that watches the deployed system from the outside and inside, turns noisy logs into actionable incidents, prepares debug packets for Claude Code/Codex, and flags drift from the product architecture described in `PROJECT_VISION.md`, `PRODUCT_VISION_DRAFT.md`, `PRODUCT_BUILD_PLAN.md`, and `CLAUDE.md`.

This should not begin as a free-roaming autonomous agent. V1 should be a scheduled worker that collects, normalizes, clusters, and summarizes evidence. The AI layer should operate on structured incident packets, not raw unbounded logs.

---

## 2. Existing Overlap

### Already Built

Relevant current system pieces:

- `bot/services/health_monitor.py`
  - `compute_plan_health(date)`
  - `compute_plan_health_rolling(days=7)`
  - `compute_whoop_health(date)`
  - `compute_qa_health()`
  - `record_and_check_emergency(source_reason, pitcher_id)`
  - `format_digest_message(digest)`
- `bot/main.py`
  - scheduled 9am Chicago admin digest
  - `/healthcheck`
  - `/healthdigest`
  - `/testemergency`
- `api/routes.py`
  - `/admin/health`
  - logs check-in, outing, ask, chat, swap, WHOOP callback failures
- `plan_generator.py`
  - persists `plan_generated.source`
  - persists `plan_generated.source_reason`
  - records LLM timeout / parse / assembly failures
- `research_resolver.py`
  - writes `research_load_log`
- `api/routes.py` + mini-app components
  - write `ui_fallback_log`
- `api/main.py`
  - basic `/health` with Supabase connectivity and env presence checks

### What Existing Monitoring Catches

- LLM enrichment degradation.
- Python fallback rates.
- WHOOP pull gaps.
- Q&A failure rates.
- Some repeated LLM/API emergency classes.
- Frontend fallback rendering events.
- Research payload / source load behavior.

### What It Does Not Yet Catch

- Railway runtime log errors outside explicitly persisted app telemetry.
- Supabase API/PostgREST/auth/storage log errors.
- Vercel frontend runtime failures.
- Repeated 4xx/5xx route-specific failures by endpoint.
- Schema drift before it causes user-facing failures.
- Migration drift between local SQL files and Supabase state.
- Build/deploy failures.
- Error clustering across services.
- Root-cause briefs for Claude Code/Codex.
- Drift from product architecture or project vision.

---

## 3. Product Framing

### Working Name

**System Guardian**

Other possible names:

- Ops Intelligence Layer
- Guardian Layer
- Reliability Coach
- Steward
- Control Tower

### North Star

The Guardian is the system's self-awareness layer. It detects when the product is silently degrading, when runtime behavior is failing, and when implementation choices diverge from the intended architecture.

It should make the product safer without making it feel brittle or bureaucratic.

### Why This Belongs In This Product

The product vision frames Battery as baseball coaching infrastructure, not a generic AI workout app. That implies trust. Trust requires:

- no silent data loss
- no silent AI degradation
- no security drift
- clear coach authority
- player autonomy inside guardrails
- deterministic constraint logic where deterministic logic belongs
- legible reasoning

The Guardian protects those promises.

---

## 4. Jobs To Be Done

### Job 1 - Detect Runtime Breakage

The Guardian should pull or receive operational signals from:

- Railway logs.
- Railway deployment/build status.
- Supabase logs and advisory signals.
- App `/health`.
- App `/admin/health`.
- Existing Supabase telemetry tables.
- Vercel logs/build status, when available.
- GitHub commit/deploy metadata, if available.

### Job 2 - Detect Silent Product Degradation

Silent degradation means the user may see a normal UI while intelligence quality declines.

Examples:

- `python_fallback` spikes.
- LLM enrichment rate drops below threshold.
- research payload size spikes.
- check-in saved but no plan ships.
- weekly narratives stop being written.
- WHOOP linked athletes stop receiving daily biometric pulls.
- frontend silently falls back to placeholder exercise rendering.
- coach dashboard reads stale team status.

### Job 3 - Cluster Noise Into Incidents

Raw logs are not the product. The Guardian should cluster observations into incidents:

```text
incident_signature = service + surface + route_or_job + error_class + stack_hash + normalized_message
```

An incident should have:

- severity
- first_seen
- last_seen
- count
- affected services
- affected routes/jobs
- affected users/pitchers, when safe and relevant
- sample log lines
- suspected source files
- current status: open / acknowledged / investigating / resolved / muted

### Job 4 - Produce Debug Packets For Claude Code/Codex

Each incident should be convertible into a compact handoff:

```text
Title
Symptom
Impact
Evidence
Likely entrypoint
Recent related changes
Suspected files
Reproduction path
Suggested tests
Open questions
Risk if ignored
```

This is the bridge from monitoring to repair. The goal is not for the Guardian to push arbitrary code automatically in V1. The goal is for it to hand Claude/Codex a well-scoped investigation packet.

### Job 5 - Detect Vision Drift

The Guardian should compare implementation changes and operational symptoms against the project's product/architecture constitution:

- `CLAUDE.md`
- `PROJECT_VISION.md`
- `PRODUCT_VISION_DRAFT.md`
- `PRODUCT_BUILD_PLAN.md`
- future accepted architecture docs

It should flag likely drift patterns:

- LLM doing deterministic constraint-engine work.
- Constraint logic duplicated across unrelated modules.
- New plan paths bypass `source` / `source_reason` tagging.
- Player agency reduced without a constraint-based reason.
- Coach authority bypassed.
- Generic fitness behavior creeping into baseball-native workflows.
- Silent fallbacks without telemetry.
- New user-facing surfaces without error states.
- New Supabase public tables without explicit RLS/grant posture.
- New plan fields written on one path but missing from fallback paths.

---

## 5. Non-Goals

V1 should not:

- auto-edit production code without human approval
- auto-deploy fixes
- ingest unlimited logs into an LLM
- store secrets in incident text
- expose sensitive athlete health data outside the existing admin boundary
- replace existing `health_monitor.py`
- become a generic observability platform

The Guardian should compose existing monitoring, not erase it.

---

## 6. Proposed Architecture

### Modules

```text
pitcher_program_app/
  bot/services/
    system_guardian/
      __init__.py
      collectors/
        app_health.py
        existing_health.py
        railway.py
        supabase.py
        vercel.py
        github.py
      normalize.py
      classify.py
      cluster.py
      incidents.py
      debug_packet.py
      vision_check.py
      notify.py
      scheduler.py
```

### Data Flow

```text
Collectors
  -> raw observations
  -> normalize
  -> classify severity/type
  -> cluster into incidents
  -> persist incidents
  -> create digest/debug packets
  -> notify admin / expose API
```

### Runtime Model

V1 should run as part of the existing Railway process using APScheduler, similar to the 9am health digest.

Initial cadence:

- every 15 minutes: collect recent platform/app signals
- every 60 minutes: send critical/warning digest only if new or changed incidents
- daily 9am: fold Guardian summary into existing health digest

Later option:

- separate Railway worker process if collectors become slow or rate-limited

---

## 7. Collector Contracts

Each collector should return normalized-ish observations and never raise.

```python
{
    "source": "railway",
    "service": "api",
    "observed_at": "2026-05-02T14:30:00-05:00",
    "severity_hint": "error",
    "event_type": "runtime_log",
    "surface": "api_route",
    "route_or_job": "POST /api/chat",
    "message": "Check-in processing error for pitcher_x: TypeError...",
    "error_class": "TypeError",
    "stack": "...",
    "metadata": {
        "deployment_id": "...",
        "request_id": "...",
        "pitcher_id": "pitcher_x"
    }
}
```

### Collector: Existing Health

Wraps current `health_monitor.compute_daily_digest()`.

Transforms plan/WHOOP/Q&A/weekly narrative health into observations. This prevents duplicate logic and keeps the current digest useful.

### Collector: App Health

Calls local functions or HTTP endpoints:

- `/health`
- `/admin/health`, when auth/context allows

Can run in-process first to avoid auth complexity.

### Collector: Railway

Possible implementation paths:

1. Railway API, if stable and credentials available.
2. Railway CLI through a controlled script, if API is unavailable.
3. Manual paste/import fallback for development.

Required env:

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_SERVICE_ID`, if needed

V1 can start with CLI/API disabled unless env is present.

### Collector: Supabase

Possible signals:

- PostgREST errors.
- auth errors.
- database logs.
- migration/advisor warnings.
- table grant/RLS posture.

Required env:

- `SUPABASE_ACCESS_TOKEN`, if using management API.
- `SUPABASE_PROJECT_REF`.
- existing `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.

V1 minimum:

- query application telemetry tables
- optionally run security posture checks against known public tables

### Collector: Vercel

V1 optional. Useful later for:

- frontend build failures
- serverless function logs, if any
- deployment status

### Collector: GitHub

V1 optional. Useful later for:

- latest commit on deployed branch
- PR/check failures
- commit range since last healthy digest

---

## 8. Incident Data Model

### Table: `system_observations`

Append-only raw-ish normalized events.

Columns:

- `id uuid primary key`
- `observed_at timestamptz not null`
- `source text not null`
- `service text`
- `event_type text not null`
- `severity_hint text`
- `surface text`
- `route_or_job text`
- `message text not null`
- `error_class text`
- `stack_hash text`
- `signature text not null`
- `metadata jsonb default '{}'`
- `created_at timestamptz default now()`

Retention:

- 14-30 days for observations.

### Table: `system_incidents`

Clustered operational events.

Columns:

- `id uuid primary key`
- `signature text unique not null`
- `title text not null`
- `status text not null default 'open'`
- `severity text not null`
- `category text not null`
- `first_seen timestamptz not null`
- `last_seen timestamptz not null`
- `count integer not null default 1`
- `affected_services text[] default '{}'`
- `affected_surfaces text[] default '{}'`
- `affected_entities jsonb default '{}'`
- `sample_messages jsonb default '[]'`
- `suspected_files text[] default '{}'`
- `debug_packet jsonb default '{}'`
- `vision_flags jsonb default '[]'`
- `last_notified_at timestamptz`
- `created_at timestamptz default now()`
- `updated_at timestamptz default now()`

### Table: `guardian_reviews`

AI-written analysis packets, separate from incidents so they can be regenerated.

Columns:

- `id uuid primary key`
- `incident_id uuid references system_incidents(id)`
- `review_type text not null`
- `model text`
- `input_fingerprint text`
- `summary text not null`
- `debug_packet jsonb default '{}'`
- `vision_flags jsonb default '[]'`
- `created_at timestamptz default now()`

---

## 9. Severity Model

### Severity: Critical

Page immediately.

Examples:

- check-in route failing repeatedly
- plan generation not shipping
- auth/security failures
- exposed secret/token pattern
- Supabase unavailable
- migration broke core dashboard endpoints
- Telegram bot cannot receive/send messages

### Severity: Warning

Send digest and surface on admin health.

Examples:

- LLM enrichment below 60% rolling
- WHOOP missing for linked pitchers
- repeated frontend fallback
- intermittent endpoint 500
- Q&A failure rate above threshold
- vision drift warning in active code path

### Severity: Info

Persist but do not notify unless included in daily summary.

Examples:

- single transient timeout
- one-off user input parse failure
- expected empty states

---

## 10. Categories

Recommended categories:

- `runtime_error`
- `deployment_failure`
- `database_error`
- `security_posture`
- `silent_degradation`
- `llm_degradation`
- `frontend_degradation`
- `schema_drift`
- `vision_drift`
- `data_quality`
- `external_integration`

---

## 11. Vision Drift Checker

### Inputs

Static docs:

- `CLAUDE.md`
- `PROJECT_VISION.md`
- `PRODUCT_VISION_DRAFT.md`
- `PRODUCT_BUILD_PLAN.md`

Code/change context:

- changed files since last accepted baseline
- new migrations
- new API routes
- new plan generation paths
- new LLM prompts
- new public tables
- new fallback paths

Operational context:

- incident category
- affected route/job
- debug packet
- source log messages

### First-Class Principles To Encode

1. **Coach equipped, not replaced.**
2. **Player agency preserved inside a defended constraint envelope.**
3. **AI is research librarian + operations manager + memory, not unconstrained coach.**
4. **Deterministic constraints live outside the LLM.**
5. **Plan generation is auditable.**
6. **Silent degradation must be observable.**
7. **Baseball-native logic beats generic fitness patterns.**
8. **Supabase public surface must be intentionally locked down.**
9. **Fallback paths must preserve data and telemetry.**
10. **Every human-facing feature needs clear error/empty/degraded states.**

### Output Shape

```python
{
    "drift": True,
    "severity": "warning",
    "principle": "Silent degradation must be observable",
    "evidence": [
        "New fallback branch in plan_generator.py returns python_plan without source_reason",
        "Existing digest depends on source_reason to classify degradation"
    ],
    "recommendation": "Add source/source_reason to the fallback and a regression test."
}
```

### V1 Implementation

Start rule-based. Do not need LLM yet.

Rules:

- If a migration creates a public table and no RLS/grant statements appear, flag.
- If `plan_generator.py` gains a `return python_plan` near an exception path without `source_reason`, flag.
- If new LLM prompt or plan path does not reference constraints/source tagging, flag for review.
- If new API route catches `Exception` and returns success or generic fallback without logging, flag.
- If new frontend route has no error state, flag.

### V2 Implementation

LLM-assisted review against docs, using a compact code diff and selected vision excerpts.

---

## 12. Debug Packet Contract

A debug packet is what gets handed to Claude Code or Codex.

```json
{
  "title": "Check-in route failing after main sync",
  "severity": "critical",
  "category": "runtime_error",
  "symptom": "POST /api/chat produced 6 failures in 18 minutes.",
  "impact": "Pitchers may be unable to complete morning check-in.",
  "evidence": [
    "TypeError in process_checkin call",
    "First seen 2026-05-02T08:12:00-05:00",
    "Affected route: POST /api/chat"
  ],
  "likely_entrypoint": "api/routes.py post_chat()",
  "suspected_files": [
    "pitcher_program_app/api/routes.py",
    "pitcher_program_app/bot/services/checkin_service.py"
  ],
  "recent_changes": [
    "Branch synced to origin/main at 81306c4"
  ],
  "reproduction": [
    "Run chat check-in payload against POST /api/chat",
    "Run tests around checkin_service signature"
  ],
  "suggested_tests": [
    "python -m pytest tests/test_checkin_service_phase1.py",
    "python -m pytest tests/test_team_daily_status_contract.py"
  ],
  "vision_flags": []
}
```

---

## 13. Notification Surfaces

### V1

- Existing Telegram admin chat.
- Existing `/admin/health`.

### V1.5

- New `/admin/guardian` endpoint returning open incidents.
- Add Guardian section to 9am digest.

### V2

- Coach dashboard admin-only page.
- GitHub issue or PR comment generation.
- Claude/Codex handoff artifact generation.

---

## 14. API Endpoints

Proposed admin endpoints:

```text
GET /admin/guardian
GET /admin/guardian/incidents
GET /admin/guardian/incidents/{id}
POST /admin/guardian/incidents/{id}/ack
POST /admin/guardian/incidents/{id}/resolve
POST /admin/guardian/incidents/{id}/mute
POST /admin/guardian/incidents/{id}/debug-packet
```

Auth should match `/admin/health` for V1.

---

## 15. Phased Build Plan

### Phase 0 - Spec Integration

Goal: merge this spec with the other local-machine ideation.

Output:

- accepted V1 scope
- collector choices
- table names
- notification policy
- whether Guardian lives in `health_monitor.py` or a new package

### Phase 1 - Internal Guardian From Existing Signals

No Railway/Supabase external log scraping yet.

Build:

- `system_guardian` package
- observation/incident data model
- collector wrapping existing `compute_daily_digest()`
- collector for app `/health` in-process
- clustering/signature logic
- admin digest section
- unit tests

This proves the shape using current telemetry.

### Phase 2 - Platform Collectors

Build:

- Railway collector
- Supabase collector
- retention/pruning
- dedup notification windows
- debug packet generation from incidents

### Phase 3 - Vision Drift V1

Build:

- rule-based vision drift checks
- migration RLS/grant posture check
- fallback telemetry check
- plan path source tagging check
- frontend error-state heuristic
- include flags in debug packets

### Phase 4 - Claude/Codex Handoff

Build:

- one-click or command-generated incident markdown
- suspected file list
- suggested tests
- optional GitHub issue creation
- optional local artifact under `docs/guardian/incidents/`

### Phase 5 - Coach/Admin Surface

Build:

- admin-only dashboard surface
- incident timeline
- status/mute controls
- trend charts for degradation categories

---

## 16. V1 Acceptance Criteria

V1 is done when:

- Existing health digest signals are converted into persisted observations/incidents.
- Repeated `python_fallback` degradation becomes one incident, not N log lines.
- Repeated WHOOP missing pulls become one incident.
- `/admin/guardian/incidents` returns open incidents.
- 9am admin digest includes a Guardian summary.
- Incident debug packet contains suspected files and suggested tests.
- Tests cover:
  - signature generation
  - clustering count/first_seen/last_seen
  - severity classification
  - digest formatting
  - debug packet shape

---

## 17. Open Questions

1. Should V1 persist observations immediately, or only persist clustered incidents?
2. Should Railway/Supabase external collectors be in-process, or run as a separate worker?
3. Should incident notifications go to Telegram only, or also to email/Slack later?
4. Do we want GitHub issue creation, or would that create too much project noise?
5. What is the "accepted vision baseline" for drift checks: `PROJECT_VISION.md`, `PRODUCT_VISION_DRAFT.md`, or a new canonical `PRODUCT_ARCHITECTURE.md`?
6. Should AI-generated debug reviews be stored in Supabase, committed as local markdown, or both?
7. Should we treat vision drift as an incident category, or as annotations on operational incidents?
8. How much athlete-specific information is acceptable in debug packets?
9. Should the Guardian be admin-only forever, or should some health signals appear in the coach dashboard?

---

## 18. Design Decisions To Debate

### Decision A - Compose Or Replace `health_monitor.py`

Recommendation: compose.

Reason: existing health monitoring is battle-tested and product-specific. Guardian should consume it as one collector, then add platform logs and incident intelligence around it.

### Decision B - Scheduled Worker Or Autonomous Agent

Recommendation: scheduled worker first.

Reason: reliability tooling should be boring at the base layer. AI belongs in summarization/review after evidence has been structured.

### Decision C - Store Raw Logs Or Normalized Observations

Recommendation: normalized observations with limited raw samples.

Reason: raw logs can contain secrets, sensitive data, and noise. Store enough evidence to debug, not unlimited exhaust.

### Decision D - Vision Drift Rule-Based Or LLM-Based

Recommendation: rule-based V1, LLM-assisted V2.

Reason: many high-value drift checks are deterministic. LLM review becomes useful once the packet is small and the principles are explicit.

### Decision E - Debug Packets As JSON Or Markdown

Recommendation: both.

Reason: JSON for API/storage, Markdown for human/Codex handoff.

---

## 19. Example Digest

```text
System Guardian - 2026-05-02 09:00

Critical: 0
Warnings: 2

Warnings:
- LLM enrichment below target: 7d rate 42%, 11 fallbacks. Top reason: llm_timeout.
- WHOOP pull missing for 2 linked pitchers.

Vision drift: 1
- New fallback path may bypass source_reason tagging. Review suggested before deploy.

Debug packets ready:
- guardian/incidents/2026-05-02-llm-enrichment-drop.md
```

---

## 20. Example Implementation Slice

Smallest useful PR:

1. Add `system_guardian/normalize.py`, `classify.py`, `cluster.py`, `debug_packet.py`.
2. Add migration for `system_observations` and `system_incidents`.
3. Add collector that converts `compute_daily_digest()` into observations.
4. Add `run_guardian_check()` that persists incidents.
5. Add tests for clustering and severity.
6. Add `/admin/guardian/incidents`.
7. Add Guardian section to `format_digest_message()`.

This avoids platform API complexity while creating the durable skeleton.

---

## 21. Integration Notes For Other Spec

When comparing another version of this idea, evaluate it against these axes:

- Does it reuse existing `health_monitor.py`, or duplicate it?
- Does it distinguish observations from incidents?
- Does it have a data-retention story?
- Does it avoid dumping raw logs into an LLM?
- Does it produce Claude/Codex-ready packets?
- Does it define severity and notification policy?
- Does it include product-vision drift, or only runtime errors?
- Does it treat security/RLS drift as first-class?
- Does it stay admin-only?
- Does it define V1 small enough to ship?
