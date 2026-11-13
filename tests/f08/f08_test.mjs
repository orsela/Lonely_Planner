// Lonely Planner F08 · stage A, conversation 1 · Node tests of app/js/f08.js (day fields + helpers) · version 3.0.0-alpha.13
// CHANGE 2026-11-13 F08-A1-02: new file (no previous version). Covers spec AC1, AC2, AC3, AC4, AC11 (helpers), AC12 (helpers), AC15.
// Run: tests/f08/run.sh   (no browser, no network)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const F = createRequire(import.meta.url)("../../app/js/f08.js");

const COUNTRIES = {
  IL: { tz: ["Asia/Jerusalem"] }, TH: { tz: ["Asia/Bangkok"] }, JP: { tz: ["Asia/Tokyo"] }, VN: { tz: ["Asia/Ho_Chi_Minh"] },
  US: { tz: ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"] },
};
const T = (iso) => Date.parse(iso);
let days = [], landing = {}, feature = "on", homeCur = "ILS", device = "Asia/Jerusalem", trip = [];
function setup(d, o = {}) {
  days = d; landing = o.landing || {}; feature = o.feature || "on"; homeCur = o.homeCur === undefined ? "ILS" : o.homeCur; device = o.device || "Asia/Jerusalem"; trip = o.trip || [];
  F.f08Configure({
    days: () => days, countries: () => COUNTRIES, tripCountries: () => trip, homeCurrency: () => homeCur, deviceTz: () => device,
    landing: (i) => (landing[i] == null ? null : landing[i]), feature: () => feature,
  });
}
const land = (date, country, city) => ({ date, country, city, tz: COUNTRIES[country].tz[0] });
const fl = (date, from, to) => ({ date, isFlight: true, flightFrom: { country: from, tz: COUNTRIES[from].tz[0] }, flightTo: { country: to, tz: COUNTRIES[to].tz[0] } });

// AC1: Israel → Thailand (UTC+7) → Japan (UTC+9) → Israel
function ac1Trip() {
  return [
    land("10/01/2027", "IL"),                       // 0
    fl("11/01/2027", "IL", "TH"),                   // 1  lands 12/01 07:30 Bangkok
    land("12/01/2027", "TH", "Bangkok"),            // 2
    land("13/01/2027", "TH", "Bangkok"),            // 3
    land("14/01/2027", "TH", "Bangkok"),            // 4
    fl("15/01/2027", "TH", "JP"),                   // 5  lands 15/01 16:00 Tokyo
    land("16/01/2027", "JP", "Tokyo"),              // 6
    land("17/01/2027", "JP", "Tokyo"),              // 7
    fl("18/01/2027", "JP", "IL"),                   // 8  lands 18/01 19:00 Jerusalem
    land("19/01/2027", "IL"),                       // 9
  ];
}
const AC1_LAND = { 1: T("2027-01-12T07:30:00+07:00"), 5: T("2027-01-15T16:00:00+09:00"), 8: T("2027-01-18T19:00:00+02:00") };

test("AC1 · the 'here' clock is right on every day, and flips exactly at landing", () => {
  setup(ac1Trip(), { landing: AC1_LAND });
  const at = (iso) => ({ i: F.f08TodayIndex(T(iso)), tz: F.f08HereTz(T(iso)), c: F.f08HereCountry(T(iso)) });
  assert.deepEqual(at("2027-01-10T12:00:00+02:00"), { i: 0, tz: "Asia/Jerusalem", c: "IL" });
  assert.deepEqual(at("2027-01-11T12:00:00+02:00"), { i: 1, tz: "Asia/Jerusalem", c: "IL" });          // flight day, before landing
  assert.deepEqual(at("2027-01-12T07:29:59+07:00"), { i: 1, tz: "Asia/Jerusalem", c: "IL" });          // the second before landing
  assert.deepEqual(at("2027-01-12T07:30:00+07:00"), { i: 2, tz: "Asia/Bangkok", c: "TH" });             // landing → Thailand
  assert.deepEqual(at("2027-01-13T23:59:00+07:00"), { i: 3, tz: "Asia/Bangkok", c: "TH" });
  assert.deepEqual(at("2027-01-15T10:00:00+07:00"), { i: 5, tz: "Asia/Bangkok", c: "TH" });             // flight Bangkok → Tokyo, in the air
  assert.deepEqual(at("2027-01-15T15:59:59+09:00"), { i: 5, tz: "Asia/Bangkok", c: "TH" });
  assert.deepEqual(at("2027-01-15T16:00:00+09:00"), { i: 5, tz: "Asia/Tokyo", c: "JP" });               // landed, still the flight day
  assert.deepEqual(at("2027-01-16T00:00:00+09:00"), { i: 6, tz: "Asia/Tokyo", c: "JP" });
  assert.deepEqual(at("2027-01-17T20:00:00+09:00"), { i: 7, tz: "Asia/Tokyo", c: "JP" });
  assert.deepEqual(at("2027-01-18T18:59:59+02:00"), { i: 8, tz: "Asia/Tokyo", c: "JP" });
  assert.deepEqual(at("2027-01-18T19:00:00+02:00"), { i: 8, tz: "Asia/Jerusalem", c: "IL" });
  assert.deepEqual(at("2027-01-19T09:00:00+02:00"), { i: 9, tz: "Asia/Jerusalem", c: "IL" });
});

test("AC1 · f08HereSide: 'from' until landing, 'to' after, null on a normal day", () => {
  setup(ac1Trip(), { landing: AC1_LAND });
  const d = days;
  assert.equal(F.f08HereSide(d[5], T("2027-01-15T15:59:59+09:00")), "from");
  assert.equal(F.f08HereSide(d[5], T("2027-01-15T16:00:00+09:00")), "to");
  assert.equal(F.f08HereSide(d[2], T("2027-01-12T12:00:00+07:00")), null);
});

test("AC1 · no landing time known → 'from' until midnight on the departure clock", () => {
  setup(ac1Trip());   // no flight-card times
  const d = days;
  assert.equal(F.f08HereSide(d[1], T("2027-01-11T23:59:00+02:00")), "from");
  assert.equal(F.f08HereSide(d[1], T("2027-01-12T00:00:00+02:00")), "to");
  assert.equal(F.f08TodayIndex(T("2027-01-12T00:00:00+02:00")), 2);   // = 05:00 Bangkok on the 12th
});

test("outside the trip: today index -1, 'here' = the device, no country", () => {
  setup(ac1Trip(), { device: "Europe/Paris" });
  for (const iso of ["2027-01-09T12:00:00+02:00", "2027-01-20T12:00:00+02:00"]) {
    assert.equal(F.f08TodayIndex(T(iso)), -1);
    assert.equal(F.f08HereTz(T(iso)), "Europe/Paris");
    assert.equal(F.f08HereCountry(T(iso)), "");
  }
});

test("AC2 · saving a range writes country/city/tz to its days only; the flight day inside is untouched", () => {
  const list = []; for (let i = 1; i <= 12; i++) list.push({ date: `${String(i).padStart(2, "0")}/03/2027`, region: "x", title: "d" + i });
  list[6] = fl("07/03/2027", "IL", "JP");   // day 7 = flight
  setup(list);
  const r = F.f08ApplyRange(list, 6, 10, { country: "JP", city: "Tokyo" });   // days 7–11 (0-based 6..10)
  assert.deepEqual(r.changed, [7, 8, 9, 10]);                                    // days 8–11 only
  assert.deepEqual(r.days[6], list[6]);                                          // the flight day: identical
  for (const i of r.changed) assert.deepEqual([r.days[i].country, r.days[i].city, r.days[i].tz], ["JP", "Tokyo", "Asia/Tokyo"]);
  for (const i of [0, 5, 11]) assert.equal(r.days[i], list[i]);                   // others: same objects
  assert.equal(list[7].country, undefined);                                       // input array not mutated
  const c = F.f08ClearRange(r.days, 7, 10);
  assert.deepEqual(c.changed, [7, 8, 9, 10]);
  assert.equal(c.days[8].country, undefined); assert.equal(c.days[8].tz, undefined); assert.equal(c.days[8].city, undefined);
  assert.throws(() => F.f08ApplyRange(list, 0, 1, { country: "jp" }));
});

test("AC3 · ranges are computed; a city change on one day splits a range", () => {
  const list = [land("01/05/2027", "TH", "Bangkok"), land("02/05/2027", "TH", "Bangkok"), land("03/05/2027", "TH", "Bangkok"), land("04/05/2027", "TH", "Bangkok"), land("05/05/2027", "JP", "Tokyo")];
  setup(list);
  assert.deepEqual(F.f08Ranges(list).map((r) => [r.from, r.to, r.country, r.city]), [[0, 3, "TH", "Bangkok"], [4, 4, "JP", "Tokyo"]]);
  const split = list.map((d, i) => (i === 2 ? { ...d, city: "Ayutthaya" } : d));
  setup(split);
  assert.deepEqual(F.f08Ranges(split).map((r) => [r.from, r.to, r.city]), [[0, 1, "Bangkok"], [2, 2, "Ayutthaya"], [3, 3, "Bangkok"], [4, 4, "Tokyo"]]);
  const withFlight = [list[0], fl("02/05/2027", "TH", "TH"), list[2]];
  setup(withFlight);
  assert.deepEqual(F.f08Ranges(withFlight).map((r) => !!r.flight), [false, true, false]);   // a flight day always splits
});

test("AC4 · the time-zone picker only for a country with several zones", () => {
  setup([]);
  assert.equal(F.f08NeedsTzPicker("US"), true);
  assert.equal(F.f08NeedsTzPicker("JP"), false);
  assert.equal(F.f08NeedsTzPicker("ZZ"), false);
});

test("§3 · derivation when fields are missing", () => {
  const list = [{ date: "01/06/2027", country: "TH" }, { date: "02/06/2027" }, { date: "03/06/2027", country: "JP", tz: "Asia/Tokyo" }, { date: "04/06/2027" }, { date: "05/06/2027", tz: "Asia/Seoul" }];
  setup(list, { trip: ["IL"] });
  assert.deepEqual([0, 1, 2, 3, 4].map((i) => F.f08DayCountry(list[i])), ["TH", "TH", "JP", "JP", "JP"]);   // nearest previous day with a country
  assert.deepEqual([0, 1, 2, 3, 4].map((i) => F.f08DayTz(list[i])), ["Asia/Bangkok", "Asia/Bangkok", "Asia/Tokyo", "Asia/Tokyo", "Asia/Seoul"]);
  const bare = [{ date: "01/06/2027" }];
  setup(bare, { trip: ["TH"] });
  assert.equal(F.f08DayCountry(bare[0]), "TH");   // no day has a country → the trip's first country
  setup(bare);
  assert.deepEqual([F.f08DayCountry(bare[0]), F.f08DayTz(bare[0])], ["VN", "Asia/Ho_Chi_Minh"]);
  setup([{ date: "01/06/2027", country: "TH", tz: "Not/AZone" }]);
  assert.equal(F.f08DayTz(days[0]), "Asia/Bangkok");   // an invalid stored tz is ignored
});

test("flight detection: isFlight, and the legacy region 'טיסות' without the field", () => {
  setup([]);
  assert.equal(F.f08IsFlight({ isFlight: true }), true);
  assert.equal(F.f08IsFlight({ region: "טיסות" }), true);
  assert.equal(F.f08IsFlight({ hotel: "טיסה חזרה" }), true);
  assert.equal(F.f08IsFlight({ region: "האנוי" }), false);
});

// AC11 (helpers): the legacy Vietnam trip, no new fields at all
function seedTrip() {
  const mk = (n, region, hotel) => ({ day: n, date: `${String(14 + n).padStart(2, "0")}/09/2026`, region, hotel, title: "t" });
  return [mk(1, "טיסות", "בטיסה"), mk(2, "האנוי", "מלון"), mk(3, "האנוי", "מלון"), mk(4, "נין בין", "ריזורט"), mk(5, "טיסות", "טיסה חזרה")];
}
test("AC11 · legacy Vietnam trip derives VN / Asia/Ho_Chi_Minh and the same flight days", () => {
  const list = seedTrip(); setup(list, { device: "Asia/Ho_Chi_Minh" });
  assert.deepEqual(list.map((d) => F.f08IsFlight(d)), [true, false, false, false, true]);
  assert.deepEqual(list.map((d) => F.f08DayCountry(d)), Array(5).fill("VN"));
  assert.deepEqual(list.map((d) => F.f08DayTz(d)), Array(5).fill("Asia/Ho_Chi_Minh"));
  assert.equal(F.f08HereTz(T("2026-09-17T12:00:00+07:00")), "Asia/Ho_Chi_Minh");
  assert.equal(F.f08HereCountry(T("2026-09-17T12:00:00+07:00")), "VN");
  assert.equal(F.f08HomeTz(), "Asia/Jerusalem");
  assert.deepEqual([F.f08FlightFrom(list[0]).tz, F.f08FlightTo(list[0]).country], ["Asia/Jerusalem", "VN"]);   // outbound: home → Vietnam
  assert.deepEqual([F.f08FlightFrom(list[4]).country, F.f08FlightTo(list[4]).tz], ["VN", "Asia/Jerusalem"]);   // return: Vietnam → home
});

test("AC12 · F08_FEATURE='off' gives the alpha.12.1 answers", () => {
  setup(ac1Trip(), { landing: AC1_LAND, feature: "off", device: "Europe/Paris", homeCur: "EUR" });
  const t = T("2027-01-13T12:00:00+07:00");
  assert.equal(F.f08HereTz(t), "Europe/Paris");        // the device clock
  assert.equal(F.f08HereCountry(t), "VN");
  assert.equal(F.f08HomeTz(), "Asia/Jerusalem");       // hard-coded home
  assert.equal(F.f08TodayIndex(t), -1);
  assert.equal(F.f08IsFlight({ isFlight: true }), false);   // the new field is ignored
  assert.equal(F.f08IsFlight({ region: "טיסות" }), true);
});

test("AC15 · home clock: ILS → Israel; another home currency → the device zone; same zone → one clock", () => {
  setup(ac1Trip(), { landing: AC1_LAND, homeCur: "ILS", device: "Europe/Paris" });
  assert.equal(F.f08HomeTz(), "Asia/Jerusalem");
  setup(ac1Trip(), { landing: AC1_LAND, homeCur: "EUR", device: "Europe/Paris" });
  assert.equal(F.f08HomeTz(), "Europe/Paris");
  setup(ac1Trip(), { landing: AC1_LAND, homeCur: "", device: "Europe/Paris" });
  assert.equal(F.f08HomeTz(), "Asia/Jerusalem");        // no home_currency → as a shekel trip
  setup(ac1Trip(), { landing: AC1_LAND });
  assert.equal(F.f08SameClock(T("2027-01-10T12:00:00+02:00")), true);    // in Israel: here = home
  assert.equal(F.f08SameClock(T("2027-01-13T12:00:00+07:00")), false);   // in Thailand
  setup(ac1Trip(), { landing: AC1_LAND, homeCur: "EUR", device: "Asia/Tokyo" });
  assert.equal(F.f08SameClock(T("2027-01-16T12:00:00+09:00")), true);    // in Japan, device (= home) in Tokyo
});
