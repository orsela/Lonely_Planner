#!/usr/bin/env bash
# Plan_Travel F20 QA runner · version 1.0.0
# CHANGE 2026-10-13 F20-QA-01: first version (no previous version); built from tests/f04/run.sh 1.2.0. What is new compared
#   to that runner: (1) the F20 browser suite (tests/f20/test_f20.py, its SWITCH_FEATURE='off' / ADMIN off / WIZARD off /
#   HOME_LAYOUT cases are served by the suite itself); (2) every regression suite runs twice, with the app as delivered
#   (SWITCH_FEATURE='on') and with a copy whose SWITCH_FEATURE is flipped to 'off' (F20 AC1: 'off' == alpha.4.2);
#   (3) a DB/Edge-Function check: F20 ships no migration and no function change (git diff against MAIN_REF).
#
# Runs:
#   1. F20 browser suite                                    (criteria 2–14; AC1 partly)
#   2. for SWITCH in on, off:
#        F04 browser suite                                  (WIZARD on + its own 'off' cases)
#        F03 regression, WIZARD_FEATURE on / off
#        F02 regression, WIZARD_FEATURE on / off
#   3. Deno: tests/f04/function_test.ts + the functions' own unit tests (unchanged by F20)
#   4. DB: `git diff MAIN_REF --stat` must not touch supabase/ or *.sql
#
# usage: ./run.sh [--only f20|f04|f03on|f03off|f02on|f02off|fn|db] [--switch on|off|both] [extra pytest args]
# env:   APP_DIR (default <repo>/app), BASELINE_DIR (v2.15.2 checkout for F02), MAIN_REF (default main), PYTHON, DENO
#
# Deselected in the regression runs — exactly the F04 runner's list (version pins of older suites, F04's intended changes),
# nothing added for F20 (F20's intended changes are handled inside the suites, marked CHANGE 2026-10-13 F20-QA-02):
#   F02, both:  test_ac15_static[app_version|title_version|manifest_visible_fields_unchanged]
#   F03, both:  test_ac18_static[app_version|title_version], test_ac10_invite_page_outside_app
#   F03, WIZARD on only: the 8 F03-landing cases replaced by F04 (see tests/f04/run.sh)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
export APP_DIR=${APP_DIR:-$REPO/app}
export REPO_DIR=$REPO
export MAIN_REF=${MAIN_REF:-main}
ONLY=""; SW=both
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2;;
    --switch) SW=$2; shift 2;;
    *) break;;
  esac
done
WORK=$(mktemp -d "${TMPDIR:-/tmp}/f20qa.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# ---- python deps (same fallbacks as tests/f04/run.sh) ----
$PY -c "import playwright" 2>/dev/null || $PY -m pip install playwright --break-system-packages -q || true
$PY -c "import pytest" 2>/dev/null || $PY -m pip install pytest --break-system-packages -q 2>/dev/null || true
if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do
    [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"
  done
fi
$PY -c "import pytest, playwright" || { echo "pytest/playwright not available"; exit 2; }

# ---- v2.15.2 baseline for the F02 suite ----
if [ -z "${BASELINE_DIR:-}" ]; then
  for c in /home/claude/orsela/vietnam_travel_planner "$HOME/.cache/plan_travel_qa/vtp_baseline"; do
    [ -f "$c/index.html" ] && export BASELINE_DIR=$c && break
  done
fi
if [ -z "${BASELINE_DIR:-}" ]; then
  mkdir -p "$HOME/.cache/plan_travel_qa"
  timeout 90 git clone -q --depth 1 https://github.com/orsela/Vietnam_Travel_Planner "$HOME/.cache/plan_travel_qa/vtp_baseline" 2>/dev/null \
    && export BASELINE_DIR="$HOME/.cache/plan_travel_qa/vtp_baseline"
fi
if ! grep -q "const APP_VERSION='2.15.2'" "${BASELINE_DIR:-/nonexistent}/index.html" 2>/dev/null; then
  echo "WARN: BASELINE_DIR is not a v2.15.2 checkout (${BASELINE_DIR:-unset}); F02 baseline-dependent cases will fail"
fi

declare -A RES
summ() { # name logfile rc
  local p f s e d
  p=$(grep -Eo "[0-9]+ passed" "$2" | tail -1 | grep -Eo "[0-9]+"); f=$(grep -Eo "[0-9]+ failed" "$2" | tail -1 | grep -Eo "[0-9]+")
  s=$(grep -Eo "[0-9]+ skipped" "$2" | tail -1 | grep -Eo "[0-9]+"); e=$(grep -Eo "[0-9]+ errors?" "$2" | tail -1 | grep -Eo "[0-9]+")
  d=$(grep -Eo "[0-9]+ deselected" "$2" | tail -1 | grep -Eo "[0-9]+")
  RES[$1]="passed=${p:-0} failed=${f:-0} skipped=${s:-0} errors=${e:-0} deselected=${d:-0} (rc=$3)"
}
pyt() { # name dir testfile logfile [pytest args]
  local name=$1 dir=$2 file=$3 log=$4; shift 4
  echo; echo "=== $name · APP_DIR=$APP_DIR"
  (cd "$dir" && $PY -m pytest "$file" -q -rA --tb=line -p no:cacheprovider "$@") >"$log" 2>&1
  local rc=$?
  grep -E "^(FAILED|ERROR|XFAIL)|[0-9]+ (passed|failed)" "$log" | sed -E 's/ - AssertionError: / — /'
  summ "$name" "$log" $rc
  return $rc
}
flip() { # src_dir dst_dir FLAG → copy with FLAG='off'
  cp -r "$1" "$2"
  if grep -Eq "const[[:space:]]+$3[[:space:]]*=[[:space:]]*['\"]on['\"]" "$2/index.html"; then
    sed -i -E "0,/const[[:space:]]+$3[[:space:]]*=[[:space:]]*['\"]on['\"]/s//const $3='off'/" "$2/index.html"
    echo "($3 flipped to 'off' in $2/index.html)"
  else
    echo "WARN: const $3='on' not found in $1/index.html — copy served as-is"
  fi
}
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }

F02_DESEL=(--deselect "tests/test_f02.py::test_ac15_static[app_version]" --deselect "tests/test_f02.py::test_ac15_static[title_version]"
           --deselect "tests/test_f02.py::test_ac15_static[manifest_visible_fields_unchanged]")
F03_DESEL_BOTH=(--deselect "test_f03.py::test_ac18_static[app_version]" --deselect "test_f03.py::test_ac18_static[title_version]"
                --deselect "test_f03.py::test_ac10_invite_page_outside_app")
F03_DESEL_ON=("${F03_DESEL_BOTH[@]}"
              --deselect "test_f03.py::test_ac10_landing_valid[fresh-device]" --deselect "test_f03.py::test_ac10_landing_valid[linked-device]"
              --deselect "test_f03.py::test_ac10_landing_network_error_and_retry" --deselect "test_f03.py::test_ac12_token_not_kept[valid]"
              --deselect "test_f03.py::test_ac10_invite_link_while_app_open" --deselect "test_f03.py::test_ac10_invite_link_encoded_and_query"
              --deselect "test_f03.py::test_ac10_invite_via_launch_queue" --deselect "test_f03.py::test_ac17_390_rtl_touch[landing-valid]")

RC=0
SRC_APP=$APP_DIR
if want f20; then
  pyt "F20 browser suite" "$HERE" test_f20.py "$HERE/.last_run_f20.txt" "$@" || RC=1
fi

case "$SW" in both) SWS="on off";; on) SWS="on";; off) SWS="off";; *) echo "bad --switch $SW"; exit 2;; esac
for S in $SWS; do
  if [ "$S" = on ]; then A="$SRC_APP"; else A="$WORK/app_switch_off"; [ -d "$A" ] || flip "$SRC_APP" "$A" SWITCH_FEATURE; fi
  AW="$WORK/app_switch_${S}_wiz_off"
  if want f03off || want f02off; then [ -d "$AW" ] || flip "$A" "$AW" WIZARD_FEATURE; fi
  if want f04; then
    APP_DIR="$A" pyt "F04 suite · SWITCH=$S" "$REPO/tests/f04" test_f04.py "$HERE/.last_run_f04_sw$S.txt" "$@" || RC=1
  fi
  if want f03on; then
    APP_DIR="$A" pyt "F03 regression · SWITCH=$S · WIZARD=on" "$REPO/tests/f03" test_f03.py "$HERE/.last_run_f03on_sw$S.txt" "${F03_DESEL_ON[@]}" "$@" || RC=1
  fi
  if want f03off; then
    APP_DIR="$AW" pyt "F03 regression · SWITCH=$S · WIZARD=off" "$REPO/tests/f03" test_f03.py "$HERE/.last_run_f03off_sw$S.txt" "${F03_DESEL_BOTH[@]}" "$@" || RC=1
  fi
  if want f02on; then
    APP_DIR="$A" pyt "F02 regression · SWITCH=$S · WIZARD=on" "$REPO/tests/f02" tests/test_f02.py "$HERE/.last_run_f02on_sw$S.txt" "${F02_DESEL[@]}" "$@" || RC=1
  fi
  if want f02off; then
    APP_DIR="$AW" pyt "F02 regression · SWITCH=$S · WIZARD=off" "$REPO/tests/f02" tests/test_f02.py "$HERE/.last_run_f02off_sw$S.txt" "${F02_DESEL[@]}" "$@" || RC=1
  fi
done

if want fn; then
  DENO=${DENO:-$(command -v deno || true)}
  for c in /tmp/claude-0/-home-claude-plan-travel/*/scratchpad/deno/deno /tmp/claude-0/-home-claude/*/scratchpad/deno/deno; do
    [ -z "$DENO" ] && [ -x "$c" ] && DENO=$c
  done
  MAP="$REPO/supabase/functions/create-trip/test_import_map.json"
  dt() { # name logfile args...
    local name=$1 log=$2; shift 2
    echo; echo "=== $name (Deno)"
    (cd "$REPO" && "$DENO" test --no-check --allow-env --allow-read "$@") >"$log" 2>&1
    local rc=$?
    sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -E "^(.* \.\.\. FAILED|ok \||FAILED \|)" | tail -20
    RES["$name"]="$(sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -Eo '(ok|FAILED) \| [0-9]+ passed( \([0-9]+ steps?\))? \| [0-9]+ failed' | tail -1) (rc=$rc)"
    return $rc
  }
  if [ -z "$DENO" ]; then
    RES["Function tests (Deno)"]="NOT RUN: deno not installed"; echo "deno not installed — skipped"
  else
    dt "F04 function tests" "$HERE/.last_run_fn.txt" --import-map="$MAP" tests/f04/function_test.ts || RC=1
    dt "create-trip unit tests (dev)" "$HERE/.last_run_fn_ct.txt" --import-map="$MAP" supabase/functions/create-trip/test.ts || RC=1
    dt "invite-manager unit tests (dev)" "$HERE/.last_run_fn_im.txt" \
       --allow-net=127.0.0.1 --import-map="$REPO/supabase/functions/invite-manager/test_import_map.json" \
       supabase/functions/invite-manager/test.ts || RC=1
  fi
fi

if want db; then
  echo; echo "=== DB / Edge Functions (F20 spec: no migration, no function change)"
  CH=$(cd "$REPO" && git diff --name-only "$MAIN_REF" -- supabase '*.sql')
  (cd "$REPO" && git diff --stat "$MAIN_REF")
  if [ -n "$CH" ]; then RES["DB / functions unchanged"]="FAILED: $CH"; RC=1; else RES["DB / functions unchanged"]="ok (no supabase/ or *.sql change vs $MAIN_REF)"; fi
fi

echo; echo "================ F20 QA summary ================"
for k in "${!RES[@]}"; do printf '%-46s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
