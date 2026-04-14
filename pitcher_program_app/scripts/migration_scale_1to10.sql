-- Scale arm_feel and energy from 1-5 → 1-10
-- Run BEFORE deploying code changes
--
-- Strategy: multiply all existing values by 2 (preserves ordering; 1→2, 5→10).
-- Applied 2026-04-13 via Supabase MCP.

-- daily_entries.pre_training.arm_feel (67 rows, range 2-5)
UPDATE daily_entries
SET pre_training = jsonb_set(pre_training, '{arm_feel}',
  to_jsonb((pre_training->>'arm_feel')::int * 2))
WHERE pre_training ? 'arm_feel';

-- daily_entries.pre_training.overall_energy (67 rows, range 3-5)
-- NOTE: key is overall_energy, not energy
UPDATE daily_entries
SET pre_training = jsonb_set(pre_training, '{overall_energy}',
  to_jsonb((pre_training->>'overall_energy')::int * 2))
WHERE pre_training ? 'overall_energy';

-- pitcher_training_model.current_arm_feel (12 rows, range 3-5)
UPDATE pitcher_training_model
SET current_arm_feel = current_arm_feel * 2
WHERE current_arm_feel IS NOT NULL;

-- No outing post_arm_feel rows exist yet; no migration needed for that.
