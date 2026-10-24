#!/usr/bin/env bash
# Lonely Planner F06 QA runner · version 1.0.0
# CHANGE 2026-10-22 F06-QA-06: first version (no previous version); built on tests/f05/run.sh 1.0.0. What is new: (1) the F06
#   browser suite (tests/f06/test_f06.py on tests/f06/harness.py); (2) the manage-members function tests
#   (tests/f06/function_test.ts, Deno-style on Node through scripts/dev/deno_test_node.mjs + tests/f05/deno_shim.mjs);
#   (3) the DB harness on a LOCAL PostgreSQL (tests/f06/db_check.py: 0001…0014 + 0015 twice, qa.f01–f06_run());
#   (4) criterion 1 "flag off = alpha.6": a copy of the repo with MEMBERS_FEATURE='off' in app/ and join/ on which the F05
#   runner (F05 browser suite + F20/F04/F03/F02 regression + dev function tests) is run unchanged.
#
# usage: ./run.sh [--only f06|fn|db|off] [extra pytest args for the F06 browser suite]
# env:   PYTHON, NODE, BASELINE_DIR (for the F02 suite, see tests/f05/run.sh), PGCONN unused (sudo -u postgres psql)
#
# Expected failures in the 'off' run (version pins only, spec §4 criterion 1 "except version pins"): every
#   *_static[app_version|pt_version|title_version] case of F02/F03/F04/F05/F20 (they pin alpha.6 or older; F06 ships
#   alpha.7). tests/f05/run.sh already deselects the older suites' pins; the F05 suite's own pins
#   test_s01_static[app_version|pt_version] and its change_comments check (F05 tags) are listed in the summary as expected.
# Nothing here talks to Supabase or the network (the F02 baseline clone in tests/f05/run.sh is the only exception, and only
# when BASELINE_DIR is missing).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
NODE=${NODE:-node}
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2;;
    *) break;;
  esac
done
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
WORK=$(mktemp -d "${TMPDIR:-/tmp}/f06qa.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

$PY -c "import pytest" 2>/dev/null || $PY -m pip install pytest --break-system-packages -q 2>/dev/null || true
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do
    [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"
  done
fi

declare -A RES
RC=0

if want f06; then
  echo; echo "=== F06 browser suite"
  (cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" JOIN_DIR="$REPO/join" $PY -m pytest test_f06.py -q -rA --tb=line \
      -p no:cacheprovider "$@") >"$HERE/.last_run_f06.txt" 2>&1
  rc=$?
  grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed)" "$HERE/.last_run_f06.txt"
  RES["F06 browser suite"]="$(grep -Eo '[0-9]+ passed|[0-9]+ failed|[0-9]+ errors?' "$HERE/.last_run_f06.txt" | tr '\n' ' ')(rc=$rc)"
  [ $rc = 0 ] || RC=1
fi

if want fn; then
  echo; echo "=== manage-members function tests (QA, Deno-style on Node)"
  (cd "$REPO" && "$NODE" --experimental-transform-types --no-warnings --import "$REPO/tests/f05/deno_shim.mjs" \
      scripts/dev/deno_test_node.mjs tests/f06/function_test.ts) >"$HERE/.last_run_fn.txt" 2>&1
  rc=$?
  grep -E "^  FAIL|pass$" "$HERE/.last_run_fn.txt" | tail -40
  RES["F06 function tests"]="$(grep -Eo '[0-9]+/[0-9]+ pass' "$HERE/.last_run_fn.txt" | tail -1) (rc=$rc)"
  [ $rc = 0 ] || RC=1
fi

if want db; then
  echo; echo "=== DB harness (local PostgreSQL)"
  (service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1) || true
  $PY "$HERE/db_check.py" >"$HERE/.last_run_db.txt" 2>&1
  rc=$?
  grep -E "^apply .*FAIL|^qa\.|FAIL|ALL OK|FAILURES|leftover" "$HERE/.last_run_db.txt"
  RES["DB harness"]="$(grep -E '^qa\.f06_run' "$HERE/.last_run_db.txt") (rc=$rc)"
  [ $rc = 0 ] || RC=1
fi

if want off; then
  echo; echo "=== Criterion 1: MEMBERS_FEATURE='off' → the F05 runner on a flipped copy"
  OFF="$WORK/repo_members_off"
  cp -r "$REPO" "$OFF"
  for f in "$OFF/app/index.html" "$OFF/join/index.html"; do
    if grep -Eq "const[[:space:]]+MEMBERS_FEATURE[[:space:]]*=[[:space:]]*['\"]on['\"]" "$f"; then
      sed -i -E "0,/const[[:space:]]+MEMBERS_FEATURE[[:space:]]*=[[:space:]]*['\"]on['\"]/s//const MEMBERS_FEATURE='off'/" "$f"
    else
      echo "FAIL: const MEMBERS_FEATURE='on' not found in $f"; RC=1
    fi
  done
  (cd "$OFF" && bash tests/f05/run.sh --join on) >"$HERE/.last_run_off.txt" 2>&1
  rc=$?
  sed -n '/F05 QA summary/,$p' "$HERE/.last_run_off.txt"
  echo "(expected in this run: version-pin cases only — see the header of this file)"
  grep -E "^FAILED " "$HERE/.last_run_off.txt" | grep -Ev "app_version|pt_version|title_version|change_comments" \
    && { echo "FAIL: non-version failures with the flag off"; RC=1; }
  RES["flag off (F05 runner)"]="rc=$rc (version pins expected)"
fi

echo; echo "================ F06 QA summary ================"
for k in "${!RES[@]}"; do printf '%-34s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
