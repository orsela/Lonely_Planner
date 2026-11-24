# OFFMAP · conversation 2 (viewer) · 3.0.0-alpha.21.1 · 24/11/2026 (first built as 20.3; renumbered after merging MORE-COMPACT, alpha.21.0)

CHANGE 2026-11-24 OFFMAP-VIEW-06: new file. What conversation 2 built, on top of the core (docs/OFFMAP_dev_notes_core.md).

## What it does
- `app/vendor/` holds Leaflet 1.9.4 (js + css) and protomaps-leaflet 5.1.0 (IIFE, global `protomapsL`), uploaded by Or (no network in the work environment). The `sourceMappingURL` lines were removed. Cached by `app/sw.js` (`SHELL_FILES`).
- `offmap.js` · section "the viewer": `tryDraw(el, {days, dayIndex, mode})`, `release()`, `viewFeatures()` (pure: line + points per map mode), `makeSource(store)` (a tile source object with `getZxy(z,x,y)`, passed as `url:` to `protomapsL.leafletLayer`; a missing tile = `undefined` = nothing drawn; a gzip tile is unpacked), `betaLevel()`, `viewEnabled()`, `needsOffline()`, `refreshView()`.
- The libraries load lazily, only when the trip is in `OFFMAP_TRIPS` and the flag is 'on' or the device beta is set. The first `tryDraw` returns false and starts the load + reads the saved-tile index; when ready it calls `host.redraw()` (= `drawMap()`), which then draws the saved map.
- One hook in `drawMap()` (app/index.html): before Google draws → `release()`; where the schematic map would draw → `tryDraw()` first. False = the old schematic map, exactly as alpha.20.2.
- Shown when: flag 'on' (or device beta) AND listed trip (never Vietnam) AND (offline OR Google not loaded OR beta 2) AND the open day has saved tiles (route / poi mode: any saved tile).
- Drawn: dashed route line, day points (open day red + label), waypoints, "מפה שמורה" badge, "© OpenStreetMap contributors · Protomaps". Zoom 6–16 (data to 14, overzoom above).

## Device beta (flag stays 'off' in the file)
Open the app with `#offmapbeta` (normal rules: offline / no Google), `#offmapbeta2` (also with a network, for a desk check), `#offmapbeta-off`. Stored in `localStorage['pt-offmap-beta']`.

## Tests
`tests/offmap/run.sh` 26/26 (3 new viewer tests; version checks → 20.3; page hook count 9 → 15). `node tests/offmap/view_smoke_run.mjs`: headless Chrome at 390px with fake MVT tiles: map mounts, 3 vector shapes, 9 canvases, badge + attribution (OK). Not measured: real Protomaps tiles, opening time, Hebrew/RTL labels, airplane mode on Or's phone.

## Not done / open
- The home map (second schematic map near line 9074) is not hooked; only the "מסלול ומפה" screen.
- Hebrew labels: protomaps-leaflet draws with canvas fonts; Romania names are Latin. RTL labels to check on the phone.
- A route change after a download needs a page reload to refresh the saved-tile index unless the download ran in the same session (`prepare()` calls `refreshView()`).
- Flag `OFFMAP_FEATURE` stays 'off'; turn on for Romania after the phone check (spec §7 items 2, 8, 9).
