/* Lonely Planner · F14 – smart chat, stage 1: the page side · version 3.0.0-alpha.15.1
   CHANGE 2026-11-15 F14-CHIPS-01 (alpha.15.1): what changed from alpha.15: new suggestions(list) — the suggested-question chips under the chat are not shown while F14 is on (it returns an empty list). Nothing else changed.
   CHANGE 2026-11-15 F14-A3-01 (step 3): new file (no alpha.14 equivalent). What changed from alpha.14: until now the chat button (CHAT_FEATURE='soon')
   showed a toast and nothing was sent anywhere; the server function chat-assistant (step 2, alpha.15.1) existed but nobody called it. This file is the
   client for it. With CHAT_FEATURE='on' and STORAGE_BACKEND='cloud' it
     1. wraps sendChatMessage (send): one question at a time, and while a question is in flight a request to the chat endpoint is rewritten on its way
        out (fetch hook, f14Fetch): + trip_id, lang, tripInfo {name, countries, homeCurrency, localCurrency, members, today, start, end, homeCity?,
        homeAirport?}, per-day country / city / tz and ISO dates (F08), the signed-in user's JWT instead of the anon key (no apikey header either);
     2. turns the server's refusals into one friendly chat line, with no retry: 401 unauthorized, 403 not_member, 429 daily_cap / rate_limited,
        503 chat_off (+ the old "coming soon" toast), 502 upstream_error, 504 / client timeout upstream_timeout, 413 too_large. Anything else (400, 500,
        no network) keeps the old generic chat error line;
     3. wraps chatMessageHtml: an action of type 'search_links' becomes the FB_Chat card (two prefilled search links, built by F24's f24ChatSearch). The card
        has no approve button and saves nothing; a request with missing[] becomes a plain question line; null (F24 off) = no card; offline = the buttons
        are disabled (F24 C9). Any other action type is dropped (D2: the chat never changes trip data).
   CHAT_FEATURE='soon' (today's value), 'off', local-only, or this file missing: none of this runs (alpha.14 behaviour). No server part in this step.
   Spec: claude/Plan_Travel_F14_spec.md (C2, C6–C8), status file overrides it. Everything the helpers need arrives through f14Configure() / attach() / mount(). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.15.1';

  /* ---- environment (injectable; the page gives it through attach at the gate and mount in the main script) ---- */
  const env = {};   // flag(), backend(), endpoint, client(), tripId(), withTimeout(p,ms), days(), tripName(), currencies() → {home,local}, countries() → {CODE:{en,he}}, home() → {city,airport},
                    // f08, chatSearch(params), travelers(), now(), online(), toast(msg), rerender(), bubble(role,text,cls,img)
  function f14Configure(o) { Object.assign(env, o || {}); }
  function attach(dep) { f14Configure(dep); B.attached = true; }
  const B = { attached: false, mounted: false, busy: 0, lastCode: '', real: null, mem: null, names: null };
  function flag() { return env.flag ? env.flag() : (typeof CHAT_FEATURE !== 'undefined' ? CHAT_FEATURE : 'soon'); }
  function backend() { return env.backend ? env.backend() : (typeof STORAGE_BACKEND !== 'undefined' ? STORAGE_BACKEND : 'cloud'); }
  function enabled() { return flag() === 'on' && backend() === 'cloud'; }
  function F8() { return env.f08 || root.__ptF08 || null; }
  function online() { try { return env.online ? !!env.online() : navigator.onLine !== false; } catch (e) { return true; } }
  const wt = (p, ms) => (env.withTimeout ? env.withTimeout(p, ms) : p);
  const escH = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pad = n => String(n).padStart(2, '0');
  const dm = iso => (iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) : '');
  const cut = (s, n) => String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);

  /* ---- 1. the friendly line for each refusal (no retry anywhere) ---- */
  const LINES = {
    unauthorized: 'צריך להתחבר מחדש כדי לשאול אותי. אפשר לרענן את האפליקציה ולנסות שוב.',
    not_member: 'נראה שאין לך גישה לטיול הזה, אז אני לא יכול לענות עליו.',
    daily_cap: 'הגענו למכסת השאלות היומית של הטיול. אפשר להמשיך מחר 🌙',
    rate_limited: 'שאלות מהר מדי 🙂 אפשר לנסות שוב בעוד רגע.',
    chat_off: "הצ'אט יחזור בקרוב",
    upstream_error: 'העוזר לא הצליח לענות כרגע. אפשר לנסות שוב בעוד כמה רגעים.',
    upstream_timeout: 'זה לקח יותר מדי זמן. אפשר לנסות שוב, אולי עם שאלה קצרה יותר.',
    too_large: 'השאלה גדולה מדי, כנראה בגלל התמונה. אפשר לנסות עם תמונה קטנה יותר או בלי תמונה.'
  };
  const BY_STATUS = { 401: 'unauthorized', 403: 'not_member', 413: 'too_large', 429: 'rate_limited', 502: 'upstream_error', 503: 'chat_off', 504: 'upstream_timeout' };
  const FRIENDLY = new Set(Object.keys(LINES).map(k => LINES[k]));   // these lines never go back to the model as history
  /* the server's error code (body.error, else by HTTP status) when it has a friendly line; '' = keep the old generic error line */
  function f14ErrorCode(status, body) {
    const c = body && typeof body.error === 'string' ? body.error : BY_STATUS[status] || '';
    return Object.prototype.hasOwnProperty.call(LINES, c) ? c : '';
  }
  function f14ErrorLine(code) { return Object.prototype.hasOwnProperty.call(LINES, code) ? LINES[code] : ''; }
  /* a normal 200 answer carrying the friendly line, so the page's own code shows it as an assistant message (and does not take its error branch) */
  function synth(code) {
    B.lastCode = code;
    return new Response(JSON.stringify({ answer: LINES[code], action: null, f14: code }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }

  /* ---- 2. what the request carries ---- */
  function localToday() { const t = new Date(env.now ? env.now() : Date.now()); return t.getFullYear() + '-' + pad(t.getMonth() + 1) + '-' + pad(t.getDate()); }
  function tid() { try { return env.tripId ? env.tripId() || '' : ''; } catch (e) { return ''; } }
  function client() { try { return env.client ? env.client() : null; } catch (e) { return null; } }
  function days() { let v = []; try { v = env.days ? env.days() : []; } catch (e) { v = []; } return Array.isArray(v) ? v : []; }
  async function jwt() {
    const c = client(); if (!c || !c.auth || typeof c.auth.getSession !== 'function') return '';
    try { const r = await wt(c.auth.getSession(), 5000), s = r && r.data && r.data.session; return s && typeof s.access_token === 'string' ? s.access_token : ''; } catch (e) { return ''; }
  }
  /* active members of the trip (cached 60 s); 0 = unknown, and then tripInfo has no members */
  async function members() {
    const t = tid(), c = client(); if (!t) return 0;
    const m = B.mem && B.mem.t === t ? B.mem : null;
    if (m && Date.now() - m.at < 60000) return m.n;
    if (!c || !online() || typeof c.from !== 'function') return m ? m.n : 0;
    try {
      const r = await wt(c.from('trip_members').select('id').eq('trip_id', t).eq('status', 'active'), 3000);
      if (r && !r.error && Array.isArray(r.data)) { B.mem = { t, n: r.data.length, at: Date.now() }; return r.data.length; }
    } catch (e) { }
    return m ? m.n : 0;
  }
  function countryNames() { try { return (env.countries ? env.countries() : null) || B.names || {}; } catch (e) { return {}; } }
  async function f14TripInfo() {
    const f8 = F8(), ds = days(), info = { today: localToday() };
    try { const n = env.tripName ? await env.tripName() : ''; if (n) info.name = cut(n, 80); } catch (e) { }
    const seen = [];   // the countries the days themselves name, in order (a flight day inherits no country here); a trip with none (the legacy Vietnam trip) reads F08's default
    ds.forEach(d => { const c = d && d.country; if (/^[A-Z]{2}$/.test(c || '') && seen.indexOf(c) < 0) seen.push(c); });
    if (!seen.length && f8) ds.forEach(d => { let c = ''; try { c = f8.f08DayCountry(d); } catch (e) { } if (c && seen.indexOf(c) < 0) seen.push(c); });
    if (seen.length) { const nm = countryNames(); info.countries = seen.map(c => (nm[c] && nm[c].en) || c); }
    let cur = null; try { cur = env.currencies ? env.currencies() : null; } catch (e) { }
    if (cur && cur.home) info.homeCurrency = cut(cur.home, 3);
    if (cur && cur.local) info.localCurrency = cut(cur.local, 3);
    const isos = f8 ? ds.map(d => { try { return f8.f08DayIso(d); } catch (e) { return ''; } }).filter(Boolean).sort() : [];
    if (isos.length) { info.start = isos[0]; info.end = isos[isos.length - 1]; }
    const n = await members(); if (n > 0) info.members = n;
    let h = null; try { h = env.home ? env.home() : null; } catch (e) { }
    if (h && h.city) info.homeCity = cut(h.city, 80);
    if (h && /^[A-Za-z]{3}$/.test(h.airport || '')) info.homeAirport = String(h.airport).toUpperCase();
    return info;
  }
  /* the route the page sends is {day, date 'dd/mm/yyyy', region, title}; the server wants ISO dates and the country / city / zone of each day (C6) */
  function f14EnrichTrip(trip) {
    const f8 = F8(), ds = days(); if (!Array.isArray(trip) || !f8) return trip;
    return trip.map((x, i) => {
      const d = ds[i]; if (!d || !x || typeof x !== 'object') return x;
      const o = Object.assign({}, x);
      const side = q => { const r = {}; if (q && q.country) r.country = q.country; if (q && q.city) r.city = cut(q.city, 60); return r; };
      try {
        const iso = f8.f08DayIso(d); if (iso) o.date = iso;
        if (f8.f08IsFlight(d)) { o.flight = { from: side(f8.f08FlightFrom(d)), to: side(f8.f08FlightTo(d)) }; if (d.country) o.country = d.country; if (d.tz) o.tz = d.tz; }   // a flight day has two sides, not one country
        else { o.country = f8.f08DayCountry(d); o.tz = f8.f08DayTz(d); }
      } catch (e) { }
      if (d.city) o.city = cut(d.city, 60);
      return o;
    });
  }
  function dropFriendly(history) { return Array.isArray(history) ? history.filter(h => !(h && h.role === 'assistant' && FRIENDLY.has(String(h.text || '').trim()))) : history; }

  /* ---- 3. the fetch to the chat endpoint, rewritten and answered (realFetch = the page's own fetch) ---- */
  async function f14Fetch(realFetch, input, init) {
    const token = await jwt(); if (!token) return synth('unauthorized');     // no session → no call, no retry
    const t = tid(); if (!t) return synth('not_member');
    let body; try { body = JSON.parse((init && init.body) || '{}'); } catch (e) { return new Response('{}', { status: 400 }); }   // not our request: the page's usual error line
    body.trip_id = t; body.lang = 'he';
    body.tripInfo = await f14TripInfo();
    body.trip = f14EnrichTrip(body.trip);
    body.history = dropFriendly(body.history);
    const next = Object.assign({}, init, { headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token }, body: JSON.stringify(body) });
    let res;
    try { res = await realFetch(input, next); } catch (e) {
      if (e && e.name === 'AbortError') return synth('upstream_timeout');          // the page's own 40 s limit
      throw e;                                                                     // no network: the page's usual error line
    }
    if (res.ok) {
      try {   // D2: the chat never changes trip data → only 'search_links' may come back as an action
        const d = await res.clone().json();
        if (d && d.action && d.action.type !== 'search_links') { d.action = null; return new Response(JSON.stringify(d), { status: 200, headers: { 'Content-Type': 'application/json' } }); }
      } catch (e) { }
      return res;
    }
    let data = null; try { data = await res.clone().json(); } catch (e) { }
    const code = f14ErrorCode(res.status, data);
    return code ? synth(code) : res;
  }

  /* sendChatMessage wrapper: one question at a time (a second Enter during an answer would burn the daily count); the toast of the old "soon" state for chat_off */
  function send(orig, text) {
    if (!enabled()) return orig(text);
    if (B.busy > 0) return Promise.resolve();
    B.busy++; B.lastCode = '';
    let p; try { p = Promise.resolve(orig(text)); } catch (e) { B.busy--; throw e; }
    return p.finally(() => {
      B.busy--;
      if (B.lastCode === 'chat_off') { try { env.toast && env.toast(LINES.chat_off); } catch (e) { } }
    });
  }
  function installFetchHook() {
    if (B.real || typeof root.fetch !== 'function') return;
    const real = root.fetch.bind(root); B.real = real;
    root.fetch = function (input, init) {
      let url = ''; try { url = typeof input === 'string' ? input : (input && input.url) || String(input); } catch (e) { }
      if (B.busy > 0 && env.endpoint && url === env.endpoint && init && init.method === 'POST') return f14Fetch(real, input, init);
      return real(input, init);
    };
  }

  /* ---- 4. the FB_Chat card ---- */
  const OFFLINE_LINE = 'אין חיבור – אפשר לחפש כשהרשת תחזור.';
  const CSS = `
.p14-row{display:flex;justify-content:flex-end}
.p14-card{width:86%;max-width:340px;box-sizing:border-box;border:1.5px dashed #9cc4b2;background:#f3faf6;border-radius:14px;padding:11px 12px;display:flex;flex-direction:column;gap:8px;margin:2px 0 8px;color:#17211b}
.p14-card b.p14-t{font-size:14px;color:#0b5841}
.p14-pt{display:flex;gap:6px;align-items:baseline;font-size:13px;min-width:0}.p14-pt span{color:#5f6861;width:22px;flex:none}.p14-pt b{overflow-wrap:anywhere}
.p14-meta{display:flex;gap:6px;flex-wrap:wrap}.p14-meta span{font-size:12px;font-weight:700;color:#3a443d;background:#fff;border:1px solid #e4e6df;border-radius:999px;padding:4px 10px}
.p14-go{display:flex;align-items:center;justify-content:space-between;min-height:48px;border-radius:12px;padding:0 14px;font-size:14px;font-weight:800;text-decoration:none;box-sizing:border-box}
.p14-go.p{background:#0f6b4f;color:#fff}.p14-go.s{background:#fff;color:#0f6b4f;border:1.5px solid #0f6b4f}.p14-go.dis{background:#c9ccc3;color:#fff;border:0;cursor:default}
.p14-off{margin:0;font-size:12.5px;color:#8a5a00;background:#fff6e0;border-radius:10px;padding:8px 10px}
`;
  function placeLabel(p) { const f = env.f24 || root.__ptF24; return f && f.f24PlaceLabel ? f.f24PlaceLabel(p) : (p && (p.cityHe || p.city || p.iata)) || ''; }
  const travelers = (n, hotel) => (hotel ? (n === 1 ? 'אורח אחד' : n + ' אורחים') : (n === 1 ? 'נוסע אחד' : n + ' נוסעים')) + ' · מחברי הטיול';
  /* pure: the card of one search_links result (the object of f24ChatSearch); o.online false → disabled buttons + the offline line */
  function f14CardHtml(r, o) {
    const on = !o || o.online !== false;
    const link = (u, cls, label) => on ? '<a class="p14-go ' + cls + '" href="' + escH(u) + '" target="_blank" rel="noopener noreferrer">' + escH(label) + ' <span aria-hidden="true">↗</span></a>'
      : '<span class="p14-go ' + cls + ' dis" role="link" aria-disabled="true">' + escH(label) + ' <span aria-hidden="true">↗</span></span>';
    const off = on ? '' : '<p class="p14-off" role="status">' + OFFLINE_LINE + '</p>';
    if (r.kind === 'flight') {
      return '<b class="p14-t">✈️ חיפוש טיסה</b>' +
        '<div class="p14-pt"><span>מ:</span><b>' + escH(placeLabel(r.from)) + '</b></div><div class="p14-pt"><span>אל:</span><b>' + escH(placeLabel(r.to)) + '</b></div>' +
        '<div class="p14-meta"><span>' + dm(r.date) + (r.roundTrip ? ' · הלוך' : ' · כיוון אחד') + '</span>' + (r.roundTrip ? '<span>חזור ' + dm(r.returnDate) + '</span>' : '') + '<span>' + escH(travelers(r.adults, false)) + '</span></div>' +
        link(r.links.googleFlights, 'p', 'חיפוש ב-Google Flights') + link(r.links.skyscanner, 's', 'חיפוש ב-Skyscanner') + off;
    }
    return '<b class="p14-t">🏨 חיפוש לינה</b>' +
      '<div class="p14-meta"><span>' + escH(r.cityHe || r.city) + '</span><span>' + dm(r.checkin) + ' – ' + dm(r.checkout) + '</span><span>' + (r.nights === 1 ? 'לילה אחד' : r.nights + ' לילות') + '</span><span>' + escH(travelers(r.adults, true)) + '</span></div>' +
      link(r.links.booking, 'p', 'חיפוש ב-Booking') + link(r.links.googleHotels, 's', 'חיפוש ב-Google Hotels') + off;
  }
  /* a search the model could not complete (f24ChatSearch said what is missing) → one plain question line */
  function f14MissingLine(r) {
    const to = r.missing.indexOf('to') >= 0, date = r.missing.indexOf('date') >= 0;
    if (r.kind === 'hotel') return to && date ? 'באיזו עיר ולאילו תאריכים לחפש לינה? (למשל 17/05/2027)' : to ? 'באיזו עיר לחפש לינה?' : 'מאיזה תאריך לחפש לינה? (למשל 17/05/2027)';
    return to && date ? 'לאן ובאיזה תאריך לחפש טיסה? (למשל 17/05/2027)' : to ? 'לאן לחפש טיסה?' : 'באיזה תאריך לחפש טיסה? (למשל 17/05/2027)';
  }
  function bubble(role, text) { return env.bubble ? env.bubble(role, text) : '<div class="chat-row"><div class="chat-bubble ' + escH(role) + '">' + escH(text) + '</div></div>'; }
  /* chatMessageHtml wrapper: search_links → bubble + card (or a question line, or just the bubble); everything else → the previous function */
  function f14MessageHtml(m, idx, orig) {
    if (!enabled() || !m || !m.action || m.action.type !== 'search_links') return orig(m, idx);
    let r = null; try { r = env.chatSearch ? env.chatSearch(m.action.params || {}) : (root.f24ChatSearch ? root.f24ChatSearch(m.action.params || {}) : null); } catch (e) { r = null; }
    const text = m.text && !/^הנה (מה שאני חושב|הצעה)/.test(m.text) ? m.text : 'הנה הקישורים 👇';
    if (!r) return bubble(m.role, m.text || text);
    if (r.missing) return bubble(m.role, f14MissingLine(r));
    return bubble(m.role, text) + '<div class="p14-row"><div class="p14-card" data-p14-kind="' + escH(r.kind) + '">' + f14CardHtml(r, { online: online() }) + '</div></div>';
  }

  /* the chat's suggested questions are switched off while F14 is on (Or, 15/11); the page's own list is ignored */
  function suggestions(list) { return enabled() ? [] : list; }

  /* mount (main script, after the chat code): styles, country names, repaint on connection change. false = nothing to do (flag, backend). */
  function mount(dep) {
    f14Configure(dep);
    if (!enabled() || typeof document === 'undefined') return false;
    if (B.mounted) return true;
    const st = document.createElement('style'); st.id = 'ptF14Css'; st.textContent = CSS; document.head.appendChild(st);
    installFetchHook();
    const again = () => { try { if (env.rerender) env.rerender(); } catch (e) { } };
    window.addEventListener('online', again); window.addEventListener('offline', again);
    fetch('countries.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : [])).then(l => { const m = {}; (l || []).forEach(x => { if (x && x.code) m[x.code] = x; }); if (Object.keys(m).length) B.names = m; }).catch(() => { });
    B.mounted = true; return true;
  }

  const api = { version: VERSION, f14Configure, f14ErrorCode, f14ErrorLine, f14TripInfo, f14EnrichTrip, f14Fetch, f14CardHtml, f14MissingLine, f14MessageHtml, attach, mount, send, messageHtml: f14MessageHtml, enabled, suggestions };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.__ptF14 = api; Object.keys(api).forEach(k => { if (k.indexOf('f14') === 0) root[k] = api[k]; }); }
})(typeof window !== 'undefined' ? window : globalThis);
