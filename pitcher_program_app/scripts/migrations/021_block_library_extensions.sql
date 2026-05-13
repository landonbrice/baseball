-- Migration 010: extend block_library to act as canonical Template store.
-- All columns nullable so existing rows continue to work.
-- See spec Section 1 — Object & Data Model — Template.

ALTER TABLE block_library
  ADD COLUMN IF NOT EXISTS domain                     TEXT
    CHECK (domain IS NULL OR domain IN ('throwing','lifting')),
  ADD COLUMN IF NOT EXISTS goal_tags                  TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS duration_range_weeks       INT4RANGE,
  ADD COLUMN IF NOT EXISTS compatible_phases          TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tunable_parameters_schema  JSONB  NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS week_scaffold_json         JSONB,
  ADD COLUMN IF NOT EXISTS research_doc_ids           TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS modification_rules_json    JSONB,  -- nullable, reserved for v2 (D7 → C target)
  ADD COLUMN IF NOT EXISTS implied_phase              TEXT;

CREATE INDEX IF NOT EXISTS idx_block_library_domain
  ON block_library (domain)
  WHERE domain IS NOT NULL;
