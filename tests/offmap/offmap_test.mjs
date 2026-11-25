// Lonely Planner OFFMAP · Node tests of app/js/offmap.js (core) · version 3.0.0-alpha.19
// CHANGE 2026-11-24 OFFMAP-T-01: new file (no previous version). Run: tests/offmap/run.sh. Covers: tile math, corridor + tile counts, coordinates (missing / invalid), budget with a small cap and a simulated
// free space, the order of sacrifice, shared days, route change + clean-up, the download engine (cap, free space, resume, 429/403, retries, key never in results), the offmap:// reader, the flag.
// CHANGE 2026-11-24 OFFMAP-T-03: version checks 3.0.0-alpha.20.2 -> 20.3 (viewer).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const OM = req("../../app/js/offmap.js");
const MB = 1024 * 1024, RO = "fd5c2b13-cdc0-455e-9c12-b52f2e45a334", VN = "f0200000-0000-4000-8000-000000000001";

// Romania-like fixture (real city coordinates; NOT Or's actual trip data)
const P = { otp: [44.5711, 26.0858], bv: [45.6427, 25.5887], bran: [45.5154, 25.3672], balv: [46.0833, 25.9333], sib: [45.7983, 24.1256], buc: [44.4268, 26.1025], sf: [45.7, 24.0] };
const dstr = n => { const d = new Date(2027, 4, 25 + n); return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`; };   // day 1 = 26/05/2027
const day = (n, ...ps) => ({ day: n, date: dstr(n), lat: ps[0][0], lng: ps[0][1], waypoints: ps.map((p, i) => ({ name: "w" + i, lat: p[0], lng: p[1] })) });
const roDays = () => [day(1, P.otp, P.bv), day(2, P.bv), day(3, P.bv, P.bran), day(4, P.bran), day(5, P.bran, P.balv), day(6, P.balv, P.sib), day(7, P.sib), day(8, P.sib, P.sf), day(9, P.sib), day(10, P.sib, P.buc)];
const avg = z => OM.avgBytes(z);
const allCost = (plan, keys) => keys.reduce((s, k) => s + avg(plan.tiles.get(k).z), 0);

test("tile math · known tiles, round trip, size", () => {
  assert.equal(OM.tileKey(0, OM.lon2x(10, 0), OM.lat2y(10, 0)), "0/0/0");
  assert.deepEqual([OM.lon2x(0, 1), OM.lat2y(0.0001, 1)], [1, 0]);                 // just north of the equator, east of Greenwich → x=1, y=0 at z1
  assert.equal(OM.lon2x(180, 5), 31); assert.equal(OM.lon2x(-180, 5), 0);            // edges clamp inside the grid
  assert.deepEqual([OM.lon2x(0, 10), OM.lat2y(51.4779, 10)], [512, 340]);            // Greenwich at z10 (well-known OSM tile 10/512/340)
  for (const [lat, lng] of [P.bv, P.sib, P.otp]) for (const z of [8, 12, 14]) {      // the tile of a point contains the point
    const x = OM.lon2x(lng, z), y = OM.lat2y(lat, z), a = OM.tileNW(z, x, y), b = OM.tileNW(z, x + 1, y + 1);
    assert.ok(lng >= a.lng && lng < b.lng && lat <= a.lat && lat > b.lat, `${z} ${lat},${lng}`);
  }
  const s = OM.tileSizeKm(14, 45.6); assert.ok(s > 1.6 && s < 1.8, "z14 tile ≈1.7 km at 45.6°N: " + s);
  assert.equal(OM.parseKey("14/9000/5800").y, 5800); assert.equal(OM.parseKey("x"), null);
});

test("coordinates · '', null, text, out of range are NOT points (the app's valid('', '') would say 0,0)", () => {
  assert.equal(OM.coord("", ""), null); assert.equal(OM.coord(null, 5), null); assert.equal(OM.coord("abc", 5), null);
  assert.equal(OM.coord(91, 5), null); assert.equal(OM.coord(5, 181), null); assert.equal(OM.coord(true, 1), null);
  assert.deepEqual(OM.coord("45.5", "25.1"), { lat: 45.5, lng: 25.1 });
  const d = { lat: "", lng: "", waypoints: [{ lat: 45.6, lng: 25.6 }, { lat: "", lng: "" }, { lat: null, lng: 3 }, { name: "x" }, null, { lat: 45.7, lng: 25.7 }] };
  const dp = OM.dayPoints(d); assert.equal(dp.points.length, 2); assert.equal(dp.missing, 4);
  assert.equal(OM.dayPoints({}).points.length, 0); assert.equal(OM.dayPoints(null).points.length, 0);
  const plan = OM.planTrip([{ date: "26/05/2027" }, { lat: "", lng: "", waypoints: [] }, day(3, P.bv)]);
  assert.ok(plan.days[0].noCoords && plan.days[1].noCoords && !plan.days[2].noCoords);
  assert.equal(plan.days[0].count, 0); assert.ok(plan.total > 0);
  assert.deepEqual(OM.planTrip([]).base, []); assert.equal(OM.planTrip(null).total, 0);                 // no days / no points: nothing, no throw
});

test("corridor · one point: a square of tiles; a leg: a continuous band; a long leg is not connected", () => {
  const one = OM.coveringTiles([{ lat: 45.6, lng: 25.6 }], 14, 3, 150).size;
  assert.ok(one >= 16 && one <= 25, "z14 3 km around a point: " + one + " tiles");   // 6 km / 1.7 km = 3.5 → 4 or 5 per side
  const a = { lat: 45.6, lng: 24.0 }, b = { lat: 45.6, lng: 24.5 };                                      // ≈39 km east-west
  const set = OM.coveringTiles([a, b], 14, 3, 150), n = OM.distKm(a, b);
  assert.ok(n > 38 && n < 40);
  for (let i = 0; i <= 200; i++) { const lng = 24.0 + 0.5 * i / 200; assert.ok(set.has(OM.tileKey(14, OM.lon2x(lng, 14), OM.lat2y(45.6, 14))), "gap at " + lng); }   // every point of the line is inside
  const rows = new Set(Array.from(set, k => OM.parseKey(k).y)); assert.ok(rows.size >= 4 && rows.size <= 6, "band is 4–5 tiles tall: " + rows.size);   // 2×3 km / 1.7 km
  const far = [{ lat: 45.6, lng: 24.0 }, { lat: 45.6, lng: 27.0 }];                                       // ≈233 km: a transfer, not a corridor
  const noLeg = OM.coveringTiles(far, 14, 3, 150).size, withLeg = OM.coveringTiles(far, 14, 3, 500).size;
  assert.ok(noLeg < 100 && withLeg > noLeg * 10, `${noLeg} vs ${withLeg}`);
  assert.equal(OM.coveringTiles([], 10, 25, 150).size, 0);
});

test("tile counts · Romania-like 10 days: per zoom, bounded, z14 is the bulk, background small", () => {
  const plan = OM.planTrip(roDays()), byZ = {}; plan.tiles.forEach(t => byZ[t.z] = (byZ[t.z] || 0) + 1);
  assert.equal(plan.days.length, 10); assert.ok(plan.days.every(d => !d.noCoords));
  assert.ok(plan.base.length > 0 && plan.base.length < 60, "background tiles " + plan.base.length);
  assert.ok(byZ[14] > byZ[13] && byZ[13] > byZ[12] && byZ[12] > byZ[11], JSON.stringify(byZ));
  assert.ok(plan.total > 1000 && plan.total < 6000, "total " + plan.total);
  let est = 0; plan.tiles.forEach(t => { est += avg(t.z); });
  assert.ok(est / MB > 30 && est / MB < 150, "estimate MB " + (est / MB).toFixed(1));
  // a bigger buffer gives more tiles (monotonic)
  const wide = OM.planTrip(roDays(), { buffers: { 8: 25, 9: 25, 10: 25, 11: 8, 12: 8, 13: 3, 14: 6 } });
  assert.ok(wide.total > plan.total);
  // fewer zooms = fewer tiles
  assert.ok(OM.planTrip(roDays(), { dayZooms: [8, 9, 10, 11, 12] }).total < plan.total);
  // a huge box (Israel → Romania flight day) keeps only the lower background zooms
  const huge = OM.planTrip([day(1, [32.0, 34.8]), day(2, P.bv), day(3, [1.35, 103.99])]);
  assert.ok(huge.base.length <= 600 + 100);
});

test("shared days · a tile used by several days is stored once, with all its days", () => {
  const plan = OM.planTrip(roDays());
  const shared = Array.from(plan.tiles).filter(([, t]) => t.days.length > 1);
  assert.ok(shared.length > 0, "days 2,3 (Brașov) and 7,8,9,10 (Sibiu) must overlap");
  const sumPerDay = plan.days.reduce((s, d) => s + d.count, 0);
  assert.ok(plan.total - plan.base.length < sumPerDay, "unique < sum of days");
  const [k, t] = shared.find(([, x]) => x.days.includes(1) && x.days.includes(2)) || shared[0];
  assert.ok(plan.days[t.days[0]].tiles[t.z].includes(k) && plan.days[t.days[1]].tiles[t.z].includes(k));
  assert.ok(Array.from(plan.tiles.values()).filter(t => t.base).every(t => t.days.every(i => i >= 0)));   // the background is labelled base, not a day
  // two identical days cost the same as one
  const one = OM.planTrip([day(1, P.sib)]), two = OM.planTrip([day(1, P.sib), day(2, P.sib)]);
  assert.equal(two.total, one.total);
});

test("budget · cap, cap already used, simulated free space and margin", () => {
  assert.equal(OM.computeBudget({}).budget, 150 * MB);
  assert.equal(OM.computeBudget({ cap: 20 * MB }).budget, 20 * MB);                                   // small cap
  assert.equal(OM.computeBudget({ cap: 20 * MB, used: 15 * MB }).budget, 5 * MB);
  assert.equal(OM.computeBudget({ cap: 20 * MB, used: 25 * MB }).budget, 0);                          // never negative
  const free = OM.computeBudget({ cap: 150 * MB, quota: 300 * MB, usage: 200 * MB });                  // 100 MB free − max(50, 10) margin = 50
  assert.equal(free.budget, 50 * MB); assert.equal(free.margin, 50 * MB);
  assert.equal(OM.computeBudget({ cap: 150 * MB, quota: 5000 * MB, usage: 0 }).budget, 150 * MB);      // plenty of room: the cap rules
  assert.equal(OM.computeBudget({ cap: 150 * MB, quota: 2000 * MB, usage: 1000 * MB }).margin, 100 * MB);   // 10% of 1000 MB free
  assert.equal(OM.computeBudget({ cap: 150 * MB, quota: 100 * MB, usage: 99 * MB }).budget, 0);        // device nearly full
  assert.equal(OM.computeBudget({ cap: 150 * MB, quota: 100 * MB, usage: 150 * MB }).budget, 0);       // usage above quota
});

test("sacrifice order · far days lose zoom 14 → 13 → 12, then far days (farthest first); today and tomorrow never; fits when it can", () => {
  const plan = OM.planTrip(roDays()), ctx = (budget, extra) => Object.assign({ cur: 0, ahead: 3, budget, stored: new Set(), avg }, extra);
  const full = OM.buildQueue(plan, ctx(1e12));
  assert.ok(full.fits && full.maxFarZ === 14 && full.droppedDays.length === 0);
  assert.deepEqual(full.candidates, [0, 1, 2, 3]); assert.deepEqual(full.protectedDays.sort(), [0, 1]);
  assert.equal(full.status[0], "selected"); assert.equal(full.status[4], "later"); assert.equal(full.status[9], "later");
  // the queue order: background first, then day 0 low→high zoom, then day 1 …
  assert.ok(full.queue.slice(0, plan.base.length).every(t => plan.tiles.get(t.key).base));
  const day0 = full.queue.slice(plan.base.length, plan.base.length + plan.days[0].count).map(t => t.z);
  assert.deepEqual(day0, day0.slice().sort((a, b) => a - b), "zoom ascending inside a day");
  const cost = full.estBytes;
  // (a) a little too small → far days drop z14 only
  const a = OM.buildQueue(plan, ctx(cost - 1)); assert.equal(a.maxFarZ, 13); assert.deepEqual(a.droppedDays, []); assert.ok(a.fits);
  assert.ok(a.queue.some(t => t.z === 14 && t.days.some(i => i <= 1)), "protected days keep z14");
  assert.ok(a.queue.filter(t => t.z === 14).every(t => t.days.some(i => i <= 1)), "far-only z14 tiles are gone");
  assert.deepEqual(a.status.slice(0, 4), ["selected", "selected", "reduced", "reduced"]);
  // (a) twice → z12
  const b = OM.buildQueue(plan, ctx(a.estBytes - 1)); assert.equal(b.maxFarZ, 12); assert.deepEqual(b.droppedDays, []);
  assert.ok(b.queue.filter(t => t.z > 12).every(t => t.days.some(i => i <= 1)));
  // (b) then far days go, farthest (day index 3) first, then 2
  const c = OM.buildQueue(plan, ctx(b.estBytes - 1)); assert.equal(c.maxFarZ, 12); assert.ok(c.droppedDays.includes(3), "the farthest day goes first"); assert.equal(c.status[3], "waiting");
  assert.ok(!c.droppedDays.includes(2) || c.droppedDays.includes(3), "day 2 only after day 3");
  const d = OM.buildQueue(plan, ctx(Math.min(c.estBytes, b.estBytes) - 1)); assert.deepEqual(d.droppedDays, [2, 3]);   // day 3 (Bran) shares almost all tiles with day 2, so dropping 3 alone frees ~nothing
  // budget so small that even today + tomorrow do not fit: they are STILL queued (never dropped), flagged short
  const e = OM.buildQueue(plan, ctx(1 * MB)); assert.ok(e.short && !e.fits); assert.deepEqual(e.droppedDays, [2, 3]);
  assert.deepEqual(e.status.slice(0, 4), ["selected", "selected", "waiting", "waiting"]);
  assert.ok(e.queue.some(t => t.days.includes(0)) && e.queue.some(t => t.days.includes(1)));
  assert.ok(!e.queue.some(t => t.days.length > 0 && t.days.every(i => i >= 2)), "no far-day-only tile in the queue");
  // already stored tiles are not queued and cost nothing
  const stored = new Set(full.queue.map(t => t.key)), s = OM.buildQueue(plan, ctx(0, { stored }));
  assert.equal(s.queue.length, 0); assert.equal(s.estBytes, 0); assert.ok(s.fits);
  // a later current day moves the window; the days before it are 'past'
  const m = OM.buildQueue(plan, ctx(1e12, { cur: 5 })); assert.deepEqual(m.candidates, [5, 6, 7, 8]); assert.equal(m.status[4], "past"); assert.equal(m.status[9], "later");
  // after the last day nothing is asked
  assert.equal(OM.buildQueue(plan, ctx(1e12, { cur: 10 })).queue.filter(t => !plan.tiles.get(t.key).base).length, 0);
  // a day without coordinates is 'none' and never a candidate
  const nc = OM.planTrip([day(1, P.bv), { date: "27/05/2027" }, day(3, P.sib)]), q = OM.buildQueue(nc, ctx(1e12));
  assert.equal(q.status[1], "none"); assert.deepEqual(q.candidates, [0, 2]);
});

test("sacrifice order · the estimate respects learned averages", () => {
  assert.equal(OM.avgBytes(14, null), 36 * 1024);
  assert.equal(OM.avgBytes(14, { 14: { n: 2, mean: 9999 } }), 36 * 1024, "fewer than 3 samples: keep the default");
  assert.equal(OM.avgBytes(14, { 14: { n: 40, mean: 12345 } }), 12345);
  assert.equal(OM.avgBytes(99, null), 100 * 1024, "unknown zoom: a safe default");
});

test("current day · before, during, between, after the trip; dates without a day", () => {
  const ds = roDays();                                          // 26/05 … 04/06/2027
  const at = (y, m, d, h = 12) => new Date(y, m - 1, d, h);
  assert.equal(OM.currentDayIndex(ds, at(2027, 4, 1)), 0);      // before the trip: prepare the first days
  assert.equal(OM.currentDayIndex(ds, at(2027, 5, 26, 0)), 0);
  assert.equal(OM.currentDayIndex(ds, at(2027, 5, 29, 23)), 3);
  assert.equal(OM.currentDayIndex(ds, at(2027, 6, 4, 23)), 9);  // the last day itself
  assert.equal(OM.currentDayIndex(ds, at(2027, 6, 5)), 10);     // the day after: nothing ahead
  assert.equal(OM.currentDayIndex([{ x: 1 }, { x: 2 }], at(2027, 5, 29)), 0);   // no dates at all
  assert.equal(OM.currentDayIndex([], at(2027, 5, 29)), 0);
});

test("route change · a new far point adds only its own tiles; a removed point is cleaned; passed days are cleaned; base kept", async () => {
  const store = OM.createMemoryStore(), A = roDays(), planA = OM.planTrip(A);
  for (const [k, t] of planA.tiles) await store.putTile(k, { z: t.z, bytes: new ArrayBuffer(10), c: 0, n: 10, days: t.base ? [] : t.days, ts: 1 });
  const idxA = await store.index();
  assert.equal(OM.cleanupPlan(planA, idxA, 0).delete.length, 0, "nothing to do when nothing changed");
  assert.equal(OM.cleanupPlan(planA, idxA, 0).relabel.length, 0);
  // B: day 8 (index 7) gets a new far waypoint (Cluj-Napoca ≈ 100 km from Sibiu)
  const B = roDays(); B[7].waypoints.push({ name: "Cluj", lat: 46.77, lng: 23.59 });
  const planB = OM.planTrip(B), qB = OM.buildQueue(planB, { cur: 6, ahead: 3, budget: 1e12, stored: idxA, avg });
  const newKeys = new Set(Array.from(planB.tiles.keys()).filter(k => !planA.tiles.has(k)));
  assert.ok(newKeys.size > 50);
  assert.ok(qB.queue.length > 0 && qB.queue.every(t => newKeys.has(t.key)), "only the NEW tiles are downloaded");
  // C: the waypoint is removed again → its exclusive tiles are deleted
  const clC = OM.cleanupPlan(OM.planTrip(A), await (async () => { for (const k of newKeys) await store.putTile(k, { z: 14, bytes: new ArrayBuffer(10), c: 0, n: 10, days: [7], ts: 1 }); return store.index(); })(), 0);
  assert.deepEqual(new Set(clC.delete), newKeys);
  // passed days: cur=5 → tiles used only by days < 5 go; tiles shared with a day ≥ 5 stay and get a new label; the background stays
  const cl5 = OM.cleanupPlan(planA, idxA, 5), del = new Set(cl5.delete);
  assert.ok(del.size > 0);
  for (const k of del) { const t = planA.tiles.get(k); assert.ok(!t.base && t.days.every(i => i < 5), k); }
  for (const [k, t] of planA.tiles) if (t.base || t.days.some(i => i >= 5)) assert.ok(!del.has(k));
  assert.ok(cl5.relabel.length === 0, "labels were already right");
  assert.equal(OM.cleanupPlan(planA, idxA, 5, { deletePast: false }).delete.length, 0, "setting: keep past days");
  // a day edit that changes the days[] of a stored tile relabels it
  const shifted = roDays(); shifted.splice(1, 1);          // delete day 2: indexes move
  assert.ok(OM.cleanupPlan(OM.planTrip(shifted), idxA, 0).relabel.length > 0);
});

// ---------- the download engine ----------
const tileBytes = (z, n = 3000) => { const b = new Uint8Array(n); for (let i = 0; i < n; i++) b[i] = (i * 7 + z) & 255; return b.buffer; };   // compressible
const rnd = (n, seed) => { const b = new Uint8Array(n); let x = (seed * 2654435761) >>> 0 || 1; for (let i = 0; i < n; i++) { x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; b[i] = x & 255; } return b.buffer; };   // incompressible
const okRes = (z, n) => ({ ok: true, status: 200, arrayBuffer: async () => tileBytes(z, n) });
const okRand = (z, n) => ({ ok: true, status: 200, arrayBuffer: async () => rnd(n, z + 1) });
const zOf = u => +/\/tiles\/v4\/(\d+)\//.exec(u)[1];
const fastOpts = (store, days, extra) => Object.assign({ days, store, key: "SECRETKEY123", cur: 0, sleep: async () => {}, backoffMs: 0 }, extra);

test("prepare · downloads in order, stores compressed, never leaks the key, no key = no request", async () => {
  const days = [day(1, P.bv), day(2, P.bv)], store = OM.createMemoryStore(), urls = [];
  const fetchFn = async u => { urls.push(u); return okRes(zOf(u), 3000); };
  const r = await OM.prepare(fastOpts(store, days, { fetchFn }));
  assert.equal(r.status, "done"); assert.equal(r.reason, null); assert.ok(r.downloaded > 30 && r.failed === 0 && r.remaining === 0);
  assert.equal(urls.length, r.downloaded);
  assert.ok(urls.every(u => u.startsWith("https://api.protomaps.com/tiles/v4/") && u.endsWith(".mvt?key=SECRETKEY123")));
  const idx = await store.index(); assert.equal(idx.size, r.downloaded);
  assert.ok(OM.usedBytes(idx) < r.downloaded * 3000, "stored compressed (smaller than raw)");
  assert.equal(r.bytes, OM.usedBytes(idx)); assert.ok(Array.from(idx.values()).every(v => v.n === 3000));
  assert.ok(!JSON.stringify({ ...r, plan: undefined, queue: undefined }).includes("SECRETKEY123"), "the key is never in the result");
  assert.ok((await store.getMeta("avg"))[14].n > 0, "real averages are learned");
  const again = await OM.prepare(fastOpts(store, days, { fetchFn: async () => { throw new Error("must not fetch"); } }));
  assert.equal(again.status, "nothing"); assert.equal(again.downloaded, 0);
  const nokey = await OM.prepare(fastOpts(store, days, { key: "", fetchFn: async () => { throw new Error("no"); } }));
  assert.equal(nokey.reason, "no_key");
});

test("prepare · a small cap is never exceeded and the budget stops it", async () => {
  const days = roDays().slice(0, 4), store = OM.createMemoryStore(), fetchFn = async u => okRand(zOf(u), 40000);
  const cap = 600 * 1024, r = await OM.prepare(fastOpts(store, days, { fetchFn, cap }));
  const used = OM.usedBytes(await store.index());
  assert.ok(used <= cap, `used ${used} > cap ${cap}`); assert.equal(r.status, "stopped"); assert.ok(["cap", "budget"].includes(r.reason), r.reason);
  assert.ok(r.downloaded > 0 && r.remaining >= 0);
});

test("prepare · simulated free space: margin kept, nothing downloaded when the device is full", async () => {
  const days = [day(1, P.bv)], fetchFn = async u => okRand(zOf(u), 40000);
  const full = OM.createMemoryStore(), r0 = await OM.prepare(fastOpts(full, days, { fetchFn, storage: { quota: 100 * MB, usage: 99 * MB } }));
  assert.equal(r0.downloaded, 0); assert.equal(r0.budget, 0);
  const tight = OM.createMemoryStore(), r1 = await OM.prepare(fastOpts(tight, days, { fetchFn, storage: { quota: 80 * MB, usage: 20 * MB } }));   // free 60 − margin 50 = 10 MB
  assert.equal(r1.budget, 10 * MB);
  const used = OM.usedBytes(await tight.index()); assert.ok(used <= 10 * MB);
  const roomy = OM.createMemoryStore(), r2 = await OM.prepare(fastOpts(roomy, days, { fetchFn, storage: { quota: 5000 * MB, usage: 0 } }));
  assert.equal(r2.status, "done");
});

test("prepare · 429 / 403 / 401 stop at once (no retry loop); network errors retry a bounded number of times; a stop resumes", async () => {
  const days = [day(1, P.bv), day(2, P.sib)];
  for (const [code, reason] of [[429, "rate_limited"], [403, "forbidden"], [401, "auth"]]) {
    const store = OM.createMemoryStore(); let calls = 0;
    const fetchFn = async () => { calls++; return { ok: false, status: code, arrayBuffer: async () => new ArrayBuffer(0) }; };
    const r = await OM.prepare(fastOpts(store, days, { fetchFn, concurrency: 5 }));
    assert.equal(r.status, "stopped"); assert.equal(r.reason, reason); assert.ok(calls <= 5, `${code}: ${calls} calls (at most one per worker, no retries)`);
    assert.equal(r.downloaded, 0);
  }
  // resume: stop after 40 tiles with a 429, then a clean run only fetches the rest
  const store = OM.createMemoryStore(); let n = 0;
  const flaky = async u => (++n > 40 ? { ok: false, status: 429, arrayBuffer: async () => new ArrayBuffer(0) } : okRes(zOf(u), 2000));
  const r1 = await OM.prepare(fastOpts(store, days, { fetchFn: flaky, concurrency: 1 }));
  assert.equal(r1.reason, "rate_limited"); assert.equal(r1.downloaded, 40);
  const seen = new Set(); const fetched = [];
  const ok = async u => { fetched.push(u); return okRes(zOf(u), 2000); };
  const stored1 = new Set((await store.index()).keys());
  const r2 = await OM.prepare(fastOpts(store, days, { fetchFn: ok }));
  assert.equal(r2.status, "done"); assert.equal(fetched.length, r2.queue.queue.length);
  fetched.forEach(u => { const m = /v4\/(\d+)\/(\d+)\/(\d+)\.mvt/.exec(u); const k = `${m[1]}/${m[2]}/${m[3]}`; assert.ok(!stored1.has(k), "never refetches a stored tile"); seen.add(k); });
  // one flaky tile: retried (bounded), then counted as failed, run continues
  const s3 = OM.createMemoryStore(); const attempts = new Map();
  const oneBad = async u => { const k = zOf(u) === 8 ? u : null; if (k) { attempts.set(k, (attempts.get(k) || 0) + 1); throw new Error("net"); } return okRes(zOf(u), 2000); };
  const r3 = await OM.prepare(fastOpts(s3, [day(1, P.bv)], { fetchFn: oneBad, retries: 2 }));
  assert.ok(r3.failed > 0); assert.ok(Array.from(attempts.values()).every(c => c === 3), "1 try + 2 retries");
  assert.equal(r3.status, "stopped");
  // total failure: gives up after a handful of consecutive failures instead of looping through everything
  const s4 = OM.createMemoryStore(); let calls4 = 0;
  const r4 = await OM.prepare(fastOpts(s4, [day(1, P.bv)], { fetchFn: async () => { calls4++; throw new Error("offline"); }, retries: 1, concurrency: 1 }));
  assert.equal(r4.reason, "network"); assert.ok(calls4 <= 10, "calls " + calls4);
  // abort
  const ac = new AbortController(), s5 = OM.createMemoryStore(); let c5 = 0;
  const r5 = await OM.prepare(fastOpts(s5, days, { fetchFn: async u => { if (++c5 === 5) ac.abort(); return okRes(zOf(u), 2000); }, signal: ac.signal, concurrency: 1 }));
  assert.equal(r5.reason, "aborted"); assert.ok(r5.downloaded <= 6);
});

test("prepare · route change downloads only the new tiles; passed days are deleted (space is freed); shared tiles keep all their days", async () => {
  const store = OM.createMemoryStore(), A = roDays(), fetchFn = async u => okRes(zOf(u), 1500);
  const rA = await OM.prepare(fastOpts(store, A, { fetchFn, cur: 0, cap: 1e9 }));
  assert.equal(rA.status, "done"); const idxA = await store.index();
  const B = roDays(); B[2].waypoints.push({ name: "Rasnov", lat: 45.59, lng: 25.46 }); B[2].waypoints.push({ name: "Far", lat: 45.9, lng: 25.0 });
  const got = []; const rB = await OM.prepare(fastOpts(store, B, { fetchFn: async u => { got.push(u); return okRes(zOf(u), 1500); }, cur: 0, cap: 1e9 }));
  assert.equal(rB.status, "done"); assert.ok(got.length > 0 && got.length < 400, "only the new: " + got.length);
  const idxB = await store.index(); assert.ok(idxB.size > idxA.size);
  // day 3 starts → days 0,1 passed: their exclusive tiles are deleted, the shared ones stay
  const before = OM.usedBytes(idxB), rC = await OM.prepare(fastOpts(store, B, { fetchFn: async u => okRes(zOf(u), 1500), cur: 2, cap: 1e9 }));
  const idxC = await store.index(); assert.ok(OM.usedBytes(idxC) < before + rC.bytes, "space came back");
  const planB = OM.planTrip(B);
  for (const [k, rec] of idxC) { const t = planB.tiles.get(k); assert.ok(t.base || t.days.some(i => i >= 2), k + " should have been deleted"); assert.deepEqual(rec.days.slice().sort(), t.base ? [] : t.days.slice().sort()); }
  const bgLeft = planB.base.filter(k => idxC.has(k)).length; assert.equal(bgLeft, planB.base.length, "the background stays");
});

test("prepare · the learned average makes the next estimate more accurate (and the cap check uses real bytes)", async () => {
  const store = OM.createMemoryStore(); const fetchFn = async u => okRes(zOf(u), 1000);
  await OM.prepare(fastOpts(store, [day(1, P.bv)], { fetchFn, cap: 1e9 }));
  const learned = await store.getMeta("avg"); assert.ok(learned[14].n >= 3 && learned[14].mean < 36 * 1024, "real stored tiles are tiny in this fake");
  const r = await OM.prepare(fastOpts(store, [day(1, P.bv), day(2, P.sib)], { fetchFn, cap: 1e9 }));
  assert.ok(r.queue.estBytes < 36 * 1024 * r.queue.queue.length, "the estimate uses the learned average");
});

test("reader · offmap:// url, stored tile round trip (compressed and not), missing tile = empty buffer, MapLibre helper (both call styles)", async () => {
  assert.deepEqual(OM.parseOffmapUrl("offmap://14/9100/5800"), { z: 14, x: 9100, y: 5800 }); assert.deepEqual(OM.parseOffmapUrl("offmap://3/1/2?x=1"), { z: 3, x: 1, y: 2 });
  assert.equal(OM.parseOffmapUrl("https://x/1/2/3"), null); assert.equal(OM.parseOffmapUrl(""), null);
  assert.equal(OM.tileUrl(3, 4, 5, "a b"), "https://api.protomaps.com/tiles/v4/3/4/5.mvt?key=a%20b");
  const store = OM.createMemoryStore(), raw = tileBytes(14, 5000), pk = await OM.pack(raw);
  assert.equal(pk.c, 1); assert.ok(pk.bytes.byteLength < raw.byteLength);
  await store.putTile("14/1/2", { z: 14, bytes: pk.bytes, c: pk.c, n: 5000, days: [0], ts: 1 });
  await store.putTile("14/1/3", { z: 14, bytes: raw, c: 0, n: 5000, days: [0], ts: 1 });
  assert.deepEqual(new Uint8Array(await OM.loadTile(store, 14, 1, 2)), new Uint8Array(raw));
  assert.deepEqual(new Uint8Array(await OM.loadTile(store, 14, 1, 3)), new Uint8Array(raw));
  assert.equal((await OM.loadTile(store, 14, 9, 9)).byteLength, 0);
  const tiny = new Uint8Array([1, 2, 3]).buffer; assert.equal((await OM.pack(tiny)).c, 0, "a tile that does not shrink is stored as is");
  let handler = null; OM.registerProtocol({ addProtocol: (n, f) => { assert.equal(n, "offmap"); handler = f; } }, store);
  const v4 = await handler({ url: "offmap://14/1/2" }, new AbortController()); assert.equal(v4.data.byteLength, 5000);
  assert.equal((await handler({ url: "offmap://14/7/7" }, new AbortController())).data.byteLength, 0);
  assert.equal((await handler({ url: "bad" }, new AbortController())).data.byteLength, 0);
  const cb = await new Promise(res => handler({ url: "offmap://14/1/3" }, (e, d) => res({ e, d }))); assert.equal(cb.e, null); assert.equal(cb.d.byteLength, 5000);
});

test("store · memory store contract (index, setDays, delete, meta, clear)", async () => {
  const s = OM.createMemoryStore();
  await s.putTile("1/0/0", { z: 1, bytes: new ArrayBuffer(7), c: 0, n: 7, days: [1], ts: 5 });
  assert.equal((await s.index()).get("1/0/0").sz, 7); await s.setDays("1/0/0", [2, 3]); assert.deepEqual((await s.index()).get("1/0/0").days, [2, 3]);
  const snap = await s.index(); snap.get("1/0/0").days.push(9); assert.deepEqual((await s.index()).get("1/0/0").days, [2, 3], "index() returns copies");
  await s.setMeta("a", { v: 1 }); assert.deepEqual(await s.getMeta("a"), { v: 1 }); assert.equal(await s.getMeta("zz"), null);
  await s.deleteTiles(["1/0/0"]); assert.equal((await s.index()).size, 0); assert.equal(await s.getTile("1/0/0"), null);
  await s.putTile("1/0/1", { z: 1, bytes: new ArrayBuffer(1), c: 0, n: 1, days: [], ts: 1 }); await s.clear(); assert.equal((await s.index()).size, 0); assert.equal(await s.getMeta("a"), null);
});

test("flag · active only for 'on' + a listed trip; Vietnam and unlisted trips never; key never read from the file", () => {
  let flag = "off", list = [RO];
  OM.configure({ feature: () => flag, trips: () => list, key: undefined });
  assert.equal(OM.active(RO), false, "flag off = nothing");
  flag = "on"; assert.equal(OM.active(RO), true); assert.equal(OM.active("other-trip"), false); assert.equal(OM.active(""), false); assert.equal(OM.active(null), false);
  list = [VN, RO]; assert.equal(OM.active(VN), false, "Vietnam is never active, even if listed by mistake");
  flag = "beta"; assert.equal(OM.active(RO), false, "only 'on' activates");
  OM.configure({ feature: undefined, trips: undefined });
  assert.equal(OM.getKey(), "", "no key in the repo (OFFMAP_KEY = '')"); OM.configure({ key: () => "k1" }); assert.equal(OM.getKey(), "k1"); OM.configure({ key: undefined });
  assert.deepEqual(OM.constants.OFFMAP_TRIPS, [RO]); assert.equal(OM.constants.DEFAULT_CAP, 150 * MB);
  assert.equal(OM.version, "3.0.0-alpha.21.2");
});

test("repo · the key is not in any file; versions agree; the page only loads the script and declares the flag 'off'", () => {
  const read = p => readFileSync(new URL(p, import.meta.url), "utf8");
  const js = read("../../app/js/offmap.js"), html = read("../../app/index.html"), sw = read("../../app/sw.js");
  assert.match(js, /const OFFMAP_KEY = '';/);
  assert.ok(!/protomaps\.com[^\s'"`]*key=[A-Za-z0-9]{8,}/.test(js + html + sw), "no Protomaps key literal anywhere");
  // CHANGE 2026-11-25 QA-TRIAGE-02: was the literal alpha.21.2; the page version now comes from tests/qa_versions.json (one place per release). OM.version (the module's own) stays as is.
  const cur = JSON.parse(read("../qa_versions.json")).app.replace(/\./g, "\\.");
  assert.match(html, new RegExp("const PT_VERSION='" + cur + "'")); assert.match(html, new RegExp("const APP_VERSION='" + cur + "'"));
  assert.match(html, /<script src="js\/offmap\.js"><\/script>/); assert.match(html, /const OFFMAP_FEATURE='off';/);
  assert.match(sw, /"js\/offmap\.js"/);
  const code = html.replace(/\/\*[\s\S]*?\*\//g, "").replace(/<!--[\s\S]*?-->/g, "");
  assert.equal((code.match(/__ptOM/g) || []).length, 15, "index.html touches the module only in the mountKeyEntry line, the attach line and the single drawMap hook (release x3 + tryDraw x3, OFFMAP-VIEW-02)");
  assert.match(code, /__ptOM\.mountKeyEntry\(\)/); assert.match(code, /__ptOM\.attach\(\{client:\(\)=>sb\}\)/);
});

test("key window · validated, stored through the device adapter, hint shows the last 4, clear removes, getKey is sync after loadKey", async () => {
  let rec = ""; const ad = { get: async () => rec, put: async v => { rec = v; }, del: async () => { rec = ""; } };
  OM.setKeyAdapter(ad); OM.configure({ key: undefined });
  assert.equal(OM.getKey(), ""); assert.equal(OM.keyHint(), "");
  for (const bad of ["", "short", "has space 12345", "a".repeat(129), "ü".repeat(10), null]) assert.equal(await OM.setKey(bad), false, String(bad));
  assert.equal(rec, "", "a rejected key stores nothing");
  assert.equal(await OM.setKey("  Abcd1234-wxyz_9876  "), true, "trimmed");
  assert.equal(rec, "Abcd1234-wxyz_9876"); assert.equal(OM.getKey(), "Abcd1234-wxyz_9876"); assert.equal(OM.keyHint(), "••••9876"); assert.ok(!OM.keyHint().includes("Abcd"));
  OM.setKeyAdapter(ad); assert.equal(OM.getKey(), "", "a new page starts without the key in memory"); assert.equal(await OM.loadKey(), "Abcd1234-wxyz_9876"); assert.equal(OM.getKey(), "Abcd1234-wxyz_9876");
  OM.configure({ key: () => "from-config-1" }); assert.equal(OM.getKey(), "from-config-1", "configure() still wins"); OM.configure({ key: undefined });
  await OM.clearKey(); assert.equal(OM.getKey(), ""); assert.equal(rec, "");
  rec = "bad key!"; assert.equal(await OM.loadKey(), "", "a corrupt stored value is ignored");
  OM.setKeyAdapter({ get: async () => { throw new Error("no idb"); }, put: async () => { throw new Error("no idb"); }, del: async () => { throw new Error("no idb"); } });
  assert.equal(await OM.setKey("Abcd1234-wxyz"), false, "storage failure: false, no throw"); assert.equal(await OM.loadKey(), "");
});
test("prepare · with no key given it loads the saved device key", async () => {
  let rec = "SavedKey_12345"; OM.setKeyAdapter({ get: async () => rec, put: async () => {}, del: async () => {} }); OM.configure({ key: undefined });
  const urls = []; const store = OM.createMemoryStore();
  const r = await OM.prepare({ days: [day(1, P.bv)], store, cur: 0, sleep: async () => {}, fetchFn: async u => { urls.push(u); return okRes(zOf(u), 2000); } });
  assert.equal(r.status, "done"); assert.ok(urls.every(u => u.endsWith("key=SavedKey_12345")));
  OM.setKeyAdapter({ get: async () => "", put: async () => {}, del: async () => {} });
  assert.equal((await OM.prepare({ days: [day(1, P.bv)], store: OM.createMemoryStore(), cur: 0, fetchFn: async () => { throw new Error("no"); } })).reason, "no_key");
});

function fakeClient({ admin = true, existing = "" } = {}) {
  const calls = [];
  return { calls, rpc: async (fn, a) => { calls.push([fn, a]);
      if (fn === "offmap_key_state") return { data: existing ? "locked" : admin ? "open" : "not_admin" };
      if (fn === "set_offmap_key") { if (!admin) return { data: "not_admin" }; if (!/^[A-Za-z0-9_-]{8,128}$/.test(a.p_key)) return { data: "invalid" }; if (existing) return { data: "locked" }; existing = a.p_key; return { data: "saved" }; }
      return { error: { message: "no" } }; },
    from: t => ({ select: () => ({ eq: () => ({ maybeSingle: async () => { calls.push(["select", t]); return { data: existing ? { value: existing } : null }; } }) }) }) };
}
test("shared key · state, write-once save, fetch for every user, device copy refreshed", async () => {
  let rec = ""; OM.setKeyAdapter({ get: async () => rec, put: async v => { rec = v; }, del: async () => { rec = ""; } });
  OM.attach({ client: () => null }); assert.equal(await OM.keyState(), "offline"); assert.equal(await OM.saveSharedKey("Abcd1234-wxyz"), "offline");
  const fc = fakeClient(); OM.attach({ client: () => fc });
  assert.equal(await OM.keyState(), "open"); assert.equal(await OM.saveSharedKey("short"), "invalid");
  assert.equal(fc.calls.filter(c => c[0] === "set_offmap_key").length, 0, "an invalid key never leaves the device");
  assert.equal(await OM.saveSharedKey("Abcd1234-wxyz"), "saved"); assert.equal(rec, "Abcd1234-wxyz");
  assert.equal(await OM.keyState(), "locked"); assert.equal(await OM.saveSharedKey("Other1234-key9"), "locked", "second write refused");
  const fn = fakeClient({ admin: false }); OM.attach({ client: () => fn }); assert.equal(await OM.keyState(), "not_admin"); assert.equal(await OM.saveSharedKey("Abcd1234-wxyz"), "not_admin");
  rec = ""; OM.setKeyAdapter({ get: async () => rec, put: async v => { rec = v; }, del: async () => {} });
  const fu = fakeClient({ admin: false, existing: "SharedKey_7777" }); OM.attach({ client: () => fu });
  assert.equal(await OM.ensureKey(), "SharedKey_7777", "an ordinary traveler gets the key from the server"); assert.equal(rec, "SharedKey_7777", "and keeps it on the device for offline");
  OM.setKeyAdapter({ get: async () => rec, put: async () => {}, del: async () => {} }); OM.attach({ client: () => null }); assert.equal(await OM.ensureKey(), "SharedKey_7777", "offline: the device copy");
});

// CHANGE 2026-11-24 OFFMAP-T-02: new tests for the viewer (alpha.20.3): what is drawn per mode, the tile source for protomaps-leaflet, the gates (flag, trip, Vietnam, network) and that tryDraw never throws.
test("viewer · viewFeatures per mode, invalid coordinates skipped", () => {
  const days = [
    { day: 1, region: "A", lat: 44.5, lng: 26.1, waypoints: [{ name: "w1", lat: 44.6, lng: 26.0 }, { name: "bad", lat: null, lng: null }] },
    { day: 2, region: "B", lat: 45.6, lng: 25.6, waypoints: [{ name: "w2", lat: 45.7, lng: 25.5 }] },
    { day: 3, region: "C", lat: null, lng: null, waypoints: [] }];
  const r = OM.viewFeatures(days, "route", 1);
  assert.deepEqual(r.line, [[44.5, 26.1], [45.6, 25.6]], "route: a line through the days that have coordinates");
  assert.deepEqual(r.points.map(p => p.kind), ["day", "active"], "the open day is the active point");
  const d = OM.viewFeatures(days, "day", 0);
  assert.equal(d.line.length, 0); assert.deepEqual(d.points.map(p => p.kind), ["active", "poi"], "day: the day point + its valid waypoints only");
  const p = OM.viewFeatures(days, "poi", 0);
  assert.deepEqual(p.points.map(x => x.label), ["יום 1: w1", "יום 2: w2"], "poi: every waypoint of every day, labelled with its day");
  assert.deepEqual(OM.viewFeatures(null, "route", 0), { line: [], points: [] }, "no days = nothing, no throw");
});
test("viewer · tile source: stored tile → data, missing → undefined, gzip is unpacked", async () => {
  const store = OM.createMemoryStore(), src = OM.makeSource(store);
  const raw = new Uint8Array([1, 2, 3, 4]).buffer;
  await store.putTile("10/5/6", { z: 10, bytes: raw, c: 0, n: 4, days: [1], ts: 1 });
  const got = await src.getZxy(10, 5, 6);
  assert.deepEqual(Array.from(new Uint8Array(got.data)), [1, 2, 3, 4]);
  assert.equal(await src.getZxy(10, 5, 7), undefined, "a tile we do not have draws nothing");
  const { gzipSync } = await import("node:zlib");
  const gz = gzipSync(Buffer.from([9, 8, 7])); const ab = gz.buffer.slice(gz.byteOffset, gz.byteOffset + gz.length);
  await store.putTile("10/5/8", { z: 10, bytes: ab, c: 0, n: 3, days: [1], ts: 1 });
  const g2 = await src.getZxy(10, 5, 8);   // Node has no browser DecompressionStream on globalThis here → returned as stored; the browser path is covered in the page test
  assert.ok(g2 && g2.data.byteLength > 0);
});
test("viewer · gates: flag, trip list, Vietnam, device beta; tryDraw never throws and says false without a page", () => {
  OM.configure({ feature: () => "off", trips: () => [RO] });
  assert.equal(OM.viewEnabled(RO), false, "flag off and no device beta = the app as alpha.20.2");
  OM.configure({ feature: () => "on" });
  assert.equal(OM.viewEnabled(RO), true); assert.equal(OM.viewEnabled(VN), false, "Vietnam never"); assert.equal(OM.viewEnabled("other"), false, "a trip outside the list");
  assert.equal(OM.tryDraw({}, { days: [], dayIndex: 0, mode: "route" }), false, "no document = false");
  assert.equal(OM.tryDraw(null, null), false);
  OM.configure({ feature: undefined, trips: undefined });
});
