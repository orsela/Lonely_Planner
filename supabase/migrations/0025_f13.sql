-- Lonely Planner · F13 stage 2 · a new trip may be created in English · version 3.0.0-alpha.18.8
-- CHANGE 2026-11-24 F13-DB-01: new file (no previous version). create_trip_from_invite (0010_f04.sql:176) accepted default_lang = 'he' only; it now accepts 'he' or 'en'
-- (decision F13-D3, claude/Plan_Travel_F13_decisions.md). Nothing else changes: the table check trips_default_lang already allows any 'xx' code. The function body is read from the live
-- definition and only this one condition is replaced, so ownership, grants and every other line stay exactly as deployed. Safe to run twice.
do $f13$
declare
  d text := pg_get_functiondef('public.create_trip_from_invite(uuid,text,jsonb)'::regprocedure);
begin
  if position($x$v_lang not in ('he', 'en')$x$ in d) > 0 then
    return;                                    -- already applied
  end if;
  if position($x$v_lang <> 'he'$x$ in d) = 0 then
    raise exception 'F13 stage 2: the default_lang condition was not found in create_trip_from_invite';
  end if;
  execute replace(d, $x$v_lang <> 'he'$x$, $x$v_lang not in ('he', 'en')$x$);
end
$f13$;
