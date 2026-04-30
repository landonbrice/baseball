-- Generalize the WHOOP-table lockdown (migration 010) to every remaining
-- public table that PostgREST exposes. Pre-state: all 13 tables grant full
-- CRUD to anon + authenticated AND have RLS disabled, meaning the project
-- anon key can read, insert, update, delete, and truncate any of them.
-- Server side reaches Supabase only through the service_role key, so this
-- revoke-and-force-RLS pass has no production impact.
--
-- Tables included:
--   Live coach-dashboard tables:
--     teams, coaches, team_games, block_library, coach_actions,
--     team_assigned_blocks, coach_suggestions, training_phase_blocks
--   Observability:
--     research_load_log, ui_fallback_log
--   Orphan / superseded (kept locked down until the drop decision lands):
--     schedule, training_programs, program_templates

DO $$
DECLARE
    target_tables text[] := ARRAY[
        'teams','coaches','team_games','block_library','coach_actions',
        'team_assigned_blocks','coach_suggestions','training_phase_blocks',
        'research_load_log','ui_fallback_log',
        'schedule','training_programs','program_templates'
    ];
    t text;
BEGIN
    FOREACH t IN ARRAY target_tables LOOP
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t);
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',  t);
        EXECUTE format(
            'DROP POLICY IF EXISTS "service_role full access" ON public.%I', t
        );
        EXECUTE format(
            'CREATE POLICY "service_role full access" ON public.%I '
            || 'FOR ALL TO service_role USING (true) WITH CHECK (true)',
            t
        );
    END LOOP;
END $$;
