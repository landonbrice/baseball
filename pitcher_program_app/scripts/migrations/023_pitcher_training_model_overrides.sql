-- Migration 012: per-pitcher phase overrides + feature flags.
-- coach_*_phase_override slots into the spec D6 precedence stack
-- (active program implied phase > coach override > team default).
-- feature_flags is consumed by Plan 4 daily-composition rewrite for
-- scoped rollout (R1).

ALTER TABLE pitcher_training_model
  ADD COLUMN IF NOT EXISTS coach_throwing_phase_override TEXT,
  ADD COLUMN IF NOT EXISTS coach_lifting_phase_override  TEXT,
  ADD COLUMN IF NOT EXISTS feature_flags                 JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pitcher_training_model.feature_flags IS
  'Per-pitcher feature flags. Known keys: program_aware_plan_gen (bool, scoped rollout for Plan 4).';
