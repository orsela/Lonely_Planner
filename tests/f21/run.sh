#!/usr/bin/env bash
# Lonely Planner F21 QA runner · version 1.0.0
# CHANGE 2026-10-30 F21-QA-07: new file (no previous version).
# usage: tests/f21/run.sh [--only browser|fn|int|db] [pytest args…]
#   browser  Playwright suite tests/f21/test_f21.py (≈8 min)
#   fn       function tests (request-trip / invite-manager F21 actions / create-trip prefill), stubs only
#   db       local PostgreSQL: 0001…0017 + qa.f01–f06/f21_run() + DB-xx scenarios (tests/f21/db_test.py)
#   int      functions wired to local PostgreSQL (tests/f21/integration_test.ts; builds DB pt_f21_int first)
# Offline: no Supabase, no network. PostgreSQL: `service postgresql start` (sudo -u postgres).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
NODE=${NODE:-node}
ONLY=""
[ "${1:-}" = "--only" ] && { ONLY=$2; shift 2; }
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"; done
fi
RC=0; declare -A RES
fnrun() { (cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import "$REPO/tests/f05/deno_shim.mjs" scripts/dev/deno_test_node.mjs "$1"); }
pg_up() { service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1; sudo -u postgres psql -Atc "select 1" >/dev/null 2>&1; }

if want fn; then
  fnrun tests/f21/function_test.ts >"$HERE/.last_run_fn.txt" 2>&1; rc=$?
  RES[fn]="$(tail -1 "$HERE/.last_run_fn.txt") (rc=$rc)"; [ $rc = 0 ] || RC=1
fi
if want db; then
  if pg_up; then (cd "$REPO" && $PY tests/f21/db_test.py) >"$HERE/.last_run_db.txt" 2>&1; rc=$?
    RES[db]="$(grep -E '^f21_db_test|^qa\.' "$HERE/.last_run_db.txt" | tr '\n' ' ') (rc=$rc)"; [ $rc = 0 ] || RC=1
  else RES[db]="SKIP (PostgreSQL not available)"; fi
fi
if want int; then
  if pg_up; then
    (cd "$REPO" && F21_QA_DB=pt_f21_int $PY tests/f21/db_test.py --setup-only && F21_QA_DB=pt_f21_int fnrun tests/f21/integration_test.ts) >"$HERE/.last_run_int.txt" 2>&1; rc=$?
    sudo -u postgres psql -qc "drop database if exists pt_f21_int" >/dev/null 2>&1
    RES[int]="$(tail -1 "$HERE/.last_run_int.txt") (rc=$rc)"; [ $rc = 0 ] || RC=1
  else RES[int]="SKIP (PostgreSQL not available)"; fi
fi
if want browser; then
  (cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" $PY -m pytest test_f21.py -q -rfEsxX --tb=line -p no:cacheprovider "$@") >"$HERE/.last_run_browser.txt" 2>&1; rc=$?
  RES[browser]="$(grep -E '[0-9]+ (passed|failed)' "$HERE/.last_run_browser.txt" | tail -1) (rc=$rc)"; [ $rc = 0 ] || RC=1
fi
echo "================ F21 QA summary ================"
for k in "${!RES[@]}"; do printf '%-8s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
