/* Lonely Planner · OFFMAP – automatic offline map tiles prepared on the device from the traveler's own route (core) · version 3.0.0-alpha.20.2
   CHANGE 2026-11-24 OFFMAP-KEY-01: what changed from alpha.19: an in-app window to enter / replace / delete the Protomaps key on THIS device (setKey, clearKey, keyHint, openKeyDialog, mountKeyEntry). It opens only when the address ends with #offmapkey (like #f22beta); the key is saved in a small device-level IndexedDB ("pt-_device-offmap": the app wraps localStorage per trip and drops writes before the trip is known, so localStorage cannot hold it), loaded at start into memory so getKey() stays synchronous (never in the address, never sent anywhere, never in the repo). Without that hash nothing is shown: the app is as alpha.19.
   CHANGE 2026-11-24 OFFMAP-01: new file (no previous version). Conversation 1 of 3 (spec: claude/Plan_Travel_OFFMAP_spec.md draft 2, approved 24/11). Contains ONLY the core, no screens and no map drawing:
   (1) pure functions: tile math, per-day corridor + tile list from tripData (planTrip), space budget (computeBudget), download queue with the sacrifice order (buildQueue), clean-up / route-change diff (cleanupPlan),
   current-day index; (2) storage: IndexedDB per trip ("pt-<trip>-offmap": stores tiles / index / meta) + an in-memory twin for tests; (3) prepare(): the download engine (4-6 parallel, retry with back-off,
   stops on 429/403/401, resumes from what is stored); (4) the offmap://z/x/y tile reader (+ MapLibre addProtocol helper). Nothing in the app calls this file yet: index.html only loads it (<script>) and
   declares OFFMAP_FEATURE='off'; drawMap() is untouched (conversation 2). Loading the file has no side effect except defining window.__ptOM.
   Active ONLY when OFFMAP_FEATURE === 'on' and the open trip is in OFFMAP_TRIPS (Vietnam is never active). Off / other trip = the app exactly as alpha.18.13.
   The Protomaps key is NOT in this file (public repo): OFFMAP_KEY stays '' until Or approves; on a device it is entered through the key window (#offmapkey) and kept in the device IndexedDB (never committed). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.20.2';

  /* ---------- constants ---------- */
  const OFFMAP_KEY = '';                                   /* Protomaps API key. EMPTY on purpose: not committed without Or's explicit approval (see report). */
  const OFFMAP_TRIPS = ['fd5c2b13-cdc0-455e-9c12-b52f2e45a334'];   /* the Romania pilot "30 שנה לגיוס רומניה"; Vietnam is never listed */
  const VN_TRIP = 'f0200000-0000-4000-8000-000000000001';
  const MB = 1024 * 1024;
  const DEFAULT_CAP = 150 * MB;                            /* per-trip cap (spec §2), changeable by the user later */
  const TILE_URL = 'https://api.protomaps.com/tiles/v4/{z}/{x}/{y}.mvt?key={key}';

  /* corridor defaults (spec §4.1): z<=10 15–30 km (25), z11–12 8 km, z13–14 3 km. Background = low zooms over the whole trip box. */
  const DEFAULTS = {
    baseZooms: [4, 5, 6, 7], dayZooms: [8, 9, 10, 11, 12, 13, 14],
    buffers: { 8: 25, 9: 25, 10: 25, 11: 8, 12: 8, 13: 3, 14: 3 },
    basePadKm: 30, maxBaseTiles: 600,
    maxLegKm: 150,           /* a leg longer than this (flight / transfer between far points) is not drawn as a corridor; only the points themselves get tiles */
    ahead: 3,                /* the current day + up to 3 days ahead (spec §4.4) */
    minFarZoom: 12,          /* sacrifice (a): far days drop from 14 → 13 → 12 */
    marginMinBytes: 50 * MB, marginFrac: 0.10   /* spec §4.3: safety margin = max(50 MB, 10% of the free space) */
  };
  /* average bytes per tile by zoom. 6/8/10/12/14 measured on Or's phone 24/11 (decoded size, around Brașov); 7/9/11/13 interpolated by the probe; 4/5 ASSUMED (few tiles). Learned averages replace these. */
  const DEFAULT_AVG_KB = { 4: 120, 5: 120, 6: 110, 7: 227, 8: 348, 9: 208, 10: 82, 11: 50, 12: 20, 13: 27, 14: 36 };

  /* ---------- tile math (Web Mercator, slippy-map scheme) ---------- */
  const MAXLAT = 85.0511287798;
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lon2x(lng, z) { const n = 2 ** z; return clamp(Math.floor((lng + 180) / 360 * n), 0, n - 1); }
  function lat2y(lat, z) {
    const n = 2 ** z, r = clamp(lat, -MAXLAT, MAXLAT) * Math.PI / 180;
    return clamp(Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n), 0, n - 1);
  }
  function tileKey(z, x, y) { return z + '/' + x + '/' + y; }
  function parseKey(k) { const m = /^(\d+)\/(\d+)\/(\d+)$/.exec(k); return m ? { z: +m[1], x: +m[2], y: +m[3] } : null; }
  function tileNW(z, x, y) {   /* north-west corner of a tile */
    const n = 2 ** z, lng = x / n * 360 - 180, lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI;
    return { lat, lng };
  }
  function tileSizeKm(z, lat) { return 40075.017 * Math.cos(clamp(lat, -MAXLAT, MAXLAT) * Math.PI / 180) / 2 ** z; }
  function distKm(a, b) {
    const R = 6371.0088, p = Math.PI / 180, dLat = (b.lat - a.lat) * p, dLng = (b.lng - a.lng) * p;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * p) * Math.cos(b.lat * p) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  /* strict coordinate check: '' / null / 'abc' are NOT 0 (the app's own valid() accepts '' as 0,0 — we must not) */
  function coord(lat, lng) {
    if (lat === '' || lng === '' || lat == null || lng == null || typeof lat === 'boolean' || typeof lng === 'boolean') return null;
    const a = Number(lat), b = Number(lng);
    return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180 ? { lat: a, lng: b } : null;
  }

  /* ---------- day points and corridor ---------- */
  /* The points of a day in order: the day's own lat/lng (if valid) then its waypoints with valid coordinates. Consecutive duplicates removed. */
  function dayPoints(d) {
    const pts = []; let missing = 0;
    const push = function (p) { const l = pts[pts.length - 1]; if (!l || Math.abs(l.lat - p.lat) > 1e-5 || Math.abs(l.lng - p.lng) > 1e-5) pts.push(p); };
    const own = d && coord(d.lat, d.lng); if (own) push(own);
    ((d && Array.isArray(d.waypoints)) ? d.waypoints : []).forEach(function (w) { const p = w && coord(w.lat, w.lng); if (p) push(p); else missing++; });
    return { points: pts, missing: missing };
  }
  function addRect(set, z, lat, lng, bufKm) {
    const dLat = bufKm / 110.574, dLng = bufKm / (111.320 * Math.max(0.05, Math.cos(clamp(lat, -MAXLAT, MAXLAT) * Math.PI / 180)));
    const x0 = lon2x(lng - dLng, z), x1 = lon2x(lng + dLng, z), y0 = lat2y(lat + dLat, z), y1 = lat2y(lat - dLat, z);
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) set.add(tileKey(z, x, y));
  }
  /* the tiles of a corridor around a polyline at one zoom: a square of ±buf around points sampled every min(buf, tile)/2 km along each leg (conservative: the square is a bit larger than the circle) */
  function coveringTiles(points, z, bufKm, maxLegKm) {
    const set = new Set(); if (!points || !points.length) return set;
    points.forEach(function (p) { addRect(set, z, p.lat, p.lng, bufKm); });
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i], dk = distKm(a, b);
      if (dk > maxLegKm || dk < 1e-6) continue;
      const step = Math.max(0.15, Math.min(bufKm, tileSizeKm(z, (a.lat + b.lat) / 2)) / 2), n = Math.ceil(dk / step);
      for (let s = 1; s < n; s++) { const t = s / n; addRect(set, z, a.lat + (b.lat - a.lat) * t, a.lng + (b.lng - a.lng) * t, bufKm); }
    }
    return set;
  }
  /* planTrip(days, opts): the corridor and the tile list of every day + the shared background.
     → { zooms, base: [keys], days: [{ i, points, missing, noCoords, tiles: {z: [keys]}, count }], tiles: Map(key → {z,x,y,days:[i…], base}), total } */
  function planTrip(days, opts) {
    const o = Object.assign({}, DEFAULTS, opts || {}), list = Array.isArray(days) ? days : [];
    const tiles = new Map(), out = [], all = [];
    const touch = function (k, i, base) {
      let t = tiles.get(k);
      if (!t) { const p = parseKey(k); t = { z: p.z, x: p.x, y: p.y, days: [], base: false }; tiles.set(k, t); }
      if (base) t.base = true; else if (t.days.indexOf(i) < 0) t.days.push(i);
    };
    list.forEach(function (d, i) {
      const dp = dayPoints(d), byZ = {}; let count = 0;
      dp.points.forEach(function (p) { all.push(p); });
      o.dayZooms.forEach(function (z) {
        const arr = dp.points.length ? Array.from(coveringTiles(dp.points, z, o.buffers[z], o.maxLegKm)) : [];
        byZ[z] = arr; count += arr.length; arr.forEach(function (k) { touch(k, i, false); });
      });
      out.push({ i: i, points: dp.points.length, missing: dp.missing, noCoords: dp.points.length === 0, tiles: byZ, count: count });
    });
    const base = [];
    if (all.length) {
      let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
      all.forEach(function (p) { minLat = Math.min(minLat, p.lat); maxLat = Math.max(maxLat, p.lat); minLng = Math.min(minLng, p.lng); maxLng = Math.max(maxLng, p.lng); });
      const midLat = (minLat + maxLat) / 2, dLat = o.basePadKm / 110.574, dLng = o.basePadKm / (111.320 * Math.max(0.05, Math.cos(midLat * Math.PI / 180)));
      o.baseZooms.forEach(function (z) {
        const x0 = lon2x(minLng - dLng, z), x1 = lon2x(maxLng + dLng, z), y0 = lat2y(maxLat + dLat, z), y1 = lat2y(minLat - dLat, z);
        if (base.length && (x1 - x0 + 1) * (y1 - y0 + 1) + base.length > o.maxBaseTiles) return;   /* a huge box (e.g. Israel→Vietnam): keep the lower zooms only */
        for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) { const k = tileKey(z, x, y); base.push(k); touch(k, -1, true); }
      });
    }
    return { zooms: o.baseZooms.concat(o.dayZooms), base: base, days: out, tiles: tiles, total: tiles.size, opts: o };
  }

  /* ---------- sizes and budget ---------- */
  function avgBytes(z, learned) {
    const l = learned && learned[z];
    if (l && l.n >= 3 && l.mean > 0) return l.mean;
    const kb = DEFAULT_AVG_KB[z]; return (kb != null ? kb : 100) * 1024;
  }
  /* budget for NEW downloads = min(cap − used, free − margin); margin = max(50 MB, 10% of the free space). quota/usage = navigator.storage.estimate() (null = unknown → cap only) */
  function computeBudget(o) {
    o = o || {};
    const cap = o.cap != null ? o.cap : DEFAULT_CAP, used = o.used || 0, capLeft = Math.max(0, cap - used);
    if (o.quota == null) return { budget: capLeft, capLeft: capLeft, freeLeft: null, margin: 0 };
    const free = Math.max(0, o.quota - (o.usage || 0)), margin = Math.max(o.marginMinBytes != null ? o.marginMinBytes : DEFAULTS.marginMinBytes, (o.marginFrac != null ? o.marginFrac : DEFAULTS.marginFrac) * free);
    const freeLeft = Math.max(0, free - margin);
    return { budget: Math.min(capLeft, freeLeft), capLeft: capLeft, freeLeft: freeLeft, margin: margin };
  }

  /* ---------- the current day ---------- */
  function dateKey(s) { const m = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/.exec(String(s || '')); return m ? +m[3] * 10000 + +m[2] * 100 + +m[1] : null; }
  /* index of today's trip day: before the trip → 0 (prepare the first days); after the last day → days.length (nothing ahead); days without a date are skipped */
  function currentDayIndex(days, now) {
    const n = now instanceof Date ? now : new Date(now == null ? Date.now() : now), today = n.getFullYear() * 10000 + (n.getMonth() + 1) * 100 + n.getDate();
    let idx = -1, last = -1, any = false;
    (days || []).forEach(function (d, i) { const k = dateKey(d && d.date); if (k == null) return; any = true; if (k <= today) idx = i; last = i; });
    if (!any) return 0;
    if (idx < 0) return 0;
    const lk = dateKey(days[last].date);
    return idx === last && today > lk ? days.length : idx;
  }

  /* ---------- the download queue and the sacrifice order (spec §4.3) ---------- */
  /* buildQueue(plan, ctx): ctx = { cur, ahead, budget, stored: Set|Map of keys already on the device, avg: z → bytes, minFarZoom }
     Order of sacrifice when it does not fit: (a) the highest zooms of FAR days 14 → 13 → 12, (b) far days themselves, farthest first, (c) NEVER the current day and the next day (nor the background).
     → { queue: [{key,z,x,y,days,est}], estBytes, budget, fits, short, maxFarZ, droppedDays, protectedDays, status: [per day] } */
  function buildQueue(plan, ctx) {
    const o = plan.opts || DEFAULTS, ahead = ctx.ahead != null ? ctx.ahead : o.ahead, minFar = ctx.minFarZoom != null ? ctx.minFarZoom : o.minFarZoom;
    const n = plan.days.length, cur = clamp(ctx.cur == null ? 0 : ctx.cur, 0, n), stored = ctx.stored || new Set(), avg = ctx.avg || function (z) { return avgBytes(z); };
    const have = function (k) { return stored.has(k); };
    const cand = []; for (let i = cur; i <= Math.min(n - 1, cur + ahead); i++) if (!plan.days[i].noCoords) cand.push(i);
    const prot = new Set(cand.filter(function (i) { return i === cur || i === cur + 1; }));
    const maxZ = Math.max.apply(null, o.dayZooms);
    function select(maxFarZ, dropped) {
      const keys = new Map(); plan.base.forEach(function (k) { keys.set(k, plan.tiles.get(k).z); });
      cand.forEach(function (i) {
        if (dropped.has(i)) return;
        o.dayZooms.forEach(function (z) {
          if (!prot.has(i) && z > maxFarZ) return;
          plan.days[i].tiles[z].forEach(function (k) { if (!keys.has(k)) keys.set(k, z); });
        });
      });
      let cost = 0; keys.forEach(function (z, k) { if (!have(k)) cost += avg(z); });
      return { keys: keys, cost: cost };
    }
    let maxFarZ = maxZ; const dropped = new Set();
    let sel = select(maxFarZ, dropped);
    for (let z = maxZ - 1; sel.cost > ctx.budget && z >= minFar; z--) { maxFarZ = z; sel = select(maxFarZ, dropped); }                 /* (a) */
    const far = cand.filter(function (i) { return !prot.has(i); }).reverse();                                                           /* farthest first */
    for (let f = 0; sel.cost > ctx.budget && f < far.length; f++) { dropped.add(far[f]); sel = select(maxFarZ, dropped); }              /* (b) */
    const queue = [];
    sel.keys.forEach(function (z, k) {
      if (have(k)) return;
      const t = plan.tiles.get(k); queue.push({ key: k, z: z, x: t.x, y: t.y, days: t.days.slice(), est: avg(z) });
    });
    const status = plan.days.map(function (d, i) {
      if (d.noCoords) return 'none';
      if (i < cur) return 'past';
      if (i > cur + ahead) return 'later';
      if (dropped.has(i)) return 'waiting';
      const all = o.dayZooms.every(function (z) { return d.tiles[z].every(function (k) { return sel.keys.has(k); }); });
      return all ? 'selected' : 'reduced';
    });
    return { queue: queue, estBytes: sel.cost, budget: ctx.budget, fits: sel.cost <= ctx.budget, short: sel.cost > ctx.budget, maxFarZ: maxFarZ,
      droppedDays: Array.from(dropped).sort(function (a, b) { return a - b; }), protectedDays: Array.from(prot), candidates: cand, status: status };
  }

  /* ---------- clean-up and route change ---------- */
  /* storedIndex: Map key → {days:[…]} as saved. Returns what to delete (past days / tiles no day needs any more after a route change; the background is kept) and which stored tiles need a new days[] label. */
  function cleanupPlan(plan, storedIndex, cur, opts) {
    const del = [], relabel = [], deletePast = !opts || opts.deletePast !== false;
    storedIndex.forEach(function (rec, k) {
      const t = plan.tiles.get(k);
      if (!t) { del.push(k); return; }                                           /* the route no longer needs it */
      if (t.base) { if ((rec.days || []).length !== 0) relabel.push({ key: k, days: [] }); return; }
      if (deletePast && !t.days.some(function (i) { return i >= cur; })) { del.push(k); return; }   /* every day that used it has passed */
      const a = (rec.days || []).slice().sort(function (p, q) { return p - q; }), b = t.days.slice().sort(function (p, q) { return p - q; });
      if (a.length !== b.length || a.some(function (v, j) { return v !== b[j]; })) relabel.push({ key: k, days: t.days.slice() });
    });
    return { delete: del, relabel: relabel };
  }

  /* ---------- active? ---------- */
  const env = {};
  function configure(o) { Object.assign(env, o || {}); }
  function feature() { return env.feature ? env.feature() : (typeof OFFMAP_FEATURE !== 'undefined' ? OFFMAP_FEATURE : 'off'); }
  function trips() { return env.trips ? env.trips() : OFFMAP_TRIPS; }
  let cachedKey = '', keyAdapter = null;
  function getKey() {
    if (env.key) { try { return String(env.key() || ''); } catch (e) { return ''; } }
    return OFFMAP_KEY || cachedKey;
  }
  /* ---------- the key window (OFFMAP-KEY-01) ---------- */
  const KEY_RE = /^[A-Za-z0-9_-]{8,128}$/;
  /* device-level storage of the key: one record in IndexedDB "pt-_device-offmap" (a name starting with 'pt-' is left alone by the app's storage wrapper) */
  function idbKeyAdapter() {
    const idb = root.indexedDB, name = 'pt-_device-offmap';
    const open = function () { return new Promise(function (res, rej) { const r = idb.open(name, 1); r.onupgradeneeded = function () { if (!r.result.objectStoreNames.contains('kv')) r.result.createObjectStore('kv', { keyPath: 'k' }); }; r.onsuccess = function () { res(r.result); }; r.onerror = function () { rej(r.error); }; }); };
    const run = function (mode, fn) { return open().then(function (db) { return new Promise(function (res, rej) { const t = db.transaction('kv', mode); let rq; t.oncomplete = function () { db.close(); res(rq ? rq.result : undefined); }; t.onerror = t.onabort = function () { db.close(); rej(t.error || new Error('idb')); }; rq = fn(t.objectStore('kv')); }); }); };
    return { get: function () { return run('readonly', function (s) { return s.get('key'); }).then(function (r) { return r ? r.v : ''; }); }, put: function (v) { return run('readwrite', function (s) { return s.put({ k: 'key', v: v }); }); }, del: function () { return run('readwrite', function (s) { return s.delete('key'); }); } };
  }
  function adapter() { return keyAdapter || (keyAdapter = idbKeyAdapter()); }
  function setKeyAdapter(a) { keyAdapter = a; cachedKey = ''; }   /* tests */
  async function loadKey() { try { const v = await adapter().get(); cachedKey = v && KEY_RE.test(v) ? v : ''; } catch (e) { /* no storage: no key */ } return cachedKey; }
  async function setKey(v) { v = String(v == null ? '' : v).trim(); if (!KEY_RE.test(v)) return false; try { await adapter().put(v); cachedKey = v; return true; } catch (e) { return false; } }
  async function clearKey() { try { await adapter().del(); } catch (e) { /* none */ } cachedKey = ''; }
  function keyHint() { const k = getKey(); return k ? '••••' + k.slice(-4) : ''; }   /* the last 4 characters only, for the screen */
  /* ---------- the shared key (OFFMAP-KEY-04): one write-once row in Supabase, set by a platform admin through the window ---------- */
  let clientGet = null;
  const host = {};
  function attach(o) { if (!o) return; if (typeof o.client === 'function') clientGet = o.client; ['days', 'tripId'].forEach(function (k) { if (typeof o[k] === 'function') host[k] = o[k]; }); }
  function sbc() { try { return clientGet ? clientGet() : null; } catch (e) { return null; } }
  /* RPC / select with a short timeout; never throws */
  function withTimeout(p, ms) { return Promise.race([p, new Promise(function (_, rej) { setTimeout(function () { rej(new Error('timeout')); }, ms || 8000); })]); }
  async function fetchRemoteKey() {
    const c = sbc(); if (!c) return '';
    try {
      const r = await withTimeout(c.from('platform_config').select('value').eq('key', 'offmap_key').maybeSingle());
      const v = r && r.data && r.data.value; if (v && KEY_RE.test(v)) { try { await adapter().put(v); } catch (e) { /* kept in memory */ } cachedKey = v; return v; }
    } catch (e) { /* offline or not signed in yet */ }
    return '';
  }
  /* memory, then the device copy, then the server (and the device copy is refreshed from it) */
  async function ensureKey() { return getKey() || (await loadKey()) || (await fetchRemoteKey()); }
  async function keyState() {
    const c = sbc(); if (!c) return 'offline';
    try { const r = await withTimeout(c.rpc('offmap_key_state')); return r && !r.error && typeof r.data === 'string' ? r.data : 'offline'; } catch (e) { return 'offline'; }
  }
  async function saveSharedKey(v) {
    v = String(v == null ? '' : v).trim(); if (!KEY_RE.test(v)) return 'invalid';
    const c = sbc(); if (!c) return 'offline';
    try { const r = await withTimeout(c.rpc('set_offmap_key', { p_key: v })); if (r && !r.error && typeof r.data === 'string') { if (r.data === 'saved') { cachedKey = v; try { await adapter().put(v); } catch (e) { /* none */ } } return r.data; } } catch (e) { /* fall through */ }
    return 'offline';
  }
  /* the window: the pasted key is masked (password field), never shown, never echoed; after a successful save, or when a key already exists, it is locked for everybody */
  function openKeyDialog(doc) {
    doc = doc || (root.document); if (!doc || !doc.body) return null;
    const old = doc.getElementById('ptOmKeyDlg'); if (old) old.remove();
    const el = function (tag, css, text) { const n = doc.createElement(tag); if (css) n.style.cssText = css; if (text != null) n.textContent = text; return n; };
    const wrap = el('div', 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:16px;direction:rtl;font-family:inherit');
    wrap.style.setProperty('display', 'flex', 'important');   /* the app's gate rule `html.pt-gate body > :not(#ptGate){display:none!important}` would hide this window while signed out */
    wrap.id = 'ptOmKeyDlg'; wrap.setAttribute('role', 'dialog'); wrap.setAttribute('aria-modal', 'true');
    const box = el('div', 'background:#fff;color:#17211b;border-radius:14px;padding:18px 16px;max-width:360px;width:100%;box-shadow:0 8px 30px rgba(0,0,0,.3)');
    box.appendChild(el('h2', 'margin:0 0 6px;font-size:17px', 'מפתח מפות אופליין'));
    box.appendChild(el('p', 'margin:0 0 10px;font-size:12.5px;color:#5f6861', 'הכנסה חד-פעמית. המפתח נשמר במערכת לכל המטיילים, אינו מוצג, ולא ניתן לשנות אותו אחרי השמירה.'));
    const status = el('p', 'margin:0 0 8px;font-size:13px;font-weight:600', 'בודק…');
    const input = el('input', 'width:100%;box-sizing:border-box;padding:10px;font-size:15px;border:1px solid #c9d1c3;border-radius:8px;direction:ltr;text-align:left');
    input.type = 'password'; input.setAttribute('autocomplete', 'off'); input.setAttribute('autocapitalize', 'off'); input.setAttribute('spellcheck', 'false'); input.placeholder = 'הדבק מפתח'; input.disabled = true;
    const msg = el('p', 'margin:8px 0 0;min-height:18px;font-size:12.5px;color:#5f6861');
    const row = el('div', 'display:flex;gap:8px;margin-top:10px');
    const btn = function (t, bg, fg) { const b = el('button', 'flex:1;padding:11px 6px;border:0;border-radius:8px;font-size:14px;background:' + bg + ';color:' + fg + ';cursor:pointer', t); b.type = 'button'; return b; };
    const save = btn('שמור', '#2f6f4f', '#fff'), close = btn('סגור', '#eef1de', '#17211b');
    const paint = function (st) {
      const open = st === 'open'; input.disabled = !open; save.disabled = !open; save.style.opacity = open ? '1' : '.4';
      if (!open) { input.value = ''; input.style.display = 'none'; save.style.display = 'none'; } else { input.style.display = ''; save.style.display = ''; }
      status.textContent = st === 'locked' ? 'המפתח הוגדר ✓ (נעול)' : st === 'open' ? 'אין מפתח במערכת — אפשר להדביק' : st === 'not_admin' ? 'רק מנהל המערכת יכול להגדיר מפתח. התחבר בחשבון המנהל.' : 'אין חיבור לשרת כרגע.';
    };
    const done = function () { input.value = ''; wrap.remove(); try { if (root.location && /offmapkey/.test(root.location.hash)) root.history.replaceState(null, '', root.location.pathname + root.location.search); } catch (e) { /* ignore */ } };
    save.onclick = async function () {
      const v = String(input.value || '').trim(); if (!KEY_RE.test(v)) { msg.textContent = 'המפתח לא תקין (8–128 תווים: אותיות, ספרות, - או _).'; return; }
      save.disabled = true; msg.textContent = 'שומר…'; const r = await saveSharedKey(v); input.value = '';
      if (r === 'saved') { msg.textContent = 'נשמר. החלון נעול.'; paint('locked'); }
      else if (r === 'locked') { msg.textContent = 'כבר הוגדר מפתח.'; paint('locked'); }
      else if (r === 'not_admin') { msg.textContent = 'אין הרשאה.'; paint('not_admin'); }
      else { msg.textContent = r === 'invalid' ? 'המפתח לא תקין.' : 'השמירה נכשלה, נסה שוב.'; save.disabled = false; }
    };
    close.onclick = done; wrap.addEventListener('click', function (e) { if (e.target === wrap) done(); });
    row.appendChild(save); row.appendChild(close);
    [status, input, msg, row].forEach(function (n) { box.appendChild(n); }); wrap.appendChild(box); doc.body.appendChild(wrap);
    keyState().then(function (st) { if (wrap.isConnected) paint(st); });
    return wrap;
  }
  /* ---------- the manual download window (#offmapdownload): prepares the offline tiles of the open trip on this device, with progress; works only for a trip listed in OFFMAP_TRIPS (the flag itself stays off) ---------- */
  const REASON_HE = { rate_limited: 'Protomaps הגביל את הקצב. מה שירד נשמר, נסה שוב בעוד כמה דקות.', forbidden: 'המפתח נדחה (403). בדוק שהמפתח תקין ושהוא מותר לדומיין orsela.github.io.', auth: 'המפתח נדחה (401).', network: 'אין רשת יציבה. מה שירד נשמר, אפשר להמשיך אחר כך.', cap: 'הגעת לתקרת 150MB. הימים הרחוקים ביותר לא ירדו.', budget: 'אין מספיק מקום פנוי במכשיר. הימים הרחוקים ביותר לא ירדו.', aborted: 'נעצר. מה שירד נשמר.', no_key: 'אין מפתח מפות במערכת (או שאין חיבור לשרת).' };
  const fmtMB = function (b) { return (b / 1048576).toFixed(1) + ' MB'; };
  function openDownloadDialog(doc) {
    doc = doc || root.document; if (!doc || !doc.body) return null;
    const old = doc.getElementById('ptOmDlDlg'); if (old) old.remove();
    const el = function (tag, css, text) { const n = doc.createElement(tag); if (css) n.style.cssText = css; if (text != null) n.textContent = text; return n; };
    const wrap = el('div', 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:16px;direction:rtl;font-family:inherit');
    wrap.style.setProperty('display', 'flex', 'important'); wrap.id = 'ptOmDlDlg'; wrap.setAttribute('role', 'dialog'); wrap.setAttribute('aria-modal', 'true');
    const box = el('div', 'background:#fff;color:#17211b;border-radius:14px;padding:18px 16px;max-width:360px;width:100%;box-shadow:0 8px 30px rgba(0,0,0,.3)');
    box.appendChild(el('h2', 'margin:0 0 6px;font-size:17px', 'הורדת מפות לשימוש אופליין'));
    const info = el('p', 'margin:0 0 8px;font-size:13px;line-height:1.5', 'בודק…');
    const bar = el('div', 'height:8px;border-radius:4px;background:#e6eadf;overflow:hidden;margin:6px 0'); const fill = el('div', 'height:100%;width:0;background:#2f6f4f;transition:width .2s'); bar.appendChild(fill);
    const msg = el('p', 'margin:8px 0 0;min-height:18px;font-size:12.5px;color:#5f6861;line-height:1.5');
    const row = el('div', 'display:flex;gap:8px;margin-top:10px');
    const btn = function (t, bg, fg) { const b = el('button', 'flex:1;padding:11px 6px;border:0;border-radius:8px;font-size:14px;background:' + bg + ';color:' + fg + ';cursor:pointer', t); b.type = 'button'; return b; };
    const go = btn('הורד', '#2f6f4f', '#fff'), stop = btn('עצור', '#f1ece4', '#8a2b1f'), close = btn('סגור', '#eef1de', '#17211b');
    stop.style.display = 'none'; let ctl = null, store = null, wake = null, running = false;
    const trip = function () { try { return host.tripId ? host.tripId() : null; } catch (e) { return null; } };
    const days = function () { try { return host.days ? (host.days() || []) : []; } catch (e) { return []; } };
    const refresh = async function () {
      const t = trip(), ok = !!t && trips().indexOf(String(t)) >= 0 && String(t) !== VN_TRIP;
      if (running) return;
      if (!ok) { info.textContent = t ? 'הטיול הפתוח לא ברשימת מפות האופליין.' : 'ממתין לטעינת הטיול… (פתח את הטיול באפליקציה)'; go.disabled = true; go.style.opacity = '.4'; return; }
      go.disabled = false; go.style.opacity = '1';
      const d = days(), withPts = d.filter(function (x) { return dayPoints(x).points.length; }).length;
      try { store = store || createIdbStore(t); const ix = await store.index(); info.textContent = 'ימים עם מסלול: ' + withPts + ' מתוך ' + d.length + '. שמור במכשיר: ' + ix.size + ' אריחים (' + fmtMB(usedBytes(ix)) + ').'; } catch (e) { info.textContent = 'ימים עם מסלול: ' + withPts + ' מתוך ' + d.length + '.'; }
    };
    const done = function () { if (ctl) ctl.abort(); try { if (wake) wake.release(); } catch (e) { /* ignore */ } wrap.remove(); try { if (root.location && /offmapdownload/.test(root.location.hash)) root.history.replaceState(null, '', root.location.pathname + root.location.search); } catch (e) { /* ignore */ } };
    go.onclick = async function () {
      if (running) return; running = true; go.disabled = true; go.style.opacity = '.4'; stop.style.display = ''; msg.textContent = 'מתחיל…'; fill.style.width = '0';
      ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      try { if (root.navigator && root.navigator.wakeLock) wake = await root.navigator.wakeLock.request('screen'); } catch (e) { /* optional */ }
      const t = trip(), d = days();
      try {
        store = store || createIdbStore(t); await persist();
        const r = await prepare({ days: d, store: store, storage: await deviceStorage(), ahead: d.length, signal: ctl && ctl.signal, onProgress: function (p) { fill.style.width = Math.round(100 * p.done / Math.max(1, p.total)) + '%'; msg.textContent = 'ירדו ' + p.done + ' מתוך ' + p.total + ' אריחים · ' + fmtMB(p.bytes); } });
        fill.style.width = r.status === 'done' || r.status === 'nothing' ? '100%' : fill.style.width;
        const head = r.status === 'done' ? 'הסתיים ✓ ' : r.status === 'nothing' ? 'הכול כבר שמור ✓ ' : '';
        msg.textContent = head + 'ירדו ' + r.downloaded + ' אריחים (' + fmtMB(r.bytes) + ')' + (r.failed ? ', נכשלו ' + r.failed : '') + '. סה"כ שמור: ' + fmtMB(r.used) + '. ' + (r.reason ? (REASON_HE[r.reason] || r.reason) : '');
      } catch (e) { msg.textContent = 'שגיאה: ' + (e && e.message || e); }
      running = false; stop.style.display = 'none'; go.disabled = false; go.style.opacity = '1'; go.textContent = 'הורד שוב / המשך'; try { if (wake) wake.release(); } catch (e) { /* ignore */ } refresh();
    };
    stop.onclick = function () { if (ctl) ctl.abort(); };
    close.onclick = done; wrap.addEventListener('click', function (e) { if (e.target === wrap) done(); });
    row.appendChild(go); row.appendChild(stop); row.appendChild(close);
    [info, bar, msg, row].forEach(function (n) { box.appendChild(n); }); wrap.appendChild(box); doc.body.appendChild(wrap); refresh();
    const poll = root.setInterval(function () { if (!wrap.isConnected) { root.clearInterval(poll); return; } refresh(); }, 1500);   /* the trip may still be loading when the address opens the window */
    return wrap;
  }
  /* opens the window when the address carries #offmapkey (now and on later hash changes); otherwise nothing at all */
  function mountKeyEntry() {
    loadKey();   /* the saved key (if any) into memory so getKey() answers synchronously */
    const check = function () { try { if (root.location && /(^|[#&])offmapkey$/.test(root.location.hash)) openKeyDialog(root.document); else if (root.location && /(^|[#&])offmapdownload$/.test(root.location.hash)) openDownloadDialog(root.document); } catch (e) { /* never break the page */ } };
    try { root.addEventListener('hashchange', check); } catch (e) { /* none */ }
    if (root.document && root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', check); else check();
  }
  /* true only for the flag 'on' and a trip in the list; Vietnam never */
  function active(tripId) { const t = String(tripId == null ? '' : tripId); return feature() === 'on' && !!t && t !== VN_TRIP && trips().indexOf(t) >= 0; }

  /* ---------- storage ---------- */
  async function pack(buf) {   /* gzip when the browser can; {bytes, c: 1|0} */
    try {
      if (typeof CompressionStream !== 'undefined' && typeof Blob !== 'undefined' && typeof Response !== 'undefined') {
        const out = await new Response(new Blob([buf]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer();
        if (out.byteLength < buf.byteLength) return { bytes: out, c: 1 };
      }
    } catch (e) { /* store as is */ }
    return { bytes: buf, c: 0 };
  }
  async function unpack(bytes, c) {
    if (!c) return bytes;
    return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  }
  /* the store interface (async): index() Map, putTile, getTile, setDays, deleteTiles, clear, getMeta, setMeta, destroy */
  function createMemoryStore() {
    const tiles = new Map(), idx = new Map(), meta = new Map();
    return {
      kind: 'memory',
      async index() { return new Map(Array.from(idx, function (e) { return [e[0], Object.assign({}, e[1], { days: e[1].days.slice() })]; })); },
      async putTile(k, rec) { tiles.set(k, { b: rec.bytes, c: rec.c }); idx.set(k, { z: rec.z, sz: rec.bytes.byteLength, n: rec.n, days: (rec.days || []).slice(), ts: rec.ts }); },
      async getTile(k) { const t = tiles.get(k); return t ? { bytes: t.b, c: t.c } : null; },
      async setDays(k, days) { const r = idx.get(k); if (r) r.days = days.slice(); },
      async deleteTiles(keys) { keys.forEach(function (k) { tiles.delete(k); idx.delete(k); }); },
      async clear() { tiles.clear(); idx.clear(); meta.clear(); },
      async getMeta(k) { return meta.has(k) ? meta.get(k) : null; },
      async setMeta(k, v) { meta.set(k, v); },
      async destroy() { tiles.clear(); idx.clear(); meta.clear(); }
    };
  }
  /* IndexedDB: database "pt-<trip>-offmap", stores tiles {k,b,c} (the heavy bytes), index {k,z,sz,n,days,ts} (small: listing it never loads tile bytes), meta {k,v} */
  function createIdbStore(tripId, idb) {
    idb = idb || (root.indexedDB);
    const name = 'pt-' + tripId + '-offmap'; let dbp = null;
    function open() {
      if (dbp) return dbp;
      dbp = new Promise(function (res, rej) {
        const r = idb.open(name, 1);
        r.onupgradeneeded = function () { const db = r.result; ['tiles', 'index', 'meta'].forEach(function (s) { if (!db.objectStoreNames.contains(s)) db.createObjectStore(s, { keyPath: 'k' }); }); };
        r.onsuccess = function () { res(r.result); };
        r.onerror = function () { dbp = null; rej(r.error || new Error('idb open')); };
      });
      return dbp;
    }
    function tx(stores, mode, fn) {
      return open().then(function (db) {
        return new Promise(function (res, rej) {
          const t = db.transaction(stores, mode); let rq;
          t.oncomplete = function () { res(rq ? rq.result : undefined); };
          t.onerror = function () { rej(t.error || new Error('idb tx')); };
          t.onabort = function () { rej(t.error || new Error('idb abort')); };
          rq = fn(t);
        });
      });
    }
    return {
      kind: 'idb', name: name,
      async index() { const rows = await tx(['index'], 'readonly', function (t) { return t.objectStore('index').getAll(); }); return new Map((rows || []).map(function (r) { return [r.k, { z: r.z, sz: r.sz, n: r.n, days: r.days || [], ts: r.ts }]; })); },
      async putTile(k, rec) {
        await tx(['tiles', 'index'], 'readwrite', function (t) {
          t.objectStore('tiles').put({ k: k, b: rec.bytes, c: rec.c });
          t.objectStore('index').put({ k: k, z: rec.z, sz: rec.bytes.byteLength, n: rec.n, days: (rec.days || []).slice(), ts: rec.ts });
        });
      },
      async getTile(k) { const r = await tx(['tiles'], 'readonly', function (t) { return t.objectStore('tiles').get(k); }); return r ? { bytes: r.b, c: r.c } : null; },
      async setDays(k, days) {
        await tx(['index'], 'readwrite', function (t) { const s = t.objectStore('index'), g = s.get(k); g.onsuccess = function () { if (g.result) { g.result.days = days.slice(); s.put(g.result); } }; return g; });
      },
      async deleteTiles(keys) { if (!keys.length) return; await tx(['tiles', 'index'], 'readwrite', function (t) { keys.forEach(function (k) { t.objectStore('tiles').delete(k); t.objectStore('index').delete(k); }); }); },
      async clear() { await tx(['tiles', 'index', 'meta'], 'readwrite', function (t) { ['tiles', 'index', 'meta'].forEach(function (s) { t.objectStore(s).clear(); }); }); },
      async getMeta(k) { const r = await tx(['meta'], 'readonly', function (t) { return t.objectStore('meta').get(k); }); return r ? r.v : null; },
      async setMeta(k, v) { await tx(['meta'], 'readwrite', function (t) { return t.objectStore('meta').put({ k: k, v: v }); }); },
      async destroy() {   /* leaving the trip / removing the member: the whole database goes (like F12 clearTrip) */
        try { const db = await open(); db.close(); } catch (e) { /* none */ }
        dbp = null;
        await new Promise(function (res) { const r = idb.deleteDatabase(name); r.onsuccess = r.onerror = r.onblocked = function () { res(); }; });
      }
    };
  }
  function usedBytes(index) { let s = 0; index.forEach(function (r) { s += r.sz || 0; }); return s; }
  async function deviceStorage(nav) {
    nav = nav || root.navigator;
    try { if (nav && nav.storage && nav.storage.estimate) { const e = await nav.storage.estimate(); return { quota: e.quota, usage: e.usage }; } } catch (e) { /* unknown */ }
    return null;
  }
  async function persist(nav) { nav = nav || root.navigator; try { return !!(nav && nav.storage && nav.storage.persist && await nav.storage.persist()); } catch (e) { return false; } }

  /* ---------- the tile reader: offmap://z/x/y ---------- */
  function parseOffmapUrl(u) { const m = /^offmap:\/\/(\d+)\/(\d+)\/(\d+)/.exec(String(u || '')); return m ? { z: +m[1], x: +m[2], y: +m[3] } : null; }
  function tileUrl(z, x, y, key) { return TILE_URL.replace('{z}', z).replace('{x}', x).replace('{y}', y).replace('{key}', encodeURIComponent(key)); }
  /* a stored tile as an ArrayBuffer of MVT bytes; a tile we do not have = an EMPTY buffer (a valid empty vector tile, so the map shows no error and simply draws nothing there) */
  async function loadTile(store, z, x, y) {
    const r = await store.getTile(tileKey(z, x, y));
    return r ? unpack(r.bytes, r.c) : new ArrayBuffer(0);
  }
  /* MapLibre GL JS: addProtocol('offmap', …). Supports the v4+ promise form (params, abortController) and the older callback form (params, callback). */
  function registerProtocol(maplibregl, store) {
    maplibregl.addProtocol('offmap', function (params, second) {
      const p = parseOffmapUrl(params && params.url), job = p ? loadTile(store, p.z, p.x, p.y) : Promise.resolve(new ArrayBuffer(0));
      if (typeof second === 'function') { job.then(function (data) { second(null, data); }, function (e) { second(e); }); return { cancel: function () {} }; }
      return job.then(function (data) { return { data: data }; });
    });
  }

  /* ---------- the download engine ---------- */
  const sleepReal = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  /* prepare(o): plan the days, fix the budget, reconcile what is stored, download what is missing. Never throws for network reasons: the result says why it stopped.
     o: { days, store, key, fetchFn, cur (index) | now, cap, storage: {quota, usage}|null, concurrency (default 5, max 6), retries (default 2), backoffMs, sleep, onProgress, signal, plan opts }
     → { status: 'done'|'stopped'|'nothing', reason: null|'rate_limited'|'forbidden'|'auth'|'network'|'cap'|'budget'|'aborted'|'no_key', downloaded, failed, bytes, remaining, plan, queue, used, budget } */
  async function prepare(o) {
    const store = o.store, days = o.days || [], fetchFn = o.fetchFn || (root.fetch && root.fetch.bind(root)), key = o.key != null ? o.key : await ensureKey();
    const sleep = o.sleep || sleepReal, conc = clamp(o.concurrency || 5, 1, 6), retries = o.retries != null ? o.retries : 2, backoff = o.backoffMs != null ? o.backoffMs : 600;
    const res = { status: 'nothing', reason: null, downloaded: 0, failed: 0, bytes: 0, remaining: 0, plan: null, queue: null, used: 0, budget: 0 };
    if (!key) { res.reason = 'no_key'; return res; }
    const plan = planTrip(days, o.plan), index = await store.index();
    const cur = o.cur != null ? o.cur : currentDayIndex(days, o.now), cap = o.cap != null ? o.cap : DEFAULT_CAP;
    /* route change / days passed: reconcile before counting what is used */
    const cl = cleanupPlan(plan, index, cur, o.cleanup);
    if (cl.delete.length) { await store.deleteTiles(cl.delete); cl.delete.forEach(function (k) { index.delete(k); }); }
    for (const r of cl.relabel) { await store.setDays(r.key, r.days); const e = index.get(r.key); if (e) e.days = r.days; }
    const used = usedBytes(index), learned = (await store.getMeta('avg')) || {};
    const b = computeBudget({ cap: cap, used: used, quota: o.storage ? o.storage.quota : null, usage: o.storage ? o.storage.usage : 0 });
    const q = buildQueue(plan, { cur: cur, ahead: o.ahead, budget: b.budget, stored: index, avg: function (z) { return avgBytes(z, learned); } });
    Object.assign(res, { plan: plan, queue: q, used: used, budget: b.budget, remaining: q.queue.length });
    if (!q.queue.length) return res;
    let next = 0, stop = null, newBytes = 0, usedNow = used, consecutiveFail = 0;
    const sums = {};
    const worker = async function () {
      while (!stop) {
        if (o.signal && o.signal.aborted) { stop = 'aborted'; break; }
        const i = next++; if (i >= q.queue.length) break;
        const it = q.queue[i]; let buf = null;
        for (let attempt = 0; attempt <= retries && !stop; attempt++) {
          try {
            const r = await fetchFn(tileUrl(it.z, it.x, it.y, key), { signal: o.signal });
            if (r.status === 429) { stop = 'rate_limited'; break; }
            if (r.status === 403) { stop = 'forbidden'; break; }
            if (r.status === 401) { stop = 'auth'; break; }
            if (!r.ok) throw new Error('http ' + r.status);
            buf = await r.arrayBuffer(); break;
          } catch (e) {
            if (o.signal && o.signal.aborted) { stop = 'aborted'; break; }
            if (attempt < retries) await sleep(backoff * (attempt + 1) * (attempt + 1));
          }
        }
        if (stop) break;
        if (!buf) { res.failed++; if (++consecutiveFail >= 5) stop = 'network'; continue; }
        consecutiveFail = 0;
        const pk = await pack(buf);
        if (usedNow + pk.bytes.byteLength > cap) { stop = 'cap'; break; }
        if (newBytes + pk.bytes.byteLength > b.budget) { stop = 'budget'; break; }
        usedNow += pk.bytes.byteLength; newBytes += pk.bytes.byteLength;
        await store.putTile(it.key, { z: it.z, bytes: pk.bytes, c: pk.c, n: buf.byteLength, days: it.days, ts: Date.now() });
        const s = sums[it.z] || (sums[it.z] = { n: 0, tot: 0 }); s.n++; s.tot += pk.bytes.byteLength;
        res.downloaded++; res.bytes = newBytes;
        if (o.onProgress) { try { o.onProgress({ done: res.downloaded, total: q.queue.length, bytes: newBytes, key: it.key }); } catch (e) { /* UI errors never stop the download */ } }
      }
    };
    await Promise.all(Array.from({ length: Math.min(conc, q.queue.length) }, worker));
    /* learn the real average (stored bytes) per zoom: running mean */
    const nl = Object.assign({}, learned);
    Object.keys(sums).forEach(function (z) { const p = nl[z] || { n: 0, mean: 0 }, s = sums[z], n = p.n + s.n; nl[z] = { n: n, mean: (p.mean * p.n + s.tot) / n }; });
    if (Object.keys(sums).length) await store.setMeta('avg', nl);
    res.used = usedNow; res.remaining = q.queue.length - res.downloaded - res.failed;
    if (stop) { res.status = 'stopped'; res.reason = stop; }
    else res.status = res.failed ? 'stopped' : 'done';
    if (res.status === 'stopped' && !res.reason) res.reason = 'network';
    return res;
  }
  /* what a day shows on a status screen: have / total tiles stored */
  function dayCoverage(plan, index, i) {
    const d = plan.days[i]; if (!d) return { have: 0, total: 0 };
    let have = 0, total = 0; Object.keys(d.tiles).forEach(function (z) { d.tiles[z].forEach(function (k) { total++; if (index.has(k)) have++; }); });
    return { have: have, total: total };
  }

  const api = {
    version: VERSION, constants: { OFFMAP_TRIPS: OFFMAP_TRIPS, DEFAULT_CAP: DEFAULT_CAP, DEFAULTS: DEFAULTS, DEFAULT_AVG_KB: DEFAULT_AVG_KB, TILE_URL: TILE_URL, VN_TRIP: VN_TRIP },
    configure: configure, active: active, getKey: getKey, setKey: setKey, clearKey: clearKey, attach: attach, openDownloadDialog: openDownloadDialog, ensureKey: ensureKey, fetchRemoteKey: fetchRemoteKey, keyState: keyState, saveSharedKey: saveSharedKey, loadKey: loadKey, setKeyAdapter: setKeyAdapter, keyHint: keyHint, openKeyDialog: openKeyDialog, mountKeyEntry: mountKeyEntry,
    lon2x: lon2x, lat2y: lat2y, tileKey: tileKey, parseKey: parseKey, tileNW: tileNW, tileSizeKm: tileSizeKm, distKm: distKm, coord: coord,
    dayPoints: dayPoints, coveringTiles: coveringTiles, planTrip: planTrip, avgBytes: avgBytes, computeBudget: computeBudget, currentDayIndex: currentDayIndex,
    buildQueue: buildQueue, cleanupPlan: cleanupPlan, dayCoverage: dayCoverage,
    createMemoryStore: createMemoryStore, createIdbStore: createIdbStore, usedBytes: usedBytes, deviceStorage: deviceStorage, persist: persist,
    pack: pack, unpack: unpack, parseOffmapUrl: parseOffmapUrl, tileUrl: tileUrl, loadTile: loadTile, registerProtocol: registerProtocol, prepare: prepare
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptOM = api;
})(typeof window !== 'undefined' ? window : globalThis);
