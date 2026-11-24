# OFFMAP · core (conversation 1) · 3.0.0-alpha.19

Branch `offmap-core` (from `origin/main` 8300f88, alpha.18.13). CHANGE 2026-11-24 OFFMAP-DOC-01: new file.

## What exists
`app/js/offmap.js` → `window.__ptOM` (Node: `module.exports`). Nothing in `index.html` calls it; the page only loads it and declares `OFFMAP_FEATURE='off'`. `drawMap()` is untouched.

## Contract for conversation 2 (display + connection)
- `__ptOM.active(tripId)` → true only for flag `'on'` + trip in `OFFMAP_TRIPS` (in offmap.js) + not Vietnam. `configure({feature, trips, key})` can override (tests / mount).
- Store: `createIdbStore(tripId)` (db `pt-<trip>-offmap`; stores `tiles`, `index`, `meta`); `loadTile(store,z,x,y)` → ArrayBuffer of MVT bytes (EMPTY buffer when the tile is missing: a valid empty tile, no map error); `registerProtocol(maplibregl, store)` registers `offmap://{z}/{x}/{y}` (MapLibre v4+ promise form and the older callback form).
- Plan: `planTrip(tripData)` → per-day tiles by zoom + shared `tiles` Map (`days[]`, `base`); `dayCoverage(plan, index, i)` for a status line; `buildQueue` statuses per day: `selected|reduced|waiting|later|past|none`.
- Run: `prepare({days, store, cur|now, cap, storage: await deviceStorage(), onProgress, signal})` → `{status, reason, downloaded, failed, bytes, remaining, plan, queue, used, budget}`; reasons: `no_key|rate_limited|forbidden|auth|network|cap|budget|aborted`. A re-run resumes (stored tiles are skipped). The key is never in a result.
- Clean-up happens inside `prepare` (tiles whose days all passed, tiles the route no longer needs); leaving a trip → `store.destroy()`.

## Decisions made here (not in the spec text)
1. Zooms: background 4–7 over the whole trip box (+30 km), per day 8–14 (z8–10 25 km, z11–12 8 km, z13–14 3 km).
2. A leg longer than 150 km (flight / long transfer) is not a corridor: only its two points get tiles.
3. "Up to 3 days ahead" = the current day + 3 more. Before the trip: day 0 is "current". After the last day: nothing.
4. Margin = max(50 MB, 10% of the FREE space). Budget = min(cap − used, free − margin).
5. If today + tomorrow do not fit in the budget they are still queued (never sacrificed); the engine stops when the budget ends and reports `short: true` in the queue.
6. Coordinates are checked strictly: '', null, text are not points (the app's own `valid('', '')` returns true for 0,0; chat-added points are saved with `lat:null`).
7. Cap counts stored (gzip) bytes; the default per-zoom estimates are decoded sizes from the 24/11 probe (conservative) until real averages are learned (≥3 tiles per zoom).
8. Not done on purpose: key in repo, mount call, drawMap hook, screens, the end-of-day trigger, Cache Storage of the viewer library and glyphs.

## Tests
`tests/offmap/run.sh` (Node, 20 tests). Browser check done by hand in headless Chrome: real IndexedDB + the engine with a fake fetch; flag off = same errors and same visible text as main.
