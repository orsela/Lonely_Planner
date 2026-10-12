// Plan_Travel F04 QA · create-trip + invite-manager black-box tests (Deno) · version 1.1.0
// CHANGE 2026-10-12 F04-QA: first version (no previous version).
// CHANGE 2026-10-12 F04-QA-05: 1.0.0 → 1.1.0, alpha.4.2 (spec §8/§8.1): defaults moved to /Lonely_Planner/ (DEFAULT_JOIN,
//   DEFAULT_APP, the IM-02 email-link check now expects /Lonely_Planner/invite/#invite=…); new NAME-01..03 cases (email
//   subject / sender name / HTML+text say "Lonely Planner" and never "Plan_Travel"; default invite link; create-trip
//   default join_url).
//
// Written from docs/F04_spec.md §3 / §5 and supabase/functions/create-trip/README.md (export surface only). The function
// sources (create-trip/index.ts) were NOT read. Case ids match tests/f04/function_cases.md.
//
// Seams used (documented):
// - create-trip: `handler(req)`, `setDeps({getUser, rpc, now})`, `resetDeps()`, `FN_VERSION` (README "Testability").
//   getUser(jwt) → user | null; rpc(name, args) → {data, error} (PostgREST shape); now() → epoch ms.
// - invite-manager: `makeHandler(deps)` with `Deps {store, verifyJwt, sendMail, now, random, appUrl, log}`,
//   `resolveAppUrl(v)`, `DEFAULT_APP_URL`, `FN_VERSION` (exported types of index.ts).
// - JOIN_URL is an environment secret: every JOIN_URL case loads a FRESH copy of the module (`index.ts?case=N`) after
//   setting the variable, so the cases hold whether the module reads it at load time or per request.
//
// Run (offline, stub for supabase-js):
//   deno test --no-check --allow-env --allow-read \
//     --import-map=supabase/functions/create-trip/test_import_map.json tests/f04/function_test.ts

const CT_PATH = new URL("../../supabase/functions/create-trip/index.ts", import.meta.url).href;
const IM_PATH = new URL("../../supabase/functions/invite-manager/index.ts", import.meta.url).href;
// CHANGE 2026-10-12 F04-QA-05: new address (spec §8.1); was https://orsela.github.io/Plan_Travel/{join,app}/
const DEFAULT_JOIN = "https://orsela.github.io/Lonely_Planner/join/";
const DEFAULT_APP = "https://orsela.github.io/Lonely_Planner/app/";
const DEFAULT_INVITE = "https://orsela.github.io/Lonely_Planner/invite/";
const APP_NAME = "Lonely Planner";
const OLD_NAMES = [/Plan_Travel/, /Vietnam Travel Planner/, /ויאטנם 2026/];
const ORIGIN = "https://orsela.github.io";

// deno-lint-ignore no-explicit-any
type Any = any;
let seq = 0;
async function loadCT(joinUrl?: string | null): Promise<Any> {
  if (joinUrl === undefined || joinUrl === null) Deno.env.delete("JOIN_URL");
  else Deno.env.set("JOIN_URL", joinUrl);
  return await import(`${CT_PATH}?case=${++seq}`);
}
const CT: Any = await loadCT(null);
const IM: Any = await import(IM_PATH);

// ---------------------------------------------------------------------------------------------------------------
// assert helpers
// ---------------------------------------------------------------------------------------------------------------
function ok(c: unknown, msg: string): asserts c {
  if (!c) throw new Error("FAIL: " + msg);
}
function eq<T>(a: T, b: T, msg: string) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`FAIL: ${msg}\n  actual:   ${JSON.stringify(a)}\n  expected: ${JSON.stringify(b)}`);
}
async function sha256hex(s: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const T = (name: string, fn: () => Promise<void> | void) =>
  Deno.test({ name, sanitizeOps: false, sanitizeResources: false, fn });

// ---------------------------------------------------------------------------------------------------------------
// console capture (logs must never contain the JWT, email or names)
// ---------------------------------------------------------------------------------------------------------------
const LOGS: string[] = [];
const C: Any = console;
for (const k of ["log", "info", "warn", "error", "debug"]) {
  const orig = C[k].bind(console);
  C[k] = (...a: unknown[]) => {
    LOGS.push(a.map((x) => (typeof x === "string" ? x : (() => { try { return JSON.stringify(x); } catch { return String(x); } })())).join(" "));
    if (Deno.env.get("QA_VERBOSE")) orig(...a);
  };
}

// ---------------------------------------------------------------------------------------------------------------
// create-trip fixtures
// ---------------------------------------------------------------------------------------------------------------
const JWT = "eyJhbGciOiJIUzI1NiJ9.qa-secret-jwt-f04.sig";
const JWT_B = "eyJhbGciOiJIUzI1NiJ9.qa-secret-jwt-b.sig";
const VERIFIED = { id: "11111111-1111-4111-8111-111111111111", email: "dana.secret@example.com", email_confirmed_at: "2026-10-12T06:00:00Z", is_anonymous: false };
const VERIFIED_B = { id: "22222222-2222-4222-8222-222222222222", email: "bob.secret@example.com", email_confirmed_at: "2026-10-12T06:00:00Z", is_anonymous: false };
const ANON = { id: "33333333-3333-4333-8333-333333333333", email: "", email_confirmed_at: null, is_anonymous: true };
const UNCONFIRMED = { id: "44444444-4444-4444-8444-444444444444", email: "pending.secret@example.com", email_confirmed_at: null, is_anonymous: false, new_email: "pending.secret@example.com" };

const PAYLOAD = {
  name: "טיול-סודי-QA", display_name: "שם-סודי-QA", start_date: "2027-04-03", end_date: "2027-04-20",
  home_currency: "ILS", default_lang: "he", default_role: "editor", countries: ["JP", "KR"],
  currencies: [{ code: "JPY", kind: "destination" }, { code: "KRW", kind: "destination" }], center: { lat: 35.68, lng: 139.69 },
};
const SECRETS = [JWT, JWT_B, VERIFIED.email, VERIFIED_B.email, UNCONFIRMED.email, PAYLOAD.name, PAYLOAD.display_name, "יפן 2027", "אור-מזמין"];

type Call = { name: string; args: Record<string, Any> };
type RpcImpl = (name: string, args: Record<string, Any>) => Any;
const FOUND = { found: true, invite_id: "9e0d6c1a-0000-4000-8000-00000000abcd", draft_name: "יפן 2027", inviter_name: "אור-מזמין",
  expires_at: "2026-10-19T06:00:00Z", email: VERIFIED.email, token_hash: "f".repeat(64) };
const CREATED = { trip_id: "5b1c1e9e-0000-4000-8000-000000000001", join_code: "X7K2M9QP", created: true };

function mock(mod: Any, users: Record<string, Any> = { [JWT]: VERIFIED }, rpcImpl?: RpcImpl) {
  mod.resetDeps();
  const calls: Call[] = [];
  const clock = { t: Date.parse("2026-10-12T06:00:00Z") };
  mod.setDeps({
    getUser: (jwt: string) => Promise.resolve(users[jwt] ?? null),
    rpc: (name: string, args: Record<string, Any>) => {
      calls.push({ name, args: JSON.parse(JSON.stringify(args ?? {})) });
      const out = rpcImpl ? rpcImpl(name, args) : name === "find_invite_for_email" ? { data: FOUND, error: null }
        : name === "create_trip_from_invite" ? { data: { ...CREATED }, error: null }
        : { data: null, error: { code: "PGRST202", message: "not found" } };
      return Promise.resolve(out);
    },
    now: () => clock.t,
  });
  return { calls, clock };
}
type Res = { status: number; body: Record<string, Any>; raw: string; headers: Headers };
async function ct(mod: Any, body: unknown, jwt: string | null = JWT, opt: { origin?: string; method?: string; rawBody?: string } = {}): Promise<Res> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Origin: opt.origin ?? ORIGIN, apikey: "sb_publishable_qa" };
  if (jwt) headers.Authorization = "Bearer " + jwt;
  const method = opt.method ?? "POST";
  const req = new Request("https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/create-trip", {
    method, headers, body: method === "GET" || method === "OPTIONS" ? undefined : (opt.rawBody ?? JSON.stringify(body)),
  });
  const r = await mod.handler(req);
  const raw = await r.text();
  let parsed: Record<string, Any> = {};
  try { parsed = JSON.parse(raw); } catch { /* not json */ }
  return { status: r.status, body: parsed, raw, headers: r.headers };
}
const code = (r: Res) => String(r.body.error ?? r.body.code ?? "");
const create = (mod: Any, extra: Record<string, unknown> = {}, jwt: string | null = JWT) => ct(mod, { action: "create", ...PAYLOAD, ...extra }, jwt);
const lookup = (mod: Any, jwt: string | null = JWT) => ct(mod, { action: "lookup" }, jwt);

// ---------------------------------------------------------------------------------------------------------------
// CT · create-trip
// ---------------------------------------------------------------------------------------------------------------
T("CT-00 export surface: handler / setDeps / resetDeps / FN_VERSION 3.0.0-alpha.4.x", () => {
  for (const k of ["handler", "setDeps", "resetDeps"]) ok(typeof CT[k] === "function", `export ${k} missing`);
  ok(/^3\.0\.0-alpha\.4(\.\d+)?$/.test(String(CT.FN_VERSION)), "FN_VERSION is not 3.0.0-alpha.4.x: " + CT.FN_VERSION);
});

T("CT-01 no Authorization / unknown JWT → 401|403, no data, rpc never called", async () => {
  const { calls } = mock(CT);
  for (const jwt of [null, "not.a.jwt"]) {
    for (const action of ["lookup", "create"]) {
      const r = await ct(CT, { action, ...PAYLOAD }, jwt);
      ok(r.status === 401 || r.status === 403, `${action} jwt=${jwt}: status ${r.status} ${r.raw}`);
      ok(!("found" in r.body) && !("trip_id" in r.body) && !("draft_name" in r.body), "data returned without a valid JWT: " + r.raw);
    }
  }
  eq(calls.length, 0, "rpc called without a valid JWT");
});

T("CT-02 anonymous user (no email) → 403 email_not_verified for lookup and create; nothing written", async () => {
  const { calls } = mock(CT, { [JWT]: ANON });
  for (const r of [await lookup(CT), await create(CT)]) {
    eq([r.status, code(r)], [403, "email_not_verified"], "anonymous");
  }
  eq(calls.length, 0, "rpc called for an anonymous user");
});

T("CT-03 email set but not confirmed (email_confirmed_at null) → 403 email_not_verified; nothing written", async () => {
  const { calls } = mock(CT, { [JWT]: UNCONFIRMED });
  for (const r of [await lookup(CT), await create(CT)]) {
    eq([r.status, code(r)], [403, "email_not_verified"], "unconfirmed");
  }
  const { calls: c2 } = mock(CT, { [JWT]: { ...VERIFIED, email: "" } });
  const r2 = await create(CT);
  eq([r2.status, code(r2)], [403, "email_not_verified"], "confirmed_at but empty email");
  eq(calls.length + c2.length, 0, "rpc called for an unverified user");
});

T("CT-10 lookup found → exactly {found, draft_name, inviter_name, expires_at}; no ids / token / email echo", async () => {
  const { calls } = mock(CT);
  const r = await lookup(CT);
  eq(r.status, 200, "status " + r.raw);
  eq(Object.keys(r.body).sort(), ["draft_name", "expires_at", "found", "inviter_name"], "lookup keys");
  eq([r.body.found, r.body.draft_name, r.body.inviter_name, r.body.expires_at], [true, FOUND.draft_name, FOUND.inviter_name, FOUND.expires_at], "values");
  for (const leak of [FOUND.invite_id, VERIFIED.email, VERIFIED.id, FOUND.token_hash, "token"]) ok(!r.raw.includes(leak), `lookup leaks ${leak}: ${r.raw}`);
  eq(calls.map((c) => c.name), ["find_invite_for_email"], "rpc");
  eq(calls[0].args.p_email, VERIFIED.email, "find_invite_for_email p_email = the JWT user's email");
});

T("CT-11 lookup not found → exactly {found:false}", async () => {
  mock(CT, undefined, () => ({ data: { found: false }, error: null }));
  const r = await lookup(CT);
  eq([r.status, r.body], [200, { found: false }], "not found");
});

T("CT-12 lookup / create ignore an email or user id in the body (identity comes from the JWT only)", async () => {
  const { calls } = mock(CT);
  await ct(CT, { action: "lookup", email: "evil@example.com", p_email: "evil@example.com" });
  await create(CT, { email: "evil@example.com", p_user: VERIFIED_B.id, user_id: VERIFIED_B.id, p_email: "evil@example.com" });
  eq(calls[0].args.p_email, VERIFIED.email, "lookup used a body email");
  const c = calls.find((x) => x.name === "create_trip_from_invite")!;
  ok(c, "create_trip_from_invite not called");
  eq([c.args.p_user, c.args.p_email], [VERIFIED.id, VERIFIED.email], "create used a body identity");
});

T("CT-20 create → rpc create_trip_from_invite(p_user, p_email, p_payload) and 200 {trip_id, join_code, join_url, created}", async () => {
  const { calls } = mock(CT);
  const r = await create(CT);
  eq(r.status, 200, "status " + r.raw);
  eq(calls.length, 1, "rpc calls");
  eq(calls[0].name, "create_trip_from_invite", "rpc name");
  eq([calls[0].args.p_user, calls[0].args.p_email], [VERIFIED.id, VERIFIED.email], "identity args");
  const p = calls[0].args.p_payload ?? {};
  for (const k of Object.keys(PAYLOAD)) eq(p[k], (PAYLOAD as Any)[k], `p_payload.${k} forwarded`);
  ok(!("action" in p) || p.action === "create", "p_payload carries an unexpected action");
  eq(Object.keys(r.body).sort(), ["created", "join_code", "join_url", "trip_id"], "response keys");
  eq([r.body.trip_id, r.body.join_code, r.body.created], [CREATED.trip_id, CREATED.join_code, true], "values");
  eq(r.body.join_url, DEFAULT_JOIN + "#code=" + CREATED.join_code, "join_url (JOIN_URL unset → default)");
  ok(!r.raw.includes(VERIFIED.email), "create response echoes the email");
});

T("CT-21 idempotent retry: created:false from the DB is passed through with the same trip and URL", async () => {
  mock(CT, undefined, (n) => n === "create_trip_from_invite" ? { data: { ...CREATED, created: false }, error: null } : { data: FOUND, error: null });
  const r = await create(CT);
  eq([r.status, r.body.trip_id, r.body.join_code, r.body.created], [200, CREATED.trip_id, CREATED.join_code, false], "retry");
  eq(r.body.join_url, DEFAULT_JOIN + "#code=" + CREATED.join_code, "join_url on retry");
});

T("CT-22 invite_invalid (P0001) → 409 invite_invalid, no trip data", async () => {
  mock(CT, undefined, () => ({ data: null, error: { code: "P0001", message: "invite_invalid", details: null, hint: null } }));
  const r = await create(CT);
  eq([r.status, code(r)], [409, "invite_invalid"], "invite_invalid");
  ok(!("trip_id" in r.body) && !("join_url" in r.body), "trip data on 409: " + r.raw);
});

T("CT-23 invalid_payload (detail names the field) → 400 invalid_payload {field}", async () => {
  for (const field of ["name", "display_name", "start_date", "end_date", "home_currency", "default_lang", "default_role", "countries", "currencies", "center"]) {
    mock(CT, undefined, () => ({ data: null, error: { code: "P0001", message: "invalid_payload", details: field, hint: null } }));
    const r = await create(CT);
    eq([r.status, code(r), r.body.field], [400, "invalid_payload", field], "invalid_payload " + field);
  }
});

T("CT-24 too_many_currencies → 400 too_many_currencies", async () => {
  mock(CT, undefined, () => ({ data: null, error: { code: "P0001", message: "too_many_currencies", details: null, hint: null } }));
  const r = await create(CT);
  eq([r.status, code(r)], [400, "too_many_currencies"], "too_many_currencies");
});

T("CT-25 unexpected DB error → 5xx, no DB message leaked; a thrown rpc too", async () => {
  mock(CT, undefined, () => ({ data: null, error: { code: "XX000", message: "internal secret detail xyz", details: "secret", hint: null } }));
  const r = await create(CT);
  ok(r.status >= 500, "status " + r.status);
  ok(!r.raw.includes("secret detail xyz"), "DB error text leaked: " + r.raw);
  mock(CT, undefined, () => { throw new Error("boom secret"); });
  const r2 = await create(CT);
  ok(r2.status >= 500 && !r2.raw.includes("boom secret"), "thrown rpc: " + r2.status + " " + r2.raw);
});

T("CT-30 rate limit: 10 create per 10 min per user → 11th 429 rate_limited; other user and lookup unaffected; window slides", async () => {
  const { calls, clock } = mock(CT, { [JWT]: VERIFIED, [JWT_B]: VERIFIED_B });
  for (let i = 0; i < 10; i++) eq((await create(CT)).status, 200, `create #${i + 1}`);
  const n = calls.length;
  const r = await create(CT);
  eq([r.status, code(r)], [429, "rate_limited"], "11th create");
  eq(calls.length, n, "rpc called for a rate-limited request");
  eq((await create(CT, {}, JWT_B)).status, 200, "another user is limited by the first user's calls");
  eq((await lookup(CT)).status, 200, "lookup limited by create calls");
  clock.t += 10 * 60_000 + 1000;
  eq((await create(CT)).status, 200, "window does not slide after 10 minutes");
});

T("CT-31 rate limit: 30 lookup per 10 min per user → 31st 429 rate_limited", async () => {
  const { clock } = mock(CT);
  for (let i = 0; i < 30; i++) eq((await lookup(CT)).status, 200, `lookup #${i + 1}`);
  const r = await lookup(CT);
  eq([r.status, code(r)], [429, "rate_limited"], "31st lookup");
  eq((await create(CT)).status, 200, "create limited by lookup calls");
  clock.t += 10 * 60_000 + 1000;
  eq((await lookup(CT)).status, 200, "lookup window does not slide");
});

T("CT-32 resetDeps clears the rate limiter", async () => {
  mock(CT);
  for (let i = 0; i < 10; i++) await create(CT);
  eq((await create(CT)).status, 429, "harness: limit not reached");
  mock(CT);
  eq((await create(CT)).status, 200, "limit kept after resetDeps");
});

T("CT-40 CORS identical to invite-manager: app origin + localhost echoed; foreign origins not; on POST too", async () => {
  mock(CT);
  for (const o of ["https://orsela.github.io", "http://localhost:5173", "http://localhost:8080", "http://localhost"]) {
    const pre = await ct(CT, null, null, { origin: o, method: "OPTIONS" });
    ok(pre.status < 300, `preflight ${o}: ${pre.status}`);
    eq(pre.headers.get("access-control-allow-origin"), o, "preflight allow-origin " + o);
    const im = IM.corsHeaders(o)["Access-Control-Allow-Origin"] ?? IM.corsHeaders(o)["access-control-allow-origin"];
    eq(pre.headers.get("access-control-allow-origin"), im ?? null, "differs from invite-manager for " + o);
    const post = await lookup(CT);
    eq(post.headers.get("access-control-allow-origin"), ORIGIN, "POST response allow-origin");
  }
  for (const o of ["https://evil.example", "https://orsela.github.io.evil.example", "http://localhost.evil.example", "null"]) {
    const pre = await ct(CT, null, null, { origin: o, method: "OPTIONS" });
    const ao = pre.headers.get("access-control-allow-origin");
    ok(ao !== o && ao !== "*", `origin ${o} allowed (${ao})`);
  }
  const pre = await ct(CT, null, null, { method: "OPTIONS" });
  const ah = (pre.headers.get("access-control-allow-headers") ?? "").toLowerCase();
  for (const h of ["authorization", "apikey", "content-type"]) ok(ah.includes(h), "Allow-Headers lacks " + h + ": " + ah);
});

T("CT-41 bad requests: GET 405, unknown action / no action / bad JSON → 4xx (never 5xx), no rpc", async () => {
  const { calls } = mock(CT);
  const g = await ct(CT, null, JWT, { method: "GET" });
  eq(g.status, 405, "GET");
  for (const b of [{ action: "nope" }, {}, { action: "" }]) {
    const r = await ct(CT, b);
    ok(r.status >= 400 && r.status < 500, `${JSON.stringify(b)} → ${r.status}`);
  }
  const bad = await ct(CT, null, JWT, { rawBody: "{not json" });
  ok(bad.status >= 400 && bad.status < 500, "bad JSON → " + bad.status);
  eq(calls.length, 0, "rpc called for a bad request");
});

const JOIN_CASES: [string | null, string][] = [
  [null, DEFAULT_JOIN],
  ["https://example.org/qa/join/", "https://example.org/qa/join/"],
  ["ttps://orsela.github.io/Plan_Travel/join/", DEFAULT_JOIN],
  ["http://orsela.github.io/Plan_Travel/join/", DEFAULT_JOIN],
  ["https://orsela.github.io/Plan_Travel/join", DEFAULT_JOIN],
  ["", DEFAULT_JOIN],
  ["not a url", DEFAULT_JOIN],
  ["https://", DEFAULT_JOIN],
  // note: "https:///x/" is NOT a case — the WHATWG parser reads it as host "x", which satisfies the spec rule.
];
T("CT-50 JOIN_URL: used only when https:// + host + trailing '/'; otherwise the default; value never logged", async () => {
  const problems: string[] = [];
  for (const [v, want] of JOIN_CASES) {
    const mod = await loadCT(v);
    mock(mod);
    const before = LOGS.length;
    const r = await create(mod);
    const got = String(r.body.join_url ?? "");
    if (got !== want + "#code=" + CREATED.join_code) problems.push(`JOIN_URL=${JSON.stringify(v)} → ${got} (want ${want}#code=…)`);
    const logged = LOGS.slice(before).join("\n");
    if (v && want === DEFAULT_JOIN && logged.includes(v)) problems.push(`JOIN_URL value logged: ${v}`);
  }
  await loadCT(null);
  ok(!problems.length, problems.join("\n"));
});

T("CT-60 logs never contain the JWT, email, names or payload; one line per request at most action/status/code", async () => {
  const before = LOGS.length;
  mock(CT, { [JWT]: VERIFIED, [JWT_B]: ANON });
  await lookup(CT);
  await create(CT);
  await create(CT, {}, JWT_B);
  mock(CT, undefined, () => ({ data: null, error: { code: "P0001", message: "invalid_payload", details: "name", hint: null } }));
  await create(CT);
  mock(CT, undefined, () => ({ data: null, error: { code: "P0001", message: "invite_invalid", details: null, hint: null } }));
  await create(CT);
  mock(CT, undefined, () => ({ data: null, error: { code: "XX000", message: "dana.secret@example.com failed", details: null, hint: null } }));
  await create(CT);
  const out = LOGS.slice(before).join("\n");
  const leaks = SECRETS.filter((s) => out.includes(s));
  ok(!leaks.length, "secrets in the logs: " + JSON.stringify(leaks) + "\n" + out.slice(0, 800));
  ok(!/eyJ[A-Za-z0-9_-]{5,}/.test(out), "something JWT-shaped in the logs");
  ok(!/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(out), "an email address in the logs");
});

// ---------------------------------------------------------------------------------------------------------------
// IM · invite-manager alpha.4 additions (APP_URL hardening, check.email)
// ---------------------------------------------------------------------------------------------------------------
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
      rows.push({ id, used_at: null, revoked_at: null, opened_at: null, created_at: new Date().toISOString(), ...row });
      return Promise.resolve(id);
    },
    deleteById: (id: string) => { const i = rows.findIndex((r) => r.id === id); if (i >= 0) rows.splice(i, 1); return Promise.resolve(); },
    revokeOpen: (id: string, at: string) => { const r = rows.find((x) => x.id === id && open(x)); if (r) r.revoked_at = at; return Promise.resolve(r ? 1 : 0); },
    updateOpen: (id: string, f: Row) => { const r = rows.find((x) => x.id === id && open(x)); if (r) Object.assign(r, f); return Promise.resolve(r ? 1 : 0); },
    markOpened: (id: string, at: string) => { const r = rows.find((x) => x.id === id); if (r && !r.opened_at) r.opened_at = at; return Promise.resolve(); },
  };
}
const NOW = new Date("2026-10-12T06:00:00Z");
function imDeps(appUrl: string, rows: Row[] = []) {
  const mails: Any[] = [];
  const logs: string[] = [];
  const deps = {
    store: memStore(rows),
    verifyJwt: (j: string) => Promise.resolve(j === "admin-jwt" ? "admin-uid" : null),
    sendMail: (m: Any) => { mails.push(m); return Promise.resolve(); },
    now: () => NOW,
    random: (n: number) => crypto.getRandomValues(new Uint8Array(n)),
    appUrl,
    log: (event: string, fields?: Record<string, unknown>) => { logs.push(event + " " + JSON.stringify(fields ?? {})); },
  };
  return { deps, mails, logs, rows };
}
async function im(h: (r: Request) => Promise<Response>, body: unknown, jwt: string | null = null): Promise<Res> {
  const headers: Record<string, string> = { "Content-Type": "application/json", Origin: ORIGIN };
  if (jwt) headers.Authorization = "Bearer " + jwt;
  const r = await h(new Request("https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/invite-manager", { method: "POST", headers, body: JSON.stringify(body) }));
  const raw = await r.text();
  let parsed: Record<string, Any> = {};
  try { parsed = JSON.parse(raw); } catch { /* */ }
  return { status: r.status, body: parsed, raw, headers: r.headers };
}
function linkOf(m: Any): string {
  const s = `${m.text ?? ""}\n${m.html ?? ""}`;
  const x = s.match(/(\S*)#invite=([A-Za-z0-9_-]{43})/);
  ok(x, "no #invite=<token> link in the email");
  return x![0].replace(/^.*?(h?t?tps?:\/\/)/, "$1").replace(/^href=["']?/, "");
}

T("IM-00 version 3.0.0-alpha.4.x; DEFAULT_APP_URL unchanged", () => {
  ok(/^3\.0\.0-alpha\.4(\.\d+)?$/.test(String(IM.FN_VERSION)), "invite-manager FN_VERSION: " + IM.FN_VERSION);
  eq(IM.DEFAULT_APP_URL, DEFAULT_APP, "DEFAULT_APP_URL");
});

T("IM-01 resolveAppUrl: ttps://, http://, empty, not-a-URL, empty host → default (fallback); valid https kept; unset → default", () => {
  const cases: [string | undefined | null, string, boolean | null][] = [
    ["ttps://orsela.github.io/Plan_Travel/app/", DEFAULT_APP, true],
    ["http://orsela.github.io/Plan_Travel/app/", DEFAULT_APP, true],
    ["", DEFAULT_APP, true],
    ["not a url", DEFAULT_APP, true],
    ["https://", DEFAULT_APP, true],
    ["  ", DEFAULT_APP, true],
    ["https://example.org/qa/app/", "https://example.org/qa/app/", false],
    [undefined, DEFAULT_APP, null],
  ];
  const bad: string[] = [];
  for (const [v, url, fb] of cases) {
    const r = IM.resolveAppUrl(v);
    if (r.url !== url) bad.push(`${JSON.stringify(v)} → url ${r.url}, want ${url}`);
    if (fb !== null && r.fallback !== fb) bad.push(`${JSON.stringify(v)} → fallback ${r.fallback}, want ${fb}`);
  }
  ok(!bad.length, bad.join("\n"));
});

for (const bad of ["ttps://orsela.github.io/Plan_Travel/app/", "", "not a url"]) {
  T(`IM-02 APP_URL=${JSON.stringify(bad)} → the invite email links to the default app URL; warning logged once, value never logged`, async () => {
    const before = LOGS.length;
    const { deps, mails, logs } = imDeps(bad);
    const h = IM.makeHandler(deps);
    const r1 = await im(h, { action: "create", email: "dana@example.com", draft_name: "יפן 2027" }, "admin-jwt");
    eq(r1.status, 200, "create " + r1.raw);
    const r2 = await im(h, { action: "create", email: "noa@example.com" }, "admin-jwt");
    eq(r2.status, 200, "second create");
    eq(mails.length, 2, "mails sent");
    for (const m of mails) {
      const s = `${m.text ?? ""}\n${m.html ?? ""}`;
      // CHANGE 2026-10-12 F04-QA-05: default link is now /Lonely_Planner/invite/#invite=… (was /Plan_Travel/)
      ok(linkOf(m).startsWith(DEFAULT_INVITE + "#invite="), "email link is not " + DEFAULT_INVITE + "#invite=…: " + linkOf(m));
      ok(!/(^|[^h])ttps:\/\//.test(s), "the broken 'ttps://' URL is in the email");
      ok(!/href=(""|''|"#"|'#'|"not a url")/.test(s), "an empty / relative link in the email");
      ok(/^https:\/\//.test(linkOf(m)), "invite link is not absolute https: " + linkOf(m));
    }
    const all = logs.concat(LOGS.slice(before));
    const warn = all.filter((l) => l.includes("app_url_invalid_fallback"));
    ok(warn.length >= 1, "no app_url_invalid_fallback warning logged");
    ok(warn.length <= 1, `warning logged ${warn.length} times (spec: a single warning line)`);
    if (bad) ok(!all.some((l) => l.includes(bad)), "the invalid APP_URL value was logged");
  });
}

T("IM-03 valid APP_URL unchanged: link built from it, no warning", async () => {
  const before = LOGS.length;
  const { deps, mails, logs } = imDeps("https://example.org/qa/app/");
  const h = IM.makeHandler(deps);
  eq((await im(h, { action: "create", email: "x@example.com" }, "admin-jwt")).status, 200, "create");
  ok(`${mails[0].text}${mails[0].html}`.includes("https://example.org/qa/"), "valid APP_URL not used in the email link");
  ok(!logs.concat(LOGS.slice(before)).some((l) => l.includes("app_url_invalid_fallback")), "warning logged for a valid APP_URL");
});

async function inviteRow(tok: string, over: Row = {}): Promise<Row> {
  return { id: crypto.randomUUID(), email: "dana@example.com", token_hash: await sha256hex(tok), draft_name: "יפן 2027",
    inviter_name: "אור-מזמין", expires_at: "2026-10-19T06:00:00Z", used_at: null, revoked_at: null, opened_at: null,
    send_count: 1, last_sent_at: "2026-10-12T05:00:00Z", created_at: "2026-10-12T05:00:00Z", ...over };
}
const tok43 = (c: string) => c.repeat(43).slice(0, 43);

T("IM-10 check valid → {valid:true, draft_name, inviter_name, expires_at, email}; email = the invite's address", async () => {
  const row = await inviteRow(tok43("A"));
  const { deps } = imDeps(DEFAULT_APP, [row]);
  const h = IM.makeHandler(deps);
  const r = await im(h, { action: "check", token: tok43("A") });
  eq(r.status, 200, "status");
  eq(Object.keys(r.body).sort(), ["draft_name", "email", "expires_at", "inviter_name", "valid"], "check keys");
  eq([r.body.valid, r.body.email, r.body.draft_name, r.body.inviter_name], [true, "dana@example.com", "יפן 2027", "אור-מזמין"], "values");
  ok(!r.raw.includes(row.token_hash), "token_hash leaked");
});

T("IM-11 check invalid (expired / revoked / used / unknown / malformed / missing) → byte-identical {\"valid\":false}, no email", async () => {
  const rows = [await inviteRow(tok43("E"), { expires_at: "2026-10-11T06:00:00Z", email: "e@example.com" }),
    await inviteRow(tok43("R"), { revoked_at: "2026-10-11T06:00:00Z", email: "r@example.com" }),
    await inviteRow(tok43("U"), { used_at: "2026-10-11T06:00:00Z", email: "u@example.com" })];
  const { deps } = imDeps(DEFAULT_APP, rows);
  const h = IM.makeHandler(deps);
  const outs: Res[] = [];
  for (const t of [tok43("E"), tok43("R"), tok43("U"), tok43("Z"), "%%bad<>", "", 12345, undefined]) {
    outs.push(await im(h, t === undefined ? { action: "check" } : { action: "check", token: t }));
  }
  for (const o of outs) {
    eq(o.status, 200, "status");
    eq(o.raw, '{"valid":false}', "invalid body");
    ok(!o.raw.includes("@"), "email in an invalid check response");
  }
});

// ---------------------------------------------------------------------------------------------------------------
// CHANGE 2026-10-12 F04-QA-05: NAME · alpha.4.2 app name + address (spec §8, §8.1)
// ---------------------------------------------------------------------------------------------------------------
T("NAME-01 invite email: subject 'הוזמנת לנהל טיול ב-Lonely Planner', sender name, HTML + text say Lonely Planner; no old name anywhere", async () => {
  const { deps, mails } = imDeps(DEFAULT_APP);
  const h = IM.makeHandler(deps);
  eq((await im(h, { action: "create", email: "dana@example.com", draft_name: "יפן 2027" }, "admin-jwt")).status, 200, "create");
  const m = mails[0];
  eq(m.subject, "הוזמנת לנהל טיול ב-" + APP_NAME, "subject");
  eq(IM.FROM_NAME, APP_NAME, "FROM_NAME (sender display name)");
  if (m.from !== undefined) ok(String(m.from).includes(APP_NAME), "mail.from lacks the app name: " + m.from);
  ok(String(m.html ?? "").includes(APP_NAME), "HTML lacks 'Lonely Planner' (header/footer)");
  ok(String(m.text ?? "").includes(APP_NAME), "text part lacks 'Lonely Planner'");
  const all = JSON.stringify(m) + "\n" + String(IM.FROM_NAME) + "\n" + String(IM.EMAIL_SUBJECT ?? "");
  const hits = OLD_NAMES.filter((re) => re.test(all)).map(String);
  ok(!hits.length, "old app name in the email: " + hits.join(", "));
});

T("NAME-02 invite-manager default address: DEFAULT_APP_URL /Lonely_Planner/app/, email link /Lonely_Planner/invite/#invite=<43>", async () => {
  eq(IM.DEFAULT_APP_URL, DEFAULT_APP, "DEFAULT_APP_URL");
  ok(/^3\.0\.0-alpha\.4\.1$/.test(String(IM.FN_VERSION)), "invite-manager FN_VERSION is not 3.0.0-alpha.4.1: " + IM.FN_VERSION);
  eq(IM.resolveAppUrl(undefined).url, DEFAULT_APP, "unset APP_URL");
  const { deps, mails } = imDeps(IM.resolveAppUrl(undefined).url);
  const h = IM.makeHandler(deps);
  eq((await im(h, { action: "create", email: "x@example.com" }, "admin-jwt")).status, 200, "create");
  ok(/^https:\/\/orsela\.github\.io\/Lonely_Planner\/invite\/#invite=[A-Za-z0-9_-]{43}$/.test(linkOf(mails[0])), "link: " + linkOf(mails[0]));
});

T("NAME-03 create-trip default join_url https://orsela.github.io/Lonely_Planner/join/#code=<CODE>; FN_VERSION alpha.4.1", async () => {
  const mod = await loadCT(null);
  mock(mod);
  ok(/^3\.0\.0-alpha\.4\.1$/.test(String(mod.FN_VERSION)), "create-trip FN_VERSION is not 3.0.0-alpha.4.1: " + mod.FN_VERSION);
  const r = await create(mod);
  eq(r.status, 200, "create " + r.raw);
  eq(r.body.join_url, DEFAULT_JOIN + "#code=" + CREATED.join_code, "join_url");
  ok(!r.raw.includes("Plan_Travel"), "old path in the response");
});
