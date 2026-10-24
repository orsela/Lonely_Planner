# F06 · Independent QA suite — member management, link rotation, viewer guard (3.0.0-alpha.7)

<!-- CHANGE 2026-10-22 F06-QA-07: new file (no previous version). -->

Contract: `docs/F06_spec.md` (branch `f06`, 858bce3) **only**. The implementation (app F06 block, `0014_f06.sql`,
`supabase/functions/manage-members`, the `join-trip` alpha.7.0 change) was not read; the suite was written before it existed.
Conventions follow F05 (`0013_qa_f05_harness.sql`, `tests/f05/*`).

## Files

| File | What | Cases |
|---|---|---|
| `supabase/migrations/0015_qa_f06_harness.sql` | `qa.f06_run()` — DB level: the six §2 functions, D2 join, tripname trigger, grants, policies, cross-trip isolation. Everything inside one sub-transaction that is always rolled back (`f06_rollback`); case 999 checks for leftovers. | **171** rows (ids 101–999) |
| `tests/f06/function_test.ts` | `manage-members` Edge Function through `setDeps` / `handler` (as approve-member): actions → SQL calls, statuses §3.1, version header + body, CORS, logs. | **19** (F6-FN-01…19) |
| `tests/f06/test_f06.py` + `harness.py` | Playwright, 390×844, he-IL: screens §1, client §3.3–§3.4. The harness extends the F05 one (fake supabase-js with Realtime is reused unchanged from `tests/f05/fake_supabase.js`) with an in-memory `manage-members`, the D2 `join-trip` behaviour and the tripname trigger. | **40** test functions, **70** collected cases |
| `tests/f06/db_check.py` | Applies shim + 0001…0014 + 0015 (twice) to a **local** PostgreSQL and runs `qa.f01–f06_run()`. `--stub` = signatures-only 0014. | — |
| `tests/f06/run.sh` | Runner: `--only f06 \| fn \| db \| off`. | — |

## How to run

```bash
tests/f06/run.sh                 # everything
tests/f06/run.sh --only f06      # browser suite (needs playwright + chromium)
tests/f06/run.sh --only fn       # function tests on Node 22 (no Deno needed)
tests/f06/run.sh --only db       # local PostgreSQL 16/17 via sudo -u postgres psql (needs 0014_f06.sql in migrations/)
tests/f06/run.sh --only off      # criterion 1: repo copy with MEMBERS_FEATURE='off' → tests/f05/run.sh (F05 + F20/F04/F03/F02)
python3 tests/f06/db_check.py --stub   # 0015 syntax / catalog check before 0014 exists
```

On the real project (Or, SQL Editor, after 0014): run `0015_qa_f06_harness.sql`, then
`select * from qa.f06_run() order by id;` — every row `pass = true`; regression `qa.f01–f05_run()` still green. Advisors
(criterion 17, last clause) are checked in the dashboard: no new warning.

Function tests need `supabase/functions/manage-members/test_stubs/supabase_js.ts` (the Node runner maps
`npm:@supabase/supabase-js` to it, like the other functions) and the exports `handler`, `setDeps({getUser, rpc})`,
`resetDeps`, `FN_VERSION`.

### Selectors in the browser suite
F06 element ids are not in the spec. Elements are found by visible Hebrew text, `aria-label="פעולות על <name>"`, `aria-pressed`
on the role segment, and existing alpha.6 ids (`#newWaypoint`, `#wpName`, `#saveWaypoint`, `#mgmtUsers`, `#ptF05Pending`,
`#lpJoin[data-screen]`, `#lpjName`). Places marked `TODO(dev-notes id)` in `test_f06.py` (sheet container / name input,
viewer header tag) should switch to the ids in `docs/F06_dev_notes.md` once it exists. The device record of §3.4
(`pt:_device:removed`) is used by name as the spec gives it.

### Self-checks done (without the implementation)
- `0015` applies twice on PostgreSQL 16 after 0001–0013 + a signatures-only 0014 stub; `qa.f01–f05_run()` stay 109/37/49/90/120
  green; `qa.f06_run()` runs to the end (42/171 pass on the stub, which are refusal / no-write / catalog rows; every
  behaviour row fails as it must); 0 rows left behind.
- `function_test.ts`: 19/19 against a throw-away, spec-shaped handler in the scratchpad (not committed), to prove the file
  runs on the Node runner.
- `test_f06.py`: collects 70 cases. Run against alpha.6 (main, 2026-10-24, 8.5 min): 7 pass / 63 fail. Every failure is
  "F06 UI / behaviour missing" or "MEMBERS_FEATURE not declared" (no harness error after fixing the offline localStorage
  read). The passes are the cases whose expected outcome is the same in alpha.6 as in alpha.7: b02[0] (no badge),
  b03[2] (no only-manager sub), h03[editor/manager] (writes reach trip_kv, no toast), h04[editor] (no viewer tag),
  l01[more] (layout of "עוד"; it gains the F06 rows once they exist).

## Criteria → tests matrix (`docs/F06_spec.md` §4)

| # | Criterion (short) | DB `qa.f06_run()` ids | Function (`F6-FN-`) | Browser (`test_f06.py`) |
|---|---|---|---|---|
| 1 | flag off = alpha.6 | — | — | a01, a02[manager/editor/viewer], a03, a04, a05; `run.sh --only off` (F05 runner on the flipped copy) |
| 2 | "עוד" rows by role, badge, leave for all | — | — | b01[3 roles], b02[0/2], b03[1/2 managers] |
| 3 | members list, order, counts, link card, shortcut | — | — | c01, c02, c03, c04[0/2], c05, c06 |
| 4 | set_role, not_manager, not_active, last_manager | 101–122, 132–137 | 02, 06, 08 | d01 |
| 5 | two managers: self-demote, row disappears live | 130, 131, 136 | — | d04 |
| 6 | rename, taken / invalid | 201–223 | 09 | d02[ok/taken/invalid] |
| 7 | remove, transfer codes, self, last_manager | 301–318 | 02, 06 | d03 |
| 8 | removed member's phone | (306, 307) | — | f01[visible/poll60/online], f02, f03, f04[cached/not], f05 |
| 9 | removed identity asks again (D2) | 701–720 | — | f04[cached], f06 |
| 10 | leave, only manager → 1.6 | 401–411 | 04, 06 | e01[other trip/none], e02, d05 |
| 11 | rotate_link | 501–516 | 12 | d06 |
| 12 | viewer guard | — | — | h01[expense/journal/waypoint/checkin], h02, h03[editor/manager], h04[viewer/editor], a03 (off) |
| 13 | demotion drops the queue | — | — | g04 (and f05 for removal) |
| 14 | role change shown ≤3 s / ≤60 s, "הבנתי" | — | — | g01[4 transitions], g02[poll60/visible], g03 |
| 15 | tripname → trips.name | 801–818 | — | — (DB side covers it; the F20 list / admin summary read `trips.name`) |
| 16 | last_seen_at | 601–609 | 02 (touch) | c02 (list), h05 |
| 17 | grants, no policies, cross-trip | 113, 122, 219, 306, 311, 314, 410, 411, 513, 516, 609, 816, 850–856, 900–917 | 03 | — |
| 18 | 390px, RTL, ≥44px, URL LTR | — | — | l01[9 screens], c03 |
| 19 | offline | — | — | j01, j02 |
| 20 | protected functions, versions, CHANGE tags, node --check, ids | — | 01 (FN_VERSION) | not in this suite's scope (static; F05 `test_s01_static` pattern applies) |
| §3.1 | manage-members contract | — | 01–19 | — |

## Spec ambiguities (tests accept either reasonable outcome where marked "open" in the case name)

- **A-1 Flag off vs D2.** §1 says `'off'` = alpha.6 exactly including the F05 `member_removed` message, but §2.6/§3.2 make the
  server stop producing `member_removed` regardless of the flag, so with the flag off a removed identity gets the form, not
  the message. a05 emulates the old server; on the real server criterion 1 cannot hold for this case.
- **A-2 Realtime for removed members (D11).** D11 says a removed member no longer receives Realtime events for its row, but
  the F01 policy `trip_members_select` has `or user_id = auth.uid()`, so the member still sees its own row and should get the
  UPDATE to `removed`. Harmless (the check catches it either way) but the client should handle a live `status='removed'`
  event too. Harness default follows the spec (`rt_removed_events=False`).
- **A-3 "<manager> שינה/תה את התפקיד שלך" (1.8a).** The member's phone cannot know which manager changed the role: no
  `changed_by` column, no actor in the Realtime payload, and §2 allows no schema change. Needs a rule (earliest manager as in
  F05 preview? drop the name?). g01 checks only "שינה/תה את התפקיד שלך.".
- **A-4 The key `version` in the rotate_link response.** `rotate_join_code` returns `{code, version:<int>}` and §3.1 says the
  body field `version` = `"3.0.0-alpha.7.0"`. They collide; F6-FN-10 accepts either winner, and F6-FN-12 only requires the
  int somewhere in the body. Suggest `link_version`.
- **A-5 Cached join code for "בקשה להצטרף שוב" (1.8b).** A member device never stores the join code in alpha.6 (F05 keeps it
  only in sessionStorage during /join/). Where is it cached, and after a rotation (D3) the cached code is dead → "הקישור כבר
  לא פעיל". f04 seeds `pt:_device:removed.join_code` directly.
- **A-6 Error codes not fixed by the spec.** Unknown member id (set_role / rename / remove): `not_active` / `not_member` /
  `not_manager` / `invalid_request`? Leave or touch by a pending / removed / foreign identity: `not_member` or `not_active`?
  Null arguments: `invalid_request` vs `role_invalid` / `name_invalid`? Role in another case (`'Editor'`): `role_invalid` or
  accepted? All accepted as alternatives (cases 109–110, 120–121, 211, 315, 403, 405, 409, 515, 607–609).
- **A-7 member_touch when it skips.** "at most once per 10 minutes": assumed to return ok without writing (602–603).
- **A-8 Trigger and service-role writes (§2.7).** Writer = `auth.uid()`; imports / Edge Functions write with no JWT → never
  update `trips.name` (818 asserts this). Confirm intended. "Collapsed spaces" assumed to mean all whitespace (tabs too),
  as `private.f05_clean_name`; range checked after cleaning (812). `update of value` vs plain update accepted (908).
- **A-9 §2.3 last_manager on remove** is "only reachable with two managers removing each other at once" — not reproducible in a
  single-session harness; 316–317 test the sequential form (the second caller is no longer a manager → `not_manager`).
- **A-10 1.8b after the boot.** "at the next boot the same screen shows … and then the not-connected card / next trip" —
  what moves on (a button, a timeout, the boot after)? When is `pt:_device:removed` cleared? Tests only assert the boot
  screen.
- **A-11 touch on visible.** §2.8 says "app start / visible", criterion 16 says "on app start". h05 expects a call on
  visible as well (the server limits writes).
- **A-12 Texts not given.** Toast for a stale non-manager on the members screen (c06), toast for offline leave/remove (j02
  only checks "אין חיבור"), the elided "N שינויים … לא נשמרו" (regex, and the N=1 wording), the refusal toasts on the sheet
  (`last_manager` / `not_active` when the target left meanwhile).
- **A-13 Anonymous callers.** Not stated that `manage-members` accepts anonymous identities; it must (F05 members are
  anonymous; leave / touch). F6-FN-04.
- **A-14 Re-used row on re-request (§2.6).** `last_seen_at` is not mentioned (keep or reset); role = default even for an
  ex-manager (706 asserts default). Preview "as for a new identity": `me = null` assumed; `me.status='removed'` also accepted
  (701).
- **A-15 Removal and F01 `relink_tokens`.** Only transfer codes are deleted on removal/leave; open relink tokens of the
  member are not mentioned.
- **A-16 Viewer guard offline.** "then reload from the cloud" is impossible offline; behaviour unspecified. The guarded key
  set is left to the dev notes.
- **A-17 Order of managers among themselves** in the members list: assumed by `joined_at` (c01).
