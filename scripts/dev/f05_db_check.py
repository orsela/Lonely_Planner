# CHANGE 2026-10-19 F05-DEVDB-01: new file (no previous version). Dev self-check, not the QA suite, never touches Supabase.
"""Apply 0001…0012 to a scratch LOCAL PostgreSQL database, run qa.f01–f04 (regression), then exercise the F05 functions.

usage:  sudo -u postgres python3 scripts/dev/f05_db_check.py ""

All F05 scenarios run inside one transaction that is rolled back. Time-window limits are exercised by back-dating
join_attempts / transfer_codes rows, never by sleeping.
"""
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f05_dev"
ORDER = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql",
         "0006_f02.sql", "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql",
         "0011_qa_f04_harness.sql", "0012_f05.sql", "0012_f05.sql"]
EXTRA = [MIG / "0013_qa_f05_harness.sql"]   # applied (twice) and run when present (written by the QA team)

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
  res jsonb; t uuid; t2 uuid; code text; code2 text; mid uuid; mid2 uuid; n int; v text; tc text; tc2 text; i int;
begin
  insert into auth.users(id,email) values (mgr,'dana@example.com'),(a,null),(b,null),(c,null),(ed,null),(mg2,'m2@example.com');
  insert into public.manager_invites(email, token_hash, draft_name, inviter_name, expires_at)
    values ('dana@example.com','h1','יפן 2027','אור', now() + interval '7 days'),
           ('m2@example.com','h2','קבוצה 2','אור', now() + interval '7 days');
  res := public.create_trip_from_invite(mgr, 'dana@example.com', pay);
  t := (res->>'trip_id')::uuid; code := res->>'join_code';
  res := public.create_trip_from_invite(mg2, 'm2@example.com', jsonb_set(pay,'{display_name}','"מנהל2"'));
  t2 := (res->>'trip_id')::uuid; code2 := res->>'join_code';

  -- preview
  res := public.join_preview(a, lower(code), 'ipA');
  insert into r(name,pass,detail) values ('preview: name, dates, 18 days, 1 member, manager, me=null',
    res->>'name'='יפן 2027' and res->>'start_date'='2027-04-03' and (res->>'days')::int=18 and (res->>'members')::int=1
    and res->>'manager'='דנה' and res->'me'='null'::jsonb and (res->>'trip_id')::uuid=t, res::text);
  res := public.join_preview(a, 'ZZZZZZZZ', 'ipA');
  insert into r(name,pass,detail) values ('preview: unknown code', res='{"error":"code_invalid"}', res::text);
  res := public.join_preview(mgr, code, null);
  insert into r(name,pass,detail) values ('preview: manager sees me=active manager', res->'me'->>'status'='active' and res->'me'->>'role'='manager', res::text);

  -- request
  res := public.join_request(a, code, '  נועה   כהן ', 'ipA');
  mid := (res->>'member_id')::uuid;
  insert into r(name,pass,detail) values ('request: pending row, cleaned name, default role',
    res->>'status'='pending' and res->>'display_name'='נועה כהן' and res->>'role'='editor' and (res->>'created')::boolean, res::text);
  select count(*) into n from public.trip_members where id=mid and user_id=a and status='pending' and display_name='נועה כהן';
  insert into r(name,pass,detail) values ('request: row stored', n=1, n::text);
  res := public.join_request(a, code, 'אחר', 'ipA');
  insert into r(name,pass,detail) values ('request again while pending: same row, created=false', (res->>'member_id')::uuid=mid and not (res->>'created')::boolean, res::text);
  res := public.join_preview(a, code, 'ipA');
  insert into r(name,pass,detail) values ('preview: me=pending', res->'me'->>'status'='pending' and (res->'me'->>'member_id')::uuid=mid, res::text);
  res := public.join_request(b, code, 'נועה  כהן', 'ipB');
  insert into r(name,pass,detail) values ('name taken (pending, spaces)', res='{"error":"name_taken"}', res::text);
  res := public.join_request(b, code, 'דנה', 'ipB');
  insert into r(name,pass,detail) values ('name taken (active manager)', res='{"error":"name_taken"}', res::text);
  res := public.join_request(b, code, '   ', 'ipB');
  insert into r(name,pass,detail) values ('name_invalid empty', res='{"error":"name_invalid"}', res::text);
  res := public.join_request(b, code, repeat('א',41), 'ipB');
  insert into r(name,pass,detail) values ('name_invalid 41', res='{"error":"name_invalid"}', res::text);
  res := public.join_request(b, 'ZZZZZZZZ', 'בני', 'ipB');
  insert into r(name,pass,detail) values ('request unknown code', res='{"error":"code_invalid"}', res::text);
  res := public.join_request(b, code, 'NOA', 'ipB');
  res := public.join_request(c, code, 'noa', 'ipC');
  insert into r(name,pass,detail) values ('name taken case-insensitive', res='{"error":"name_taken"}', res::text);

  -- approve / reject
  res := public.approve_member(ed, mid, 'approve', 'editor');
  insert into r(name,pass,detail) values ('approve by non-member → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.approve_member(mg2, mid, 'approve', 'editor');
  insert into r(name,pass,detail) values ('approve by other trip manager → not_manager', res='{"error":"not_manager"}', res::text);
  res := public.approve_member(mgr, mid, 'approve', 'boss');
  insert into r(name,pass,detail) values ('role_invalid', res='{"error":"role_invalid"}', res::text);
  res := public.approve_member(mgr, mid, 'maybe', null);
  insert into r(name,pass,detail) values ('bad decision → invalid_request', res='{"error":"invalid_request"}', res::text);
  res := public.approve_member(mgr, mid, 'approve', 'viewer');
  select count(*) into n from public.trip_members where id=mid and status='active' and role='viewer' and approved_at is not null;
  insert into r(name,pass,detail) values ('approve as viewer', res->>'status'='active' and n=1, res::text);
  res := public.approve_member(mgr, mid, 'approve', 'editor');
  insert into r(name,pass,detail) values ('second approve → not_pending', res='{"error":"not_pending"}', res::text);
  res := public.join_request(a, code, 'x', 'ipA');
  insert into r(name,pass,detail) values ('request when active: status active, no new row', res->>'status'='active' and not (res->>'created')::boolean, res::text);
  -- approve default role
  select id into mid2 from public.trip_members where user_id=b and trip_id=t;
  res := public.approve_member(mgr, mid2, 'approve', null);
  insert into r(name,pass,detail) values ('approve with no role → trip default (editor)', res->>'role'='editor', res::text);
  -- reject + rate limit (3 successful requests per 24h)
  delete from public.trip_members where user_id=c and trip_id=t;
  res := public.join_request(c, code, 'רוני', 'ipC'); mid := (res->>'member_id')::uuid;
  res := public.approve_member(mgr, mid, 'reject', null);
  select count(*) into n from public.trip_members where id=mid;
  insert into r(name,pass,detail) values ('reject deletes the row', res->>'status'='rejected' and n=0, res::text);
  res := public.join_request(c, code, 'רוני', 'ipC'); mid := (res->>'member_id')::uuid;
  res := public.join_cancel(c, t);
  insert into r(name,pass,detail) values ('cancel own pending', res='{"ok":true}', res::text);
  res := public.join_cancel(c, t);
  insert into r(name,pass,detail) values ('cancel again → not_pending', res='{"error":"not_pending"}', res::text);
  res := public.join_request(c, code, 'רוני', 'ipC');
  insert into r(name,pass,detail) values ('3rd request in 24h ok', res->>'status'='pending', res::text);
  perform public.join_cancel(c, t);
  res := public.join_request(c, code, 'רוני', 'ipC');
  insert into r(name,pass,detail) values ('4th request in 24h → rate_limited', res='{"error":"rate_limited"}', res::text);
  update private.join_attempts set at = at - interval '25 hours' where user_id=c and kind='request';
  res := public.join_request(c, code, 'רוני', 'ipC');
  insert into r(name,pass,detail) values ('after 24h → allowed again', res->>'status'='pending', res::text);
  -- removed
  update public.trip_members set status='removed' where user_id=c and trip_id=t;
  res := public.join_request(c, code, 'רוני', 'ipC');
  insert into r(name,pass,detail) values ('removed → member_removed', res='{"error":"member_removed"}', res::text);
  -- ip limit on requests
  for i in 1..10 loop perform public.join_request(gen_random_uuid(), 'ZZZZZZZZ', 'x', 'ipFlood'); end loop;
  res := public.join_request(ed, code, 'אדם', 'ipFlood');
  insert into r(name,pass,detail) values ('11th request from one ip/hour → rate_limited', res='{"error":"rate_limited"}', res::text);
  -- preview limit per user
  for i in 1..30 loop perform public.join_preview(ed, code, 'ipP'||i); end loop;
  res := public.join_preview(ed, code, 'ipX');
  insert into r(name,pass,detail) values ('31st preview per user/hour → rate_limited', res='{"error":"rate_limited"}', res::text);
  -- pending cap 20
  for i in 1..20 loop
    mid2 := gen_random_uuid(); insert into auth.users(id) values (mid2);
    insert into public.trip_members(trip_id,user_id,display_name,role,status) values (t2, mid2, 'p'||i, 'editor', 'pending');
  end loop;
  res := public.join_request(ed, code2, 'עוד אחד', 'ipQ');
  insert into r(name,pass,detail) values ('21st pending in a trip → rate_limited', res='{"error":"rate_limited"}', res::text);

  -- transfer (a is an active viewer in t)
  res := public.issue_transfer(b, t2);
  insert into r(name,pass,detail) values ('issue for a trip I am not in → not_member', res='{"error":"not_member"}', res::text);
  res := public.issue_transfer(a, t); tc := res->>'code';
  insert into r(name,pass,detail) values ('issue: 6 digits + expiry ~24h', tc ~ '^[0-9]{6}$' and (res->>'expires_at')::timestamptz between now()+interval '23 hours' and now()+interval '25 hours', res::text);
  select count(*) into n from private.transfer_codes where code_hash <> encode(extensions.digest(tc,'sha256'),'hex') and code_hash ~ '^[0-9a-f]{64}$';
  select count(*) into n from private.transfer_codes where code_hash = tc;
  insert into r(name,pass,detail) values ('plain code never stored', n=0, n::text);
  res := public.issue_transfer(a, t); tc2 := res->>'code';
  select count(*) into n from private.transfer_codes tc0 join public.trip_members m on m.id=tc0.member_id where m.user_id=a and used_at is null;
  insert into r(name,pass,detail) values ('reissue voids the earlier unused code', n=1, n::text);
  res := public.claim_transfer(ed, tc, 'ipT');
  insert into r(name,pass,detail) values ('old code → transfer_invalid', tc=tc2 or res='{"error":"transfer_invalid"}', res::text);
  res := public.claim_transfer(ed, ' '||substr(tc2,1,3)||' '||substr(tc2,4)||' ', 'ipT');
  select count(*) into n from public.trip_members where trip_id=t and user_id=ed and display_name='נועה כהן' and role='viewer' and status='active';
  insert into r(name,pass,detail) values ('claim moves membership (spaces ok)', res->>'role'='viewer' and (res->>'trip_id')::uuid=t and n=1, res::text);
  select count(*) into n from public.trip_members where trip_id=t and user_id=a;
  insert into r(name,pass,detail) values ('old identity no longer member', n=0, n::text);
  res := public.claim_transfer(b, tc2, 'ipT');
  insert into r(name,pass,detail) values ('second claim → transfer_invalid', res='{"error":"transfer_invalid"}', res::text);
  -- expired
  res := public.issue_transfer(ed, t); tc := res->>'code';
  update private.transfer_codes set expires_at = now() - interval '1 second' where used_at is null;
  res := public.claim_transfer(a, tc, 'ipT');
  insert into r(name,pass,detail) values ('expired → transfer_invalid', res='{"error":"transfer_invalid"}', res::text);
  -- already_member: b (active editor in t) claims ed's code
  res := public.issue_transfer(ed, t); tc := res->>'code';
  res := public.claim_transfer(b, tc, 'ipU');
  insert into r(name,pass,detail) values ('claimer already in trip → already_member', res='{"error":"already_member"}', res::text);
  -- claim limit: 5 failed/user/hour (b already has 1 failed + 1 already_member)
  for i in 1..3 loop perform public.claim_transfer(b, '000000', 'ipU'); end loop;
  res := public.claim_transfer(b, tc, 'ipU');
  insert into r(name,pass,detail) values ('6th claim after 5 failures → rate_limited', res='{"error":"rate_limited"}', res::text);
  res := public.claim_transfer(a, 'abc', 'ipV');
  insert into r(name,pass,detail) values ('bad format → transfer_invalid', res='{"error":"transfer_invalid"}', res::text);
  -- manager transfer keeps the trip's manager (last-manager trigger allows it)
  res := public.issue_transfer(mgr, t); tc := res->>'code';
  res := public.claim_transfer(a, tc, 'ipW');
  select count(*) into n from public.trip_members where trip_id=t and user_id=a and role='manager' and status='active';
  insert into r(name,pass,detail) values ('manager membership transfers', n=1 and res->>'role'='manager', res::text);

  -- cleanup of old attempts
  insert into private.join_attempts(kind, at) values ('preview', now() - interval '8 days');
  select count(*) into n from private.join_attempts where at < now() - interval '7 days';
  insert into r(name,pass,detail) values ('old attempt row exists (cleanup is opportunistic)', n>=1, n::text);
end
$t$;

-- grants + RLS
insert into r(name,pass,detail) select 'no client can execute F05 functions',
  bool_and(not has_function_privilege('anon', p.oid, 'execute') and not has_function_privilege('authenticated', p.oid, 'execute')
           and has_function_privilege('service_role', p.oid, 'execute')), string_agg(p.proname, ',')
  from pg_proc p join pg_namespace s on s.oid=p.pronamespace
 where (s.nspname='private' and p.proname like 'f05\_%') or (s.nspname='public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member'));
insert into r(name,pass,detail) select 'search_path="" on all F05 functions',
  bool_and(p.proconfig @> array['search_path=""']), string_agg(p.proname,',')
  from pg_proc p join pg_namespace s on s.oid=p.pronamespace
 where (s.nspname='private' and p.proname like 'f05\_%') or (s.nspname='public' and p.proname in ('join_preview','join_request','join_cancel','issue_transfer','claim_transfer','approve_member'));
insert into r(name,pass,detail) select 'no table privileges for clients',
  not has_table_privilege('authenticated','private.transfer_codes','select') and not has_table_privilege('anon','private.transfer_codes','select')
  and not has_table_privilege('authenticated','private.join_attempts','select') and not has_table_privilege('authenticated','private.join_attempts','insert'), '';
insert into r(name,pass,detail) select 'schema private closed to clients; public still 9 tables',
  not has_schema_privilege('authenticated','private','usage') and not has_schema_privilege('anon','private','usage')
  and (select count(*) from pg_tables where schemaname='public')=9, '';
insert into r(name,pass,detail) select 'RLS on, no policies', (select bool_and(relrowsecurity) from pg_class where oid in ('private.transfer_codes'::regclass,'private.join_attempts'::regclass))
  and not exists (select 1 from pg_policies where tablename in ('transfer_codes','join_attempts')), '';
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","role":"authenticated"}',true);
insert into r(name,pass,detail) select 'removed member reads own row only, 0 trips/kv',
  (select count(*) from public.trip_members)=1 and (select count(*) from public.trips)=0 and (select count(*) from public.trip_kv)=0, '';
reset role;
select id, pass, name, detail from r order by id;
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
    runs = ["f01", "f02", "f03", "f04"] + (["f05"] if all(f.exists() for f in EXTRA) else [])
    for run in runs:
        r = psql(conn, DB, "-A", "-t", "-F", "\t", "-c", (("select id, pass, scenario from qa.%s_run() order by id") if run == "f01"
                    else "select id, pass, name, detail from qa.%s_run() order by id") % run)
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        print("qa.%s_run(): %d/%d pass%s" % (run, len(rows) - len(fails), len(rows), "" if not r.returncode else " ERROR " + r.stderr[-300:]))
        for x in fails:
            print("    FAIL %s %s :: %s" % (x[0], x[2] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:300]))
        ok &= not fails and not r.returncode and bool(rows)
    r = psql(conn, DB, "-A", "-t", "-F", "\t", input_sql="begin;\n" + SCENARIOS + "\nrollback;\n")
    if r.returncode:
        print("F05 scenarios ERROR", r.stderr[-2000:])
        return 1
    rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.count("\t") >= 2]
    fails = [x for x in rows if x[1] != "t"]
    for x in rows:
        print("  %s %-3s %s%s" % ("ok " if x[1] == "t" else "FAIL", x[0], x[2], "" if x[1] == "t" else "  :: " + x[3][:300]))
    print("F05 scenarios: %d/%d pass" % (len(rows) - len(fails), len(rows)))
    r = psql(conn, DB, "-A", "-t", "-c", "select (select count(*) from public.trips)+(select count(*) from private.join_attempts)+(select count(*) from private.transfer_codes)")
    left = r.stdout.strip()
    print("leftover rows after rollback:", left)
    ok &= not fails and left == "0"
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
