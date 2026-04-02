-- Migration: Enrich weekly_summaries with structured aggregation columns
-- Applied: 2026-04-01

ALTER TABLE weekly_summaries
  ADD COLUMN IF NOT EXISTS avg_arm_feel FLOAT,
  ADD COLUMN IF NOT EXISTS avg_sleep FLOAT,
  ADD COLUMN IF NOT EXISTS exercise_completion_rate FLOAT,
  ADD COLUMN IF NOT EXISTS exercises_skipped JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS throwing_sessions INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_throws INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS flag_distribution JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS movement_pattern_balance JSONB DEFAULT '{}';
