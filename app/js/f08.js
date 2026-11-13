/* Lonely Planner · F08 – country and time zone for every day (stage A, conversation 1: day fields + helper functions) · version 3.0.0-alpha.13
   CHANGE 2026-11-13 F08-A1-01: new file (no previous version). Spec: docs/F08_spec.md §1–§3 (+ D8 home clock in §4.4 / AC15).
   CHANGE 2026-11-13 F08-A2-01 (conversation 2): what changed from F08-A1-01 (helpers only, not wired): added the screen
   "מדינות לפי ימים" + the range sheet (spec §4.1–§4.2) at the bottom of this file, and attach / mount, which app/index.html
   calls (flag F08_FEATURE, gate hook F08-GATE-01, main-script hook F08-MOUNT-01). The helpers above that section are unchanged.
   Day edit, flight day and the home clocks (§4.3–§4.4) are conversation 3.
   Everything the helpers need from the app arrives through f08Configure(); in the browser the defaults read the app's own
   globals (tripData, isFlightDay, F08_FEATURE, window.__ptF10), under Node the tests inject them.
   F08_FEATURE === 'off' → every helper returns what alpha.12.1 does (device clock, Asia/Jerusalem at home, 'VN', isFlightDay).
   Day fields (all optional, spec §1): country (ISO-2), city (≤ 60), tz (IANA), isFlight, flightFrom / flightTo {country, tz, city?}. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.13';
  const LEGACY_COUNTRY = 'VN', LEGACY_TZ = 'Asia/Ho_Chi_Minh', ISRAEL_TZ = 'Asia/Jerusalem';
  const MIN = 60000, DAY = 86400000;

  /* ---- environment (injectable) ---- */
  const env = {};   // days(), countries() → {CODE:{tz:[…]}}, tripCountries() → ['TH',…] in trip order, homeCurrency(), deviceTz(), landing(i,d) → ms|null, feature(), legacyFlight(d)
  function f08Configure(o) { Object.assign(env, o || {}); clearCaches(); }
  function days() { const v = env.days ? env.days() : (typeof tripData !== 'undefined' ? tripData : []); return Array.isArray(v) ? v : []; }
  function feature() { return env.feature ? env.feature() : (typeof F08_FEATURE !== 'undefined' ? F08_FEATURE : 'on'); }
  function off() { return feature() === 'off'; }
  /* countries.json rows, by code. Only VN and IL are known without the file, so the legacy Vietnam trip works offline (spec §3.3). */
  const BUILTIN = { VN: { tz: [LEGACY_TZ] }, IL: { tz: [ISRAEL_TZ] } };
  function countryRow(code) {
    const m = env.countries ? env.countries() : null;
    const r = m && (Array.isArray(m) ? m.find(x => x && x.code === code) : m[code]);
    return r || BUILTIN[code] || null;
  }
  function deviceTz() {
    if (env.deviceTz) return env.deviceTz();
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (e) { return 'UTC'; }
  }
  function legacyFlight(d) {   // alpha.12.1 isFlightDay (UI-01), kept as the fallback when the app's own function is absent (tests)
    if (env.legacyFlight) return !!env.legacyFlight(d);
    if (typeof isFlightDay === 'function') return !!isFlightDay(d);
    if (!d) return false;
    const region = String(d.region == null ? '' : d.region).trim(), hotel = String(d.hotel == null ? '' : d.hotel).trim();
    return region === 'טיסות' || hotel === 'בטיסה' || hotel === 'טיסה חזרה';
  }

  /* ---- time zone arithmetic (cached: tickClocks calls these every second) ---- */
  const fmtCache = new Map(), validCache = new Map(), midnightCache = new Map();
  function clearCaches() { midnightCache.clear(); }
  function fmt(tz) {
    let f = fmtCache.get(tz);
    if (!f) {
      f = new Intl.DateTimeFormat('en-CA', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
      fmtCache.set(tz, f);
    }
    return f;
  }
  function validTz(tz) {
    if (typeof tz !== 'string' || !tz) return false;
    if (validCache.has(tz)) return validCache.get(tz);
    let ok = true; try { fmt(tz); } catch (e) { ok = false; }
    validCache.set(tz, ok); return ok;
  }
  function parts(ms, tz) {
    const o = {}; fmt(tz).formatToParts(new Date(ms)).forEach(p => { o[p.type] = p.value; });
    return { y: +o.year, mo: +o.month, d: +o.day, h: +o.hour, mi: +o.minute, s: +o.second };
  }
  function offsetMs(ms, tz) { const p = parts(ms, tz); return Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) - Math.floor(ms / 1000) * 1000; }
  function pad(n) { return String(n).padStart(2, '0'); }
  /* 'YYYY-MM-DD' of the instant on the wall clock of tz */
  function localDate(ms, tz) { const p = parts(ms, tz); return p.y + '-' + pad(p.mo) + '-' + pad(p.d); }
  function addDays(iso, n) { const t = new Date(iso + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
  /* the instant of 00:00 of iso on the wall clock of tz */
  function localMidnight(iso, tz) {
    const key = iso + '|' + tz, c = midnightCache.get(key); if (c !== undefined) return c;
    const g = Date.parse(iso + 'T00:00:00Z');
    let t = g - offsetMs(g, tz); const o2 = offsetMs(t, tz); t = g - o2;
    midnightCache.set(key, t); return t;
  }
  /* a day's date field ('15/09/2026' as the app stores it, or ISO) → 'YYYY-MM-DD' | '' */
  function f08DayIso(d) {
    const s = String((d && d.date) == null ? '' : d.date).trim();
    let m = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/.exec(s);
    if (m) return m[3] + '-' + pad(+m[2]) + '-' + pad(+m[1]);
    m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    return m ? m[1] + '-' + m[2] + '-' + m[3] : '';
  }
  function asMs(v) { return v instanceof Date ? v.getTime() : (typeof v === 'number' ? v : (v ? Date.parse(v) : Date.now())); }

  /* ---- §2 / §3: country, tz, flight of a day ---- */
  function validCountry(c) { return typeof c === 'string' && /^[A-Z]{2}$/.test(c); }
  function idxOf(d) {
    const a = days(); let i = a.indexOf(d);
    if (i < 0 && d) { const k = f08DayIso(d); if (k) i = a.findIndex(x => f08DayIso(x) === k); }
    return i;
  }
  function firstTripCountry() { const l = env.tripCountries ? env.tripCountries() : []; return Array.isArray(l) && validCountry(l[0]) ? l[0] : ''; }

  /* §3: country missing → nearest previous day that has one, else the trip's first country, else VN (the legacy Vietnam trip) */
  function f08DayCountry(d) {
    if (!d) return LEGACY_COUNTRY;
    if (off()) return LEGACY_COUNTRY;
    if (validCountry(d.country)) return d.country;
    const a = days(); let i = idxOf(d);
    for (i = i - 1; i >= 0; i--) if (validCountry(a[i] && a[i].country)) return a[i].country;
    return firstTripCountry() || LEGACY_COUNTRY;
  }
  function tzOfCountry(code) { const r = countryRow(code); const t = r && Array.isArray(r.tz) ? r.tz.find(validTz) : ''; return t || ''; }
  /* §3.1: tz missing → tz[0] of the country. (A flight day's clock boundaries use its departure zone: boundaryTz.) */
  function f08DayTz(d) {
    if (!d) return LEGACY_TZ;
    if (off()) return LEGACY_TZ;
    if (validTz(d.tz)) return d.tz;
    return tzOfCountry(f08DayCountry(d)) || LEGACY_TZ;
  }
  function f08IsFlight(d) {
    if (!d) return false;
    if (off()) return legacyFlight(d);
    return d.isFlight === true || legacyFlight(d);
  }
  /* §1 defaults: flight origin = the previous day, destination = the next day (a previous / next flight day contributes its
     own destination / origin; no neighbour = home, so the legacy seed's first and last flights read Israel). */
  function f08HomeTz() {
    if (off()) return ISRAEL_TZ;
    let cur = ''; try { cur = env.homeCurrency ? env.homeCurrency() : (root.__ptF10 && root.__ptF10.get ? root.__ptF10.get().home : ''); } catch (e) { cur = ''; }
    return !cur || cur === 'ILS' ? ISRAEL_TZ : deviceTz();   // D8: ILS (or unknown) → Israel, otherwise the device's zone
  }
  function sideOf(d, which, depth) {
    const key = which === 'from' ? 'flightFrom' : 'flightTo', e = d && d[key];
    if (e && (validCountry(e.country) || validTz(e.tz))) {
      const country = validCountry(e.country) ? e.country : '';
      return { country, tz: validTz(e.tz) ? e.tz : (tzOfCountry(country) || f08HomeTz()), city: e.city || '' };
    }
    const a = days(), i = idxOf(d), n = which === 'from' ? i - 1 : i + 1, nb = a[n];
    if (i < 0 || !nb || (depth || 0) > a.length) return { country: '', tz: f08HomeTz(), city: '' };
    if (f08IsFlight(nb)) return sideOf(nb, which === 'from' ? 'to' : 'from', (depth || 0) + 1);
    return { country: f08DayCountry(nb), tz: f08DayTz(nb), city: nb.city || '' };
  }
  function f08FlightFrom(d) { return sideOf(d, 'from', 0); }
  function f08FlightTo(d) { return sideOf(d, 'to', 0); }

  /* ---- §2: where "today" is ---- */
  /* the zone a day's midnights are counted in: a flight day's is the zone it departs from, any other day's is its own */
  function boundaryTz(d) { return f08IsFlight(d) ? f08FlightFrom(d).tz : f08DayTz(d); }
  /* instant at which day i starts: its local midnight, or the previous flight day's landing when that is later */
  function dayStart(i) {
    const a = days(), d = a[i], iso = f08DayIso(d); if (!iso) return NaN;
    let s = localMidnight(iso, boundaryTz(d));
    const p = a[i - 1];
    if (p && f08IsFlight(p)) { const L = landingMs(i - 1); if (Number.isFinite(L) && L > s) s = L; }
    return s;
  }
  /* landing of flight day i: the flight card's time when the app can give it, else the end of the day on the departure clock ("midnight") */
  function landingMs(i) {
    const a = days(), d = a[i], iso = f08DayIso(d); if (!iso) return NaN;
    let L = env.landing ? env.landing(i, d) : null;
    L = L == null ? NaN : asMs(L);
    return Number.isFinite(L) ? L : localMidnight(addDays(iso, 1), boundaryTz(d));
  }
  /* index of the trip day that "now" belongs to, -1 before the trip / after it / with no usable dates */
  function f08TodayIndex(now) {
    if (off()) return -1;
    const t = asMs(now), a = days(); let hit = -1;
    for (let i = 0; i < a.length; i++) { const s = dayStart(i); if (Number.isFinite(s) && s <= t) hit = i; else if (Number.isFinite(s)) break; }
    if (hit < 0) return -1;
    const d = a[hit], iso = f08DayIso(d);
    const mid = localMidnight(addDays(iso, 1), boundaryTz(d)), end = f08IsFlight(d) ? Math.max(landingMs(hit), mid) : mid;
    return hit === a.length - 1 && t >= end ? -1 : hit;
  }
  /* D7: on a flight day 'from' until the landing, 'to' after it; null on any other day */
  function f08HereSide(d, now) {
    if (!d || !f08IsFlight(d) || off()) return null;
    const i = idxOf(d); if (i < 0) return 'from';
    const L = landingMs(i);
    return Number.isFinite(L) && asMs(now) >= L ? 'to' : 'from';
  }
  function here(now) {
    const i = f08TodayIndex(now); if (i < 0) return null;
    const d = days()[i];
    if (f08IsFlight(d)) { const s = f08HereSide(d, now) === 'to' ? f08FlightTo(d) : f08FlightFrom(d); return { country: s.country, tz: s.tz, i }; }
    return { country: f08DayCountry(d), tz: f08DayTz(d), i };
  }
  /* the zone of "כאן": the trip's own while the trip runs, the device's before / after it (and with the flag off, as alpha.12.1) */
  function f08HereTz(now) { if (off()) return deviceTz(); const h = here(now); return h && h.tz ? h.tz : deviceTz(); }
  /* the country of "כאן" ('' outside the trip: callers fall back to what they did in alpha.12.1; with the flag off, 'VN') */
  function f08HereCountry(now) { if (off()) return LEGACY_COUNTRY; const h = here(now); return h ? h.country : ''; }
  /* §4.4: one clock when "here" and "home" are the same zone */
  function f08SameClock(now) { return f08HereTz(now) === f08HomeTz(); }

  /* ---- §1: ranges (computed, never stored) ---- */
  const FIELDS = ['country', 'city', 'tz'];
  function sameSpot(x, y) { return (x.country || '') === (y.country || '') && (x.city || '') === (y.city || '') && (x.tz || '') === (y.tz || ''); }
  /* runs of consecutive non-flight days with the same country+city+tz; [{from, to, country, city, tz}] (indexes); flight days are returned as {flight:true, from:i, to:i}.
     A day with none of the three fields is a day of the derived range (§3), so it joins the neighbour it is derived from. */
  function f08Ranges(list) {
    const a = list || days(), out = [];
    a.forEach((d, i) => {
      if (f08IsFlight(d)) { out.push({ flight: true, from: i, to: i }); return; }
      const spot = { country: f08DayCountry(d), city: d.city || '', tz: f08DayTz(d) }, last = out[out.length - 1];
      if (last && !last.flight && last.to === i - 1 && sameSpot(last, spot)) last.to = i; else out.push({ from: i, to: i, ...spot });
    });
    return out;
  }
  /* §1: saving a range writes country/city/tz into each of its days in ONE new array; flight days inside the range are untouched.
     Returns {days, changed:[indexes]}. `from`/`to` are day indexes (inclusive). */
  function f08ApplyRange(list, from, to, spot) {
    const a = list || days(), country = spot && spot.country, tz = spot && spot.tz, city = String((spot && spot.city) || '').slice(0, 60);
    if (!validCountry(country)) throw new Error('f08: country must be an ISO-2 code');
    const zone = validTz(tz) ? tz : tzOfCountry(country) || LEGACY_TZ, changed = [];
    const next = a.map((d, i) => {
      if (i < Math.min(from, to) || i > Math.max(from, to) || f08IsFlight(d)) return d;
      changed.push(i);
      const n = { ...d, country, tz: zone };
      if (city) n.city = city; else delete n.city;
      return n;
    });
    return { days: next, changed };
  }
  /* "מחיקת הטווח": clear country/city/tz from the days of the range (back to §3 derivation); flight days untouched */
  function f08ClearRange(list, from, to) {
    const a = list || days(), changed = [];
    const next = a.map((d, i) => {
      if (i < Math.min(from, to) || i > Math.max(from, to) || f08IsFlight(d)) return d;
      changed.push(i); const n = { ...d }; FIELDS.forEach(k => { delete n[k]; }); return n;
    });
    return { days: next, changed };
  }
  /* AC4: the time-zone picker is shown only for a country with more than one zone */
  function f08NeedsTzPicker(code) { const r = countryRow(code); return !!(r && Array.isArray(r.tz) && r.tz.length > 1); }

  /* =====================================================================================================================
     CHANGE 2026-11-13 F08-A2-01 (conversation 2): new section (the previous version of this file had helpers only).
     Spec §4.1 "מדינות לפי ימים" (F08_Ranges) and §4.2 range sheet (F08_RangeSheet).
     - Pure part (Node-tested): f08RangesView, f08RangesHtml, f08NewRangeState / f08EditRangeState, f08SheetHtml,
       f08CountryListHtml, f08UiCommit.
     - Browser part: attach (gate: role / client / trip) and mount (main script: $, days, setDays, switchPanel, toast).
       mount adds the "עוד" row, the panel #ptF08Panel and the sheet #ptF08Layer. Nothing runs unless index.html calls mount,
       and it does that only with F08_FEATURE==='on'.
     Writing: one setDays(newArray) per save = the app's saveTrip → SS.set (offline queue and viewer guard as for any edit).
     ===================================================================================================================== */
  const PALETTE = ['#0f6b4f', '#c2410c', '#1d4ed8', '#7c3aed', '#b45309', '#0e7490', '#be185d', '#4d7c0f'];
  function escH(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
  function cName(code) { const r = countryRow(code); return (r && r.he) || code || ''; }
  function cFlag(code) { const r = countryRow(code); return (r && r.flag) || '🏳️'; }
  function allCountries() {
    const m = env.countries ? env.countries() : null; if (!m) return [];
    return (Array.isArray(m) ? m : Object.keys(m).map(k => Object.assign({ code: k }, m[k]))).filter(x => x && validCountry(x.code));
  }
  function utcLabel(tz, ms) {
    if (!validTz(tz)) return '';
    const m = Math.round(offsetMs(Number.isFinite(ms) ? ms : Date.now(), tz) / MIN), a = Math.abs(m);
    return 'UTC' + (m < 0 ? '-' : '+') + Math.floor(a / 60) + (a % 60 ? ':' + pad(a % 60) : '');
  }
  function dayNo(d, i) { return d && d.day != null && d.day !== '' ? d.day : i + 1; }
  function dayDM(d) { const k = f08DayIso(d); return k ? k.slice(8, 10) + '/' + k.slice(5, 7) : ''; }
  function dayMs(d) { const k = f08DayIso(d); return k ? Date.parse(k + 'T12:00:00Z') : NaN; }
  function sideName(s) { return s && s.country ? cName(s.country) + (s.city ? ' · ' + s.city : '') : 'בית'; }
  const LTR = s => '<span dir="ltr">' + escH(s) + '</span>';

  /* what the screen shows: rows (ranges + flight days, in trip order) and the axis strip */
  function f08RangesView() {
    const a = days(), colors = {}; let nc = 0;
    const color = c => { if (!(c in colors)) colors[c] = PALETTE[nc++ % PALETTE.length]; return colors[c]; };
    const rows = f08Ranges(a).map(r => {
      const d0 = a[r.from], d1 = a[r.to];
      if (r.flight) return { kind: 'flight', from: r.from, to: r.to, day: dayNo(d0, r.from), date: dayDM(d0), fromName: sideName(f08FlightFrom(d0)), toName: sideName(f08FlightTo(d0)) };
      const n = r.to - r.from + 1;
      return {
        kind: 'range', from: r.from, to: r.to, n, country: r.country, name: cName(r.country), flag: cFlag(r.country), city: r.city, tz: r.tz,
        utc: utcLabel(r.tz, dayMs(d0)), color: color(r.country),
        auto: a.slice(r.from, r.to + 1).every(d => !validCountry(d && d.country)),   /* nothing saved on these days: §3 derivation */
        label: n > 1 ? 'ימים ' + dayNo(d0, r.from) + '–' + dayNo(d1, r.to) : 'יום ' + dayNo(d0, r.from),
        dates: n > 1 && dayDM(d0) && dayDM(d1) ? dayDM(d0) + '–' + dayDM(d1) : dayDM(d0),
      };
    });
    return { rows, total: a.length, countries: Object.keys(colors), flights: rows.filter(r => r.kind === 'flight').length, first: a.length ? dayDM(a[0]) : '', last: a.length ? dayDM(a[a.length - 1]) : '' };
  }
  function f08RangesHtml(view, canEdit) {
    const v = view || f08RangesView();
    if (!v.total) return '<div class="p08-note info" id="ptF08Empty">אין ימים בטיול.</div>';
    let h = canEdit ? '' : '<div class="p08-note info" id="ptF08RO">צפייה בלבד – רק מנהלים ועורכים משנים מדינות וימים.</div>';
    h += '<div class="p08-axis" id="ptF08Axis" role="img" aria-label="ציר הטיול: ' + v.total + ' ימים">' + v.rows.map(r => r.kind === 'flight'
      ? '<span class="p08-seg fl" style="flex:1 1 0" title="יום טיסה">✈</span>'
      : '<span class="p08-seg" style="flex:' + r.n + ' 1 0;background:' + r.color + '" title="' + escH(r.name + ' · ' + r.label) + '">' + escH(r.flag) + '</span>').join('') + '</div>' +
      '<div class="p08-ends"><span>' + escH(v.first) + '</span><span>' + escH(v.last) + '</span></div>';
    h += v.rows.map(r => {
      if (r.kind === 'flight') return '<div class="p08-row fl" data-f08-flight="' + r.from + '"><span class="p08-ic">✈️</span><span class="p08-nm"><b>יום טיסה · יום ' + escH(r.day) + '</b><span class="p08-sub">' + LTR(r.date) + ' · ' + escH(r.fromName) + ' ← ' + escH(r.toName) + '</span></span></div>';
      const inner = '<span class="p08-ic" style="border-inline-start:4px solid ' + r.color + '">' + escH(r.flag) + '</span><span class="p08-nm"><b>' + escH(r.name) + (r.city ? ' · ' + escH(r.city) : '') + '</b><span class="p08-sub">' + escH(r.label) + (r.dates ? ' · ' + LTR(r.dates) : '') + (r.utc ? ' · ' + LTR(r.utc) : '') + '</span></span>' +
        (r.auto ? '<span class="p08-tag">אוטומטי</span>' : '');
      return canEdit ? '<button type="button" class="p08-row" data-f08-range="' + r.from + '-' + r.to + '">' + inner + '<span class="p08-chev">‹</span></button>' : '<div class="p08-row" data-f08-row="' + r.from + '-' + r.to + '">' + inner + '</div>';
    }).join('');
    if (canEdit) h += '<div style="margin-top:8px"><button type="button" class="p08-btn" id="ptF08Add">+ טווח ימים חדש</button></div>';
    return h;
  }

  /* sheet state: {mode, orig:{from,to}|null, country, from, to, city, tz, pick, confirmDel} */
  function f08NewRangeState() {
    const a = days(); let i = a.findIndex(d => !f08IsFlight(d) && !validCountry(d && d.country)); if (i < 0) i = a.findIndex(d => !f08IsFlight(d)); if (i < 0) i = 0;
    let j = i; while (j + 1 < a.length && !f08IsFlight(a[j + 1]) && !validCountry(a[j + 1] && a[j + 1].country)) j++;
    return { mode: 'new', orig: null, country: '', from: i, to: j, city: '', tz: '', pick: true, confirmDel: false };
  }
  function f08EditRangeState(from, to) {
    const a = days(), d = a[from] || {}, auto = a.slice(from, to + 1).every(x => !validCountry(x && x.country));
    return { mode: 'edit', orig: { from, to }, auto, country: f08DayCountry(d), from, to, city: d.city || '', tz: f08DayTz(d), pick: false, confirmDel: false };
  }
  function f08CountryListHtml(q, extra) {
    const all = allCountries(); if (!all.length) return '<div class="p08-sub" style="margin:6px 4px">אין חיבור לרשימת המדינות – נסו שוב כשיש רשת.</div>';
    const norm = s => String(s || '').toLowerCase().trim(), k = norm(q), by = {}; all.forEach(x => { by[x.code] = x; });
    const opt = x => '<button type="button" class="p08-row" data-f08-c="' + x.code + '"><span class="p08-ic">' + escH(x.flag || '🏳️') + '</span><span class="p08-nm"><b>' + escH(x.he || x.code) + '</b><span class="p08-sub">' + escH(x.en || '') + '</span></span></button>';
    if (k) {
      const hit = all.filter(x => norm(x.he).indexOf(k) > -1 || norm(x.en).indexOf(k) > -1 || norm(x.code) === k).slice(0, 40);
      return hit.length ? hit.map(opt).join('') : '<div class="p08-sub" style="margin:6px 4px">לא נמצאה מדינה</div>';
    }
    const mine = []; (extra || []).concat(env.tripCountries ? env.tripCountries() || [] : [], days().map(d => d && d.country)).forEach(c => { if (by[c] && mine.indexOf(c) < 0) mine.push(c); });
    const pop = all.filter(x => x.popular && mine.indexOf(x.code) < 0).sort((x, y) => String(x.he).localeCompare(String(y.he), 'he'));
    return (mine.length ? '<div class="p08-grp">בטיול</div>' + mine.map(c => opt(by[c])).join('') : '') + (pop.length ? '<div class="p08-grp">נפוצות</div>' + pop.map(opt).join('') : '') + '<div class="p08-sub" style="margin:6px 4px">לכל שאר המדינות – חפשו בשם.</div>';
  }
  function f08SheetHtml(st) {
    const a = days(), c = st.country, row = c ? countryRow(c) : null, zones = row && Array.isArray(row.tz) ? row.tz.filter(validTz) : [];
    const lo = Math.min(st.from, st.to), hi = Math.max(st.from, st.to), ms = dayMs(a[lo]);
    const opts = sel => a.map((d, i) => '<option value="' + i + '"' + (i === sel ? ' selected' : '') + '>יום ' + escH(dayNo(d, i)) + (dayDM(d) ? ' · ' + dayDM(d) : '') + (f08IsFlight(d) ? ' ✈' : '') + '</option>').join('');
    const nFl = a.slice(lo, hi + 1).filter(f08IsFlight).length, nDays = hi - lo + 1 - nFl;
    let h = '<div class="p08-handle"></div><div class="p08-head"><div class="p08-nm"><b>' + (st.mode === 'edit' ? 'עריכת טווח' : 'טווח ימים חדש') + '</b><span class="p08-sub">' + (nDays === 1 ? 'יום אחד' : nDays + ' ימים') + (nFl ? ' · ימי טיסה בטווח לא משתנים' : '') + '</span></div><button type="button" class="p08-x" data-f08-close aria-label="סגירה">×</button></div>';
    h += '<div class="p08-lbl">מדינה</div><button type="button" class="p08-field" id="ptF08Country" aria-expanded="' + (st.pick ? 'true' : 'false') + '">' + (c ? '<span>' + escH(cFlag(c)) + ' ' + escH(cName(c)) + '</span>' : '<span class="p08-sub" style="font-size:15px">בחירת מדינה</span>') + '<span class="p08-chev">' + (st.pick ? '▴' : '▾') + '</span></button>';
    if (st.pick) h += '<input id="ptF08Search" class="p08-in" type="search" placeholder="חיפוש מדינה" autocomplete="off" aria-label="חיפוש מדינה"><div id="ptF08CList" class="p08-clist">' + f08CountryListHtml('', c ? [c] : []) + '</div>';
    h += '<div class="p08-2"><label class="p08-lbl" for="ptF08From">מיום<select id="ptF08From" class="p08-in">' + opts(st.from) + '</select></label><label class="p08-lbl" for="ptF08To">עד יום<select id="ptF08To" class="p08-in">' + opts(st.to) + '</select></label></div>';
    h += '<label class="p08-lbl" for="ptF08City">עיר (לא חובה)<input id="ptF08City" class="p08-in" type="text" maxlength="60" autocomplete="off" value="' + escH(st.city || '') + '"></label>';
    if (c && zones.length > 1) h += '<label class="p08-lbl" for="ptF08Tz">אזור זמן<select id="ptF08Tz" class="p08-in" dir="ltr">' + zones.map(z => '<option value="' + escH(z) + '"' + (z === st.tz ? ' selected' : '') + '>' + escH(z.replace(/_/g, ' ') + ' (' + utcLabel(z, ms) + ')') + '</option>').join('') + '</select></label>';
    else if (c && zones.length) h += '<div class="p08-sub" id="ptF08TzLine">אזור זמן: ' + LTR(zones[0].replace(/_/g, ' ') + ' · ' + utcLabel(zones[0], ms)) + '</div>';
    h += '<button type="button" class="p08-btn" id="ptF08Save"' + (c && nDays > 0 ? '' : ' disabled') + '>שמירה</button>';
    if (st.mode === 'edit' && !st.auto) h += '<button type="button" class="p08-btn red' + (st.confirmDel ? '' : ' out') + '" id="ptF08Del">' + (st.confirmDel ? 'לאשר מחיקה? הימים יחזרו לברירת המחדל' : 'מחיקת הטווח') + '</button>';
    return h;
  }
  /* the only writer: op = {type:'apply', from, to, spot:{country, city, tz}} | {type:'clear', from, to}; deps = {days(), setDays(a), role()} */
  async function f08UiCommit(deps, op) {
    if (off()) return { ok: false, reason: 'off' };
    if ((deps.role ? deps.role() : null) === 'viewer') return { ok: false, reason: 'viewer' };   /* AC9 (SS.set blocks it as well) */
    const a = deps.days(), from = Number(op && op.from), to = Number(op && op.to);
    if (!Array.isArray(a) || !Number.isInteger(from) || !Number.isInteger(to) || Math.min(from, to) < 0 || Math.max(from, to) >= a.length) return { ok: false, reason: 'range' };
    let r;
    if (op.type === 'clear') r = f08ClearRange(a, from, to);
    else { if (!validCountry(op.spot && op.spot.country)) return { ok: false, reason: 'country' }; r = f08ApplyRange(a, from, to, op.spot); }
    if (!r.changed.length) return { ok: false, reason: 'flights' };   /* only flight days in the range */
    await deps.setDays(r.days);                                        /* ONE write of the whole days array (§1) */
    clearCaches();
    return { ok: true, changed: r.changed };
  }

  /* ---------------- browser part ---------------- */
  let gate = null;
  function attach(a) { if (!gate && a && typeof a === 'object') gate = a; }
  const CSS = `
#ptF08Panel .p08-top{position:relative;padding:14px 56px 6px;text-align:center}#ptF08Panel .p08-top h1{margin:0;font-size:17px}
#ptF08Back{position:absolute;right:2px;top:4px;width:44px;height:44px;border:0;background:none;font-size:24px;color:var(--text,#17211b);cursor:pointer}
.p08-sub{display:block;font-size:11.5px;font-weight:400;color:var(--muted,#5f6861)}
.p08-body{display:flex;flex-direction:column;gap:6px;max-width:560px;margin:0 auto;padding:6px 2px 24px}
.p08-axis{display:flex;gap:2px;height:30px;border-radius:10px;overflow:hidden;margin-top:4px}
.p08-seg{min-width:0;display:flex;align-items:center;justify-content:center;font-size:13px;line-height:1;color:#fff;overflow:hidden;white-space:nowrap}
.p08-seg.fl{background:#c9ccc3;color:#3a443d;font-size:10px}
.p08-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--muted,#5f6861);margin:0 2px 4px}
.p08-row{display:flex;align-items:center;gap:10px;width:100%;box-sizing:border-box;text-align:right;background:#fff;border:1px solid #e4e6df;border-radius:12px;padding:5px 10px;min-height:54px;color:#17211b;font-family:inherit;font-size:inherit}
button.p08-row{cursor:pointer}.p08-row.fl{background:#f1f0ea;border-style:dashed}
.p08-ic{width:36px;height:36px;border-radius:10px;background:#f5f2ea;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;box-sizing:border-box}
.p08-nm{flex:1;min-width:0}.p08-nm b{display:block;font-size:14px;overflow-wrap:anywhere}
.p08-tag{font-size:11px;font-weight:700;color:var(--muted,#5f6861);background:#ecebe4;border-radius:999px;padding:2px 9px;white-space:nowrap}
.p08-chev{color:var(--muted,#5f6861);font-size:16px;flex-shrink:0}
.p08-grp{font-size:12px;font-weight:800;color:var(--muted,#5f6861);margin:6px 4px 0}
.p08-note{border-radius:14px;padding:10px 12px;font-size:12.5px;line-height:1.45}.p08-note.info{background:#eef4fb;color:#1d3f63;border:1px solid #cfe0f2}
.p08-btn{display:flex;align-items:center;justify-content:center;gap:6px;width:100%;min-height:46px;border:0;border-radius:14px;background:var(--primary,#0f6b4f);color:#fff;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;padding:4px 10px;box-sizing:border-box}
.p08-btn.red{background:#b42318}.p08-btn.red.out{background:#fff;color:#b42318;border:1px solid #b42318}.p08-btn[disabled]{background:#c9ccc3;color:#fff;border:0;cursor:default}
#ptF08Layer{position:fixed;inset:0;z-index:1150;display:flex;align-items:flex-end;justify-content:center}#ptF08Layer[hidden]{display:none}
#ptF08Layer .p08-scrim{position:absolute;inset:0;background:#0f172a66}
#ptF08Layer .p08-sheet{position:relative;width:100%;max-width:560px;max-height:min(90vh,760px);overflow-y:auto;overflow-x:hidden;background:#fff;border-radius:20px 20px 0 0;box-shadow:0 -8px 28px #00000020;padding:10px 16px calc(20px + env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:8px;color:#17211b;box-sizing:border-box}
.p08-handle{width:38px;height:4px;border-radius:99px;background:#e4e6df;margin:0 auto}
.p08-head{display:flex;align-items:center;gap:10px}.p08-head .p08-nm b{font-size:17px}
.p08-x{width:44px;height:44px;border-radius:12px;border:1px solid #e4e6df;background:#fff;font-size:18px;cursor:pointer;flex-shrink:0}
.p08-lbl{display:flex;flex-direction:column;gap:4px;font-size:12px;font-weight:800;color:var(--muted,#5f6861);min-width:0}
.p08-in{width:100%;box-sizing:border-box;min-height:46px;padding:0 12px;border:1px solid #d6d9d0;border-radius:12px;font-size:16px;font-family:inherit;font-weight:400;color:#17211b;background:#fff;min-width:0}
.p08-field{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;box-sizing:border-box;min-height:48px;padding:0 12px;border:1px solid #d6d9d0;border-radius:12px;background:#fff;font-size:16px;font-weight:700;font-family:inherit;color:#17211b;cursor:pointer;text-align:right}
.p08-clist{display:flex;flex-direction:column;gap:5px;max-height:38vh;overflow-y:auto;border:1px solid #efeee8;border-radius:12px;padding:6px}
.p08-2{display:flex;gap:8px}.p08-2>*{flex:1}
`;
  function mount(deps) {
    if (off() || typeof document === 'undefined' || !deps || typeof deps.$ !== 'function') return false;
    if (document.getElementById('ptF08Css')) return true;
    const $ = deps.$, toast = m => { try { deps.toast(m); } catch (e) { } };
    const online = () => { try { return navigator.onLine !== false; } catch (e) { return true; } };
    const role = () => { try { return gate ? gate.role() : null; } catch (e) { return null; } };
    const canEdit = () => role() !== 'viewer';   /* D5: managers and editors (no gate = local mode = the device's own trip) */
    let byCode = null, tripC = [], st = null, busy = false;
    const st0 = document.createElement('style'); st0.id = 'ptF08Css'; st0.textContent = CSS; document.head.appendChild(st0);
    f08Configure({ countries: () => byCode, tripCountries: () => tripC });

    /* countries.json (names, flags, zones) and the trip's own countries (for §3 and the top of the picker) */
    function loadCountries() {
      if (byCode) return Promise.resolve(byCode);
      const p = root.__ptF04 && typeof root.__ptF04.curData === 'function' ? Promise.resolve(root.__ptF04.curData()).then(d => d && d.byCode) : Promise.resolve(null);
      return p.then(m => m || fetch('countries.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : [])).then(l => { const o = {}; (l || []).forEach(x => { if (x && x.code) o[x.code] = x; }); return Object.keys(o).length ? o : null; }))
        .then(m => { if (m) { byCode = m; f08Configure({}); } return byCode; }).catch(() => null);
    }
    async function loadTripCountries() {
      let t = null; try { t = gate && gate.tripId(); } catch (e) { }
      const key = 'pt-f08:tc:' + (t || 'local');
      try { const c = JSON.parse(localStorage.getItem(key) || '[]'); if (Array.isArray(c)) tripC = c.filter(validCountry); } catch (e) { }
      let c = null; try { c = gate && gate.client(); } catch (e) { }
      if (!c || !t || !online()) return;
      try {
        const r = await gate.withTimeout(c.from('trip_countries').select('country_code,sort').eq('trip_id', t), gate.timeoutMs);
        if (r && !r.error && Array.isArray(r.data)) {
          tripC = r.data.slice().sort((x, y) => (Number(x.sort) || 0) - (Number(y.sort) || 0)).map(x => x.country_code).filter(validCountry);
          try { localStorage.setItem(key, JSON.stringify(tripC)); } catch (e) { }
          f08Configure({});
        }
      } catch (e) { }
    }

    /* "עוד" row */
    function moreHost() { const more = $('more'), tb = more && more.querySelector('.topbar'); return tb && tb.nextElementSibling; }
    function paintMore() {
      const host = moreHost(); if (!host) return;
      let row = $('ptF08Row');
      if (!row) {
        row = document.createElement('button'); row.type = 'button'; row.className = 'listitem'; row.id = 'ptF08Row';
        row.style.cssText = 'width:100%;text-align:right;font:inherit;color:inherit;min-height:58px';
        const after = $('ptF10bRow') || $('ptF06MembersRow') || $('ptAccount');
        if (after && after.parentNode === host) host.insertBefore(row, after.nextSibling); else host.insertBefore(row, host.firstChild);
        row.onclick = openPanel;
      }
      const v = f08RangesView();
      row.innerHTML = '<div class="ic" style="background:#e7f3ec" aria-hidden="true">🌍</div><div class="lbl">מדינות לפי ימים<span id="ptF08RowSub" style="display:block;font-weight:400;font-size:.72rem;color:var(--muted)">' +
        escH(v.countries.map(cFlag).join(' ') + (v.countries.length ? ' · ' : '') + v.total + ' ימים') + '</span></div><div class="chev">‹</div>';
    }

    /* panel */
    function ensurePanel() {
      let p = $('ptF08Panel'); if (p) return p;
      const more = $('more'); if (!more) return null;
      p = document.createElement('section'); p.id = 'ptF08Panel'; p.className = 'panel'; p.setAttribute('aria-labelledby', 'ptF08Title');
      p.innerHTML = '<div class="p08-top"><button type="button" id="ptF08Back" aria-label="חזרה">›</button><h1 id="ptF08Title">מדינות לפי ימים</h1><div class="p08-sub" id="ptF08Sub"></div></div><div class="p08-body" id="ptF08Body"></div>';
      more.parentNode.insertBefore(p, more.nextSibling);
      $('ptF08Back').onclick = () => { try { deps.switchPanel('more'); } catch (e) { } };
      return p;
    }
    const panelOpen = () => { const p = $('ptF08Panel'); return !!p && p.classList.contains('active'); };
    function paintPanel() {
      const p = $('ptF08Panel'); if (!p) return;
      const v = f08RangesView(), edit = canEdit();
      $('ptF08Sub').textContent = v.total + ' ימים · ' + v.countries.length + (v.countries.length === 1 ? ' מדינה' : ' מדינות') + (v.flights ? ' · ' + v.flights + ' ימי טיסה' : '');
      $('ptF08Body').innerHTML = f08RangesHtml(v, edit);
      const add = $('ptF08Add'); if (add) add.onclick = () => openSheet(f08NewRangeState());
      p.querySelectorAll('[data-f08-range]').forEach(b => { b.onclick = () => { const x = b.dataset.f08Range.split('-'); openSheet(f08EditRangeState(+x[0], +x[1])); }; });
    }
    async function openPanel() {
      const p = ensurePanel(); if (!p) return;
      document.querySelectorAll('.panel').forEach(x => x.classList.toggle('active', x === p));
      document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.panel === 'more'));
      try { root.scrollTo(0, 0); } catch (e) { }
      paintPanel();
      await Promise.all([loadCountries(), loadTripCountries()]);
      paintPanel(); paintMore();
    }

    /* sheet */
    function layer() {
      let l = $('ptF08Layer');
      if (!l) {
        l = document.createElement('div'); l.id = 'ptF08Layer'; l.hidden = true; document.body.appendChild(l);
        document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('ptF08Layer').hidden) closeSheet(); });
      }
      return l;
    }
    function closeSheet() { const l = $('ptF08Layer'); if (l) { l.hidden = true; l.innerHTML = ''; } st = null; }
    function readForm() {
      if (!st) return;
      const f = $('ptF08From'), t = $('ptF08To'), c = $('ptF08City'), z = $('ptF08Tz');
      if (f) st.from = +f.value; if (t) st.to = +t.value; if (c) st.city = c.value.trim().slice(0, 60); if (z) st.tz = z.value;
    }
    function paintSheet() {
      const l = layer();
      l.innerHTML = '<div class="p08-scrim" data-f08-close></div><div class="p08-sheet" id="ptF08Sheet" role="dialog" aria-modal="true" aria-label="' + (st.mode === 'edit' ? 'עריכת טווח' : 'טווח ימים חדש') + '">' + f08SheetHtml(st) + '</div>';
      l.hidden = false;
      l.querySelectorAll('[data-f08-close]').forEach(x => { x.onclick = closeSheet; });
      $('ptF08Country').onclick = () => { readForm(); st.pick = !st.pick; st.confirmDel = false; paintSheet(); };
      const pickC = () => l.querySelectorAll('[data-f08-c]').forEach(b => { b.onclick = () => { readForm(); st.country = b.dataset.f08C; st.tz = ''; st.pick = false; paintSheet(); }; });
      const s = $('ptF08Search'); if (s) { s.oninput = () => { $('ptF08CList').innerHTML = f08CountryListHtml(s.value, st.country ? [st.country] : []); pickC(); }; pickC(); }
      $('ptF08From').onchange = () => { readForm(); if (st.to < st.from) st.to = st.from; paintSheet(); };
      $('ptF08To').onchange = () => { readForm(); if (st.to < st.from) st.from = st.to; paintSheet(); };
      $('ptF08Save').onclick = () => { readForm(); commit({ type: 'apply', from: st.from, to: st.to, spot: { country: st.country, city: st.city, tz: st.tz } }, 'הטווח נשמר'); };
      const del = $('ptF08Del'); if (del) del.onclick = () => { readForm(); if (!st.confirmDel) { st.confirmDel = true; paintSheet(); return; } commit({ type: 'clear', from: st.orig.from, to: st.orig.to }, 'הטווח נמחק'); };
    }
    function openSheet(s) { if (!canEdit()) return; st = s; loadCountries().then(() => { if (st === s) paintSheet(); }); paintSheet(); }
    async function commit(op, okMsg) {
      if (busy) return; busy = true;
      document.querySelectorAll('#ptF08Layer button').forEach(b => { b.disabled = true; });
      let r; try { r = await f08UiCommit({ days: deps.days, setDays: deps.setDays, role }, op); } catch (e) { r = { ok: false, reason: 'error' }; }
      busy = false;
      if (r.ok) { closeSheet(); toast('✅ ' + okMsg + (online() ? '' : ' במכשיר – יישלח כשיחזור חיבור')); }
      else { toast('⚠️ ' + ({ viewer: 'צפייה בלבד – השינוי לא נשמר', flights: 'בטווח יש רק ימי טיסה', country: 'צריך לבחור מדינה' }[r.reason] || 'השמירה נכשלה – נסו שוב')); if (st) paintSheet(); }
      paintPanel(); paintMore();
    }

    /* boot */
    paintMore();
    try { const host = moreHost(); if (host) new MutationObserver(() => { if (!$('ptF08Row')) paintMore(); }).observe(host, { childList: true }); } catch (e) { }
    Promise.all([loadCountries(), loadTripCountries()]).then(() => { paintMore(); if (panelOpen()) paintPanel(); });
    root.addEventListener('online', () => { loadCountries(); loadTripCountries().then(() => { if (panelOpen()) paintPanel(); }); });
    return true;
  }

  const api = { version: VERSION, f08Configure, f08DayIso, f08DayCountry, f08DayTz, f08IsFlight, f08FlightFrom, f08FlightTo, f08TodayIndex, f08HereSide, f08HereTz, f08HereCountry, f08HomeTz, f08SameClock, f08Ranges, f08ApplyRange, f08ClearRange, f08NeedsTzPicker, f08LocalDate: localDate,
    /* CHANGE 2026-11-13 F08-A2-01: conversation 2 additions */ f08RangesView, f08RangesHtml, f08NewRangeState, f08EditRangeState, f08SheetHtml, f08CountryListHtml, f08UiCommit, attach, mount };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptF08 = api; Object.keys(api).forEach(k => { if (k.indexOf('f08') === 0) root[k] = api[k]; }); }
})(typeof window !== 'undefined' ? window : globalThis);
