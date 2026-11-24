#!/usr/bin/env bash
# Lonely Planner F13 developer test runner · version 3.0.0-alpha.17.2
# CHANGE 2026-11-24 F13-QA-03: new file (no previous version). Stage 0: Node tests of app/js/f13.js + the coverage report; add "browser" to also run the 390px browser test.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/f13/f13_test.mjs || exit 1
"${NODE:-node}" tests/f13/coverage.mjs | tail -3
if [ "${1:-}" = "browser" ]; then (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_browser.py -q -x --tb=short -p no:cacheprovider) 2>&1 | tail -30; fi
