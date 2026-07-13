# Program Engine v1 — Phase 5 clean-room demo

_Generated 2026-06-02 against `landon_brice`._

## Run environment

- **LLM**: `live`
- **block_library**: `live`
- **persist mode**: `on`

## What this demonstrates

1. **End-to-end generation** — see [`01_generated_program.md`](01_generated_program.md) for human-readable; [`01_generated_program.json`](01_generated_program.json) for the artifact.
   - Pitcher: `landon_brice`
   - Goal: `return_to_play` · 9 weeks
   - knowledge_version: `9d185eb1dd6ea5aabc7508919c3ee936f7c81a21`
   - Generation attempts: 3
   - Fallback used: True
   - Total days: 63

2. **Living-knowledge proof** — see [`02_living_knowledge_proof.md`](02_living_knowledge_proof.md).
   - kv before: `9d185eb1dd6ea5aabc7508919c3ee936f7c81a21`
   - kv after: `12239824c8035d80aa2bc401bb8283313417aa1c`
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

_A `programs` row was written (see top-of-script return value)._