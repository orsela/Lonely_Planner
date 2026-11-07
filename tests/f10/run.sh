#!/usr/bin/env bash
# Lonely Planner F10 QA runner · version 1.0.0
# CHANGE 2026-11-07 F10-QA-03: new file (no previous version).
# usage: tests/f10/run.sh [pytest args…]   — the F10 browser suite (tests/f10/test_f10.py, ≈5 min). Offline: no Supabase,
#   no network (open.er-api.com and the chat-assistant function are stubbed; alpha.8 is read from git 4ca777b).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"; done
fi
(cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" $PY -m pytest test_f10.py -q -rfEsxX --tb=short -p no:cacheprovider "$@") \
  >"$HERE/.last_run.txt" 2>&1
rc=$?
grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed)" "$HERE/.last_run.txt"
echo "F10 browser suite rc=$rc (log: $HERE/.last_run.txt)"
exit $rc
