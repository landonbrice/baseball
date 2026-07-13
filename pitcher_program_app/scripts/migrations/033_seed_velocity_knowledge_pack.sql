-- Migration 033 — Program Engine v1 / Task 1.2
-- Seed the velocity knowledge pack into block_library.velocity_12wk_v1.
--
-- Idempotent: pure UPDATE keyed by block_template_id PK. Safe to re-run.
--
-- Enrichments:
--   1. content — adds phase_gates + acwr_governor + lifting_integration sections.
--   2. tunable_parameters_schema — operator-visible knobs (Task 1.2 §7 of the
--      velocity_progression_model doc).
--   3. modification_rules_json — flag deltas (GREEN/YELLOW/RED/CRITICAL_RED).
--   4. research_doc_ids — the 9 cited docs the Program Engine surfaces in the
--      "why this program" panel.
--
-- The existing `content.phases` array (4-phase arc with effort_pct + distances
-- + total_throws_range) is PRESERVED; the migration uses `content || ...` so
-- existing keys are not clobbered.

UPDATE block_library
SET
  content = content || jsonb_build_object(
    'engine_version', 'v1',
    'phase_gates', jsonb_build_object(
      'mound_introduction', jsonb_build_object(
        'min_week', 6,
        'default_week', 7,
        'criteria', jsonb_build_array(
          'acwr_rolling in [0.8, 1.3] for 7 consecutive days',
          'no active YELLOW or RED triage flag',
          'no active FPM modification (FPM.md gate cleared)',
          'bullpen volume reached 30+ throws at 85-90% intent'
        )
      ),
      'pulldowns_introduction', jsonb_build_object(
        'min_week', 6,
        'default_week', 7,
        'criteria', jsonb_build_array(
          'co-introduce with mound by default',
          '105ft long-toss sustained at 70%+ for 3 consecutive sessions'
        )
      ),
      'live_abs', jsonb_build_object(
        'probable_week', 7,
        'clearance_week', 8
      )
    ),
    'acwr_governor', jsonb_build_object(
      'band_lower', 0.8,
      'band_upper', 1.3,
      'hard_cap', 1.5,
      'acute_window_days', 7,
      'chronic_window_days', 28,
      'deload_drop_pct', 0.15,
      'deload_weeks_default', jsonb_build_array(4, 7),
      'weekly_g_reference_curve', jsonb_build_array(
        6960, 9194, 10935, 10375, 12049, 13516,
        12090, 12960, 13620, 14000, 14300, 14616
      ),
      'verified_daily_anchor', jsonb_build_object(
        'distance_ft', 45,
        'throw_count', 40,
        'intent_pct', 50,
        'expected_G', 2145,
        'tolerance_pct', 5
      )
    ),
    'invariant_warmup_ladder', jsonb_build_array(
      jsonb_build_object('distance_ft', 45, 'intent_pct', 50, 'note', 'high/pec load 10@30ft, snap-snap rocker x5, self-toss x5'),
      jsonb_build_object('distance_ft', 60, 'intent_pct', 60, 'note', null),
      jsonb_build_object('distance_ft', 75, 'intent_pct', 70, 'note', null)
    ),
    'day_type_taxonomy', jsonb_build_array(
      jsonb_build_object('day_type', 'recovery',       'intent_pct_band', jsonb_build_array(50, 60)),
      jsonb_build_object('day_type', 'hybrid_b',       'intent_pct_band', jsonb_build_array(60, 70)),
      jsonb_build_object('day_type', 'hybrid_a',       'intent_pct_band', jsonb_build_array(80, 90)),
      jsonb_build_object('day_type', 'velo',           'intent_pct_band', jsonb_build_array(100, 100)),
      jsonb_build_object('day_type', 'plyo_velo',      'intent_pct_band', jsonb_build_array(100, 100)),
      jsonb_build_object('day_type', 'wb_mound_velo',  'intent_pct_band', jsonb_build_array(100, 100)),
      jsonb_build_object('day_type', 'mound_velo',     'intent_pct_band', jsonb_build_array(100, 100)),
      jsonb_build_object('day_type', 'short_box',      'intent_pct_band', jsonb_build_array(60, 80)),
      jsonb_build_object('day_type', 'game_day',       'intent_pct_band', null),
      jsonb_build_object('day_type', 'no_throw',       'intent_pct_band', null)
    ),
    'lifting_integration', jsonb_build_object(
      'mode_default', 'unified',
      'phase_mapping', jsonb_build_array(
        jsonb_build_object('throwing_phase_weeks', jsonb_build_array(1,2,3), 'lifting_phase', 'hypertrophy', 'rest_s', 30,  'intensity_pct_1rm_band', jsonb_build_array(50, 75)),
        jsonb_build_object('throwing_phase_weeks', jsonb_build_array(4,5,6), 'lifting_phase', 'hypertrophy_to_strength', 'rest_s', 60, 'intensity_pct_1rm_band', jsonb_build_array(60, 85)),
        jsonb_build_object('throwing_phase_weeks', jsonb_build_array(7,8,9), 'lifting_phase', 'strength', 'rest_s', 120, 'intensity_pct_1rm_band', jsonb_build_array(80, 90)),
        jsonb_build_object('throwing_phase_weeks', jsonb_build_array(10,11,12), 'lifting_phase', 'strength_power', 'rest_s', 240, 'intensity_pct_1rm_band', jsonb_build_array(87, 95))
      ),
      'day_split', jsonb_build_array('posterior_chain', 'push_pull'),
      'sessions_per_week', 2,
      'pull_push_ratio_min', 2.0,
      'fpm_min_days_per_week', 4
    ),
    'bullpen_progression_throws', jsonb_build_array(15, 20, 25, 30, 40, 45, 50),
    'bullpen_progression_starts_at_week', 5
  ),
  tunable_parameters_schema = jsonb_build_object(
    'target_velocity_gain_mph', jsonb_build_object(
      'type', 'int', 'default', 3, 'min', 1, 'max', 5,
      'description', 'Realistic 12-week target in MPH. 5+ requires extension to 16-week.'
    ),
    'deload_preference', jsonb_build_object(
      'type', 'enum', 'default', 'every_4th_week',
      'choices', jsonb_build_array('every_4th_week', 'acwr_driven'),
      'description', 'Pattern (3-up-1-down) vs ACWR-driven. The golden does both.'
    ),
    'mound_introduction_week', jsonb_build_object(
      'type', 'int', 'default', 7, 'min', 6, 'max', 10,
      'description', 'Earlier requires cleared phase_gates.mound_introduction.criteria.'
    ),
    'pulldowns_introduction_week', jsonb_build_object(
      'type', 'int', 'default', 7, 'min', 6, 'max', 10,
      'description', 'Defaults to mound_introduction_week.'
    ),
    'lifting_domain', jsonb_build_object(
      'type', 'enum', 'default', 'unified',
      'choices', jsonb_build_array('unified', 'throwing_only'),
      'description', 'unified runs lifting in parallel on the same calendar.'
    ),
    'bullpen_volume_max', jsonb_build_object(
      'type', 'int', 'default', 50, 'min', 30, 'max', 75,
      'description', 'Wk9 peak throw count for the bullpen.'
    ),
    'weekly_throws_band', jsonb_build_object(
      'type', 'int_array', 'default', jsonb_build_array(3, 4),
      'description', 'Throwing sessions per week — [min, max].'
    )
  ),
  modification_rules_json = jsonb_build_object(
    'flag_deltas', jsonb_build_object(
      'GREEN', jsonb_build_object(
        'throwing', 'run_prescribed',
        'lifting',  'run_prescribed',
        'counter',  'advance'
      ),
      'YELLOW', jsonb_build_object(
        'throwing', 'drop_one_intent_tier',
        'tier_order', jsonb_build_array('velo', 'hybrid_a', 'hybrid_b', 'recovery'),
        'lifting', 'drop_one_accessory_keep_compounds',
        'counter', 'advance',
        'trigger_when_any_of', jsonb_build_object(
          'arm_feel_max', 6,
          'arm_feel_min', 5,
          'acwr_min', 1.3,
          'acwr_max', 1.5,
          'tissue_score_max', 4
        )
      ),
      'RED', jsonb_build_object(
        'throwing', 'recovery_only',
        'forbidden_day_types', jsonb_build_array('hybrid_a', 'velo', 'plyo_velo', 'wb_mound_velo', 'mound_velo'),
        'lifting', 'light_session',
        'lifting_template', jsonb_build_object(
          'compounds', 1, 'accessories', 2, 'core', 1, 'explosive', 0
        ),
        'counter', 'pause_with_hold_event',
        'trigger_when_any_of', jsonb_build_object(
          'arm_feel_max', 4,
          'active_mod_flag', true
        )
      ),
      'CRITICAL_RED', jsonb_build_object(
        'throwing', 'shutdown',
        'lifting', 'mobility_only',
        'counter', 'pause_with_hold_event',
        'trigger_when_any_of', jsonb_build_object(
          'arm_feel_max', 2
        )
      )
    ),
    'banked_vs_planned_drift_threshold', jsonb_build_object(
      'ratio_floor', 0.75,
      'rolling_window_days', 14,
      'on_breach', 'emit_program_drift_insight'
    ),
    'fpm_gate', jsonb_build_object(
      'when_active', 'pause_throwing_progression_switch_to_FPM_isometrics',
      'cleared_by', 'thinker_test_pain_free + 30_reps_x2_consecutive_pain_free_days',
      'reference_doc', 'FPM'
    )
  ),
  research_doc_ids = ARRAY[
    'velocity_progression_model',
    'driveline_throwing_program',
    'driveline_lifting_programs',
    'final_research_base',
    'advanced_workload_performance',
    'fpm_strain_protocol',
    'ucl_flexor_pronator_protection',
    'gemini_researching_lifting',
    'research_gap_analysis'
  ]
WHERE block_template_id = 'velocity_12wk_v1';

-- Verification: confirm the row updated (RAISE if not)
DO $$
DECLARE
  cnt int;
  has_gates boolean;
BEGIN
  SELECT COUNT(*) INTO cnt FROM block_library WHERE block_template_id = 'velocity_12wk_v1';
  IF cnt = 0 THEN
    RAISE EXCEPTION 'block_library.velocity_12wk_v1 row missing; cannot seed velocity knowledge pack';
  END IF;
  SELECT (content ? 'phase_gates' AND content ? 'acwr_governor' AND content ? 'lifting_integration')
    INTO has_gates FROM block_library WHERE block_template_id = 'velocity_12wk_v1';
  IF NOT has_gates THEN
    RAISE EXCEPTION 'velocity_12wk_v1 update did not write phase_gates/acwr_governor/lifting_integration';
  END IF;
END $$;
