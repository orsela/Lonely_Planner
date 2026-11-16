# Plan_Travel – CHANGELOG

## 3.0.0-alpha.16.4 — F24 · country-only flight side → the country's main airport (2026-11-16)
- `f24FlightSearch`: a side with only a country gets the first airport of that country in airports.json (AE→DXB, GR→ATH); never the same airport on both sides; card note "ניחוש לפי המדינה". The Google Flights link now always names origin, destination, date and "one way". Node test FIX-04.

## 3.0.0-alpha.16.3 — F24 · change control for the flight destination (2026-11-16)
- The "אל" leg of the flight card is a button with "שינוי" (same airport sheet, title "טסים אל…"); applies to this search only. `f24FlightSearch(i,{dest})`. Node test FIX-03.

## 3.0.0-alpha.16.2 — F24 · last-day flight with country-only sides (2026-11-16)
- `f24FlightSearch` (app/js/f24.js): on the last day of the trip, a flight whose destination is only a country goes to Tel Aviv (TLV); an origin that is only a country becomes the airport of the previous day's city (else this day's city) when it is in airports.json and in the same country. Or's choice C after the day-9 phone check. Node test FIX-02.

## 3.0.0-alpha.16.1 — F24 · Google Flights link when a flight side has only a country (2026-11-16)
- `f24GoogleFlightsUrl` (app/js/f24.js): a side with no airport code and no city is no longer written as "from <country> to <country>" (Google left the fields empty, Or's phone check on day 9). The link names the known side only, or opens the plain page. The flight card shows a one-line hint in that case. Skyscanner unchanged. Node test FIX-01.

## 3.0.0-alpha.16 — F07 · conversations 2 + 3 (page side, app side, flag ON; 2026-11-16; phone check pending)
<!-- CHANGE 2026-11-16 F07-DOCS-07: new entry on top of the conversation-1 entry below (same version 3.0.0-alpha.16: f07-build was never released before this merge). Notes: docs/F07_dev_notes_page.md (conversation 2), docs/F07_dev_notes_app.md (conversation 3). -->
- `RELINK_FEATURE='on'` in the app and in `/join/`: a member on a new phone opens the join link, picks "כבר הייתי בטיול" and their name; the manager approves ("מכשיר חדש", no role picker); same name, role and records, one person with two devices.
- "חברים וקישור": one row per person (the count is persons), the devices under it with "ניתוק" (two taps); never on this device or on a person's last device; "ניתוק מכשיר לא מסיר את החבר מהטיול".
- "אני · <שם>" → "המכשירים שלי" card with "ניתוק". Managers: a home card "<שם> נכנס/ה ממכשיר חדש · <ספק>" with "הבנתי" / "זה לא הוא/היא · ניתוק" (C8).
- A disconnected device signs out within 60 s (touch every 60 s; `device_revoked` or a dead session → "המכשיר הזה נותק מהטיול"). Offline: the buttons are disabled with the offline line. iPhone Safari: the F05 transfer card after an approved relink (C11).
- Note: "אני · <שם>" is F22a's screen and `ACCOUNT_FEATURE` is still `'beta'`, so "המכשירים שלי" shows only on beta devices until F22a goes `'on'`.
- Tests: `tests/f07/run_page.sh` (Node 9, browser 4 + 2 at 390 px); F06 browser suite 70/70 and F05 suite unchanged vs `main` (13 old failures, same as before) with the flag on.

## 3.0.0-alpha.16 — F07 · a member who changed phones gets back into the trip (conversation 1 of 3: server only, 2026-11-16)
<!-- CHANGE 2026-11-16 F07-DOCS-05: new entry. Spec docs/F07_spec.md, notes docs/F07_dev_notes_server.md. Nothing visible in the app yet; the app/join pages are not bumped until conversation 2. -->
- Server, not yet applied to the database: migration `0018_f07.sql` (+ QA harness `0019`): one **person** can have several devices (`person_id`); a "כבר הייתי בטיול" request (`join_request` with a person, 24 h) approved by a manager takes the person's current role and name; role / name / removal / leave apply to every device; the last-manager rule counts persons; per-device sessions (`member_sessions`) with disconnect (`device_disconnect`) and a login notice for managers (`device_list` / `device_notice_ack`).
- Edge Functions `join-trip`, `approve-member`, `manage-members` → 3.0.0-alpha.16.0 (backward compatible with the alpha.15.x app).
- Tests: `tests/f07/run.sh` (functions 35 + `qa.f07_run()` 46/46 on a local PostgreSQL).

## 3.0.0-alpha.15.4 — F14 · chat bubbles show bold, not raw asterisks (2026-11-16)
- `chatBubbleHtml` (app/index.html): assistant text is escaped, then `**x**` becomes `<strong>x</strong>`. User bubbles unchanged. Found in Or's phone check (screenshot 16/11). No server change.

## 3.0.0-alpha.15 — F14 · the smart chat (2026-11-15; phone check pending)
<!-- CHANGE 2026-11-15 F14-DOCS-06: new entry. Spec claude/Plan_Travel_F14_spec.md (project doc), steps 1–4. -->
- 💬 opens the chat: questions about the trip (days, budget, expenses, currency, weather, a photo) are answered in Hebrew by Claude through the new
  Edge Function `chat-assistant`, as the signed-in user; any active member (viewers too) can ask. 100 questions per trip per UTC day.
- "Find me a flight home from Batumi on 17/5" / a hotel request → a card with prefilled Google Flights + Skyscanner / Booking + Google Hotels links
  (F24's builders). No prices, nothing saved, no approve step; a request without a date gets a question back. The chat never changes trip data.
- Refusals (not signed in, not a member, daily limit, service off, timeout) are one friendly line, never a retry.
- Flag `CHAT_FEATURE` ('soon' = alpha.14); server kill switch: secret `CHAT_FEATURE=off`. Code: `app/js/f14.js`, `supabase/functions/chat-assistant/`,
  migration `0022_f14.sql`. Tests: `tests/f14/run.sh` (db 23, fn 36, app: 15 Node + one 390 px browser pass).

## 3.0.0-alpha.14 — F24 · flight and hotel search links (2026-11-14; branch f24, phone check pending)
<!-- CHANGE 2026-11-14 F24-DOCS-03: new entry. Spec claude/Plan_Travel_F24_spec.md (project doc), conversations 1–2 of 3 (the chat part, C8, is conversation 3). No server part, no migration. -->
- Day card under the day's reservations: a flight day with no flight reservation shows "עוד אין טיסה ליום הזה" (origin TLV by default or the previous
  city, destination from the route, dates, round trip on the first flight when a later day flies home, member count) with prefilled Google Flights and
  Skyscanner links; the first night of a run of unbooked nights in one city shows "עוד אין לינה ל-…" with Booking and Google Hotels links.
  A booked day has no new node at all (its HTML is identical to the flag-off page). Offline: the buttons are disabled with an offline line.
- Origin sheet ("שינוי"): TLV and ETM pinned, the last 3 origins used on this device (per trip), search over `app/airports.json` (289 airports).
  The change applies to this day's search only.
- The card is part of the day card, so it shows in the "ציר זמן" view of "מסלול ומפה" (the map view hides the day card, as before).
- Flag `TRAVELSEARCH_FEATURE` ('off' = alpha.13.1). Code: `app/js/f24.js`; `sw.js` also caches `js/f24.js` and `airports.json`.
- Tests: `tests/f24/run.sh` (16 Node), `tests/f24/run_browser.sh` (real app, 390 px: AC1–AC5, AC7–AC9). F08 browser test: version string updated to alpha.14.

## 3.0.0-alpha.13.1 — F08 stage B · the rest of the hard-coded Vietnam (2026-11-14; phone check pending)
<!-- CHANGE 2026-11-14 F08-DOCS-02: new entry. Spec docs/F08_spec.md §5 (rows marked stage B), AC5–AC8. No server part. -->
- Converter: the "local" currency follows the country of today's day (flight day: origin until landing, then destination), only when
  that currency is in the trip's list; re-applied every 30 s and on every currency-model change (`__ptF10.setLocal`, new, not cached).
- Weather: a day without lat/lng uses the capital of its country (countries.json).
- Place search (Google autocomplete): limited to the country of today's day (flight day: destination) instead of Vietnam only.
- Flight card: departure time is read on the origin's zone (explicit `flightFrom`, or a day-derived zone when the airport is not
  TLV/AUH); the card's clock times (leave, check-in, take-off) show on that zone.
- Google Timeline import and "ביקרנו בפועל": the date and clock of a point use the zone of the trip day it falls in (23:30 Tokyo
  belongs to the Japanese date); outside the trip, the nearest day's zone. Legacy Vietnam trip: still UTC+7.
- `F08_FEATURE='off'` = alpha.12.1. Changed existing bodies (all flagged in code): `tlVnDateKey`, `visVnHM`, `fcHHMM`, `fcVnHour`,
  `fcParse` (departure line), the weather functions' coordinate lines, the Places `componentRestrictions`.
- Tests: `tests/f08/run.sh` 31 Node; `tests/f08/run_browser.sh` (adds converter wiring). F10 browser suite: same 4 failures as before
  stage B (static checks of an old base: sw precache, versions, no_migration) – not caused by this change.

## 3.0.0-alpha.13 — F08 stage A · country and time zone for every day (2026-11-14; phone check pending)
<!-- CHANGE 2026-11-14 F08-DOCS-01: new entry (no previous version). Branch f08 → main. Spec: docs/F08_spec.md. -->
- App: "עוד → מדינות לפי ימים" (ranges of days by country / city / zone, range sheet); inside "✎ עריכת יום" a new box: the
  "יום טיסה" switch with origin + destination, or country / city / zone for that single day (only a value that differs from
  what the day derives is saved). Home clocks: "כאן" = the zone of today's trip day (flight day: the origin until landing,
  then the destination), "בבית" = Israel for shekel trips, otherwise the device zone; one clock when they are the same;
  a destination clock on a flight day. `isFlightDay` now answers through `f08IsFlight` (an explicit switch-off beats the old
  region / hotel test). Landing time is read from the flight reservation text ("נחיתה 18:40" / "landing 18:40" on the
  destination clock); none found → midnight on the departure clock.
- Flag `F08_FEATURE` ('off' = alpha.12.1 behaviour). No server part, no migration. Code: `app/js/f08.js` (+ `sw.js`, `countries.json` offline).
- Not in this stage (stage B, alpha.13.1): converter, weather, place autocomplete, flight card zones, Timeline / "ביקרנו" zones.
- Tests: `tests/f08/run.sh` (26 Node), `tests/f08/run_browser.sh` (real app, 390 px). Known: F10b `c14` compares "עוד" with alpha.9 and
  now sees the F08 row (expected difference).

## 3.0.0-alpha.12 — F23 (live 2026-11-13; phone check and independent QA pending)
<!-- CHANGE 2026-11-13 F23-DOCS-15: heading was "F23 (in progress, branch `f23`)". Deployed and merged 13/11: migrations 0020 + 0021, request-trip
     3.0.0-alpha.12.0 (deploy bundle), main = f23. invite-manager not redeployed. See docs/F23_dev_notes_server.md → Deploy. -->

### 3.0.0-alpha.12.1 · wizard calendar opens on the requested month (2026-11-13)
<!-- CHANGE 2026-11-13 F23-DOCS-16: new entry. Found by Or on the phone check of F23. -->
- App: in the trip wizard, an empty "יציאה" / "חזרה" date field now opens its calendar on the month chosen in the request
  (was: today's month, with only a help line naming the requested month). Nothing is pre-chosen and no date is forbidden.
  Flag `WZMONTH_FEATURE` ('off' = alpha.12). Test: `tests/f23/test_f23_wizard_month.py` (2). Not verifiable in the test
  browser: the native picker itself on Android / iPhone — phone check.

### F23 · Trip request without approval + AI destination ideas — server stage (2026-11-13)
<!-- CHANGE 2026-11-13 F23-DOCS-11: new entry (draft). Base: main e477da0 (3.0.0-alpha.11). Server only; the `/request/`
     page and the admin screen follow. Nothing deployed yet. -->
- Migration `0020_f23.sql` (+ QA harness `0021`, `qa.f23_run()` 49 rows): `trip_requests` gains `where_mode`, `interests`,
  `max_flight`, `pref_note`, `suggestions`, `session_hash`, status `auto_approved`; new service-role functions
  `request_verify2`, `request_suggest_begin`, `request_suggest_save`, `request_choose`, `request_invite_mail_failed`,
  `request_invite_draft`; `request_start` and `admin_trip_requests` replaced (same signatures).
- `request-trip` 3.0.0-alpha.12.0: `REQUEST_MODE` 'auto' (a verified email opens the trip: invite created, token returned
  to the browser, invite email sent and counted in the 50/day cap) | 'manual' (= F21); new actions `suggest` (Anthropic
  Messages API, no name / email in the prompt, 3 per request, 30 per day, 10 s, fallback to the country picker) and
  `choose`; one auto-approval per email per day.
- `invite-manager` 3.0.0-alpha.12.0: `approve_request` sends through the new shared module `_shared/approve.ts` (same email).
- Or's decisions 2026-11-13: the Hebrew automatic invite keeps "Lonely Planner מזמין אותך…"; the English automatic invite
  no longer says "approved" (subject "Your trip is ready to set up", button "Set up the trip"); a verified request that
  never got a destination is deleted after 3 days.
- Tests: `tests/f23/run.sh` (db 49/49, integration 11/11); F21 suites pinned to manual mode and green.
  Details: `docs/F23_dev_notes_server.md`.

### F23 · client stage (2026-11-13)
<!-- CHANGE 2026-11-13 F23-DOCS-13: new entry (draft). Not merged, not deployed. -->
- `/request/` 3.0.0-alpha.12 (flags `REQUEST_MODE` 'auto', `SUGGEST_FEATURE` 'on'): new subtitle + three "what we do /
  don't" lines; "לאן?" choice "יודע/ת לאן" / "עוד לא החלטתי" with interests, flight time and a short note; after the code
  either the ideas screen (3 AI destinations, 2 refreshes, country picker as fallback) or straight to the new ready screen
  with the button into the trip wizard. `'manual'` + `'off'` = the alpha.8 page.
- App 3.0.0-alpha.12 (flag `REQAUTO_FEATURE`): "ניהול מערכת → בקשות" shows "הצעות AI היום N מתוך 30" and the history
  "נפתחו אוטומטית" with each invite's state and a button to the existing invite sheet.
- Tests: `tests/f23/run.sh --only page` 8/8, `--only app` 3/3. Details: `docs/F23_dev_notes_client.md`; spec `docs/F23_spec.md`.

## 3.0.0-alpha.11 — F22a (2026-11-07)

### F22a · Sign in with Google (account backup for every member)
<!-- CHANGE 2026-11-07 F22A-DOCS-02: new entry. Base: main b32ef62 (3.0.0-alpha.10 + spike page). -->
- App + `/invite/` (flag `ACCOUNT_FEATURE` = 'off' | 'on' | 'beta'; shipped **'beta'**: only on a device opened once with
  `#f22beta`, `#f22beta-off` turns it off). 'off' = alpha.10 exactly.
- Gate: "כבר בטיול? כניסה עם החשבון" (המשך עם Google + קוד למייל) on top, "בלי חשבון" (join link, Safari transfer code)
  below (C5). After Google: welcome header + "מסמכים ושינויים…" line, 1 trip → straight in, 2+ → list, open invite → the F04
  wizard, super-admin → F20 chooser, none → "החשבון הזה עוד לא בטיול" (C6).
- "עוד → אני · <שם>" for every member: sync card + "חשבון כניסה" (link Google with `linkIdentity` on the same uid, C1/C2;
  masked address, owner only; the F03 email row moves into the card, C7). Conflict sheet on `identity_already_exists` (C4).
  "הסרה" of Google with the D12 warning; when Supabase refuses to remove the last identity the refusal and its code are shown
  (R1, no server change) (C8). iPhone home-screen app: no Google, "באייפון: כניסה עם קוד למייל" (C9). Offline: Google /
  unlink disabled with the offline line.
- "המשך עם Google" on the F04 email step and on `/invite/` (C10). New static pages `/privacy/` and `/terms/` (Hebrew + short
  English, draft for Or's approval) linked from the gate and "אני" (C12).
- No migration, no Edge Function, no dashboard change. `/join/` unchanged. Tests: tests/f22a (run.sh). Spec:
  docs/F22a_spec.md; dev notes: docs/F22a_dev_notes.md.

## 3.0.0-alpha.10 — F10b (2026-11-07)

### F10b · Trip currencies screen: add, swap, remove (cap 10)
<!-- CHANGE 2026-11-07 F10B-DOCS-02: new entry. Base: main 43394ff (3.0.0-alpha.9). -->
- App only (flag `CURMGR_FEATURE`, 'off' = alpha.9). "עוד → 💱 מטבעות · N מתוך 10" for every member and a "ניהול מטבעות"
  link in the quick FX sheet (D1). Screen: base currencies locked ("קבוע"), the others with ⋯ (manager online).
- Managers: add (search + "מוצעים" = trip-country currencies not in the trip, D5), swap via ⋯ or, at 10, "מה יוצא?" (D3) —
  one atomic UPDATE of the row; remove with the expense-count warning (D4). Editors / viewers read only (D2); offline =
  cached list, actions off (D6). Converters rebuild at once (TRIPCUR refresh); a new code gets its live rate and, when shared
  rates are saved, is added to them (spec §6).
- Server unchanged: the existing RLS (managers), cap-10 trigger and base-lock trigger enforce the rules. No migration.
  Spec: docs/F10b_spec.md; dev notes: docs/F10b_dev_notes.md.

## 3.0.0-alpha.9 — F10 (2026-11-07)

### F10 · Every trip converts in its own currencies
<!-- CHANGE 2026-11-07 F10-DOCS-03: new entry. Base: main 4ca777b (3.0.0-alpha.8). -->
- QA (independent, tests/f10, 33 tests): 33/33 after F10-BUG-01 fix (the "עוד" chip's dashed border lost to the UI-kit solid border). Report: docs/qa/F10_QA.md.
- App only (flag `CURRENCY_FEATURE`, 'off' = alpha.8). The trip's currency model TRIPCUR is built from `trips.home_currency`,
  `trip_countries`, `trip_currencies` + countries.json / currencies.json, cached per trip (`pt:<trip>:tripcur`), exposed
  read-only as `window.__PT.tripcur`. Fallback = the Vietnam converter (VND ILS USD EUR).
- Chip rows (add expense, budget converter, quick FX sheet, quick expense) follow the trip's list (local first, D6), at most 5
  chips + "עוד" sheet (D7); default = last pick on this device for this trip, else the local currency (D2).
- Rates `fxrates` v2 `{v:2, base, rates, updatedAt, source}`; ILS trips also keep the alpha.8 `USD/EUR/VND` fields (dual
  write). Rate rows per list currency, weak currencies per 1,000 (C2); "אין שער" disables a conversion.
- Home currency everywhere an amount was "₪" (`fmtHome`, D3); new expenses store `homeCurrency` (D4); old expenses in a
  non-ILS trip are shown converted with "(₪ מקורי)". Floating button "<home> ⇄ <local>", reservation cost placeholder,
  chat context `fx` = `{base, rates, home, local}`.
- No migration, no Edge Function change. Dev notes: docs/F10_dev_notes.md.

## 3.0.0-alpha.8 — F21 (2026-10-30)

### F21 · Anyone can request to open a trip; the super-admin approves
<!-- CHANGE 2026-10-30 F21-DOCS-02: new entry. Base: hotfix 3.0.0-alpha.7.2 (QA-DEBT-BUG-01..04) is included in this release. -->
- New page `/request/` (3.0.0-alpha.8, flag `REQUEST_FEATURE`): bilingual form (עב / EN), in-app-browser hop, Cloudflare
  Turnstile, our own 6-digit email code (10 min, resume after reload, never stored), daily cap screen "נסו שוב מחר",
  "הבקשה נשלחה". F21-REQ-05: the code boxes are emptied after a wrong/expired code (QA bug F21-QA-BUG-01).
- App 3.0.0-alpha.8 (flag `REQUEST_FEATURE`): chooser badge "<N> בקשות חדשות" + "<M> הזמנות ממתינות"; admin tab
  "בקשות" with mail meter (N מתוך 50), markers (EN / כבר מנהל / יש הזמנה פעילה); approve sheet (draft name D16, replaces an
  active invite D12) and reject sheet (polite mail optional, D4); wizard pre-filled from the request (name, countries,
  "בבקשה: <month>"). Protected functions byte-identical.
- DB 0016_f21 (+ QA 0017): `private.trip_requests`, `request_attempts`, `mail_log`; `manager_invites.request_id/lang`;
  `request_*` service-role functions, `admin_trip_requests()`, `find_invite_for_email` + prefill. Live `qa.f21_run()` 101/101.
- Edge Functions alpha.8.0: new `request-trip` (start/verify/resend); `invite-manager` approve_request / reject_request +
  English invite and reject emails (Hebrew invite byte-identical); `create-trip` lookup returns prefill.
- QA (independent): browser 101 pass / 1 skip, functions 33/33, integration 10/10, DB 67/67; full regression green.
  See docs/qa/F21_QA.md.
- request-trip alpha.8.1 (F21-FN-03): logs the Turnstile failure reason (Cloudflare error-codes / hostname only).
- Phone check (Or, Android, 2026-10-30 → 11-07): passed — Hebrew request → approve → pre-filled wizard → trip created;
  English request with a wrong code first → reject with English mail. Known limitation outside F21: the in-trip currency
  converter still shows VND (→ F10).

## 3.0.0-alpha.7.2 — hotfix (2026-10-26 → 2026-10-30)

### Four app bugs found by the QA-DEBT pass
<!-- CHANGE 2026-10-30 FIX-DOCS-01: new entry. -->
- FIX-01 (high): Supabase Realtime does not filter DELETE events, so the membership watch treated ANY deleted
  `trip_members` row (a rejected / cancelled request) as "my row" → every open phone showed "כבר אינך חבר/ה" and wiped
  the trip's local data. Now only a DELETE whose `old.id` is my member id counts; any other DELETE re-reads my row.
- FIX-02: approve-member `not_manager` hides the pending card (F05 §1.5).
- FIX-03: pending-card role buttons 40 → 44 px.
- FIX-04: `/join/` error screen no longer holds `#joinTitle` twice.
- Versions: app 3.0.0-alpha.7.2; `/invite/` and `/join/` version comments aligned. No DB / Edge Function change.
- Tests: `tests/run_all.sh` full regression green (every suite PASS, 0 failures); new runtime test
  `test_s02_join_fatal_single_title`; dev check `scripts/dev/fix772_static_check.py`. QA-DEBT pass:
  docs/qa/QA-DEBT_2026-10-26.md. Phone check (Or, 2026-10-30, trip "F04-HOME"): manager on the Android app rejected a
  pending request while the app was open → no "כבר אינך חבר/ה", trip stays; the requester saw "הבקשה לא אושרה"; DB: both
  active members intact. <!-- CHANGE 2026-10-30 FIX-DOCS-02: FIX-01 confirmed on a real phone. -->

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
