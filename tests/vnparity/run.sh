#!/usr/bin/env bash
# Vietnam parity runner · version 1.0.0 (CHANGE 2026-11-25 VNPAR-01: new file)
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
python3 -I "$REPO/tests/vnparity/test_vn_parity.py" 2>&1 | tail -20
