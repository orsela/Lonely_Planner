/* Lonely Planner · TRIP-COUNTRY-A – country-aware search text and booking link (no Vietnam hard-coding for other trips) · version 3.0.0-alpha.18.1
   CHANGE 2026-11-24 TC-A-01: new file (no previous version). Why: a trip that is not Vietnam (the Romania pilot) got ", Vietnam" appended to the place search
   (waypoint lookup), to the hotel navigation query and to the airport-address fallback, and its Booking.com link was fixed to "Vietnam", 2 adults, 3 children
   (17/15/11) and 2 rooms. Here: suffix(d) gives ", <English country name of the day>" (Intl.DisplayNames, no file needed); booking(stay, day) gives the Booking.com
   parameters from the day's country and the trip's traveller count (F24 C6: active members, all adults, rooms = ceil(n/2), no children / ages).
   Active only when TRIPCOUNTRY_FEATURE === 'on' AND the storage is cloud AND the open trip is not the Vietnam trip; in every other case suffix() is exactly
   ", Vietnam" and booking() is null (the caller keeps its own old parameters), so the Vietnam trip is byte-identical to alpha.18. Pure helpers, no DOM. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.18.1';
  const VN_TRIP = 'f0200000-0000-4000-8000-000000000001';   /* the Vietnam trip id (same as app/js/f13.js FORCED_HE_TRIPS) */
  const env = {};   /* feature() → 'on'|'off', backend() → 'cloud'|…, tripId() → string, travelers() → number */
  function tcConfigure(o) { Object.assign(env, o || {}); }
  function feature() { return env.feature ? env.feature() : (typeof TRIPCOUNTRY_FEATURE !== 'undefined' ? TRIPCOUNTRY_FEATURE : 'off'); }
  function backend() { return env.backend ? env.backend() : (typeof STORAGE_BACKEND !== 'undefined' ? STORAGE_BACKEND : ''); }
  function tripId() { try { return String(env.tripId ? env.tripId() : ''); } catch (e) { return ''; } }
  /* true = this trip gets country-aware behaviour; false = exactly the alpha.18 (Vietnam) behaviour */
  function tcActive() { try { return feature() === 'on' && backend() === 'cloud' && !!tripId() && tripId() !== VN_TRIP; } catch (e) { return false; } }

  function dayCountry(d) {
    try { const f = root.__ptF08; const c = f && f.f08DayCountry ? f.f08DayCountry(d) : ''; return /^[A-Z]{2}$/.test(c || '') ? c : ''; } catch (e) { return ''; }
  }
  function nameOf(code) {
    if (!code) return '';
    try { const n = new Intl.DisplayNames(['en'], { type: 'region' }).of(code); return n && n !== code ? n : ''; } catch (e) { return ''; }
  }
  /* '' = unknown (callers leave the country out rather than guess) */
  function tcCountryName(d) { return tcActive() ? nameOf(dayCountry(d)) : 'Vietnam'; }
  /* ", Romania" / ", Vietnam" (inactive) / "" (unknown country) */
  function tcSuffix(d) { const n = tcCountryName(d); return n ? ', ' + n : ''; }

  function travelers() {
    let n = 1;
    try { n = env.travelers ? env.travelers() : (root.__ptF24 && root.__ptF24.f24Travelers ? root.__ptF24.f24Travelers() : 1); } catch (e) { n = 1; }
    n = Math.floor(Number(n)); return Number.isFinite(n) && n >= 1 ? n : 1;
  }
  /* Booking.com searchresults parameters of a stay block {hotel, region, checkin, checkout}; null = inactive (keep the old Vietnam parameters) */
  function tcBooking(stay, day) {
    if (!tcActive() || !stay) return null;
    const n = travelers();
    return { ss: [stay.hotel, stay.region].filter(Boolean).join(', ') + tcSuffix(day), checkin: stay.checkin, checkout: stay.checkout,
      group_adults: String(n), group_children: '0', no_rooms: String(Math.max(1, Math.ceil(n / 2))) };
  }

  const api = { version: VERSION, tcConfigure, tcActive, tcCountryName, tcSuffix, tcBooking };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptTC = { version: VERSION, configure: tcConfigure, active: tcActive, countryName: tcCountryName, suffix: tcSuffix, booking: tcBooking }; }
})(typeof window !== 'undefined' ? window : globalThis);
