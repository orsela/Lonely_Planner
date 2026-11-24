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

## Conversation 3 (offline + clean-up) · 3.0.0-alpha.18 (same version, not on `main` yet)
<!-- CHANGE 2026-11-24 F12-DOC-03: new section (what changed from F12-DOC-02: conversation 3 code written; phone check and flag still open). -->
- **Merge:** `main` c5ca0d2 (F13, alpha.17.2) merged into `f12-build` (1c448f2). Conflicts only in `index.html` (script tags, `PT_VERSION`, `APP_VERSION`) and `sw.js` (`SHELL_FILES`): both sides kept, version stays alpha.18, F13 `i18n/en.json` + `js/f13.js` and `js/f12.js` all in `SHELL_FILES`.
- **Store:** Cache API `pt-docs-v1` (starts with `pt-`, so `sw.js` `ownCache()` can touch it, but the worker never deletes it). Key `/_vault/<trip>/<doc>`; `/_vault/index.json` = `{trips:{<trip>:{docs:[metadata], saved:{<id>:{size}}}}}`. Metadata kept on the device is only: id, title, category, mime, size, uploader, created_at, storage_path (test F12-N15). Writes to the index are serialized (F12-N14). `makeOffline(cs)` takes the cache storage as a parameter, so Node tests use a fake.
- **UI:** per-row button 📥 / ⏳ / ✅ (44px); "✅ שמור במכשיר" under the title; upload sheet box "שמור גם במכשיר שלי" (unticked; the picked file is stored directly, no second download); offline (no network or last load failed) = list from the device, not-saved rows dimmed with no button, tap → "המסמך לא שמור במכשיר"; saved document opens from the cache with or without network (PDF = blob + "פתיחת ה-PDF", image = blob URL). `navigator.storage.persist()` asked on the first save. "No space" (`QuotaExceededError`) gets its own message.
- **Clean-up:** (1) every online load → `sync()` deletes local copies whose document is not on the server (manager deleted it, or member no longer sees the trip); (2) `purge(t)` in `index.html` (member removed / left, called by `cleanTrip` and `bootCheck`) → `__ptF12.clearTrip(t)`; (3) `revoked()` in `f07.js` (`device_revoked` / dead session) → `__ptF12.clearAll()` deletes the whole cache. All three are additive one-liners guarded by `window.__ptF12`.
- **Not covered by the clean-up (decide with Or):** a normal sign-out ("יציאה", `signOutClean` in F22) leaves the saved copies on the device.
- **Tests:** `tests/f12/run.sh --only page` = Node 15/15 + browser (stub page with a fake Cache Storage, because `file://` pages cannot use the real one) all passed; F13 12/12; F07 page 9 + 4 + 2.
- **Still open:** Or's Android phone check (PDF, image, airplane mode, "no space"), then `VAULT_FEATURE='on'`, merge to `main`, STATUS + LEAN_RULES update. Real server and real Cache API on a device are untested.
- **Sign-out clean-up (Or approved, 24/11):** `signOutClean` in `index.html` now awaits `__ptF12.clearAll()` before the reload (F12-SIGNOUT-01). Replaces the "not covered" note above.
