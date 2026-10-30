# F21 · QA report — request a trip, super-admin approves (3.0.0-alpha.8 / functions alpha.8.0)

<!-- CHANGE 2026-10-30 F21-QA-10: new file (no previous version). -->

Implementation tested: branch `f21` @ **1776a3d** (app alpha.8, `/request/`, migrations 0016/0017, request-trip /
invite-manager / create-trip alpha.8.0). The later commits on `f21` (37432e0 … e38193c) are only checkpoints of this QA work
(tests/ + docs/qa/). Suite: `tests/f21/` (README there). Written from `docs/F21_spec.md` only. Not read: app / `/request/`
logic, function sources (only `export` lines and exported interfaces), 0016/0017 bodies, F21 dev notes, `scripts/dev/f21_*`
(run as black boxes by the `static` job only). No Supabase, no network.

## Results

| Suite | Collected | Passed | Failed | Skip / xfail |
|---|---|---|---|---|
| Browser `test_f21.py` (Playwright 390×844, he/en, flags on/off) | 102 | 100 | 1 (F21-QA-BUG-01) | 1 skip (advisors) |
| Functions `function_test.ts` (RT/IMR/CTP, stubs) | 33 | 33 | 0 | — |
| Integration `integration_test.ts` (real handlers ↔ local PG 0001…0017) | 10 | 10 | 0 | — |
| DB `db_test.py` own scenarios DB-* | 67 | 67 | 0 | — |
| DB harnesses on 0001…0017: qa.f01/f02/f03/f04/f05/f06/f21_run() | 109/37/49/90/120/171/101 | all except 4 superseded | 0 | f05 #100/#101 (F06 D2), f06 #910/#911 (F21 §2) |
| Dev function unit tests (run, black box): request-trip/test.ts, invite-manager/test.ts + test_f21.ts, create-trip/test.ts + test_f21.ts | 14/21/14/9/4 | all | 0 | — |

## Per criterion

| # | Criterion | Result | Where |
|---|---|---|---|
| 1 | Flags off = alpha.7.2; `/request/` off = closed card, no network | **pass** | c01 ×3; run_all `sup_f20_req_off` 4/4; all older suites green (version pins only) |
| 2 | Language: ?lang / #lang, device, switch keeps values, remembered | **pass** | c02 ×6 |
| 3 | In-app: iPhone Safari button URL, Android single intent hop, continue here | **pass** | c03 ×6 |
| 4 | Validation bounds inline, no call; D11a box EN only | **pass** | c04 ×11, RT-08, DB-06, DB-11 |
| 5 | Turnstile pass/fail; row unverified + one code mail in page language, code in subject, no link | **pass** (fake widget, see manual) | c05 ×4, RT-02…07, INT-01/03, DB-10 |
| 6 | Verify / wrong / locked / expired / resend rules | **FAIL** — F21-QA-BUG-01 (retyping after one wrong code locks the request); rest pass | c06 ×6, RT-11/12, INT-01/04, DB-12/20–22/30–32 |
| 7 | Resume: reload ≤10 min → code screen + banner, no send; key cleared; never holds the code | **pass** | c07 ×4 |
| 8 | Limits 4th start per email, 11th per IP, 21st wrong verify per IP/h | **pass** | c08 ×2, RT-09, INT-05, DB-13/14/15/23 |
| 9 | Cap 50: start/resend → 1.4 (never on load); reject → mail_skipped; F03 create/approval still send | **pass** | c09 ×5, c15 cap ×2, IMR-09, INT-06, DB-16/17/32/52/53 |
| 10 | C4 identical start response for a manager's email | **pass** | RT-10, INT-02 (real DB, manager + active invite) |
| 11 | Admin tab, list, markers, button rule, meter, chooser badges | **pass** | c11 ×5, DB-70…73 |
| 12 | Approve: invite with request_id/lang/edited name; HE mail byte-identical to alpha.7.2, EN template; /invite/ link | **pass** | c12 ×2, IMR-02…04/07/10/11, INT-07, DB-40/41 |
| 13 | D12 replace: old revoked, one active invite | **pass** | c13, IMR-06, INT-07, DB-42 |
| 14 | Email failure on approve → nothing changed | **pass** | c14 ×2, IMR-05, INT-08, DB-43/44 |
| 15 | Reject with/without mail, language; 5-day cleanup; pending kept | **pass** | c15 ×5, IMR-08/09, INT-09, DB-50…54, DB-60…62 |
| 16 | Wizard pre-fill; without request = today | **pass** | c16 ×3, CTP-01…03, INT-10, DB-80, DB-04.find_unchanged |
| 17 | Security: private tables, admin RPC, admin actions, no new grants/policies, logs | **pass** | DB-01…05/70/81/82/99, IMR-01/12, RT-01/13/14 |
| 18 | 390px, RTL/LTR, touch ≥44, emails/codes/URLs LTR | **pass** (offline layout) | c18 ×16 |
| 19 | Offline: /request/ toast keeps values; admin as F03 | **pass** | c19 ×3 |
| 20 | Protected functions, versions, CHANGE markers, node --check, ids; advisors | **pass**; advisors **manual** | c20 ×17 + runtime ids, RT-00/15, IMR-00 |

## Bugs

| Id | Crit. | Severity | Steps | Expected (spec) | Actual |
|---|---|---|---|---|---|
| **F21-QA-BUG-01** | 6 | **High** | `/request/` → send → code screen. Type a wrong code (auto-submits → "הקוד שגוי. נשארו 4 ניסיונות."). Tap the first box and type the right 6 digits on the keyboard. | §1.3/§4: one more verify with the typed code → "הבקשה נשלחה"; `code_locked` only after 5 real wrong codes. | The six boxes keep the wrong digits after `code_wrong`; every keystroke in a full row auto-submits a mixed 6-digit code → 4 more `code_wrong` → `code_locked` → the request is deleted and the user is thrown back to the form ("יותר מדי ניסיונות. מתחילים מחדש."). With focus left on the last box, typing does nothing (boxes stay full). Paste/autofill of a full code still works. Test: `test_c06_retype_after_wrong_code` (verify sequence `code_wrong ×5 → code_locked`). Likely fix: clear the boxes (or stop auto-submit until all six are re-entered) after `code_wrong` / `code_expired`. Confirm on the phone. |

No other implementation defects found. Observations (no action needed unless Or disagrees):
- O1 `private.mail_log` has an extra `request_id` column (spec lists `id, kind, at`); used to remove the code-mail row with a
  failed request (§3.1). O2 extra service-role function `public.request_mail_failed(uuid,text)` (not named in §2.6; grants
  correct). O3 `request_approve` additionally refuses a non-admin `p_admin` (`not_platform_admin`) — stricter, fine.
- O4 request-trip accepts lower-case country codes and upper-cases them before the DB; sends `month` as `YYYY-MM` to SQL,
  stored as the 1st (INT-01).

## Ambiguities (my reading → what was tested)
- A1 §1.2 failing Turnstile key: the widget never yields a token (Cloudflare "always blocks"). Tested: no row, no mail, no
  code screen (the page may block client-side or the server answers `turnstile_failed`). Server-side `turnstile_failed`
  → toast + widget reset tested by forcing siteverify to fail.
- A2 §4 resend cooldown error code is not named; the server answers `rate_limited` (+`retry_in`). Tested as "refused, no mail".
- A3 §1.3 "הקוד שגוי. נשארו N ניסיונות." — for N=1 the page says "נשאר ניסיון אחד." (correct Hebrew singular). Accepted.
- A4 §1.2 month with neither a month nor "עוד לא יודעים" → treated as an inline error on the select (the page does so).
- A5 §1.1 "x-safari-https://<host>/…/request/?lang=<l>" — tested exact URL `x-safari-https://<host>/Lonely_Planner/request/?lang=he`.
- A6 C5 "every request-trip call runs cleanup": tested at the SQL layer (request_start/verify/resend each remove a 6-day-old
  rejected row, DB-62) and via `admin_trip_requests` (DB-61).
- A7 `/request/` ids are rendered per screen from templates (one `#rqTitle` per screen): static markup + every rendered screen
  are duplicate-free; the template source naturally repeats ids.

## Regression (`tests/run_all.sh -j 2`, 21 min, then f04h/static/f21 re-run after the edits below)

| Job | Status | Collected | Passed | Failed | Skip | xfail | Desel |
|---|---|---|---|---|---|---|---|
| f04 | PASS | 126 | 118 | 0 | 1 | 0 | 7 |
| f05 | PASS | 91 | 87 | 0 | 1 | 0 | 3 |
| f20 | PASS | 82 | 76 | 0 | 0 | 0 | 6 (2 old + **4 F21 §1.6**) |
| f03on / f03off | PASS | 59 / 59 | 48 / 56 | 0 | 1 / 1 | 0 | 10 / 2 |
| f02 | PASS | 40 | 33 | 0 | 3 | 0 | 4 |
| f04h (re-run) | PASS | 93 | 90 | 0 | 1 | 1 (known ambiguity F4H-09e[exit]) | **1 version pin** |
| f06 | PASS | 70 | 70 | 0 | 0 | 0 | 0 |
| **f21** (new; re-run identical) | FAIL (BUG-01 only) | 102 | 100 | 1 | 1 | 0 | 0 |
| sup_f02_flags_off / sup_f04_members / sup_f04_home / sup_f05_home | PASS | 2/3/1/3 | all | 0 | 1/0/0/0 | 0 | 0 |
| **sup_f20_req_off** (new) | PASS | 4 | 4 | 0 | 0 | 0 | 0 |
| fn (+4 F21 files) | PASS | 181 | 180 | 0 | 0 | 1 (KNOWN-BUG F05-QA-D1) | 0 |
| static (re-run) | PASS (was FAIL: pinned to alpha.7.2 `fix772_static_check.py`; now the F21 dev checks) | 1 | 1 | 0 | 0 | 0 | 0 |
| db (0001…0015) | PASS | 576 | 574 | 0 | 0 | 0 | 2 superseded |
| **db21** (new: 0001…0017 + scenarios + integration) | PASS | 754 | 746 | 0 | 0 | 0 | 4 superseded |

Regression edits (all marked `CHANGE 2026-10-30 F21-QA-NN`):
- `tests/run_all.sh` 1.0.1 → 1.1.0 (F21-QA-08): jobs `f21`, `sup_f20_req_off` (REQUEST_FEATURE='off' copy of app/), `db21`;
  `fn` + `tests/f21/function_test.ts`, `request-trip/test.ts`, `invite-manager/test_f21.ts`, `create-trip/test_f21.ts`;
  f20 deselects `test_b01_superadmin_online_sees_chooser_no_trip_started`, `test_c01_chooser_rows_order_content_flags_last_badge`,
  `test_c02_pending_badge[two]`, `test_d01_network_reads_only_spec_tables` (F21 §1.6 texts + new RPC; they pass in
  `sup_f20_req_off`; new texts tested by `test_c11_chooser_badges*`); f04h deselects `test_f4h_13_static[invite_version_comment]`
  (version pin: /invite/ is untouched by F21; now `test_c20_static[invite_unchanged]`); `static` runs
  `scripts/dev/f21_static_check.py` + `f21_request_static_check.py` (both pass when run alone); `db21` counts qa.f06 #910/#911
  as superseded by F21 §2 (exact contents of schema `private`), now `DB-03.private` / `DB-03.private_fn`. The 0015 harness
  itself was not edited (it lives under `supabase/`).
- `tests/f04/function_test.ts` 1.1.0 → 1.1.1 (F21-QA-06): CT-00, IM-00, NAME-02, NAME-03 read `tests/qa_versions.json`.

## Manual / phone checklist (Or — Android / Chrome only)
1. Real Cloudflare Turnstile on orsela.github.io (managed widget, Hebrew and English labels; site key in `/request/`;
   `TURNSTILE_SECRET` set) — offline runs used a fake widget with the test keys.
2. **BUG-01 on the phone:** type a wrong code, then the right one by keyboard → does it lock? (and with the notification
   autofill / paste → should succeed).
3. Open `/request/` from WhatsApp (Android in-app) → automatic Chrome hop once; "להמשיך כאן בכל זאת" works inside WhatsApp.
4. Hebrew request with a second address → code email: subject "<6 digits> – קוד האימות לבקשה ב-Lonely Planner", no link,
   RTL; code from the Gmail notification; switch to Gmail and back → resume banner, no second mail.
5. Chooser "1 בקשות חדשות" + "N הזמנות ממתינות"; requests tab, meter count; approve → Hebrew invite mail identical to the
   F03 invite → `/invite/` → wizard pre-filled (box, name, "מהבקשה", picker on the month, step 2 countries + currencies).
6. English run with another address → English code mail (LTR) → reject with mail → English reject mail, no link.
7. Approve for an email with an active invite → old link shows "invalid" in `/invite/`, new link works.
8. Mail rendering in Gmail Android (RTL/LTR, monospace code, button) — not checkable offline. The daily cap and the 5-day
   cleanup only offline (DB tests).
9. Supabase advisors after running 0016 / 0017 (criterion 20).

Overall: every job green except `f21`, whose only failure is F21-QA-BUG-01.

## Architect addendum (2026-10-30)
- **F21-QA-BUG-01 fixed** in `request/index.html` (CHANGE F21-REQ-05): after `code_wrong` / `code_expired` the six boxes are
  emptied and the first box is focused. Re-run on the fix: `tests/f21/test_f21.py` **101 passed, 1 skipped** (advisors,
  manual); dev checks `/request/` static 30/30, smoke 130/130.
- Deployed so far: migration 0016 + 0017 on `plan-travel` (`qa.f21_run()` 101/101 live; f01–f04 all pass, f05 #100/101 and
  f06 #910/911 superseded as expected; no F21 rows left behind), Edge Function `request-trip` v1 (alpha.8.0).
