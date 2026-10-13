# F20 · dev notes — the super-admin entry is separate from the trips (v3.0.0-alpha.5)

<!-- CHANGE 2026-10-13 F20-DOCS-02: new file (no previous version). -->

Contract: `docs/F20_spec.md` (mockup approved 2026-10-13, canvas row 6, alternative A: artboards `F20_Choose`, `F20_Admin`,
`F20_SwitchSheet`). Base: `app/` at 3.0.0-alpha.4.2 (F04). Client only: no migration, no Edge Function, no `sw.js` change.
Nothing was deployed, pushed, committed or run against Supabase. All checks below are local (sandbox, fake supabase-js).

## 1. What changed (file / area → why)

All changes are in `app/index.html`.

| File / area | CHANGE ID | What changed from 3.0.0-alpha.4.2 | Spec |
|---|---|---|---|
| flags script | F20-FLAG-01 | new top-level `const SWITCH_FEATURE='on'` (next to `ADMIN_FEATURE` / `WIZARD_FEATURE`) | §1 |
| head, new style + script block between the F04 block and the F02 gate block | F20-UI-01 | all F20 UI and logic (sub-areas below). Returns on its first line when `SWITCH_FEATURE!=='on'` or `STORAGE_BACKEND!=='cloud'`; exposes only the frozen `window.__ptF20 = {version, attach, check, route, adminHead}` | §1, §2 |
| ↳ same block | F20-BOOT-01 / -02 | `check()` = own `platform_admins` row (never rejects, failure = not admin); `route(rows, cached, check)` = the boot decision table §1.4 (see §2 below) | §1.4 |
| ↳ same block | F20-BOOT-03 | the admin check has its own bound `PT_ADMIN_CHECK_MS = 2500` (was the gate's 8 s `PT_TIMEOUT_MS` in the first draft); a timeout = not super-admin → normal boot. Still parallel with `fetchTrips` (architect decision 2026-10-13) | §1.4 |
| ↳ same block | F20-CHOOSE-01 | start chooser `#ptChoose` (no trip chrome: `html.pt-choose` hides every other body child): brand, "שלום <name>, לאן נכנסים?", "ניהול" row + pending badge, "הטיולים שלי" rows (flag, name, role · dates · members, "אחרון"), loading / failure / empty states; tap → enter the trip without reload | §1.1 |
| ↳ same block | F20-D3-01 | checkbox "לפתוח תמיד ישר לטיול האחרון" → raw key `pt:_device:open_last_trip` = `"1"` / removed | §1.1, D3 |
| ↳ same block | F20-ADMIN-02 | standalone admin (no trip started): history handling (`#admin` entry pushed from the chooser, browser back / forward, `hashchange`), "הטיולים שלי" → chooser in place, or reload to `?choose=1` when a trip had started; a MutationObserver returns to the chooser if the F03 screen closes itself (rights revoked) | §1.2 |
| ↳ same block | F20-ADMIN-03 (F20 side) | `adminHead(el)`: rebuilds the admin header after each F03 render: shield icon, F03's own `h1#ptAdminTitle` (moved, not re-created), subtitle "Lonely Planner · סופר-אדמין" (badge), button `#ptAdminSwitch` "הטיולים שלי" with a swap icon instead of `#ptAdminBack` | §1.2 |
| ↳ same block | F20-SWITCH-01 | avatar button (44×44, first letter of the member's display name) in the home header of `HOME_LAYOUT` v2 / HOME-MIN (`#homeV2 .hv2-head`, left group) and v1 (`#home .homehero-top`), per D5; bottom sheet `#ptF20Sheet` (trips, current trip ✓, "ניהול" for the super-admin); switch = `writeCached` + reload; admin = reload to `#admin`; offline → toast; closes on backdrop / Escape / × / browser back | §1.3 |
| F03 block, `renderAccount` | F20-MORE-01 | **one new line** after `card.innerHTML=h`: with `window.__ptF20` present, `#ptAdminRow` is removed (not rendered in "עוד"); "מייל מקושר" / "קישור מייל לחשבון" unchanged | §1.5, D6 |
| F03 block, `renderAdmin` | F20-ADMIN-03 | **one new line** at the end: `if(window.__ptF20)window.__ptF20.adminHead(el);` | §1.2 |
| F03 block, before the `__ptF03` export | F20-ADMIN-01 | **new lines only**: `adminSolo()` (= existing `openAdmin(false)` for a verified admin + the screen's click handler on the element, because `onStarted` has not run), `adminSoloClose()` (closeAdmin's clean-up without `switchPanel` / `refreshAccount` / `history.back`), online/offline re-render while no trip runs; exported as frozen `window.__ptF03Admin {open, close, isOpen, isAdmin}` only when `SWITCH_FEATURE='on'` | §1.2 |
| F02 gate, `resolveAndStart` | F20-BOOT-01 | **one new line** before `fetchTrips`: `const f20=window.__ptF20?window.__ptF20.check():null;` (admin check in parallel) | §1.4 |
| F02 gate, `resolveAndStart` | F20-BOOT-02 | **one new line** after `fetchTrips`: `if(f20&&await window.__ptF20.route(rows,cached,f20))return;` | §1.4 |
| F02 gate, before the F03 bridge | F20-GATE-01 | **new lines only**: `window.__ptF20.attach({…})` (client, uid, timeout helper, `activeTrips`, cached trip read/write/clear, raw `pt:_device:` keys, `enterTrip` = writeCached → setTrip → installStorage → start, `started`/`tripId`/`role`, `phase` → `__PT.phase` = `choose` / `admin` while no trip runs) | §1.4 |
| F02 gate, `PT_VERSION` | F20-VER-02 | `'3.0.0-alpha.4.2'` → `'3.0.0-alpha.5'` | §3.14 |
| main script, `APP_VERSION` | F20-VER-01 | `'3.0.0-alpha.4.2'` → `'3.0.0-alpha.5'`, appended to the CHANGE chain on that line | §3.14 |
| `<title>` | — | unchanged: `Lonely Planner` | §3.14 |

Lines removed/changed in `app/index.html` vs `HEAD` (alpha.4.2): exactly **2** — `PT_VERSION` and `APP_VERSION`. Everything
else is additive (the main script differs only in the `APP_VERSION` line).

## 2. Existing code touched and runtime hooks

Existing function bodies with new lines (no existing statement edited):
1. `renderAccount` (F03) — F20-MORE-01: 1 line. `'off'`: `window.__ptF20` undefined → no-op.
2. `renderAdmin` (F03) — F20-ADMIN-03: 1 line. `'off'`: no-op.
3. `resolveAndStart` (gate) — F20-BOOT-01 + F20-BOOT-02: 2 lines. `'off'`: `f20` is `null`, the second line is skipped.
4. Version strings: `PT_VERSION`, `APP_VERSION`.

New code inside existing blocks (not inside existing functions): F20-ADMIN-01 (F03 IIFE, new functions + export), F20-GATE-01
(gate IIFE, attach). Protected functions (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`, `SEED_DATA`,
`stayBlock`, `bookingUrl`): **byte-identical** to `git show HEAD:app/index.html`. No main-script function is wrapped or patched.

Runtime hooks (new code only):
- MutationObservers on `<html class>`: start hook (like F03/F04) and the "F03 admin closed itself in standalone mode" guard.
- DOM injection only: avatar buttons appended into the existing home header rows; one CSS rule
  `#home .homehero-top:has(>.pt-f20-av)>.menuic{margin-inline-start:auto…}` keeps v1's ⚙️ next to the avatar (it only
  matches when the F20 avatar is in that row).
- `hashchange` (acts only while no trip runs; inside a trip F03's own listener handles `#admin` as before) and `popstate` (the
  switch sheet's history entry). The sheet pushes a state without changing the URL; leaving the trip from the sheet first
  undoes that entry, then reloads.

Boot decision (`route`, called only online with client + session, after `fetchTrips` succeeded):

| Situation | Result |
|---|---|
| not super-admin / check failed | `false` → gate continues unchanged (D4). Exception, see §6.6: `WIZARD_FEATURE='off'` + cached trip still active → F20 enters the cached trip itself |
| super-admin, `?trip=` in the URL | `false` (normal boot) |
| super-admin, `#admin` | standalone admin, no trip started |
| super-admin, D3 on, `?choose=1` absent, cached trip active | `enterTrip(cached)` |
| super-admin otherwise (also 0 trips; then `pt:_device:active_trip` is cleared as on the card path) | chooser |

`?choose=1` is read and removed from the address bar when the F20 block loads (before the gate runs). Offline with a cached
trip, library / sign-in failure and a failed `fetchTrips` never reach `route` → unchanged alpha.4.2 paths (no chooser).

## 3. Flags

| Flag | Values | Default | Effect |
|---|---|---|---|
| `SWITCH_FEATURE` | `'on'` / `'off'` | `'on'` | `off` = alpha.4.2 exactly: the F20 block returns on its first line, `window.__ptF20` and `window.__ptF03Admin` are undefined, the 4 hook lines are no-ops, styles match nothing (no `pt-f20-*` element is ever created). |
| `ADMIN_FEATURE` | unchanged | `'on'` | `off`: no admin at all — no `platform_admins` query by F20, no chooser, no "ניהול" section; the switcher still appears for users with ≥2 trips. |
| `WIZARD_FEATURE` | unchanged | `'on'` | independent; see §6.6 for the `off` combination. |
| `STORAGE_BACKEND` | unchanged | `'cloud'` | `local-only` disables all of F20. |
| `APP_VERSION` / `PT_VERSION` | `'3.0.0-alpha.5'` | | |

## 4. For QA — stable ids and visible texts

Chooser — `<main id="ptChoose" dir="rtl" aria-labelledby="ptChooseTitle">`, `html.pt-choose` while shown (no tab bar, chat
FAB, FX pill, sync card), `window.__PT.phase === 'choose'`, `window.__PT.started === false`, `tripData` undefined.
- `#ptChooseTitle` (h1): "שלום <name>, לאן נכנסים?" / "שלום, לאן נכנסים?"; brand "Lonely Planner" above it.
- Section "ניהול" (super-admin only): `button#ptChooseAdmin` — "ניהול מערכת" / "כל הקבוצות והזמנת מנהלים"; badge
  `#ptChoosePending` "<N> ממתינות" (only when N>0; N = invites with status `pending`).
- Section "הטיולים שלי" (`#ptChooseTripsTitle`), list `#ptChooseTrips` (role=group): one `button.pt-f20-card[data-trip="<trip_id>"]`
  per active membership, newest first; inside: flag (`.pt-f20-flag`, emoji or a pin svg), `b` = trip name, `.pt-f20-sub` =
  "<מנהל|עורך|צופה> · dd/mm–dd/mm/yyyy · <N> חברים" ("חבר אחד" for 1; dates "dd/mm/yyyy–dd/mm/yyyy" when the years differ;
  the members part is omitted when that query fails); badge `#ptChooseLastBadge` "אחרון" on the cached trip.
- States in `#ptChooseTrips`: `#ptChooseLoading` "טוענים…" (aria-busy), `#ptChooseErr` "לא הצלחנו לטעון את הטיולים. נסו
  שוב." + `#ptChooseRetry` "נסו שוב" (offline: "אין חיבור. נסו שוב כשהרשת תחזור." + the same button), `#ptChooseNone` "אין
  עדיין טיולים".
- Checkbox `input#ptChooseD3[type=checkbox]` inside `label[for=ptChooseD3]` "לפתוח תמיד ישר לטיול האחרון" (the native input is
  transparent over a 44×44 box; the visible square is `.pt-f20-box`). Raw key `pt:_device:open_last_trip` = `"1"` when on,
  absent when off.
- The mockup footnote "המסך הזה מופיע רק לסופר-אדמין…" is not shipped.

Admin screen (F03 `#admin`, unchanged ids) — header with F20 on: `#ptAdminTitle` "ניהול מערכת", `.pt-adm-head .pt-sub`
textContent "Lonely Planner · סופר-אדמין" (badge `.pt-badge.adm`), `button#ptAdminSwitch` "הטיולים שלי"; `#ptAdminBack` is
absent. Standalone: `html.pt-admin-open`, `__PT.phase === 'admin'`, `__PT.started === false`, URL hash `#admin`.

In-trip switcher — avatar `button#ptAvatarBtn` (in `#homeV2 .hv2-head`, v2 and HOME-MIN) and `button#ptAvatarBtnV1` (in
`#home .homehero-top`, v1); both carry `data-pt-switch`, `aria-label="החשבון שלי ומעבר בין טיולים"`, `aria-haspopup=dialog`;
text = first letter of the member's display name. Absent for a non-admin with one trip.
- Sheet: `#ptF20Sheet` (layer; `hidden` when closed), `#ptF20SheetBox` (role=dialog, aria-modal, aria-label "מעבר בין טיולים"),
  `#ptSwitchName` (display name), `#ptSwitchEmail` (LTR, `hidden` when no email), close × `[data-f20-close][aria-label=סגירה]`.
- "הטיולים שלי": `#ptSwitchTrips`; current trip = `div.pt-f20-row[data-trip-current="<id>"][aria-current=true]` with sub
  "<תפקיד> · כאן עכשיו" and `svg[role=img][aria-label="הטיול הנוכחי"]`; other trips = `button.pt-f20-row[data-trip="<id>"]`
  with sub "<תפקיד> · dd/mm–dd/mm"; states `#ptSwitchLoading`, `#ptSwitchErr` + `#ptSwitchRetry`.
- "ניהול" (super-admin only): `button#ptSwitchAdmin` "ניהול מערכת" / "יציאה מהטיול למסך הניהול" / badge "סופר-אדמין".
- Offline tap on a trip (or on "ניהול מערכת") → toast `#ptToast` "אין חיבור. נסו שוב כשהרשת תחזור.", no navigation.
- "עוד": `#ptAdminRow` is never in the DOM with the flag on.

Network (read-only, existing RLS): `platform_admins.select('user_id').eq('user_id',uid).maybeSingle()` once per boot;
`trips.select('id,name,start_date,end_date').in('id',ids)`, `trip_countries.select('trip_id,country_code,sort').in('trip_id',ids)`,
`trip_members.select('trip_id').in('trip_id',ids).eq('status','active')` — on the chooser, and on the first sheet open inside a
trip; `rpc('admin_trip_summary')` on the chooser (admin only); `GET countries.json` (flags). Nothing new is cached.

## 5. Self-check results (2026-10-13, sandbox)

- After F20-BOOT-03 (re-run): `node --check` 8/8 OK, no new duplicate ids, protected functions identical; dev smoke **15/15**
  (new case: admin check hanging → trip boots in 2.64 s, no chooser); `bash tests/f04/run.sh --only f04`: 122 passed, 4
  failed — the same 4 as below. The full matrix below was run before F20-BOOT-03 (that change only shortens one timeout).
- `node --check`: all 8 inline script blocks of `app/index.html` (SW-register, flags, F03, F04, **F20**, F02 gate,
  gm_authFailure, main) — OK (blocks extracted with HTML comments skipped).
- Duplicate static ids: only the pre-existing `hminHotelDocs`; no new duplicates (F20 reuses F03's `#ptAdminTitle` element
  instead of emitting a second one). Live DOM: one id per element on the chooser, admin header and sheet.
- Protected functions: **byte-identical** vs `HEAD` (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`,
  `SEED_DATA`, `stayBlock`, `bookingUrl`). `<title>` = "Lonely Planner"; `APP_VERSION` = `PT_VERSION` = `3.0.0-alpha.5`.
- Existing suites, `bash tests/f04/run.sh` (F04 + F03 wizard on/off + F02 wizard on/off + Deno), same sandbox. Baseline =
  `HEAD` (alpha.4.2) copy: F04 126/126, F03 47/1 skipped (on) · 55/1 (off), F02 36/1 · 36/1, Deno 31 / 9 / 21 — all green.

  | Run | `SWITCH_FEATURE='on'` (as shipped) | `SWITCH_FEATURE='off'` (scratch copy) |
  |---|---|---|
  | F04 browser suite | 122 passed, 4 failed | 124 passed, 2 failed |
  | F03 regression · wizard on | 30 passed, 17 failed, 1 skipped | 47 passed, 1 skipped |
  | F03 regression · wizard off | 38 passed, 17 failed, 1 skipped | 55 passed, 1 skipped |
  | F02 regression · wizard on / off | 36 / 36 passed, 1 / 1 skipped | 36 / 36 passed, 1 / 1 skipped |
  | Deno: F04 function / create-trip / invite-manager | 31 / 9 / 21 ok | 31 / 9 / 21 ok |

  Failures, all caused by the spec:
  - version pins (both states): F04 `test_c21_static[app_version]`, `[pt_version]` (`3.0.0-alpha.4.2`). The F03/F02 version
    tests are already deselected by `run.sh`.
  - flag on, F03 (same 17 in both wizard states): every admin-screen test boots a super-admin and waits for the trip home
    (`wait_ready`) — with F20 the super-admin lands on the chooser (§1.1), and the admin screen is no longer in "עוד" (§1.5):
    `test_ac02_admin_entry_for_admin`, `test_ac02_admin_rpc_refused_shows_no_list`, `test_ac03_admin_screen_shows_no_trip_content`,
    `test_ac04_invite_sheet_create_sends_and_refreshes`, `test_ac05_invite_exists_notice_and_resend_existing`,
    `test_ac05_invite_sheet_validation`, `test_ac07_actions_sheet_rows_and_resend`, `test_ac08_actions_sheet_revoke_with_confirm`,
    `test_ac07_ac08_expired_card_buttons`, `test_ac09_create_email_failure_shows_error`, `test_ac13_statuses_and_filter_counts`,
    `test_ac14_sorting`, `test_ac14_card_contents`, `test_ac14_offline_admin`, `test_ac17_390_rtl_touch[admin|invite-sheet|actions-sheet]`.
    Cross-check (scratch copy of the F03 suite, NOT in `tests/`, with two adapters only: a chooser → tap the trip, and
    `open_admin` → avatar → "ניהול מערכת" instead of the "עוד" row): **14 of the 17 pass** — the admin screen behaves as in F03
    in standalone mode. The 3 that still fail assert the "עוד" row itself (`test_ac02_admin_entry_for_admin`,
    `test_ac02_admin_rpc_refused_shows_no_list`, `test_ac14_offline_admin`) — removed by §1.5 / D6.
  - flag on, F04: `test_n01_no_old_name_rendered[admin]` (opens the admin screen from the "עוד" row, §1.5);
    `test_c19_boot_prefers_cached_trip_only_when_on[off]` (wizard off + switcher: see §6.6 — an interpretation for Or).
- Dev smoke (scratch `…/scratchpad/smoke/test_f20_smoke.py`, Playwright 390×844, F04 fake backend extended in the scratch
  file only: extra memberships at sign-in, `platform_admins` failure switch): **14/14** — super-admin chooser (title, admin row
  + "1 ממתינות", trips newest-first with flag / role / dates / members, no chrome, `__PT.started=false`, `tripData`
  undefined, no footnote, 390 px / RTL / 44 px); enter a trip without reload (correct trip id, cached key); avatar + sheet
  (current ✓ "כאן עכשיו", other trip dates, "ניהול" row; Escape / back gesture / backdrop close; current row not a button);
  "עוד" without `#ptAdminRow`, link-email row kept; sheet → standalone admin (reload, `#admin`, no trip chrome, header
  "הטיולים שלי" / "Lonely Planner · סופר-אדמין", no `#ptAdminBack`, filters work); header → chooser in place ("אחרון" badge);
  chooser → admin → browser back → chooser → forward → header → chooser; enter another trip after admin, in-trip `#admin` →
  header → reload to the chooser (`?choose=1` cleaned); `#admin` direct; D3 on (persists, no navigation) → next boot straight
  to the cached trip, `?choose=1` still shows the chooser, off removes the key; `?trip=` → normal boot; non-admin 1 trip (no
  avatar; `#admin` → trip, hash cleaned); non-admin 2 trips (avatar "ד", no "ניהול", offline tap → toast and stay, online tap →
  reload into the chosen trip, stays after another reload); offline boot (`navigator.onLine=false`) and backend-down boot with
  a cached trip → the trip, no chooser; admin check failure → normal boot, no error; super-admin with no trips → chooser
  "אין עדיין טיולים" (no not-connected card); details failure → "לא הצלחנו לטעון…" + "נסו שוב" → list; standalone admin
  invite sheet (create works without a trip, badge becomes "2 ממתינות"); rights revoked meanwhile → back on the chooser
  without the admin row (no blank page); avatar 44×44 at the left, no overlap and no horizontal scroll in v2 (HOME-MIN), v1 and
  v2 with HOME_MIN off; flag off (no `__ptF20` / `__ptF03Admin`, no avatar / chooser, "עוד" row + `#ptAdminBack` as before);
  `ADMIN_FEATURE='off'` (no chooser, switcher for ≥2 trips without "ניהול", no `platform_admins` query); wizard off + switch
  sticks. No page errors in any scenario.

## 6. Interpretations, known limitations, open points

1. **"<N> חברים" for N=1** is written "חבר אחד" (same helper as the F03 admin cards; the mockup shows "חבר 1").
2. **Current trip row in the sheet**: sub = "<תפקיד> · כאן עכשיו" without dates, as in the artboard (spec: "… · כאן עכשיו").
3. **Close button** × in the sheet header (not in the artboard), for screen-reader / keyboard users; backdrop, Escape and the
   browser back gesture also close it. The back gesture uses a URL-less history entry (the existing sheets have none).
4. **Offline "ניהול מערכת" in the sheet** → the same offline toast as for trips (an offline reload would only land back in the
   cached trip). Spec names the toast for trips only.
5. **`?trip=`**: no code in the app reads it yet; F20 only treats it as "opened for a specific destination" (no chooser).
6. **DECIDED (architect, 2026-10-13): kept.** **`WIZARD_FEATURE='off'` + `SWITCH_FEATURE='on'`**: the gate then boots the newest membership (F04-BOOT-01 is off), which
   would undo every switch made in the sheet. F20 therefore enters a still-active cached trip itself for non-admins in that
   combination (D4 wording: "cached trip, else newest"). Consequence: F04 `test_c19_boot_prefers_cached_trip_only_when_on[off]`
   fails (it expects the newest trip with the wizard off) — QA should update that case for the F20 flag-on state.
7. **`fetchTrips` failure for a super-admin** keeps the alpha.4.2 path (cached trip, else the not-connected card): the chooser
   needs the membership list. The chooser's failure state covers the details load (trips / flags / counts).
8. **Super-admin with no trips** sees the chooser instead of the not-connected card (spec), so the F04 gate card "כניסה עם
   הזמנה" is not shown to them; the invite link still opens the wizard.
9. **FIXED (F20-BOOT-03, architect decision 2026-10-13)**: the admin check has its own 2500 ms bound (`PT_ADMIN_CHECK_MS`), so
   a hanging `platform_admins` query delays boot by at most ~2.5 s and then counts as "not super-admin" (normal boot, no
   chooser). Smoke: hanging check → trip started 2.64 s after navigation, no chooser, no error. For an admin inside a trip the
   existing F03 check in "עוד" still runs as before (a second, unchanged query, F03's own 8 s timeout).
10. **Pending badge** counts invites with status `pending` ("ממתין למנהל") only — expired ones are not counted.
11. **Offline-started trip**: the trip list is not known, so the avatar appears only after the network returns (one lazy
    `fetchTrips` + admin check), or after the next online boot.
12. **Admin screen body** keeps F03's look (green invite button / filter); only the header follows `F20_Admin` (spec: "Changes
    to its header"). The artboard's indigo button and page tint are not applied.
13. **D3 checkbox**: a custom 44×44 control (transparent native checkbox over a styled 22 px box) so the touch target is ≥44 px.
14. History: from the chooser the admin screen pushes `#admin`; back/forward move between them without reload. Opened directly
    at `#admin`, "הטיולים שלי" replaces the entry (no hash) and shows the chooser in place. From a running trip it reloads to
    `?choose=1` (removed at once).
15. Not verified here (needs the real stack / Or's phone): real RLS answers for the `in(...)` member-count query per role,
    iOS installed-app back gesture on the sheet, Safari rendering of flag emoji.
