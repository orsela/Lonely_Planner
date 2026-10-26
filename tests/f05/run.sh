#!/usr/bin/env bash
# Plan_Travel F05 QA runner · version 1.0.1
# CHANGE 2026-10-26 QA-DEBT-13: 1.0.0 → 1.0.1: the v2.15.2 baseline is never cloned from GitHub (offline runs); without a local
#   checkout in BASELINE_DIR the F02 suite still runs (protected functions from git) and its 4 whole-old-app cases skip.
#   The full regression is tests/run_all.sh (one summary table, current deselect list); this runner is kept for its feature.
# CHANGE 2026-10-19 F05-QA-01: first version (no previous version); built from tests/f20/run.sh 1.0.0. What is new compared
#   to that runner: (1) the F05 browser suite (tests/f05/test_f05.py, its own fake supabase-js + fake join-trip /
#   approve-member backend; it serves the repo like GitHub Pages so /Lonely_Planner/app/ and /Lonely_Planner/join/ share an
#   origin); (2) every regression suite runs twice: the repo as delivered (JOIN_FEATURE='on' in app/ and join/) and a copy of
#   the repo with JOIN_FEATURE flipped to 'off' in BOTH app/index.html and join/index.html (spec criterion 1: 'off' ==
#   alpha.5.1, /join/ = the F04 "בקרוב" page); (3) the Deno-style function tests run on Node through
#   scripts/dev/deno_test_node.mjs, preloaded with tests/f05/deno_shim.mjs (Deno.env.set/delete, Deno.listen/connect on
#   loopback) so tests/f04/function_test.ts and invite-manager's SMTP test run too; (4) the DB harness runs on the local
#   PostgreSQL through scripts/dev/f05_db_check.py (0001…0012 + 0013_qa_f05_harness.sql applied twice, qa.f01–f05_run()).
#
# usage: ./run.sh [--only f05|f20|f04|f03on|f03off|f02|fn|db] [--join on|off|both] [extra pytest args]
# env:   PYTHON, BASELINE_DIR (v2.15.2 checkout for F02; default ~/.cache/plan_travel_qa/vtp_baseline, cloned when missing),
#        F20_MAIN_REF (alpha.4.2 reference for the F20 static checks; default a7c7a32), PGCONN (psql connection args, default "")
#
# Deselected in the regression runs (version pins + what F05 changes on purpose; each with its F05 replacement):
#   F02 (both):  test_ac15_static[app_version|title_version|manifest_visible_fields_unchanged]   — as in the F04/F20 runners
#   F03 (both):  test_ac18_static[app_version|title_version], test_ac10_invite_page_outside_app — as in the F04/F20 runners
#   F03 WIZARD on: the 8 F03-landing cases replaced by F04                                     — as in the F04/F20 runners
#   F04 (both):  test_c21_static[app_version|pt_version]   version pins (alpha.5.1 → alpha.6)  [test_f05.py::test_s01_static[app_version|pt_version]]
#   F04 (on):    test_c11_c12_done_link_whatsapp_copy      asserts the "בקרוב · … (F05)" card on the F04 done screen, which F05
#                                                          shows only with JOIN_FEATURE='off' (dev notes §1 F05-DONE-01)
#                                                          [test_f05.py::test_r01_f04_done_screen[on|off]: same checks, card only when off]
#                test_c16_join_page_coming_soon_clears_hash  /join/ is the F05 join page when 'on' (spec §1.1)
#                                                          [test_f05.py::test_a01_join_off_is_coming_soon, test_b01_preview…]
#                test_n01_no_old_name_rendered[join]       same /join/ "בקרוב" page                [test_f05.py::test_b01_preview… (brand, no old names)]
#   F20 (both):  test_st_static[app_version|pt_version]     version pins                         [test_f05.py::test_s01_static[app_version|pt_version]]
#                test_st_static[change_comments_cover_hunks] F20 rule "every hunk vs alpha.4.2 has an F20 comment"; F05 hunks
#                                                          carry F05 comments                  [test_f05.py::test_s01_static[change_comments]]
#                test_st_static[no_db_or_function_change]  F20 shipped no migration; F05 adds 0012 + two functions on purpose
#                                                          [DB harness qa.f05_run() + function tests]
#   The F20 suite's MAIN_REF must be alpha.4.2 (its static checks compare against it): F20_MAIN_REF=a7c7a32 (main is alpha.5.1 now).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
ONLY=""; JS=both
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2;;
    --join) JS=$2; shift 2;;
    *) break;;
  esac
done
WORK=$(mktemp -d "${TMPDIR:-/tmp}/f05qa.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# ---- python deps (same fallbacks as tests/f20/run.sh) ----
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
# CHANGE 2026-10-26 QA-DEBT-13: no network clone any more — the F02 protected functions / SEED_DATA come from git
#   (tests/qa_refs.py V2152_REF); only the 4 F02 cases that RUN the whole v2.15.2 app need a local checkout and SKIP without one.
F02_OK=1   # CHANGE 2026-10-26 QA-DEBT-13: always run F02 (was 0 = "NOT RUN" without a v2.15.2 checkout)
if ! grep -q "const APP_VERSION='2.15.2'" "${BASELINE_DIR:-/nonexistent}/index.html" 2>/dev/null; then
  echo "NOTE: no v2.15.2 checkout in BASELINE_DIR (${BASELINE_DIR:-unset}); the 4 F02 cases that run the old app will skip"
  export BASELINE_DIR=${BASELINE_DIR:-/nonexistent-v2152-checkout}
fi

declare -A RES
summ() { # name logfile rc
  local p f s e d
  p=$(grep -Eo "[0-9]+ passed" "$2" | tail -1 | grep -Eo "[0-9]+"); f=$(grep -Eo "[0-9]+ failed" "$2" | tail -1 | grep -Eo "[0-9]+")
  s=$(grep -Eo "[0-9]+ skipped" "$2" | tail -1 | grep -Eo "[0-9]+"); e=$(grep -Eo "[0-9]+ errors?" "$2" | tail -1 | grep -Eo "[0-9]+")
  d=$(grep -Eo "[0-9]+ deselected" "$2" | tail -1 | grep -Eo "[0-9]+")
  RES[$1]="passed=${p:-0} failed=${f:-0} skipped=${s:-0} errors=${e:-0} deselected=${d:-0} (rc=$3)"
}
pyt() { # name repo_dir subdir testfile logfile [pytest args]   (APP_DIR / REPO_DIR / MAIN_REF come from the environment)
  local name=$1 rd=$2 sub=$3 file=$4 log=$5; shift 5
  echo; echo "=== $name · REPO_DIR=$rd"
  (cd "$rd/$sub" && REPO_DIR="$rd" APP_DIR="$rd/app" $PY -m pytest "$file" -q -rA --tb=line -p no:cacheprovider "$@") >"$log" 2>&1
  local rc=$?
  grep -E "^(FAILED|ERROR) [^ ]+::|[0-9]+ (passed|failed)" "$log" | sed -E 's/ - AssertionError: / — /'
  summ "$name" "$log" $rc
  return $rc
}
flip() { # file FLAG on|off — first top-level const FLAG='…'
  if grep -Eq "const[[:space:]]+$2[[:space:]]*=[[:space:]]*['\"](on|off)['\"]" "$1"; then
    sed -i -E "0,/const[[:space:]]+$2[[:space:]]*=[[:space:]]*['\"](on|off)['\"]/s//const $2='$3'/" "$1"
  else
    echo "WARN: const $2 not found in $1"
  fi
}
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
repo_copy() { # dst JOIN on|off  → a copy of the repo (with .git) whose app/ and join/ carry JOIN_FEATURE=<state>
  if [ ! -d "$1" ]; then
    cp -r "$REPO" "$1"
    flip "$1/app/index.html" JOIN_FEATURE "$2"
    flip "$1/join/index.html" JOIN_FEATURE "$2"
    echo "(repo copy $1: JOIN_FEATURE='$2' in app/ and join/)"
  fi
}

F02_DESEL=(--deselect "tests/test_f02.py::test_ac15_static[app_version]" --deselect "tests/test_f02.py::test_ac15_static[title_version]"
           --deselect "tests/test_f02.py::test_ac15_static[manifest_visible_fields_unchanged]")
F03_DESEL_BOTH=(--deselect "test_f03.py::test_ac18_static[app_version]" --deselect "test_f03.py::test_ac18_static[title_version]"
                --deselect "test_f03.py::test_ac10_invite_page_outside_app")
F03_DESEL_ON=("${F03_DESEL_BOTH[@]}"
              --deselect "test_f03.py::test_ac10_landing_valid[fresh-device]" --deselect "test_f03.py::test_ac10_landing_valid[linked-device]"
              --deselect "test_f03.py::test_ac10_landing_network_error_and_retry" --deselect "test_f03.py::test_ac12_token_not_kept[valid]"
              --deselect "test_f03.py::test_ac10_invite_link_while_app_open" --deselect "test_f03.py::test_ac10_invite_link_encoded_and_query"
              --deselect "test_f03.py::test_ac10_invite_via_launch_queue" --deselect "test_f03.py::test_ac17_390_rtl_touch[landing-valid]")
F04_DESEL_BOTH=(--deselect "test_f04.py::test_c21_static[app_version]" --deselect "test_f04.py::test_c21_static[pt_version]")
F04_DESEL_ON=("${F04_DESEL_BOTH[@]}" --deselect "test_f04.py::test_c11_c12_done_link_whatsapp_copy"
              --deselect "test_f04.py::test_c16_join_page_coming_soon_clears_hash" --deselect "test_f04.py::test_n01_no_old_name_rendered[join]")
F20_DESEL=(--deselect "test_f20.py::test_st_static[app_version]" --deselect "test_f20.py::test_st_static[pt_version]"
           --deselect "test_f20.py::test_st_static[change_comments_cover_hunks]" --deselect "test_f20.py::test_st_static[no_db_or_function_change]")

RC=0
if want f05; then
  pyt "F05 browser suite" "$REPO" tests/f05 test_f05.py "$HERE/.last_run_f05.txt" "$@" || RC=1
fi

case "$JS" in both) JSS="on off";; on) JSS="on";; off) JSS="off";; *) echo "bad --join $JS"; exit 2;; esac
for J in $JSS; do
  if [ "$J" = on ]; then R="$REPO"; else R="$WORK/repo_join_off"; fi
  if [ "$J" = off ] && { want f20 || want f04 || want f03on || want f03off || want f02; }; then repo_copy "$R" off; fi
  RW="$WORK/repo_join_${J}_wiz_off"
  if want f03off; then
    if [ ! -d "$RW" ]; then cp -r "$R" "$RW"; flip "$RW/app/index.html" WIZARD_FEATURE off; fi
  fi
  if [ "$J" = on ]; then D4=("${F04_DESEL_ON[@]}"); else D4=("${F04_DESEL_BOTH[@]}"); fi
  if want f20; then
    MAIN_REF=${F20_MAIN_REF:-a7c7a32} pyt "F20 suite · JOIN=$J" "$R" tests/f20 test_f20.py "$HERE/.last_run_f20_j$J.txt" "${F20_DESEL[@]}" "$@" || RC=1
  fi
  if want f04; then
    pyt "F04 suite · JOIN=$J" "$R" tests/f04 test_f04.py "$HERE/.last_run_f04_j$J.txt" "${D4[@]}" "$@" || RC=1
  fi
  if want f03on; then
    pyt "F03 regression · JOIN=$J · WIZARD=on" "$R" tests/f03 test_f03.py "$HERE/.last_run_f03on_j$J.txt" "${F03_DESEL_ON[@]}" "$@" || RC=1
  fi
  if want f03off; then
    pyt "F03 regression · JOIN=$J · WIZARD=off" "$RW" tests/f03 test_f03.py "$HERE/.last_run_f03off_j$J.txt" "${F03_DESEL_BOTH[@]}" "$@" || RC=1
  fi
  if want f02; then
    if [ "$F02_OK" = 1 ]; then
      pyt "F02 regression · JOIN=$J" "$R" tests/f02 tests/test_f02.py "$HERE/.last_run_f02_j$J.txt" "${F02_DESEL[@]}" "$@" || RC=1
    else
      RES["F02 regression · JOIN=$J"]="NOT RUN: no v2.15.2 baseline"
    fi
  fi
done

if want fn; then
  NODE=${NODE:-node}
  dn() { # name logfile flag files...
    local name=$1 log=$2 fl=$3; shift 3
    echo; echo "=== $name (Deno-style on Node)"
    (cd "$REPO" && "$NODE" "$fl" --no-warnings --import "$HERE/deno_shim.mjs" scripts/dev/deno_test_node.mjs "$@") >"$log" 2>&1
    local rc=$?
    grep -E "^  FAIL|pass$" "$log" | tail -40
    RES["$name"]="$(grep -Eo '[0-9]+/[0-9]+ pass' "$log" | tail -1) (rc=$rc)"
    return $rc
  }
  dn "F05 function tests (QA)" "$HERE/.last_run_fn_f05.txt" --experimental-transform-types tests/f05/function_test.ts || RC=1
  dn "join-trip unit tests (dev)" "$HERE/.last_run_fn_jt.txt" --experimental-strip-types supabase/functions/join-trip/test.ts || RC=1
  dn "approve-member unit tests (dev)" "$HERE/.last_run_fn_am.txt" --experimental-strip-types supabase/functions/approve-member/test.ts || RC=1
  dn "create-trip unit tests (dev)" "$HERE/.last_run_fn_ct.txt" --experimental-transform-types supabase/functions/create-trip/test.ts || RC=1
  dn "invite-manager unit tests (dev)" "$HERE/.last_run_fn_im.txt" --experimental-transform-types supabase/functions/invite-manager/test.ts || RC=1
  dn "F04 function tests (QA)" "$HERE/.last_run_fn_f04.txt" --experimental-transform-types tests/f04/function_test.ts || RC=1
fi

if want db; then
  echo; echo "=== DB harness (local PostgreSQL: 0001…0012, 0013 applied twice, qa.f01–f05_run())"
  (service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1) || true
  (cd "$REPO" && sudo -u postgres $PY scripts/dev/f05_db_check.py "${PGCONN:-}") >"$HERE/.last_run_db.txt" 2>&1
  rc=$?
  grep -E "^apply .*FAIL|^qa\.|FAIL|ALL OK|FAILURES|leftover" "$HERE/.last_run_db.txt"
  RES["DB harness qa.f05_run()"]="$(grep -E '^qa\.f05_run' "$HERE/.last_run_db.txt") · $(grep -E '^qa\.f0[1-4]_run' "$HERE/.last_run_db.txt" | tr '\n' ' ') (rc=$rc)"
  [ $rc = 0 ] || RC=1
fi

echo; echo "================ F05 QA summary ================"
for k in "${!RES[@]}"; do printf '%-46s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
