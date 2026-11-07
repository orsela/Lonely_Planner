# F10b QA report: trip currencies screen (add / swap / remove, cap 10)

<!-- version 1.0.0 · CHANGE 2026-11-07 F10B-QA-04: new file (no previous version). -->

Tree under test: branch `f10b`, app commit 04c36dd (3.0.0-alpha.10). Base: main 43394ff (alpha.9). Contract: docs/F10b_spec.md only.
The F10B blocks of app/index.html and docs/F10b_dev_notes.md were **not** read. UI was found only through the ids and texts that the spec names.
Suite: `tests/f10b/run.sh` (tests/f10b/test_f10b.py + harness.py). The harness emulates the spec §0 server facts: cap 10 → `currency_limit` 23514,
base lock → `base_currency_locked` 23514, duplicate → 23505, managers-only RLS, PK-changing UPDATE. It also logs every write request (POST/PATCH/DELETE + body + filters)
and can inject one-shot errors.

Result: **21 passed, 2 failed** (23 tests, ≈2.5 min).

| # | Criterion | Result | Test(s) |
|---|---|---|---|
| 1 | "עוד" row "6 מתוך 10" (manager + editor), 3 base "קבוע" + 3 others in sort order | PASS | test_c01_more_row_and_list[manager], [editor] |
| 2 | Quick FX link closes the sheet and opens the screen | PASS | test_c02_quick_fx_link |
| 3 | E: GBP suggested → insert {GBP, destination, sort 3}; TRIPCUR local GBP; £ chip; toast; "4 מתוך 10" | PASS | test_c03_england_add_gbp |
| 4 | Search "ין" / "JPY" / "יפן" (+ case / English) finds JPY; codes in trip disabled "כבר בטיול" | PASS (behaviour) / **FAIL** (sheet id) | test_c04_search_and_disabled · test_c04_sheet_ids → F10B-BUG-01 |
| 5 | Non-country code → kind 'added', last in TRIPCUR.list | PASS | test_c05_added_kind_last |
| 6 | F 10/10: LAK → swap lists the 7 non-base; KHR → exactly 1 PATCH, no POST/DELETE; 10 stays; KHR gone from P1/P4/P5/P7 | PASS | test_c06_full_swap_lak_for_khr |
| 7 | ⋯ → swap THB → JPY, one PATCH, no second list | PASS | test_c07_row_swap_thb_jpy |
| 8 | ⋯ → remove KHR with 3 KHR expenses: alert text, one DELETE, expenses byte-identical, count 5 (+ k=0 text, cancel = no write) | PASS | test_c08_remove_khr_keeps_expenses, test_c08_remove_alert_without_expenses |
| 9 | Base rows have no ⋯; swap list never offers a base | PASS | test_c09_base_rows_no_actions |
| 10 | Editor / viewer: no ⋯, no add, #ptF10bRO, no write | PASS | test_c10_read_only_roles[editor], [viewer] |
| 11 | Offline manager: cache list, #ptF10bOff, add disabled, no ⋯; online → actions return | PASS | test_c11_offline_manager |
| 12 | Errors → §7 texts, list reloaded, no exception | PASS ×4 / **FAIL** ×1 | test_c12_errors[currency_limit, dup, network, base] PASS · [rls403] FAIL → F10B-BUG-02 |
| 13 | Saved v2 without GBP → rates.GBP added (stubbed er-api, 1 call), other keys untouched; £→₪ works without reload | PASS | test_c13_rate_added_to_saved_object |
| 14 | Flag off: no F10b ids; DOM of "עוד" + FX sheet equals alpha.9 | PASS | test_c14_flag_off_equals_alpha9 |
| 15 | 390 px: no h-scroll, controls ≥44 px, RTL (screen, row sheet, alert, picker, swap) | PASS | test_c15_layout_390 |
| 16 | Regression: F10 suite with QA_EXPECTED_VERSION=3.0.0-alpha.10 | 32/33 (failure is in the test, not the app) | tests/f10/run.sh — see note |
| 17 | 📱 phone | not run (manual) | — |

Note on 16: the only F10 failure is `test_c13_static[versions]`. It asserts `APP_VERSION == '3.0.0-alpha.9'`, which is hardcoded in
tests/f10/test_f10.py (`VERSION = "3.0.0-alpha.9"`) and does not read QA_EXPECTED_VERSION. That is expected after a version bump and is debt in the F10 suite,
not an app bug. Running F10 also needed the alpha.8 base commit 4ca777b, which the shallow clone did not have, so it was fetched (`git fetch --deepen`).
`tests/run_all.sh` was not run, to save compute.

## Bugs

### F10B-BUG-01: the picker sheet has no `#ptF10bPicker` id
- Steps: S trip (or F), manager → "עוד" → "💱 מטבעות" → "+ הוספת מטבע".
- Expected (§4): the sheet is `#ptF10bPicker`.
- Actual: the sheet opens inside a generic `#ptF10bLayer` (`div.p10-sheet[role=dialog]`, aria-label "הוספת מטבע") and the dialog has no id.
  `#ptF10bSearch`, `#ptF10bConfirm` and all picker behaviour are correct. The other sheets do carry their spec ids (`#ptF10bRowSheet`, `#ptF10bRemove`, `#ptF10bSwap`).
  Minor (the id contract). The suite falls back to "the dialog containing #ptF10bSearch" so the behaviour could still be tested.

### F10B-BUG-02: a 403 (role changed) does not repaint the screen as read-only
- Steps: S trip, device is manager, screen open. On the server the member's role becomes editor, so RLS refuses the insert with 42501 / HTTP 403.
  Then "+ הוספת מטבע" → JPY → confirm.
- Expected (§7): message "רק מנהל הטיול יכול לשנות מטבעות", **and repaint as read-only** (no ⋯, no #ptF10bAdd; #ptF10bRO per §3 Roles).
- Actual: the message is shown, the list is reloaded and nothing is written, but the screen still shows the ⋯ buttons on THB/VND/KHR and the add button (checked 4 s after the error).
  Reproduced on 3 runs (first with an injected 403, then twice with a real role change in the fake backend).

## Not testable here
- Real Postgres triggers / RLS (§0): emulated in tests/f10b/harness.py F10bBackend. The live DB was not touched.
- Two managers editing at the same time, for real: emulated by injecting `currency_limit` / 23505.
- Criterion 17 (Or's Android phone) and the "שמור" on a real er-api: er-api is stubbed.
- A forced DELETE/PATCH of a base row from outside the UI (criterion 9 only covers that the UI offers none). The server-side lock is emulated, and an injected
  `base_currency_locked` shows "מטבע בסיס קבוע" (PASS).

## Re-run after fix (2026-11-07, architect)
<!-- CHANGE 2026-11-07 F10B-QA-FIX-02: new section. -->
- F10B-BUG-01 fixed (`F10B-BUG-01`: the picker dialog has id `#ptF10bPicker`). F10B-BUG-02 fixed (`F10B-BUG-02`: after a
  401/403/RLS refusal the screen repaints read-only until reload).
- `tests/f10b/run.sh -k "c04 or c12"`: **7 passed / 0 failed** → suite 23/23.
- `tests/f10/test_f10.py` VERSION now reads `QA_EXPECTED_VERSION` (default 3.0.0-alpha.10) — the F10 32/33 failure was this pin.
