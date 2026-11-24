// Lonely Planner TRIP-COUNTRY-A · Node tests of app/js/tripcountry.js + the first/last day flight card in app/js/f24.js · version 3.0.0-alpha.18.1
// CHANGE 2026-11-24 TC-A-T-01: new file (no previous version). Run: tests/tripcountry/run.sh (no browser, no network).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const F8 = req("../../app/js/f08.js"), F = req("../../app/js/f24.js"), TC = req("../../app/js/tripcountry.js");
const AIRPORTS = JSON.parse(readFileSync(new URL("../../app/airports.json", import.meta.url), "utf8"));
const COUNTRIES = { IL: { en: "Israel", he: "ישראל", tz: ["Asia/Jerusalem"] }, RO: { en: "Romania", he: "רומניה", tz: ["Europe/Bucharest"] }, VN: { en: "Vietnam", he: "וייטנאם", tz: ["Asia/Ho_Chi_Minh"] } };
const RO_TRIP = "fd5c2b13-cdc0-455e-9c12-b52f2e45a334", VN_TRIP = "f0200000-0000-4000-8000-000000000001";
let days = [], flag = "on", backend = "cloud", trip = RO_TRIP, res = [];
function setup(d, o = {}) {
  days = d; res = o.res || []; flag = o.flag || "on"; backend = o.backend || "cloud"; trip = o.trip || RO_TRIP;
  F8.f08Configure({ days: () => days, countries: () => COUNTRIES, tripCountries: () => ["RO"], homeCurrency: () => "ILS", deviceTz: () => "Asia/Jerusalem", landing: () => null, feature: () => "on" });
  F.f24Configure({ f08: F8, days: () => days, reservations: () => res, members: () => 10, airports: () => AIRPORTS, countries: () => COUNTRIES, feature: () => "on" });
  TC.tcConfigure({ feature: () => flag, backend: () => backend, tripId: () => trip, travelers: () => 10 });
  globalThis.__ptTC = { active: TC.tcActive }; globalThis.__ptF08 = F8;   // what f24.js / tripcountry.js read in the browser
}
// Romania: 10 days, none marked as a flight day (26/05–04/06/2027), country RO on every day
const roDays = () => Array.from({ length: 10 }, (_, k) => ({ date: `${String(26 + k > 31 ? 26 + k - 31 : 26 + k).padStart(2, "0")}/0${26 + k > 31 ? 6 : 5}/2027`, country: "RO", city: k === 0 ? "Brașov" : "Brașov", region: "בראשוב", hotel: "H" }));

test("suffix · active trip names its country; Vietnam, flag off and local storage keep ', Vietnam'", () => {
  setup(roDays()); assert.equal(TC.tcSuffix(days[0]), ", Romania");
  setup(roDays(), { flag: "off" }); assert.equal(TC.tcSuffix(days[0]), ", Vietnam");
  setup(roDays(), { backend: "local" }); assert.equal(TC.tcSuffix(days[0]), ", Vietnam");
  setup(roDays(), { trip: VN_TRIP }); assert.equal(TC.tcSuffix(days[0]), ", Vietnam");
  setup([{ date: "01/01/2027", region: "x", hotel: "y" }]); assert.equal(TC.tcSuffix(days[0]), ", Romania", "a day without a country takes the trip's first country (F08)");
});

test("booking · traveller count, rooms = ceil(n/2), no children; null when inactive (caller keeps the Vietnam parameters)", () => {
  setup(roDays());
  const b = TC.tcBooking({ hotel: "Hotel X", region: "Brașov", checkin: "2027-05-26", checkout: "2027-05-28" }, days[0]);
  assert.deepEqual(b, { ss: "Hotel X, Brașov, Romania", checkin: "2027-05-26", checkout: "2027-05-28", group_adults: "10", group_children: "0", no_rooms: "5" });
  TC.tcConfigure({ travelers: () => 7 }); assert.equal(TC.tcBooking({ hotel: "H", region: "R", checkin: "a", checkout: "b" }, days[0]).no_rooms, "4");
  TC.tcConfigure({ travelers: () => 0 }); assert.equal(TC.tcBooking({ hotel: "H", region: "R", checkin: "a", checkout: "b" }, days[0]).group_adults, "1");
  setup(roDays(), { trip: VN_TRIP }); assert.equal(TC.tcBooking({ hotel: "H", region: "R", checkin: "a", checkout: "b" }, days[0]), null);
  setup(roDays(), { flag: "off" }); assert.equal(TC.tcBooking({ hotel: "H", region: "R", checkin: "a", checkout: "b" }, days[0]), null);
});

test("flight search · unmarked first day: TLV → OTP (guessed), round trip to the last day; unmarked last day: OTP → TLV, one way", () => {
  setup(roDays());
  const a = F.f24FlightSearch(0);
  assert.ok(a && a.virt === "first", "card on day 1");
  assert.equal(a.from.iata, "TLV"); assert.equal(a.to.iata, "OTP"); assert.equal(a.guessTo, true);
  assert.equal(a.roundTrip, true); assert.equal(a.returnDate, "2027-06-04"); assert.equal(a.date, "2027-05-26");
  const z = F.f24FlightSearch(9);
  assert.ok(z && z.virt === "last", "card on day 10");
  assert.equal(z.from.iata, "OTP"); assert.equal(z.to.iata, "TLV"); assert.equal(z.roundTrip, false); assert.equal(z.date, "2027-06-04");
  assert.match(a.links.googleFlights, /^https:\/\/www\.google\.com\/travel\/flights/);
  assert.equal(F.f24FlightSearch(4), null, "a middle day has no flight card");
});

test("flight search · a booked flight, the flag off, the Vietnam trip, marked flight days and a home-country day change nothing", () => {
  setup(roDays(), { res: [{ type: "flight", linkedDays: [9] }] });
  assert.equal(F.f24FlightSearch(9), null, "booked last day: no card");
  assert.equal(F.f24FlightSearch(0).roundTrip, false, "last day booked: first day is one way");
  setup(roDays(), { res: [{ type: "flight", linkedDays: [0] }] }); assert.equal(F.f24FlightSearch(0), null);
  for (const o of [{ flag: "off" }, { trip: VN_TRIP }, { backend: "local" }]) { setup(roDays(), o); assert.equal(F.f24FlightSearch(0), null); assert.equal(F.f24FlightSearch(9), null); }
  const marked = roDays(); marked[0].isFlight = true; marked[0].flightFrom = { country: "IL", tz: "Asia/Jerusalem" }; marked[0].flightTo = { country: "RO", tz: "Europe/Bucharest" };
  setup(marked); const m = F.f24FlightSearch(0); assert.ok(m && m.virt === "", "a marked flight day keeps its normal card");
  assert.equal(F.f24FlightSearch(1), null, "day next to a marked flight day gets no extra card");
  const il = roDays().map(d => ({ ...d, country: "IL" })); setup(il); assert.equal(F.f24FlightSearch(0), null, "a trip inside Israel: no flight card");
  setup([roDays()[0]]); assert.equal(F.f24FlightSearch(0), null, "a one-day trip: no card");
});
