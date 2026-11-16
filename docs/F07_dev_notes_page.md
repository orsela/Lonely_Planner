# F07 dev notes — page side (conversation 2 of 3)

<!-- CHANGE 2026-11-16 F07-DOCS-05: new file (no previous version). Continues docs/F07_dev_notes_server.md. Branch `f07-build`, version 3.0.0-alpha.16. -->

## What was built
- `app/js/f07.js` (`window.__ptF07`): `/join/` screens (switch, name list, pending with "בתוקף עד" + WhatsApp, expired, approved note), the manager card pieces (tag, body without a role picker), the one-time toast. Flag `RELINK_FEATURE='off'` in `app/index.html` and `join/index.html` — **both stay `'off'`** until conversation 3 is done.
- Connection points: `join/flow.js` (6 hooks, only when `opts.relink`), `join/index.html` (flag, loads `../app/js/f07.js`), `app/index.html` (flag, script tag, in-app join mount option, F05 block: select column, expired filter, tag, `else if(F7)` body, relink toast; mount block for the toast), `app/sw.js` (`SHELL_FILES`).
- Tests: `tests/f07/f07_test.mjs` (6, Node), `tests/f07/test_f07_browser.py` (3, one browser pass at 390 px: relink flow AC1/AC2 + layout, expired screen AC3, flag off), runner `tests/f07/run_page.sh`.

## Decisions
1. Flag off = the old query: `loadMembers` adds `relink_expires_at` to its select only with `RELINK_FEATURE='on'` (the older fake backends reject unknown columns; and 'off' must equal alpha.15.3).
2. Expired relink rows are hidden client-side in the manager list (the server deletes them lazily, C5); a person with two active rows is one name in the user list (`Set`).
3. The member's "documents don't move" line: a note on the approved screen + a one-time toast in the app (`pt:_device:relink_notice`, set when "פתיחת הטיול" is pressed).
4. The WhatsApp button uses `wa.me/?text=…` (no number: the member picks the manager's chat), as the app stores no phone numbers.
5. In-app gate (`inApp:true`) gets the switch too, but no "כניסה עם החשבון" link (the gate already has it, F22a).

## Not done here (conversation 3)
Devices per member in "חברים וקישור", "אני · <שם>" + "המכשירים שלי", login-notice card (C8), offline states on disconnect, iPhone C11 check, member list grouped by person (it still lists device rows), `RELINK_FEATURE='on'`, merge to `main`, phone check, STATUS update.

## Known
- `tests/f07/test_f07_browser.py` extends the F02 fake's column whitelist (`person_id`, `relink_expires_at`) and emulates `people` / `relink` / `person` / the approve `relink` flag in the F05 fake; server rules themselves are `tests/f07/run.sh`.
- Not run here: the full regression (LEAN rule 5/6); F05 spot check (b03, b04, a03) green.
