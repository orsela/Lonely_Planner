#!/usr/bin/env bash
# Lonely Planner LAUNCH-QA runner · version 1.0.0
# CHANGE 2026-11-17 LAUNCH-QA-02: new file. Browser pass over links / points of interest / booking links at 390px.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$REPO/tests/launch_qa" || exit 1
export PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1 REPO_DIR="$REPO" APP_DIR="$REPO/app" JOIN_DIR="$REPO/join" SCRIPTS_DIR="$REPO/scripts"
python3 -m pytest test_launch_qa.py -q -x --tb=short -p no:cacheprovider 2>&1 | tail -30
