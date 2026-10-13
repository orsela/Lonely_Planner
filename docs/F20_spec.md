# F20 — Super-admin entry is separate from the trips · spec

<!-- CHANGE 2026-10-13 F20-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.5** (app). No database migration, no Edge Function change. Mockup approved by Or
2026-10-13: canvas https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 6, alternative A (artboards `F20_Choose`,
`F20_Admin`, `F20_SwitchSheet`). Alternative B (`F20_AdminURL`, a separate /admin/ address) was rejected.

User value: the super-admin reaches "ניהול מערכת" without first entering a trip, and moves between the admin screen and
any of their trips in one tap. Everyone with more than one trip can switch trips (the core of F09, brought forward).

Base: `main` at 3.0.0-alpha.4.2 (F04). Branch `f20`. The live project `vietnam-trip-2026` is never touched.

## 0. Decisions (Or, 2026-10-13)

| # | Decision |
|---|---|
| D1 | Alternative A: a start chooser for the super-admin + a switcher inside a trip (like Airbnb's "switch to hosting"). |
| D2 | The chooser shows **all** the user's active trips (not only the last one). |
| D3 | A device option "לפתוח תמיד ישר לטיול האחרון", **off by default**. |
| D4 | Regular users (not super-admin) boot exactly as today (cached trip, else newest membership). |
| D5 (Claude default) | The in-trip switcher (avatar button) is shown to the super-admin always, and to any user with ≥2 active trips. Its "ניהול" section only for the super-admin. A user with one trip and no admin sees no button (unchanged screen). |
| D6 (Claude default) | The "ניהול מערכת" row leaves "עוד" (it lives in the switcher). The "מייל מקושר" row stays. |

## 1. Screens (match the artboards; Hebrew, RTL, 390px, touch ≥44px, F03/F04 `pt-*` styles)

Flag: `SWITCH_FEATURE='on'|'off'` (top-level, next to `ADMIN_FEATURE` / `WIZARD_FEATURE`). `'off'` = exactly alpha.4.2.
F20 needs `STORAGE_BACKEND==='cloud'`; with `ADMIN_FEATURE==='off'` there is no admin, so no chooser and no admin
section (the switcher still lists trips for users with ≥2 trips).

### 1.1 Start chooser `#ptChoose` (artboard `F20_Choose`) — no trip chrome
Shown at boot instead of entering a trip when **all** hold: online, the client and session exist, the user is a super-admin
(`platform_admins` row for `auth.uid()`, the existing F03 check), the device option D3 is off, and the page was not
opened for a specific destination (no `#admin`, `#invite=`, wizard path, or `?trip=` — see 1.4).
- Header: brand "Lonely Planner", title "שלום <name>, לאן נכנסים?" where <name> = the display name of the user's newest
  active membership; if none, "שלום, לאן נכנסים?".
- Section "ניהול": one row (link-style button) "ניהול מערכת" / sub "כל הקבוצות והזמנת מנהלים" / badge "<N> ממתינות"
  (amber) when N>0 pending invites (status "ממתין למנהל", from the existing `admin_trip_summary()`; badge omitted when 0
  or when the call fails). Tap → the admin screen (1.2).
- Section "הטיולים שלי": one row per active membership, newest first, each: flag of the trip's first country
  (`trip_countries` sort 0, emoji from `countries.json`; none → a neutral pin icon), trip name (`trips.name`), sub
  "<תפקיד> · dd/mm–dd/mm/yyyy · <N> חברים" (role in Hebrew: מנהל / עורך / צופה; member count = active members), badge
  "אחרון" (green) on the cached trip (`pt:_device:active_trip`) if it is in the list. Tap → enter that trip (writeCached →
  setTrip → installStorage → start; no reload needed, the main script has not run yet).
- No trips: the section shows "אין עדיין טיולים" (muted) — no trip rows.
- Checkbox (label) "לפתוח תמיד ישר לטיול האחרון" — off by default; stored per device in raw key
  `pt:_device:open_last_trip` = `"1"` when on (removed when off). Changing it does not navigate.
- Footnote "המסך הזה מופיע רק לסופר-אדמין. משתמש רגיל נכנס ישר לטיול שלו." is a mockup annotation — **not** shipped.
- Loading state while the trip list loads: the header and the admin row are shown, the trips section shows a one-line
  "טוענים…"; a failure shows "לא הצלחנו לטעון את הטיולים. נסו שוב." with a "נסו שוב" button.

### 1.2 Admin screen standalone (artboard `F20_Admin`)
The existing F03 admin screen (`#admin`, all its behaviour unchanged) can now run **without a trip started**: when the
page boots with `#admin` (or the chooser's admin row is tapped) and the user is a super-admin, the trip main script is
**not** started; only the admin layer shows. Changes to its header:
- The back control "חזרה לטיול" is replaced by a button **"הטיולים שלי"** (with a swap icon) on the left: → the chooser
  (1.1) in place (no reload) when no trip has started; if a trip had started (admin opened from the switcher), → reload to
  the chooser (`location.replace(<app path>)`, no hash) — the device option D3 is ignored for this navigation (go to the
  chooser explicitly, e.g. `?choose=1`, cleaned from the URL after use).
- The subtitle shows "Lonely Planner · סופר-אדמין" (badge style as in the artboard; accent indigo #3730a3).
- Browser back from the standalone admin screen → the chooser (when it came from the chooser) — no blank page.
- A non-admin opening `#admin` boots normally into their trip (as today: the hash is cleaned).

### 1.3 In-trip switcher (artboard `F20_SwitchSheet`) — a trip screen, all global elements present
- An avatar button (44×44, circle, the first letter of the member's display name, `aria-label="החשבון שלי ומעבר בין
  טיולים"`) at the top-left of the home screen header (both `HOME_LAYOUT` v1 and v2, and `HOME_MIN` home), visible per D5.
  It must not overlap existing header controls at 390px.
- Tap → bottom sheet (the existing `openSheet` look): header with avatar, display name and the linked email (LTR) if any;
  section "הטיולים שלי": rows as in 1.1 (flag, name, "<תפקיד> · dd/mm–dd/mm"), the current trip marked with a check
  icon (`role="img" aria-label="הטיול הנוכחי"`) and sub "… · כאן עכשיו"; section "ניהול" (super-admin only): row "ניהול
  מערכת" / "יציאה מהטיול למסך הניהול" / badge "סופר-אדמין".
- Tap another trip → `writeCached` + `location.reload()` (the main script is per trip). Offline → toast "אין חיבור. נסו
  שוב כשהרשת תחזור." and stay.
- Tap "ניהול מערכת" → reload to the standalone admin screen (`#admin`) — the trip's pending offline queue is kept (it is
  per trip in localStorage and flushes next time the trip opens).
- The current trip row is not a link (tap does nothing / closes the sheet).
- The sheet closes on backdrop tap, Escape, and the browser back gesture, like other sheets.

### 1.4 Boot rules (summary)
| Situation | Result |
|---|---|
| `SWITCH_FEATURE='off'` | alpha.4.2 exactly |
| `#invite=` / F04 wizard paths | unchanged (they take over before trip boot) |
| Not super-admin | unchanged (D4) |
| Super-admin, `#admin` | standalone admin (1.2), no trip started |
| Super-admin, `?choose=1` | chooser, ignoring D3; the query is removed from the URL |
| Super-admin, D3 on, cached trip active | enter the cached trip directly (switcher available) |
| Super-admin, otherwise online | chooser (1.1) |
| Offline with a cached trip (anyone) | enter the cached trip as today (no chooser — the list needs the network) |
| Super-admin with no trips | chooser with the admin row and "אין עדיין טיולים" (instead of the "not connected" card) |
| The admin check fails (network/timeout) | behave as not super-admin (D4) — never block boot |

The admin check runs once per boot, with the existing timeout; total added boot delay for a non-admin ≤ one round trip
(the check may run in parallel with `fetchTrips`).

### 1.5 "עוד"
With the flag on, the F03 row "ניהול מערכת" (`#ptAdminRow`) is not rendered in "עוד". Everything else in "עוד" unchanged.

## 2. Data
Read-only, under existing RLS (members read their trips): `trip_members` (own active rows — already fetched),
`trips` (id, name, start_date, end_date) and `trip_countries` (trip_id, country_code, sort) for those trip ids, member
counts via `trip_members` select of `trip_id` for those trips (status active), `platform_admins` (own row),
`admin_trip_summary()` for the pending count (admin only). No new tables, columns, policies or functions. If a member
count query is not allowed by RLS for some role, omit the "· N חברים" part rather than fail.
Nothing new is cached except the D3 key and the existing `pt:_device:active_trip`.

## 3. Acceptance criteria
1. Flag off → behaves as alpha.4.2 (F02/F03/F04 suites pass in that state, except version pins).
2. Super-admin online, D3 off → the chooser shows (no tab bar, chat, FX pill, sync card); the trip main script has not
   started (e.g. `tripData` undefined / no `#home` rendering activity).
3. Chooser lists all active memberships newest-first with name, dates, role, flag; the cached one is marked "אחרון";
   tapping a trip enters it (correct trip id) without reload; the pending badge shows N when N>0.
4. Chooser admin row → standalone admin screen; its header has "הטיולים שלי" and no "חזרה לטיול"; no trip chrome;
   "הטיולים שלי" → back to the chooser; browser back from admin → chooser.
5. Opening the app at `#admin` as super-admin → standalone admin without starting a trip; as non-admin → their trip, hash
   cleaned.
6. D3 checkbox: off by default; turning it on persists `pt:_device:open_last_trip`; next boot goes straight to the cached
   trip; `?choose=1` still shows the chooser; turning it off removes the key.
7. Non-admin with 1 trip: no avatar button, boot unchanged. Non-admin with ≥2 trips: avatar button; sheet lists trips,
   no "ניהול" section; switching reloads into the chosen trip and it stays chosen after another reload.
8. Super-admin inside a trip: avatar sheet shows trips (current checked) + "ניהול מערכת"; tapping it lands on the
   standalone admin screen (no trip chrome).
9. "עוד" no longer shows "ניהול מערכת" (flag on).
10. Offline boot with a cached trip → the trip (no chooser, no error); offline tap on another trip in the sheet → toast,
    no navigation.
11. Admin check failure → normal boot (no chooser), no error shown.
12. 390px: no horizontal scroll, RTL, touch ≥44px on chooser, admin header and sheet; the avatar button does not overlap
    header controls in HOME_LAYOUT v2, v1 and HOME_MIN.
13. RLS: the chooser/sheet show only the user's own memberships; nothing new is readable by a non-member (existing
    policies; verified by the QA DB check that no new grants/policies exist).
14. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`,
    `SEED_DATA`, `stayBlock`, `bookingUrl`); versions `APP_VERSION`/`PT_VERSION` = 3.0.0-alpha.5 (title stays
    "Lonely Planner"); every change marked `CHANGE 2026-10-13 F20-…` with what changed from alpha.4.2; `node --check` on all
    script blocks; no new duplicate ids.

## 4. Deployment
Client only: merge `f20` → `main` after F04's address change is finished and Or approves. No Supabase step.
Phone check (Or): chooser on open; admin and back; switch trip from the avatar; D3 on/off; non-admin device unchanged.
