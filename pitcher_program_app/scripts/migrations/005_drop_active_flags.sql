-- Migration: Drop active_flags table (replaced by pitcher_training_model)
-- Applied: 2026-04-01
-- Data migrated via: scripts/migrate_active_flags_to_model.py (or inline SQL)

-- Step 1: Soft delete (applied)
-- ALTER TABLE active_flags RENAME TO active_flags_deprecated;

-- Step 2: Drop (applied after verification)
-- DROP TABLE IF EXISTS active_flags_deprecated;
