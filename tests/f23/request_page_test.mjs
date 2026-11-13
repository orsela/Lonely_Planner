// Lonely Planner F23 · /request/ page developer smoke test (Playwright, Chromium) · version 1.0.0
// CHANGE 2026-11-13 F23-QA-07: new file (no previous version). Serves the repo from a local static server, stubs
// Cloudflare Turnstile and the request-trip function (route interception — nothing leaves the machine), and walks the
// F23 screens at 390 px: criteria 1, 2, 4, 5, 6 (page side), 11 (flags), 12 (390 px, RTL/LTR, touch ≥ 44 px, no
// horizontal scroll). Run: node tests/f23/request_page_test.mjs [--shots <dir>]
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");   // the globally installed Playwright (require() finds it; ESM import does not)
import http from "node:http";
import { readFileSync, existsSync, statSync, mkdirSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SHOTS = process.argv.includes("--shots") ? process.argv[process.argv.indexOf("--shots") + 1] : "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
const MIME = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript", ".png": "image/png" };
let flags = {};   // per-test replacements of the page's flag constants
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split("?")[0]);
  if (p.endsWith("/")) p += "index.html";
  const f = join(REPO, p);
  if (!f.startsWith(REPO) || !existsSync(f) || !statSync(f).isFile()) { res.writeHead(404); res.end("nf"); return; }
  let body = readFileSync(f);
  if (p === "/request/index.html") {
    let s = body.toString("utf8");
    for (const [k, v] of Object.entries(flags)) {
      const re = new RegExp("const " + k + "='[^']*';");
      if (!re.test(s)) throw new Error("flag not found: " + k);
      s = s.replace(re, "const " + k + "='" + v + "';");
    }
    body = Buffer.from(s, "utf8");
  }
  res.writeHead(200, { "Content-Type": MIME[extname(f)] || "application/octet-stream", "Cache-Control": "no-store" });
  res.end(body);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = "http://127.0.0.1:" + server.address().port;
const TOKEN = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v";   // 43 chars
const SESSION = "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i2H1g0F9e";

let pass = 0, fail = 0;
const results = [];
function ok(c, msg) { if (!c) throw new Error(msg); }
function eq(a, b, msg) { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${msg}\n    actual:   ${JSON.stringify(a)}\n    expected: ${JSON.stringify(b)}`); }

const browser = await chromium.launch();
async function open(opts = {}) {
  flags = opts.flags || {};
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: opts.locale || "he-IL", deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const calls = [];
  const fn = opts.fn || {};
  await page.route("**/challenges.cloudflare.com/**", (r) => r.fulfill({ contentType: "text/javascript",
    body: "window.turnstile={render:function(el,o){el.textContent='[turnstile stub]';setTimeout(function(){o.callback('ts-token')},0);return 1},reset:function(){},remove:function(){}};window.rqTurnstileReady&&window.rqTurnstileReady();" }));
  await page.route("**/functions/v1/request-trip", async (r) => {
    if (r.request().method() === "OPTIONS") return r.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*" } });
    const b = JSON.parse(r.request().postData() || "{}");
    calls.push(b);
    const h = fn[b.action];
    const out = typeof h === "function" ? h(b, calls.filter((c) => c.action === b.action).length) : h;
    await r.fulfill({ status: out && out.ok === false ? 400 : 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(out ?? { ok: false, code: "server_error" }) });
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(BASE + "/request/" + (opts.query || ""));
  await page.waitForSelector("#rqApp[data-screen=form]");
  return { page, ctx, calls, errors };
}
const noHScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const small = (page, sel) => page.evaluate((s) => [...document.querySelectorAll(s)].filter((e) => e.offsetParent !== null).map((e) => { const r = e.getBoundingClientRect(); return [e.id || e.textContent.trim().slice(0, 20), Math.round(r.width), Math.round(r.height)]; }).filter((x) => x[2] < 44 || x[1] < 44), sel);
async function fillBase(page, email = "roy@example.com") {
  await page.fill("#rqName", "רועי");
  await page.fill("#rqEmail", email);
  await page.selectOption("#rqWhen", { index: 3 });
}
async function typeCode(page, code = "123456") {
  await page.waitForSelector("#rqApp[data-screen=code]");
  await page.fill("#rqOtp0", code);
}
const ITEMS1 = [{ country: "GE", reason: "הרים ירוקים במאי ומטבח שילדים אוהבים.", tags: ["טיסות ישירות", "אביב נעים", "טיול ברכב"] },
  { country: "PT", reason: "חופי האטלנטי ועיירות על צוקים.", tags: ["חופים וערים"] }, { country: "ME", reason: "מפרץ קוטור, אגמים והרים.", tags: [] }];
const ITEMS2 = [{ country: "GR", reason: "איים וחופים.", tags: ["חופים"] }, { country: "CY", reason: "קרוב וחם.", tags: [] }, { country: "HR", reason: "חוף דלמטי.", tags: [] }];
const READY = (c) => ({ ok: true, request_id: "r1", next: "ready", invite_token: TOKEN, mail_sent: true, countries: c, month: "2027-02-01", travellers: 2, draft_name: "x" });

async function T(name, fn) {
  let h = null;
  try { await fn((o) => open(o).then((x) => (h = x))); pass++; results.push("  ok   " + name); }
  catch (e) { fail++; results.push("  FAIL " + name + "\n    " + String(e.message || e)); if (h && SHOTS) await h.page.screenshot({ path: join(SHOTS, "FAIL_" + name.slice(0, 12).replace(/\W+/g, "_") + ".png"), fullPage: true }).catch(() => {}); }
  finally { if (h) await h.ctx.close(); }
}

await T("P-01 [C1][C12] auto form (he): subtitle + 3 lines, where-choice, privacy line; RTL, no horizontal scroll", async (open) => {
  const { page, errors } = await open();
  eq(await page.getAttribute("html", "dir"), "rtl", "dir");
  eq(await page.textContent(".rq-sub"), "מקימים כאן טיול משותף ומקבלים אפליקציה אחת לכל המטיילים.", "subtitle");
  eq(await page.$$eval("#rqWhat > div", (a) => a.map((d) => [d.className, d.textContent])), [["yes", "מסלול יומי ומפה, מסמכים והוצאות במקום אחד"],
    ["yes", "צ'אט חכם שמכיר את הטיול"], ["no", "לא מזמינים כאן טיסות או מלונות בעצמנו"]], "3 lines");
  eq([await page.getAttribute("#rqSegKnown", "aria-pressed"), await page.getAttribute("#rqSegUnd", "aria-pressed"), await page.isHidden("#rqUndBox"), await page.isVisible("#rqWhere")], ["true", "false", true, true], "default = knows");
  ok((await page.textContent(".rq-privacy")).includes("בקשה שהמייל שלה לא אומת נמחקת אחרי 5 ימים") && !(await page.textContent("#rqApp")).includes("אישור"), "privacy / no approval wording");
  ok(await noHScroll(page), "horizontal scroll");
  eq(await small(page, "#rqSegKnown,#rqSegUnd"), [], "touch targets");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "01_form_known.png"), fullPage: true });
  eq(errors, [], "page errors");
});

await T("P-02 [C1] English: LTR, subtitle + 3 lines + choice in English", async (open) => {
  const { page } = await open({ query: "?lang=en", locale: "en-US" });
  eq(await page.getAttribute("html", "dir"), "ltr", "dir");
  eq(await page.textContent(".rq-sub"), "Set up a shared trip here and get one app for all the travelers.", "subtitle");
  eq(await page.$$eval("#rqWhat > div", (a) => a.length), 3, "3 lines");
  eq([await page.textContent("#rqSegKnown"), await page.textContent("#rqSegUnd")], ["I know where", "✨ Not decided yet"], "choice");
  await page.click("#rqSegUnd");
  eq(await page.$$eval("#rqInts button", (a) => a.map((b) => b.textContent)), ["Nature & views", "Food", "Beaches", "Cities & culture", "Fun for kids", "Adventure"], "interest chips");
  ok(await noHScroll(page), "horizontal scroll");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "02_form_en_undecided.png"), fullPage: true });
});

await T("P-03 [C2] known destination: form → code → ready with destination / month / travelers; button → /invite/#invite=<token>; body = the F21 start body", async (open) => {
  const { page, calls, errors } = await open({ fn: { start: { ok: true, request_id: "r1", sent_at: "x" }, verify: READY(["PT"]) } });
  await fillBase(page);
  await page.fill("#rqWhere", "פורטוגל");
  await page.click("#rqWhereList button[data-code=PT]");
  await page.click("#rqSend");
  await page.waitForSelector("#rqApp[data-screen=code]");
  eq(await page.textContent("#rqVerify"), "אימות והמשך", "verify label");
  ok(!(await page.textContent("#rqApp")).includes("לאישור"), "no approval wording on the code screen");
  await typeCode(page);
  await page.waitForSelector("#rqApp[data-screen=ready]");
  eq(Object.keys(calls[0]).sort(), ["action", "countries", "email", "lang", "month", "name", "note", "travellers", "turnstile_token"], "start body keys (F21)");
  eq(calls[1], { action: "verify", request_id: "r1", code: "123456" }, "verify body");
  eq([await page.textContent("#rqTitle"), await page.textContent("#rqSumWhere"), await page.textContent("#rqSumWhen"), await page.textContent("#rqSumCount")], ["אפשר להתחיל", "🇵🇹 פורטוגל", "פברואר 2027", "2"], "ready");
  eq([await page.textContent("#rqStart"), await page.getAttribute("#rqStart", "href")], ["הקמת הטיול · כ-3 דקות", "../invite/#invite=" + TOKEN], "button");
  eq(await page.evaluate(() => new URL(document.getElementById("rqStart").href).pathname), "/invite/", "resolves to /invite/");
  ok(await page.isVisible("#rqReadyMail"), "mail line shown");
  ok(!(await page.textContent("#rqApp")).includes("הבקשה נשלחה"), "no 'request sent'");
  ok(await noHScroll(page), "horizontal scroll"); eq(await small(page, "#rqStart"), [], "touch");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "03_ready.png"), fullPage: true });
  await page.reload();
  await page.waitForSelector("#rqApp[data-screen=ready]");
  eq(await page.getAttribute("#rqStart", "href"), "../invite/#invite=" + TOKEN, "ready survives a reload of the tab");
  eq(errors, [], "page errors");
});

await T("P-04 [C3] mail_sent false → the 'saved a link in your email' line is hidden", async (open) => {
  const { page } = await open({ fn: { start: { ok: true, request_id: "r1" }, verify: { ...READY(["PT"]), mail_sent: false } } });
  await fillBase(page); await page.fill("#rqWhere", "פורטוגל"); await page.click("#rqWhereList button[data-code=PT]"); await page.click("#rqSend");
  await typeCode(page);
  await page.waitForSelector("#rqApp[data-screen=ready]");
  eq(await page.$("#rqReadyMail"), null, "line hidden");
});

await T("P-05 [C4][C5] undecided: interests required; 3 ideas with reason + tags; refresh twice then disabled ('נשארו 0'); pick → 'המשך עם <country>' → ready", async (open) => {
  const { page, calls, errors } = await open({ fn: {
    start: { ok: true, request_id: "r1" }, verify: { ok: true, request_id: "r1", next: "suggest", token: SESSION, left: 3 },
    suggest: (b, n) => ({ ok: true, request_id: "r1", items: n === 1 ? ITEMS1 : ITEMS2, left: 3 - n }),
    choose: (b) => READY([b.country]) } });
  await fillBase(page);
  await page.click("#rqSegUnd");
  ok(await page.isHidden("#rqWhere") && await page.isHidden("#rqNoteBox") && await page.isVisible("#rqUndBox"), "undecided box");
  await page.click("#rqSend");
  eq(await page.textContent("#rqInterestsErr"), "בחרו לפחות דבר אחד.", "interests required");
  eq(calls.length, 0, "no call");
  await page.click("#rqInts button[data-int=nature]"); await page.click("#rqInts button[data-int=kids]");
  await page.selectOption("#rqFlight", "8");
  await page.fill("#rqPref", "לא חם מדי");
  eq(await small(page, "#rqInts button,#rqFlight,#rqPref"), [], "touch targets");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "05a_form_undecided.png"), fullPage: true });
  await page.click("#rqSend");
  await typeCode(page);
  await page.waitForSelector("#rqSgList");
  const st = calls[0];
  eq([st.where_mode, st.interests, st.max_flight, st.pref_note, st.note, "countries" in st], ["undecided", ["nature", "kids"], "8", "לא חם מדי", null, false], "start body");
  eq(calls[1], { action: "verify", request_id: "r1", code: "123456", undecided: true }, "verify body");
  eq(calls[2], { action: "suggest", request_id: "r1", token: SESSION }, "suggest body");
  eq(await page.textContent("#rqTitle"), "3 יעדים שמתאימים לכם", "title");
  ok((await page.textContent(".rq-sum")).includes("2 מטיילים") && (await page.textContent(".rq-sum")).includes("טבע ונופים, אטרקציות לילדים") && (await page.textContent(".rq-sum")).includes("טיסה עד 8 שעות"), "summary line");
  eq(await page.$$eval("#rqSgList .rq-dest", (a) => a.map((d) => [d.dataset.country, d.querySelector(".nm").textContent, d.querySelectorAll(".rq-facts span").length])), [["GE", "גאורגיה", 3], ["PT", "פורטוגל", 1], ["ME", "מונטנגרו", 0]], "cards");
  eq([await page.textContent("#rqSgMore"), await page.isDisabled("#rqSgGo")], ["↻ 3 הצעות אחרות · נשארו 2", true], "refresh label, continue disabled");
  ok(await noHScroll(page), "horizontal scroll"); eq(await small(page, "#rqSgList button,#rqSgMore,#rqSgGo"), [], "touch targets");
  await page.click("button[data-pick=GE]");
  eq([await page.getAttribute("button[data-pick=GE]", "aria-pressed"), await page.textContent("button[data-pick=GE]"), await page.textContent("#rqSgGo")], ["true", "✓ נבחר", "המשך עם גאורגיה"], "picked");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "05b_suggest.png"), fullPage: true });
  await page.click("#rqSgMore");
  await page.waitForSelector(".rq-dest[data-country=GR]");
  eq(await page.textContent("#rqSgMore"), "↻ 3 הצעות אחרות · נשארו 1", "1 left");
  await page.click("#rqSgMore");
  await page.waitForFunction(() => document.getElementById("rqSgMore").textContent.includes("נשארו 0"));
  eq([await page.isDisabled("#rqSgMore"), calls.filter((c) => c.action === "suggest").length], [true, 3], "disabled at 0, 3 calls");
  await page.click("button[data-pick=CY]");
  await page.click("#rqSgGo");
  await page.waitForSelector("#rqApp[data-screen=ready]");
  eq(calls[calls.length - 1], { action: "choose", request_id: "r1", token: SESSION, country: "CY" }, "choose body");
  eq(await page.textContent("#rqSumWhere"), "🇨🇾 קפריסין", "ready with the pick");
  eq(errors, [], "page errors");
});

await T("P-06 [C6] fallback: 'אי אפשר להציע יעדים כרגע' + the regular country picker; the flow completes", async (open) => {
  const { page, calls } = await open({ fn: { start: { ok: true, request_id: "r1" }, verify: { ok: true, request_id: "r1", next: "suggest", token: SESSION, left: 3 },
    suggest: { ok: true, request_id: "r1", fallback: true, items: [], left: 0 }, choose: (b) => READY([b.country]) } });
  await fillBase(page); await page.click("#rqSegUnd"); await page.click("#rqInts button[data-int=food]"); await page.click("#rqSend");
  await typeCode(page);
  await page.waitForSelector("#rqSgFallback");
  eq([await page.textContent("#rqTitle"), await page.isDisabled("#rqSgGo")], ["אי אפשר להציע יעדים כרגע", true], "fallback");
  await page.fill("#rqPick", "יפן");
  await page.click("#rqPickList button[data-code=JP]");
  eq(await page.textContent("#rqSgGo"), "המשך עם יפן", "continue label");
  ok(await noHScroll(page), "horizontal scroll");
  if (SHOTS) await page.screenshot({ path: join(SHOTS, "06_fallback.png"), fullPage: true });
  await page.click("#rqSgGo");
  await page.waitForSelector("#rqApp[data-screen=ready]");
  eq(calls[calls.length - 1].country, "JP", "choose JP");
});

await T("P-07 [C8][C9] session gone → back to the form with a message; second auto-approval → the 'try tomorrow' toast, still on the code screen", async (open) => {
  let h = await open({ fn: { start: { ok: true, request_id: "r1" }, verify: { ok: true, request_id: "r1", next: "suggest", token: SESSION, left: 3 }, suggest: { ok: false, code: "request_unknown" } } });
  await fillBase(h.page); await h.page.click("#rqSegUnd"); await h.page.click("#rqInts button[data-int=food]"); await h.page.click("#rqSend");
  await typeCode(h.page);
  await h.page.waitForSelector("#rqApp[data-screen=form]");
  eq([await h.page.textContent("#rqToast"), await h.page.inputValue("#rqEmail")], ["עבר יותר מדי זמן. מתחילים מחדש.", "roy@example.com"], "restart");
  await h.ctx.close();
  h = await open({ fn: { start: { ok: true, request_id: "r1" }, verify: { ok: false, code: "rate_limited" } } });
  await fillBase(h.page); await h.page.fill("#rqWhere", "פורטוגל"); await h.page.click("#rqWhereList button[data-code=PT]"); await h.page.click("#rqSend");
  await typeCode(h.page);
  await h.page.waitForFunction(() => !document.getElementById("rqToast").hidden);
  eq([await h.page.textContent("#rqToast"), await h.page.getAttribute("#rqApp", "data-screen")], ["יותר מדי בקשות היום. נסו שוב מחר.", "code"], "try tomorrow");
  await h.ctx.close();
});

await T("P-08 [C11] flags: SUGGEST_FEATURE off → no choice; REQUEST_MODE manual → the F21 hero / privacy / code texts and the 'request sent' screen", async (open) => {
  let h = await open({ flags: { SUGGEST_FEATURE: "off" } });
  eq([await h.page.$("#rqSegUnd"), await h.page.$("#rqUndBox"), await h.page.isVisible("#rqWhere"), await h.page.isVisible("#rqNote"), await h.page.$$eval("#rqWhat > div", (a) => a.length)], [null, null, true, true, 3], "no choice, auto hero stays");
  await h.ctx.close();
  h = await open({ flags: { REQUEST_MODE: "manual", SUGGEST_FEATURE: "off" }, fn: { start: { ok: true, request_id: "r1" }, verify: { ok: true, request_id: "r1" } } });
  eq([await h.page.textContent(".rq-sub"), await h.page.$("#rqWhat"), await h.page.$("#rqSegUnd")], ["ספרו לנו לאן ומתי. אחרי אישור יגיע אליכם מייל עם קישור להקמת הטיול.", null, null], "F21 hero");
  ok((await h.page.textContent(".rq-privacy")).includes("בקשה שנדחתה"), "F21 privacy");
  await fillBase(h.page); await h.page.fill("#rqWhere", "פורטוגל"); await h.page.click("#rqWhereList button[data-code=PT]"); await h.page.click("#rqSend");
  await h.page.waitForSelector("#rqApp[data-screen=code]");
  eq(await h.page.textContent("#rqVerify"), "אימות ושליחת הבקשה", "F21 verify label");
  await typeCode(h.page);
  await h.page.waitForSelector("#rqApp[data-screen=sent]");
  eq(await h.page.textContent("#rqTitle"), "הבקשה נשלחה", "F21 sent screen");
  await h.ctx.close();
});

await browser.close();
server.close();
console.log("# tests/f23/request_page_test.mjs\n" + results.join("\n") + `\n${pass}/${pass + fail} pass`);
process.exit(fail ? 1 : 0);
