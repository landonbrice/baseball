-- Pin search_path on three functions flagged by advisor function_search_path_mutable.
-- A mutable search_path lets a privileged caller resolve unqualified names through a
-- schema they control (e.g. by injecting a malicious "pg_temp.update_updated_at_column").
-- Setting search_path explicitly on the function definition removes the resolution
-- ambiguity for every caller, regardless of session state.

ALTER FUNCTION public.update_updated_at_column()
    SET search_path = public, pg_temp;

ALTER FUNCTION public.update_updated_at()
    SET search_path = public, pg_temp;

ALTER FUNCTION public.set_daily_entry_team_id_from_pitcher()
    SET search_path = public, pg_temp;
