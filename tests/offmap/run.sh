#!/usr/bin/env bash
# Lonely Planner OFFMAP developer test runner · version 3.0.0-alpha.19
# CHANGE 2026-11-24 OFFMAP-T-02: new file (no previous version). Node tests of app/js/offmap.js (no browser, no network, no Protomaps key).
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/offmap/offmap_test.mjs
