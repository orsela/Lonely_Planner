#!/usr/bin/env bash
# TC-BUG-01 browser test runner · version 3.0.0-alpha.18.4 (CHANGE 2026-11-24 TC-OFF-T-03: new file)
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
python3 -I "$REPO/tests/tripcountry/test_offline_browser.py" 2>&1 | tail -20
