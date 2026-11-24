-- Lonely Planner · F13-TR (AI translation of trip content) · migration 0026 · version 3.0.0-alpha.19
-- CHANGE 2026-11-24 F13-TR-DB-01: new file (no previous version). Contract: claude/Plan_Travel_F13_translate_spec.md C4.
--   1 new table in schema `private`: tr_usage (trip_id, day, n) — RLS on, NO policies, no client grants.
--   2 service-role-only functions in `public`, used by the Edge Function `translate-content`:
--     public.tr_take(p_user uuid, p_trip uuid, p_cap int, p_dry boolean) returns jsonb
--         {"ok":true,"used":N,"cap":C} | {"error":"not_member"|"daily_cap"|"invalid_request", ...}
--         The caller must be an ACTIVE member of p_trip (any role). p_dry = true only checks membership + reports the counter;
--         p_dry = false also adds one run to today's (UTC) counter, only while it is below p_cap.
--     public.tr_refund(p_trip uuid) returns jsonb   {"ok":true,"used":N}   (never below 0)
--   Rows older than 7 days are deleted inside tr_take. No new policies, no new grants on existing tables.
-- Idempotent. Requires 0012_f05.sql (schema `private`, private.f05_err).

create table if not exists private.tr_usage (
  trip_id uuid    not null references public.trips (id) on delete cascade,
  day     date    not null,
  n       integer not null default 0,
  constraint tr_usage_pkey primary key (trip_id, day),
  constraint tr_usage_n_nonneg check (n >= 0)
);
alter table private.tr_usage enable row level security;
revoke all on private.tr_usage from public, anon, authenticated;

create or replace function public.tr_take(p_user uuid, p_trip uuid, p_cap int, p_dry boolean default false)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_day  date := (pg_catalog.now() at time zone 'UTC')::date;
  v_used int;
begin
  if p_user is null or p_trip is null or p_cap is null or p_cap < 1 then
    return private.f05_err('invalid_request');
  end if;
  if not exists (select 1 from public.trip_members m
                  where m.trip_id = p_trip and m.user_id = p_user and m.status = 'active') then
    return private.f05_err('not_member');
  end if;

  delete from private.tr_usage u where u.day < v_day - 7;

  if p_dry then
    select coalesce(max(u.n), 0) into v_used from private.tr_usage u where u.trip_id = p_trip and u.day = v_day;
    if v_used >= p_cap then
      return pg_catalog.jsonb_build_object('error', 'daily_cap', 'used', v_used, 'cap', p_cap);
    end if;
    return pg_catalog.jsonb_build_object('ok', true, 'used', v_used, 'cap', p_cap);
  end if;

  insert into private.tr_usage as u (trip_id, day, n) values (p_trip, v_day, 1)
  on conflict (trip_id, day) do update set n = u.n + 1 where u.n < p_cap
  returning u.n into v_used;

  if v_used is null then
    select u.n into v_used from private.tr_usage u where u.trip_id = p_trip and u.day = v_day;
    return pg_catalog.jsonb_build_object('error', 'daily_cap', 'used', v_used, 'cap', p_cap);
  end if;
  return pg_catalog.jsonb_build_object('ok', true, 'used', v_used, 'cap', p_cap);
end;
$$;

create or replace function public.tr_refund(p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_day  date := (pg_catalog.now() at time zone 'UTC')::date;
  v_used int;
begin
  update private.tr_usage u set n = greatest(u.n - 1, 0) where u.trip_id = p_trip and u.day = v_day returning u.n into v_used;
  return pg_catalog.jsonb_build_object('ok', true, 'used', coalesce(v_used, 0));
end;
$$;

revoke all on function public.tr_take(uuid, uuid, int, boolean) from public, anon, authenticated;
revoke all on function public.tr_refund(uuid)                   from public, anon, authenticated;
grant execute on function public.tr_take(uuid, uuid, int, boolean) to service_role;
grant execute on function public.tr_refund(uuid)                   to service_role;
