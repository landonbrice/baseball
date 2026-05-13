# Supabase Divergence Scanner — Design

**Status:** Design only. Build deferred until migrations 017+018 are applied.

**Problem this solves.** The April 30 lockdown work (migrations 010/011/012) cleared every advisor lint and CLAUDE.md declared the schema secure. One week later, a new "programs core" migration series introduced 7 tables with RLS disabled and full anon CRUD, plus a function with mutable search_path. Nothing surfaced the regression — the 9am health digest only watches plan-gen enrichment and WHOOP pulls. We caught it via this audit, manually.

The pattern will keep repeating: schema work happens through dashboard SQL editor, MCP `apply_migration`, or new feature migrations, and there's no continuous check that the *intent* (revoke anon, enable+force RLS, pin search_path) survives. We need a checked-in declaration of intent and a daily check that compares it to live state.

## What it checks

Three classes of drift against a checked-in `supabase-intent.yaml`:

1. **Table posture** — for each `public.*` table:
   - RLS enabled? RLS forced?
   - Direct grants on anon/authenticated (should be empty for any table not explicitly opted-in)
   - Policy list — names + role bindings + qual + with_check
2. **Function posture** — for each `public.*` function listed:
   - search_path pinned?
3. **Advisor lints** — pull `get_advisors(security)` + `get_advisors(performance)`. New lint that isn't in an `accepted_lints` allowlist → drift.

## Intent file

`pitcher_program_app/supabase-intent.yaml`. Single file, human-edited, reviewed in PRs.

```yaml
schema_version: 1

# Default posture for every public table.
default:
  rls_enabled: true
  rls_forced: true
  anon_grants: []
  authenticated_grants: []
  policies:
    - name: "service_role full access"
      roles: ["service_role"]
      cmd: ALL
      qual: "true"
      with_check: "true"

# Per-table overrides (rare — exceptions only).
tables:
  # Example: a future read-only public catalog table
  # exercise_library_public:
  #   anon_grants: [SELECT]
  #   policies:
  #     - { name: "anon read-only", roles: [anon], cmd: SELECT, qual: "true" }

functions:
  - name: update_updated_at_column
    args: ""
    search_path: ["public", "pg_temp"]
  - name: update_updated_at
    args: ""
    search_path: ["public", "pg_temp"]
  - name: set_daily_entry_team_id_from_pitcher
    args: ""
    search_path: ["public", "pg_temp"]
  - name: advance_program_counter
    args: "uuid, jsonb, date"
    search_path: ["public", "pg_temp"]

accepted_lints:
  # Auth dashboard toggle, not migration-fixable
  - auth_leaked_password_protection
```

A new public table without an entry in `tables:` inherits `default`. That's the load-bearing rule — it makes the regression we just hit *impossible* to ship silently: the new table must either match the default (locked down) or list itself as an exception in the PR.

## Architecture

```
pitcher_program_app/
├── supabase-intent.yaml                  ← intent (checked-in, PR-reviewed)
└── scripts/
    └── supabase_audit/
        ├── __init__.py
        ├── audit.py                      ← the scanner
        ├── live_state.py                 ← reads via Supabase MCP / SQL
        ├── intent_loader.py              ← parses + validates yaml
        ├── diff.py                       ← intent vs live → list[Drift]
        └── remediation.py                ← Drift → SQL patch
```

### `audit.py` CLI

```
python -m scripts.supabase_audit.audit [--mode {check,fix-suggest}] [--out FILE]

  check         exit 0 on clean, exit 1 on any drift, prints a punch list
  fix-suggest   above + writes a candidate migration SQL to FILE (no apply)
```

No `--apply` mode in v1. Generated migrations land in `scripts/migrations/` via PR review, then are applied via `apply_migration` like every other change. Auto-apply is a much bigger trust step and not in scope.

### Drift output shape

```python
@dataclass
class Drift:
    severity: Literal["critical", "warn", "info"]
    kind: Literal["rls_disabled", "rls_not_forced", "unexpected_grant",
                  "missing_policy", "unexpected_policy", "function_search_path",
                  "new_advisor_lint"]
    object: str   # "public.programs", "public.advance_program_counter(uuid,jsonb,date)"
    detail: str
    fix_sql: str | None
```

`severity` mapping:
- `critical` — anon/authenticated has any grant on a non-allowlisted public table; advisor ERROR-level lint not in `accepted_lints`.
- `warn` — RLS not forced; permissive policy bound to a non-service role; advisor WARN-level lint not in `accepted_lints`.
- `info` — function not yet known to intent (new function landed since intent updated).

## Where it runs

Two surfaces, escalating:

1. **9am health digest.** Append a section to `format_digest_message`. If `audit()` returns 0 drifts, one-line `🛡️ Schema posture: clean`. Otherwise `🚨 Schema posture: N drifts` and the top 3 by severity. Reuses the existing Telegram admin chat. Zero new infra.
2. **GitHub Actions on PRs that touch `scripts/migrations/*`.** Job runs `audit --mode fix-suggest`, posts a comment with the diff if any drift would result from the migration. Catches regressions at PR time, not next morning.

Skip CI for v1 if it adds friction. The 9am digest is the floor.

## How auto-fix works (deferred from v1)

Most drift kinds map to a single deterministic SQL statement (the `fix_sql` field on `Drift`). `remediation.py` collects them into a candidate migration, ordered by dependency. The migration is *suggested*, not applied — committed via PR.

The hard part is the `unexpected_policy` case where a real human policy exists but isn't in intent. v1 punts: surface as `warn`, do not generate a DROP. Human reads the diff, either updates intent.yaml or adjusts the policy.

## Trust boundary

The scanner reads via the same Supabase MCP server already wired in `.mcp.json`. It runs with the service_role context (same as the bot). It does not hold any new secrets. It does not call `apply_migration` in v1.

## Sequencing

1. Apply migrations 017+018 (this PR).
2. Build v1 of the scanner: read-only audit, exits non-zero on drift, no auto-fix.
3. Wire into 9am digest.
4. Add accepted_lints allowlist for `auth_leaked_password_protection` and any other intentional exceptions.
5. **Stop here for a week.** Watch the digest. If the scanner stays green on intentional changes and red on real drift, advance to step 6.
6. PR-time GitHub Action.
7. Optional v2: SQL-suggestion mode that drops a candidate migration into the PR.

## What this is *not*

Not a general schema linter — Supabase's `get_advisors` already does that. The scanner adds the *intent* layer: "this is what we declared the posture should be," so divergence is detectable even when the lint catalog hasn't grown a rule for it yet (the May 1 RLS-disabled tables *were* lint-flagged; we just had no daily check pulling lints).

Not coupled to product/feature intent in CLAUDE.md. Tying scanner findings to feature docs ("this table was added but the spec says it should be team-scoped") is a separate problem — much harder, much more subjective. Punt.

Not a replacement for code review. Permissive policies that an engineer wrote *deliberately* will get flagged; the engineer either updates intent.yaml in the same PR or accepts the warn. The scanner is a safety net, not a gate.
