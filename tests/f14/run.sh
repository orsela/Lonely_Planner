#!/usr/bin/env bash
# Lonely Planner F14 developer test runner · version 1.0.0
# CHANGE 2026-11-15 F14-QA-02: new file (no previous version).
# usage: tests/f14/run.sh [--only db|fn|app]    (fn and app are added in steps 2 and 3)
#   db   local PostgreSQL: 0001…0017 (tests/f21/db_test.py --setup-only) + 0022_f14.sql (applied twice: idempotent) → tests/f14/db_test.sql
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
DB=${F14_QA_DB:-pt_f14_db}; ONLY=""; RC=0
[ "${1:-}" = "--only" ] && { ONLY=$2; shift 2; }
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
q() { (cd /tmp && sudo -u postgres psql -X -q -At -F ' | ' -v ON_ERROR_STOP=1 -d "$DB" "$@"); }
service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1
if want db; then
  (cd "$REPO" && F21_QA_DB="$DB" python3 tests/f21/db_test.py --setup-only) >"$HERE/.last_build.txt" 2>&1 || { echo "build FAILED (tests/f14/.last_build.txt)"; exit 1; }
  for f in 0022_f14.sql 0022_f14.sql; do cp "$REPO/supabase/migrations/$f" "/tmp/f14_$f"; chmod 644 "/tmp/f14_$f"; q -f "/tmp/f14_$f" >/dev/null 2>"$HERE/.last_apply.txt" || { echo "apply $f FAILED"; cat "$HERE/.last_apply.txt"; exit 1; }; done
  cp "$HERE/db_test.sql" /tmp/f14_db_test.sql; chmod 644 /tmp/f14_db_test.sql
  out=$(q -f /tmp/f14_db_test.sql 2>&1 | grep -E ' \| (PASS|FAIL) \|' ); echo "$out" | grep -c PASS | sed 's/^/db  PASS: /'
  bad=$(echo "$out" | grep FAIL); [ -z "$bad" ] || { echo "$bad"; RC=1; }
  [ -n "$out" ] || { echo "db  produced no rows"; RC=1; }
  (cd /tmp && sudo -u postgres psql -X -qc "drop database if exists $DB" >/dev/null 2>&1)
fi
exit $RC
