-- Lonely Planner QA · F21 DB-level test harness · version 3.0.0-alpha.8 · F21 (dev harness 1.0.0)
-- CHANGE 2026-10-27 F21-QA-01: new file (no previous version). Installs qa.f21_run() in the locked `qa` schema, same pattern
--   as F01–F06 (0002–0004, 0007, 0009, 0011, 0013, 0015): helpers impersonate a user via request.jwt.claims + SET LOCAL ROLE,
--   all test data is created inside a sub-transaction that is always rolled back (raise 'f21_rollback'), search_path pinned
--   to '', nothing granted to public/anon/authenticated. SECURITY INVOKER (run as postgres, the owner of the F21 functions).
--   The entry functions are called with NAMED arguments exactly as docs/F21_spec.md §2.6 writes them, so a renamed
--   parameter fails visibly. To keep the run deterministic the sub-transaction first empties private.trip_requests /
--   request_attempts / mail_log (rolled back with everything else; nothing real is lost). Time windows are exercised by
--   back-dating rows (inside one transaction now() is constant), never by sleeping.
--
-- Run (after 0016_f21.sql):   select * from qa.f21_run() order by id;
-- Output: one row per scenario (id, name, pass, detail) — detail = 'expected: … | actual: …'.
-- Covers spec §2.1–2.9, §4 limits, D5/C5 cleanup, D10/C2/C3 cap, D12 approve transaction + undo, C4 (DB side: the start
-- result has the same keys for a known and an unknown email; the rest of C4 is a function-level matter), criterion 17.

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

create or replace function qa.f21_as(p_uid uuid, p_role text)
returns void language plpgsql set search_path = '' as $f$
begin
  execute 'reset role';
  if p_role = 'postgres' then
    perform pg_catalog.set_config('request.jwt.claims', '', true);
    perform pg_catalog.set_config('request.jwt.claim.sub', '', true);
    return;
  end if;
  perform pg_catalog.set_config('request.jwt.claims',
    case when p_uid is null then pg_catalog.json_build_object('role', p_role)::text
         else pg_catalog.json_build_object('sub', p_uid, 'role', p_role)::text end, true);
  perform pg_catalog.set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
  execute pg_catalog.format('set local role %I', p_role);
end $f$;

-- Evaluate a scalar expression while impersonating; 'error <sqlstate> <message>' on failure.
create or replace function qa.f21_val(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare v text;
begin
  perform qa.f21_as(p_uid, p_role);
  execute p_sql into v;
  execute 'reset role';
  return coalesce(v, 'NULL');
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate || ' ' || left(sqlerrm, 160);
end $f$;

-- Run one statement as postgres in its own sub-transaction: 'ok' or 'error <sqlstate>'.
create or replace function qa.f21_try(p_sql text)
returns text language plpgsql set search_path = '' as $f$
begin
  execute p_sql;
  return 'ok';
exception when others then
  return 'error ' || sqlstate;
end $f$;

create or replace function qa.f21_h(p text)
returns text language sql immutable set search_path = '' as $f$
  select pg_catalog.encode(extensions.digest(p, 'sha256'), 'hex')
$f$;

-- Call wrappers with the parameter names of spec §2.6. A raised exception becomes {"raised": "..."}.
create or replace function qa.f21_start(p_request uuid, p_payload jsonb, p_email_hash text, p_ip text, p_code_hash text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_start(p_request => p_request, p_payload => p_payload, p_email_hash => p_email_hash, p_ip => p_ip, p_code_hash => p_code_hash);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_verify(p_request uuid, p_code_hash text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_verify(p_request => p_request, p_code_hash => p_code_hash, p_ip => p_ip);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_resend(p_request uuid, p_code_hash text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_resend(p_request => p_request, p_code_hash => p_code_hash);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_failed(p_request uuid, p_action text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_mail_failed(p_request => p_request, p_action => p_action);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_approve(p_admin uuid, p_request uuid, p_token_hash text, p_draft text, p_inviter text)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_approve(p_admin => p_admin, p_request => p_request, p_token_hash => p_token_hash, p_draft => p_draft, p_inviter => p_inviter);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_undo(p_invite uuid, p_revoked uuid, p_request uuid)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_approve_undo(p_invite => p_invite, p_revoked => p_revoked, p_request => p_request);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f21_reject(p_admin uuid, p_request uuid, p_mail boolean)
returns jsonb language plpgsql set search_path = '' as $f$
begin return public.request_reject(p_admin => p_admin, p_request => p_request, p_mail => p_mail);
exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

-- error code of a result, 'ok' when it has no "error" key
create or replace function qa.f21_e(p jsonb)
returns text language sql immutable set search_path = '' as $f$
  select case when p is null then 'null'
              when pg_catalog.jsonb_typeof(p) <> 'object' then 'ok'
              when p ? 'raised' then 'raised ' || (p->>'raised')
              when p ? 'error' then p->>'error' else 'ok' end
$f$;

-- 'status' of a request row ('∅' when gone)
create or replace function qa.f21_st(p uuid)
returns text language sql stable set search_path = '' as $f$
  select coalesce((select q.status from private.trip_requests q where q.id = p), '∅')
$f$;

create or replace function qa.f21_mails()
returns int language sql stable set search_path = '' as $f$
  select pg_catalog.count(*)::int from private.mail_log l where l.at >= private.f21_day_start()
$f$;

-- Expected-value grammar (as F01–F06): exact · 'error 42501' prefix · 'A or B'.
create or replace function qa.f21_match(p_exp text, p_act text)
returns boolean language plpgsql immutable set search_path = '' as $f$
declare alt text;
begin
  if p_act is null then return false; end if;
  if position(' or ' in p_exp) > 0 then
    foreach alt in array pg_catalog.string_to_array(p_exp, ' or ') loop
      if qa.f21_match(alt, p_act) then return true; end if;
    end loop;
    return false;
  end if;
  if p_exp like 'error %' then return p_act like p_exp || '%'; end if;
  return p_act = p_exp;
end $f$;

create or replace function qa.f21_rec(r jsonb, p_id int, p_name text, p_exp text, p_act text)
returns jsonb language plpgsql set search_path = '' as $f$
begin
  return r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
    'id', p_id, 'name', p_name,
    'detail', 'expected: ' || p_exp || ' | actual: ' || coalesce(p_act, '(null)'),
    'pass', qa.f21_match(p_exp, p_act)));
end $f$;

create or replace function qa.f21_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r      jsonb := '[]'::jsonb;
  u_adm  constant uuid := 'f2100000-0000-4000-8000-0000000000a1';
  u_mgr  constant uuid := 'f2100000-0000-4000-8000-0000000000a2';
  u_out  constant uuid := 'f2100000-0000-4000-8000-0000000000a3';
  t1     constant uuid := 'f2100000-0000-4000-8000-00000000f001';
  e_mgr  constant text := 'f21-mgr@qa.invalid';
  e_inv  constant text := 'f21-inv@qa.invalid';
  m_now  text := pg_catalog.to_char(private.f21_month_start(), 'YYYY-MM');
  m2     text := pg_catalog.to_char(private.f21_month_start() + interval '2 months', 'YYYY-MM');
  m17    text := pg_catalog.to_char(private.f21_month_start() + interval '17 months', 'YYYY-MM');
  m18    text := pg_catalog.to_char(private.f21_month_start() + interval '18 months', 'YYYY-MM');
  m_prev text := pg_catalog.to_char(private.f21_month_start() - interval '1 month', 'YYYY-MM');
  base   jsonb;
  res    jsonb; res2 jsonb;
  q1 uuid; q2 uuid; q3 uuid; q4 uuid; q5 uuid; q6 uuid; q7 uuid; q8 uuid; q9 uuid; q10 uuid; qx uuid;
  i_old  uuid; i_new uuid;
  act    text; act2 text;
  n      int; n2 int; k int;
  v      text;
  n_req_before bigint; n_inv_before bigint; n_users_before bigint; n_trips_before bigint;
begin
  select count(*) into n_req_before from private.trip_requests;
  select count(*) into n_inv_before from public.manager_invites;
  select count(*) into n_users_before from auth.users;
  select count(*) into n_trips_before from public.trips;

  begin
    -- ================= SETUP =================
    perform qa.f21_as(null, 'postgres');
    delete from private.mail_log;
    delete from private.request_attempts;
    delete from public.manager_invites i where i.request_id is not null;
    delete from private.trip_requests;
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at) values
      (u_adm, 'authenticated', 'authenticated', 'f21-admin@qa.invalid', '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_mgr, 'authenticated', 'authenticated', 'F21-MGR@qa.invalid',   '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_out, 'authenticated', 'authenticated', 'f21-out@qa.invalid',   '00000000-0000-0000-0000-000000000000', now(), now());
    insert into public.platform_admins (user_id) values (u_adm);
    insert into public.trips (id, name, start_date, end_date, created_by) values (t1, 'F21 קיים', '2027-04-03', '2027-04-20', u_mgr);
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at)
      values (t1, u_mgr, 'מנהלת', 'manager', 'active', now(), now());
    base := pg_catalog.jsonb_build_object('lang', 'he', 'name', 'דנה QA', 'email', 'f21-a@qa.invalid',
              'countries', pg_catalog.jsonb_build_array('PT', 'ES'), 'month', m2, 'travellers', 4, 'note', 'שלום');

    -- ================= 0xx · §2.1–2.4 table constraints =================
    r := qa.f21_rec(r, 1, '§2.1 a valid row inserts', 'ok', qa.f21_try(
      'insert into private.trip_requests (lang,name,email,countries,month,travellers,status) values (''en'',''A'',''a@b.co'',''{PT}'',''2027-04-01'',1,''unverified'')'));
    r := qa.f21_rec(r, 2, '§2.1 lang fr → check violation', 'error 23514', qa.f21_try(
      'insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''fr'',''A'',''a@b.co'',''{PT}'',1,''unverified'')'));
    r := qa.f21_rec(r, 3, '§2.1 name 0 / 41 chars → check violation', 'error 23514/error 23514',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'','''',''a@b.co'',''{PT}'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',repeat(''x'',41),''a@b.co'',''{PT}'',1,''unverified'')'));
    r := qa.f21_rec(r, 4, '§2.1 email not lower-case → check violation', 'error 23514', qa.f21_try(
      'insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''A@b.co'',''{PT}'',1,''unverified'')'));
    r := qa.f21_rec(r, 5, '§2.1 countries {} / 11 / ''pt'' / ''PRT'' → check violation', 'error 23514/error 23514/error 23514/error 23514',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{}'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{AA,AB,AC,AD,AE,AF,AG,AH,AI,AJ,AK}'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{pt}'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PRT}'',1,''unverified'')'));
    r := qa.f21_rec(r, 6, '§2.1 month not the 1st / travellers 0, 31 / note 201 / status bad → check violation',
      'error 23514/error 23514/error 23514/error 23514/error 23514',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,month,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',''2027-04-02'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',0,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',31,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,note,status) values (''he'',''A'',''a@b.co'',''{PT}'',1,repeat(''n'',201),''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',1,''done'')'));
    r := qa.f21_rec(r, 7, '§2.2/2.3 attempts kind / mail_log kind outside the list → check violation', 'error 23514/error 23514',
      qa.f21_try('insert into private.request_attempts (kind) values (''login'')') || '/' ||
      qa.f21_try('insert into private.mail_log (kind) values (''invite'')'));
    r := qa.f21_rec(r, 8, '§2.4 manager_invites.lang defaults to he, rejects fr; request_id FK on delete set null', '''he''::text/error 23514/n',
      (select c.column_default from information_schema.columns c where c.table_schema = 'public' and c.table_name = 'manager_invites' and c.column_name = 'lang') || '/' ||
      qa.f21_try('insert into public.manager_invites (email, token_hash, expires_at, lang) values (''f21-x@qa.invalid'', ''f21-h-x'', now(), ''fr'')') || '/' ||
      coalesce((select c.confdeltype::text from pg_catalog.pg_constraint c where c.conname = 'manager_invites_request_id_fkey'), '∅'));
    r := qa.f21_rec(r, 9, '§2.1 indexes (status, verified_at) and (email, created_at)', '2',
      (select count(*)::text from pg_catalog.pg_indexes x where x.schemaname = 'private' and x.tablename = 'trip_requests'
        and (x.indexdef like '%(status, verified_at)%' or x.indexdef like '%(email, created_at)%')));
    delete from private.trip_requests;

    -- ================= 1xx · request_start =================
    q1 := gen_random_uuid();
    res := qa.f21_start(q1, base, qa.f21_h('e-a'), qa.f21_h('ip-1'), qa.f21_h(q1::text || '111111'));
    r := qa.f21_rec(r, 101, '§2.6 start → {request_id, sent_at}; row unverified with code hash, 10 min, 1 code mail today',
      'ok/request_id,sent_at/unverified/true/1',
      qa.f21_e(res) || '/' || (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(res) k2) || '/' || qa.f21_st(q1) || '/' ||
      (select (q.code_hash = qa.f21_h(q1::text || '111111') and q.code_expires_at = now() + interval '10 minutes'
               and q.countries = '{PT,ES}' and q.month = (m2 || '-01')::date and q.travellers = 4 and q.note = 'שלום'
               and q.email = 'f21-a@qa.invalid' and q.name = 'דנה QA')::text from private.trip_requests q where q.id = q1) || '/' ||
      qa.f21_mails()::text);
    -- validation: a fresh email hash per call so the per-email limit never interferes
    k := 0;
    for act, res in select x.f, x.p from (values
        ('lang',       base || '{"lang":"fr"}'),
        ('name',       base || '{"name":"   "}'),
        ('name',       base || pg_catalog.jsonb_build_object('name', repeat('א', 41))),
        ('email',      base || '{"email":"nope"}'),
        ('email',      base || '{"email":"a b@x.com"}'),
        ('countries',  base || '{"countries":[]}'),
        ('countries',  base || '{"countries":["AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK"]}'),
        ('countries',  base || '{"countries":["pt"]}'),
        ('countries',  base || '{"countries":["PT","PT"]}'),
        ('month',      base || pg_catalog.jsonb_build_object('month', m_prev)),
        ('month',      base || pg_catalog.jsonb_build_object('month', m18)),
        ('month',      base || '{"month":"2027-13"}'),
        ('travellers', base || '{"travellers":0}'),
        ('travellers', base || '{"travellers":31}'),
        ('travellers', base || '{"travellers":"2"}'),
        ('note',       base || pg_catalog.jsonb_build_object('note', repeat('n', 201))),
        ('payload',    '[1]'::jsonb)) x(f, p) loop
      k := k + 1;
      qx := gen_random_uuid();
      res2 := qa.f21_start(qx, res, qa.f21_h('val-' || k), qa.f21_h('ipv-' || k), qa.f21_h('c' || k));
      r := qa.f21_rec(r, 110 + k, '§1.2 start validation → invalid_request field=' || act || ' (case ' || k || '), no row',
        'invalid_request/' || act || '/∅', qa.f21_e(res2) || '/' || coalesce(res2->>'field', '-') || '/' || qa.f21_st(qx));
    end loop;
    r := qa.f21_rec(r, 128, '§1.2 validation refusals sent no mail (still 1 today)', '1', qa.f21_mails()::text);
    q2 := gen_random_uuid();
    res := qa.f21_start(q2, base || pg_catalog.jsonb_build_object('email', '  F21-B@QA.invalid ', 'month', m17, 'note', '  ',
                                                                    'lang', 'en', 'name', '  Tom  '), qa.f21_h('e-b'), qa.f21_h('ip-2'), qa.f21_h('c-b'));
    r := qa.f21_rec(r, 129, 'D7 month YYYY-MM at +17 months ok; email trimmed+lowered; blank note → null; name trimmed',
      'ok/' || m17 || '-01/f21-b@qa.invalid/NULL/Tom/en',
      qa.f21_e(res) || '/' || (select q.month::text || '/' || q.email || '/' || coalesce(q.note, 'NULL') || '/' || q.name || '/' || q.lang
                                 from private.trip_requests q where q.id = q2));
    q3 := gen_random_uuid();
    res := qa.f21_start(q3, base || '{"month":null}', qa.f21_h('e-a'), qa.f21_h('ip-1'), qa.f21_h('c-a2'));
    r := qa.f21_rec(r, 130, '§2.6 a new start for the same email deletes the earlier unverified row; month null accepted',
      'ok/∅/unverified/1/NULL', qa.f21_e(res) || '/' || qa.f21_st(q1) || '/' || qa.f21_st(q3) || '/' ||
      (select count(*)::text from private.trip_requests q where q.email = 'f21-a@qa.invalid') || '/' ||
      coalesce((select q.month::text from private.trip_requests q where q.id = q3), 'NULL'));
    res := qa.f21_start(gen_random_uuid(), base, qa.f21_h('e-a'), qa.f21_h('ip-1'), qa.f21_h('c-a3'));
    res2 := qa.f21_start(gen_random_uuid(), base, qa.f21_h('e-a'), qa.f21_h('ip-1b'), qa.f21_h('c-a4'));
    r := qa.f21_rec(r, 131, '§4 start: 3rd per email ok, 4th per email in a day → rate_limited (any ip)', 'ok/rate_limited',
      qa.f21_e(res) || '/' || qa.f21_e(res2));
    update private.request_attempts a set at = private.f21_day_start() - interval '1 minute' where a.email_hash = qa.f21_h('e-a');
    res := qa.f21_start(gen_random_uuid(), base, qa.f21_h('e-a'), qa.f21_h('ip-1c'), qa.f21_h('c-a5'));
    r := qa.f21_rec(r, 132, 'C3 attempts from before today''s Jerusalem midnight do not count', 'ok', qa.f21_e(res));
    for k in 1..9 loop
      perform qa.f21_start(gen_random_uuid(), base || pg_catalog.jsonb_build_object('email', 'ipl' || k || '@qa.invalid'),
                           qa.f21_h('ipl-' || k), qa.f21_h('ip-L'), qa.f21_h('c-l' || k));
    end loop;
    res := qa.f21_start(gen_random_uuid(), base || '{"email":"ipl10@qa.invalid"}', qa.f21_h('ipl-10'), qa.f21_h('ip-L'), qa.f21_h('c-l10'));
    res2 := qa.f21_start(gen_random_uuid(), base || '{"email":"ipl11@qa.invalid"}', qa.f21_h('ipl-11'), qa.f21_h('ip-L'), qa.f21_h('c-l11'));
    r := qa.f21_rec(r, 133, '§4 start: 10th per ip ok, 11th per ip in a day → rate_limited', 'ok/rate_limited',
      qa.f21_e(res) || '/' || qa.f21_e(res2));
    -- invalid attempts count too (spec "counted ok or not")
    perform qa.f21_start(gen_random_uuid(), base || '{"name":""}', qa.f21_h('e-inv'), qa.f21_h('ip-inv'), qa.f21_h('c'));
    perform qa.f21_start(gen_random_uuid(), base || '{"name":""}', qa.f21_h('e-inv'), qa.f21_h('ip-inv2'), qa.f21_h('c'));
    perform qa.f21_start(gen_random_uuid(), base || '{"name":""}', qa.f21_h('e-inv'), qa.f21_h('ip-inv3'), qa.f21_h('c'));
    res := qa.f21_start(gen_random_uuid(), base, qa.f21_h('e-inv'), qa.f21_h('ip-inv4'), qa.f21_h('c'));
    r := qa.f21_rec(r, 134, '§4 refused (invalid) starts count toward the per-email limit', 'rate_limited', qa.f21_e(res));
    -- C4 (DB side): an email that manages a trip gets the same result shape
    res := qa.f21_start(gen_random_uuid(), base || pg_catalog.jsonb_build_object('email', e_mgr), qa.f21_h('e-mgr'), qa.f21_h('ip-m'), qa.f21_h('c-m'));
    r := qa.f21_rec(r, 135, 'C4 start for a manager''s email → same keys as for a new email (request_id, sent_at)', 'ok/request_id,sent_at',
      qa.f21_e(res) || '/' || (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(res) k2));
    r := qa.f21_rec(r, 136, '§2.6 refusals return {"error":…} (never raise); bad hashes → invalid_request', 'invalid_request/invalid_request',
      qa.f21_e(qa.f21_start(gen_random_uuid(), base, 'nothex', null, qa.f21_h('x'))) || '/' ||
      qa.f21_e(qa.f21_start(gen_random_uuid(), base, qa.f21_h('zz'), null, 'short')));

    -- ================= 2xx · request_verify =================
    q4 := gen_random_uuid();
    perform qa.f21_start(q4, base || '{"email":"f21-v@qa.invalid"}', qa.f21_h('e-v'), qa.f21_h('ip-v'), qa.f21_h(q4::text || '222222'));
    act := '';
    for k in 1..4 loop
      res := qa.f21_verify(q4, qa.f21_h(q4::text || '00000' || k), qa.f21_h('ip-vv'));
      act := act || qa.f21_e(res) || ':' || coalesce(res->>'attempts_left', '-') || ',';
    end loop;
    r := qa.f21_rec(r, 201, '§4 wrong code ×4 → code_wrong with attempts_left 4,3,2,1; row still unverified',
      'code_wrong:4,code_wrong:3,code_wrong:2,code_wrong:1,/unverified', act || '/' || qa.f21_st(q4));
    res := qa.f21_verify(q4, qa.f21_h(q4::text || '000009'), qa.f21_h('ip-vv'));
    r := qa.f21_rec(r, 202, '§4 5th wrong code → code_locked and the row is deleted', 'code_locked/∅', qa.f21_e(res) || '/' || qa.f21_st(q4));
    r := qa.f21_rec(r, 203, '§2.6 verify on an unknown / deleted request → request_unknown', 'request_unknown/request_unknown',
      qa.f21_e(qa.f21_verify(q4, qa.f21_h(q4::text || '222222'), null)) || '/' || qa.f21_e(qa.f21_verify(gen_random_uuid(), qa.f21_h('x'), null)));
    q5 := gen_random_uuid();
    perform qa.f21_start(q5, base || '{"email":"f21-w@qa.invalid","lang":"en","name":"Tom Baker"}', qa.f21_h('e-w'), qa.f21_h('ip-w'), qa.f21_h(q5::text || '333333'));
    res := qa.f21_verify(q5, qa.f21_h(q5::text || '333333'), qa.f21_h('ip-w'));
    r := qa.f21_rec(r, 204, '§2.6 right code → pending, verified_at set, code cleared', 'ok/pending/true',
      qa.f21_e(res) || '/' || qa.f21_st(q5) || '/' ||
      (select (q.verified_at is not null and q.code_hash is null and q.code_expires_at is null)::text from private.trip_requests q where q.id = q5));
    r := qa.f21_rec(r, 205, '§2.6 verifying a pending request again → request_unknown', 'request_unknown',
      qa.f21_e(qa.f21_verify(q5, qa.f21_h(q5::text || '333333'), null)));
    q6 := gen_random_uuid();
    perform qa.f21_start(q6, base || '{"email":"f21-x@qa.invalid"}', qa.f21_h('e-x'), qa.f21_h('ip-x'), qa.f21_h(q6::text || '444444'));
    update private.trip_requests q set code_expires_at = now() - interval '1 second' where q.id = q6;
    r := qa.f21_rec(r, 206, '§4 after 10 min → code_expired (even with the right code), row kept', 'code_expired/unverified',
      qa.f21_e(qa.f21_verify(q6, qa.f21_h(q6::text || '444444'), null)) || '/' || qa.f21_st(q6));
    -- ip limit: 20 wrong in the last hour (back-dated rows older than 1 h do not count)
    insert into private.request_attempts (kind, ip_hash, ok, at)
      select 'verify', qa.f21_h('ip-B'), false, now() - interval '2 hours' from generate_series(1, 30);
    insert into private.request_attempts (kind, ip_hash, ok, at)
      select 'verify', qa.f21_h('ip-B'), false, now() - interval '10 minutes' from generate_series(1, 19);
    q7 := gen_random_uuid();
    perform qa.f21_start(q7, base || '{"email":"f21-y@qa.invalid"}', qa.f21_h('e-y'), qa.f21_h('ip-y'), qa.f21_h(q7::text || '555555'));
    res := qa.f21_verify(q7, qa.f21_h('wrong'), qa.f21_h('ip-B'));
    res2 := qa.f21_verify(q7, qa.f21_h(q7::text || '555555'), qa.f21_h('ip-B'));
    r := qa.f21_rec(r, 207, '§4 20th wrong verify per ip in an hour still answered; 21st → rate_limited (right code too)', 'code_wrong/rate_limited/unverified',
      qa.f21_e(res) || '/' || qa.f21_e(res2) || '/' || qa.f21_st(q7));
    res := qa.f21_verify(q7, qa.f21_h(q7::text || '555555'), qa.f21_h('ip-C'));
    r := qa.f21_rec(r, 208, '§4 a different ip is not limited', 'ok/pending', qa.f21_e(res) || '/' || qa.f21_st(q7));

    -- ================= 3xx · request_resend / request_mail_failed =================
    q8 := gen_random_uuid();
    perform qa.f21_start(q8, base || '{"email":"f21-r@qa.invalid"}', qa.f21_h('e-r'), qa.f21_h('ip-r'), qa.f21_h(q8::text || '666666'));
    res := qa.f21_resend(q8, qa.f21_h(q8::text || '777777'));
    r := qa.f21_rec(r, 301, '§4 resend within 60 s → rate_limited with retry_in, hash unchanged', 'rate_limited/60/true',
      qa.f21_e(res) || '/' || coalesce(res->>'retry_in', '-') || '/' ||
      (select (q.code_hash = qa.f21_h(q8::text || '666666'))::text from private.trip_requests q where q.id = q8));
    update private.trip_requests q set code_sent_at = now() - interval '61 seconds', code_attempts = 2 where q.id = q8;
    n := qa.f21_mails();
    res := qa.f21_resend(q8, qa.f21_h(q8::text || '777777'));
    r := qa.f21_rec(r, 302, '§2.6 resend after 60 s → {request_id, sent_at}; new hash, attempts reset, resend_count 1, +1 code mail',
      'ok/true/1', qa.f21_e(res) || '/' ||
      (select (q.code_hash = qa.f21_h(q8::text || '777777') and q.code_attempts = 0 and q.code_sent_at = now()
               and q.code_expires_at = now() + interval '10 minutes')::text || '/' || q.resend_count from private.trip_requests q where q.id = q8)
      || case when qa.f21_mails() = n + 1 then '' else ' mails ' || n || '→' || qa.f21_mails() end);
    r := qa.f21_rec(r, 303, 'criterion 6: a resend kills the previous code (old → code_wrong)', 'code_wrong',
      qa.f21_e(qa.f21_verify(q8, qa.f21_h(q8::text || '666666'), null)));
    act := '';
    for k in 2..4 loop
      update private.trip_requests q set code_sent_at = now() - interval '61 seconds' where q.id = q8;
      act := act || qa.f21_e(qa.f21_resend(q8, qa.f21_h(q8::text || '88888' || k))) || ',';
    end loop;
    r := qa.f21_rec(r, 304, '§4 resends 2 and 3 ok, the 4th → rate_limited', 'ok,ok,rate_limited,', act);
    res := qa.f21_verify(q8, qa.f21_h(q8::text || '888883'), null);
    r := qa.f21_rec(r, 305, 'the newest code verifies', 'ok/pending', qa.f21_e(res) || '/' || qa.f21_st(q8));
    r := qa.f21_rec(r, 306, '§2.6 resend on a pending / unknown request → request_unknown', 'request_unknown/request_unknown',
      qa.f21_e(qa.f21_resend(q8, qa.f21_h('z'))) || '/' || qa.f21_e(qa.f21_resend(gen_random_uuid(), qa.f21_h('z'))));
    -- mail failed on start: the row and its code mail row go
    q9 := gen_random_uuid();
    n := qa.f21_mails();
    perform qa.f21_start(q9, base || '{"email":"f21-f@qa.invalid"}', qa.f21_h('e-f'), qa.f21_h('ip-f'), qa.f21_h(q9::text || '123456'));
    res := qa.f21_failed(q9, 'start');
    r := qa.f21_rec(r, 310, '§3.1 email failed on start → row deleted, its code mail row removed', 'ok/∅/true',
      qa.f21_e(res) || '/' || qa.f21_st(q9) || '/' || (qa.f21_mails() = n)::text);
    q9 := gen_random_uuid();
    perform qa.f21_start(q9, base || '{"email":"f21-g@qa.invalid"}', qa.f21_h('e-g'), qa.f21_h('ip-g'), qa.f21_h(q9::text || '123456'));
    update private.trip_requests q set code_sent_at = now() - interval '61 seconds' where q.id = q9;
    n := qa.f21_mails();
    perform qa.f21_resend(q9, qa.f21_h(q9::text || '654321'));
    res := qa.f21_failed(q9, 'resend');
    act := (qa.f21_mails() = n)::text || '/' || (select q.resend_count::text from private.trip_requests q where q.id = q9);
    res2 := qa.f21_resend(q9, qa.f21_h(q9::text || '111222'));
    r := qa.f21_rec(r, 311, '§3.1 email failed on resend → mail row removed, resend_count back to 0, a new resend allowed at once',
      'ok/true/0/ok', qa.f21_e(res) || '/' || act || '/' || qa.f21_e(res2));
    act := qa.f21_e(qa.f21_failed(q9, 'drop'));
    res := qa.f21_failed(q8, 'start');
    r := qa.f21_rec(r, 312, 'request_mail_failed: bad action → invalid_request; ''start'' never deletes a pending row', 'invalid_request/ok/pending',
      act || '/' || qa.f21_e(res) || '/' || qa.f21_st(q8));

    -- ================= 4xx · cap (D10, C2, C3) and queue =================
    delete from private.mail_log;
    insert into private.mail_log (kind, at) select 'code', private.f21_day_start() - interval '1 minute' from generate_series(1, 60);
    insert into private.mail_log (kind, at) select 'reject', private.f21_day_start() + interval '1 minute' from generate_series(1, 49);
    r := qa.f21_rec(r, 401, 'C3 mail_today counts from Jerusalem midnight only (49 today, 60 yesterday)', '49', private.f21_mail_today()::text);
    qx := gen_random_uuid();
    res := qa.f21_start(qx, base || '{"email":"f21-cap1@qa.invalid"}', qa.f21_h('e-cap1'), qa.f21_h('ip-cap1'), qa.f21_h('c'));
    r := qa.f21_rec(r, 402, 'D10 49 mails today → start ok (makes 50)', 'ok/50', qa.f21_e(res) || '/' || private.f21_mail_today());
    res := qa.f21_start(gen_random_uuid(), base || '{"email":"f21-cap2@qa.invalid"}', qa.f21_h('e-cap2'), qa.f21_h('ip-cap2'), qa.f21_h('c'));
    update private.trip_requests q set code_sent_at = now() - interval '61 seconds' where q.id = qx;
    res2 := qa.f21_resend(qx, qa.f21_h('c2'));
    r := qa.f21_rec(r, 403, 'criterion 9: at 50 → start and resend → daily_limit, no row, no mail', 'daily_limit/daily_limit/50/0',
      qa.f21_e(res) || '/' || qa.f21_e(res2) || '/' || private.f21_mail_today() || '/' ||
      (select count(*)::text from private.trip_requests q where q.email = 'f21-cap2@qa.invalid'));
    -- reject with mail at the cap succeeds without mail (C2); approval is never blocked (invites are not counted)
    res := qa.f21_reject(u_adm, q7, true);
    r := qa.f21_rec(r, 404, 'C2 reject with mail at the cap → rejected, {mail:false, reason:daily_limit}, no mail row',
      'ok/false/daily_limit/rejected/false/50', qa.f21_e(res) || '/' || (res->>'mail') || '/' || coalesce(res->>'reason', '-') || '/' ||
      qa.f21_st(q7) || '/' || (select q.reject_mailed::text from private.trip_requests q where q.id = q7) || '/' || private.f21_mail_today());
    res := qa.f21_approve(u_adm, q8, qa.f21_h('tok-q8'), 'פורטוגל', 'אור');
    r := qa.f21_rec(r, 405, 'C2 approval at the cap still creates the invite (not counted)', 'ok/approved/50',
      qa.f21_e(res) || '/' || qa.f21_st(q8) || '/' || private.f21_mail_today());
    delete from private.mail_log;
    insert into private.trip_requests (lang, name, email, countries, travellers, status, verified_at)
      select 'he', 'Q' || g, 'f21-q' || g || '@qa.invalid', '{PT}', 1, 'pending', now() from generate_series(1, 100 - (select count(*)::int from private.trip_requests where status = 'pending')) g;
    res := qa.f21_start(gen_random_uuid(), base || '{"email":"f21-q@qa.invalid"}', qa.f21_h('e-q'), qa.f21_h('ip-q'), qa.f21_h('c'));
    r := qa.f21_rec(r, 406, '§4 queue: 100 verified pending rows → start → daily_limit', '100/daily_limit',
      (select count(*)::text from private.trip_requests where status = 'pending') || '/' || qa.f21_e(res));
    delete from private.trip_requests q where q.email like 'f21-q%@qa.invalid';

    -- ================= 5xx · request_approve / request_approve_undo (D12) =================
    r := qa.f21_rec(r, 501, 'approve: not a platform admin → not_platform_admin; no invite', 'not_platform_admin/pending/0',
      qa.f21_e(qa.f21_approve(u_out, q5, qa.f21_h('tok-x'), 'x', 'x')) || '/' || qa.f21_st(q5) || '/' ||
      (select count(*)::text from public.manager_invites i where i.request_id = q5));
    r := qa.f21_rec(r, 502, 'approve: unverified / rejected / unknown request → request_closed', 'request_closed/request_closed/request_closed',
      qa.f21_e(qa.f21_approve(u_adm, q6, qa.f21_h('tok-a'), null, 'אור')) || '/' ||
      qa.f21_e(qa.f21_approve(u_adm, q7, qa.f21_h('tok-b'), null, 'אור')) || '/' ||
      qa.f21_e(qa.f21_approve(u_adm, gen_random_uuid(), qa.f21_h('tok-c'), null, 'אור')));
    r := qa.f21_rec(r, 503, 'approve: draft 81 chars → invalid_request field draft_name', 'invalid_request/draft_name/pending',
      qa.f21_e(qa.f21_approve(u_adm, q5, qa.f21_h('tok-d'), repeat('x', 81), 'אור')) || '/' ||
      coalesce(qa.f21_approve(u_adm, q5, qa.f21_h('tok-d'), repeat('x', 81), 'אור')->>'field', '-') || '/' || qa.f21_st(q5));
    res := qa.f21_approve(u_adm, q5, qa.f21_h('tok-q5'), '  Portugal  ', 'אור');
    i_new := (res->>'invite_id')::uuid;
    r := qa.f21_rec(r, 504, 'criterion 12: approve (no invite) → one invite with request_id, lang en, draft, 7 days, F03 columns; request approved',
      'ok/null/1/true/approved/true',
      qa.f21_e(res) || '/' || coalesce(res->>'revoked_invite_id', 'null') || '/' ||
      (select count(*)::text from public.manager_invites i where i.request_id = q5) || '/' ||
      (select (i.lang = 'en' and i.draft_name = 'Portugal' and i.email = 'f21-w@qa.invalid' and i.token_hash = qa.f21_h('tok-q5')
               and i.expires_at = now() + interval '7 days' and i.invited_by = u_adm and i.inviter_name = 'אור' and i.send_count = 1
               and i.last_sent_at = now() and i.used_at is null and i.revoked_at is null)::text from public.manager_invites i where i.id = i_new) || '/' ||
      qa.f21_st(q5) || '/' ||
      (select (q.invite_id = i_new and q.decided_by = u_adm and q.decided_at = now())::text from private.trip_requests q where q.id = q5));
    r := qa.f21_rec(r, 505, 'approve result carries email, name, lang for the invite email', 'f21-w@qa.invalid/Tom Baker/en/Portugal',
      (res->>'email') || '/' || (res->>'name') || '/' || (res->>'lang') || '/' || (res->>'draft_name'));
    r := qa.f21_rec(r, 506, 'approve again → request_closed, still one invite', 'request_closed/1',
      qa.f21_e(qa.f21_approve(u_adm, q5, qa.f21_h('tok-q5b'), null, 'אור')) || '/' ||
      (select count(*)::text from public.manager_invites i where i.request_id = q5));
    -- D12: an email with an active F03 invite
    insert into public.manager_invites (email, token_hash, draft_name, invited_by, inviter_name, expires_at, last_sent_at)
      values (e_inv, qa.f21_h('tok-old'), 'יפן', u_adm, 'אור', now() + interval '3 days', now() - interval '4 days') returning id into i_old;
    insert into private.trip_requests (id, lang, name, email, countries, month, travellers, status, verified_at)
      values (gen_random_uuid(), 'he', 'רוני', e_inv, '{JP}', (m2 || '-01')::date, 3, 'pending', now() - interval '1 hour') returning id into q1;
    res := qa.f21_approve(u_adm, q1, qa.f21_h('tok-new'), 'יפן · אפריל', 'אור');
    i_new := (res->>'invite_id')::uuid;
    r := qa.f21_rec(r, 510, 'criterion 13 / D12: approve with an active invite → old revoked (id returned), new active, exactly one open invite',
      'ok/true/true/false/1',
      qa.f21_e(res) || '/' || ((res->>'revoked_invite_id')::uuid = i_old)::text || '/' ||
      (select (i.revoked_at is not null)::text from public.manager_invites i where i.id = i_old) || '/' ||
      (select (i.revoked_at is not null)::text from public.manager_invites i where i.id = i_new) || '/' ||
      (select count(*)::text from public.manager_invites i where i.email = e_inv and i.used_at is null and i.revoked_at is null));
    r := qa.f21_rec(r, 511, 'D12 the old token no longer finds the invite; find_invite_for_email returns the new one with prefill',
      'true/he/רוני/JP/' || m2 || '-01',
      ((public.find_invite_for_email(e_inv)->>'invite_id')::uuid = i_new)::text || '/' ||
      (public.find_invite_for_email(e_inv)#>>'{prefill,lang}') || '/' || (public.find_invite_for_email(e_inv)#>>'{prefill,name}') || '/' ||
      (public.find_invite_for_email(e_inv)#>>'{prefill,countries,0}') || '/' || (public.find_invite_for_email(e_inv)#>>'{prefill,month}'));
    res2 := qa.f21_undo(i_new, i_old, q1);
    r := qa.f21_rec(r, 512, 'criterion 14: undo → new invite gone, old invite open again, request pending, invite_id/decided cleared',
      'ok/0/false/pending/true',
      qa.f21_e(res2) || '/' || (select count(*)::text from public.manager_invites i where i.id = i_new) || '/' ||
      (select (i.revoked_at is not null)::text from public.manager_invites i where i.id = i_old) || '/' || qa.f21_st(q1) || '/' ||
      (select (q.invite_id is null and q.decided_at is null and q.decided_by is null)::text from private.trip_requests q where q.id = q1));
    r := qa.f21_rec(r, 513, 'after undo the old invite is found again (no prefill: it is an F03 invite)', 'true/false',
      ((public.find_invite_for_email(e_inv)->>'invite_id')::uuid = i_old)::text || '/' || (public.find_invite_for_email(e_inv) ? 'prefill')::text);
    res := qa.f21_approve(u_adm, q1, qa.f21_h('tok-new2'), null, null);
    r := qa.f21_rec(r, 514, 'approve after undo works; empty draft → null; empty inviter → fallback', 'ok/approved/NULL/מנהל המערכת/he',
      qa.f21_e(res) || '/' || qa.f21_st(q1) || '/' ||
      (select coalesce(i.draft_name, 'NULL') || '/' || i.inviter_name || '/' || i.lang from public.manager_invites i where i.id = (res->>'invite_id')::uuid));
    -- an expired-but-unrevoked invite also holds the slot and is revoked
    update public.manager_invites i set expires_at = now() - interval '1 day' where i.id = (res->>'invite_id')::uuid;
    insert into private.trip_requests (id, lang, name, email, countries, travellers, status, verified_at)
      values (gen_random_uuid(), 'he', 'רוני', e_inv, '{JP}', 3, 'pending', now()) returning id into q2;
    res2 := qa.f21_approve(u_adm, q2, qa.f21_h('tok-new3'), null, 'אור');
    r := qa.f21_rec(r, 515, 'D12 an expired unrevoked invite is revoked too (unique slot), no 23505', 'ok/true',
      qa.f21_e(res2) || '/' || ((res2->>'revoked_invite_id')::uuid = (res->>'invite_id')::uuid)::text);
    res := qa.f21_undo(gen_random_uuid(), null, gen_random_uuid());
    r := qa.f21_rec(r, 516, 'undo with unknown ids / no revoked invite is harmless', 'ok', qa.f21_e(res));
    res := qa.f21_undo((res2->>'invite_id')::uuid, null, q5);
    r := qa.f21_rec(r, 517, 'undo never deletes an invite that belongs to another request', 'ok/1/approved',
      qa.f21_e(res) || '/' || (select count(*)::text from public.manager_invites i where i.id = (res2->>'invite_id')::uuid) || '/' || qa.f21_st(q2));

    -- ================= 6xx · request_reject =================
    qx := gen_random_uuid();
    insert into private.trip_requests (id, lang, name, email, countries, travellers, status, verified_at)
      values (qx, 'en', 'Tom', 'f21-rj@qa.invalid', '{PT}', 2, 'pending', now());
    n := qa.f21_mails();
    res := qa.f21_reject(u_adm, qx, true);
    r := qa.f21_rec(r, 601, 'criterion 15: reject with mail under the cap → {mail:true, lang, email, name}; rejected; +1 reject mail',
      'ok/true/en/f21-rj@qa.invalid/Tom/rejected/true/true',
      qa.f21_e(res) || '/' || (res->>'mail') || '/' || (res->>'lang') || '/' || (res->>'email') || '/' || (res->>'name') || '/' ||
      qa.f21_st(qx) || '/' || (select q.reject_mailed::text from private.trip_requests q where q.id = qx) || '/' ||
      (qa.f21_mails() = n + 1 and exists (select 1 from private.mail_log l where l.kind = 'reject' and l.request_id = qx))::text);
    insert into private.trip_requests (id, lang, name, email, countries, travellers, status, verified_at)
      values (gen_random_uuid(), 'he', 'דן', 'f21-rk@qa.invalid', '{PT}', 2, 'pending', now()) returning id into q3;
    res := qa.f21_reject(u_adm, q3, false);
    r := qa.f21_rec(r, 602, 'reject without mail → {mail:false, reason:not_requested}, no mail row', 'ok/false/not_requested/rejected/true',
      qa.f21_e(res) || '/' || (res->>'mail') || '/' || (res->>'reason') || '/' || qa.f21_st(q3) || '/' || (qa.f21_mails() = n + 1)::text);
    r := qa.f21_rec(r, 603, 'reject again / reject an unverified or unknown request → request_closed; non-admin → not_platform_admin',
      'request_closed/request_closed/request_closed/not_platform_admin',
      qa.f21_e(qa.f21_reject(u_adm, q3, false)) || '/' || qa.f21_e(qa.f21_reject(u_adm, q6, false)) || '/' ||
      qa.f21_e(qa.f21_reject(u_adm, gen_random_uuid(), false)) || '/' || qa.f21_e(qa.f21_reject(u_out, q6, false)));

    -- ================= 7xx · admin_trip_requests (§2.7) =================
    insert into private.trip_requests (id, lang, name, email, countries, month, travellers, note, status, verified_at)
      values (gen_random_uuid(), 'en', 'Mgr', e_mgr, '{IT,FR}', (m2 || '-01')::date, 5, 'hi', 'pending', now() - interval '3 days') returning id into q4;
    insert into public.manager_invites (email, token_hash, draft_name, invited_by, inviter_name, expires_at, last_sent_at)
      values (e_mgr, qa.f21_h('tok-mgr'), 'איטליה', u_adm, 'אור', now() + interval '5 days', now() - interval '2 days');
    insert into private.trip_requests (id, lang, name, email, countries, travellers, status, verified_at)
      values (gen_random_uuid(), 'he', 'בלי', 'f21-plainreq@qa.invalid', '{GR}', 2, 'pending', now() - interval '1 day') returning id into q10;
    r := qa.f21_rec(r, 701, 'criterion 17: admin_trip_requests as a non-admin → not_platform_admin (42501); anon → 42501',
      'error 42501/error 42501',
      left(qa.f21_val(u_out, 'authenticated', 'select public.admin_trip_requests()::text'), 11) || '/' ||
      left(qa.f21_val(null, 'anon', 'select public.admin_trip_requests()::text'), 11));
    r := qa.f21_rec(r, 702, 'non-admin refusal message is not_platform_admin', 'error 42501 not_platform_admin',
      qa.f21_val(u_out, 'authenticated', 'select public.admin_trip_requests()::text'));
    v := qa.f21_val(u_adm, 'authenticated', 'select public.admin_trip_requests()::text');
    res := case when v like '{%' then v::jsonb else pg_catalog.jsonb_build_object('raised', v) end;
    r := qa.f21_rec(r, 703, '§2.7 admin: {cap:50, mail_today = today''s mail_log rows, requests = pending only}',
      '50/true/' || (select count(*) from private.trip_requests where status = 'pending'),
      coalesce(res->>'cap', v) || '/' || ((res->>'mail_today')::int = qa.f21_mails())::text || '/' ||
      coalesce(pg_catalog.jsonb_array_length(res->'requests')::text, '-'));
    r := qa.f21_rec(r, 704, '§2.7 oldest verification first; exact key set; no code/ip hashes or decided fields',
      'true/active_invite,countries,email,id,lang,manages,month,name,note,travellers,verified_at/false',
      (select bool_and(a.ok)::text from (select (e->>'verified_at')::timestamptz >= lag((e->>'verified_at')::timestamptz, 1, '-infinity') over (order by o) as ok
                                     from pg_catalog.jsonb_array_elements(res->'requests') with ordinality x(e, o)) a) || '/' ||
      (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(res->'requests'->0) k2) || '/' ||
      (v ~ ('(code_hash|ip_hash|decided|' || qa.f21_h('tok-mgr') || ')'))::text);
    r := qa.f21_rec(r, 705, 'D6 markers: manager''s email (any case in auth) → manages [trip]; active invite {id, draft_name, last_sent_at, expires_at}',
      'en/["F21 קיים"]/איטליה/draft_name,expires_at,id,last_sent_at/["IT", "FR"]/' || m2 || '-01/5/hi',
      (select (e->>'lang') || '/' || (e->'manages')::text || '/' || (e#>>'{active_invite,draft_name}') || '/' ||
              (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(e->'active_invite') k2) || '/' ||
              (e->'countries')::text || '/' || (e->>'month') || '/' || (e->>'travellers') || '/' || (e->>'note')
         from pg_catalog.jsonb_array_elements(res->'requests') e where (e->>'id')::uuid = q4));
    r := qa.f21_rec(r, 706, 'a request without markers → manages [] and active_invite null', '[]/null',
      coalesce((select (e->'manages')::text || '/' || (e->'active_invite')::text
         from pg_catalog.jsonb_array_elements(res->'requests') e where (e->>'id')::uuid = q10), 'not listed'));

    -- ================= 8xx · cleanup (D5 / C5) =================
    update private.trip_requests q set decided_at = now() - interval '6 days' where q.id = q3;           -- rejected 6 d
    update private.trip_requests q set decided_at = now() - interval '4 days' where q.id = qx;           -- rejected 4 d
    update private.trip_requests q set created_at = now() - interval '6 days' where q.id = q6;           -- unverified 6 d
    update private.trip_requests q set created_at = now() - interval '9 days', verified_at = now() - interval '9 days' where q.id = q4; -- pending 9 d
    insert into private.request_attempts (kind, at) values ('start', now() - interval '8 days'), ('start', now() - interval '6 days');
    insert into private.mail_log (kind, at) values ('code', now() - interval '8 days'), ('code', now() - interval '6 days');
    v := qa.f21_val(u_adm, 'authenticated', 'select (public.admin_trip_requests()->>''cap'')');
    r := qa.f21_rec(r, 801, 'D5/C5 the admin list load runs cleanup: rejected 6 d and unverified 6 d gone; rejected 4 d and pending 9 d stay',
      '50/∅/rejected/∅/pending', v || '/' || qa.f21_st(q3) || '/' || qa.f21_st(qx) || '/' || qa.f21_st(q6) || '/' || qa.f21_st(q4));
    r := qa.f21_rec(r, 802, 'cleanup: attempts and mail_log older than 7 days deleted, 6-day-old kept', '0/1/0/1',
      (select count(*)::text from private.request_attempts a where a.at < now() - interval '7 days') || '/' ||
      (select count(*)::text from private.request_attempts a where a.at = now() - interval '6 days') || '/' ||
      (select count(*)::text from private.mail_log l where l.at < now() - interval '7 days') || '/' ||
      (select count(*)::text from private.mail_log l where l.at = now() - interval '6 days'));
    update private.trip_requests q set decided_at = now() - interval '6 days' where q.id = qx;
    perform qa.f21_verify(gen_random_uuid(), qa.f21_h('x'), null);
    r := qa.f21_rec(r, 803, 'C5 every request-trip RPC runs cleanup too (verify)', '∅', qa.f21_st(qx));

    -- ================= 85x · find_invite_for_email (§2.8) =================
    insert into public.manager_invites (email, token_hash, draft_name, inviter_name, expires_at)
      values ('f21-plain@qa.invalid', qa.f21_h('tok-plain'), 'יוון', 'אור', now() + interval '2 days');
    r := qa.f21_rec(r, 851, '§2.8 an invite without a request → exactly the alpha.7 keys (no prefill)',
      'draft_name,expires_at,found,invite_id,inviter_name',
      (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(public.find_invite_for_email(' F21-PLAIN@qa.invalid ')) k2));
    r := qa.f21_rec(r, 852, '§2.8 an approved request''s invite → prefill {countries, lang, month, name}; month null kept as null',
      'countries,lang,month,name/en/Tom Baker/["PT", "ES"]/' || m2 || '-01',
      (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(public.find_invite_for_email('f21-w@qa.invalid')->'prefill') k2) || '/' ||
      (public.find_invite_for_email('f21-w@qa.invalid')#>>'{prefill,lang}') || '/' ||
      (public.find_invite_for_email('f21-w@qa.invalid')#>>'{prefill,name}') || '/' ||
      (public.find_invite_for_email('f21-w@qa.invalid')#>'{prefill,countries}')::text || '/' ||
      (public.find_invite_for_email('f21-w@qa.invalid')#>>'{prefill,month}'));
    delete from private.trip_requests q where q.id = q5;
    r := qa.f21_rec(r, 853, '§2.4 deleting the request row sets invite.request_id null; lookup falls back to no prefill', 'null/false',
      coalesce((select i.request_id::text from public.manager_invites i where i.email = 'f21-w@qa.invalid'), 'null') || '/' ||
      (public.find_invite_for_email('f21-w@qa.invalid') ? 'prefill')::text);

    raise exception 'f21_rollback';
  exception when others then
    if sqlerrm <> 'f21_rollback' then
      r := r || pg_catalog.jsonb_build_array(pg_catalog.jsonb_build_object(
        'id', 0, 'name', 'unexpected error (setup or harness) — later scenarios did not run',
        'detail', 'expected: no error | actual: error ' || sqlstate || ' ' || sqlerrm, 'pass', false));
    end if;
  end;

  perform qa.f21_as(null, 'postgres');

  -- ================= 9xx · grants / catalog (criterion 17, §2.9) =================
  r := qa.f21_rec(r, 901, 'criterion 17: anon / authenticated cannot read or write the 3 private tables',
    'false',
    (select bool_or(pg_catalog.has_table_privilege(g, c.oid, 'select,insert,update,delete'))::text
       from pg_catalog.pg_class c join pg_catalog.pg_namespace s on s.oid = c.relnamespace, unnest(array['anon', 'authenticated']) g
      where s.nspname = 'private' and c.relname in ('trip_requests', 'request_attempts', 'mail_log')));
  r := qa.f21_rec(r, 902, 'criterion 17: a direct select as authenticated / anon → permission denied', 'error 42501/error 42501',
    left(qa.f21_val('f2100000-0000-4000-8000-0000000000a1', 'authenticated', 'select count(*)::text from private.trip_requests'), 11) || '/' ||
    left(qa.f21_val(null, 'anon', 'select count(*)::text from private.mail_log'), 11));
  r := qa.f21_rec(r, 903, '§2.1–2.3 RLS on for the 3 tables, no policies in private', 'true/0',
    (select bool_and(c.relrowsecurity)::text from pg_catalog.pg_class c join pg_catalog.pg_namespace s on s.oid = c.relnamespace
      where s.nspname = 'private' and c.relname in ('trip_requests', 'request_attempts', 'mail_log')) || '/' ||
    (select count(*)::text from pg_catalog.pg_policies p where p.schemaname = 'private'));
  r := qa.f21_rec(r, 904, '§2.9 no anon / authenticated / PUBLIC execute on any F21 service function (7 entry + private f21_* + find_invite)', '0',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where ((s.nspname = 'public' and p.proname in ('request_start','request_verify','request_resend','request_mail_failed','request_approve',
                                                    'request_approve_undo','request_reject','find_invite_for_email'))
             or (s.nspname = 'private' and p.proname like 'f21\_%'))
        and (pg_catalog.has_function_privilege('anon', p.oid, 'execute') or pg_catalog.has_function_privilege('authenticated', p.oid, 'execute')
             or exists (select 1 from pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
                         where a.grantee = 0 and a.privilege_type = 'EXECUTE'))));
  r := qa.f21_rec(r, 905, '§2.9 service_role executes the 7 entry functions + admin_trip_requests', '8',
    (select count(*)::text from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('request_start','request_verify','request_resend','request_mail_failed','request_approve',
                                                  'request_approve_undo','request_reject','admin_trip_requests')
        and pg_catalog.has_function_privilege('service_role', p.oid, 'execute')));
  r := qa.f21_rec(r, 906, '§2.7 admin_trip_requests: authenticated yes, anon / PUBLIC no', 'true/false/false',
    pg_catalog.has_function_privilege('authenticated', 'public.admin_trip_requests()', 'execute')::text || '/' ||
    pg_catalog.has_function_privilege('anon', 'public.admin_trip_requests()', 'execute')::text || '/' ||
    exists (select 1 from pg_catalog.pg_proc p, pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
             where p.oid = 'public.admin_trip_requests()'::regprocedure and a.grantee = 0 and a.privilege_type = 'EXECUTE')::text);
  r := qa.f21_rec(r, 907, '§2.6 entry functions + admin RPC: security definer, search_path='''', no overloads', '9/true/true/9',
    (select count(*)::text || '/' || bool_and(p.prosecdef)::text || '/' || bool_and(coalesce(p.proconfig @> array['search_path=""'], false))::text || '/' ||
            count(distinct p.proname)::text
       from pg_catalog.pg_proc p join pg_catalog.pg_namespace s on s.oid = p.pronamespace
      where s.nspname = 'public' and p.proname in ('request_start','request_verify','request_resend','request_mail_failed','request_approve',
                                                  'request_approve_undo','request_reject','admin_trip_requests','find_invite_for_email')));
  r := qa.f21_rec(r, 908, '§2.9 public keeps exactly the 9 F01 tables; private = F05 + F21 tables', '9/join_attempts,mail_log,request_attempts,transfer_codes,trip_requests',
    (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public') || '/' ||
    (select string_agg(t.tablename, ',' order by t.tablename) from pg_catalog.pg_tables t where t.schemaname = 'private'));
  r := qa.f21_rec(r, 909, 'criterion 17: no new policies on public (= the alpha.7 set)',
    'platform_admins:platform_admins_select_own:SELECT,trip_countries:trip_countries_delete_manager:DELETE,trip_countries:trip_countries_insert_manager:INSERT,trip_countries:trip_countries_select_member:SELECT,trip_countries:trip_countries_update_manager:UPDATE,trip_currencies:trip_currencies_delete_manager:DELETE,trip_currencies:trip_currencies_insert_manager:INSERT,trip_currencies:trip_currencies_select_member:SELECT,trip_currencies:trip_currencies_update_manager:UPDATE,trip_join_codes:trip_join_codes_select_manager:SELECT,trip_kv:trip_kv_delete_editor:DELETE,trip_kv:trip_kv_insert_editor:INSERT,trip_kv:trip_kv_select_member:SELECT,trip_kv:trip_kv_update_editor:UPDATE,trip_members:trip_members_select:SELECT,trips:trips_select_member:SELECT,trips:trips_update_manager:UPDATE',
    (select string_agg(p.tablename || ':' || p.policyname || ':' || p.cmd, ',' order by p.tablename, p.policyname)
       from pg_catalog.pg_policies p where p.schemaname = 'public'));
  r := qa.f21_rec(r, 910, 'criterion 17: no new grant on existing tables for anon / authenticated / PUBLIC (= the alpha.7 set; manager_invites none)',
    'platform_admins:authenticated:SELECT;trip_countries:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_currencies:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_join_codes:authenticated:SELECT;trip_kv:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_members:authenticated:SELECT;trips:authenticated:SELECT',
    (select string_agg(x, ';' order by x) from (
       select g.table_name || ':' || g.grantee || ':' || string_agg(g.privilege_type, ',' order by g.privilege_type) as x
         from information_schema.role_table_grants g
        where g.table_schema = 'public' and g.grantee in ('anon', 'authenticated', 'PUBLIC')
        group by g.table_name, g.grantee) q));
  r := qa.f21_rec(r, 911, '§2.4 manager_invites: 2 new columns (lang not null), RLS on, still no policies, no column grants to clients', 'lang:NO,request_id:YES/true/0/0',
    (select string_agg(c.column_name || ':' || c.is_nullable, ',' order by c.column_name) from information_schema.columns c
      where c.table_schema = 'public' and c.table_name = 'manager_invites' and c.column_name in ('lang', 'request_id')) || '/' ||
    (select c.relrowsecurity::text from pg_catalog.pg_class c where c.oid = 'public.manager_invites'::regclass) || '/' ||
    (select count(*)::text from pg_catalog.pg_policies p where p.schemaname = 'public' and p.tablename = 'manager_invites') || '/' ||
    (select count(*)::text from information_schema.column_privileges c where c.table_schema = 'public' and c.table_name = 'manager_invites'
       and c.grantee in ('anon', 'authenticated', 'PUBLIC')));
  r := qa.f21_rec(r, 912, 'the private schema stays closed to anon / authenticated', 'false/false',
    pg_catalog.has_schema_privilege('anon', 'private', 'usage')::text || '/' ||
    pg_catalog.has_schema_privilege('authenticated', 'private', 'usage')::text);
  r := qa.f21_rec(r, 999, 'Leftovers after the run: 0 f21 users / trips; request and invite counts unchanged', '0/0/true',
    (select count(*) from auth.users u where u.id::text like 'f2100000-%')::text || '/' ||
    (select count(*) from public.trips t where t.name like 'F21 %')::text || '/' ||
    ((select count(*) from private.trip_requests) = n_req_before and (select count(*) from public.manager_invites) = n_inv_before
      and (select count(*) from auth.users) = n_users_before and (select count(*) from public.trips) = n_trips_before)::text);

  return query
    select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail'
      from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
