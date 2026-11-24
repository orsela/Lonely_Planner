# F12 · shared document vault — dev notes, conversation 2 (page) · 3.0.0-alpha.18

<!-- CHANGE 2026-11-24 F12-DOC-02: new file (no previous version). -->

Branch `f12-build`, on top of `e791893` (conversation 1, server). Spec: `claude/Plan_Travel_F12_spec.md` §5; server contract: `docs/F12_dev_notes_server.md`.

## What was added
- `app/js/f12.js` (new, `window.__ptF12`): row **"כספת משותפת"** in "עוד" (☁️, right under the local "כספת מסמכים" row, with a counter "N מסמכים · X MB"),
  full-screen vault (quota bar, category chips, list newest first, empty state), upload sheet, viewer (image in the app; PDF = blob + "פתיחת ה-PDF" button),
  ⋮ menu (rename/recategorise for the manager or the uploader, delete for the manager), offline = the vault needs a connection (message only).
- `app/index.html` (additive): flags `VAULT_FEATURE='off'`, `VAULT_TRIPS=[Romania]`; `<script src="js/f12.js">`; an attach block after F08's (client, uid, tripId, role); a mount block before the NOTES-RICH mount; versions `PT_VERSION` / `APP_VERSION` = 3.0.0-alpha.18.
- `app/sw.js`: `"js/f12.js"` in `SHELL_FILES`.
- Tests: `tests/f12/f12_test.mjs` (Node, 10), `tests/f12/test_f12_browser.py` (390px, fake client, 28 checks), `tests/f12/run.sh --only page`.

## Decisions (not in the spec text)
1. **Row name "כספת משותפת"**, not "כספת מסמכים": the app already has a local, offline-only row with that name (`documentsBtn`, IndexedDB documents). Same word would confuse; the local row is untouched.
2. The row is inserted by `f12.js` after `#documentsBtn`; it appears/disappears when "עוד" is opened (class observer), so a trip switch needs no extra hook.
3. PDF: after the blob is ready the viewer shows an "פתיחת ה-PDF" link (a fresh tap) instead of `window.open` after an await (popup blockers on mobile). To verify on Or's phone (conversation 3).
4. `functions.invoke('vault-delete', {body:{doc_id}})`; a rename that RLS blocks returns 0 rows, so `.select('id')` is checked (not only `error`).
5. The "שמור גם במכשיר שלי" checkbox and the per-document "שמור לאופליין" button are **not drawn yet** (conversation 3 owns `pt-docs-v1`).
6. The existing chat input `documents` (F14, local vault names) is unrelated to `trip_docs`; criterion 9 grep (`trip_docs|trip-docs`) is clean in `chat-assistant` and `f14.js` (test F12-N10).

## Not done / for conversation 3
Offline cache + `index.json`, local cleanup (delete / member removal / `device_revoked`), phone check (PDF, image, offline, Android), `VAULT_FEATURE='on'`, merge to `main`, STATUS update. Not tested against the real server from here (no network): upload/insert/delete flows run on a fake client; the server side is covered by `qa.f12_run()` 48/48.
