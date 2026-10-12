# F04 — An invited manager sets up a trip in three steps · spec

<!-- CHANGE 2026-10-12 F04-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.4** (S2). Mockup approved by Or 2026-10-12: canvas https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 5 (artboards `F04_Landing`, `F04_Gate`, `F04_Code`, `F04_Step1`, `F04_Step2`, `F04_Step3`, `F04_Done`, `F04_Home`).

User value: a manager invited by email (F03) verifies the email with a 6-digit code inside the app, creates the trip in three steps (details → destinations → review), and leaves with a join link and a WhatsApp button. The new trip opens with one empty day per date — never the Vietnam seed.

Base: `app/` at 3.0.0-alpha.3 (F03, function `invite-manager` alpha.3.7). Supabase project `plan-travel` (`zwufpxnioqaweobnvffs`). The live project `vietnam-trip-2026` is never touched.

## 0. Decisions (Or, 2026-10-12)

| # | Decision |
|---|---|
| D1 | Email verification = **6-digit code typed in the app** (Supabase email OTP), not a magic link. The email is linked to the device's existing anonymous identity (same `auth.uid()`), as with Or's super-admin link in F03. |
| D2 | The wizard runs **inside the app** (`/app/`). `/invite/` stays outside the PWA scope; its button now opens the app. |
| D3 | The invite is resolved by the **verified email**, not only by the link token. This is what makes the iPhone home-screen app work (its storage is separate from Safari's, so a token opened in Safari never reaches it). Entry points: the token link (email prefilled) and a new "כניסה עם הזמנה" button on the "not connected" card (email typed). |
| D4 | A new trip starts with **one empty day per date** in the range. A cloud trip never falls back to `SEED_DATA`. |
| D5 | Until F09: the active trip on a device = **the last one selected or created** (cached `trip_id` if still an active membership, else newest `joined_at`). |
| D6 | A device whose identity already has a **different** confirmed email cannot accept the invite: a clear explanation, nothing changes. |
| D7 | Claude defaults accepted: full `countries.json`; `create-trip` atomic and idempotent; join link in the F05 format `/join/#code=<CODE>` outside the PWA scope with a "coming soon" page until F05; group language Hebrew only, English shown disabled "בקרוב" (F13); `APP_URL` hardening; invite validity re-checked at create time; review step before create (step 3 = review, then the done screen). |

## 1. Screens (match the approved artboards)

All Hebrew, RTL, 390px-safe, touch ≥44px, existing UI-kit styles (the F03 `pt-*` classes). Flag: `WIZARD_FEATURE='on'|'off'` (top-level, next to `ADMIN_FEATURE`). `off` = exactly the alpha.3 behaviour (F03 in-app landing with the disabled "בקרוב" button, no gate button, no first-steps card, seed fallback unchanged, boot picks newest membership). Screens 2–7 have **no trip chrome** (no tab bar, chat FAB, FX pill, sync card) — they exist before the trip does. Screen 8 is a trip screen with all global elements.

1. **`/invite/` page** (`F04_Landing`): valid invite → same verified card, copy "…הזמין אותך לנהל את הקבוצה "<draft>". ההקמה לוקחת כ-3 דקות.", expiry line, 4 steps (1 = "האפליקציה נפתחת ושולחת קוד בן 6 ספרות למייל שלך"), an enabled link-button **"פתיחה באפליקציה והקמת הטיול"** → `../app/?invite=1#invite=<token>`, and a note: "האפליקציה כבר מותקנת אצלך במסך הבית? אפשר לפתוח אותה משם ולבחור "כניסה עם הזמנה"." (aligned to the gate button, Or 2026-10-12) Invalid/network states unchanged from F03.
2. **Not-connected card** (`F04_Gate`, the F02 `#ptGate`): unchanged content plus a second card below: title "קיבלת הזמנה לנהל טיול?", text "נאמת את המייל שאליו נשלחה ההזמנה, ותקים את הטיול מכאן.", outline button "כניסה עם הזמנה" → the code screen in *email-entry* mode. (No "חדש · F04" badge in production — it is a mockup annotation.)
3. **Email + code** (`F04_Code`), two states in one screen:
   - *Email state* (only when no email is known): label "המייל שאליו נשלחה ההזמנה", email input (LTR), button "שליחת קוד".
   - *Code state*: title "הקוד נשלח למייל", explanation "שלחנו קוד בן 6 ספרות. מקלידים אותו כאן, בטלפון הזה – לא צריך ללחוץ על קישור במייל.", the email read-only, 6 single-digit inputs (`inputmode="numeric"`, `autocomplete="one-time-code"` on the first, LTR order, auto-advance, backspace goes back, paste of 6 digits fills all), help "הקוד בתוקף שעה. הדבקה מהמייל ממלאת את כל התיבות.", "שליחה חוזרת בעוד m:ss" (disabled for 45 s, then "שליחה חוזרת"), "לא הגיע? בדקו בספאם" (opens a one-line hint), the green privacy note, primary button "אימות והמשך להקמה" (enabled at 6 digits; also auto-submits on the 6th digit). A "שינוי מייל" link returns to the email state only in email-entry mode (not when the email came from the token).
   - Skipped entirely when the session user already has a confirmed email equal to the invite email (go straight to lookup → step 1).
4. **Step 1 · פרטי הטיול** (`F04_Step1`): progress bar 1/3 with labels פרטי הטיול / יעדים / אישור וקישור; subtitle "המייל אומת. נקים את הקבוצה בשלושה צעדים."; שם הטיול (prefilled from `draft_name`, help "מולא מההזמנה, אפשר לשנות"; 1–80 chars, `dir=auto`); השם שלך בקבוצה (1–40; prefilled from an existing display name of this user if any); יציאה / חזרה as native `<input type="date">` (displayed dd/mm/yyyy by the platform), help "<N> ימים · ייווצר יום ריק לכל תאריך"; שפת הקבוצה segmented: עברית on, English disabled with "בקרוב"; מטבע הבית select ILS / USD / EUR (default ILS). "המשך ←" validates: name, display name, both dates, end ≥ start, length 1–120 days.
5. **Step 2 · יעדים** (`F04_Step2`): search (Hebrew or English names, prefix and contains, diacritic/case-insensitive), "נפוצות" chips row (horizontal scroll), selected list "נבחרו · N" in selection order: flag, Hebrew name, "<symbol> <Hebrew currency name> · <CODE> · UTC±h <capital in Hebrew>", × (44px). Currencies block "מטבעות בטיול · K מתוך 10": home currency chip first marked "בית", the other two bases (USD/EUR/ILS minus home) shaded, destination currencies in country order (deduped, bases excluded), "+ הוספה" (the existing `CurrencySheet` design: search `currencies.json`, common-for-travellers first; added currencies get ×). Removing a country removes its destination currency unless another selected country uses it. Cap 10 total: when full, "+ הוספה" is disabled and a newly selected country whose currency doesn't fit shows an inline note "המטבע <CODE> לא נכנס – הממיר מלא (10/10). אפשר להסיר מטבע אחר." 1–15 countries required to continue. Help text: "שקל, דולר ויורו קבועים. מטבע של מדינה נוסף כשבוחרים אותה ויוצא כשמסירים אותה."
6. **Step 3 · אישור** (`F04_Step3`): title "הכול נכון?", subtitle "אחרי היצירה אפשר לשנות הכול מהגדרות הטיול."; summary card rows טיול / תאריכים (LTR range + "· N ימים") / את/ה בקבוצה ("<name> · מנהל/ת") / יעדים (flags + names) / מטבעות (codes, home marked "(בית)") — rows 1, 2, 4 have "עריכה" links back to their step (state preserved); card "הרשאה למצטרפים חדשים" segmented עורך (default) / צופה + help text. Primary "יצירת הטיול" (shows a spinner and disables while calling; double taps send once), "חזרה".
7. **Done** (`F04_Done`): check icon, "הטיול נוצר", "<name> · <flags> · N ימים"; card "קישור הצטרפות לקבוצה" with the URL (LTR, ellipsis), "שליחה בווטסאפ" (`https://wa.me/?text=` + encoded Hebrew message containing the trip name and URL) and "העתקה" (clipboard, toast "הקישור הועתק"); amber "בקרוב" card about F05; line "הקישור נשמר גם בהגדרות הטיול, אין צורך לשמור אותו עכשיו."; primary "כניסה לטיול ←" starts the trip (no full reload required, but a reload is acceptable).
8. **Home of the new trip** (`F04_Home`): the normal home screen with all global elements, trip name and dates in the header. A **"צעדים ראשונים"** card at the top for managers only, while not complete: ✓ הקמת הטיול (always done), ○ שליחת קישור לקבוצה (done after WhatsApp/copy was used on this device, from Done, the card, or the "עוד" row), ○ הוספת היעד הראשון ליום 1 (done when any day has ≥1 waypoint); buttons "שליחה בווטסאפ" and "למסלול". The card disappears when all three are done. Days with no waypoints show "עוד לא נוספו נקודות" wherever the home/route list would show the day title.
9. **"עוד" → row "קישור הצטרפות לקבוצה"** (managers only, under the trip section): opens a bottom sheet with the same link card as Done (URL, WhatsApp, copy). Reads the code from `trip_join_codes` (RLS: active managers). This is how "נשמר בהגדרות הטיול" is kept true until F06.
10. **`/join/` page** (new, outside the PWA scope, styled like `/invite/`): "Plan_Travel", card "ההצטרפות לטיול תיפתח בקרוב", text "הקישור תקין לשמירה – פתחו אותו שוב בעוד כמה ימים." It does **not** validate or display the code, and removes the hash from the address bar.

### Error and edge states (all Hebrew, one line each, inside the current screen)

| Case | Where | Text / behaviour |
|---|---|---|
| Wrong code | code | "הקוד שגוי. בדקו את המייל האחרון ונסו שוב." Inputs cleared, focus first. |
| Expired code | code | "הקוד פג. שלחו קוד חדש." |
| Too many requests | email/code | "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות." |
| Offline | any step | "אין חיבור. נסו שוב כשהרשת תחזור." Buttons disabled while offline; entered data kept. |
| No active invite for the verified email | after verify | Full card: "לא מצאנו הזמנה פעילה למייל הזה" + "בקשו ממי שהזמין אותכם לשלוח הזמנה חדשה." Button "חזרה". |
| Invite expired/revoked/used by someone else between lookup and create | step 3 | Same generic card as above; nothing created. |
| Device already linked to a different email (D6) | before sending a code | Card: "המכשיר הזה כבר מקושר למייל אחר (<masked current email>)." + "פתחו את ההזמנה במכשיר אחר, או בקשו לשלוח אותה למייל שמקושר כאן." No auth call is made. Masking: first char + "•••" + "@domain". |
| Invite email belongs to another existing account, and this anonymous device has no active trip | code | Allowed: sign in to that account with an email OTP (`signInWithOtp`, `shouldCreateUser:false`); the device switches identity. |
| Same, but this anonymous device already has an active trip membership | before sending a code | Card: "המייל הזה כבר משויך לחשבון אחר. כדי לא לאבד את הטיול שכבר במכשיר, פתחו את ההזמנה במכשיר אחר." No auth call. |
| Retry after a network failure during create | step 3 | Retrying returns the same trip (idempotent) and goes to Done. |

## 2. Database — migration `0010_f04.sql`

Idempotent, `search_path=''` everywhere, advisors clean. No new client-writable grants.

- `public.create_trip_from_invite(p_user uuid, p_email text, p_payload jsonb) returns jsonb`, `security definer`, `volatile`, `set search_path=''`. **Execute: service_role only** (revoke from public, anon, authenticated). One transaction:
  1. Normalize `p_email` (trim, lower). Lock the invite row `for update`: the newest invite with that email where `revoked_at is null`.
  2. Idempotency: if it has `used_at` and `trip_id` and the trip has an active manager membership for `p_user` → return the same result as a fresh create (`{trip_id, join_code, created:false}`).
  3. Otherwise require `used_at is null and expires_at > now()`; else raise `invite_invalid` (errcode `P0001`, message exactly `invite_invalid`).
  4. Validate payload (raise `invalid_payload` with a `detail` naming the field): `name` 1–80 after trim; `display_name` 1–40; `start_date`, `end_date` ISO dates, end ≥ start, 1–120 days; `home_currency` ∈ {ILS, USD, EUR}; `default_lang` = 'he'; `default_role` ∈ {editor, viewer}; `countries` array of 1–15 distinct `^[A-Z]{2}$`; `currencies` array of `{code ^[A-Z]{3}$, kind ∈ destination|added}` distinct and not a base code; total with the 3 bases ≤ 10 (else `too_many_currencies`); `center` `{lat −90..90, lng −180..180}`.
  5. Insert `trips` (name, dates, home_currency, default_lang, default_role, status 'active', created_by `p_user`); `trip_countries` (sort = array order); `trip_currencies`: the home currency sort 0, the other two bases sort 1–2 (kind `base`), then payload currencies sort 3… ; `trip_members` (`p_user`, display_name, role `manager`, status `active`, approved_at now); `trip_join_codes` (8 chars from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` using `extensions.gen_random_bytes`, retry on unique violation up to 5 times); `trip_kv` key `trip` = JSON array of empty days (below), `updated_by` = `p_user`. Also `trip_kv` key `tripname` = the trimmed trip name as plain text (the key the app's `getTripName()` reads; added 2026-10-12, Or).
  6. Mark the invite `used_at = now()`, `trip_id = <new id>`.
  7. Return `{trip_id, join_code, created:true}`.
- Empty day object (one per date, `day` 1…N, date `dd/mm/yyyy`):
  `{"day":i,"date":"dd/mm/yyyy","region":"","title":"","activities":"","hotel":"","cost":0,"notes":"","lat":<center.lat>,"lng":<center.lng>,"zoom":5,"waypoints":[],"country":"<first country>"}`
  (`country` is pre-filled for F08; the app ignores unknown fields.)
- `public.find_invite_for_email(p_email text) returns jsonb` — service_role only; returns `{found:true, invite_id, draft_name, inviter_name, expires_at}` for an active, unexpired, unused invite of that email, else `{found:false}`.
- QA harness `0011_qa_f04_harness.sql`: `qa.f04_run()` in the locked `qa` schema, rolled back, F01–F03 pattern (scenarios in §5 "DB").

## 3. Edge Functions

### 3.1 New `create-trip` (Deno, service role, `verify_jwt=false`; the function verifies the JWT itself)

Body `{action, …}`. Every action requires `Authorization: Bearer <user JWT>`; the user is read with the service client `auth.getUser(jwt)`. The user must have `email` and `email_confirmed_at` (else 403 `email_not_verified`). Anonymous users without email → 403 `email_not_verified`.

| action | input | does |
|---|---|---|
| `lookup` | — | `find_invite_for_email(user.email)` → `{found, draft_name, inviter_name, expires_at}` (no ids, no email echo). |
| `create` | `name, display_name, start_date, end_date, home_currency, default_lang, default_role, countries[], currencies[], center` | `rpc('create_trip_from_invite', {p_user: user.id, p_email: user.email, p_payload})`. Maps `invite_invalid` → 409 `invite_invalid`, `invalid_payload` → 400 `invalid_payload` {field}, `too_many_currencies` → 400. Success → 200 `{trip_id, join_code, join_url, created}` where `join_url = <JOIN_URL base>#code=<join_code>`; `JOIN_URL` secret optional, default `https://orsela.github.io/Plan_Travel/join/`, validated like APP_URL (must start with `https://`, end with `/`; else default). |

- CORS identical to `invite-manager` (app origin + localhost). Never log the JWT, email or payload names; log only action, status and error code.
- Rate limit (in-memory, per user id): max 10 `create` and 30 `lookup` per 10 minutes → 429 `rate_limited`.

### 3.2 `invite-manager` changes (function version alpha.4.0)

- **APP_URL hardening**: the secret is used only if it parses as a URL, starts with `https://` and the host is not empty; otherwise `DEFAULT_APP_URL` is used and a single warning line is logged (`app_url_invalid_fallback`, no value logged). Same rule for the link built in the email.
- `check` (valid case) additionally returns `email` (the invite's address). Invalid response shape unchanged (`{valid:false}`).
- Everything else byte-identical in behaviour; existing Deno tests must pass unchanged.

## 4. Client wiring (`app/index.html`, `invite/index.html`, new `join/index.html`, new `app/countries.json`, `app/currencies.json`)

- `countries.json`: every ISO-3166-1 alpha-2 country (≥ 245 entries) `{code, he, en, flag, currency, tz:[IANA…], capital:{he, en, lat, lng}, popular:bool}` where `tz[0]` is the capital's zone and `currency` is the primary ISO-4217 code. `popular` true for: TH, GR, US, IT, ES, FR, GB, DE, PT, CY, GE, VN, JP, IN, NL, CZ, HU, AT, MX, AE (order of this list = order of the chips). Hebrew names in common Israeli usage. `currencies.json`: every currency used by a country in `countries.json` plus ILS/USD/EUR `{code, symbol, he, en, common:bool}`. Both fetched lazily only when the wizard opens (network required for the wizard anyway); not added to the SW precache.
- UTC offset shown in step 2 is computed with `Intl.DateTimeFormat(…, {timeZone, timeZoneName:'shortOffset'})` for the trip start date (fallback: today).
- Auth (D1, D3, D6):
  - Current user has confirmed email = invite email → skip code.
  - Current user has a different confirmed email → D6 card.
  - Current user anonymous (no email) → `auth.updateUser({email})` (sends the *Change Email* OTP) → `auth.verifyOtp({email, token, type:'email_change'})`. Same `auth.uid()`.
  - If `updateUser` fails with `email_exists` / `user_already_exists`: if the device has no active membership → `auth.signInWithOtp({email, options:{shouldCreateUser:false}})` → `verifyOtp({email, token, type:'email'})`; else the "already linked to another account" card.
  - Resend = repeat the same send call; 45 s cooldown in the UI.
  - Never store the code, the token or the email in localStorage beyond what supabase-js itself persists; never log them.
- Token entry: the F03 in-app `#invite=` landing (when `WIZARD_FEATURE='on'`) calls `check`; valid → code screen with the returned email prefilled and locked; invalid → the F03 invalid page (unchanged). The token is cleared from the URL as in F03.
- After verify → `create-trip` `lookup`; not found → the "no active invite" card. Found → step 1 with `draft_name`.
- Create → on success: `writeCached({trip_id, role:'manager'})`, store `{join_url}` in memory for Done, show Done; "כניסה לטיול" starts the trip through the normal gate path (`setTrip`, `installStorage`, `start`) or `location.reload()`.
- Boot (D5): `resolveAndStart` prefers the cached `trip_id` when it is among the active rows; else `rows[0]` (newest `joined_at`, already the current order). With `WIZARD_FEATURE='off'` exactly the alpha.3 behaviour.
- Seed (D4): in `loadState`, when `STORAGE_BACKEND==='cloud'` and `WIZARD_FEATURE==='on'`, a stored `trip` value that parses as an array is used as-is **even when empty**; `makeSeed()` is used only when nothing is stored at all. Every screen must render without throwing with 1-day, 18-day and 0-day trips whose days have no waypoints (route/map screens fall back to the day's `lat/lng`/`zoom`; an empty trip shows the existing empty text or "אין ימים בטיול").
- First-steps state: `localStorage` key `pt:<trip_id>:firststeps` = `{shared:true}` (per device); the waypoint condition is computed from `tripData`.
- Version `APP_VERSION='3.0.0-alpha.4'`, `PT_VERSION` and `<title>` likewise; every change marked `CHANGE 2026-10-12 F04-…` stating what changed from alpha.3. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`, `SEED_DATA`, `stayBlock`, `bookingUrl`). Changes to existing function bodies limited to: `loadState` (seed rule), `resolveAndStart` (cached preference), `showCard` (second card), the F03 landing's valid branch, and version strings — each flagged in the dev notes.

## 5. Acceptance criteria

Auth and invite
1. From the token link, the code screen shows the invite email locked; from the gate button the user types it. A correct code links the email to the **same** `auth.uid()` when the device was anonymous; trip memberships of that uid are kept.
2. Wrong / expired code / rate limit / offline show the mapped Hebrew text; no navigation.
3. A device whose user already has a different confirmed email gets the D6 card and makes **no** auth call. A device whose user already has the invite email skips the code screen.
4. Invite email owned by another account: device with no active membership signs in with OTP (`shouldCreateUser:false`) and continues; device with an active membership gets the "already linked" card and makes no auth call.
5. `create-trip` refuses a JWT without a confirmed email (`email_not_verified`), and refuses create when the invite is expired, revoked, used by another trip, or replaced (`invite_invalid`); nothing is written in those cases.
6. `lookup` never returns ids, tokens or the email; `check` returns `email` only when valid; invalid response shape unchanged.

Wizard
7. Step 1 prefills the name from `draft_name`; validation per §1.4; English is disabled; day count text updates with the dates.
8. Step 2 search finds countries by Hebrew and English (e.g. "יפ" → יפן, "jap" → Japan, "קור" → both Koreas); popular chips add a country; × removes it; currencies update per §1.5; cap 10 enforced in the UI and server; the inline full-converter note appears.
9. Step 3 shows exactly what will be created; "עריכה" returns to the right step with state kept; the default-role choice is sent.
10. Double tap / retry after a network error creates exactly one trip and reaches Done.

Result
11. After create: one `trips` row with the entered fields; `trip_countries` in order; `trip_currencies` = 3 bases (home sort 0) + destinations/added; one active manager membership with the display name; one `trip_join_codes` row (8 chars, allowed alphabet); `trip_kv.trip` with N empty days, consecutive `dd/mm/yyyy` dates from start to end, `day` 1…N, `waypoints: []`, centre coords of the first country's capital, `country` = first country; `trip_kv.tripname` = the trip name, so the v1 home header and ניהול → הגדרות מסע show it (not "מסע של חלומות"); invite `used_at` and `trip_id` set.
12. Done shows the join URL `https://orsela.github.io/Plan_Travel/join/#code=<CODE>`; WhatsApp opens `wa.me` with the trip name and URL; copy writes the URL.
13. Entering the trip shows the new trip (not the Vietnam seed, not another trip of the same user), with all global elements, the first-steps card (managers only) and empty days; reloading keeps the same trip (D5).
14. Deleting all days (if the UI allows) or a stored empty array never brings back `SEED_DATA` in cloud mode with the flag on; no screen throws on 0, 1 or 18 empty days.
15. "עוד" shows "קישור הצטרפות לקבוצה" for managers only; it shows the same URL.
16. `/join/#code=…` shows the "coming soon" card and clears the hash; `/invite/` button links to `../app/?invite=1#invite=<token>`.

RLS / security
17. A non-member cannot read the new trip's rows; an editor/viewer cannot read `trip_join_codes`; `create_trip_from_invite` and `find_invite_for_email` are not executable by `anon` or `authenticated`.
18. APP_URL: a secret without `https://` (e.g. `ttps://…`), empty, or not a URL → emails use `DEFAULT_APP_URL`.

Definition of Done
19. `WIZARD_FEATURE='off'` → behaves exactly as alpha.3 (F03 and F02 suites pass unchanged in that state, except version-string assertions). With `'on'`, F02/F03 suites pass except assertions about the F03 "בקרוב" landing button, which F04 intentionally replaces.
20. 390px: no horizontal scroll, RTL, touch ≥44px; no trip chrome on screens 2–7; all global elements on screen 8.
21. Protected functions byte-identical; version + CHANGE comments; `node --check` on every script block; JSON files parse; advisors clean; `qa.f04_run()` all pass, nothing left behind; Deno tests for both functions pass.

## 6. Deployment steps (Or, one at a time, after code and QA are ready)

1. Supabase → Authentication → Emails → Templates: in **"Change email address"** and in **"Magic link"** add the line `קוד האימות שלך: {{ .Token }}` (keeping the existing link, so F03's link-email keeps working). Claude provides the exact Hebrew template text.
2. Supabase → Authentication → Providers → Email: confirm "Email OTP length" = 6 and expiry 3600 s.
3. SQL Editor: run `0010_f04.sql`, then `0011_qa_f04_harness.sql`. Claude verifies by reading and runs `qa.f04_run()`.
4. Claude deploys `create-trip` (`verify_jwt=false`) and `invite-manager` alpha.4.0 through the connector. No new secrets (optional `JOIN_URL`).
5. Claude pushes the app; GitHub Pages publishes.
6. Phone: Or sends himself an invite to a second address and runs the manual checklist `tests/f04/MANUAL.md` (code from the token link on Android; the gate button path; create; WhatsApp; reload).

## 7. Test strategy

- Client: Playwright 390×844 with the F03 fake supabase-js extended with `auth.updateUser` (email_change OTP), `auth.verifyOtp`, `auth.signInWithOtp`, a fake `create-trip` and `invite-manager` endpoint (route interception) and `trip_join_codes`. Both flag states. Mobile overflow and touch-size checks on screens 2–8.
- Functions: Deno unit tests for `create-trip` (mocked service client/RPC) and the `invite-manager` additions (APP_URL cases, `check.email`).
- DB: `qa.f04_run()` for criteria 5, 10, 11, 17 and payload validation (each invalid field), idempotency, cap 10, join-code alphabet, day generation across a month boundary and a leap day (2028-02-28 → 2028-03-01 = 3 days).
- Or's phone after deployment (§6.6).
