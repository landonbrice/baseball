-- Pin search_path on advance_program_counter (added in the May 1 programs-core
-- migration series, missed by 011). Same rationale as 011: a mutable
-- search_path lets a privileged caller resolve unqualified names through a
-- schema they control.

ALTER FUNCTION public.advance_program_counter(uuid, jsonb, date)
    SET search_path = public, pg_temp;
