# F06 — A manager changes roles, removes members and resets the link · spec

<!-- CHANGE 2026-10-22 F06-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.7** (app + `/join/` page), migration **0014_f06.sql** (+ QA harness **0015**), one new Edge
Function **`manage-members`** (alpha.7.0) and a small change to **`join-trip`** (alpha.7.0, removed members may ask
again). Mockup approved by Or 2026-10-22: canvas https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 8 (artboards
`F06_More`, `F06_Members`, `F06_MemberSheet`, `F06_RemoveConfirm`, `F06_Rotate`, `F06_LastManager`, `F06_Leave`,
`F06_Changed`).

User value: the manager controls who is in the trip and what each person may do — from one screen, with immediate effect on
everyone's phone. A member can leave on their own. A trip always keeps a manager.

Base: `main` at 3.0.0-alpha.6 (F05, 6803d0f). Branch `f06`. Push rule (INDEX): client code that needs the new server stays
on `f06` until the migration and functions are deployed. The live project `vietnam-trip-2026` is never touched.

## 0. Decisions

| # | Decision |
|---|---|
| D1 (Or) | One manager screen **"חברים וקישור"**, a row in "עוד" (managers only). It replaces the F04 row "קישור הצטרפות לקבוצה" (F04-MORE-01) and "ניהול ← משתמשים" (the old "מי אני" modal) in cloud mode. |
| D2 (Or) | Removal = `status='removed'` (row kept, name freed). A removed identity that opens the link again **may ask again**: its row goes back to `pending` and the manager decides. Replaces F05 D7's "הוסרת – פנו למנהל". |
| D3 (Or) | Rotating the link kills the old code at once; **pending requests stay**; transfer codes (F05 D1) are not affected. |
| D4 (Or) | Trip name in one place: a manager's rename in "הגדרות מסע" also updates `trips.name` (F09 lists, admin summary, preview). |
| D5 (Or) | Any member can **leave** the trip ("יציאה מהטיול"). |
| D6 (Or) | The **only** active manager cannot leave or step down: explanation + "למנות מנהל אחר"; with no other members – "פונים למנהל המערכת". (There is no account deletion in the app; this is the real `last_manager` case from F01.) |
| D7 (Or) | A manager can fix any member's `display_name` (including their own); same rules as F05 D5 (1–40, unique among pending+active, case/space-insensitive). |
| D8 (Or) | Demoted to viewer, or removed, with unsent offline changes → those changes are **dropped** with a message "N שינויים … לא נשמרו". |
| D9 (Or) | On the members screen pending requests are a **shortcut row** "N ממתינים לאישור · לאישור בבית"; approving stays in the F05 home card. |
| D10 (Or) | **Viewer guard in one place:** every trip-data write by a viewer is stopped before the local copy and the queue, with a toast "צפייה בלבד – השינוי לא נשמר", and the screen reloads from the cloud. Edit buttons stay visible (a full read-only UI is a later feature). A "צופה" tag shows in the home header. |
| D11 (Claude default) | Role and removal changes reach a member's phone via Realtime on their own `trip_members` row **plus** a membership check on start, on `visibilitychange`→visible, on `online`, and every 60 s while open (a removed member no longer receives Realtime events for the row, so the check is what catches removal). |
| D12 (Claude default) | Leaving and removal both use `status='removed'`; the member's records (`by` names, expenses, journal) stay in the trip. |
| D13 (Claude default) | One Edge Function `manage-members` with five actions (`set_role`, `rename`, `remove`, `leave`, `rotate_link`) instead of the two names in the architecture doc (`update-member`, `rotate-join-link`): one deploy, one auth path. |

Out of scope: "חיבור מחדש למכשיר חדש" (F07, removed from the member sheet), a full read-only UI for viewers, member avatars
/ colours beyond F05.

## 1. Screens (Hebrew, RTL, 390px, touch ≥44px, existing `pt-*` / `pt5-*` styles)

Flag: `MEMBERS_FEATURE='on'|'off'` in the app (next to `JOIN_FEATURE`) and in `/join/`. `'off'` = alpha.6 exactly
(F04 "קישור הצטרפות" row, "ניהול ← משתמשים", F05 `member_removed` message, no viewer guard, no membership watch).

### 1.1 "עוד" (artboard `F06_More`)
- Section "הטיול": row **"חברים וקישור"** (managers only), sub "<N> חברים · תפקידים · קישור הצטרפות", amber badge
  "<P> ממתינים" when P>0. Replaces the F04-MORE-01 row. "הגדרות מסע" sub mentions the name updates for the whole group.
- New section **"אני בטיול"** (everyone, cloud mode): row "יציאה מהטיול" (red). For the only manager the sub reads "את/ה
  המנהל/ת היחיד/ה – קודם ממנים מנהל" and the row opens 1.6 instead of 1.7.
- "ניהול ← משתמשים" is hidden in cloud mode with the flag on (local mode unchanged).

### 1.2 "חברים וקישור" (artboard `F06_Members`) — trip screen with tab bar
- Back arrow to "עוד". Subtitle "<trip> · מנהלים בלבד". A non-manager who reaches it (stale UI) sees nothing but a toast
  and is sent back.
- **Link card:** title, help "מי שפותח – ממתין לאישורך", the URL (LTR, monospace, read from `trip_join_codes` as F04),
  buttons "שליחה בווטסאפ" (same text as F04), "העתקה", "איפוס" (red text) → 1.5.
- **Pending shortcut (D9):** shown when P>0: "<P> ממתינים לאישור" + button "לאישור בבית" (goes to home; the F05 card is there).
- **Members card:** "חברים · <N>" and "<M> מנהלים" / "מנהל/ת אחד/ת". Active members ordered: me first, then managers, then
  by `joined_at`. Row: avatar letter (F05 colours), name (+ "(את/ה)" for me), sub = last seen relative ("פעיל/ה היום",
  "פעיל/ה אתמול", "לפני X ימים", "עוד לא נכנס/ה" when `last_seen_at` is null), role badge (green for manager), "⋯" button
  (`aria-label="פעולות על <name>"`) → 1.3 (for me: 1.6 when I am the only manager, else 1.3 with my own row).
- Footnote "שינוי תפקיד או הסרה נכנסים לתוקף מיד, גם בטלפון של החבר."
- Live: the F05 Realtime channel on `trip_members` (trip filter) refreshes the list. Offline: last cached list, all action
  buttons disabled, "אין חיבור – אפשר לשנות כשהרשת תחזור."

### 1.3 Member sheet (artboard `F06_MemberSheet`) — bottom sheet
- Header: avatar, name, "הצטרף/ה ב-dd/mm/yyyy · <last seen>", close ×.
- **Role:** segmented צופה / עורך / מנהל (`aria-pressed`), help line with the three meanings. Tapping a different role saves
  at once (`set_role`) → toast "<name> עכשיו <role>". On `last_manager` (demoting the last manager — only possible on my own
  row) the control is disabled anyway (1.6).
- **Name:** input (maxlength 40) + "שמירה" (`rename`); `name_taken` / `name_invalid` inline as in F05 1.6b.
- **"הסרה מהטיול"** row (red) → 1.4. Not shown on my own row (I use "יציאה מהטיול").

### 1.4 Remove confirm (artboard `F06_RemoveConfirm`) — alert dialog
"להסיר את <name> מהטיול?" + three points (access blocked at once also on their phone; what they added stays; if they open
the link again you get a new request) + "הסרה" (red) / "ביטול". → `remove` → toast "<name> הוסר/ה מהטיול", sheet closes.

### 1.5 Rotate confirm (artboard `F06_Rotate`) — alert dialog
"לאפס את קישור ההצטרפות?" + points (old link stops now and shows "הקישור כבר לא פעיל"; the N members are not affected; the P
pending requests stay; send the new link afterwards) + "איפוס הקישור" (red) / "ביטול". → `rotate_link` → the link card
shows the new URL and a toast "נוצר קישור חדש" with action "שליחה בווטסאפ".

### 1.6 Only manager (artboard `F06_LastManager`) — my own sheet
Role segment disabled except "מנהל/ת"; my name editable; amber box "את/ה המנהל/ת היחיד/ה בטיול" + text + button "למנות
מנהל אחר" (closes the sheet; the members list stays open) + "אין בטיול חברים אחרים? פונים למנהל המערכת." When another
active manager exists, my sheet is the normal 1.3 (I may step down).

### 1.7 Leave (artboard `F06_Leave`) — from "עוד", any member except the only manager
`לצאת מ"<trip>"?` + points (the trip is removed from this phone; what you added stays with the group; to come back open the
join link again and the manager approves) + "יציאה" / "ביטול". → `leave` → local clean-up (§3.4) → the next active trip
(F20 rules) or the not-connected card.

### 1.8 On the member's phone (artboard `F06_Changed`)
a. **Role changed** (any direction): on home, a status card "ההרשאה שלך השתנתה ל<role>" + "<manager> שינה/תה את התפקיד שלך."
   + for viewer "אפשר לראות הכול, אבל לא לשנות." + D8 line when changes were dropped + "הבנתי" (dismiss, per trip+role,
   device-local). Header shows the "צופה" tag while viewer (D10).
b. **Removed** (detected live or at boot): full screen, no trip chrome: `כבר אינך חבר/ה ב"<trip>"`, "מנהל הטיול הסיר אותך.
   הנתונים של הטיול נמחקו מהטלפון הזה.", D8 line, buttons "בקשה להצטרף שוב" (opens `/join/` in the join flow with the
   **cached** join code if this device has one, otherwise the line "בקשו מהמנהל את קישור ההצטרפות") and "הטיולים שלי" (only
   with another active trip). The trip name is kept in device storage only for this screen.

## 2. Data — migration 0014_f06.sql (Or runs it in the SQL Editor; Claude verifies by reading)

All new functions in `public`, `security definer`, `set search_path=''`, **executable by `service_role` only**, refusals
returned as `{"error":<code>}` (F05 pattern), helpers in `private` (`private.f06_*`). No new tables, no new policies or
grants on existing tables.

1. `member_set_role(p_user, p_member, p_role)` — caller must be an active manager of the member's trip; target must be
   `active`; `p_role` in (manager, editor, viewer) else `role_invalid`; same role → ok, no write. Demoting the last active
   manager → `last_manager` (checked before the update; the F01 trigger stays as the backstop).
2. `member_rename(p_user, p_member, p_name)` — caller active manager; target active; name via `private.f05_clean_name`,
   1–40 else `name_invalid`; unique among pending+active of the trip except itself (`f05_name_key`) else `name_taken`.
3. `member_remove(p_user, p_member)` — caller active manager; target active and not the caller (`invalid_request` for self:
   use leave); removing the last manager → `last_manager` (only reachable with two managers removing each other at once);
   sets `status='removed'`; deletes the member's open `private.transfer_codes`.
4. `member_leave(p_user, p_trip)` — caller's own active row; last active manager → `last_manager`; sets `removed`; deletes open
   transfer codes.
5. `rotate_join_code(p_user, p_trip)` — caller active manager; new random 8-char code from the F01 alphabet
   (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, unique, retry on collision), `version = version + 1`, `rotated_at = now()`; returns
   `{code, version}`. Pending rows untouched (D3).
6. **`join_preview` / `join_request` change (D2):** a `removed` row of the caller no longer returns `member_removed`.
   Preview answers as for a new identity (form shown). Request **re-uses that row**: `status='pending'`, new
   `display_name`, `role = trips.default_role`, `joined_at=now()`, `approved_at=null`; the F05 limits (3 per 24 h, 20
   pending, name rules) apply as for a new request. `member_removed` stays in the code list but is no longer produced.
7. **Trip name (D4):** trigger `after insert or update of value on public.trip_kv`, `for each row when (new.key =
   'tripname')`: if the writer (`auth.uid()`) is an active manager of the trip, set `trips.name` to the cleaned value
   (trimmed, collapsed spaces, 1–80; outside that range → no change). Editors' writes keep today's kv-only behaviour.
   Security definer, never raises (a failure must not block the kv write).
8. `last_seen_at`: `member_touch(p_user, p_trip)` sets the caller's `last_seen_at=now()` at most once per 10 minutes; called
   by `manage-members` action `touch` (see §3) on app start / visible. (Today nothing writes it.)

Error codes: `not_manager`, `not_member`, `not_active`, `role_invalid`, `name_invalid`, `name_taken`, `last_manager`,
`invalid_request`.

## 3. Server and client logic

### 3.1 Edge Function `manage-members` (Claude deploys; `verify_jwt=false`, JWT checked in code like `approve-member`)
POST `{action, …}`: `set_role {member_id, role}` · `rename {member_id, display_name}` · `remove {member_id}` ·
`leave {trip_id}` · `rotate_link {trip_id}` · `touch {trip_id}` → the SQL functions above. Statuses: 200 ok · 400
invalid_request / role_invalid / name_invalid · 401 unauthorized · 403 not_manager / not_member · 409 not_active /
name_taken / last_manager · 405 · 500. Version header and body field `version` = `3.0.0-alpha.7.0` (closes F05 QA §3 for
this function). Testable like `approve-member` (`setDeps`, `handler`). One JSON log line per request, no ids or names.

### 3.2 `join-trip` (alpha.7.0)
No code change beyond the version; the D2 behaviour comes from the SQL. `/join/` with the flag on: the "removed" message
branch is not reached any more (kept for flag off).

### 3.3 Viewer guard (D10)
In `SS.set` / `SS.del` (and any other direct `window.storage.set/delete` path on trip data): when cloud mode, flag on and
the current role is `viewer`, do **not** write `localStorage`, do not call storage, do not enqueue; show the toast once per
5 s; then reload from the cloud (`loadState(); fillSelects(); updateDates(); render()`, debounced). Device-only keys that are
not trip data (e.g. `planner:lastsync`, UI prefs) are not guarded — the developer lists the guarded key set in the dev notes.

### 3.4 Membership watch and clean-up (D8, D11)
- Watch: Realtime on `trip_members` `id=eq.<my member id>` + `fetchMyMembership()` (one select of my row's role/status) on
  the triggers in D11. Results: same role → nothing; new role → update `state.role` and the cached active trip, show 1.8a;
  if the new role is viewer → drop the queue (below); no row / not active → 1.8b.
- Drop the queue: count the queued ops of this trip, clear them, remember N for the message.
- Removed/left clean-up: delete every device key with prefix `pt:<trip>:` (data, queue, members cache) except the small
  record for 1.8b (`pt:_device:removed` = {trip_id, name, n_dropped, join_code?}), clear the active-trip cache if it points
  to this trip, unsubscribe channels.
- RLS-rejected writes (`42501` / the F02 "delete rejected" error) during `flushQueue` trigger `fetchMyMembership()` at once.

### 3.5 Trip name
`saveTripName` unchanged (kv write); the trigger does the rest. The home header and "הגדרות מסע" keep reading `tripname`.

## 4. Acceptance criteria
1. Flag off → alpha.6 behaviour (F02/F03/F04/F05/F20 suites pass except version pins); "עוד" shows the F04 link row.
2. "עוד": managers see "חברים וקישור" with the pending badge when P>0; editors/viewers do not; everyone sees "יציאה מהטיול".
3. Members screen lists exactly the active members (pending/removed not listed), me first, managers next; counts correct;
   link card shows the current code; pending shortcut appears only with P>0 and navigates home.
4. `set_role` to each role stores it; a non-manager / a manager of another trip → `not_manager`; a pending or removed target →
   `not_active`; demoting the last manager → `last_manager` (no row change).
5. With two managers, one may demote themself; afterwards the "חברים וקישור" row disappears from their "עוד" without reload.
6. `rename`: valid name saved and shown everywhere (members list, home "שלום <name>", new `by` values); taken/invalid →
   inline error, no change.
7. `remove`: target becomes `removed`; their open transfer codes deleted; self → `invalid_request`; last manager →
   `last_manager`.
8. On the removed member's phone (open): within 60 s (immediately on returning to the app) 1.8b shows; `pt:<trip>:*` keys
   are gone; the trip no longer opens; at the next boot the same screen shows (from `pt:_device:removed`) and then the
   not-connected card / next trip.
9. Removed member opens the join link → the normal form; a request makes the same row `pending` with the new name and the
   default role; the manager sees it in the home card; approve → active again. The F05 limits apply.
10. `leave`: own row → removed, local clean-up, next trip or not-connected card; the only manager → `last_manager` and the
    UI shows 1.6 instead of the confirm.
11. `rotate_link`: new code (alphabet, 8 chars, unique), version+1; the old link → "הקישור כבר לא פעיל"; pending rows
    unchanged; active members unaffected; F05 transfer codes still claimable.
12. Viewer guard: as viewer, adding a waypoint / expense / journal entry / check-in shows the toast, nothing is written to
    `trip_kv`, `localStorage` trip keys are unchanged, the queue stays empty, the screen shows the cloud state. Editors and
    managers write as before.
13. Demotion with queued offline changes: going online after demotion drops them; 1.8a shows "N שינויים … לא נשמרו" with the
    right N; the queue is empty; nothing reaches `trip_kv`.
14. Role change on an open phone shows 1.8a within ≤3 s (Realtime) or ≤60 s (poll); "הבנתי" hides it for that role.
15. Trip name: a manager's rename in "הגדרות מסע" updates `trips.name` (admin summary, F20 trips list, join preview); an
    editor's kv write leaves `trips.name` unchanged; a 0-char or >80-char value never breaks the kv write.
16. `last_seen_at` updates on app start at most once per 10 min; the members list shows it.
17. RLS / grants: the new functions are not executable by `anon`/`authenticated`; no new policies; a member of trip B cannot
    act on trip A through the function (QA `qa.f06_run()`); advisors: no new warning.
18. 390px: no horizontal scroll, RTL, touch ≥44px on all 8 artboards' screens; the URL is LTR.
19. Offline: the members screen shows the cached list with actions disabled; leaving/removing is impossible offline (toast).
20. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`, `SEED_DATA`,
    `stayBlock`, `bookingUrl`); `APP_VERSION`/`PT_VERSION` = 3.0.0-alpha.7; every change marked `CHANGE 2026-10-2x F06-…`
    with what changed from alpha.6; `node --check` on all script blocks; no duplicate ids.

## 5. Deployment (one step at a time, Or confirms each)
1. Or runs `0014_f06.sql` then `0015_qa_f06_harness.sql` in the SQL Editor; Claude verifies (`qa.f01–f06_run()`).
2. Claude deploys `manage-members` and `join-trip` alpha.7.0.
3. Claude merges `f06` → `main` (app + `/join/`).
4. Phone check (Or), trip "טסט3": demote "בדיקה"… (already viewer) → make editor → back to viewer and see 1.8a on the incognito
   tab; remove "בדיקה" (also cleans the F05 test member) → 1.8b; ask again from the link → approve; rotate the link → old link
   shows "לא פעיל"; rename the trip in "הגדרות מסע" → the F20 trips list shows the new name; try "יציאה מהטיול" as the only
   manager → 1.6.
