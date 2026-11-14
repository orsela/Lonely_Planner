/* Lonely Planner · F24 – flight and hotel search from the trip, stage 1: smart links (conversation 1: data + link builders) · version 3.0.0-alpha.14
   CHANGE 2026-11-14 F24-A1-01: new file (no previous version). Spec: claude/Plan_Travel_F24_spec.md, rulings C1–C8 at the data level:
   when a flight / lodging search applies (C1–C3), origin and destination (C4), round trip (C5), travelers (C6), the four link
   builders (C7, R2 fallback), the chat request → search (C8, pure part), airport lookup for the origin sheet (C4).
   No screens yet and not wired: no script tag in app/index.html, no TRAVELSEARCH_FEATURE flag there, no version bump, not in sw.js.
   Everything the helpers need arrives through f24Configure(); in the browser the defaults read window.__ptF08 and the flag.
   TRAVELSEARCH_FEATURE === 'off' → f24FlightSearch / f24LodgingSearch / f24ChatSearch return null (no card anywhere). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.14';
  const HOME_IATA = 'TLV', PINNED = ['TLV', 'ETM'], HOME_CC = 'IL', RECENT_MAX = 3;

  /* ---- environment (injectable) ---- */
  const env = {};   // f08 (the F08 api), days(), reservations() → [], members() → number, airports() → [{iata,he,en,cc,alt?}], countries() → {CODE:{en,he}}, feature()
  let index = null;
  function f24Configure(o) { Object.assign(env, o || {}); index = null; }
  function F8() { return env.f08 || root.__ptF08 || null; }
  function days() { const v = env.days ? env.days() : (typeof tripData !== 'undefined' ? tripData : []); return Array.isArray(v) ? v : []; }
  function reservations() { const v = env.reservations ? env.reservations() : []; return Array.isArray(v) ? v : []; }
  function airports() { const v = env.airports ? env.airports() : []; return Array.isArray(v) ? v : []; }
  function feature() { return env.feature ? env.feature() : (typeof TRAVELSEARCH_FEATURE !== 'undefined' ? TRAVELSEARCH_FEATURE : 'on'); }
  function off() { return feature() === 'off' || !F8(); }
  function countryEn(code) { const m = env.countries ? env.countries() : null; const r = m && m[code]; return (r && r.en) || ''; }
  function countryHe(code) { const m = env.countries ? env.countries() : null; const r = m && m[code]; return (r && r.he) || countryEn(code); }

  /* ---- small helpers ---- */
  function isIso(s) { if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false; const t = new Date(s + 'T00:00:00Z'); return !isNaN(t) && t.toISOString().slice(0, 10) === s; }
  function addDays(iso, n) { const t = new Date(iso + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
  function diffDays(a, b) { return Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000); }
  function yymmdd(iso) { return iso.slice(2, 4) + iso.slice(5, 7) + iso.slice(8, 10); }
  function norm(s) { return String(s == null ? '' : s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/['"`׳״’.,()\-_/]/g, ' ').replace(/\s+/g, ' ').trim(); }
  function dayIso(d) { const f = F8(); const k = f && d ? f.f08DayIso(d) : ''; return isIso(k) ? k : ''; }
  function adultsOf(n) { n = Math.floor(Number(n)); return Number.isFinite(n) && n >= 1 ? n : 1; }

  /* ---- airports (C4, C7) ---- */
  function buildIndex() {
    const byIata = new Map(), byName = new Map();
    for (const a of airports()) {
      if (!a || !/^[A-Z]{3}$/.test(a.iata || '')) continue;
      byIata.set(a.iata, a);
      [a.he, a.en].concat(Array.isArray(a.alt) ? a.alt : []).forEach(n => { const k = norm(n); if (k && !byName.has(k)) byName.set(k, a); });
    }
    index = { byIata, byName };
  }
  function idx() { if (!index) buildIndex(); return index; }
  function f24Airport(iata) { return idx().byIata.get(String(iata || '').toUpperCase()) || null; }
  /* a city name (Hebrew / English / alias) or an IATA code → the airport row, or null */
  function f24AirportByName(text) {
    const raw = String(text == null ? '' : text).trim(); if (!raw) return null;
    if (/^[A-Za-z]{3}$/.test(raw) && f24Airport(raw)) return f24Airport(raw);
    return idx().byName.get(norm(raw)) || null;
  }
  function place(a) { return { iata: a.iata, city: a.en, cityHe: a.he, country: a.cc }; }
  /* F08 side {country, city} → a place {iata, city, cityHe, country}; home (no country / Israel without a known city) → TLV */
  function placeOfSide(side) {
    const s = side || {}, city = String(s.city || '').trim(), cc = s.country || '';
    const a = city ? f24AirportByName(city) : null;
    if (a && (!cc || a.cc === cc)) return place(a);
    if (!cc || cc === HOME_CC) { const h = f24Airport(HOME_IATA); return h ? place(h) : { iata: HOME_IATA, city: 'Tel Aviv', cityHe: 'תל אביב', country: HOME_CC }; }
    return { iata: '', city, cityHe: city, country: cc };
  }
  function isHomePlace(p) { return !!p && p.country === HOME_CC; }
  /* what the Google Flights sentence names: the code, else the city, else the country */
  function gfName(p) { return p.iata || (p.city ? p.city + (countryEn(p.country) ? ', ' + countryEn(p.country) : '') : countryEn(p.country) || p.country || ''); }
  function skyCode(p) { return (p.iata || p.country || '').toLowerCase(); }
  function f24PlaceLabel(p) { return p ? (p.iata ? p.iata + ' · ' + (p.cityHe || p.city) : (p.cityHe || p.city || countryHe(p.country) || '')) : ''; }

  /* origin sheet (FB_Origin): pinned TLV + ETM, the last origins used on this device, and the search results */
  function f24AirportSearch(q, recents) {
    const k = norm(q), pinned = PINNED.map(f24Airport).filter(Boolean);
    const recent = (Array.isArray(recents) ? recents : []).map(f24Airport).filter(a => a && PINNED.indexOf(a.iata) < 0).slice(0, RECENT_MAX);
    if (!k) return { pinned, recent, results: [] };
    const starts = [], has = [];
    for (const a of idx().byIata.values()) {
      const names = [a.iata, a.he, a.en, countryHe(a.cc), countryEn(a.cc)].concat(Array.isArray(a.alt) ? a.alt : []).map(norm).filter(Boolean);
      if (names.some(n => n.indexOf(k) === 0)) starts.push(a); else if (k.length >= 2 && names.some(n => n.indexOf(k) > 0)) has.push(a);
    }
    return { pinned, recent, results: starts.concat(has).slice(0, 30) };
  }
  /* newest first, no duplicates, at most 3 (the caller keeps the list in localStorage per trip) */
  function f24PushRecent(list, iata) {
    const c = String(iata || '').toUpperCase(); const l = (Array.isArray(list) ? list : []).filter(x => typeof x === 'string' && /^[A-Z]{3}$/.test(x) && x !== c);
    return (/^[A-Z]{3}$/.test(c) ? [c] : []).concat(l).slice(0, RECENT_MAX);
  }

  /* ---- C6: travelers = the trip's active members, at least 1, all sent as adults ---- */
  function f24Travelers() { let n = 1; try { n = env.members ? env.members() : 1; } catch (e) { n = 1; } return adultsOf(n); }

  /* ---- C3: "booked" = an existing reservation record of type flight / hotel for that day ---- */
  function linked(r, i) {
    if (Array.isArray(r.linkedDays) && r.linkedDays.indexOf(i) >= 0) return true;
    if (r.linkedDayStart == null || r.linkedDayStart === '') return false;
    const a = Number(r.linkedDayStart), b = r.linkedDayEnd == null || r.linkedDayEnd === '' ? a : Number(r.linkedDayEnd);
    return Number.isFinite(a) && i >= a && i <= (Number.isFinite(b) ? b : a);
  }
  function textDateIs(txt, iso) {   // "17/5", "17.05.2027", "17/05/27" inside free text
    const m = /(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?/.exec(String(txt || '')); if (!m || !iso) return false;
    if (+m[1] !== +iso.slice(8, 10) || +m[2] !== +iso.slice(5, 7)) return false;
    if (!m[3]) return true; const y = m[3].length === 2 ? '20' + m[3] : m[3]; return y === iso.slice(0, 4);
  }
  function f24FlightBooked(i) {
    const d = days()[i], iso = dayIso(d);
    return reservations().some(r => r && r.type === 'flight' && (linked(r, i) || textDateIs(r.datetime, iso)));
  }
  function f24LodgingBooked(i) {
    const d = days()[i], iso = dayIso(d); if (!d) return false;
    if (d.isBooked) return true;   // a hotel reservation writes straight into the day's booking fields (v1.8.0)
    return reservations().some(r => r && r.type === 'hotel' && (linked(r, i) || (iso && isIso(r.checkin) && isIso(r.checkout) && r.checkin <= iso && iso < r.checkout)));
  }

  /* ---- C1, C4, C5: the flight search of day i (null = no card) ---- */
  function flightIdx() { const f = F8(), a = days(), out = []; for (let i = 0; i < a.length; i++) if (f.f08IsFlight(a[i])) out.push(i); return out; }
  function f24FlightSearch(i, opt) {
    if (off()) return null;
    const f = F8(), a = days(), d = a[i], date = dayIso(d);
    if (!d || !date || !f.f08IsFlight(d) || f24FlightBooked(i)) return null;
    const fl = flightIdx(), first = fl[0] === i;
    let to = placeOfSide(f.f08FlightTo(d)), from = placeOfSide(f.f08FlightFrom(d));
    /* C4: the first flight of the trip leaves from TLV, unless the trip already spent days abroad before it */
    const sideFrom = f.f08FlightFrom(d);
    if (first && !(sideFrom.country && sideFrom.country !== HOME_CC && i > 0)) from = placeOfSide({});
    const o = opt && opt.origin ? f24Airport(opt.origin) : null; if (o) from = place(o);
    /* C5: round trip only on the first flight day, when a later flight day flies back to Israel */
    let returnDate = '';
    if (first && isHomePlace(from) && !isHomePlace(to)) {
      for (let k = fl.length - 1; k > 0; k--) { const b = a[fl[k]], bd = dayIso(b); if (bd && bd > date && isHomePlace(placeOfSide(f.f08FlightTo(b)))) { returnDate = bd; break; } }
    }
    const q = { from, to, date, returnDate, adults: f24Travelers() };
    return { i, kind: 'flight', from, to, date, returnDate, roundTrip: !!returnDate, adults: q.adults, links: { googleFlights: f24GoogleFlightsUrl(q), skyscanner: f24SkyscannerUrl(q) } };
  }

  /* ---- C2: the lodging search of day i: only on the first night of a run of non-flight, not-booked nights in one city ---- */
  function nightKey(i) {
    const f = F8(), d = days()[i]; if (!d || !dayIso(d) || f.f08IsFlight(d) || f24LodgingBooked(i)) return '';
    const cc = f.f08DayCountry(d) || '', city = norm(d.city); return cc || city ? cc + '|' + city : '';
  }
  function f24LodgingSearch(i) {
    if (off()) return null;
    const f = F8(), a = days(), k = nightKey(i); if (!k || (i > 0 && nightKey(i - 1) === k)) return null;
    let e = i; while (e + 1 < a.length && nightKey(e + 1) === k && dayIso(a[e + 1]) === addDays(dayIso(a[e]), 1)) e++;
    const d = a[i], cc = f.f08DayCountry(d) || '', city = String(d.city || '').trim(), ap = city ? f24AirportByName(city) : null;
    const q = { city: (ap && (!cc || ap.cc === cc) ? ap.en : city), country: cc, checkin: dayIso(d), checkout: addDays(dayIso(a[e]), 1), adults: f24Travelers() };
    return { i, kind: 'hotel', city: q.city, cityHe: (ap && (!cc || ap.cc === cc) ? ap.he : city) || countryHe(cc), country: cc, checkin: q.checkin, checkout: q.checkout, nights: e - i + 1, adults: q.adults,
      links: { booking: f24BookingUrl(q), googleHotels: f24GoogleHotelsUrl(q) } };
  }

  /* ---- C7: link builders (pure). R2: a request that cannot be built falls back to the site's own page with the city in the query ---- */
  const enc = encodeURIComponent;
  function f24GoogleFlightsUrl(q) {
    const base = 'https://www.google.com/travel/flights', to = q && q.to ? gfName(q.to) : '', from = q && q.from ? gfName(q.from) : '';
    if (!to || !from || !isIso(q.date)) return base + (to ? '?q=' + enc('Flights to ' + to) : '');
    const back = isIso(q.returnDate) && q.returnDate > q.date;
    return base + '?q=' + enc('Flights from ' + from + ' to ' + to + ' on ' + q.date + (back ? ' through ' + q.returnDate : ' one way') + ', ' + adultsOf(q.adults) + (adultsOf(q.adults) === 1 ? ' adult' : ' adults'));
  }
  function f24SkyscannerUrl(q) {
    const base = 'https://www.skyscanner.net/', from = q && q.from ? skyCode(q.from) : '', to = q && q.to ? skyCode(q.to) : '';
    if (!from || !to || !isIso(q.date)) return base + (q && q.to && (q.to.city || q.to.iata) ? '?q=' + enc(q.to.city || q.to.iata) : '');
    const back = isIso(q.returnDate) && q.returnDate > q.date;
    return base + 'transport/flights/' + from + '/' + to + '/' + yymmdd(q.date) + '/' + (back ? yymmdd(q.returnDate) + '/' : '') + '?adultsv2=' + adultsOf(q.adults);
  }
  function hotelPlace(q) { const c = String((q && q.city) || '').trim(), n = q && q.country ? countryEn(q.country) : ''; return c ? c + (n ? ', ' + n : '') : n; }
  function f24BookingUrl(q) {
    const base = 'https://www.booking.com/searchresults.html', ss = hotelPlace(q);
    if (!ss) return 'https://www.booking.com/';
    if (!isIso(q.checkin) || !isIso(q.checkout) || q.checkout <= q.checkin) return base + '?ss=' + enc(ss);
    return base + '?ss=' + enc(ss) + '&checkin=' + q.checkin + '&checkout=' + q.checkout + '&group_adults=' + adultsOf(q.adults) + '&no_rooms=1';
  }
  function f24GoogleHotelsUrl(q) {
    const base = 'https://www.google.com/travel/hotels', ss = hotelPlace(q);
    if (!ss) return base;
    if (!isIso(q.checkin) || !isIso(q.checkout) || q.checkout <= q.checkin) return base + '?q=' + enc('hotels in ' + ss);
    return base + '?q=' + enc('hotels in ' + ss + ' ' + q.checkin + ' to ' + q.checkout);
  }

  /* ---- C8 (pure part): the chat tool search_links {kind, from?, to, date, return_date?, nights?} → a search, or what to ask ---- */
  function toIso(v) {
    const s = String(v == null ? '' : v).trim(); if (isIso(s)) return s;
    const m = /^(\d{1,2})[./](\d{1,2})[./](\d{4})$/.exec(s); if (!m) return '';
    const k = m[3] + '-' + String(m[2]).padStart(2, '0') + '-' + String(m[1]).padStart(2, '0'); return isIso(k) ? k : '';
  }
  function placeByText(t) { const s = String(t == null ? '' : t).trim(); if (!s) return null; const a = f24AirportByName(s); return a ? place(a) : { iata: '', city: s, cityHe: s, country: '' }; }
  function f24ChatSearch(a) {
    if (off() || !a || (a.kind !== 'flight' && a.kind !== 'hotel')) return null;
    const date = toIso(a.date), to = String(a.to == null ? '' : a.to).trim(), missing = [];
    if (!to) missing.push('to'); if (!date) missing.push('date');
    if (missing.length) return { kind: a.kind, missing };
    const adults = f24Travelers();
    if (a.kind === 'flight') {
      const from = placeByText(a.from) || placeOfSide({}), dest = placeByText(to), back = toIso(a.return_date), returnDate = back && back > date ? back : '';
      const q = { from, to: dest, date, returnDate, adults };
      return { kind: 'flight', from, to: dest, date, returnDate, roundTrip: !!returnDate, adults, links: { googleFlights: f24GoogleFlightsUrl(q), skyscanner: f24SkyscannerUrl(q) } };
    }
    const ap = f24AirportByName(to), back = toIso(a.return_date), n = Math.floor(Number(a.nights));
    const nights = back && back > date ? diffDays(date, back) : (Number.isFinite(n) && n >= 1 ? Math.min(n, 60) : 1);
    const q = { city: ap ? ap.en : to, country: ap ? ap.cc : '', checkin: date, checkout: addDays(date, nights), adults };
    return { kind: 'hotel', city: q.city, cityHe: ap ? ap.he : to, country: q.country, checkin: q.checkin, checkout: q.checkout, nights, adults, links: { booking: f24BookingUrl(q), googleHotels: f24GoogleHotelsUrl(q) } };
  }

  const api = { version: VERSION, f24Configure, f24Airport, f24AirportByName, f24AirportSearch, f24PushRecent, f24PlaceLabel, f24Travelers, f24FlightBooked, f24LodgingBooked,
    f24FlightSearch, f24LodgingSearch, f24GoogleFlightsUrl, f24SkyscannerUrl, f24BookingUrl, f24GoogleHotelsUrl, f24ChatSearch };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptF24 = api; Object.keys(api).forEach(k => { if (k.indexOf('f24') === 0) root[k] = api[k]; }); }
})(typeof window !== 'undefined' ? window : globalThis);
