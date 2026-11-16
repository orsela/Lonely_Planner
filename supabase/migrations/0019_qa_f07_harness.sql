-- Lonely Planner QA · F07 DB-level test harness · version 3.0.0-alpha.16 · F07 (QA 1.0.0)
-- CHANGE 2026-11-16 F07-QA-01: first version (no previous version). Installs qa.f07_run() in the locked `qa` schema, same
--   pattern as F01–F06: all data lives in a sub-transaction that is always rolled back (raise 'f07_rollback'), search_path
--   pinned to '', nothing granted to public/anon/authenticated, SECURITY INVOKER (runs as postgres, the owner of the F07
--   functions; PostgreSQL forbids SET ROLE inside SECURITY DEFINER). Calls use NAMED arguments as in docs/F07_spec.md §2.
--
-- Run (after 0018_f07.sql):   select * from qa.f07_run() order by id;
-- Output: one row per scenario (id, name, pass, detail = 'expected: … | actual: …'). Each name starts with the spec §4
-- acceptance number(s) it covers (AC1 … AC13) or the ruling (C5, C8 …). Time windows are exercised by back-dating rows.
-- Criteria covered here (DB side): 1–9, 10 (the session / notice rows), 12, 13; 11 and 14–15 belong to the client.
-- A refusal must be RETURNED as {"error":code}; a raised exception is reported as {"raised":…} and fails the scenario.

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

create or replace function qa.f07_as(p_uid uuid, p_role text)
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

-- rows returned by p_sql while impersonating ('N rows' | 'error <sqlstate> …')
create or replace function qa.f07_count(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f07_as(p_uid, p_role);
  execute 'select count(*) from (' || p_sql || ') f07_s' into n;
  execute 'reset role';
  return n || ' rows';
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 120);
end $f$;

-- a service-role call: p_expr is a SQL expression returning jsonb (named arguments as in the spec)
create or replace function qa.f07_j(p_expr text)
returns jsonb language plpgsql set search_path = '' as $f$
declare v jsonb;
begin
  execute 'select ' || p_expr into v;
  return v;
exception when others then
  return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm);
end $f$;

create or replace function qa.f07_e(p jsonb)
returns text language sql immutable set search_path = '' as $f$
  select case when p is null then 'null' when p ? 'raised' then 'raised ' || (p->>'raised')
              when p ? 'error' then p->>'error' else 'ok' end
$f$;

-- 'status/role/name' of a member row
create or replace function qa.f07_row(p_member uuid)
returns text language sql stable set search_path = '' as $f$
  select coalesce((select m.status || '/' || m.role || '/' || m.display_name from public.trip_members m where m.id = p_member), '∅')
$f$;

create or replace function qa.f07_rec(r jsonb, p_id int, p_name text, p_exp text, p_act text)
returns jsonb language plpgsql set search_path = '' as $f$
begin
  return r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
    'id', p_id, 'name', p_name, 'detail', 'expected: ' || p_exp || ' | actual: ' || coalesce(p_act, '(null)'),
    'pass', p_act is not null and (p_act = p_exp or (position(' or ' in p_exp) > 0 and p_act = any (pg_catalog.string_to_array(p_exp, ' or '))))));
end $f$;

create or replace function qa.f07_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r   jsonb := '[]'::jsonb;
  au  constant text := 'authenticated';
  u_a1 constant uuid := 'f0700000-0000-4000-8000-0000000000a1';  -- T1 manager "דנה", device 1
  u_a2 constant uuid := 'f0700000-0000-4000-8000-0000000000a2';  -- T1 manager "דנה", device 2 (same person)
  u_b1 constant uuid := 'f0700000-0000-4000-8000-0000000000b1';  -- T1 manager "אבי" (single device)
  u_e1 constant uuid := 'f0700000-0000-4000-8000-0000000000c1';  -- T1 editor "עדן" (single device)
  u_v1 constant uuid := 'f0700000-0000-4000-8000-0000000000d1';  -- T1 viewer "צופה", device 1
  u_v2 constant uuid := 'f0700000-0000-4000-8000-0000000000d2';  -- T1 viewer "צופה", device 2
  u_x1 constant uuid := 'f0700000-0000-4000-8000-0000000000e1';  -- T1 removed person "הוסר"
  u_n1 constant uuid := 'f0700000-0000-4000-8000-0000000000f1';  -- fresh identity (the member's new phone)
  u_n2 constant uuid := 'f0700000-0000-4000-8000-0000000000f2';  -- another fresh identity
  u_n3 constant uuid := 'f0700000-0000-4000-8000-0000000000f3';  -- another fresh identity (name / limits)
  u_o  constant uuid := 'f0700000-0000-4000-8000-000000000e01';  -- outsider (no trip)
  u_m2 constant uuid := 'f0700000-0000-4000-8000-000000000b02';  -- T2 manager
  u_e9 constant uuid := 'f0700000-0000-4000-8000-000000000b03';  -- T2 editor "Tom"
  u_s1 constant uuid := 'f0700000-0000-4000-8000-000000000c11';  -- T3 sole manager "סולו", device 1
  u_s2 constant uuid := 'f0700000-0000-4000-8000-000000000c12';  -- T3 sole manager "סולו", device 2
  u_s3 constant uuid := 'f0700000-0000-4000-8000-000000000c13';  -- T3 editor "עורך"
  u_t1 constant uuid := 'f0700000-0000-4000-8000-000000000d11';  -- identity that claims a transfer code
  t1 constant uuid := 'f0700000-0000-4000-8000-00000000f001';
  t2 constant uuid := 'f0700000-0000-4000-8000-00000000f002';
  t3 constant uuid := 'f0700000-0000-4000-8000-00000000f003';
  c1 constant text := 'F7QAJNAA';
  c2 constant text := 'F7QAJNBB';
  s_a  constant uuid := 'f0700000-0000-4000-8000-0000005e0001';  -- session ids
  s_b  constant uuid := 'f0700000-0000-4000-8000-0000005e0002';
  s_c  constant uuid := 'f0700000-0000-4000-8000-0000005e0003';
  s_d  constant uuid := 'f0700000-0000-4000-8000-0000005e0004';
  unknown constant uuid := 'f0700000-0000-4000-8000-0000000000ff';
  mid_a1 uuid; mid_a2 uuid; mid_b1 uuid; mid_e1 uuid; mid_v1 uuid; mid_v2 uuid; mid_x1 uuid; mid_n1 uuid; mid_n2 uuid;
  mid_s1 uuid; mid_s2 uuid; mid_s3 uuid; mid_e9 uuid;
  p_a uuid; p_e uuid; p_v uuid; p_x uuid; p_t2 uuid; p_s uuid;
  res jsonb; res2 jsonb; act text; act2 text; k int; ts timestamptz;
  n_trips_before bigint; n_att_before bigint; n_tc_before bigint; n_users_before bigint;
  has_auth_sessions boolean;
  v_gone text;
begin
  select count(*) into n_trips_before from public.trips;
  select count(*) into n_att_before from private.join_attempts;
  select count(*) into n_tc_before from private.transfer_codes;
  select count(*) into n_users_before from auth.users;
  has_auth_sessions := pg_catalog.to_regclass('auth.sessions') is not null;

  begin
    -- ================= SETUP (postgres, bypasses RLS) =================
    perform qa.f07_as(null, 'postgres');
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at)
      select u, 'authenticated', 'authenticated', null, '00000000-0000-0000-0000-000000000000', now(), now()
        from unnest(array[u_a1, u_a2, u_b1, u_e1, u_v1, u_v2, u_x1, u_n1, u_n2, u_n3, u_o, u_m2, u_e9, u_s1, u_s2, u_s3, u_t1]) u;
    insert into public.trips (id, name, start_date, end_date, default_role, created_by) values
      (t1, 'F07 יפן 2027', '2027-04-03', '2027-04-20', 'editor', u_a1),
      (t2, 'F07 קבוצה 2',  '2027-05-30', '2027-06-02', 'viewer', u_m2),
      (t3, 'F07 סולו',     '2027-07-01', '2027-07-03', 'editor', u_s1);
    insert into public.trip_join_codes (trip_id, code, version, rotated_at) values
      (t1, c1, 1, now() - interval '1 day'), (t2, c2, 1, now() - interval '1 day'), (t3, 'F7QAJNCC', 1, now() - interval '1 day');
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at) values
      (t1, u_a1, 'דנה',   'manager', 'active',  now() - interval '90 days', now() - interval '90 days'),
      (t1, u_b1, 'אבי',   'manager', 'active',  now() - interval '80 days', now() - interval '80 days'),
      (t1, u_e1, 'עדן',   'editor',  'active',  now() - interval '70 days', now() - interval '70 days'),
      (t1, u_v1, 'צופה',  'viewer',  'active',  now() - interval '60 days', now() - interval '60 days'),
      (t1, u_x1, 'הוסר',  'editor',  'removed', now() - interval '50 days', now() - interval '50 days'),
      (t2, u_m2, 'מנהל2', 'manager', 'active',  now() - interval '20 days', now() - interval '20 days'),
      (t2, u_e9, 'Tom',   'editor',  'active',  now() - interval '18 days', now() - interval '18 days'),
      (t3, u_s1, 'סולו',  'manager', 'active',  now() - interval '10 days', now() - interval '10 days'),
      (t3, u_s3, 'עורך',  'editor',  'active',  now() - interval '9 days',  now() - interval '9 days');
    select m.id, m.person_id into mid_a1, p_a from public.trip_members m where m.trip_id = t1 and m.user_id = u_a1;
    select m.id, m.person_id into mid_e1, p_e from public.trip_members m where m.trip_id = t1 and m.user_id = u_e1;
    select m.id, m.person_id into mid_v1, p_v from public.trip_members m where m.trip_id = t1 and m.user_id = u_v1;
    select m.id, m.person_id into mid_x1, p_x from public.trip_members m where m.trip_id = t1 and m.user_id = u_x1;
    select m.id into mid_b1 from public.trip_members m where m.trip_id = t1 and m.user_id = u_b1;
    select m.id, m.person_id into mid_e9, p_t2 from public.trip_members m where m.trip_id = t2 and m.user_id = u_e9;
    select m.id, m.person_id into mid_s1, p_s from public.trip_members m where m.trip_id = t3 and m.user_id = u_s1;
    select m.id into mid_s3 from public.trip_members m where m.trip_id = t3 and m.user_id = u_s3;
    -- second device rows of the same persons (what an approved relink produces)
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at, person_id) values
      (t1, u_a2, 'דנה',   'manager', 'active', now() - interval '30 days', now() - interval '30 days', p_a),
      (t1, u_v2, 'צופה',  'viewer',  'active', now() - interval '29 days', now() - interval '29 days', p_v),
      (t3, u_s2, 'סולו',  'manager', 'active', now() - interval '8 days',  now() - interval '8 days',  p_s);
    select m.id into mid_a2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_a2;
    select m.id into mid_v2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_v2;
    select m.id into mid_s2 from public.trip_members m where m.trip_id = t3 and m.user_id = u_s2;
    insert into public.trip_kv (trip_id, key, value, updated_by) values (t1, 'trip', '[]', null);

    -- ================= 0xx · schema (C1) =================
    r := qa.f07_rec(r, 1, 'C1 person_id is set on insert (= own id) and is never null', 'true/true/0',
      ((select m.person_id = m.id from public.trip_members m where m.id = mid_e1))::text || '/' ||
      ((select m.person_id = p_a from public.trip_members m where m.id = mid_a2))::text || '/' ||
      (select count(*) from public.trip_members m where m.person_id is null)::text);
    r := qa.f07_rec(r, 2, 'C3 member_sessions: closed schema, RLS on, no policy, no client grant', 'true/0/false',
      (select c.relrowsecurity::text from pg_catalog.pg_class c where c.oid = 'private.member_sessions'::regclass) || '/' ||
      (select count(*)::text from pg_catalog.pg_policies p where p.schemaname = 'private' and p.tablename = 'member_sessions') || '/' ||
      pg_catalog.has_table_privilege('authenticated', 'private.member_sessions', 'select')::text);

    -- ================= 1xx · relink request (AC1, AC3, AC4, AC12, AC13, C5, C7) =================
    res := qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, c1, 'ip-n1'));
    r := qa.f07_rec(r, 101, 'AC4 preview lists ACTIVE persons only (names, one per person), no roles, members = persons', '4/true/0/false/4',
      jsonb_array_length(res->'people')::text || '/' ||
      (select bool_and(e ? 'person_id' and e ? 'display_name') from jsonb_array_elements(res->'people') e)::text || '/' ||
      (select count(*) from jsonb_array_elements(res->'people') e where e ? 'role' or e->>'person_id' = p_x::text)::text || '/' ||
      (res ? 'relink' and res->'relink' <> 'null'::jsonb)::text || '/' || (res->>'members'));
    r := qa.f07_rec(r, 102, 'AC4 an invalid / rotated code returns no names', 'code_invalid/false',
      qa.f07_e(qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, 'ZZZZZZZZ', 'ip-n1'))) || '/' ||
      (qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, 'ZZZZZZZZ', 'ip-n1')) ? 'people')::text);
    res := qa.f07_j(format('public.join_request(p_user => %L, p_code => %L, p_name => %L, p_ip => %L, p_person => %L)',
                           u_n1, c1, null, 'ip-n1', p_e));
    select m.id into mid_n1 from public.trip_members m where m.trip_id = t1 and m.user_id = u_n1;
    r := qa.f07_rec(r, 103, 'AC1 relink request for "עדן" → one pending row with the person''s id, name and role; no name_taken',
      'ok/pending/editor/עדן/true/true',
      qa.f07_e(res) || '/' || coalesce(res->>'status', '') || '/' || coalesce(res->>'role', '') || '/' || coalesce(res->>'display_name', '') || '/' ||
      (select (m.person_id = p_e)::text from public.trip_members m where m.id = mid_n1) || '/' ||
      (select (m.relink_expires_at > now() + interval '23 hours' and m.relink_expires_at <= now() + interval '24 hours')::text
         from public.trip_members m where m.id = mid_n1));
    r := qa.f07_rec(r, 104, 'AC1 the same identity asking again → the same row, created=false (idempotent)', 'ok/false/1',
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n1, c1, null, 'ip-n1', p_e))) || '/' ||
      (qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n1, c1, null, 'ip-n1', p_e))->>'created') || '/' ||
      (select count(*) from public.trip_members m where m.user_id = u_n1 and m.trip_id = t1)::text);
    r := qa.f07_rec(r, 105, 'AC1 preview of the asking identity reports relink pending with the name + me.status pending', 'pending/עדן/pending',
      (qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, c1, 'ip-n1'))->'relink'->>'status') || '/' ||
      (qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, c1, 'ip-n1'))->'relink'->>'display_name') || '/' ||
      (qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n1, c1, 'ip-n1'))->'me'->>'status'));
    r := qa.f07_rec(r, 106, 'AC4/AC12 a removed person, a person of another trip, a guessed id → person_invalid (nothing written)',
      'person_invalid/person_invalid/person_invalid/0',
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n2, c1, null, 'ip-n2', p_x))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n2, c1, null, 'ip-n2', p_t2))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n2, c1, null, 'ip-n2', unknown))) || '/' ||
      (select count(*) from public.trip_members m where m.user_id = u_n2)::text);
    r := qa.f07_rec(r, 107, 'C5 an active member asking to relink → already_member', 'already_member',
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_e1, c1, null, 'ip-e1', p_e))));
    res := qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n2, c1, null, 'ip-n2', p_e));
    r := qa.f07_rec(r, 108, 'C5 one open relink per person: a newer request from another identity replaces the older one', 'ok/0/1',
      qa.f07_e(res) || '/' || (select count(*) from public.trip_members m where m.id = mid_n1)::text || '/' ||
      (select count(*) from public.trip_members m where m.trip_id = t1 and m.person_id = p_e and m.status = 'pending')::text);
    select m.id into mid_n2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_n2;
    -- a NEW person asking by name is unchanged (F05/F06) — and a taken name is still taken
    r := qa.f07_rec(r, 109, 'F05 a normal request by a taken name → name_taken; the 4-argument form still works', 'name_taken/ok',
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L)', u_n3, c1, 'עדן', 'ip-n3'))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L)', u_n3, c1, 'שם חדש', 'ip-n3'))));
    delete from public.trip_members m where m.user_id = u_n3;
    -- AC3: expiry after 24 h
    update public.trip_members set relink_expires_at = now() - interval '1 minute' where id = mid_n2;
    res := qa.f07_j(format('public.join_preview(%L, %L, %L)', u_n2, c1, 'ip-n2'));
    r := qa.f07_rec(r, 110, 'AC3 an unanswered relink request is reported "expired" once, the row is gone, me=null', 'expired/עדן/true/0',
      (res->'relink'->>'status') || '/' || (res->'relink'->>'display_name') || '/' || (res->'me' = 'null'::jsonb)::text || '/' ||
      (select count(*) from public.trip_members m where m.id = mid_n2)::text);
    res := qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n2, c1, null, 'ip-n2', p_e));
    select m.id into mid_n2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_n2;
    r := qa.f07_rec(r, 111, 'AC3 after it expired the member can ask again', 'ok/pending',
      qa.f07_e(res) || '/' || (select m.status from public.trip_members m where m.id = mid_n2));
    update public.trip_members set relink_expires_at = now() - interval '1 minute' where id = mid_n2;
    act := qa.f07_e(qa.f07_j(format('public.approve_member(%L, %L, %L, %L)', u_a1, mid_n2, 'approve', null)));
    r := qa.f07_rec(r, 112, 'C5 a manager cannot approve an expired relink (treated as absent, row deleted)', 'not_pending/0',
      act || '/' || (select count(*) from public.trip_members m where m.id = mid_n2)::text);
    -- AC13: the F05 ip limit counts relink requests (10 per ip per hour)
    for k in 1..10 loop
      perform qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_o, c1, null, 'ip-limit', unknown));
    end loop;
    r := qa.f07_rec(r, 113, 'AC13 the F05 limits apply to relink requests (11th attempt from one ip → rate_limited)', 'rate_limited',
      qa.f07_e(qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_o, c1, null, 'ip-limit', p_e))));

    -- ================= 2xx · approve a relink (AC2, C6) =================
    res := qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n1, c1, null, 'ip-n1b', p_e));
    select m.id into mid_n1 from public.trip_members m where m.trip_id = t1 and m.user_id = u_n1;
    perform qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_a1, mid_e1, 'viewer'));        -- role changes AFTER the request
    perform qa.f07_j(format('public.member_rename(%L, %L, %L)', u_a1, mid_e1, 'עדן כהן'));          -- name changes AFTER the request
    r := qa.f07_rec(r, 201, 'C6 non-manager cannot approve', 'not_manager',
      qa.f07_e(qa.f07_j(format('public.approve_member(%L, %L, %L, %L)', u_e1, mid_n1, 'approve', null))));
    res := qa.f07_j(format('public.approve_member(%L, %L, %L, %L)', u_a1, mid_n1, 'approve', 'manager'));
    r := qa.f07_rec(r, 202, 'AC2/C6 approve → active with the person''s CURRENT role and name (role parameter ignored)',
      'ok/active/viewer/עדן כהן/true',
      qa.f07_e(res) || '/' || qa.f07_row(mid_n1) || '/' || (res->>'relink'));
    r := qa.f07_rec(r, 203, 'AC2 one person, two devices: preview counts 4 persons, device_list shows 2 devices for "עדן כהן"',
      '4/2',
      (qa.f07_j(format('public.join_preview(%L, %L, %L)', u_o, c1, 'ip-o'))->>'members') || '/' ||
      (select jsonb_array_length(e->'devices')::text
         from jsonb_array_elements(qa.f07_j(format('public.device_list(%L, %L)', u_a1, t1))->'persons') e
        where e->>'person_id' = p_e::text));
    perform qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_a1, mid_e1, 'editor'));
    -- reject
    res := qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_n3, c1, null, 'ip-n3', p_v));
    select m.id into mid_n2 from public.trip_members m where m.trip_id = t1 and m.user_id = u_n3;
    res := qa.f07_j(format('public.approve_member(%L, %L, %L, %L)', u_a1, mid_n2, 'reject', null));
    r := qa.f07_rec(r, 204, 'AC3 rejecting a relink deletes the row', 'rejected/0',
      (res->>'status') || '/' ||
      (select count(*) from public.trip_members m where m.id = mid_n2)::text);

    -- ================= 3xx · person-wide changes (AC5, AC6, C1, C2) =================
    res := qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_a1, mid_v1, 'editor'));
    r := qa.f07_rec(r, 301, 'AC5 set_role reaches every device row of the person', 'ok/editor/editor',
      qa.f07_e(res) || '/' || (select m.role from public.trip_members m where m.id = mid_v1) || '/' ||
      (select m.role from public.trip_members m where m.id = mid_v2));
    res := qa.f07_j(format('public.member_rename(%L, %L, %L)', u_a1, mid_v2, 'צופה חדשה'));
    r := qa.f07_rec(r, 302, 'AC5 rename on one device row renames the person on every device', 'ok/צופה חדשה/צופה חדשה',
      qa.f07_e(res) || '/' || (select m.display_name from public.trip_members m where m.id = mid_v1) || '/' ||
      (select m.display_name from public.trip_members m where m.id = mid_v2));
    r := qa.f07_rec(r, 303, 'C2 rename to another PERSON''s name → name_taken; to the person''s own current name → ok (no change)',
      'name_taken/ok',
      qa.f07_e(qa.f07_j(format('public.member_rename(%L, %L, %L)', u_a1, mid_v1, 'אבי'))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.member_rename(%L, %L, %L)', u_a1, mid_v1, 'צופה חדשה'))));
    -- last manager counts persons (AC6): T3's only manager person has two device rows
    r := qa.f07_rec(r, 304, 'AC6 a manager with two devices is still "the only manager": demote / leave / self-remove refused', 'last_manager/last_manager/invalid_request',
      qa.f07_e(qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_s1, mid_s2, 'editor'))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.member_leave(%L, %L)', u_s2, t3))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.member_remove(%L, %L)', u_s1, mid_s2))));
    act := qa.f07_e(qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_a1, mid_a2, 'editor')));
    r := qa.f07_rec(r, 305, 'AC6 with another manager person, the two-device manager can be demoted on BOTH rows', 'ok/editor/editor',
      act || '/' ||
      (select m.role from public.trip_members m where m.id = mid_a1) || '/' || (select m.role from public.trip_members m where m.id = mid_a2));
    act := qa.f07_e(qa.f07_j(format('public.member_set_role(%L, %L, %L)', u_b1, mid_a1, 'manager')));
    r := qa.f07_rec(r, 306, 'AC6 promoting the person back (both rows) for the next scenarios', 'ok/manager/manager',
      act || '/' ||
      (select m.role from public.trip_members m where m.id = mid_a1) || '/' || (select m.role from public.trip_members m where m.id = mid_a2));
    -- remove / leave reach every device row
    res := qa.f07_j(format('public.member_remove(%L, %L)', u_a1, mid_v1));
    r := qa.f07_rec(r, 307, 'AC5 remove a person → every device row removed; the devices read 0 rows at once', 'ok/removed/removed/0 rows/0 rows',
      qa.f07_e(res) || '/' || (select m.status from public.trip_members m where m.id = mid_v1) || '/' ||
      (select m.status from public.trip_members m where m.id = mid_v2) || '/' ||
      qa.f07_count(u_v1, au, format('select 1 from public.trip_kv where trip_id = %L', t1)) || '/' ||
      qa.f07_count(u_v2, au, format('select 1 from public.trip_kv where trip_id = %L', t1)));
    res := qa.f07_j(format('public.join_request(%L, %L, %L, %L, %L)', u_o, c1, null, 'ip-o2', p_e));   -- an open relink of "עדן כהן"
    res := qa.f07_j(format('public.member_leave(%L, %L)', u_e1, t1));
    r := qa.f07_rec(r, 308, 'AC5 leave → all the person''s rows removed (both devices), an open relink request of the person deleted',
      'ok/removed/removed/0',
      qa.f07_e(res) || '/' || (select m.status from public.trip_members m where m.id = mid_e1) || '/' ||
      (select m.status from public.trip_members m where m.id = mid_n1) || '/' ||
      (select count(*) from public.trip_members m where m.person_id = p_e and m.status = 'pending')::text);

    -- ================= 4xx · devices (AC7, AC8, AC9, AC12, C3, C4, C8) =================
    -- touch records the session; an account session is a device of its own
    res := qa.f07_j(format('public.member_touch(p_user => %L, p_trip => %L, p_session => %L, p_label => %L, p_via => %L)', u_a1, t1, s_a, 'Android · Chrome', 'anon'));
    res2 := qa.f07_j(format('public.member_touch(%L, %L)', u_a2, t1));
    r := qa.f07_rec(r, 401, 'C3 touch records the session (label, via); the 2-argument call still works', 'ok/ok/1/Android · Chrome/anon',
      qa.f07_e(res) || '/' || qa.f07_e(res2) || '/' ||
      (select count(*) from private.member_sessions s where s.member_id = mid_a1)::text || '/' ||
      (select s.label from private.member_sessions s where s.member_id = mid_a1) || '/' ||
      (select s.via from private.member_sessions s where s.member_id = mid_a1));
    res := qa.f07_j(format('public.device_list(%L, %L)', u_b1, t1));
    r := qa.f07_rec(r, 402, 'D4 a manager lists every active person with devices (דנה has 2); a member lists only their own person', '2/2/1',
      jsonb_array_length(res->'persons')::text || '/' ||
      (select jsonb_array_length(e->'devices')::text from jsonb_array_elements(res->'persons') e where e->>'person_id' = p_a::text) || '/' ||
      jsonb_array_length(qa.f07_j(format('public.device_list(%L, %L)', u_s3, t3))->'persons')::text);
    -- AC7: anonymous device → row removed, RLS cuts it at once, the person stays on the other device
    res := qa.f07_j(format('public.device_disconnect(p_user => %L, p_trip => %L, p_member => %L)', u_a1, t1, mid_a2));
    r := qa.f07_rec(r, 403, 'AC7 disconnect an anonymous device → that row removed, its reads 0 rows, the person stays active on the other', 'ok/row/removed/0 rows/active/1 rows',
      qa.f07_e(res) || '/' || coalesce(res->>'kind', '') || '/' || (select m.status from public.trip_members m where m.id = mid_a2) || '/' ||
      qa.f07_count(u_a2, au, format('select 1 from public.trip_kv where trip_id = %L', t1)) || '/' ||
      (select m.status from public.trip_members m where m.id = mid_a1) || '/' ||
      qa.f07_count(u_a1, au, format('select 1 from public.trip_kv where trip_id = %L', t1)));
    r := qa.f07_rec(r, 404, 'AC9 the last device of a person has no disconnect: the API refuses, row unchanged', 'last_device/active/last_device',
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_a1, t1, mid_a1))) || '/' ||
      (select m.status from public.trip_members m where m.id = mid_a1) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_b1, t1, mid_a1))));
    -- AC8: an account (email) person with two sessions
    res := qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_b1, t1, s_c, 'Windows · Chrome', 'email'));
    res2 := qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_b1, t1, s_d, 'Mac · Safari', 'google'));
    r := qa.f07_rec(r, 405, 'C3 account sessions (email, google) are separate devices of the same row: 2 devices for אבי', 'ok/ok/2',
      qa.f07_e(res) || '/' || qa.f07_e(res2) || '/' ||
      (select jsonb_array_length(e->'devices')::text
         from jsonb_array_elements(qa.f07_j(format('public.device_list(%L, %L)', u_a1, t1))->'persons') e
        where e->>'display_name' = 'אבי'));
    update private.member_sessions set created_at = now() - interval '2 days' where member_id = mid_b1 and session_id = s_c;
    if has_auth_sessions then
      execute 'insert into auth.sessions (id, user_id, created_at, updated_at) values ($1, $3, now(), now()), ($2, $3, now(), now())'
        using s_c, s_d, u_b1;
    end if;
    res := qa.f07_j(format('public.device_disconnect(%L, %L, %L, %L)', u_a1, t1, mid_b1, s_c));
    v_gone := 'true';       -- (auth.sessions is looked up dynamically: the table may not exist in a local scratch database)
    if has_auth_sessions then
      execute 'select (not exists (select 1 from auth.sessions a where a.id = $1))::text' using s_c into v_gone;
    end if;
    r := qa.f07_rec(r, 406, 'AC8 disconnect an account session → revoked, its auth.sessions row gone, the member row stays active', 'ok/session/true/active',
      qa.f07_e(res) || '/' || coalesce(res->>'kind', '') || '/' ||
      v_gone || '/' ||
      (select m.status from public.trip_members m where m.id = mid_b1));
    r := qa.f07_rec(r, 407, 'AC8 the revoked device is told device_revoked on its next check; the other sessions keep working', 'device_revoked/ok',
      qa.f07_e(qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_b1, t1, s_c, null, 'email'))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_b1, t1, s_d, null, 'google'))));
    -- C8: login notice
    res := qa.f07_j(format('public.device_list(%L, %L)', u_a1, t1));
    r := qa.f07_rec(r, 408, 'C8 a new account session of a person who had an earlier session → a notice for the OTHER managers', '1/אבי/google/0',
      jsonb_array_length(res->'notices')::text || '/' || coalesce(res->'notices'->0->>'display_name', '') || '/' ||
      coalesce(res->'notices'->0->>'via', '') || '/' ||
      jsonb_array_length(qa.f07_j(format('public.device_list(%L, %L)', u_b1, t1))->'notices')::text);
    r := qa.f07_rec(r, 409, 'C8 only a manager can acknowledge; once any manager does, the notice is gone for all', 'not_manager/ok/0',
      qa.f07_e(qa.f07_j(format('public.device_notice_ack(%L, %L, %L)', u_s3, t1, s_d))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_notice_ack(%L, %L, %L)', u_a1, t1, s_d))) || '/' ||
      jsonb_array_length(qa.f07_j(format('public.device_list(%L, %L)', u_a1, t1))->'notices')::text);
    -- a person's FIRST ever session is not a notice; a notice expires after 7 days
    insert into private.member_sessions (member_id, session_id, via, created_at) values (mid_e9, s_a, 'google', now());
    insert into private.member_sessions (member_id, session_id, via, created_at) values (mid_s3, s_a, 'anon', now() - interval '30 days');
    insert into private.member_sessions (member_id, session_id, via, created_at) values (mid_s3, s_b, 'email', now() - interval '8 days');
    r := qa.f07_rec(r, 410, 'C8 no notice for a person''s first-ever session', '0',
      jsonb_array_length(qa.f07_j(format('public.device_list(%L, %L)', u_m2, t2))->'notices')::text);
    r := qa.f07_rec(r, 411, 'C8 a login notice older than 7 days is gone', '0',
      jsonb_array_length(qa.f07_j(format('public.device_list(%L, %L)', u_s1, t3))->'notices')::text);
    -- AC12: isolation
    r := qa.f07_rec(r, 412, 'AC12 an outsider, and a manager of ANOTHER trip, can list / disconnect / acknowledge nothing', 'not_member/not_member/not_member/not_manager',
      qa.f07_e(qa.f07_j(format('public.device_list(%L, %L)', u_o, t1))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_m2, t1, mid_b1))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_o, t1, mid_b1))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_notice_ack(%L, %L, %L)', u_m2, t1, s_d))));
    r := qa.f07_rec(r, 413, 'D4 a member may disconnect their own other device but not another person''s', 'not_manager/ok',
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_s3, t3, mid_s1))) || '/' ||
      qa.f07_e(qa.f07_j(format('public.device_disconnect(%L, %L, %L)', u_s2, t3, mid_s1))));
    r := qa.f07_rec(r, 414, 'C4 removed device returns not_member on touch (F06 D11 path unchanged)', 'not_member',
      qa.f07_e(qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_s1, t3, s_a, null, 'anon'))));

    -- ================= 5xx · transfer, grants =================
    perform qa.f07_j(format('public.member_touch(%L, %L, %L, %L, %L)', u_s3, t3, s_c, 'iPhone · Safari', 'anon'));
    res := qa.f07_j(format('public.issue_transfer(%L, %L)', u_s3, t3));
    res2 := qa.f07_j(format('public.claim_transfer(%L, %L, %L)', u_t1, res->>'code', 'ip-t'));
    r := qa.f07_rec(r, 501, 'C11 claim_transfer moves the device row to the new identity, person_id kept, old sessions forgotten', 'ok/true/true/0',
      qa.f07_e(res2) || '/' ||
      (select (m.user_id = u_t1)::text from public.trip_members m where m.id = mid_s3) || '/' ||
      (select (m.person_id = m.id)::text from public.trip_members m where m.id = mid_s3) || '/' ||
      (select count(*) from private.member_sessions s where s.member_id = mid_s3 and s.session_id = s_c)::text);
    r := qa.f07_rec(r, 502, 'C12 the new functions are service-role only (authenticated / anon cannot execute or read member_sessions)',
      'false/false/false/false',
      pg_catalog.has_function_privilege('authenticated', 'public.device_list(uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.device_disconnect(uuid, uuid, uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('anon', 'public.device_notice_ack(uuid, uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.member_touch(uuid, uuid, uuid, text, text)', 'execute')::text);
    r := qa.f07_rec(r, 503, 'C1 RLS unchanged: a member of T1 reads 0 rows of T2 members; every active device row reads its own trip', '0 rows/1 rows',
      qa.f07_count(u_b1, au, format('select 1 from public.trip_members where trip_id = %L', t2)) || '/' ||
      qa.f07_count(u_a1, au, format('select 1 from public.trip_kv where trip_id = %L', t1)));
    r := qa.f07_rec(r, 504, 'schema: private adds only member_sessions to F05''s two tables (no new table in public)', 'join_attempts,member_sessions,transfer_codes/0',
      (select string_agg(t.tablename, ',' order by t.tablename) from pg_catalog.pg_tables t where t.schemaname = 'private'
         and t.tablename in ('join_attempts', 'member_sessions', 'transfer_codes')) || '/' ||
      (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public' and t.tablename in ('member_sessions', 'devices')));

    raise exception 'f07_rollback';
  exception when others then
    perform qa.f07_as(null, 'postgres');
    if sqlerrm <> 'f07_rollback' then
      r := qa.f07_rec(r, 998, 'harness aborted', 'f07_rollback', sqlstate || ' ' || sqlerrm);
    end if;
  end;

  r := qa.f07_rec(r, 999, 'Leftovers after the run: 0 f07 users / trips / sessions, counters unchanged', '0/0/0/true',
    (select count(*) from auth.users u where u.id::text like 'f0700000-%')::text || '/' ||
    (select count(*) from public.trips t where t.name like 'F07 %')::text || '/' ||
    (select count(*) from private.member_sessions s where s.session_id::text like 'f0700000-%')::text || '/' ||
    ((select count(*) from public.trips) = n_trips_before and (select count(*) from private.transfer_codes) = n_tc_before
      and (select count(*) from auth.users) = n_users_before and (select count(*) from private.join_attempts) <= n_att_before)::text);

  return query select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail' from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
