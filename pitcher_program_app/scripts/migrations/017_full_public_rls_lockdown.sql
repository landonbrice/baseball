-- Generalize the lockdown pattern (010, 012) to every remaining public table
-- that PostgREST exposes with anon/authenticated CRUD or with permissive
-- USING(true) policies bound to PUBLIC.
--
-- Pre-state verified 2026-05-08:
--
--   Group A — RLS disabled, full anon+authenticated CRUD, NO policies:
--     programs, favorited_blocks, program_builder_sessions,
--     program_hold_events, program_schedule_revisions,
--     program_generation_failures, coach_visible_override_events
--   These tables landed in the May 1 "programs core" migration series and
--   never adopted the lockdown pattern.
--
--   Group B — RLS enabled but NOT forced, anon+authenticated grants retained,
--   only policy is "Service role full access" / "Allow all for service role"
--   bound to PUBLIC with USING(true) WITH CHECK(true). Anon CAN reach these
--   through the policy. (CLAUDE.md framed this group as low-risk; reading
--   the policy roles list shows otherwise.)
--     chat_messages, daily_entries, exercises, injury_history,
--     mobility_videos, mobility_weekly_rotation, pitcher_training_model,
--     pitchers, saved_plans, templates, weekly_summaries
--
-- Backend reaches Supabase only through service_role; coach-app's
-- supabase-js usage is auth-schema-only (verified in useCoachAuth.jsx).
-- Mini-app does not use supabase-js. Lockdown is application-safe.

DO $$
DECLARE
    target_tables text[] := ARRAY[
        -- Group A (no RLS)
        'programs', 'favorited_blocks', 'program_builder_sessions',
        'program_hold_events', 'program_schedule_revisions',
        'program_generation_failures', 'coach_visible_override_events',
        -- Group B (permissive policy, retained grants)
        'chat_messages', 'daily_entries', 'exercises', 'injury_history',
        'mobility_videos', 'mobility_weekly_rotation',
        'pitcher_training_model', 'pitchers', 'saved_plans',
        'templates', 'weekly_summaries'
    ];
    bad_policy_names text[] := ARRAY[
        'Service role full access',
        'service_role full access',
        'Allow all for service role'
    ];
    t text;
    pol text;
BEGIN
    FOREACH t IN ARRAY target_tables LOOP
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t);

        FOREACH pol IN ARRAY bad_policy_names LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', pol, t);
        END LOOP;

        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE public.%I FORCE  ROW LEVEL SECURITY', t);

        EXECUTE format(
            'CREATE POLICY "service_role full access" ON public.%I '
            || 'FOR ALL TO service_role USING (true) WITH CHECK (true)',
            t
        );
    END LOOP;
END $$;
