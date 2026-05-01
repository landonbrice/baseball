-- Migration 015: bootstrap an active "Starter 7-day cadence" program for each
-- current 7-day starter. Idempotent via the partial unique index on
-- (pitcher_id, domain) WHERE status='active'. Generated schedule = 12 weeks
-- (84 days) of the cadence, day_index aligned to current days_since_outing.

DO $$
DECLARE
  rec RECORD;
  computed_start_date DATE;
  computed_day_index  INT;
  schedule JSONB;
  i INT;
  rotation_keys JSONB := '[
    {"day_offset": 0, "template_key": "day_0"},
    {"day_offset": 1, "template_key": "day_1"},
    {"day_offset": 2, "template_key": "day_2"},
    {"day_offset": 3, "template_key": "day_3"},
    {"day_offset": 4, "template_key": "day_4"},
    {"day_offset": 5, "template_key": "day_5"},
    {"day_offset": 6, "template_key": "day_6"}
  ]'::jsonb;
BEGIN
  FOR rec IN
    SELECT p.pitcher_id, COALESCE(ptm.days_since_outing, 0) AS dso
    FROM pitchers p
    LEFT JOIN pitcher_training_model ptm USING (pitcher_id)
    WHERE p.role ILIKE '%starter%'
  LOOP
    -- Skip if pitcher already has an active throwing program (idempotency)
    IF EXISTS (
      SELECT 1 FROM programs
      WHERE pitcher_id = rec.pitcher_id AND domain = 'throwing' AND status = 'active'
    ) THEN
      CONTINUE;
    END IF;

    computed_day_index := rec.dso;
    computed_start_date := CURRENT_DATE - (rec.dso || ' days')::interval;

    -- Build 84-day schedule
    schedule := '{"days": []}'::jsonb;
    FOR i IN 0..83 LOOP
      schedule := jsonb_set(
        schedule,
        '{days}',
        (schedule->'days') || jsonb_build_object(
          'day_index', i,
          'template_key', rotation_keys->(i % 7)->>'template_key',
          'date', (computed_start_date + (i || ' days')::interval)::date
        )
      );
    END LOOP;

    INSERT INTO programs (
      pitcher_id, parent_template_id, domain, tuned_spec_json,
      generated_schedule_json, start_date, nominal_end_date,
      current_day_index, held_days_count, status,
      created_by, created_by_role, activated_at
    ) VALUES (
      rec.pitcher_id,
      'tpl_starter_7day_cadence_v1',
      'throwing',
      '{"bootstrapped_from": "legacy_cadence"}'::jsonb,
      schedule,
      computed_start_date,
      (computed_start_date + INTERVAL '84 days')::date,
      computed_day_index,
      0,
      'active',
      'system_bootstrap',
      'coach',
      now()
    );
  END LOOP;
END $$;
