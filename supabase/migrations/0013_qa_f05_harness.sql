-- Plan_Travel QA · F05 DB-level test harness · version 3.0.0-alpha.6 · F05
-- CHANGE 2026-10-19 F05-QA-01: first version (no previous version). Installs qa.f05_run() in the locked `qa` schema,
--   same pattern as F01–F04 (0002–0004, 0007, 0009, 0011): helpers impersonate a user via request.jwt.claims +
--   SET LOCAL ROLE, all test data is created inside a sub-transaction that is always rolled back (raise 'f05_rollback'),
--   search_path pinned to '', nothing granted to public/anon/authenticated. SECURITY INVOKER (run as postgres, the owner
--   of the F05 functions), because PostgreSQL forbids SET ROLE inside a SECURITY DEFINER function.
--   Written black-box from docs/F05_spec.md §2 / §4 (the implementation in 0012_f05.sql was not read; only the catalog
--   signatures of the six entry functions were looked up).
--
-- Run (after 0012_f05.sql):   select * from qa.f05_run() order by id;
-- Output: one row per scenario (id, name, pass, detail) — detail = 'expected: … | actual: …'.
--
-- Time windows (24 h, 1 h, transfer expiry) are exercised by back-dating private.join_attempts / private.transfer_codes
-- rows, never by sleeping. Every refusal must be RETURNED as {"error":code} (spec §2.3); a raised exception is reported by
-- the call wrappers as {"raised":"<sqlstate> <message>"} and therefore fails the scenario.
-- A call that writes and the check of its effect are always separate statements: a sub-select in the same PL/pgSQL
-- expression reads the snapshot taken before the call.
--
-- Criteria covered (docs/F05_spec.md §4): 3, 4 (DB side), 5, 6, 7, 8, 9, 12, 14, plus §2.1–2.5 (rate limits, catalog,
-- grants, no new policies/grants on existing tables, `public` still 9 tables, schema `private` closed).

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

-- Impersonate: p_role in ('authenticated','anon','postgres'); p_uid null = no "sub" claim.
create or replace function qa.f05_as(p_uid uuid, p_role text)
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
create or replace function qa.f05_count(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f05_as(p_uid, p_role);
  execute 'select count(*) from (' || p_sql || ') f05_s' into n;
  execute 'reset role';
  return n || ' rows';
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Evaluate a scalar expression while impersonating; report it as text.
create or replace function qa.f05_val(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare v text;
begin
  perform qa.f05_as(p_uid, p_role);
  execute p_sql into v;
  execute 'reset role';
  return coalesce(v, 'NULL');
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Call wrappers (as postgres = what the Edge Functions do with the service role). A raised exception becomes
-- {"raised": "..."} so the scenario fails visibly instead of aborting the harness.
create or replace function qa.f05_prev(p_user uuid, p_code text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.join_preview(p_user, p_code, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f05_req(p_user uuid, p_code text, p_name text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.join_request(p_user, p_code, p_name, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f05_cancel(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.join_cancel(p_user, p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f05_issue(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.issue_transfer(p_user, p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f05_claim(p_user uuid, p_code text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.claim_transfer(p_user, p_code, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f05_appr(p_user uuid, p_member uuid, p_decision text, p_role text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.approve_member(p_user, p_member, p_decision, p_role);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

-- The error code of a result, or 'ok' when the result has no "error" key.
create or replace function qa.f05_e(p jsonb)
returns text language sql immutable set search_path = '' as $f$
  select case when p ? 'raised' then 'raised ' || (p->>'raised')
              when p ? 'error' then p->>'error' else 'ok' end
$f$;

-- Expected-value grammar (same as F01–F04): 'N rows' exact · 'error 42501' prefix · 'error contains xyz' · 'A or B'.
create or replace function qa.f05_match(p_exp text, p_act text)
returns boolean language plpgsql immutable set search_path = '' as $f$
declare alt text;
begin
  if p_act is null then return false; end if;
  if position(' or ' in p_exp) > 0 then
    foreach alt in array pg_catalog.string_to_array(p_exp, ' or ') loop
      if qa.f05_match(alt, p_act) then return true; end if;
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

create or replace function qa.f05_rec(r jsonb, p_id int, p_name text, p_exp text, p_act text)
returns jsonb language plpgsql set search_path = '' as $f$
begin
  return r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
    'id', p_id, 'name', p_name,
    'detail', 'expected: ' || p_exp || ' | actual: ' || coalesce(p_act, '(null)'),
    'pass', qa.f05_match(p_exp, p_act)));
end $f$;

create or replace function qa.f05_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r    jsonb := '[]'::jsonb;
  au   constant text := 'authenticated';
  -- fixed identities (namespace f0500000-…)
  u_m1  constant uuid := 'f0500000-0000-4000-8000-0000000000a1';  -- earliest manager of T1 ("דנה")
  u_m1b constant uuid := 'f0500000-0000-4000-8000-0000000000a2';  -- later manager of T1 ("אבי")
  u_e1  constant uuid := 'f0500000-0000-4000-8000-0000000000a3';  -- editor of T1
  u_v1  constant uuid := 'f0500000-0000-4000-8000-0000000000a4';  -- viewer of T1
  u_m2  constant uuid := 'f0500000-0000-4000-8000-0000000000a5';  -- manager of T2 only
  u_j1  constant uuid := 'f0500000-0000-4000-8000-0000000000b1';  -- joiner (happy path)
  u_j2  constant uuid := 'f0500000-0000-4000-8000-0000000000b2';  -- joiner (name taken, then other name)
  u_j3  constant uuid := 'f0500000-0000-4000-8000-0000000000b3';  -- joiner (reject / 3-per-24h)
  u_j4  constant uuid := 'f0500000-0000-4000-8000-0000000000b4';  -- joiner (removed)
  u_j5  constant uuid := 'f0500000-0000-4000-8000-0000000000b5';  -- joiner of T2 (default role viewer) + active elsewhere
  u_j6  constant uuid := 'f0500000-0000-4000-8000-0000000000b6';  -- joiner (approve as manager)
  u_j7  constant uuid := 'f0500000-0000-4000-8000-0000000000b7';  -- joiner (failed requests do not count)
  u_p   constant uuid := 'f0500000-0000-4000-8000-0000000000c1';  -- preview limit
  u_t1  constant uuid := 'f0500000-0000-4000-8000-0000000000d1';  -- transfer: installed-app identity #1
  u_t2  constant uuid := 'f0500000-0000-4000-8000-0000000000d2';  -- transfer: identity #2
  u_t3  constant uuid := 'f0500000-0000-4000-8000-0000000000d3';  -- transfer: brute force
  u_t4  constant uuid := 'f0500000-0000-4000-8000-0000000000d4';  -- transfer: manager's new identity
  u_o   constant uuid := 'f0500000-0000-4000-8000-0000000000e1';  -- outsider
  t1    constant uuid := 'f0500000-0000-4000-8000-00000000f001';
  t2    constant uuid := 'f0500000-0000-4000-8000-00000000f002';
  t3    constant uuid := 'f0500000-0000-4000-8000-00000000f003';  -- pending-cap trip
  c1    constant text := 'F5QAJNAA';
  c2    constant text := 'F5QAJNBB';
  c3    constant text := 'F5QAJNCC';
  res   jsonb; res2 jsonb;
  mid   uuid; mid2 uuid; mid_e uuid; mid_m1 uuid;
  tc    text; tc2 text;
  act   text;
  n     bigint; n2 bigint;
  k     int;
  g     uuid;
  n_trips_before bigint; n_att_before bigint; n_tc_before bigint;
begin
  select count(*) into n_trips_before from public.trips;
  select count(*) into n_att_before from private.join_attempts;
  select count(*) into n_tc_before from private.transfer_codes;

  begin
    -- ================= SETUP (as postgres, bypassing RLS) =================
    execute 'reset role';
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at)
      select u, 'authenticated', 'authenticated', null, '00000000-0000-0000-0000-000000000000', now(), now()
        from unnest(array[u_m1, u_m1b, u_e1, u_v1, u_m2, u_j1, u_j2, u_j3, u_j4, u_j5, u_j6, u_j7, u_p,
                          u_t1, u_t2, u_t3, u_t4, u_o]) u;
    insert into public.trips (id, name, start_date, end_date, default_role, created_by) values
      (t1, 'F05 יפן 2027',  '2027-04-03', '2027-04-20', 'editor', u_m1),
      (t2, 'F05 קבוצה 2',   '2027-05-30', '2027-06-02', 'viewer', u_m2),
      (t3, 'F05 תקרה',      '2027-07-01', '2027-07-01', 'editor', u_m2);
    insert into public.trip_join_codes (trip_id, code) values (t1, c1), (t2, c2), (t3, c3);
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at) values
      (t1, u_m1,  'דנה',      'manager', 'active', now() - interval '30 days', now() - interval '30 days'),
      (t1, u_m1b, 'אבי',      'manager', 'active', now() - interval '20 days', now() - interval '20 days'),
      (t1, u_e1,  'Editor Q', 'editor',  'active', now() - interval '10 days', now() - interval '10 days'),
      (t1, u_v1,  'צופה',     'viewer',  'active', now() - interval '9 days',  now() - interval '9 days'),
      (t2, u_m2,  'מנהל2',    'manager', 'active', now() - interval '5 days',  now() - interval '5 days'),
      (t3, u_m2,  'מנהל2',    'manager', 'active', now() - interval '5 days',  now() - interval '5 days');
    insert into public.trip_kv (trip_id, key, value) values (t1, 'trip', '[]'), (t1, 'tripname', 'F05 יפן 2027');
    select m.id into mid_e  from public.trip_members m where m.trip_id = t1 and m.user_id = u_e1;
    select m.id into mid_m1 from public.trip_members m where m.trip_id = t1 and m.user_id = u_m1;

    -- ================= C2 · preview =================
    res := qa.f05_prev(u_j1, c1, 'f05ip-j1');
    r := qa.f05_rec(r, 1, 'C2 preview: trip_id, name, start/end, 18 days, 4 active members, earliest manager, me=null',
      'true/F05 יפן 2027/2027-04-03/2027-04-20/18/4/דנה/null',
      ((res->>'trip_id') = t1::text)::text || '/' || coalesce(res->>'name', '∅') || '/' || coalesce(res->>'start_date', '∅') || '/' ||
      coalesce(res->>'end_date', '∅') || '/' || coalesce(res->>'days', '∅') || '/' || coalesce(res->>'members', '∅') || '/' ||
      coalesce(res->>'manager', '∅') || '/' || coalesce((res->'me')::text, 'null'));
    r := qa.f05_rec(r, 2, 'C14 preview discloses no identities / emails / join codes / other members', 'false/false/false/false',
      (position(u_m1::text in res::text) > 0)::text || '/' || (res::text ilike '%email%')::text || '/' ||
      (position(c1 in res::text) > 0 and not (res ? 'code'))::text || '/' || (position('Editor Q' in res::text) > 0)::text);
    res := qa.f05_prev(u_j1, 'ZZZZZZZZ', 'f05ip-j1');
    r := qa.f05_rec(r, 3, 'C7 preview of an unknown code → code_invalid (returned, not raised)', 'code_invalid', qa.f05_e(res));
    res := qa.f05_prev(u_j1, '', 'f05ip-j1');
    r := qa.f05_rec(r, 4, 'C7 preview of an empty code → code_invalid or invalid_request', 'code_invalid or invalid_request', qa.f05_e(res));
    res := qa.f05_prev(u_m1, c1, 'f05ip-m1');
    r := qa.f05_rec(r, 5, 'C8 preview by an active member → me.status=active (+ role)', 'active/manager',
      coalesce(res->'me'->>'status', '∅') || '/' || coalesce(res->'me'->>'role', '∅'));
    r := qa.f05_rec(r, 6, 'preview wrote an attempt row (kind preview) for the caller', '1 rows or 2 rows or 3 rows',
      (select count(*) || ' rows' from private.join_attempts a where a.kind = 'preview' and a.user_id = u_j1));

    -- ================= C3 · request =================
    res := qa.f05_req(u_j1, c1, '  נועה    כהן  ', 'f05ip-j1');
    mid := nullif(res->>'member_id', '')::uuid;
    r := qa.f05_rec(r, 10, 'C3 request: ok, pending, cleaned name (trim + single spaces), trip default role editor',
      'ok/pending/נועה כהן/editor',
      qa.f05_e(res) || '/' || coalesce(res->>'status', '∅') || '/' || coalesce(res->>'display_name', '∅') || '/' || coalesce(res->>'role', '∅'));
    r := qa.f05_rec(r, 11, 'C3 exactly one pending row with that name, the caller''s uid, the returned id, approved_at null', '1',
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_j1 and m.id = mid
          and m.status = 'pending' and m.display_name = 'נועה כהן' and m.approved_at is null));
    res := qa.f05_req(u_j1, c1, 'שם אחר', 'f05ip-j1');
    r := qa.f05_rec(r, 12, 'C8 request again while pending → same member, no new row, name unchanged', 'ok/true/1/נועה כהן',
      qa.f05_e(res) || '/' || ((res->>'member_id') = mid::text)::text || '/' ||
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_j1) || '/' ||
      (select m.display_name from public.trip_members m where m.id = mid));
    res := qa.f05_prev(u_j1, c1, 'f05ip-j1');
    r := qa.f05_rec(r, 13, 'C8 preview while pending → me.status=pending with my member id', 'pending/true',
      coalesce(res->'me'->>'status', '∅') || '/' || ((res->'me'->>'member_id') = mid::text)::text);
    r := qa.f05_rec(r, 14, 'C2 preview: pending members are not counted in "M חברים"', '4', coalesce(res->>'members', '∅'));

    -- ================= C6 · names =================
    select count(*) into n from public.trip_members m where m.trip_id = t1;
    r := qa.f05_rec(r, 20, 'C6 name taken by a pending member (extra spaces) → name_taken', 'name_taken',
      qa.f05_e(qa.f05_req(u_j2, c1, ' נועה   כהן', 'f05ip-j2')));
    r := qa.f05_rec(r, 21, 'C6 name taken by an active member (different case) → name_taken', 'name_taken',
      qa.f05_e(qa.f05_req(u_j2, c1, 'editor q', 'f05ip-j2')));
    r := qa.f05_rec(r, 22, 'C6 name taken by an active member (upper case + inner double space) → name_taken', 'name_taken',
      qa.f05_e(qa.f05_req(u_j2, c1, 'EDITOR  Q', 'f05ip-j2')));
    r := qa.f05_rec(r, 23, 'C6 name taken by the manager → name_taken', 'name_taken',
      qa.f05_e(qa.f05_req(u_j2, c1, 'דנה', 'f05ip-j2')));
    r := qa.f05_rec(r, 24, 'C6 empty name (spaces only) → name_invalid', 'name_invalid',
      qa.f05_e(qa.f05_req(u_j2, c1, '    ', 'f05ip-j2')));
    r := qa.f05_rec(r, 25, 'C6 41-char name → name_invalid', 'name_invalid',
      qa.f05_e(qa.f05_req(u_j2, c1, pg_catalog.repeat('א', 41), 'f05ip-j2')));
    r := qa.f05_rec(r, 26, 'C6 null name → name_invalid or invalid_request', 'name_invalid or invalid_request',
      qa.f05_e(qa.f05_req(u_j2, c1, null, 'f05ip-j2')));
    r := qa.f05_rec(r, 27, 'C6 refusals created no row', 'true', ((select count(*) from public.trip_members m where m.trip_id = t1) = n)::text);
    res := qa.f05_req(u_j2, c1, '  ' || pg_catalog.repeat('ב', 40) || '  ', 'f05ip-j2');
    r := qa.f05_rec(r, 28, 'C6 exactly 40 chars after trim → accepted (pending)', 'ok/pending/40',
      qa.f05_e(res) || '/' || coalesce(res->>'status', '∅') || '/' || coalesce(pg_catalog.char_length(res->>'display_name')::text, '∅'));
    r := qa.f05_rec(r, 29, 'C7 request with an unknown code → code_invalid', 'code_invalid',
      qa.f05_e(qa.f05_req(u_j6, 'ZZZZZZZZ', 'משה', 'f05ip-j6')));

    -- ================= C7 · rotated code =================
    update public.trip_join_codes set code = 'F5QAJNAR', version = version + 1, rotated_at = now() where trip_id = t1;
    r := qa.f05_rec(r, 30, 'C7 rotated: old code → code_invalid (preview / request)', 'code_invalid/code_invalid',
      qa.f05_e(qa.f05_prev(u_j6, c1, 'f05ip-j6')) || '/' || qa.f05_e(qa.f05_req(u_j6, c1, 'משה', 'f05ip-j6')));
    r := qa.f05_rec(r, 31, 'C7 rotated: the new code previews the same trip', 'ok/true',
      qa.f05_e(qa.f05_prev(u_j6, 'F5QAJNAR', 'f05ip-j6')) || '/' || ((qa.f05_prev(u_j6, 'F5QAJNAR', 'f05ip-j6')->>'trip_id') = t1::text)::text);
    update public.trip_join_codes set code = c1 where trip_id = t1;

    -- ================= C14 · RLS for a pending member =================
    r := qa.f05_rec(r, 40, 'C14 pending member reads 0 rows of trips / trip_kv / trip_countries / trip_currencies / trip_join_codes', '0 rows',
      qa.f05_count(u_j1, au, pg_catalog.format(
        'select 1 from public.trips where id = %1$L union all select 1 from public.trip_kv where trip_id = %1$L
         union all select 1 from public.trip_countries where trip_id = %1$L union all select 1 from public.trip_currencies where trip_id = %1$L
         union all select 1 from public.trip_join_codes where trip_id = %1$L', t1)));
    r := qa.f05_rec(r, 41, 'C14 pending member reads only its own trip_members row (Realtime filter id=eq.<member>)', '1 rows',
      qa.f05_count(u_j1, au, pg_catalog.format('select 1 from public.trip_members where trip_id = %L', t1)));
    r := qa.f05_rec(r, 42, 'C14 pending member cannot insert/update trip_members itself', 'error 42501',
      qa.f05_val(u_j1, au, pg_catalog.format('with u as (update public.trip_members set status = ''active'' where id = %L returning 1) select count(*)::text from u', mid)));
    r := qa.f05_rec(r, 43, 'C14 authenticated cannot insert a trip_members row', 'error 42501',
      qa.f05_val(u_o, au, pg_catalog.format('with i as (insert into public.trip_members(trip_id,user_id,display_name,role,status) values (%L,%L,''x'',''editor'',''active'') returning 1) select count(*)::text from i', t1, u_o)));
    r := qa.f05_rec(r, 44, 'C14 authenticated cannot read private.transfer_codes / private.join_attempts', 'error 42501',
      qa.f05_count(u_j1, au, 'select 1 from private.transfer_codes union all select 1 from private.join_attempts'));
    r := qa.f05_rec(r, 45, 'C14 anon cannot read private.join_attempts', 'error 42501',
      qa.f05_count(null, 'anon', 'select 1 from private.join_attempts'));
    r := qa.f05_rec(r, 46, 'C14 authenticated cannot write private.join_attempts / transfer_codes', 'error 42501',
      qa.f05_val(u_j1, au, 'with i as (insert into private.join_attempts(kind) values (''preview'') returning 1) select count(*)::text from i'));
    r := qa.f05_rec(r, 47, 'C14 authenticated cannot call join_request directly (service role only)', 'error 42501',
      qa.f05_val(u_o, au, pg_catalog.format('select public.join_request(%L::uuid, %L, ''x'', ''ip'')::text', u_o, c1)));
    r := qa.f05_rec(r, 48, 'C14 anon cannot call join_preview directly', 'error 42501',
      qa.f05_val(null, 'anon', pg_catalog.format('select public.join_preview(%L::uuid, %L, ''ip'')::text', u_o, c1)));
    r := qa.f05_rec(r, 49, 'C14 authenticated cannot call approve_member / claim_transfer directly', 'error 42501',
      qa.f05_val(u_m1, au, pg_catalog.format('select public.approve_member(%L::uuid, %L::uuid, ''approve'', ''editor'')::text', u_m1, mid)));

    -- ================= C12 · approve-member refusals =================
    r := qa.f05_rec(r, 50, 'C12 approve by an editor of the trip → not_manager', 'not_manager',
      qa.f05_e(qa.f05_appr(u_e1, mid, 'approve', 'editor')));
    r := qa.f05_rec(r, 51, 'C12 approve by a viewer of the trip → not_manager', 'not_manager',
      qa.f05_e(qa.f05_appr(u_v1, mid, 'approve', 'editor')));
    r := qa.f05_rec(r, 52, 'C12 approve by a manager of ANOTHER trip → not_manager', 'not_manager',
      qa.f05_e(qa.f05_appr(u_m2, mid, 'reject', null)));
    r := qa.f05_rec(r, 53, 'C12 approve by an outsider → not_manager', 'not_manager',
      qa.f05_e(qa.f05_appr(u_o, mid, 'approve', 'editor')));
    r := qa.f05_rec(r, 54, 'C12 the pending member approving itself → not_manager', 'not_manager',
      qa.f05_e(qa.f05_appr(u_j1, mid, 'approve', 'manager')));
    r := qa.f05_rec(r, 55, 'role outside viewer/editor/manager → role_invalid', 'role_invalid',
      qa.f05_e(qa.f05_appr(u_m1, mid, 'approve', 'owner')));
    r := qa.f05_rec(r, 56, 'unknown decision → invalid_request', 'invalid_request',
      qa.f05_e(qa.f05_appr(u_m1, mid, 'maybe', 'editor')));
    act := qa.f05_e(qa.f05_appr(u_m1, mid_e, 'approve', 'manager'));
    r := qa.f05_rec(r, 57, 'C12 approve an ACTIVE row (editor) → not_pending, row untouched', 'not_pending/editor',
      act || '/' || (select m.role from public.trip_members m where m.id = mid_e));
    act := qa.f05_e(qa.f05_appr(u_m1, mid_e, 'reject', null));
    r := qa.f05_rec(r, 58, 'C12 reject an ACTIVE row → not_pending, row kept', 'not_pending/1',
      act || '/' || (select count(*)::text from public.trip_members m where m.id = mid_e));
    r := qa.f05_rec(r, 59, 'unknown member id → not_pending or not_manager', 'not_pending or not_manager',
      qa.f05_e(qa.f05_appr(u_m1, 'f0500000-0000-4000-8000-0000000000ff', 'approve', 'editor')));
    r := qa.f05_rec(r, 60, 'refusals left the pending row as it was', '1',
      (select count(*)::text from public.trip_members m where m.id = mid and m.status = 'pending' and m.role = 'editor' and m.approved_at is null));

    -- ================= C4 · approve (chosen role) =================
    res := qa.f05_appr(u_m1b, mid, 'approve', 'viewer');
    r := qa.f05_rec(r, 61, 'C4 a second (later) manager approves as viewer → ok', 'ok', qa.f05_e(res));
    r := qa.f05_rec(r, 62, 'C4 row active, role viewer, approved_at set, same uid / name', '1',
      (select count(*)::text from public.trip_members m where m.id = mid and m.user_id = u_j1 and m.status = 'active'
          and m.role = 'viewer' and m.approved_at is not null and m.display_name = 'נועה כהן'));
    act := qa.f05_e(qa.f05_appr(u_m1, mid, 'approve', 'manager'));
    r := qa.f05_rec(r, 63, 'C11 second approve of the same row → not_pending, role unchanged', 'not_pending/viewer',
      act || '/' || (select m.role from public.trip_members m where m.id = mid));
    r := qa.f05_rec(r, 64, 'C4 approved member now reads the trip and its kv', '1 rows/2 rows',
      qa.f05_count(u_j1, au, pg_catalog.format('select 1 from public.trips where id = %L', t1)) || '/' ||
      qa.f05_count(u_j1, au, pg_catalog.format('select 1 from public.trip_kv where trip_id = %L', t1)));
    select count(*) into n from public.trip_members m where m.trip_id = t1;
    res := qa.f05_req(u_j1, c1, 'נועה כהן', 'f05ip-j1');
    r := qa.f05_rec(r, 65, 'C8 request by an already active identity → no new row, status active', 'true/active',
      ((select count(*) from public.trip_members m where m.trip_id = t1) = n)::text || '/' ||
      coalesce(res->>'status', res->'me'->>'status', qa.f05_e(res)));
    res := qa.f05_prev(u_j1, c1, 'f05ip-j1');
    r := qa.f05_rec(r, 66, 'C2 preview counts the new active member (5)', '5', coalesce(res->>'members', '∅'));
    -- approve as manager
    res := qa.f05_req(u_j6, c1, 'משה', 'f05ip-j6');
    mid2 := nullif(res->>'member_id', '')::uuid;
    res := qa.f05_appr(u_m1, mid2, 'approve', 'manager');
    r := qa.f05_rec(r, 67, 'C11 approve as manager stores role manager', 'ok/1',
      qa.f05_e(res) || '/' || (select count(*)::text from public.trip_members m where m.id = mid2 and m.role = 'manager' and m.status = 'active'));
    -- the 40-char pending of u_j2: approve with no role → default (editor)
    select m.id into mid2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_j2;
    res := qa.f05_appr(u_m1, mid2, 'approve', null);
    r := qa.f05_rec(r, 68, 'approve without role → trips.default_role (editor)', 'ok/editor',
      qa.f05_e(res) || '/' || (select m.role from public.trip_members m where m.id = mid2));
    -- default role viewer on T2; u_j5 is active elsewhere (D8)
    insert into public.trip_members (trip_id, user_id, display_name, role, status, approved_at) values (t1, u_j5, 'Five', 'editor', 'active', now());
    res := qa.f05_req(u_j5, c2, 'Five', 'f05ip-j5');
    mid2 := nullif(res->>'member_id', '')::uuid;
    r := qa.f05_rec(r, 69, 'D8 identity active in another trip can request (same name allowed in another trip); role = T2 default viewer',
      'ok/pending/viewer', qa.f05_e(res) || '/' || coalesce(res->>'status', '∅') || '/' || coalesce(res->>'role', '∅'));
    res := qa.f05_appr(u_m2, mid2, 'approve', null);
    r := qa.f05_rec(r, 70, 'approve without role on a viewer-default trip → viewer', 'ok/viewer',
      qa.f05_e(res) || '/' || (select m.role from public.trip_members m where m.id = mid2));
    r := qa.f05_rec(r, 71, 'C12 manager of T1 cannot approve rows of T2 (not_manager)', 'not_manager',
      qa.f05_e(qa.f05_appr(u_m1, mid2, 'approve', 'editor')));

    -- ================= C5 · reject / cancel / 3 per 24 h =================
    res := qa.f05_req(u_j3, c1, 'רוני', 'f05ip-j3');                                   -- request #1
    mid2 := nullif(res->>'member_id', '')::uuid;
    res := qa.f05_appr(u_m1, mid2, 'reject', null);
    r := qa.f05_rec(r, 80, 'C5 reject → ok, row deleted', 'ok/0',
      qa.f05_e(res) || '/' || (select count(*)::text from public.trip_members m where m.id = mid2));
    r := qa.f05_rec(r, 81, 'C5 reject of an already rejected (deleted) row → not_pending', 'not_pending or not_manager',
      qa.f05_e(qa.f05_appr(u_m1, mid2, 'reject', null)));
    res := qa.f05_prev(u_j3, c1, 'f05ip-j3');
    r := qa.f05_rec(r, 82, 'C5 after reject the identity previews as a stranger (me=null)', 'null', coalesce((res->'me')::text, 'null'));
    res := qa.f05_req(u_j3, c1, 'רוני', 'f05ip-j3');                                   -- request #2
    r := qa.f05_rec(r, 83, 'C5 a new request after reject works', 'ok/pending', qa.f05_e(res) || '/' || coalesce(res->>'status', '∅'));
    act := qa.f05_e(qa.f05_cancel(u_j3, t1));
    r := qa.f05_rec(r, 84, 'cancel own pending → ok, row deleted', 'ok/0',
      act || '/' || (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_j3));
    r := qa.f05_rec(r, 85, 'cancel with nothing pending → not_pending', 'not_pending',
      qa.f05_e(qa.f05_cancel(u_j3, t1)));
    act := qa.f05_e(qa.f05_cancel(u_e1, t1));
    r := qa.f05_rec(r, 86, 'cancel by an ACTIVE member → refused (not_pending), membership kept', 'not_pending/1',
      act || '/' || (select count(*)::text from public.trip_members m where m.id = mid_e and m.status = 'active'));
    r := qa.f05_rec(r, 87, 'cancel by a stranger of a trip → not_pending or not_member', 'not_pending or not_member',
      qa.f05_e(qa.f05_cancel(u_o, t1)));
    res := qa.f05_req(u_j3, c1, 'רוני', 'f05ip-j3');                                   -- request #3
    r := qa.f05_rec(r, 88, 'C5 3rd request within 24 h → ok', 'ok/pending', qa.f05_e(res) || '/' || coalesce(res->>'status', '∅'));
    perform qa.f05_appr(u_m1, nullif(res->>'member_id', '')::uuid, 'reject', null);
    select count(*) into n from private.join_attempts a where a.kind = 'request';
    res := qa.f05_req(u_j3, c1, 'רוני', 'f05ip-j3b');                                  -- request #4 (other ip)
    r := qa.f05_rec(r, 89, 'C5 4th request within 24 h → rate_limited (returned), no row', 'rate_limited/0',
      qa.f05_e(res) || '/' || (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_j3));
    r := qa.f05_rec(r, 90, '§2.3 the refused attempt is kept in join_attempts (not rolled back by a raise)', 'true',
      ((select count(*) from private.join_attempts a where a.kind = 'request') > n)::text);
    r := qa.f05_rec(r, 91, 'the 3-per-24h limit is per trip: the same identity can request another trip', 'ok',
      qa.f05_e(qa.f05_req(u_j3, c2, 'רוני', 'f05ip-j3c')));
    update private.join_attempts a set at = a.at - interval '25 hours' where a.kind = 'request' and a.user_id = u_j3 and a.trip_id = t1;
    res := qa.f05_req(u_j3, c1, 'רוני', 'f05ip-j3');
    r := qa.f05_rec(r, 92, 'C5 after 24 h (attempts back-dated 25 h) → allowed again', 'ok/pending', qa.f05_e(res) || '/' || coalesce(res->>'status', '∅'));
    -- refused requests (name_taken) are not "requests" in the D6 sense
    for k in 1..3 loop perform qa.f05_req(u_j7, c1, 'דנה', 'f05ip-j7'); end loop;
    res := qa.f05_req(u_j7, c1, 'שבע', 'f05ip-j7');
    r := qa.f05_rec(r, 93, 'D6 three name_taken refusals do not use up the 3 requests/24 h (4th call with a free name → ok)', 'ok/pending',
      qa.f05_e(res) || '/' || coalesce(res->>'status', '∅'));

    -- ================= C8 · removed =================
    insert into public.trip_members (trip_id, user_id, display_name, role, status, approved_at) values (t1, u_j4, 'הוסר', 'editor', 'removed', now());
    res := qa.f05_prev(u_j4, c1, 'f05ip-j4');
    r := qa.f05_rec(r, 100, 'C8 preview by a removed identity → member_removed (error or me.status)', 'member_removed or removed',
      case when res ? 'error' then res->>'error' else coalesce(res->'me'->>'status', qa.f05_e(res)) end);
    res := qa.f05_req(u_j4, c1, 'שם חדש', 'f05ip-j4');
    r := qa.f05_rec(r, 101, 'C8 request by a removed identity → member_removed, row stays removed', 'member_removed/removed',
      qa.f05_e(res) || '/' || (select m.status from public.trip_members m where m.trip_id = t1 and m.user_id = u_j4));
    r := qa.f05_rec(r, 102, 'D5 the name of a removed member is free (unique among pending+active only)', 'ok',
      qa.f05_e(qa.f05_req(u_o, c1, 'הוסר', 'f05ip-o')));
    perform qa.f05_cancel(u_o, t1);
    r := qa.f05_rec(r, 103, 'C14 removed member reads 0 rows of trips / trip_kv', '0 rows',
      qa.f05_count(u_j4, au, pg_catalog.format('select 1 from public.trips where id = %1$L union all select 1 from public.trip_kv where trip_id = %1$L', t1)));

    -- ================= §2.4 · rate limits =================
    -- requests: 10 per ip_hash per hour (any outcome)
    for k in 1..10 loop perform qa.f05_req(pg_catalog.gen_random_uuid(), 'ZZZZZZZZ', 'x' || k, 'f05ip-flood'); end loop;
    r := qa.f05_rec(r, 110, '§2.4 11th request from one ip_hash within an hour → rate_limited', 'rate_limited',
      qa.f05_e(qa.f05_req(u_o, c1, 'Flood', 'f05ip-flood')));
    r := qa.f05_rec(r, 111, '§2.4 the same identity from another ip_hash → allowed', 'ok',
      qa.f05_e(qa.f05_req(u_o, c1, 'Flood', 'f05ip-other')));
    perform qa.f05_cancel(u_o, t1);
    update private.join_attempts a set at = a.at - interval '61 minutes' where a.ip_hash = 'f05ip-flood';
    r := qa.f05_rec(r, 112, '§2.4 ip window over (attempts back-dated 61 min) → allowed', 'ok',
      qa.f05_e(qa.f05_req(u_o, c1, 'Flood', 'f05ip-flood')));
    perform qa.f05_cancel(u_o, t1);
    -- 20 pending per trip
    for k in 1..19 loop
      g := pg_catalog.gen_random_uuid();
      insert into auth.users (id) values (g);
      insert into public.trip_members (trip_id, user_id, display_name, role, status) values (t3, g, 'pend' || k, 'editor', 'pending');
    end loop;
    res := qa.f05_req(u_j6, c3, 'עשרים', 'f05ip-cap1');
    r := qa.f05_rec(r, 113, '§2.4 the 20th pending row of a trip is accepted', 'ok/pending', qa.f05_e(res) || '/' || coalesce(res->>'status', '∅'));
    res := qa.f05_req(u_j7, c3, 'עשרים ואחת', 'f05ip-cap2');
    r := qa.f05_rec(r, 114, '§2.4 a 21st pending row → rate_limited, no row', 'rate_limited/20',
      qa.f05_e(res) || '/' || (select count(*)::text from public.trip_members m where m.trip_id = t3 and m.status = 'pending'));
    -- previews: 30 per user per hour
    for k in 1..30 loop perform qa.f05_prev(u_p, c1, 'f05ip-p' || k); end loop;
    r := qa.f05_rec(r, 115, '§2.4 31st preview by one identity within an hour → rate_limited', 'rate_limited',
      qa.f05_e(qa.f05_prev(u_p, c1, 'f05ip-pX')));
    update private.join_attempts a set at = a.at - interval '61 minutes' where a.user_id = u_p and a.kind = 'preview';
    r := qa.f05_rec(r, 116, '§2.4 preview window over (back-dated 61 min) → allowed', 'ok',
      qa.f05_e(qa.f05_prev(u_p, c1, 'f05ip-pY')));
    -- previews: 60 per ip_hash per hour
    for k in 1..60 loop perform qa.f05_prev(pg_catalog.gen_random_uuid(), c1, 'f05ip-pflood'); end loop;
    r := qa.f05_rec(r, 117, '§2.4 61st preview from one ip_hash within an hour → rate_limited', 'rate_limited',
      qa.f05_e(qa.f05_prev(u_o, c1, 'f05ip-pflood')));

    -- ================= C9 · transfer =================
    -- u_j1 = active viewer "נועה כהן" in T1 (member id mid)
    r := qa.f05_rec(r, 120, 'C9 issue_transfer by a non-member → not_member', 'not_member',
      qa.f05_e(qa.f05_issue(u_o, t1)));
    res := qa.f05_req(u_t3, c1, 'ממתין', 'f05ip-t3');
    r := qa.f05_rec(r, 121, 'C9 issue_transfer by a PENDING member → refused (only active members)', 'not_member or not_pending',
      qa.f05_e(qa.f05_issue(u_t3, t1)));
    perform qa.f05_cancel(u_t3, t1);
    r := qa.f05_rec(r, 122, 'C9 issue_transfer by a REMOVED member → refused', 'not_member or member_removed',
      qa.f05_e(qa.f05_issue(u_j4, t1)));
    res := qa.f05_issue(u_j1, t1); tc := res->>'code';
    r := qa.f05_rec(r, 123, 'C9 issue_transfer → 6 digits, expires in ~24 h', 'ok/true/true',
      qa.f05_e(res) || '/' || coalesce(tc ~ '^[0-9]{6}$', false)::text || '/' ||
      coalesce((res->>'expires_at')::timestamptz between now() + interval '23 hours 55 minutes' and now() + interval '24 hours 5 minutes', false)::text);
    r := qa.f05_rec(r, 124, '§2.1 the plain code is not stored; code_hash is 64 hex', '0/1',
      (select count(*)::text from private.transfer_codes x where x.code_hash = tc or x.code_hash like '%' || tc || '%') || '/' ||
      (select count(*)::text from private.transfer_codes x where x.member_id = mid and x.used_at is null and x.code_hash ~ '^[0-9a-f]{64}$'));
    res := qa.f05_issue(u_j1, t1); tc2 := res->>'code';
    r := qa.f05_rec(r, 125, 'C9 re-issue → a new code; exactly one unused code left for the member', 'ok/1',
      qa.f05_e(res) || '/' || (select count(*)::text from private.transfer_codes x where x.member_id = mid and x.used_at is null and x.expires_at > now()));
    if tc is distinct from tc2 then
      r := qa.f05_rec(r, 126, 'C9 the earlier unused code is void → transfer_invalid', 'transfer_invalid',
        qa.f05_e(qa.f05_claim(u_t2, tc, 'f05ip-t2')));
    else
      r := qa.f05_rec(r, 126, 'C9 the earlier unused code is void (codes collided — 1 in 10⁶; not testable this run)', 'ok', 'ok');
    end if;
    res := qa.f05_claim(u_t1, tc2, 'f05ip-t1');
    r := qa.f05_rec(r, 127, 'C9 claim from a second identity → ok, returns the trip', 'ok/true', qa.f05_e(res) || '/' || ((res->>'trip_id') = t1::text)::text);
    r := qa.f05_rec(r, 128, 'C9 membership moved: same member id, new uid, name / role / status kept', '1',
      (select count(*)::text from public.trip_members m where m.id = mid and m.user_id = u_t1 and m.display_name = 'נועה כהן'
          and m.role = 'viewer' and m.status = 'active' and m.approved_at is not null));
    r := qa.f05_rec(r, 129, 'C9 the old identity has no row in the trip and reads 0 rows of trips / trip_kv', '0/0 rows',
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_j1) || '/' ||
      qa.f05_count(u_j1, au, pg_catalog.format('select 1 from public.trips where id = %1$L union all select 1 from public.trip_kv where trip_id = %1$L', t1)));
    r := qa.f05_rec(r, 130, 'C9 the new identity reads the trip', '1 rows',
      qa.f05_count(u_t1, au, pg_catalog.format('select 1 from public.trips where id = %L', t1)));
    r := qa.f05_rec(r, 131, 'C9 the code is marked used', '1',
      (select count(*)::text from private.transfer_codes x where x.member_id = mid and x.used_at is not null));
    r := qa.f05_rec(r, 132, 'C9 second claim of the same code → transfer_invalid', 'transfer_invalid',
      qa.f05_e(qa.f05_claim(u_t2, tc2, 'f05ip-t2')));
    r := qa.f05_rec(r, 133, 'C9 the old identity can no longer issue a code for the trip', 'not_member',
      qa.f05_e(qa.f05_issue(u_j1, t1)));
    -- expired
    res := qa.f05_issue(u_t1, t1); tc := res->>'code';
    update private.transfer_codes x set expires_at = now() - interval '1 second' where x.member_id = mid and x.used_at is null;
    act := qa.f05_e(qa.f05_claim(u_t2, tc, 'f05ip-t2'));
    r := qa.f05_rec(r, 134, 'C9 expired code → transfer_invalid, membership not moved', 'transfer_invalid/1',
      act || '/' ||
      (select count(*)::text from public.trip_members m where m.id = mid and m.user_id = u_t1));
    -- already_member
    res := qa.f05_issue(u_t1, t1); tc := res->>'code';
    act := qa.f05_e(qa.f05_claim(u_e1, tc, 'f05ip-e1'));
    r := qa.f05_rec(r, 135, 'C9 claim by an identity that already has a row in the trip → already_member, nothing moved', 'already_member/1/1',
      act || '/' ||
      (select count(*)::text from public.trip_members m where m.id = mid and m.user_id = u_t1) || '/' ||
      (select count(*)::text from public.trip_members m where m.id = mid_e and m.user_id = u_e1));
    act := qa.f05_e(qa.f05_claim(u_m2, tc, 'f05ip-m2'));
    r := qa.f05_rec(r, 136, 'D8 claim by an identity active in ANOTHER trip → ok (adds a trip)', 'ok/true',
      act || '/' ||
      ((select count(*) from public.trip_members m where m.user_id = u_m2 and m.status = 'active') = 3)::text);
    -- claim rate limit: 5 failed per identity per hour → the 6th (wrong) claim is rate_limited
    for k in 1..5 loop
      act := qa.f05_e(qa.f05_claim(u_t3, pg_catalog.lpad(k::text, 6, '9'), 'f05ip-t3-' || k));
    end loop;
    r := qa.f05_rec(r, 137, 'C9 5th wrong claim is still transfer_invalid', 'transfer_invalid', act);
    r := qa.f05_rec(r, 138, 'C9 6th wrong claim within an hour → rate_limited', 'rate_limited',
      qa.f05_e(qa.f05_claim(u_t3, '999990', 'f05ip-t3-6')));
    res := qa.f05_issue(u_m2, t1); tc := res->>'code';
    act := qa.f05_e(qa.f05_claim(u_t3, tc, 'f05ip-t3-7'));
    r := qa.f05_rec(r, 139, 'C9 while limited even a valid code → rate_limited, nothing moved', 'rate_limited/1',
      act || '/' ||
      (select count(*)::text from public.trip_members m where m.id = mid and m.user_id = u_m2));
    update private.join_attempts a set at = a.at - interval '61 minutes' where a.kind = 'claim' and a.user_id = u_t3;
    r := qa.f05_rec(r, 140, 'C9 failed claims back-dated 61 min → the valid code works', 'ok',
      qa.f05_e(qa.f05_claim(u_t3, tc, 'f05ip-t3-8')));
    -- 20 failed per ip_hash per hour
    for k in 1..20 loop perform qa.f05_claim(pg_catalog.gen_random_uuid(), '000000', 'f05ip-cflood'); end loop;
    res := qa.f05_issue(u_t3, t1); tc := res->>'code';
    r := qa.f05_rec(r, 141, '§2.4 21st claim from an ip_hash with 20 failures in the hour → rate_limited', 'rate_limited',
      qa.f05_e(qa.f05_claim(u_t2, tc, 'f05ip-cflood')));
    r := qa.f05_rec(r, 142, 'malformed code → transfer_invalid', 'transfer_invalid',
      qa.f05_e(qa.f05_claim(u_t2, 'abcdef', 'f05ip-t2x')));
    -- manager transfer (the earliest manager moves to a new identity)
    res := qa.f05_issue(u_m1, t1); tc := res->>'code';
    res := qa.f05_claim(u_t4, tc, 'f05ip-t4');
    r := qa.f05_rec(r, 143, 'C9 a manager''s membership transfers (role manager kept, same member id)', 'ok/1',
      qa.f05_e(res) || '/' || (select count(*)::text from public.trip_members m where m.id = mid_m1 and m.user_id = u_t4 and m.role = 'manager' and m.status = 'active'));
    r := qa.f05_rec(r, 144, 'the moved manager can approve with the new identity; the old one cannot', 'not_manager/ok',
      qa.f05_e(qa.f05_appr(u_m1, (select m.id from public.trip_members m where m.trip_id = t1 and m.user_id = u_j7), 'approve', 'editor')) || '/' ||
      qa.f05_e(qa.f05_appr(u_t4, (select m.id from public.trip_members m where m.trip_id = t1 and m.user_id = u_j7), 'approve', 'editor')));

    execute 'reset role';
    raise exception 'f05_rollback';
  exception when others then
    if sqlerrm <> 'f05_rollback' then
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
  r := qa.f05_rec(r, 200, '§2.3 the six entry functions exist in public, security definer, search_path=''''', '6/6/6',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member')) || '/' ||
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member') and p.prosecdef) || '/' ||
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member')
        and p.proconfig @> array['search_path=""']));
  r := qa.f05_rec(r, 201, '§2.3 C14 anon / authenticated / PUBLIC cannot execute any F05 function (public entry + private helpers)', '0',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where ((s.nspname = 'public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member'))
             or s.nspname = 'private')
        and (pg_catalog.has_function_privilege('anon', p.oid, 'execute') or pg_catalog.has_function_privilege('authenticated', p.oid, 'execute')
             or exists (select 1 from pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
                         where a.grantee = 0 and a.privilege_type = 'EXECUTE'))));
  r := qa.f05_rec(r, 202, '§2.3 service_role can execute the six entry functions', '6',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member')
        and pg_catalog.has_function_privilege('service_role', p.oid, 'execute')));
  r := qa.f05_rec(r, 203, '§2.0 schema private: no usage / create for anon, authenticated, PUBLIC', 'false/false/false/false',
    pg_catalog.has_schema_privilege('anon', 'private', 'usage')::text || '/' ||
    pg_catalog.has_schema_privilege('authenticated', 'private', 'usage')::text || '/' ||
    pg_catalog.has_schema_privilege('authenticated', 'private', 'create')::text || '/' ||
    coalesce((select bool_or(a.grantee = 0) from pg_catalog.pg_namespace s, pg_catalog.aclexplode(coalesce(s.nspacl, pg_catalog.acldefault('n', s.nspowner))) a
               where s.nspname = 'private'), false)::text);
  r := qa.f05_rec(r, 204, '§2.1–2.2 private holds transfer_codes + join_attempts, RLS on, no policies', 'join_attempts,transfer_codes/true/0',
    (select string_agg(c.relname, ',' order by c.relname) from pg_catalog.pg_class c join pg_catalog.pg_namespace s on s.oid = c.relnamespace
      where s.nspname = 'private' and c.relkind = 'r' and c.relname in ('transfer_codes', 'join_attempts')) || '/' ||
    (select bool_and(c.relrowsecurity)::text from pg_catalog.pg_class c join pg_catalog.pg_namespace s on s.oid = c.relnamespace
      where s.nspname = 'private' and c.relname in ('transfer_codes', 'join_attempts')) || '/' ||
    (select count(*)::text from pg_catalog.pg_policies p where p.schemaname = 'private'));
  r := qa.f05_rec(r, 205, '§2.1–2.2 C14 no table privilege on the private tables for anon / authenticated', 'false',
    (select bool_or(pg_catalog.has_table_privilege(g, c.oid, 'select,insert,update,delete'))::text
       from pg_catalog.pg_class c join pg_catalog.pg_namespace s on s.oid = c.relnamespace, unnest(array['anon','authenticated']) g
      where s.nspname = 'private' and c.relkind = 'r'));
  r := qa.f05_rec(r, 206, '§2.1 transfer_codes: partial unique index on code_hash where used_at is null; member_id indexed; FK cascade', 'true/true/c',
    (select bool_or(pg_catalog.pg_get_indexdef(i.indexrelid) ilike '%unique%(code_hash)%where%used_at is null%')::text
       from pg_catalog.pg_index i where i.indrelid = 'private.transfer_codes'::regclass) || '/' ||
    (select bool_or(pg_catalog.pg_get_indexdef(i.indexrelid) ilike '%(member_id)%')::text
       from pg_catalog.pg_index i where i.indrelid = 'private.transfer_codes'::regclass) || '/' ||
    coalesce((select c.confdeltype::text from pg_catalog.pg_constraint c where c.conrelid = 'private.transfer_codes'::regclass and c.contype = 'f'
               and c.confrelid = 'public.trip_members'::regclass), '∅'));
  r := qa.f05_rec(r, 207, '§2.2 join_attempts.kind restricted to preview/request/claim', 'error 23514',
    qa.f05_val(null, 'postgres', 'with i as (insert into private.join_attempts(kind) values (''other'') returning 1) select count(*)::text from i'));
  r := qa.f05_rec(r, 208, '§2.5 public still holds exactly the 9 F01 tables', '9',
    (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public'));
  r := qa.f05_rec(r, 209, '§2.5 C14 no new policy on existing tables (public policies = the alpha.5.1 set)',
    'platform_admins:platform_admins_select_own:SELECT,trip_countries:trip_countries_delete_manager:DELETE,trip_countries:trip_countries_insert_manager:INSERT,trip_countries:trip_countries_select_member:SELECT,trip_countries:trip_countries_update_manager:UPDATE,trip_currencies:trip_currencies_delete_manager:DELETE,trip_currencies:trip_currencies_insert_manager:INSERT,trip_currencies:trip_currencies_select_member:SELECT,trip_currencies:trip_currencies_update_manager:UPDATE,trip_join_codes:trip_join_codes_select_manager:SELECT,trip_kv:trip_kv_delete_editor:DELETE,trip_kv:trip_kv_insert_editor:INSERT,trip_kv:trip_kv_select_member:SELECT,trip_kv:trip_kv_update_editor:UPDATE,trip_members:trip_members_select:SELECT,trips:trips_select_member:SELECT,trips:trips_update_manager:UPDATE',
    (select string_agg(p.tablename || ':' || p.policyname || ':' || p.cmd, ',' order by p.tablename, p.policyname)
       from pg_catalog.pg_policies p where p.schemaname = 'public'));
  r := qa.f05_rec(r, 210, '§2.5 C14 no new grant on existing tables for anon / authenticated / PUBLIC (= the alpha.5.1 set)',
    'platform_admins:authenticated:SELECT;trip_countries:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_currencies:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_join_codes:authenticated:SELECT;trip_kv:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_members:authenticated:SELECT;trips:authenticated:SELECT',
    (select string_agg(x, ';' order by x) from (
       select g.table_name || ':' || g.grantee || ':' || string_agg(g.privilege_type, ',' order by g.privilege_type) as x
         from information_schema.role_table_grants g
        where g.table_schema = 'public' and g.grantee in ('anon', 'authenticated', 'PUBLIC')
        group by g.table_name, g.grantee) q));
  r := qa.f05_rec(r, 211, '§2.5 trip_members not writable by clients (no insert/update/delete grant)', 'false',
    (pg_catalog.has_table_privilege('authenticated', 'public.trip_members', 'insert,update,delete')
     or pg_catalog.has_table_privilege('anon', 'public.trip_members', 'insert,update,delete'))::text);
  r := qa.f05_rec(r, 212, '§1.2 / §1.5 trip_members is in the supabase_realtime publication (live updates)', '1 rows or 0 rows (no publication)',
    (select case when not exists (select 1 from pg_catalog.pg_publication where pubname = 'supabase_realtime') then '0 rows (no publication)'
                 else (select count(*) || ' rows' from pg_catalog.pg_publication_tables t
                        where t.pubname = 'supabase_realtime' and t.schemaname = 'public' and t.tablename = 'trip_members') end));
  r := qa.f05_rec(r, 213, 'Leftovers after the run: 0 f05 users / trips / attempts / codes', '0/0/true/true',
    (select count(*) from auth.users u where u.id::text like 'f0500000-%')::text || '/' ||
    (select count(*) from public.trips t where t.name like 'F05 %')::text || '/' ||
    ((select count(*) from private.join_attempts) <= n_att_before)::text || '/' ||
    ((select count(*) from private.transfer_codes) = n_tc_before and (select count(*) from public.trips) = n_trips_before)::text);

  return query
    select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail'
      from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
