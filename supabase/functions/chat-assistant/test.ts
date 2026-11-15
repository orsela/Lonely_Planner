// Lonely Planner · chat-assistant unit tests · version 3.0.0-alpha.15.1 · F14
// CHANGE 2026-11-15 F14-FN-03: new file (no previous version). Deno-style tests for docs/F14_dev_notes.md / spec C1–C11 with
//   stubbed deps (auth, rpc chat_take / chat_refund, Anthropic fetch). No network, no database.
// Run offline (no Deno binary):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        supabase/functions/chat-assistant/test.ts
import {
  buildMessages, buildSystemPrompt, buildUserContent, corsHeaders, dailyCap, FN_VERSION, handler, isIsoDate, provider, resetDeps, setDeps,
  statusFor, TOOLS, validateAction,
} from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}

const TRIP = "11111111-2222-4333-8444-555555555555";
const USER = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const ORIGIN = "https://orsela.github.io";
const NOW = Date.parse("2026-11-15T10:00:00Z");

type Rec = { rpc: { name: string; args: Record<string, unknown> }[]; fetch: any[]; users: string[]; logs: string[] };
let rec: Rec;
let env: Record<string, string>;
let takeAnswer: Record<string, unknown>;
let upstream: () => Promise<Response>;
let clock: number;
const realLog = console.log;

function reply(content: unknown[], extra: Record<string, unknown> = {}) {
  return () => Promise.resolve(new Response(JSON.stringify({ content, stop_reason: "end_turn", usage: { input_tokens: 120, output_tokens: 30 }, ...extra }), { status: 200 }));
}
function setup() {
  rec = { rpc: [], fetch: [], users: [], logs: [] };
  env = { ANTHROPIC_API_KEY: "sk-test" };
  takeAnswer = { ok: true, used: 1, cap: 100 };
  upstream = reply([{ type: "text", text: "תשובה" }]);
  clock = NOW;
  resetDeps();
  console.log = (...a: unknown[]) => { rec.logs.push(a.map(String).join(" ")); };
  setDeps({
    getUser: (jwt: string) => { rec.users.push(jwt); return Promise.resolve(jwt === "good" ? { id: USER } : null); },
    rpc: (name: string, args: Record<string, unknown>) => {
      rec.rpc.push({ name, args });
      if (name === "chat_take") return Promise.resolve({ data: takeAnswer, error: null });
      return Promise.resolve({ data: { ok: true, used: 0 }, error: null });
    },
    fetch: (url: string, init: RequestInit) => { rec.fetch.push({ url, init, body: JSON.parse(String(init.body)) }); return upstream(); },
    now: () => clock,
    env: (k: string) => env[k],
  });
}
function done() {
  console.log = realLog;
  resetDeps();
}
function post(body: unknown, headers: Record<string, string> = {}, raw?: string): Request {
  return new Request("https://x.supabase.co/functions/v1/chat-assistant", {
    method: "POST",
    headers: { "content-type": "application/json", origin: ORIGIN, authorization: "Bearer good", ...headers },
    body: raw ?? JSON.stringify(body),
  });
}
const BASE = { trip_id: TRIP, question: "כמה הוצאנו?", lang: "he" };
async function run(body: unknown, headers: Record<string, string> = {}, raw?: string) {
  const r = await handler(post(body, headers, raw));
  return { status: r.status, body: await r.json(), headers: r.headers };
}
const takes = () => rec.rpc.filter((c) => c.name === "chat_take").length;
const refunds = () => rec.rpc.filter((c) => c.name === "chat_refund").length;

function test(name: string, fn: () => Promise<void> | void) {
  Deno.test(name, async () => {
    setup();
    try { await fn(); } finally { done(); }
  });
}

// ---------------------------------------------------------------- pure helpers
test("statusFor maps every code", () => {
  eq([statusFor("unauthorized"), statusFor("not_member"), statusFor("daily_cap"), statusFor("chat_off"), statusFor("too_large"), statusFor("upstream_timeout"), statusFor("nope")], [401, 403, 429, 503, 413, 504, 500]);
});
test("isIsoDate accepts real dates only", () => {
  assert(isIsoDate("2026-05-17"));
  assert(!isIsoDate("2026-02-30") && !isIsoDate("17/5") && !isIsoDate("2026-5-17") && !isIsoDate(20260517) && !isIsoDate(""));
});
test("validateAction: flight with from, hotel with nights, drops the incomplete (AC5/AC6)", () => {
  const f = validateAction({ name: "search_links", input: { kind: "flight", from: " Batumi ", to: "TLV", date: "2027-05-17" } });
  eq(f.params, { kind: "flight", to: "TLV", date: "2027-05-17", from: "Batumi" });
  eq(f.type, "search_links");
  const h = validateAction({ name: "search_links", input: { kind: "hotel", to: "Tbilisi", date: "2026-12-01", nights: 3, from: "X" } });
  eq(h.params, { kind: "hotel", to: "Tbilisi", date: "2026-12-01", nights: 3 });
  const rt = validateAction({ name: "search_links", input: { kind: "flight", to: "ATH", date: "2026-12-01", return_date: "2026-12-08" } });
  eq(rt.params.return_date, "2026-12-08");
  const back = validateAction({ name: "search_links", input: { kind: "flight", to: "ATH", date: "2026-12-08", return_date: "2026-12-01" } });
  assert(back.params.return_date === undefined, "return before departure is dropped");
  for (const bad of [{ kind: "hotel", to: "Tbilisi" }, { kind: "hotel", date: "2026-12-01" }, { kind: "train", to: "A", date: "2026-12-01" }, { kind: "hotel", to: "A", date: "1/12" }, { kind: "hotel", to: "  ", date: "2026-12-01" }]) {
    assert(validateAction({ name: "search_links", input: bad }) === null, JSON.stringify(bad));
  }
  assert(validateAction({ name: "add_expense", input: { description: "x", amount: 5, category: "food" } }) === null, "old tools are gone");
  assert(validateAction(null) === null);
});
test("validateAction caps long strings and strips control characters", () => {
  const a = validateAction({ name: "search_links", input: { kind: "hotel", to: "A\u0000B".padEnd(300, "x"), date: "2026-12-01" } });
  assert(a.params.to.length <= 80 && !a.params.to.includes("\u0000"));
});
test("TOOLS = search_links only (D2, AC7)", () => {
  eq(TOOLS.map((t) => t.name), ["search_links"]);
});
test("system prompt is trip-generic (C6)", () => {
  const he = buildSystemPrompt("he", "2026-11-15", { start: "2026-12-01", end: "2026-12-10" });
  const en = buildSystemPrompt("en", "2026-11-15", null);
  assert(!/vietnam|ויטנאם|וייטנאם|VND|Hoi An/i.test(he + en), "no fixed country in the prompt");
  assert(he.includes("Hebrew") && he.includes("2026-11-15") && he.includes("2026-12-01 to 2026-12-10"));
  assert(en.includes("English") && !en.includes("The trip runs"));
  assert(he.includes("Tel Aviv (TLV)") && he.includes("homeCity"), "home resolves to TLV for ILS trips");
  assert(provider("anything") === "claude");
});
test("buildMessages: empty entries, trailing duplicate, user first, alternating roles (v2.2.0 CHAT-FIX)", () => {
  const h = [
    { role: "assistant", text: "היי" }, { role: "user", text: "   " }, { role: "user", text: "שאלה 1" },
    { role: "assistant", text: "תשובה 1" }, { role: "user", text: "שאלה 2" },
  ];
  const m = buildMessages(h, "שאלה 2", "CUR");
  eq(m.map((x: any) => x.role), ["user", "assistant", "user"]);
  eq(m[2].content, "CUR");
  eq(m[0].content, "שאלה 1");
  const merged = buildMessages([{ role: "user", text: "a" }, { role: "user", text: "b" }], "q", "CUR");
  eq(merged.length, 1);
  eq(merged[0].content, "a\n\nb\n\nCUR");
  const withImg = buildMessages([{ role: "user", text: "a" }], "", [{ type: "text", text: "t" }]);
  eq(withImg.length, 1);
  eq(withImg[0].content.length, 2);
  eq(buildMessages(undefined, "q", "CUR").length, 1);
  assert(buildMessages(new Array(20).fill(0).map((_, i) => ({ role: i % 2 ? "assistant" : "user", text: "t" + i })), "q", "C").length <= 9);
});
test("buildUserContent: includes sections, question last, no truncation when small", () => {
  const r = buildUserContent({ tripInfo: { name: "ג'ורג'יה", countries: ["GE"] }, expenses: [{ a: 1 }], question: " שלום " });
  assert(!r.trimmed && r.text.includes("ג'ורג'יה") && r.text.endsWith("User's question:\n\nשלום"));
  assert(!r.text.includes("Journal entries"), "empty sections are left out");
});
test("buildUserContent: over 60,000 characters drops the OLDEST journal first and tells the model (R2)", () => {
  const journal = new Array(400).fill(0).map((_, i) => ({ day: i, entries: [{ who: "w", text: "טקסט ".repeat(60) + "#" + i }] }));
  const r = buildUserContent({ tripInfo: { name: "T" }, expenses: [{ a: 1 }], journal, question: "q" });
  assert(r.trimmed && r.text.includes("NOTE: the data was too long"));
  assert(r.text.length < 60_000 + 1500, "context + note stay near the cap, got " + r.text.length);
  assert(r.text.includes("#399") && !r.text.includes("#0\""), "newest kept, oldest dropped");
  assert(r.text.includes("\"a\":1"), "expenses untouched while the journal could absorb the cut");
});
test("buildUserContent: expenses then documents shrink when the journal alone is not enough", () => {
  const big = (n: number, p: string) => new Array(n).fill(0).map((_, i) => ({ t: p + i + "x".repeat(300) }));
  const r = buildUserContent({ journal: big(10, "J"), expenses: big(250, "E"), documents: big(5, "D"), question: "q" });
  assert(r.trimmed);
  assert(r.text.length <= 60_000 + 1500);
  assert(r.text.includes("E249") && !r.text.includes("\"E0x"), "oldest expenses dropped");
});
test("corsHeaders: page origin and localhost only", () => {
  assert(corsHeaders(ORIGIN)["Access-Control-Allow-Origin"] === ORIGIN);
  assert(corsHeaders("http://localhost:8080")["Access-Control-Allow-Origin"] === "http://localhost:8080");
  assert(!corsHeaders("https://evil.example")["Access-Control-Allow-Origin"]);
});
test("dailyCap: default 100, secret overrides, garbage ignored", () => {
  eq(dailyCap(), 100);
  env.CHAT_DAILY_CAP = "25"; eq(dailyCap(), 25);
  env.CHAT_DAILY_CAP = "abc"; eq(dailyCap(), 100);
  env.CHAT_DAILY_CAP = "0"; eq(dailyCap(), 100);
});

// ---------------------------------------------------------------- handler: refusals (no call to Claude)
test("OPTIONS → 204 with CORS; GET → 405", async () => {
  const o = await handler(new Request("https://x/f", { method: "OPTIONS", headers: { origin: ORIGIN } }));
  assert(o.status === 204 && o.headers.get("Access-Control-Allow-Origin") === ORIGIN);
  const g = await handler(new Request("https://x/f", { method: "GET", headers: { origin: ORIGIN } }));
  eq(g.status, 405);
});
test("401: no bearer, anon-style bad token — no rpc, no fetch (AC2)", async () => {
  let r = await run(BASE, { authorization: "" });
  eq([r.status, r.body.error], [401, "unauthorized"]);
  r = await run(BASE, { authorization: "Bearer anon-key" });
  eq([r.status, r.body.error], [401, "unauthorized"]);
  eq([rec.rpc.length, rec.fetch.length], [0, 0]);
});
test("403 not_member — nothing sent to Claude, nothing to refund (AC2)", async () => {
  takeAnswer = { error: "not_member" };
  const r = await run(BASE);
  eq([r.status, r.body.error], [403, "not_member"]);
  eq([rec.fetch.length, refunds()], [0, 0]);
});
test("429 daily_cap carries used + cap, no Claude call, no refund (AC3)", async () => {
  takeAnswer = { error: "daily_cap", used: 100, cap: 100 };
  const r = await run(BASE);
  eq([r.status, r.body.error, r.body.used, r.body.cap], [429, "daily_cap", 100, 100]);
  eq([rec.fetch.length, refunds()], [0, 0]);
});
test("503 chat_off when CHAT_FEATURE=off — before anything else (AC4)", async () => {
  env.CHAT_FEATURE = "off";
  const r = await run(BASE);
  eq([r.status, r.body.error], [503, "chat_off"]);
  eq([rec.users.length, rec.rpc.length, rec.fetch.length], [0, 0, 0]);
});
test("400 invalid requests: bad JSON, array, trip_id, empty question, bad image", async () => {
  const cases: [unknown, string, string?][] = [
    [null, "body", "{nope"], [[], "body"], [{ question: "x" }, "trip_id"], [{ trip_id: "abc", question: "x" }, "trip_id"],
    [{ trip_id: TRIP, question: "   " }, "question"], [{ trip_id: TRIP, question: "x", image: { mime: "image/svg+xml", data: "AAAA" } }, "image"],
    [{ trip_id: TRIP, question: "x", image: { mime: "image/png", data: "" } }, "image"], [{ trip_id: TRIP, question: "x", image: { mime: "image/png", data: "<script>" } }, "image"],
  ];
  for (const [b, field, raw] of cases) {
    const r = await run(b, {}, raw);
    eq([r.status, r.body.error, r.body.field], [400, "invalid_request", field], JSON.stringify(b));
  }
  eq([takes(), rec.fetch.length], [0, 0]);
});
test("413 too_large by body size (and by content-length)", async () => {
  const r = await run(null, {}, JSON.stringify({ ...BASE, journal: "x".repeat(6_100_000) }));
  eq([r.status, r.body.error], [413, "too_large"]);
  const r2 = await run(BASE, { "content-length": "7000000" });
  eq(r2.status, 413);
  eq([takes(), rec.fetch.length], [0, 0]);
});
test("500 when the API key is missing — the cap is not touched", async () => {
  delete env.ANTHROPIC_API_KEY;
  const r = await run(BASE);
  eq([r.status, r.body.error], [500, "server_error"]);
  eq([takes(), rec.fetch.length], [0, 0]);
});
test("500 when chat_take itself fails — no Claude call", async () => {
  setDeps({ rpc: () => Promise.resolve({ data: null, error: { message: "boom" } }) });
  const r = await run(BASE);
  eq([r.status, r.body.error, rec.fetch.length], [500, "server_error", 0]);
});
test("burst limit: the 16th question within a minute → 429 rate_limited, no further take", async () => {
  for (let i = 0; i < 15; i++) eq((await run(BASE)).status, 200, "q" + i);
  const r = await run(BASE);
  eq([r.status, r.body.error], [429, "rate_limited"]);
  eq(takes(), 15);
  clock += 61_000;
  eq((await run(BASE)).status, 200, "a minute later it works again");
});

// ---------------------------------------------------------------- handler: success paths
test("200 plain answer: request to Claude has search_links only, generic prompt, default model, cap passed (AC1, AC7)", async () => {
  env.CHAT_DAILY_CAP = "40";
  const r = await run({ ...BASE, tripInfo: { name: "Georgia 26", countries: ["GE"], today: "2026-11-15" }, expenses: [{ d: "2026-11-01", amount: 5 }] });
  eq([r.status, r.body.answer, r.body.action, r.body.version], [200, "תשובה", null, FN_VERSION]);
  eq(r.headers.get("X-Function-Version"), FN_VERSION);
  const c = rec.fetch[0];
  eq(c.url, "https://api.anthropic.com/v1/messages");
  eq([c.body.model, c.body.max_tokens, c.body.tools.map((t: any) => t.name)], ["claude-haiku-5-5", 4000, ["search_links"]]);
  eq(c.init.headers["x-api-key"], "sk-test");
  assert(!/vietnam|ויטנאם|וייטנאם/i.test(JSON.stringify(c.body)), "no fixed country anywhere in the request");
  assert(c.body.messages[0].content.includes("Georgia 26") && c.body.system.includes("Today's date is 2026-11-15"));
  eq(rec.rpc[0], { name: "chat_take", args: { p_user: USER, p_trip: TRIP, p_cap: 40 } });
  eq(refunds(), 0);
});
test("CHAT_MODEL overrides the model without a deploy", async () => {
  env.CHAT_MODEL = "claude-test-model";
  await run(BASE);
  eq(rec.fetch[0].body.model, "claude-test-model");
});
test("flight request → action search_links + a short line when the model wrote no text (AC5)", async () => {
  upstream = reply([{ type: "tool_use", id: "t1", name: "search_links", input: { kind: "flight", from: "Batumi", to: "TLV", date: "2027-05-17" } }], { stop_reason: "tool_use" });
  const r = await run({ ...BASE, question: "תמצא לי טיסה הביתה מבטומי ב-17/5" });
  eq(r.status, 200);
  eq(r.body.answer, "הנה הקישורים 👇");
  eq(r.body.action.type, "search_links");
  eq(r.body.action.params, { kind: "flight", to: "TLV", date: "2027-05-17", from: "Batumi" });
  eq(rec.logs.filter((l) => l.includes("chat_answer")).length, 1);
  assert(rec.logs.some((l) => l.includes("\"tool\":\"search_links\"")));
});
test("model text is kept next to the action; English line for lang=en", async () => {
  upstream = reply([{ type: "text", text: "Sure." }, { type: "tool_use", id: "t", name: "search_links", input: { kind: "hotel", to: "Tbilisi", date: "2026-12-01", nights: 2 } }]);
  let r = await run({ ...BASE, lang: "en" });
  eq([r.body.answer, r.body.action.params.nights, r.body.action.description], ["Sure.", 2, "Hotel search: Tbilisi, 2026-12-01"]);
  upstream = reply([{ type: "tool_use", id: "t", name: "search_links", input: { kind: "hotel", to: "Tbilisi", date: "2026-12-01" } }]);
  r = await run({ ...BASE, lang: "en" });
  eq(r.body.answer, "Here are the links 👇");
});
test("hotel without a date → no card; the chat asks (AC6)", async () => {
  upstream = reply([{ type: "tool_use", id: "t", name: "search_links", input: { kind: "hotel", to: "טביליסי" } }], { stop_reason: "tool_use" });
  const r = await run({ ...BASE, question: "תמצא לי מלון בטביליסי" });
  eq(r.body.action, null);
  assert(r.body.answer.includes("באיזה תאריך"));
  upstream = reply([{ type: "text", text: "לאיזה תאריכים?" }, { type: "tool_use", id: "t", name: "search_links", input: { kind: "hotel", to: "X" } }]);
  eq((await run(BASE)).body.answer, "לאיזה תאריכים?");
});
test("an old tool name from the model is dropped (D2)", async () => {
  upstream = reply([{ type: "tool_use", id: "t", name: "add_expense", input: { description: "x", amount: 5, category: "food" } }], { stop_reason: "tool_use" });
  eq((await run(BASE)).body.action, null);
});
test("max_tokens stop adds the cut-off note", async () => {
  upstream = reply([{ type: "text", text: "ארוך" }], { stop_reason: "max_tokens" });
  assert((await run(BASE)).body.answer.includes("נקטעה"));
});
test("image question: only the current image is sent; image-only question gets the fallback text (AC8)", async () => {
  const hist = [{ role: "user", text: "קודם" }, { role: "assistant", text: "ok" }, { role: "user", text: "" }];
  const r = await run({ trip_id: TRIP, image: { mime: "image/jpeg", data: "QUJD" }, history: hist });
  eq(r.status, 200);
  const msgs = rec.fetch[0].body.messages;
  eq(msgs.map((m: any) => m.role), ["user", "assistant", "user"]);
  const cur = msgs[2].content;
  eq([cur[1].type, cur[1].source.media_type, cur[1].source.data], ["image", "image/jpeg", "QUJD"]);
  assert(cur[0].text.includes("No text was written") && typeof msgs[0].content === "string");
  // a later question after an image-only entry still works (empty text entries never reach Claude)
  const r2 = await run({ ...BASE, history: [{ role: "user", text: "" }, { role: "assistant", text: "תיאור" }, { role: "user", text: BASE.question }] });
  eq(r2.status, 200);
});
test("bookingRef and document names are passed on (F1 closed by Or: send everything)", async () => {
  await run({ ...BASE, currentDay: { day: 3, bookingRef: "ABC123" }, documents: [{ name: "דרכון_דני.pdf" }] });
  const t = rec.fetch[0].body.messages[0].content;
  assert(t.includes("ABC123") && t.includes("דרכון_דני.pdf"));
});

// ---------------------------------------------------------------- handler: upstream failures give the question back (AC3)
test("upstream 500 → 502 upstream_error and one refund", async () => {
  upstream = () => Promise.resolve(new Response("nope", { status: 500 }));
  const r = await run(BASE);
  eq([r.status, r.body.error, r.body.upstreamStatus, takes(), refunds()], [502, "upstream_error", 500, 1, 1]);
  eq(rec.rpc[1], { name: "chat_refund", args: { p_trip: TRIP } });
});
test("upstream timeout (abort) → 504 and one refund", async () => {
  upstream = () => Promise.reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
  const r = await run(BASE);
  eq([r.status, r.body.error, refunds()], [504, "upstream_timeout", 1]);
});
test("network failure → 502 and one refund; invalid JSON from Claude → 502 and one refund", async () => {
  upstream = () => Promise.reject(new TypeError("fetch failed"));
  let r = await run(BASE);
  eq([r.status, r.body.error, refunds()], [502, "upstream_error", 1]);
  upstream = () => Promise.resolve(new Response("<html>", { status: 200 }));
  r = await run(BASE);
  eq([r.status, refunds()], [502, 2]);
});
test("a failing refund never changes the answer", async () => {
  upstream = () => Promise.resolve(new Response("x", { status: 529 }));
  setDeps({ rpc: (name: string) => name === "chat_refund" ? Promise.reject(new Error("db down")) : Promise.resolve({ data: { ok: true, used: 1, cap: 100 }, error: null }) });
  const r = await run(BASE);
  eq([r.status, r.body.error], [502, "upstream_error"]);
  assert(rec.logs.some((l) => l.includes("refund_failed")));
});

// ---------------------------------------------------------------- logs (C10)
test("logs never contain the question, the answer, the context, the JWT or any id (AC11)", async () => {
  upstream = reply([{ type: "text", text: "TOP-SECRET-ANSWER" }]);
  await run({ ...BASE, question: "TOP-SECRET-QUESTION", journal: [{ text: "TOP-SECRET-JOURNAL" }] });
  takeAnswer = { error: "not_member" };
  await run({ ...BASE, question: "TOP-SECRET-QUESTION-2" });
  const all = rec.logs.join("\n");
  assert(!/TOP-SECRET|good|sk-test/.test(all) && !all.includes(USER) && !all.includes(TRIP), all);
  const ans = JSON.parse(rec.logs.find((l) => l.includes("chat_answer"))!);
  eq([ans.ev, ans.in, ans.out, ans.status, ans.fn, ans.v], ["chat_answer", 120, 30, 200, "chat-assistant", FN_VERSION]);
  assert(typeof ans.ms === "number");
});
