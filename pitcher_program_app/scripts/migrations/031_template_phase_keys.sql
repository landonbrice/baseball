-- Plan 8 / B2 — converge the two phase vocabularies.
-- training_phase_blocks.phase_name is freeform display text; block_library.compatible_phases
-- is a fixed 4-value enum. Plan 7 C5 bridged them client-side via phaseToTemplatePhaseIds().
-- This migration makes the canonical token authoritative at write time so the bridge dies.
--
-- The column type is text[] (plural name) so a single phase row can map to multiple
-- compatible_phases enum values when the team's phase semantics straddle two template
-- buckets (e.g. "In-Season" -> both 'in_season' and 'in_season_active').
--
-- No CHECK constraint: PostgreSQL doesn't natively support per-element CHECK on arrays.
-- Future writers (coach UI when phases are editable, Plan 9) will validate against the
-- canonical 4-value set in Python before insert.

BEGIN;

-- (1) Add the column nullable; backfill below; future writers must populate.
ALTER TABLE training_phase_blocks
  ADD COLUMN IF NOT EXISTS template_phase_keys text[];

-- (2) Backfill existing rows via the same mapping rules the Plan 7 C5
--     `phaseToTemplatePhaseIds()` helper used.
UPDATE training_phase_blocks
   SET template_phase_keys = CASE
     WHEN phase_name ~* 'in[-\s]?season'                       THEN ARRAY['in_season','in_season_active']
     WHEN phase_name ~* 'preseason'                            THEN ARRAY['preseason']
     WHEN phase_name ~* 'postseason|off[-\s]?season'           THEN ARRAY['off_season']
     WHEN emphasis = 'maintenance'                             THEN ARRAY['in_season','in_season_active']
     WHEN emphasis = 'power'                                   THEN ARRAY['preseason']
     WHEN emphasis IN ('hypertrophy','strength','gpp')         THEN ARRAY['off_season']
     ELSE ARRAY[]::text[]
   END
 WHERE template_phase_keys IS NULL;

COMMIT;
