#!/usr/bin/env bash
# Lonely Planner F14 developer test runner · version 1.2.0
# CHANGE 2026-11-15 F14-QA-04: what changed from 1.1.0: + `app` (step 3: Node tests of app/js/f14.js, then ONE browser pass at 390 px in the real app with a stubbed chat endpoint).
# CHANGE 2026-11-15 F14-QA-03: what changed from 1.0.0: + `fn` (step 2: Node run of supabase/functions/chat-assistant/test.ts, no Deno binary needed).
# CHANGE 2026-11-15 F14-QA-02: new file (no previous version).
# usage: tests/f14/run.sh [--only db|fn|app]
#   app  tests/f14/f14_test.mjs (Node, no browser) + tests/f14/test_f14_browser.py (Chromium, fake backend, no network)
#   fn   chat-assistant unit tests (stubbed auth, rpc and Anthropic): validators, history, cap, 401/403/429/503, refunds, logs
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
if want fn; then
  NODE=${NODE:-node}
  out=$(cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import "$REPO/tests/f05/deno_shim.mjs" scripts/dev/deno_test_node.mjs supabase/functions/chat-assistant/test.ts 2>&1)
  echo "$out" | tail -1 | sed 's/^/fn  /'
  bad=$(echo "$out" | grep -E '^\s+FAIL'); [ -z "$bad" ] || { echo "$bad"; RC=1; }
  echo "$out" | tail -1 | grep -qE '^([0-9]+)/\1 pass' || RC=1
fi
if want app; then
  NODE=${NODE:-node}
  out=$(cd "$REPO" && "$NODE" --test tests/f14/f14_test.mjs 2>&1)
  echo "$out" | grep -E '^# (pass|fail)' | tr '\n' ' ' | sed 's/^/app node: /'; echo
  echo "$out" | grep -E '^not ok' ; echo "$out" | grep -qE '^# fail 0' || RC=1
  out=$(cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" python3 -m pytest test_f14_browser.py -q -x --tb=short -p no:cacheprovider 2>&1 | tail -30)
  echo "$out" | tail -3 | sed 's/^/app browser: /'
  echo "$out" | grep -qE '[0-9]+ passed' && ! echo "$out" | grep -qE 'failed|error' || { echo "$out"; RC=1; }
fi
exit $RC
