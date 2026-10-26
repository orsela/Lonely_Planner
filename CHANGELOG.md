# Plan_Travel – CHANGELOG

## 3.0.0-alpha.7.1 — F04-HOME (2026-10-26)

### F04-HOME · An invited manager ends up with the app on the home screen, and the email code never gets lost
<!-- CHANGE 2026-10-26 F04H-DOCS-03: new entry. -->
- `/invite/` (flag `HOME_INSTALL_FEATURE`): detects a mail app's in-app browser → "פתיחה בספארי" (iPhone,
  `x-safari-https`, button only) / automatic hop to Chrome (Android, token as one-hop `?t=`); iPhone Safari: "קודם
  מוסיפים את האפליקציה למסך הבית" with 3 steps + "להמשיך בדפדפן בלי להתקין"; Android: line about installing at the end.
- App 3.0.0-alpha.7.1: gate card "מנהל/ת טיול → כניסה עם המייל" on top; after the code, no open invite + an active trip →
  the trip opens (C3, was "לא מצאנו הזמנה" until restart); code screen resumes within 10 min after a reload without a new
  send (`pt:_device:wz_resume`, never the code or the token); "איפה הקוד?" card; "הטיול נוצר" install card when not
  standalone (iPhone steps / Android `beforeinstallprompt`). Protected functions byte-identical.
- Supabase Auth templates "Change email address" + "Magic link": subject `{{ .Token }} – קוד הכניסה ל-Lonely Planner`,
  body code only, no link (Or, 2026-10-26; docs/F04-HOME_email_templates.md).
- No DB or Edge Function change.
- QA: independent suite 91 pass / 0 fail / 1 skip (advisors) / 1 xfail (no "explicit exit" control — spec ambiguity);
  static 15/15; flag-off regression identical to alpha.7. Phone check pending. See docs/qa/F04-HOME_QA.md.

## 3.0.0-alpha.7 — S3 (F06 done, 2026-10-26)

### F06 · A manager changes roles, removes members and resets the link — 2026-10-22 → 2026-10-26
<!-- CHANGE 2026-10-26 F06-DOCS-04: new entry. -->
- App (3.0.0-alpha.7, flag `MEMBERS_FEATURE`): "עוד" → "חברים וקישור" (managers): join link card with WhatsApp / copy /
  reset, pending shortcut to home, members list with role badges and last seen; member sheet (role, rename, remove);
  "יציאה מהטיול" for everyone; only-manager guard; viewer guard ("צפייה בלבד – השינוי לא נשמר"); membership watch
  (Realtime + 60 s check) with "ההרשאה שלך השתנתה" and "כבר אינך חבר" screens and local clean-up. 2 existing lines
  changed (versions). Protected functions byte-identical.
- `/join/`: a removed member may ask again (D2); the join code is kept on the device for "בקשה להצטרף שוב".
- Edge Functions: new `manage-members` (set_role / rename / remove / leave / rotate_link / touch) and `join-trip`
  3.0.0-alpha.7.0 (version header), deployed 2026-10-26.
- DB `0014_f06`: six service-role functions, D2 change in `join_preview`/`join_request`, trigger trip name → `trips.name`
  (managers), `member_touch`; `0015_qa_f06_harness` (`qa.f06_run()`). Applied by Or 2026-10-26.
- QA: qa.f06 171/171 on the real project, independent browser suite 70/70, functions 19/19 + 23/23, flag-off regression
  identical to alpha.6; phone check partial (4א). See docs/qa/F06_QA.md.

## 3.0.0-alpha.5.1 — S2 (F20, 2026-10-13 → 2026-10-17)

### F20 · Super-admin start chooser, standalone admin, in-trip switcher
<!-- CHANGE 2026-10-26 F20-DOCS-01: entry added at formal closure (it was missing). -->
- App 3.0.0-alpha.5 → 5.1 (flag `SWITCH_FEATURE`): super-admin boots on "לאן נכנסים?" (ניהול מערכת with pending invites
  count + "הטיולים שלי" = all trips); admin screen stands alone (no trip chrome, header "הטיולים שלי", `#admin`); device
  option "לפתוח תמיד ישר לטיול האחרון" (off by default). D7 (Or, 17/10): no admin entry inside a trip; the avatar opens
  the trip switcher only for 2+ trips; `#admin` while a trip runs reloads into the standalone admin.
- No DB or Edge Function change.
- QA: F20 suite 77/77 (alpha.5) → 82/82 (alpha.5.1); F02/F03/F04 regression and Deno green in both SWITCH states; no
  defects. See docs/qa/F20_QA.md.

## 3.0.0-alpha.4.2 — S2 (F04, 2026-10-12)

### F04 · An invited manager sets up a trip in three steps
<!-- CHANGE 2026-10-26 F04-DOCS-01: entry added at formal closure (it was missing). -->
- App 3.0.0-alpha.4 (flag `WIZARD_FEATURE`): invite → 6-digit email code (Supabase OTP, email linked to the device's
  anonymous identity) → wizard (name/dates/language · countries + currencies · review) → "הטיול נוצר" with the WhatsApp
  join link; new trip = one empty day per date (never Vietnam `SEED_DATA`); "כניסה עם הזמנה" on the not-connected card.
  alpha.4.1: tappable first-steps rows + "הוספת נקודה". alpha.4.2: display name "Lonely Planner", new address
  `/Lonely_Planner/`, redirect pages from the old address.
- `/invite/`: "פתיחה באפליקציה והקמת הטיול" + installed-app note.
- Edge Functions: new `create-trip` (lookup / create, atomic, idempotent; writes `trip_kv.tripname`), `invite-manager`
  alpha.4.x (APP_URL hardening, `check.email`). DB `0010_f04`, `0011_qa_f04_harness` (`qa.f04_run()` 90/90 on the real
  project).
- QA: F04 browser suite 85/85 (alpha.4) → 126/126 (alpha.4.2); F03/F02 regression green; functions 28/28 + 9/9 + 21/21;
  local DB f01–f04 all pass. No product defects. See docs/qa/F04_QA.md.

## 3.0.0-alpha.6 — S2 (F05 done, 2026-10-22)

### F05 · A member joins from the group link, after manager approval — 2026-10-19 → 2026-10-22
<!-- CHANGE 2026-10-22 F05-DOCS-05: new entry. -->
- `/join/` (flag `JOIN_FEATURE`): trip preview → name → waiting screen that opens by itself (Realtime + 20 s poll) →
  approved; iPhone Safari also gets a 6-digit transfer code for the home-screen app. Shared screens in `join/flow.js`.
- App (3.0.0-alpha.6, flag `JOIN_FEATURE`): not-connected screen "כמעט שם" (transfer code, pasted join link inside the
  app; F04 invite card kept); managers' home card "ממתינים לאישור" with role choice (editor preselected) and
  approve / reject; "מי אני" = the member's display name (picker never opens in cloud mode); vault members = the trip's
  active members. 3 existing lines changed (versions, F04 "בקרוב" join card). Protected functions byte-identical.
- Edge Functions `join-trip`, `approve-member` (3.0.0-alpha.6.0, deployed 2026-10-19).
- DB `0012_f05`: schema `private` (transfer_codes, join_attempts), six service-role functions, DB rate limits;
  `0013_qa_f05_harness` (`qa.f05_run()`). Applied by Or 2026-10-19 / 2026-10-22.
- QA (short, by Or's decision): qa.f05 120/120 + f01–f04 regression on the real project, dev DB 51/51, functions 14/14
  (+ independent 11/12, finding: no version header), smoke 28/28, phone check passed. Full browser QA not run.
  See docs/qa/F05_QA.md.

## 3.0.0-alpha.3.4 — S2 (F03 done, 2026-10-12)

### F03 · Super-admin invites a manager — 2026-10-05 → 2026-10-12
- App (`app/`, now 3.0.0-alpha.3.4): flag `ADMIN_FEATURE='on'|'off'`; "החשבון שלי" in עוד (link email via
  `auth.updateUser`, linked email, "ניהול מערכת" for platform admins); admin screen (filter, cards, revoked toggle,
  offline notice, no trip chrome); invite + actions sheets; in-app `#invite=` landing. `off` = alpha.2 behaviour.
  Protected functions byte-identical.
- Invite page `invite/` (new, outside the installed app's scope): the link in the email opens it; it runs the
  `check` call and shows valid / invalid / no connection itself.
- Edge Function `invite-manager` (deployed, 3.0.0-alpha.3.7): create / resend / revoke / check; own MIME + SMTP client
  over smtp.gmail.com:465 (denomailer removed — it broke Hebrew subjects); redesigned RTL email (button
  "קבלת ההזמנה והקמת הטיול", 3 steps, fallback link); mailer errors logged without secrets.
- DB: `0008_f03` (invite tracking columns, one active invite per email, `admin_trip_summary()`), `0009_qa_f03_harness`
  — applied by Or 2026-10-09. Or registered as platform admin (email linked to his phone identity, membership kept).
- Fixes found in live testing (2026-10-09 → 12): link-email error showed "no connection" on server errors; Gmail showed
  raw MIME (subject encoding); invite link while the app is open (hash reload, `?invite=1`, launch_handler + launchQueue,
  `/invite/` page); root cause of the "dead button": the `APP_URL` secret was `ttps://…` (fixed by Or 2026-10-11).
- QA: browser 58/58 (+1 skip), F02 regression 37/37 in both flag states, function 18/18, DB qa.f01 109/109,
  qa.f02 37/37, qa.f03 49/49; advisors: one expected note (admin RPC is security definer, refuses non-admins).
  Or's phone: email linked, admin screen, create / resend / revoke, email received and the button opens the invite.
  See docs/qa/F03_QA.md.
- Open for F04: harden `invite-manager` so an invalid `APP_URL` falls back to the default.

## 3.0.0-alpha.2 — S1

### F02 · The app on the new infrastructure — 2026-10-05
- `app/`: v2.15.2 running on `plan-travel` (index.html, sw.js, manifest.json, icons). Live at https://orsela.github.io/Plan_Travel/app/.
- Identity: silent anonymous Supabase sign-in; active trip resolved from `trip_members`; unlinked devices see the
  "המכשיר עדיין לא מחובר לטיול" card with an 8-char device code (the only new UI).
- `window.storage` reads/writes `trip_kv` by `trip_id` (keys without `planner:`), same interface/timeout as v2.15.2;
  offline queue and SYNC-MERGE unchanged.
- Same-origin isolation from the live app: localStorage under `pt:<trip_id>:`, IndexedDB `pt-vault-<trip_id>`,
  caches `pt-*`; the live app's `planner:*` / `vietnam_planner_*` / `vtp-*` state is never read or written.
- Flags (top-level): `STORAGE_BACKEND='cloud'|'local-only'`, `CHAT_FEATURE='soon'` (chat shows "בקרוב", no network).
- Protected functions byte-identical to v2.15.2. Live project `vietnam-trip-2026` untouched (read-only comparison only).
- `scripts/import_planner_kv.py`: planner_kv export → trip_kv SQL + verification counts.
- DB: `0005_f02_test_trip` (test trip `f0200000-…-0001` + `admin_assign_device`, applied 2026-10-04 by an earlier session;
  data = 32 keys copied read-only from the live app, 29 byte-identical, 3 updated in the live app afterwards);
  `0006_f02` (Realtime on trip_kv/trip_members; trigger `trip_kv_set_updated_by`);
  `0007_qa_f02_harness` (`qa.f02_run()`). 0006/0007 were run by Or in the dashboard SQL Editor on 2026-10-05
  (Connector write approval unavailable), so they are not in `supabase_migrations.schema_migrations`.
- QA: browser 39/39 (1 skipped → covered by DB), DB 37/37, advisors: no new findings. Or's phone: linked and opens the trip.
  See docs/qa/F02_QA.md.

## 3.0.0-alpha.1 — S1

### F01 · Trip isolation (schema + RLS) — 2026-10-04
- Supabase project `plan-travel` (eu-central-1, free plan).
- `0001_core`: 9 tables (platform_admins, trips, trip_join_codes, trip_countries, trip_currencies, trip_members,
  manager_invites, relink_tokens, trip_kv), 7 indexes, helper functions `is_platform_admin()`, `trip_role()`,
  `my_trip_ids()`, triggers (`currency_limit` ≤10, `base_currency_locked`, `last_manager`, `trip_kv_trip_locked`,
  `updated_at`), RLS on all tables (authenticated only; anon has no privileges).
- Decision (Or, 2026-10-04): join code stored readable by trip managers only (not hashed) so the link can always be copied.
- `0002`–`0004`: QA harness `qa.f01_run()` in a locked, non-exposed `qa` schema (109 scenarios, always rolled back).
- QA: 109/109 pass, no test data left behind. See docs/qa/F01_QA.md.

## 0.0.1 — 2026-10-04
- Repo bootstrap (README).
