# F04 · dev notes — an invited manager sets up a trip in three steps (v3.0.0-alpha.4)

<!-- CHANGE 2026-10-12 F04-DOCS-02: new file (no previous version). -->

Contract: `docs/F04_spec.md` (mockup approved 2026-10-12, canvas row 5, artboards `F04_Landing` … `F04_Home`, plus the
existing `CurrencySheet` artboard for "+ הוספה"). Base: `app/` at 3.0.0-alpha.3.4 (F03), server side (0010, `create-trip`,
`invite-manager` alpha.4.0, `countries.json`, `currencies.json`) already committed and **not modified** here.
Nothing was deployed or run against Supabase. All checks below are local (sandbox).

## 1. What changed (file / area → why)

| File / area | CHANGE ID | What changed from 3.0.0-alpha.3 | Spec |
|---|---|---|---|
| `app/index.html` `<title>` | F04-VER-02 | v3.0.0-alpha.3.4 → v3.0.0-alpha.4 | §4 |
| `app/index.html` flags script | F04-FLAG-01 | new top-level `const WIZARD_FEATURE='on'` (next to `ADMIN_FEATURE`) | §1 |
| `app/index.html` F03 landing `landCheck` | F04-LAND-01 | **one new line in an existing function body** (valid branch): with the flag on, a valid `check` hands over to `window.__ptF04.fromInvite(j)` → code screen with the email locked; invalid/network unchanged | §1.3, §4 "Token entry" |
| `app/index.html` head, new style + script block between the F03 block and the F02 gate block | F04-UI-01 | all F04 UI (sub-areas below). Returns on its first line when `WIZARD_FEATURE!=='on'` or `STORAGE_BACKEND!=='cloud'`; exposes only the frozen `window.__ptF04 = {version, attach, fromInvite, gateCard, emptyTrip}` | §1, §4 |
| ↳ same block | F04-CODE-01 | screen 3: email state / code state, supabase-js OTP (`updateUser` → `verifyOtp email_change`; `email_exists` → `signInWithOtp {shouldCreateUser:false}` → `verifyOtp email`), D6 card, "already linked" card, 45 s resend, spam hint, error map | §1.3, error table, §4 Auth |
| ↳ same block | F04-WIZ-01 / -02 / -03 | screens 4–6: step 1 (details + validation), step 2 (search, "נפוצות" chips in the spec §4 order, selected list with currency/UTC/capital line, currencies block with cap 10 + `CurrencySheet`), step 3 (review, "עריכה", default role) → `create-trip` `lookup` / `create` | §1.4–1.6 |
| ↳ same block | F04-DONE-01 | screen 7: join URL, WhatsApp (`https://wa.me/?text=`), copy + toast, F05 "בקרוב" card; "כניסה לטיול" = gate `enterTrip` (no reload) | §1.7, §4 |
| ↳ same block + `showCard` | F04-GATECARD-01 | screen 2: second card "קיבלת הזמנה לנהל טיול?" / "כניסה עם הזמנה" on `#ptGate`. **One new line in `showCard`** (calls `__ptF04.gateCard(g)` right after the card is built) | §1.2 |
| ↳ same block | F04-HOME-01 | screen 8: "צעדים ראשונים" card (managers only, until all 3 done) at the top of the home panel (`#homeV2` before the map hero; `#home` under its top bar when `HOME_LAYOUT='v1'`) | §1.8 |
| ↳ same block | F04-HOME-02 | home header `#hv2TripTitle` shows `trips.name` for a trip created by the wizard (its day objects carry `country`); other trips untouched | §1.8 "trip name and dates in the header" |
| ↳ same block | F04-HOME-03 | an empty day (no title, no waypoints) shows "עוד לא נוספו נקודות" in `#title` (route), `#hv2TodayRegion`, and the HOME-MIN pill `#hminPillTitle` / schedule title — via MutationObservers on those elements (no renderer changed) | §1.8, §4 |
| ↳ same block | F04-EMPTY-01 | 0-day trip only: runtime wrappers on `updateDates` and `render` (see §2) so boot shows "אין ימים בטיול" instead of throwing | §4 Seed |
| ↳ same block | F04-MORE-01 | screen 9: "עוד" row "קישור הצטרפות לקבוצה" (managers only, first row under "הטיול") + bottom sheet; code read with `from('trip_join_codes').select('code').eq('trip_id',…).maybeSingle()` | §1.9 |
| `app/index.html` F02 gate, `PT_VERSION` | F04-VER-03 | `'3.0.0-alpha.3.4'` → `'3.0.0-alpha.4'` (version string only) | §4 |
| `app/index.html` F02 gate, before the F03 bridge | F04-GATE-01 | **new lines only**: `PT_TRIP_ENDPOINT = PT_SUPABASE_URL + '/functions/v1/create-trip'` and `window.__ptF04.attach({…})` (client, uid, `ensureSession`, `activeTrips`, `cacheTrip`, first-steps raw keys, `enterTrip`) | §4 |
| `app/index.html` F02 gate `resolveAndStart` | F04-BOOT-01 | **existing function body**: `const m=rows[0]` → cached trip if still active (flag on), else `rows[0]` | §0 D5, §4 Boot |
| `app/index.html` main script `loadState` | F04-SEED-01 | **existing function body**: new early branch (flag on + cloud + stored value is an array → use as-is, even empty; 0 days → `__ptF04.emptyTrip()`); the original lines below are untouched | §0 D4, §4 Seed |
| `app/index.html` main script `APP_VERSION` | F04-VER-01 | `'3.0.0-alpha.3.4'` → `'3.0.0-alpha.4'`, appended to the existing CHANGE chain on that line | §4 |
| `invite/index.html` | F04-INV-01 | valid card per `F04_Landing`: new copy, expiry line, "מה יקרה עכשיו" steps, enabled link-button "פתיחה באפליקציה והקמת הטיול" → `../app/?invite=1#invite=<token>`, installed-app note. Invalid / network markup unchanged | §1.1 |
| `join/index.html` | F04-JOIN-01 | new: "coming soon" card, removes the `#hash`, never reads/shows/sends the code, no network | §1.10 |
| `supabase/migrations/0011_qa_f04_harness.sql` | F04-QA-01 | new: `qa.f04_run()` (90 rows) in the locked `qa` schema, F01–F03 pattern, always rolled back, leftovers row #127 | §2, §5 DB |
| `scripts/dev/f04_db_check.py` | F04-DEVDB-03 | also applies 0011 (twice) and runs `qa.f04_run()`; prints failing rows | DoD |
| `app/sw.js` | — | **unchanged** (JSON files are fetched only when the wizard opens and go straight to the network — sw.js only intercepts icons, navigations, supabase-js and the manifest) | §4 |

Lines removed/changed in `app/index.html` vs `HEAD` (alpha.3.4): exactly **4** — `<title>`, `PT_VERSION`, `const m=rows[0]`
(replaced by the F04-BOOT-01 line), `APP_VERSION`. Everything else is additive (main script 4042 → 4050 lines: +8 in
`loadState`, 1 changed `APP_VERSION`).

## 2. Existing code modified (the five allowed spots) and runtime hooks

1. `loadState` (main script) — F04-SEED-01: one new `if (…) {…; return}` block after the first `SS.get`. `'off'`: skipped.
2. `resolveAndStart` (gate) — F04-BOOT-01: `rows[0]` → `cached && rows.find(trip_id===cached.trip_id) || rows[0]` with the flag on.
3. `showCard` (gate) — F04-GATECARD-01: one new line `if(window.__ptF04)window.__ptF04.gateCard(g);` inside the `if(!g){…}` build.
4. F03 landing `landCheck`, valid branch — F04-LAND-01: one new line before `landRender(…)`.
5. Version strings: `<title>`, `PT_VERSION`, `APP_VERSION`.

Nothing else in an existing body was edited. Runtime hooks (new code only, flagged here because they touch existing behaviour):
- **F04-EMPTY-01 wrappers**: only when the stored trip has **0 days**, `window.updateDates` and `window.render` are replaced by
  wrappers that call the original unchanged as soon as `tripData` has days, and otherwise write "אין ימים בטיול". Same technique
  as the existing DAY-TODAY-01 `updateRouteDayStrip` wrapper. Probe result: with only these two wrapped, a 0-day trip boots and
  every tab (+ route map modes, day arrows, timeline, check-in) runs with no page error; without them boot aborts on
  `tripData[0].date`. **No protected function is wrapped.**
- **MutationObservers**: `<html class>` (start hook, like F03), and `#title`, `#hv2TodayRegion`, `#hminPillTitle`,
  `#hminSchedBody` (empty-day text). They only write text into those elements; no function is patched.
- Protected functions (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`, `SEED_DATA`, `stayBlock`,
  `bookingUrl`): **byte-identical** to `git show HEAD:app/index.html` (379 / 4613 / 3427 / 178 / 9277 / 517 / 309 bytes).

## 3. Flags

| Flag | Values | Default | Effect |
|---|---|---|---|
| `WIZARD_FEATURE` | `'on'` / `'off'` | `'on'` | `off` = alpha.3 exactly: the F04 block returns on its first line, `window.__ptF04` is undefined, the gate bridge / `showCard` line / F03 landing line are no-ops, `loadState` and `resolveAndStart` take their alpha.3 paths (seed fallback, newest membership). Styles exist but match nothing. |
| `ADMIN_FEATURE` | unchanged | `'on'` | The token path needs the F03 landing; with `ADMIN_FEATURE='off'` and the wizard on, `#invite=` is ignored (F03 absent) but the gate button path still works. |
| `STORAGE_BACKEND` | unchanged | `'cloud'` | `local-only` disables all of F04. |
| `APP_VERSION` / `PT_VERSION` | `'3.0.0-alpha.4'` | | |

## 4. For QA — stable ids and visible texts

Screens live in `<main id="ptWizard" data-screen="…">` (values: `busy`, `email`, `code`, `card:<kind>`, `step1`, `step2`,
`step3`, `done`); `html.pt-wizard` hides every other body child (no tab bar, chat FAB, FX pill, sync card). One screen is in the
DOM at a time; `#ptWzTitle` (h1), `#ptWzErr` (one-line error, `role=alert`), `#ptWzOff` (offline notice) exist on every screen.

- Gate (screen 2): `#ptGateInvite`, button `#ptGateInviteBtn` "כניסה עם הזמנה"; card texts "קיבלת הזמנה לנהל טיול?",
  "נאמת את המייל שאליו נשלחה ההזמנה, ותקים את הטיול מכאן.".
- Email state: `#ptWzEmail` (LTR), `#ptWzSend` "שליחת קוד"; label "המייל שאליו נשלחה ההזמנה".
- Code state: `#ptWzCodeEmail` (readonly, LTR), `#ptWzChangeEmail` "שינוי מייל" (entry mode only), digits `#ptOtp0`…`#ptOtp5`
  (`.pt-otp`, `inputmode=numeric`, `#ptOtp0` has `autocomplete=one-time-code`), `#ptWzResend` ("שליחה חוזרת בעוד m:ss" →
  "שליחה חוזרת"), `#ptWzSpam` "לא הגיע? בדקו בספאם" → `#ptWzSpamHint`, `#ptWzVerify` "אימות והמשך להקמה" (auto-submits on
  the 6th digit; paste of 6 digits fills all).
- Cards: `#ptWzCard[data-kind]` = `noinvite` ("לא מצאנו הזמנה פעילה למייל הזה" + "בקשו ממי שהזמין אותכם לשלוח הזמנה חדשה."),
  `d6` ("המכשיר הזה כבר מקושר למייל אחר (d•••@domain)." + "פתחו את ההזמנה במכשיר אחר, או בקשו לשלוח אותה למייל שמקושר כאן."),
  `linked` ("המייל הזה כבר משויך לחשבון אחר. כדי לא לאבד את הטיול שכבר במכשיר, פתחו את ההזמנה במכשיר אחר."), `retry`
  (offline / rate / generic with "נסו שוב"); button `#ptWzCardBtn` ("חזרה" → back to the gate, or a clean boot after a token link).
- Error texts: wrong "הקוד שגוי. בדקו את המייל האחרון ונסו שוב." (inputs cleared, focus `#ptOtp0`), expired "הקוד פג. שלחו קוד
  חדש.", rate "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.", offline "אין חיבור. נסו שוב כשהרשת תחזור.", invalid email "כתובת
  המייל לא תקינה.".
- Step 1: `#ptWzName`, `#ptWzMe`, `#ptWzFrom`, `#ptWzTo` (native date), `#ptWzDays` ("18 ימים · ייווצר יום ריק לכל תאריך"),
  `#ptWzLang [data-lang=he|en]` (en disabled, "בקרוב"), `#ptWzCur` (ILS/USD/EUR), `#ptWzNext` "המשך ←".
- Step 2: `#ptWzSearch`, results `#ptWzResults [data-add=CC]`, chips `#ptWzPopular [data-pop=CC]` (aria-pressed),
  `#ptWzSelCount` "נבחרו · N", `#ptWzSel [data-code=CC]` with `.pt-l` line and × `[data-rm=CC]`, `#ptWzCurCount` "K מתוך 10",
  `#ptWzCurs [data-cur=XXX]` (home chip text "… · בית"; added chips have × `[data-rmcur=XXX]`), `#ptWzCurAdd` "+ הוספה",
  `#ptWzNote` (full-converter note), `#ptWzBack` "חזרה". Currency sheet: `#ptF04Sheet`, `#ptCurSearch`, `#ptCurList
  [data-cur]` (role=checkbox), `#ptCurOk` "הוספה (n)".
- Step 3: `#ptWzSum` rows `[data-row=name|dates|me|countries|currencies]`, edit links `[data-edit=1|2]` "עריכה",
  `#ptWzRole [data-role=editor|viewer]`, `#ptWzCreate` "יצירת הטיול" (spinner + `aria-busy` while calling).
- Done: `#ptWzDoneSub`, `#ptWzUrl`, `#ptWzWa` (`<a href="https://wa.me/?text=…">`), `#ptWzCopy` (toast "הקישור הועתק" in
  `#ptToast`), `#ptWzEnter` "כניסה לטיול ←".
- Home: `#ptFirstSteps`, `#ptFsCount` "N מתוך 3", rows `#ptFs1/2/3[data-done]`, `#ptFsWa`, `#ptFsRoute` "למסלול".
  Empty day: "עוד לא נוספו נקודות" (class `pt-empty-day`). 0 days: "אין ימים בטיול".
- עוד: `#ptJoinRow` "קישור הצטרפות לקבוצה"; sheet `#ptF04Sheet` with `#ptJoinUrl`, `#ptJoinWa`, `#ptJoinCopy`.
- Storage: device key `pt:<trip_id>:firststeps` = `{"shared":true}`; `pt:_device:active_trip` written at create success.
  The OTP code, the invite token and the email are never written by F04 (only supabase-js's own session object holds the
  user's email, as before).
- Network: `POST <SUPABASE_URL>/functions/v1/create-trip` with `apikey` + `Authorization: Bearer <session JWT>`, body
  `{action:'lookup'}` / `{action:'create', name, display_name, start_date, end_date, home_currency, default_lang:'he',
  default_role, countries[], currencies[{code,kind}], center{lat,lng}}` (center = first country's capital).

## 5. Self-check results (2026-10-12, sandbox)

- `node --check`: all 7 inline script blocks of `app/index.html` (SW-register, flags, F03, **F04**, F02 gate, gm_authFailure,
  main), `invite/index.html` (1), `join/index.html` (1), `sw.js` — OK. `countries.json`, `currencies.json` parse.
- Duplicate static ids: only the pre-existing `hminHotelDocs`; no new duplicates (screen-level ids are emitted by one helper
  each). Live DOM checked on every wizard screen in the smoke: no duplicates.
- Protected functions: byte-identical vs `HEAD`.
- DB (`sudo -u postgres python3 scripts/dev/f04_db_check.py ""`, local PostgreSQL 16 + shim): 0001–0011 applied (0010 and 0011
  twice) → `qa.f01_run()` 109/109, `qa.f02_run()` 37/37, `qa.f03_run()` 49/49, **`qa.f04_run()` 90/90** (leftovers row 0/0/0),
  inline F04 scenarios 51/51, 0 leftover rows. `qa.f04_run()` re-run twice in one session: 90/90 both times.
- Existing suites (`bash tests/f03/run.sh --only f03|f02on|f02off`; HEAD baseline in the same sandbox: F03 58 passed /
  1 skipped, F02 on 37/1, F02 off 37/1):

  | Run | `WIZARD_FEATURE='on'` (as shipped) | `WIZARD_FEATURE='off'` (scratch copy) |
  |---|---|---|
  | F03 browser suite | 46 passed, 12 failed, 1 skipped | 55 passed, 3 failed, 1 skipped |
  | F02 regression · ADMIN on | 37 passed, 1 skipped | 37 passed, 1 skipped |
  | F02 regression · ADMIN off | 37 passed, 1 skipped | 37 passed, 1 skipped |

  F03 failures, all expected by spec §5.19 except the one marked ★:
  - version strings (both states): `test_ac18_static[app_version]`, `[title_version]` (pin `3.0.0-alpha.3.4`).
  - `/invite/` page (both states — that page lives outside the app and has no flag): `test_ac10_invite_page_outside_app`
    asserts the old "התחלת הקמה · בקרוב" button that F04-INV-01 replaces.
  - flag on, the F03 in-app valid landing is replaced by the F04 code screen (the F03 QA fake's `check` has no `email`, so the
    email-entry state appears): `test_ac10_landing_valid[fresh-device]`, `[linked-device]`, `test_ac10_landing_network_error_and_retry`
    (retry reaches the valid branch), `test_ac12_token_not_kept[valid]`, `test_ac17_390_rtl_touch[landing-valid]`,
    `test_ac10_invite_link_while_app_open`, `test_ac10_invite_link_encoded_and_query`, `test_ac10_invite_via_launch_queue`.
  - ★ flag on: `test_ac16_off_more_panel_identical_to_alpha2` (ADMIN_FEATURE='off' run) sees the new F04 manager row
    "קישור הצטרפות לקבוצה" at the top of עוד (spec §1.9). Not changed: hiding a spec'd F04 row because F03 is off would couple
    the two flags. QA should exclude `#ptJoinRow` in that comparison (or run it with `WIZARD_FEATURE='off'`, where it passes).
- Dev smoke (scratch, Playwright 390×844, F03 fake supabase-js extended with `verifyOtp` / `signInWithOtp` /
  `trip_join_codes` + fake `invite-manager` (check with `email`) and `create-trip`): **102/102** — token link → locked email →
  `updateUser({email})` once → wrong code (text, cleared, focus) → paste → `verifyOtp email_change` same uid → step 1
  (prefill, validation, day count, offline disables "המשך" and keeps data) → step 2 (chip order, "יפ"/"jap"/"קור", × removes the
  country and its currency, currency sheet, cap 10 + note) → step 3 (summary, עריכה keeps state, role) → create with a dropped
  response + double tap = 2 requests, 1 trip → Done (URL, wa.me, copy toast) → home (new trip, all chrome, header name, first
  steps 2/3, empty-day text on home/route/HOME-MIN pill, card disappears at 3/3) → עוד row + sheet → reload keeps the trip (D5)
  despite a newer membership; gate card → email → rate-limit text → resend → no-invite card → back to gate; D6 card with no OTP
  call; email owned by another account (no membership → `signInWithOtp {shouldCreateUser:false}` + `verifyOtp email`, identity
  switched; with membership → "already linked" card, no `signInWithOtp`); 0 / 1 / 18 empty days: no page error on any tab, never
  the seed, "אין ימים בטיול"; flag off: F03 "בקרוב" landing, no gate card, `[]` → seed; `/invite/` button href + copy; `/join/`
  clears the hash and never shows the code. No horizontal scroll, RTL, targets ≥ 44 px and no trip chrome on screens 2–7;
  no token / code / email in storage (outside supabase-js's session) or the console.

## 6. Interpretations, known limitations, open points

1. **Wrong vs expired code**: Supabase answers `otp_expired` / "Token has expired or is invalid" for both. The client shows the
   expired text only when the code is older than 1 h (time since the last send) or the error says "expired" without
   "invalid"; otherwise the wrong-code text (inputs cleared).
2. **"Already linked to another account" = no auth call**: the only way to learn that the email belongs to another account is
   the `updateUser` answer (`email_exists`), which sends nothing. With an active membership the card is shown and **no**
   `signInWithOtp` / `verifyOtp` is made; without one the device switches identity with `signInWithOtp
   {shouldCreateUser:false}`. D6 (different confirmed email) makes no auth call at all (decided from the stored session).
3. Entry mode on a device that already has a **confirmed** email: no email/code screen; `lookup` runs with that email (found →
   step 1, else the "no active invite" card).
4. Join link outside Done: rebuilt as `https://orsela.github.io/Plan_Travel/join/#code=<code>` (the function's default
   `JOIN_URL`); if Or sets a different `JOIN_URL` secret, the first-steps card / עוד sheet would still show the default base.
5. Header name (F04-HOME-02) applies only to trips whose days carry `country` (wizard trips); the Vietnam trip keeps its
   hard-coded "🇻🇳 ויאטנם" header (parity with the F02 suite). `#tripName` (v1 home) and ניהול → הגדרות מסע still read
   `planner:tripname` (not written by `create-trip`), so they show "מסע של חלומות" for a new trip until F06.
6. The `/invite/` note says to choose "קיבלתי הזמנה לנהל טיול" (spec/mockup copy), while the gate button reads "כניסה עם
   הזמנה" under the title "קיבלת הזמנה לנהל טיול?". Copy kept exactly as approved; Or may want them aligned.
7. A device that already runs a trip never sees the gate card, so on an installed iPhone app with an existing trip the only
   entry is the token link (opened in Safari it continues in Safari's storage). As specified (F09 picker later).
8. "1 ימים" is written "יום אחד" (step 1 help, step 3 and Done); every other N is "N ימים".
9. Popular chips toggle (tap again removes the country) — the spec only says they add.
10. The country cap note "אפשר לבחור עד 15 מדינות." and step validation messages are new copy (not in the mockup).
11. Not verified here (needs the real stack / Or's phone, spec §6.6): real Supabase OTP emails and templates, `verifyOtp`
    shapes from GoTrue, the deployed `create-trip`, Safari/iOS date inputs and `one-time-code` autofill.

## 7. Follow-ups after Or's review (2026-10-12)

- §6.5 resolved — **F04-DB-02**: `create_trip_from_invite` also writes `trip_kv` key `tripname` (plain text). The v1 home
  `#tripName` and ניהול → הגדרות מסע now show the entered name. Spec §2 step 5 and criterion 11 updated.
- §6.6 resolved — **F04-INV-02**: the `/invite/` installed-app note now says `"כניסה עם הזמנה"`, matching the gate button.
- QA note (★ in §5): `test_ac16_off_more_panel_identical_to_alpha2` should exclude `#ptJoinRow` when the wizard flag is on
  (the row is spec'd F04 behaviour, independent of `ADMIN_FEATURE`).
