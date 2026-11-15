-- Plan_Travel migration 0022_f14 · version 3.0.0-alpha.15 · F14 (smart chat, stage 1: daily usage cap per trip)
-- CHANGE 2026-11-15 F14-DB-01: first version (no previous version). What changed from 0001–0021:
--   1 new table in schema `private`: chat_usage (trip_id, day, n) — RLS on, NO policies, no client grants.
--   2 new service-role-only functions in `public`, used by the Edge Function `chat-assistant` (alpha.15.0):
--     public.chat_take(p_user uuid, p_trip uuid, p_cap int)  returns jsonb
--         {"ok":true,"used":N,"cap":C}  |  {"error":"not_member"|"daily_cap"|"invalid_request", ...}
--         Atomic: the caller must be an ACTIVE member of p_trip (any role, viewers included — the chat writes nothing);
--         the trip's counter for today (UTC day) is incremented only while it is below p_cap. daily_cap also returns used + cap.
--     public.chat_refund(p_trip uuid)  returns jsonb   {"ok":true,"used":N}
--         Gives one question back (the upstream call failed); never below 0.
--   Rows older than 7 days are deleted inside chat_take (no cron).
--   No new policies, no new grants on existing tables; `public` still has exactly the 9 F01 tables.
--
-- Contract: claude/Plan_Travel_F14_spec.md C3. Idempotent: `create table if not exists` + `create or replace` + re-applied
-- grants; safe to run more than once. Requires 0012_f05.sql (schema `private`, private.f05_err).
-- Day boundary = UTC day (02:00–03:00 Israel time), D3. The cap value is passed by the function (secret CHAT_DAILY_CAP).

create table if not exists private.chat_usage (
  trip_id uuid    not null references public.trips (id) on delete cascade,
  day     date    not null,
  n       integer not null default 0,
  constraint chat_usage_pkey primary key (trip_id, day),
  constraint chat_usage_n_nonneg check (n >= 0)
);
alter table private.chat_usage enable row level security;
revoke all on private.chat_usage from public, anon, authenticated;

create or replace function public.chat_take(p_user uuid, p_trip uuid, p_cap int)
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

  delete from private.chat_usage u where u.day < v_day - 7;

  -- the first question of the day creates the row; every other one needs headroom (n < p_cap)
  insert into private.chat_usage as u (trip_id, day, n) values (p_trip, v_day, 1)
  on conflict (trip_id, day) do update set n = u.n + 1 where u.n < p_cap
  returning u.n into v_used;

  if v_used is null then   -- the conflict branch matched no row: the counter is at the cap
    select u.n into v_used from private.chat_usage u where u.trip_id = p_trip and u.day = v_day;
    return pg_catalog.jsonb_build_object('error', 'daily_cap', 'used', v_used, 'cap', p_cap);
  end if;
  return pg_catalog.jsonb_build_object('ok', true, 'used', v_used, 'cap', p_cap);
end;
$$;

create or replace function public.chat_refund(p_trip uuid)
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
  if p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  update private.chat_usage u set n = u.n - 1
   where u.trip_id = p_trip and u.day = v_day and u.n > 0
  returning u.n into v_used;
  return pg_catalog.jsonb_build_object('ok', true, 'used', coalesce(v_used, 0));
end;
$$;

revoke all on function public.chat_take(uuid, uuid, int) from public, anon, authenticated;
revoke all on function public.chat_refund(uuid)          from public, anon, authenticated;
grant execute on function public.chat_take(uuid, uuid, int) to service_role;
grant execute on function public.chat_refund(uuid)          to service_role;
