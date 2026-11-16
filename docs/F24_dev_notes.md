# F24 – flight and hotel search from the trip (stage 1: smart links) · developer notes

<!-- CHANGE 2026-11-14 F24-A1-04: new file (no previous version). Conversation 1 of 3. -->
<!-- CHANGE 2026-11-14 F24-A2-06: what changed from the previous version: conversation 2 done (state table, "Conversation 2" section, "Not done" updated). -->

Spec: project doc `claude/Plan_Travel_F24_spec.md` (approved 2026-11-13). Branch `f24`, based on `main` dc9503f (F08 stage B, alpha.13.1).
Work is split like F08, one conversation = one commit:

| # | Scope | State |
|---|---|---|
| 1 | `app/js/f24.js` data + link builders (C1–C8 pure part), `app/airports.json`, Node tests | **done 2026-11-14** |
| 2 | Day cards `FB_DayFlight` / `FB_DayHotel`, origin sheet `FB_Origin`, offline (C9), wiring into `app/index.html` (script tag, `TRAVELSEARCH_FEATURE`, version alpha.14), `sw.js` (`js/f24.js`, `airports.json`), one 390 px browser check, HTML-equality check of a booked day (AC3) | **done 2026-11-14** (link formats not opened: no network here) |
| 3 | Chat (C8): check R1 first (`chat-assistant` on `plan-travel`); card `FB_Chat`; restore the `/request/` hero line (F23-REQ-19); merge; Or's phone check | **partly done 2026-11-15:** R1 checked (no `chat-assistant` on `plan-travel`), hero line restored, merged; chat part (C8, `FB_Chat`) and the phone check are open |

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
1. **Where the card shows (changed 2026-11-15 by Or, F24-A3-01):** right after the route screen's weather card (`#routeDayWeather`), under the day strip, so it shows in both the map and the timeline view. Conversation 2 had put it inside the day card, which the map view (the default) hides.
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

## Conversation 3 – what was done (2026-11-15)
- **R1 checked (Supabase `plan-travel`, edge functions):** invite-manager, create-trip, approve-member, join-trip, manage-members, request-trip, request-trip-f23. **There is no
  `chat-assistant`.** Per the spec, the chat part (C8 tool `search_links`, card `FB_Chat`) is **not built**: it needs a new server function (Anthropic key already in the
  project, a Gemini key only for maps / photos) and belongs with F14 (the smart chat). The day cards (C1–C7, C9) are complete and independent of it.
  `app/js/f24.js` already has `f24ChatSearch(args)` (pure, tested) ready for F14 to call; the card markup can reuse `f24FlightCardHtml` / `f24HotelCardHtml`.
- `/request/` hero line restored in Hebrew and English (F24-A3-03); `tests/f23/request_page_test.mjs` updated (page 8/8).
- Card moved under the day strip's weather card (F24-A3-01).
- Merged `f24` into `main` (fast-forward). Flag `TRAVELSEARCH_FEATURE='off'` returns alpha.13.1 behaviour.
## Open for Or
- Phone check: one flight day, one lodging day; open one link of each of the four sites and tell me if any lands on an empty search (formats not checked from here).
- Decision: build the chat tool now (needs a new `chat-assistant` function on `plan-travel`) or leave it to F14.

## Phone test round, 2026-11-16 (Or, Android) — F14, F24, F08 stage B
Versions on the way: alpha.15.4 (chat bold), 16.1, 16.2, 16.3, 16.4, 16.5. Each CHANGE comment in the code says what moved from the version before it.
- **F14 chat:** questions about the trip — passed. "Flight home" with no date — passed after F14-FIX-02/03 and chat-assistant v2 (plain text, no `**`; no date = last day of the trip). Hotel with no date and the FB_Chat card against the mockup — **not reported**.
- **F24 flight card:** day card, origin sheet ("שינוי"), Skyscanner link, lodging card on the first night — passed. Day 7 was a wrong test day (rule C2), not a bug.
- **Google Flights, day 9 (return, sides are only a country):** opened empty (16.1 fixed "from <country> to <country>"), then generic from the phone location (16.2: last day → TLV passed), then "from Haifa", round trip (16.4: a country-only side gets the country's main airport, link always has both sides + one way). **16.3 destination "שינוי" — passed.** **16.4 — phone check 13 reported "failed" 3 minutes after deploy, most likely a cached build; not yet re-checked.** Three times the phone stayed on an old build (Service Worker); 16.5 shows the version in "עוד".
- **F08 stage B:** items 3 (places in the day's country) and 4 (flight time in the origin clock) passed. Item 1 (currency of the day's country) did not add UZS to the sheet — by design: only currencies in the trip list, and "here" depends on today's date; checked in Node only. Item 2 (weather by capital) cannot be checked until about 2 weeks before the trip.
- **Backlog from the round:** suggest adding the day's country currency when it is missing; add points of interest intuitively and through the chat (needs reversing F14 decision D2); `VERSION` in f24.js still says alpha.14; browser tests of F14/F24 pin old version strings (QA round); the Skyscanner link with a country-only side was meaningless (16.4 now fills an airport); delete the temporary functions `chat-assistant-f14` and `request-trip-f23` in the Supabase dashboard.
