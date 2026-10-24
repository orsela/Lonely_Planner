// Lonely Planner F06 QA · manage-members black-box tests (Deno-style) · version 1.0.0
// CHANGE 2026-10-22 F06-QA-02: first version (no previous version).
//
// Written from docs/F06_spec.md §2 / §3.1 ONLY (the function source did not exist and was not read). Export surface assumed
// from spec §3.1 "Testable like approve-member (setDeps, handler)": handler(req), setDeps({getUser, rpc}), resetDeps(),
// FN_VERSION — the same surface tests/f05/function_test.ts uses for approve-member. Case ids F6-FN-xx → README matrix.
//
// Contract under test (§3.1): POST {action, …}
//   set_role {member_id, role}           → rpc member_set_role  {p_user, p_member, p_role}
//   rename   {member_id, display_name}   → rpc member_rename    {p_user, p_member, p_name}
//   remove   {member_id}                 → rpc member_remove    {p_user, p_member}
//   leave    {trip_id}                   → rpc member_leave     {p_user, p_trip}
//   rotate_link {trip_id}                → rpc rotate_join_code {p_user, p_trip}
//   touch    {trip_id}                   → rpc member_touch     {p_user, p_trip}
//   200 ok · 400 invalid_request / role_invalid / name_invalid · 401 unauthorized · 403 not_manager / not_member ·
//   409 not_active / name_taken / last_manager · 405 · 500. Version header + body field `version` = 3.0.0-alpha.7.0.
//   One JSON log line per request, no ids or names.
//
// Run without Deno (sandbox; needs supabase/functions/manage-members/test_stubs/supabase_js.ts like the other functions):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        tests/f06/function_test.ts
// With Deno: deno test --no-check --allow-env --allow-read \
//        --import-map=supabase/functions/manage-members/test_import_map.json tests/f06/function_test.ts

// deno-lint-ignore no-explicit-any
type Any = any;
const MM: Any = await import(new URL("../../supabase/functions/manage-members/index.ts", import.meta.url).href);

const VERSION = "3.0.0-alpha.7.0";
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

const JWT = "eyJhbGciOiJIUzI1NiJ9.qa-secret-jwt-f06.sig";
// members joined through F05 are ANONYMOUS identities (spec F05 D1) — they must be accepted (leave, touch, …)
const MEMBER_ID_USER = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", is_anonymous: true, email: "" };
const MGR = { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", is_anonymous: false, email: "dana.secret@example.com" };
const TRIP = "f0600000-0000-4000-8000-000000000001";
const MEMBER = "f0600000-0000-4000-8000-0000000000aa";
const ORIGIN = "https://orsela.github.io";
const NAME = "שם-סודי-QA-F06";
const JCODE = "X7K2M9QP";
type Call = { name: string; args: Record<string, Any> };

function mock(out: Any = {}, user: Any = MGR) {
  MM.resetDeps();
  const calls: Call[] = [];
  MM.setDeps({
    getUser: (jwt: string) => Promise.resolve(jwt === JWT ? user : null),
    rpc: (name: string, args: Record<string, Any>) => {
      calls.push({ name, args: JSON.parse(JSON.stringify(args ?? {})) });
      const o = typeof out === "function" ? out(name, args) : out;
      return Promise.resolve({ data: o, error: null });
    },
  });
  return calls;
}
type Res = { status: number; body: Record<string, Any>; headers: Headers; text: string };
async function call(body: unknown, o: { jwt?: string | null; origin?: string; method?: string; raw?: string } = {}): Promise<Res> {
  const h: Record<string, string> = { "Content-Type": "application/json", apikey: "sb_publishable_qa", Origin: o.origin ?? ORIGIN };
  if (o.jwt !== null) h.Authorization = "Bearer " + (o.jwt ?? JWT);
  const method = o.method ?? "POST";
  const r = await MM.handler(new Request("https://zwufpxnioqaweobnvffs.supabase.co/functions/v1/manage-members", {
    method, headers: h, body: method === "POST" ? (o.raw ?? JSON.stringify(body)) : undefined,
  }));
  const t = await r.text();
  let j: Record<string, Any> = {};
  try { j = JSON.parse(t); } catch { /* */ }
  return { status: r.status, body: j, headers: r.headers, text: t };
}
const errCode = (r: Res) => String(r.body.error ?? r.body.code ?? "");
const T = (name: string, fn: () => Promise<void> | void) => Deno.test({ name, sanitizeOps: false, sanitizeResources: false, fn });
const hdrVersion = (r: Res) => [...r.headers.entries()].filter(([, v]) => v === VERSION).map(([k]) => k);

// a valid body + the SQL function + its named args + a plausible SQL success result, per action (spec §3.1 / §2)
const ACTIONS: [string, Record<string, Any>, string, Record<string, Any>, Any][] = [
  ["set_role", { action: "set_role", member_id: MEMBER, role: "viewer" }, "member_set_role",
   { p_member: MEMBER, p_role: "viewer" }, { ok: true, member_id: MEMBER, role: "viewer" }],
  ["rename", { action: "rename", member_id: MEMBER, display_name: NAME }, "member_rename",
   { p_member: MEMBER, p_name: NAME }, { ok: true, member_id: MEMBER, display_name: NAME }],
  ["remove", { action: "remove", member_id: MEMBER }, "member_remove", { p_member: MEMBER }, { ok: true, member_id: MEMBER }],
  ["leave", { action: "leave", trip_id: TRIP }, "member_leave", { p_trip: TRIP }, { ok: true }],
  ["rotate_link", { action: "rotate_link", trip_id: TRIP }, "rotate_join_code", { p_trip: TRIP }, { code: JCODE, version: 2 }],
  ["touch", { action: "touch", trip_id: TRIP }, "member_touch", { p_trip: TRIP }, { ok: true }],
];

// ---------------------------------------------------------------------------------------------------------------
T("F6-FN-01 §3.1 FN_VERSION = 3.0.0-alpha.7.0", () => {
  eq(String(MM.FN_VERSION), VERSION, "FN_VERSION");
});

T("F6-FN-02 §3.1 every action calls its SQL function once with the named args of §2 and p_user = the JWT uid", async () => {
  for (const [act, body, fn, args, out] of ACTIONS) {
    const calls = mock(out);
    const r = await call(body);
    eq(r.status, 200, `${act}: status (body ${r.text.slice(0, 200)})`);
    eq(calls.map((c) => c.name), [fn], `${act}: rpc name`);
    eq(calls[0].args.p_user, MGR.id, `${act}: p_user`);
    for (const [k, v] of Object.entries(args)) eq(calls[0].args[k], v, `${act}: ${k}`);
    const extra = Object.keys(calls[0].args).filter((k) => k !== "p_user" && !(k in args));
    eq(extra, [], `${act}: unexpected rpc args (the SQL function would not resolve)`);
  }
});

T("F6-FN-03 the caller identity comes only from the JWT: user_id / p_user / p_member in the body are ignored", async () => {
  const OTHER = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
  for (const [act, body, , , out] of ACTIONS) {
    const calls = mock(out);
    await call({ ...body, user_id: OTHER, p_user: OTHER, uid: OTHER });
    eq(calls[0]?.args?.p_user, MGR.id, `${act}: p_user taken from the body`);
  }
});

T("F6-FN-04 anonymous identities are accepted (F05 members are anonymous): leave / touch as an anonymous user → 200", async () => {
  for (const [act, body, fn, , out] of ACTIONS.filter((a) => a[0] === "leave" || a[0] === "touch")) {
    const calls = mock(out, MEMBER_ID_USER);
    const r = await call(body);
    eq([r.status, calls[0]?.name, calls[0]?.args?.p_user], [200, fn, MEMBER_ID_USER.id], act + " as anonymous");
  }
});

T("F6-FN-05 auth: no / malformed / unknown JWT → 401 unauthorized, no rpc", async () => {
  const calls = mock({});
  for (const [label, jwt] of [["no Authorization", null], ["unknown JWT", "bogus"], ["empty bearer", ""]] as const) {
    const r = await call(ACTIONS[0][1], { jwt });
    eq([r.status, errCode(r)], [401, "unauthorized"], label);
  }
  const r = await call(ACTIONS[0][1], { jwt: "bogus" });
  eq(r.status, 401, "unknown JWT");
  eq(calls.length, 0, "rpc called without a valid identity");
});

T("F6-FN-06 §3.1 SQL refusals → status per code (400 / 403 / 409), code passed through as {error}", async () => {
  const map: [string, number][] = [
    ["invalid_request", 400], ["role_invalid", 400], ["name_invalid", 400],
    ["not_manager", 403], ["not_member", 403],
    ["not_active", 409], ["name_taken", 409], ["last_manager", 409],
  ];
  // each code on an action that can produce it (§2), plus every code on set_role (the mapping must not depend on the action)
  const where: Record<string, string[]> = {
    invalid_request: ["remove", "leave"], role_invalid: ["set_role"], name_invalid: ["rename"], not_manager: ["set_role", "rename", "remove", "rotate_link"],
    not_member: ["leave", "touch"], not_active: ["set_role", "rename", "remove"], name_taken: ["rename"], last_manager: ["set_role", "remove", "leave"],
  };
  for (const [code, st] of map) {
    for (const act of new Set([...where[code], "set_role"])) {
      const a = ACTIONS.find((x) => x[0] === act)!;
      mock({ error: code });   // the SQL function RETURNS {"error":code} as data (spec §2, F05 pattern)
      const r = await call(a[1]);
      eq([r.status, errCode(r)], [st, code], `${act} → ${code}`);
    }
  }
});

T("F6-FN-07 bad requests → 400 invalid_request without a database call", async () => {
  const bad: [string, unknown, string | undefined][] = [
    ["unknown action", { action: "drop_trip", trip_id: TRIP }, undefined],
    ["no action", { trip_id: TRIP }, undefined],
    ["bad JSON", null, "{not json"],
    ["array body", null, "[1,2]"],
    ["set_role without member_id", { action: "set_role", role: "viewer" }, undefined],
    ["set_role with a non-uuid member_id", { action: "set_role", member_id: "x", role: "viewer" }, undefined],
    ["rename without member_id", { action: "rename", display_name: "x" }, undefined],
    ["remove without member_id", { action: "remove" }, undefined],
    ["remove with a numeric member_id", { action: "remove", member_id: 7 }, undefined],
    ["leave without trip_id", { action: "leave" }, undefined],
    ["rotate_link with a non-uuid trip_id", { action: "rotate_link", trip_id: "nope" }, undefined],
    ["touch without trip_id", { action: "touch" }, undefined],
  ];
  for (const [label, body, raw] of bad) {
    const calls = mock({});
    const r = await call(body, { raw });
    eq([r.status, errCode(r), calls.length], [400, "invalid_request", 0], label);
  }
});

T("F6-FN-08 set_role: a role outside manager/editor/viewer → 400 role_invalid (checked here or in SQL — either is fine)", async () => {
  for (const role of ["owner", "", null, "MANAGER"]) {
    mock({ error: "role_invalid" });
    const r = await call({ action: "set_role", member_id: MEMBER, role });
    ok(r.status === 400 && ["role_invalid", "invalid_request"].includes(errCode(r)),
      `role ${JSON.stringify(role)}: ${r.status} ${errCode(r)} (want 400 role_invalid; invalid_request accepted for a missing role)`);
  }
  for (const role of ["manager", "editor", "viewer"]) {
    const calls = mock({ ok: true });
    const r = await call({ action: "set_role", member_id: MEMBER, role });
    eq([r.status, calls[0]?.args?.p_role], [200, role], "valid role " + role);
  }
});

T("F6-FN-09 rename: the name reaches the SQL function unchanged (cleaning is §2.2 private.f05_clean_name); empty / 41 chars → 400 name_invalid", async () => {
  let calls = mock({ ok: true });
  await call({ action: "rename", member_id: MEMBER, display_name: "  נועה   כהן " });
  ok(["  נועה   כהן ", "נועה כהן"].includes(calls[0]?.args?.p_name), "p_name " + JSON.stringify(calls[0]?.args?.p_name));
  for (const n of ["", "   ", "א".repeat(41)]) {
    calls = mock({ error: "name_invalid" });
    const r = await call({ action: "rename", member_id: MEMBER, display_name: n });
    eq([r.status, errCode(r)], [400, "name_invalid"], "name " + JSON.stringify(n.slice(0, 5)) + "… len " + n.length);
  }
  calls = mock({ error: "name_invalid" });
  const r = await call({ action: "rename", member_id: MEMBER });
  ok(r.status === 400 && ["name_invalid", "invalid_request"].includes(errCode(r)), "missing display_name: " + r.status + " " + errCode(r));
});

T("F6-FN-10 §3.1 version: success responses carry a header with value 3.0.0-alpha.7.0 and body.version = 3.0.0-alpha.7.0", async () => {
  for (const [act, body, , , out] of ACTIONS) {
    mock(out);
    const r = await call(body);
    ok(hdrVersion(r).length > 0, `${act}: no response header has the value ${VERSION} (headers: ${[...r.headers.keys()].join(", ")})`);
    if (act === "rotate_link") {
      // open (spec ambiguity A-FN-1): rotate_join_code returns {code, version:<int>} and the body field `version` is the function
      // version — one of them must move. Accepted: body.version = function version and the int under another key, OR the int
      // kept in body.version with the function version still in the header.
      ok(r.body.version === VERSION || r.body.version === 2, `rotate_link: body.version ${JSON.stringify(r.body.version)}`);
    } else {
      eq(r.body.version, VERSION, `${act}: body.version`);
    }
  }
});

T("F6-FN-11 §3.1 version header also on refusals, 401, 400, 405 and OPTIONS (body.version, when present, is correct)", async () => {
  const cases: [string, () => Promise<Res>][] = [
    ["409 last_manager", async () => { mock({ error: "last_manager" }); return await call(ACTIONS[0][1]); }],
    ["403 not_manager", async () => { mock({ error: "not_manager" }); return await call(ACTIONS[0][1]); }],
    ["401", async () => { mock({}); return await call(ACTIONS[0][1], { jwt: null }); }],
    ["400", async () => { mock({}); return await call({ action: "nope" }); }],
    ["405", async () => { mock({}); return await call({}, { method: "GET" }); }],
    ["OPTIONS", async () => { mock({}); return await call({}, { method: "OPTIONS" }); }],
  ];
  for (const [label, f] of cases) {
    const r = await f();
    ok(hdrVersion(r).length > 0, `${label}: no version header (headers: ${[...r.headers.keys()].join(", ")})`);
    ok(r.body.version === undefined || r.body.version === VERSION, `${label}: body.version ${JSON.stringify(r.body.version)}`);
  }
});

T("F6-FN-12 rotate_link: the new code (and the join-code version) reach the client", async () => {
  mock({ code: JCODE, version: 7 });
  const r = await call({ action: "rotate_link", trip_id: TRIP });
  eq([r.status, r.body.code], [200, JCODE], "code passed through");
  ok(JSON.stringify(r.body).includes("7"), "join-code version (7) not in the body: " + r.text);
});

T("F6-FN-13 success bodies have no `error` key and keep the SQL result fields", async () => {
  for (const [act, body, , , out] of ACTIONS) {
    mock(out);
    const r = await call(body);
    ok(!("error" in r.body), `${act}: error key in a success body: ${r.text}`);
    for (const [k, v] of Object.entries(out)) {
      if (k === "version") continue;   // see F6-FN-10
      eq(r.body[k], v, `${act}: body.${k}`);
    }
  }
});

T("F6-FN-14 database failure / unexpected rpc error → 500, no database message or secret in the body", async () => {
  MM.resetDeps();
  MM.setDeps({ getUser: () => Promise.resolve(MGR),
               rpc: () => Promise.resolve({ data: null, error: { code: "57014", message: "statement timeout " + NAME + " " + MEMBER } }) });
  const r = await call({ action: "rename", member_id: MEMBER, display_name: NAME });
  eq(r.status, 500, "status");
  ok(!r.text.includes(NAME) && !r.text.includes("statement timeout") && !r.text.includes(MEMBER), "db message leaked: " + r.text);
  MM.resetDeps();
  MM.setDeps({ getUser: () => Promise.resolve(MGR), rpc: () => Promise.reject(new Error("boom " + NAME)) });
  const r2 = await call({ action: "touch", trip_id: TRIP });
  eq(r2.status, 500, "throwing rpc");
  ok(!r2.text.includes(NAME), "exception text leaked");
  MM.resetDeps();
  MM.setDeps({ getUser: () => Promise.reject(new Error("auth down")), rpc: () => Promise.resolve({ data: {}, error: null }) });
  const r3 = await call({ action: "touch", trip_id: TRIP });
  ok(r3.status === 500 || r3.status === 401, "getUser throws → " + r3.status + " (500 or 401 accepted)");
});

T("F6-FN-15 an SQL error code that is not in the §2 list → 500 (never 200, never a raw pass-through status)", async () => {
  mock({ error: "something_new" });
  const r = await call(ACTIONS[0][1]);
  ok(r.status >= 500, "unknown SQL error code → " + r.status);
});

T("F6-FN-16 CORS: app origin echoed, OPTIONS 204 with authorization+apikey allowed, foreign origin not allowed, GET/PUT 405", async () => {
  mock({});
  let r = await call({}, { method: "OPTIONS" });
  eq([r.status, r.headers.get("access-control-allow-origin")], [204, ORIGIN], "preflight");
  const ah = r.headers.get("access-control-allow-headers") || "";
  ok(/authorization/i.test(ah) && /apikey/i.test(ah) && /content-type/i.test(ah), "allow-headers " + ah);
  r = await call({}, { method: "OPTIONS", origin: "https://evil.example" });
  const ao = r.headers.get("access-control-allow-origin");
  ok(ao !== "https://evil.example" && ao !== "*", "foreign origin allowed: " + ao);
  for (const m of ["GET", "PUT", "DELETE"]) {
    r = await call({}, { method: m });
    eq(r.status, 405, m);
  }
});

T("F6-FN-17 §3.1 exactly one JSON log line per request", async () => {
  const reqs: [string, () => Promise<Res>][] = [
    ...ACTIONS.map(([act, body, , , out]) => [act, async () => { mock(out); return await call(body); }] as [string, () => Promise<Res>]),
    ["refusal", async () => { mock({ error: "last_manager" }); return await call(ACTIONS[0][1]); }],
    ["401", async () => { mock({}); return await call(ACTIONS[0][1], { jwt: null }); }],
    ["400", async () => { mock({}); return await call({ action: "x" }); }],
  ];
  for (const [label, f] of reqs) {
    capture();
    await f();
    const lines = LOGS.filter((l) => l.trim());
    const json = lines.filter((l) => { try { return typeof JSON.parse(l) === "object"; } catch { return false; } });
    eq([lines.length, json.length], [1, 1], `${label}: log lines ${JSON.stringify(lines).slice(0, 300)}`);
  }
});

T("F6-FN-18 §3.1 logs contain no ids or names: no uid, member id, trip id, display name, email, JWT or join code", async () => {
  capture();
  for (const [, body, , , out] of ACTIONS) {
    mock({ ...out, display_name: NAME, trip_id: TRIP, user_id: MGR.id });
    await call(body);
  }
  mock({ error: "name_taken" });
  await call({ action: "rename", member_id: MEMBER, display_name: NAME });
  MM.resetDeps();
  MM.setDeps({ getUser: () => Promise.resolve(MGR), rpc: () => Promise.resolve({ data: null, error: { message: "fail " + NAME + " " + TRIP } }) });
  await call({ action: "rename", member_id: MEMBER, display_name: NAME });
  ok(LOGS.length > 0, "nothing logged at all (expected one line per request)");
  for (const s of [MGR.id, MEMBER, TRIP, NAME, MGR.email, JWT, JCODE]) ok(!LOGS.some((l) => l.includes(s)), "secret / id in logs: " + s);
});

T("F6-FN-19 the log line names the action and the outcome (useful without ids)", async () => {
  capture();
  mock({ error: "last_manager" });
  await call({ action: "leave", trip_id: TRIP });
  const l = LOGS.join("\n");
  ok(/leave/.test(l) && /(409|last_manager)/.test(l), "log line lacks action / outcome: " + l.slice(0, 300));
});
