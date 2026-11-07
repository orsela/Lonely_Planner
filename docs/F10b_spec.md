# F10b — Trip currencies screen: add, swap, remove (cap 10) · spec

<!-- CHANGE 2026-11-07 F10B-DOCS-01: new file (no previous version). -->

Base: `main` 43394ff (app 3.0.0-alpha.9). Target: app **3.0.0-alpha.10**. Decisions: claude/Plan_Travel_F10b_decisions.md
(D1–D8, Or, 2026-11-07). Mockup: canvas row 12 (`F10b_*`, approved 2026-11-07). Scope: `app/index.html` only (+ docs,
CHANGELOG, tests). **No migration, no Edge Function, no change in `/request/`, `/join/`, `/invite/`, the F04 wizard, F10's
TRIPCUR rules (§1 of docs/F10_spec.md) or `SEED_DATA`.**

## 0. Server facts this feature relies on (already live, verified 2026-11-07)

- `public.trip_currencies(trip_id uuid, currency_code char(3) ^[A-Z]{3}$, kind 'base'|'destination'|'added', sort int)`,
  PK `(trip_id, currency_code)`.
- RLS: select = trip members; insert / update / delete = trip **managers** only.
- Trigger `trip_currencies_limit` (AFTER INSERT OR UPDATE OF trip_id): more than 10 rows → error `currency_limit: …`
  (SQLSTATE 23514).
- Trigger `trip_currencies_base_lock` (BEFORE DELETE OR UPDATE): a `base` row cannot be deleted or changed → error
  `base_currency_locked: …` (23514).
- Duplicate code → 23505.

## 1. Flag

`const CURMGR_FEATURE='on';` right after `CURRENCY_FEATURE`. Needs `CURRENCY_FEATURE='on'` and `STORAGE_BACKEND='cloud'`.
`'off'` (or either prerequisite missing) → no row, no screen, no link, no network call: the app is alpha.9 exactly.

## 2. Entry points (D1)

- **"עוד"**: a row `#ptF10bRow` "💱 מטבעות", sub "<N> מתוך 10", for **every member** (D2), in the "הטיול" section,
  after the F06 row "חברים וקישור" when it exists (else at the top of that section / the list, F06 convention).
- **Quick FX sheet** (`#fxQuickModal`): a link `#ptF10bFxLink` "💱 ניהול מטבעות" at the bottom of the sheet; tap closes the
  sheet and opens the screen. Shown to everyone.

## 3. The screen `#ptF10bPanel` (a `.panel`; tab bar, FX pill and chat button stay; "עוד" tab is active)

- Header: back `›` (`#ptF10bBack` → "עוד"), title "מטבעות", sub = "<trip name> · <N> מתוך 10" (`#ptF10bSub`).
  At 10: "10 מתוך 10 · מלא".
- Group **"מטבעות בסיס"**: one row per `kind='base'` currency (home first, then the other bases in `sort` order).
  Row: symbol, "<he> · <CODE>", sub "מטבע הבית" for home else "בסיס", and a lock + "קבוע". No actions.
- Group **"יעדים ונוספים"**: every other row in `sort` order. Row: symbol, "<he> · <CODE>", sub = "<flag> <country he>" when
  the code is the currency of a trip country, else "נוסף ידנית". Manager online: a `⋯` button (`data-f10b-act="<CODE>"`,
  `aria-label="פעולות על <he>"`).
- Footer button `#ptF10bAdd` "+ הוספת מטבע" (manager only).
- Source of the list: `trip_currencies` read from the DB when the screen opens (online); offline → TRIPCUR cache
  (`window.__ptF10.get()`), base rows = ILS/USD/EUR present in it.
- Order in the converters / chips is **not** changed by this screen (D7, F10 D6: local ← home ← rest; added at the end).

### Roles (D2)
- Manager: actions as below.
- Editor / viewer: same list, no `⋯`, no add button, and a note `#ptF10bRO` "רק מנהל הטיול יכול להוסיף, להחליף או להסיר
  מטבעות."

### Offline (D6)
- Manager offline: list shown (from cache), no `⋯`, add button `disabled`, note `#ptF10bOff` "אין חיבור. צריך חיבור כדי
  לשנות מטבעות – הרשימה מוצגת כפי שנשמרה." Coming back online repaints with actions.

## 4. Add (D5) and swap when full (D3)

- `#ptF10bAdd` opens sheet `#ptF10bPicker`: title "הוספת מטבע", sub "<N> מתוך 10 · נשארו <10−N>" (at 10: "יש כבר 10 –
  בוחרים מטבע ואז מה יוצא"), search input `#ptF10bSearch` (matches Hebrew name, code, English name, and Hebrew / English
  name of any country using it; case-insensitive), group **"מוצעים"** = currencies of trip countries (`trip_countries`
  → countries.json `currency`) that are not in the trip, then **"כל המטבעות"** = currencies.json sorted by Hebrew name.
  Codes already in the trip are shown disabled with "כבר בטיול". One choice (radio, `aria-pressed`); confirm button
  `#ptF10bConfirm` "הוספת <he> (<CODE>)" (disabled until a choice).
- **N < 10** → `insert {trip_id, currency_code, kind, sort: max(sort)+1}`; `kind='destination'` when the code is the
  currency of a trip country, else `'added'`.
- **N = 10** → after the choice, sheet `#ptF10bSwap`: "מוסיפים <sym> <he> · <CODE>", sub "יש כבר 10 מטבעות – בחרו אחד
  שיוצא במקומו", radio list of the non-base rows (base never listed), note with the expense count of the chosen one
  (§6), button `#ptF10bSwapGo` "החלפת <OLD> ב-<NEW>" (disabled until a choice).
- **Swap = one UPDATE** of the chosen row: `currency_code=<NEW>, kind=<as above>, sort=max(sort)+1`
  `.eq(trip_id).eq(currency_code,<OLD>)` (atomic; the limit trigger does not fire on it).

## 5. Row actions (`⋯`, manager online)

Sheet `#ptF10bRowSheet`: header symbol + "<he> · <CODE>", actions **"⇄ החלפה במטבע אחר"** (`#ptF10bDoSwap`, opens the
picker in swap mode: pick NEW → same UPDATE as §4, no second list) and **"✕ הסרה מהטיול"** (`#ptF10bDoRemove`, red).

### Remove (D4)
Alert `#ptF10bRemove`: title "להסיר <he> מהטיול?", text: when the trip has k>0 expenses with `originalCurrency=<CODE>`:
"<k> הוצאות נשמרו ב<he> – הן יישארו כמו שהן (הסכום שמור גם במטבע הבית). " + always "<he> לא יופיע יותר בממיר ובשבבים.";
buttons "ביטול" / "הסרה" (`#ptF10bRemoveGo`, red) → `delete .eq(trip_id).eq(currency_code)`.
Removing the currency of a trip country is allowed (D4); the country stays.

## 6. After every successful write

1. `await window.__ptF10.refresh()` → TRIPCUR rebuilt, every chip row / text rebuilt by F10's `onChange`.
2. **Rate for a new code** (C1): if online and no rate exists for it (saved v2 object or live memory), fetch er-api once
   (`f10Live`), and keep the rate in the live memory so converters work at once. If saved rates exist (shared v2 object)
   and lack the code, the **manager's** device adds that code's rate to the saved object (`SS.set`, existing keys
   untouched; ILS-home legacy fields unchanged). Offline / failure → F10 "אין שער" behaviour.
3. Repaint the screen, the "עוד" row count, and toast `✅` "<he> נוסף" / "<NEW> נכנס במקום <OLD>" / "<he> הוסר".
- Expenses are never changed (D4/D8). A removed / swapped-out currency simply disappears (D8). A remembered pick
  (`planner:lastExpenseCurrency`, `planner:qe:cur`) that is no longer listed falls back to local (F10 §3, already).

## 7. Errors (all keep the screen; no partial state)
- `currency_limit` (another manager filled it meanwhile) → "הטיול הגיע ל-10 מטבעות – בחרו מטבע להחלפה" and reload list.
- 23505 → "<CODE> כבר בטיול" and reload. `base_currency_locked` → "מטבע בסיס קבוע". RLS / 401 / 403 (role changed) →
  "רק מנהל הטיול יכול לשנות מטבעות" and repaint as read-only. Timeout / network → "אין חיבור – נסו שוב".

## 8. Versions / code rules
`PT_VERSION` / `APP_VERSION` → '3.0.0-alpha.10' (`CHANGE 2026-11-07 F10B-VER-0N: was '3.0.0-alpha.9'`). Every new block /
changed line carries `CHANGE 2026-11-07 F10B-<AREA>-NN`. Additive only; existing function bodies unchanged except one-line
hooks. CHANGELOG entry. 390 px, RTL, every control ≥44 px, real buttons with aria-labels. No new network origin.

## 9. Acceptance criteria (automated unless 📱)

Fixtures (F10 harness): **S** (ILS; TH VN KH; ILS USD EUR + THB VND KHR = 6), **E** England (ILS; GB; bases only = 3),
**F** full (S + MYR SGD IDR PHP added = 10), plus trip country LA for S/F in the swap tests (LAK suggested).

1. "עוד": manager and editor both see `#ptF10bRow` with "6 מתוך 10" (S). Opening it shows 3 base rows with "קבוע" and 3
   other rows in sort order.
2. Quick FX sheet shows `#ptF10bFxLink`; tap closes the sheet and opens the screen.
3. E, manager: picker "מוצעים" contains GBP (country GB); confirm → row inserted `{GBP,'destination',sort 3}`; TRIPCUR
   list now contains GBP, local = GBP; the expense chip row shows £; toast; count "4 מתוך 10".
4. Search "ין" / "JPY" / "יפן" finds JPY; codes in the trip are disabled "כבר בטיול".
5. Added code that is no trip country's currency → `kind='added'`, appended last in TRIPCUR.list.
6. F (10/10): add → pick LAK → `#ptF10bSwap` lists only the 7 non-base rows; choose KHR → exactly one PATCH
   (`currency_code=LAK`); no POST, no DELETE; count stays 10; KHR gone from all chip rows.
7. `⋯` → "החלפה" on THB → pick JPY → THB replaced by JPY (one PATCH).
8. `⋯` → "הסרה" on KHR with 3 KHR expenses: alert text contains "3 הוצאות נשמרו ב" ; "הסרה" → one DELETE; expenses
   unchanged byte-for-byte; count 5.
9. Base rows have no `⋯`; a forced DELETE/PATCH of a base row is not offered anywhere in the UI.
10. Editor and viewer: no `⋯`, no `#ptF10bAdd`, `#ptF10bRO` shown; no write request is ever sent.
11. Offline manager: list from cache, `#ptF10bOff` shown, add disabled, no `⋯`; back online → actions return.
12. Errors: backend answers `currency_limit` / 23505 / 403 → the §7 texts; list reloaded; no exception.
13. Rates: online, saved v2 rates without GBP (trip E) → after adding GBP the saved object gains `rates.GBP` (from the
    stubbed er-api) and keeps every other key; converting £→₪ works without reload. Offline add is impossible (11).
14. Flag `CURMGR_FEATURE='off'`: no `#ptF10bRow`, no `#ptF10bFxLink`, no panel; DOM of "עוד" and the FX sheet equals
    alpha.9 (43394ff).
15. 390 px: no horizontal scroll on the screen and every sheet; all controls ≥44 px; RTL.
16. Regression: F10 suite and `tests/run_all.sh` green (with `QA_EXPECTED_VERSION=3.0.0-alpha.10`).
17. 📱 Or's Android phone: add GBP to "אנגליה חורף 26"; the chips show £.
