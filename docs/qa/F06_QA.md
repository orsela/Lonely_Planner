# F06 · QA report — a manager changes roles, removes members and resets the link (v3.0.0-alpha.7)

<!-- CHANGE 2026-10-26 F06-DOCS-03: new file (no previous version). -->

Closed 2026-10-26 by Or's decision with a **partial phone check** (same "value fast" rule as F05): the full automated
QA ran; the phone check stopped after step 4א. Contract: `docs/F06_spec.md` (+ §0.1 rulings C1–C11). `main` = 0722872.

## 1. Results
| Check | Where | Result |
|---|---|---|
| `qa.f06_run()` (independent QA harness, 0015) | real project, 2026-10-26 | **171/171** |
| `qa.f01–f05_run()` regression | real project | 109/37/49/90 full; f05 **118/120** — rows 100/101 test the F05 rule "removed → member_removed", replaced on purpose by F06 D2 |
| Independent browser suite `tests/f06` (70 cases, 390px) | local, fake Supabase | **70/70** (first run 46/70; triage in docs/F06_dev_notes.md §9: 7 app bugs fixed, 7 test-side fixes, none weakened) |
| Independent function tests `manage-members` | local | **19/19** (found: `ok:true` missing on 3 actions — fixed, F06-FN-09) |
| Dev checks | local | DB 92/92, functions 23/23, smoke 49/49, static clean (2 existing lines changed in app/index.html) |
| Flag off (`MEMBERS_FEATURE='off'`) → F05 runner on F02–F05/F20 suites | local | identical failure set to a clean `main` (alpha.6) run → no F06 regression. Those failures are pre-existing test debt (see §3) |
| Supabase advisors (security) | real project | no new item |
| Phone (Or, 2026-10-26) | live alpha.7 | 4א passed: "עוד" row, members screen, removal of the F05 test member "בדיקה" (server: remove 200, row removed), touch/last-seen working; a real join + approve ("אבנר", manager) on alpha.7.0 functions |

## 2. Not checked on a phone
Role change seen live on the member's phone (1.8a), viewer guard (D10), removed screen (1.8b) and re-request (D2), link
rotation, leave, only-manager screen (now not reachable in "טסט3" — it has two managers), trip rename → `trips.name`.
All are covered by the automated suites above.

## 3. Open (not blocking)
- Dev open questions (dev notes): the F04 "צעדים ראשונים" card keeps the old WhatsApp link until restart after a reset;
  the F05 pending card may show once with the old role right after a role change; `pt:_device:join_code:<trip>` is never
  deleted.
- Pre-existing test debt (also failing on alpha.6 `main`): protected-function and parity checks in the F02–F05/F20 suites
  (missing reference checkout); F05 function tests pin alpha.6.0.
- The `manage-members` header comment lists success bodies without `ok:true` (cosmetic).
- "טסט3" now has a real member ("אבנר", manager): run future phone tests in a separate test trip.
