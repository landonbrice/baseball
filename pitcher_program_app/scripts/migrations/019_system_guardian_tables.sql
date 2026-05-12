-- System Guardian PR-1: create observation/incident/review tables with RLS lockdown.
--
-- Pre-state: none of these tables exist. This migration introduces them for the
-- first time, so the lockdown posture is established at creation rather than
-- bolted on after the fact (the path migrations 010 + 012 had to take).
--
-- What this migration creates:
--   1. public.system_observations - append-only normalized event stream feeding
--      the Guardian. Holds source/service/route/message/signature plus jsonb
--      metadata. 14-day retention enforced by the prune_old_observations()
--      function below (PR-2 will wire a 3am APScheduler job to call it).
--   2. public.system_incidents    - clustered open/ack/resolved incidents
--      keyed by signature (unique). Tracks first/last_seen, count, affected
--      services/surfaces, sample messages, suspected files, and debug packet.
--   3. public.guardian_reviews    - AI-written analysis attached to an
--      incident; separate so reviews can be regenerated without mutating the
--      incident row.
--   4. public.prune_old_observations() - deletes observations older than 14
--      days and returns the row count pruned.
--
-- RLS posture rationale: per the 010/012 precedent, every public table that
-- PostgREST exposes must revoke anon/authenticated grants, enable + force
-- RLS, and grant explicit service_role access. These tables will hold
-- pitcher_id references plus arm/injury context inside debug packets, so the
-- lockdown is mandatory (amendments doc, decision A3).
--
-- Search_path posture rationale: prune_old_observations() pins
-- search_path = public, pg_temp, matching migration 011's pattern. Without
-- this, advisor function_search_path_mutable would fire.

-- Tables share the existing update_updated_at_column() function from migration
-- 003. We reuse it rather than redefining.

-- 1. system_observations -------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_observations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    observed_at     timestamptz NOT NULL,
    source          text NOT NULL,
    service         text,
    event_type      text NOT NULL,
    severity_hint   text,
    surface         text,
    route_or_job    text,
    message         text NOT NULL,
    error_class     text,
    stack_hash      text,
    signature       text NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS system_observations_observed_at_idx
    ON public.system_observations (observed_at DESC);

CREATE INDEX IF NOT EXISTS system_observations_signature_idx
    ON public.system_observations (signature);

-- 2. system_incidents ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_incidents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signature           text NOT NULL,
    title               text NOT NULL,
    status              text NOT NULL DEFAULT 'open',
    severity            text NOT NULL,
    category            text NOT NULL,
    first_seen          timestamptz NOT NULL,
    last_seen           timestamptz NOT NULL,
    count               integer NOT NULL DEFAULT 1,
    affected_services   text[] NOT NULL DEFAULT '{}',
    affected_surfaces   text[] NOT NULL DEFAULT '{}',
    affected_entities   jsonb NOT NULL DEFAULT '{}'::jsonb,
    sample_messages     jsonb NOT NULL DEFAULT '[]'::jsonb,
    suspected_files     text[] NOT NULL DEFAULT '{}',
    debug_packet        jsonb NOT NULL DEFAULT '{}'::jsonb,
    vision_flags        jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_notified_at    timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS system_incidents_signature_key
    ON public.system_incidents (signature);

CREATE INDEX IF NOT EXISTS system_incidents_status_last_seen_idx
    ON public.system_incidents (status, last_seen DESC);

-- Reuse the existing trigger function from migration 003.
DROP TRIGGER IF EXISTS update_system_incidents_updated_at ON public.system_incidents;
CREATE TRIGGER update_system_incidents_updated_at
    BEFORE UPDATE ON public.system_incidents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 3. guardian_reviews ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.guardian_reviews (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         uuid REFERENCES public.system_incidents(id) ON DELETE CASCADE,
    review_type         text NOT NULL,
    model               text,
    input_fingerprint   text,
    summary             text NOT NULL,
    debug_packet        jsonb NOT NULL DEFAULT '{}'::jsonb,
    vision_flags        jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS guardian_reviews_incident_id_idx
    ON public.guardian_reviews (incident_id);

-- 4. prune_old_observations() --------------------------------------------------
-- Deletes system_observations rows older than 14 days, returns row count.
-- search_path pinned to match migration 011. Plain (no SECURITY DEFINER); the
-- 3am scheduled job that will call this (PR-2) runs as the service role, which
-- already has full access via the policy below.
CREATE OR REPLACE FUNCTION public.prune_old_observations()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM public.system_observations
    WHERE observed_at < now() - interval '14 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- 5. RLS lockdown --------------------------------------------------------------
-- Matches the 010/012 idiom: revoke anon+authenticated, enable + force RLS,
-- install explicit service_role policy. DO-block + array of table names so
-- adding a future Guardian table to this list stays a one-line change.

DO $$
DECLARE
    target_tables text[] := ARRAY[
        'system_observations',
        'system_incidents',
        'guardian_reviews'
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
