#!/usr/bin/env bash
# Lonely Planner F22a QA runner · version 1.0.0
# CHANGE 2026-11-07 F22A-QA-03: new file (no previous version).
# usage: tests/f22a/run.sh [pytest args…]   — the F22a browser suite (tests/f22a/test_f22a.py). Offline: no Supabase, no
#   Google (the OAuth round trip is simulated by the patched fake supabase-js; alpha.10 is read from git 76d2495).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"; done
fi
export PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1
(cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" $PY -m pytest test_f22a.py -q -rfEsxX --tb=short -p no:cacheprovider "$@") \
  >"$HERE/.last_run.txt" 2>&1
rc=$?
grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed)" "$HERE/.last_run.txt"
echo "F22a browser suite rc=$rc (log: $HERE/.last_run.txt)"
exit $rc
