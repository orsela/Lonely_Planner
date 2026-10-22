# CHANGE 2026-10-22 F06-DEVDB-01: new file (no previous version). Dev self-check, not the QA suite, never touches Supabase.
"""Apply 0001…0014 to a scratch LOCAL PostgreSQL database, run qa.f01–f05 (regression), then exercise the F06 functions.

usage:  sudo -u postgres python3 scripts/dev/f06_db_check.py ""

All F06 scenarios run inside one transaction that is rolled back. Time windows (10 min last_seen, 24 h requests) are
exercised by back-dating rows, never by sleeping. The trigger is exercised as an `authenticated` client (SET LOCAL ROLE +
request.jwt.claims), exactly as the app writes trip_kv.

qa.f05_run() rows 100/101 (C8 "removed → member_removed") test the F05 rule that F06 D2 replaces on purpose; they are
reported as EXPECTED changes, not failures. The same holds for the F05 dev check's "removed → member_removed" row.
"""
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f06_dev"
ORDER = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql",
         "0006_f02.sql", "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql",
         "0011_qa_f04_harness.sql", "0012_f05.sql", "0013_qa_f05_harness.sql", "0014_f06.sql", "0014_f06.sql"]
EXTRA = [MIG / "0015_qa_f06_harness.sql"]   # applied (twice) and run when present (written by the QA team)
EXPECTED_F05_CHANGES = {"100", "101"}       # F05 C8 removed → member_removed, replaced by F06 D2

SCENARIOS = r"""
create temp table r(id serial, name text, pass boolean, detail text);
grant all on r to public; grant all on sequence r_id_seq to public;
do $t$
declare
  mgr uuid := '11111111-1111-4111-8111-111111111111';
  a   uuid := 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
  b   uuid := 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
  c   uuid := 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
  ed  uuid := 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
  mg2 uuid := 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
  pay jsonb := '{"name":"יפן 2027","display_name":"דנה","start_date":"2027-04-03","end_date":"2027-04-20",
                 "home_currency":"ILS","default_lang":"he","default_role":"editor","countries":["JP"],
                 "currencies":[{"code":"JPY","kind":"destination"}],"center":{"lat":35.68,"lng":139.65}}';
  res jsonb; t uuid; t2 uuid; code text; code2 text; mm uuid; ma uuid; mb uuid; mc uuid; me2 uuid; n int; v text; tc text;
  oldcode text; oldver int; i int; ts timestamptz;
begin
  insert into auth.users(id,email) values (mgr,'dana@example.com'),(a,null),(b,null),(c,null),(ed,null),(mg2,'m2@example.com');
  insert into public.manager_invites(email, token_hash, draft_name, inviter_name, expires_at)
    values ('dana@example.com','h1','יפן 2027','אור', now() + interval '7 days'),
           ('m2@example.com','h2','קבוצה 2','אור', now() + interval '7 days');
  res := public.create_trip_from_invite(mgr, 'dana@example.com', pay);
  t := (res->>'trip_id')::uuid; code := res->>'join_code';
  res := public.create_trip_from_invite(mg2, 'm2@example.com', jsonb_set(pay,'{display_name}','"מנהל2"'));
  t2 := (res->>'trip_id')::uuid; code2 := res->>'join_code';
  select id into mm from public.trip_members where trip_id=t and user_id=mgr;
  select id into me2 from public.trip_members where trip_id=t2 and user_id=mg2;
  -- a, b, c join t and are approved (a editor, b viewer, c editor); ed stays pending
  ma := (public.join_request(a, code, 'נועה', 'ipA')->>'member_id')::uuid; perform public.approve_member(mgr, ma, 'approve', 'editor');
  mb := (public.join_request(b, code, 'איתי', 'ipB')->>'member_id')::uuid; perform public.approve_member(mgr, mb, 'approve', 'viewer');
  mc := (public.join_request(c, code, 'רוני', 'ipC')->>'member_id')::uuid; perform public.approve_member(mgr, mc, 'approve', 'editor');
  perform public.join_request(ed, code, 'ממתין', 'ipD');

  -- ================= §2.1 member_set_role =================
  res := public.member_set_role(mgr, ma, 'viewer');
  select role into v from public.trip_members where id=ma;
  insert into r(name,pass,detail) values ('set_role editor→viewer stored', res->>'role'='viewer' and (res->>'changed')::boolean and v='viewer', res::text);
  res := public.member_set_role(mgr, ma, 'manager');
  select role into v from public.trip_members where id=ma;
  insert into r(name,pass,detail) values ('set_role viewer→manager stored', v='manager', res::text);
  res := public.member_set_role(mgr, ma, 'editor');
  select role into v from public.trip_members where id=ma;
  insert into r(name,pass,detail) values ('set_role manager→editor stored (another manager exists)', v='editor', res::text);
  res := public.member_set_role(mgr, ma, 'editor');
  insert into r(name,pass,detail) values ('set_role same role → ok, changed=false', res->>'role'='editor' and not (res->>'changed')::boolean, res::text);
  res := public.member_set_role(mgr, ma, 'boss');
  insert into r(name,pass,detail) values ('set_role bad role → role_invalid', res='{"error":"role_invalid"}', res::text);
  res := public.member_set_role(mgr, ma, null);
  insert into r(name,pass,detail) values ('set_role null role → role_invalid', res='{"error":"role_invalid"}', res::text);
  res := public.member_set_role(a, mb, 'editor');
  insert into r(name,pass,detail) values ('set_role by an editor → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_set_role(mg2, mb, 'editor');
  insert into r(name,pass,detail) values ('set_role by a manager of another trip → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_set_role(mgr, me2, 'viewer');
  insert into r(name,pass,detail) values ('set_role on a member of another trip → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_set_role(mgr, (select id from public.trip_members where user_id=ed and trip_id=t), 'viewer');
  insert into r(name,pass,detail) values ('set_role on a pending row → not_active', res='{"error":"not_active"}', res::text);
  res := public.member_set_role(mgr, gen_random_uuid(), 'viewer');
  insert into r(name,pass,detail) values ('set_role unknown member → not_active', res='{"error":"not_active"}', res::text);
  res := public.member_set_role(null, ma, 'viewer');
  insert into r(name,pass,detail) values ('set_role null user → invalid_request', res='{"error":"invalid_request"}', res::text);
  res := public.member_set_role(mgr, mm, 'editor');
  select role into v from public.trip_members where id=mm;
  insert into r(name,pass,detail) values ('demote the last manager (self) → last_manager, no change', res='{"error":"last_manager"}' and v='manager', res::text);
  -- two managers: one may step down
  perform public.member_set_role(mgr, ma, 'manager');
  res := public.member_set_role(mgr, mm, 'editor');
  select role into v from public.trip_members where id=mm;
  insert into r(name,pass,detail) values ('with two managers, self-demote ok', v='editor', res::text);
  res := public.member_set_role(mgr, mb, 'editor');
  insert into r(name,pass,detail) values ('the demoted (now editor) → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_set_role(a, ma, 'viewer');
  insert into r(name,pass,detail) values ('new sole manager cannot demote self → last_manager', res='{"error":"last_manager"}', res::text);
  perform public.member_set_role(a, mm, 'manager');   -- restore: mgr manager again (a and mgr managers)

  -- ================= §2.2 member_rename =================
  res := public.member_rename(mgr, mb, '  איתי   כהן ');
  select display_name into v from public.trip_members where id=mb;
  insert into r(name,pass,detail) values ('rename: cleaned name stored', v='איתי כהן' and res->>'display_name'='איתי כהן', res::text);
  res := public.member_rename(mgr, mm, 'דנה ל');
  select display_name into v from public.trip_members where id=mm;
  insert into r(name,pass,detail) values ('rename own row ok', v='דנה ל', res::text);
  res := public.member_rename(mgr, mb, 'נועה');
  insert into r(name,pass,detail) values ('rename to an active name → name_taken', res='{"error":"name_taken"}', res::text);
  res := public.member_rename(mgr, mb, 'ממתין');
  insert into r(name,pass,detail) values ('rename to a pending name → name_taken', res='{"error":"name_taken"}', res::text);
  res := public.member_rename(mgr, mb, 'NOAA');
  res := public.member_rename(mgr, mc, ' noaa ');
  insert into r(name,pass,detail) values ('name_taken case/space-insensitive', res='{"error":"name_taken"}', res::text);
  res := public.member_rename(mgr, mb, 'noaa');
  insert into r(name,pass,detail) values ('rename to own name in other case → ok', res->>'display_name'='noaa', res::text);
  res := public.member_rename(mgr, mb, '   ');
  insert into r(name,pass,detail) values ('rename empty → name_invalid', res='{"error":"name_invalid"}', res::text);
  res := public.member_rename(mgr, mb, repeat('א',41));
  insert into r(name,pass,detail) values ('rename 41 chars → name_invalid', res='{"error":"name_invalid"}', res::text);
  res := public.member_rename(c, mb, 'זר');
  insert into r(name,pass,detail) values ('rename by an editor → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_rename(mg2, mb, 'זר');
  insert into r(name,pass,detail) values ('rename by a manager of another trip → not_manager', res='{"error":"not_manager"}', res::text);
  perform public.member_rename(mgr, mb, 'איתי');

  -- ================= §2.3 member_remove =================
  perform public.issue_transfer(b, t);
  select count(*) into n from private.transfer_codes where member_id=mb and used_at is null;
  insert into r(name,pass,detail) values ('setup: b has an open transfer code', n=1, n::text);
  res := public.member_remove(c, mb);
  insert into r(name,pass,detail) values ('remove by an editor → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_remove(mg2, mb);
  insert into r(name,pass,detail) values ('remove by a manager of another trip → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.member_remove(mgr, mm);
  insert into r(name,pass,detail) values ('remove self → invalid_request', res='{"error":"invalid_request"}', res::text);
  res := public.member_remove(mgr, mb);
  select status into v from public.trip_members where id=mb;
  select count(*) into n from private.transfer_codes where member_id=mb and used_at is null;
  insert into r(name,pass,detail) values ('remove: status removed, row kept, open transfer codes deleted', res->>'status'='removed' and v='removed' and n=0, res::text||' codes='||n);
  res := public.member_remove(mgr, mb);
  insert into r(name,pass,detail) values ('remove again → not_active', res='{"error":"not_active"}', res::text);
  res := public.member_set_role(mgr, mb, 'editor');
  insert into r(name,pass,detail) values ('set_role on a removed row → not_active', res='{"error":"not_active"}', res::text);
  res := public.member_rename(mgr, mb, 'x');
  insert into r(name,pass,detail) values ('rename a removed row → not_active', res='{"error":"not_active"}', res::text);
  -- a manager may remove the other manager (the caller stays); remove of an editor
  res := public.member_remove(a, mm);
  select status into v from public.trip_members where id=mm;
  insert into r(name,pass,detail) values ('manager removes the other manager → ok', v='removed', res::text);
  update public.trip_members set status='active' where id=mm;                 -- restore (harness only)
  update public.trip_members set role='editor' where id=ma;
  res := public.member_remove(mgr, ma);
  insert into r(name,pass,detail) values ('remove an editor → ok', res->>'status'='removed', res::text);
  update public.trip_members set status='active', role='manager' where id=ma; -- restore (harness only)
  -- last_manager on remove is only reachable with two managers removing each other at once (spec §2.3); the guard and
  -- the F01 trigger backstop are exercised through member_set_role / member_leave and the direct-write row at the end.

  -- ================= §2.4 member_leave =================
  res := public.member_leave(c, t);
  select status into v from public.trip_members where id=mc;
  insert into r(name,pass,detail) values ('leave: own row removed', res->>'ok'='true' and v='removed', res::text);
  res := public.member_leave(c, t);
  insert into r(name,pass,detail) values ('leave again → not_member', res='{"error":"not_member"}', res::text);
  res := public.member_leave(ed, t);
  insert into r(name,pass,detail) values ('leave while pending → not_member', res='{"error":"not_member"}', res::text);
  res := public.member_leave(mg2, t2);
  select status into v from public.trip_members where id=me2;
  insert into r(name,pass,detail) values ('the only manager leaves → last_manager, row unchanged', res='{"error":"last_manager"}' and v='active', res::text);
  res := public.member_leave(a, t);   -- a and mgr are managers → ok
  select status into v from public.trip_members where id=ma;
  insert into r(name,pass,detail) values ('one of two managers leaves → ok', v='removed', res::text);
  res := public.member_leave(mgr, t);
  insert into r(name,pass,detail) values ('now the only manager → last_manager', res='{"error":"last_manager"}', res::text);
  res := public.member_leave(null, t);
  insert into r(name,pass,detail) values ('leave null user → invalid_request', res='{"error":"invalid_request"}', res::text);

  -- ================= §2.6 D2 removed may ask again =================
  -- b is removed. preview: me=null (form); request: same row → pending with the new name and the default role
  res := public.join_preview(b, code, 'ipB2');
  insert into r(name,pass,detail) values ('D2 preview by a removed identity: me=null (form)', res->'me'='null'::jsonb and res->>'name' is not null, res::text);
  update public.trips set default_role='viewer' where id=t;
  res := public.join_request(b, code, 'איתי חדש', 'ipB2');
  select status||'/'||role||'/'||display_name||'/'||(approved_at is null)::text||'/'||(joined_at > now() - interval '1 minute')::text into v from public.trip_members where id=mb;
  insert into r(name,pass,detail) values ('D2 request re-uses the row: pending, new name, default role, approved_at null, joined_at now',
    (res->>'member_id')::uuid=mb and res->>'status'='pending' and res->>'role'='viewer' and (res->>'created')::boolean and v='pending/viewer/איתי חדש/true/true', res::text||' row='||v);
  select count(*) into n from public.trip_members where trip_id=t and user_id=b;
  insert into r(name,pass,detail) values ('D2 still one row for (trip, user)', n=1, n::text);
  res := public.join_preview(b, code, 'ipB2');
  insert into r(name,pass,detail) values ('D2 preview after re-request: me=pending', res->'me'->>'status'='pending', res::text);
  res := public.approve_member(mgr, mb, 'approve', null);
  select status into v from public.trip_members where id=mb;
  insert into r(name,pass,detail) values ('D2 manager approves → active again', v='active' and res->>'role'='viewer', res::text);
  update public.trips set default_role='editor' where id=t;
  -- D2 limits: name rules apply
  res := public.join_request(c, code, 'נועה', 'ipC2');   -- a (נועה) is removed → name free
  select status into v from public.trip_members where id=mc;
  insert into r(name,pass,detail) values ('D2 removed member''s name is free; c re-requests with it', res->>'status'='pending' and v='pending', res::text);
  perform public.join_cancel(c, t);
  select count(*) into n from public.trip_members where id=mc;
  insert into r(name,pass,detail) values ('D2 cancel of a re-used row deletes it (F05 cancel unchanged)', n=0, n::text);
  res := public.join_request(a, code, 'איתי חדש', 'ipA2');
  insert into r(name,pass,detail) values ('D2 name_taken still applies', res='{"error":"name_taken"}', res::text);
  res := public.join_request(a, code, '   ', 'ipA2');
  insert into r(name,pass,detail) values ('D2 name_invalid still applies', res='{"error":"name_invalid"}', res::text);
  -- 3 successful requests per 24 h: a had 1 (initial); two more ok, then rate_limited
  update public.trip_members set status='removed' where id=ma and status<>'removed';
  res := public.join_request(a, code, 'א2', 'ipA3'); perform public.approve_member(mgr, ma, 'reject', null);
  -- after reject the row is deleted → a is a new identity now; 3rd success ok, 4th limited
  res := public.join_request(a, code, 'א3', 'ipA4');
  insert into r(name,pass,detail) values ('D2 3rd request in 24h ok', res->>'status'='pending', res::text);
  perform public.join_cancel(a, t);
  res := public.join_request(a, code, 'א4', 'ipA5');
  insert into r(name,pass,detail) values ('D2 4th request in 24h → rate_limited', res='{"error":"rate_limited"}', res::text);
  -- a removed row with the 24h limit reached
  update private.join_attempts set at = at - interval '25 hours' where user_id=a and kind='request';
  res := public.join_request(a, code, 'א5', 'ipA6'); ma := (res->>'member_id')::uuid;
  perform public.approve_member(mgr, ma, 'approve', 'editor');
  perform public.member_remove(mgr, ma);
  perform public.join_request(a, code, 'א6', 'ipA7'); perform public.join_cancel(a, t);
  perform public.join_request(a, code, 'א7', 'ipA8'); perform public.approve_member(mgr, (select id from public.trip_members where trip_id=t and user_id=a), 'approve', 'editor');
  perform public.member_remove(mgr, (select id from public.trip_members where trip_id=t and user_id=a));
  res := public.join_request(a, code, 'א8', 'ipA9');
  select status into v from public.trip_members where trip_id=t and user_id=a;
  insert into r(name,pass,detail) values ('D2 removed + 3 successes in 24h → rate_limited, row stays removed', res='{"error":"rate_limited"}' and v='removed', res::text||' '||v);
  -- 20 pending cap applies to a removed identity
  update private.join_attempts set at = at - interval '25 hours' where user_id=a and kind='request';
  for i in 1..20 loop
    me2 := gen_random_uuid(); insert into auth.users(id) values (me2);
    insert into public.trip_members(trip_id,user_id,display_name,role,status) values (t, me2, 'p'||i, 'editor', 'pending');
  end loop;
  res := public.join_request(a, code, 'א9', 'ipA10');
  insert into r(name,pass,detail) values ('D2 removed identity with 20 pending → rate_limited', res='{"error":"rate_limited"}', res::text);
  delete from public.trip_members where trip_id=t and display_name ~ '^p[0-9]+$' and status='pending';
  select id into me2 from public.trip_members where trip_id=t2 and user_id=mg2;

  -- ================= §2.5 rotate_join_code =================
  select jc.code, jc.version into oldcode, oldver from public.trip_join_codes jc where jc.trip_id=t;
  select count(*) into n from public.trip_members where trip_id=t and status='pending';
  res := public.rotate_join_code(b, t);
  insert into r(name,pass,detail) values ('rotate by a viewer → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.rotate_join_code(mg2, t);
  insert into r(name,pass,detail) values ('rotate by a manager of another trip → not_manager', res='{"error":"not_manager"}', res::text);
  -- a transfer code issued before the rotation must stay claimable
  perform public.issue_transfer(b, t);
  res := public.issue_transfer(b, t); tc := res->>'code';
  res := public.rotate_join_code(mgr, t);
  select jc.code into v from public.trip_join_codes jc where jc.trip_id=t;
  insert into r(name,pass,detail) values ('rotate: new 8-char code from the alphabet, version+1, stored',
    res->>'code' ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$' and res->>'code'<>oldcode and (res->>'version')::int=oldver+1 and v=res->>'code', res::text);
  insert into r(name,pass,detail) values ('rotate: rotated_at = now', (select rotated_at > now() - interval '1 minute' from public.trip_join_codes where trip_id=t), '');
  res := public.join_preview(c, oldcode, 'ipR');
  insert into r(name,pass,detail) values ('old code → code_invalid', res='{"error":"code_invalid"}', res::text);
  res := public.join_preview(c, v, 'ipR');
  insert into r(name,pass,detail) values ('new code → preview ok', (res->>'trip_id')::uuid=t, res::text);
  select count(*) into i from public.trip_members where trip_id=t and status='pending';
  insert into r(name,pass,detail) values ('rotate: pending rows unchanged', i=n, n||'→'||i);
  res := public.claim_transfer(c, tc, 'ipR');
  insert into r(name,pass,detail) values ('rotate: earlier transfer code still claimable (D3)', (res->>'trip_id')::uuid=t, res::text);
  res := public.rotate_join_code(mgr, t); res := public.rotate_join_code(mgr, t);
  insert into r(name,pass,detail) values ('rotate twice more → version+3', (res->>'version')::int=oldver+3, res::text);

  -- ================= §2.8 member_touch =================
  res := public.member_touch(mgr, t);
  select last_seen_at into ts from public.trip_members where id=mm;
  insert into r(name,pass,detail) values ('touch: last_seen_at set', (res->>'touched')::boolean and ts is not null, res::text);
  res := public.member_touch(mgr, t);
  insert into r(name,pass,detail) values ('touch again within 10 min → no write', not (res->>'touched')::boolean and (select last_seen_at from public.trip_members where id=mm)=ts, res::text);
  update public.trip_members set last_seen_at = now() - interval '11 minutes' where id=mm;
  res := public.member_touch(mgr, t);
  insert into r(name,pass,detail) values ('touch after 11 min → written', (res->>'touched')::boolean, res::text);
  res := public.member_touch(ed, t);
  insert into r(name,pass,detail) values ('touch by a pending member → not_member', res='{"error":"not_member"}', res::text);
  res := public.member_touch(mgr, t2);
  insert into r(name,pass,detail) values ('touch another trip → not_member', res='{"error":"not_member"}', res::text);

  -- ================= F01 backstop stays =================
  begin
    update public.trip_members set role='editor' where trip_id=t2 and user_id=mg2;
    insert into r(name,pass,detail) values ('F01 last_manager trigger still raises on a direct demotion', false, 'no error');
  exception when check_violation then
    insert into r(name,pass,detail) values ('F01 last_manager trigger still raises on a direct demotion', sqlerrm like 'last_manager%', sqlerrm);
  end;
end
$t$;

-- ================= §2.7 trigger: tripname → trips.name, as authenticated clients =================
do $t$
declare t uuid; mgr uuid := '11111111-1111-4111-8111-111111111111'; v text;
begin
  select trip_id into t from public.trip_members where user_id=mgr limit 1;
  -- c holds b's former membership since the transfer-claim scenario: make it an active editor for the editor case
  update public.trip_members set role='editor', status='active' where trip_id=t and user_id='cccccccc-cccc-4ccc-8ccc-cccccccccccc';
  perform set_config('qa.t', t::text, true);
end $t$;

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
update public.trip_kv set value = '  יפן   2028 ' where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
reset role;
insert into r(name,pass,detail) select 'trigger: manager kv write → trips.name cleaned', name='יפן 2028', name from public.trips where id=current_setting('qa.t')::uuid;
insert into r(name,pass,detail) select 'trigger: kv value itself unchanged', value='  יפן   2028 ', value from public.trip_kv where trip_id=current_setting('qa.t')::uuid and key='tripname';

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","role":"authenticated"}',true);
update public.trip_kv set value = 'שם של עורך' where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
reset role;
insert into r(name,pass,detail) select 'trigger: editor kv write → trips.name unchanged, kv written',
  (select name from public.trips where id=current_setting('qa.t')::uuid)='יפן 2028'
  and (select value from public.trip_kv where trip_id=current_setting('qa.t')::uuid and key='tripname')='שם של עורך',
  (select name from public.trips where id=current_setting('qa.t')::uuid)||' / '||(select value from public.trip_kv where trip_id=current_setting('qa.t')::uuid and key='tripname')
  ||' / c='||(select string_agg(role||':'||status,',') from public.trip_members where user_id='cccccccc-cccc-4ccc-8ccc-cccccccccccc');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
update public.trip_kv set value = '' where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
update public.trip_kv set value = repeat('ש', 81) where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
reset role;
insert into r(name,pass,detail) select 'trigger: 0-char and 81-char values never break the kv write, name unchanged',
  (select name from public.trips where id=current_setting('qa.t')::uuid)='יפן 2028'
  and (select char_length(value) from public.trip_kv where trip_id=current_setting('qa.t')::uuid and key='tripname')=81, '';

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
update public.trip_kv set value = null where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
delete from public.trip_kv where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
insert into public.trip_kv(trip_id, key, value) values (current_setting('qa.t')::uuid, 'tripname', repeat('ת', 80));
update public.trip_kv set value = 'מפתח אחר' where trip_id = current_setting('qa.t')::uuid and key = 'trip';
reset role;
insert into r(name,pass,detail) select 'trigger: null value ok; insert (80 chars) by manager → trips.name; other keys ignored',
  (select name from public.trips where id=current_setting('qa.t')::uuid)=repeat('ת', 80), (select name from public.trips where id=current_setting('qa.t')::uuid);

-- service role write (no auth.uid) → no change
select set_config('request.jwt.claims','',true);
update public.trip_kv set value = 'שירות' where trip_id = current_setting('qa.t')::uuid and key = 'tripname';
insert into r(name,pass,detail) select 'trigger: write without auth.uid() (service role) → trips.name unchanged',
  (select name from public.trips where id=current_setting('qa.t')::uuid)=repeat('ת', 80), '';

-- ================= grants / catalog =================
insert into r(name,pass,detail) select 'no client can execute F06 functions; service_role can (entry + helpers)',
  bool_and(not has_function_privilege('anon', p.oid, 'execute') and not has_function_privilege('authenticated', p.oid, 'execute')
           and (p.proname='f06_tripname_sync' or has_function_privilege('service_role', p.oid, 'execute'))), string_agg(p.proname, ',')
  from pg_proc p join pg_namespace s on s.oid=p.pronamespace
 where (s.nspname='private' and p.proname like 'f06\_%') or (s.nspname='public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch','join_preview','join_request'));
insert into r(name,pass,detail) select 'PUBLIC has no execute on F06 functions',
  not exists (select 1 from pg_proc p join pg_namespace s on s.oid=p.pronamespace, aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
               where ((s.nspname='private' and p.proname like 'f06\_%') or (s.nspname='public' and p.proname like 'member\_%') or p.proname='rotate_join_code')
                 and a.grantee=0 and a.privilege_type='EXECUTE'), '';
insert into r(name,pass,detail) select 'F06 entry functions: 6, security definer, search_path=""',
  count(*)=6 and bool_and(p.prosecdef) and bool_and(p.proconfig @> array['search_path=""']), count(*)::text
  from pg_proc p join pg_namespace s on s.oid=p.pronamespace
 where s.nspname='public' and p.proname in ('member_set_role','member_rename','member_remove','member_leave','rotate_join_code','member_touch');
insert into r(name,pass,detail) select 'helpers in private, security definer, search_path=""',
  count(*)=4 and bool_and(p.prosecdef) and bool_and(p.proconfig @> array['search_path=""']), string_agg(p.proname, ',')
  from pg_proc p join pg_namespace s on s.oid=p.pronamespace where s.nspname='private' and p.proname like 'f06\_%';
insert into r(name,pass,detail) select 'trigger trip_kv_tripname_sync: after insert/update of value, row-level, when key=tripname',
  count(*)=1 and bool_and(pg_get_triggerdef(t.oid) ilike '%AFTER INSERT OR UPDATE OF value ON public.trip_kv FOR EACH ROW WHEN ((new.key = ''tripname''::text))%'), string_agg(pg_get_triggerdef(t.oid), ' | ')
  from pg_trigger t where t.tgrelid='public.trip_kv'::regclass and t.tgname='trip_kv_tripname_sync';
insert into r(name,pass,detail) select 'public still 9 tables; no policy in private; public policies unchanged (17)',
  (select count(*) from pg_tables where schemaname='public')=9 and (select count(*) from pg_policies where schemaname='private')=0
  and (select count(*) from pg_policies where schemaname='public')=17, '';
insert into r(name,pass,detail) select 'no new client grants on existing tables (= alpha.6 set)',
  string_agg(x, ';' order by x) = 'platform_admins:authenticated:SELECT;trip_countries:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_currencies:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_join_codes:authenticated:SELECT;trip_kv:authenticated:DELETE,INSERT,SELECT,UPDATE;trip_members:authenticated:SELECT;trips:authenticated:SELECT', string_agg(x, ';' order by x)
  from (select g.table_name || ':' || g.grantee || ':' || string_agg(g.privilege_type, ',' order by g.privilege_type) as x
          from information_schema.role_table_grants g
         where g.table_schema = 'public' and g.grantee in ('anon', 'authenticated', 'PUBLIC') group by g.table_name, g.grantee) q;
insert into r(name,pass,detail) select 'authenticated cannot call member_set_role directly (42501)', false, 'placeholder';
select id, pass, name, detail from r order by id;
"""

DIRECT_CALL = r"""
begin;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
select public.member_set_role('11111111-1111-4111-8111-111111111111', gen_random_uuid(), 'viewer');
rollback;
"""


def psql(conn, db, *args, input_sql=None):
    cmd = ["psql"] + conn + ["-d", db, "-v", "ON_ERROR_STOP=1", "-X", "-q"] + list(args)
    return subprocess.run(cmd, input=input_sql, capture_output=True, text=True)


def main():
    conn = shlex.split(sys.argv[1]) if len(sys.argv) > 1 else []
    psql(conn, "postgres", "-c", "drop database if exists %s" % DB)
    r = psql(conn, "postgres", "-c", "create database %s" % DB)
    if r.returncode:
        print(r.stderr)
        return 2
    ok = True
    files = [SHIM] + [MIG / n for n in ORDER] + [f for f in EXTRA if f.exists()] * 2
    for f in files:
        r = psql(conn, DB, "-1", "-f", str(f))
        print("apply %-28s %s" % (f.name, "OK" if r.returncode == 0 else "FAIL\n" + r.stderr[-1500:]))
        ok &= r.returncode == 0
    if not ok:
        return 1
    runs = ["f01", "f02", "f03", "f04", "f05"] + (["f06"] if all(f.exists() for f in EXTRA) else [])
    for run in runs:
        r = psql(conn, DB, "-A", "-t", "-F", "\t", "-c", (("select id, pass, scenario from qa.%s_run() order by id") if run == "f01"
                    else "select id, pass, name, detail from qa.%s_run() order by id") % run)
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        expected = [x for x in fails if run == "f05" and x[0] in EXPECTED_F05_CHANGES]
        real = [x for x in fails if x not in expected]
        print("qa.%s_run(): %d/%d pass%s%s" % (run, len(rows) - len(fails), len(rows),
              (" (+%d expected D2 changes)" % len(expected)) if expected else "", "" if not r.returncode else " ERROR " + r.stderr[-300:]))
        for x in expected:
            print("    EXPECTED (F06 D2) %s %s :: %s" % (x[0], x[2] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:200]))
        for x in real:
            print("    FAIL %s %s :: %s" % (x[0], x[2] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:300]))
        ok &= not real and not r.returncode and bool(rows)
    sql = "begin;\n" + SCENARIOS.replace(
        "insert into r(name,pass,detail) select 'authenticated cannot call member_set_role directly (42501)', false, 'placeholder';\n", "") + "\nrollback;\n"
    r = psql(conn, DB, "-A", "-t", "-F", "\t", input_sql=sql)
    if r.returncode:
        print("F06 scenarios ERROR", r.stderr[-2000:])
        return 1
    rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.count("\t") >= 2]
    d = psql(conn, DB, "-A", "-t", input_sql=DIRECT_CALL)
    rows.append([str(len(rows) + 1), "t" if (d.returncode and "permission denied" in d.stderr) else "f",
                 "authenticated cannot call member_set_role directly (permission denied)", d.stderr.strip()[-200:]])
    fails = [x for x in rows if x[1] != "t"]
    for x in rows:
        print("  %s %-3s %s%s" % ("ok " if x[1] == "t" else "FAIL", x[0], x[2], "" if x[1] == "t" else "  :: " + x[3][:300]))
    print("F06 scenarios: %d/%d pass" % (len(rows) - len(fails), len(rows)))
    r = psql(conn, DB, "-A", "-t", "-c", "select (select count(*) from public.trips)+(select count(*) from private.join_attempts)+(select count(*) from private.transfer_codes)")
    left = r.stdout.strip()
    print("leftover rows after rollback:", left)
    ok &= not fails and left == "0"
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
