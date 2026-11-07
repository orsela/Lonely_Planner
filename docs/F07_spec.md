# F07 — A member who changed phones gets back into the trip · spec

<!-- CHANGE 2026-11-07 F07-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.11** (app + `/join/`), migration **0018_f07.sql** (+ QA harness **0019**), changes to
**`join-trip`**, **`approve-member`** and **`manage-members`** (all alpha.11.0). Mockup approved by Or 2026-11-07: canvas
https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 13 (`F07_Join`, `F07_Pending`, `F07_HomeManager`, `F07_Members`,
`F07_MyDevices`, `F07_EmailNotice`, `F07_Expired`). Decisions: claude/Plan_Travel_F07_decisions.md.

User value: a member whose phone was replaced or wiped gets back into the trip with the same name, role and records, in
under a minute, without a duplicate "ghost" member; a member who linked an email does it alone.

Base: `main` at 3.0.0-alpha.10 (F10b) — if F10b is not merged yet, branch from `main` and rebase before merging. Branch
`f07`. Push rule (INDEX): client code stays on `f07` until the migration and functions are deployed. The live project
`vietnam-trip-2026` is never touched.

## 0. Decisions

| # | Decision |
|---|---|
| D1 (Or) | The member starts it, from the **regular join link**: a switch "אני חדש/ה בטיול" / "כבר הייתי בטיול". No personal link from the manager (replaces the Backlog wording). |
| D2 (Or) | The member **picks their name** from the list of active members (names only, no roles). Manager approval is the guard; the request card says "מכשיר חדש" and shows the name and role. |
| D3 (Or) | **Several devices per member.** One person (name + role) with N devices; role change, rename, removal and leave apply to all of them. |
| D4 (Or) | A device can be disconnected by the **member** ("אני · <שם>") and by a **manager** ("חברים וקישור"). Disconnecting a device does not remove the member. |
| D5 (Or) | A "כבר הייתי" request **expires after 24 h** without a decision; the member can ask again. |
| D6 (Or) | **Email backup inside F07.** Any member can link an email (6-digit code, F04 infrastructure). With it, a new device gets in through "כניסה עם המייל" with **no approval** — managers only get a notice card. |
| D7 (Claude, approved with the mockup) | The email is visible only to its owner. The member's own screen is "אני · <שם>", a row in "עוד" for every member. |

Out of scope: moving data that lived only on the old phone (vault documents until F12, an unsent offline queue) — the
member is told so; account deletion; per-device roles.

## 1. Architect rulings

| # | Ruling |
|---|---|
| C1 | **Person = rows sharing `person_id`.** `trip_members` keeps one row per auth user (one anonymous identity = one device). New column `person_id uuid not null`, set to the row's own `id` on insert (trigger) and backfilled `= id`. All RLS policies and the F01 helpers (`trip_role`, `my_trip_ids`) stay **unchanged**: every device row is a normal active member row. Role, `display_name` and `status` are kept equal across a person by the DB functions that change them (they update `where person_id = …`). |
| C2 | **Name uniqueness and counts are per person**: F05/F06 name checks compare against other *persons*; "N חברים", the last-manager rule (F06 D6) and `f06_other_managers` count distinct `person_id`. |
| C3 | **Email devices share one auth user** (signInWithOtp returns the same uid), so they are one `trip_members` row. To list and cut them one by one, `private.member_sessions` records each auth session (`session_id` from the JWT, label, via `anon`/`email`, first/last seen, `revoked_at`), written by `member_touch`. |
| C4 | **Disconnect:** an anonymous device → that row `status='removed'` (RLS cuts it at once). An email session → its `auth.sessions` row is deleted (refresh token dead) and `revoked_at` set; the app on that device sees `device_revoked` on its next membership check (F06 D11: start, visible, online, every 60 s) and signs out. Known limit: an already-issued access token stays valid up to 1 h on a modified client. A person's last device cannot be disconnected (use "יציאה מהטיול" / removal). |
| C5 | **Relink request** = a `pending` row with `person_id` of the chosen person, the person's `display_name` and `role` copied, `relink_expires_at = now() + 24 h`. One open relink per person (a new one replaces the older). Expiry is lazy: an expired row is treated as absent and deleted on the next `join_preview`/`approve_member`/`member_touch` that sees it (no pg_cron, as F21 C5). |
| C6 | **Approve a relink:** role parameter ignored; the row takes the person's **current** role and name (they may have changed since the request). Reject = delete. A removed person cannot be chosen (only `active` persons are listed). |
| C7 | **Rate limit:** relink requests share F05's `join_attempts` limits (same identity, same IP). The name list is returned only with a valid, current join code. |
| C8 | **Email login notice (D6):** a new `member_sessions` row with `via='email'` for a person that already had a session → a home card for managers ("<שם> נכנס/ה עם המייל"), until **any** manager presses "הבנתי" (`acked_at`) or 7 days pass. "זו לא היא · ניתוק" = C4 on that session. |
| C9 | **Email link for members** reuses the F04 code screen (`updateUser({email})` + `verifyOtp` type `email_change`, resume entry of F04-HOME C4). Email that belongs to another account → F04 D6 explanation, no change. |
| C10 | **Gate:** the "לא מחובר" card "מנהל/ת טיול → כניסה עם המייל" becomes "כבר בטיול? כניסה עם המייל" (managers and members). After verify, F04-HOME C3 path: no invite + has trips → enter the trip. |
| C11 | **iPhone:** an approved relink in Safari shows the F05 transfer code as today; `claim_transfer` moves that device row to the installed app (its `person_id` is kept). |
| C12 | Flag **`RELINK_FEATURE='off'`**: no switch on `/join/`, no device lists, no "אני" row, no email card; server functions stay deployed and unused. |

## 2. Server

### 2.1 Migration 0018_f07.sql
- `trip_members.person_id` + backfill + `before insert` trigger + index `(trip_id, person_id)`; `relink_expires_at timestamptz null`.
- `private.member_sessions (id, member_id → trip_members on delete cascade, session_id uuid, label text ≤60, via text check in ('anon','email'), created_at, last_seen_at, revoked_at, acked_at, acked_by)`, unique `(member_id, session_id)`.
- `public.join_preview` (replace): adds `people: [{person_id, display_name}]` of active persons, and `relink: {status: pending|expired, display_name}` for the caller's own relink row.
- `public.join_request` (replace): optional `p_person uuid` → C5; refuses if the caller is already active in the trip, the person is not active, or limits are hit.
- `public.approve_member` (replace): C6.
- `public.member_set_role / member_rename / member_remove / member_leave` (replace): apply to the whole person (C1, C2).
- `public.member_touch` (replace): also upserts the session (C3), returns `device_revoked` when its session is revoked.
- New `public.device_list(p_trip)`, `public.device_disconnect(p_trip, p_member, p_session)`, `public.device_notice_ack(p_trip, p_session)` — service_role only, called by `manage-members`; the member may act on own person, a manager on anyone (D4).
- Unused F01 table `relink_tokens` stays (no drop; noted for S6 cleanup).

### 2.2 Edge Functions
- `join-trip`: passes `person` through; returns `people` from preview.
- `approve-member`: unchanged shape; relink rows approved per C6.
- `manage-members`: new actions `devices`, `disconnect_device`, `ack_device_notice`; `disconnect_device` deletes the `auth.sessions` row with the service role (C4).

## 3. App and `/join/`
- `/join/`: switch (D1), name list as radio buttons (D2), "בקשה לחבר את הטלפון הזה", pending screen with expiry time and a WhatsApp button to the manager (`wa.me` with a short text), expired screen (D5), email shortcut → app gate (C10).
- Home (managers): relink card in "ממתינים לאישור" with "מכשיר חדש" tag, no role picker, warning line; email notice card (C8).
- "חברים וקישור": devices per person (label, last seen, "ניתוק"; last device without the button).
- "עוד" → "אני · <שם>": email backup card (C9), "המכשירים שלי" with "ניתוק" (not on the current device).
- After a relink approval, a one-time toast: "מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים".
- Offline: request and disconnect buttons disabled with the F10b offline line.

## 4. Acceptance criteria
1. A member on a new identity opens the join link, picks "כבר הייתי", picks their name → one `pending` row with the person's `person_id`, name and role; no name-taken error.
2. The manager's home shows the request with "מכשיר חדש" and the role; approving makes the device active with the person's current role and name; the member list still shows **one** person with **2 devices**.
3. A rejected relink deletes the row; an unanswered one is treated as gone after 24 h and the member sees "הבקשה פגה" and can ask again.
4. Only active persons are listed; a removed person or an invalid/rotated code returns no names.
5. Role change, rename, removal and leave on a person reach **every** device row (DB check + the device's screen within 60 s).
6. Last-manager rule counts persons: a manager with two devices is still "the only manager".
7. Disconnecting an anonymous device: that row becomes `removed`, its reads return 0 rows at once; the person stays active on the other device.
8. Disconnecting an email session: the `auth.sessions` row is gone and the device signs out on its next check (≤ 60 s while open).
9. The last device of a person has no "ניתוק"; the API refuses it.
10. A member links an email with a 6-digit code; on a fresh identity "כניסה עם המייל" opens the trip with no approval, and managers see the notice card until one presses "הבנתי".
11. An email that belongs to another account → explanation, nothing changes.
12. RLS: a user from another trip cannot list devices, request a relink with a guessed `person_id`, or disconnect anything.
13. Rate limit: the F05 limits apply to relink requests.
14. `RELINK_FEATURE='off'` → the app and `/join/` behave exactly as alpha.10 (regression suites F01–F06, F10/F10b, F20, F21 green).
15. 390 px, RTL, touch ≥ 44 px, no horizontal scroll on all seven screens.

## 5. Deploy order (push rule)
Migration 0018 (Or, SQL Editor) → `qa.f07_run()` → functions `join-trip`, `approve-member`, `manage-members` → merge `f07`
→ phone check on Or's Android: relink from Chrome with a second identity ("בודק" on the computer) + email login notice.
