# F10 — Every trip converts in its own currencies · spec

<!-- CHANGE 2026-11-07 F10-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.9** (app only). **No migration, no Edge Function change**: `trips.home_currency`,
`trip_countries` and `trip_currencies` exist since F01/F04 and are already readable by every active member (RLS
`trip_role(trip_id) is not null`). Mockup approved by Or 2026-11-07: canvas
https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, **row 11** (4 artboards `F10_*`). Decisions D1–D7: project doc
`claude/Plan_Travel_F10_decisions.md`.

User value: a family that opens a trip to Thailand sees baht, not dong; a family whose home currency is the dollar sees
its budget in dollars. Until now every trip saw the Vietnam converter (₪ $ € ₫), and every amount was shekels.

Base: `main` = 4ca777b (3.0.0-alpha.8). Branch `f10`. Since there is no server part, `f10` merges to `main` after QA
and Or's phone check. The live project `vietnam-trip-2026` is never touched.

## 0. Decisions

| # | Decision |
|---|---|
| D1 (Or) | Scope: the app **reads** the trip's currencies and every currency place becomes dynamic. No currency-management screen (add / swap / cap) and no per-day country (F08). |
| D2 (Or) | Default ("local") currency = the currency of the **first trip country** (`trip_countries.sort`). The last chip the user picked is remembered on the device, per trip. |
| D3 (Or) | **Full support for `trips.home_currency`**. Every place that today means "shekels" means the trip's home currency. Vietnam stays ILS. |
| D4 (Or) | An expense stores `amount` in the home currency plus `originalAmount` / `originalCurrency` (as today). New expenses also store `homeCurrency`; an expense without it is ILS. |
| D5 (Or) | Mockup row 11 approved as drawn. |
| D6 (Or) | Chip order (RTL, first = rightmost): **local currencies, then home, then the rest**. |
| D7 (Or) | More than 5 currencies in a chip row: **5 chips + a "עוד" chip** that opens a list. |
| C1 (Claude) | Rates stay in the shared trip key `fxrates` (today `planner:fxrates` → `trip_kv`), new format v2 (§2), with a reader for the old `{USD,EUR,VND}` object. |
| C2 (Claude) | A "weak" currency is shown per **1,000 units** when one unit is worth less than 0.01 of the home currency. |
| C3 (Claude) | Flag `CURRENCY_FEATURE='on'|'off'` next to `REQUEST_FEATURE`. `'off'` = exactly alpha.8 (Vietnam converter). |

Out of scope: adding/removing currencies in the app (F10b), the missing-currency reminder (F11), per-day country/time
zone (F08), changing a trip's home currency after creation, server-side rate fetching.

## 1. The trip's currency model (`TRIPCUR`)

Built when a trip opens (same moment the app loads trip name/members), from:
- `trips.home_currency` (ISO-4217),
- `trip_countries` (`country_code`, `sort`) → each country's `currency` from `countries.json`,
- `trip_currencies` (`currency_code`, `kind`, `sort`),
- symbols and Hebrew names from `currencies.json` (fallback symbol = the code).

Shape: `{home:'ILS', local:'THB', list:['THB','ILS','USD','EUR'], sym:{THB:'฿',…}, he:{…}, unit:{VND:1000,…}}`.

- **`local`** = currency of the first trip country that has one. If that currency is also a base (Greece → EUR) it is
  still `local`. No countries → `local = home`.
- **`list` order (D6):** (1) destination currencies in trip-country order, deduped (this includes a base currency when a
  country uses it, e.g. EUR for Greece); (2) `home`; (3) the other base currencies in `trip_currencies.sort` order;
  (4) `added` currencies in `sort` order. No duplicates. Only currencies present in `trip_currencies` or `home` appear,
  except a destination currency of a country that `trip_currencies` lacks (cap reached) — it is skipped.
- **Cache / offline:** the built object is saved device-only per trip (`localStorage` with the existing per-trip
  prefix, key `…:tripcur`) and used immediately on the next open, then refreshed from the DB when online.
  `countries.json` / `currencies.json` are fetched once when online and the derived symbols/names are kept in that cache —
  they are **not** added to the service-worker precache.
- **Fallback** (no cache and no network, or the trip is the migrated Vietnam trip without rows): `home='ILS'`,
  `list=['VND','ILS','USD','EUR']`, `local='VND'` — i.e. today's behaviour.
- Exposed for tests as `window.__PT.tripcur` (read-only copy).

## 2. Rates (`fxrates`, shared through `SS` like today)

- **v2 format:** `{"v":2,"base":"<home>","rates":{"<CODE>":<home per 1 unit>,…},"updatedAt":<ms>,"source":"live"|"manual"}`.
- **Reading:** v2 whose `base` = current home → used. Old object `{USD,EUR,VND}` (ILS per unit, VND per 1,000) → read as
  v2 with base ILS when home is ILS; ignored otherwise. Anything else → treated as "no saved rates".
- **Writing ("שמור שערים", editors/managers only — the F06 viewer guard on `SS.set` already blocks viewers):** v2 for all
  `list` currencies. When home is ILS the legacy top-level `USD`, `EUR`, `VND` (VND per 1,000) fields are written **in the
  same object** when those codes have rates, so a device on alpha.8 or with the flag `'off'` keeps working.
- **Live fetch** ("עדכון אוטומטי"): one call to `https://open.er-api.com/v6/latest/USD` (unchanged URL, 6 s timeout);
  `homePerUnit(c) = usd[home] / usd[c]`. Fills the inputs; saving shares them, as today.
- **Defaults:** when no saved rates exist and the device is online, the app fetches live rates once per session and uses
  them in memory (shown as "שערים חיים · לא נשמרו"). Offline with no saved rates: home ILS → the existing `FX_DEFAULTS`
  for USD/EUR/VND; every other currency without a rate shows "אין שער" and conversion to/from it is disabled with the
  message "אין שער ל-<code> – עדכנו שערים בתקציב".
- `ilsPerUnit(rates,code)` is replaced by `homePerUnit(code)` (ILS-home trips give identical numbers to alpha.8).
- **Unit (C2):** `unit[c] = 1000` when `homePerUnit(c) < 0.01`, else 1. Rate rows and rate texts read "1,000 VND = …";
  amounts typed by users are always whole units (no ×1000 on input).

## 3. The places that change (all currently fixed to ₪ / VND)

All chip rows are built from `TRIPCUR.list`; a row shows at most 5 chips, then a "עוד" chip (dashed, label "עוד" and the
hidden symbols underneath, `aria-label="עוד N מטבעות: …"`) that opens a small sheet listing the rest as the same chips;
picking one closes the sheet and shows that currency selected in the 5th slot of the row until the row is rebuilt.

| # | Place | alpha.8 | alpha.9 |
|---|---|---|---|
| P1 | Add-expense "שולם ב־" chips | ₪ $ € ₫ | `list`; default = last picked for this trip, else `local` |
| P2 | Add-expense amount placeholder + calc button | "סכום בש״ח" / "חשב לשקלים" | "סכום ב-<sym of picked>" / "חשב ל<home word>" (ILS שקלים, USD דולרים, EUR אירו, other: "חשב ל-<CODE>"); button hidden when picked = home |
| P3 | Budget "מחשבון המרה" rate rows | 1 USD, 1 EUR, 1000 VND (in ₪) | one row per `list` currency except home, in `list` order, label with `unit[c]`; header "שערים ב<home word>" |
| P4 | Budget converter chips | ₪ $ € ₫, from VND to ILS | `list`; default from `local` to `home` (from = to → from the next currency) |
| P5 | Quick FX sheet chips + result | same as P4 | same as P4; result text uses symbols; "הוספה כהוצאה" when target = home |
| P6 | Floating FX button | "₪ ⇄ $" | "<home sym> ⇄ <local sym>"; when local = home: "<home sym> ⇄ <first other in list>" |
| P7 | Quick expense ("＋ הוצאה מהירה") chips + preview | VND ₪ $, default VND | `list` (pill style, same 5 + "עוד" rule); default last picked for this trip, else `local`; preview "≈ <home amount>" |
| P8 | Reservation cost placeholder | "עלות (₪ / ₫)" | "עלות (<home sym> / <local sym>)" (just home when equal) |
| P9 | Every display of a stored `amount` (budget totals, category bars, expense list, daily burn, home budget widgets, reservation totals, expense detail card) | "… ₪" / "ש״ח" | formatted by one helper `fmtHome(n)` with the home symbol (ILS output identical to alpha.8) |
| P10 | Chat context `fx` | `{USD,EUR,VND}` | `{base, rates}` (v2) plus `home`, `local` |

Not changed: seed/itinerary text that happens to mention ש״ח (user content), the Vietnam `SEED_DATA`, F04 wizard.

Device-remembered picks become per trip: `planner:lastExpenseCurrency` and `planner:qe:cur` keep their names but live under
the per-trip prefix (they are already in `DEVICE_ONLY`). A remembered code that is not in `list` falls back to `local`.

## 4. Expenses (D4)

- New/edited expense: `amount` (home), `homeCurrency` (= home), and when picked ≠ home also `originalAmount`,
  `originalCurrency`. Picked = home → no original fields (as today for ILS).
- Old expenses (no `homeCurrency`) are ILS. In a trip whose home is not ILS such an expense is shown converted with the
  current rate and marked "(₪ מקורי)"; it is never rewritten silently.

## 5. Flags, versions, code rules

- `const CURRENCY_FEATURE='on';` with the usual comment. `'off'` → every F10 line is a no-op and the app is alpha.8.
- `PT_VERSION` and `APP_VERSION` → `'3.0.0-alpha.9'` with `CHANGE 2026-11-xx F10-VER-0N` comments; every changed line
  carries `CHANGE … F10-<AREA>-NN: was …` per the project rule. CHANGELOG entry.
- No new network origins (CSP unchanged); `countries.json` / `currencies.json` are same-origin.

## 6. Acceptance criteria (automated unless marked 📱)

Fixtures: build the trips in the QA harness / Playwright with stubbed Supabase responses — **V** Vietnam (ILS; VN; ILS USD
EUR VND), **T** Thailand (ILS; TH; + THB), **A** UAE (USD; AE; USD ILS EUR AED), **G** Greece (ILS; GR; bases only),
**S** SE-Asia (ILS; TH, VN, KH; + THB VND KHR = 6).

1. **V regression:** with saved legacy rates every screen, number and text in P1–P10 equals alpha.8 except chip order
   (VND first, D6). Totals of the existing expense fixture identical.
2. **T:** P1/P4/P5/P7 default to THB; P6 reads "₪ ⇄ ฿"; P3 rows THB, USD, EUR (no VND anywhere in the budget, FX sheet or
   floating button).
3. **A:** every P9 amount shows "$", none shows ₪ (except an ILS chip and the "(₪ מקורי)" marker); P2 button "חשב
   לדולרים"; an AED expense saves `amount` in USD + `homeCurrency:'USD'` + `originalCurrency:'AED'`.
4. **G:** `local` = EUR; chip order € ₪ $; P6 "₪ ⇄ €".
5. **S:** chip rows show 5 chips + "עוד"; "עוד" lists EUR; picking it selects it in the 5th slot; VND and KHR rate rows
   read per 1,000.
6. **Rates:** saving in V writes v2 **and** legacy USD/EUR/VND; an alpha.8 reader (`getFxRates` of alpha.8) reads the saved
   object correctly. Live fetch computes `homePerUnit` from a stubbed er-api payload for A (AED ≈ 0.2723 USD).
7. **Missing rate:** offline, no saved rates, trip A → AED chip shows "אין שער" message and conversion is disabled; no
   exception.
8. **Offline:** after one online open, reload offline → `TRIPCUR` from cache, same chips and symbols.
9. **Isolation:** switching from trip T to trip A (F20 switcher) rebuilds every row; remembered picks are per trip.
10. **Viewer:** a viewer can convert but "שמור שערים" is blocked by the F06 guard ("צפייה בלבד").
11. **Flag off:** `CURRENCY_FEATURE='off'` → DOM of the budget tab, FX sheet and quick expense equals alpha.8 for V and T.
12. **390px:** no horizontal scroll on budget tab, FX sheet and "עוד" sheet; every chip ≥44px tall; RTL correct.
13. **No server change:** migrations folder and `supabase/functions` untouched; Supabase advisors unchanged.
14. 📱 Or's Android phone: trip "איחוד האמירויות · ינואר 2027" shows dollars and AED; the F02 Vietnam test trip looks as
    before.
