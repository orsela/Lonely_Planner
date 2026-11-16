// Lonely Planner F07 · conversation 2 · Node tests of app/js/f07.js (the screens' HTML and the small helpers) · version 3.0.0-alpha.16
// CHANGE 2026-11-16 F07-QA-05: new file (no previous version). Covers the page-side logic without a browser: pending / expired / approved
//   markup, the WhatsApp link, the manager's request body (no role picker), the one-time toast. Layout is in test_f07_browser.py.
// Run: tests/f07/run_page.sh   (no browser, no network)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const store = new Map();
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); if (t && t.unref) t.unref(); return t; };   // pending() arms a 24 h expiry timer: must not keep node alive
globalThis.window = globalThis;
globalThis.localStorage = { getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
globalThis.document = { getElementById: () => null, createElement: () => ({}), head: { appendChild() {} } };
const req = createRequire(import.meta.url);
req("../../app/js/f07.js");
const F = window.__ptF07;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
function ctx(over = {}) {
  const c = { painted: null, screen: null, timers: 0, watching: false, st: { trip: { name: "יפן 2027", manager: "דנה", people: [{ person_id: "p1", display_name: "נועה" }] }, relinkInfo: null, me: null },
    el: { dataset: { screen: "pending" } }, esc, ROLE: { manager: "מנהל", editor: "עורך", viewer: "צופה" },
    hero: () => "<hero>", back: () => "", $: () => ({}), cancel() {}, watch() { c.watching = true; }, load() { c.loaded = true; },
    paint(s, h) { c.screen = s; c.painted = h; }, showForm() {}, route() {}, toast() {}, errText: () => "x", online: () => true };
  return Object.assign(c, over);
}

test("flag file loads and exposes the hooks flow.js and index.html call", () => {
  assert.equal(F.ok, true); assert.equal(F.version, "3.0.0-alpha.16");
  for (const k of ["form", "pending", "expired", "approvedNote", "markNotice", "tag", "mgrOpenHtml", "mountApp"]) assert.equal(typeof F[k], "function", k);
});

test("AC1/AC2 · pending screen: name + role kept, 'בתוקף עד', WhatsApp to the manager, cancel, watches the row", () => {
  const c = ctx(); c.st.relinkInfo = { display_name: "נועה", role: "editor", expires_at: new Date(Date.now() + 3600e3).toISOString() };
  F.pending(c);
  assert.equal(c.screen, "pending"); assert.match(c.painted, /הבקשה נשלחה לדנה/); assert.match(c.painted, /מכשיר חדש · נועה · עורך/);
  assert.match(c.painted, /id="lpjUntil"[^>]*>בתוקף עד \d\d:\d\d · \d\d\/\d\d/); assert.match(c.painted, /id="lpjCancel"/); assert.equal(c.watching, true);
  const href = /href="(https:\/\/wa\.me\/\?text=[^"]+)"/.exec(c.painted)[1];
  assert.equal(decodeURIComponent(href.split("text=")[1]), "היי, זה נועה. ביקשתי לחבר טלפון חדש לטיול יפן 2027 – אפשר לאשר?");
  assert.match(c.painted, /rel="noopener noreferrer"/);
});

test("names are escaped in the pending screen", () => {
  const c = ctx(); c.st.relinkInfo = { display_name: '<b>"x"', role: "viewer", expires_at: null }; F.pending(c);
  assert.ok(!c.painted.includes("<b>\"x\"")); assert.match(c.painted, /&lt;b&gt;&quot;x&quot;/);
});

test("AC3 · expired screen: 'הבקשה פגה', new request only when the person is still listed, back to the name list", () => {
  let c = ctx(); F.expired(c, { status: "expired", display_name: "נועה" });
  assert.equal(c.screen, "expired"); assert.match(c.painted, /<h2 id="lpjTitle">הבקשה פגה<\/h2>/); assert.match(c.painted, /id="lpjRelinkAgain"/); assert.match(c.painted, /id="lpjBackToName"/);
  c = ctx(); F.expired(c, { status: "expired", display_name: "מישהו אחר" });
  assert.ok(!c.painted.includes("lpjRelinkAgain")); assert.match(c.painted, /id="lpjBackToName"/);
});

test("approved screen note + one-time toast on the new device (spec §3)", () => {
  assert.match(F.approvedNote(), /מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים/);
  const shown = []; assert.equal(F.mountApp({ toast: m => shown.push(m) }), false);          // nothing marked: silent
  F.markNotice(); assert.equal(F.mountApp({ toast: m => shown.push(m) }), true);
  assert.equal(shown.length, 1); assert.equal(F.mountApp({ toast: m => shown.push(m) }), false); assert.equal(shown.length, 1);   // once
});

test("AC2 · manager card body: no role picker, warning line, approve / reject, disabled offline or while busy", () => {
  const h = F.mgrOpenHtml({ off: false, busy: false });
  assert.match(h, /data-act="approve"/); assert.match(h, /data-act="reject"/); assert.match(h, /id="pt7Warn"/);
  assert.ok(!h.includes("data-role") && !h.includes("pt5-seg"));
  assert.ok(!/data-act="approve"[^>]*disabled/.test(h));
  assert.match(F.mgrOpenHtml({ off: true, busy: false }), /data-act="approve" disabled/);
  assert.match(F.mgrOpenHtml({ off: false, busy: true }), /data-act="approve" disabled/);
  assert.match(F.tag(), /מכשיר חדש/);
});
