# Phase 1: Trajectory-Aware Triage — Deployment Runbook

## Pre-deploy checklist

- [ ] Apply migration: `pitcher_program_app/scripts/migrations/007_baseline_snapshot.sql` via Supabase MCP or dashboard
- [ ] Verify migration: `SELECT column_name FROM information_schema.columns WHERE table_name='pitcher_training_model' AND column_name='baseline_snapshot';` returns 1 row
- [ ] Run test suite: `cd pitcher_program_app && python -m pytest tests/test_baselines.py tests/test_triage_phase1.py tests/test_checkin_service_phase1.py`
- [ ] Manual smoke test: run a /checkin via Telegram dev bot and verify logs show `triage_phase1` line with non-null category scores

## First-check-in behavior per pitcher

- **First check-in ever**: Tier 1 (population defaults). Trajectory signals null. Behavior matches legacy triage.
- **After 7+ check-ins / 1 rotation**: Tier 2 auto-promotes. Rotation-day baselines computed.
- **After 21+ check-ins / 3 rotations**: Tier 3 auto-promotes. Full trajectory authority.

## Monitoring

Every check-in now logs a `triage_phase1` line with: `flag`, `tissue`, `load`, `recovery`, `baseline_tier`, `chronic_drift`, `recovery_stall`. Grep Railway logs for `triage_phase1` to audit flag decisions.

The `daily_entries.pre_training` JSONB now includes `category_scores` and `baseline_tier`, queryable for retroactive analysis.

## Rollback

The rewrite preserves backward compat via `_legacy_flag_level()`. To roll back flag decisions without reverting code:
1. Add a feature flag env var (e.g., `DISABLE_PHASE1_TRIAGE=1`)
2. In checkin_service.py, skip passing Phase 1 args when flag is set. Triage falls back to legacy path.

Full code rollback: revert commits from `5728e0f` forward. All Phase 1 changes are contained in the commit range `5728e0f..HEAD` on branch `phase1-trajectory-triage`.

## What's in the new output

- `flag_level` (existing): red | yellow | modified_green | green
- `modifications` (existing): list of mod tags
- `alerts` (existing): list of alert strings
- `protocol_adjustments` (existing): dict
- `reasoning` (existing): string
- `category_scores` (new): `{tissue: float, load: float, recovery: float}` — always populated
- `trajectory_context` (new): `{recovery_curve_status, chronic_drift, trend_flags}` — populated when pitcher_baseline available
- `baseline_tier` (new): 1 | 2 | 3 — always populated

## Known follow-ups (not in this sprint)

- UChicago schedule/pitch-count scraper for outing auto-detection
- Category score visualization in coach dashboard
- Per-pitcher baseline admin inspection command
- Phase 4 science refinement of YAML values
