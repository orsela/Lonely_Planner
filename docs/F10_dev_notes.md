# F10 — dev notes (app 3.0.0-alpha.9)

<!-- CHANGE 2026-11-07 F10-DOCS-02: new file (no previous version). -->

Contract: `docs/F10_spec.md`. Scope: `app/index.html` only (+ this file, CHANGELOG). No migration, no Edge Function,
nothing in `/request/`, `/join/`, `/invite/`, the F04 wizard flow or `SEED_DATA`.

Every changed or added line carries `CHANGE 2026-11-07 F10-<AREA>-NN: … (was: …)`. Tags:
FLAG-01, CUR-01, F04-01/02, GATE-01, VER-01/02, CORE-01, PLACES-01, P1-01…04, P2-01/02, P3-01…03, P4-01…05,
P5-01…05, P6-01, P7-01…05, P8-01, P9-01…07, P10-01, EXP-01…03.

## 1. Flag

`const CURRENCY_FEATURE='on';` in the flags script, right after `REQUEST_FEATURE` (F10-FLAG-01).
`'off'`: the head block returns on its first line (no `window.__ptF10`), so `CUR_ON` is `false` and every F10 line in the
main script is a no-op. Verified: with `'off'` the outerHTML of `#budget`, `#fxQuickModal`, `#globalFxBtn` and `#resCost`
is identical to 4ca777b (alpha.8) for a V and a T trip (dev check, §6 below).

## 2. Where the code is

| Piece | Location | What |
|---|---|---|
| F10-CUR-01 | new `<script>` after the F06 block (head) | `window.__ptF10` (frozen): `version, attach, get, snapshot, onChange, setUnit, refresh, source`. Builds TRIPCUR. |
| F10-F04-01/02 | end of the F04 block | `window.__ptF04.curData()` = the wizard's own `loadData()` (countries.json / currencies.json, lazy, not precached) → `{byCode, curByCode}`. |
| F10-GATE-01 | gate IIFE, before the F03 bridge | `__ptF10.attach({withTimeout, timeoutMs, client, tripId})`; `window.__PT.tripcur` = getter returning a fresh copy (null before a trip is known). |
| F10-CORE-01 | main script, right after `SS` | `CUR_ON`, `f10TC`, `fmtHome`, rates v2 (`f10Parse`, `f10Rates`, `f10Live`, `f10Hpu`, `f10Conv`), D4 helpers (`f10Legacy`, `f10Amt`, `f10AmtTxt`), chip rows (`F10_ROWS`, `f10Row`, `f10OpenMore`), `f10RefreshTexts`. |
| F10-PLACES-01 | end of the main script | the F10 versions of every place (`f10ApplyExpenseUI`, `f10SaveExpense`, `f10RefreshFxInputs`, `f10SaveRates`, `f10BudgetCalc`, `f10QuickCalc`, `f10QeSave`, `f10ChatFx`, …), `homePerUnit(code)`, the `#f10Css` style and the boot/refresh hook. |
| hook lines | in the alpha.8 functions | one guard line each: `if(CUR_ON)return f10…()` or `if(!CUR_ON)` around the old static chip binding. |

### TRIPCUR (spec §1)
- Read on first `get()` after the trip is known: localStorage `tripcur` (= `pt:<trip>:tripcur` through the F02 namespace),
  else the fallback `{home:'ILS', local:'VND', list:['VND','ILS','USD','EUR']}`; then `refresh()` reads
  `trips.home_currency`, `trip_countries(country_code,sort)`, `trip_currencies(currency_code,kind,sort)` with the gate's
  client (8 s timeout) + `curData()`. When the result differs from what is shown, `onChange` listeners rebuild every row
  and text. Offline: refresh is retried on the `online` event.
- A trip with no country rows, no currency rows and home ILS (migrated Vietnam trip) → fallback.
- If countries.json can't be loaded, destination currencies come from `trip_currencies.kind='destination'` instead.
- `unit` (C2) lives in the model and its cache: the main script calls `setUnit` from the rates (1,000 when
  homePerUnit < 0.01). Before any rate is known VND defaults to 1,000, everything else to 1.

### Rates (spec §2)
- `f10Parse(raw, home)`: v2 with `base === home` → its `rates`; object without `v` and with finite `USD/EUR/VND` → legacy
  (ILS per unit, VND /1000) only when home is ILS; else `null`.
- `f10Rates(opts)`: saved → else live (one er-api call per session, kept in memory `f10Mem`, shown "שערים חיים · לא נשמרו")
  → else (home ILS) `FX_DEFAULTS`. `opts.noLive` never touches the network (totals/boot).
- "שמור שערים" (`f10SaveRates`): `{v:2, base, rates, updatedAt, source:'live'|'manual'}`; home ILS also writes `USD`, `EUR`
  (ILS per 1) and `VND` (ILS per 1,000) in the same object. Goes through `SS.set` → the F06 viewer guard applies.
- `homePerUnit(code)` exists as a global (alias of `f10Hpu`); `ilsPerUnit` / `getFxRates` are kept unchanged for 'off'.

## 3. Places P1–P10 and DOM ids for QA

Chip rows keep their alpha.8 ids; content is rebuilt from `TRIPCUR.list` (max 5 chips + "עוד").

| # | Element ids | Notes |
|---|---|---|
| P1 | `#expenseCurRow .curchip[data-cur]`, selected = `.active` | default `f10Pick(planner:lastExpenseCurrency)` (per trip) else `local`. |
| P2 | `#expenseAmount` placeholder, `#expenseCalcRow` (hidden when picked = home), `#expenseCalcBtn` ("🔄 חשב לשקלים/לדולרים/לאירו/ל-<CODE>"), `#expenseCalcBox` | no rate → box shows "⚠️ אין שער ל-<code> – עדכנו שערים בתקציב" and the button is `disabled`. |
| P3 | header `#f10RatesHead` ("שערים בשקלים"), grid `#f10RateGrid`, inputs `#rate<CODE>` with `data-f10-rate="<CODE>"`, label `.info-label` "1 USD" / "1,000 VND", `#fxRatesInfo`, buttons `#fxAutoUpdate`, `#fxUpdate` | inputs show home per `unit[c]` units; missing rate → empty input, placeholder "אין שער". |
| P4 | `#budgetFxRow .curchip[data-cur]` (`.src` / `.dst`), `#fxAmount`, `#fxCalculate`, `#fxResult`, `#fxSave` | default local→home. |
| P5 | `#quickFxRow .curchip[data-cur]`, `#quickFxCalculate`, `#quickFxResult` (symbols), `#quickFxAddExpenseBtn` (target = home) | |
| P6 | `#globalFxBtn` text "<home sym> ⇄ <local sym>" | |
| P7 | `#qeCurRow .qe-chip[data-qe-cur]` (`.on`, `aria-pressed`), `#qeConv` ("≈ <home amount>"), `#qeSave` | VND chip label stays "VND" as alpha.8. |
| P8 | `#resCost` placeholder "עלות (₪ / ฿)" / "עלות ($)" | |
| P9 | `#budgetSpentAmt`, `#budgetAvailAmt`, `#budgetAvailSub`, `#catChips .trow.actual b`, `#expenseList .bd-amount`, `#budgetBurn` / `#homeBurn` / `#hv2WalletCard` (burnMarkup), `#personalSpentSummary`, `#dayCost`, `#qeRecent`, EDIT_MENU expense sheet title | all through `fmtHome`. |
| P10 | chat body `fx` = `{base, rates, home, local}` | |
| "עוד" | chip `#<rowId>More` (`#expenseCurRowMore`, `#budgetFxRowMore`, `#quickFxRowMore`, `#qeCurRowMore`), `data-f10-more`, `aria-label="עוד N מטבעות: …"`; sheet `#f10MoreSheet` (`hidden` attr), list `#f10MoreList` with chips `[data-f10-pick="<CODE>"]`, close `#f10MoreClose` / scrim `[data-f10-close]` / Escape | picking selects it in the 5th slot of the row it was opened from. |
| model | `window.__PT.tripcur`, `window.__ptF10.source()` ('none' / 'cache' / 'fallback' / 'db') | |

Expenses saved by the form, the quick card, "הוסף לתקציב", the quick FX "הוסף כהוצאה" path, the chat `add_expense` action
and reservation-linked expenses get `homeCurrency` (D4). Picked = home → no `originalAmount/originalCurrency` (also on edit,
where the old original fields are removed).

## 4. Spec ambiguities and how I resolved them

1. **"ILS output byte-identical"** — `fmtHome(n, opts, tight)` reproduces each alpha.8 template exactly (`tight` = the
   category tile's `…₪` with no space). Places that were not "stored amounts" (the converter result line, which uses codes)
   keep their alpha.8 text in P4; P5's result uses symbols as the spec says.
2. **Old ILS expense in a non-ILS trip without an ILS rate** — counted as 0 in totals and shown as "100 ₪ (₪ מקורי)" until a
   rate exists (never rewritten). With a rate: "27 $ (₪ מקורי)", rounded to whole units.
3. **Live defaults (§2)** — when nothing is saved and the device is online, the F10 boot hook calls `f10Rates()` once,
   which makes the single er-api request of the session (same URL as alpha.8's "עדכון אוטומטי"; no new origin) and keeps
   the result in memory. Totals (`renderBudget`, `calcDailyBurn`) call `f10Rates({noLive:true})` and never wait on the
   network. Offline: home ILS → `FX_DEFAULTS`; anything else → "אין שער" (acceptance 7).
4. **Rate rows for currencies with no rate** — shown empty with placeholder "אין שער"; saving with some rows empty saves the
   filled ones only (alpha.8 required all three).
5. **"שערים ב<home word>"** — ILS "שערים בשקלים", USD "בדולרים", EUR "באירו", other "ב-<CODE>".
6. **Units for unknown rates** — VND defaults to 1,000 (alpha.8 row); other weak currencies switch to 1,000 once a rate is
   known (e.g. KHR after a live fetch).
7. **Trip switch (acceptance 9)** — the F20 switcher reloads the page; TRIPCUR is per-trip cached and remembered picks are
   per-trip through the F02 namespace, so nothing extra was needed.
8. **Edit an expense whose currency is not in this trip's list** → the form opens in home currency with the home amount.
9. **`trips` read** — TRIPCUR adds a select on `trips(home_currency)`, `trip_countries`, `trip_currencies` once per open
   (+ on `online`). These are the spec's tables; no write.

## 5. Open questions

- `tests/qa_versions.json` still pins `3.0.0-alpha.8` (QA owns it); suites were run with `QA_EXPECTED_VERSION=3.0.0-alpha.9`.
- F20 `test_d01_network_reads_only_spec_tables` lists the tables allowed on the chooser / sheet; F10 adds `trip_currencies`
  (and a `trips.home_currency` select) inside a trip. If QA's network allow-list is strict, it needs `trip_currencies`.
- Placeholders "תקציב יעד (₪)" / "יעד אישי (₪)" / booking "מחיר כולל בש״ח" / quick FX hint "מופיע רק כשהיעד הוא ₪" are
  switched to the home currency only for non-ILS homes (they are not in the P-table; ILS trips unchanged).
- Excel export column headers "עלות מתוכננת (₪)" were left as is (backup format, not a display of a stored amount).

## 6. Dev smoke checks (not the QA suite)

Scratch scripts on the F04 fake backend (stubbed Supabase, 390 px): trips V/T/A/G/S as in spec §6.
- V (legacy rates): rows `VND ILS USD EUR`, P3 rows 1,000 VND = 0.14 / 1 USD = 3.6 / 1 EUR = 3.9; save → `{v:2,base:'ILS',
  rates:{VND:0.00014,USD:3.6,EUR:3.9},…,USD:3.6,EUR:3.9,VND:0.14}`; new expense has `homeCurrency:'ILS'`; "100 ₪".
- T: THB default everywhere, `₪ ⇄ ฿`, P3 rows THB/USD/EUR (no VND).
- A: `$ ⇄ AED`, "חשב לדולרים", totals in $, old expense "(₪ מקורי)"; no rates → AED "אין שער…" and calc disabled; with v2
  rates `AED 0.2723` → 100 AED = 27.23 $, saved `{amount:27.23, originalCurrency:'AED', homeCurrency:'USD'}`.
- G: local EUR, chips € ₪ $, `₪ ⇄ €`.  S: 5 chips + "עוד €", picking EUR → 5th slot, "עוד $"; VND row per 1,000.
- `document.documentElement.scrollWidth === 390` on the budget tab for all; no `pageerror`.
- Flag 'off' vs 4ca777b: identical DOM (budget, FX sheet, floating button, reservation cost) for V and T.
