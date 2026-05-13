-- Migration 009b: corrections to 009_programs_core
-- Applied while tables are empty (verified before apply).
--
-- C1: parent_template_id / chosen_template_id changed UUID → TEXT to match
--     block_library.block_template_id (text PRIMARY KEY in migration 006).
-- I1: favorited_blocks.source_daily_entry_id (UUID NOT NULL) replaced with
--     source_pitcher_id TEXT + source_entry_date DATE — daily_entries has
--     a composite PK (pitcher_id text, date), no UUID column to point at.
-- M5: non-negative CHECKs on programs.current_day_index, held_days_count.

-- C1
ALTER TABLE programs
  ALTER COLUMN parent_template_id TYPE TEXT USING parent_template_id::text;

ALTER TABLE program_builder_sessions
  ALTER COLUMN chosen_template_id TYPE TEXT USING chosen_template_id::text;

-- I1
ALTER TABLE favorited_blocks
  DROP COLUMN source_daily_entry_id,
  ADD COLUMN source_pitcher_id TEXT NOT NULL,
  ADD COLUMN source_entry_date DATE NOT NULL;

-- M5
ALTER TABLE programs
  ADD CONSTRAINT programs_current_day_index_nonneg CHECK (current_day_index >= 0),
  ADD CONSTRAINT programs_held_days_count_nonneg   CHECK (held_days_count   >= 0);
