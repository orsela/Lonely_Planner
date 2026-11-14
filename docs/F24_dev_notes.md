# F24 – flight and hotel search from the trip (stage 1: smart links) · developer notes

<!-- CHANGE 2026-11-14 F24-A1-04: new file (no previous version). Conversation 1 of 3. -->

Spec: project doc `claude/Plan_Travel_F24_spec.md` (approved 2026-11-13). Branch `f24`, based on `main` dc9503f (F08 stage B, alpha.13.1).
Work is split like F08, one conversation = one commit:

| # | Scope | State |
|---|---|---|
| 1 | `app/js/f24.js` data + link builders (C1–C8 pure part), `app/airports.json`, Node tests | **done 2026-11-14** |
| 2 | Day cards `FB_DayFlight` / `FB_DayHotel`, origin sheet `FB_Origin`, offline (C9), wiring into `app/index.html` (script tag, `TRAVELSEARCH_FEATURE`, version alpha.14), `sw.js` (`js/f24.js`, `airports.json`), one 390 px browser check, HTML-equality check of a booked day (AC3) | open |
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

## Not done / not checked
- **Link formats were not opened in a real browser** (C7 asks for one manual check) – no outside network here. To do in conversation 2
  or on Or's phone: one Google Flights, Skyscanner, Booking and Google Hotels link each, and record the result here.
- No screens, no flag in the app, no version bump, nothing in `sw.js`.
