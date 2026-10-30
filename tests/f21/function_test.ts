// Lonely Planner F21 QA · request-trip + invite-manager (F21 actions) + create-trip (prefill) black-box tests · version 1.0.0
// CHANGE 2026-10-30 F21-QA-02: new file (no previous version).
//
// Written from docs/F21_spec.md §1.10, §3, §4, §5.1 only. The function sources were NOT read: the modules are imported as
// black boxes and driven through their exported surface (export lines / exported interfaces only):
//   request-trip:   handler(req), setDeps({rpc, sendMail, fetch, now, random, uuid, env}), resetDeps(), FN_VERSION
//   invite-manager: makeHandler(deps{store, verifyJwt, sendMail, now, random, appUrl, log, rpc?}), renderInviteEmail, FN_VERSION
//   create-trip:    handler(req), setDeps({getUser, rpc, now}), resetDeps(), FN_VERSION
// The "before" invite email (criterion 12: Hebrew template byte-identical) is the alpha.7.2 invite-manager read from git
// (313eb14), loaded from a scratch copy. SMTP, RPCs and Cloudflare siteverify are stubs; nothing talks to the network.
// Case ids RT-* (request-trip), IMR-* (invite-manager), CTP-* (create-trip); criteria in brackets [Cn] (spec §6).
//
// Run (sandbox, no Deno):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        tests/f21/function_test.ts
// deno-lint-ignore-file no-explicit-any
type Any = any;
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync, copyFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REPO = new URL("../../", import.meta.url);
const RT: Any = await import(new URL("supabase/functions/request-trip/index.ts", REPO).href);
const IM: Any = await import(new URL("supabase/functions/invite-manager/index.ts", REPO).href);
const CT: Any = await import(new URL("supabase/functions/create-trip/index.ts", REPO).href);
const QV: Any = JSON.parse(readFileSync(new URL("tests/qa_versions.json", REPO), "utf8"));

// alpha.7.2 invite-manager (the "before" of criterion 12), from git, in a scratch dir with the offline supabase-js stub
const OLD_REF = "313eb14";
const oldDir = mkdtempSync(join(tmpdir(), "f21qa_im_"));
writeFileSync(join(oldDir, "index.ts"), execFileSync("git", ["-C", new URL(".", REPO).pathname, "show", `${OLD_REF}:supabase/functions/invite-manager/index.ts`]));
mkdirSync(join(oldDir, "test_stubs"));
copyFileSync(new URL("supabase/functions/invite-manager/test_stubs/supabase_js.ts", REPO), join(oldDir, "test_stubs", "supabase_js.ts"));
const IM_OLD: Any = await import("file://" + join(oldDir, "index.ts"));

// ---------------------------------------------------------------------------------------------------------------
function ok(c: unknown, msg: string): asserts c {
  if (!c) throw new Error("FAIL: " + msg);
}
function eq<T>(a: T, b: T, msg: string) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`FAIL: ${msg}\n  actual:   ${JSON.stringify(a)}\n  expected: ${JSON.stringify(b)}`);
}
async function sha(s: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const T = (name: string, fn: () => Promise<void> | void) => Deno.test({ name, sanitizeOps: false, sanitizeResources: false, fn });
const LOGS: string[] = [];
const C: Any = console;
function capture() {
  LOGS.length = 0;
  for (const k of ["log", "info", "warn", "error", "debug"]) {
    C[k] = (...a: unknown[]) => {
      LOGS.push(a.map((x) => (typeof x === "string" ? x : (() => { try { return JSON.stringify(x); } catch { return String(x); } })())).join(" "));
    };
  }
}

const ORIGIN = "https://orsela.github.io";
const NOW = Date.parse("2026-10-12T06:00:00Z");
const RID = "21000000-0000-4000-8000-0000000000a1";
const IP = "203.0.113.77";
const BODY_HE = { action: "start", lang: "he", name: "דנה-סודי", email: " Dana.Secret@Example.com ", countries: ["PT", "ES"], month: "2027-04-01",
  travellers: 4, note: "הערה-סודית", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX" };
const BODY_EN = { ...BODY_HE, lang: "en", name: "Ann-Secret", note: "secret-note" };
const SECRETS = ["dana.secret@example.com", "Dana.Secret", "דנה-סודי", "הערה-סודית", "Ann-Secret", "secret-note", "XXXX.DUMMY.TOKEN.XXXX", "qa-ts-secret"];

type Call = { name: string; args: Record<string, Any> };
type RtOpt = {
  rpc?: (name: string, args: Record<string, Any>) => Any; mailFail?: boolean; sv?: Record<string, Any> | ((body: Any) => Any);
  env?: Record<string, string>; ids?: string[];
};
function rt(o: RtOpt = {}) {
  RT.resetDeps();
  const calls: Call[] = [], mails: Any[] = [], fetches: { url: string; body: Record<string, string> }[] = [];
  const ids = [...(o.ids ?? [RID])];
  const env: Record<string, string> = { TURNSTILE_SECRET: "qa-ts-secret", ...(o.env ?? {}) };
  RT.setDeps({
    rpc: (name: string, args: Record<string, Any>) => {
      calls.push({ name, args: JSON.parse(JSON.stringify(args ?? {})) });
      const d = o.rpc ? o.rpc(name, args) : name === "request_start" ? { request_id: args.p_request, sent_at: "2026-10-12T06:00:00Z" }
        : name === "request_verify" ? { status: "pending", request_id: args.p_request }
        : name === "request_resend" ? { request_id: args.p_request, sent_at: "2026-10-12T06:01:01Z", email: "dana.secret@example.com", lang: "he" }
        : { ok: true };
      if (d && d.__dbError) return Promise.resolve({ data: null, error: { message: d.__dbError } });
      return Promise.resolve({ data: d, error: null });
    },
    sendMail: (m: Any) => { if (o.mailFail) return Promise.reject(new Error("smtp down qa")); mails.push(m); return Promise.resolve(); },
    fetch: async (url: string, init: Any) => {
      const b: Record<string, string> = {};
      const raw = init?.body;
      if (raw instanceof URLSearchParams || (typeof FormData !== "undefined" && raw instanceof FormData)) { for (const [k, v] of (raw as Any).entries()) b[k] = String(v); }
      else if (typeof raw === "string") { try { Object.assign(b, JSON.parse(raw)); } catch { for (const [k, v] of new URLSearchParams(raw)) b[k] = v; } }
      fetches.push({ url: String(url), body: b });
      const sv = typeof o.sv === "function" ? o.sv(b) : (o.sv ?? { success: true, hostname: "orsela.github.io", "error-codes": [] });
      return new Response(JSON.stringify(sv), { status: 200, headers: { "content-type": "application/json" } });
    },
    now: () => NOW,
    random: (n: number) => crypto.getRandomValues(new Uint8Array(n)),
    uuid: () => ids.shift() ?? crypto.randomUUID(),
    env: (k: string) => env[k],
  });
  return { calls, mails, fetches };
}
type Res = { status: number; body: Record<string, Any>; raw: string; headers: Headers };
async function post(h: (r: Request) => Promise<Response>, body: unknown, o: { origin?: string; ip?: string; method?: string; jwt?: string; raw?: string; url?: string } = {}): Promise<Res> {
  const headers: Record<string, string> = { "Content-Type": "application/json", apikey: "sb_publishable_qa", Origin: o.origin ?? ORIGIN };
  if (o.ip !== null) headers["x-forwarded-for"] = o.ip ?? `${IP}, 10.0.0.1`;
  if (o.jwt) headers.Authorization = "Bearer " + o.jwt;
  const method = o.method ?? "POST";
  const r = await h(new Request(o.url ?? "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/request-trip", {
    method, headers, body: method === "POST" ? (o.raw ?? JSON.stringify(body)) : undefined }));
  const raw = await r.text();
  let j: Record<string, Any> = {};
  try { j = JSON.parse(raw); } catch { /* */ }
  return { status: r.status, body: j, raw, headers: r.headers };
}
const code = (r: Res) => String(r.body.code ?? r.body.error ?? "");
const digits = (m: Any) => (String(m.subject).match(/^(\d{6})\s*[–-]/) ?? [])[1] ?? "";
const hasLink = (s: string) => /https?:\/\/|href\s*=|www\./i.test(s);

// =====================================================================================================================
// RT · request-trip
// =====================================================================================================================
T("RT-00 [C20] export surface; FN_VERSION = tests/qa_versions.json request-trip (alpha.8.0); a response header carries it", async () => {
  for (const k of ["handler", "setDeps", "resetDeps"]) ok(typeof RT[k] === "function", "export " + k);
  eq(String(RT.FN_VERSION), QV.functions["request-trip"], "FN_VERSION");
  rt();
  const r = await post(RT.handler, { action: "verify", request_id: "x", code: "1" });
  ok([...r.headers.values()].includes(QV.functions["request-trip"]), "no header carries " + QV.functions["request-trip"] + ": " + JSON.stringify([...r.headers]));
});

T("RT-01 [C17] CORS: orsela.github.io and http://localhost:<port> echoed (preflight + POST); foreign origins not", async () => {
  rt();
  const bad: string[] = [];
  for (const [o, want] of [[ORIGIN, true], ["http://localhost:8080", true], ["http://localhost", true], ["https://evil.example", false], ["https://orsela.github.io.evil.example", false], ["http://127.0.0.1:8080", false]] as [string, boolean][]) {
    for (const m of ["OPTIONS", "POST"]) {
      const r = await post(RT.handler, { action: "verify", request_id: RID, code: "123456" }, { origin: o, method: m });
      const a = r.headers.get("access-control-allow-origin");
      if (want && a !== o) bad.push(`${m} ${o} → ${a}`);
      if (!want && (a === o || a === "*")) bad.push(`${m} ${o} echoed (${a})`);
      if (m === "OPTIONS" && r.status >= 300) bad.push(`OPTIONS ${o} status ${r.status}`);
    }
  }
  ok(!bad.length, bad.join("; "));
});

T("RT-02 [C5] start: siteverify(secret, token, remote IP) → request_start(id from uuid(), payload, sha256(email), sha256(first XFF ip), sha256(id‖code)) → code email → {ok, request_id, sent_at}", async () => {
  const { calls, mails, fetches } = rt();
  const r = await post(RT.handler, BODY_HE);
  eq(r.status, 200, "status " + r.raw);
  eq([r.body.ok, r.body.request_id, typeof r.body.sent_at], [true, RID, "string"], "body " + r.raw);
  eq(fetches.length, 1, "siteverify calls");
  ok(fetches[0].url === RT.SITEVERIFY_URL && /challenges\.cloudflare\.com\/turnstile\/v0\/siteverify$/.test(fetches[0].url), "siteverify URL " + fetches[0].url);
  eq([fetches[0].body.secret, fetches[0].body.response, fetches[0].body.remoteip], ["qa-ts-secret", BODY_HE.turnstile_token, IP], "siteverify params");
  const st = calls.filter((c) => c.name === "request_start");
  eq(st.length, 1, "request_start calls");
  const a = st[0].args;
  eq(a.p_request, RID, "p_request");
  eq(a.p_email_hash, await sha("dana.secret@example.com"), "p_email_hash = sha256(normalized email)");
  eq(a.p_ip, await sha(IP), "p_ip = sha256(first x-forwarded-for address)");
  // the p_payload month format between function and SQL is not in the spec ("2027-04" or "2027-04-01"); INT-01 checks the stored date
  eq([a.p_payload.lang, a.p_payload.name, a.p_payload.email, a.p_payload.countries, String(a.p_payload.month).slice(0, 7), a.p_payload.travellers, a.p_payload.note],
    ["he", "דנה-סודי", "dana.secret@example.com", ["PT", "ES"], "2027-04", 4, "הערה-סודית"], "p_payload");
  ok(!JSON.stringify(a.p_payload).includes("DUMMY"), "turnstile token stored in the payload");
  eq(mails.length, 1, "code emails");
  const c = digits(mails[0]);
  ok(/^\d{6}$/.test(c), "subject does not start with 6 digits: " + mails[0].subject);
  eq(a.p_code_hash, await sha(RID + c), "p_code_hash = sha256(request_id ‖ code) for the mailed code");
  eq(mails[0].to, "dana.secret@example.com", "to");
});

T("RT-03 [C5] Hebrew code email: subject '<6 digits> – קוד האימות לבקשה ב-Lonely Planner', body texts, code shown, HTML + text, dir=rtl, NO link", async () => {
  const { mails } = rt();
  await post(RT.handler, BODY_HE);
  const m = mails[0];
  const c = digits(m);
  eq(m.subject, `${c} – קוד האימות לבקשה ב-Lonely Planner`, "subject");
  const all = `${m.html}\n${m.text}`;
  for (const t of ["קוד האימות לבקשה שלך:", "חוזרים לדף הבקשה ומקלידים את הקוד. הוא תקף 10 דקות."]) {
    ok(String(m.text).includes(t) && String(m.html).replace(/<[^>]+>/g, "").includes(t), "missing in html or text: " + t);
  }
  ok(String(m.html).includes(c) && String(m.text).includes(c), "code not in both parts");
  ok(/dir=["']?rtl/i.test(String(m.html)), "html not dir=rtl");
  ok(/monospace/i.test(String(m.html)), "code not in monospace");
  ok(!hasLink(all), "a link in the code email: " + (all.match(/https?:\/\/\S+|href=\S+/i) ?? [""])[0]);
});

T("RT-04 [C5][C11a] English code email: subject '<6 digits> – your Lonely Planner verification code', dir=ltr, no link, no Hebrew body", async () => {
  const { mails, calls } = rt();
  const r = await post(RT.handler, BODY_EN);
  eq(r.status, 200, "status");
  const m = mails[0];
  const c = digits(m);
  eq(m.subject, `${c} – your Lonely Planner verification code`, "subject");
  ok(/dir=["']?ltr/i.test(String(m.html)), "html not dir=ltr");
  ok(!hasLink(`${m.html}\n${m.text}`), "link in the English code email");
  ok(!/[֐-׿]/.test(String(m.text)), "Hebrew in the English text part");
  eq(calls.find((x) => x.name === "request_start")!.args.p_payload.lang, "en", "lang stored");
});

T("RT-05 [C5] Turnstile refused (success:false) / wrong hostname → turnstile_failed: no request_start, no mail", async () => {
  for (const sv of [{ success: false, "error-codes": ["invalid-input-response"] }, { success: true, hostname: "evil.example" },
    { success: true, hostname: "localhost" }, { success: true }]) {
    const { calls, mails } = rt({ sv });
    const r = await post(RT.handler, BODY_HE);
    eq(code(r), "turnstile_failed", "code for " + JSON.stringify(sv) + " → " + r.raw);
    ok(r.body.ok === false, "ok:false");
    eq(calls.filter((c) => c.name === "request_start").length, 0, "request_start called");
    eq(mails.length, 0, "mail sent");
  }
});

T("RT-06 [C5] hostname localhost accepted only with TURNSTILE_ALLOW_LOCALHOST=1; missing token → turnstile_failed", async () => {
  let x = rt({ sv: { success: true, hostname: "localhost" }, env: { TURNSTILE_ALLOW_LOCALHOST: "1" } });
  let r = await post(RT.handler, BODY_HE);
  eq(r.status, 200, "localhost + flag " + r.raw);
  eq(x.mails.length, 1, "mail");
  x = rt({ sv: (b: Any) => (b.response ? { success: true, hostname: "orsela.github.io" } : { success: false, "error-codes": ["missing-input-response"] }) });
  r = await post(RT.handler, { ...BODY_HE, turnstile_token: "" });
  eq(code(r), "turnstile_failed", "empty token " + r.raw);
  eq(x.calls.length, 0, "rpc called without a token");
});

T("RT-07 [C5] email failure on start → {ok:false, code:'email_failed'} and the row is removed (a call naming the request id follows request_start)", async () => {
  const { calls } = rt({ mailFail: true });
  const r = await post(RT.handler, BODY_HE);
  eq([r.body.ok, code(r)], [false, "email_failed"], "body " + r.raw);
  const i = calls.findIndex((c) => c.name === "request_start");
  const after = calls.slice(i + 1);
  ok(after.some((c) => JSON.stringify(c.args).includes(RID)), "no cleanup call for the request after the failed email: " + JSON.stringify(calls.map((c) => c.name)));
});

T("RT-08 [C4] invalid start bodies → 400 invalid_request with the field; no request_start, no mail", async () => {
  const cases: [Record<string, unknown>, string][] = [
    [{ name: "" }, "name"], [{ name: "א".repeat(41) }, "name"], [{ email: "not-an-email" }, "email"], [{ countries: [] }, "countries"],
    [{ countries: ["PT", "ES", "FR", "IT", "DE", "GR", "TH", "VN", "JP", "US", "GB"] }, "countries"], [{ countries: ["PRT"] }, "countries"],
    [{ month: "2026-09-01" }, "month"], [{ month: "2028-04-01" }, "month"], [{ month: "2027-04-02" }, "month"], [{ travellers: 0 }, "travellers"],
    [{ travellers: 31 }, "travellers"], [{ note: "n".repeat(201) }, "note"], [{ lang: "fr" }, "lang"],
  ];
  const bad: string[] = [];
  for (const [over, field] of cases) {
    const { calls, mails } = rt();
    const r = await post(RT.handler, { ...BODY_HE, ...over });
    if (r.status !== 400 || code(r) !== "invalid_request" || calls.some((c) => c.name === "request_start") || mails.length) bad.push(`${JSON.stringify(over).slice(0, 40)} → ${r.status} ${r.raw.slice(0, 100)}`);
    else if (r.body.field !== field) bad.push(`${JSON.stringify(over).slice(0, 40)} → field ${r.body.field} (want ${field})`);
  }
  // lower-case codes: accepted only if normalized to upper case before the DB (spec: each ^[A-Z]{2}$)
  { const { calls } = rt(); const r = await post(RT.handler, { ...BODY_HE, countries: ["pt"] });
    if (r.status === 200 && JSON.stringify(calls.find((c) => c.name === "request_start")?.args.p_payload.countries) !== '["PT"]') bad.push("['pt'] accepted without normalization"); }
  for (const okOver of [{ month: null }, { month: "2026-10-01" }, { month: "2028-03-01" }, { note: "" }, { travellers: 30 }, { name: "א".repeat(40) }]) {
    const { mails } = rt();
    const r = await post(RT.handler, { ...BODY_HE, ...okOver });
    if (r.status !== 200 || mails.length !== 1) bad.push(`valid ${JSON.stringify(okOver).slice(0, 40)} refused: ${r.raw.slice(0, 100)}`);
  }
  ok(!bad.length, bad.join("\n  "));
});

T("RT-09 [C8][C9] refusals of request_start passed through: daily_limit / rate_limited → {ok:false, code}, no mail", async () => {
  for (const e of ["daily_limit", "rate_limited"]) {
    const { mails } = rt({ rpc: (n) => (n === "request_start" ? { error: e } : { ok: true }) });
    const r = await post(RT.handler, BODY_HE);
    eq([r.body.ok, code(r)], [false, e], e + " → " + r.raw);
    ok(r.status >= 400 && r.status < 500, e + " status " + r.status);
    eq(mails.length, 0, e + " mail sent");
  }
});

T("RT-10 [C10] C4: the start response is identical whatever the email's history (stub: same DB answer) — keys and status", async () => {
  const outs: Res[] = [];
  for (const email of ["new.person@example.com", "existing.manager@example.com"]) {
    rt({ ids: [RID] });
    outs.push(await post(RT.handler, { ...BODY_HE, email }));
  }
  eq([outs[0].status, Object.keys(outs[0].body).sort()], [outs[1].status, Object.keys(outs[1].body).sort()], "status/keys");
  ok(!/manager|marker|exists|known/i.test(outs[1].raw), "response hints the email is known: " + outs[1].raw);
});

T("RT-11 [C6] verify → request_verify(p_request, sha256(id‖code), sha256(ip)); results mapped (pending → ok; code_wrong + attempts_left; code_expired; code_locked; request_unknown)", async () => {
  let x = rt();
  let r = await post(RT.handler, { action: "verify", request_id: RID, code: "123456" });
  eq(r.status, 200, "ok " + r.raw);
  eq(r.body.ok, true, "ok:true");
  const a = x.calls.find((c) => c.name === "request_verify")!.args;
  eq([a.p_request, a.p_code_hash, a.p_ip], [RID, await sha(RID + "123456"), await sha(IP)], "args");
  for (const [db, want] of [[{ error: "code_wrong", attempts_left: 3 }, "code_wrong"], [{ error: "code_expired" }, "code_expired"],
    [{ error: "code_locked" }, "code_locked"], [{ error: "request_unknown" }, "request_unknown"], [{ error: "rate_limited" }, "rate_limited"]] as [Any, string][]) {
    x = rt({ rpc: (n) => (n === "request_verify" ? db : { ok: true }) });
    r = await post(RT.handler, { action: "verify", request_id: RID, code: "123456" });
    eq([r.body.ok, code(r)], [false, want], JSON.stringify(db) + " → " + r.raw);
    if (want === "code_wrong") eq(r.body.attempts_left, 3, "attempts_left passed through");
  }
  x = rt();
  r = await post(RT.handler, { action: "verify", request_id: RID, code: " 123 456 " });
  ok(r.status === 200 || code(r) === "invalid_request", "spaced code: " + r.raw);
});

T("RT-12 [C6] resend → a NEW code: request_resend(p_request, sha256(id‖new)) + mail with that code; refusal (cooldown / 4th / daily_limit) → no mail", async () => {
  let x = rt();
  let r = await post(RT.handler, { action: "resend", request_id: RID });
  eq([r.status, r.body.ok, r.body.request_id], [200, true, RID], "ok " + r.raw);
  ok(typeof r.body.sent_at === "string", "sent_at");
  eq(x.mails.length, 1, "mail");
  const c = digits(x.mails[0]);
  eq(x.calls.find((k) => k.name === "request_resend")!.args.p_code_hash, await sha(RID + c), "hash of the mailed code");
  for (const db of [{ error: "rate_limited", retry_in: 30 }, { error: "daily_limit" }, { error: "request_unknown" }]) {
    x = rt({ rpc: (n) => (n === "request_resend" ? db : { ok: true }) });
    r = await post(RT.handler, { action: "resend", request_id: RID });
    eq([r.body.ok, code(r)], [false, db.error], JSON.stringify(db) + " → " + r.raw);
    eq(x.mails.length, 0, "mail sent on refusal " + db.error);
  }
});

T("RT-13 [C17] logs: one JSON line per request with action / status / error code only — never email, name, note, code or token", async () => {
  capture();
  const before = LOGS.length;
  const x = rt();
  await post(RT.handler, BODY_HE);
  const c = digits(x.mails[0]);
  rt({ mailFail: true });
  await post(RT.handler, BODY_EN);
  rt({ rpc: (n) => (n === "request_verify" ? { error: "code_wrong", attempts_left: 2 } : { ok: true }) });
  await post(RT.handler, { action: "verify", request_id: RID, code: "654321" });
  rt({ sv: { success: false } });
  await post(RT.handler, BODY_HE);
  const logs = LOGS.slice(before);
  const leaks = logs.filter((l) => [...SECRETS, c, "654321"].some((s) => l.includes(s)));
  ok(!leaks.length, "secret in logs: " + leaks.join(" | "));
  ok(logs.length >= 4, "fewer log lines than requests: " + logs.length);
  for (const l of logs) {
    let j: Any = null;
    try { j = JSON.parse(l.slice(l.indexOf("{"))); } catch { /* */ }
    ok(j && typeof j === "object", "log line is not JSON: " + l);
  }
});

T("RT-14 [C17] bad requests: GET → 405, unknown action / bad JSON → 400 invalid_request (never 5xx), no rpc", async () => {
  const { calls } = rt();
  const g = await post(RT.handler, null, { method: "GET" });
  ok(g.status === 405, "GET status " + g.status);
  for (const raw of ['{"action":"delete_all"}', "{not json", '{"action":"verify"}', '{"action":"verify","request_id":"x","code":"1"}']) {
    const r = await post(RT.handler, null, { raw });
    ok(r.status >= 400 && r.status < 500, raw + " → " + r.status);
  }
  ok(!calls.length, "rpc called: " + calls.map((c) => c.name));
});

T("RT-15 [C20] §3.1 MIME + SMTP helpers come from ../invite-manager/index.ts (no copy in request-trip)", () => {
  const src = readFileSync(new URL("supabase/functions/request-trip/index.ts", REPO), "utf8");
  const imp = src.split("\n").filter((l) => /^import .*from "\.\.\/invite-manager\/index\.ts"/.test(l));
  ok(imp.length === 1, "no import from ../invite-manager/index.ts");
  ok(!/function\s+(smtpSend|buildMime|encodeSubjectHeader)\b/.test(src), "a copy of the SMTP/MIME helpers");
});

T("RT-16 [C5] From name 'Lonely Planner' (F04-NAME-01): the mailer of request-trip is invite-manager's (FROM_NAME)", () => {
  eq(IM.FROM_NAME, "Lonely Planner", "FROM_NAME");
});

// =====================================================================================================================
// IMR · invite-manager F21 actions
// =====================================================================================================================
type Row = Record<string, Any>;
function memStore(rows: Row[]) {
  const open = (r: Row) => !r.used_at && !r.revoked_at;
  return {
    rows,
    isPlatformAdmin: (uid: string) => Promise.resolve(uid === "admin-uid"),
    inviterName: () => Promise.resolve("אור-מזמין"),
    findOpenByEmail: (e: string) => Promise.resolve(rows.find((r) => r.email === e && open(r)) ?? null),
    getById: (id: string) => Promise.resolve(rows.find((r) => r.id === id) ?? null),
    findByHash: (h: string) => Promise.resolve(rows.find((r) => r.token_hash === h) ?? null),
    insert: (row: Row) => {
      if (rows.some((r) => r.email === row.email && open(r))) return Promise.reject({ code: "23505" });
      const id = crypto.randomUUID();
      rows.push({ id, used_at: null, revoked_at: null, opened_at: null, created_at: new Date(NOW).toISOString(), ...row });
      return Promise.resolve(id);
    },
    deleteById: (id: string) => { const i = rows.findIndex((r) => r.id === id); if (i >= 0) rows.splice(i, 1); return Promise.resolve(); },
    revokeOpen: (id: string, at: string) => { const r = rows.find((x) => x.id === id && open(x)); if (r) r.revoked_at = at; return Promise.resolve(r ? 1 : 0); },
    updateOpen: (id: string, f: Row) => { const r = rows.find((x) => x.id === id && open(x)); if (r) Object.assign(r, f); return Promise.resolve(r ? 1 : 0); },
    markOpened: (id: string, at: string) => { const r = rows.find((x) => x.id === id); if (r && !r.opened_at) r.opened_at = at; return Promise.resolve(); },
  };
}
const REQ = "21000000-0000-4000-8000-0000000000b2";
const NEWINV = "21000000-0000-4000-8000-0000000000c3";
const OLDINV = "21000000-0000-4000-8000-0000000000d4";
type ImOpt = { rpc?: (name: string, args: Record<string, Any>) => Any; mailFail?: boolean | ((m: Any) => boolean); rows?: Row[]; seed?: number };
function seeded(seed: number) {
  let s = seed >>> 0;
  return (n: number) => { const a = new Uint8Array(n); for (let i = 0; i < n; i++) { s = (s * 1664525 + 1013904223) >>> 0; a[i] = s >>> 24; } return a; };
}
function im(o: ImOpt = {}, mod: Any = IM) {
  const mails: Any[] = [], calls: Call[] = [], logs: string[] = [];
  const reqLang = { v: "he" };
  const deps: Any = {
    store: memStore(o.rows ?? []),
    verifyJwt: (j: string) => Promise.resolve(j === "admin-jwt" ? "admin-uid" : j === "user-jwt" ? "user-uid" : null),
    sendMail: (m: Any) => {
      const f = typeof o.mailFail === "function" ? o.mailFail(m) : o.mailFail;
      if (f) return Promise.reject(new Error("smtp down qa"));
      mails.push(m); return Promise.resolve();
    },
    now: () => new Date(NOW),
    random: o.seed !== undefined ? seeded(o.seed) : (n: number) => crypto.getRandomValues(new Uint8Array(n)),
    appUrl: IM.DEFAULT_APP_URL,
    log: (event: string, fields?: Record<string, unknown>) => { logs.push(event + " " + JSON.stringify(fields ?? {})); },
    rpc: (name: string, args: Record<string, Any>) => {
      calls.push({ name, args: JSON.parse(JSON.stringify(args ?? {})) });
      const d = o.rpc ? o.rpc(name, args) : name === "request_approve"
        ? { invite_id: NEWINV, expires_at: "2026-10-19T06:00:00Z", revoked_invite_id: null, email: "ann.secret@example.com", lang: reqLang.v, name: "Ann-Secret", draft_name: args.p_draft }
        : name === "request_reject" ? (args.p_mail ? { mail: true, lang: reqLang.v, email: "ann.secret@example.com", name: "Ann-Secret" } : { mail: false, reason: "not_requested" })
        : { ok: true };
      if (d && d.__throw) return Promise.reject(new Error(d.__throw));
      return Promise.resolve(d);
    },
  };
  return { h: mod.makeHandler(deps), mails, calls, logs, deps, reqLang };
}
const linkOf = (m: Any) => (`${m.text}\n${m.html}`.match(/https:\/\/[^\s"'<>]*#invite=[A-Za-z0-9_-]{43}/) ?? [""])[0];
const IM_URL = "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/invite-manager";

T("IMR-00 [C20] invite-manager FN_VERSION = tests/qa_versions.json (alpha.8.0); create-trip too", () => {
  eq(String(IM.FN_VERSION), QV.functions["invite-manager"], "invite-manager");
  eq(String(CT.FN_VERSION), QV.functions["create-trip"], "create-trip");
});

T("IMR-01 [C17] approve_request / reject_request refuse non-admins (no JWT, unknown JWT, non-admin JWT) → 403 not_platform_admin, no rpc, no mail", async () => {
  const x = im();
  const bad: string[] = [];
  for (const jwt of [undefined, "garbage-jwt", "user-jwt"]) {
    for (const body of [{ action: "approve_request", request_id: REQ, draft_name: "x" }, { action: "reject_request", request_id: REQ, send_mail: true }]) {
      const r = await post(x.h, body, { jwt, url: IM_URL });
      if (r.status !== 403 || code(r) !== "not_platform_admin") bad.push(`${jwt} ${body.action} → ${r.status} ${r.raw}`);
    }
  }
  ok(!bad.length, bad.join("; "));
  eq([x.calls.length, x.mails.length], [0, 0], "rpc / mail");
});

T("IMR-02 [C12] approve_request (he): request_approve(p_admin, p_request, sha256(token in the link), p_draft = edited name, p_inviter) → Hebrew invite mail; 200 {ok, invite_id, expires_at}", async () => {
  const x = im();
  const r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "  פורטוגל וספרד · אפריל 2027  " }, { jwt: "admin-jwt", url: IM_URL });
  eq(r.status, 200, "status " + r.raw);
  eq([r.body.ok, r.body.invite_id], [true, NEWINV], "body");
  const ap = x.calls.filter((c) => c.name === "request_approve");
  eq(ap.length, 1, "request_approve calls");
  const a = ap[0].args;
  eq([a.p_admin, a.p_request, a.p_draft], ["admin-uid", REQ, "פורטוגל וספרד · אפריל 2027"], "args (draft trimmed)");
  ok(typeof a.p_inviter === "string" && a.p_inviter.length > 0, "p_inviter");
  eq(x.mails.length, 1, "mails");
  const tok = linkOf(x.mails[0]).split("#invite=")[1];
  eq(a.p_token_hash, await sha(tok), "p_token_hash = sha256(link token)");
  eq(x.mails[0].subject, IM.EMAIL_SUBJECT, "Hebrew subject");
  eq(x.mails[0].to, "ann.secret@example.com", "to = the request's email");
  ok(linkOf(x.mails[0]).startsWith("https://orsela.github.io/Lonely_Planner/invite/#invite="), "link as F03/F04-HOME: " + linkOf(x.mails[0]));
});

T("IMR-03 [C12] Hebrew approval mail == the alpha.7.2 F03 template byte for byte (same token, draft, inviter, expiry); renderInviteEmail(lang default) == alpha.7.2", async () => {
  const p = { to: "ann.secret@example.com", inviter: "אור-מזמין", draftName: "פורטוגל וספרד · אפריל 2027", link: "https://orsela.github.io/Lonely_Planner/invite/#invite=" + "A".repeat(43), expiresAt: "2026-10-19T06:00:00Z" };
  eq(IM.renderInviteEmail(p), IM_OLD.renderInviteEmail(p), "renderInviteEmail(no lang) vs alpha.7.2");
  eq(IM.renderInviteEmail({ ...p, lang: "he" }), IM_OLD.renderInviteEmail(p), "renderInviteEmail(lang he) vs alpha.7.2");
  // end-to-end: the approve mail vs the alpha.7.2 `create` mail with the same random source and the same row values
  const x = im({ seed: 7, rpc: (n, a) => (n === "request_approve" ? { invite_id: NEWINV, expires_at: "2026-10-19T06:00:00.000Z", revoked_invite_id: null, email: "ann.secret@example.com", lang: "he", name: "Ann-Secret", draft_name: a.p_draft } : { ok: true }) });
  await post(x.h, { action: "approve_request", request_id: REQ, draft_name: p.draftName }, { jwt: "admin-jwt", url: IM_URL });
  const y = im({ seed: 7 }, IM_OLD);
  await post(y.h, { action: "create", email: "ann.secret@example.com", draft_name: p.draftName }, { jwt: "admin-jwt", url: IM_URL });
  eq(x.mails.length + y.mails.length, 2, "both mails sent");
  eq([x.mails[0].subject, x.mails[0].html, x.mails[0].text], [y.mails[0].subject, y.mails[0].html, y.mails[0].text], "approval mail (he) vs alpha.7.2 create mail");
});

T("IMR-04 [C12][C11b] approve_request (en): English template — subject, greeting by requester name, trip name, button, same /invite/ link builder, Hebrew-for-now note, dd/mm/yyyy, LTR", async () => {
  const x = im();
  x.reqLang.v = "en";
  const r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "Portugal & Spain · April 2027" }, { jwt: "admin-jwt", url: IM_URL });
  eq(r.status, 200, "status " + r.raw);
  const m = x.mails[0];
  eq(m.subject, "Your trip request was approved", "subject");
  const html = String(m.html), text = String(m.text);
  for (const s of ["Ann-Secret", "Accept and set up the trip", "Lonely Planner"]) ok(html.includes(s) || html.includes(IM.htmlEscape(s)), "html lacks " + s);
  ok(html.includes("Portugal &amp; Spain · April 2027") || html.includes("Portugal & Spain · April 2027"), "trip name not in html");
  ok(text.includes("Portugal & Spain · April 2027") && text.includes("Ann-Secret"), "text lacks the trip / greeting");
  ok(/Hebrew/i.test(text), "no 'Hebrew for now' note");
  ok(/19\/10\/2026/.test(text) && /19\/10\/2026/.test(html), "validity date dd/mm/yyyy (19/10/2026) missing");
  ok(/dir=["']?ltr/i.test(html), "html not LTR");
  ok(!/[֐-׿]/.test(text.replace("Ann-Secret", "")), "Hebrew in the English text part");
  ok(/^https:\/\/orsela\.github\.io\/Lonely_Planner\/invite\/#invite=[A-Za-z0-9_-]{43}$/.test(linkOf(m)), "link " + linkOf(m));
  eq(x.calls.find((c) => c.name === "request_approve")!.args.p_token_hash, await sha(linkOf(m).split("#invite=")[1]), "hash of the mailed token");
});

T("IMR-05 [C14] approve_request email failure → request_approve_undo(new invite, revoked invite, request) → 502 email_failed", async () => {
  for (const revoked of [OLDINV, null]) {
    const x = im({ mailFail: true, rpc: (n, a) => (n === "request_approve" ? { invite_id: NEWINV, expires_at: "2026-10-19T06:00:00Z", revoked_invite_id: revoked, email: "ann.secret@example.com", lang: "he", name: "Ann-Secret", draft_name: a.p_draft } : { ok: true }) });
    const r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "x" }, { jwt: "admin-jwt", url: IM_URL });
    eq([r.status, code(r)], [502, "email_failed"], "response " + r.raw);
    const u = x.calls.filter((c) => c.name === "request_approve_undo");
    eq(u.length, 1, "undo calls");
    eq([u[0].args.p_invite, u[0].args.p_revoked ?? null, u[0].args.p_request], [NEWINV, revoked, REQ], "undo args");
  }
});

T("IMR-06 [C13] approve_request with an active invite: the response reports the revoked invite; create keeps invite_exists (D12 is approval-only)", async () => {
  const x = im({ rows: [{ id: OLDINV, email: "ann.secret@example.com", token_hash: "f".repeat(64), draft_name: "ישן", inviter_name: "אור", expires_at: "2026-10-16T06:00:00Z", used_at: null, revoked_at: null, opened_at: null, send_count: 1, last_sent_at: "2026-10-10T06:00:00Z", created_at: "2026-10-10T06:00:00Z" }],
    rpc: (n, a) => (n === "request_approve" ? { invite_id: NEWINV, expires_at: "2026-10-19T06:00:00Z", revoked_invite_id: OLDINV, email: "ann.secret@example.com", lang: "he", name: "Ann-Secret", draft_name: a.p_draft } : { ok: true }) });
  const r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "חדש" }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, r.body.revoked_invite_id], [200, OLDINV], "approve " + r.raw);
  const c = await post(x.h, { action: "create", email: "ann.secret@example.com", draft_name: "y" }, { jwt: "admin-jwt", url: IM_URL });
  eq([c.status, code(c)], [409, "invite_exists"], "create still refuses an open invite: " + c.raw);
});

T("IMR-07 [C12] approve_request refusals: request_closed → 409; draft name > 80 → 400; missing request_id → 400; no mail", async () => {
  let x = im({ rpc: (n) => (n === "request_approve" ? { error: "request_closed" } : { ok: true }) });
  let r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "x" }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, code(r)], [409, "request_closed"], "closed " + r.raw);
  eq(x.mails.length, 0, "mail on request_closed");
  x = im();
  r = await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "א".repeat(81) }, { jwt: "admin-jwt", url: IM_URL });
  ok(r.status === 400, "81-char draft → " + r.status + " " + r.raw);
  r = await post(x.h, { action: "approve_request", draft_name: "x" }, { jwt: "admin-jwt", url: IM_URL });
  ok(r.status === 400, "no request_id → " + r.status);
  eq([x.calls.filter((c) => c.name === "request_approve").length, x.mails.length], [0, 0], "rpc / mail on bad input");
});

T("IMR-08 [C15] reject_request with mail: request_reject(p_admin, p_request, p_mail:true) → reject mail in the request language (§5.1), no link, no reason", async () => {
  for (const lang of ["he", "en"]) {
    const x = im();
    x.reqLang.v = lang;
    const r = await post(x.h, { action: "reject_request", request_id: REQ, send_mail: true }, { jwt: "admin-jwt", url: IM_URL });
    eq([r.status, r.body.ok], [200, true], lang + " " + r.raw);
    ok(!("mail_skipped" in r.body), "mail_skipped on a sent mail");
    const a = x.calls.find((c) => c.name === "request_reject")!.args;
    eq([a.p_admin, a.p_request, a.p_mail], ["admin-uid", REQ, true], "args");
    eq(x.mails.length, 1, "mails");
    const m = x.mails[0];
    eq(m.to, "ann.secret@example.com", "to");
    if (lang === "he") {
      eq(m.subject, "הבקשה שלך ל-Lonely Planner", "he subject");
      ok(String(m.text).includes("תודה על ההתעניינות ב-Lonely Planner. כרגע לא נוכל לפתוח את הטיול שלך. אפשר לשלוח בקשה חדשה בעתיד."), "he body");
      ok(/dir=["']?rtl/i.test(String(m.html)), "he html rtl");
    } else {
      eq(m.subject, "Your Lonely Planner request", "en subject");
      ok(!/[֐-׿]/.test(String(m.text)), "Hebrew in the English reject mail");
      ok(/dir=["']?ltr/i.test(String(m.html)), "en html ltr");
    }
    ok(!hasLink(`${m.html}\n${m.text}`), lang + " reject mail has a link");
  }
});

T("IMR-09 [C15][C9] reject_request: without mail → no mail; at the cap → {ok:true, mail_skipped:'daily_limit'}; SMTP failure → {ok:true, mail_skipped:'email_failed'}", async () => {
  let x = im();
  let r = await post(x.h, { action: "reject_request", request_id: REQ, send_mail: false }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, r.body.ok, x.mails.length], [200, true, 0], "no mail " + r.raw);
  eq(x.calls.find((c) => c.name === "request_reject")!.args.p_mail, false, "p_mail false");
  x = im({ rpc: (n) => (n === "request_reject" ? { mail: false, reason: "daily_limit" } : { ok: true }) });
  r = await post(x.h, { action: "reject_request", request_id: REQ, send_mail: true }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, r.body.ok, r.body.mail_skipped, x.mails.length], [200, true, "daily_limit", 0], "cap " + r.raw);
  x = im({ mailFail: true });
  r = await post(x.h, { action: "reject_request", request_id: REQ, send_mail: true }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, r.body.ok, r.body.mail_skipped], [200, true, "email_failed"], "smtp failure " + r.raw);
  x = im({ rpc: (n) => (n === "request_reject" ? { error: "request_closed" } : { ok: true }) });
  r = await post(x.h, { action: "reject_request", request_id: REQ, send_mail: true }, { jwt: "admin-jwt", url: IM_URL });
  eq([r.status, code(r)], [409, "request_closed"], "closed " + r.raw);
});

T("IMR-10 [C12][C11b] resend of an English invite uses the stored lang (English template); a Hebrew / legacy row stays Hebrew", async () => {
  const base = { email: "ann.secret@example.com", token_hash: "e".repeat(64), draft_name: "Portugal", inviter_name: "אור", expires_at: "2026-10-16T06:00:00Z", used_at: null, revoked_at: null, opened_at: null, send_count: 1, last_sent_at: "2026-10-10T06:00:00Z", created_at: "2026-10-10T06:00:00Z", request_id: REQ };
  const x = im({ rows: [{ ...base, id: OLDINV, lang: "en" }], rpc: () => ({ name: "Ann-Secret", lang: "en", email: base.email }) });
  const r = await post(x.h, { action: "resend", invite_id: OLDINV }, { jwt: "admin-jwt", url: IM_URL });
  eq(r.status, 200, "resend en " + r.raw);
  eq(x.mails[0]?.subject, "Your trip request was approved", "English resend subject");
  const y = im({ rows: [{ ...base, id: OLDINV, lang: "he", request_id: null }, ] });
  const r2 = await post(y.h, { action: "resend", invite_id: OLDINV }, { jwt: "admin-jwt", url: IM_URL });
  eq([r2.status, y.mails[0]?.subject], [200, IM.EMAIL_SUBJECT], "Hebrew resend");
  const z = im({ rows: [{ ...base, id: OLDINV, request_id: null, lang: undefined }] });
  const r3 = await post(z.h, { action: "resend", invite_id: OLDINV }, { jwt: "admin-jwt", url: IM_URL });
  eq([r3.status, z.mails[0]?.subject], [200, IM.EMAIL_SUBJECT], "legacy row (no lang) resend");
});

T("IMR-11 [C12] create (F03 sheet) unchanged: Hebrew mail == alpha.7.2 create mail for the same random source", async () => {
  const x = im({ seed: 11 });
  await post(x.h, { action: "create", email: "noa.secret@example.com", draft_name: "יפן 2027" }, { jwt: "admin-jwt", url: IM_URL });
  const y = im({ seed: 11 }, IM_OLD);
  await post(y.h, { action: "create", email: "noa.secret@example.com", draft_name: "יפן 2027" }, { jwt: "admin-jwt", url: IM_URL });
  eq([x.mails[0].subject, x.mails[0].html, x.mails[0].text], [y.mails[0].subject, y.mails[0].html, y.mails[0].text], "create mail vs alpha.7.2");
});

T("IMR-12 [C17] invite-manager F21 logs carry no email / name / draft / token", async () => {
  capture();
  const before = LOGS.length;
  const x = im();
  x.reqLang.v = "en";
  await post(x.h, { action: "approve_request", request_id: REQ, draft_name: "Secret-Draft-QA" }, { jwt: "admin-jwt", url: IM_URL });
  await post(x.h, { action: "reject_request", request_id: REQ, send_mail: true }, { jwt: "admin-jwt", url: IM_URL });
  const y = im({ mailFail: true });
  await post(y.h, { action: "approve_request", request_id: REQ, draft_name: "Secret-Draft-QA" }, { jwt: "admin-jwt", url: IM_URL });
  const tok = linkOf(x.mails[0]).split("#invite=")[1];
  const all = x.logs.concat(y.logs, LOGS.slice(before));
  const leaks = all.filter((l) => ["ann.secret@example.com", "Ann-Secret", "Secret-Draft-QA", tok, "admin-jwt"].some((s) => s && l.includes(s)));
  ok(!leaks.length, "leak in logs: " + leaks.join(" | "));
});

// =====================================================================================================================
// CTP · create-trip lookup prefill (§3.3)
// =====================================================================================================================
const VERIFIED = { id: "11111111-1111-4111-8111-111111111111", email: "dana.secret@example.com", email_confirmed_at: "2026-10-12T06:00:00Z", is_anonymous: false };
function ct(find: Any) {
  CT.resetDeps();
  const calls: Call[] = [];
  CT.setDeps({
    getUser: (j: string) => Promise.resolve(j === "jwt-ok" ? VERIFIED : null),
    rpc: (name: string, args: Record<string, Any>) => { calls.push({ name, args }); return Promise.resolve(name === "find_invite_for_email" ? { data: find, error: null } : { data: { trip_id: "t", join_code: "X7K2M9QP", created: true }, error: null }); },
    now: () => NOW,
  });
  return calls;
}
const FOUND = { found: true, invite_id: "9e0d6c1a-0000-4000-8000-00000000abcd", draft_name: "Portugal & Spain · April 2027", inviter_name: "אור", expires_at: "2026-10-19T06:00:00Z" };

T("CTP-01 [C16] lookup passes prefill {name, countries, month, lang} through from find_invite_for_email", async () => {
  ct({ ...FOUND, prefill: { name: "Ann", countries: ["PT", "ES"], month: "2027-04-01", lang: "en" } });
  const r = await post(CT.handler, { action: "lookup" }, { jwt: "jwt-ok", url: "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip" });
  eq(r.status, 200, "status " + r.raw);
  eq(r.body.prefill, { name: "Ann", countries: ["PT", "ES"], month: "2027-04-01", lang: "en" }, "prefill");
  eq([r.body.found, r.body.draft_name], [true, FOUND.draft_name], "found/draft");
  ct({ ...FOUND, prefill: { name: "נועה", countries: ["JP"], month: null, lang: "he" } });
  const r2 = await post(CT.handler, { action: "lookup" }, { jwt: "jwt-ok", url: "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip" });
  eq(r2.body.prefill, { name: "נועה", countries: ["JP"], month: null, lang: "he" }, "month null");
});

T("CTP-02 [C16] invite without a request → lookup exactly as alpha.7.2 {found, draft_name, inviter_name, expires_at} (no prefill key)", async () => {
  ct(FOUND);
  const r = await post(CT.handler, { action: "lookup" }, { jwt: "jwt-ok", url: "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip" });
  eq(Object.keys(r.body).sort(), ["draft_name", "expires_at", "found", "inviter_name"], "keys");
  ct({ found: false });
  const r2 = await post(CT.handler, { action: "lookup" }, { jwt: "jwt-ok", url: "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip" });
  eq(r2.raw, '{"found":false}', "not found body");
});

T("CTP-03 [C16] create unchanged: the wizard's payload is sent as confirmed (no prefill merged in)", async () => {
  const calls = ct({ ...FOUND, prefill: { name: "Ann", countries: ["PT", "ES"], month: "2027-04-01", lang: "en" } });
  const P = { name: "טיול", display_name: "דנה", start_date: "2027-04-03", end_date: "2027-04-20", home_currency: "ILS", default_lang: "he", default_role: "editor",
    countries: ["JP"], currencies: [{ code: "JPY", kind: "destination" }], center: { lat: 35.68, lng: 139.69 } };
  const r = await post(CT.handler, { action: "create", ...P }, { jwt: "jwt-ok", url: "https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip" });
  eq(r.status, 200, "create " + r.raw);
  const c = calls.find((x) => x.name === "create_trip_from_invite")!;
  eq(c.args.p_payload.countries, ["JP"], "countries as sent by the wizard");
});
