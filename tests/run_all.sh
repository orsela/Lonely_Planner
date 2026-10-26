#!/usr/bin/env bash
# Lonely Planner · full regression runner (every QA suite, one summary table) · version 1.0.0
# CHANGE 2026-10-26 QA-DEBT-11: new file (no previous version). Replaces running tests/f0x/run.sh one by one for the full
#   regression. Offline: no Supabase, no network (the v2.15.2 protected-function baseline is read from git, tests/qa_refs.py).
#
# usage: tests/run_all.sh [-j N] [--only "job job …"] [--list]
#   -j N      parallel jobs (default 2; each browser suite drives its own Chromium, ~1 CPU each; full run ≈18 min at -j 2)
#   --only    a subset of jobs (names below); --list prints them
# env: PYTHON, NODE, QA_OUT (log dir, default tests/.last_run_all_logs — it git-ignores itself),
#      BASELINE_DIR (optional v2.15.2 checkout: only 4 F02 cases RUN the old app; without it they SKIP), QA_HEADFUL
#      SCRIPTS_DIR is set to <repo>/scripts for every suite (the F02 import-tool case had a stale default path and skipped)
#
# Jobs and what is deselected (each line = reason + the feature that changed the behaviour on purpose + where it is tested now):
#   f02       F02 suite. Deselected: test_ac15_static[title_version]  — superseded by F04 §8 (<title> is exactly "Lonely
#             Planner", tested by F04 test_c21_static[title_version]); test_ac15_static[manifest_visible_fields_unchanged] —
#             superseded by F04 §8 (installed-app name; F04 test_n02_static_names[manifest_*]);
#             test_ac03_viewer_write_rejected_kept_locally_and_pending — superseded by F06 D10 (viewer guard: the write is
#             blocked client-side, F06 suite); test_ac05_parity_with_v2152_rendering — superseded by F05 D10 ("מי אני" =
#             display_name, member chips = active members instead of the fixed USERS). Both RUN in job sup_f02_flags_off.
#   sup_f02_flags_off  F02 ac03 + ac05 on a copy with JOIN_FEATURE='off' and MEMBERS_FEATURE='off' (app/ + join/).
#   f03on     F03 suite, WIZARD_FEATURE on. Deselected: test_ac18_static[title_version] (F04 §8, as above);
#             test_ac10_invite_page_outside_app (F04 §1.1 replaced the "בקרוב" button; F04 test_c16_invite_page_button_opens_app);
#             the 8 F03 landing cases replaced by the F04 code screen (F04 §4; list in tests/f04/run.sh header).
#   f03off    F03 suite on a copy with WIZARD_FEATURE='off'. Deselected: title_version + invite_page_outside_app (as above).
#   f04       F04 suite. Deselected: test_c11_c12_done_link_whatsapp_copy, test_c16_join_page_coming_soon_clears_hash,
#             test_n01_no_old_name_rendered[join] — superseded by F05 (done card / the /join/ page; F05 test_r01, test_a01,
#             test_b01); test_c15_more_join_link_row[manager], test_n01_no_old_name_rendered[more_sheet],
#             test_n03_whatsapp_text_name_and_url[sheet] — superseded by F06 D1 (the "עוד" row "קישור הצטרפות לקבוצה" became
#             "חברים וקישור"; F06 suite). These 3 still RUN in job sup_f04_members and must pass there.
#             test_c01_gate_button_email_entry — superseded by F04-HOME C1 (gate card "קיבלת הזמנה לנהל טיול?" → "מנהל/ת טיול";
#             F4H-07a/07b); it RUNS in job sup_f04_home. (Other gate/invite cases follow F04-HOME inside the suite, 1.5.0.)
#   sup_f04_members  the 3 F06-superseded F04 cases on a copy with MEMBERS_FEATURE='off' in app/ and join/ (F06 criterion 1).
#   sup_f04_home     the F04-HOME-superseded F04 case on a copy with HOME_INSTALL_FEATURE='off' in app/ and invite/.
#   f05       F05 suite. Deselected: test_a02_app_off_is_alpha51, test_c01_not_connected_screen,
#             test_c07_f04_invite_entry_unchanged — superseded by F04-HOME C1 (the gate's F04 card "כניסה עם הזמנה" became
#             "מנהל/ת טיול" → "כניסה עם המייל", moved to the top; F04-HOME F4H-07a/07c). They RUN in job sup_f05_home.
#   sup_f05_home     those 3 F05 cases on a copy with HOME_INSTALL_FEATURE='off' in app/ and invite/ (F04-HOME criterion 1).
#   f06       F06 suite.
#   f20       F20 suite (MAIN_REF = alpha.4.2 from tests/qa_refs.py). Deselected: test_st_static[change_comments_cover_hunks]
#             (F20's rule "every hunk vs alpha.4.2 carries an F20 tag" — F05/F06/F04-HOME hunks carry their own tags) and
#             test_st_static[no_db_or_function_change] (F20 shipped no migration; F05/F06 add migrations + functions on purpose).
#   f04h      F04-HOME suite.
#   static    dev self-check of the latest feature: scripts/dev/f04home_static_check.py ee5c723 (each suite above also runs
#             its own static cases: protected functions == v2.15.2, versions from tests/qa_versions.json, node --check …).
#   fn        Deno-style function tests on Node (scripts/dev/deno_test_node.mjs + tests/f05/deno_shim.mjs): QA F04/F05/F06 and
#             the 5 functions' own unit tests. A failure whose message starts "KNOWN-BUG" is counted as xfail.
#   db        local PostgreSQL only (`service postgresql start`): tests/f06/db_check.py (0001…0015, qa.f01–f06_run());
#             skipped with a note when PostgreSQL cannot start.
# Version pins: every suite reads the expected app version from tests/qa_versions.json (no pin is deselected).
# Known app bugs are xfailed by the suites only when the failure is exactly that bug (docs/qa/QA-DEBT_2026-10-26.md §4).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PY=${PYTHON:-python3}
NODE=${NODE:-node}
JOBS=2; ONLY=""
ALL_JOBS="f04 f05 f20 f03on f03off f02 f04h f06 sup_f02_flags_off sup_f04_members sup_f04_home sup_f05_home fn static db"
while [ $# -gt 0 ]; do
  case "$1" in
    -j) JOBS=$2; shift 2;;
    --only) ONLY=$2; shift 2;;
    --list) echo "$ALL_JOBS"; exit 0;;
    *) echo "unknown argument $1"; exit 2;;
  esac
done
OUT=${QA_OUT:-$HERE/.last_run_all_logs}
mkdir -p "$OUT"; rm -f "$OUT"/*.txt "$OUT"/*.res
printf '*\n' >"$OUT/.gitignore"   # the log dir ignores itself (no change to the repo's .gitignore)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/qa_all.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

if ! $PY -c "import pytest" 2>/dev/null; then
  for d in /root/.local/share/uv/tools/pytest/lib/python3*/site-packages; do
    [ -d "$d" ] && export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$d"
  done
fi
$PY -c "import pytest, playwright" || { echo "pytest/playwright not available"; exit 2; }
export PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1
# F02: only 4 cases run the whole v2.15.2 app; use a local checkout when one exists, never clone
if [ -z "${BASELINE_DIR:-}" ]; then
  for c in /home/claude/orsela/vietnam_travel_planner "$HOME/.cache/plan_travel_qa/vtp_baseline"; do
    grep -q "const APP_VERSION='2.15.2'" "$c/index.html" 2>/dev/null && export BASELINE_DIR=$c && break
  done
fi
export BASELINE_DIR=${BASELINE_DIR:-/nonexistent-v2152-checkout}

# ---------- flag-flipped repo copies (with .git, so the git-based references work) ----------
flip() { # file FLAG value — the first top-level `const|let|var FLAG='…'`
  if grep -Eq "(const|let|var)[[:space:]]+$2[[:space:]]*=[[:space:]]*['\"](on|off)['\"]" "$1"; then
    sed -i -E "0,/((const|let|var)[[:space:]]+$2[[:space:]]*=[[:space:]]*)['\"](on|off)['\"]/s//\1'$3'/" "$1"
  else
    echo "WARN: $2 not found in $1"
  fi
}
copy_repo() { # dst — a copy of the repo (without logs)
  [ -d "$1" ] || { cp -r "$REPO" "$1"; rm -rf "$1/tests/.last_run_all_logs"; }
}
want() { [ -z "$ONLY" ] || [[ " $ONLY " == *" $1 "* ]]; }
if want f03off; then copy_repo "$WORK/wiz_off"; flip "$WORK/wiz_off/app/index.html" WIZARD_FEATURE off; fi
if want sup_f02_flags_off; then copy_repo "$WORK/join_members_off"; for f in app/index.html join/index.html; do flip "$WORK/join_members_off/$f" JOIN_FEATURE off; flip "$WORK/join_members_off/$f" MEMBERS_FEATURE off; done; fi
if want sup_f04_members; then copy_repo "$WORK/members_off"; flip "$WORK/members_off/app/index.html" MEMBERS_FEATURE off; flip "$WORK/members_off/join/index.html" MEMBERS_FEATURE off; fi
if want sup_f04_home || want sup_f05_home; then copy_repo "$WORK/home_off"; flip "$WORK/home_off/app/index.html" HOME_INSTALL_FEATURE off; flip "$WORK/home_off/invite/index.html" HOME_INSTALL_FEATURE off; fi

# ---------- job bodies (each writes $OUT/<job>.txt and $OUT/<job>.res = "status|collected|passed|failed|skipped|xfail|desel|note") ----------
pyjob() { # job repo subdir file-or-nodeid reason-note [pytest args...]
  local job=$1 rd=$2 sub=$3 file=$4 note=$5; shift 5
  local log="$OUT/$job.txt" t0=$SECONDS
  (cd "$rd/$sub" && REPO_DIR="$rd" APP_DIR="$rd/app" JOIN_DIR="$rd/join" SCRIPTS_DIR="$rd/scripts" $PY -m pytest "$file" -q -rfEsxX --tb=line \
      -p no:cacheprovider "$@") >"$log" 2>&1
  local rc=$? last; last=$(grep -E "^=*.*[0-9]+ (passed|failed|error|skipped|deselected|xfailed)" "$log" | tail -1)
  n() { echo "$last" | grep -Eo "[0-9]+ $1" | grep -Eo "[0-9]+" | head -1; }
  local p f s x d e
  p=$(n passed); f=$(n failed); s=$(n skipped); x=$(n xfailed); d=$(n deselected); e=$(n "errors?")
  p=${p:-0}; f=$(( ${f:-0} + ${e:-0} )); s=${s:-0}; x=${x:-0}; d=${d:-0}
  echo "$([ $rc = 0 ] && echo PASS || echo FAIL)|$((p + f + s + x + d))|$p|$f|$s|$x|$d|$note ($((SECONDS - t0))s)" >"$OUT/$job.res"
}

run_job() {
  local j=$1
  case "$j" in
    f02) pyjob f02 "$REPO" tests/f02 tests/test_f02.py "desel: 2 superseded by F04 §8, 1 by F06 D10, 1 by F05 D10" \
           --deselect "tests/test_f02.py::test_ac03_viewer_write_rejected_kept_locally_and_pending" \
           --deselect "tests/test_f02.py::test_ac05_parity_with_v2152_rendering" \
           --deselect "tests/test_f02.py::test_ac15_static[title_version]" \
           --deselect "tests/test_f02.py::test_ac15_static[manifest_visible_fields_unchanged]";;
    f03on) pyjob f03on "$REPO" tests/f03 test_f03.py "WIZARD on; desel: 1 F04 §8, 1 F04 §1.1, 8 F04 §4" \
           --deselect "test_f03.py::test_ac18_static[title_version]" --deselect "test_f03.py::test_ac10_invite_page_outside_app" \
           --deselect "test_f03.py::test_ac10_landing_valid[fresh-device]" --deselect "test_f03.py::test_ac10_landing_valid[linked-device]" \
           --deselect "test_f03.py::test_ac10_landing_network_error_and_retry" --deselect "test_f03.py::test_ac12_token_not_kept[valid]" \
           --deselect "test_f03.py::test_ac10_invite_link_while_app_open" --deselect "test_f03.py::test_ac10_invite_link_encoded_and_query" \
           --deselect "test_f03.py::test_ac10_invite_via_launch_queue" --deselect "test_f03.py::test_ac17_390_rtl_touch[landing-valid]";;
    f03off) pyjob f03off "$WORK/wiz_off" tests/f03 test_f03.py "WIZARD off copy; desel: 1 F04 §8, 1 F04 §1.1" \
           --deselect "test_f03.py::test_ac18_static[title_version]" --deselect "test_f03.py::test_ac10_invite_page_outside_app";;
    f04) pyjob f04 "$REPO" tests/f04 test_f04.py "desel: 3 superseded by F05, 3 by F06 D1, 1 by F04-HOME C1 (sup_*)" \
           --deselect "test_f04.py::test_c01_gate_button_email_entry" \
           --deselect "test_f04.py::test_c11_c12_done_link_whatsapp_copy" --deselect "test_f04.py::test_c16_join_page_coming_soon_clears_hash" \
           --deselect "test_f04.py::test_n01_no_old_name_rendered[join]" \
           --deselect "test_f04.py::test_c15_more_join_link_row[manager]" --deselect "test_f04.py::test_n01_no_old_name_rendered[more_sheet]" \
           --deselect "test_f04.py::test_n03_whatsapp_text_name_and_url[sheet]";;
    sup_f02_flags_off) pyjob sup_f02_flags_off "$WORK/join_members_off" tests/f02 \
           "tests/test_f02.py::test_ac03_viewer_write_rejected_kept_locally_and_pending" "F05/F06-superseded F02 cases, JOIN+MEMBERS off copy" \
           "tests/test_f02.py::test_ac05_parity_with_v2152_rendering";;
    sup_f04_members) pyjob sup_f04_members "$WORK/members_off" tests/f04 "test_f04.py::test_c15_more_join_link_row[manager]" \
           "F06-superseded F04 cases, MEMBERS_FEATURE=off copy" "test_f04.py::test_n01_no_old_name_rendered[more_sheet]" \
           "test_f04.py::test_n03_whatsapp_text_name_and_url[sheet]";;
    f05) pyjob f05 "$REPO" tests/f05 test_f05.py "desel: 3 superseded by F04-HOME C1 (run in sup_f05_home)" \
           --deselect "test_f05.py::test_a02_app_off_is_alpha51" --deselect "test_f05.py::test_c01_not_connected_screen" \
           --deselect "test_f05.py::test_c07_f04_invite_entry_unchanged";;
    sup_f04_home) pyjob sup_f04_home "$WORK/home_off" tests/f04 "test_f04.py::test_c01_gate_button_email_entry" \
           "F04-HOME-superseded F04 case, HOME_INSTALL_FEATURE=off copy";;
    sup_f05_home) pyjob sup_f05_home "$WORK/home_off" tests/f05 "test_f05.py::test_a02_app_off_is_alpha51" \
           "F04-HOME-superseded F05 cases, HOME_INSTALL_FEATURE=off copy" "test_f05.py::test_c01_not_connected_screen" \
           "test_f05.py::test_c07_f04_invite_entry_unchanged";;
    f06) pyjob f06 "$REPO" tests/f06 test_f06.py "";;
    f20) pyjob f20 "$REPO" tests/f20 test_f20.py "desel: 2 F20 diff rules superseded by F05/F06/F04-HOME" \
           --deselect "test_f20.py::test_st_static[change_comments_cover_hunks]" --deselect "test_f20.py::test_st_static[no_db_or_function_change]";;
    f04h) pyjob f04h "$REPO" tests/f04home test_f04home.py "";;
    static)
      local log="$OUT/static.txt"
      (cd "$REPO" && $PY scripts/dev/f04home_static_check.py ee5c723) >"$log" 2>&1
      local rc=$?
      echo "$([ $rc = 0 ] && echo PASS || echo FAIL)|1|$([ $rc = 0 ] && echo 1 || echo 0)|$([ $rc = 0 ] && echo 0 || echo 1)|0|0|0|f04home_static_check.py ee5c723" >"$OUT/static.res";;
    fn)
      local log="$OUT/fn.txt" P=0 F=0 X=0 rc=0
      : >"$log"
      for spec in "transform tests/f04/function_test.ts" "transform tests/f05/function_test.ts" "transform tests/f06/function_test.ts" \
                  "strip supabase/functions/join-trip/test.ts" "strip supabase/functions/approve-member/test.ts" \
                  "transform supabase/functions/create-trip/test.ts" "transform supabase/functions/invite-manager/test.ts" \
                  "transform supabase/functions/manage-members/test.ts"; do
        set -- $spec
        local one="$WORK/fn_$(echo "$2" | tr '/.' '__').txt"
        (cd "$REPO" && "$NODE" --experimental-$1-types --no-warnings --import "$REPO/tests/f05/deno_shim.mjs" \
            scripts/dev/deno_test_node.mjs "$2") >"$one" 2>&1
        cat "$one" >>"$log"
        local ok fail known
        ok=$(grep -c "^  ok " "$one"); fail=$(grep -c "^  FAIL " "$one"); known=$(grep -A1 "^  FAIL " "$one" | grep -c "KNOWN-BUG")
        P=$((P + ok)); F=$((F + fail - known)); X=$((X + known))
        grep -q "pass$" "$one" || { F=$((F + 1)); echo "  CRASH $2" >>"$log"; }
      done
      echo "$([ $F = 0 ] && echo PASS || echo FAIL)|$((P + F + X))|$P|$F|0|$X|0|8 files (QA F04/F05/F06 + 5 function unit tests)" >"$OUT/fn.res";;
    db)
      local log="$OUT/db.txt"
      if (service postgresql status >/dev/null 2>&1 || service postgresql start >/dev/null 2>&1) && sudo -u postgres psql -Atc "select 1" >/dev/null 2>&1; then
        (cd "$REPO" && $PY tests/f06/db_check.py) >"$log" 2>&1
        # qa.f05_run() rows 100/101 assert the F05 rule "removed → member_removed", replaced on purpose by F06 D2 (removed
        # identities may ask again; docs/qa/F06_QA.md §1) — they run but are counted as superseded, nothing else is ignored
        $PY - "$log" >"$OUT/db.res" <<'PYEOF'
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
SUPERSEDED = {("qa.f05_run", "100"), ("qa.f05_run", "101")}
tot = ok = 0; bad = []; sup = 0; cur = None
for line in t.splitlines():
    m = re.match(r"^(qa\.f0\d_run)\(\): (\d+)/(\d+) pass", line)
    if m:
        cur = m.group(1); ok += int(m.group(2)); tot += int(m.group(3)); continue
    m = re.match(r"^\s+FAIL (\d+) ", line)
    if m and cur:
        if (cur, m.group(1)) in SUPERSEDED: sup += 1
        else: bad.append("%s #%s" % (cur, m.group(1)))
apply_bad = [f for f, st in re.findall(r"^apply (\S+)\s+(\S+)", t, re.M) if st != "OK"]
left = re.search(r"leftover rows after the runs: (\d+)", t)
fails = len(bad) + len(apply_bad) + (0 if left and left.group(1) == "0" else 1)
note = "local PG 0001…0015: %d qa rows; %d superseded (qa.f05 #100/#101 → F06 D2)%s" % (tot, sup, ("; FAILED: " + ", ".join(bad + apply_bad)) if bad or apply_bad else "")
print("%s|%d|%d|%d|0|0|%d|%s" % ("PASS" if fails == 0 and tot else "FAIL", tot, ok, fails, sup, note))
PYEOF
      else
        echo "PostgreSQL could not be started — DB checks skipped" >"$log"
        echo "SKIP|0|0|0|0|0|0|PostgreSQL not available (service postgresql start failed)" >"$OUT/db.res"
      fi;;
    *) echo "unknown job $j"; return 2;;
  esac
}

echo "Lonely Planner full regression · repo $REPO @ $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null) · -j $JOBS · logs $OUT"
echo "expected app version $($PY -c "import json;print(json.load(open('$HERE/qa_versions.json'))['app'])") · BASELINE_DIR=$BASELINE_DIR"
T0=$SECONDS
running=0
for j in $ALL_JOBS; do
  want "$j" || continue
  echo "[$(date +%H:%M:%S)] start $j"
  ( run_job "$j"; echo "[$(date +%H:%M:%S)] done  $j: $(cut -d'|' -f1 "$OUT/$j.res" 2>/dev/null)" ) &
  running=$((running + 1))
  if [ "$running" -ge "$JOBS" ]; then wait -n; running=$((running - 1)); fi
done
wait

# ---------- summary ----------
echo
echo "================ Lonely Planner full regression · summary ($(( (SECONDS - T0) / 60 )) min) ================"
printf '%-18s %-6s %9s %7s %7s %8s %6s %6s  %s\n' job status collected passed failed skipped xfail desel note
RC=0
for j in $ALL_JOBS; do
  want "$j" || continue
  if [ ! -f "$OUT/$j.res" ]; then printf '%-18s %-6s %s\n' "$j" ERROR "no result (see $OUT/$j.txt)"; RC=1; continue; fi
  IFS='|' read -r st c p f s x d note <"$OUT/$j.res"
  printf '%-18s %-6s %9s %7s %7s %8s %6s %6s  %s\n' "$j" "$st" "$c" "$p" "$f" "$s" "$x" "$d" "$note"
  [ "$st" = FAIL ] && RC=1
done
echo
echo "Failures (not deselected, not a known bug):"
FL=$( { grep -hE "^FAILED |^ERROR " "$OUT"/*.txt 2>/dev/null
        awk '/^  FAIL /{f=$0; getline n; if (n !~ /KNOWN-BUG/) print f} /^  CRASH /{print}' "$OUT/fn.txt" 2>/dev/null
        grep -ho "FAILED: .*" "$OUT/db.res" 2>/dev/null | sed 's/^/db /'; } )
if [ -n "$FL" ]; then echo "$FL" | sed 's/^ */  /'; else echo "  none"; fi
echo "Known app bugs / accepted xfails:"
grep -hE "^XFAIL " "$OUT"/*.txt 2>/dev/null | awk '{t=$2; r=$0; sub(/^XFAIL [^ ]+ - /,"",r); if (r ~ /^QA-DEBT-BUG-[0-9]+:/) {split(r,a,":"); print "  " a[1] "  " t} else print "  (other) " t " — " r}' | sort | uniq
grep -h -A1 "^  FAIL " "$OUT/fn.txt" 2>/dev/null | grep -o "KNOWN-BUG [A-Z0-9-]*" | sed 's/^/  /' | sort | uniq
echo "overall rc=$RC"
exit $RC
