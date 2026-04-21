-- Phase 1: Trajectory-aware triage
-- Adds baseline_snapshot JSONB column for per-pitcher rotation-day baselines.
-- Cache is populated on-the-fly by baselines.get_or_refresh_baseline().

ALTER TABLE pitcher_training_model
ADD COLUMN IF NOT EXISTS baseline_snapshot JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pitcher_training_model.baseline_snapshot IS
'Cached baseline: tier, rotation_day_baselines, overall_mean, chronic_drift, computed_at, last_outing_date. Written by bot.services.baselines.get_or_refresh_baseline(). 24h TTL + outing-triggered invalidation.';
