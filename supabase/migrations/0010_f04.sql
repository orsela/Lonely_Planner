-- Plan_Travel migration 0010_f04 · version 3.0.0-alpha.4 · F04 (an invited manager sets up a trip in three steps)
-- CHANGE 2026-10-12 F04-DB-01: two new service-role-only functions used by the Edge Function `create-trip`:
--   public.create_trip_from_invite(p_user uuid, p_email text, p_payload jsonb) returns jsonb
--   public.find_invite_for_email(p_email text) returns jsonb
--   What changed from 0001–0009: 2 new functions only. No new tables, columns, indexes, policies or triggers, and no
--   new client grants (both functions: execute revoked from public/anon/authenticated, granted to service_role only).
--   create_trip_from_invite writes trips / trip_countries / trip_currencies / trip_members / trip_join_codes / trip_kv
--   (keys 'trip' and, since F04-DB-02, 'tripname') and marks the manager_invites row used, all in the caller's single transaction; the existing F01 triggers
--   (currency cap 10, base-currency lock, last manager, trip_kv updated_by) stay in force.
--
-- Contract: docs/F04_spec.md §2 (decisions D3, D4, D7). Idempotent: `create or replace` + re-applied grants; safe to
-- run more than once. Requires pgcrypto in the `extensions` schema (always present on Supabase) for
-- extensions.gen_random_bytes (join code).
--
-- Errors (SQLSTATE P0001, message exactly):
--   invite_invalid       — no open invite for the email, or it is used (by another trip/user), revoked or expired
--   invalid_payload      — DETAIL names the field: name | display_name | start_date | end_date | home_currency |
--                          default_lang | default_role | countries | currencies | center   (end_date also covers
--                          end < start and a range outside 1–120 days; `payload` when p_payload is not an object)
--   too_many_currencies  — 3 base currencies + payload currencies > 10

-- ===========================================================================
-- 1. find_invite_for_email — the active (unused, unrevoked, unexpired) invite for an email, newest first
-- ===========================================================================
create or replace function public.find_invite_for_email(p_email text)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_email text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_email, '')));
  r record;
begin
  if v_email = '' then
    return pg_catalog.jsonb_build_object('found', false);
  end if;
  select i.id, i.draft_name, i.inviter_name, i.expires_at
    into r
    from public.manager_invites i
   where i.email = v_email
     and i.used_at is null
     and i.revoked_at is null
     and i.expires_at > pg_catalog.now()
   order by i.created_at desc
   limit 1;
  if not found then
    return pg_catalog.jsonb_build_object('found', false);
  end if;
  return pg_catalog.jsonb_build_object(
    'found', true,
    'invite_id', r.id,
    'draft_name', r.draft_name,
    'inviter_name', r.inviter_name,
    'expires_at', r.expires_at);
end;
$$;

revoke all     on function public.find_invite_for_email(text) from public, anon, authenticated;
grant  execute on function public.find_invite_for_email(text) to service_role;

-- ===========================================================================
-- 2. create_trip_from_invite — atomic and idempotent trip creation (spec §2 steps 1–7)
-- ===========================================================================
create or replace function public.create_trip_from_invite(p_user uuid, p_email text, p_payload jsonb)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  c_alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';   -- 32 chars: byte % 32 is unbiased
  c_bases    constant text[] := array['ILS', 'USD', 'EUR'];
  v_email    text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_email, '')));
  inv        record;
  v_code     text;
  v_trip     uuid;
  v_name     text;
  v_display  text;
  v_start    date;
  v_end      date;
  v_days     int;
  v_home     text;
  v_lang     text;
  v_role     text;
  v_countries jsonb;
  v_currs    jsonb;
  v_lat      numeric;
  v_lng      numeric;
  v_first    text;
  v_el       jsonb;
  v_seen     text[] := array[]::text[];
  v_bytes    bytea;
  v_try      int;
  v_i        int;
  v_sort     int;
begin
  -- 1. the invite row, locked (serializes concurrent creates / retries for the same invite)
  if p_user is null or v_email = '' then
    raise exception 'invite_invalid' using errcode = 'P0001';
  end if;
  select i.id, i.used_at, i.trip_id, i.expires_at
    into inv
    from public.manager_invites i
   where i.email = v_email
     and i.revoked_at is null
   order by i.created_at desc
   limit 1
     for update;
  if not found then
    raise exception 'invite_invalid' using errcode = 'P0001';
  end if;

  -- 2. idempotency: already used for a trip this user manages → same answer as the first create
  if inv.used_at is not null and inv.trip_id is not null then
    if exists (select 1 from public.trip_members m
                where m.trip_id = inv.trip_id and m.user_id = p_user and m.role = 'manager' and m.status = 'active') then
      select c.code into v_code from public.trip_join_codes c where c.trip_id = inv.trip_id;
      return pg_catalog.jsonb_build_object('trip_id', inv.trip_id, 'join_code', v_code, 'created', false);
    end if;
  end if;

  -- 3. otherwise the invite must still be open
  if inv.used_at is not null or inv.expires_at <= pg_catalog.now() then
    raise exception 'invite_invalid' using errcode = 'P0001';
  end if;

  -- 4. payload validation (field named in DETAIL)
  if p_payload is null or pg_catalog.jsonb_typeof(p_payload) <> 'object' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'payload';
  end if;

  if pg_catalog.jsonb_typeof(p_payload -> 'name') is distinct from 'string' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'name';
  end if;
  v_name := pg_catalog.btrim(p_payload ->> 'name');
  if pg_catalog.char_length(v_name) not between 1 and 80 then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'name';
  end if;

  if pg_catalog.jsonb_typeof(p_payload -> 'display_name') is distinct from 'string' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'display_name';
  end if;
  v_display := pg_catalog.btrim(p_payload ->> 'display_name');
  if pg_catalog.char_length(v_display) not between 1 and 40 then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'display_name';
  end if;

  begin
    if coalesce(p_payload ->> 'start_date', '') !~ '^\d{4}-\d{2}-\d{2}$' then raise exception 'x'; end if;
    v_start := (p_payload ->> 'start_date')::date;
    if pg_catalog.to_char(v_start, 'YYYY-MM-DD') <> p_payload ->> 'start_date' then raise exception 'x'; end if;
  exception when others then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'start_date';
  end;
  begin
    if coalesce(p_payload ->> 'end_date', '') !~ '^\d{4}-\d{2}-\d{2}$' then raise exception 'x'; end if;
    v_end := (p_payload ->> 'end_date')::date;
    if pg_catalog.to_char(v_end, 'YYYY-MM-DD') <> p_payload ->> 'end_date' then raise exception 'x'; end if;
  exception when others then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'end_date';
  end;
  v_days := (v_end - v_start) + 1;
  if v_end < v_start or v_days not between 1 and 120 then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'end_date';
  end if;

  v_home := p_payload ->> 'home_currency';
  if pg_catalog.jsonb_typeof(p_payload -> 'home_currency') is distinct from 'string' or not (v_home = any (c_bases)) then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'home_currency';
  end if;

  v_lang := p_payload ->> 'default_lang';
  if pg_catalog.jsonb_typeof(p_payload -> 'default_lang') is distinct from 'string' or v_lang <> 'he' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'default_lang';
  end if;

  v_role := p_payload ->> 'default_role';
  if pg_catalog.jsonb_typeof(p_payload -> 'default_role') is distinct from 'string' or v_role not in ('editor', 'viewer') then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'default_role';
  end if;

  v_countries := p_payload -> 'countries';
  if pg_catalog.jsonb_typeof(v_countries) is distinct from 'array'
     or pg_catalog.jsonb_array_length(v_countries) not between 1 and 15 then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'countries';
  end if;
  for v_el in select e from pg_catalog.jsonb_array_elements(v_countries) as t(e) loop
    if pg_catalog.jsonb_typeof(v_el) <> 'string' or (v_el #>> '{}') !~ '^[A-Z]{2}$' or (v_el #>> '{}') = any (v_seen) then
      raise exception 'invalid_payload' using errcode = 'P0001', detail = 'countries';
    end if;
    v_seen := v_seen || (v_el #>> '{}');
  end loop;
  v_first := v_countries ->> 0;

  v_currs := p_payload -> 'currencies';
  if v_currs is null or pg_catalog.jsonb_typeof(v_currs) = 'null' then
    v_currs := '[]'::jsonb;
  end if;
  if pg_catalog.jsonb_typeof(v_currs) <> 'array' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'currencies';
  end if;
  v_seen := array[]::text[];
  for v_el in select e from pg_catalog.jsonb_array_elements(v_currs) as t(e) loop
    if pg_catalog.jsonb_typeof(v_el) <> 'object'
       or pg_catalog.jsonb_typeof(v_el -> 'code') is distinct from 'string'
       or (v_el ->> 'code') !~ '^[A-Z]{3}$'
       or (v_el ->> 'code') = any (c_bases)
       or (v_el ->> 'code') = any (v_seen)
       or coalesce(v_el ->> 'kind', '') not in ('destination', 'added') then
      raise exception 'invalid_payload' using errcode = 'P0001', detail = 'currencies';
    end if;
    v_seen := v_seen || (v_el ->> 'code');
  end loop;
  if 3 + pg_catalog.jsonb_array_length(v_currs) > 10 then
    raise exception 'too_many_currencies' using errcode = 'P0001';
  end if;

  if pg_catalog.jsonb_typeof(p_payload -> 'center') is distinct from 'object'
     or pg_catalog.jsonb_typeof(p_payload #> '{center,lat}') is distinct from 'number'
     or pg_catalog.jsonb_typeof(p_payload #> '{center,lng}') is distinct from 'number' then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'center';
  end if;
  v_lat := (p_payload #>> '{center,lat}')::numeric;
  v_lng := (p_payload #>> '{center,lng}')::numeric;
  if v_lat not between -90 and 90 or v_lng not between -180 and 180 then
    raise exception 'invalid_payload' using errcode = 'P0001', detail = 'center';
  end if;

  -- 5. writes
  insert into public.trips (name, start_date, end_date, home_currency, default_lang, default_role, status, created_by)
  values (v_name, v_start, v_end, v_home, v_lang, v_role, 'active', p_user)
  returning id into v_trip;

  insert into public.trip_countries (trip_id, country_code, sort)
  select v_trip, t.e #>> '{}', (t.ord - 1)::int
    from pg_catalog.jsonb_array_elements(v_countries) with ordinality as t(e, ord);

  -- bases: home sort 0, the other two sort 1–2 (fixed order ILS, USD, EUR minus home); then payload currencies 3…
  insert into public.trip_currencies (trip_id, currency_code, kind, sort) values (v_trip, v_home, 'base', 0);
  v_sort := 1;
  foreach v_code in array c_bases loop
    if v_code <> v_home then
      insert into public.trip_currencies (trip_id, currency_code, kind, sort) values (v_trip, v_code, 'base', v_sort);
      v_sort := v_sort + 1;
    end if;
  end loop;
  insert into public.trip_currencies (trip_id, currency_code, kind, sort)
  select v_trip, t.e ->> 'code', t.e ->> 'kind', (t.ord + 2)::int
    from pg_catalog.jsonb_array_elements(v_currs) with ordinality as t(e, ord);

  insert into public.trip_members (trip_id, user_id, display_name, role, status, approved_at)
  values (v_trip, p_user, v_display, 'manager', 'active', pg_catalog.now());

  -- join code: 8 chars from the 32-char alphabet; retry on a (very unlikely) unique violation, max 5 attempts
  v_code := null;
  for v_try in 1..5 loop
    v_bytes := extensions.gen_random_bytes(8);
    v_code := '';
    for v_i in 0..7 loop
      v_code := v_code || pg_catalog.substr(c_alphabet, (pg_catalog.get_byte(v_bytes, v_i) % 32) + 1, 1);
    end loop;
    begin
      insert into public.trip_join_codes (trip_id, code) values (v_trip, v_code);
      exit;
    exception when unique_violation then
      v_code := null;
    end;
  end loop;
  if v_code is null then
    raise exception 'join_code_exhausted' using errcode = 'P0001';
  end if;

  -- one empty day per date (D4); value is the JSON text the app stores under planner:trip
  insert into public.trip_kv (trip_id, key, value, updated_by)
  select v_trip, 'trip',
         pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object(
             'day', g.ord,
             'date', pg_catalog.to_char(g.d, 'DD/MM/YYYY'),
             'region', '', 'title', '', 'activities', '', 'hotel', '',
             'cost', 0, 'notes', '',
             'lat', v_lat, 'lng', v_lng, 'zoom', 5,
             'waypoints', '[]'::jsonb,
             'country', v_first)
           order by g.ord)::text,
         p_user
    from pg_catalog.generate_series(v_start::timestamp, v_end::timestamp, interval '1 day') with ordinality as g(d, ord);

  -- CHANGE 2026-10-12 F04-DB-02: also write trip_kv key 'tripname' (plain text = the trip name), the key the app's
  --   existing getTripName() reads (planner:tripname). Before: not written, so the v1 home header and ניהול → הגדרות מסע
  --   showed the fallback "מסע של חלומות" for a new trip (dev notes §6.5; Or 2026-10-12: fix in F04).
  insert into public.trip_kv (trip_id, key, value, updated_by)
  values (v_trip, 'tripname', v_name, p_user);

  -- 6. consume the invite
  update public.manager_invites set used_at = pg_catalog.now(), trip_id = v_trip where id = inv.id;

  -- 7.
  return pg_catalog.jsonb_build_object('trip_id', v_trip, 'join_code', v_code, 'created', true);
end;
$$;

revoke all     on function public.create_trip_from_invite(uuid, text, jsonb) from public, anon, authenticated;
grant  execute on function public.create_trip_from_invite(uuid, text, jsonb) to service_role;
