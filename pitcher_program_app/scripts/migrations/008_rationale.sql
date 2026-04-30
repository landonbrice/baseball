-- pitcher_program_app/scripts/migrations/008_rationale.sql
-- F4 Legible AI Decisions — add rationale JSONB on daily_entries.
-- Per-exercise rationale + day_summary_rationale live inside plan_generated (no schema change).

ALTER TABLE daily_entries
  ADD COLUMN IF NOT EXISTS rationale JSONB DEFAULT NULL;

COMMENT ON COLUMN daily_entries.rationale IS
  'F4 rationale layer: {rationale_short: str ≤120, rationale_detail: {status_line, signal_line, response_line}}. Null for pre-F4 rows.';
