#!/usr/bin/env bash
# Lonely Planner F24 developer test runner · version 1.0.0
# CHANGE 2026-11-14 F24-A1-03: new file (no previous version). Conversation 1: Node tests of app/js/f24.js + app/airports.json only.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO" && exec "${NODE:-node}" --test tests/f24/f24_test.mjs
