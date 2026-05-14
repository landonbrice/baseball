-- Migration 014: seed canonical Starter 7-day cadence template into block_library.
-- Mirrors legacy plan_generator rotation (bot/services/plan_generator.py:158-160 —
-- `today_template = rotation_template["days"].get(f"day_{rotation_day}")`) so
-- bootstrapped programs (Task 9) produce the same daily prescriptions as the
-- legacy code. JSON source of truth: data/templates/starter_7day_cadence.json.

INSERT INTO block_library (
  block_template_id,
  name,
  description,
  block_type,
  duration_days,
  content,
  source,
  domain,
  goal_tags,
  duration_range_weeks,
  compatible_phases,
  tunable_parameters_schema,
  week_scaffold_json,
  research_doc_ids,
  modification_rules_json,
  implied_phase
) VALUES (
  'tpl_starter_7day_cadence_v1',
  'In-Season Maintenance — Starter 7-day',
  'Canonical 7-day starter cadence. Bootstraps in-season programs that mirror legacy plan_generator rotation.',
  'throwing',
  84,
  '{"scaffold_ref": "tpl_starter_7day_cadence_v1.week_scaffold_json", "source_template": "starter_7day_v1"}'::jsonb,
  'spec_program_builder_v1',
  'throwing',
  ARRAY['in_season_maintenance','starter_cadence'],
  '[12,12]'::int4range,
  ARRAY['in_season_active','in_season'],
  '{}'::jsonb,
  $${
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0", "label": "Game Day"},
      {"day_offset": 1, "template_key": "day_1", "label": "Day After — Active Recovery"},
      {"day_offset": 2, "template_key": "day_2", "label": "Lower Body — Power Focus"},
      {"day_offset": 3, "template_key": "day_3", "label": "Upper Body — Pull Emphasis"},
      {"day_offset": 4, "template_key": "day_4", "label": "Lower Body — Strength Focus"},
      {"day_offset": 5, "template_key": "day_5", "label": "Light Upper + Pre-Game Prep"},
      {"day_offset": 6, "template_key": "day_6", "label": "Pre-Game Day — Rest/Mobility Only"}
    ],
    "source_template": "starter_7day_v1",
    "notes": "Mirrors legacy plan_generator rotation: days_since_outing N (mod 7) selects starter_7day_v1.days.day_N."
  }$$::jsonb,
  ARRAY[]::TEXT[],
  NULL,
  'in_season_active'
)
ON CONFLICT (block_template_id) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    block_type = EXCLUDED.block_type,
    duration_days = EXCLUDED.duration_days,
    content = EXCLUDED.content,
    source = EXCLUDED.source,
    domain = EXCLUDED.domain,
    goal_tags = EXCLUDED.goal_tags,
    duration_range_weeks = EXCLUDED.duration_range_weeks,
    compatible_phases = EXCLUDED.compatible_phases,
    tunable_parameters_schema = EXCLUDED.tunable_parameters_schema,
    week_scaffold_json = EXCLUDED.week_scaffold_json,
    research_doc_ids = EXCLUDED.research_doc_ids,
    modification_rules_json = EXCLUDED.modification_rules_json,
    implied_phase = EXCLUDED.implied_phase;
