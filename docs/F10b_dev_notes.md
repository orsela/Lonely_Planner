# F10b — dev notes (app 3.0.0-alpha.10)

<!-- CHANGE 2026-11-07 F10B-DOCS-03: new file (no previous version). -->

Contract: `docs/F10b_spec.md`. Scope: `app/index.html` only. Tags: F10B-FLAG-01, F10B-HEAD-01, F10B-GATE-01, F10B-VER-01/02,
F10B-UI-01 (sub-areas MORE-01, FXLINK-01, PANEL-01, PICK-01, WRITE-01, REMOVE-01). No existing function body changed.

## Where
| Piece | Location |
|---|---|
| `CURMGR_FEATURE` | flags script, after `CURRENCY_FEATURE` |
| `window.__ptF10b` {version, attach, api} | new head script right after the F10 head block |
| gate hook (client, withTimeout, timeoutMs, tripId, role) | after F10-GATE-01, cloud only |
| UI + writes | one IIFE at the end of the main script (`F10B_ON`), uses SS / getExpenses / f10Live / f10Mem / f10Rates / closeModal / switchPanel |

## DOM ids for QA
`#ptF10bRow` (+ `#ptF10bRowSub` "N מתוך 10"), `#ptF10bFxLink`, `#ptF10bPanel` (`#ptF10bBack`, `#ptF10bSub`, `#ptF10bBody`),
rows `.p10-row[data-f10b-code]`, ⋯ `[data-f10b-act="<CODE>"]`, `#ptF10bAdd`, `#ptF10bRO`, `#ptF10bOff`; sheet layer
`#ptF10bLayer` (scrim `[data-f10b-close]`, Escape): picker (`#ptF10bSearch`, `#ptF10bList`, options `[data-f10b-pick]`
`aria-pressed`, `#ptF10bConfirm`), `#ptF10bSwap` (`[data-f10b-out]`, `#ptF10bOutNote`, `#ptF10bSwapGo`), `#ptF10bRowSheet`
(`#ptF10bDoSwap`, `#ptF10bDoRemove`), `#ptF10bRemove` (`#ptF10bRemoveTxt`, `#ptF10bRemoveGo`).

## Behaviour notes
1. Writes use `.select()` so an RLS-filtered write (0 rows) is reported as "רק מנהל…", not as success.
2. Row list: DB on open (online), else synthesized from the cached TRIPCUR (bases = ILS/USD/EUR in it).
3. `kind` = 'destination' when the code is a trip country's currency, else 'added'; `sort` = max+1 for add and swap.
4. Rate (§6): live memory first; when shared rates exist without the code, the manager's device adds `rates.<CODE>` to the
   saved v2 object (a legacy ILS object is upgraded to v2 keeping its USD/EUR/VND fields).
5. Count on the "עוד" row = TRIPCUR list length until the screen has read the DB.

## Dev smoke (scratch, F10 harness)
S manager: row "6 מתוך 10"; add JPY (search "יפן") → `('JPY','added',6)`, TRIPCUR gains JPY; remove KHR with 3 KHR expenses →
warning "3 הוצאות נשמרו בריאל קמבודי…", one DELETE; swap THB→GBP via ⋯ → one row updated; scrollWidth 390; no page errors.
Viewer: no add, no ⋯.
