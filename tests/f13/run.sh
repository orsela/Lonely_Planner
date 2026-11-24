#!/usr/bin/env bash
# Lonely Planner F13 developer test runner · version 3.0.0-alpha.18.8
# CHANGE 2026-11-24 F13-QA-03: new file (no previous version). Stage 0: Node tests of app/js/f13.js + the coverage report; add "browser" to also run the 390px browser test.
# CHANGE 2026-11-24 F13-QA-07: + stage 1 — the dictionary test always runs; "join" / "invite" / "all" run the 390px browser tests of /join/ and /invite/ (each in its own pytest process: they load different harnesses called `harness`).
# CHANGE 2026-11-24 F13-QA-10: + stage 3 — f13_stage3_test.mjs (css freshness + mirror rules) always runs; "stage3" / "browser" / "all" run the app-page browser test.
# CHANGE 2026-11-24 F13-QA-12: + "wizard" (stage 2: test_f13_wizard.py, F04-HOME harness) — also part of "all".
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO" || exit 1
"${NODE:-node}" --test tests/f13/f13_test.mjs || exit 1
"${NODE:-node}" tests/f13/coverage.mjs | tail -3
if [ "${1:-}" = "browser" ]; then (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_browser.py -q -x --tb=short -p no:cacheprovider) 2>&1 | tail -30; fi
"${NODE:-node}" --test tests/f13/f13_stage3_test.mjs 2>&1 | grep -E "^# (tests|pass|fail)|not ok"
"${NODE:-node}" --test tests/f13/f13_stage1_test.mjs 2>&1 | grep -E "^# (tests|pass|fail)|not ok"
case "${1:-}" in join|all) (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_join.py -q --tb=short -p no:cacheprovider) 2>&1 | tail -20;; esac
case "${1:-}" in invite|all) (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_invite.py -q --tb=short -p no:cacheprovider) 2>&1 | tail -20;; esac
case "${1:-}" in stage3|all) (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_browser.py -q --tb=short -p no:cacheprovider) 2>&1 | tail -20;; esac
case "${1:-}" in wizard|all) (cd tests/f13 && REPO_DIR="$REPO" python3 -m pytest test_f13_wizard.py -q --tb=short -p no:cacheprovider) 2>&1 | tail -20;; esac
