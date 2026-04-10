-- Migration: Programs tab + periodization scaffolding
-- Adds program_templates (seed library) and training_programs (per-pitcher instances).
-- Adds pitcher_training_model.active_program_id FK.

CREATE TABLE IF NOT EXISTS program_templates (
  id                      TEXT PRIMARY KEY,
  name                    TEXT NOT NULL,
  role                    TEXT NOT NULL,           -- 'starter' | 'short_relief' | 'long_relief' | 'any'
  phase_type              TEXT NOT NULL,           -- 'in_season' | 'off_season' | 'pre_season' | 'return_to_throwing'
  rotation_length         INTEGER NOT NULL,
  default_total_weeks     INTEGER,
  description             TEXT,
  phases                  JSONB NOT NULL,
  rotation_template_keys  JSONB,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS training_programs (
  id                      BIGSERIAL PRIMARY KEY,
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  template_id             TEXT NOT NULL REFERENCES program_templates(id),
  name                    TEXT NOT NULL,
  start_date              DATE NOT NULL,
  end_date                DATE,
  total_weeks             INTEGER,
  phases_snapshot         JSONB NOT NULL,
  deactivated_at          TIMESTAMPTZ,
  deactivation_reason     TEXT,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_training_programs_pitcher
  ON training_programs(pitcher_id);

CREATE INDEX IF NOT EXISTS idx_training_programs_active
  ON training_programs(pitcher_id, deactivated_at)
  WHERE deactivated_at IS NULL;

ALTER TABLE pitcher_training_model
  ADD COLUMN IF NOT EXISTS active_program_id BIGINT REFERENCES training_programs(id);
