-- Plan 6 / B1 hotfix — seed the 3 stub block_library rows with Plan-1-era
-- fields so the Build a Program form returns candidates for goals beyond
-- "in_season_maintenance". Before this migration, only tpl_starter_7day_cadence_v1
-- was fully seeded; the other three rows had NULL domain / empty goal_tags /
-- empty compatible_phases / NULL duration_range_weeks → matcher returned 0
-- candidates for every other goal.
--
-- Idempotent: UPDATEs only the rows where the fields are still NULL/empty.
-- Re-runs are no-ops once fields are populated.

UPDATE block_library SET
  domain                = 'throwing',
  goal_tags             = ARRAY['velocity','velocity_development'],
  compatible_phases     = ARRAY['off_season','preseason'],
  duration_range_weeks  = '[10,14]'::int4range,
  implied_phase         = 'off_season',
  week_scaffold_json    = $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Velocity Intent — High Effort"},
      {"day_offset": 1, "template_key": "day_1", "label": "Recovery + Light Arm Care"},
      {"day_offset": 2, "template_key": "day_2", "label": "Mound — Plyo + Pulldowns"},
      {"day_offset": 3, "template_key": "day_3", "label": "Long Toss + Recovery"},
      {"day_offset": 4, "template_key": "day_4", "label": "Lower-Body Lifting"},
      {"day_offset": 5, "template_key": "day_5", "label": "Light Catch + Mobility"},
      {"day_offset": 6, "template_key": "day_6", "label": "Off — Mobility Only"}
    ],
    "source_template": "velocity_12wk_v1",
    "notes": "Velocity development block. Day-content resolution defers to exercise_pool at consume time."
  }$$::jsonb
WHERE block_template_id = 'velocity_12wk_v1' AND domain IS NULL;

UPDATE block_library SET
  domain                = 'throwing',
  goal_tags             = ARRAY['longtoss','arm_health','return_to_throwing'],
  compatible_phases     = ARRAY['off_season','preseason'],
  duration_range_weeks  = '[4,8]'::int4range,
  implied_phase         = 'preseason',
  week_scaffold_json    = $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Long Toss — Extension Day"},
      {"day_offset": 1, "template_key": "day_1", "label": "Recovery + Mobility"},
      {"day_offset": 2, "template_key": "day_2", "label": "Mid-Distance Catch"},
      {"day_offset": 3, "template_key": "day_3", "label": "Long Toss — Pull-Down Day"},
      {"day_offset": 4, "template_key": "day_4", "label": "Lower-Body Lifting"},
      {"day_offset": 5, "template_key": "day_5", "label": "Light Catch"},
      {"day_offset": 6, "template_key": "day_6", "label": "Off"}
    ],
    "source_template": "longtoss_ramp_6wk_v1",
    "notes": "Long-toss ramp for return-to-throwing or pre-season distance ramp."
  }$$::jsonb
WHERE block_template_id = 'longtoss_ramp_6wk_v1' AND domain IS NULL;

UPDATE block_library SET
  domain                = 'throwing',
  goal_tags             = ARRAY['offseason_base','base','gpp'],
  compatible_phases     = ARRAY['off_season'],
  duration_range_weeks  = '[3,6]'::int4range,
  implied_phase         = 'off_season',
  week_scaffold_json    = $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Light Catch + Movement Prep"},
      {"day_offset": 1, "template_key": "day_1", "label": "Mobility + Recovery"},
      {"day_offset": 2, "template_key": "day_2", "label": "Mid Catch + Plyo Care"},
      {"day_offset": 3, "template_key": "day_3", "label": "Lower-Body Lifting"},
      {"day_offset": 4, "template_key": "day_4", "label": "Light Catch"},
      {"day_offset": 5, "template_key": "day_5", "label": "Upper-Body Lifting"},
      {"day_offset": 6, "template_key": "day_6", "label": "Off"}
    ],
    "source_template": "offseason_base_4wk_v1",
    "notes": "Off-season base block. Builds throwing tolerance pre-velocity work."
  }$$::jsonb
WHERE block_template_id = 'offseason_base_4wk_v1' AND domain IS NULL;
