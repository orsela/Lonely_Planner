"""Lonely Planner F07 QA · local DB runner for qa.f07_run() · version 3.0.0-alpha.16
CHANGE 2026-11-16 F07-QA-03: first version (no previous version).

Applies scripts/dev/supabase_local_shim.sql + 0001…0022 (in file order, 0018/0019 = F07) to a scratch LOCAL PostgreSQL
database, adds a minimal auth.sessions table (the shim has none; Supabase has one) and runs qa.f01–f07 + f21 + f23 harnesses.
Never touches Supabase or the network. usage: python3 tests/f07/db_check.py   (needs `sudo -u postgres psql`, `service postgresql start`)

Exit 0 only when every qa.f07_run() row passes and every OTHER harness row either passes or is listed in EXPECTED below
(rows that pin the pre-F07 shape on purpose; F07 changes it). Rows listed under OLD_FAILURES fail without F07 too.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = "pt_f07_qa"
EXPECTED = {  # superseded by F07 on purpose
    ("f05", 2): "F07 D2: the preview now returns people[] (names of active persons)",
    ("f06", 900): "F07: member_touch has 5 arguments (p_session, p_label, p_via)",
    ("f06", 901): "F07: member_touch has 5 arguments",
    ("f06", 910): "F07: new private helpers f07_*",
    ("f06", 911): "F07: private.member_sessions",
    ("f21", 908): "F07 (+F14): private tables list",
}
OLD_FAILURES = {  # fail on main without F07 as well
    ("f05", 100): "F06 D2 (a removed identity may ask again)",
    ("f05", 101): "F06 D2",
    ("f21", 7): "F23",
    ("f21", 101): "F23",
    ("f21", 128): "F23",
}
RUNS = ("f01", "f02", "f03", "f04", "f05", "f06", "f07", "f21", "f23")


def psql(*a):
    return subprocess.run(["sudo", "-u", "postgres", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"] + list(a),
                          capture_output=True, text=True, cwd="/tmp")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="f07qa_"))
    tmp.chmod(0o755)
    files = [SHIM] + sorted(MIG.glob("00*.sql"))
    psql("-c", "drop database if exists %s" % DB)
    r = psql("-c", "create database %s" % DB)
    if r.returncode:
        print(r.stderr)
        return 2
    for f in files:
        shutil.copy(f, tmp / f.name)
        (tmp / f.name).chmod(0o644)
        r = psql("-1", "-d", DB, "-f", str(tmp / f.name))
        if r.returncode:
            print("apply %-32s FAIL\n%s" % (f.name, r.stderr[-1500:]))
            return 1
        if f.name == "0017_qa_f21_harness.sql":   # auth.sessions for the F07 disconnect scenario (Supabase has it)
            psql("-d", DB, "-c", "create table if not exists auth.sessions (id uuid primary key, user_id uuid references auth.users(id) "
                 "on delete cascade, created_at timestamptz, updated_at timestamptz)")
    # 0018 + 0019 twice: idempotent
    for n in ("0018_f07.sql", "0019_qa_f07_harness.sql"):
        r = psql("-1", "-d", DB, "-f", str(tmp / n))
        if r.returncode:
            print("re-apply %s FAIL\n%s" % (n, r.stderr[-1500:]))
            return 1
    print("applied %d files (+0018/0019 a second time): OK" % len(files))
    bad = 0
    for run in RUNS:
        cols = "id, pass, scenario, actual" if run == "f01" else "id, pass, name, detail"
        r = psql("-d", DB, "-A", "-t", "-F", "\t", "-c", "select %s from qa.%s_run() order by id" % (cols, run))
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        new = [x for x in fails if (run, int(x[0])) not in EXPECTED and (run, int(x[0])) not in OLD_FAILURES]
        print("qa.%s_run(): %d/%d pass, %d known/superseded, %d NEW failures" % (run, len(rows) - len(fails), len(rows),
                                                                               len(fails) - len(new), len(new)))
        for x in new:
            print("    FAIL %s %s :: %s" % (x[0], x[2][:100], (x[3] if len(x) > 3 else "")[:300]))
        bad += len(new) + (0 if rows else 1)
    r = psql("-d", DB, "-A", "-t", "-c", "select (select count(*) from auth.users) + (select count(*) from public.trips) "
             "+ (select count(*) from private.member_sessions)")
    left = r.stdout.strip()
    print("leftovers after all runs (users+trips+sessions): %s" % left)
    if left != "0":
        bad += 1
    psql("-c", "drop database if exists %s" % DB)
    print("ALL OK" if not bad else "FAILURES: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
