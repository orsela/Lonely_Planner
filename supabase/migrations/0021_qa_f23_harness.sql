-- Lonely Planner QA · F23 DB-level test harness · version 3.0.0-alpha.12 · F23 (dev harness 1.0.0)
-- CHANGE 2026-11-13 F23-QA-01: new file (no previous version). Installs qa.f23_run() in the locked `qa` schema, same
--   pattern as qa.f21_run() (0017) and reusing its helpers (qa.f21_as / f21_rec / f21_h / f21_e / f21_st / f21_try):
--   all test data lives in a sub-transaction that is always rolled back (raise 'f23_rollback'); time windows are
--   exercised by back-dating rows. The sub-transaction first empties private.trip_requests / request_attempts /
--   mail_log and the request-born invites (rolled back with everything else; nothing real is lost).
--
-- Run (after 0020_f23.sql):   select * from qa.f23_run() order by id;
-- Output: one row per scenario (id, name, pass, detail).
-- Superseded on purpose by 0020: qa.f21_run() rows 7, 101, 128 (mail_log kind 'invite' is now allowed, C4 — row 7
--   expects it to be refused, and its now-successful insert adds one mail to the counts read by rows 101 and 128).

create or replace function qa.f23_j(p jsonb)
returns jsonb language plpgsql set search_path = '' as $f$
begin return p; exception when others then return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm); end $f$;

create or replace function qa.f23_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r      jsonb := '[]'::jsonb;
  u_adm  constant uuid := 'f2300000-0000-4000-8000-0000000000a1';
  u_out  constant uuid := 'f2300000-0000-4000-8000-0000000000a3';
  m2     text := pg_catalog.to_char(private.f21_month_start() + interval '2 months', 'YYYY-MM');
  known  jsonb;
  und    jsonb;
  res    jsonb; res2 jsonb;
  q1 uuid; q2 uuid; q3 uuid; q4 uuid; q5 uuid; q6 uuid; q7 uuid; q8 uuid; q9 uuid;
  i_old  uuid;
  s      text := qa.f21_h('sess-1');
  n_req_before bigint; n_inv_before bigint; n_users_before bigint; n_att_before bigint; n_mail_before bigint;
begin
  select count(*) into n_req_before from private.trip_requests;
  select count(*) into n_inv_before from public.manager_invites;
  select count(*) into n_users_before from auth.users;
  select count(*) into n_att_before from private.request_attempts;
  select count(*) into n_mail_before from private.mail_log;

  begin
    perform qa.f21_as(null, 'postgres');
    delete from private.mail_log;
    delete from private.request_attempts;
    delete from public.manager_invites i where i.request_id is not null;
    delete from private.trip_requests;
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at) values
      (u_adm, 'authenticated', 'authenticated', 'f23-admin@qa.invalid', '00000000-0000-0000-0000-000000000000', now(), now()),
      (u_out, 'authenticated', 'authenticated', 'f23-out@qa.invalid',   '00000000-0000-0000-0000-000000000000', now(), now());
    insert into public.platform_admins (user_id) values (u_adm);
    known := pg_catalog.jsonb_build_object('lang', 'he', 'name', 'דנה QA', 'email', 'f23-a@qa.invalid',
               'countries', pg_catalog.jsonb_build_array('PT'), 'month', m2, 'travellers', 4, 'note', null);
    und := pg_catalog.jsonb_build_object('lang', 'en', 'name', 'Dana QA', 'email', 'f23-u@qa.invalid', 'where_mode', 'undecided',
             'interests', pg_catalog.jsonb_build_array('nature', 'food'), 'max_flight', '8', 'pref_note', 'quiet places',
             'month', null, 'travellers', 5, 'note', null);

    -- ================= 0xx · C10 columns and checks =================
    r := qa.f21_rec(r, 1, 'C10 new columns exist with defaults (where_mode known, suggestions [])', '6/''known''::text/''[]''::jsonb',
      (select count(*)::text from information_schema.columns c where c.table_schema = 'private' and c.table_name = 'trip_requests'
        and c.column_name in ('where_mode', 'interests', 'max_flight', 'pref_note', 'suggestions', 'session_hash')) || '/' ||
      (select c.column_default from information_schema.columns c where c.table_schema = 'private' and c.table_name = 'trip_requests' and c.column_name = 'where_mode') || '/' ||
      (select c.column_default from information_schema.columns c where c.table_schema = 'private' and c.table_name = 'trip_requests' and c.column_name = 'suggestions'));
    r := qa.f21_rec(r, 2, 'C10 status auto_approved allowed; "done" still refused', 'ok/error 23514',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',1,''auto_approved'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{PT}'',1,''done'')'));
    r := qa.f21_rec(r, 3, 'countries {} allowed only for undecided', 'error 23514/ok',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status) values (''he'',''A'',''a@b.co'',''{}'',1,''unverified'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status,where_mode,interests) values (''he'',''A'',''a@b.co'',''{}'',1,''unverified'',''undecided'',''{food}'')'));
    r := qa.f21_rec(r, 4, 'checks: where_mode / interests key / max_flight / pref_note 101', 'error 23514/error 23514/error 23514/error 23514',
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status,where_mode) values (''he'',''A'',''a@b.co'',''{PT}'',1,''unverified'',''maybe'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status,interests) values (''he'',''A'',''a@b.co'',''{PT}'',1,''unverified'',''{shopping}'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status,max_flight) values (''he'',''A'',''a@b.co'',''{PT}'',1,''unverified'',''12'')') || '/' ||
      qa.f21_try('insert into private.trip_requests (lang,name,email,countries,travellers,status,pref_note) values (''he'',''A'',''a@b.co'',''{PT}'',1,''unverified'',repeat(''n'',101))'));
    r := qa.f21_rec(r, 5, 'kinds: attempts suggest + auto, mail invite allowed; "login" refused', 'ok/ok/ok/error 23514',
      qa.f21_try('insert into private.request_attempts (kind) values (''suggest'')') || '/' ||
      qa.f21_try('insert into private.request_attempts (kind) values (''auto'')') || '/' ||
      qa.f21_try('insert into private.mail_log (kind) values (''invite'')') || '/' ||
      qa.f21_try('insert into private.request_attempts (kind) values (''login'')'));
    delete from private.trip_requests; delete from private.request_attempts; delete from private.mail_log;

    -- ================= 1xx · request_start with the undecided payload (C9) =================
    q1 := gen_random_uuid();
    res := public.request_start(q1, und, qa.f21_h('e-u'), qa.f21_h('ip-1'), qa.f21_h(q1::text || '111111'));
    r := qa.f21_rec(r, 101, 'start undecided → row with empty countries, interests, max_flight, pref_note', 'ok/undecided/0/nature,food/8/quiet places',
      qa.f21_e(res) || '/' || (select q.where_mode || '/' || pg_catalog.cardinality(q.countries)::text || '/' || pg_catalog.array_to_string(q.interests, ',') || '/' || q.max_flight || '/' || q.pref_note
                                 from private.trip_requests q where q.id = q1));
    r := qa.f21_rec(r, 102, 'undecided: no interests / bad key / duplicate / 7 → invalid interests', 'interests/interests/interests',
      (public.request_start(gen_random_uuid(), und - 'interests', qa.f21_h('e-x1'), null, qa.f21_h('c'))->>'field') || '/' ||
      (public.request_start(gen_random_uuid(), und || '{"interests":["shopping"]}'::jsonb, qa.f21_h('e-x2'), null, qa.f21_h('c'))->>'field') || '/' ||
      (public.request_start(gen_random_uuid(), und || '{"interests":["food","food"]}'::jsonb, qa.f21_h('e-x3'), null, qa.f21_h('c'))->>'field'));
    r := qa.f21_rec(r, 103, 'undecided: countries given / max_flight 12 / pref_note 101 / where_mode bad', 'countries/max_flight/pref_note/where_mode',
      (public.request_start(gen_random_uuid(), und || '{"countries":["PT"]}'::jsonb, qa.f21_h('e-x4'), null, qa.f21_h('c'))->>'field') || '/' ||
      (public.request_start(gen_random_uuid(), und || '{"max_flight":"12"}'::jsonb, qa.f21_h('e-x5'), null, qa.f21_h('c'))->>'field') || '/' ||
      (public.request_start(gen_random_uuid(), und || pg_catalog.jsonb_build_object('pref_note', pg_catalog.repeat('n', 101)), qa.f21_h('e-x6'), null, qa.f21_h('c'))->>'field') || '/' ||
      (public.request_start(gen_random_uuid(), und || '{"where_mode":"maybe"}'::jsonb, qa.f21_h('e-x7'), null, qa.f21_h('c'))->>'field'));
    q2 := gen_random_uuid();
    res := public.request_start(q2, known, qa.f21_h('e-a'), qa.f21_h('ip-2'), qa.f21_h(q2::text || '222222'));
    r := qa.f21_rec(r, 104, 'start without where_mode = F21 (known, countries kept, max_flight default only for undecided)', 'ok/known/PT/∅',
      qa.f21_e(res) || '/' || (select q.where_mode || '/' || pg_catalog.array_to_string(q.countries, ',') || '/' || coalesce(q.max_flight, '∅')
                                 from private.trip_requests q where q.id = q2));
    q9 := gen_random_uuid();
    res := public.request_start(q9, (und - 'max_flight') || '{"email":"f23-d@qa.invalid"}'::jsonb, qa.f21_h('e-d'), null, qa.f21_h('c'));
    r := qa.f21_rec(r, 105, 'undecided: max_flight defaults to 5 when absent', 'ok/5',
      qa.f21_e(res) || '/' || (select q.max_flight from private.trip_requests q where q.id = q9));

    -- ================= 2xx · request_verify2 (C1, C2) =================
    insert into public.manager_invites (email, token_hash, draft_name, expires_at) values ('f23-a@qa.invalid', 'f23-old-hash', 'ישן', now() + interval '3 days')
      returning id into i_old;
    res := public.request_verify2(q2, qa.f21_h(q2::text || '999999'), qa.f21_h('ip-2'), true, qa.f21_h('tok-2'), s, 'פורטוגל');
    r := qa.f21_rec(r, 201, 'verify2 wrong code → code_wrong 4, still unverified, no invite', 'code_wrong/4/unverified/0',
      qa.f21_e(res) || '/' || (res->>'attempts_left') || '/' || qa.f21_st(q2) || '/' ||
      (select count(*)::text from public.manager_invites i where i.request_id = q2));
    res := public.request_verify2(q2, qa.f21_h(q2::text || '222222'), qa.f21_h('ip-2'), true, qa.f21_h('tok-2'), s, 'פורטוגל');
    r := qa.f21_rec(r, 202, 'C1 verify2 known + auto → auto_approved, invite linked (lang, draft, 7 days, no admin), mail logged', 'ok/ready/auto_approved/true/true/true',
      qa.f21_e(res) || '/' || (res->>'next') || '/' || qa.f21_st(q2) || '/' ||
      (select (i.token_hash = qa.f21_h('tok-2') and i.lang = 'he' and i.draft_name = 'פורטוגל' and i.invited_by is null
               and i.expires_at = now() + interval '7 days' and i.used_at is null and i.revoked_at is null)::text
         from public.manager_invites i where i.id = (res->>'invite_id')::uuid) || '/' ||
      (res->'mail')::text || '/' ||
      (select (count(*) = 1)::text from private.mail_log l where l.kind = 'invite' and l.request_id = q2));
    r := qa.f21_rec(r, 203, 'D12 the previous open invite of the email was revoked and reported', 'true/true',
      (select (i.revoked_at is not null)::text from public.manager_invites i where i.id = i_old) || '/' ||
      ((res->>'revoked_invite_id')::uuid = i_old)::text);
    r := qa.f21_rec(r, 204, 'request row: invite_id, decided_at, no decided_by, code cleared', 'true',
      (select (q.invite_id = (res->>'invite_id')::uuid and q.decided_at is not null and q.decided_by is null and q.code_hash is null
               and q.verified_at is not null)::text from private.trip_requests q where q.id = q2));
    r := qa.f21_rec(r, 205, 'find_invite_for_email carries the request prefill', 'true/["PT"]',
      (public.find_invite_for_email('f23-a@qa.invalid')->>'found') || '/' || (public.find_invite_for_email('f23-a@qa.invalid')->'prefill'->'countries')::text);
    r := qa.f21_rec(r, 206, 'verify2 again on a handled request → request_unknown', 'request_unknown',
      qa.f21_e(public.request_verify2(q2, qa.f21_h(q2::text || '222222'), null, true, qa.f21_h('tok-2b'), s, null)));

    res2 := public.request_invite_draft(q2, (res->>'invite_id')::uuid, '  פורטוגל · ינואר 2027 ');
    r := qa.f21_rec(r, 213, 'request_invite_draft sets the trip name of the automatic invite (trimmed); wrong pair / 81 chars refused', 'true/פורטוגל · ינואר 2027/false/invalid_request',
      (res2->>'ok') || '/' || (select i.draft_name from public.manager_invites i where i.id = (res->>'invite_id')::uuid) || '/' ||
      (public.request_invite_draft(q2, i_old, 'x')->>'ok') || '/' || qa.f21_e(public.request_invite_draft(q2, (res->>'invite_id')::uuid, pg_catalog.repeat('x', 81))));

    -- criterion 9: one auto-approval per email per day
    q3 := gen_random_uuid();
    res := public.request_start(q3, known, qa.f21_h('e-a'), qa.f21_h('ip-2'), qa.f21_h(q3::text || '333333'));
    res := public.request_verify2(q3, qa.f21_h(q3::text || '333333'), qa.f21_h('ip-2'), true, qa.f21_h('tok-3'), s, null);
    r := qa.f21_rec(r, 207, 'criterion 9: second auto-approval same email same day → rate_limited, code not consumed, first invite intact', 'rate_limited/unverified/true/true',
      qa.f21_e(res) || '/' || qa.f21_st(q3) || '/' ||
      (select (q.code_hash is not null)::text from private.trip_requests q where q.id = q3) || '/' ||
      (select (count(*) = 1)::text from public.manager_invites i where i.email = 'f23-a@qa.invalid' and i.used_at is null and i.revoked_at is null));
    update private.request_attempts a set at = now() - interval '25 hours' where a.kind = 'auto';
    res := public.request_verify2(q3, qa.f21_h(q3::text || '333333'), qa.f21_h('ip-2'), true, qa.f21_h('tok-3'), s, null);
    r := qa.f21_rec(r, 208, 'the next day the same email is auto-approved again', 'ok/auto_approved', qa.f21_e(res) || '/' || qa.f21_st(q3));

    -- manual mode
    q4 := gen_random_uuid();
    res := public.request_start(q4, known || '{"email":"f23-m@qa.invalid"}'::jsonb, qa.f21_h('e-m'), null, qa.f21_h(q4::text || '444444'));
    res := public.request_verify2(q4, qa.f21_h(q4::text || '444444'), null, false, null, s, null);
    r := qa.f21_rec(r, 209, 'criterion 11: verify2 with p_auto false = F21 (pending, no invite)', 'ok/pending/pending/0',
      qa.f21_e(res) || '/' || (res->>'next') || '/' || qa.f21_st(q4) || '/' || (select count(*)::text from public.manager_invites i where i.request_id = q4));
    res2 := public.request_approve(u_adm, q4, qa.f21_h('tok-4'), 'ידני', 'אור');
    r := qa.f21_rec(r, 210, 'F21 request_approve still works on it', 'ok/approved', qa.f21_e(res2) || '/' || qa.f21_st(q4));

    -- C4 cap
    q5 := gen_random_uuid();
    res := public.request_start(q5, known || '{"email":"f23-c@qa.invalid"}'::jsonb, qa.f21_h('e-c'), null, qa.f21_h(q5::text || '555555'));
    insert into private.mail_log (kind) select 'code' from pg_catalog.generate_series(1, 50);
    res := public.request_verify2(q5, qa.f21_h(q5::text || '555555'), null, true, qa.f21_h('tok-5'), s, null);
    r := qa.f21_rec(r, 211, 'C4 at the mail cap: auto-approved, mail false, no invite mail row', 'ok/auto_approved/false/0',
      qa.f21_e(res) || '/' || qa.f21_st(q5) || '/' || (res->'mail')::text || '/' ||
      (select count(*)::text from private.mail_log l where l.kind = 'invite' and l.request_id = q5));
    delete from private.mail_log l where l.request_id is null;
    res2 := public.request_invite_mail_failed(q2);
    r := qa.f21_rec(r, 212, 'request_invite_mail_failed removes the invite mail row only', 'ok/0/auto_approved',
      qa.f21_e(res2) || '/' ||
      (select count(*)::text from private.mail_log l where l.kind = 'invite' and l.request_id = q2) || '/' || qa.f21_st(q2));

    -- ================= 3xx · undecided: verify2 → suggest → choose (C2, C5, C7) =================
    res := public.request_verify2(q1, qa.f21_h(q1::text || '111111'), qa.f21_h('ip-1'), true, qa.f21_h('tok-1'), s, null);
    r := qa.f21_rec(r, 301, 'C2 verify2 undecided → next suggest, pending, session stored, NO invite', 'ok/suggest/3/pending/true/0',
      qa.f21_e(res) || '/' || (res->>'next') || '/' || (res->>'left') || '/' || qa.f21_st(q1) || '/' ||
      (select (q.session_hash = s)::text from private.trip_requests q where q.id = q1) || '/' ||
      (select count(*)::text from public.manager_invites i where i.request_id = q1));
    r := qa.f21_rec(r, 302, 'admin list: the undecided request is not pending work', '0',
      qa.f21_val(u_adm, 'authenticated', 'select pg_catalog.jsonb_array_length(public.admin_trip_requests()->''requests'')::text'));
    res := public.request_suggest_begin(q1, s, true);
    r := qa.f21_rec(r, 303, 'C6 suggest_begin returns prompt data only — no name, no email', 'ok/false/false/en/8/["nature", "food"]/quiet places/5/2',
      qa.f21_e(res) || '/' || (res ? 'name')::text || '/' || (res ? 'email')::text || '/' || (res->>'lang') || '/' || (res->>'max_flight') || '/' ||
      (res->'interests')::text || '/' || (res->>'pref_note') || '/' || (res->>'travellers') || '/' || (res->>'left'));
    r := qa.f21_rec(r, 304, 'criterion 8: wrong session / unknown request → request_unknown, nothing counted', 'request_unknown/request_unknown/1',
      qa.f21_e(public.request_suggest_begin(q1, qa.f21_h('other'), true)) || '/' || qa.f21_e(public.request_suggest_begin(gen_random_uuid(), s, true)) || '/' ||
      (select count(*)::text from private.request_attempts a where a.kind = 'suggest'));
    res := public.request_suggest_save(q1, s, array['GR', 'IT', 'HR']);
    res := public.request_suggest_begin(q1, s, true);
    r := qa.f21_rec(r, 305, 'D4 the second set sees the first as shown; 1 left', '["GR", "IT", "HR"]/1', (res->'shown')::text || '/' || (res->>'left'));
    res := public.request_suggest_save(q1, s, array['CY', 'GE']);
    res := public.request_suggest_begin(q1, s, true);
    r := qa.f21_rec(r, 306, 'third set: 5 shown, 0 left; a 4th call → suggest_limit', '5/0/suggest_limit',
      pg_catalog.jsonb_array_length(res->'shown')::text || '/' || (res->>'left') || '/' || qa.f21_e(public.request_suggest_begin(q1, s, true)));
    r := qa.f21_rec(r, 307, 'suggest_save: bad list → invalid_request', 'invalid_request/invalid_request',
      qa.f21_e(public.request_suggest_save(q1, s, array['gr'])) || '/' || qa.f21_e(public.request_suggest_save(q1, s, array['A1', 'B2', 'C3', 'D4']::text[])));
    r := qa.f21_rec(r, 308, 'criterion 8: choose with wrong session / bad country → nothing changes', 'request_unknown/invalid_request/0',
      qa.f21_e(public.request_choose(q1, qa.f21_h('other'), 'GR', true, qa.f21_h('tok-1'), null)) || '/' ||
      qa.f21_e(public.request_choose(q1, s, 'gr', true, qa.f21_h('tok-1'), null)) || '/' ||
      (select pg_catalog.cardinality(q.countries)::text from private.trip_requests q where q.id = q1));
    res := public.request_choose(q1, s, 'GR', true, qa.f21_h('tok-1'), 'Greece');
    r := qa.f21_rec(r, 309, 'choose → countries set, auto_approved, invite in the request language, session cleared', 'ok/ready/auto_approved/GR/en/true',
      qa.f21_e(res) || '/' || (res->>'next') || '/' || qa.f21_st(q1) || '/' ||
      (select pg_catalog.array_to_string(q.countries, ',') from private.trip_requests q where q.id = q1) || '/' ||
      (select i.lang from public.manager_invites i where i.id = (res->>'invite_id')::uuid) || '/' ||
      (select (q.session_hash is null)::text from private.trip_requests q where q.id = q1));
    r := qa.f21_rec(r, 310, 'criterion 8: suggest / choose on a request that has countries → request_unknown', 'request_unknown/request_unknown',
      qa.f21_e(public.request_suggest_begin(q1, s, true)) || '/' || qa.f21_e(public.request_choose(q1, s, 'IT', true, qa.f21_h('tok-1b'), null)));

    -- 30 minutes, and the daily AI cap
    q6 := gen_random_uuid();
    res := public.request_start(q6, und || '{"email":"f23-t@qa.invalid"}'::jsonb, qa.f21_h('e-t'), null, qa.f21_h(q6::text || '666666'));
    res := public.request_verify2(q6, qa.f21_h(q6::text || '666666'), null, true, qa.f21_h('tok-6'), s, null);
    insert into private.request_attempts (kind) select 'suggest' from pg_catalog.generate_series(1, 27);
    r := qa.f21_rec(r, 311, 'C7 30 AI calls today → suggest_unavailable (not counted); admin counter 30 of 30', 'suggest_unavailable/30/30/30',
      qa.f21_e(public.request_suggest_begin(q6, s, true)) || '/' || private.f23_suggest_today()::text || '/' ||
      qa.f21_val(u_adm, 'authenticated', 'select (public.admin_trip_requests()->>''ai_today'')') || '/' ||
      qa.f21_val(u_adm, 'authenticated', 'select (public.admin_trip_requests()->>''ai_cap'')'));
    res2 := public.request_suggest_begin(q6, s, false);
    r := qa.f21_rec(r, 316, 'suggest_begin without counting: session check only, works at the cap, counts nothing, no prompt data', 'ok/false/30',
      qa.f21_e(res2) || '/' || (res2 ? 'interests')::text || '/' || private.f23_suggest_today()::text);
    r := qa.f21_rec(r, 317, 'suggest_begin without counting still refuses a wrong session', 'request_unknown',
      qa.f21_e(public.request_suggest_begin(q6, qa.f21_h('other'), false)));
    update private.request_attempts a set at = now() - interval '25 hours' where a.kind = 'suggest' and a.request_id is null;
    r := qa.f21_rec(r, 312, 'the cap is per Israel day: yesterday''s calls do not count', 'ok', qa.f21_e(public.request_suggest_begin(q6, s, true)));
    update private.trip_requests q set verified_at = now() - interval '31 minutes' where q.id = q6;
    r := qa.f21_rec(r, 313, 'criterion 8: after 30 minutes → request_unknown for suggest and choose', 'request_unknown/request_unknown/pending',
      qa.f21_e(public.request_suggest_begin(q6, s, true)) || '/' || qa.f21_e(public.request_choose(q6, s, 'GR', true, qa.f21_h('tok-6'), null)) || '/' || qa.f21_st(q6));

    -- fallback picker in manual mode, and choose refused by the per-day auto limit
    q7 := gen_random_uuid();
    res := public.request_start(q7, und || '{"email":"f23-p@qa.invalid"}'::jsonb, qa.f21_h('e-p'), null, qa.f21_h(q7::text || '777777'));
    res := public.request_verify2(q7, qa.f21_h(q7::text || '777777'), null, false, null, s, null);
    res := public.request_choose(q7, s, 'JP', false, null, null);
    r := qa.f21_rec(r, 314, 'manual mode: undecided → suggest; choose → pending with the country, listed for the admin', 'ok/pending/JP/1',
      qa.f21_e(res) || '/' || qa.f21_st(q7) || '/' || (select pg_catalog.array_to_string(q.countries, ',') from private.trip_requests q where q.id = q7) || '/' ||
      qa.f21_val(u_adm, 'authenticated', 'select pg_catalog.jsonb_array_length(public.admin_trip_requests()->''requests'')::text'));
    q8 := gen_random_uuid();
    res := public.request_start(q8, und, qa.f21_h('e-u'), null, qa.f21_h(q8::text || '888888'));
    res := public.request_verify2(q8, qa.f21_h(q8::text || '888888'), null, true, qa.f21_h('tok-8'), s, null);
    res := public.request_choose(q8, s, 'IT', true, qa.f21_h('tok-8'), null);
    r := qa.f21_rec(r, 315, 'criterion 9 via choose: same email already auto-approved today → rate_limited, countries stay empty', 'rate_limited/pending/0',
      qa.f21_e(res) || '/' || qa.f21_st(q8) || '/' || (select pg_catalog.cardinality(q.countries)::text from private.trip_requests q where q.id = q8));

    -- ================= 4xx · admin list (C11), cleanup, grants =================
    res := qa.f21_val(u_adm, 'authenticated', 'select public.admin_trip_requests()::text')::jsonb;
    r := qa.f21_rec(r, 401, 'C11 admin list: keys; auto history holds the auto-approved requests with their invite', 'ai_cap,ai_today,auto,cap,mail_today,requests/4/true',
      (select string_agg(k2, ',' order by k2) from pg_catalog.jsonb_object_keys(res) k2) || '/' || pg_catalog.jsonb_array_length(res->'auto')::text || '/' ||
      (select pg_catalog.bool_and(e->'invite' ? 'id' and e ? 'where_mode')::text from pg_catalog.jsonb_array_elements(res->'auto') e));
    update public.manager_invites i set revoked_at = now() where i.request_id = q1;
    r := qa.f21_rec(r, 402, 'C11 a revoked auto invite shows revoked_at and no longer resolves for the email', 'true/false',
      (select (e->'invite'->>'revoked_at' is not null)::text from pg_catalog.jsonb_array_elements(
         qa.f21_val(u_adm, 'authenticated', 'select public.admin_trip_requests()::text')::jsonb->'auto') e where (e->>'id')::uuid = q1) || '/' ||
      (public.find_invite_for_email('f23-u@qa.invalid')->>'found'));
    r := qa.f21_rec(r, 403, 'admin list refused for a non-admin', 'error 42501',
      qa.f21_val(u_out, 'authenticated', 'select public.admin_trip_requests()::text'));
    -- CHANGE 2026-11-13 F23-QA-05: 3 days (Or's decision), was 5 in the first draft; + the "not yet" half (row 408)
    update private.trip_requests q set verified_at = now() - interval '2 days 23 hours' where q.id = q8;
    perform private.f23_cleanup();
    r := qa.f21_rec(r, 408, 'cleanup: a verified request without a destination is kept for 3 days', 'pending', qa.f21_st(q8));
    update private.trip_requests q set verified_at = now() - interval '3 days 1 hour' where q.id = q8;
    perform private.f23_cleanup();
    r := qa.f21_rec(r, 404, 'cleanup: a verified request without a destination goes after 3 days; auto_approved stays', '∅/auto_approved', qa.f21_st(q8) || '/' || qa.f21_st(q2));
    r := qa.f21_rec(r, 405, 'grants: the new functions are closed to anon / authenticated', 'false/false/false/false/false',
      pg_catalog.has_function_privilege('anon', 'public.request_verify2(uuid,text,text,boolean,text,text,text)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.request_suggest_begin(uuid,text,boolean)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.request_suggest_save(uuid,text,text[])', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('anon', 'public.request_choose(uuid,text,text,boolean,text,text)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.request_invite_mail_failed(uuid)', 'execute')::text);
    r := qa.f21_rec(r, 406, 'private.f23_email_hash = SHA-256 hex of the normalized email', 'true',
      (private.f23_email_hash('  Dana@Example.COM ') = qa.f21_h('dana@example.com'))::text);
    r := qa.f21_rec(r, 407, 'public still has exactly the 9 F01 tables', '9',
      (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public'));

    raise exception 'f23_rollback';
  exception when others then
    execute 'reset role';
    if sqlerrm <> 'f23_rollback' then
      r := qa.f21_rec(r, 998, 'harness error', 'none', sqlstate || ' ' || sqlerrm);
    end if;
  end;

  r := qa.f21_rec(r, 999, 'Leftovers after the run: counts unchanged', 'true',
    ((select count(*) from private.trip_requests) = n_req_before and (select count(*) from public.manager_invites) = n_inv_before
      and (select count(*) from auth.users) = n_users_before and (select count(*) from private.request_attempts) = n_att_before
      and (select count(*) from private.mail_log) = n_mail_before)::text);

  return query
    select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail'
      from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
