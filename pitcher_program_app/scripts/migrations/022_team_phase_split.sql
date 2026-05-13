-- Migration 011: split teams.training_phase into per-domain columns.
-- Locked spec answer (2026-04-30): per-domain phase model goes in v1, not v2.
-- training_phase column stays for one cycle (deprecated) as a fallback so
-- straggler reads keep working; cleanup deferred to a later plan once all
-- callers migrate to team_scope.get_team_phase(team_id, domain).

ALTER TABLE teams
  ADD COLUMN IF NOT EXISTS throwing_phase TEXT,
  ADD COLUMN IF NOT EXISTS lifting_phase  TEXT;

-- Backfill: every existing team's per-domain phases default to its current training_phase.
UPDATE teams
SET throwing_phase = COALESCE(throwing_phase, training_phase),
    lifting_phase  = COALESCE(lifting_phase,  training_phase)
WHERE training_phase IS NOT NULL;

COMMENT ON COLUMN teams.training_phase IS
  'DEPRECATED — use throwing_phase / lifting_phase. Retained for one cycle.';
