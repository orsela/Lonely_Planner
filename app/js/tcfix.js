/* Lonely Planner · TC-BUG-01 – a cloud trip that is not Vietnam never falls back to the Vietnam seed when the cloud is unreachable · version 3.0.0-alpha.18.4
   CHANGE 2026-11-24 TCFIX-01: new file (no previous version). Why: loadState() read the trip through SS.get(); with no network SS.get swallowed the error and returned the (empty) local copy, so
   loadState() ended in makeSeed() = the Vietnam SEED_DATA, and every 15 s (pullRemoteUpdates) or on return to the app (visibilitychange) the open Romania trip was replaced on screen by
   "האנוי", 16/09–06/10 and 20 nights (Or's phone test of TRIP-COUNTRY, 24/11). A later save would also have queued the seed for the trip's cloud row. SS.get never kept a copy of what it read from the cloud,
   so a trip that was imported (not edited on the device) had no local copy at all.
   Here (pure helpers, no DOM): ok(raw) = the cloud answered for the trip key (keeps a "last good" local copy, clears the offline state); fail() = the cloud did not answer;
   resolve(current) = what loadState() should do when it has no valid stored trip: cloud down + days already loaded → keep them; cloud down + no days → the last good copy, else no days (and saves are
   blocked, so nothing is written to the cloud); cloud answered + no row → no days (never the seed). blockSave() = true while there is nothing real to save.
   Active only when TCFIX_FEATURE === 'on' AND the storage is cloud AND the open trip is not the Vietnam trip; in every other case every function is a no-op and the old path runs (alpha.18.3). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.18.4';
  const VN_TRIP = 'f0200000-0000-4000-8000-000000000001';   /* the Vietnam trip id (same as app/js/tripcountry.js) */
  const LG = 'planner:trip:lg';                              /* last good copy of the trip days; the app's Storage wrapper namespaces it per trip (pt:<trip>:) */
  const env = {}, st = { down: false, noData: false };
  function tfConfigure(o) { Object.assign(env, o || {}); }
  function feature() { return env.feature ? env.feature() : (typeof TCFIX_FEATURE !== 'undefined' ? TCFIX_FEATURE : 'off'); }
  function backend() { return env.backend ? env.backend() : (typeof STORAGE_BACKEND !== 'undefined' ? STORAGE_BACKEND : ''); }
  function tripId() { try { return String(env.tripId ? env.tripId() : (typeof state !== 'undefined' && state && state.tripId ? state.tripId : '')); } catch (e) { return ''; } }   /* default = the app's own open-trip state (set before the first loadState) */
  function store() { try { return env.store ? env.store() : root.localStorage; } catch (e) { return null; } }
  function tfActive() { try { return feature() === 'on' && backend() === 'cloud' && !!tripId() && tripId() !== VN_TRIP; } catch (e) { return false; } }
  function tfReset() { st.down = false; st.noData = false; }

  /* the cloud answered for the trip key; raw = the stored value or null (no row) */
  function tfOk(raw) {
    if (!tfActive()) return;
    st.down = false; st.noData = false;
    if (typeof raw === 'string' && raw) { try { const s = store(); if (s) s.setItem(LG, raw); } catch (e) { } }
  }
  function tfFail() { if (tfActive()) st.down = true; }
  function tfDown() { return tfActive() && st.down; }
  function lastGood() {
    try { const s = store(), raw = s && s.getItem(LG), a = raw ? JSON.parse(raw) : null; return Array.isArray(a) && a.length ? a : null; } catch (e) { return null; }
  }
  /* loadState() has no valid stored trip. Returns {keep:true} (leave tripData as it is) or {days:[…]} (use these days; never the seed). */
  function tfResolve(current) {
    if (st.down) {
      if (Array.isArray(current) && current.length) { st.noData = false; return { keep: true }; }
      const lg = lastGood();
      if (lg) { st.noData = false; return { days: lg }; }
      st.noData = true; return { days: [] };
    }
    st.noData = false; return { days: [] };
  }
  /* saveTrip(): while there are no real days (cloud down, nothing local) nothing may be queued for the cloud */
  function tfBlockSave() { return tfActive() && st.noData; }

  const api = { version: VERSION, tfConfigure, tfActive, tfReset, tfOk, tfFail, tfDown, tfResolve, tfBlockSave, lastGood, LG };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptTCFix = { version: VERSION, configure: tfConfigure, active: tfActive, ok: tfOk, fail: tfFail, down: tfDown, resolve: tfResolve, blockSave: tfBlockSave }; }
})(typeof window !== 'undefined' ? window : globalThis);
