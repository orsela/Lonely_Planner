# CHANGE 2026-10-27 F21-DEVDB-01: new file (no previous version). Dev self-check, not the QA suite, never touches Supabase.
"""Apply 0001…0017 to a scratch LOCAL PostgreSQL database, run qa.f01–f06 (regression) and qa.f21_run(), then a few F21
checks a harness function cannot do (real role errors on a direct call, D12 atomicity when the insert fails, a second
session seeing nothing of a rolled-back approve).

usage:  sudo -u postgres python3 scripts/dev/f21_db_check.py ""        (argument = extra psql connection options)

Expected (on purpose) failures of older harnesses, reported as EXPECTED, not as failures:
  qa.f05_run() 100/101 — F05 C8 "removed → member_removed", replaced by F06 D2 (as in scripts/dev/f06_db_check.py);
  qa.f06_run() 910/911 — F06 pins the exact contents of schema `private` (only f05_/f06_ functions, only its 2 tables);
                         F21 adds private.f21_* and 3 tables on purpose (spec §2.1–2.3); covered now by qa.f21_run() 908.
"""
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f21_dev"
ORDER = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql",
         "0006_f02.sql", "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql",
         "0011_qa_f04_harness.sql", "0012_f05.sql", "0013_qa_f05_harness.sql", "0014_f06.sql", "0015_qa_f06_harness.sql",
         "0016_f21.sql", "0016_f21.sql", "0017_qa_f21_harness.sql", "0017_qa_f21_harness.sql"]
EXPECTED = {"f05": {"100", "101"}, "f06": {"910", "911"}}

# Each check prints one line "name<TAB>t|f<TAB>detail".
CHECKS = r"""
-- D12 atomicity: the new invite's insert fails (token_hash already used) → the revoke of the old invite is rolled back too
begin;
insert into auth.users(id, email) values ('21000000-0000-4000-8000-0000000000a1', 'admin@example.com');
insert into public.platform_admins(user_id) values ('21000000-0000-4000-8000-0000000000a1');
insert into public.manager_invites(id, email, token_hash, expires_at)
  values ('21000000-0000-4000-8000-0000000000b1', 'old@example.com', repeat('a', 64), now() + interval '3 days');
insert into private.trip_requests(id, lang, name, email, countries, travellers, status, verified_at)
  values ('21000000-0000-4000-8000-0000000000c1', 'he', 'A', 'old@example.com', '{PT}', 2, 'pending', now());
do $$ begin
  perform public.request_approve('21000000-0000-4000-8000-0000000000a1', '21000000-0000-4000-8000-0000000000c1', repeat('a', 64), 'x', 'אור');
  raise notice 'approve did not raise';
exception when unique_violation then null; end $$;
select 'D12 failed insert rolls back the revoke and keeps the request pending',
       ((select revoked_at is null from public.manager_invites where id = '21000000-0000-4000-8000-0000000000b1')
        and (select status = 'pending' from private.trip_requests where id = '21000000-0000-4000-8000-0000000000c1')
        and (select count(*) = 1 from public.manager_invites where email = 'old@example.com'))::text, '';
rollback;
"""

DIRECT = [
    ("authenticated cannot call request_start directly", "authenticated",
     "select public.request_start(gen_random_uuid(), '{}'::jsonb, repeat('a',64), null, repeat('a',64))"),
    ("anon cannot call request_verify directly", "anon", "select public.request_verify(gen_random_uuid(), repeat('a',64), null)"),
    ("authenticated cannot call request_approve directly", "authenticated",
     "select public.request_approve(gen_random_uuid(), gen_random_uuid(), repeat('a',64), null, null)"),
    ("authenticated cannot call find_invite_for_email", "authenticated", "select public.find_invite_for_email('a@b.co')"),
    ("anon cannot read private.trip_requests", "anon", "select count(*) from private.trip_requests"),
]


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
    for run in ["f01", "f02", "f03", "f04", "f05", "f06", "f21"]:
        cols = "id, pass, scenario" if run == "f01" else "id, pass, name, detail"
        r = psql(conn, DB, "-A", "-t", "-F", "\t", "-c", "select %s from qa.%s_run() order by id" % (cols, run))
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        expected = [x for x in fails if x[0] in EXPECTED.get(run, set())]
        real = [x for x in fails if x not in expected]
        print("qa.%s_run(): %d/%d pass%s%s" % (run, len(rows) - len(fails), len(rows),
              (" (+%d expected changes)" % len(expected)) if expected else "", "" if not r.returncode else " ERROR " + r.stderr[-300:]))
        for x in expected:
            print("    EXPECTED %s %s" % (x[0], x[2] if len(x) > 2 else ""))
        for x in real:
            print("    FAIL %s %s :: %s" % (x[0], x[2] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:300]))
        ok &= not real and not r.returncode and bool(rows)
    checks = []
    r = psql(conn, DB, "-A", "-t", "-F", "\t", input_sql=CHECKS)
    for ln in r.stdout.splitlines():
        parts = ln.rstrip("\n").split("\t")
        if len(parts) == 3:
            checks.append((parts[0], parts[1] == "true", parts[2]))
    if r.returncode or not checks:
        checks.append(("CHECKS script", False, r.stderr[-400:]))
    for name, role, sql in DIRECT:
        d = psql(conn, DB, "-A", "-t", input_sql="begin; set local role %s; %s; rollback;" % (role, sql))
        checks.append((name, bool(d.returncode) and "permission denied" in d.stderr, d.stderr.strip()[-160:]))
    for name, passed, detail in checks:
        print("  %s %s%s" % ("ok  " if passed else "FAIL", name, "" if passed else "  :: " + detail))
        ok &= passed
    r = psql(conn, DB, "-A", "-t", "-c", "select (select count(*) from private.trip_requests)+(select count(*) from private.mail_log)"
             "+(select count(*) from private.request_attempts)+(select count(*) from public.manager_invites)+(select count(*) from public.trips)")
    left = r.stdout.strip()
    print("leftover rows after the runs:", left)
    ok &= left == "0"
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
