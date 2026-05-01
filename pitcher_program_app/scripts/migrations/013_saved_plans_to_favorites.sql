-- Migration 013: backfill favorited_blocks from saved_plans (locked spec answer 2026-04-30).
-- Idempotent via the 'migrated_from_saved_plans:<saved_plan_id>' note marker — safe to re-run.
--
-- saved_plans is NOT dropped — historical access stays for the existing Profile UI
-- until that surface is rebuilt in Plan 6.
--
-- Column substitutions (observed via information_schema on 2026-04-30):
--   <PLAN_COL> -> plan_data       (jsonb, NOT NULL)
--   <DATE_COL> -> date_created    (date, nullable — fallback chain handles nulls)
--   PK         -> id              (bigint)
--
-- favorited_blocks shape is the post-Task-1-corrections composite ref:
--   source_pitcher_id TEXT NOT NULL  (mirrors saved_plans.pitcher_id)
--   source_entry_date DATE NOT NULL  (saved_plans has no FK to daily_entries; use the
--                                     best date we have, falling back to CURRENT_DATE
--                                     as a last resort so the NOT NULL constraint holds)
--
-- Lifting block extracted if present; otherwise the whole plan payload is captured
-- (favorited_blocks.block_snapshot_json is JSONB and accepts any shape).

INSERT INTO favorited_blocks (
  pitcher_id,
  source_pitcher_id,
  source_entry_date,
  block_type,
  block_snapshot_json,
  note,
  favorited_at
)
SELECT
  sp.pitcher_id,
  sp.pitcher_id,                                                          -- composite ref part 1
  COALESCE(sp.date_created, sp.created_at::date, CURRENT_DATE),           -- composite ref part 2
  'lifting',
  COALESCE(sp.plan_data->'lifting', sp.plan_data),
  'migrated_from_saved_plans:' || sp.id::text,
  COALESCE(sp.created_at, now())
FROM saved_plans sp
WHERE NOT EXISTS (
  SELECT 1 FROM favorited_blocks fb
  WHERE fb.note = 'migrated_from_saved_plans:' || sp.id::text
);
