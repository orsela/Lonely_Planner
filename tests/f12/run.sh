#!/usr/bin/env bash
# Lonely Planner F12 developer test runner · version 3.0.0-alpha.18
# CHANGE 2026-11-24 F12-QA-03: new file (no previous version). Conversation 1 (server): the vault-delete unit tests + the local DB
#   runner tests/f12/db_check.py (0001…0024, qa.f01–f07 + f12 + f21 + f23). No browser tests yet (they arrive with conversations 2–3).
# usage: tests/f12/run.sh [--only fn|db]     env: NODE, PYTHON.   `service postgresql start` first for the db part.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
NODE=${NODE:-node}; PY=${PYTHON:-python3}; ONLY=""; [ "${1:-}" = "--only" ] && ONLY=${2:-}
RC=0
if [ -z "$ONLY" ] || [ "$ONLY" = fn ]; then
  out=$(cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs supabase/functions/vault-delete/test.ts 2>&1)
  echo "vault-delete/test.ts: $(echo "$out" | grep -Eo '[0-9]+/[0-9]+ pass' | tail -1)"; echo "$out" | grep -E "^  FAIL" && RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = db ]; then
  (service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1) || true
  $PY "$HERE/db_check.py" || RC=1
fi
exit $RC
