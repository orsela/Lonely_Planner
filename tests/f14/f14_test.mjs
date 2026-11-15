// Lonely Planner F14 · step 3 · Node tests of app/js/f14.js (the page side of the smart chat) · version 3.0.0-alpha.15
// CHANGE 2026-11-15 F14-A3-02: new file (no previous version). Covers, at the code level, spec criteria 1–2 and 4–9 of the client:
//   what the request carries (trip_id, tripInfo, the user's JWT and not the anon key, ISO days with country / city / tz), every refusal as ONE friendly
//   line with a single request (no retry), the FB_Chat card (links from F24, no approve button, nothing saved), missing[] → a question line, null → no card,
//   offline → disabled buttons, and the 'soon' / local-only states where nothing is wrapped.
// Run: tests/f14/run.sh --only app   (no browser here, no network)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const F8 = req("../../app/js/f08.js"), F24 = req("../../app/js/f24.js"), F = req("../../app/js/f14.js");
const AIRPORTS = JSON.parse(readFileSync(new URL("../../app/airports.json", import.meta.url), "utf8"));
const COUNTRIES = {
  IL: { en: "Israel", he: "ישראל", tz: ["Asia/Jerusalem"] }, GE: { en: "Georgia", he: "גאורגיה", tz: ["Asia/Tbilisi"] },
};
const ANON = "sb_publishable_ANON_KEY", JWT = "user.jwt.token", TRIP = "11111111-1111-4111-8111-111111111111", ENDPOINT = "https://x.supabase.co/functions/v1/chat-assistant";
const land = (date, city) => ({ date, country: "GE", city, tz: "Asia/Tbilisi" });
const fl = (date, f, t, fc, tc) => ({ date, isFlight: true, flightFrom: { country: f, tz: COUNTRIES[f].tz[0], city: fc }, flightTo: { country: t, tz: COUNTRIES[t].tz[0], city: tc } });
const DAYS = [fl("03/05/2027", "IL", "GE", "", "טביליסי"), land("04/05/2027", "טביליסי"), land("05/05/2027", "Batumi"), fl("17/05/2027", "GE", "IL", "Batumi", "")];

let calls = [], toasts = [], online = true, f24feature = "on", flag = "on", back = "cloud", session = { access_token: JWT }, memberRows = 5, memberCalls = 0, home = null;
function client() {
  return {
    auth: { getSession: async () => ({ data: { session } }) },
    from: (t) => { assert.equal(t, "trip_members"); memberCalls++; const q = { select: () => q, eq: () => q, then: (ok) => ok({ data: Array.from({ length: memberRows }, (_, i) => ({ id: i })), error: null }) }; return q; },
  };
}
function setup(o = {}) {
  calls = []; toasts = []; online = true; f24feature = o.f24 || "on"; flag = o.flag || "on"; back = o.backend || "cloud"; session = "session" in o ? o.session : { access_token: JWT }; home = o.home || null;
  memberRows = "members" in o ? o.members : 5; memberCalls = 0;
  F8.f08Configure({ days: () => DAYS, countries: () => COUNTRIES, tripCountries: () => [], homeCurrency: () => "ILS", deviceTz: () => "Asia/Jerusalem", landing: () => null, feature: () => "on" });
  F24.f24Configure({ f08: F8, days: () => DAYS, reservations: () => [], members: () => memberRows, airports: () => AIRPORTS, countries: () => COUNTRIES, feature: () => f24feature });
  F.f14Configure({
    flag: () => flag, backend: () => back, endpoint: ENDPOINT, client, tripId: () => TRIP, withTimeout: (p) => Promise.resolve(p), f08: F8, f24: F24,
    days: () => DAYS, tripName: async () => "גאורגיה 2027", currencies: () => ({ home: "ILS", local: "GEL" }), countries: () => COUNTRIES, home: () => home,
    now: () => new Date(2027, 1, 9, 12).getTime(), online: () => online, toast: (m) => toasts.push(m), chatSearch: (p) => F24.f24ChatSearch(p),
  });
}
// the request the page itself builds (anon key, old body shape); the stub answers like the server
function pageRequest(extra = {}) {
  return {
    method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + ANON, "apikey": ANON },
    body: JSON.stringify({ question: "כמה ימים בבטומי?", image: null, currentDay: null, trip: DAYS.map((d, i) => ({ day: i + 1, date: d.date, region: "r", title: "t" })), history: [{ role: "user", text: "היי" }, { role: "assistant", text: "צריך להתחבר מחדש כדי לשאול אותי. אפשר לרענן את האפליקציה ולנסות שוב." }, { role: "user", text: "שוב" }], ...extra }),
  };
}
const answer = (status, body) => async (input, init) => { calls.push({ input, init }); return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); };

test("AC1 · the request carries trip_id, tripInfo and the user's JWT, never the anon key", async () => {
  setup({ home: { city: "תל אביב", airport: "tlv" } });
  const res = await F.f14Fetch(answer(200, { answer: "שלושה ימים", action: null }), ENDPOINT, pageRequest());
  assert.equal((await res.json()).answer, "שלושה ימים");
  assert.equal(calls.length, 1);
  const { init } = calls[0], b = JSON.parse(init.body);
  assert.equal(init.headers.Authorization, "Bearer " + JWT); assert.ok(!("apikey" in init.headers)); assert.ok(!JSON.stringify(init).includes(ANON));
  assert.equal(b.trip_id, TRIP); assert.equal(b.lang, "he");
  assert.deepEqual(b.tripInfo, { today: "2027-02-09", name: "גאורגיה 2027", countries: ["Georgia"], homeCurrency: "ILS", localCurrency: "GEL", start: "2027-05-03", end: "2027-05-17", members: 5, homeCity: "תל אביב", homeAirport: "TLV" });
  assert.deepEqual([b.trip[2].date, b.trip[2].country, b.trip[2].city, b.trip[2].tz], ["2027-05-05", "GE", "Batumi", "Asia/Tbilisi"]);
  assert.deepEqual(b.trip[0].flight, { from: { country: "IL" }, to: { country: "GE", city: "טביליסי" } }); assert.ok(!("country" in b.trip[0]));   // a flight day: two sides, no invented country
  assert.equal(b.question, "כמה ימים בבטומי?");                              // the page's own fields stay
});

test("tripInfo · without a home city, without members and without currencies it simply has no such keys (nothing guessed)", async () => {
  setup({ members: 0 });
  F.f14Configure({ currencies: () => null, tripId: () => "22222222-2222-4222-8222-222222222222" });   // another trip: the 60 s members cache is per trip
  await F.f14Fetch(answer(200, { answer: "x", action: null }), ENDPOINT, pageRequest());
  const ti = JSON.parse(calls[0].init.body).tripInfo;
  for (const k of ["homeCity", "homeAirport", "members", "homeCurrency", "localCurrency"]) assert.ok(!(k in ti), k);
});

test("history · the friendly refusal lines never go back to the model", async () => {
  setup();
  await F.f14Fetch(answer(200, { answer: "x", action: null }), ENDPOINT, pageRequest());
  const h = JSON.parse(calls[0].init.body).history;
  assert.deepEqual(h.map(x => x.text), ["היי", "שוב"]);
});

test("AC2 · no valid session → the friendly line, and no request at all (no anon-key fallback)", async () => {
  setup({ session: null });
  const res = await F.f14Fetch(answer(200, { answer: "x" }), ENDPOINT, pageRequest());
  const d = await res.json();
  assert.equal(res.status, 200); assert.equal(d.answer, F.f14ErrorLine("unauthorized")); assert.equal(d.action, null); assert.equal(calls.length, 0);
});

test("every refusal is one friendly line and exactly one request (no retry loop)", async () => {
  const cases = [[401, { error: "unauthorized" }, "unauthorized"], [403, { error: "not_member" }, "not_member"], [429, { error: "daily_cap", used: 100, cap: 100 }, "daily_cap"],
    [429, { error: "rate_limited" }, "rate_limited"], [503, { error: "chat_off" }, "chat_off"], [502, { error: "upstream_error" }, "upstream_error"],
    [504, { error: "upstream_timeout" }, "upstream_timeout"], [413, { error: "too_large" }, "too_large"], [401, {}, "unauthorized"], [429, {}, "rate_limited"]];
  for (const [status, body, code] of cases) {
    setup();
    const res = await F.f14Fetch(answer(status, body), ENDPOINT, pageRequest());
    const d = await res.json();
    assert.equal(res.status, 200, code); assert.equal(d.answer, F.f14ErrorLine(code), code); assert.ok(d.answer.length > 5); assert.equal(d.action, null); assert.equal(calls.length, 1, code);
  }
  assert.match(F.f14ErrorLine("chat_off"), /יחזור בקרוב/);                    // the old "coming soon" wording
});

test("other failures keep the page's old generic error line (400, 500, no network); the page's own timeout gets its line", async () => {
  setup();
  for (const status of [400, 500]) { const res = await F.f14Fetch(answer(status, { error: "invalid_request" }), ENDPOINT, pageRequest()); assert.equal(res.status, status); }
  await assert.rejects(F.f14Fetch(async () => { throw new TypeError("Failed to fetch"); }, ENDPOINT, pageRequest()), /Failed to fetch/);
  const ab = Object.assign(new Error("aborted"), { name: "AbortError" });
  const res = await F.f14Fetch(async () => { throw ab; }, ENDPOINT, pageRequest());
  assert.equal((await res.json()).answer, F.f14ErrorLine("upstream_timeout"));
});

test("D2 · only search_links can come back as an action; anything else is dropped", async () => {
  setup();
  let d = await (await F.f14Fetch(answer(200, { answer: "ok", action: { type: "add_expense", params: {} } }), ENDPOINT, pageRequest())).json();
  assert.equal(d.action, null); assert.equal(d.answer, "ok");
  const keep = { type: "search_links", params: { kind: "flight", to: "TLV", date: "2027-05-17" } };
  d = await (await F.f14Fetch(answer(200, { answer: "ok", action: keep }), ENDPOINT, pageRequest())).json();
  assert.deepEqual(d.action, keep);
});

test("AC5 · search_links flight → FB_Chat card: BUS → TLV, 17/05, 5 travelers, two prefilled links, no approve button, nothing to save", () => {
  setup();
  const m = { role: "assistant", text: "הנה הקישורים 👇", action: { type: "search_links", params: { kind: "flight", from: "בטומי", to: "תל אביב", date: "2027-05-17" } } };
  const html = F.f14MessageHtml(m, 3, () => "ORIG");
  assert.ok(html.includes("הנה הקישורים") && html.includes('data-p14-kind="flight"'));
  assert.ok(html.includes("BUS · ") && html.includes("TLV · ") && html.includes("17/05") && html.includes("5 נוסעים") && html.includes("כיוון אחד"));
  const hrefs = [...html.matchAll(/<a class="p14-go [ps]" href="([^"]+)" target="_blank" rel="noopener noreferrer"/g)].map(x => x[1].replace(/&amp;/g, "&"));
  assert.equal(hrefs.length, 2);
  assert.ok(hrefs[0].startsWith("https://www.google.com/travel/flights?q=") && decodeURIComponent(hrefs[0]).includes("BUS to TLV on 2027-05-17 one way, 5 adults"));
  assert.equal(hrefs[1], "https://www.skyscanner.net/transport/flights/bus/tlv/270517/?adultsv2=5");
  assert.ok(!/<button|data-chat-approve|data-chat-cancel|אישור/.test(html));
});

test("search_links hotel → the lodging card (city, dates, nights, guests, Booking + Google Hotels)", () => {
  setup();
  const html = F.f14MessageHtml({ role: "assistant", text: "הנה", action: { type: "search_links", params: { kind: "hotel", to: "בטומי", date: "2027-05-07", nights: 3 } } }, 0, () => "ORIG");
  assert.ok(html.includes("חיפוש לינה") && html.includes("07/05 – 10/05") && html.includes("3 לילות") && html.includes("5 אורחים") && html.includes("Booking") && html.includes("Google Hotels"));
  assert.equal((html.match(/<a class="p14-go/g) || []).length, 2);
});

test("AC6 · a request with missing[] is one plain question line, no card; null (F24 off) = no card", () => {
  setup();
  const mk = p => ({ role: "assistant", text: "הנה הקישורים 👇", action: { type: "search_links", params: p } });
  let html = F.f14MessageHtml(mk({ kind: "hotel", to: "טביליסי" }), 0, () => "ORIG");
  assert.ok(html.includes("מאיזה תאריך לחפש לינה?") && !html.includes("p14-card") && !html.includes("הנה הקישורים"));
  html = F.f14MessageHtml(mk({ kind: "flight", date: "2027-05-17" }), 0, () => "ORIG");
  assert.ok(html.includes("לאן לחפש טיסה?") && !html.includes("p14-card"));
  html = F.f14MessageHtml(mk({ kind: "flight", to: "TLV", date: "17/5" }), 0, () => "ORIG");     // a date without a year is missing (F24 rule)
  assert.ok(html.includes("באיזה תאריך לחפש טיסה?") && !html.includes("p14-card"));
  assert.equal(F.f14MissingLine({ kind: "flight", missing: ["to", "date"] }).startsWith("לאן ובאיזה תאריך"), true);
  setup({ f24: "off" });
  html = F.f14MessageHtml(mk({ kind: "flight", to: "TLV", date: "2027-05-17" }), 0, () => "ORIG");
  assert.ok(html.includes("הנה הקישורים") && !html.includes("p14-card") && !html.includes("<a "));
});

test("AC9 · offline: the link buttons are disabled and the offline line shows", () => {
  setup(); online = false;
  const html = F.f14MessageHtml({ role: "assistant", text: "הנה", action: { type: "search_links", params: { kind: "flight", to: "TLV", from: "BUS", date: "2027-05-17" } } }, 0, () => "ORIG");
  assert.equal((html.match(/<a /g) || []).length, 0); assert.equal((html.match(/aria-disabled="true"/g) || []).length, 2); assert.ok(html.includes("אין חיבור"));
});

test("other messages and other states go to the previous function untouched", () => {
  setup();
  assert.equal(F.f14MessageHtml({ role: "assistant", text: "היי" }, 0, () => "ORIG"), "ORIG");
  assert.equal(F.f14MessageHtml({ role: "assistant", text: "x", action: { type: "travel_time", params: {} } }, 0, () => "ORIG"), "ORIG");
  setup({ flag: "soon" });
  assert.equal(F.f14MessageHtml({ role: "assistant", text: "x", action: { type: "search_links", params: { kind: "flight", to: "TLV", date: "2027-05-17" } } }, 0, () => "ORIG"), "ORIG");
});

test("AC4 · 'soon' and local-only: enabled() is false, send() just calls the old function, nothing is mounted", async () => {
  for (const o of [{ flag: "soon" }, { flag: "off" }, { backend: "local-only" }]) {
    setup(o); assert.equal(F.enabled(), false);
    let n = 0; await F.send(async t => { n++; return t; }, "שלום"); assert.equal(n, 1);
    assert.equal(F.mount({}), false);
  }
  setup(); assert.equal(F.enabled(), true);
});

test("send · one question at a time, and chat_off shows the old 'coming soon' toast", async () => {
  setup();
  let n = 0, release; const slow = () => { n++; return new Promise(r => { release = r; }); };
  const p1 = F.send(slow, "א"), p2 = F.send(slow, "ב");   // the second one is ignored while the first is running
  assert.equal(n, 1); release(); await p1; await p2;
  assert.deepEqual(toasts, []);
  await F.send(async () => { await F.f14Fetch(answer(503, { error: "chat_off" }), ENDPOINT, pageRequest()); }, "ג");
  assert.deepEqual(toasts, ["הצ'אט יחזור בקרוב"]);
  await F.send(async () => { n++; }, "ד"); assert.equal(n, 2);   // the guard is released
});

test("the page's html carries no anon key outside the gate: f14.js itself never mentions an apikey header", () => {
  const src = readFileSync(new URL("../../app/js/f14.js", import.meta.url), "utf8");
  assert.ok(!/apikey['"]?\s*:/i.test(src) && !/SUPABASE_ANON_KEY|sb_publishable/.test(src));
});
