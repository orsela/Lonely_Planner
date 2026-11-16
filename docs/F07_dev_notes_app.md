# F07 dev notes — app side (conversation 3 of 3)

<!-- CHANGE 2026-11-16 F07-DOCS-06: new file (no previous version). Continues docs/F07_dev_notes_server.md and docs/F07_dev_notes_page.md. Branch `f07-build`, version 3.0.0-alpha.16 (unchanged: f07-build was never released before this merge). -->

## What was built
- `app/js/f07.js` (app part, after the `/join/` part): state `S` (persons with devices, login notices, current session), `refresh()` (`manage-members` action `devices`, one call at a time, a burst of members events = one call plus a trailing one), `devsHtml(m)` / `people(list, uid)` / `foot()` for "חברים וקישור", `meCard()` for the "המכשירים שלי" card, `paintNotices()` for the managers' home card (C8), `onTouchError(e)` for `device_revoked` / dead session, `attach(api, hooks)` + `start()`. Cached in `pt7_devices` (namespaced) for offline.
- Connection points in `app/index.html` (all `CHANGE … F07-…`): F06 `loadMembers` (+ `person_id` in the select with the flag, + `F7.refresh()`), `managers()` / `onlyManager()` / `personCount()` by person (C2, AC6; without `person_id` they fall back to the row id = the old behaviour), `paintMembers` (persons, devices, foot line), touch (error → `onTouchError`, + a `touch()` every 60 s with the flag), `onStarted` (`F7.start()`), `attach` (`F7.attach`), F22a `paintMe` (`F7.meCard()`). No new script tag, no new sw.js line (f07.js was added in conversation 2).
- Flag `RELINK_FEATURE='on'` in `app/index.html` and `join/index.html`. No server change (the three functions stay at 3.0.0-alpha.16.0, v5/v4/v4).

## Decisions
1. Disconnect is two taps ("ניתוק" → "לנתק? לחצו שוב", 4 s) — no extra dialog layer; the same on the home notice card.
2. The notice button reads "זה לא הוא/היא · ניתוק" (the approved mockup says "זו לא היא · ניתוק"; made gender-neutral).
3. A plain 401 from `manage-members` is checked with `auth.getUser()` before signing out (a refresh hiccup must not sign the member out); `device_revoked` signs out at once. Sign-out = `signOut({scope:'local'})` + a full-screen "המכשיר הזה נותק מהטיול" with "המשך" (reload → the F22a gate).
4. A device is "this one" by `session_id === current_session`; an anonymous device with no recorded session yet is matched by its own member row.
5. Notices sit under the F05 requests card on home; "הבנתי" acknowledges for every manager (server C8).

## Known / for Or
- **"אני · <שם>" belongs to F22a and `ACCOUNT_FEATURE` is `'beta'`**: "המכשירים שלי" is only visible on a beta device (`#f22beta`) until F22a is switched `'on'`. Members can still disconnect nothing themselves otherwise; managers do it in "חברים וקישור".
- Test harness: the F05 and F06 fakes now know `person_id` / `relink_expires_at` (the app selects them with the flag).
- Not run: the full regression (LEAN rule 5/6) and the phone check (Or: Chrome on the computer = a second identity).
