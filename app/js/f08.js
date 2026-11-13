/* Lonely Planner · F08 – country and time zone for every day (stage A, conversation 1: day fields + helper functions) · version 3.0.0-alpha.13
   CHANGE 2026-11-13 F08-A1-01: new file (no previous version). Spec: docs/F08_spec.md §1–§3 (+ D8 home clock in §4.4 / AC15).
   Pure helpers only: no screens, no storage, no DOM, nothing is wired into app/index.html yet (conversation 2/3).
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

  const api = { version: VERSION, f08Configure, f08DayIso, f08DayCountry, f08DayTz, f08IsFlight, f08FlightFrom, f08FlightTo, f08TodayIndex, f08HereSide, f08HereTz, f08HereCountry, f08HomeTz, f08SameClock, f08Ranges, f08ApplyRange, f08ClearRange, f08NeedsTzPicker, f08LocalDate: localDate };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptF08 = api; Object.keys(api).forEach(k => { if (k.indexOf('f08') === 0) root[k] = api[k]; }); }
})(typeof window !== 'undefined' ? window : globalThis);
