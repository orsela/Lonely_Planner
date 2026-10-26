#!/usr/bin/env bash
# Plan_Travel F04 QA runner · version 1.2.1
# CHANGE 2026-10-26 QA-DEBT-13: 1.2.0 → 1.2.1: the v2.15.2 baseline is never cloned from GitHub (offline runs); without a local
#   checkout in BASELINE_DIR the F02 suite still runs (protected functions from git) and its 4 whole-old-app cases skip.
#   The full regression is tests/run_all.sh (one summary table, current deselect list); this runner is kept for its feature.
# CHANGE 2026-10-12 F04-QA: first version (no previous version); built from tests/f03/run.sh 1.0.0.
# CHANGE 2026-10-12 F04-QA-03: 1.0.0 → 1.1.0: the invite-manager Deno run gets --allow-net=127.0.0.1 (its F03-MAIL-04
#   test opens a local fake SMTP listener on 127.0.0.1:0; loopback only, no external network). Nothing else changed.
# CHANGE 2026-10-12 F04-QA-05: 1.1.0 → 1.2.0: F02 test_ac15_static[manifest_visible_fields_unchanged] is deselected in
#   both states — F04 spec §8 (alpha.4.2) renames the installed app (manifest name/short_name "Lonely Planner") on purpose.
#   F04 replacements: test_f04.py::test_n02_static_names[manifest_name|manifest_short_name|manifest_icons_unchanged].
#
# Runs everything available for F04 and prints a pass/fail summary:
#   1. F04 browser suite (tests/f04/test_f04.py) — WIZARD_FEATURE 'on' plus the 'off' cases inside it
#   2. F03 regression with WIZARD_FEATURE='on'  (app as delivered)          (criterion 19)
#   3. F03 regression with WIZARD_FEATURE='off' (copy of APP_DIR, flag flipped)
#   4. F02 regression 'on' and 'off'
#   5. Deno: tests/f04/function_test.ts (create-trip + invite-manager additions) and the functions' own unit tests
#      (spec §3.2: "existing Deno tests must pass unchanged")
#   6. DB harness: prints how to run qa.f04_run() (real project; the architect runs it via the Connector)
#
# usage: ./run.sh [--only f04|f03on|f03off|f02on|f02off|fn] [extra pytest args]
# env:   APP_DIR (default <repo>/app), BASELINE_DIR (v2.15.2 checkout for F02), ALPHA2_REF, ALPHA3_REF, PYTHON, DENO
#
# Deselected in the regression runs (spec §5.19 — exactly these, nothing else):
#   F02, both states:  test_ac15_static[app_version], test_ac15_static[title_version]          (version strings)
#                      test_ac15_static[manifest_visible_fields_unchanged]  (installed-app name, F04 spec §8; F04-QA-05)
#   F03, both states:  test_ac18_static[app_version], test_ac18_static[title_version]          (version strings)
#                      test_ac10_invite_page_outside_app — asserts the "התחלת הקמה · בקרוב" button on /invite/; /invite/
#                      is not behind the flag (spec §1.1 replaces that button unconditionally), so it is deselected in
#                      'off' too. Its F04 replacement: test_f04.py::test_c16_invite_page_button_opens_app.
#   F03, 'on' only — assertions that need the F03 valid landing page with the disabled "בקרוב" button, which F04 replaces
#   with the code screen (spec §4 "Token entry"); F04 replacements in brackets:
#                      test_ac10_landing_valid[fresh-device], test_ac10_landing_valid[linked-device]   [test_c01_token_link_code_screen_email_locked]
#                      test_ac10_landing_network_error_and_retry                                       [the retry lands on the code screen; network page itself unchanged]
#                      test_ac12_token_not_kept[valid]                                                 [test_c01_token_and_code_never_stored_or_logged]
#                      test_ac10_invite_link_while_app_open                                            [test_c01_token_entry_variants…[hash_change_while_open]]
#                      test_ac10_invite_link_encoded_and_query                                         [test_c01_token_entry_variants…[query|encoded]]
#                      test_ac10_invite_via_launch_queue                                               [test_c01_token_entry_variants…[launch_queue]]
#                      test_ac17_390_rtl_touch[landing-valid]                                          [test_c20_layout_390_rtl_touch[code]]
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY=${PYTHON:-python3}
export APP_DIR=${APP_DIR:-$REPO/app}
export REPO_DIR=$REPO
ONLY=""
if [ "${1:-}" = "--only" ]; then ONLY=$2; shift 2; fi
WORK=$(mktemp -d "${TMPDIR:-/tmp}/f04qa.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# ---- python deps (same fallbacks as tests/f03/run.sh) ----
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
if ! grep -q "const APP_VERSION='2.15.2'" "${BASELINE_DIR:-/nonexistent}/index.html" 2>/dev/null; then
  echo "WARN: BASELINE_DIR is not a v2.15.2 checkout (${BASELINE_DIR:-unset}); F02 baseline-dependent cases will fail"
fi

declare -A RES
summ() { # name logfile rc
  local p f s e
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
  grep -E "^(PASSED|FAILED|ERROR|SKIPPED|XFAIL)|[0-9]+ (passed|failed)" "$log" | sed -E 's/ - AssertionError: / — /'
  summ "$name" "$log" $rc
  return $rc
}
flip_off() { # src_dir dst_dir → copy with WIZARD_FEATURE='off'
  cp -r "$1" "$2"
  if grep -Eq "const[[:space:]]+WIZARD_FEATURE[[:space:]]*=[[:space:]]*['\"]on['\"]" "$2/index.html"; then
    sed -i -E "0,/const[[:space:]]+WIZARD_FEATURE[[:space:]]*=[[:space:]]*['\"]on['\"]/s//const WIZARD_FEATURE='off'/" "$2/index.html"
    echo; echo "(WIZARD_FEATURE flipped to 'off' in $2/index.html)"
  else
    echo; echo "WARN: const WIZARD_FEATURE='on' not found in $1/index.html — 'off' run uses the app as-is"
  fi
}

F02_DESEL=(--deselect "tests/test_f02.py::test_ac15_static[app_version]" --deselect "tests/test_f02.py::test_ac15_static[title_version]"
           --deselect "tests/test_f02.py::test_ac15_static[manifest_visible_fields_unchanged]")  # CHANGE 2026-10-12 F04-QA-05
F03_DESEL_BOTH=(--deselect "test_f03.py::test_ac18_static[app_version]" --deselect "test_f03.py::test_ac18_static[title_version]"
                --deselect "test_f03.py::test_ac10_invite_page_outside_app")
F03_DESEL_ON=("${F03_DESEL_BOTH[@]}"
              --deselect "test_f03.py::test_ac10_landing_valid[fresh-device]" --deselect "test_f03.py::test_ac10_landing_valid[linked-device]"
              --deselect "test_f03.py::test_ac10_landing_network_error_and_retry" --deselect "test_f03.py::test_ac12_token_not_kept[valid]"
              --deselect "test_f03.py::test_ac10_invite_link_while_app_open" --deselect "test_f03.py::test_ac10_invite_link_encoded_and_query"
              --deselect "test_f03.py::test_ac10_invite_via_launch_queue" --deselect "test_f03.py::test_ac17_390_rtl_touch[landing-valid]")

RC=0
if [ -z "$ONLY" ] || [ "$ONLY" = f04 ]; then
  pyt "F04 browser suite" "$HERE" test_f04.py "$HERE/.last_run_f04.txt" "$@" || RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = f03on ]; then
  pyt "F03 regression · WIZARD_FEATURE=on" "$REPO/tests/f03" test_f03.py "$HERE/.last_run_f03_on.txt" "${F03_DESEL_ON[@]}" "$@" || RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = f03off ] || [ "$ONLY" = f02off ]; then
  OFF="$WORK/app_off"; flip_off "$APP_DIR" "$OFF"
fi
if [ -z "$ONLY" ] || [ "$ONLY" = f03off ]; then
  APP_DIR="$OFF" pyt "F03 regression · WIZARD_FEATURE=off" "$REPO/tests/f03" test_f03.py "$HERE/.last_run_f03_off.txt" "${F03_DESEL_BOTH[@]}" "$@" || RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = f02on ]; then
  pyt "F02 regression · WIZARD_FEATURE=on" "$REPO/tests/f02" tests/test_f02.py "$HERE/.last_run_f02_on.txt" "${F02_DESEL[@]}" "$@" || RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = f02off ]; then
  APP_DIR="$OFF" pyt "F02 regression · WIZARD_FEATURE=off" "$REPO/tests/f02" tests/test_f02.py "$HERE/.last_run_f02_off.txt" "${F02_DESEL[@]}" "$@" || RC=1
fi
if [ -z "$ONLY" ] || [ "$ONLY" = fn ]; then
  DENO=${DENO:-$(command -v deno || true)}
  [ -z "$DENO" ] && [ -x /tmp/claude-0/-home-claude/c74d9359-2e9b-50d4-96a0-fd2a16b7206f/scratchpad/deno/deno ] && \
    DENO=/tmp/claude-0/-home-claude/c74d9359-2e9b-50d4-96a0-fd2a16b7206f/scratchpad/deno/deno
  MAP="$REPO/supabase/functions/create-trip/test_import_map.json"
  dt() { # name logfile args...
    local name=$1 log=$2; shift 2
    echo; echo "=== $name (Deno)"
    (cd "$REPO" && "$DENO" test --no-check --allow-env --allow-read "$@") >"$log" 2>&1
    local rc=$?
    sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -E "^(.* \.\.\. (ok|FAILED|ignored)|ok \||FAILED \|)" | tail -60
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
       supabase/functions/invite-manager/test.ts || RC=1  # CHANGE 2026-10-12 F04-QA-03: loopback net for F03-MAIL-04
  fi
fi

echo; echo "=== DB harness"
echo "qa.f04_run() needs the real database. Compare the dev harness 0011_qa_f04_harness.sql against"
echo "tests/f04/sql/qa_f04_cases.md, then (architect, via the Connector): select * from qa.f04_run() order by id;"

echo; echo "================ F04 QA summary ================"
for k in "${!RES[@]}"; do printf '%-42s %s\n' "$k" "${RES[$k]}"; done | sort
echo "overall rc=$RC"
exit $RC
