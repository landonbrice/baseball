-- 016_advance_program_counter_fn.sql
-- Atomic counter advance OR hold-event insert for active programs.
-- Consumed by db.write_daily_entry_with_counter_advance via Supabase RPC.
--
-- p_hold_event NULL -> advance counter by 1 day.
-- p_hold_event populated -> insert program_hold_events row + bump
--   held_days_count + push nominal_end_date by one day.
--
-- The two paths are mutually exclusive: either the program advanced today,
-- or it was held. UNIQUE (program_id, hold_date) on program_hold_events
-- prevents double-write on the same date.

CREATE OR REPLACE FUNCTION advance_program_counter(
    p_program_id UUID,
    p_hold_event JSONB,
    p_event_date DATE
) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_hold_event IS NULL THEN
        UPDATE programs
        SET current_day_index = current_day_index + 1
        WHERE program_id = p_program_id;
    ELSE
        INSERT INTO program_hold_events (
            program_id,
            hold_date,
            triage_result,
            reason_code
        ) VALUES (
            p_program_id,
            p_event_date,
            p_hold_event->'triage_result',
            p_hold_event->>'reason_code'
        );

        UPDATE programs
        SET held_days_count = held_days_count + 1,
            nominal_end_date = nominal_end_date + INTERVAL '1 day'
        WHERE program_id = p_program_id;
    END IF;
END;
$$;
