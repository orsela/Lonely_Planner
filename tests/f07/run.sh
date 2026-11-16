#!/usr/bin/env bash
# Lonely Planner F07 developer test runner · version 3.0.0-alpha.16
# CHANGE 2026-11-16 F07-QA-04: new file (no previous version). Conversation 1 (server): the three Edge Function unit-test files
#   (join-trip, approve-member, manage-members) + the F05 / F06 QA function tests whose version pins moved + the local DB runner
#   tests/f07/db_check.py (0001…0022, qa.f01–f07 + f21 + f23). No browser tests yet (they arrive with conversations 2–3).
# usage: tests/f07/run.sh [--only fn|db]     env: NODE, PYTHON.   `service postgresql start` first for the db part.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
NODE=${NODE:-node}; PY=${PYTHON:-python3}; ONLY=""; [ "${1:-}" = "--only" ] && ONLY=${2:-}
RC=0
if [ -z "$ONLY" ] || [ "$ONLY" = fn ]; then
  for t in supabase/functions/join-trip/test.ts supabase/functions/approve-member/test.ts supabase/functions/manage-members/test.ts \
           tests/f05/function_test.ts tests/f06/function_test.ts; do
    out=$(cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs "$t" 2>&1)
    echo "$t: $(echo "$out" | grep -Eo '[0-9]+/[0-9]+ pass' | tail -1)"; echo "$out" | grep -E "^  FAIL"
    # known: F05-QA-D1 (approve-member sends no X-Function-Version header) is the only expected failure
    echo "$out" | grep -E "^  FAIL" | grep -v "F5-FN-02b" && RC=1
  done
fi
if [ -z "$ONLY" ] || [ "$ONLY" = db ]; then
  (service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1) || true
  $PY "$HERE/db_check.py" || RC=1
fi
exit $RC
