# F24 – flight and hotel search from the trip (stage 1: smart links) · developer notes

<!-- CHANGE 2026-11-14 F24-A1-04: new file (no previous version). Conversation 1 of 3. -->
<!-- CHANGE 2026-11-14 F24-A2-06: what changed from the previous version: conversation 2 done (state table, "Conversation 2" section, "Not done" updated). -->

Spec: project doc `claude/Plan_Travel_F24_spec.md` (approved 2026-11-13). Branch `f24`, based on `main` dc9503f (F08 stage B, alpha.13.1).
Work is split like F08, one conversation = one commit:

| # | Scope | State |
|---|---|---|
| 1 | `app/js/f24.js` data + link builders (C1–C8 pure part), `app/airports.json`, Node tests | **done 2026-11-14** |
| 2 | Day cards `FB_DayFlight` / `FB_DayHotel`, origin sheet `FB_Origin`, offline (C9), wiring into `app/index.html` (script tag, `TRAVELSEARCH_FEATURE`, version alpha.14), `sw.js` (`js/f24.js`, `airports.json`), one 390 px browser check, HTML-equality check of a booked day (AC3) | **done 2026-11-14** (link formats not opened: no network here) |
| 3 | Chat (C8): check R1 first (`chat-assistant` on `plan-travel`); card `FB_Chat`; restore the `/request/` hero line (F23-REQ-19); merge; Or's phone check | open |

## Conversation 1 – what exists
- `app/js/f24.js` (not loaded by the app yet): `f24FlightSearch(i,{origin?})`, `f24LodgingSearch(i)`, `f24ChatSearch(args)` return the
  full card data (places, dates, adults, the two links) or `null` when no card applies; `f24AirportSearch(q, recents)` and
  `f24PushRecent` serve the origin sheet; four link builders. It reads the trip through `f24Configure()` and F08's api.
- `app/airports.json`: 289 airports `{iata, he, en, cc, alt?}`, about one per city.
- `tests/f24/run.sh`: 9 Node tests, all green (AC1–AC6, AC8 at the data level, R2, the airports file).

## Decisions taken beyond the spec (for Or's review)
1. **airports.json was written by hand, not generated from a dataset.** The work environment cannot download the public
   dataset (network allow-list). IATA codes are plain facts; the list covers the common destinations from Israel. A missing
   city still works: Google Flights gets the city name, Skyscanner the country code (C7).
2. **First flight = TLV** unless the trip already has days abroad before it and the flight's origin is another country
   (a trip that starts by land); then the origin is F08's `from`.
3. **"Booked" lodging** also covers a day whose `isBooked` field is set (hotel reservations write it since v1.8.0), in addition
   to hotel reservation records linked to the day or whose check-in / check-out range holds it.
4. **One-way wording for Google Flights:** "… on 2027-05-17 one way, 5 adults" (the spec gives only the round-trip sentence).
5. Hotel links name the city and the country ("Batumi, Georgia") to avoid same-name cities.
6. A lodging day with no city uses the country alone; with neither, no card.
7. Chat dates are accepted as `yyyy-mm-dd` or `dd/mm/yyyy`; a date without a year counts as missing (the chat asks).

## Conversation 2 – what was added
- `app/js/f24.js` browser part: `attach` (client / trip id / timeout helper from the gate, for the active-member count), `mount` (styles, `airports.json` and
  `countries.json` fetch, online / offline repaint), `paintDay`, `setReservations`, and the pure markup builders `f24FlightCardHtml`, `f24HotelCardHtml`,
  `f24OriginSheetHtml` (Node-tested). Last 3 origins: `localStorage['pt-f24-recent-<trip>']` (the app namespaces localStorage per trip itself).
- `app/index.html` (all marked F24-…): flag `TRAVELSEARCH_FEATURE`, script tag after f08.js, gate hook F24-GATE-01 (attach), main-script hook F24-MOUNT-01
  (wrapper of `renderDayReservations`: after the original draws, the card is drawn under it or removed), versions alpha.14 (`PT_VERSION`, `APP_VERSION`).
- `app/sw.js`: `js/f24.js` and `airports.json` added to `SHELL_FILES`.
- Tests: `tests/f24/run.sh` 16 Node; `tests/f24/run_browser.sh` one pass in the real app (390 px): AC1, AC2, AC3 (booked day HTML equals the flag-off page), AC4, AC5, AC7, AC8, AC9.

## Decisions taken in conversation 2 (for Or's review)
1. **Where the card shows:** inside the day card (right after "הזמנות מקושרות ליום זה"), as in the mockup. That card is visible in the "ציר זמן" view of
   "מסלול ומפה"; the map view hides the day card (existing CSS), so there the F24 card is hidden too. Moving it above the map view is a one-line change if Or wants it.
2. **Member count:** F06 keeps its member list private, so F24 reads `trip_members` (status active) itself, at most once a minute while a card is on screen, and caches
   the number per trip. No cloud / first load before the answer: 1 traveler. A trip in local-only mode: 1.
3. **One-way chip:** a one-way flight card says "כיוון אחד" instead of "הלוך" (the mockup shows only the round-trip case).
4. **Offline line:** "אין חיבור – אפשר לחפש כשהרשת תחזור." (the wording of the F10b / F06 offline lines; the F10b_Offline artboard was not opened, LEAN rule 5).
5. **Origin change lives in memory:** it is kept for that day while the app is open and the card is redrawn; a reload goes back to the default (TLV or the previous city).
   The device list of the last 3 origins is what persists.

## Not done / not checked
- **Link formats were not opened in a real browser** (C7 asks for one manual check) – no outside network in this environment either (conversation 1 and 2).
  To do on Or's phone in conversation 3: one Google Flights, Skyscanner, Booking and Google Hotels link each; record the result here.
- Phone check (one flight day, one lodging day) – conversation 3. Chat (C8) and the `/request/` hero line – conversation 3.
- Not run: the full F10 / F10b browser suites (LEAN rule 5); `tests/qa_versions.json` still lists old versions (updated in the QA round before v3.0.0).
