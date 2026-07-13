# Runbook — Program Engine v1 live-LLM run (Sprint A step 6)

> The single most important unverified claim in the project: `author.py` (the
> LLM-forward authoring core) has never run against a real model. Everything
> green so far ran the deterministic fallback. This runbook is the one-command
> path to closing that gap, targeting the **return-to-play** pack per the
> 2026-07-13 goal pivot.

## Prerequisites

1. **Env vars** (already added to the Claude cloud environment 2026-07-13):
   `DEEPSEEK_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
2. **Network egress** to `api.deepseek.com` and `beyolhukpbvvoxvjnwtd.supabase.co`.
   ⚠️ As of 2026-07-13 the Claude cloud environment's **network policy denies
   both hosts** (proxy answers 403 to CONNECT — verified). Fix in
   claude.ai/code → environment settings → network access: allow those two
   domains (or set the policy to trusted). Alternative: run from your laptop
   or a Railway shell, where `.env` already works.
3. **Seed the RTP template** (one-time, idempotent):
   ```bash
   cd pitcher_program_app
   python -m scripts.seed_rtp_knowledge_pack          # exit 0 = seeded+verified
   ```

## The run

```bash
cd pitcher_program_app
python -m scripts.demo_program_engine_v1 --goal return_to_play            # no DB write
python -m scripts.demo_program_engine_v1 --goal return_to_play --persist  # + programs row
```

(`--goal velocity` runs the original velocity pack; default is return_to_play.)

## What success looks like

- `Generation:` block shows `mode_used: live`, `fallback_used: False`, and an
  attempts list ending in a validated program (repair/re-prompt attempts ≤ 2
  are fine — that's the guardrail plane working).
- `living_knowledge.changed: true` (knowledge_version moves when the doc moves).
- Artifacts in `docs/superpowers/research/2026-06-02-program-engine-demo/`:
  `01_generated_program.json` (inspect: 9 weeks, phases named per the RTP arc,
  every exercise ID resolvable, warm-up ladder present on throwing days) and
  the rendered Markdown + drive-seam trace.
- With `--persist`: a `programs` row with `generation_provenance` set and
  `engine_version: v1`.

## Known failure modes

| Symptom | Meaning | Action |
|---|---|---|
| `ProxyError: 403 Forbidden` | network policy still blocking | fix prereq 2 |
| `GenerationFailure: parse` repeatedly → fallback | model output not valid JSON / schema | inspect `program_generation_failures` rows; tune `bot/prompts/program_engine_author.md`; re-run |
| Guardrail rejects ×3 → fallback | authored program violates invariants | read the ValidationResult in the failure row — if the invariant is wrong for RTP (e.g. velocity-shaped assumption), fix the invariant knobs in the template row, not the validator code |
| 120s timeout → fallback | deepseek-reasoner latency | re-run; if chronic, raise timeout in `call_llm_reasoning` caller |

Every failure lands in the demo report AND (with Supabase env) in
`program_generation_failures` — nothing is silent.

## After a good run

1. Commit the demo artifacts, update MISSION_CONTROL.html (engine workstream
   pct/log) and the sprint queue.
2. Sanity-read the program as a coach: does the arc respect the mound-volume
   ladder + gates? Landon reviews before anything goes further.
3. Then Sprint A close-out: CLAUDE.md "What's Next", tag
   `program-engine-v1-clean-room` after PR #37 merges.
