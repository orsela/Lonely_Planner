# F10 · QA report — every trip converts in its own currencies (3.0.0-alpha.9)

<!-- CHANGE 2026-11-07 F10-QA-10: new file (no previous version). -->

Implementation tested: `origin/f10` @ **ee26471** (`app/` + `CHANGELOG.md` checked out onto branch `f10-qa`). Suite:
`tests/f10/` (`harness.py`, `test_f10.py`, `run.sh`), written from `docs/F10_spec.md` (8291e7d) **before** the implementation
existed. The pre-implementation run on alpha.8 gave **27 failed / 5 passed**, which confirms the suite tests the feature. The 5
passes were behaviour F10 has to keep: legacy-rate reading in V, the viewer guard, and three server/sw-unchanged checks.
`docs/F10_dev_notes.md` was read only after the implementation landed, to check selectors. No selector needed a dev id, and
no assertion was weakened. There were two test-side fixes (header of `test_f10.py`):
FIX-01 removed `#budgetBurn` from the P9 list because it exists in neither alpha.8 nor alpha.9.
FIX-02 makes the fallback test wipe the cache from the blank page, because the running app page wrote it back.
No Supabase, no network. open.er-api.com and chat-assistant are stubbed, and alpha.8 is read from git `4ca777b`.

Run: `tests/f10/run.sh` (≈3 min). Result on ee26471: **33 collected · 29 passed · 4 failed** (all 4 = F10-BUG-01).

## Per criterion

| # | Criterion | Result | Evidence (tests/f10/test_f10.py) |
|---|---|---|---|
| 1 | V regression vs alpha.8 (P1–P10, totals) | **PASS** | `c01_v_regression_vs_alpha8` runs the same V scenario on `git show 4ca777b:app/index.html` and on alpha.9. All P9 texts (totals 458.5 ₪, tiles, list, detail card, personal, home burn), P2 calc box, P4 result, P5 numbers, P7 preview, P8 and the rate values are identical. The §3-redefined texts are in §3 form: "סכום ב-₫", "חשב לשקלים", P6 "₪ ⇄ ₫". P10 = `{base:'ILS', rates:{USD:3.6,EUR:3.9,VND:0.00014}, home, local}`. `c01_v_defaults_and_order`: VND ₪ $ € with VND rightmost, P1/P7 default VND, P4/P5 VND→ILS, `__PT.tripcur` as §1. `c01_v_new_expense_shape`: amount 14 ₪ + `homeCurrency:'ILS'` + originals; an ILS expense has no originals; old expenses are not rewritten |
| 2 | T: THB defaults, P6 "₪ ⇄ ฿", P3 THB/USD/EUR, no VND | **PASS** | `c02_thailand` (also: result uses ฿/₪, "הוסף כהוצאה" when target = home, live in-memory rate). `c02_live_defaults_label`: "שערים חיים · לא נשמרו", exactly 1 er-api call, nothing written |
| 3 | A: all P9 in $, no ₪ except marker; "חשב לדולרים"; AED expense in USD | **PASS** | `c03_uae_dollars_everywhere` (totals with the old ₪ expense at 0.27 and its "(₪ מקורי)" marker, detail cards, home widget, P8 "עלות ($ / AED)", P6 "$ ⇄ AED"). `c03_uae_aed_expense_saved_in_usd`: form 200 AED → 54.46 USD + `homeCurrency:'USD'` + `originalCurrency:'AED'`; quick card too |
| 4 | G: local EUR, € ₪ $, P6 "₪ ⇄ €" | **PASS** | `c04_greece` |
| 5 | S: 5 + "עוד", lists EUR, pick → 5th slot; VND/KHR per 1,000 | **FAIL** (visual only) — F10-BUG-01 | `c05_s_five_plus_more[P1,P4,P5,P7]`: order, `aria-label="עוד 1 מטבעות: €"`, sheet, pick → EUR selected in the 5th slot all pass. The **dashed border** (§3) does not render. `c05_s_units_per_1000` PASS ("1,000 VND", "1,000 KHR", calc 100,000 VND whole units) |
| 6 | Save writes v2 + legacy; alpha.8 reads it; live fetch homePerUnit (AED ≈ 0.2723) | **PASS** | `c06_save_writes_v2_and_legacy_and_alpha8_reads_it`: object has `v:2, base:'ILS', rates{…per unit}, updatedAt, source` and top-level USD/EUR/VND (per 1,000), and alpha.8 shows 3.55/3.95/0.142. `c06_legacy_object_read_as_v2`. `c06_live_fetch_home_per_unit_uae`: 1 call to `https://open.er-api.com/v6/latest/USD`, AED 0.2723, ILS 1/3.7, EUR 1/0.92 |
| 7 | Missing rate offline (A): "אין שער", conversion disabled, no exception | **PASS** | `c07_missing_rate_offline_uae` (P3 row, P1/P2 message "אין שער ל-AED – עדכנו שערים בתקציב", no save, P7 no preview, P5 no result, 0 page errors) |
| 8 | Offline reload → TRIPCUR from cache, same chips/symbols | **PASS** | `c08_offline_tripcur_from_cache` (`pt:<trip>:tripcur`, identical rows / P6 / P8; sw.js does not precache the JSON). `c08_fallback_no_cache_no_network`: VND ILS USD EUR / local VND |
| 9 | T → A via F20 switcher rebuilds rows; picks per trip | **PASS** | `c09_switch_trip_rebuilds_rows_picks_per_trip` (`pt:<T>:planner:lastExpenseCurrency`=USD / `…:qe:cur`=ILS kept, A defaults AED, back in T = USD/ILS). `c09_remembered_code_not_in_list_falls_back` |
| 10 | Viewer converts; "שמור שערים" blocked ("צפייה בלבד") | **PASS** | `c10_viewer_converts_but_cannot_save_rates` (trip_kv `fxrates` unchanged) |
| 11 | Flag off: budget / FX sheet / quick expense DOM = alpha.8 (V, T) | **PASS** | `c11_flag_off_dom_equals_alpha8[V,T]` (full DOM signature: tags, ids, classes, data-*, aria, placeholders, visibility, own text). `c11_flag_off_behaviour_equals_alpha8`: the whole V P1–P10 capture plus chat fx is identical, and `__PT.tripcur` is null when the flag is off |
| 12 | 390px: no h-scroll (budget, FX sheet, "עוד" sheet); chips ≥44px; RTL | **PASS** | `c12_390_layout` (S fixture: P1/P4/P5/P7 chips and "עוד" sheet chips ≥44px, all rows `direction:rtl`, sheet inside 390px) |
| 13 | No server change | **PASS** (advisors: not run, see below) | `c13_static[no_migration_or_function_change]`: `git diff 4ca777b -- supabase` empty; also `app/sw.js`, `manifest.json`, `countries.json`, `currencies.json`, `/join/`, `/invite/`, `/request/` unchanged. `csp_unchanged`: CSP meta identical, no new https origin. `versions`, `flag`, `changelog`, `change_comments`, `sw_precache` |
| 14 | 📱 phone check | not automated | Or's Android phone |

## Bugs

### F10-BUG-01 · "עוד" chip is not dashed (low, visual)
- Steps: trip S (ILS; TH VN KH; 6 currencies) → budget tab (any of P1/P4/P5/P7) → look at the last chip "עוד €".
- Expected (§3 / D5 mockup): "a "עוד" chip (**dashed**, label "עוד" and the hidden symbols underneath …)".
- Actual: `getComputedStyle(chip).borderStyle === 'solid'` in all four rows. Cause: the F10 rule
  `.curchip.f10-more,.qe-chip.f10-more{border-style:dashed}` (specificity 0,2,0) loses to the UI-kit rules
  `html.ui-kit .curchip{border:1.5px solid …}` and `html.ui-kit .res-chip,html.ui-kit .qe-chip,…{border:1.5px solid …}`
  (0,2,1). The UI kit is on by default (`UI_KIT='on'`). This is the CSS-specificity gotcha already known in this project.
  Fix suggestion: prefix the F10 rule with `html.ui-kit` too, or put it after the kit with ≥0,2,1 specificity.
- Everything else about "עוד" works: order, aria-label, sheet, pick into the 5th slot, ≥44px, no overflow.

### F10-NOTE-01 · three changed lines without their own CHANGE comment (info)
`git diff -U0 4ca777b` has 45 hunks. Three of them (renderBudget's `#catChips` tile line, `expenseRows`, the detail table row,
≈ lines 7075/7083/7088) carry no `F10-…` tag on or next to the line. They are covered only by the block comment F10-P9-05
a few lines above. §5 asks that "every changed line carries `CHANGE … F10-<AREA>-NN: was …`". This is a documentation rule,
not a behaviour bug.

## Regression (tests/run_all.sh on ee26471, -j 2, offline, `QA_EXPECTED_VERSION=3.0.0-alpha.9`)

| Job | alpha.8 tree (before) | alpha.9 tree (F10) |
|---|---|---|
| f02, f03on, f03off, f04, f04h, f05, f06, f20, f21 | PASS (f03off not run) | **PASS** (same counts: f04 118, f05 87, f20 76, f03on 48, f03off 56, f02 33, f04h 90+1 xfail, f06 70, f21 101) |
| sup_f02_flags_off, sup_f04_members, sup_f04_home, sup_f05_home, sup_f20_req_off | — | **PASS** |
| fn (181 function tests) | — | PASS (1 known xfail F05-QA-D1, server side, unrelated) |
| static (`scripts/dev/f21_static_check.py`) | PASS | **FAIL, expected**. This is the F21 release check. It pins alpha.8 → 313eb14 rules ("existing lines changed must be only PT/APP_VERSION", "was 3.0.0-alpha.7.2" comments), so any later feature trips it. Its F10-independent parts still pass: node --check on all 11 scripts, no new duplicate ids, the 7 protected v2.15.2 functions byte-identical, F21 hook lines gated, sw.js unchanged. It needs an F10 successor (dev side) |
| db / db21 (local PostgreSQL) | not run | not run: F10 has no migration (C13 shows `supabase/` is unchanged), so the DB layer is identical to alpha.8 |

## Not testable here / left open
- C13 "Supabase advisors unchanged": not run, because supabase.co is unreachable. It is implied by the unchanged
  `supabase/` tree, and the live project is untouched.
- C14: phone check (Or).
- The real er-api / real network latency (stubbed payload). Real `countries.json` / `currencies.json` are served same-origin.
- Spec looseness, as read by the suite: criterion 1 says "every text equals alpha.8 except chip order", but §3 redefines some
  V texts (P2 placeholder "סכום ב-₫", P6 "₪ ⇄ ₫", P1/P5 defaults = local VND, P10 shape). The suite asserts the §3 form for
  those and byte-equality for everything §3 does not name. P5 wording: §3 says "הוספה כהוצאה" while alpha.8/alpha.9 say
  "➕ הוסף כהוצאה", and the suite accepts both (an unchanged alpha.8 text cannot be a regression).
