/* Lonely Planner · TRIP-COUNTRY-A – country-aware search text and booking link (no Vietnam hard-coding for other trips) · version 3.0.0-alpha.18.5
   CHANGE 2026-11-24 TC-OFF-01: what changed from alpha.18.3 (TC-BUG-01, Or's phone check 4): pick(v, current) decides what loadState does for a cloud trip that is not Vietnam when TRIPOFFLINE_FEATURE is 'on': days read -> use them and save a copy on the device (save:true); nothing read but days already on screen -> keep them; nothing at all -> an empty trip (empty:true), never the Vietnam SEED_DATA. Null = inactive: loadState runs exactly as in alpha.18.3 (Vietnam, local storage, flag off).
   CHANGE 2026-11-24 TC-OFF-02: what changed from alpha.18.4: schematicBase(W, H) = the route-screen schematic map background (grid, no Vietnam outline / rivers / "מפרץ טונקין") for the same trips and flag; null = the Vietnam shapes as before.
   CHANGE 2026-11-24 TC-B-01: what changed from alpha.18.2 (alpha.18.1 here) (Or's choice A of the mockup, with the offline-maps hint): fallbackMap(el) swaps the Vietnam outline of the home-screen fallback map for a neutral grid and adds a chip "מפה פשוטה · אין חיבור למפה" with the line "לניווט בלי רשת: Google Maps ← מפות אופליין ← הורדת האזור" (shown only after the real map image failed: mapFailed(true)); region(d) gives the Static Maps `region=` parameter of the trip's country instead of a fixed VN. Same activation rule as before; inactive = the Vietnam map exactly as it was (and a swap made earlier is undone).
   CHANGE 2026-11-24 TC-A-01: new file (no previous version). Why: a trip that is not Vietnam (the Romania pilot) got ", Vietnam" appended to the place search
   (waypoint lookup), to the hotel navigation query and to the airport-address fallback, and its Booking.com link was fixed to "Vietnam", 2 adults, 3 children
   (17/15/11) and 2 rooms. Here: suffix(d) gives ", <English country name of the day>" (Intl.DisplayNames, no file needed); booking(stay, day) gives the Booking.com
   parameters from the day's country and the trip's traveller count (F24 C6: active members, all adults, rooms = ceil(n/2), no children / ages).
   Active only when TRIPCOUNTRY_FEATURE === 'on' AND the storage is cloud AND the open trip is not the Vietnam trip; in every other case suffix() is exactly
   ", Vietnam" and booking() is null (the caller keeps its own old parameters), so the Vietnam trip is byte-identical to alpha.18. Pure helpers, no DOM. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.18.5';
  const VN_TRIP = 'f0200000-0000-4000-8000-000000000001';   /* the Vietnam trip id (same as app/js/f13.js FORCED_HE_TRIPS) */
  const env = {};   /* feature() → 'on'|'off', backend() → 'cloud'|…, tripId() → string, travelers() → number */
  function tcConfigure(o) { Object.assign(env, o || {}); }
  function feature() { return env.feature ? env.feature() : (typeof TRIPCOUNTRY_FEATURE !== 'undefined' ? TRIPCOUNTRY_FEATURE : 'off'); }
  function backend() { return env.backend ? env.backend() : (typeof STORAGE_BACKEND !== 'undefined' ? STORAGE_BACKEND : ''); }
  function tripId() { try { return String(env.tripId ? env.tripId() : ''); } catch (e) { return ''; } }
  /* true = this trip gets country-aware behaviour; false = exactly the alpha.18 (Vietnam) behaviour */
  function offFeature() { return env.offlineFeature ? env.offlineFeature() : 'off'; }
  /* TC-BUG-01: the offline-copy rule applies only here */
  /* the id comes from configure() like TC-A, and from window.__PT when that gave nothing (the same value; loadState runs early) */
  function offTripId() { let t = tripId(); if (!t) { try { t = String((root.__PT && root.__PT.tripId) || ''); } catch (e) { t = ''; } } return t; }
  function tcOfflineActive() { try { const t = offTripId(); return offFeature() === 'on' && backend() === 'cloud' && !!t && t !== VN_TRIP; } catch (e) { return false; } }
  /* v = the days read (array or null), current = the days on screen. null = inactive (caller keeps the old path) */
  function tcPick(v, current) {
    if (!tcOfflineActive()) return null;
    if (Array.isArray(v) && v.length) return { save: true, keep: false, empty: false };
    if (Array.isArray(v)) return { save: false, keep: false, empty: false };   /* a stored 0-day trip: the existing F04 path handles it */
    if (Array.isArray(current) && current.length) return { save: false, keep: true, empty: false };
    return { save: false, keep: false, empty: true };
  }
  /* TC-OFF-MAP: SVG background of the route-screen schematic map (W x H) without Vietnam shapes; null = inactive (the caller draws the Vietnam shapes as before) */
  function tcSchematicBase(W, H) {
    if (!tcOfflineActive()) return null;
    const xs = [], ys = []; for (let k = 1; k < 10; k++) { xs.push(Math.round(W * k / 10)); ys.push(Math.round(H * k / 10)); }
    return '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#eef1de"/>' + xs.map(x => '<path d="M' + x + ' 0V' + H + '" stroke="#dfe5c6" stroke-width=".8"/>').join('') + ys.map(y => '<path d="M0 ' + y + 'H' + W + '" stroke="#dfe5c6" stroke-width=".8"/>').join('');
  }
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

  /* ---- TC-B-01: home-screen fallback map ---- */
  const NEUTRAL = '<rect width="300" height="230" fill="#eef1de"/>' +
    [30, 60, 90, 120, 150, 180, 210, 240, 270].map(x => '<path d="M' + x + ' 0 V230" stroke="#dfe5c6" stroke-width=".6"/>').join('') +
    [23, 46, 69, 92, 115, 138, 161, 184, 207].map(y => '<path d="M0 ' + y + ' H300" stroke="#dfe5c6" stroke-width=".6"/>').join('');
  const CHIP_STYLE = 'position:absolute;top:10px;inset-inline-start:10px;max-width:72%;display:none;flex-direction:column;gap:2px;background:#ffffffe6;border-radius:12px;padding:6px 10px;box-sizing:border-box;font-size:11px;line-height:1.35;color:#3d4a3f;pointer-events:none';
  const CHIP_HTML = '<b style="font-weight:800">מפה פשוטה · אין חיבור למפה</b><span>לניווט בלי רשת: Google Maps ← מפות אופליין ← הורדת האזור</span>';
  /* el = #hv2MapSchematic. Returns true when the neutral map is in place. Idempotent; called on every redraw. */
  function tcFallbackMap(el) {
    try {
      if (!el) return false;
      const bg = el.querySelector('.hv2-map-bg'); if (!bg) return false;
      const on = tcActive(), done = el.getAttribute('data-tc') === '1';
      if (on && !done) {
        el.__tcOrig = bg.innerHTML; bg.innerHTML = NEUTRAL; el.setAttribute('data-tc', '1');
        const chip = document.createElement('div'); chip.id = 'hv2TcChip'; chip.setAttribute('style', CHIP_STYLE); chip.innerHTML = CHIP_HTML; el.appendChild(chip);
      } else if (!on && done) {
        if (typeof el.__tcOrig === 'string') bg.innerHTML = el.__tcOrig;
        el.removeAttribute('data-tc'); const c = document.getElementById('hv2TcChip'); if (c && c.parentNode) c.parentNode.removeChild(c);
      }
      return on;
    } catch (e) { return false; }
  }
  /* the chip is only for a real failure: the fallback is also visible while the image is still loading */
  function tcMapFailed(failed) { try { const c = document.getElementById('hv2TcChip'); if (c) c.style.display = failed ? 'flex' : 'none'; } catch (e) { } }
  /* Static Maps `region=` parameter: the trip's country when active, else the old fixed VN */
  function tcRegion(d) { if (!tcActive()) return 'region=VN'; const c = dayCountry(d); return c ? 'region=' + c : ''; }

  const api = { version: VERSION, tcConfigure, tcActive, tcCountryName, tcSuffix, tcBooking, tcFallbackMap, tcMapFailed, tcRegion, tcPick, tcOfflineActive, tcSchematicBase };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptTC = { version: VERSION, configure: tcConfigure, active: tcActive, countryName: tcCountryName, suffix: tcSuffix, booking: tcBooking, fallbackMap: tcFallbackMap, mapFailed: tcMapFailed, region: tcRegion, pick: tcPick, offlineActive: tcOfflineActive, schematicBase: tcSchematicBase }; }
})(typeof window !== 'undefined' ? window : globalThis);
