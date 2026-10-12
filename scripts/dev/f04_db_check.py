# CHANGE 2026-10-12 F04-DEVDB-02: new file (no previous version). Dev self-check, not the QA suite, never touches Supabase.
# CHANGE 2026-10-12 F04-DEVDB-03: what changed from the F04-DEVDB-02 version: also applies 0011_qa_f04_harness.sql
#   (twice, idempotency) and runs qa.f04_run() next to qa.f01/f02/f03; the run fails on any failing row of any harness.
"""Apply 0001…0011 to a scratch LOCAL PostgreSQL database, run qa.f01/f02/f03/f04, then exercise the F04 functions.

usage:  python3 scripts/dev/f04_db_check.py "<psql connection args>"
        e.g. sudo -u postgres python3 scripts/dev/f04_db_check.py ""

Scenarios (all inside one transaction that is rolled back at the end): happy path (rows in every table, day objects,
dates across a month boundary), idempotent retry, used-by-another-user, expired, revoked, replaced, cap 10
(too_many_currencies) and one invalid_payload per field, leap day 2028-02-28 → 2028-03-01 = 3 days, join-code alphabet,
find_invite_for_email, grants (anon/authenticated cannot execute), RLS read of the new trip by a non-member.
"""
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f04_dev"
ORDER = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql",
         "0006_f02.sql", "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql",
         "0010_f04.sql", "0011_qa_f04_harness.sql", "0011_qa_f04_harness.sql"]

SCENARIOS = r"""
create temp table r(id serial, name text, pass boolean, detail text);
grant all on r to public; grant all on sequence r_id_seq to public;
do $t$
declare
  u1 uuid := '11111111-1111-4111-8111-111111111111';
  u2 uuid := '22222222-2222-4222-8222-222222222222';
  u3 uuid := '33333333-3333-4333-8333-333333333333';
  pay jsonb := '{"name":"  יפן 2027 ","display_name":"דנה","start_date":"2027-04-03","end_date":"2027-04-20",
                 "home_currency":"ILS","default_lang":"he","default_role":"viewer","countries":["JP","KR"],
                 "currencies":[{"code":"JPY","kind":"destination"},{"code":"KRW","kind":"destination"}],
                 "center":{"lat":35.6762,"lng":139.6503}}';
  res jsonb; res2 jsonb; t uuid; n int; v text; days jsonb; msg text; det text; f text; bad jsonb;
  procedure_ok boolean;
begin
  insert into auth.users(id,email) values (u1,'dana@example.com'),(u2,'other@example.com'),(u3,'x@example.com');
  insert into public.manager_invites(email, token_hash, draft_name, inviter_name, expires_at)
    values ('dana@example.com','h1','יפן 2027','אור', now() + interval '7 days');

  -- find_invite_for_email
  res := public.find_invite_for_email('  DANA@example.com ');
  insert into r(name,pass,detail) values ('find: found, normalized email', (res->>'found')::boolean and res->>'draft_name'='יפן 2027' and res ? 'invite_id' and not (res ? 'email'), res::text);
  res := public.find_invite_for_email('nobody@example.com');
  insert into r(name,pass,detail) values ('find: not found', res = '{"found":false}'::jsonb, res::text);

  -- happy path
  res := public.create_trip_from_invite(u1, ' Dana@Example.com ', pay);
  t := (res->>'trip_id')::uuid;
  insert into r(name,pass,detail) values ('create: created=true + 8-char code', (res->>'created')::boolean and res->>'join_code' ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$', res::text);
  select count(*) into n from public.trips where id=t and name='יפן 2027' and start_date='2027-04-03' and end_date='2027-04-20' and home_currency='ILS' and default_lang='he' and default_role='viewer' and status='active' and created_by=u1;
  insert into r(name,pass,detail) values ('trips row', n=1, n::text);
  select string_agg(country_code||':'||sort, ',' order by sort) into v from public.trip_countries where trip_id=t;
  insert into r(name,pass,detail) values ('trip_countries in order', v='JP:0,KR:1', v);
  select string_agg(currency_code||':'||kind||':'||sort, ',' order by sort) into v from public.trip_currencies where trip_id=t;
  insert into r(name,pass,detail) values ('trip_currencies bases + destinations', v='ILS:base:0,USD:base:1,EUR:base:2,JPY:destination:3,KRW:destination:4', v);
  select count(*) into n from public.trip_members where trip_id=t and user_id=u1 and display_name='דנה' and role='manager' and status='active' and approved_at is not null;
  insert into r(name,pass,detail) values ('manager membership', n=1, n::text);
  select value::jsonb into days from public.trip_kv where trip_id=t and key='trip';
  insert into r(name,pass,detail) values ('18 empty days', jsonb_array_length(days)=18 and days->0->>'date'='03/04/2027' and days->17->>'date'='20/04/2027' and (days->17->>'day')::int=18, (days->0)::text);
  insert into r(name,pass,detail) values ('day object shape', days->0 = '{"day":1,"date":"03/04/2027","region":"","title":"","activities":"","hotel":"","cost":0,"notes":"","lat":35.6762,"lng":139.6503,"zoom":5,"waypoints":[],"country":"JP"}'::jsonb, (days->0)::text);
  select count(*) into n from public.trip_kv where trip_id=t and updated_by=u1;
  insert into r(name,pass,detail) values ('trip_kv updated_by (trip + tripname, F04-DB-02)', n=2, n::text);
  select count(*) into n from public.manager_invites where email='dana@example.com' and used_at is not null and trip_id=t;
  insert into r(name,pass,detail) values ('invite used + trip_id', n=1, n::text);

  -- idempotent retry
  res2 := public.create_trip_from_invite(u1, 'dana@example.com', pay);
  insert into r(name,pass,detail) values ('retry: same trip, created=false', res2->>'trip_id'=res->>'trip_id' and res2->>'join_code'=res->>'join_code' and not (res2->>'created')::boolean, res2::text);
  select count(*) into n from public.trips;
  insert into r(name,pass,detail) values ('retry: one trip only', n=1, n::text);
  res2 := public.find_invite_for_email('dana@example.com');
  insert into r(name,pass,detail) values ('find after use: not found', res2='{"found":false}'::jsonb, res2::text);

  -- used by another user
  begin perform public.create_trip_from_invite(u2, 'dana@example.com', pay); msg:='none';
  exception when others then get stacked diagnostics msg = message_text; end;
  insert into r(name,pass,detail) values ('used by another user → invite_invalid', msg='invite_invalid', msg);

  -- no invite at all
  begin perform public.create_trip_from_invite(u2, 'other@example.com', pay); msg:='none';
  exception when others then get stacked diagnostics msg = message_text; end;
  insert into r(name,pass,detail) values ('no invite → invite_invalid', msg='invite_invalid', msg);

  -- expired
  insert into public.manager_invites(email, token_hash, expires_at) values ('other@example.com','h2', now() - interval '1 minute');
  begin perform public.create_trip_from_invite(u2, 'other@example.com', pay); msg:='none';
  exception when others then get stacked diagnostics msg = message_text; end;
  insert into r(name,pass,detail) values ('expired → invite_invalid', msg='invite_invalid', msg);
  -- revoked
  update public.manager_invites set revoked_at=now() where token_hash='h2';
  insert into public.manager_invites(email, token_hash, expires_at, revoked_at) values ('x@example.com','h3', now() + interval '1 day', now());
  begin perform public.create_trip_from_invite(u3, 'x@example.com', pay); msg:='none';
  exception when others then get stacked diagnostics msg = message_text; end;
  insert into r(name,pass,detail) values ('revoked → invite_invalid', msg='invite_invalid', msg);
  select count(*) into n from public.trips;
  insert into r(name,pass,detail) values ('refusals wrote nothing', n=1, n::text);

  -- payload validation (fresh open invite for u2)
  insert into public.manager_invites(email, token_hash, expires_at) values ('other@example.com','h4', now() + interval '7 days');
  for f, bad in select * from (values
      ('name', jsonb_set(pay,'{name}','"  "')),
      ('name', jsonb_set(pay,'{name}', to_jsonb(repeat('a',81)))),
      ('display_name', pay - 'display_name'),
      ('display_name', jsonb_set(pay,'{display_name}', to_jsonb(repeat('a',41)))),
      ('start_date', jsonb_set(pay,'{start_date}','"2027-02-30"')),
      ('start_date', jsonb_set(pay,'{start_date}','"03/04/2027"')),
      ('end_date', jsonb_set(pay,'{end_date}','"2027-04-02"')),
      ('end_date', jsonb_set(pay,'{end_date}','"2027-08-01"')),
      ('home_currency', jsonb_set(pay,'{home_currency}','"JPY"')),
      ('default_lang', jsonb_set(pay,'{default_lang}','"en"')),
      ('default_role', jsonb_set(pay,'{default_role}','"manager"')),
      ('countries', jsonb_set(pay,'{countries}','[]')),
      ('countries', jsonb_set(pay,'{countries}','["JP","JP"]')),
      ('countries', jsonb_set(pay,'{countries}','["jp"]')),
      ('countries', jsonb_set(pay,'{countries}','["AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN","AO","AP"]')),
      ('currencies', jsonb_set(pay,'{currencies}','[{"code":"USD","kind":"destination"}]')),
      ('currencies', jsonb_set(pay,'{currencies}','[{"code":"JPY","kind":"base"}]')),
      ('currencies', jsonb_set(pay,'{currencies}','[{"code":"JPY","kind":"added"},{"code":"JPY","kind":"destination"}]')),
      ('center', jsonb_set(pay,'{center}','{"lat":91,"lng":0}')),
      ('center', pay - 'center')) as x(f,b)
  loop
    begin perform public.create_trip_from_invite(u2, 'other@example.com', bad); msg:='none'; det:='';
    exception when others then get stacked diagnostics msg = message_text, det = pg_exception_detail; end;
    insert into r(name,pass,detail) values ('invalid_payload '||f, msg='invalid_payload' and det=f, msg||'/'||coalesce(det,''));
  end loop;
  -- cap 10: 8 currencies + 3 bases = 11
  bad := jsonb_set(pay,'{currencies}','[{"code":"JPY","kind":"destination"},{"code":"KRW","kind":"destination"},{"code":"THB","kind":"added"},{"code":"GBP","kind":"added"},{"code":"CHF","kind":"added"},{"code":"CZK","kind":"added"},{"code":"HUF","kind":"added"},{"code":"PLN","kind":"added"}]');
  begin perform public.create_trip_from_invite(u2, 'other@example.com', bad); msg:='none';
  exception when others then get stacked diagnostics msg = message_text; end;
  insert into r(name,pass,detail) values ('11 currencies → too_many_currencies', msg='too_many_currencies', msg);
  select count(*) into n from public.trips;
  insert into r(name,pass,detail) values ('validation refusals wrote nothing', n=1, n::text);
  -- exactly 10 is fine + leap day range
  bad := jsonb_set(jsonb_set(jsonb_set(bad,'{currencies}', (bad->'currencies') - 7),'{start_date}','"2028-02-28"'),'{end_date}','"2028-03-01"');
  bad := jsonb_set(bad, '{home_currency}', '"EUR"');
  res := public.create_trip_from_invite(u2, 'other@example.com', bad);
  t := (res->>'trip_id')::uuid;
  select value::jsonb into days from public.trip_kv where trip_id=t and key='trip';
  insert into r(name,pass,detail) values ('leap: 2028-02-28→03-01 = 3 days', jsonb_array_length(days)=3 and days->0->>'date'='28/02/2028' and days->1->>'date'='29/02/2028' and days->2->>'date'='01/03/2028', days::text);
  select count(*) into n from public.trip_currencies where trip_id=t;
  select string_agg(currency_code||':'||sort, ',' order by sort) into v from public.trip_currencies where trip_id=t and kind='base';
  insert into r(name,pass,detail) values ('10 currencies ok, home EUR sort 0', n=10 and v='EUR:0,ILS:1,USD:2', n||' '||v);

  -- join code alphabet over many draws
  select count(*) into n from public.trip_join_codes where code !~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$';
  insert into r(name,pass,detail) values ('join codes in alphabet', n=0, n::text);
end
$t$;

-- grants + RLS (as roles)
insert into r(name,pass,detail) select 'anon cannot execute create', not has_function_privilege('anon','public.create_trip_from_invite(uuid,text,jsonb)','execute'), '';
insert into r(name,pass,detail) select 'authenticated cannot execute create', not has_function_privilege('authenticated','public.create_trip_from_invite(uuid,text,jsonb)','execute'), '';
insert into r(name,pass,detail) select 'authenticated cannot execute find', not has_function_privilege('authenticated','public.find_invite_for_email(text)','execute') and not has_function_privilege('anon','public.find_invite_for_email(text)','execute'), '';
insert into r(name,pass,detail) select 'service_role can execute both', has_function_privilege('service_role','public.create_trip_from_invite(uuid,text,jsonb)','execute') and has_function_privilege('service_role','public.find_invite_for_email(text)','execute'), '';
insert into r(name,pass,detail) select 'security definer + search_path=""', bool_and(p.prosecdef and p.proconfig @> array['search_path=""']), string_agg(p.proname||coalesce(array_to_string(p.proconfig,';'),''),' ') from pg_proc p where p.proname in ('create_trip_from_invite','find_invite_for_email');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"33333333-3333-4333-8333-333333333333","role":"authenticated"}',true);
insert into r(name,pass,detail) select 'non-member reads 0 trips / kv / codes', (select count(*) from public.trips)=0 and (select count(*) from public.trip_kv)=0 and (select count(*) from public.trip_join_codes)=0, '';
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
insert into r(name,pass,detail) select 'manager reads own trip + code', (select count(*) from public.trips)=1 and (select count(*) from public.trip_join_codes)=1, '';
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
    for f in [SHIM] + [MIG / n for n in ORDER]:
        r = psql(conn, DB, "-1", "-f", str(f))
        print("apply %-28s %s" % (f.name, "OK" if r.returncode == 0 else "FAIL\n" + r.stderr[-1500:]))
        ok &= r.returncode == 0
    if not ok:
        return 1
    for run in ("f01", "f02", "f03", "f04"):
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
        print("F04 scenarios ERROR", r.stderr[-2000:])
        return 1
    rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.count("\t") >= 2]
    fails = [x for x in rows if x[1] != "t"]
    for x in rows:
        print("  %s %-3s %s%s" % ("ok " if x[1] == "t" else "FAIL", x[0], x[2], "" if x[1] == "t" else "  :: " + x[3][:300]))
    print("F04 scenarios: %d/%d pass" % (len(rows) - len(fails), len(rows)))
    r = psql(conn, DB, "-A", "-t", "-c", "select (select count(*) from public.trips)+(select count(*) from public.manager_invites)+(select count(*) from auth.users)")
    print("leftover rows after rollback:", r.stdout.strip())
    ok &= not fails and r.stdout.strip() == "0"
    print("ALL OK" if ok else "PROBLEMS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
