-- Lock down WHOOP tables. Pre-state: anon + authenticated had full CRUD on
-- whoop_tokens (incl. access_token / refresh_token), whoop_daily, whoop_pending_auth.
-- Server side uses the service_role key, so revoking anon/authenticated is safe.

-- 1. Revoke direct privileges from the API roles.
REVOKE ALL ON TABLE public.whoop_tokens       FROM anon, authenticated;
REVOKE ALL ON TABLE public.whoop_daily        FROM anon, authenticated;
REVOKE ALL ON TABLE public.whoop_pending_auth FROM anon, authenticated;

-- 2. Enable + force RLS as defense in depth (catches any future grant slip-ups).
ALTER TABLE public.whoop_tokens       ENABLE  ROW LEVEL SECURITY;
ALTER TABLE public.whoop_tokens       FORCE   ROW LEVEL SECURITY;
ALTER TABLE public.whoop_daily        ENABLE  ROW LEVEL SECURITY;
ALTER TABLE public.whoop_daily        FORCE   ROW LEVEL SECURITY;
ALTER TABLE public.whoop_pending_auth ENABLE  ROW LEVEL SECURITY;
ALTER TABLE public.whoop_pending_auth FORCE   ROW LEVEL SECURITY;

-- 3. Explicit service_role policy. (service_role bypasses RLS by default, but an
--    explicit policy makes the intent visible and survives any future
--    "service_role no longer bypasses" platform change.)
DROP POLICY IF EXISTS "service_role full access" ON public.whoop_tokens;
CREATE POLICY "service_role full access" ON public.whoop_tokens
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role full access" ON public.whoop_daily;
CREATE POLICY "service_role full access" ON public.whoop_daily
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role full access" ON public.whoop_pending_auth;
CREATE POLICY "service_role full access" ON public.whoop_pending_auth
    FOR ALL TO service_role USING (true) WITH CHECK (true);
