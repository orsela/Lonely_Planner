"""Lonely Planner F06 QA · local DB runner for qa.f06_run() · version 1.0.0
CHANGE 2026-10-22 F06-QA-05: first version (no previous version).

Applies scripts/dev/supabase_local_shim.sql + 0001…0014 + 0015_qa_f06_harness.sql (twice: idempotent) to a scratch LOCAL
PostgreSQL database and runs qa.f01–f06_run(). Never touches Supabase or the network.

usage:  python3 tests/f06/db_check.py [--stub]        (needs `sudo -u postgres psql`; PG 16/17)
  --stub   use a signatures-only stand-in for 0014 (every call returns {"error":"stub"}) — checks that 0015 applies and that
           the catalog / refusal scenarios run; most behaviour scenarios then FAIL by design.
Exit 0 only when every qa.*_run() row passes and nothing is left behind.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f06_qa"
BEFORE = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql", "0006_f02.sql",
          "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql", "0011_qa_f04_harness.sql",
          "0012_f05.sql", "0013_qa_f05_harness.sql"]
STUB = """-- signatures only (docs/F06_spec.md §2); NOT the feature
create or replace function public.member_set_role(p_user uuid, p_member uuid, p_role text) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
create or replace function public.member_rename(p_user uuid, p_member uuid, p_name text) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
create or replace function public.member_remove(p_user uuid, p_member uuid) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
create or replace function public.member_leave(p_user uuid, p_trip uuid) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
create or replace function public.rotate_join_code(p_user uuid, p_trip uuid) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
create or replace function public.member_touch(p_user uuid, p_trip uuid) returns jsonb language sql security definer set search_path = '' as $$ select '{"error":"stub"}'::jsonb $$;
revoke all on function public.member_set_role(uuid,uuid,text), public.member_rename(uuid,uuid,text), public.member_remove(uuid,uuid),
  public.member_leave(uuid,uuid), public.rotate_join_code(uuid,uuid), public.member_touch(uuid,uuid) from public, anon, authenticated;
grant execute on function public.member_set_role(uuid,uuid,text), public.member_rename(uuid,uuid,text), public.member_remove(uuid,uuid),
  public.member_leave(uuid,uuid), public.rotate_join_code(uuid,uuid), public.member_touch(uuid,uuid) to service_role;
"""


def psql(*a):
    return subprocess.run(["sudo", "-u", "postgres", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"] + list(a),
                          capture_output=True, text=True, cwd="/tmp")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="f06qa_"))
    os.chmod(tmp, 0o755)
    files = [SHIM] + [MIG / n for n in BEFORE]
    if "--stub" in sys.argv:
        (tmp / "0014_stub.sql").write_text(STUB, encoding="utf-8")
        files.append(tmp / "0014_stub.sql")
    else:
        f14 = MIG / "0014_f06.sql"
        if not f14.exists():
            print("0014_f06.sql not found (merge the f06 branch, or run with --stub)")
            return 2
        files.append(f14)
    files += [MIG / "0015_qa_f06_harness.sql"] * 2
    for f in set(files):
        if f.parent != tmp:
            shutil.copy(f, tmp / f.name)
    psql("-c", "drop database if exists %s" % DB)
    r = psql("-c", "create database %s" % DB)
    if r.returncode:
        print(r.stderr)
        return 2
    ok = True
    for f in files:
        r = psql("-1", "-d", DB, "-f", str(tmp / f.name))
        print("apply %-30s %s" % (f.name, "OK" if r.returncode == 0 else "FAIL\n" + r.stderr[-2000:]))
        if r.returncode:
            return 1
    for run in ("f01", "f02", "f03", "f04", "f05", "f06"):
        cols = "id, pass, scenario, actual" if run == "f01" else "id, pass, name, detail"
        r = psql("-d", DB, "-A", "-t", "-F", "\t", "-c", "select %s from qa.%s_run() order by id" % (cols, run))
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        print("qa.%s_run(): %d/%d pass%s" % (run, len(rows) - len(fails), len(rows), "" if not r.returncode else " ERROR " + r.stderr[-300:]))
        for x in fails:
            print("    FAIL %s %s :: %s" % (x[0], x[2][:120] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:300]))
        ok &= not fails and not r.returncode and bool(rows)
    r = psql("-d", DB, "-A", "-t", "-c", "select (select count(*) from public.trips)+(select count(*) from private.join_attempts)"
             "+(select count(*) from private.transfer_codes)+(select count(*) from auth.users)")
    left = r.stdout.strip()
    print("leftover rows after the runs:", left)
    ok &= left == "0"
    shutil.rmtree(tmp, ignore_errors=True)
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
