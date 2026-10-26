#!/usr/bin/env bash
# Lonely Planner F04-HOME QA runner · version 1.0.0
# CHANGE 2026-10-26 F04H-QA-04: first version (no previous version); built like tests/f06/run.sh 1.0.0.
#   (1) f04h:   the F04-HOME browser suite tests/f04home/test_f04home.py (Playwright, 390×844, he-IL, fake backend);
#   (2) static: only its static cases (F4H-13: protected functions vs BASE_REF, versions, flag, CHANGE tags, node --check, ids);
#   (3) off:    criterion 1 "flag off = alpha.7": a copy of the repo with HOME_INSTALL_FEATURE='off' in app/ AND invite/, on
#               which the existing suites are run unchanged: F04 (tests/f05/run.sh --join on --only f04), F05
#               (tests/f05/run.sh --join on --only f05, MAIN_REF = the alpha.5.1 commit it pins) and F06 (tests/f06/run.sh
#               --only f06). OFF_SUITES="f04 f05 f06 f20" adds F20 (long).
#
# usage: ./run.sh [--only f04h|static|off] [extra pytest args for the F04-HOME browser suite]
# env:   PYTHON, BASE_REF (default ee5c723), OFF_SUITES (default "f04 f05 f06")
#
# Expected failures in the 'off' run (version pins only, spec §4 criterion 1 "except version pins"):
#   F05 suite: test_s01_static[app_version|pt_version] (pin alpha.6) and test_s01_static[change_comments] (F05 tags rule);
#   F04/F20 version pins are already deselected by tests/f05/run.sh. Failures that already occur on ee5c723 (alpha.7 without
#   F04-HOME; recorded in off_baseline_ee5c723.txt: 3 F04 cases about the "עוד" sheet changed by F06, 11 F05 cases) are not
#   counted. Anything else failing with the flag off is a finding.
# Before the implementation exists (ee5c723) the flag is missing: the copy is then identical to the repo (= alpha.7) and
# the runner says so (the static case F4H-13[flag_declared] fails for that reason).
# Nothing here talks to Supabase or the network.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2;;
    *) break;;
  esac
done
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
WORK=$(mktemp -d "${TMPDIR:-/tmp}/f04hqa.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

$PY -c "import pytest" 2>/dev/null || true
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do
    [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"
  done
fi
$PY -c "import pytest, playwright" || { echo "pytest/playwright not available"; exit 2; }

declare -A RES
RC=0
summ() { # name logfile rc
  local p f s e
  p=$(grep -Eo "[0-9]+ passed" "$2" | tail -1 | grep -Eo "[0-9]+"); f=$(grep -Eo "[0-9]+ failed" "$2" | tail -1 | grep -Eo "[0-9]+")
  s=$(grep -Eo "[0-9]+ skipped" "$2" | tail -1 | grep -Eo "[0-9]+"); e=$(grep -Eo "[0-9]+ errors?" "$2" | tail -1 | grep -Eo "[0-9]+")
  RES[$1]="passed=${p:-0} failed=${f:-0} skipped=${s:-0} errors=${e:-0} (rc=$3)"
}

if want f04h; then
  echo; echo "=== F04-HOME browser suite"
  (cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" $PY -m pytest test_f04home.py -q -rA --tb=line -p no:cacheprovider "$@") \
    >"$HERE/.last_run_f04h.txt" 2>&1
  rc=$?
  grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed)" "$HERE/.last_run_f04h.txt"
  summ "F04-HOME browser suite" "$HERE/.last_run_f04h.txt" $rc
  [ $rc = 0 ] || RC=1
fi

if [ "$ONLY" = static ]; then
  echo; echo "=== F04-HOME static cases (F4H-13)"
  (cd "$HERE" && REPO_DIR="$REPO" APP_DIR="$REPO/app" $PY -m pytest test_f04home.py -q -rA --tb=line -p no:cacheprovider \
      -k "f4h_13" "$@") >"$HERE/.last_run_static.txt" 2>&1
  rc=$?
  grep -E "^(FAILED|ERROR|PASSED) |[0-9]+ (passed|failed)" "$HERE/.last_run_static.txt"
  summ "F04-HOME static" "$HERE/.last_run_static.txt" $rc
  [ $rc = 0 ] || RC=1
fi

if want off; then
  echo; echo "=== Criterion 1: HOME_INSTALL_FEATURE='off' → the F04 / F05 / F06 suites on a flipped copy"
  OFF="$WORK/repo_home_off"
  cp -r "$REPO" "$OFF"
  MISSING=""
  for f in "$OFF/app/index.html" "$OFF/invite/index.html"; do
    if grep -Eq "(const|let|var)[[:space:]]+HOME_INSTALL_FEATURE[[:space:]]*=[[:space:]]*['\"]on['\"]" "$f"; then
      sed -i -E "0,/((const|let|var)[[:space:]]+HOME_INSTALL_FEATURE[[:space:]]*=[[:space:]]*)['\"]on['\"]/s//\1'off'/" "$f"
      echo "(flipped: ${f#$OFF/})"
    else
      echo "WARN: HOME_INSTALL_FEATURE='on' not found in ${f#$OFF/} — copy left as is (= alpha.7 before the implementation)"
      MISSING="$MISSING ${f#$OFF/}"
    fi
  done
  # F05's static checks compare with the alpha.5.1 app: the parent of the commit that introduced APP_VERSION alpha.6
  A6=$(git -C "$REPO" log --format=%h -S"APP_VERSION='3.0.0-alpha.6'" -- app/index.html | tail -1)
  F05_MAIN=${F05_MAIN_REF:-${A6:+$A6^}}
  for s in ${OFF_SUITES:-f04 f05 f06}; do
    case "$s" in
      f04|f05|f20)
        log="$HERE/.last_run_off_$s.txt"
        (cd "$OFF" && MAIN_REF="${F05_MAIN:-main}" bash tests/f05/run.sh --join on --only "$s") >"$log" 2>&1
        rc=$?
        sed -n '/F05 QA summary/,$p' "$log" | grep -v "^overall"
        ;;
      f06)
        log="$HERE/.last_run_off_f06.txt"
        (cd "$OFF" && bash tests/f06/run.sh --only f06) >"$log" 2>&1
        rc=$?
        sed -n '/F06 QA summary/,$p' "$log" | grep -v "^overall"
        ;;
      *) echo "unknown suite $s"; continue;;
    esac
    # failures already present on ee5c723 (alpha.7 before F04-HOME) are listed in off_baseline_ee5c723.txt and not counted
    known=$(grep -E "^$s " "$HERE/off_baseline_ee5c723.txt" 2>/dev/null | cut -d' ' -f2-)
    unexpected=$(grep -E "^FAILED |^ERROR " "$log" | sed -E 's/^(FAILED|ERROR) ([^ ]+).*/\2/' \
      | grep -Ev "app_version|pt_version|title_version|change_comments" | grep -Fxv -f <(printf '%s\n' "$known" | sed '/^$/d'; echo "__none__"))
    if [ -n "$unexpected" ]; then
      echo "FAIL ($s): failures with the flag off that are not version pins and not pre-existing on ee5c723:"; echo "$unexpected"; RC=1
      RES["flag off · $s"]="rc=$rc, NEW NON-VERSION FAILURES (see $log)"
    else
      RES["flag off · $s"]="rc=$rc (version pins / pre-existing ee5c723 failures only)"
    fi
  done
  [ -n "$MISSING" ] && RES["flag off · flag missing in"]="$MISSING (copy = repo)"
fi

echo; echo "================ F04-HOME QA summary ================"
for k in "${!RES[@]}"; do printf '%-34s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
