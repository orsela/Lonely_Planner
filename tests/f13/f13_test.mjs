// Lonely Planner F13 · stage 0 · Node tests of app/js/f13.js (language state, translate/t, catalog, locale wrapper, flag off) · version 3.0.0-alpha.17.2
// CHANGE 2026-11-24 F13-QA-02: new file (no previous version). Each case loads a fresh copy of the module with its own fake window, so the flag value is per case.
// Run: tests/f13/run.sh   (no browser, no network)
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../app/js/f13.js"), "utf8");

/* a fake browser: localStorage, documentElement, location.hash, fetch with a counter; returns {win, run(), calls} */
function load({ flag, backend = "cloud", store = {}, hash = "", nav = "he-IL", catalog = null } = {}) {
  const ls = new Map(Object.entries(store));
  const calls = { fetch: [], listeners: [], setItem: 0, removeItem: 0 };
  class Storage {
    getItem(k) { return ls.has(k) ? ls.get(k) : null; }
    setItem(k, v) { calls.setItem++; ls.set(k, String(v)); }
    removeItem(k) { calls.removeItem++; ls.delete(k); }
  }
  const doc = { documentElement: { lang: "he", dir: "rtl" } };
  const win = {
    document: doc, Storage, localStorage: new Storage(), navigator: { language: nav },
    location: { hash, pathname: "/app/", search: "", reload() { win.reloaded = true; } },
    history: { state: null, replaceState(s, t, url) { win.location.hash = ""; win.replaced = url; } },
    addEventListener(n, f) { calls.listeners.push(n); win["on_" + n] = f; },
    dispatchEvent(e) { (win.events = win.events || []).push(e.detail && e.detail.lang); return true; },
    CustomEvent: class { constructor(n, o) { this.type = n; this.detail = o && o.detail; } },
    fetch(u) { calls.fetch.push(u); return Promise.resolve({ ok: !!catalog, json: () => Promise.resolve(catalog) }); },
  };
  win.window = win;
  const ctx = vm.createContext(win);
  vm.runInContext("var STORAGE_BACKEND=" + JSON.stringify(backend) + ";" + (flag === undefined ? "" : "var LANG_FEATURE=" + JSON.stringify(flag) + ";"), ctx);
  vm.runInContext(SRC, ctx);
  /* the context has its own Date/Number: patching them never leaks into the host or into the other cases */
  return { win, calls, ls, F: win.__ptF13, D: vm.runInContext("Date", ctx), N: vm.runInContext("Number", ctx) };
}
const settle = () => new Promise(r => setImmediate(r));

test("pure: normLang, pickLang order (device > trip > browser > he)", () => {
  const { F } = load({ flag: "off" }); const P = F._pure;
  assert.equal(P.normLang("EN-gb"), "en"); assert.equal(P.normLang("iw"), "he"); assert.equal(P.normLang("fr"), null);
  assert.equal(P.pickLang({ device: "en", trip: "he", browser: "he" }), "en");
  assert.equal(P.pickLang({ trip: "en", browser: "he-IL" }), "en");
  assert.equal(P.pickLang({ browser: "en-US" }), "en");
  assert.equal(P.pickLang({ browser: "ru" }), "he");
  assert.equal(P.pickLang({}), "he"); assert.equal(P.pickLang(), "he");
});

test("pure: Vietnam trip and a non-cloud backend are forced Hebrew", () => {
  const P = load({ flag: "off" }).F._pure;
  assert.equal(P.isForcedHebrew("f0200000-0000-4000-8000-000000000001", "cloud"), true);
  assert.equal(P.isForcedHebrew("fd5c2b13-cdc0-455e-9c12-b52f2e45a334", "cloud"), false);
  assert.equal(P.isForcedHebrew(null, "cloud"), false);
  assert.equal(P.isForcedHebrew("x", "local"), true);
});

test("pure: translator — exact, whitespace kept, patterns with placeholders, miss = null", () => {
  const P = load({ flag: "off" }).F._pure;
  const T = P.makeTranslator({ exact: { "עוד": "More", "שמירה": "Save" }, patterns: [{ he: "יום {n} · {name}", en: "Day {n} · {name}" }, { he: "{n} נוסעים", en: "{n} travellers" }],
    keys: { greet: { he: "שלום {name}", en: "Hello {name}" }, only_he: { he: "רק עברית" } } });
  assert.equal(T.translate("עוד"), "More");
  assert.equal(T.translate("  שמירה \n"), "  Save \n");
  assert.equal(T.translate("יום 3 · בוקרשט"), "Day 3 · בוקרשט");
  assert.equal(T.translate("8 נוסעים"), "8 travellers");
  assert.equal(T.translate("לא קיים"), null); assert.equal(T.translate(""), null); assert.equal(T.translate("   "), null); assert.equal(T.translate(5), null);
  assert.equal(T.t("greet", { name: "Dana" }, "en"), "Hello Dana"); assert.equal(T.t("greet", { name: "דנה" }, "he"), "שלום דנה");
  assert.equal(T.t("only_he", {}, "en"), "רק עברית"); assert.equal(T.t("nope", {}, "en"), "nope");
  assert.equal(T.t("greet", {}, "en"), "Hello {name}");   /* a missing param stays visible, never "undefined" */
});

test("pure: ptLocale", () => {
  const P = load({ flag: "off" }).F._pure; assert.equal(P.ptLocale("en"), "en-GB"); assert.equal(P.ptLocale("he"), "he-IL"); assert.equal(P.ptLocale("xx"), "he-IL");
});

test("flag off: inert — no storage, no listener, no fetch, no DOM change, English requests ignored", async () => {
  const w = load({ flag: "off", store: { "pt:_device:lang": "en", "pt-f13-beta": "1" }, hash: "#f13beta", nav: "en-US" });
  await settle();
  const { F, win, calls } = w;
  assert.equal(F.mode, "off"); assert.equal(F.lang(), "he"); assert.equal(F.active(), false);
  assert.equal(win.document.documentElement.lang, "he"); assert.equal(win.document.documentElement.dir, "rtl");
  assert.deepEqual(calls.fetch, []); assert.deepEqual(calls.listeners, []); assert.equal(calls.setItem, 0); assert.equal(calls.removeItem, 0);
  assert.equal(win.location.hash, "#f13beta");   /* the hash is not even consumed */
  assert.equal(F.setLang("en"), "he"); assert.equal(calls.setItem, 0);
  assert.equal(F.translate("עוד"), "עוד"); assert.equal(F.t("k"), "k");
  assert.equal(String(w.D.prototype.toLocaleString).includes("native code"), true);   /* Date was never patched */
});

test("flag missing = off", () => {
  const { F, calls } = load({ flag: undefined }); assert.equal(F.mode, "off"); assert.deepEqual(calls.listeners, []);
});

test("beta without the device key: nothing applies; hash #f13beta sets the key; #f13en picks English; #f13beta-off clears both", async () => {
  let w = load({ flag: "beta", store: { "pt:_device:lang": "en" }, nav: "en-GB" }); await settle();
  assert.equal(w.F.active(), false); assert.equal(w.win.document.documentElement.dir, "rtl"); assert.deepEqual(w.calls.fetch, []);
  w = load({ flag: "beta", hash: "#f13beta" }); await settle();
  assert.equal(w.ls.get("pt-f13-beta"), "1"); assert.equal(w.win.location.hash, "");   /* the hash is removed at once */
  assert.equal(w.F.lang(), "he");
  w = load({ flag: "beta", store: { "pt-f13-beta": "1" }, hash: "#f13en" }); await settle();
  assert.equal(w.ls.get("pt:_device:lang"), "en"); assert.equal(w.F.lang(), "en"); assert.equal(w.F.active(), true);
  assert.equal(w.win.document.documentElement.lang, "en"); assert.equal(w.win.document.documentElement.dir, "ltr");
  w = load({ flag: "beta", store: { "pt-f13-beta": "1", "pt:_device:lang": "en" }, hash: "#f13beta-off" }); await settle();
  assert.equal(w.ls.has("pt-f13-beta"), false); assert.equal(w.ls.has("pt:_device:lang"), false); assert.equal(w.F.active(), false);
  w = load({ flag: "beta", hash: "#f13en" }); await settle();   /* #f13en without the beta key does nothing */
  assert.equal(w.ls.has("pt:_device:lang"), false); assert.equal(w.F.lang(), "he");
});

test("on: English from the device choice; Vietnam trip and a local backend stay Hebrew/RTL; leaving Vietnam restores English", async () => {
  const w = load({ flag: "on", store: { "pt:_device:lang": "en" } }); await settle();
  const { F, win } = w, el = win.document.documentElement;
  assert.equal(F.lang(), "en"); assert.equal(el.dir, "ltr"); assert.equal(el.lang, "en");
  F.setTrip("f0200000-0000-4000-8000-000000000001", "en");
  assert.equal(F.lang(), "he"); assert.equal(el.dir, "rtl"); assert.equal(el.lang, "he");
  F.setTrip("fd5c2b13-cdc0-455e-9c12-b52f2e45a334", "he");
  assert.equal(F.lang(), "en"); assert.equal(el.dir, "ltr");
  F.setLang("he"); assert.equal(F.lang(), "he"); assert.equal(el.dir, "rtl"); assert.equal(w.ls.get("pt:_device:lang"), "he");
  assert.deepEqual([...win.events], ["en", "he", "en", "he"]);   /* one langchange event per real change (the first is the start-up en) */
  const loc = load({ flag: "on", backend: "local", store: { "pt:_device:lang": "en" } }); await settle();
  assert.equal(loc.F.lang(), "he"); assert.equal(loc.win.document.documentElement.dir, "rtl");
});

test("language order with no device choice: trip default, then the browser, then Hebrew", async () => {
  let w = load({ flag: "on", nav: "en-US" }); await settle(); assert.equal(w.F.lang(), "en");
  w = load({ flag: "on", nav: "he-IL" }); await settle(); assert.equal(w.F.lang(), "he");
  w.F.setTrip("t1", "en"); assert.equal(w.F.lang(), "en");
  w = load({ flag: "on", nav: "ru" }); await settle(); assert.equal(w.F.lang(), "he");
});

test("catalog: fetched only when English is active; translate falls back to Hebrew and counts the gaps", async () => {
  const cat = { exact: { "עוד": "More" }, patterns: [{ he: "יום {n}", en: "Day {n}" }], keys: { k: { he: "ש", en: "s" } } };
  let w = load({ flag: "on", nav: "he-IL", catalog: cat }); await settle();
  assert.deepEqual(w.calls.fetch, []); assert.equal(w.F.translate("עוד"), "עוד");
  w = load({ flag: "on", store: { "pt:_device:lang": "en" }, catalog: cat }); await settle(); await settle();
  assert.deepEqual(w.calls.fetch, ["i18n/en.json"]);
  assert.equal(w.F.translate("עוד"), "More"); assert.equal(w.F.translate("יום 5"), "Day 5"); assert.equal(w.F.t("k"), "s");
  assert.equal(w.F.translate("חסר"), "חסר");
  const st = w.F.stats(); assert.equal(st.loaded, true); assert.equal(st.missing, 1); assert.deepEqual([...st.missingList], ["חסר"]);
  w = load({ flag: "on", store: { "pt:_device:lang": "en" }, catalog: null }); await settle(); await settle();   /* offline / 404: the app stays usable in Hebrew text */
  assert.equal(w.F.translate("עוד"), "עוד");
});

test("locale wrapper: 'he-IL' → en-GB only while English is active; no-locale calls untouched", async () => {
  const w = load({ flag: "on", store: { "pt:_device:lang": "en" } }); await settle();
  const d = new w.D(Date.UTC(2026, 10, 24, 15, 5));   /* 24 Nov 2026 */
  const opts = { timeZone: "UTC", day: "2-digit", month: "2-digit", year: "numeric" };
  const en = d.toLocaleDateString("he-IL", opts);
  assert.equal(en, "24/11/2026");   /* en-GB */
  assert.equal(d.toLocaleDateString("en-US", opts), "11/24/2026");   /* other locales untouched */
  assert.equal(d.toLocaleTimeString("he-IL", { timeZone: "UTC", hour: "2-digit", minute: "2-digit" }), "15:05");
  assert.equal(new w.N(1234.5).toLocaleString("he-IL", { maximumFractionDigits: 2 }), "1,234.5");
  w.F.setLang("he");
  assert.notEqual(d.toLocaleDateString("he-IL", opts), "24/11/2026");   /* he-IL has its own dotted format (24.11.2026) */
});

test("beta without the key never patches Date (zero footprint)", async () => {
  const w = load({ flag: "beta" }); await settle();
  assert.equal(String(w.D.prototype.toLocaleString).includes("native code"), true);   /* the native function, not our wrapper */
  assert.equal(String(w.D.prototype.toLocaleDateString).includes("native code"), true);
});
