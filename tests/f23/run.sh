#!/usr/bin/env bash
# Lonely Planner F23 developer test runner · version 1.0.0
# CHANGE 2026-11-13 F23-QA-04: new file (no previous version).
# usage: tests/f23/run.sh [--only db|int|f21]
#   db    local PostgreSQL: 0001…0017 + 0020_f23.sql + 0021 harness (applied twice: idempotent) → qa.f23_run(),
#         and qa.f01…f06 / f21_run() for regression (superseded rows listed below are reported, not failed)
#   int   request-trip wired to that database (tests/f23/integration_test.ts)
#   f21   the F21 function suites, pinned to REQUEST_MODE='manual' (criterion 11), + the function unit tests
# Offline: no Supabase, no network. PostgreSQL: `service postgresql start` (sudo -u postgres).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
NODE=${NODE:-node}
DB=${F23_QA_DB:-pt_f23_int}
ONLY=""
[ "${1:-}" = "--only" ] && { ONLY=$2; shift 2; }
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
fnrun() { (cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import "$REPO/tests/f05/deno_shim.mjs" scripts/dev/deno_test_node.mjs "$1"); }
q() { (cd /tmp && sudo -u postgres psql -X -q -At -v ON_ERROR_STOP=1 -d "$DB" "$@"); }
# rows that an earlier harness expects differently on purpose: f05 100/101 (F06 D2), f06 910/911 (F21 §2),
# f21 7/101/128 (F23 C4: mail_log kind 'invite' is allowed; row 7's insert now succeeds and adds one mail to 101/128)
SUPERSEDED="f05:100 f05:101 f06:910 f06:911 f21:7 f21:101 f21:128"
RC=0
service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1

build() {
  (cd "$REPO" && F21_QA_DB="$DB" $PY tests/f21/db_test.py --setup-only) >"$HERE/.last_build.txt" 2>&1 || { echo "build FAILED (see tests/f23/.last_build.txt)"; exit 1; }
  for f in 0020_f23.sql 0021_qa_f23_harness.sql 0020_f23.sql 0021_qa_f23_harness.sql; do
    cp "$REPO/supabase/migrations/$f" "/tmp/f23_$f" && chmod 644 "/tmp/f23_$f"
    q -f "/tmp/f23_$f" >/dev/null 2>"$HERE/.last_apply.txt" || { echo "apply $f FAILED"; cat "$HERE/.last_apply.txt"; exit 1; }
  done
}

if want db || want int; then build; fi
if want db; then
  n=$(q -c "select count(*) filter (where pass) || '/' || count(*) from qa.f23_run()")
  bad=$(q -c "select id || ' ' || name || ' :: ' || detail from qa.f23_run() where not pass order by id")
  echo "qa.f23_run  $n"; [ -z "$bad" ] || { echo "$bad"; RC=1; }
  for h in f01 f02 f03 f04 f05 f06 f21; do
    n=$(q -c "select count(*) filter (where pass) || '/' || count(*) from qa.${h}_run()")
    fails=$(q -c "select id from qa.${h}_run() where not pass order by id" | tr '\n' ' ')
    unexpected=""
    for id in $fails; do case " $SUPERSEDED " in *" $h:$id "*) ;; *) unexpected="$unexpected $id";; esac; done
    echo "qa.${h}_run  $n${fails:+  (not passing: $fails)}${unexpected:+  UNEXPECTED:$unexpected}"
    [ -z "$unexpected" ] || RC=1
  done
fi
if want int; then
  F23_QA_DB="$DB" fnrun tests/f23/integration_test.ts >"$HERE/.last_run_int.txt" 2>&1; rc=$?
  echo "int         $(tail -1 "$HERE/.last_run_int.txt") (rc=$rc)"; [ $rc = 0 ] || { grep -B1 -A6 "FAIL\|not ok\|Error" "$HERE/.last_run_int.txt" | head -60; RC=1; }
fi
if want db || want int; then (cd /tmp && sudo -u postgres psql -X -qc "drop database if exists $DB" >/dev/null 2>&1); fi
if want f21; then
  for t in supabase/functions/request-trip/test.ts supabase/functions/invite-manager/test.ts supabase/functions/invite-manager/test_f21.ts tests/f21/function_test.ts; do
    out=$(fnrun "$t" 2>&1); rc=$?
    echo "$(printf '%-52s' "$t") $(echo "$out" | tail -1) (rc=$rc)"; [ $rc = 0 ] || RC=1
  done
fi
exit $RC
