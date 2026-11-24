#!/usr/bin/env bash
# Lonely Planner TRIP-COUNTRY-A developer test runner · version 1.0.0
# CHANGE 2026-11-24 TC-A-T-02: new file. Node tests of app/js/tripcountry.js and the first/last day flight card in app/js/f24.js.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/tripcountry/tripcountry_test.mjs
