// Lonely Planner F24 · conversation 1 · Node tests of app/js/f24.js (data + link builders) · version 3.0.0-alpha.14
// CHANGE 2026-11-14 F24-A1-02: new file (no previous version). Covers the spec's acceptance criteria 1–6 and 8 at the data level
//   (what a card would show and where its buttons lead), the link builders (9) and app/airports.json.
// Run: tests/f24/run.sh   (no browser, no network)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const F8 = req("../../app/js/f08.js"), F = req("../../app/js/f24.js");
const AIRPORTS = JSON.parse(readFileSync(new URL("../../app/airports.json", import.meta.url), "utf8"));
const COUNTRIES = {
  IL: { en: "Israel", he: "ישראל", tz: ["Asia/Jerusalem"] }, GE: { en: "Georgia", he: "גאורגיה", tz: ["Asia/Tbilisi"] },
  TH: { en: "Thailand", he: "תאילנד", tz: ["Asia/Bangkok"] }, JP: { en: "Japan", he: "יפן", tz: ["Asia/Tokyo"] },
  CY: { en: "Cyprus", he: "קפריסין", tz: ["Asia/Nicosia"] },
};
let days = [], res = [], members = 5, feature = "on";
function setup(d, o = {}) {
  days = d; res = o.res || []; members = o.members === undefined ? 5 : o.members; feature = o.feature || "on";
  F8.f08Configure({ days: () => days, countries: () => COUNTRIES, tripCountries: () => [], homeCurrency: () => "ILS", deviceTz: () => "Asia/Jerusalem", landing: () => null, feature: () => "on" });
  F.f24Configure({ f08: F8, days: () => days, reservations: () => res, members: () => members, airports: () => AIRPORTS, countries: () => COUNTRIES, feature: () => feature });
}
const land = (date, country, city) => ({ date, country, city, tz: COUNTRIES[country].tz[0] });
const side = (c, city) => ({ country: c, tz: COUNTRIES[c].tz[0], city });
const fl = (date, from, to, fromCity, toCity) => ({ date, isFlight: true, flightFrom: side(from, fromCity), flightTo: side(to, toCity) });

// Georgia: TLV → Tbilisi 03/05, Tbilisi ×3, Batumi ×10, Batumi → home 17/05
function georgia() {
  const d = [fl("03/05/2027", "IL", "GE", "", "טביליסי")];
  for (let k = 4; k <= 6; k++) d.push(land(`0${k}/05/2027`, "GE", "טביליסי"));
  for (let k = 7; k <= 16; k++) d.push(land(`${String(k).padStart(2, "0")}/05/2027`, "GE", "Batumi"));
  d.push(fl("17/05/2027", "GE", "IL", "Batumi", ""));
  return d;
}

test("airports.json · unique codes, complete rows, TLV and ETM present", () => {
  const seen = new Set();
  for (const a of AIRPORTS) {
    assert.match(a.iata, /^[A-Z]{3}$/); assert.match(a.cc, /^[A-Z]{2}$/); assert.ok(a.he && a.en, a.iata);
    assert.ok(!seen.has(a.iata), "duplicate " + a.iata); seen.add(a.iata);
  }
  assert.ok(seen.has("TLV") && seen.has("ETM") && AIRPORTS.length > 200);
});

test("AC1 · first flight day without a reservation: TLV → destination, round trip, member count, both links", () => {
  setup(georgia());
  const s = F.f24FlightSearch(0);
  assert.equal(s.from.iata, "TLV"); assert.equal(s.to.iata, "TBS"); assert.equal(s.date, "2027-05-03");
  assert.equal(s.returnDate, "2027-05-17"); assert.equal(s.roundTrip, true); assert.equal(s.adults, 5);
  assert.equal(s.links.googleFlights, "https://www.google.com/travel/flights?q=" + encodeURIComponent("Flights from TLV to TBS on 2027-05-03 through 2027-05-17, 5 adults"));
  assert.equal(s.links.skyscanner, "https://www.skyscanner.net/transport/flights/tlv/tbs/270503/270517/?adultsv2=5");
  assert.equal(F.f24PlaceLabel(s.to), "TBS · טביליסי");
});

test("AC2 · changing the origin applies to this search only", () => {
  setup(georgia());
  const s = F.f24FlightSearch(0, { origin: "LCA" });
  assert.equal(s.from.iata, "LCA"); assert.match(s.links.skyscanner, /\/flights\/lca\/tbs\//); assert.match(decodeURIComponent(s.links.googleFlights), /from LCA to TBS/);
  assert.equal(s.roundTrip, false);                       // a return to Israel is not a round trip from Larnaca
  assert.equal(F.f24FlightSearch(0).from.iata, "TLV");    // the next search is TLV again
  const r = F.f24AirportSearch("", ["LCA", "TLV", "ATH", "XXX"]);
  assert.deepEqual(r.pinned.map(a => a.iata), ["TLV", "ETM"]); assert.deepEqual(r.recent.map(a => a.iata), ["LCA", "ATH"]);
  assert.equal(F.f24AirportSearch("לרנ").results[0].iata, "LCA"); assert.equal(F.f24AirportSearch("larn").results[0].iata, "LCA");
  assert.ok(F.f24AirportSearch("קפריסין").results.some(a => a.iata === "PFO"));
  assert.deepEqual(F.f24PushRecent(["ATH", "LCA", "ROM"], "lca"), ["LCA", "ATH", "ROM"]);
  assert.deepEqual(F.f24PushRecent(["A1", "ATH", "LCA", "FCO"], "MAD"), ["MAD", "ATH", "LCA"]);   // a broken entry is dropped, at most 3 kept
});

test("AC3 · a day with a flight / lodging reservation gets no search", () => {
  setup(georgia(), { res: [{ type: "flight", linkedDayStart: 0 }] });
  assert.equal(F.f24FlightSearch(0), null); assert.ok(F.f24FlightSearch(14));
  setup(georgia(), { res: [{ type: "flight", datetime: "17/5 21:40" }] });
  assert.equal(F.f24FlightSearch(14), null); assert.ok(F.f24FlightSearch(0));
  setup(georgia(), { res: [{ type: "hotel", checkin: "2027-05-04", checkout: "2027-05-07" }] });
  assert.equal(F.f24LodgingSearch(1), null); assert.ok(F.f24LodgingSearch(4));
  const d = georgia(); d[1].isBooked = true; d[2].isBooked = true; d[3].isBooked = true; setup(d);
  assert.equal(F.f24LodgingSearch(1), null); assert.equal(F.f24LodgingSearch(2), null);
  setup(georgia()); assert.equal(F.f24LodgingSearch(0), null); assert.equal(F.f24FlightSearch(1), null);   // wrong kind of day
});

test("AC4 · lodging run: card on the first night only, nights and checkout right, links prefilled", () => {
  setup(georgia());
  const a = F.f24LodgingSearch(1), b = F.f24LodgingSearch(4);
  assert.deepEqual([a.city, a.checkin, a.checkout, a.nights, a.adults], ["Tbilisi", "2027-05-04", "2027-05-07", 3, 5]);
  assert.deepEqual([b.city, b.checkin, b.checkout, b.nights], ["Batumi", "2027-05-07", "2027-05-17", 10]);
  assert.equal(F.f24LodgingSearch(2), null); assert.equal(F.f24LodgingSearch(5), null);
  assert.equal(a.links.booking, "https://www.booking.com/searchresults.html?ss=" + encodeURIComponent("Tbilisi, Georgia") + "&checkin=2027-05-04&checkout=2027-05-07&group_adults=5&no_rooms=1");
  assert.equal(a.links.googleHotels, "https://www.google.com/travel/hotels?q=" + encodeURIComponent("hotels in Tbilisi, Georgia 2027-05-04 to 2027-05-07"));
  // a booked night in the middle splits the run: 07–09 and 11–16
  setup(georgia(), { res: [{ type: "hotel", linkedDays: [7] }] });
  assert.deepEqual([F.f24LodgingSearch(4).nights, F.f24LodgingSearch(4).checkout], [3, "2027-05-10"]);
  assert.equal(F.f24LodgingSearch(7), null); assert.deepEqual([F.f24LodgingSearch(8).nights, F.f24LodgingSearch(8).checkin], [6, "2027-05-11"]);
});

test("AC5 · mid-trip flight leaves from the previous city; the return lands at TLV; round trip only on the first flight", () => {
  const d = [fl("11/01/2027", "IL", "TH", "", "Bangkok"), land("12/01/2027", "TH", "בנגקוק"), land("13/01/2027", "TH", "בנגקוק"),
    { date: "14/01/2027", isFlight: true }, land("15/01/2027", "JP", "Tokyo"), fl("16/01/2027", "JP", "IL", "Tokyo", "")];
  setup(d, { members: 0 });
  const mid = F.f24FlightSearch(3), back = F.f24FlightSearch(5), out = F.f24FlightSearch(0);
  assert.deepEqual([mid.from.iata, mid.to.iata, mid.roundTrip, mid.adults], ["BKK", "NRT", false, 1]);
  assert.match(mid.links.skyscanner, /\/flights\/bkk\/nrt\/270114\/\?adultsv2=1$/); assert.match(decodeURIComponent(mid.links.googleFlights), /on 2027-01-14 one way, 1 adult$/);
  assert.deepEqual([back.from.iata, back.to.iata, back.roundTrip], ["NRT", "TLV", false]);
  assert.deepEqual([out.from.iata, out.to.iata, out.returnDate], ["TLV", "BKK", "2027-01-16"]);
  // a destination without an airport in the list: Google Flights names the city, Skyscanner gets the country code
  setup([fl("03/05/2027", "IL", "GE", "", "Mestia"), land("04/05/2027", "GE", "Mestia")]);
  const m = F.f24FlightSearch(0);
  assert.equal(m.to.iata, ""); assert.match(decodeURIComponent(m.links.googleFlights), /from TLV to Mestia, Georgia on 2027-05-03 one way/); assert.match(m.links.skyscanner, /\/flights\/tlv\/ge\/270503\/\?/);
});

test("AC6 · chat request → card data; a missing date or destination is asked for, never guessed", () => {
  setup(georgia());
  const s = F.f24ChatSearch({ kind: "flight", from: "בטומי", to: "תל אביב", date: "2027-05-17" });
  assert.deepEqual([s.from.iata, s.to.iata, s.date, s.adults, s.roundTrip], ["BUS", "TLV", "2027-05-17", 5, false]);
  assert.match(s.links.skyscanner, /\/flights\/bus\/tlv\/270517\/\?adultsv2=5$/);
  assert.deepEqual(F.f24ChatSearch({ kind: "flight", from: "בטומי", to: "TLV" }), { kind: "flight", missing: ["date"] });
  assert.deepEqual(F.f24ChatSearch({ kind: "hotel", date: "17/5" }), { kind: "hotel", missing: ["to", "date"] });
  assert.equal(F.f24ChatSearch({ kind: "flight", to: "Athens", date: "17/05/2027" }).from.iata, "TLV");
  const h = F.f24ChatSearch({ kind: "hotel", to: "בטומי", date: "2027-05-07", nights: 3 });
  assert.deepEqual([h.city, h.checkin, h.checkout, h.nights], ["Batumi", "2027-05-07", "2027-05-10", 3]);
  assert.equal(F.f24ChatSearch({ kind: "hotel", to: "Kazbegi", date: "2027-05-07", return_date: "2027-05-09" }).nights, 2);
  assert.equal(F.f24ChatSearch({ kind: "car", to: "x", date: "2027-05-07" }), null);
});

test("AC8 · TRAVELSEARCH_FEATURE='off' → no search anywhere", () => {
  setup(georgia(), { feature: "off" });
  assert.equal(F.f24FlightSearch(0), null); assert.equal(F.f24LodgingSearch(1), null); assert.equal(F.f24ChatSearch({ kind: "flight", to: "TLV", date: "2027-05-17" }), null);
});

test("R2 · a request that cannot be built falls back to the site's own page", () => {
  setup(georgia());
  const tbs = { iata: "TBS", city: "Tbilisi", country: "GE" }, tlv = { iata: "TLV", city: "Tel Aviv", country: "IL" };
  assert.equal(F.f24GoogleFlightsUrl({ from: tlv, to: tbs, date: "soon" }), "https://www.google.com/travel/flights?q=" + encodeURIComponent("Flights to TBS"));
  assert.equal(F.f24SkyscannerUrl({ from: tlv, to: tbs, date: "2027-02-30" }), "https://www.skyscanner.net/?q=Tbilisi");
  assert.equal(F.f24BookingUrl({ city: "Batumi", country: "GE", checkin: "2027-05-07", checkout: "2027-05-07" }), "https://www.booking.com/searchresults.html?ss=" + encodeURIComponent("Batumi, Georgia"));
  assert.equal(F.f24BookingUrl({}), "https://www.booking.com/"); assert.equal(F.f24GoogleHotelsUrl({}), "https://www.google.com/travel/hotels");
  assert.equal(F.f24SkyscannerUrl({ from: tlv, to: tbs, date: "2027-05-03", returnDate: "2027-05-01", adults: 2 }), "https://www.skyscanner.net/transport/flights/tlv/tbs/270503/?adultsv2=2");
});

// ---------------------------------------------------------------------------------------------------------------
// CHANGE 2026-11-14 F24-A2-02: conversation 2 — the pure HTML of the cards and the origin sheet (what the browser draws), AC1 / AC2 / AC4 / AC7 at the markup level.
test("A2 · flight card: legs, chips, two prefilled links that open in a new tab", () => {
  setup(georgia());
  const html = F.f24FlightCardHtml(F.f24FlightSearch(0), { online: true, fromDay: "" });
  assert.match(html, /עוד אין טיסה ליום הזה/); assert.match(html, /TLV · תל אביב/); assert.match(html, /TBS · טביליסי/);
  assert.match(html, /ברירת מחדל/); assert.match(html, /03\/05 · הלוך/); assert.match(html, /חזור 17\/05/); assert.match(html, /5 נוסעים · מחברי הטיול/);
  assert.equal((html.match(/<a class="p24-go/g) || []).length, 2); assert.match(html, /target="_blank" rel="noopener"/);
  assert.match(html, /href="https:\/\/www\.google\.com\/travel\/flights\?q=/); assert.match(html, /href="https:\/\/www\.skyscanner\.net\/transport\/flights\/tlv\/tbs\/270503\/270517\/\?adultsv2=5"/);
  assert.ok(!/p24-off/.test(html));
});
test("A2 · flight card with a manual origin says so, and a one-way search has no return chip", () => {
  setup(georgia());
  const c = F.f24FlightSearch(0, { origin: "LCA" }), html = F.f24FlightCardHtml(c, { online: true, manual: true });
  assert.match(html, /LCA · לרנקה/); assert.match(html, /נבחר ידנית/); assert.match(html, /03\/05 · כיוון אחד/); assert.ok(!/חזור/.test(html));
});
test("A2 · mid-trip (return) flight card names the previous day as the source of the origin", () => {
  setup(georgia());
  days[13].day = 14;
  const c = F.f24FlightSearch(14), html = F.f24FlightCardHtml(c, { online: true, fromDay: 14 });
  assert.equal(c.from.iata, "BUS"); assert.equal(c.to.iata, "TLV");
  assert.match(html, /מהמסלול · יום 14/); assert.match(html, /BUS · /); assert.match(html, /TLV · תל אביב/); assert.match(html, /כיוון אחד/);
});
test("AC7 · offline: both buttons are disabled spans, no href, with the offline line", () => {
  setup(georgia());
  const html = F.f24FlightCardHtml(F.f24FlightSearch(0), { online: false });
  assert.equal((html.match(/<a /g) || []).length, 0); assert.equal((html.match(/aria-disabled="true"/g) || []).length, 2); assert.match(html, /אין חיבור/);
  const h = F.f24HotelCardHtml(F.f24LodgingSearch(1), { online: false });
  assert.equal((h.match(/<a /g) || []).length, 0); assert.match(h, /אין חיבור/);
});
test("AC4 · lodging card: city, nights, guests, checkout in the title, Booking + Google Hotels", () => {
  setup(georgia());
  const s = F.f24LodgingSearch(1), html = F.f24HotelCardHtml(s, { online: true });
  assert.match(html, /עוד אין לינה ל-04\/05 עד 07\/05/); assert.match(html, /טביליסי/); assert.match(html, /3 לילות/); assert.match(html, /5 אורחים · מחברי הטיול/);
  assert.match(html, /booking\.com\/searchresults\.html\?ss=/); assert.match(html, /google\.com\/travel\/hotels\?q=/);
});
test("A2 · origin sheet: suggestions are TLV, ETM and the recent origins; the selected one is pressed; a search lists matches", () => {
  setup(georgia());
  let h = F.f24OriginSheetHtml({ sel: "TLV", q: "" }, ["LCA"]);
  assert.match(h, /data-p24-ap="TLV"[^>]*aria-pressed="true"/); assert.match(h, /data-p24-ap="ETM"[^>]*aria-pressed="false"/);
  assert.match(h, /data-p24-ap="LCA"/); assert.match(h, /חיפשתם מכאן קודם/); assert.match(h, /השינוי חל רק על החיפוש הזה/);
  h = F.f24OriginSheetHtml({ sel: "LCA", q: "אתונה" }, []);
  assert.match(h, /data-p24-ap="ATH"/); assert.ok(!/data-p24-ap="TLV"/.test(h));
  h = F.f24OriginSheetHtml({ sel: "TLV", q: "zzzzqq" }, []);
  assert.match(h, /לא נמצא שדה תעופה/);
});
test("A2 · card HTML escapes city names from the trip", () => {
  setup([fl("03/05/2027", "IL", "GE", "", '<img src=x onerror=1>')]);
  const s = F.f24FlightSearch(0), html = F.f24FlightCardHtml(s, { online: true });
  assert.ok(!/<img/.test(html));
});
