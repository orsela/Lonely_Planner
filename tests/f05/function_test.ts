// Plan_Travel F05 QA · join-trip + approve-member black-box tests (Deno-style) · version 1.0.0
// CHANGE 2026-10-19 F05-QA-05: first version (no previous version).
//
// Written from docs/F05_spec.md §2–§3 and the two README files (export surface only: handler(req), setDeps({getUser, rpc}),
// resetDeps(), FN_VERSION). The function sources were NOT read. Case ids F5-FN-xx are listed in docs/qa/F05_QA.md.
//
// Run without Deno (sandbox):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        tests/f05/function_test.ts
// With Deno: deno test --no-check --allow-env --allow-read --import-map=supabase/functions/join-trip/test_import_map.json \
//        tests/f05/function_test.ts

// deno-lint-ignore no-explicit-any
type Any = any;
const JT: Any = await import(new URL("../../supabase/functions/join-trip/index.ts", import.meta.url).href);
const AM: Any = await import(new URL("../../supabase/functions/approve-member/index.ts", import.meta.url).href);

const LOGS: string[] = [];
const C: Any = console;
// (re)installed at the start of each test that reads logs: the Node runner swaps console.log per test
function capture() {
  LOGS.length = 0;
  for (const k of ["log", "info", "warn", "error", "debug"]) {
    C[k] = (...a: unknown[]) => {
      LOGS.push(a.map((x) => (typeof x === "string" ? x : (() => { try { return JSON.stringify(x); } catch { return String(x); } })())).join(" "));
    };
  }
}
function ok(c: unknown, msg: string): asserts c {
  if (!c) throw new Error("FAIL: " + msg);
}
function eq<T>(a: T, b: T, msg: string) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`FAIL: ${msg}\n  actual:   ${JSON.stringify(a)}\n  expected: ${JSON.stringify(b)}`);
}

const JWT = "eyJhbGciOiJIUzI1NiJ9.qa-secret-jwt-f05.sig";
const ANON = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", is_anonymous: true, email: "" };
const MGR = { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", is_anonymous: false, email: "dana.secret@example.com" };
const TRIP = "f0500000-0000-4000-8000-000000000001";
const MEMBER = "f0500000-0000-4000-8000-0000000000aa";
const ORIGIN = "https://orsela.github.io";
const IP = "203.0.113.77";
const NAME = "שם-סודי-QA";
const CODE = "X7K2M9QP";
const TCODE = "482916";
type Call = { name: string; args: Record<string, Any> };

function mock(mod: Any, out: Any = {}, user: Any = ANON) {
  mod.resetDeps();
  const calls: Call[] = [];
  mod.setDeps({
    getUser: (jwt: string) => Promise.resolve(jwt === JWT ? user : null),
    rpc: (name: string, args: Record<string, Any>) => {
      calls.push({ name, args: JSON.parse(JSON.stringify(args ?? {})) });
      const o = typeof out === "function" ? out(name, args) : out;
      return Promise.resolve({ data: o, error: null });
    },
  });
  return calls;
}
type Res = { status: number; body: Record<string, Any>; headers: Headers };
async function call(mod: Any, body: unknown, o: { jwt?: string | null; origin?: string; method?: string; ip?: string; raw?: string } = {}): Promise<Res> {
  const h: Record<string, string> = { "Content-Type": "application/json", apikey: "sb_publishable_qa", Origin: o.origin ?? ORIGIN };
  if (o.jwt !== null) h.Authorization = "Bearer " + (o.jwt ?? JWT);
  if (o.ip !== undefined) h["x-forwarded-for"] = o.ip;
  const method = o.method ?? "POST";
  const r = await mod.handler(new Request("https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/x", {
    method, headers: h, body: method === "POST" ? (o.raw ?? JSON.stringify(body)) : undefined,
  }));
  const t = await r.text();
  let j: Record<string, Any> = {};
  try { j = JSON.parse(t); } catch { /* */ }
  return { status: r.status, body: j, headers: r.headers };
}
const errCode = (r: Res) => String(r.body.error ?? r.body.code ?? "");
const T = (name: string, fn: () => Promise<void> | void) => Deno.test({ name, sanitizeOps: false, sanitizeResources: false, fn });
async function sha(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ---------------------------------------------------------------------------------------------------------------
T("F5-FN-01 version alpha.6.0 (FN_VERSION) in both functions", () => {
  ok(/alpha\.6\.0$/.test(String(JT.FN_VERSION)), "join-trip FN_VERSION " + JT.FN_VERSION);
  ok(/alpha\.6\.0$/.test(String(AM.FN_VERSION)), "approve-member FN_VERSION " + AM.FN_VERSION);
});

T("F5-FN-02 §3 'Version header alpha.6.0': responses carry a header whose value names alpha.6.0", async () => {
  mock(JT, { trip_id: TRIP, name: "n", me: null });
  const a = await call(JT, { action: "preview", code: CODE }, { ip: IP });
  mock(AM, { status: "active", member_id: MEMBER, role: "editor" }, MGR);
  const b = await call(AM, { member_id: MEMBER, decision: "approve" });
  for (const [n, r] of [["join-trip", a], ["approve-member", b]] as const) {
    const vals = [...r.headers.entries()].filter(([k, v]) => /alpha\.6\.0/.test(v) || /version/i.test(k));
    ok(vals.some(([, v]) => /alpha\.6\.0/.test(v)), `${n}: no response header carries the version (headers: ${[...r.headers.keys()].join(", ")})`);
  }
});

T("F5-FN-03 auth: no / unknown JWT → 401 unauthorized, no rpc; anonymous identity accepted (join-trip)", async () => {
  let calls = mock(JT, { trip_id: TRIP });
  let r = await call(JT, { action: "preview", code: CODE }, { jwt: null });
  eq([r.status, errCode(r)], [401, "unauthorized"], "no JWT");
  r = await call(JT, { action: "preview", code: CODE }, { jwt: "bogus" });
  eq([r.status, errCode(r)], [401, "unauthorized"], "bad JWT");
  eq(calls.length, 0, "rpc called without a valid identity");
  calls = mock(JT, { trip_id: TRIP, name: "n", me: null }, ANON);
  r = await call(JT, { action: "preview", code: CODE }, { ip: IP });
  eq(r.status, 200, "anonymous preview");
  eq(calls[0]?.args?.p_user, ANON.id, "p_user = caller uid");
  calls = mock(AM, {}, MGR);
  r = await call(AM, { member_id: MEMBER, decision: "approve" }, { jwt: null });
  eq([r.status, errCode(r), calls.length], [401, "unauthorized", 0], "approve-member without JWT");
});

T("F5-FN-04 each join-trip action calls its §2.3 SQL function with the caller's uid (never a uid from the body)", async () => {
  const cases: [Record<string, Any>, string, Record<string, Any>, Any][] = [
    [{ action: "preview", code: CODE, p_user: MGR.id, user_id: MGR.id }, "join_preview", { p_code: CODE }, { trip_id: TRIP, name: "n", me: null }],
    [{ action: "request", code: CODE, display_name: NAME, user_id: MGR.id }, "join_request", { p_code: CODE, p_name: NAME },
     { trip_id: TRIP, member_id: MEMBER, status: "pending", role: "editor", display_name: NAME, created: true }],
    [{ action: "cancel", trip_id: TRIP, user_id: MGR.id }, "join_cancel", { p_trip: TRIP }, { ok: true }],
    [{ action: "issue_transfer", trip_id: TRIP }, "issue_transfer", { p_trip: TRIP }, { code: TCODE, expires_at: "2026-10-20T06:00:00Z" }],
    [{ action: "claim_transfer", code: "482 916" }, "claim_transfer", {}, { trip_id: TRIP, member_id: MEMBER, role: "editor", display_name: NAME }],
  ];
  for (const [body, fn, args, out] of cases) {
    const calls = mock(JT, out);
    const r = await call(JT, body, { ip: IP });
    ok(r.status === 200, `${body.action}: status ${r.status} ${JSON.stringify(r.body)}`);
    eq(calls.map((c) => c.name), [fn], `${body.action}: rpc`);
    eq(calls[0].args.p_user, ANON.id, `${body.action}: p_user`);
    for (const [k, v] of Object.entries(args)) eq(calls[0].args[k], v, `${body.action}: ${k}`);
  }
  // a whole link / lower case / spaces are accepted for preview (spec §1.4 "paste the link or the 8-char code")
  for (const v of ["https://orsela.github.io/Lonely_Planner/join/#code=x7k2m9qp", " x7k2 m9qp "]) {
    const calls = mock(JT, { trip_id: TRIP, name: "n", me: null });
    const r = await call(JT, { action: "preview", code: v }, { ip: IP });
    eq([r.status, calls[0]?.args?.p_code], [200, CODE], "normalised code for " + v);
  }
});

T("F5-FN-05 ip_hash: SHA-256 hex of the FIRST x-forwarded-for address; the raw address never reaches the database or logs", async () => {
  capture();
  let calls = mock(JT, { trip_id: TRIP, name: "n", me: null });
  await call(JT, { action: "preview", code: CODE }, { ip: IP + ", 10.0.0.1" });
  const h1 = calls[0].args.p_ip;
  ok(/^[0-9a-f]{64}$/.test(String(h1)), "p_ip is not a SHA-256 hex: " + h1);
  ok(!JSON.stringify(calls).includes(IP), "raw IP passed to the database");
  calls = mock(JT, { trip_id: TRIP, name: "n", me: null });
  await call(JT, { action: "preview", code: CODE }, { ip: IP });
  eq(calls[0].args.p_ip, h1, "same first address → same hash (only the first address counts)");
  calls = mock(JT, { trip_id: TRIP, name: "n", me: null });
  await call(JT, { action: "preview", code: CODE }, { ip: "198.51.100.1" });
  ok(calls[0].args.p_ip !== h1, "different address → different hash");
  ok(h1 !== await sha("10.0.0.1"), "hash uses the last address");
  ok(!LOGS.some((l) => l.includes(IP)), "raw IP logged");
});

T("F5-FN-06 refusals: SQL {error:code} → the code with the README status (code_invalid 404, name_taken 409, rate_limited 429, …)", async () => {
  const map: [string, number, Record<string, Any>][] = [
    ["code_invalid", 404, { action: "preview", code: CODE }], ["name_taken", 409, { action: "request", code: CODE, display_name: NAME }],
    ["name_invalid", 400, { action: "request", code: CODE, display_name: NAME }], ["rate_limited", 429, { action: "request", code: CODE, display_name: NAME }],
    ["member_removed", 403, { action: "request", code: CODE, display_name: NAME }], ["not_pending", 409, { action: "cancel", trip_id: TRIP }],
    ["not_member", 403, { action: "issue_transfer", trip_id: TRIP }], ["transfer_invalid", 409, { action: "claim_transfer", code: TCODE }],
    ["already_member", 409, { action: "claim_transfer", code: TCODE }],
  ];
  for (const [code, st, body] of map) {
    mock(JT, { error: code }, ANON);   // the SQL function RETURNS {"error":code} as data (spec §2.3)
    const r = await call(JT, body, { ip: IP });
    eq([r.status, errCode(r)], [st, code], "join-trip " + code);
  }
  for (const [code, st] of [["not_manager", 403], ["not_pending", 409], ["role_invalid", 400]] as const) {
    mock(AM, { error: code }, MGR);
    const r = await call(AM, { member_id: MEMBER, decision: "approve", role: "editor" });
    eq([r.status, errCode(r)], [st, code], "approve-member " + code);
  }
});

T("F5-FN-07 database failure → 5xx, no secret in the body", async () => {
  JT.resetDeps();
  JT.setDeps({ getUser: () => Promise.resolve(ANON), rpc: () => Promise.resolve({ data: null, error: { code: "57014", message: "statement timeout " + NAME } }) });
  const r = await call(JT, { action: "request", code: CODE, display_name: NAME }, { ip: IP });
  ok(r.status >= 500, "status " + r.status);
  ok(!JSON.stringify(r.body).includes(NAME), "db message leaked to the client");
});

T("F5-FN-08 bad requests: unknown action / bad JSON / missing fields → 400 invalid_request without a database call", async () => {
  for (const [body, raw] of [[{ action: "drop" }, undefined], [null, "{not json"], [{ action: "cancel" }, undefined],
                             [{ action: "issue_transfer", trip_id: "nope" }, undefined], [{ action: "preview" }, undefined]] as const) {
    const calls = mock(JT, {});
    const r = await call(JT, body, { ip: IP, raw: raw as Any });
    ok(r.status === 400 || r.status === 404, `status ${r.status} for ${raw ?? JSON.stringify(body)}`);
    ok(["invalid_request", "code_invalid"].includes(errCode(r)), `code ${errCode(r)} for ${raw ?? JSON.stringify(body)}`);
    eq(calls.length, 0, "db called for an invalid request " + (raw ?? JSON.stringify(body)));
  }
  for (const body of [{ member_id: "x", decision: "approve" }, { member_id: MEMBER, decision: "maybe" }, { decision: "approve" }]) {
    const calls = mock(AM, {}, MGR);
    const r = await call(AM, body);
    eq([r.status, errCode(r), calls.length], [400, "invalid_request", 0], "approve-member " + JSON.stringify(body));
  }
});

T("F5-FN-09 approve-member: decision + role passed to approve_member; no role → null (trip default in SQL); reject ignores role", async () => {
  let calls = mock(AM, { status: "active", member_id: MEMBER, role: "viewer", display_name: "x", trip_id: TRIP }, MGR);
  let r = await call(AM, { member_id: MEMBER, decision: "approve", role: "viewer" });
  eq(r.status, 200, "approve status");
  eq([calls[0].name, calls[0].args.p_user, calls[0].args.p_member, calls[0].args.p_decision, calls[0].args.p_role],
     ["approve_member", MGR.id, MEMBER, "approve", "viewer"], "approve args");
  calls = mock(AM, { status: "active", member_id: MEMBER, role: "editor" }, MGR);
  await call(AM, { member_id: MEMBER, decision: "approve" });
  eq(calls[0].args.p_role ?? null, null, "default role");
  calls = mock(AM, { status: "rejected", member_id: MEMBER }, MGR);
  r = await call(AM, { member_id: MEMBER, decision: "reject", role: "manager" });
  eq([r.status, calls[0].args.p_decision], [200, "reject"], "reject");
  ok(calls[0].args.p_role == null || calls[0].args.p_role === "manager", "reject role arg");
});

T("F5-FN-10 CORS: app origin echoed, OPTIONS 204, foreign origin not allowed, GET 405", async () => {
  for (const mod of [JT, AM]) {
    mock(mod, {});
    let r = await call(mod, {}, { method: "OPTIONS" });
    eq([r.status, r.headers.get("access-control-allow-origin")], [204, ORIGIN], "preflight");
    ok(/authorization/i.test(r.headers.get("access-control-allow-headers") || "") && /apikey/i.test(r.headers.get("access-control-allow-headers") || ""), "allow-headers");
    r = await call(mod, {}, { method: "OPTIONS", origin: "https://evil.example" });
    ok(r.headers.get("access-control-allow-origin") !== "https://evil.example" && r.headers.get("access-control-allow-origin") !== "*", "foreign origin allowed");
    r = await call(mod, {}, { method: "GET" });
    eq(r.status, 405, "GET");
  }
});

T("F5-FN-11 logs never contain the JWT, join code, transfer code, display name, email or raw IP", async () => {
  capture();
  mock(JT, { trip_id: TRIP, member_id: MEMBER, status: "pending", role: "editor", display_name: NAME, created: true });
  await call(JT, { action: "request", code: CODE, display_name: NAME }, { ip: IP });
  mock(JT, { trip_id: TRIP, member_id: MEMBER, role: "editor", display_name: NAME });
  await call(JT, { action: "claim_transfer", code: TCODE }, { ip: IP });
  mock(JT, { code: TCODE, expires_at: "2026-10-20T06:00:00Z" });
  await call(JT, { action: "issue_transfer", trip_id: TRIP }, { ip: IP });
  mock(AM, { status: "active", member_id: MEMBER, role: "editor", display_name: NAME }, MGR);
  await call(AM, { member_id: MEMBER, decision: "approve" });
  ok(LOGS.length > 0, "nothing logged at all (expected action/status lines)");
  for (const s of [JWT, CODE, TCODE, NAME, MGR.email, IP]) ok(!LOGS.some((l) => l.includes(s)), "secret in logs: " + s);
});

T("F5-FN-12 success bodies pass the SQL result through (preview fields, request member_id/status, issue code)", async () => {
  const pv = { trip_id: TRIP, name: "יפן 2027", start_date: "2027-04-03", end_date: "2027-04-20", days: 18, members: 4, manager: "דנה", me: null };
  mock(JT, pv);
  let r = await call(JT, { action: "preview", code: CODE }, { ip: IP });
  for (const k of Object.keys(pv)) eq(r.body[k], (pv as Any)[k], "preview." + k);
  mock(JT, { code: TCODE, expires_at: "2026-10-20T06:00:00Z" });
  r = await call(JT, { action: "issue_transfer", trip_id: TRIP }, { ip: IP });
  eq([r.status, r.body.code], [200, TCODE], "issue_transfer code");
});
