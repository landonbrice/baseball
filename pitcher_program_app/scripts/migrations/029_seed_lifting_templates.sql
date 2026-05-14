-- Plan 7 / A13 — seed lifting templates so the Build form's lifting domain
-- has candidates beyond the "coming soon" message.

INSERT INTO block_library (
  block_template_id, name, description, block_type, duration_days, content,
  source, domain, goal_tags, duration_range_weeks, compatible_phases,
  tunable_parameters_schema, week_scaffold_json, research_doc_ids, implied_phase
) VALUES (
  'hypertrophy_8wk_v1',
  '8-Week Hypertrophy Block',
  'Upper/Lower split 4x/week. Volume emphasis on compound + accessory pairings. Pitcher-specific volume caps to protect shoulder health.',
  'lifting', 56,
  '{"scaffold_ref": "hypertrophy_8wk_v1.week_scaffold_json", "source_template": "hypertrophy_8wk_v1"}'::jsonb,
  'spec_program_builder_v1',
  'lifting',
  ARRAY['hypertrophy','muscle_growth','size'],
  '[6,10]'::int4range,
  ARRAY['off_season','preseason'],
  '{}'::jsonb,
  $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Upper — Hypertrophy"},
      {"day_offset": 1, "template_key": "day_1", "label": "Lower — Hypertrophy"},
      {"day_offset": 2, "template_key": "day_2", "label": "Recovery + Mobility"},
      {"day_offset": 3, "template_key": "day_3", "label": "Upper — Accessory Volume"},
      {"day_offset": 4, "template_key": "day_4", "label": "Lower — Posterior Chain"},
      {"day_offset": 5, "template_key": "day_5", "label": "Active Recovery"},
      {"day_offset": 6, "template_key": "day_6", "label": "Off"}
    ],
    "source_template": "hypertrophy_8wk_v1",
    "notes": "Volume-focused 4-day split. Day-content via exercise_pool with hypertrophy intent tag."
  }$$::jsonb,
  ARRAY[]::TEXT[],
  'off_season'
), (
  'in_season_lifting_starter_v1',
  'In-Season Lifting — Starter Maintenance',
  '2x/week minimum-effective-dose lifting block. Preserves strength without compromising recovery between starts.',
  'lifting', 84,
  '{"scaffold_ref": "in_season_lifting_starter_v1.week_scaffold_json", "source_template": "in_season_lifting_starter_v1"}'::jsonb,
  'spec_program_builder_v1',
  'lifting',
  ARRAY['in_season_lifting','strength_maintain','minimum_effective_dose'],
  '[10,16]'::int4range,
  ARRAY['in_season_active','in_season'],
  '{}'::jsonb,
  $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Game / Rest"},
      {"day_offset": 1, "template_key": "day_1", "label": "Day-After — Light Recovery"},
      {"day_offset": 2, "template_key": "day_2", "label": "Lower — Power Maintain"},
      {"day_offset": 3, "template_key": "day_3", "label": "Upper — Pull Emphasis"},
      {"day_offset": 4, "template_key": "day_4", "label": "Recovery"},
      {"day_offset": 5, "template_key": "day_5", "label": "Light Upper + Mobility"},
      {"day_offset": 6, "template_key": "day_6", "label": "Pre-Game — Mobility Only"}
    ],
    "source_template": "in_season_lifting_starter_v1",
    "notes": "Pairs with tpl_starter_7day_cadence_v1 throwing block — same calendar shape."
  }$$::jsonb,
  ARRAY[]::TEXT[],
  'in_season_active'
)
ON CONFLICT (block_template_id) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    domain = EXCLUDED.domain,
    goal_tags = EXCLUDED.goal_tags,
    duration_range_weeks = EXCLUDED.duration_range_weeks,
    compatible_phases = EXCLUDED.compatible_phases,
    week_scaffold_json = EXCLUDED.week_scaffold_json,
    implied_phase = EXCLUDED.implied_phase;
