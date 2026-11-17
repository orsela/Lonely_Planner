#!/usr/bin/env bash
# Lonely Planner NOTES-RICH developer test runner · version 1.0.0
# CHANGE 2026-11-17 NOTES-RICH-T-02: new file. Node tests of app/js/richnotes.js; add "browser" to also run the 390px browser test.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/richnotes/richnotes_test.mjs || exit 1
if [ "${1:-}" = "browser" ]; then (cd tests/richnotes && REPO_DIR="$REPO" APP_DIR="$REPO/app" python3 -m pytest test_richnotes_browser.py -q -x --tb=short -p no:cacheprovider) 2>&1 | tail -30; fi
