-- Lonely Planner QA · F06 DB-level test harness · version 3.0.0-alpha.7 · F06 (QA 1.0.0)
-- CHANGE 2026-10-22 F06-QA-01: first version (no previous version). Installs qa.f06_run() in the locked `qa` schema, same
--   pattern as F01–F05 (0002–0004, 0007, 0009, 0011, 0013): helpers impersonate a user via request.jwt.claims + SET LOCAL
--   ROLE, all test data is created inside a sub-transaction that is always rolled back (raise 'f06_rollback'), search_path
--   pinned to '', nothing granted to public/anon/authenticated. SECURITY INVOKER (run as postgres, the owner of the F06
--   functions), because PostgreSQL forbids SET ROLE inside a SECURITY DEFINER function.
--   Written black-box from docs/F06_spec.md §2 / §4 ONLY (0014_f06.sql was not read; it did not exist when this was
--   written). The six entry functions are called with NAMED arguments exactly as the spec writes them
--   (member_set_role(p_user, p_member, p_role) …), so a different parameter name fails the scenario visibly.
--
-- Run (after 0014_f06.sql):   select * from qa.f06_run() order by id;
-- Output: one row per scenario (id, name, pass, detail) — detail = 'expected: … | actual: …'. Each name starts with the
-- spec §4 criterion number(s) it covers (C4 … C17) or the §2 item / decision (§2.6, D2, D7 …).
--
-- Conventions (as F05): every refusal must be RETURNED as {"error":code} (spec §2 "F05 pattern"); a raised exception is
-- reported by the call wrappers as {"raised":"<sqlstate> <message>"} and therefore fails the scenario. A call that writes and
-- the check of its effect are always separate statements. "No write" is checked with the row's ctid (any UPDATE, even a
-- no-op one, creates a new tuple version and so a new ctid). Time windows are exercised by back-dating rows, never sleeping.
--
-- Where the spec leaves a detail open, the expected value lists the accepted alternatives ('A or B') and the scenario name
-- says "(open: …)". Those points are listed in tests/f06/README.md §"Spec ambiguities".
--
-- Criteria covered (docs/F06_spec.md §4): 4, 5 (DB side), 6 (DB side), 7, 9 (DB side), 10 (DB side), 11 (DB side),
-- 15 (DB side), 16 (DB side), 17 (grants / policies / cross-trip; advisors are checked in the Supabase dashboard), plus
-- §2.1–2.8, D2, D3, D6, D7, D12.

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

-- Impersonate: p_role in ('authenticated','anon','postgres'); p_uid null = no "sub" claim.
create or replace function qa.f06_as(p_uid uuid, p_role text)
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
create or replace function qa.f06_count(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f06_as(p_uid, p_role);
  execute 'select count(*) from (' || p_sql || ') f06_s' into n;
  execute 'reset role';
  return n || ' rows';
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Evaluate a scalar expression while impersonating; report it as text.
create or replace function qa.f06_val(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare v text;
begin
  perform qa.f06_as(p_uid, p_role);
  execute p_sql into v;
  execute 'reset role';
  return coalesce(v, 'NULL');
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Call wrappers (as postgres = what manage-members does with the service role), named arguments exactly as spec §2.
-- A raised exception (also "function does not exist" = wrong name / parameter names) becomes {"raised": "..."}.
create or replace function qa.f06_setrole(p_user uuid, p_member uuid, p_role text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.member_set_role(p_user => p_user, p_member => p_member, p_role => p_role);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_rename(p_user uuid, p_member uuid, p_name text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.member_rename(p_user => p_user, p_member => p_member, p_name => p_name);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_remove(p_user uuid, p_member uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.member_remove(p_user => p_user, p_member => p_member);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_leave(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.member_leave(p_user => p_user, p_trip => p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_rotate(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.rotate_join_code(p_user => p_user, p_trip => p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_touch(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.member_touch(p_user => p_user, p_trip => p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

-- F05 entry points used by the D2 / D3 scenarios (behaviour changed by F06 §2.6)
create or replace function qa.f06_prev(p_user uuid, p_code text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.join_preview(p_user, p_code, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_req(p_user uuid, p_code text, p_name text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.join_request(p_user, p_code, p_name, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_appr(p_user uuid, p_member uuid, p_decision text, p_role text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.approve_member(p_user, p_member, p_decision, p_role);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_issue(p_user uuid, p_trip uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.issue_transfer(p_user, p_trip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f06_claim(p_user uuid, p_code text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.claim_transfer(p_user, p_code, p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

-- The error code of a result, or 'ok' when the result has no "error" key ('null' for a SQL null result).
create or replace function qa.f06_e(p jsonb)
returns text language sql immutable set search_path = '' as $f$
  select case when p is null then 'null'
              when pg_catalog.jsonb_typeof(p) <> 'object' then 'ok'
              when p ? 'raised' then 'raised ' || (p->>'raised')
              when p ? 'error' then p->>'error' else 'ok' end
$f$;

-- 'status/role/display_name' of a member row ('∅' when the row does not exist).
create or replace function qa.f06_row(p_member uuid)
returns text language sql stable set search_path = '' as $f$
  select coalesce((select m.status || '/' || m.role || '/' || m.display_name from public.trip_members m where m.id = p_member), '∅')
$f$;

-- The physical tuple id of a member row (changes on ANY update, including a no-op one).
create or replace function qa.f06_ctid(p_member uuid)
returns text language sql stable set search_path = '' as $f$
  select coalesce((select m.ctid::text from public.trip_members m where m.id = p_member), '∅')
$f$;

-- An authenticated trip_kv upsert as p_uid (what window.storage.set sends). Returns '1' or 'error <sqlstate> …'.
create or replace function qa.f06_kvset(p_uid uuid, p_trip uuid, p_key text, p_value text)
returns text language sql set search_path = '' as $f$
  select qa.f06_val(p_uid, 'authenticated', pg_catalog.format(
    'with w as (insert into public.trip_kv (trip_id, key, value) values (%L, %L, %L)
       on conflict (trip_id, key) do update set value = excluded.value returning 1) select count(*)::text from w',
    p_trip, p_key, p_value))
$f$;

-- Expected-value grammar (same as F01–F05): 'N rows' exact · 'error 42501' prefix · 'error contains xyz' · 'A or B'.
create or replace function qa.f06_match(p_exp text, p_act text)
returns boolean language plpgsql immutable set search_path = '' as $f$
declare alt text;
begin
  if p_act is null then return false; end if;
  if position(' or ' in p_exp) > 0 then
    foreach alt in array pg_catalog.string_to_array(p_exp, ' or ') loop
      if qa.f06_match(alt, p_act) then return true; end if;
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

create or replace function qa.f06_rec(r jsonb, p_id int, p_name text, p_exp text, p_act text)
returns jsonb language plpgsql set search_path = '' as $f$
begin
  return r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
    'id', p_id, 'name', p_name,
    'detail', 'expected: ' || p_exp || ' | actual: ' || coalesce(p_act, '(null)'),
    'pass', qa.f06_match(p_exp, p_act)));
end $f$;

create or replace function qa.f06_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r    jsonb := '[]'::jsonb;
  au   constant text := 'authenticated';
  alpha constant text := '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$';
  -- fixed identities (namespace f0600000-…)
  u_m1  constant uuid := 'f0600000-0000-4000-8000-0000000000a1';  -- T1 earliest manager "דנה"
  u_m1b constant uuid := 'f0600000-0000-4000-8000-0000000000a2';  -- T1 second manager "אבי"
  u_e1  constant uuid := 'f0600000-0000-4000-8000-0000000000a3';  -- T1 editor "Editor Q" (set_role / rename target)
  u_e2  constant uuid := 'f0600000-0000-4000-8000-0000000000a4';  -- T1 editor "עורכת" (remove target)
  u_e3  constant uuid := 'f0600000-0000-4000-8000-0000000000a5';  -- T1 editor "יוצא" (leaves)
  u_v1  constant uuid := 'f0600000-0000-4000-8000-0000000000a6';  -- T1 viewer "צופה"
  u_tr  constant uuid := 'f0600000-0000-4000-8000-0000000000a7';  -- T1 editor "מעביר" (transfer code across a rotation)
  u_p1  constant uuid := 'f0600000-0000-4000-8000-0000000000a8';  -- T1 pending "ממתין"
  u_x1  constant uuid := 'f0600000-0000-4000-8000-0000000000a9';  -- T1 removed ex-MANAGER "הוסר" (D2 re-request)
  u_x3  constant uuid := 'f0600000-0000-4000-8000-0000000000aa';  -- T1 removed "הוסר3" (3 requests / 24 h)
  u_x4  constant uuid := 'f0600000-0000-4000-8000-0000000000ab';  -- T1 removed "הוסר4" (ip limit)
  u_m2  constant uuid := 'f0600000-0000-4000-8000-0000000000b1';  -- T2 manager only
  u_m3  constant uuid := 'f0600000-0000-4000-8000-0000000000b2';  -- T2 manager AND T1 editor "מנהל3"
  u_e9  constant uuid := 'f0600000-0000-4000-8000-0000000000b3';  -- T2 editor "Tom"
  u_x5  constant uuid := 'f0600000-0000-4000-8000-0000000000b4';  -- T2 removed (default role viewer)
  u_s   constant uuid := 'f0600000-0000-4000-8000-0000000000c1';  -- T3 the ONLY member, manager "סולו"
  u_m4  constant uuid := 'f0600000-0000-4000-8000-0000000000c2';  -- T4 manager (pending-cap trip)
  u_x2  constant uuid := 'f0600000-0000-4000-8000-0000000000c3';  -- T4 removed (pending cap)
  u_t1  constant uuid := 'f0600000-0000-4000-8000-0000000000d1';  -- installed-app identity claiming a transfer code
  u_o   constant uuid := 'f0600000-0000-4000-8000-0000000000e1';  -- outsider
  u_n   constant uuid := 'f0600000-0000-4000-8000-0000000000e2';  -- someone who takes a free name in T1
  t1    constant uuid := 'f0600000-0000-4000-8000-00000000f001';
  t2    constant uuid := 'f0600000-0000-4000-8000-00000000f002';
  t3    constant uuid := 'f0600000-0000-4000-8000-00000000f003';
  t4    constant uuid := 'f0600000-0000-4000-8000-00000000f004';
  c1    constant text := 'F6QAJNAA';
  c2    constant text := 'F6QAJNBB';
  c3    constant text := 'F6QAJNCC';
  c4    constant text := 'F6QAJNDD';
  unknown constant uuid := 'f0600000-0000-4000-8000-0000000000ff';
  res   jsonb;
  mid_m1 uuid; mid_m1b uuid; mid_e1 uuid; mid_e2 uuid; mid_e3 uuid; mid_v1 uuid; mid_tr uuid; mid_p1 uuid;
  mid_x1 uuid; mid_x3 uuid; mid_x4 uuid; mid_m3 uuid; mid_e9 uuid; mid_x5 uuid; mid_s uuid; mid_x2 uuid; mid_m2 uuid;
  ct    text; ct2 text; ct3 text;
  act   text; act2 text;
  v     text;
  v_code  text; v_code2 text; tcode text;
  codes text[] := '{}';
  ver   int;
  ts    timestamptz;
  n     bigint; n2 bigint;
  k     int;
  g     uuid;
  t2_snap text;
  n_trips_before bigint; n_att_before bigint; n_tc_before bigint; n_users_before bigint;
begin
  select count(*) into n_trips_before from public.trips;
  select count(*) into n_att_before from private.join_attempts;
  select count(*) into n_tc_before from private.transfer_codes;
  select count(*) into n_users_before from auth.users;

  begin
    -- ================= SETUP (as postgres, bypassing RLS) =================
    perform qa.f06_as(null, 'postgres');
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at)
      select u, 'authenticated', 'authenticated', null, '00000000-0000-0000-0000-000000000000', now(), now()
        from unnest(array[u_m1, u_m1b, u_e1, u_e2, u_e3, u_v1, u_tr, u_p1, u_x1, u_x3, u_x4, u_m2, u_m3, u_e9, u_x5,
                          u_s, u_m4, u_x2, u_t1, u_o, u_n]) u;
    insert into public.trips (id, name, start_date, end_date, default_role, created_by) values
      (t1, 'F06 יפן 2027',   '2027-04-03', '2027-04-20', 'editor', u_m1),
      (t2, 'F06 קבוצה 2',    '2027-05-30', '2027-06-02', 'viewer', u_m2),
      (t3, 'F06 סולו',       '2027-07-01', '2027-07-03', 'editor', u_s),
      (t4, 'F06 תקרה',       '2027-08-01', '2027-08-01', 'editor', u_m4);
    insert into public.trip_join_codes (trip_id, code, version, rotated_at) values
      (t1, c1, 1, now() - interval '1 day'), (t2, c2, 1, now() - interval '1 day'),
      (t3, c3, 1, now() - interval '1 day'), (t4, c4, 1, now() - interval '1 day');
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at) values
      (t1, u_m1,  'דנה',      'manager', 'active',  now() - interval '90 days', now() - interval '90 days'),
      (t1, u_m1b, 'אבי',      'manager', 'active',  now() - interval '80 days', now() - interval '80 days'),
      (t1, u_e1,  'Editor Q', 'editor',  'active',  now() - interval '70 days', now() - interval '70 days'),
      (t1, u_e2,  'עורכת',    'editor',  'active',  now() - interval '60 days', now() - interval '60 days'),
      (t1, u_e3,  'יוצא',     'editor',  'active',  now() - interval '50 days', now() - interval '50 days'),
      (t1, u_v1,  'צופה',     'viewer',  'active',  now() - interval '40 days', now() - interval '40 days'),
      (t1, u_tr,  'מעביר',    'editor',  'active',  now() - interval '35 days', now() - interval '35 days'),
      (t1, u_m3,  'מנהל3',    'editor',  'active',  now() - interval '33 days', now() - interval '33 days'),
      (t1, u_p1,  'ממתין',    'editor',  'pending', now() - interval '1 hour',  null),
      (t1, u_x1,  'הוסר',     'manager', 'removed', now() - interval '100 days', now() - interval '100 days'),
      (t1, u_x3,  'הוסר3',    'editor',  'removed', now() - interval '30 days', now() - interval '30 days'),
      (t1, u_x4,  'הוסר4',    'editor',  'removed', now() - interval '30 days', now() - interval '30 days'),
      (t2, u_m2,  'מנהל2',    'manager', 'active',  now() - interval '20 days', now() - interval '20 days'),
      (t2, u_m3,  'מנהל3',    'manager', 'active',  now() - interval '19 days', now() - interval '19 days'),
      (t2, u_e9,  'Tom',      'editor',  'active',  now() - interval '18 days', now() - interval '18 days'),
      (t2, u_x5,  'הוסר5',    'editor',  'removed', now() - interval '18 days', now() - interval '18 days'),
      (t3, u_s,   'סולו',     'manager', 'active',  now() - interval '10 days', now() - interval '10 days'),
      (t4, u_m4,  'מנהל4',    'manager', 'active',  now() - interval '10 days', now() - interval '10 days'),
      (t4, u_x2,  'הוסר2',    'editor',  'removed', now() - interval '9 days',  now() - interval '9 days');
    insert into public.trip_kv (trip_id, key, value, updated_by) values
      (t1, 'trip', '[]', null), (t1, 'tripname', 'F06 יפן 2027', u_m1), (t2, 'tripname', 'F06 קבוצה 2', u_m2),
      (t1, 'expenses', '[{"by":"עורכת","amount":5}]', u_e2);
    select m.id into mid_m1  from public.trip_members m where m.trip_id = t1 and m.user_id = u_m1;
    select m.id into mid_m1b from public.trip_members m where m.trip_id = t1 and m.user_id = u_m1b;
    select m.id into mid_e1  from public.trip_members m where m.trip_id = t1 and m.user_id = u_e1;
    select m.id into mid_e2  from public.trip_members m where m.trip_id = t1 and m.user_id = u_e2;
    select m.id into mid_e3  from public.trip_members m where m.trip_id = t1 and m.user_id = u_e3;
    select m.id into mid_v1  from public.trip_members m where m.trip_id = t1 and m.user_id = u_v1;
    select m.id into mid_tr  from public.trip_members m where m.trip_id = t1 and m.user_id = u_tr;
    select m.id into mid_p1  from public.trip_members m where m.trip_id = t1 and m.user_id = u_p1;
    select m.id into mid_x1  from public.trip_members m where m.trip_id = t1 and m.user_id = u_x1;
    select m.id into mid_x3  from public.trip_members m where m.trip_id = t1 and m.user_id = u_x3;
    select m.id into mid_x4  from public.trip_members m where m.trip_id = t1 and m.user_id = u_x4;
    select m.id into mid_m3  from public.trip_members m where m.trip_id = t1 and m.user_id = u_m3;
    select m.id into mid_m2  from public.trip_members m where m.trip_id = t2 and m.user_id = u_m2;
    select m.id into mid_e9  from public.trip_members m where m.trip_id = t2 and m.user_id = u_e9;
    select m.id into mid_x5  from public.trip_members m where m.trip_id = t2 and m.user_id = u_x5;
    select m.id into mid_s   from public.trip_members m where m.trip_id = t3 and m.user_id = u_s;
    select m.id into mid_x2  from public.trip_members m where m.trip_id = t4 and m.user_id = u_x2;
    -- snapshot of T2 (cross-trip isolation is checked at the end)
    select string_agg(m.id || ':' || m.status || ':' || m.role || ':' || m.display_name || ':' || m.ctid::text, ';' order by m.id)
      into t2_snap from public.trip_members m where m.trip_id = t2;

    -- ================= 1xx · member_set_role (C4, C5, §2.1) =================
    res := qa.f06_setrole(u_m1, mid_e1, 'viewer');
    r := qa.f06_rec(r, 101, 'C4 set_role editor→viewer by a manager → ok, stored viewer', 'ok/active/viewer/Editor Q',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e1));
    res := qa.f06_setrole(u_m1, mid_e1, 'manager');
    r := qa.f06_rec(r, 102, 'C4 set_role viewer→manager → ok, stored manager', 'ok/active/manager/Editor Q',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e1));
    -- a freshly promoted manager may act at once
    res := qa.f06_setrole(u_e1, mid_e2, 'viewer');
    r := qa.f06_rec(r, 103, 'C4 the promoted member (now manager) can set_role at once', 'ok/active/viewer/עורכת',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e2));
    res := qa.f06_setrole(u_m1, mid_e1, 'editor');
    r := qa.f06_rec(r, 104, 'C4 set_role manager→editor (3 managers) → ok, stored editor', 'ok/active/editor/Editor Q',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e1));
    act := qa.f06_e(qa.f06_setrole(u_e1, mid_e2, 'editor'));
    r := qa.f06_rec(r, 105, 'C4 the demoted member loses the right at once → not_manager, target unchanged', 'not_manager/active/viewer/עורכת',
      act || '/' || qa.f06_row(mid_e2));
    perform qa.f06_setrole(u_m1, mid_e2, 'editor');
    r := qa.f06_rec(r, 106, 'C4 set_role touches only role (user, joined_at, approved_at, last_seen_at unchanged)', '1',
      (select count(*)::text from public.trip_members m where m.id = mid_e1 and m.user_id = u_e1 and m.trip_id = t1
          and m.joined_at = now() - interval '70 days' and m.approved_at = now() - interval '70 days' and m.last_seen_at is null));
    ct := qa.f06_ctid(mid_e1);
    res := qa.f06_setrole(u_m1, mid_e1, 'editor');
    r := qa.f06_rec(r, 107, '§2.1 same role → ok, no write (ctid unchanged)', 'ok/true',
      qa.f06_e(res) || '/' || (qa.f06_ctid(mid_e1) = ct)::text);
    ct := qa.f06_ctid(mid_e1);
    r := qa.f06_rec(r, 108, 'C4 role outside manager/editor/viewer → role_invalid', 'role_invalid',
      qa.f06_e(qa.f06_setrole(u_m1, mid_e1, 'owner')));
    r := qa.f06_rec(r, 109, 'C4 role in other case (''Editor'') → role_invalid (open: case-insensitive accepted as ok, no write)', 'role_invalid or ok',
      qa.f06_e(qa.f06_setrole(u_m1, mid_e1, 'Editor')));
    ct := qa.f06_ctid(mid_e1);
    r := qa.f06_rec(r, 110, 'C4 null role → role_invalid (open: or invalid_request)', 'role_invalid or invalid_request',
      qa.f06_e(qa.f06_setrole(u_m1, mid_e1, null)));
    r := qa.f06_rec(r, 111, 'C4 an editor of the trip → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_e3, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 112, 'C4 a viewer of the trip → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_v1, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 113, 'C4 C17 a manager of ANOTHER trip → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_m2, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 114, 'C4 an outsider → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_o, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 115, 'C4 a PENDING member of the trip as caller → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_p1, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 116, 'C4 a REMOVED ex-manager as caller → not_manager', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_x1, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 117, 'C4 refusals 110–116 left the target untouched (ctid, role editor)', 'true/active/editor/Editor Q',
      (qa.f06_ctid(mid_e1) = ct)::text || '/' || qa.f06_row(mid_e1));
    ct := qa.f06_ctid(mid_p1);
    act := qa.f06_e(qa.f06_setrole(u_m1, mid_p1, 'viewer'));
    r := qa.f06_rec(r, 118, 'C4 a PENDING target → not_active, row untouched', 'not_active/true/pending/editor/ממתין',
      act || '/' || (qa.f06_ctid(mid_p1) = ct)::text || '/' || qa.f06_row(mid_p1));
    ct := qa.f06_ctid(mid_x1);
    act := qa.f06_e(qa.f06_setrole(u_m1, mid_x1, 'editor'));
    r := qa.f06_rec(r, 119, 'C4 a REMOVED target → not_active, row untouched', 'not_active/true/removed/manager/הוסר',
      act || '/' || (qa.f06_ctid(mid_x1) = ct)::text || '/' || qa.f06_row(mid_x1));
    r := qa.f06_rec(r, 120, 'C4 unknown member id → a refusal (open: not_active / not_member / not_manager / invalid_request)',
      'not_active or not_member or not_manager or invalid_request', qa.f06_e(qa.f06_setrole(u_m1, unknown, 'viewer')));
    r := qa.f06_rec(r, 121, 'C4 null p_user → a refusal (open: invalid_request / not_manager)', 'invalid_request or not_manager',
      qa.f06_e(qa.f06_setrole(null, mid_e1, 'viewer')));
    r := qa.f06_rec(r, 122, 'C4 C17 a T1 manager on a T2 member → not_manager, T2 row untouched', 'not_manager/active/editor/Tom',
      qa.f06_e(qa.f06_setrole(u_m1, mid_e9, 'viewer')) || '/' || qa.f06_row(mid_e9));
    -- C5: two managers → one may step down; afterwards the last one may not
    res := qa.f06_setrole(u_m1b, mid_m1b, 'editor');
    r := qa.f06_rec(r, 130, 'C5 with two active managers, one demotes THEMSELF → ok, now editor', 'ok/active/editor/אבי',
      qa.f06_e(res) || '/' || qa.f06_row(mid_m1b));
    r := qa.f06_rec(r, 131, 'C5 the self-demoted ex-manager → not_manager on the next call', 'not_manager',
      qa.f06_e(qa.f06_setrole(u_m1b, mid_e1, 'viewer')));
    ct := qa.f06_ctid(mid_m1);
    act := qa.f06_e(qa.f06_setrole(u_m1, mid_m1, 'editor'));
    r := qa.f06_rec(r, 132, 'C4 D6 demoting the LAST active manager (self → editor) → last_manager, returned not raised, no write',
      'last_manager/true/active/manager/דנה', act || '/' || (qa.f06_ctid(mid_m1) = ct)::text || '/' || qa.f06_row(mid_m1));
    act := qa.f06_e(qa.f06_setrole(u_m1, mid_m1, 'viewer'));
    r := qa.f06_rec(r, 133, 'C4 D6 last manager self → viewer → last_manager, no write', 'last_manager/true',
      act || '/' || (qa.f06_ctid(mid_m1) = ct)::text);
    act := qa.f06_e(qa.f06_setrole(u_m1, mid_m1, 'manager'));
    r := qa.f06_rec(r, 134, '§2.1 last manager self → manager (same role) → ok, no write', 'ok/true',
      act || '/' || (qa.f06_ctid(mid_m1) = ct)::text);
    act := qa.f06_e(qa.f06_setrole(u_s, mid_s, 'viewer'));
    r := qa.f06_rec(r, 135, 'C4 D6 the ONLY member of a trip (manager) self → viewer → last_manager', 'last_manager/active/manager/סולו',
      act || '/' || qa.f06_row(mid_s));
    res := qa.f06_setrole(u_m1, mid_m1b, 'manager');
    r := qa.f06_rec(r, 136, 'C4 a manager promotes the ex-manager back → ok (two managers again)', 'ok/2',
      qa.f06_e(res) || '/' || (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.role = 'manager' and m.status = 'active'));
    r := qa.f06_rec(r, 137, '§2 success results carry no "error" key (set_role result is a JSON object)', 'object/false',
      coalesce(pg_catalog.jsonb_typeof(res), 'null') || '/' || coalesce(res ? 'error', false)::text);

    -- ================= 2xx · member_rename (C6, D7, §2.2) =================
    res := qa.f06_rename(u_m1, mid_e1, '  Editor   Quinn  ');
    r := qa.f06_rec(r, 201, 'C6 rename by a manager → ok, stored cleaned (trim + single spaces)', 'ok/active/editor/Editor Quinn',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e1));
    res := qa.f06_rename(u_m1, mid_m1, 'דנה כהן');
    r := qa.f06_rec(r, 202, 'C6 D7 a manager renames THEMSELF → ok', 'ok/active/manager/דנה כהן',
      qa.f06_e(res) || '/' || qa.f06_row(mid_m1));
    res := qa.f06_rename(u_m1, mid_e1, 'EDITOR quinn');
    r := qa.f06_rec(r, 203, 'C6 D7 own name in another case (unique except itself) → ok, stored as given', 'ok/active/editor/EDITOR quinn',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e1));
    ct := qa.f06_ctid(mid_e2);
    r := qa.f06_rec(r, 204, 'C6 name of another ACTIVE member with extra spaces → name_taken', 'name_taken',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, '  צופה ')));
    r := qa.f06_rec(r, 205, 'C6 name of another ACTIVE member, other case + inner double space → name_taken', 'name_taken',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, 'editor  QUINN')));
    r := qa.f06_rec(r, 206, 'C6 name of a PENDING member → name_taken', 'name_taken',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, 'ממתין')));
    r := qa.f06_rec(r, 207, 'C6 name of a manager → name_taken', 'name_taken',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, 'דנה  כהן')));
    r := qa.f06_rec(r, 208, 'C6 empty name → name_invalid', 'name_invalid', qa.f06_e(qa.f06_rename(u_m1, mid_e2, '')));
    r := qa.f06_rec(r, 209, 'C6 spaces only → name_invalid', 'name_invalid', qa.f06_e(qa.f06_rename(u_m1, mid_e2, '     ')));
    r := qa.f06_rec(r, 210, 'C6 41 chars → name_invalid', 'name_invalid',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, pg_catalog.repeat('א', 41))));
    r := qa.f06_rec(r, 211, 'C6 null name → name_invalid (open: or invalid_request)', 'name_invalid or invalid_request',
      qa.f06_e(qa.f06_rename(u_m1, mid_e2, null)));
    r := qa.f06_rec(r, 212, 'C6 refusals 204–211 left the row untouched (ctid, name עורכת)', 'true/active/editor/עורכת',
      (qa.f06_ctid(mid_e2) = ct)::text || '/' || qa.f06_row(mid_e2));
    res := qa.f06_rename(u_m1, mid_e2, '  ' || pg_catalog.repeat('ב', 40) || '  ');
    r := qa.f06_rec(r, 213, 'C6 exactly 40 chars after trim → ok', 'ok/40',
      qa.f06_e(res) || '/' || (select pg_catalog.char_length(m.display_name)::text from public.trip_members m where m.id = mid_e2));
    res := qa.f06_rename(u_m1, mid_e2, 'הוסר');
    r := qa.f06_rec(r, 214, 'C6 D2 the name of a REMOVED member is free → ok', 'ok/active/editor/הוסר',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e2));
    res := qa.f06_rename(u_m1, mid_v1, 'tom');
    r := qa.f06_rec(r, 215, 'C6 C17 a name used in ANOTHER trip (T2 "Tom") → ok (unique per trip)', 'ok/active/viewer/tom',
      qa.f06_e(res) || '/' || qa.f06_row(mid_v1));
    res := qa.f06_rename(u_m1, mid_v1, E'צו\tפה');
    r := qa.f06_rec(r, 216, 'C6 a tab inside the name is collapsed to one space', 'ok/active/viewer/צו פה',
      qa.f06_e(res) || '/' || qa.f06_row(mid_v1));
    perform qa.f06_rename(u_m1, mid_v1, 'צופה');
    ct := qa.f06_ctid(mid_e3);
    r := qa.f06_rec(r, 217, 'C6 an editor renames another member → not_manager', 'not_manager',
      qa.f06_e(qa.f06_rename(u_e1, mid_e3, 'שם חדש')));
    r := qa.f06_rec(r, 218, 'C6 D7 an editor renames THEMSELF → not_manager (only managers rename)', 'not_manager',
      qa.f06_e(qa.f06_rename(u_e3, mid_e3, 'שם חדש')));
    r := qa.f06_rec(r, 219, 'C6 C17 a manager of another trip → not_manager', 'not_manager',
      qa.f06_e(qa.f06_rename(u_m2, mid_e3, 'שם חדש')));
    r := qa.f06_rec(r, 220, 'C6 refusals 217–219 left the row untouched', 'true/active/editor/יוצא',
      (qa.f06_ctid(mid_e3) = ct)::text || '/' || qa.f06_row(mid_e3));
    act := qa.f06_e(qa.f06_rename(u_m1, mid_p1, 'אחר'));
    r := qa.f06_rec(r, 221, 'C6 a PENDING target → not_active, name unchanged', 'not_active/pending/editor/ממתין',
      act || '/' || qa.f06_row(mid_p1));
    act := qa.f06_e(qa.f06_rename(u_m1, mid_x1, 'אחר'));
    r := qa.f06_rec(r, 222, 'C6 a REMOVED target → not_active, name unchanged', 'not_active/removed/manager/הוסר',
      act || '/' || qa.f06_row(mid_x1));
    r := qa.f06_rec(r, 223, 'C6 rename keeps role / status (manager renamed stays manager)', 'active/manager/דנה כהן', qa.f06_row(mid_m1));

    -- ================= 3xx · member_remove (C7, D12, §2.3) =================
    -- a real F05 transfer code of e2 (claimed after the removal), then extra open codes of e2 (two) and a used one; one open
    -- code of e1 that must survive
    res := qa.f06_issue(u_e2, t1); tcode := res->>'code';
    insert into private.transfer_codes (member_id, code_hash, expires_at, used_at) values
      (mid_e2, md5('f06-a') || md5('f06-a2'), now() + interval '20 hours', null),
      (mid_e2, md5('f06-b') || md5('f06-b2'), now() + interval '10 hours', null),
      (mid_e2, md5('f06-c') || md5('f06-c2'), now() + interval '10 hours', now() - interval '1 hour'),
      (mid_e1, md5('f06-d') || md5('f06-d2'), now() + interval '20 hours', null),
      (mid_e3, md5('f06-e') || md5('f06-e2'), now() + interval '20 hours', null);
    ct := qa.f06_ctid(mid_m1);
    act := qa.f06_e(qa.f06_remove(u_m1, mid_m1));
    r := qa.f06_rec(r, 301, 'C7 remove SELF → invalid_request (use leave), row untouched', 'invalid_request/true/active/manager/דנה כהן',
      act || '/' || (qa.f06_ctid(mid_m1) = ct)::text || '/' || qa.f06_row(mid_m1));
    res := qa.f06_remove(u_m1, mid_e2);
    r := qa.f06_rec(r, 302, 'C7 a manager removes an active editor → ok, status removed, the row is KEPT (D12)', 'ok/removed/1',
      qa.f06_e(res) || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_e2), '∅') || '/' ||
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_e2));
    r := qa.f06_rec(r, 303, 'C7 the removed member''s OPEN transfer codes are deleted', '0',
      (select count(*)::text from private.transfer_codes c where c.member_id = mid_e2 and c.used_at is null));
    r := qa.f06_rec(r, 318, 'C7 the removed member''s real transfer code can no longer be claimed → transfer_invalid, row stays removed',
      'transfer_invalid/removed/' || u_e2::text,
      qa.f06_e(qa.f06_claim(u_o, tcode, 'f06ip-claim')) || '/' ||
      coalesce((select m.status || '/' || m.user_id::text from public.trip_members m where m.id = mid_e2), '∅'));
    r := qa.f06_rec(r, 304, 'C7 other members'' open transfer codes are untouched', '1',
      (select count(*)::text from private.transfer_codes c where c.member_id = mid_e1 and c.used_at is null));
    r := qa.f06_rec(r, 305, 'D12 what the removed member wrote stays in the trip (trip_kv row updated_by = them)', '1',
      (select count(*)::text from public.trip_kv k where k.trip_id = t1 and k.key = 'expenses' and k.updated_by = u_e2));
    r := qa.f06_rec(r, 306, 'C7 C17 the removed member reads 0 rows of trips / trip_kv / trip_members of others', '0 rows',
      qa.f06_count(u_e2, au, pg_catalog.format(
        'select 1 from public.trips where id = %1$L union all select 1 from public.trip_kv where trip_id = %1$L
         union all select 1 from public.trip_members where trip_id = %1$L and user_id <> %2$L', t1, u_e2)));
    r := qa.f06_rec(r, 307, 'C7 the removed member cannot write trip_kv (RLS)', 'error 42501',
      qa.f06_kvset(u_e2, t1, 'expenses', '[]'));
    r := qa.f06_rec(r, 308, 'C7 removing an already removed member → not_active', 'not_active',
      qa.f06_e(qa.f06_remove(u_m1, mid_e2)));
    ct := qa.f06_ctid(mid_p1);
    act := qa.f06_e(qa.f06_remove(u_m1, mid_p1));
    r := qa.f06_rec(r, 309, 'C7 a PENDING target → not_active, row untouched (rejecting stays in approve-member)', 'not_active/true',
      act || '/' || (qa.f06_ctid(mid_p1) = ct)::text);
    ct := qa.f06_ctid(mid_e3);
    r := qa.f06_rec(r, 310, 'C7 an editor removes another member → not_manager', 'not_manager',
      qa.f06_e(qa.f06_remove(u_e1, mid_e3)));
    r := qa.f06_rec(r, 311, 'C7 C17 a manager of another trip → not_manager', 'not_manager',
      qa.f06_e(qa.f06_remove(u_m2, mid_e3)));
    r := qa.f06_rec(r, 312, 'C7 an outsider → not_manager', 'not_manager', qa.f06_e(qa.f06_remove(u_o, mid_e3)));
    r := qa.f06_rec(r, 313, 'C7 refusals 310–312 left the target active', 'true/active/editor/יוצא',
      (qa.f06_ctid(mid_e3) = ct)::text || '/' || qa.f06_row(mid_e3));
    r := qa.f06_rec(r, 314, 'C7 C17 a T2 manager removing a T1 member via T2 rights is impossible; T1 manager on a T2 member → not_manager',
      'not_manager/active/editor/Tom', qa.f06_e(qa.f06_remove(u_m1, mid_e9)) || '/' || qa.f06_row(mid_e9));
    r := qa.f06_rec(r, 315, 'C7 unknown member id → a refusal (open: not_active / not_member / not_manager / invalid_request)',
      'not_active or not_member or not_manager or invalid_request', qa.f06_e(qa.f06_remove(u_m1, unknown)));
    -- two managers removing each other: sequential stand-in for the concurrent case of §2.3
    res := qa.f06_remove(u_m1, mid_m1b);
    r := qa.f06_rec(r, 316, 'C7 with two managers, one removes the other → ok', 'ok/removed',
      qa.f06_e(res) || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_m1b), '∅'));
    ct := qa.f06_ctid(mid_m1);
    act := qa.f06_e(qa.f06_remove(u_m1b, mid_m1));
    r := qa.f06_rec(r, 317, 'C7 D6 the removed manager then removes the other → not_manager; the trip keeps its manager',
      'not_manager/true/1', act || '/' || (qa.f06_ctid(mid_m1) = ct)::text || '/' ||
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.role = 'manager' and m.status = 'active'));
    update public.trip_members set status = 'active' where id = mid_m1b;   -- restore two managers

    -- ================= 4xx · member_leave (C10, D5, D6, §2.4) =================
    res := qa.f06_leave(u_e3, t1);
    r := qa.f06_rec(r, 401, 'C10 D5 an editor leaves → ok, own row removed (kept)', 'ok/removed/editor/יוצא',
      qa.f06_e(res) || '/' || qa.f06_row(mid_e3));
    r := qa.f06_rec(r, 402, 'C10 the leaver''s open transfer codes are deleted', '0',
      (select count(*)::text from private.transfer_codes c where c.member_id = mid_e3 and c.used_at is null));
    r := qa.f06_rec(r, 403, 'C10 leave again (row removed) → refused (open: not_member / not_active)', 'not_member or not_active',
      qa.f06_e(qa.f06_leave(u_e3, t1)));
    r := qa.f06_rec(r, 404, 'C10 C17 an outsider leaves a trip → not_member', 'not_member',
      qa.f06_e(qa.f06_leave(u_o, t1)));
    ct := qa.f06_ctid(mid_p1);
    act := qa.f06_e(qa.f06_leave(u_p1, t1));
    r := qa.f06_rec(r, 405, 'C10 a PENDING member leaves → refused (open: not_member / not_active), row still pending (cancel is join_cancel)',
      'not_member/true or not_active/true', act || '/' || (qa.f06_ctid(mid_p1) = ct)::text);
    ct := qa.f06_ctid(mid_s);
    act := qa.f06_e(qa.f06_leave(u_s, t3));
    r := qa.f06_rec(r, 406, 'C10 D6 the ONLY manager (only member) leaves → last_manager, returned not raised, no write',
      'last_manager/true/active/manager/סולו', act || '/' || (qa.f06_ctid(mid_s) = ct)::text || '/' || qa.f06_row(mid_s));
    res := qa.f06_leave(u_m1b, t1);
    r := qa.f06_rec(r, 407, 'C10 with two managers, one leaves → ok', 'ok/removed', qa.f06_e(res) || '/' ||
      coalesce((select m.status from public.trip_members m where m.id = mid_m1b), '∅'));
    ct := qa.f06_ctid(mid_m1);
    act := qa.f06_e(qa.f06_leave(u_m1, t1));
    r := qa.f06_rec(r, 408, 'C10 D6 the now-only manager (other members exist) leaves → last_manager, no write',
      'last_manager/true/active/manager', act || '/' || (qa.f06_ctid(mid_m1) = ct)::text || '/' ||
      (select m.status || '/' || m.role from public.trip_members m where m.id = mid_m1));
    update public.trip_members set status = 'active', role = 'manager' where id = mid_m1b;   -- restore
    r := qa.f06_rec(r, 409, 'C10 null trip → refused (open: invalid_request / not_member)', 'invalid_request or not_member',
      qa.f06_e(qa.f06_leave(u_v1, null)));
    r := qa.f06_rec(r, 410, 'C10 C17 a T2 manager "leaves" T1 (not a member there) → not_member; still active in T2', 'not_member/active',
      qa.f06_e(qa.f06_leave(u_m2, t1)) || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_m2), '∅'));
    res := qa.f06_leave(u_m3, t1);
    r := qa.f06_rec(r, 411, 'C10 C17 leaving T1 does not touch the same identity''s T2 membership (manager there)', 'ok/removed/active/manager',
      qa.f06_e(res) || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_m3), '∅') || '/' ||
      coalesce((select m.status || '/' || m.role from public.trip_members m where m.trip_id = t2 and m.user_id = u_m3), '∅'));
    update public.trip_members set status = 'active' where id = mid_m3;   -- restore (used by the trigger cases)

    -- ================= 5xx · rotate_join_code (C11, D3, §2.5) =================
    res := qa.f06_issue(u_tr, t1); tcode := res->>'code';                 -- F05 transfer code issued BEFORE the rotation
    select count(*) into n from public.trip_members m where m.trip_id = t1 and m.status = 'pending';
    select count(*) into n2 from public.trip_members m where m.trip_id = t1 and m.status = 'active';
    ct := qa.f06_ctid(mid_p1);
    select string_agg(m.id || m.role || m.ctid::text, ',' order by m.id) into ct2 from public.trip_members m where m.trip_id = t1 and m.status = 'active';
    res := qa.f06_rotate(u_m1, t1); v_code := res->>'code';
    r := qa.f06_rec(r, 501, 'C11 rotate by a manager → ok, {code: 8 chars of the F01 alphabet, version: 2}', 'ok/true/2',
      qa.f06_e(res) || '/' || coalesce(v_code ~ alpha, false)::text || '/' || coalesce(res->>'link_version', res->>'version', '∅'));
    r := qa.f06_rec(r, 502, 'C11 trip_join_codes: one row, code = returned code, version 2, rotated_at moved to now', '1/true/2/true',
      (select count(*)::text from public.trip_join_codes j where j.trip_id = t1) || '/' ||
      coalesce((select (j.code = v_code)::text from public.trip_join_codes j where j.trip_id = t1), '∅') || '/' ||
      coalesce((select j.version::text from public.trip_join_codes j where j.trip_id = t1), '∅') || '/' ||
      coalesce((select (j.rotated_at >= now())::text from public.trip_join_codes j where j.trip_id = t1), '∅'));
    r := qa.f06_rec(r, 503, 'C11 the new code differs from the old one and from every other trip''s code', 'true/0',
      (coalesce(v_code, c1) <> c1)::text || '/' ||
      (select count(*)::text from public.trip_join_codes j where j.trip_id <> t1 and j.code = v_code));
    r := qa.f06_rec(r, 504, 'C11 D3 the OLD link stops at once: preview / request → code_invalid', 'code_invalid/code_invalid',
      qa.f06_e(qa.f06_prev(u_o, c1, 'f06ip-o1')) || '/' || qa.f06_e(qa.f06_req(u_o, c1, 'חדש', 'f06ip-o1')));
    res := qa.f06_prev(u_o, v_code, 'f06ip-o2');
    r := qa.f06_rec(r, 505, 'C11 the new code previews the same trip', 'ok/true', qa.f06_e(res) || '/' || ((res->>'trip_id') = t1::text)::text);
    r := qa.f06_rec(r, 506, 'C11 D3 pending requests stay (count and the pending row untouched)', 'true/true',
      ((select count(*) from public.trip_members m where m.trip_id = t1 and m.status = 'pending') = n)::text || '/' ||
      (qa.f06_ctid(mid_p1) = ct)::text);
    r := qa.f06_rec(r, 507, 'C11 active members are unaffected (same rows, roles, tuples)', 'true/true',
      ((select count(*) from public.trip_members m where m.trip_id = t1 and m.status = 'active') = n2)::text || '/' ||
      ((select string_agg(m.id || m.role || m.ctid::text, ',' order by m.id) from public.trip_members m where m.trip_id = t1 and m.status = 'active') = ct2)::text);
    res := qa.f06_claim(u_t1, tcode, 'f06ip-t1');
    r := qa.f06_rec(r, 508, 'C11 D3 an F05 transfer code issued before the rotation is still claimable', 'ok/true',
      qa.f06_e(res) || '/' || coalesce((select (m.user_id = u_t1)::text from public.trip_members m where m.id = mid_tr), '∅'));
    res := qa.f06_rotate(u_m1b, t1); v_code2 := res->>'code';
    r := qa.f06_rec(r, 509, 'C11 a second rotation (other manager) → version 3, another code', 'ok/3/true',
      qa.f06_e(res) || '/' || coalesce(res->>'link_version', res->>'version', '∅') || '/' || (coalesce(v_code2, v_code) <> v_code)::text);
    codes := array[c1, v_code, v_code2];
    for k in 1..20 loop
      res := qa.f06_rotate(u_m1, t1);
      codes := codes || (res->>'code');
    end loop;
    r := qa.f06_rec(r, 510, 'C11 20 more rotations: every code valid and distinct; version = 23', '23/23/23',
      (select count(distinct c)::text from unnest(codes) c where c ~ alpha) || '/' ||
      pg_catalog.array_length(codes, 1)::text || '/' ||
      coalesce((select (j.version + 0)::text from public.trip_join_codes j where j.trip_id = t1), '∅'));
    select j.code, j.version into v_code, ver from public.trip_join_codes j where j.trip_id = t1;
    r := qa.f06_rec(r, 511, 'C11 an editor rotates → not_manager, code unchanged', 'not_manager/true',
      qa.f06_e(qa.f06_rotate(u_e1, t1)) || '/' || ((select j.code from public.trip_join_codes j where j.trip_id = t1) = v_code)::text);
    r := qa.f06_rec(r, 512, 'C11 a viewer rotates → not_manager', 'not_manager', qa.f06_e(qa.f06_rotate(u_v1, t1)));
    r := qa.f06_rec(r, 513, 'C11 C17 a manager of ANOTHER trip rotates T1 → not_manager, T1 code / version unchanged', 'not_manager/true',
      qa.f06_e(qa.f06_rotate(u_m2, t1)) || '/' ||
      ((select j.code || j.version from public.trip_join_codes j where j.trip_id = t1) = v_code || ver)::text);
    r := qa.f06_rec(r, 514, 'C11 an outsider / a removed ex-manager / a pending member rotate → not_manager', 'not_manager/not_manager/not_manager',
      qa.f06_e(qa.f06_rotate(u_o, t1)) || '/' || qa.f06_e(qa.f06_rotate(u_x1, t1)) || '/' || qa.f06_e(qa.f06_rotate(u_p1, t1)));
    r := qa.f06_rec(r, 515, 'C11 null / unknown trip → refused (open: invalid_request / not_manager)', 'invalid_request/not_manager or not_manager/not_manager or invalid_request/invalid_request or not_manager/invalid_request',
      qa.f06_e(qa.f06_rotate(u_m1, null)) || '/' || qa.f06_e(qa.f06_rotate(u_m1, unknown)));
    r := qa.f06_rec(r, 516, 'C11 C17 the other trips'' join codes are untouched', 'F6QAJNBB/1/F6QAJNCC/1',
      (select j.code || '/' || j.version from public.trip_join_codes j where j.trip_id = t2) || '/' ||
      (select j.code || '/' || j.version from public.trip_join_codes j where j.trip_id = t3));

    -- ================= 6xx · member_touch / last_seen_at (C16, §2.8) =================
    res := qa.f06_touch(u_v1, t1);
    r := qa.f06_rec(r, 601, 'C16 touch by an active member with last_seen_at null → ok, last_seen_at = now', 'ok/true',
      qa.f06_e(res) || '/' || coalesce((select (m.last_seen_at between now() - interval '1 second' and pg_catalog.clock_timestamp())::text
                                            from public.trip_members m where m.id = mid_v1), '∅'));
    ct := qa.f06_ctid(mid_v1);
    select m.last_seen_at into ts from public.trip_members m where m.id = mid_v1;
    res := qa.f06_touch(u_v1, t1);
    r := qa.f06_rec(r, 602, 'C16 a second touch at once → ok, no write (ctid and last_seen_at unchanged)', 'ok/true/true',
      qa.f06_e(res) || '/' || (qa.f06_ctid(mid_v1) = ct)::text || '/' ||
      ((select m.last_seen_at from public.trip_members m where m.id = mid_v1) = ts)::text);
    update public.trip_members set last_seen_at = now() - interval '9 minutes' where id = mid_v1;
    ct := qa.f06_ctid(mid_v1);
    res := qa.f06_touch(u_v1, t1);
    r := qa.f06_rec(r, 603, 'C16 last touch 9 min ago → ok, no write (at most once per 10 min)', 'ok/true/true',
      qa.f06_e(res) || '/' || (qa.f06_ctid(mid_v1) = ct)::text || '/' ||
      ((select m.last_seen_at from public.trip_members m where m.id = mid_v1) = now() - interval '9 minutes')::text);
    update public.trip_members set last_seen_at = now() - interval '11 minutes' where id = mid_v1;
    res := qa.f06_touch(u_v1, t1);
    r := qa.f06_rec(r, 604, 'C16 last touch 11 min ago → ok, last_seen_at moved to now', 'ok/true',
      qa.f06_e(res) || '/' || coalesce((select (m.last_seen_at >= now() - interval '1 second')::text from public.trip_members m where m.id = mid_v1), '∅'));
    r := qa.f06_rec(r, 605, 'C16 touch changes nothing else (role / status / name)', 'active/viewer/צופה', qa.f06_row(mid_v1));
    res := qa.f06_touch(u_m1, t1);
    r := qa.f06_rec(r, 606, 'C16 a manager''s touch → ok, own row only (other rows'' last_seen_at untouched)', 'ok/true/0',
      qa.f06_e(res) || '/' || coalesce((select (m.last_seen_at is not null)::text from public.trip_members m where m.id = mid_m1), '∅') || '/' ||
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.id not in (mid_m1, mid_v1) and m.last_seen_at is not null));
    r := qa.f06_rec(r, 607, 'C16 C17 an outsider touches a trip → refused (open: not_member / not_active)', 'not_member or not_active',
      qa.f06_e(qa.f06_touch(u_o, t1)));
    r := qa.f06_rec(r, 608, 'C16 a pending / a removed member touches → refused, no last_seen_at written', 'true/true/0',
      (qa.f06_e(qa.f06_touch(u_p1, t1)) in ('not_member', 'not_active'))::text || '/' ||
      (qa.f06_e(qa.f06_touch(u_x1, t1)) in ('not_member', 'not_active'))::text || '/' ||
      (select count(*)::text from public.trip_members m where m.id in (mid_p1, mid_x1) and m.last_seen_at is not null));
    r := qa.f06_rec(r, 609, 'C16 C17 a T1 member touching T2 → refused (open: not_member / not_active)', 'not_member or not_active',
      qa.f06_e(qa.f06_touch(u_v1, t2)));

    -- ================= 7xx · D2: a removed identity asks again (C9, §2.6) =================
    res := qa.f06_prev(u_x1, v_code, 'f06ip-x1');
    r := qa.f06_rec(r, 701, 'C9 D2 preview by a REMOVED identity → no error (not member_removed); me = null as a new identity (open: me.status removed)',
      'ok/null or ok/removed', qa.f06_e(res) || '/' || coalesce(res->'me'->>'status', 'null'));
    r := qa.f06_rec(r, 702, 'C9 preview by a removed identity: the trip is shown (name / trip_id)', 'true',
      ((res->>'trip_id') = t1::text and res ? 'name')::text);
    select count(*) into n from public.trip_members m where m.trip_id = t1;
    act := qa.f06_e(qa.f06_req(u_x1, v_code, 'דנה כהן', 'f06ip-x1'));
    r := qa.f06_rec(r, 703, 'C9 re-request with a TAKEN name → name_taken; the row stays removed, no new row', 'name_taken/removed/true',
      act || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_x1), '∅') || '/' ||
      ((select count(*) from public.trip_members m where m.trip_id = t1) = n)::text);
    act := qa.f06_e(qa.f06_req(u_x1, v_code, '   ', 'f06ip-x1'));
    r := qa.f06_rec(r, 704, 'C9 re-request with an empty name → name_invalid; row stays removed', 'name_invalid/removed',
      act || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_x1), '∅'));
    select count(*) into n2 from private.join_attempts a where a.kind = 'request' and a.user_id = u_x1 and a.trip_id = t1 and a.ok;
    res := qa.f06_req(u_x1, v_code, '  חוזר   שוב ', 'f06ip-x1');
    r := qa.f06_rec(r, 705, 'C9 D2 re-request → ok, pending, SAME member id', 'ok/pending/true',
      qa.f06_e(res) || '/' || coalesce(res->>'status', '∅') || '/' || ((res->>'member_id') = mid_x1::text)::text);
    r := qa.f06_rec(r, 706, 'C9 §2.6 the same row: one row for the identity, pending, new cleaned name, role = trip default (was manager)',
      '1/pending/editor/חוזר שוב',
      (select count(*)::text from public.trip_members m where m.trip_id = t1 and m.user_id = u_x1) || '/' || qa.f06_row(mid_x1));
    r := qa.f06_rec(r, 707, 'C9 §2.6 joined_at = now, approved_at = null', 'true/true',
      coalesce((select (m.joined_at >= now() - interval '1 second')::text from public.trip_members m where m.id = mid_x1), '∅') || '/' ||
      coalesce((select (m.approved_at is null)::text from public.trip_members m where m.id = mid_x1), '∅'));
    r := qa.f06_rec(r, 708, 'C9 §2.6 the re-request counts as a successful request attempt (limits apply as for a new one)', '1',
      ((select count(*) from private.join_attempts a where a.kind = 'request' and a.user_id = u_x1 and a.trip_id = t1 and a.ok) - n2)::text);
    res := qa.f06_req(u_x1, v_code, 'שם אחר', 'f06ip-x1');
    r := qa.f06_rec(r, 709, 'C9 request again while pending → same row, name unchanged (F05 D7)', 'ok/true/pending/editor/חוזר שוב',
      qa.f06_e(res) || '/' || ((res->>'member_id') = mid_x1::text)::text || '/' || qa.f06_row(mid_x1));
    res := qa.f06_prev(u_x1, v_code, 'f06ip-x1');
    r := qa.f06_rec(r, 710, 'C9 preview now shows me.status = pending with the same member id', 'pending/true',
      coalesce(res->'me'->>'status', '∅') || '/' || ((res->'me'->>'member_id') = mid_x1::text)::text);
    res := qa.f06_appr(u_m1, mid_x1, 'approve', null);
    r := qa.f06_rec(r, 711, 'C9 the manager approves → active again (same row, default role)', 'ok/active/editor/חוזר שוב',
      qa.f06_e(res) || '/' || qa.f06_row(mid_x1));
    r := qa.f06_rec(r, 712, 'C9 the re-approved member reads the trip again', '1 rows',
      qa.f06_count(u_x1, au, pg_catalog.format('select 1 from public.trips where id = %L', t1)));
    -- limits: 3 successful requests per (user, trip) per 24 h
    insert into private.join_attempts (kind, user_id, trip_id, ip_hash, ok, at)
      select 'request', u_x3, t1, 'f06ip-x3-old', true, now() - (k2 || ' hours')::interval from generate_series(1, 3) k2;
    ct := qa.f06_ctid(mid_x3);
    act := qa.f06_e(qa.f06_req(u_x3, v_code, 'שלוש', 'f06ip-x3'));
    r := qa.f06_rec(r, 713, 'C9 F05 limit: 4th request in 24 h by a removed identity → rate_limited, row untouched (removed)',
      'rate_limited/true/removed', act || '/' || (qa.f06_ctid(mid_x3) = ct)::text || '/' ||
      coalesce((select m.status from public.trip_members m where m.id = mid_x3), '∅'));
    update private.join_attempts a set at = a.at - interval '25 hours' where a.user_id = u_x3 and a.ip_hash = 'f06ip-x3-old';
    res := qa.f06_req(u_x3, v_code, 'שלוש', 'f06ip-x3');
    r := qa.f06_rec(r, 714, 'C9 after 24 h (back-dated 25 h) → ok, same row pending', 'ok/true/pending',
      qa.f06_e(res) || '/' || ((res->>'member_id') = mid_x3::text)::text || '/' ||
      coalesce((select m.status from public.trip_members m where m.id = mid_x3), '∅'));
    -- limits: 10 attempts per ip_hash per hour
    insert into private.join_attempts (kind, user_id, trip_id, ip_hash, ok)
      select 'request', pg_catalog.gen_random_uuid(), null, 'f06ip-flood', false from generate_series(1, 10);
    act := qa.f06_e(qa.f06_req(u_x4, v_code, 'ארבע', 'f06ip-flood'));
    r := qa.f06_rec(r, 715, 'C9 F05 limit: 11th request from one ip_hash in an hour (removed identity) → rate_limited, still removed',
      'rate_limited/removed', act || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_x4), '∅'));
    -- limits: 20 pending per trip
    for k in 1..20 loop
      g := pg_catalog.gen_random_uuid();
      insert into auth.users (id) values (g);
      insert into public.trip_members (trip_id, user_id, display_name, role, status) values (t4, g, 'pend' || k, 'editor', 'pending');
    end loop;
    act := qa.f06_e(qa.f06_req(u_x2, c4, 'עשרים ואחת', 'f06ip-x2'));
    r := qa.f06_rec(r, 716, 'C9 F05 limit: 20 pending in the trip → the removed identity''s request is rate_limited, row stays removed',
      'rate_limited/removed/20', act || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_x2), '∅') || '/' ||
      (select count(*)::text from public.trip_members m where m.trip_id = t4 and m.status = 'pending'));
    -- name rules: the old own name taken meanwhile by someone else
    res := qa.f06_req(u_n, v_code, 'הוסר4', 'f06ip-n');
    act := qa.f06_e(qa.f06_req(u_x4, v_code, ' הוסר4 ', 'f06ip-x4b'));
    r := qa.f06_rec(r, 717, 'C9 D2 the removed member''s old name was taken by a new requester → name_taken for the returning one',
      'ok/name_taken/removed', qa.f06_e(res) || '/' || act || '/' || coalesce((select m.status from public.trip_members m where m.id = mid_x4), '∅'));
    -- a member who LEFT asks again (D12: leave = removed)
    res := qa.f06_req(u_e3, v_code, 'יוצא', 'f06ip-e3');
    r := qa.f06_rec(r, 718, 'C9 D5 a member who LEFT asks again → same row pending, role = trip default', 'ok/true/pending/editor/יוצא',
      qa.f06_e(res) || '/' || ((res->>'member_id') = mid_e3::text)::text || '/' || qa.f06_row(mid_e3));
    res := qa.f06_req(u_x5, c2, 'חוזר לקבוצה', 'f06ip-x5');
    r := qa.f06_rec(r, 719, 'C9 §2.6 in a trip with default_role viewer the re-request gets viewer (same row)', 'ok/true/pending/viewer/חוזר לקבוצה',
      qa.f06_e(res) || '/' || ((res->>'member_id') = mid_x5::text)::text || '/' || qa.f06_row(mid_x5));
    r := qa.f06_rec(r, 720, '§2.6 the removed-member refusal code is no longer produced (no actual result in 701–719 carried it)', 'true',
      coalesce((select not bool_or(split_part(e->>'detail', '| actual: ', 2) like '%member_removed%')
                  from pg_catalog.jsonb_array_elements(r) e where (e->>'id')::int between 701 and 719), false)::text);

    -- ================= 8xx · trip name trigger (C15, D4, §2.7) =================
    v := qa.f06_kvset(u_m1, t1, 'tripname', E'  F06   טוקיו\t2027  ');
    r := qa.f06_rec(r, 801, 'C15 D4 a MANAGER writes tripname (upsert of an existing key) → the kv write succeeds', '1', v);
    r := qa.f06_rec(r, 802, 'C15 trips.name = the cleaned value (trimmed, whitespace collapsed)', 'F06 טוקיו 2027',
      (select t.name from public.trips t where t.id = t1));
    r := qa.f06_rec(r, 803, '§2.7 the kv row keeps the value as written (trigger is AFTER, kv untouched) and updated_by = the manager',
      'true/true', ((select k.value from public.trip_kv k where k.trip_id = t1 and k.key = 'tripname') = E'  F06   טוקיו\t2027  ')::text || '/' ||
      ((select k.updated_by from public.trip_kv k where k.trip_id = t1 and k.key = 'tripname') = u_m1)::text);
    res := qa.f06_prev(u_o, v_code, 'f06ip-o3');
    r := qa.f06_rec(r, 804, 'C15 the join preview shows the new trip name', 'F06 טוקיו 2027', coalesce(res->>'name', qa.f06_e(res)));
    v := qa.f06_kvset(u_e1, t1, 'tripname', 'עורך שינה');
    r := qa.f06_rec(r, 805, 'C15 an EDITOR writes tripname → kv write ok, trips.name unchanged', '1/F06 טוקיו 2027/עורך שינה',
      v || '/' || (select t.name from public.trips t where t.id = t1) || '/' ||
      (select k.value from public.trip_kv k where k.trip_id = t1 and k.key = 'tripname'));
    v := qa.f06_kvset(u_v1, t1, 'tripname', 'צופה שינה');
    r := qa.f06_rec(r, 806, 'C15 a VIEWER write is refused by RLS (unchanged F01 rule), trips.name unchanged', 'error 42501/F06 טוקיו 2027',
      left(v, 11) || '/' || (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', '');
    r := qa.f06_rec(r, 807, 'C15 a manager writes a 0-char value → kv write ok (value ''''), trips.name unchanged', '1/true/F06 טוקיו 2027',
      v || '/' || ((select k.value from public.trip_kv k where k.trip_id = t1 and k.key = 'tripname') = '')::text || '/' ||
      (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', '      ');
    r := qa.f06_rec(r, 808, 'C15 spaces only (0 chars after cleaning) → kv write ok, trips.name unchanged', '1/F06 טוקיו 2027',
      v || '/' || (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', pg_catalog.repeat('ש', 81));
    r := qa.f06_rec(r, 809, 'C15 an 81-char value → kv write ok (81 chars stored), trips.name unchanged (never raises)', '1/81/F06 טוקיו 2027',
      v || '/' || (select pg_catalog.char_length(k.value)::text from public.trip_kv k where k.trip_id = t1 and k.key = 'tripname') || '/' ||
      (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', null);
    r := qa.f06_rec(r, 810, 'C15 a null value → kv write ok, trips.name unchanged', '1/F06 טוקיו 2027',
      v || '/' || (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', pg_catalog.repeat('ת', 80));
    r := qa.f06_rec(r, 811, 'C15 exactly 80 chars → trips.name updated', '1/80',
      v || '/' || (select pg_catalog.char_length(t.name)::text from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m1, t1, 'tripname', '   ' || pg_catalog.repeat('ק', 80) || '   ');
    r := qa.f06_rec(r, 812, 'C15 80 chars + surrounding spaces (range applies after cleaning) → trips.name updated to the 80 chars', '1/true',
      v || '/' || ((select t.name from public.trips t where t.id = t1) = pg_catalog.repeat('ק', 80))::text);
    v := qa.f06_val(u_m1, au, pg_catalog.format(
      'with w as (update public.trip_kv set value = %L where trip_id = %L and key = ''tripname'' returning 1) select count(*)::text from w',
      'F06 קיוטו', t1));
    r := qa.f06_rec(r, 813, 'C15 a plain UPDATE of value by a manager → trips.name updated', '1/F06 קיוטו',
      v || '/' || (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_s, t3, 'tripname', 'F06 סולו חדש');
    r := qa.f06_rec(r, 814, 'C15 a manager INSERTs tripname (no row before) → trips.name updated', '1/F06 סולו חדש',
      v || '/' || (select t.name from public.trips t where t.id = t3));
    v := qa.f06_kvset(u_m1, t1, 'notes', 'F06 לא שם');
    r := qa.f06_rec(r, 815, '§2.7 a manager writes another key → trips.name unchanged', '1/F06 קיוטו',
      v || '/' || (select t.name from public.trips t where t.id = t1));
    v := qa.f06_kvset(u_m3, t1, 'tripname', 'F06 מנהל זר');
    r := qa.f06_rec(r, 816, 'C15 C17 a manager of T2 who is only an EDITOR of T1 writes T1 tripname → kv ok, T1 and T2 names unchanged',
      '1/F06 קיוטו/F06 קבוצה 2', v || '/' || (select t.name from public.trips t where t.id = t1) || '/' ||
      (select t.name from public.trips t where t.id = t2));
    perform qa.f06_setrole(u_m1, mid_m1b, 'editor');
    v := qa.f06_kvset(u_m1b, t1, 'tripname', 'F06 מנהל לשעבר');
    r := qa.f06_rec(r, 817, 'C15 C5 a manager demoted to editor writes tripname → kv ok, trips.name unchanged', '1/F06 קיוטו',
      v || '/' || (select t.name from public.trips t where t.id = t1));
    perform qa.f06_setrole(u_m1, mid_m1b, 'manager');
    perform qa.f06_as(null, 'postgres');
    update public.trip_kv set value = 'F06 ייבוא שרת' where trip_id = t1 and key = 'tripname';
    r := qa.f06_rec(r, 818, 'C15 §2.7 a service-role / SQL write (auth.uid() null = not an active manager) → kv ok, trips.name unchanged',
      'F06 קיוטו', (select t.name from public.trips t where t.id = t1));

    -- ================= 85x · cross-trip isolation summary (C17) =================
    r := qa.f06_rec(r, 850, 'C17 nothing above changed any T2 member row except the T2 re-request of 719', 'true',
      ((select string_agg(m.id || ':' || m.status || ':' || m.role || ':' || m.display_name || ':' || m.ctid::text, ';' order by m.id)
          from public.trip_members m where m.trip_id = t2 and m.id <> mid_x5)
       = (select string_agg(x, ';' order by x) from unnest(pg_catalog.string_to_array(t2_snap, ';')) x where x not like mid_x5::text || ':%'))::text);
    r := qa.f06_rec(r, 851, 'C17 T2 join code and name unchanged by every T1 action', 'F6QAJNBB/1/F06 קבוצה 2',
      (select j.code || '/' || j.version from public.trip_join_codes j where j.trip_id = t2) || '/' ||
      (select t.name from public.trips t where t.id = t2));
    r := qa.f06_rec(r, 852, 'C17 an authenticated client cannot call member_set_role directly', 'error 42501',
      qa.f06_val(u_m1, au, pg_catalog.format('select public.member_set_role(%L::uuid, %L::uuid, ''viewer'')::text', u_m1, mid_e1)));
    r := qa.f06_rec(r, 853, 'C17 anon cannot call rotate_join_code directly', 'error 42501',
      qa.f06_val(null, 'anon', pg_catalog.format('select public.rotate_join_code(%L::uuid, %L::uuid)::text', u_m1, t1)));
    r := qa.f06_rec(r, 854, 'C17 an authenticated client cannot call member_remove / member_leave / member_touch / member_rename directly',
      'error 42501/error 42501/error 42501/error 42501',
      left(qa.f06_val(u_m1, au, pg_catalog.format('select public.member_remove(%L::uuid, %L::uuid)::text', u_m1, mid_e1)), 11) || '/' ||
      left(qa.f06_val(u_v1, au, pg_catalog.format('select public.member_leave(%L::uuid, %L::uuid)::text', u_v1, t1)), 11) || '/' ||
      left(qa.f06_val(u_v1, au, pg_catalog.format('select public.member_touch(%L::uuid, %L::uuid)::text', u_v1, t1)), 11) || '/' ||
      left(qa.f06_val(u_m1, au, pg_catalog.format('select public.member_rename(%L::uuid, %L::uuid, ''x'')::text', u_m1, mid_e1)), 11));
    r := qa.f06_rec(r, 855, 'C17 a manager still cannot update trip_members directly (no client grant)', 'error 42501',
      qa.f06_val(u_m1, au, pg_catalog.format('with u as (update public.trip_members set role = ''viewer'' where id = %L returning 1) select count(*)::text from u', mid_e1)));
    r := qa.f06_rec(r, 856, 'C17 a manager still cannot update trip_join_codes directly', 'error 42501',
      qa.f06_val(u_m1, au, pg_catalog.format('with u as (update public.trip_join_codes set version = version + 1 where trip_id = %L returning 1) select count(*)::text from u', t1)));

    perform qa.f06_as(null, 'postgres');
    raise exception 'f06_rollback';
  exception when others then
    if sqlerrm <> 'f06_rollback' then
      r := r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
        'id', 0, 'name', 'unexpected error (setup or harness) — later scenarios did not run',
        'detail', 'expected: no error | actual: error ' || sqlstate || ' ' || sqlerrm, 'pass', false));
    end if;
  end;

  perform qa.f06_as(null, 'postgres');

  -- ================= 9xx · catalog (read-only, outside the rolled-back block) — C17, §2 =================
  r := qa.f06_rec(r, 900, '§2 the six entry functions exist with the spec signatures (uuid args, text role / name)', '6',
    (select count(*)::text from unnest(array['public.member_set_role(uuid,uuid,text)', 'public.member_rename(uuid,uuid,text)',
       'public.member_remove(uuid,uuid)', 'public.member_leave(uuid,uuid)', 'public.rotate_join_code(uuid,uuid)',
       'public.member_touch(uuid,uuid)']) s where pg_catalog.to_regprocedure(s) is not null));
  r := qa.f06_rec(r, 901, '§2 / §3.1 parameter names exactly as the spec (the Edge Function calls them by name)', '6',
    (select count(*)::text from (values
       ('public.member_set_role(uuid,uuid,text)', 'p_user uuid, p_member uuid, p_role text'),
       ('public.member_rename(uuid,uuid,text)',   'p_user uuid, p_member uuid, p_name text'),
       ('public.member_remove(uuid,uuid)',        'p_user uuid, p_member uuid'),
       ('public.member_leave(uuid,uuid)',         'p_user uuid, p_trip uuid'),
       ('public.rotate_join_code(uuid,uuid)',     'p_user uuid, p_trip uuid'),
       ('public.member_touch(uuid,uuid)',         'p_user uuid, p_trip uuid')) x(s, a)
      where pg_catalog.to_regprocedure(x.s) is not null
        and pg_catalog.pg_get_function_identity_arguments(pg_catalog.to_regprocedure(x.s)) = x.a));
  r := qa.f06_rec(r, 902, '§2 F05 pattern: all six return jsonb ({"error":code} returned, not raised)', '6',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch')
        and p.prorettype = 'jsonb'::regtype));
  r := qa.f06_rec(r, 903, '§2 all six: security definer, search_path=''''', '6/6',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch')
        and p.prosecdef) || '/' ||
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch')
        and p.proconfig @> array['search_path=""']));
  r := qa.f06_rec(r, 904, 'C17 anon / authenticated / PUBLIC cannot execute any F06 function (6 entry, private.f06_*, the tripname trigger function)', '0',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where ((s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch'))
             or (s.nspname = 'private' and p.proname like 'f06%')
             or p.oid in (select t.tgfoid from pg_catalog.pg_trigger t where t.tgrelid = 'public.trip_kv'::regclass and not t.tgisinternal
                            and t.tgname not in ('trip_kv_before_update', 'trip_kv_set_updated_by')))
        and (pg_catalog.has_function_privilege('anon', p.oid, 'execute') or pg_catalog.has_function_privilege('authenticated', p.oid, 'execute')
             or exists (select 1 from pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
                         where a.grantee = 0 and a.privilege_type = 'EXECUTE'))));
  r := qa.f06_rec(r, 905, '§2 service_role can execute the six entry functions', '6',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch')
        and pg_catalog.has_function_privilege('service_role', p.oid, 'execute')));
  r := qa.f06_rec(r, 906, '§2 no overloads: exactly one function per entry name', '6',
    (select count(distinct p.proname)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch')
      having count(*) = count(distinct p.proname)));
  r := qa.f06_rec(r, 907, '§2.7 exactly one new trigger on trip_kv: AFTER, FOR EACH ROW, INSERT + UPDATE (of value), WHEN key = tripname',
    '1/true/true/true/true/true',
    (select count(*)::text from pg_catalog.pg_trigger t where t.tgrelid = 'public.trip_kv'::regclass and not t.tgisinternal
        and t.tgname not in ('trip_kv_before_update', 'trip_kv_set_updated_by')) || '/' ||
    coalesce((select bool_and(
        (t.tgtype & 2) = 0                                  -- not BEFORE
        )::text || '/' || bool_and((t.tgtype & 1) = 1)::text || '/' ||   -- ROW
        bool_and((t.tgtype & 4) = 4)::text || '/' ||                       -- INSERT
        bool_and((t.tgtype & 16) = 16)::text || '/' ||                     -- UPDATE
        bool_and(pg_catalog.pg_get_triggerdef(t.oid) ~* 'when \(.*key.*tripname')::text
       from pg_catalog.pg_trigger t where t.tgrelid = 'public.trip_kv'::regclass and not t.tgisinternal
        and t.tgname not in ('trip_kv_before_update', 'trip_kv_set_updated_by')), '∅'));
  r := qa.f06_rec(r, 908, '§2.7 the trigger is "update OF value" (open: plain UPDATE also accepted)', 'true or false (plain update)',
    coalesce((select case when count(*) = 0 then null when bool_and(pg_catalog.pg_get_triggerdef(t.oid) ~* 'update of value') then 'true' else 'false (plain update)' end
       from pg_catalog.pg_trigger t where t.tgrelid = 'public.trip_kv'::regclass and not t.tgisinternal
        and t.tgname not in ('trip_kv_before_update', 'trip_kv_set_updated_by')), '∅'));
  r := qa.f06_rec(r, 909, '§2.7 the trigger function is security definer with search_path=''''', 'true/true',
    coalesce((select bool_and(p.prosecdef)::text || '/' || bool_and(coalesce(p.proconfig @> array['search_path=""'], false))::text
       from pg_catalog.pg_trigger t join pg_catalog.pg_proc p on p.oid = t.tgfoid
      where t.tgrelid = 'public.trip_kv'::regclass and not t.tgisinternal
        and t.tgname not in ('trip_kv_before_update', 'trip_kv_set_updated_by')), '∅'));
  r := qa.f06_rec(r, 910, '§2 helpers live in private and are named f06_* (no other new private function)', 'true',
    (not exists (select 1 from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
       where s.nspname = 'private' and p.proname not like 'f05\_%' and p.proname not like 'f06\_%'))::text);
  r := qa.f06_rec(r, 911, '§2 no new tables: public = the 9 F01 tables, private = join_attempts + transfer_codes', '9/join_attempts,transfer_codes',
    (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public') || '/' ||
    coalesce((select string_agg(t.tablename, ',' order by t.tablename) from pg_catalog.pg_tables t where t.schemaname = 'private'), '∅'));
  r := qa.f06_rec(r, 912, 'C17 §2 no new policies (public = the alpha.6 set, private = none)',
    'platform_admins:platform_admins_select_own:SELECT,trip_countries:trip_countries_delete_manager:DELETE,trip_countries:trip_countries_insert_manager:INSERT,trip_countries:trip_countries_select_member:SELECT,trip_countries:trip_countries_update_manager:UPDATE,trip_currencies:trip_currencies_delete_manager:DELETE,trip_currencies:trip_currencies_insert_manager:INSERT,trip_currencies:trip_currencies_select_member:SELECT,trip_currencies:trip_currencies_update_manager:UPDATE,trip_join_codes:trip_join_codes_select_manager:SELECT,trip_kv:trip_kv_delete_editor:DELETE,trip_kv:trip_kv_insert_editor:INSERT,trip_kv:trip_kv_select_member:SELECT,trip_kv:trip_kv_update_editor:UPDATE,trip_members:trip_members_select:SELECT,trips:trips_select_member:SELECT,trips:trips_update_manager:UPDATE/0',
    (select string_agg(p.tablename || ':' || p.policyname || ':' || p.cmd, ',' order by p.tablename, p.policyname)
       from pg_catalog.pg_policies p where p.schemaname = 'public') || '/' ||
    (select count(*)::text from pg_catalog.pg_policies p where p.schemaname = 'private'));
  r := qa.f06_rec(r, 913, 'C17 §2 no new grant on existing tables for anon / authenticated / PUBLIC (= the alpha.6 set)',
    'platform_admins:authenticated:SELECT;trip_countries:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_currencies:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_join_codes:authenticated:SELECT;trip_kv:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_members:authenticated:SELECT;trips:authenticated:SELECT',
    (select string_agg(x, ';' order by x) from (
       select g.table_name || ':' || g.grantee || ':' || string_agg(g.privilege_type, ',' order by g.privilege_type) as x
         from information_schema.role_table_grants g
        where g.table_schema = 'public' and g.grantee in ('anon', 'authenticated', 'PUBLIC')
        group by g.table_name, g.grantee) q));
  r := qa.f06_rec(r, 914, 'C17 column grants unchanged: authenticated may update only the 7 trips settings columns', 'default_lang,default_role,end_date,home_currency,name,start_date,status',
    (select string_agg(c.column_name, ',' order by c.column_name) from information_schema.column_privileges c
      where c.table_schema = 'public' and c.table_name = 'trips' and c.grantee = 'authenticated' and c.privilege_type = 'UPDATE'));
  r := qa.f06_rec(r, 915, 'C17 the private schema stays closed to anon / authenticated', 'false/false',
    pg_catalog.has_schema_privilege('anon', 'private', 'usage')::text || '/' ||
    pg_catalog.has_schema_privilege('authenticated', 'private', 'usage')::text);
  r := qa.f06_rec(r, 916, '§2.1 the F01 last-manager trigger is still in place (backstop)', '1',
    (select count(*)::text from pg_catalog.pg_trigger t where t.tgrelid = 'public.trip_members'::regclass and t.tgname = 'trip_members_last_manager'));
  r := qa.f06_rec(r, 917, '§1.2 / D11 trip_members still in the supabase_realtime publication', '1 rows or 0 rows (no publication)',
    (select case when not exists (select 1 from pg_catalog.pg_publication where pubname = 'supabase_realtime') then '0 rows (no publication)'
                 else (select count(*) || ' rows' from pg_catalog.pg_publication_tables t
                        where t.pubname = 'supabase_realtime' and t.schemaname = 'public' and t.tablename = 'trip_members') end));
  r := qa.f06_rec(r, 999, 'Leftovers after the run: 0 f06 users / trips / attempts / codes', '0/0/true/true',
    (select count(*) from auth.users u where u.id::text like 'f0600000-%')::text || '/' ||
    (select count(*) from public.trips t where t.name like 'F06 %')::text || '/' ||
    ((select count(*) from private.join_attempts) <= n_att_before)::text || '/' ||
    ((select count(*) from private.transfer_codes) = n_tc_before and (select count(*) from public.trips) = n_trips_before
      and (select count(*) from auth.users) = n_users_before)::text);

  return query
    select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail'
      from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
