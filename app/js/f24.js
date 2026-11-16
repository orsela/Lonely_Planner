/* Lonely Planner · F24 – flight and hotel search from the trip, stage 1: smart links · version 3.0.0-alpha.16.3
   CHANGE 2026-11-16 F24-FIX-05: what changed from alpha.16.2 (Or's phone check, day 9): the destination leg of the flight card is now a button with a "שינוי" control, like the origin. It opens the same airport sheet
   (title "טסים אל…"); the choice applies only to this search (B.overTo, per day). f24FlightSearch takes opt.dest; the card shows "נבחר ידנית" under a manual destination. Origin behaviour is unchanged.
   CHANGE 2026-11-16 F24-FIX-04: what changed from alpha.16.1 (Or's choice C after the day-9 phone check): f24FlightSearch — on the LAST day of the trip, a flight whose
   destination is only a country (no code, no city) goes to Tel Aviv (TLV); and an origin that is only a country becomes the airport of the previous day's city
   (else this day's city) when that city is in airports.json and in the same country. Nothing else changes; flights on other days are untouched.
   CHANGE 2026-11-16 F24-FIX-01: what changed from alpha.14 (Or's phone check 16/11: day 9 flight with only a country on both sides opened Google Flights with empty
   fields): f24GoogleFlightsUrl — when a side has only a country (no airport code, no city) and the date is valid, the sentence names only the known side
   ("Flights to X on date" / "Flights from X on date") or, with no known side, the plain page; before it was "from <country> to <country>", which Google cannot
   parse. f24FlightCardHtml — a one-line hint under the links when a side is country-only. Skyscanner links and every other function unchanged.
   CHANGE 2026-11-15 F24-A3-01 (conversation 3): what changed from F24-A2-01: the card is placed under the route screen's weather card (#routeDayWeather) instead of
   under #dayReservations, so it shows in the map view too (Or's decision 2026-11-15). Nothing else in the file changed in this step.
   CHANGE 2026-11-14 F24-A2-01 (conversation 2): what changed from conversation 1 (same file, same version number alpha.14, which was never loaded
   by the app before): new "browser part" before the export — attach (client / trip id for the member count), mount (styles, the day cards
   FB_DayFlight / FB_DayHotel, the origin sheet FB_Origin, offline rule C9, airports.json / countries.json loading, the last 3 origins in
   localStorage per trip), paintDay, setReservations. The pure part (C1–C8 data and link builders) is unchanged.
   CHANGE 2026-11-14 F24-A1-01: new file (no previous version). Spec: claude/Plan_Travel_F24_spec.md, rulings C1–C8 at the data level:
   when a flight / lodging search applies (C1–C3), origin and destination (C4), round trip (C5), travelers (C6), the four link
   builders (C7, R2 fallback), the chat request → search (C8, pure part), airport lookup for the origin sheet (C4).
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
  /* F24-FIX-01: a place with neither an airport code nor a city (only a country, or nothing) */
  function isVague(p) { return !!p && !p.iata && !p.city; }
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
    /* F24-FIX-04: the last day of the trip, destination only a country → home (TLV); origin only a country → the airport of the previous day's city, else this day's city */
    if (i === a.length - 1 && isVague(to)) {
      to = placeOfSide({});
      if (isVague(from)) {
        const byCity = c => { const ap = c ? f24AirportByName(String(c).trim()) : null; return ap && (!from.country || ap.cc === from.country) && ap.cc !== HOME_CC ? place(ap) : null; };
        const p = byCity(a[i - 1] && a[i - 1].city) || byCity(d.city); if (p) from = p;
      }
    }
    /* C4: the first flight of the trip leaves from TLV, unless the trip already spent days abroad before it */
    const sideFrom = f.f08FlightFrom(d);
    if (first && !(sideFrom.country && sideFrom.country !== HOME_CC && i > 0)) from = placeOfSide({});
    const o = opt && opt.origin ? f24Airport(opt.origin) : null; if (o) from = place(o);
    const dd = opt && opt.dest ? f24Airport(opt.dest) : null; if (dd) to = place(dd);   /* F24-FIX-05: manual destination */
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
    /* F24-FIX-01: a side with only a country cannot be parsed by Google Flights; name only the side that has a code or a city */
    if (isIso(q && q.date) && (isVague(q.from) || isVague(q.to))) {
      if (q.to && !isVague(q.to)) return base + '?q=' + enc('Flights to ' + to + ' on ' + q.date);
      if (q.from && !isVague(q.from)) return base + '?q=' + enc('Flights from ' + from + ' on ' + q.date);
      return base;
    }
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


  /* =====================================================================================================================
     Browser part (conversation 2) — screens. Nothing below runs unless app/index.html calls mount() (hook F24-MOUNT-01).
     ===================================================================================================================== */
  const CSS = `
.p24-find{border:1.5px dashed #9cc4b2;background:#f3faf6;border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:10px;margin-top:10px;box-sizing:border-box;color:#17211b}
.p24-find b.t{font-size:14px;color:#0b5841}
.p24-leg{display:flex;align-items:center;gap:8px;min-height:48px;border:1px solid #d6d9d0;border-radius:12px;background:#fff;padding:0 12px;font-size:14px;color:#17211b;width:100%;text-align:right;font-family:inherit;box-sizing:border-box}
.p24-leg small{display:block;font-size:11px;color:#5f6861;font-weight:400}
.p24-leg.st{background:#fbfbf8}
.p24-chg{margin-inline-start:auto;font-size:12.5px;font-weight:800;color:#0f6b4f}
button.p24-leg{cursor:pointer}
.p24-meta{display:flex;gap:6px;flex-wrap:wrap}
.p24-meta span{font-size:12px;font-weight:700;color:#3a443d;background:#fff;border:1px solid #e4e6df;border-radius:999px;padding:4px 10px}
.p24-go{display:flex;align-items:center;justify-content:space-between;min-height:48px;border-radius:12px;padding:0 14px;font-size:14px;font-weight:800;text-decoration:none;box-sizing:border-box}
.p24-go.p{background:#0f6b4f;color:#fff}.p24-go.s{background:#fff;color:#0f6b4f;border:1.5px solid #0f6b4f}
.p24-go.dis{background:#c9ccc3;color:#fff;border:0;cursor:default}
.p24-hint{margin:0;font-size:11.5px;color:#5f6861;line-height:1.5}
.p24-off{margin:0;font-size:12.5px;color:#8a5a00;background:#fff6e0;border-radius:10px;padding:8px 10px}
#ptF24Layer{position:fixed;inset:0;z-index:1150;display:flex;align-items:flex-end;justify-content:center}#ptF24Layer[hidden]{display:none}
#ptF24Layer .p24-scrim{position:absolute;inset:0;background:#0f172a66}
#ptF24Layer .p24-sheet{position:relative;width:100%;max-width:560px;max-height:min(90vh,760px);overflow-y:auto;overflow-x:hidden;background:#fff;border-radius:20px 20px 0 0;box-shadow:0 -8px 28px #00000020;padding:10px 16px calc(20px + env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:10px;color:#17211b;box-sizing:border-box}
.p24-grab{width:38px;height:4px;border-radius:99px;background:#e4e6df;margin:0 auto}
.p24-hd{display:flex;align-items:center;justify-content:space-between}.p24-hd h2{margin:0;font-size:17px}
.p24-x{width:44px;height:44px;border-radius:12px;border:1px solid #e4e6df;background:#fff;font-size:18px;cursor:pointer;font-family:inherit}
.p24-lbl{font-size:12px;font-weight:800;color:#5f6861;margin:4px 2px 0}
.p24-in{width:100%;box-sizing:border-box;min-height:46px;padding:0 12px;border:1px solid #d6d9d0;border-radius:12px;background:#fff;color:#17211b;font-size:16px;font-family:inherit}
.p24-ap{display:flex;align-items:center;gap:10px;min-height:52px;padding:0 12px;border:1px solid #e4e6df;border-radius:12px;background:#fff;width:100%;text-align:right;color:#17211b;font-size:14.5px;font-family:inherit;cursor:pointer;box-sizing:border-box}
.p24-ap.on{border:1.5px solid #0f6b4f;background:#edf8f3}
.p24-code{font-size:12px;font-weight:800;color:#3a443d;background:#f1f2ec;border-radius:8px;padding:3px 7px;direction:ltr}
.p24-ap small{display:block;font-size:11px;color:#5f6861}
.p24-list{display:flex;flex-direction:column;gap:6px}
.p24-save{display:flex;align-items:center;justify-content:center;width:100%;min-height:46px;border:0;border-radius:14px;background:#0f6b4f;color:#fff;font-size:14px;font-weight:800;font-family:inherit;cursor:pointer}
`;
  const escH = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const dm = iso => iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) : '';
  const OFFLINE_LINE = 'אין חיבור – אפשר לחפש כשהרשת תחזור.';
  function onlineNow() { try { return navigator.onLine !== false; } catch (e) { return true; } }
  function travelersLabel(n, hotel) { return (hotel ? (n === 1 ? 'אורח אחד' : n + ' אורחים') : (n === 1 ? 'נוסע אחד' : n + ' נוסעים')) + ' · מחברי הטיול'; }

  /* pure: the card HTML of a flight / lodging search (the objects of f24FlightSearch / f24LodgingSearch). origin: {manual:boolean, dayNo:number} */
  function f24FlightCardHtml(c, o) {
    o = o || {}; const on = o.online !== false, d = days()[c.i] || {};
    const fromNote = o.manual ? 'נבחר ידנית' : (c.from.iata === HOME_IATA && c.from.country === HOME_CC ? 'ברירת מחדל' : 'מהמסלול · יום ' + (o.fromDay || ''));
    const link = (u, cls, label) => on ? '<a class="p24-go ' + cls + '" href="' + escH(u) + '" target="_blank" rel="noopener">' + escH(label) + ' <span aria-hidden="true">↗</span></a>'
      : '<span class="p24-go ' + cls + ' dis" role="link" aria-disabled="true">' + escH(label) + ' <span aria-hidden="true">↗</span></span>';
    return '<b class="t">עוד אין טיסה ליום הזה</b>' +
      '<button type="button" class="p24-leg" id="ptF24Chg" aria-label="שינוי נקודת מוצא"><span>מ: <b>' + escH(f24PlaceLabel(c.from)) + '</b><small>' + escH(fromNote) + '</small></span><span class="p24-chg">שינוי</span></button>' +
      '<button type="button" class="p24-leg" id="ptF24ChgTo" aria-label="שינוי יעד"><span>אל: <b>' + escH(f24PlaceLabel(c.to)) + '</b><small>' + (o.manualTo ? 'נבחר ידנית' : 'מהמסלול · יום ' + escH(d.day || c.i + 1)) + '</small></span><span class="p24-chg">שינוי</span></button>' +
      '<div class="p24-meta"><span>' + dm(c.date) + (c.roundTrip ? ' · הלוך' : ' · כיוון אחד') + '</span>' + (c.roundTrip ? '<span>חזור ' + dm(c.returnDate) + '</span>' : '') + '<span>' + escH(travelersLabel(c.adults, false)) + '</span></div>' +
      link(c.links.googleFlights, 'p', 'חיפוש ב-Google Flights') + link(c.links.skyscanner, 's', 'חיפוש ב-Skyscanner') +
      (on ? '' : '<p class="p24-off" role="status">' + OFFLINE_LINE + '</p>') +
      (isVague(c.from) || isVague(c.to) ? '<p class="p24-hint">בהזמנה חסר שדה תעופה או עיר, אז החיפוש כללי יותר. אפשר לדייק ב"שינוי" או בפרטי הטיסה.</p>' : '') +
      '<p class="p24-hint">הפרטים כבר ממולאים. באתר אפשר למיין לפי הכי זול, הכי מהיר או הכי משתלם. כשמזמינים, מעלים את הכרטיס לכספת והכרטיס הזה מתחלף בפרטי הטיסה.</p>';
  }
  function f24HotelCardHtml(c, o) {
    o = o || {}; const on = o.online !== false;
    const link = (u, cls, label) => on ? '<a class="p24-go ' + cls + '" href="' + escH(u) + '" target="_blank" rel="noopener">' + escH(label) + ' <span aria-hidden="true">↗</span></a>'
      : '<span class="p24-go ' + cls + ' dis" role="link" aria-disabled="true">' + escH(label) + ' <span aria-hidden="true">↗</span></span>';
    return '<b class="t">עוד אין לינה ל-' + dm(c.checkin) + ' עד ' + dm(c.checkout) + '</b>' +
      '<div class="p24-meta"><span>' + escH(c.cityHe || c.city) + '</span><span>' + (c.nights === 1 ? 'לילה אחד' : c.nights + ' לילות') + '</span><span>' + escH(travelersLabel(c.adults, true)) + '</span></div>' +
      link(c.links.booking, 'p', 'חיפוש ב-Booking') + link(c.links.googleHotels, 's', 'חיפוש ב-Google Hotels') +
      (on ? '' : '<p class="p24-off" role="status">' + OFFLINE_LINE + '</p>') +
      '<p class="p24-hint">העיר והלילות נלקחים מטווח הימים של המסלול. באתר אפשר למיין לפי מחיר או דירוג.</p>';
  }
  /* pure: the origin sheet body. s = {sel, q}, recents = [iata…] */
  function f24OriginSheetHtml(s, recents) {
    const r = f24AirportSearch(s.q, recents), row = (a, sub) => '<button type="button" class="p24-ap' + (a.iata === s.sel ? ' on' : '') + '" data-p24-ap="' + a.iata + '" aria-pressed="' + (a.iata === s.sel ? 'true' : 'false') + '"><span class="p24-code">' + a.iata + '</span><span style="flex-grow:1"><b>' + escH(a.he) + '</b><small>' + escH(sub) + '</small></span>' + (a.iata === s.sel ? '<span aria-hidden="true">✓</span>' : '') + '</button>';
    const sub = a => a.iata === 'TLV' ? 'ברירת מחדל' : a.iata === 'ETM' ? 'שדה נוסף בישראל' : (r.recent.indexOf(a) >= 0 ? 'חיפשתם מכאן קודם' : (countryHe(a.cc) || a.en));
    let h = '<div class="p24-grab"></div><div class="p24-hd"><h2>' + (s.side === 'to' ? 'טסים אל…' : 'טסים מ…') + '</h2><button type="button" class="p24-x" data-p24-close aria-label="סגירה">×</button></div>' +
      '<label class="p24-lbl" for="ptF24Q" style="margin-top:0">עיר או שדה תעופה</label><input id="ptF24Q" class="p24-in" placeholder="למשל: אתונה, LCA" value="' + escH(s.q) + '" autocomplete="off">';
    if (!s.q.trim()) h += '<div class="p24-lbl">מוצעים</div><div class="p24-list">' + r.pinned.concat(r.recent).map(a => row(a, sub(a))).join('') + '</div>';
    else h += '<div class="p24-list">' + (r.results.length ? r.results.map(a => row(a, sub(a))).join('') : '<p class="p24-hint">לא נמצא שדה תעופה. אפשר לנסות שם עיר באנגלית או קוד של שלוש אותיות.</p>') + '</div>';
    if (!r.pinned.length) h += '<p class="p24-hint">אין חיבור לרשימת שדות התעופה – נסו שוב כשיש רשת.</p>';
    h += '<p class="p24-hint">השינוי חל רק על החיפוש הזה.' + (s.side === 'to' ? '' : ' ביום טיסה באמצע הטיול, המוצא הוא העיר של היום הקודם.') + '</p><button type="button" class="p24-save" id="ptF24Save">שמירה</button>';
    return h;
  }

  const B = { dep: null, res: [], members: 0, over: {}, overTo: {}, sheet: null, mounted: false, airports: null, countries: null, busy: false };
  const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { } };
  function tid() { try { return B.dep && B.dep.tripId ? (B.dep.tripId() || '') : ''; } catch (e) { return ''; } }
  function recents() { try { const a = JSON.parse(lsGet('pt-f24-recent-' + tid()) || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
  function saveRecent(iata) { lsSet('pt-f24-recent-' + tid(), JSON.stringify(f24PushRecent(recents(), iata))); }

  /* attach: the client, trip id and timeout helper from the app (cloud only, like F08). Without it the member count comes from the device cache, minimum 1. */
  function attach(dep) { B.dep = dep || null; B.members = Number(lsGet('pt-f24-members-' + tid())) || 0; }
  async function refreshMembers() {
    if (B.busy || !B.dep || !onlineNow() || Date.now() - (B.memAt || 0) < 60000) return; const t = tid(); let c = null; try { c = B.dep.client && B.dep.client(); } catch (e) { }
    if (!t || !c) return; B.busy = true; B.memAt = Date.now();
    try {
      const r = await B.dep.withTimeout(c.from('trip_members').select('id').eq('trip_id', t).eq('status', 'active'), B.dep.timeoutMs || 8000);
      if (r && !r.error && Array.isArray(r.data) && r.data.length !== B.members) { B.members = r.data.length; lsSet('pt-f24-members-' + t, String(B.members)); repaint(); }
    } catch (e) { } finally { B.busy = false; }
  }
  function setReservations(a) { B.res = Array.isArray(a) ? a : []; }

  function closeSheet() { const l = document.getElementById('ptF24Layer'); if (l) { l.hidden = true; l.innerHTML = ''; } B.sheet = null; }
  function paintSheet(keepFocus) {
    const s = B.sheet; if (!s) return;
    let l = document.getElementById('ptF24Layer');
    if (!l) { l = document.createElement('div'); l.id = 'ptF24Layer'; l.hidden = true; document.body.appendChild(l); document.addEventListener('keydown', e => { if (e.key === 'Escape' && !l.hidden) closeSheet(); }); }
    l.innerHTML = '<div class="p24-scrim" data-p24-close></div><div class="p24-sheet" role="dialog" aria-modal="true" aria-label="נקודת מוצא">' + f24OriginSheetHtml(s, recents()) + '</div>';
    l.hidden = false;
    l.querySelectorAll('[data-p24-close]').forEach(x => { x.onclick = closeSheet; });
    l.querySelectorAll('[data-p24-ap]').forEach(b => { b.onclick = () => { s.sel = b.dataset.p24Ap; paintSheet(); }; });
    const q = document.getElementById('ptF24Q'); if (q) { q.oninput = () => { s.q = q.value; paintSheet(true); }; if (keepFocus) { q.focus(); try { q.setSelectionRange(q.value.length, q.value.length); } catch (e) { } } }
    document.getElementById('ptF24Save').onclick = () => { if (s.sel) { (s.side === 'to' ? B.overTo : B.over)[s.i] = s.sel; saveRecent(s.sel); } closeSheet(); repaint(); };
  }
  function openSheet(i, cur, side) { B.sheet = { i, sel: cur, q: '', side: side || 'from' }; paintSheet(); }

  /* paintDay(reservations?) — called after the day's reservations are drawn. A day with no search card gets no node at all (D3 / C3: byte-identical). */
  function paintDay(res) {
    if (res) setReservations(res);
    const old = document.getElementById('ptF24Card'); if (old) old.remove();
    if (!B.mounted || off()) return;
    const i = B.dep && B.dep.dayIndex ? B.dep.dayIndex() : 0, anchor = document.getElementById('routeDayWeather') || document.getElementById('dayReservations'); if (!anchor) return;   /* F24-A3-01: route-v2 hides the old day card in the map view, so the card sits under the day strip's weather card (both views) */
    let c = null, html = '', on = onlineNow();
    try {
      c = f24FlightSearch(i, (B.over[i] || B.overTo[i]) ? { origin: B.over[i], dest: B.overTo[i] } : undefined);
      if (c) { const prev = days()[i - 1]; html = f24FlightCardHtml(c, { online: on, manual: !!B.over[i], manualTo: !!B.overTo[i], fromDay: prev ? (prev.day || i) : '' }); }
      else { c = f24LodgingSearch(i); if (c) html = f24HotelCardHtml(c, { online: on }); }
    } catch (e) { c = null; }
    if (!c) return;
    const el = document.createElement('div'); el.id = 'ptF24Card'; el.className = 'p24-find'; el.setAttribute('data-kind', c.kind); el.innerHTML = html;
    anchor.insertAdjacentElement('afterend', el);
    const chg = document.getElementById('ptF24Chg'); if (chg) chg.onclick = () => openSheet(i, c.from.iata || HOME_IATA);
    const chgTo = document.getElementById('ptF24ChgTo'); if (chgTo) chgTo.onclick = () => openSheet(i, c.to.iata || HOME_IATA, 'to');
    refreshMembers();
  }
  function repaint() { try { paintDay(); } catch (e) { } }
  function loadJson(url) { return fetch(url, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null); }

  /* mount({dayIndex, days, tripId?}) — styles, data files, online / offline repaint. Returns false when the feature is off or there is no document. */
  function mount(dep) {
    if (typeof document === 'undefined' || !F8() || feature() === 'off') return false;
    B.dep = Object.assign({}, B.dep || {}, dep || {});
    if (B.mounted) return true;
    const st = document.createElement('style'); st.id = 'ptF24Css'; st.textContent = CSS; document.head.appendChild(st);
    f24Configure({
      days: B.dep.days || undefined, reservations: () => B.res, members: () => B.members || 1,
      airports: () => B.airports || [], countries: () => B.countries || {}
    });
    B.mounted = true;
    Promise.all([loadJson('airports.json'), loadJson('countries.json')]).then(r => {
      B.airports = Array.isArray(r[0]) ? r[0] : null;
      const m = {}; (Array.isArray(r[1]) ? r[1] : []).forEach(x => { if (x && x.code) m[x.code] = x; }); B.countries = Object.keys(m).length ? m : null;
      f24Configure({}); repaint();
    });
    window.addEventListener('online', repaint); window.addEventListener('offline', repaint);
    return true;
  }

  const api = { version: VERSION, f24Configure, f24Airport, f24AirportByName, f24AirportSearch, f24PushRecent, f24PlaceLabel, f24Travelers, f24FlightBooked, f24LodgingBooked,
    f24FlightSearch, f24LodgingSearch, f24GoogleFlightsUrl, f24SkyscannerUrl, f24BookingUrl, f24GoogleHotelsUrl, f24ChatSearch,
    f24FlightCardHtml, f24HotelCardHtml, f24OriginSheetHtml, attach, mount, paintDay, setReservations };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptF24 = api; Object.keys(api).forEach(k => { if (k.indexOf('f24') === 0) root[k] = api[k]; }); }
})(typeof window !== 'undefined' ? window : globalThis);
