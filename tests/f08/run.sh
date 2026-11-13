#!/usr/bin/env bash
# Lonely Planner F08 developer test runner · version 1.0.0
# CHANGE 2026-11-13 F08-A2-03: same runner; the test file now also covers conversation 2 (screen + range sheet builders, AC9).
# CHANGE 2026-11-13 F08-A1-03: new file (no previous version). Stage A conversation 1: Node tests of app/js/f08.js only
#   (AC1, AC2, AC3, AC4, AC11 helpers, AC12 helpers, AC15). The browser suite arrives with conversation 3.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO" && exec "${NODE:-node}" --test tests/f08/f08_test.mjs
