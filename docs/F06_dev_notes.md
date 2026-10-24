# F06 · dev notes — a manager changes roles, removes members and resets the link (v3.0.0-alpha.7)

<!-- CHANGE 2026-10-22 F06-DOCS-02: new file (no previous version). -->

Contract: `docs/F06_spec.md` (mockup approved 2026-10-22, canvas row 8, artboards `F06_More` … `F06_Changed`) plus the
architect's spec clarifications C1–C11 of 2026-10-22 (§7; the spec text itself is amended by the architect). Base: `main` at
3.0.0-alpha.6 (6803d0f). Branch `f06`. **Nothing was pushed, deployed or run against Supabase.** All checks below are local.

## 1. What changed (file / area → why)

| File / area | CHANGE ID | What changed from 3.0.0-alpha.6 | Spec |
|---|---|---|---|
| `supabase/migrations/0014_f06.sql` | F06-DB-01 | new: 6 service-role-only functions in `public` — `member_set_role`, `member_rename`, `member_remove`, `member_leave`, `rotate_join_code` (returns `{code, link_version}`), `member_touch`; helpers `private.f06_is_manager`, `f06_other_managers`, `f06_new_join_code`; trigger `trip_kv_tripname_sync` (`private.f06_tripname_sync`, never raises). Refusals returned `{"error":code}`. remove/leave also delete open `private.transfer_codes` and open `public.relink_tokens`. No new tables/policies/grants on existing tables. Idempotent. | §2.1–2.5, 2.7, 2.8 |
| same | F06-DB-02 / -03 | `create or replace` of `join_preview` (a removed row → `me:null`) and `join_request` (a removed row is re-used: pending, new name, `trips.default_role`, `joined_at=now()`, `approved_at=null`, `last_seen_at` kept; F05 limits unchanged). Rest byte-identical to 0012. | §2.6, D2 |
| `supabase/functions/manage-members/*` | F06-FN-01/03/04/05/06 | new Edge Function (3.0.0-alpha.7.0): actions `set_role`, `rename`, `remove`, `leave`, `rotate_link`, `touch`; body field `version` + header `X-Function-Version` (exposed via CORS) on every response; README, main.ts, test.ts, stub, import map | §3.1 |
| `supabase/functions/join-trip/*` | F06-FN-07 / -08 | `FN_VERSION` 3.0.0-alpha.6.0 → 3.0.0-alpha.7.0, + header `X-Function-Version` (closes F05 QA D1 for this function); test pin alpha.7 + header test. No logic change | §3.2 |
| `app/index.html` flags script | F06-FLAG-01 | new `const MEMBERS_FEATURE='on'` (after `JOIN_FEATURE`) | §1 |
| `app/index.html` new style + script block after the F05 block | F06-UI-01 (MORE / MEMBERS / SHEET / WATCH / GUARD / TOUCH) | all F06 app UI and logic; returns on its first lines when `MEMBERS_FEATURE!=='on'`, `JOIN_FEATURE!=='on'` or not cloud; exposes only frozen `window.__ptF06 = {version, attach}` | §1, §3.3–3.4 |
| `app/index.html` F04 `injectMoreRow()` | F06-MORE-02 | **one new line**: `if(window.__ptF06)return;` (the F06 row replaces the F04 "קישור הצטרפות לקבוצה" row) | D1 |
| `app/index.html` gate, before the F03 bridge | F06-GATE-01 | new lines only: `window.__ptF06.attach({endpoint, key, withTimeout, timeoutMs, client, uid, tripId, role, setRole, cached, clearCached, dev, rawGet, purge, stopTrip, activeTrips, enterTrip, started, phase})` | §3.4 |
| `app/index.html` `PT_VERSION`, `APP_VERSION` | F06-VER-02 / -01 | `'3.0.0-alpha.6'` → `'3.0.0-alpha.7'` | DoD |
| `join/index.html` | F06-JOIN-01 | new `MEMBERS_FEATURE='on'`; "פתיחת הטיול" also stores the join code as raw `pt:_device:join_code:<trip>` (C5). Header version 3.0.0-alpha.7 | §1.8b, C5 |
| `join/flow.js` | F06-JOIN-02 | `VERSION` alpha.6 → alpha.7 only | §3.2 |
| `scripts/dev/f06_db_check.py`, `f06_static_check.py`, `f06_smoke.py` | F06-DEVDB-01 / DEVCHK-01 / DEVSMOKE-01 | dev self-checks (below) | — |

**Existing lines removed/changed in `app/index.html` vs `main`: exactly 2** (`PT_VERSION`, `APP_VERSION`). Everything else is
additive (757 added lines). Protected functions byte-identical (`drawMap` 379, `drawGoogleMap` 4613, `drawSchematicMap` 3427,
`fallbackToSchematic` 178, `SEED_DATA` 9277, `stayBlock` 517, `bookingUrl` 309 bytes). `join/index.html`: 1 existing line changed (the
header comment's version line); `join/flow.js`: 2 (header comment version line, `VERSION`).

## 2. Runtime hooks (new code touching existing behaviour)
- **Viewer guard (D10, §3.3)** — `SS.set` / `SS.del` (main script) and `window.storage.set` / `.delete` (gate, already wrapped by
  SYNC-MERGE) are **wrapped at runtime** in the microtask right after the main script ran (same technique as F05's
  `openUserModal` wrap), before its async boot writes anything. The main-script function bodies are unchanged (0 lines).
  With role `viewer` a guarded key never reaches `localStorage`, the queue or `trip_kv`; `SS.set/del` return `false`.
  Toast "צפייה בלבד – השינוי לא נשמר" at most once per 5 s, then `loadState(); fillSelects(); updateDates(); render()`
  (debounced 400 ms). Toast + reload only when the write follows a user gesture within 4 s (a background write at boot, e.g.
  `ensureDefaultLodgingBudget`, is blocked silently). Offline: blocked + toast, no reload (C11).
- **Guarded key set**: every key written through `SS.set` / `SS.del` / `window.storage.set|delete` that starts with
  `planner:` — today: `planner:trip`, `planner:expenses`, `planner:budget`, `planner:reservations`, `planner:googlephotoslink`,
  `planner:timeline`, `planner:checkins`, `planner:catbudgets`, `planner:personalbudget:<user>`, `planner:fxrates`,
  `planner:tripname`, `planner:userphotos`, `planner:journal:<day>`, `planner:journal:<day>:entry:<id>`,
  `planner:photo:<day>:<id>`. **Not guarded** (device-only, written with `localStorage` directly): `planner:lastsync`,
  `planner:__queue__`, `planner:mergebase:*`, `planner:lastExpenseCurrency`, `planner:qe:cur`, `planner:timeline:show`,
  `planner:visits:showplan`, `planner:chat:history:v1`, `planner:documents` (vault, local), `KEYS.user`.
- **RLS-rejected writes** (`42501`, "row-level security", the F02 "delete rejected" error) inside the `window.storage` wrapper
  trigger `fetchMyMembership()` at once (covers `flushQueue`, whose body is unchanged).
- **Role update**: `api.setRole(r)` sets the gate's `state.role` and the cached active trip, so F04/F05 `isManager()` follow.
- **Realtime**: `trip_members` `trip_id=eq.<trip>` (channel `pt6-members-<trip>`, refreshes the list/row/badge) and
  `id=eq.<my member id>` (channel `pt6-me-<id>`; an UPDATE to status≠active or a DELETE → 1.8b at once (C2), anything else →
  re-read). Checks also on start, `visibilitychange`→visible, `online`, every 60 s while visible.
- **Clean-up (removed / left)**: `purge(trip)` deletes every raw `pt:<trip>:` key and the IndexedDB `pt-vault-<trip>`; the
  cached active trip is cleared when it points to the trip; channels unsubscribed; `stopTrip()` drops further namespaced
  writes. Device record `pt:_device:removed` = `{trip_id, name, n_dropped, join_code?}` only for 1.8b.
- **Boot**: `attach()` (before `boot()`) shows 1.8b from the record (then clears it, C8); and when the cached trip did not
  start, one select of the own row — status `removed` / no row → clean-up + 1.8b now (no record, C8).
- **"ניהול ← משתמשים"** (`#mgmtUsers`) is hidden by style in cloud mode; `#mgmtTrip` gets the sub "שם, תאריכים · השם מתעדכן
  לכל הקבוצה" for managers. ("הגדרות מסע" stays inside "ניהול" — see §6.)
- **Device keys written**: namespaced `pt6_members` (cache), `pt6_role_seen`, `pt6_changed` (1.8a until "הבנתי"),
  `pt6_join_code` (managers, offline link card); raw `pt:_device:join_code:<trip>`, `pt:_device:join_code_pending` (in-app
  join flow, moved to the trip key when that trip starts), `pt:_device:removed`.

## 3. Flags
| Flag | Where | Default | `'off'` |
|---|---|---|---|
| `MEMBERS_FEATURE` | `app/index.html` flags script | `'on'` | alpha.6 exactly: no F06 block (no `__ptF06`), F04 row back, gate/F04 hooks no-ops, no guard, no watch. F06 also needs `JOIN_FEATURE='on'` |
| `MEMBERS_FEATURE` | `join/index.html` | `'on'` | the join code is not stored (alpha.6) |
D2 is server-side and applies regardless of the flags (C1): with `'off'` a removed member gets the join form.

## 4. For QA — stable ids and visible texts
**"עוד"** (`#more`): `#ptF06MembersRow` (managers) "חברים וקישור", sub `#ptF06MembersSub` "<N> חברים · תפקידים · קישור הצטרפות",
badge `#ptF06PendingBadge` "<P> ממתינים" (P>0); heading `#ptF06TripSec` "הטיול" only when F03's account section is absent.
Section `#ptF06MeSec` "אני בטיול" → `#ptF06LeaveRow` "יציאה מהטיול", sub `#ptF06LeaveSub` "כל חבר יכול לצאת בעצמו" / "את/ה
המנהל/ת היחיד/ה – קודם ממנים מנהל". In ניהול: `#ptF06TripSub` under "הגדרות מסע"; `#mgmtUsers` hidden.

**Members screen** `#ptF06Members.panel` (tab "עוד" active): back `#ptF06Back` (aria-label "חזרה"), `#ptF06Title` "חברים וקישור",
`#ptF06Sub` "<trip> · מנהלים בלבד". Link card `#ptF06Link` (`#ptF06LinkTitle` "קישור הצטרפות", "מי שפותח – ממתין לאישורך"),
URL `#ptF06Url` (LTR, monospace), `#ptF06Wa` "שליחה בווטסאפ" (wa.me, F04 text), `#ptF06Copy` "העתקה", `#ptF06Rotate` "איפוס".
Pending shortcut `#ptF06PendingRow`: `#ptF06PendingTxt` "<P> ממתינים לאישור", `#ptF06ToHome` "לאישור בבית". List: `#ptF06ListTitle`
"חברים · <N>", `#ptF06MgrCount` "מנהל/ת אחד/ת" / "<M> מנהלים", rows `#ptF06List .pt6-mrow[data-member]` (me first, then managers,
then `joined_at`; managers among themselves by `joined_at`), me "(את/ה)" + "המכשיר הזה", others "פעיל/ה היום" / "פעיל/ה אתמול" /
"לפני X ימים" / "עוד לא נכנס/ה"; "⋯" `#ptF06Act-<member_id>` (`data-act`, aria-label "פעולות על <name>"). Footnote "שינוי
תפקיד או הסרה נכנסים לתוקף מיד, גם בטלפון של החבר." Offline `#ptF06Offline` "אין חיבור – אפשר לשנות כשהרשת תחזור." (actions
disabled). Non-manager reaching it: toast "רק מנהלים יכולים לנהל חברים" and back to "עוד".

**Layer** `#ptF06Layer` (scrim `[data-f06-close]`), box `#ptF06Box` (`role=dialog` for sheets, `alertdialog` for confirms; Escape closes).
- Member sheet: `#ptF06SheetName`, close `#ptF06SheetClose` "×", role group `#ptF06Roles` (label `#ptF06RoleLbl` "תפקיד") with
  `#ptF06Role-viewer|editor|manager` "צופה|עורך|מנהל" (`aria-pressed`), help "צופה: רואה הכול, לא משנה. עורך: מסלול, הוצאות,
  מסמכים. מנהל: גם חברים, קישור והגדרות."; name `#ptF06NameIn` (maxlength 40, label "השם בקבוצה" / own "השם שלי בקבוצה"),
  `#ptF06NameSave` "שמירה", help `#ptF06NameHelp` "1–40 תווים, שם שלא קיים כבר בטיול.", error `#ptF06NameErr` (role=alert:
  F05 name_taken text / "כתבו שם של עד 40 תווים."); `#ptF06RemoveRow` "הסרה מהטיול" + "הגישה של <name> נחסמת מיד" (not on own row).
  Toasts: "<name> עכשיו <role>", "השם נשמר: <name>"; errors "בטיול חייב להישאר מנהל אחד" / "רק מנהלים יכולים לשנות" / "משהו
  השתבש. נסו שוב." / offline "אין חיבור – אפשר לשנות כשהרשת תחזור.".
- Only manager (own sheet): `#ptF06OnlyMgr` "את/ה המנהל/ת היחיד/ה בטיול", text, `#ptF06PickMgr` "למנות מנהל אחר", "אין בטיול
  חברים אחרים? פונים למנהל המערכת."; role buttons except מנהל disabled.
- Remove: `#ptF06RemoveT` "להסיר את <name> מהטיול?", 3 points, `#ptF06RemoveYes` "הסרה", `#ptF06RemoveNo` "ביטול" → toast "<name> הוסר/ה מהטיול".
- Rotate: `#ptF06RotateT` "לאפס את קישור ההצטרפות?", points (old link → "הקישור כבר לא פעיל"; "<N> החברים בטיול לא מושפעים.";
  "<P> הבקשות הממתינות נשארות – …" when P>0; "אחרי האיפוס שולחים את הקישור החדש לקבוצה."), `#ptF06RotateYes` "איפוס הקישור",
  `#ptF06RotateNo` "ביטול" → toast "נוצר קישור חדש" with action `#ptF06ToastAct` "שליחה בווטסאפ".
- Leave: `#ptF06LeaveT` `לצאת מ"<trip>"?`, 3 points, `#ptF06LeaveYes` "יציאה", `#ptF06LeaveNo` "ביטול".
Toast element `#ptF06Toast` (role=status).

**1.8a** `#ptF06Changed` (home, role=status): `#ptF06ChangedTitle` "ההרשאה שלך השתנתה ל<צופה|עורך|מנהל>", "מנהל הטיול שינה את
התפקיד שלך." (+ "אפשר לראות הכול, אבל לא לשנות." for viewer), `#ptF06Dropped` "שינוי אחד שעשית בלי רשת לא נשמר." / "N שינויים
שעשית בלי רשת לא נשמרו.", `#ptF06Ack` "הבנתי". Header tag `#ptF06ViewerTag` (v2, beside `#hv2TripTitle`) / `#ptF06ViewerTagV1`
(beside `#tripName`) "צופה".

**1.8b** `#ptF06Removed` (full screen, role=dialog): `#ptF06RemovedTitle` `כבר אינך חבר/ה ב"<trip>"`, "מנהל הטיול הסיר אותך.
הנתונים של הטיול נמחקו מהטלפון הזה.", `#ptF06RemovedDropped` (D8 line), `#ptF06Rejoin` "בקשה להצטרף שוב" (→ `../join/#code=`,
only with a stored code) or `#ptF06AskLink` "בקשו מהמנהל את קישור ההצטרפות", `#ptF06MyTrips` "הטיולים שלי" (only with another
active trip) or `#ptF06RemovedClose` "סגירה".

Endpoint: `<SUPABASE_URL>/functions/v1/manage-members`, headers `apikey` + `Authorization: Bearer <session access_token>`.

## 5. Local checks (sandbox; no Deno binary, no registries, no Supabase)
- `sudo -u postgres python3 scripts/dev/f06_db_check.py ""` (0001…0014, 0014 applied twice) → qa.f01–f04 109/37/49/90,
  **qa.f05 118/120** (rows 100/101 = the F05 rule "removed → member_removed" that D2 replaces on purpose), **F06 scenarios
  92/92**, 0 leftovers.
- `node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/{manage-members,join-trip,approve-member}/test.ts` → **23/23**.
- `python3 scripts/dev/f06_static_check.py main` → ALL OK: every inline script `node --check` OK, no new duplicate ids (app, join),
  protected functions identical, versions alpha.7, 2 changed lines, every diff hunk carries an F06 CHANGE marker (the new
  `test_import_map.json` is exempt: JSON has no comments).
- `python3 scripts/dev/f06_smoke.py` (Playwright, fake supabase-js, 390px) → **49/49**: flag off = alpha.6 "עוד"; members row
  + badge; list order/counts/last seen; URL LTR; no h-scroll; touch ≥44px; rename (taken / ok); set_role; rotate + toast;
  only-manager sheet; leave → 1.6; remove; viewer guard (toast, kv / localStorage / queue unchanged, device key still written);
  1.8a live + "הבנתי"; D8 drop of 2 queued ops; 1.8b via Realtime payload (C2), keys purged, no chrome; 1.8b once more at boot
  then record cleared (C8); rejoin → form → same row pending; leave → not-connected card; manager sees re-request; self-demote
  hides the row; offline leave toast (C10); no page errors.
- F05 regression: `f05_db_check` ALL OK (51/51; it applies 0001–0012 only), `f05_static_check main` ALL OK (2 changed lines),
  `f05_smoke` 28/28.
- F20 QA browser suite (`tests/f20/test_f20.py`, not static): **63/63**. Its `test_st_static` rows: 10 fail on `main` as well
  (alpha.4.2 base / alpha.5.1 version pins); 2 more fail on f06 by design (F20-only "every hunk has an F20 marker" and "no
  DB/function change"). F02/F03/F04 QA suites were not run (their runners need a v2.15.2 baseline checkout not present here).

## 6. Deviations from the spec (with reason)
1. `rotate_join_code` / `rotate_link` return the link version as `link_version` (C4), not `version` (body `version` = function version).
2. Viewer guard and membership watch hook by **wrapping** `SS.set/del` and `window.storage.set/delete` at runtime instead of
   editing `SS` (keeps 0 changed main-script lines; behaviour as §3.3). Toast/reload only after a user gesture (≤4 s) so
   background boot writes don't toast.
3. "הגדרות מסע" stays in "ניהול" (where the app has it); the D4 sub-text is added there, not as a new row in "עוד".
4. 1.8b: when there is no other active trip, a "סגירה" button is shown (the mockup has only "בקשה להצטרף שוב" / "הטיולים
   שלי"); without it the screen could not be left to reach the not-connected card (C8).
5. On the members list my own row's sub is "המכשיר הזה" (mockup) instead of a last-seen text.
6. A second Realtime channel on `trip_members` (`pt6-members-<trip>`) is used for the list instead of the F05 channel (F05's
   handler lives in its closure; reusing it would need an F05 code change).
7. Remove dialog points are gender-neutral ("הגישה נחסמת מיד, גם בטלפון של <name>." …) where the mockup used "שלו".
8. F06 requires `JOIN_FEATURE='on'` as well (it builds on the F05 member model).

## 7. Spec clarifications applied (architect, 2026-10-22)
C1 D2 is server-side, independent of the flag · C2 own-row Realtime UPDATE→removed shows 1.8b at once (poll = backstop) ·
C3 1.8a text without a manager name · C4 `link_version` · C5 device-wide `pt:_device:join_code:<trip>` from `/join/` and the
in-app join flow; else "בקשו מהמנהל את קישור ההצטרפות" · C6 unknown member → `not_active` (409); leave/touch non-active →
`not_member` (403); null/missing args → `invalid_request`; lower-case roles only; touch within 10 min → `{ok:true,
touched:false}` · C7 trigger only for an active manager's session; trim + collapse whitespace, 1–80 after cleaning · C8 1.8b
until a tap / app close; once more at the next boot, then the record is cleared · C9 touch on start and on visible (≤1/10 min)
· C10 the listed toast/error texts · C11 anonymous identities accepted; re-request keeps `last_seen_at`; remove/leave delete
open `relink_tokens`; the guard works the same offline (no reload); managers among themselves by `joined_at`.

## 8. Open questions
1. F04 "צעדים ראשונים" keeps its in-memory join URL after a rotate until the next app start (no F04 API to refresh it).
2. After a role change, F05's pending card may repaint once with the old role before `setRole` lands (≤ one Realtime event /
   60 s); harmless (approve would return `not_manager`).
3. `0015_qa_f06_harness.sql` is for the QA team; `f06_db_check.py` applies and runs it automatically when present.
4. `pt:_device:join_code:<trip>` is never deleted (it is what "בקשה להצטרף שוב" needs); confirm that is acceptable.
