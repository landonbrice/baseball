# Program Engine v1 — Phase 5 clean-room demo

_Generated 2026-06-02 against `landon_brice`._

## Run environment

- **LLM**: `mocked_fallback_as_llm`
- **block_library**: `stubbed_from_migration_033`
- **persist mode**: `dry-run`

> ⚠️ **LLM call was mocked.** `DEEPSEEK_API_KEY` was not set when this script ran, so `author_program` was bypassed and the deterministic `build_fallback_program` floor was used as the program source. The rest of the pipeline (resolver, schema, guardrails, persistence shape, drive seam) ran for real.

> To re-run with the real LLM, export `DEEPSEEK_API_KEY` and re-execute this script. The fallback path is exactly what would run in prod if the LLM timed out or kept producing rejected programs, so this output is a faithful representation of one of the two real production paths.

## What this demonstrates

1. **End-to-end generation** — see [`01_generated_program.md`](01_generated_program.md) for human-readable; [`01_generated_program.json`](01_generated_program.json) for the artifact.
   - Pitcher: `landon_brice`
   - Goal: `velocity` · 12 weeks
   - knowledge_version: `0c62fd5547765d88`
   - Generation attempts: 1
   - Fallback used: True
   - Total days: 84

2. **Living-knowledge proof** — see [`02_living_knowledge_proof.md`](02_living_knowledge_proof.md).
   - kv before: `0c62fd5547765d88`
   - kv after: `7f1af73f2efc68bf`
   - **Hash invalidates as expected.**

3. **Drive seam walk** — see [`03_drive_seam_trace.md`](03_drive_seam_trace.md).
   - 7-day mixed-readiness trace through `project()` with policy `silent_absorb`.
   - Days traced: 7

## Plan §5 acceptance check

> _An operator can read the output and say 'yes, this is a real program.'_

- ✅ Phase arc present and properly ordered (Base → Distance → Compression → Max Intent).
- ✅ Deload weeks marked at Wk4 and Wk7 per the velocity governor.
- ✅ Base-phase throwing intensity stays <85% (Phase 2.2 gate guarantee).
- ✅ Every lifting day has FPM coverage (landon_brice's `elevated_fpm_volume` mod respected).
- ✅ knowledge_version SHA-1 changes when the source doc is edited (living-knowledge proof).
- ✅ Drive seam modulates throwing on YELLOW/RED days without breaking the program.

_Dry-run only — no `programs` row was written. Re-run with `--persist` to commit one._