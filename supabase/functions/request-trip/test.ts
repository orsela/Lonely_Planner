// Lonely Planner · request-trip unit tests · version 3.0.0-alpha.8.0 · F21
// CHANGE 2026-10-27 F21-FN-03: new file (no previous version). Deno-style tests for docs/F21_spec.md §3.1 / §1.10 / §4
//   (function side) with stubbed RPCs (a small in-memory fake with the database's semantics), SMTP and Turnstile siteverify.
//   No network, no database.
//
// Run offline (no Deno binary):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        supabase/functions/request-trip/test.ts
// With Deno: deno test --allow-env --no-check --import-map=supabase/functions/request-trip/test_import_map.json supabase/functions/request-trip/test.ts

import { codeHash, FN_VERSION, handler, jerusalemMonth, makeCode, renderCodeEmail, resetDeps, setDeps, SITEVERIFY_URL } from "./index.ts";
import { sha256Hex, type MailMessage } from "../invite-manager/index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}

const NOW = Date.parse("2026-10-27T09:00:00Z");
const M0 = jerusalemMonth(NOW, 0), M2 = jerusalemMonth(NOW, 2), M17 = jerusalemMonth(NOW, 17), M18 = jerusalemMonth(NOW, 18), MP = jerusalemMonth(NOW, -1);
const IP = "203.0.113.7";
const ORIGIN = "https://orsela.github.io";
const FORM = {
  lang: "he", name: "  דנה כהן ", email: "  Dana@Example.COM ", countries: ["pt", "ES"], month: M2, travellers: 4,
  note: "  נשמח לעזרה  ", turnstile_token: "tok-ok",
};

type Row = { email: string; lang: string; code_hash: string; attempts: number; status: string };
class FakeDb {
  rows = new Map<string, Row>();
  mails = 0;
  next: Record<string, unknown> | null = null; // a forced answer for the next rpc
  calls: { name: string; args: Record<string, unknown> }[] = [];
  rpc(name: string, args: Record<string, unknown>) {
    this.calls.push({ name, args });
    if (this.next) { const n = this.next; this.next = null; return n; }
    const id = String(args.p_request);
    const row = this.rows.get(id);
    switch (name) {
      case "request_start": {
        const p = args.p_payload as Record<string, unknown>;
        this.rows.set(id, { email: String(p.email), lang: String(p.lang), code_hash: String(args.p_code_hash), attempts: 0, status: "unverified" });
        this.mails++;
        return { request_id: id, sent_at: "2026-10-27T09:00:00+00:00" };
      }
      case "request_verify": {
        if (!row || row.status !== "unverified") return { error: "request_unknown" };
        if (row.code_hash === args.p_code_hash) { row.status = "pending"; return { status: "pending", request_id: id }; }
        row.attempts++;
        if (row.attempts >= 5) { this.rows.delete(id); return { error: "code_locked" }; }
        return { error: "code_wrong", attempts_left: 5 - row.attempts };
      }
      case "request_resend": {
        if (!row || row.status !== "unverified") return { error: "request_unknown" };
        row.code_hash = String(args.p_code_hash);
        row.attempts = 0;
        this.mails++;
        return { request_id: id, sent_at: "2026-10-27T09:01:30+00:00", email: row.email, lang: row.lang };
      }
      case "request_mail_failed": {
        this.mails--;
        if (args.p_action === "start") this.rows.delete(id);
        return { ok: true };
      }
    }
    return { error: "invalid_request" };
  }
}

function setup(opts: { failMail?: boolean; siteverify?: unknown; env?: Record<string, string>; fetchThrows?: boolean } = {}) {
  resetDeps();
  const db = new FakeDb();
  const sent: MailMessage[] = [];
  const verifies: { url: string; body: string }[] = [];
  const ctl = { failMail: !!opts.failMail };
  const env: Record<string, string> = { TURNSTILE_SECRET: "sec-123", ...(opts.env || {}) };
  let n = 0;
  setDeps({
    rpc: (name, args) => Promise.resolve({ data: db.rpc(name, args), error: null }),
    sendMail: (m) => ctl.failMail ? Promise.reject(new Error(`SMTP 550 mailbox ${m.to} rejected ${m.subject}`)) : (sent.push(m), Promise.resolve()),
    fetch: (url, init) => {
      if (opts.fetchThrows) return Promise.reject(new Error("offline"));
      verifies.push({ url, body: String(init.body) });
      return Promise.resolve(new Response(JSON.stringify(opts.siteverify ?? { success: true, hostname: "orsela.github.io" })));
    },
    now: () => NOW,
    random: (k) => { const a = new Uint8Array(k); for (let i = 0; i < k; i++) a[i] = (n * 37 + i * 11 + 5) & 255; n++; return a; },
    uuid: () => `0f210000-0000-4000-8000-${String(++n).padStart(12, "0")}`,
    env: (k) => env[k],
  });
  async function call(body: unknown, headers: Record<string, string> = {}, method = "POST") {
    const h: Record<string, string> = { "content-type": "application/json", origin: ORIGIN, "x-forwarded-for": `${IP}, 10.0.0.1`, ...headers };
    const res = await handler(new Request("https://x.supabase.co/functions/v1/request-trip", { method, headers: h, body: method === "POST" ? JSON.stringify(body) : undefined }));
    let j: Record<string, unknown> = {};
    try { j = await res.json(); } catch { /* 204 */ }
    return { status: res.status, j, res };
  }
  const codeOf = (m: MailMessage) => /^(\d{6}) – /.exec(m.subject)![1];
  return { db, sent, verifies, ctl, call, codeOf };
}

function captureLogs<T>(fn: () => Promise<T>): Promise<{ out: T; lines: string[] }> {
  const lines: string[] = [];
  const orig = console.log;
  console.log = (...a: unknown[]) => lines.push(a.join(" "));
  return fn().then((out) => ({ out, lines }), (e) => { throw e; }).finally(() => { console.log = orig; });
}

// ---------------------------------------------------------------------------------------------------
Deno.test("version, CORS, method, unknown action, version header", async () => {
  eq(FN_VERSION, "3.0.0-alpha.8.0");
  const s = setup();
  const pre = await handler(new Request("https://x/f", { method: "OPTIONS", headers: { origin: "http://localhost:5173" } }));
  eq([pre.status, pre.headers.get("access-control-allow-origin")], [204, "http://localhost:5173"]);
  const bad = await handler(new Request("https://x/f", { method: "OPTIONS", headers: { origin: "https://evil.example" } }));
  eq(bad.headers.get("access-control-allow-origin"), null);
  const g = await s.call(null, {}, "GET");
  eq([g.status, g.j.code], [405, "method_not_allowed"]);
  const u = await s.call({ action: "drop" });
  eq([u.status, u.j], [400, { ok: false, code: "invalid_request", error: "invalid_request", field: "action" }]);
  eq(u.res.headers.get("x-function-version"), FN_VERSION);
  eq(u.res.headers.get("access-control-allow-origin"), ORIGIN);
});

Deno.test("start: Turnstile with secret + token + first X-Forwarded-For; rpc args (hashes, normalized payload); Hebrew code email", async () => {
  const s = setup();
  const r = await s.call({ action: "start", ...FORM });
  eq(r.status, 200);
  eq(Object.keys(r.j).sort(), ["ok", "request_id", "sent_at"]);
  eq(r.j.ok, true);
  eq(s.verifies.length, 1);
  eq(s.verifies[0].url, SITEVERIFY_URL);
  const form = new URLSearchParams(s.verifies[0].body);
  eq([form.get("secret"), form.get("response"), form.get("remoteip")], ["sec-123", "tok-ok", IP]);
  const c = s.db.calls[0];
  eq(c.name, "request_start");
  eq(c.args.p_request, r.j.request_id);
  eq(c.args.p_payload, { lang: "he", name: "דנה כהן", email: "dana@example.com", countries: ["PT", "ES"], month: M2, travellers: 4, note: "נשמח לעזרה" });
  eq(c.args.p_email_hash, await sha256Hex("dana@example.com"));
  eq(c.args.p_ip, await sha256Hex(IP));
  eq(s.sent.length, 1);
  const m = s.sent[0];
  const code = s.codeOf(m);
  eq(c.args.p_code_hash, await codeHash(String(r.j.request_id), code));
  eq(c.args.p_code_hash, await sha256Hex(String(r.j.request_id) + code));
  eq(m.to, "dana@example.com");
  eq(m.subject, `${code} – קוד האימות לבקשה ב-Lonely Planner`);
  assert(m.html.includes('dir="rtl"') && m.html.includes(`>${code}</div>`) && m.text.includes(code), "code in body");
  assert(m.text.includes("חוזרים לדף הבקשה ומקלידים את הקוד. הוא תקף 10 דקות."), "body line");
  assert(!/https?:\/\/|<a\s/i.test(m.html + m.text), "the code email must have no link");
  assert(!JSON.stringify(r.j).includes(code), "code in the response");
});

Deno.test("start in English → English subject and LTR body", async () => {
  const s = setup();
  const r = await s.call({ action: "start", ...FORM, lang: "en", name: "Tom" });
  eq(r.status, 200);
  const code = s.codeOf(s.sent[0]);
  eq(s.sent[0].subject, `${code} – your Lonely Planner verification code`);
  assert(s.sent[0].html.includes('lang="en" dir="ltr"') && s.sent[0].text.includes("Your verification code:"));
});

Deno.test("start validation (criterion 4): each bound → 400 invalid_request {field}; no Turnstile call, no rpc, no mail", async () => {
  const cases: [string, Record<string, unknown>][] = [
    ["lang", { lang: "fr" }], ["name", { name: "  " }], ["name", { name: "x".repeat(41) }], ["name", { name: 5 }],
    ["email", { email: "nope" }], ["email", { email: "a b@x.com" }], ["countries", { countries: [] }],
    ["countries", { countries: Array.from({ length: 11 }, (_, i) => "A" + String.fromCharCode(65 + i)) }],
    ["countries", { countries: ["PRT"] }], ["countries", { countries: ["PT", "pt"] }], ["countries", { countries: "PT" }],
    ["month", { month: MP }], ["month", { month: M18 }], ["month", { month: "2027-13" }], ["month", { month: 202704 }],
    ["travellers", { travellers: 0 }], ["travellers", { travellers: 31 }], ["travellers", { travellers: 2.5 }], ["travellers", { travellers: "2" }],
    ["note", { note: "n".repeat(201) }], ["note", { note: 7 }],
  ];
  for (const [field, over] of cases) {
    const s = setup();
    const r = await s.call({ action: "start", ...FORM, ...over });
    eq([r.status, r.j.code, r.j.field], [400, "invalid_request", field], JSON.stringify(over));
    eq([s.verifies.length, s.db.calls.length, s.sent.length], [0, 0, 0], JSON.stringify(over));
  }
  for (const over of [{ month: M0 }, { month: M17 }, { month: `${M17}-01` }, { month: null }, { note: null }, { note: "" }, { travellers: 30 }, { name: "x".repeat(40) }]) {
    const s = setup();
    eq((await s.call({ action: "start", ...FORM, ...over })).status, 200, JSON.stringify(over));
  }
});

Deno.test("Turnstile (D2, criterion 5): failure / wrong host / no secret / no token / network error → 403 turnstile_failed, no row, no mail", async () => {
  const variants: Parameters<typeof setup>[0][] = [
    { siteverify: { success: false, "error-codes": ["invalid-input-response"] } },
    { siteverify: { success: true, hostname: "evil.example" } },
    { siteverify: { success: true, hostname: "localhost" } },
    { env: { TURNSTILE_SECRET: "" } },
    { fetchThrows: true },
  ];
  for (const v of variants) {
    const s = setup(v);
    const r = await s.call({ action: "start", ...FORM });
    eq([r.status, r.j.code], [403, "turnstile_failed"], JSON.stringify(v));
    eq([s.db.calls.length, s.sent.length], [0, 0]);
  }
  const s = setup();
  eq((await s.call({ action: "start", ...FORM, turnstile_token: "" })).j.code, "turnstile_failed");
  const l = setup({ siteverify: { success: true, hostname: "localhost" }, env: { TURNSTILE_SECRET: "s", TURNSTILE_ALLOW_LOCALHOST: "1" } });
  eq((await l.call({ action: "start", ...FORM })).status, 200, "localhost allowed with TURNSTILE_ALLOW_LOCALHOST=1");
});

Deno.test("start: database refusals pass through (daily_limit 429, rate_limited 429, invalid_request field); no mail", async () => {
  for (const [ans, status] of [[{ error: "daily_limit" }, 429], [{ error: "rate_limited" }, 429], [{ error: "invalid_request", field: "month" }, 400]] as const) {
    const s = setup();
    s.db.next = ans as Record<string, unknown>;
    const r = await s.call({ action: "start", ...FORM });
    eq(r.status, status);
    eq(r.j, { ok: false, code: ans.error, error: ans.error, ...("field" in ans ? { field: ans.field } : {}) });
    eq(s.sent.length, 0);
  }
  const s = setup();
  s.db.next = { error: "something_new" };
  eq((await s.call({ action: "start", ...FORM })).j, { ok: false, code: "server_error", error: "server_error" });
  setDeps({ rpc: () => Promise.resolve({ data: null, error: { message: "boom" } }) });
  eq((await s.call({ action: "start", ...FORM })).status, 500);
});

Deno.test("start: email failure → request_mail_failed(id,'start'), 502 email_failed, row gone, mail count back", async () => {
  const s = setup({ failMail: true });
  const r = await s.call({ action: "start", ...FORM });
  eq([r.status, r.j], [502, { ok: false, code: "email_failed", error: "email_failed" }]);
  eq(s.db.calls.map((c) => c.name), ["request_start", "request_mail_failed"]);
  eq(s.db.calls[1].args, { p_request: s.db.calls[0].args.p_request, p_action: "start" });
  eq([s.db.rows.size, s.db.mails], [0, 0]);
});

Deno.test("C4: the start answer for a known address equals the one for a new address (status and keys)", async () => {
  const s = setup();
  const a = await s.call({ action: "start", ...FORM, email: "manager@example.com" });
  const b = await s.call({ action: "start", ...FORM, email: "nobody@example.com" });
  eq([a.status, Object.keys(a.j).sort()], [b.status, Object.keys(b.j).sort()]);
});

Deno.test("verify: right code (spaces ignored) → ok; wrong → code_wrong {attempts_left}; 5th → code_locked; then request_unknown", async () => {
  const s = setup();
  const st = await s.call({ action: "start", ...FORM });
  const id = String(st.j.request_id), code = s.codeOf(s.sent[0]);
  const wrong = code === "000000" ? "111111" : "000000";
  for (let k = 4; k >= 1; k--) {
    const r = await s.call({ action: "verify", request_id: id, code: wrong });
    eq([r.status, r.j.code, r.j.attempts_left], [400, "code_wrong", k]);
  }
  const lock = await s.call({ action: "verify", request_id: id, code: wrong });
  eq([lock.status, lock.j.code], [423, "code_locked"]);
  eq((await s.call({ action: "verify", request_id: id, code })).j.code, "request_unknown");
  const s2 = setup();
  const st2 = await s2.call({ action: "start", ...FORM });
  const c2 = s2.codeOf(s2.sent[0]);
  const ok = await s2.call({ action: "verify", request_id: String(st2.j.request_id).toUpperCase(), code: ` ${c2.slice(0, 3)} ${c2.slice(3)} ` });
  eq([ok.status, ok.j], [200, { ok: true, request_id: st2.j.request_id }]);
  eq(s2.db.calls[1].args.p_ip, await sha256Hex(IP));
  eq(s2.db.calls[1].args.p_code_hash, await sha256Hex(String(st2.j.request_id) + c2));
});

Deno.test("verify: bad input → invalid_request {field}; database codes code_expired 410 / rate_limited 429 / request_unknown 404", async () => {
  const s = setup();
  eq((await s.call({ action: "verify", request_id: "x", code: "123456" })).j.field, "request_id");
  eq((await s.call({ action: "verify", request_id: "0f210000-0000-4000-8000-000000000001", code: "12345" })).j.field, "code");
  eq((await s.call({ action: "verify", request_id: "0f210000-0000-4000-8000-000000000001", code: "12a456" })).j.field, "code");
  eq(s.db.calls.length, 0);
  for (const [code, status] of [["code_expired", 410], ["rate_limited", 429], ["request_unknown", 404]] as const) {
    s.db.next = { error: code };
    const r = await s.call({ action: "verify", request_id: "0f210000-0000-4000-8000-000000000001", code: "123456" });
    eq([r.status, r.j.code], [status, code]);
  }
});

Deno.test("resend: new code to the stored address in the request's language; previous code stops working; no Turnstile", async () => {
  const s = setup();
  const st = await s.call({ action: "start", ...FORM, lang: "en" });
  const id = String(st.j.request_id), c1 = s.codeOf(s.sent[0]);
  const r = await s.call({ action: "resend", request_id: id });
  eq([r.status, r.j], [200, { ok: true, request_id: id, sent_at: "2026-10-27T09:01:30+00:00" }]);
  eq(s.verifies.length, 1, "resend must not call Turnstile");
  eq(s.sent.length, 2);
  const c2 = s.codeOf(s.sent[1]);
  eq(s.sent[1].to, "dana@example.com");
  assert(s.sent[1].subject.endsWith("your Lonely Planner verification code"));
  eq(s.db.calls[1].args, { p_request: id, p_code_hash: await codeHash(id, c2) });
  if (c1 !== c2) eq((await s.call({ action: "verify", request_id: id, code: c1 })).j.code, "code_wrong");
  eq((await s.call({ action: "verify", request_id: id, code: c2 })).j.ok, true);
});

Deno.test("resend: daily_limit / rate_limited {retry_in} pass through, no mail; email failure → request_mail_failed(id,'resend') + 502", async () => {
  const s = setup();
  const st = await s.call({ action: "start", ...FORM });
  const id = String(st.j.request_id);
  s.db.next = { error: "daily_limit" };
  eq((await s.call({ action: "resend", request_id: id })).j, { ok: false, code: "daily_limit", error: "daily_limit" });
  s.db.next = { error: "rate_limited", retry_in: 42 };
  eq((await s.call({ action: "resend", request_id: id })).j, { ok: false, code: "rate_limited", error: "rate_limited", retry_in: 42 });
  eq(s.sent.length, 1);
  s.ctl.failMail = true;
  const f = await s.call({ action: "resend", request_id: id });
  eq([f.status, f.j.code], [502, "email_failed"]);
  const last = s.db.calls[s.db.calls.length - 1];
  eq(last, { name: "request_mail_failed", args: { p_request: id, p_action: "resend" } });
  eq((await s.call({ action: "resend", request_id: "nope" })).j.field, "request_id");
});

Deno.test("logs: one line per request with action/status/code only — never email, name, note, code, token or address", async () => {
  const { lines } = await captureLogs(async () => {
    const s = setup();
    const st = await s.call({ action: "start", ...FORM });
    const code = s.codeOf(s.sent[0]);
    await s.call({ action: "verify", request_id: st.j.request_id, code: code === "000000" ? "111111" : "000000" });
    await s.call({ action: "verify", request_id: st.j.request_id, code });
    s.ctl.failMail = true;
    await s.call({ action: "start", ...FORM });  // SMTP error message carries the address and the subject (with the code)
    (globalThis as Record<string, unknown>).__code = code;
    return null;
  });
  const all = lines.join("\n");
  assert(lines.length >= 4, "expected log lines");
  for (const x of ["dana@", "Dana@", "דנה", "נשמח", "tok-ok", IP, "sec-123", String((globalThis as Record<string, unknown>).__code)]) {
    assert(!all.includes(x), "log leaked " + x);
  }
  assert(!/\b\d{6}\b/.test(all), "a 6-digit number in the logs");
  for (const l of lines) {
    const o = JSON.parse(l);
    eq(o.fn, "request-trip");
    for (const k of Object.keys(o)) assert(["fn", "v", "action", "status", "code", "event", "name", "message"].includes(k), "log key " + k);
  }
});

Deno.test("helpers: makeCode always 6 digits and rejects the biased top range; renderCodeEmail subjects", () => {
  let k = 0;
  const seq = [[255, 255, 255, 255], [0, 0, 0, 7]];
  eq(makeCode(() => Uint8Array.from(seq[k++])), "000007", "rejection sampling skips 0xFFFFFFFF");
  for (let i = 0; i < 200; i++) assert(/^\d{6}$/.test(makeCode((n) => crypto.getRandomValues(new Uint8Array(n)))));
  eq(renderCodeEmail({ to: "a@b.co", code: "729015", lang: "he" }).subject, "729015 – קוד האימות לבקשה ב-Lonely Planner");
  eq(renderCodeEmail({ to: "a@b.co", code: "729015", lang: "en" }).subject, "729015 – your Lonely Planner verification code");
  eq(renderCodeEmail({ to: "a@b.co", code: "729015", lang: "xx" }).subject, "729015 – קוד האימות לבקשה ב-Lonely Planner");
  resetDeps();
});
