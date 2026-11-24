/* CHANGE 2026-09-30 APP-OFFLINE-01 (v2.12.0, PRD TASK-104): the app now opens with no network.
   What changed from the PWA-01 version (network-only, icons cached): page navigations are now
   NETWORK-FIRST with a cache fallback — online, the family still always gets the live version from
   GitHub Pages (the concern that made PWA-01 network-only); every successful load refreshes the
   cached copy; offline (or no answer within 6 seconds, e.g. weak airport Wi-Fi) the last cached
   copy is served. The Supabase library from jsdelivr is cached the same way so the app starts
   offline. Supabase data / weather / fx / Google calls are still left to the network (the app
   already falls back to its local data for those). Revert: set SHELL_OFFLINE = false. */
const SHELL_OFFLINE = true;
/* CHANGE 2026-10-04 F02-SW-01 (v3.0.0-alpha.2): cache names renamed to pt-icons-v1 / pt-shell-v1.
   This app (/Plan_Travel/...) shares its origin with the live Vietnam_Travel_Planner app, and Cache Storage is per
   origin: the live app's caches must never be read, overwritten or deleted from here (spec F02 §2).
   The worker is registered from its own directory with the default scope (that directory only), so it never
   controls the live app's pages. ownCache() guards every delete: a cache whose name doesn't start with "pt-" is
   never deleted. Nothing else in this file changed from v2.15.2. */
const ICON_CACHE = "pt-icons-v1";
const SHELL_CACHE = "pt-shell-v1";
function ownCache(name) { return typeof name === "string" && name.indexOf("pt-") === 0; }
const ICONS = ["icon-192.png", "icon-512.png"];
/* CHANGE 2026-11-13 F08-SW-01: app/js/f08.js (F08, v3.0.0-alpha.13) is a separate file, so offline (AC10) it must come from the shell cache like the
   page itself: precached at install, then network-first with a cache fallback (online the family still gets the live version).
   Nothing else in this file changed from the previous version. */
/* CHANGE 2026-11-13 F08-SW-02: was ["js/f08.js"]. countries.json added: the F08 range sheet needs the country names and
   time zones to save a range offline (AC10). */
/* CHANGE 2026-11-14 F24-SW-01: was ["js/f08.js", "countries.json"]. js/f24.js (F24, v3.0.0-alpha.14) and airports.json (the origin sheet) added, so the
   flight / lodging cards and the origin search work offline (C9). Nothing else in this file changed. */
/* CHANGE 2026-11-15 F14-SW-01: was ["js/f08.js", "js/f24.js", "countries.json", "airports.json"]. js/f14.js (F14, v3.0.0-alpha.15, the smart chat's page side) added, so it loads
   offline like the page itself (LEAN rule 7). Nothing else in this file changed. */
/* CHANGE 2026-11-16 F07-SW-01: was ["js/f08.js", "js/f24.js", "js/f14.js", "countries.json", "airports.json"]. js/f07.js (F07, v3.0.0-alpha.16, the relink screens and the manager card) added (LEAN rule 7). Nothing else in this file changed. */
/* CHANGE 2026-11-17 BUDGETPP-SW-01: "js/budgetpp.js" added to SHELL_FILES (LEAN rule 7). */
/* CHANGE 2026-11-17 NOTES-RICH-SW-01: "js/richnotes.js" added to SHELL_FILES (LEAN rule 7). */
/* CHANGE 2026-11-24 F13-TR-SW-01: + "js/f13tr.js" (F13-TR, 3.0.0-alpha.19.0). */
/* CHANGE 2026-11-24 F13-SW-02: + "css/f13-ltr.css" (F13 stage 3, 3.0.0-alpha.18.7). */
/* CHANGE 2026-11-24 F13-SW-01: was [..., "js/budgetpp.js", "countries.json", "airports.json"]. js/f13.js (F13 stage 0, 3.0.0-alpha.17.2) and i18n/en.json (the English catalog, fetched only when English is active) added, so they load offline (LEAN rule 7). Nothing else in this file changed. */
/* CHANGE 2026-11-24 F12-SW-01: "js/f12.js" added to SHELL_FILES (LEAN rule 7). */
/* CHANGE 2026-11-24 TC-A-SW-01: "js/tripcountry.js" added to SHELL_FILES (LEAN rule 7). */
/* CHANGE 2026-11-24 OFFMAP-SW-01: "js/offmap.js" added to SHELL_FILES (LEAN rule 7; OFFMAP core). Nothing else in this file changed. */
/* CHANGE 2026-11-24 OFFMAP-SW-02: was [... "js/offmap.js", "countries.json", "airports.json"]. vendor/leaflet.css, vendor/leaflet.js and vendor/protomaps-leaflet.js added (LEAN rule 7): the saved-map viewer loads them offline. Nothing else in this file changed. */
const SHELL_FILES = ["js/f08.js", "js/f24.js", "js/f14.js", "js/f07.js", "js/richnotes.js", "js/budgetpp.js", "js/f13.js", "js/f13tr.js", "i18n/en.json", "css/f13-ltr.css", "js/f12.js", "js/tripcountry.js", "js/offmap.js", "vendor/leaflet.css", "vendor/leaflet.js", "vendor/protomaps-leaflet.js", "countries.json", "airports.json"];
const NAV_TIMEOUT_MS = 6000;

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(Promise.all([
    caches.open(ICON_CACHE).then((c) => c.addAll(ICONS)).catch(() => {}),
    SHELL_OFFLINE ? caches.open(SHELL_CACHE).then((c) => Promise.all(["./"].concat(SHELL_FILES).map((f) => c.add(f).catch(() => {})))) : Promise.resolve()
  ]));
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    if (!SHELL_OFFLINE && ownCache(SHELL_CACHE)) await caches.delete(SHELL_CACHE); /* CHANGE 2026-10-04 F02-SW-01: guarded by ownCache() */
    await self.clients.claim();
  })());
});

function shellKey(url) {
  // one cached copy of the app regardless of "index.html" / query string
  const u = new URL(url);
  u.search = ""; u.hash = "";
  if (u.pathname.endsWith("/index.html")) u.pathname = u.pathname.slice(0, -"index.html".length);
  return u.href;
}

async function networkFirst(request, key, timeoutMs) {
  const cache = await caches.open(SHELL_CACHE);
  const net = fetch(request).then((res) => {
    if (res && (res.ok || res.type === "opaque")) cache.put(key, res.clone()).catch(() => {});
    return res;
  });
  const cached = () => cache.match(key);
  if (!timeoutMs) {
    try { return await net; } catch (err) { const c = await cached(); if (c) return c; throw err; }
  }
  return new Promise((resolve, reject) => {
    let done = false;
    const timer = setTimeout(async () => {
      const c = await cached();
      if (c && !done) { done = true; resolve(c); }
    }, timeoutMs);
    net.then((res) => { if (!done) { done = true; clearTimeout(timer); resolve(res); } })
      .catch(async (err) => {
        clearTimeout(timer);
        if (done) return;
        const c = await cached();
        done = true;
        c ? resolve(c) : reject(err);
      });
  });
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (ICONS.some((i) => url.pathname.endsWith(i))) {
    e.respondWith(caches.open(ICON_CACHE).then((c) => c.match(req)).then((r) => r || fetch(req))); /* CHANGE 2026-10-04 F02-SW-01: was caches.match(req), which searches every cache on the origin (incl. the live app's); now only this app's own icon cache */
    return;
  }
  if (!SHELL_OFFLINE) return;
  if (req.mode === "navigate" && url.origin === self.location.origin) {
    e.respondWith(networkFirst(req, shellKey(req.url), NAV_TIMEOUT_MS));
    return;
  }
  if (url.origin === self.location.origin && SHELL_FILES.some((f) => url.pathname.endsWith("/" + f))) {   /* CHANGE 2026-11-13 F08-SW-01 */
    e.respondWith(networkFirst(req, url.origin + url.pathname, NAV_TIMEOUT_MS));
    return;
  }
  if (url.hostname === "cdn.jsdelivr.net" && url.pathname.includes("/@supabase/supabase-js")) {
    e.respondWith(networkFirst(req, url.href, 0));
    return;
  }
  if (url.origin === self.location.origin && /\/(manifest\.webmanifest|manifest\.json|apple-touch-icon\.png)$/.test(url.pathname)) {
    e.respondWith(networkFirst(req, url.href, 0));
    return;
  }
  // Everything else (Supabase data, weather, fx, Google, the update check) goes straight to the network.
});
