-- Plan 8 / C1 — track when a coach accepted an insight so A4's daily dedup
-- can suppress re-firing for 14 days. Plan 7 A4's insights have `status`
-- (pending / dismissed / accepted) but no timestamp on the accept event;
-- we need the timestamp so the suppression window is calendar-bounded.

ALTER TABLE coach_suggestions
  ADD COLUMN IF NOT EXISTS accepted_at timestamptz;
