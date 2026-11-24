/* Lonely Planner · F13-TR – AI translation of trip content (client) · version 3.0.0-alpha.19.0
   CHANGE 2026-11-24 F13-TR-CL-01: new file (no previous version). Spec: claude/Plan_Travel_F13_translate_spec.md. When English is active (F13) and
   TRANSLATE_FEATURE='on', the More list gets "Translate trip content". On tap: collect the Hebrew texts of the itinerary (day title / region / activities /
   hotel / notes / booking notes, waypoint name + notes) and the bookings (title / provider / address / notes) — never the journal — that have no translation
   yet, send them to the Edge Function translate-content with the user's JWT (max 3 runs per trip per UTC day, server side), and add the answer as a SEPARATE
   layer ({hebrew: english}) to the F13 translator (window.__ptF13.addLayer). The Hebrew source is never changed. The layer is kept in the trip's shared storage
   (planner:i18n_en) and in localStorage as a cache, so every member sees it. Everything is a no-op unless attach() was called with flag 'on'. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.19.0';
  const env = {};   // flag(), backend(), endpoint, client(), tripId(), days(), reservations() → Promise<[]>, get(), set(v), toast(msg), withTimeout(p,ms)
  const HE = /[֐-׿]/;
  const OK_KEY = 'pt-f13tr-ok';
  const B = { busy: false, count: 0, loadedFor: null };
  const LINES = {
    unauthorized: 'Please sign in again and try once more.',
    not_member: 'You are not a member of this trip.',
    daily_cap: 'Translation limit for today reached (3 per trip). Try again tomorrow.',
    translate_off: 'Translation is switched off right now.',
    upstream_error: 'The translation did not work this time. Nothing was used — try again in a moment.',
    upstream_timeout: 'The translation took too long. Nothing was used — try again in a moment.',
    too_large: 'There is too much text to translate in one go.',
    offline: 'You are offline. Connect and try again.',
    generic: 'Could not translate right now. Try again later.'
  };
  const flat = (s) => String(s).trim().replace(/\s+/g, ' ');
  function on() { try { return env.flag && env.flag() === 'on' && (!env.backend || env.backend() === 'cloud'); } catch (e) { return false; } }
  function F() { return root.__ptF13 || null; }
  function attach(o) { Object.assign(env, o || {}); try { load(); } catch (e) { /* ignore */ } }
  function lk(id) { return 'pt-f13tr-layer:' + id; }

  /* ---- 1. which Hebrew texts exist and are still untranslated ---- */
  const DAY_FIELDS = ['title', 'region', 'activities', 'hotel', 'notes', 'bookedHotel', 'bookingNotes'];
  const RES_FIELDS = ['title', 'provider', 'address', 'notes'];
  function collect(days, reservations, layer) {
    const have = layer || {}, seen = new Set(), out = [];
    const add = (v) => { if (typeof v !== 'string' || !HE.test(v)) return; const t = v.trim(); if (!t || seen.has(t) || have[flat(t)]) return; seen.add(t); out.push(t); };
    (Array.isArray(days) ? days : []).forEach((d) => {
      if (!d) return;
      DAY_FIELDS.forEach((k) => add(d[k]));
      (Array.isArray(d.waypoints) ? d.waypoints : []).forEach((w) => { if (w) { add(w.name); add(w.notes); } });
    });
    (Array.isArray(reservations) ? reservations : []).forEach((r) => { if (r) RES_FIELDS.forEach((k) => add(r[k])); });
    return out;
  }

  /* ---- 2. the layer: local cache + shared storage ---- */
  async function load() {
    const f = F(), id = env.tripId && env.tripId(); if (!f || !f.addLayer || !id) return 0;
    let n = 0;
    try { const c = root.localStorage && root.localStorage.getItem(lk(id)); if (c) n = f.addLayer(JSON.parse(c)); } catch (e) { /* ignore */ }
    try { const raw = env.get ? await env.get() : null; if (raw) { const m = JSON.parse(raw); n = f.addLayer(m); try { root.localStorage.setItem(lk(id), JSON.stringify(m)); } catch (e) { /* quota */ } } } catch (e) { /* offline / viewer */ }
    B.count = f.layerSize ? f.layerSize() : n; row(); return n;
  }
  async function save(map) {
    const id = env.tripId && env.tripId(); let all = map;
    try { const raw = env.get ? await env.get() : null; if (raw) all = Object.assign({}, JSON.parse(raw), map); } catch (e) { /* keep the new part only */ }
    try { root.localStorage.setItem(lk(id), JSON.stringify(all)); } catch (e) { /* quota */ }
    try { if (env.set) await env.set(JSON.stringify(all)); return true; } catch (e) { return false; }
  }

  /* ---- 3. the run ---- */
  async function token() { try { const c = env.client && env.client(); const r = await c.auth.getSession(); return (r && r.data && r.data.session && r.data.session.access_token) || ''; } catch (e) { return ''; } }
  function say(m) { try { env.toast ? env.toast(m) : null; } catch (e) { /* ignore */ } }
  async function run() {
    if (!on() || B.busy) return { ok: false, code: 'off' };
    const f = F(); if (!f || !f.active || !f.active()) return { ok: false, code: 'off' };
    if (root.navigator && root.navigator.onLine === false) { say(LINES.offline); return { ok: false, code: 'offline' }; }
    const layer = {}; // current layer is inside the translator; collect() needs it to skip finished texts
    try { const id = env.tripId(); const c = root.localStorage.getItem(lk(id)); if (c) Object.assign(layer, JSON.parse(c)); } catch (e) { /* ignore */ }
    const days = env.days ? env.days() : [], res = env.reservations ? await env.reservations() : [];
    const strings = collect(days, res, layer);
    if (!strings.length) { say('Everything is already translated.'); return { ok: true, added: 0 }; }
    try { if (!root.localStorage.getItem(OK_KEY)) { if (root.confirm && !root.confirm('The trip texts (titles, activities, places, notes, bookings — not the journal) are sent to an AI service to be translated into English. Continue?')) return { ok: false, code: 'declined' }; root.localStorage.setItem(OK_KEY, '1'); } } catch (e) { /* ignore */ }
    const jwt = await token(); if (!jwt) { say(LINES.unauthorized); return { ok: false, code: 'unauthorized' }; }
    B.busy = true; row();
    try {
      const r = await (env.fetch || root.fetch)(env.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + jwt }, body: JSON.stringify({ trip_id: env.tripId(), strings }) });
      let j = {}; try { j = await r.json(); } catch (e) { /* not json */ }
      if (!r.ok) { const code = j && j.error; say(LINES[code] || LINES.generic); return { ok: false, code: code || 'error' }; }
      const map = j && j.map && typeof j.map === 'object' ? j.map : {};
      const added = f.addLayer(map); B.count = f.layerSize();
      const shared = await save(map);
      say(added ? 'Translated ' + added + ' texts' + (shared ? '.' : ' on this device (could not share with the other members).') : 'Nothing new to translate.');
      return { ok: true, added, shared };
    } catch (e) { say(LINES.generic); return { ok: false, code: 'network' }; }
    finally { B.busy = false; row(); }
  }

  /* ---- 4. the row in "More" (below the language row) ---- */
  function row() {
    try {
      const d = root.document, f = F(), more = d && d.getElementById('more'); if (!more) return;
      let el = d.getElementById('ptF13TrRow');
      const show = on() && f && f.active && f.active();
      if (!show) { if (el) el.remove(); return; }
      const sub = B.busy ? 'Translating…' : (B.count ? B.count + ' texts translated · tap to update' : 'Tap to translate itinerary and bookings');
      if (el) { const v = el.querySelector('.val'); if (v && v.textContent !== sub) v.textContent = sub; return; }
      const anchor = d.getElementById('ptF13LangRow'); if (!anchor || !anchor.parentNode) return;
      el = d.createElement('div'); el.className = 'listitem'; el.id = 'ptF13TrRow'; el.setAttribute('role', 'button'); el.setAttribute('tabindex', '0'); el.setAttribute('data-f13-skip', '1');
      el.innerHTML = '<div class="ic" style="background:#eef2fb">✨</div><div class="lbl">Translate trip content<span class="val" style="display:block;font-weight:400;font-size:.72rem"></span></div><div class="chev">‹</div>';   /* CHANGE 2026-11-24 F13-TR-CL-03: + the chevron like every other row of More (Or's phone check: the row had none) */
      el.querySelector('.val').textContent = sub;
      const go = function () { run(); };
      el.addEventListener('click', go);
      el.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } });
      anchor.parentNode.insertBefore(el, anchor.nextSibling);
    } catch (e) { /* no DOM */ }
  }
  try { root.addEventListener && root.addEventListener('pt:langchange', function () { load(); row(); }); } catch (e) { /* ignore */ }

  function sync() { try { const id = env.tripId && env.tripId(); if (on() && id && B.loadedFor !== id) { B.loadedFor = id; load(); } } catch (e) { /* ignore */ } }
  const api = { version: VERSION, attach, collect, run, load, row, sync, _env: env, _LINES: LINES };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptF13TR = api;
})(typeof window !== 'undefined' ? window : globalThis);
