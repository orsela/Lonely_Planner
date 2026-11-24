// Lonely Planner TC-BUG-01 · Node tests of app/js/tcfix.js + the REAL SS / loadState / saveTrip of app/index.html (extracted, run in a vm with a fake cloud) · version 3.0.0-alpha.18.4
// CHANGE 2026-11-24 TCFIX-T-01: new file (no previous version). Run: tests/tcfix/run.sh (no browser, no network).
import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
const HTML = readFileSync(new URL("../../app/index.html", import.meta.url), "utf8");
const TCFIX_SRC = readFileSync(new URL("../../app/js/tcfix.js", import.meta.url), "utf8");
const RO = "fd5c2b13-cdc0-455e-9c12-b52f2e45a334", VN = "f0200000-0000-4000-8000-000000000001";
const roDays = () => Array.from({ length: 3 }, (_, i) => ({ day: i + 1, date: `${26 + i}/05/2027`, title: "RO" + i, region: "בראשוב", waypoints: [] }));

function cut(from, to) { const a = HTML.indexOf(from); assert.ok(a >= 0, "not found: " + from); const b = HTML.indexOf(to, a + from.length); assert.ok(b > a, "end not found: " + to); return HTML.slice(a, b); }
const SS_SRC = cut("const SS={", "\n};\n") + "\n};\n";
const LOAD_SRC = cut("async function loadState(){", "async function saveTrip(){");
const SAVE_SRC = cut("async function saveTrip(){", "function requireUser(){");

/* a fresh app context: localStorage namespaced per trip like the real wrapper, a cloud that answers / fails on demand */
function app({ flag = "on", trip = RO, backend = "cloud", cloud = "up", row = null, local = {}, loaded = [] } = {}) {
  const store = new Map(Object.entries(local)), queue = [], cloudWrites = [];
  const ctx = {
    console, JSON, Array, Promise, Object, String, Number, Math, Date,
    TCFIX_FEATURE: flag, STORAGE_BACKEND: backend, WIZARD_FEATURE: "on",
    SHARED: { trip: "planner:trip" }, KEYS: { trip: "vietnam_planner_trip_v1", user: "vietnam_planner_user_v1" },
    SEED_DATA: [{ day: 1, date: "16/09/2026", title: "האנוי", region: "האנוי", waypoints: [] }],
    state: { tripId: trip }, tripData: loaded.slice(), globalDayIndex: 0, activeUser: "",
    localStorage: { getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => { store.set(k, String(v)); }, removeItem: k => { store.delete(k); } },
    enqueue: (t, k, v) => queue.push({ t, k, v }), dequeue: () => {},
    hasCloud: () => true,
    window: {},
  };
  ctx.window.storage = {
    get: async () => { if (ctx.cloud === "down") throw new Error("offline"); return ctx.row == null ? null : { value: ctx.row }; },
    set: async (k, v) => { if (ctx.cloud === "down") throw new Error("offline"); cloudWrites.push({ k, v }); return true; },
  };
  ctx.window.localStorage = ctx.localStorage;
  ctx.cloud = cloud; ctx.row = row; ctx.window.__ptF04 = { emptyTrip: () => { ctx.emptyCalled = true; } };
  vm.createContext(ctx);
  vm.runInContext("var window=this.window;", ctx);   // keep `window` pointing at the plain object below
  ctx.window = ctx.window;
  vm.runInContext(TCFIX_SRC, Object.assign(ctx, {}), { filename: "tcfix.js" });   // root = globalThis of ctx → sets globalThis.__ptTCFix
  vm.runInContext("function makeSeed(){return SEED_DATA.map(d=>({...d,waypoints:[]}))}\n" + SS_SRC.replace("const SS=", "var SS=") + "\n" + LOAD_SRC.replace("async function loadState", "var loadState=async function") + "\n" + SAVE_SRC.replace("async function saveTrip", "var saveTrip=async function") + ";", ctx);
  return { ctx, store, queue, cloudWrites, set tripData(v) { ctx.tripData = v; } };
}
const run = (a, code) => vm.runInContext(code, a.ctx);

test("pure · tcfix is inactive for Vietnam, flag off and a non-cloud backend", () => {
  for (const o of [{ trip: VN }, { flag: "off" }, { backend: "local-only" }]) {
    const a = app(o); assert.equal(a.ctx.window.__ptTCFix.active(), false);
    a.ctx.window.__ptTCFix.fail(); assert.equal(a.ctx.window.__ptTCFix.down(), false); assert.equal(a.ctx.window.__ptTCFix.blockSave(), false);
  }
  assert.equal(app().ctx.window.__ptTCFix.active(), true);
});

test("S1 · warm: the cloud drops while the Romania days are loaded → loadState keeps them (not the Vietnam seed)", async () => {
  const a = app({ cloud: "up", row: JSON.stringify(roDays()) });
  await run(a, "loadState()");                                  // online load
  assert.equal(a.ctx.tripData.length, 3); assert.equal(a.ctx.tripData[0].title, "RO0");
  a.ctx.cloud = "down";
  await run(a, "loadState()");                                  // pullRemoteUpdates while offline
  assert.equal(a.ctx.tripData.length, 3); assert.equal(a.ctx.tripData[0].title, "RO0", "must stay Romania");
  assert.ok(!a.ctx.tripData.some(d => d.title === "האנוי"));
});

test("S2 · cold: reopened offline with a last good copy → the Romania days from the copy", async () => {
  const a = app({ cloud: "up", row: JSON.stringify(roDays()) });
  await run(a, "loadState()");                                  // online once: the copy is written
  assert.ok(a.store.get("planner:trip:lg"), "last good copy kept");
  const b = app({ cloud: "down", local: { "planner:trip:lg": a.store.get("planner:trip:lg") } });   // new page load, offline
  await run(b, "loadState()");
  assert.equal(b.ctx.tripData.length, 3); assert.equal(b.ctx.tripData[0].title, "RO0");
});

test("S3 · cold, offline, no copy at all → no days (never the seed) and saveTrip writes nothing", async () => {
  const a = app({ cloud: "down" });
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData.length, 0); assert.equal(a.ctx.emptyCalled, true);
  await run(a, "saveTrip()");
  assert.equal(a.queue.length, 0, "nothing queued for the cloud"); assert.equal(a.cloudWrites.length, 0);
  assert.equal(a.store.has("planner:trip"), false, "nothing written locally either");
});

test("S4 · the cloud answers with no row → no days, never the seed; saving is allowed", async () => {
  const a = app({ cloud: "up", row: null });
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData.length, 0);
  await run(a, "saveTrip()");
  assert.equal(a.cloudWrites.length, 1, "a real (empty) trip may be saved");
});

test("S5 · recovery: after being offline the next online read replaces the days and saving works again", async () => {
  const a = app({ cloud: "down" });
  await run(a, "loadState()"); assert.equal(a.ctx.tripData.length, 0);
  a.ctx.cloud = "up"; a.ctx.row = JSON.stringify(roDays());
  await run(a, "loadState()"); assert.equal(a.ctx.tripData.length, 3);
  await run(a, "saveTrip()"); assert.equal(a.cloudWrites.length, 1);
  assert.equal(JSON.parse(a.cloudWrites[0].v)[0].title, "RO0", "what is written is the Romania days");
});

test("S6 · an offline edit never sends the Vietnam seed to the cloud (the data-loss path)", async () => {
  const a = app({ cloud: "down" });
  await run(a, "loadState()"); await run(a, "saveTrip()");
  await run(a, "loadState()"); await run(a, "saveTrip()");
  for (const q of a.queue) assert.ok(!String(q.v).includes("האנוי"), "the seed must not be queued");
  assert.equal(a.cloudWrites.length, 0);
});

test("S7 · the user's own local edits still win offline (primary local copy is a valid array)", async () => {
  const mine = roDays().map(d => ({ ...d, title: "EDIT" }));
  const a = app({ cloud: "down", local: { "planner:trip": JSON.stringify(mine) } });
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData[0].title, "EDIT");
});

test("V1 · Vietnam trip: offline keeps the OLD behaviour (the seed), unchanged", async () => {
  const a = app({ trip: VN, cloud: "down" });
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData.length, 1); assert.equal(a.ctx.tripData[0].title, "האנוי");
  assert.equal(a.store.has("planner:trip:lg"), false, "no extra local copy for Vietnam");
});

test("V2 · TCFIX_FEATURE='off': exactly the old path (the seed offline)", async () => {
  const a = app({ flag: "off", cloud: "down" });
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData[0].title, "האנוי");
});

test("V3 · hooks are additive: with tcfix.js missing the three functions behave as in alpha.18.3", async () => {
  const a = app({ cloud: "down" }); a.ctx.window.__ptTCFix = undefined;
  await run(a, "loadState()");
  assert.equal(a.ctx.tripData[0].title, "האנוי");
  await run(a, "saveTrip()"); assert.equal(a.queue.length, 1);
});

test("static · version, flag, script tag and service-worker entry", () => {
  assert.match(HTML, /const PT_VERSION='3\.0\.0-alpha\.18\.4'/); assert.match(HTML, /const APP_VERSION='3\.0\.0-alpha\.18\.4'/);
  assert.match(HTML, /const TCFIX_FEATURE='on';/); assert.match(HTML, /<script src="js\/tcfix\.js"><\/script>/);
  assert.match(readFileSync(new URL("../../app/sw.js", import.meta.url), "utf8"), /"js\/tcfix\.js"/);
});
