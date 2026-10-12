# F04 · QA report — an invited manager sets up a trip in three steps

Version: app 3.0.0-alpha.4 · create-trip 3.0.0-alpha.4.0 · invite-manager alpha.4.0 · DB 0010/0011 · QA suite 1.1.0 · 2026-10-12.
CHANGE 2026-10-12 F04-QA-03: first version of this report (covers the spec changes F04-DB-02 `tripname` and F04-INV-02 /invite/ note).

## Automated
Branch `f04` @ 5cdcf2d, sandbox only (no Supabase, no network services). Browser suites: Playwright 390×844, written by the QA team from the spec only.

| Suite | Result |
|---|---|
| F04 browser suite (tests/f04/test_f04.py 1.1.0, `run.sh --only f04`) | 85/85 (83 earlier + 2 new: `test_c11_tripname_shown_home_and_settings[v1\|v2]`) |
| F03 regression, WIZARD_FEATURE=on (run.sh deselection, spec §5.19) | 47 passed, 1 skipped (DB/function-level pointer), 11 deselected |
| F03 regression, WIZARD_FEATURE=off | 55 passed, 1 skipped, 3 deselected |
| F03 raw (no deselection), on / off | 47 + 11 failed / 55 + 3 failed: all expected by spec (below) |
| F02 regression, WIZARD_FEATURE=on / off | 37 passed, 1 skipped (DB only), 2 deselected — each |
| F02 raw (no deselection), on / off | 37 + 2 failed each: version strings only (expected) |
| F04 function tests (tests/f04/function_test.ts, Deno 2.1.4) | 28/28 |
| create-trip unit tests (supabase/functions/create-trip/test.ts) | 9/9 |
| invite-manager unit tests (supabase/functions/invite-manager/test.ts) | 21/21 (needs `--allow-net=127.0.0.1`, now in run.sh 1.1.0) |
| DB, local Postgres 16 (scripts/dev/f04_db_check.py; 0010 and 0011 applied twice) | `qa.f01_run()` 109/109 · `qa.f02_run()` 37/37 · `qa.f03_run()` 49/49 · `qa.f04_run()` 90/90 · F04 scenarios 51/51 · 0 rows left behind |
| DB `qa.f04_run()` on plan-travel + Supabase advisors | not run here (deployment step 3) |

Expected failures in the raw F03/F02 runs (spec §5.19; each one is deselected by run.sh):
- Version pins: F03 `test_ac18_static[app_version|title_version]` (want alpha.3.4) and F02 `test_ac15_static[app_version|title_version]` (want alpha.2). Both flag states.
- /invite/ page: F03 `test_ac10_invite_page_outside_app` looks for "התחלת הקמה · בקרוב". F04 §1.1 replaces it in both states, because /invite/ is not behind the flag. Replaced by `test_c16_invite_page_button_opens_app`.
- On only: the F03 in-app valid landing is now the code screen (§4 "Token entry"). This affects `test_ac10_landing_valid[fresh-device|linked-device]`, `test_ac10_landing_network_error_and_retry`, `test_ac12_token_not_kept[valid]`, `test_ac10_invite_link_while_app_open`, `test_ac10_invite_link_encoded_and_query`, `test_ac10_invite_via_launch_queue` and `test_ac17_390_rtl_touch[landing-valid]`. The F04 suite has a replacement for each one.
- `test_ac16_off_more_panel_identical_to_alpha2`: this test now leaves out `#ptJoinRow` when WIZARD_FEATURE='on'. That follows the architect's decision in dev notes §7, with the change marked in tests/f03/test_f03.py 1.0.1. It passes in both states.

Test changes in this round (`CHANGE 2026-10-12 F04-QA-03`):
- The fake `create-trip` writes trip_kv `tripname` (the trimmed name).
- New tests for criterion 11. With the v1 home (HOME_LAYOUT flipped in a copy that is served to the browser) and the v2 home, `#tripName`, the ניהול → הגדרות מסע row and the field in its dialog all show the entered name. They never show "מסע של חלומות", and the name is still there after a reload. A mutation check confirms the test fails when the row is missing.
- Criterion 16: the /invite/ note must be the new text, and "קיבלתי הזמנה לנהל טיול" must be gone.
- run.sh 1.1.0 adds loopback net permission for the invite-manager Deno tests.

## Open for deployment / Or's phone
Deployment (spec §6, one at a time):
- [ ] 1. Email templates "Change email address" and "Magic link" contain `קוד האימות שלך: {{ .Token }}` (link kept).
- [ ] 2. Email provider: OTP length 6, expiry 3600 s.
- [ ] 3. Run `0010_f04.sql`, then `0011_qa_f04_harness.sql`; `qa.f04_run()` all pass, nothing left behind; advisors clean.
- [ ] 4. Deploy `create-trip` (`verify_jwt=false`) and `invite-manager` alpha.4.0; optional `JOIN_URL` secret.
- [ ] 5. Push the app; GitHub Pages published.

Or's phone (tests/f04/MANUAL.md):
- [ ] Android, email link: /invite/ shows "פתיחה באפליקציה והקמת הטיול" and the new note (…"כניסה עם הזמנה"). The app opens on "הקוד נשלח למייל" with the email locked and no tab bar.
- [ ] A 6-digit code arrives. A wrong digit gives "הקוד שגוי…" and clears the boxes. Pasting the code fills all 6 boxes and verification starts. Step 1 is prefilled with the draft name.
- [ ] iPhone home-screen app: "קיבלת הזמנה לנהל טיול?" → "כניסה עם הזמנה" → type email → "שליחת קוד". The 45 s resend countdown works. The keyboard's code suggestion works.
- [ ] Step 1: the day count follows the dates and English is disabled with "בקרוב". Step 2: "יפ" / "jap" both find יפן, the currencies follow the countries, and removing a country removes its currency. Step 3: "עריכה" keeps the state and "צופה" can be chosen.
- [ ] "יצירת הטיול" leads to "הטיול נוצר" with the name, flags and day count. In airplane mode on step 3 the button is disabled and shows "אין חיבור…".
- [ ] WhatsApp message contains the name and `https://orsela.github.io/Plan_Travel/join/#code=…`. The /join/ link shows "ההצטרפות לטיול תיפתח בקרוב" with no code in the address bar. "העתקה" shows "הקישור הועתק".
- [ ] "כניסה לטיול": shows the trip name and dates (not Vietnam, not "מסע של חלומות"). Every day shows "עוד לא נוספו נקודות", the "צעדים ראשונים" card appears, and the tab bar, chat and FX are there.
- [ ] ניהול → הגדרות מסע shows the trip name (F04-DB-02).
- [ ] "עוד" → "קישור הצטרפות לקבוצה" shows the same link. Closing and reopening the app shows the same new trip. Adding a point to day 1 after sharing makes the card disappear.
- [ ] Claude runs `qa.f04_run()` and the advisors on plan-travel and reports.

## Defects found
None in the product.

| # | Found | Cause | Fix |
|---|---|---|---|
| — | (test infra) invite-manager Deno test F03-MAIL-04 failed in run.sh: `NotCapable: Requires net access to "127.0.0.1:0"` | run.sh 1.0.0 did not grant loopback net to the local fake SMTP listener | run.sh 1.1.0: `--allow-net=127.0.0.1`; 21/21 |

## Open questions
1. **Wrong vs expired code.** GoTrue answers both with the same error (403 `otp_expired`, "Token has expired or is invalid"). To show "הקוד שגוי…" or "הקוד פג…", the app has to use the time since sending. The fake does the same, so only the phone can confirm the real behaviour, for example after waiting more than 1 h, or after a resend that makes the old code invalid.
2. **Two sources for the trip name.** `trips.name` and trip_kv `tripname` are both written at create. The spec doesn't say whether renaming in הגדרות מסע should also update `trips.name`, which F09 trip lists will read. Proposal: decide this in F06/F09.
3. **/invite/ ignores the flag.** The /invite/ page changes even with WIZARD_FEATURE='off', because it is outside the app. With 'off', its button opens the app, which then shows the F03 landing with "בקרוב". Is that acceptable as the rollback state?
4. **Where criterion 11 is tested.** The browser test checks the fake's `tripname` and the client display. The real DB write is covered by `qa.f04_run()` row 20 (trimmed name), which so far has only run on local Postgres.

## alpha.4.1 (2026-10-12) — first-steps card (F04-HOME-04, F04-VER-04)
CHANGE 2026-10-12 F04-QA-04: new section. Contract: spec §1.8 (button "הוספת נקודה" `#ptFsRoute`, tappable open rows) and dev notes §8. Suite tests/f04/test_f04.py 1.1.0 → 1.2.0.

Suite changes:
- Version pin is now 3.0.0-alpha.4.1.
- TXT "למסלול" → "הוספת נקודה". In `test_c13_enter_trip_home`, the route-tab check is replaced: the button must open `#waypointModal` with "הוספת נקודת עניין · יום 1", and closing it must return to home.
- The `c20` home card anchor uses the new button text.
- New tests:
  - `test_c13_fs_row3_opens_add_point[tap|enter|space]`
  - `test_c13_fs_row3_without_device_user`: the legacy "מי אני" modal is accepted here (deferred to F05)
  - `test_c13_fs_row2_tap_marks_shared`: wa.me with the join URL, `pt:<trip>:firststeps` {shared:true}, row done, count 1 → 2 מתוך 3
  - `test_c13_fs_rows_tappable_only_when_open[none_done|shared_done]`: role=button, tabindex=0, "‹" and ≥44px only on open rows; fits in 390px

| Suite | Result |
|---|---|
| F04 browser suite 1.2.0 | 92/92 (85 + 7 new) |
| F03 regression, WIZARD_FEATURE=on / off | 47 passed, 1 skipped, 11 deselected / 55 passed, 1 skipped, 3 deselected |
| F03 deselected tests run on their own, on / off | 11 / 3 failed: the same expected set as alpha.4 (version pins alpha.3.4, "בקרוב" /invite/ button, F03 in-app landing replaced by the code screen) |
| F02 regression, WIZARD_FEATURE=on / off | 37 passed, 1 skipped, 2 deselected each; the 2 deselected (version pins) fail as expected |
| Deno: F04 function tests · create-trip · invite-manager | 28/28 · 9/9 · 21/21 |
| DB | no DB change in alpha.4.1; not re-run (alpha.4 result above) |

Defects: none.
Out of scope, noted from dev notes §8: a new trip still uses the device-wide "מי אני" name, deferred to F05.
Phone (add to the checklist):
- [ ] On the "צעדים ראשונים" card, tapping "הוספת היעד הראשון ליום 1" or "הוספת נקודה" opens "הוספת נקודת עניין · יום 1", and closing it returns home.
- [ ] Tapping "שליחת קישור לקבוצה" opens WhatsApp, and the row turns ✓.

## alpha.4.2 (2026-10-12) — app name "Lonely Planner" + new address (F04-NAME-01/02/03)
CHANGE 2026-10-12 F04-QA-05: new section. Contract: spec §8 and §8.1. Branch `f04` @ 7d984df. Deliverable under test: `ops/old_address_redirect/`.

### Test changes (all marked `CHANGE 2026-10-12 F04-QA-05`)
- **Harness:** the local server now serves the app under `/Lonely_Planner/` (F02 harness 1.0.1, `APP_PATH`).
- **F03 harness 1.0.2:** `PROD_APP_URL` is now `/Lonely_Planner/app/`, and the fake email subject is "…ב-Lonely Planner". The F03 Deno test (1.0.1) has the same subject, sender and URL changes. It needs a real database, so it is not run here.
- **F04 suite 1.3.0:**
  - `JOIN_BASE` is now `https://orsela.github.io/Lonely_Planner/join/` and `VERSION` is 3.0.0-alpha.4.2.
  - `test_c21_static[title_version]` asserts the app `<title>` == "Lonely Planner" exactly.
  - The /join/ test expects the brand "Lonely Planner".
- **New browser tests:**
  - `test_n01_no_old_name_rendered[15 screens]`: gate, email, code (the spam hint contains "Lonely Planner"), steps 1–3, Done, first-steps card, the "עוד" sheet, admin ("Lonely Planner · סופר-אדמין"), in-app landing (invalid; F03 valid with the wizard off), /invite/ valid and invalid, /join/.
  - `test_n02_static_names[7]`: manifest name and short_name, apple title, the /invite/ and /join/ `<title>` (they carry the name; the spec does not require them to be exactly the name), no old name in displayed fields, manifest icons unchanged.
  - `test_n03_whatsapp_text_name_and_url[done|card|sheet]`.
  - `test_n04_old_address_redirects[8]`: the old pages are served at `/Plan_Travel/` and `https://orsela.github.io/Lonely_Planner/**` is intercepted locally. Query and hash are kept, unknown old paths go to the app, and Back skips the redirect page (location.replace).
  - `test_n04_old_invite_link_end_to_end`: the old invite link reaches the real /invite/ page at the new address, and the token is validated.
- **F04 Deno tests 1.1.0:** the defaults moved to `/Lonely_Planner/`, and the IM-02 email link is now `/Lonely_Planner/invite/#invite=…`. New cases:
  - NAME-01: the email subject, `FROM_NAME`, HTML and text say Lonely Planner, and no old name appears anywhere.
  - NAME-02: the default address and the invite link.
  - NAME-03: the create-trip default `join_url`.
- **run.sh 1.2.0:** deselects F02 `test_ac15_static[manifest_visible_fields_unchanged]` in both states. The installed-app name changes on purpose (§8); the icons part is now covered by `test_n02_static_names[manifest_icons_unchanged]`.
- **MANUAL.md 1.1.0:** new URLs and a new section 6.

| Suite | Result |
|---|---|
| F04 browser suite 1.3.0 | 126/126 (92 + 34 new) |
| F03 regression, WIZARD_FEATURE=on / off | 47 passed, 1 skipped, 11 deselected / 55 passed, 1 skipped, 3 deselected |
| F03 deselected tests run on their own, on | 11 failed, the same expected set as before (version pins alpha.3.4; "בקרוב" /invite/ button; F03 landing replaced by the code screen) |
| F02 regression, WIZARD_FEATURE=on / off | 36 passed, 1 skipped, 3 deselected — each. Before the deselection: 1 failure each, `manifest_visible_fields_unchanged` ("manifest name changed"), expected by §8 |
| Deno: F04 function tests · create-trip · invite-manager | 31/31 · 9/9 · 21/21 |
| DB | no DB change; not re-run |

Defects: none.

Phone (alpha.4.2, see MANUAL.md section 6):
- [ ] Re-add the installed app from `https://orsela.github.io/Lonely_Planner/app/`. The icon is named "Lonely Planner", and the trip, data and sign-in carry over.
- [ ] Old links redirect: `…/Plan_Travel/invite/#invite=…` from an earlier email opens the invite at `…/Lonely_Planner/invite/`. `…/Plan_Travel/app/` and `…/Plan_Travel/join/#code=…` land on the new address, and Back does not loop.
- [ ] A new invite email: subject "הוזמנת לנהל טיול ב-Lonely Planner", sender "Lonely Planner", header and footer say Lonely Planner, and the button goes to `…/Lonely_Planner/invite/`.
- [ ] Dashboard (Or): secret `APP_URL` = `https://orsela.github.io/Lonely_Planner/app/`; Auth URL configuration and the SMTP sender name updated.
