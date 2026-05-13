# System Guardian — Spec Amendments & Decision Log

> **Status:** Amendments to `2026-05-02-system-guardian-ops-intelligence.md`
> **Created:** 2026-05-09
> **Audience:** Lando, Claude Code, Codex, future implementation agent
> **Purpose:** Lock V1 design decisions, fold in validation findings, and define what must change in the original spec before Phases 2 and 3 begin. The 2026-05-02 spec stays intact as the ideation artifact; this file is the build contract.

---

## 1. Decision Log

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | V1 scope | Phase 1 + Phase 2 + Phase 3 (vision drift) | Confirmed by product owner. Phase 4/5 deferred. |
| D2 | Runtime model | In-process + threadpool isolation | Keep Phase 1 inside existing Railway process; Phase 2 external HTTP collectors run via `asyncio.to_thread` / APScheduler executor with bounded timeouts. Avoids stalling the Telegram event loop. Re-evaluate worker split when collector p95 > 5s. |
| D3 | Persistence | Persist all observations + incidents, 14d retention on observations | Maximum debugging fidelity. Cost paid in storage + PII surface; mitigated by D5 + new RLS migration (A3). |
| D4 | Incident promotion | Notify on every new incident signature | First occurrence is notification-worthy; subsequent occurrences silent until status changes. Paired with shakedown window (A6) so prod baseline doesn't flood. |
| D5 | Athlete data in packets | Full context (pitcher_id, names, flag levels, injury history) | Codex/Claude need real context to investigate. Hard rule: packets are runtime/Telegram/admin-API only. Never written to git, never POSTed to GitHub issues without redaction. |
| D6 | Secret redaction | Read-time **+** write-time regex for known formats | User chose read-time-only; amended to dual-pass. Write-time regex covers Telegram bot tokens, Supabase `sbp_*`/`sbs_*`, JWT `eyJ` prefix, OAuth bearer headers, refresh tokens. Read-time covers everything else. See A4. |
| D7 | Railway collector | Public Railway API token-based, feature-flagged | Behind `if RAILWAY_TOKEN: ...`. Pinned GraphQL query. Kill switch documented. |
| D8 | Supabase collector | Split into two: management API + telemetry tables | Different auth, different rate limits, different failure modes. Spec §7 conflated them. |
| D9 | Vision drift hooks | File-anchored + `# guardian:source-tagged` annotation **+** structural fallback rule | User chose annotation hooks; amended because annotations only catch regressions, not new drift. Structural rule fires when a function returns a plan-shaped dict from inside an `except` block without the annotation. |
| D10 | `recent_changes` source | `git log` shelled out from Railway container | `.git` ships with the Railway deploy. New `subprocess` call only; no library dependency. |
| D11 | Vision baseline docs | Owner to write `PRODUCT_VISION_DRAFT.md` + `PRODUCT_BUILD_PLAN.md` before Phase 3 | Phase 3 is blocked on these landing. Phases 1 and 2 are not. |
| D12 | Shakedown ack mechanism | API-only: `POST /admin/guardian/shakedown/ack`, header auth vs `ADMIN_TELEGRAM_CHAT_ID`. No Telegram inline keyboard in V1. | Smallest viable surface. Telegram button can land in a follow-up if friction proves real. |
| D13 | `compute_plan_health_rolling` integration | `existing_health` collector emits a separate observation with signature `plan_enrichment_health` per digest run, in addition to wrapping `compute_daily_digest()`. | Lets Guardian incident-cluster on enrichment ratio independent of digest output format; otherwise a digest schema change masks the LLM regression class. |
| D14 | `recent_changes` cardinality | `git log` bounded to **last 50 commits AND last 7 days, whichever yields fewer**. Fields: `sha`, `subject`, `author`, `committed_at`. Used only inside debug packets. | Bounds the worst case during a deploy storm. |
| D15 | Observation retention pruning | PR-1 ships SQL function `prune_old_observations()` enforcing the 14d window. PR-2 wires an APScheduler 3am daily job that calls it and emits a `guardian_self` observation with the row count pruned. | Without a scheduled prune the table grows unbounded; we'd discover it months later. Self-observation closes the loop. |

---

## 2. Spec Amendments

Each amendment cites the section of the 2026-05-02 spec it modifies.

### A1 — §6 Runtime contract (concrete)

Original: "APScheduler, similar to the 9am health digest" — does not specify async/sync, timeout, or isolation.

Amend to:

- All collectors are coroutines with a hard `asyncio.wait_for(timeout=5.0)` ceiling per call.
- Sync HTTP work (Railway, Supabase mgmt) runs inside `asyncio.to_thread`.
- Collector failures must not raise — they return an empty list and emit a `collector_failure` observation.
- A single Guardian tick wraps all collectors in `asyncio.gather(..., return_exceptions=True)` with a tick budget of 30s total.
- If tick budget exceeded twice in a row, the next tick logs a `severity=warning category=guardian_self` incident.

### A2 — §7 Supabase collector split

Replace the single Supabase collector with two:

- **`collectors/supabase_app.py`** — queries `daily_entries`, `research_load_log`, `ui_fallback_log`, `whoop_daily`. Auth: existing `SUPABASE_SERVICE_KEY`. No new env vars. Phase 1 candidate.
- **`collectors/supabase_mgmt.py`** — Supabase Management API for advisor lints, RLS posture check, migration drift. Auth: new `SUPABASE_ACCESS_TOKEN` + `SUPABASE_PROJECT_REF`. Add to env-var table in `CLAUDE.md`. Phase 2 candidate, feature-flagged.

### A3 — §8 New tables get RLS lockdown migration

Original §8 declares `system_observations`, `system_incidents`, `guardian_reviews` schemas but does not mandate RLS posture. Given they will contain pitcher IDs + arm/injury context (per D5), they must follow the 010/012 lockdown precedent.

Mandate: the same migration that creates the tables must:

- `enable + force row level security`
- `revoke all on ... from anon, authenticated`
- add explicit `service_role full access` policy per table

V1 acceptance includes a Supabase advisor check showing zero `rls_disabled_in_public` ERRORs and zero `sensitive_columns_exposed` WARNs for the three new tables.

### A4 — §9 Secret-pattern critical clarified

Original lists "exposed secret/token pattern" as Critical without specifying detector or pipeline placement.

Amend to:

- Write-time regex redactor in `normalize.py` runs **before** any DB write. Replaces matches with `[REDACTED:<kind>]`. Increments a counter and emits a `category=security_posture severity=critical` observation tagged with the source/route/job (no secret content).
- Read-time redactor wraps `message`/`stack`/`sample_messages` on every digest/packet/API emit, catching anything the write-time pass missed.
- Patterns covered at minimum:
  - Telegram bot token: `\d{8,10}:[A-Za-z0-9_-]{35,}`
  - Supabase keys: `sbp_[a-z0-9_-]{20,}`, `sbs_[a-z0-9_-]{20,}`, JWT `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
  - WHOOP/OAuth bearer: `Bearer [A-Za-z0-9._-]{20,}`
  - Generic `(?i)(api[_-]?key|secret|password)["'=:\s]+[A-Za-z0-9_-]{16,}`

Tests must assert that a synthetic JWT in a sample message produces a redacted observation **and** a `security_posture` incident.

### A5 — §11 Vision drift rules — principle coverage + structural hook

Original lists ~5 file-anchored rules. Amend to:

- Each of the 10 principles in §11 has at least one rule, even if some start as `TODO` stubs. The principle↔rule map is published in `docs/guardian/vision_rules.md` and updated whenever a new rule lands.
- Existing file-anchored rules keep their place but are **paired** with structural fallbacks:
  - "Plan path missing source_reason" → structural rule: any function whose return statement lives inside an `except` block and produces a dict containing `lifting` or `throwing` keys must include `source` and `source_reason`. AST walk over `bot/services/*.py`.
  - "New public table without RLS" → structural rule: any new migration creating a `public.*` table must have a matching `enable row level security` statement in the same file. Recognizes the 010/012 DO-block + array-of-table-names idiom.
- `# guardian:source-tagged` annotation is an **assertion** that the function is intentionally exempt; removing it on an existing function flags. Adding a new function does not require the annotation — the structural rule covers that case.

### A6 — §16 Acceptance — shakedown window + notification policy

Append to V1 acceptance:

- **24h shakedown window** on first deploy: Guardian persists observations and incidents but suppresses Telegram notifications. Admin receives a single "shakedown summary" at the end of the window listing all signatures seen. Admin acknowledges the baseline; only post-ack new signatures notify.
- Notification dedup policy: same incident signature notifies on first occurrence. `last_notified_at` advances only on status changes (open → ack, ack → resolved, etc.) or severity escalation. No re-notify on rising count alone.
- Shakedown is re-armable via `POST /admin/guardian/shakedown` (admin-only) for major deploys.

### A7 — §15 Phase 4 — packet artifact policy

Phase 4 must not write packets to `docs/guardian/incidents/` or any in-repo path. Amend §15 Phase 4 to:

- Packet generation surfaces: Telegram admin DM, `/admin/guardian/incidents/{id}/debug-packet` API response, and **redacted** GitHub issue body (only when `--redact-pii` flag is passed and athlete IDs are stripped).
- Local artifact path is removed entirely. PII never enters git.

---

## 3. Updated V1 Acceptance Criteria

V1 is done when:

1. `system_observations`, `system_incidents`, `guardian_reviews` tables exist with RLS locked down per A3. Advisor lints clean.
2. Phase 1 collectors live: `existing_health` (wraps `compute_daily_digest()`), `app_health` (in-process `/health` + `/admin/health`), `supabase_app` (queries app telemetry tables).
3. Signature generation, clustering, severity classification, and digest formatting covered by unit tests.
4. Write-time regex redactor (A4) covered by tests including the synthetic-JWT case.
5. 24h shakedown window (A6) is observable: shakedown observations exist in DB but no Telegram pings emitted; admin ack endpoint flips it off.
6. `/admin/guardian` and `/admin/guardian/incidents` return open incidents.
7. 9am admin digest includes a Guardian summary section.
8. Debug packet contract from §12 returns a valid JSON for at least one synthetic incident.
9. `recent_changes` populated via `git log` (D10).
10. Runtime contract from A1 is enforced — collector failures emit `collector_failure` observations and don't raise.
11. Daily 3am pruning job (D15) runs and emits a `guardian_self` observation reporting rows pruned. `system_observations` row count stays bounded over a 30-day soak.

Phase 2 (Railway + Supabase mgmt collectors) and Phase 3 (vision drift) are tracked separately and ship after V1.

---

## 4. Residual Risks

- **Read-time redaction lag.** Even with A4 write-time regex, an unknown secret format will live in `system_observations.message` until either retention prunes it or read-time catches it. Mitigation: retention is 14d, and read-time runs on every emit. If a new format appears in production logs, add it to the regex set within the same week.
- **Railway public API instability.** Pinned GraphQL query may break on upstream changes. Mitigation: kill switch via `RAILWAY_TOKEN` absence, and the Phase 2 collector emits `collector_failure` rather than crashing.
- **Annotation drift.** Existing functions that get the `# guardian:source-tagged` annotation today may have it stripped accidentally during refactors. Mitigation: structural rule (A5) catches the common pattern even without the annotation.
- **Shakedown window blind spot.** A real incident occurring during the first 24h is suppressed from Telegram. Mitigation: shakedown summary lists everything seen so admin can review before acking; critical-severity items can opt out of suppression in a future amendment if this proves painful.
- **Vision baseline gap.** Phase 3 is blocked on `PRODUCT_VISION_DRAFT.md` and `PRODUCT_BUILD_PLAN.md` (D11). Phase 1 + Phase 2 not blocked.

---

## 5. Open Items Carried From §17

Not blockers for V1; revisit before Phase 4 / Phase 5:

- §17 Q3 — notification surfaces beyond Telegram (Slack/email)
- §17 Q4 — GitHub issue auto-creation policy (deferred to Phase 4 with redaction)
- §17 Q6 — AI-generated review storage (git is off the table per D5; Supabase only)
- §17 Q7 — vision drift as separate incident category vs annotation on operational incidents
- §17 Q9 — admin-only forever vs coach dashboard surface

---

## 6. Implementation Order

Recommended PR sequence, smallest first:

1. **PR-1** — migration: create `system_observations`, `system_incidents`, `guardian_reviews` with RLS lockdown (A3).
2. **PR-2** — `system_guardian` package skeleton: `normalize.py` (with A4 redactor), `classify.py`, `cluster.py`, `incidents.py`, `debug_packet.py`. Unit tests.
3. **PR-3** — `collectors/existing_health.py` wrapping `compute_daily_digest()`. Wires into 9am digest as a new section.
4. **PR-4** — `collectors/app_health.py` + `collectors/supabase_app.py`. Signature dedup proven with at least three real signal types.
5. **PR-5** — `/admin/guardian` and `/admin/guardian/incidents` endpoints; shakedown window + ack endpoint (A6).
6. **PR-6** — runtime contract enforcement (A1): timeouts, threadpool isolation, `collector_failure` observations.
7. **PR-7+** — Phase 2 Railway/Supabase mgmt collectors (separate); Phase 3 vision drift (separate, blocked on D11).
