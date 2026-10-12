-- Plan_Travel QA · F04 DB-level test harness · version 3.0.0-alpha.4 · F04
-- CHANGE 2026-10-12 F04-QA-02: rows 20, 31, 102 expect the new trip_kv key 'tripname' (0010 F04-DB-02).
-- CHANGE 2026-10-12 F04-QA-01: first version (no previous version). Installs qa.f04_run() in the locked `qa` schema,
--   same pattern as F01–F03 (0002–0004, 0007, 0009): helpers impersonate a user via request.jwt.claims + SET LOCAL ROLE,
--   all test data is created inside a sub-transaction that is always rolled back (raise 'f04_rollback'),
--   search_path pinned to '', nothing granted to public/anon/authenticated. SECURITY INVOKER (run as postgres, the owner
--   of public.create_trip_from_invite / public.find_invite_for_email), because PostgreSQL forbids SET ROLE inside a
--   SECURITY DEFINER function.
--
-- Run (after 0010_f04.sql):   select * from qa.f04_run() order by id;
-- Output: one row per scenario (id, name, pass, detail) — detail = 'expected: … | actual: …'.
--
-- Criteria covered (docs/F04_spec.md §5, §7 "DB"): 5 (refusals: expired, revoked, used by another user, replaced, no
-- invite — nothing written), 10 (idempotent retry → same trip, created=false), 11 (rows in trips / trip_countries /
-- trip_currencies / trip_members / trip_join_codes / trip_kv, the empty-day objects, invite marked used), 17 (non-member
-- reads 0 rows; editor/viewer cannot read trip_join_codes, the manager can; neither function executable by anon or
-- authenticated), payload validation (one invalid_payload per field, too_many_currencies, exactly 10 accepted), day
-- generation across a month boundary and a leap day (2028-02-28 → 2028-03-01 = 3 days), join-code alphabet, and §2
-- catalog checks (security definer, search_path='', volatility, grants).
--
-- Interpretation of "replaced" (criterion 5): invites are resolved by the verified email (D3), newest non-revoked row
-- first. A replaced invite is the older row of an email that got a new invite (the older one revoked by the resend /
-- re-invite flow). Scenarios: the replacement is open → create uses the NEW row and leaves the old one untouched; the
-- replacement itself has expired → invite_invalid and nothing is written.

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

-- Impersonate: p_role in ('authenticated','anon','postgres'); p_uid null = no "sub" claim (anon key without a session).
create or replace function qa.f04_as(p_uid uuid, p_role text)
returns void language plpgsql set search_path = '' as $f$
begin
  execute 'reset role';
  if p_role = 'postgres' then
    perform pg_catalog.set_config('request.jwt.claims', '', true);
    perform pg_catalog.set_config('request.jwt.claim.sub', '', true);
    perform pg_catalog.set_config('request.jwt.claim.role', '', true);
    return;
  end if;
  perform pg_catalog.set_config('request.jwt.claims',
    case when p_uid is null then pg_catalog.json_build_object('role', p_role)::text
         else pg_catalog.json_build_object('sub', p_uid, 'role', p_role)::text end, true);
  perform pg_catalog.set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
  perform pg_catalog.set_config('request.jwt.claim.role', p_role, true);
  execute pg_catalog.format('set local role %I', p_role);
end $f$;

-- Count rows returned by p_sql while impersonating.
create or replace function qa.f04_count(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f04_as(p_uid, p_role);
  execute 'select count(*) from (' || p_sql || ') f04_s' into n;
  execute 'reset role';
  return n || ' rows';
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Evaluate a scalar expression while impersonating; report it as text.
create or replace function qa.f04_val(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare v text;
begin
  perform qa.f04_as(p_uid, p_role);
  execute p_sql into v;
  execute 'reset role';
  return coalesce(v, 'NULL');
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Call public.create_trip_from_invite as the current (postgres) role inside a sub-transaction: a refusal rolls back
-- anything the call wrote. Returns 'ok <result json>' or 'error <sqlstate> <message>[ detail=<detail>]'.
create or replace function qa.f04_create(p_user uuid, p_email text, p_payload jsonb)
returns text language plpgsql set search_path = '' as $f$
declare v jsonb; d text;
begin
  v := public.create_trip_from_invite(p_user, p_email, p_payload);
  return 'ok ' || v::text;
exception when others then
  get stacked diagnostics d = pg_exception_detail;
  return 'error ' || sqlstate || ' ' || sqlerrm || coalesce(' detail=' || nullif(d, ''), '');
end $f$;

-- Expected-value grammar (same as F01–F03): 'N rows' exact · 'error 42501' prefix · 'error contains xyz' · 'A or B'.
create or replace function qa.f04_match(p_exp text, p_act text)
returns boolean language plpgsql immutable set search_path = '' as $f$
declare alt text;
begin
  if p_act is null then return false; end if;
  if position(' or ' in p_exp) > 0 then
    foreach alt in array pg_catalog.string_to_array(p_exp, ' or ') loop
      if qa.f04_match(alt, p_act) then return true; end if;
    end loop;
    return false;
  end if;
  if p_exp like 'error contains %' then
    return p_act like 'error %' and position(substr(p_exp, 16) in p_act) > 0;
  end if;
  if p_exp like 'error %' then
    return p_act like p_exp || '%';
  end if;
  return p_act = p_exp;
end $f$;

create or replace function qa.f04_rec(r jsonb, p_id int, p_name text, p_exp text, p_act text)
returns jsonb language plpgsql set search_path = '' as $f$
begin
  return r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
    'id', p_id, 'name', p_name,
    'detail', 'expected: ' || p_exp || ' | actual: ' || coalesce(p_act, '(null)'),
    'pass', qa.f04_match(p_exp, p_act)));
end $f$;

create or replace function qa.f04_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r   jsonb := '[]'::jsonb;
  au  constant text := 'authenticated';
  -- fixed test identities (namespace f04…)
  u_m   constant uuid := 'f0400000-0000-4000-8000-0000000000a1';  -- invited manager (dana)
  u_x   constant uuid := 'f0400000-0000-4000-8000-0000000000a2';  -- another user (tries to reuse dana's invite)
  u_e   constant uuid := 'f0400000-0000-4000-8000-0000000000a3';  -- editor added to the new trip
  u_v   constant uuid := 'f0400000-0000-4000-8000-0000000000a4';  -- viewer added to the new trip
  u_o   constant uuid := 'f0400000-0000-4000-8000-0000000000d1';  -- outsider (no membership)
  u_k   constant uuid := 'f0400000-0000-4000-8000-0000000000b1';  -- validation / cap / leap / month runs
  u_r   constant uuid := 'f0400000-0000-4000-8000-0000000000c1';  -- replaced-invite runs
  e_m   constant text := 'f04-dana@qa.invalid';
  e_k   constant text := 'f04-k@qa.invalid';
  e_r   constant text := 'f04-r@qa.invalid';
  alpha constant text := '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$';
  pay   jsonb := '{"name":"  F04 יפן 2027 ","display_name":"דנה","start_date":"2027-04-03","end_date":"2027-04-20",
                   "home_currency":"ILS","default_lang":"he","default_role":"viewer","countries":["JP","KR"],
                   "currencies":[{"code":"JPY","kind":"destination"},{"code":"KRW","kind":"destination"}],
                   "center":{"lat":35.68,"lng":139.69}}';
  cap10 jsonb := '[{"code":"JPY","kind":"destination"},{"code":"KRW","kind":"destination"},{"code":"THB","kind":"added"},
                   {"code":"GBP","kind":"added"},{"code":"CHF","kind":"added"},{"code":"CZK","kind":"added"},
                   {"code":"HUF","kind":"added"}]';
  res   jsonb;
  res2  jsonb;
  t_m   uuid;          -- the happy-path trip
  t2    uuid;
  days  jsonb;
  act   text;
  i_old uuid;
  i_new uuid;
  n_before bigint;
  n_inv_before bigint;
  n_trips_before bigint;
  k     int;
  f     text;
  bad   jsonb;
  case_id int;
begin
  select count(*) into n_inv_before from public.manager_invites where used_at is null;
  select count(*) into n_trips_before from public.trips;

  begin
    -- ================= SETUP (as postgres, bypassing RLS) =================
    execute 'reset role';
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at) values
      (u_m, 'authenticated', 'authenticated', e_m,                   '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_x, 'authenticated', 'authenticated', 'f04-x@qa.invalid',    '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_e, 'authenticated', 'authenticated', 'f04-e@qa.invalid',    '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_v, 'authenticated', 'authenticated', 'f04-v@qa.invalid',    '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_o, 'authenticated', 'authenticated', null,                  '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_k, 'authenticated', 'authenticated', e_k,                   '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_r, 'authenticated', 'authenticated', e_r,                   '00000000-0000-0000-0000-000000000000', now(), now());
    insert into public.manager_invites (email, token_hash, draft_name, inviter_name, expires_at)
      values (e_m, 'f04hash-m', 'F04 יפן 2027', 'אור', now() + interval '7 days');

    -- ================= find_invite_for_email =================
    res := public.find_invite_for_email('  F04-DANA@qa.invalid ');
    r := qa.f04_rec(r, 1, 'find: open invite found with trimmed / lower-cased email', 'true/F04 יפן 2027/אור',
      (res->>'found') || '/' || coalesce(res->>'draft_name', '') || '/' || coalesce(res->>'inviter_name', ''));
    r := qa.f04_rec(r, 2, 'find: result keys (no email, no token / hash)', 'draft_name,expires_at,found,invite_id,inviter_name',
      (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(res) k2));
    r := qa.f04_rec(r, 3, 'find: unknown email → {found:false}', '{"found": false}',
      public.find_invite_for_email('f04-nobody@qa.invalid')::text);
    r := qa.f04_rec(r, 4, 'find: empty / null email → {found:false}', '{"found": false}/{"found": false}',
      public.find_invite_for_email('  ')::text || '/' || public.find_invite_for_email(null)::text);

    -- ================= C11 · happy path =================
    select count(*) into n_before from public.trips;
    res := public.create_trip_from_invite(u_m, ' F04-Dana@QA.invalid ', pay);
    t_m := (res->>'trip_id')::uuid;
    r := qa.f04_rec(r, 10, 'C11 create → created=true, trip_id, 8-char join code', 'true/true/true',
      (res->>'created') || '/' || (t_m is not null)::text || '/' || ((res->>'join_code') ~ alpha)::text);
    r := qa.f04_rec(r, 11, 'C11 exactly one new trips row', '1',
      ((select count(*) from public.trips) - n_before)::text);
    r := qa.f04_rec(r, 12, 'C11 trips row fields (trimmed name, dates, home, lang, role, status, created_by)', '1',
      (select count(*)::text from public.trips where id = t_m and name = 'F04 יפן 2027' and start_date = '2027-04-03'
          and end_date = '2027-04-20' and home_currency = 'ILS' and default_lang = 'he' and default_role = 'viewer'
          and status = 'active' and created_by = u_m));
    r := qa.f04_rec(r, 13, 'C11 trip_countries in payload order', 'JP:0,KR:1',
      (select string_agg(country_code || ':' || sort, ',' order by sort) from public.trip_countries where trip_id = t_m));
    r := qa.f04_rec(r, 14, 'C11 trip_currencies = home base sort 0, other bases 1–2, then destinations', 'ILS:base:0,USD:base:1,EUR:base:2,JPY:destination:3,KRW:destination:4',
      (select string_agg(currency_code || ':' || kind || ':' || sort, ',' order by sort) from public.trip_currencies where trip_id = t_m));
    r := qa.f04_rec(r, 15, 'C11 one active manager membership with the display name + approved_at', '1/1',
      (select count(*)::text from public.trip_members where trip_id = t_m) || '/' ||
      (select count(*)::text from public.trip_members where trip_id = t_m and user_id = u_m and display_name = 'דנה'
          and role = 'manager' and status = 'active' and approved_at is not null));
    r := qa.f04_rec(r, 16, 'C11 one trip_join_codes row in the allowed alphabet, equal to the returned code', '1/true',
      (select count(*)::text from public.trip_join_codes where trip_id = t_m) || '/' ||
      coalesce((select (code ~ alpha and code = res->>'join_code')::text from public.trip_join_codes where trip_id = t_m), 'false'));
    select value::jsonb into days from public.trip_kv where trip_id = t_m and key = 'trip';
    r := qa.f04_rec(r, 17, 'C11 trip_kv.trip = 18 days, 03/04/2027 … 20/04/2027, day 1…18', '18/03/04/2027/20/04/2027/1/18',
      pg_catalog.jsonb_array_length(days)::text || '/' || (days->0->>'date') || '/' || (days->17->>'date') || '/' ||
      (days->0->>'day') || '/' || (days->17->>'day'));
    r := qa.f04_rec(r, 18, 'C11 day object shape exactly (empty texts, cost 0, centre coords, zoom 5, no waypoints, first country)', 'true',
      (days->0 = '{"day":1,"date":"03/04/2027","region":"","title":"","activities":"","hotel":"","cost":0,"notes":"","lat":35.68,"lng":139.69,"zoom":5,"waypoints":[],"country":"JP"}'::jsonb)::text);
    r := qa.f04_rec(r, 19, 'C11 every day: consecutive dates, day = position, waypoints [], same centre + country', '18',
      (select count(*)::text from pg_catalog.jsonb_array_elements(days) with ordinality as d(e, ord)
        where (e->>'day')::int = ord
          and e->>'date' = pg_catalog.to_char(date '2027-04-03' + (ord::int - 1), 'DD/MM/YYYY')
          and e->'waypoints' = '[]'::jsonb and (e->>'lat')::numeric = 35.68 and (e->>'lng')::numeric = 139.69
          and e->>'country' = 'JP' and e->>'title' = ''));
    -- CHANGE 2026-10-12 F04-QA-02: keys are now "trip" + "tripname" (F04-DB-02); was: only "trip", 1 row by the manager.
    r := qa.f04_rec(r, 20, 'C11 trip_kv: keys "trip" + "tripname" (= trip name), updated_by = manager', 'trip,tripname/2/F04 יפן 2027',
      (select string_agg(key, ',' order by key) from public.trip_kv where trip_id = t_m) || '/' ||
      (select count(*)::text from public.trip_kv where trip_id = t_m and updated_by = u_m) || '/' ||
      coalesce((select value from public.trip_kv where trip_id = t_m and key = 'tripname'), '∅'));
    r := qa.f04_rec(r, 21, 'C11 invite marked used_at + trip_id', '1',
      (select count(*)::text from public.manager_invites where email = e_m and used_at is not null and trip_id = t_m));
    r := qa.f04_rec(r, 22, 'find after use → {found:false}', '{"found": false}', public.find_invite_for_email(e_m)::text);

    -- ================= C10 · idempotent retry =================
    select count(*) into n_before from public.trips;
    res2 := public.create_trip_from_invite(u_m, e_m, jsonb_set(pay, '{name}', '"other name"'));
    r := qa.f04_rec(r, 30, 'C10 retry by the same manager → same trip_id + join_code, created=false', 'true/true/false',
      (res2->>'trip_id' = res->>'trip_id')::text || '/' || (res2->>'join_code' = res->>'join_code')::text || '/' || (res2->>'created'));
    r := qa.f04_rec(r, 31, 'C10 retry wrote nothing (trips, members, codes, kv unchanged; name kept)', '0/1/1/2/F04 יפן 2027',  -- F04-QA-02: kv 1 → 2
      ((select count(*) from public.trips) - n_before)::text || '/' ||
      (select count(*)::text from public.trip_members where trip_id = t_m) || '/' ||
      (select count(*)::text from public.trip_join_codes where trip_id = t_m) || '/' ||
      (select count(*)::text from public.trip_kv where trip_id = t_m) || '/' ||
      (select name from public.trips where id = t_m));

    -- ================= C5 · refusals (nothing written) =================
    select count(*) into n_before from public.trips;
    r := qa.f04_rec(r, 32, 'C5 invite already used by another user''s trip → invite_invalid', 'error P0001 invite_invalid',
      qa.f04_create(u_x, e_m, pay));
    r := qa.f04_rec(r, 33, 'C5 no invite for the email → invite_invalid', 'error P0001 invite_invalid',
      qa.f04_create(u_x, 'f04-x@qa.invalid', pay));
    r := qa.f04_rec(r, 34, 'C5 null user / empty email → invite_invalid', 'error P0001 invite_invalid / error P0001 invite_invalid',
      qa.f04_create(null, e_m, pay) || ' / ' || qa.f04_create(u_x, '  ', pay));
    insert into public.manager_invites (email, token_hash, expires_at) values ('f04-x@qa.invalid', 'f04hash-x1', now() - interval '1 minute');
    r := qa.f04_rec(r, 35, 'C5 expired invite → invite_invalid', 'error P0001 invite_invalid',
      qa.f04_create(u_x, 'f04-x@qa.invalid', pay));
    r := qa.f04_rec(r, 36, 'find: expired invite → {found:false}', '{"found": false}', public.find_invite_for_email('f04-x@qa.invalid')::text);
    update public.manager_invites set revoked_at = now() where token_hash = 'f04hash-x1';
    insert into public.manager_invites (email, token_hash, expires_at, revoked_at)
      values ('f04-x@qa.invalid', 'f04hash-x2', now() + interval '5 days', now());
    r := qa.f04_rec(r, 37, 'C5 revoked invite (still within expiry) → invite_invalid', 'error P0001 invite_invalid',
      qa.f04_create(u_x, 'f04-x@qa.invalid', pay));
    r := qa.f04_rec(r, 38, 'find: revoked invite → {found:false}', '{"found": false}', public.find_invite_for_email('f04-x@qa.invalid')::text);
    -- replaced: the older invite was revoked when a newer one was issued to the same email
    insert into public.manager_invites (id, email, token_hash, draft_name, expires_at, revoked_at, created_at)
      values (gen_random_uuid(), e_r, 'f04hash-r1', 'F04 old', now() + interval '6 days', now(), now() - interval '2 days')
      returning id into i_old;
    insert into public.manager_invites (id, email, token_hash, draft_name, expires_at, created_at)
      values (gen_random_uuid(), e_r, 'f04hash-r2', 'F04 new', now() - interval '1 minute', now() - interval '1 day')
      returning id into i_new;
    r := qa.f04_rec(r, 39, 'C5 replaced invite whose replacement expired → invite_invalid', 'error P0001 invite_invalid',
      qa.f04_create(u_r, e_r, pay));
    r := qa.f04_rec(r, 40, 'C5 refusals wrote nothing (trips count unchanged, refused invites still unused)', '0/0',
      ((select count(*) from public.trips) - n_before)::text || '/' ||
      (select count(*)::text from public.manager_invites where email in ('f04-x@qa.invalid', e_r) and (used_at is not null or trip_id is not null)));
    update public.manager_invites set revoked_at = now() where id = i_new;
    insert into public.manager_invites (email, token_hash, draft_name, expires_at)
      values (e_r, 'f04hash-r3', 'F04 newest', now() + interval '7 days') returning id into i_new;
    r := qa.f04_rec(r, 41, 'find: replaced → returns the newest open invite', 'F04 newest',
      public.find_invite_for_email(e_r)->>'draft_name');
    act := qa.f04_create(u_r, e_r, jsonb_set(pay, '{countries}', '["GR"]') - 'currencies');
    r := qa.f04_rec(r, 42, 'C5 replaced invite with an open replacement → created from the NEW invite', 'ok',
      split_part(act, ' ', 1));
    r := qa.f04_rec(r, 43, 'replaced: new invite used, old ones untouched (unused)', '1/0',
      (select count(*)::text from public.manager_invites where id = i_new and used_at is not null and trip_id is not null) || '/' ||
      (select count(*)::text from public.manager_invites where email = e_r and id <> i_new and used_at is not null));
    r := qa.f04_rec(r, 44, 'currencies omitted → bases only (3 rows)', '3',
      (select count(*)::text from public.trip_currencies c join public.manager_invites i on i.trip_id = c.trip_id where i.id = i_new));

    -- ================= payload validation (one invalid_payload per field) =================
    insert into public.manager_invites (email, token_hash, expires_at) values (e_k, 'f04hash-k1', now() + interval '7 days');
    select count(*) into n_before from public.trips;
    case_id := 50;
    for f, bad in select * from (values
        ('payload',       '"not an object"'::jsonb),
        ('name',          jsonb_set(pay, '{name}', '"   "')),
        ('name',          jsonb_set(pay, '{name}', to_jsonb(pg_catalog.repeat('a', 81)))),
        ('name',          jsonb_set(pay, '{name}', '42')),
        ('display_name',  pay - 'display_name'),
        ('display_name',  jsonb_set(pay, '{display_name}', '""')),
        ('display_name',  jsonb_set(pay, '{display_name}', to_jsonb(pg_catalog.repeat('a', 41)))),
        ('start_date',    jsonb_set(pay, '{start_date}', '"2027-02-30"')),
        ('start_date',    jsonb_set(pay, '{start_date}', '"03/04/2027"')),
        ('start_date',    pay - 'start_date'),
        ('end_date',      jsonb_set(pay, '{end_date}', '"2027-04-31"')),
        ('end_date',      jsonb_set(pay, '{end_date}', '"2027-04-02"')),
        ('end_date',      jsonb_set(pay, '{end_date}', '"2027-08-01"')),
        ('home_currency', jsonb_set(pay, '{home_currency}', '"JPY"')),
        ('home_currency', pay - 'home_currency'),
        ('default_lang',  jsonb_set(pay, '{default_lang}', '"en"')),
        ('default_role',  jsonb_set(pay, '{default_role}', '"manager"')),
        ('countries',     jsonb_set(pay, '{countries}', '[]')),
        ('countries',     jsonb_set(pay, '{countries}', '["JP","JP"]')),
        ('countries',     jsonb_set(pay, '{countries}', '["jp"]')),
        ('countries',     jsonb_set(pay, '{countries}', '"JP"')),
        ('countries',     jsonb_set(pay, '{countries}', '["AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN","AO","AP"]')),
        ('currencies',    jsonb_set(pay, '{currencies}', '[{"code":"USD","kind":"destination"}]')),
        ('currencies',    jsonb_set(pay, '{currencies}', '[{"code":"JPY","kind":"base"}]')),
        ('currencies',    jsonb_set(pay, '{currencies}', '[{"code":"JPY","kind":"added"},{"code":"JPY","kind":"destination"}]')),
        ('currencies',    jsonb_set(pay, '{currencies}', '[{"code":"jpy","kind":"added"}]')),
        ('currencies',    jsonb_set(pay, '{currencies}', '{"code":"JPY"}')),
        ('center',        jsonb_set(pay, '{center}', '{"lat":91,"lng":0}')),
        ('center',        jsonb_set(pay, '{center}', '{"lat":0,"lng":-181}')),
        ('center',        jsonb_set(pay, '{center}', '{"lat":"35","lng":139}')),
        ('center',        pay - 'center')) as x(f, b)
    loop
      r := qa.f04_rec(r, case_id, 'payload: invalid ' || f || ' → invalid_payload detail=' || f,
        'error P0001 invalid_payload detail=' || f, qa.f04_create(u_k, e_k, bad));
      case_id := case_id + 1;
    end loop;
    -- cap 10: 8 payload currencies + 3 bases = 11
    r := qa.f04_rec(r, 90, 'cap: 3 bases + 8 currencies → too_many_currencies', 'error P0001 too_many_currencies',
      qa.f04_create(u_k, e_k, jsonb_set(pay, '{currencies}', cap10 || '[{"code":"PLN","kind":"added"}]'::jsonb)));
    r := qa.f04_rec(r, 91, 'validation refusals wrote nothing; the invite is still open', '0/true',
      ((select count(*) from public.trips) - n_before)::text || '/' || (public.find_invite_for_email(e_k)->>'found'));

    -- exactly 10 accepted + leap day range + home EUR
    res := public.create_trip_from_invite(u_k, e_k,
      jsonb_set(jsonb_set(jsonb_set(jsonb_set(pay, '{currencies}', cap10), '{start_date}', '"2028-02-28"'),
                '{end_date}', '"2028-03-01"'), '{home_currency}', '"EUR"'));
    t2 := (res->>'trip_id')::uuid;
    r := qa.f04_rec(r, 92, 'cap: 3 bases + 7 currencies = 10 accepted; home EUR sort 0, then ILS, USD', '10/EUR:0,ILS:1,USD:2',
      (select count(*)::text from public.trip_currencies where trip_id = t2) || '/' ||
      (select string_agg(currency_code || ':' || sort, ',' order by sort) from public.trip_currencies where trip_id = t2 and kind = 'base'));
    select value::jsonb into days from public.trip_kv where trip_id = t2 and key = 'trip';
    r := qa.f04_rec(r, 93, 'leap day: 2028-02-28 → 2028-03-01 = 3 days (28/02, 29/02, 01/03)', '3/28/02/2028,29/02/2028,01/03/2028',
      pg_catalog.jsonb_array_length(days)::text || '/' ||
      (select string_agg(e->>'date', ',' order by ord) from pg_catalog.jsonb_array_elements(days) with ordinality as d(e, ord)));

    -- month boundary + 1-day + 120-day trips (each needs its own open invite)
    -- every invite of the transaction has the same created_at (now()); retire the previous ones so the next create
    -- resolves to the fresh invite (the function takes the newest non-revoked row)
    update public.manager_invites set revoked_at = now() where email = e_k and revoked_at is null;
    insert into public.manager_invites (email, token_hash, expires_at) values (e_k, 'f04hash-k2', now() + interval '7 days');
    res := public.create_trip_from_invite(u_k, e_k,
      jsonb_set(jsonb_set(pay, '{start_date}', '"2027-01-30"'), '{end_date}', '"2027-02-02"'));
    select value::jsonb into days from public.trip_kv where trip_id = (res->>'trip_id')::uuid and key = 'trip';
    r := qa.f04_rec(r, 94, 'month boundary: 2027-01-30 → 2027-02-02 = 4 days (30/01, 31/01, 01/02, 02/02)', '4/30/01/2027,31/01/2027,01/02/2027,02/02/2027',
      pg_catalog.jsonb_array_length(days)::text || '/' ||
      (select string_agg(e->>'date', ',' order by ord) from pg_catalog.jsonb_array_elements(days) with ordinality as d(e, ord)));
    update public.manager_invites set revoked_at = now() where email = e_k and revoked_at is null;
    insert into public.manager_invites (email, token_hash, expires_at) values (e_k, 'f04hash-k3', now() + interval '7 days');
    res := public.create_trip_from_invite(u_k, e_k,
      jsonb_set(jsonb_set(pay, '{start_date}', '"2027-12-31"'), '{end_date}', '"2027-12-31"'));
    select value::jsonb into days from public.trip_kv where trip_id = (res->>'trip_id')::uuid and key = 'trip';
    r := qa.f04_rec(r, 95, 'one-day trip (start = end) → exactly 1 day', '1/31/12/2027/1',
      pg_catalog.jsonb_array_length(days)::text || '/' || (days->0->>'date') || '/' || (days->0->>'day'));
    update public.manager_invites set revoked_at = now() where email = e_k and revoked_at is null;
    insert into public.manager_invites (email, token_hash, expires_at) values (e_k, 'f04hash-k4', now() + interval '7 days');
    res := public.create_trip_from_invite(u_k, e_k,
      jsonb_set(jsonb_set(pay, '{start_date}', '"2027-01-01"'), '{end_date}', '"2027-04-30"'));
    select value::jsonb into days from public.trip_kv where trip_id = (res->>'trip_id')::uuid and key = 'trip';
    r := qa.f04_rec(r, 96, '120-day trip (upper bound) accepted, last day 30/04/2027 = day 120', '120/30/04/2027/120',
      pg_catalog.jsonb_array_length(days)::text || '/' || (days->119->>'date') || '/' || (days->119->>'day'));

    -- ================= join-code alphabet over many draws =================
    for k in 1..20 loop
      update public.manager_invites set revoked_at = now() where email = e_k and revoked_at is null;
      insert into public.manager_invites (email, token_hash, expires_at) values (e_k, 'f04hash-j' || k, now() + interval '7 days');
      perform public.create_trip_from_invite(u_k, e_k, pay);
    end loop;
    r := qa.f04_rec(r, 97, 'join codes: 26 QA trips, every code 8 chars from ABCDEFGHJKLMNPQRSTUVWXYZ23456789, all distinct', '26/0/26',
      (select count(*)::text from public.trip_join_codes c join public.trips t on t.id = c.trip_id where t.created_by in (u_m, u_k, u_r)) || '/' ||
      (select count(*)::text from public.trip_join_codes c join public.trips t on t.id = c.trip_id where t.created_by in (u_m, u_k, u_r) and c.code !~ alpha) || '/' ||
      (select count(distinct c.code)::text from public.trip_join_codes c join public.trips t on t.id = c.trip_id where t.created_by in (u_m, u_k, u_r)));

    -- ================= C17 · RLS on the new trip =================
    insert into public.trip_members (trip_id, user_id, display_name, role, status, approved_at) values
      (t_m, u_e, 'F04Editor', 'editor', 'active', now()),
      (t_m, u_v, 'F04Viewer', 'viewer', 'active', now());
    r := qa.f04_rec(r, 100, 'C17 non-member reads 0 rows of the new trip (trips / members / countries / currencies / kv / join code)', '0 rows',
      qa.f04_count(u_o, au, pg_catalog.format(
        'select 1 from public.trips where id = %1$L union all select 1 from public.trip_members where trip_id = %1$L
         union all select 1 from public.trip_countries where trip_id = %1$L union all select 1 from public.trip_currencies where trip_id = %1$L
         union all select 1 from public.trip_kv where trip_id = %1$L union all select 1 from public.trip_join_codes where trip_id = %1$L', t_m)));
    r := qa.f04_rec(r, 101, 'C17 anon reads 0 rows of the new trip (or no privilege)', '0 rows or error 42501',
      qa.f04_count(null, 'anon', pg_catalog.format(
        'select 1 from public.trips where id = %1$L union all select 1 from public.trip_kv where trip_id = %1$L', t_m)));
    r := qa.f04_rec(r, 102, 'C17 the manager reads the trip, its kv and its join code', '1 rows/2 rows/1 rows',  -- F04-QA-02: kv 1 → 2
      qa.f04_count(u_m, au, pg_catalog.format('select 1 from public.trips where id = %L', t_m)) || '/' ||
      qa.f04_count(u_m, au, pg_catalog.format('select 1 from public.trip_kv where trip_id = %L', t_m)) || '/' ||
      qa.f04_count(u_m, au, pg_catalog.format('select 1 from public.trip_join_codes where trip_id = %L', t_m)));
    r := qa.f04_rec(r, 103, 'C17 an editor of the trip cannot read trip_join_codes', '0 rows or error 42501',
      qa.f04_count(u_e, au, pg_catalog.format('select 1 from public.trip_join_codes where trip_id = %L', t_m)));
    r := qa.f04_rec(r, 104, 'C17 a viewer of the trip cannot read trip_join_codes', '0 rows or error 42501',
      qa.f04_count(u_v, au, pg_catalog.format('select 1 from public.trip_join_codes where trip_id = %L', t_m)));
    r := qa.f04_rec(r, 105, 'C17 editor/viewer still read the trip itself (sanity)', '1 rows/1 rows',
      qa.f04_count(u_e, au, pg_catalog.format('select 1 from public.trips where id = %L', t_m)) || '/' ||
      qa.f04_count(u_v, au, pg_catalog.format('select 1 from public.trips where id = %L', t_m)));
    r := qa.f04_rec(r, 106, 'C17 the manager cannot write trip_join_codes (no client writes)', 'error 42501 or 0 rows',
      qa.f04_val(u_m, au, pg_catalog.format('with u as (update public.trip_join_codes set code = ''AAAAAAAA'' where trip_id = %L returning 1) select count(*)::text || '' rows'' from u', t_m)));
    r := qa.f04_rec(r, 107, 'C17 authenticated calling create_trip_from_invite → no execute privilege', 'error 42501',
      qa.f04_val(u_m, au, pg_catalog.format('select public.create_trip_from_invite(%L::uuid, %L, ''{}''::jsonb)::text', u_m, e_m)));
    r := qa.f04_rec(r, 108, 'C17 anon calling create_trip_from_invite → no execute privilege', 'error 42501',
      qa.f04_val(null, 'anon', pg_catalog.format('select public.create_trip_from_invite(%L::uuid, %L, ''{}''::jsonb)::text', u_m, e_m)));
    r := qa.f04_rec(r, 109, 'C17 authenticated calling find_invite_for_email → no execute privilege', 'error 42501',
      qa.f04_val(u_m, au, 'select public.find_invite_for_email(''f04-dana@qa.invalid'')::text'));
    r := qa.f04_rec(r, 110, 'C17 anon calling find_invite_for_email → no execute privilege', 'error 42501',
      qa.f04_val(null, 'anon', 'select public.find_invite_for_email(''f04-dana@qa.invalid'')::text'));

    execute 'reset role';
    raise exception 'f04_rollback';
  exception when others then
    if sqlerrm <> 'f04_rollback' then
      r := r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
        'id', 0, 'name', 'unexpected error (setup or harness) — later scenarios did not run',
        'detail', 'expected: no error | actual: error ' || sqlstate || ' ' || sqlerrm, 'pass', false));
    end if;
  end;

  execute 'reset role';
  perform pg_catalog.set_config('request.jwt.claims', '', true);
  perform pg_catalog.set_config('request.jwt.claim.sub', '', true);
  perform pg_catalog.set_config('request.jwt.claim.role', '', true);

  -- ================= §2 · catalog checks (read-only, outside the rolled-back block) =================
  r := qa.f04_rec(r, 120, '§2 create_trip_from_invite: security definer, volatile, search_path=''''', 'true/v/search_path=""',
    (select p.prosecdef::text || '/' || p.provolatile::text || '/' || coalesce(array_to_string(p.proconfig, ','), '')
       from pg_catalog.pg_proc p where p.oid = 'public.create_trip_from_invite(uuid,text,jsonb)'::regprocedure));
  r := qa.f04_rec(r, 121, '§2 find_invite_for_email: security definer, search_path=''''', 'true/search_path=""',
    (select p.prosecdef::text || '/' || coalesce(array_to_string(p.proconfig, ','), '')
       from pg_catalog.pg_proc p where p.oid = 'public.find_invite_for_email(text)'::regprocedure));
  r := qa.f04_rec(r, 122, '§2 grants: anon / authenticated cannot execute either function', 'false/false/false/false',
    pg_catalog.has_function_privilege('anon', 'public.create_trip_from_invite(uuid,text,jsonb)', 'execute')::text || '/' ||
    pg_catalog.has_function_privilege('authenticated', 'public.create_trip_from_invite(uuid,text,jsonb)', 'execute')::text || '/' ||
    pg_catalog.has_function_privilege('anon', 'public.find_invite_for_email(text)', 'execute')::text || '/' ||
    pg_catalog.has_function_privilege('authenticated', 'public.find_invite_for_email(text)', 'execute')::text);
  r := qa.f04_rec(r, 123, '§2 grants: service_role can execute both functions', 'true/true',
    pg_catalog.has_function_privilege('service_role', 'public.create_trip_from_invite(uuid,text,jsonb)', 'execute')::text || '/' ||
    pg_catalog.has_function_privilege('service_role', 'public.find_invite_for_email(text)', 'execute')::text);
  r := qa.f04_rec(r, 124, '§2 PUBLIC has no execute on either function', '0',
    (select count(*)::text from pg_catalog.pg_proc p, pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
      where p.oid in ('public.create_trip_from_invite(uuid,text,jsonb)'::regprocedure, 'public.find_invite_for_email(text)'::regprocedure)
        and a.grantee = 0 and a.privilege_type = 'EXECUTE'));
  r := qa.f04_rec(r, 125, '§2 no client write grants on trip_join_codes (authenticated / anon)', 'false',
    (pg_catalog.has_table_privilege('authenticated', 'public.trip_join_codes', 'insert,update,delete')
     or pg_catalog.has_table_privilege('anon', 'public.trip_join_codes', 'insert,update,delete'))::text);
  r := qa.f04_rec(r, 126, '§2 no new tables in public (still the 9 F01 tables)', '9',
    (select count(*)::text from pg_catalog.pg_tables where schemaname = 'public'));
  r := qa.f04_rec(r, 127, 'Leftovers after the run: 0 f04 users, 0 f04 trips, 0 f04 invites, invites/trips counts unchanged', '0/0/0/true',
    (select (select count(*) from auth.users where id::text like 'f0400000-%')::text || '/' ||
            (select count(*) from public.trips where name like 'F04 %')::text || '/' ||
            (select count(*) from public.manager_invites where email like 'f04-%@qa.invalid')::text || '/' ||
            ((select count(*) from public.manager_invites where used_at is null) = n_inv_before
             and (select count(*) from public.trips) = n_trips_before)::text));

  return query
    select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail'
      from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
