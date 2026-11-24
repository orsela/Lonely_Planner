// Lonely Planner · F13-TR client tests · version 3.0.0-alpha.19.0
// CHANGE 2026-11-24 F13-TR-CL-02: new file. collect() + run() of app/js/f13tr.js with stubs (no network, no DOM).
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const TR = req("../../app/js/f13tr.js");
const store = {}, toasts = [], layer = {}, saved = [];
globalThis.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
globalThis.confirm = () => true;
globalThis.document = undefined;
let calls = [], answer;
function setup(extra = {}) {
  for (const k of Object.keys(store)) delete store[k]; toasts.length = 0; calls = []; for (const k of Object.keys(layer)) delete layer[k]; saved.length = 0;
  globalThis.__ptF13 = { active: () => true, addLayer: (m) => { Object.assign(layer, m); return Object.keys(m).length; }, layerSize: () => Object.keys(layer).length };
  answer = { status: 200, body: { map: { "האנוי": "Hanoi" } } };
  TR.attach({
    flag: () => "on", backend: () => "cloud", tripId: () => "t1", endpoint: "https://x/f", toast: (m) => toasts.push(m),
    client: () => ({ auth: { getSession: async () => ({ data: { session: { access_token: "JWT" } } }) } }),
    days: () => [{ title: "האנוי", region: "צפון", notes: "", waypoints: [{ name: "אגם", notes: "Walk" }], journal: "סוד" }],
    reservations: async () => [{ title: "מלון", provider: "Booking" }],
    get: async () => null, set: async (v) => { saved.push(v); },
    fetch: async (url, init) => { calls.push({ url, init }); return { ok: answer.status < 400, status: answer.status, json: async () => answer.body }; },
    ...extra,
  });
}
test("collect: Hebrew only, deduped, journal excluded, already-translated skipped", () => {
  const out = TR.collect([{ title: "א", region: "א", activities: "ב", journal: "ג", waypoints: [{ name: "ד" }] }], [{ title: "ה", notes: "x" }], { "ב": "b" });
  assert.deepEqual(out, ["א", "ד", "ה"]);
});
test("run: sends JWT + strings, adds the layer, stores it, toasts", async () => {
  setup();
  const r = await TR.run();
  assert.equal(r.ok, true); assert.equal(r.added, 1);
  const c = calls[0], b = JSON.parse(c.init.body);
  assert.equal(c.init.headers.Authorization, "Bearer JWT"); assert.equal(b.trip_id, "t1");
  assert.deepEqual(b.strings.sort(), ["אגם", "האנוי", "מלון", "צפון"].sort());
  assert.equal(layer["האנוי"], "Hanoi"); assert.equal(saved.length, 1);
  assert.ok(toasts[0].startsWith("Translated 1"));
});
test("run: daily cap shows the friendly line and adds nothing", async () => {
  setup(); answer = { status: 429, body: { error: "daily_cap" } };
  const r = await TR.run();
  assert.equal(r.ok, false); assert.equal(r.code, "daily_cap"); assert.equal(Object.keys(layer).length, 0); assert.match(toasts[0], /limit/i);
});
test("run: not active English = no call", async () => {
  setup(); globalThis.__ptF13.active = () => false;
  const r = await TR.run(); assert.equal(r.ok, false); assert.equal(calls.length, 0);
});
test("run: declined privacy prompt = no call", async () => {
  setup(); globalThis.confirm = () => false;
  const r = await TR.run(); assert.equal(r.code, "declined"); assert.equal(calls.length, 0); globalThis.confirm = () => true;
});
