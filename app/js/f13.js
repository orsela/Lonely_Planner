/* Lonely Planner · F13 (full English support) · foundation: language state, dir/lang, translate/t(), catalog loader, locale helpers · version 3.0.0-alpha.17.2
   CHANGE 2026-11-24 F13-FN-01: new file (no previous version). Stage 0 of claude/Plan_Travel_F13_spec.md + claude/Plan_Travel_F13_decisions.md (D1 hybrid dictionary, D3 all at once + a personal
   test switch, D4 en-GB + an additive wrapper of toLocale*String). It ships NO visible English yet: the catalog (app/i18n/en.json) is empty and no screen calls t() / translate(); the later stages
   fill the catalog and add the connection points. Flag LANG_FEATURE (app/index.html): 'off' = exactly 3.0.0-alpha.17.1 (this file only defines an inert API: no storage, no listener, no fetch,
   no DOM change); 'beta' = only on a device where localStorage['pt-f13-beta']==='1' (open the app with #f13beta to set it, #f13beta-off to clear it; with it set, #f13en / #f13he choose the
   device language); 'on' = every device. English never applies to the Vietnam trip (forced Hebrew/RTL) nor when STORAGE_BACKEND is not 'cloud' (the legacy local app).
   Language order (spec §4): the device choice (pt:_device:lang) → the trip's default_lang → the browser language → 'he'. Everything inside try/catch: a failure here never breaks the app. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.17.2';
  const LANGS = ['he', 'en'];
  const LOCALES = { he: 'he-IL', en: 'en-GB' };            /* D4 */
  const FORCED_HE_TRIPS = ['f0200000-0000-4000-8000-000000000001'];   /* the Vietnam trip: never English (spec §2) */
  const LANG_KEY = 'pt:_device:lang';                      /* device level, read/written raw (the F02 gate namespaces Storage.prototype later) */
  const BETA_KEY = 'pt-f13-beta';
  const CATALOG_URL = 'i18n/en.json';

  /* ---------------- pure part (Node-testable) ---------------- */
  function normLang(x) {
    const s = String(x == null ? '' : x).toLowerCase().slice(0, 2);
    return s === 'iw' ? 'he' : (LANGS.indexOf(s) >= 0 ? s : null);
  }
  /* device choice → trip default → browser language → 'he' (spec §4.3) */
  function pickLang(o) {
    o = o || {};
    return normLang(o.device) || normLang(o.trip) || normLang(o.browser) || 'he';
  }
  function isForcedHebrew(tripId, backend) {
    if (backend != null && backend !== 'cloud') return true;
    return !!tripId && FORCED_HE_TRIPS.indexOf(String(tripId)) >= 0;
  }
  function ptLocale(lang) { return LOCALES[lang] || LOCALES.he; }
  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  /* "יום {n} · {name}" → regex + the placeholder order; every placeholder matches any text */
  function compilePattern(p) {
    const names = [];
    const src = String(p.he).split(/(\{[a-zA-Z0-9_]+\})/).map(function (part) {
      const m = /^\{([a-zA-Z0-9_]+)\}$/.exec(part);
      if (m) { names.push(m[1]); return '([\\s\\S]+?)'; }
      return escRe(part);
    }).join('');
    return { re: new RegExp('^' + src + '$'), names: names, en: String(p.en) };
  }
  function fill(tpl, params) {
    return String(tpl).replace(/\{([a-zA-Z0-9_]+)\}/g, function (all, k) {
      return params && Object.prototype.hasOwnProperty.call(params, k) && params[k] != null ? String(params[k]) : all;
    });
  }
  /* catalog = {version, exact:{he:en}, patterns:[{he,en}], keys:{key:{he,en}}} */
  function makeTranslator(catalog) {
    const cat = catalog || {};
    const exact = cat.exact || {};
    const pats = (cat.patterns || []).map(compilePattern);
    const keys = cat.keys || {};
    return {
      /* the Hebrew source → English; null when there is no entry (the caller keeps the Hebrew) */
      translate: function (src) {
        if (typeof src !== 'string' || !src) return null;
        const trimmed = src.trim();
        if (!trimmed) return null;
        const lead = src.slice(0, src.indexOf(trimmed.charAt(0))), trail = src.slice(lead.length + trimmed.length);
        let out = Object.prototype.hasOwnProperty.call(exact, trimmed) ? String(exact[trimmed]) : null;
        if (out == null) {
          for (let i = 0; i < pats.length; i++) {
            const m = pats[i].re.exec(trimmed);
            if (!m) continue;
            const params = {}; pats[i].names.forEach(function (n, j) { params[n] = m[j + 1]; });
            out = fill(pats[i].en, params); break;
          }
        }
        return out == null ? null : lead + out + trail;
      },
      /* new code: t('key', {n}) → the text in `lang`; unknown key/lang → the Hebrew text, then the key */
      t: function (key, params, lang) {
        const e = keys[key];
        if (!e) return String(key);
        const txt = (lang === 'en' && e.en != null) ? e.en : (e.he != null ? e.he : String(key));
        return fill(txt, params);
      }
    };
  }

  /* ---------------- runtime part ---------------- */
  const W = root && root.document ? root : null;
  const FLAG = (function () { try { return typeof LANG_FEATURE === 'undefined' ? 'off' : String(LANG_FEATURE); } catch (e) { return 'off'; } })();
  const MODE = (FLAG === 'on' || FLAG === 'beta') ? FLAG : 'off';

  const S = { lang: 'he', trip: null, tripLang: null, catalog: null, tr: makeTranslator(null), loaded: false, loading: null,
              changedDoc: false, miss: {}, missN: 0, patched: false };

  /* the browser's own Storage methods, captured before the F02 gate wraps Storage.prototype (same technique as F22a) */
  const RAW = (function () {
    try { const ls = root.localStorage, P = root.Storage.prototype; return { ls: ls, g: P.getItem, s: P.setItem, d: P.removeItem }; } catch (e) { return null; }
  })();
  function lsGet(k) { try { return RAW ? RAW.g.call(RAW.ls, k) : null; } catch (e) { return null; } }
  function lsSet(k, v) { try { if (RAW) RAW.s.call(RAW.ls, k, v); } catch (e) { /* storage may be blocked */ } }
  function lsDel(k) { try { if (RAW) RAW.d.call(RAW.ls, k); } catch (e) { /* storage may be blocked */ } }

  function backend() { try { return typeof STORAGE_BACKEND === 'undefined' ? null : STORAGE_BACKEND; } catch (e) { return null; } }
  function betaOn() { return lsGet(BETA_KEY) === '1'; }
  function enabled() { return MODE === 'on' || (MODE === 'beta' && betaOn()); }
  function browserLang() { try { return (root.navigator && (root.navigator.language || (root.navigator.languages || [])[0])) || ''; } catch (e) { return ''; } }
  function effectiveLang() {
    if (!enabled() || isForcedHebrew(S.trip, backend())) return 'he';
    return pickLang({ device: lsGet(LANG_KEY), trip: S.tripLang, browser: browserLang() });
  }
  function active() { return enabled() && effectiveLang() === 'en'; }

  /* additive wrapper of Date/Number toLocale*String (D4): with English active, 'he-IL' / 'he' → en-GB. Installed once, only when F13 is enabled;
     the wrapper checks the language on every call, so it is inert in Hebrew. A call without a locale is left alone. */
  function patchLocale() {
    if (S.patched || !root.Date) return; S.patched = true;
    [[root.Date.prototype, ['toLocaleString', 'toLocaleDateString', 'toLocaleTimeString']], [root.Number.prototype, ['toLocaleString']]].forEach(function (pair) {
      pair[1].forEach(function (name) {
        const orig = pair[0][name]; if (typeof orig !== 'function') return;
        pair[0][name] = function (loc) {
          if (S.lang === 'en' && (loc === 'he-IL' || loc === 'he')) { const a = Array.prototype.slice.call(arguments); a[0] = LOCALES.en; return orig.apply(this, a); }
          return orig.apply(this, arguments);
        };
      });
    });
  }

  function applyDoc() {
    const doc = W && W.document && W.document.documentElement; if (!doc) return;
    if (S.lang === 'en') { doc.lang = 'en'; doc.dir = 'ltr'; S.changedDoc = true; }
    else if (S.changedDoc) { doc.lang = 'he'; doc.dir = 'rtl'; S.changedDoc = false; }   /* back to exactly what the page ships with */
  }
  function apply() {
    if (MODE === 'off') return S.lang;
    const l = effectiveLang(), changed = l !== S.lang;
    S.lang = l;
    if (enabled()) patchLocale();
    applyDoc();
    if (l === 'en') loadCatalog();
    if (changed) { try { root.dispatchEvent(new root.CustomEvent('pt:langchange', { detail: { lang: l } })); } catch (e) { /* no CustomEvent */ } }
    return l;
  }

  function loadCatalog() {
    if (S.loaded || S.loading || typeof root.fetch !== 'function') return S.loading || Promise.resolve(S.catalog);
    S.loading = root.fetch(CATALOG_URL, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (j && typeof j === 'object') { S.catalog = j; S.tr = makeTranslator(j); }
      S.loaded = true; S.loading = null; return S.catalog;
    }).catch(function () { S.loading = null; return null; });   /* offline without a cached copy: stay with the Hebrew text */
    return S.loading;
  }

  /* ---------------- public API ---------------- */
  function translate(src) {
    if (!active()) return src;
    const out = S.tr.translate(src);
    if (out == null) { const k = String(src).trim(); if (k && !S.miss[k]) { S.miss[k] = 1; S.missN++; } return src; }   /* missing → the Hebrew stays; counted for coverage */
    return out;
  }
  function t(key, params) { return S.tr.t(key, params, active() ? 'en' : 'he'); }
  function setTrip(tripId, tripDefaultLang) { S.trip = tripId == null ? null : String(tripId); S.tripLang = normLang(tripDefaultLang); return apply(); }
  function setLang(l) { const n = normLang(l); if (!n || MODE === 'off') return S.lang; lsSet(LANG_KEY, n); return apply(); }

  const API = {
    VERSION: VERSION, mode: MODE,
    lang: function () { return S.lang; }, active: function () { return MODE !== 'off' && S.lang === 'en'; },
    locale: function () { return ptLocale(S.lang); },
    translate: translate, t: t, setTrip: setTrip, setLang: setLang, loadCatalog: loadCatalog,
    stats: function () { return { lang: S.lang, loaded: S.loaded, missing: S.missN, missingList: Object.keys(S.miss) }; },
    _pure: { normLang: normLang, pickLang: pickLang, isForcedHebrew: isForcedHebrew, ptLocale: ptLocale, makeTranslator: makeTranslator, compilePattern: compilePattern, fill: fill }
  };
  try { root.__ptF13 = API; } catch (e) { /* frozen global */ }

  /* ---------------- start-up (flag off: nothing below runs) ---------------- */
  if (MODE === 'off' || !W) return;
  try {
    if (MODE === 'beta') {
      const hashCmd = function () {
        let h = ''; try { h = String(root.location.hash || ''); } catch (e) { /* no location */ }
        if (h !== '#f13beta' && h !== '#f13beta-off' && h !== '#f13en' && h !== '#f13he') return false;
        if (h === '#f13beta') lsSet(BETA_KEY, '1');
        else if (h === '#f13beta-off') { lsDel(BETA_KEY); lsDel(LANG_KEY); }
        else if (betaOn()) lsSet(LANG_KEY, h === '#f13en' ? 'en' : 'he');
        try { root.history.replaceState(root.history.state, '', root.location.pathname + root.location.search); } catch (e) { /* no history */ }
        return true;
      };
      hashCmd();
      root.addEventListener('hashchange', function () { if (hashCmd()) { try { root.location.reload(); } catch (e) { apply(); } } });   /* a hash typed into an open app: reload, like F22a */
    }
    apply();
  } catch (e) { /* never break the app */ }
}(typeof window !== 'undefined' ? window : globalThis));

if (typeof module !== 'undefined' && module.exports) { module.exports = (typeof window !== 'undefined' ? window : globalThis).__ptF13; }
