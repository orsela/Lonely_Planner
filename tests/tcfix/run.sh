#!/usr/bin/env bash
# Lonely Planner TC-BUG-01 developer test runner · version 1.0.0
# CHANGE 2026-11-24 TCFIX-T-02: new file. Node tests of app/js/tcfix.js and of the real SS / loadState / saveTrip source of app/index.html.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/tcfix/tcfix_test.mjs
