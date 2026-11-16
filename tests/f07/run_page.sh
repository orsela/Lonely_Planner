#!/usr/bin/env bash
# Lonely Planner F07 page-side test runner · version 3.0.0-alpha.16
# CHANGE 2026-11-16 F07-QA-06: new file. Conversation 2: Node tests of app/js/f07.js, then the browser pass (tests/f07/test_f07_browser.py). tests/f07/run.sh is the server runner (conversation 1).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
node --test "$HERE/f07_test.mjs" 2>&1 | grep -E "^# (tests|pass|fail)|not ok|✖" ; RC=${PIPESTATUS[0]}
# CHANGE 2026-11-16 F07-QA-09: + conversation 3 — test_f07_app_browser.py runs in its own pytest process (it loads the F06 harness, the other file the F05 one; both are called `harness`).
[ "${1:-}" = "--no-browser" ] || (cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" python3 -m pytest test_f07_browser.py -q -x --tb=short -p no:cacheprovider 2>&1 | tail -30; REPO_DIR="$REPO" python3 -m pytest test_f07_app_browser.py -q -x --tb=short -p no:cacheprovider 2>&1 | tail -30)
exit $RC
