# F05 — A member joins from the group link, after manager approval · spec

<!-- CHANGE 2026-10-19 F05-DOCS-02: §2 — the two new tables and the internal helpers live in a new schema `private` (closed to
     clients, so `public` keeps exactly the 9 F01 tables and the F02–F04 catalog checks stay valid); business refusals are
     returned as {"error":code} instead of raised, so rate-limit attempt rows survive. -->
<!-- CHANGE 2026-10-19 F05-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.6** (app + `/join/` page), migration **0012_f05.sql** (+ QA harness **0013**), two new Edge
Functions **`join-trip`** and **`approve-member`** (alpha.6.0). Mockup approved by Or 2026-10-19: canvas
https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 7 (artboards `F05_Join`, `F05_Pending`, `F05_Approved`,
`F05_Transfer`, `F05_HomeManager`, `F05_Invalid`).

User value: a family member opens the WhatsApp link, types a name and is in the trip as soon as the manager approves —
no email, no password. The manager approves from the home screen. Every member is recorded under their own name.

Base: `main` at 3.0.0-alpha.5.1 (F20, 870612a). Branch `f05`. Push rule (INDEX): client code that needs the new server
stays on `f05` until the migration and functions are deployed. The live project `vietnam-trip-2026` is never touched.

## 0. Decisions

| # | Decision |
|---|---|
| D1 (Or) | **iPhone:** join in the browser; after approval the browser shows a **transfer code** (6 digits, 24 h, single use). The first launch of the installed app (not connected) accepts it and moves the membership to the app's identity. Android/desktop: no code (the installed app shares the browser's storage). |
| D2 (Or) | The manager learns of requests from a **"ממתינים לאישור" card at the top of the home screen**, managers only, with approve/reject in place. No email, no badge on the avatar. |
| D3 (Or) | **Role chosen at approval:** viewer / **editor (preselected)** / manager. |
| D4 (Or) | **Bots:** rate limits in the database (per identity, per IP hash, per code). No Turnstile now (before inviting outside groups). |
| D5 (Claude default) | Name 1–40 chars after trim; unique in the trip among pending+active members, case- and space-insensitive. |
| D6 (Claude default) | Reject deletes the pending row. The same identity may request again: ≤3 requests per trip per 24 h. |
| D7 (Claude default) | Identity already active in the trip → the link opens the trip directly. Pending → the waiting screen. Removed → "הוסרת מהטיול – פנו למנהל". |
| D8 (Claude default) | Identity active in another trip → joining adds a trip (switching via the F20 avatar). |
| D9 (Claude default) | Unknown or rotated code → one message "הקישור כבר לא פעיל". The rotate button stays in F06. |
| D10 (Or, from F04) | In F05: "מי אני" in cloud mode = the member's `display_name` (fixes the F04 bug where a new trip wrote "דנה"); the fixed `USERS` list is replaced by the trip's active members. |

## 1. Screens (Hebrew, RTL, 390px, touch ≥44px, existing `pt-*` styles; brand "Lonely Planner" everywhere)

Flag: `JOIN_FEATURE='on'|'off'` in the app (next to `SWITCH_FEATURE`) and in `/join/` (top-level const). `'off'` = alpha.5.1
exactly (and `/join/` = the F04 "בקרוב" page).

### 1.1 `/join/#code=<CODE>` (artboard `F05_Join`) — browser page, outside the PWA scope, no trip chrome
- On load: read `code` from the hash, keep it in memory (sessionStorage key `lp:join_code` so a reload works), **remove the
  hash from the address bar** (as today). Load supabase-js, ensure a session (`signInAnonymously` when none — same origin
  as `/app/`, so the same browser identity is shared).
- Call `join-trip` `{action:'preview', code}` → header: "<manager> מזמינה/מזמין אותך להצטרף לטיול", trip name, dates
  dd/mm–dd/mm/yyyy, "<N> ימים · <M> חברים". (Gendered verb: neutral form "מזמין/ה" is acceptable; the manager is the
  trip's earliest active manager.)
- Card: label "איך קוראים לך?", input (maxlength 40, autofocus), help "כך יראו אותך שאר החברים, וכך יירשמו ההוצאות
  שלך.", button "בקשת הצטרפות" → `{action:'request', code, display_name}`.
- Three ticks: "בלי מייל ובלי סיסמה", "<manager> מאשר/ת את הבקשה, והטיול נפתח כאן לבד", "הטלפון הזה יזוהה אוטומטית
  בפעם הבאה". Footer "מה שתזינו בטיול גלוי רק לחברי הקבוצה."
- Preview results that skip the form: `member_active` → go to 1.3 (or straight to the app on Android/desktop);
  `member_pending` → 1.2; `member_removed` → message (D7); `code_invalid` → 1.6a.
- Errors on request: `name_taken` → inline 1.6b; `rate_limited` → toast "יותר מדי ניסיונות. נסו שוב מאוחר יותר.";
  offline → toast "אין חיבור. נסו שוב כשהרשת תחזור."; anything else → "משהו השתבש. נסו שוב."

### 1.2 Waiting (artboard `F05_Pending`)
- Title "הבקשה נשלחה ל<manager>", text, pill "ממתין לאישור · <name>", three-step progress (sent ✓ / waiting / opened).
- Updates **without a manual refresh**: Realtime subscription on `trip_members` filtered `id=eq.<member_id>` (the row is
  visible to its owner under existing RLS) **plus** a poll every 20 s (and on `visibilitychange` → visible). Active → 1.3;
  row gone → 1.6c.
- Button "ביטול הבקשה" → `{action:'cancel', trip_id}` (deletes own pending row) → back to 1.1.
- The mockup's "(במוקאפ: …)" link is an annotation — **not** shipped.

### 1.3 Approved (artboard `F05_Approved`)
- Title "<manager> אישר/ה – ברוכים הבאים, <name>!", "הצטרפת לטיול כ<role>" (עורך/ת · צופה · מנהל/ת).
- **iPhone/iPad Safari, not standalone** (`/iPad|iPhone|iPod/` or iPadOS desktop-UA + touch, and not
  `navigator.standalone`): card "מוסיפים את האפליקציה למסך הבית" with the 3 steps and the transfer code from
  `{action:'issue_transfer', trip_id}` shown as "482 916" (LTR, monospace, copy button `aria-label="העתקת הקוד"`), "בתוקף
  24 שעות · פעם אחת". Secondary button "לא עכשיו – פתיחת הטיול כאן" → write `pt:_device:active_trip` = this trip and
  open `/app/`. Re-entering 1.3 issues a new code (the previous unused one dies).
- **Other platforms:** no code card; primary button "פתיחת הטיול" (same action) and the line "אפשר גם להתקין את
  האפליקציה – היא תמשיך עם אותה זהות."

### 1.4 Installed app, not connected (artboard `F05_Transfer`) — no trip chrome
Replaces the F04 "לא מחובר" card content when `JOIN_FEATURE='on'` and the device has no active membership:
- Title "כמעט שם", text "הטלפון הזה עוד לא מחובר לטיול. הצטרפת בספארי? מקלידים את קוד ההעברה שקיבלת שם."
- Six digit boxes (LTR, `inputmode="numeric"`, paste fills all, auto-advance), help text, button "כניסה לטיול" →
  `join-trip` `{action:'claim_transfer', code}` → on success cache the trip and start it (no reload needed).
  `transfer_invalid` (wrong/used/expired) → "הקוד לא תקף. פותחים שוב את קישור ההצטרפות בספארי ומקבלים קוד חדש.";
  `rate_limited` → as 1.1.
- "דרכים אחרות": (a) "יש לי קישור הצטרפות מווטסאפ" → a field to paste the link or the 8-char code → the 1.1 flow inside
  the app (same screens, rendered in the gate; works for Android users who installed first); (b) "כניסה עם הזמנה
  (מנהלים)" → the existing F04 flow, unchanged.

### 1.5 Manager home card (artboard `F05_HomeManager`) — trip screen, all global elements present
- Shown at the **top of home** (above the sync card is not required — under it, as drawn), for **active managers only**,
  when the trip has ≥1 pending member. Both `HOME_LAYOUT` v1/v2 and `HOME_MIN`.
- Header "ממתינים לאישור · <N>" + "רק מנהלים רואים". Rows newest first: avatar letter, name, "ביקש/ה להצטרף · לפני X"
  (relative time). The **first** row is expanded: role segmented control (צופה / **עורך** preselected / מנהל, `aria-pressed`)
  and buttons "אישור כ<role>" + "דחייה". Other rows are collapsed with "פתיחה" (expands that row, collapses the other).
- Approve → `approve-member` `{member_id, decision:'approve', role}`; reject → confirm sheet "לדחות את הבקשה של <name>?"
  → `{decision:'reject'}`. Row disappears; toast "<name> הצטרף/ה כ<role>" / "הבקשה נדחתה".
- Live: Realtime on `trip_members` `trip_id=eq.<trip>` while home is open (+ refresh on visible and on sync). Offline → the
  card shows the last known list with buttons disabled and "אין חיבור".
- Errors: `not_pending` (someone else already handled it) → toast "הבקשה כבר טופלה" and refresh; `not_manager` → hide card.

### 1.6 Error states (artboard `F05_Invalid`)
a. Code unknown/rotated → card "הקישור כבר לא פעיל" + text (no form).
b. Name taken → red input + message `יש כבר "<name>" בטיול. אפשר להוסיף אות או שם משפחה, למשל "<name> ל".`
c. Rejected (row gone while waiting) → card "הבקשה לא אושרה" + "בקשה חדשה" (back to 1.1 with the name prefilled) + "עד 3
   בקשות ביום מאותו טלפון."

### 1.7 "מי אני" and member names (D10)
With `STORAGE_BACKEND==='cloud'` and `JOIN_FEATURE='on'`:
- `activeUser` = the current membership's `display_name` (from the boot's `trip_members` query); the user modal is never
  opened and `KEYS.user` is neither read nor written. Local backend: unchanged.
- The member list (chips/colors in the vault, the personal budget label, any `USERS` use) = active members of the trip
  ordered by `joined_at`, cached per trip (`pt:<trip>:members`) for offline; colors by index as today. Fallback when the
  list is empty/unavailable: the current user only. `USERS` itself stays in the code (protected seed data path).

## 2. Data — migration 0012_f05.sql (Or runs it in the SQL Editor; Claude verifies by reading)

0. New schema `private` (no usage for anon/authenticated; not exposed by the API). Tables 1–2 and the internal helpers
   (`private.f05_*`) live there; the six entry functions in item 3 live in `public`.
1. `private.transfer_codes` — `id uuid pk`, `member_id uuid not null → trip_members(id) on delete cascade`, `code_hash text
   not null` (SHA-256 hex of the 6 digits + a server pepper is **not** needed: the table has no policies), `expires_at
   timestamptz not null`, `used_at timestamptz`, `created_at timestamptz default now()`. Partial unique index on
   `code_hash where used_at is null`. Index on `member_id`. RLS on, **no policies** (service role only).
2. `private.join_attempts` — `id bigint identity pk`, `kind text check in ('preview','request','claim')`, `user_id uuid`,
   `trip_id uuid`, `ip_hash text`, `ok boolean`, `at timestamptz default now()`. Index `(kind, user_id, at)`, `(kind,
   ip_hash, at)`, `(trip_id, at)`. RLS on, no policies. Rows older than 7 days are deleted by the functions
   opportunistically (no cron).
3. Security-definer SQL functions (`set search_path=''`, executable by `service_role` only), called by the Edge Functions —
   the same pattern as `create_trip_from_invite`:
   - `join_preview(p_user, p_code)`, `join_request(p_user, p_code, p_name)`, `join_cancel(p_user, p_trip)`,
     `issue_transfer(p_user, p_trip)` (returns the plain 6 digits once; voids earlier unused codes of that member),
     `claim_transfer(p_user, p_code)` (moves `trip_members.user_id` to `p_user`, marks used; fails with
     `already_member` if `p_user` already has a row in that trip), `approve_member(p_user, p_member, p_decision, p_role)`.
   - Refusals are **returned** as `{"error":<code>}` (not raised, so attempt rows are kept), fixed codes: `code_invalid`, `name_taken`, `name_invalid`, `rate_limited`,
     `member_removed`, `transfer_invalid`, `already_member`, `not_manager`, `not_pending`, `not_member`, `role_invalid`,
     `invalid_request`.
4. Rate limits (D4), counted in `join_attempts`: preview ≤30/h per user and ≤60/h per ip_hash; request ≤3 per (user, trip)
   per 24 h and ≤10/h per ip_hash; claim ≤5 failed per user per hour and ≤20 failed per ip_hash per hour. A trip may hold
   at most 20 pending rows (`request` → `rate_limited` beyond that).
5. No change to existing tables, policies or grants. `trip_members` stays writable only by the functions.

## 3. Edge Functions (Claude deploys; `verify_jwt=false`, JWT checked in code like `create-trip`)
- `join-trip`: actions `preview | request | cancel | issue_transfer | claim_transfer`. Any authenticated identity
  (anonymous included). ip_hash = SHA-256 of the first `x-forwarded-for` address (never stored raw). CORS for the app
  origin. Version header `alpha.6.0`.
- `approve-member`: `{member_id, decision:'approve'|'reject', role?}`; caller must be an active manager of that trip.
  Approve: status → active, role (default `trips.default_role`), `approved_at=now()`. Reject: delete row.
- Both return `{ok:true,…}` or `{ok:false, code}` with HTTP 200/4xx as in F04; the client maps `code` to the texts above.
- No secrets needed beyond the existing service role.

## 4. Acceptance criteria
1. Flag off → alpha.5.1 behaviour (F02/F03/F04/F20 suites pass, except version pins); `/join/` shows "בקרוב".
2. `/join/#code=VALID` with a fresh identity: preview shows trip name, dates, member count, manager name; hash removed.
3. Request with a valid name → a `pending` row with that name and the caller's uid; waiting screen shows.
4. Manager approves (any role) → within ≤3 s with Realtime (≤20 s by poll alone) the waiting screen changes to approved,
   without reload; the row is `active` with the chosen role and `approved_at` set.
5. Reject → the row is deleted; the waiting screen shows 1.6c; a new request works; the 4th request within 24 h →
   `rate_limited`.
6. Name taken (pending or active, case/space-insensitive) → `name_taken`, no row created. Empty/41-char name → `name_invalid`.
7. Unknown code and a code whose trip was rotated (simulated by changing `trip_join_codes.code`) → `code_invalid`, 1.6a.
8. Already active identity opens the link → no new row; approved/open path. Pending → waiting. Removed → message.
9. Transfer (D1): `issue_transfer` returns 6 digits; `claim_transfer` from a second identity moves the membership (same
   member id, new uid); the old identity no longer sees the trip; a second claim → `transfer_invalid`; an expired code →
   `transfer_invalid`; 6 wrong claims in an hour → `rate_limited`. Issuing again voids the earlier unused code.
10. Not-connected app screen (1.4) shows the code entry and the two alternatives; pasting a join link inside the app runs the
    join flow; "כניסה עם הזמנה" behaves as F04.
11. Manager home card: visible only to active managers with ≥1 pending; editors/viewers never see it; editor preselected;
    approving as viewer/manager stores that role; a second manager approving the same row → `not_pending` toast; the card
    updates live when a new request arrives.
12. `approve-member` by a non-manager, by a manager of another trip, or for an active row → `not_manager` / `not_pending`.
13. "מי אני": in a trip joined via F05 the name shown on home/budget and written as `by` on a new expense/check-in is the
    member's `display_name`, never a stale device name; the user modal never opens in cloud mode. Vault chips list the
    active members.
14. RLS: a pending member reads 0 rows of `trip_kv`/`trips` details beyond what preview returns; `transfer_codes` and
    `join_attempts` are unreadable/unwritable by `authenticated` and `anon`; no new policies or grants on existing tables
    (QA DB check `qa.f05_run()`).
15. 390px: no horizontal scroll, RTL, touch ≥44px on all six screens; the home card does not push global elements out of
    place; the code boxes are LTR.
16. Offline: `/join/` and 1.4 show the offline toast and keep input; the home card shows disabled buttons.
17. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`,
    `SEED_DATA`, `stayBlock`, `bookingUrl`); `APP_VERSION`/`PT_VERSION` = 3.0.0-alpha.6; every change marked
    `CHANGE 2026-10-19 F05-…` with what changed from alpha.5.1; `node --check` on all script blocks; no duplicate ids;
    Supabase advisors: no new warning.

## 5. Deployment (one step at a time, Or confirms each)
1. Or runs `0012_f05.sql` then `0013_qa_f05_harness.sql` in the SQL Editor; Claude verifies (`qa.f01–f05_run()`).
2. Claude deploys `join-trip` and `approve-member`.
3. Claude merges `f05` → `main` (app + `/join/`).
4. Phone check (Or): from a second phone/incognito open the WhatsApp link → name → approve on Or's phone (as editor) →
   opens by itself; on an iPhone: add to home screen → transfer code → trip opens; reject flow once.
