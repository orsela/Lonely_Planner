# F21 · Independent QA suite — "anyone can request a trip; the super-admin approves" (3.0.0-alpha.8 / functions alpha.8.0)

<!-- CHANGE 2026-10-30 F21-QA-09: new file (no previous version). -->

Contract: `docs/F21_spec.md` (§0–§8, criteria §6 = 20 items) **only**. Not read: `app/index.html` / `request/index.html`
logic, `supabase/functions/**/*.ts` bodies, `0016_f21.sql` / `0017_qa_f21_harness.sql` bodies, `docs/F21_dev_notes_*.md`,
`scripts/dev/f21_*`. Used as black boxes: the pages (served, run in Chromium), the functions' exported surface (`export`
lines and exported interfaces only — `handler`, `setDeps({rpc, sendMail, fetch, now, random, uuid, env})`, `makeHandler(deps)`
…), the SQL functions / tables of spec §2 on a local PostgreSQL, the localStorage keys of §1, and the top-level constants the
brief names (`REQUEST_FEATURE`, `TURNSTILE_SITE_KEY`). Element ids on `/request/` (`#rqName` … `#rqOtp0…5`) were **observed in
the rendered DOM**, not read from source.

## Files

| File | What | Cases |
|---|---|---|
| `harness.py` | Extends the F04-HOME harness (→ F06 → F05 → F20 → F04 → F03 → F02). Adds an in-memory `request-trip` (§3.1/§4), `rpc('admin_trip_requests')`, invite-manager `approve_request` / `reject_request` (§3.2), create-trip `lookup.prefill` (§3.3), a fake Cloudflare Turnstile `api.js` with the documented test keys (`1x00000000000000000000AA` pass → `XXXX.DUMMY.TOKEN.XXXX`, `2x00000000000000000000AB` fail → error-callback), `serve_request()` rewriting `TURNSTILE_SITE_KEY` (the real key only works on orsela.github.io) and flipping `REQUEST_FEATURE`, `serve_app_request()`, devices with an `en-US` locale / custom `navigator.languages`. | — |
| `test_f21.py` | Playwright 390×844, both languages, both flag states, route-intercepted Edge Functions. | see `pytest --collect-only` |
| `function_test.ts` | request-trip (RT-*), invite-manager F21 actions (IMR-*), create-trip prefill (CTP-*), stubs for RPC / SMTP / siteverify. The Hebrew invite mail is compared byte for byte with the alpha.7.2 invite-manager read from git (313eb14). | 33 |
| `integration_test.ts` | The three real handlers with `rpc` executed as `service_role` on a local DB built from 0001…0017 (INT-*). | 10 |
| `db_test.py` | Local PostgreSQL: shim + 0001…0015, snapshot, 0016 + 0017, snapshot diff; `qa.f01–f06_run()` + `qa.f21_run()`; own scenarios DB-* (§2 schema, constraints, grants/RLS, limits, cap + C3 day, D12, undo, reject, D5/C5 cleanup, admin list, prefill, criterion 17). | 67 + harness rows |
| `run.sh` | `--only browser | fn | db | int`. | — |

## How to run

```bash
service postgresql start
tests/f21/run.sh                 # everything (≈10 min)
tests/f21/run.sh --only fn       # node --experimental-transform-types … scripts/dev/deno_test_node.mjs tests/f21/function_test.ts
tests/f21/run.sh --only db       # python3 tests/f21/db_test.py   (--keep keeps the scratch DB pt_f21_qa)
tests/f21/run.sh --only int
tests/f21/run.sh --only browser  # REPO_DIR / APP_DIR / QA_HEADFUL=1 as in the other suites
tests/run_all.sh --only "f21 sup_f20_req_off db21 fn"
```

## Criteria → tests

| # | Tests |
|---|---|
| 1 | `test_c01_request_off_closed_card_no_network[he,en]`, `test_c01_app_off_is_alpha72_chooser`; regression: run_all `sup_f20_req_off` (F20 cases on a REQUEST_FEATURE='off' copy) + every older suite |
| 2 | `test_c02_lang_en_from_link[query,hash]`, `test_c02_lang_from_device[he,en]`, `test_c02_lang_hebrew_tag_not_first`, `test_c02_switch_keeps_values_flips_dir_stores` |
| 3 | `test_c03_iphone_inapp_safari_button[gmail_ios,outlook_ios]`, `test_c03_android_inapp_one_intent_hop`, `test_c03_real_browser_no_card[3]` |
| 4 | `test_c04_validation_inline_no_call[6]`, `…countries_max_10_and_chip_remove`, `…month_options_18_and_unsure`, `…travellers_bounds`, `…note_counter_and_d11a_box`, `…email_normalized_ltr`; RT-08; DB-06, DB-11 |
| 5 | `test_c05_*` (3); RT-02…07, RT-16; INT-01, INT-03; DB-10 |
| 6 | `test_c06_*` (5); RT-11, RT-12; INT-01, INT-04; DB-12, DB-20…22, DB-30…32 |
| 7 | `test_c07_*` (4) |
| 8 | `test_c08_rate_limited_toast[he,en]`; RT-09; INT-05; DB-13, DB-14, DB-15, DB-23 |
| 9 | `test_c09_*` (4), `test_c15_reject_at_cap`, `test_c15_capped_toast`; RT-09, IMR-09; INT-06; DB-15…17, DB-32, DB-52, DB-53 |
| 10 | RT-10, INT-02 (C4 is a server property; the browser sees the same code screen) |
| 11 | `test_c11_*` (4); DB-70…73 |
| 12 | `test_c12_approve_sheet_and_send[he,en]`; IMR-02…04, IMR-07, IMR-10, IMR-11; INT-07; DB-40, DB-41 |
| 13 | `test_c13_approve_replace_sheet`; IMR-06; INT-07; DB-42 |
| 14 | `test_c14_approve_errors[2]`; IMR-05; INT-08; DB-43, DB-44 |
| 15 | `test_c15_reject_sheet[3]`; IMR-08, IMR-09; INT-09; DB-50…54, DB-60…62 |
| 16 | `test_c16_*` (3); CTP-01…03; INT-10; DB-80, DB-04.find_unchanged |
| 17 | DB-01…05, DB-70, DB-81, DB-82, DB-99; IMR-01, IMR-12; RT-01, RT-13, RT-14 |
| 18 | `test_c18_request_390_layout[6 screens × he,en]`, `test_c18_app_390[4]` |
| 19 | `test_c19_offline_and_other_error[2]`, `test_c19_admin_requests_offline` |
| 20 | `test_c20_static[15]`, `test_c20_runtime_duplicate_ids`; RT-00, RT-15, IMR-00; advisors → manual |

## Known limits (offline)
- The real Turnstile widget and Cloudflare `siteverify` are unreachable: the browser uses a fake `api.js` with the documented
  test-key behaviour; the function tests stub `siteverify`. Real widget → phone check.
- Real SMTP / Gmail rendering, the notification autofill of the code, and WhatsApp in-app behaviour → phone check.
- Supabase advisors → dashboard.
