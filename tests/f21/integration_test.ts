// Lonely Planner F21 QA · Edge Functions wired to a LOCAL PostgreSQL with 0001…0017 · version 1.0.0
// CHANGE 2026-10-30 F21-QA-03: new file (no previous version).
//
// The real handlers (request-trip, invite-manager, create-trip) with their `rpc` dependency executed as service_role on a
// scratch local database built by `python3 tests/f21/db_test.py --setup-only` (env F21_QA_DB, default pt_f21_int). SMTP and
// siteverify are stubs. This checks the function ↔ SQL contract end to end without reading either side. Case ids INT-*.
// Run: F21_QA_DB=pt_f21_int python3 tests/f21/db_test.py --setup-only && \
//      node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs tests/f21/integration_test.ts
// deno-lint-ignore-file no-explicit-any
type Any = any;
import { execFileSync } from "node:child_process";

const REPO = new URL("../../", import.meta.url);
const RT: Any = await import(new URL("supabase/functions/request-trip/index.ts", REPO).href);
const IM: Any = await import(new URL("supabase/functions/invite-manager/index.ts", REPO).href);
const CT: Any = await import(new URL("supabase/functions/create-trip/index.ts", REPO).href);
const DB = process.env.F21_QA_DB || "pt_f21_int";

function psql(sql: string): string {
  return execFileSync("sudo", ["-u", "postgres", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", DB, "-At", "-c", sql], { cwd: "/tmp", encoding: "utf8" }).trim();
}
const lit = (s: string) => "$qa$" + s.replace(/\$qa\$/g, "") + "$qa$";
const SIG: Record<string, { names: string[]; types: string[] }> = {};
for (const ln of psql(`select p.proname||'|'||array_to_string(p.proargnames, ',')||'|'||array_to_string(p.proargtypes::regtype[]::text[], ',')
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.pronargs > 0`).split("\n")) {
  const [n, a, t] = ln.split("|");
  SIG[n] = { names: a.split(","), types: t.split(",") };
}
const PG_CALLS: string[] = [];
function pgCall(name: string, args: Record<string, Any>): Any {
  const s = SIG[name];
  if (!s) throw new Error("no public function " + name);
  PG_CALLS.push(name);
  const parts = Object.entries(args ?? {}).map(([k, v]) => {
    const i = s.names.indexOf(k);
    if (i < 0) throw new Error(`${name}: unknown argument ${k} (have ${s.names})`);
    const t = s.types[i];
    return `${k} => ${v === null || v === undefined ? "null" : lit(typeof v === "object" ? JSON.stringify(v) : String(v))}::${t}`;
  });
  const out = psql(`set role service_role; select to_jsonb(public.${name}(${parts.join(", ")}))::text;`);
  return JSON.parse(out.split("\n").pop() || "null");
}
const rpcRT = (name: string, args: Record<string, Any>) => {
  try { return Promise.resolve({ data: pgCall(name, args), error: null }); } catch (e) { return Promise.resolve({ data: null, error: { message: String(e).slice(0, 300) } }); }
};
const rpcIM = (name: string, args: Record<string, Any>) => { try { return Promise.resolve(pgCall(name, args)); } catch (e) { return Promise.reject(e); } };

function ok(c: unknown, msg: string): asserts c { if (!c) throw new Error("FAIL: " + msg); }
function eq<T>(a: T, b: T, msg: string) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`FAIL: ${msg}\n  actual:   ${JSON.stringify(a)}\n  expected: ${JSON.stringify(b)}`);
}
async function sha(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const T = (name: string, fn: () => Promise<void> | void) => Deno.test({ name, sanitizeOps: false, sanitizeResources: false, fn });
function reset() {
  psql(`delete from public.manager_invites; delete from private.trip_requests; delete from private.request_attempts; delete from private.mail_log;
        delete from public.trips; delete from public.platform_admins; delete from auth.users;`);
}
const sql1 = (q: string) => psql(q).split("\n").pop() ?? "";

const MAILS: Any[] = [];
let MAIL_FAIL = false;
function rtDeps() {
  RT.resetDeps();
  MAILS.length = 0;
  RT.setDeps({
    rpc: rpcRT,
    sendMail: (m: Any) => (MAIL_FAIL ? Promise.reject(new Error("smtp qa")) : (MAILS.push(m), Promise.resolve())),
    fetch: () => Promise.resolve(new Response(JSON.stringify({ success: true, hostname: "orsela.github.io" }), { status: 200 })),
    now: () => Date.now(), random: (n: number) => crypto.getRandomValues(new Uint8Array(n)), uuid: () => crypto.randomUUID(),
    env: (k: string) => (k === "TURNSTILE_SECRET" ? "qa" : undefined),
  });
}
async function post(h: (r: Request) => Promise<Response>, body: unknown, o: { jwt?: string; ip?: string } = {}) {
  const headers: Record<string, string> = { "Content-Type": "application/json", Origin: "https://orsela.github.io", apikey: "x", "x-forwarded-for": o.ip ?? "198.51.100.9" };
  if (o.jwt) headers.Authorization = "Bearer " + o.jwt;
  const r = await h(new Request("https://x.supabase.co/functions/v1/f", { method: "POST", headers, body: JSON.stringify(body) }));
  const raw = await r.text();
  let j: Any = {};
  try { j = JSON.parse(raw); } catch { /* */ }
  return { status: r.status, body: j, raw };
}
const START = (email: string, lang = "he", extra: Record<string, unknown> = {}) => ({ action: "start", lang, name: "דנה", email, countries: ["PT", "ES"],
  month: (() => { const d = new Date(); return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 3, 1)).toISOString().slice(0, 10); })(),
  travellers: 4, note: null, turnstile_token: "XXXX.DUMMY.TOKEN.XXXX", ...extra });
const digits = (m: Any) => (String(m.subject).match(/^(\d{6})/) ?? [])[1] ?? "";
const code = (r: Any) => String(r.body.code ?? r.body.error ?? "");

T("INT-01 [C5][C6] start → row unverified (month stored as the 1st), one code mail logged; wrong code → code_wrong 4 left; mailed code → pending", async () => {
  reset(); rtDeps();
  const s = START("int1@example.com");
  const r = await post(RT.handler, s);
  eq([r.status, r.body.ok], [200, true], "start " + r.raw);
  const id = r.body.request_id;
  eq(sql1(`select status||'|'||coalesce(month::text,'-')||'|'||lang from private.trip_requests where id='${id}'`), `unverified|${s.month}|he`, "row");
  eq(sql1("select count(*) from private.mail_log where kind='code'"), "1", "mail_log");
  const w = await post(RT.handler, { action: "verify", request_id: id, code: digits(MAILS[0]) === "000000" ? "111111" : "000000" });
  eq([code(w), w.body.attempts_left], ["code_wrong", 4], "wrong " + w.raw);
  const v = await post(RT.handler, { action: "verify", request_id: id, code: digits(MAILS[0]) });
  eq([v.status, v.body.ok], [200, true], "verify " + v.raw);
  eq(sql1(`select status from private.trip_requests where id='${id}'`), "pending", "status");
});

T("INT-02 [C10] C4: start for an existing manager's email (+ active invite) answers exactly like a new email (status, keys)", async () => {
  reset(); rtDeps();
  psql(`insert into auth.users(id, email) values ('31000000-0000-4000-8000-000000000001', 'mgr@example.com');
        insert into public.trips(id, name) values ('31000000-0000-4000-8000-0000000000aa', 'יפן');
        insert into public.trip_members(trip_id, user_id, display_name, role, status) values ('31000000-0000-4000-8000-0000000000aa','31000000-0000-4000-8000-000000000001','דנה','manager','active');
        insert into public.manager_invites(email, token_hash, expires_at) values ('mgr@example.com', repeat('a',64), now()+interval '3 days');`);
  const a = await post(RT.handler, START("mgr@example.com"), { ip: "198.51.100.1" });
  const b = await post(RT.handler, START("fresh@example.com"), { ip: "198.51.100.2" });
  eq([a.status, Object.keys(a.body).sort()], [b.status, Object.keys(b.body).sort()], "responses differ");
  eq(MAILS.length, 2, "both get a code");
});

T("INT-03 [C5] email failure on start → {ok:false, email_failed}; no row and no code mail_log row left", async () => {
  reset(); rtDeps(); MAIL_FAIL = true;
  try {
    const r = await post(RT.handler, START("int3@example.com"));
    eq(code(r), "email_failed", r.raw);
  } finally { MAIL_FAIL = false; }
  eq(sql1("select (select count(*) from private.trip_requests)||'/'||(select count(*) from private.mail_log)"), "0/0", "rows/mails left");
});

T("INT-04 [C6] resend: <60 s refused (no mail); after 60 s a new code, the old one is dead, the new one verifies; 4th resend refused", async () => {
  reset(); rtDeps();
  const r = await post(RT.handler, START("int4@example.com"));
  const id = r.body.request_id, c0 = digits(MAILS[0]);
  const e = await post(RT.handler, { action: "resend", request_id: id });
  ok(e.body.ok === false && MAILS.length === 1, "early resend accepted: " + e.raw);
  const age = () => psql(`update private.trip_requests set code_sent_at = now() - interval '61 seconds' where id='${id}'`);
  age();
  const r1 = await post(RT.handler, { action: "resend", request_id: id });
  eq([r1.body.ok, MAILS.length], [true, 2], "resend " + r1.raw);
  const c1 = digits(MAILS[1]);
  if (c1 !== c0) eq(code(await post(RT.handler, { action: "verify", request_id: id, code: c0 })), "code_wrong", "old code still valid");
  age(); await post(RT.handler, { action: "resend", request_id: id });
  age(); const r3 = await post(RT.handler, { action: "resend", request_id: id });
  ok(r3.body.ok === true, "3rd resend " + r3.raw);
  age(); const r4 = await post(RT.handler, { action: "resend", request_id: id });
  ok(r4.body.ok === false, "4th resend accepted: " + r4.raw);
  const last = digits(MAILS[MAILS.length - 1]);
  eq((await post(RT.handler, { action: "verify", request_id: id, code: last })).body.ok, true, "latest code verifies");
});

T("INT-05 [C8] 4th start for one email in a day → rate_limited (DB limits through the function)", async () => {
  reset(); rtDeps();
  const out: string[] = [];
  for (let i = 0; i < 4; i++) out.push(code(await post(RT.handler, START("int5@example.com"), { ip: "198.51.100." + (10 + i) })) || "ok");
  eq(out, ["ok", "ok", "ok", "rate_limited"], "codes");
});

T("INT-06 [C9] cap: 50 mail_log rows today → start and resend → daily_limit; reject with mail → ok, mail_skipped daily_limit", async () => {
  reset(); rtDeps();
  const r = await post(RT.handler, START("int6@example.com"));
  const id = r.body.request_id;
  psql(`insert into private.mail_log(kind) select 'code' from generate_series(1,49); update private.trip_requests set code_sent_at = now()-interval '61 seconds'`);
  eq(code(await post(RT.handler, START("int6b@example.com"), { ip: "198.51.100.99" })), "daily_limit", "start at cap");
  eq(code(await post(RT.handler, { action: "resend", request_id: id })), "daily_limit", "resend at cap");
  psql(`update private.trip_requests set status='pending', verified_at=now(), code_hash=null where id='${id}';
        insert into auth.users(id, email) values ('36000000-0000-4000-8000-000000000001', 'or@example.com');
        insert into public.platform_admins(user_id) values ('36000000-0000-4000-8000-000000000001');`);
  const h = imHandler();
  const j = await post(h.h, { action: "reject_request", request_id: id, send_mail: true }, { jwt: "admin-jwt" });
  eq([j.status, j.body.ok, j.body.mail_skipped, h.mails.length], [200, true, "daily_limit", 0], "reject " + j.raw);
  eq(sql1(`select status from private.trip_requests where id='${id}'`), "rejected", "status");
});

const ADMIN = "37000000-0000-4000-8000-000000000001";
function imHandler(mailFail = false) {
  const mails: Any[] = [];
  const store: Any = {
    isPlatformAdmin: (u: string) => Promise.resolve(sql1(`select count(*) from public.platform_admins where user_id='${u}'`) === "1"),
    inviterName: () => Promise.resolve("אור"),
    findOpenByEmail: () => Promise.resolve(null), getById: () => Promise.resolve(null), findByHash: () => Promise.resolve(null),
    insert: () => Promise.reject(new Error("not used")), deleteById: () => Promise.resolve(), revokeOpen: () => Promise.resolve(0),
    updateOpen: () => Promise.resolve(0), markOpened: () => Promise.resolve(),
  };
  const h = IM.makeHandler({
    store, verifyJwt: (j: string) => Promise.resolve(j === "admin-jwt" ? sql1("select user_id from public.platform_admins limit 1") || null : null),
    sendMail: (m: Any) => (mailFail ? Promise.reject(new Error("smtp qa")) : (mails.push(m), Promise.resolve())),
    now: () => new Date(), random: (n: number) => crypto.getRandomValues(new Uint8Array(n)), appUrl: IM.DEFAULT_APP_URL,
    log: () => {}, rpc: rpcIM,
  });
  return { h, mails };
}
async function pendingRequest(email: string, lang = "en") {
  rtDeps();
  const r = await post(RT.handler, START(email, lang, { name: "Ann" }), { ip: "198.51.100." + Math.floor(Math.random() * 200) });
  const v = await post(RT.handler, { action: "verify", request_id: r.body.request_id, code: digits(MAILS[MAILS.length - 1]) });
  ok(v.body.ok, "fixture verify " + v.raw);
  return r.body.request_id as string;
}
function admin() {
  psql(`insert into auth.users(id, email) values ('${ADMIN}', 'or@example.com'); insert into public.platform_admins(user_id) values ('${ADMIN}');`);
}

T("INT-07 [C12][C13] approve (en) with an active invite: old revoked, one active invite linked to the request (lang en, edited draft), English mail whose token hashes to the stored token_hash", async () => {
  reset(); admin();
  psql("insert into public.manager_invites(id, email, token_hash, expires_at, draft_name) values ('37000000-0000-4000-8000-0000000000dd', 'ann@example.com', repeat('b',64), now()+interval '3 days', 'ישן')");
  const id = await pendingRequest("ann@example.com", "en");
  const x = imHandler();
  const r = await post(x.h, { action: "approve_request", request_id: id, draft_name: "Portugal & Spain" }, { jwt: "admin-jwt" });
  eq([r.status, r.body.ok], [200, true], "approve " + r.raw);
  eq(sql1("select (revoked_at is not null)::text from public.manager_invites where id='37000000-0000-4000-8000-0000000000dd'"), "true", "old revoked");
  const act = sql1("select count(*)||'|'||string_agg(lang||'|'||coalesce(draft_name,'')||'|'||(request_id::text = '" + id + "')::text||'|'||token_hash, ',') from public.manager_invites where email='ann@example.com' and revoked_at is null and used_at is null");
  const [n, lang, draft, linked, th] = act.split("|");
  eq([n, lang, draft, linked], ["1", "en", "Portugal & Spain", "true"], "active invite");
  eq(x.mails.length, 1, "mails");
  eq(x.mails[0].subject, "Your trip request was approved", "English mail");
  const tok = (String(x.mails[0].text).match(/#invite=([A-Za-z0-9_-]{43})/) ?? [])[1];
  eq(th, await sha(tok ?? ""), "token in the mail ↔ token_hash");
  eq(sql1(`select status||'|'||(invite_id is not null)::text from private.trip_requests where id='${id}'`), "approved|true", "request");
});

T("INT-08 [C14] approve with a failing email: no new invite, old invite active again, request still pending, 502 email_failed", async () => {
  reset(); admin();
  psql("insert into public.manager_invites(id, email, token_hash, expires_at) values ('38000000-0000-4000-8000-0000000000dd', 'bob@example.com', repeat('c',64), now()+interval '3 days')");
  const id = await pendingRequest("bob@example.com", "he");
  const x = imHandler(true);
  const r = await post(x.h, { action: "approve_request", request_id: id, draft_name: "x" }, { jwt: "admin-jwt" });
  eq([r.status, code(r)], [502, "email_failed"], r.raw);
  eq(sql1("select count(*)||'|'||string_agg(id::text,',') from public.manager_invites where email='bob@example.com' and revoked_at is null"), "1|38000000-0000-4000-8000-0000000000dd", "active invites");
  eq(sql1("select count(*) from public.manager_invites"), "1", "no new invite row");
  eq(sql1(`select status from private.trip_requests where id='${id}'`), "pending", "request");
});

T("INT-09 [C15] reject with mail (he) → rejected, Hebrew reject mail, reject mail logged; then reject again → request_closed", async () => {
  reset(); admin();
  const id = await pendingRequest("noa@example.com", "he");
  const x = imHandler();
  const r = await post(x.h, { action: "reject_request", request_id: id, send_mail: true }, { jwt: "admin-jwt" });
  eq([r.status, r.body.ok, x.mails.length, x.mails[0]?.subject], [200, true, 1, "הבקשה שלך ל-Lonely Planner"], r.raw);
  eq(sql1(`select status from private.trip_requests where id='${id}'`) + "|" + sql1("select count(*) from private.mail_log where kind='reject'"), "rejected|1", "db");
  const again = await post(x.h, { action: "reject_request", request_id: id, send_mail: true }, { jwt: "admin-jwt" });
  eq([again.status, code(again)], [409, "request_closed"], again.raw);
});

T("INT-10 [C16] create-trip lookup for the approved email (DB find_invite_for_email) returns prefill {name, countries, month, lang}", async () => {
  reset(); admin();
  const id = await pendingRequest("pf@example.com", "en");
  const x = imHandler();
  await post(x.h, { action: "approve_request", request_id: id, draft_name: "Portugal" }, { jwt: "admin-jwt" });
  CT.resetDeps();
  CT.setDeps({
    getUser: () => Promise.resolve({ id: "39000000-0000-4000-8000-000000000001", email: "pf@example.com", email_confirmed_at: new Date().toISOString(), is_anonymous: false }),
    rpc: rpcRT, now: () => Date.now(),
  });
  const r = await post(CT.handler, { action: "lookup" }, { jwt: "j" });
  eq(r.status, 200, r.raw);
  const m = START("x").month;
  eq(r.body.prefill, { name: "Ann", countries: ["PT", "ES"], month: m, lang: "en" }, "prefill");
  eq(r.body.draft_name, "Portugal", "draft");
});
