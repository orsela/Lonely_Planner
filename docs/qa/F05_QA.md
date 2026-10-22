# F05 · QA report — a member joins from the group link, after manager approval (v3.0.0-alpha.6)

<!-- CHANGE 2026-10-22 F05-QA-02: new file (no previous version). Short closing report: by Or's decision (2026-10-22) F05 was
     merged after the dev self-check and verified on his phone; the independent QA suite was stopped part-way. -->

Spec: `docs/F05_spec.md` · Dev notes: `docs/F05_dev_notes.md` · Live: `main` = 29d1e21 (2026-10-22), function versions
`join-trip` v1 / `approve-member` v1 (3.0.0-alpha.6.0), migrations 0012 (applied 2026-10-19) and 0013 (applied 2026-10-22).

## Decision
Or (2026-10-22): merge now and test on the phone; the full independent QA (browser suite + F02/F04/F20 regression) is
**not** run for F05. Rollback: `JOIN_FEATURE='off'` in `app/index.html` and `join/index.html`.

## Results

| Check | Where | Result |
|---|---|---|
| DB harness `qa.f05_run()` (independent QA, 0013) | **real project** | **120/120** |
| Regression `qa.f01–f04_run()` | real project, after 0012 + 0013 | 109/109 · 37/37 · 49/49 · 90/90 |
| Dev DB scenarios (`scripts/dev/f05_db_check.py`) | local Postgres | 51/51, 0 leftovers |
| Function unit tests (dev) | Node runner | 14/14 |
| Function tests (independent QA, `tests/f05/function_test.ts`) | Node runner | 11/12 — finding F05-QA-D1 |
| Browser smoke (dev, `scripts/dev/f05_smoke.py`, 390px) | local Chromium | 28/28 |
| Static: node --check all scripts, no new duplicate ids, protected functions byte-identical, 3 changed lines | local | OK |
| F03 browser regression (independent QA) | local | 47 pass, 1 skip, 11 deselected (as in the F04/F20 runners) |
| Independent browser suite `tests/f05/test_f05.py`, F02/F04/F20 regression | — | **not run** (stopped) |
| Supabase advisors | real project | no new warning; 2 expected INFO notes (RLS on, no policy) for `private.transfer_codes` / `private.join_attempts` |

## Phone check (Or, 2026-10-22, Android Chrome + incognito tab)
1. The join link opened on the manager's own phone → recognised as an active member → straight into the trip (D7). ✓
2. Incognito tab → join page with trip name, dates and manager → name "בדיקה" → "הבקשה נשלחה" (server: pending, editor). ✓
3. Manager's home: "ממתינים לאישור · 1", role switched to צופה, "אישור כצופה" → card gone (server: active, viewer). ✓
4. The waiting tab switched to "הבקשה אושרה – ברוכים הבאים, בדיקה!" by itself within seconds; no transfer card on Android. ✓
5. "פתיחת הטיול" → trip home with the name "בדיקה", no "מי אני" picker, no pending card (viewer). ✓
Not checked on a phone: reject flow, iPhone transfer code (covered by the DB harness and the dev smoke test only).

## Findings
- **F05-QA-D1 (low, spec §3 "Version header alpha.6.0")** — `join-trip` / `approve-member` responses carry no version
  header (the version is only in the logs). Repro: any POST → no `x-function-version`-style header. Fix: add the header
  in the next function deploy.

## Test data left in the real project
Trip "טסט3": member "בדיקה" (viewer, anonymous incognito identity). Harmless; remove from the member screen when F06 exists.
