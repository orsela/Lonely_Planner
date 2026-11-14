#!/usr/bin/env bash
# Lonely Planner F08 browser test runner · version 1.0.0
# CHANGE 2026-11-14 F08-A3-04: new file. Runs tests/f08/test_f08_browser.py (real app, fake backend, no network).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
(cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" python3 -m pytest test_f08_browser.py -q -x --tb=short -p no:cacheprovider "$@") 2>&1 | tail -30
