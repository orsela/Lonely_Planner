// Lonely Planner · manage-members unit tests · version 3.0.0-alpha.7.0 · F06
// CHANGE 2026-10-22 F06-FN-05: new file (no previous version). Dev self-tests for docs/F06_spec.md §3.1 (mocked deps).
//
// Run with Deno:      deno test --allow-env --no-check --import-map=supabase/functions/manage-members/test_import_map.json \
//                                supabase/functions/manage-members/test.ts
// Run without Deno:   node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/manage-members/test.ts

import { FN_VERSION, handler, resetDeps, setDeps, statusFor, VERSION_HEADER } from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}
const MGR = { id: "11111111-1111-4111-8111-111111111111" };
const MEMBER = "22222222-2222-4222-8222-222222222222";
const TRIP = "33333333-3333-4333-8333-333333333333";

async function call(body: unknown, jwt: string | null = "jwt-ok", method = "POST") {
  const h: Record<string, string> = { "content-type": "application/json", origin: "https://orsela.github.io" };
  if (jwt !== null) h["authorization"] = `Bearer ${jwt}`;
  const r = await handler(new Request("http://x/functions/v1/manage-members", {
    method, headers: h, body: method === "GET" || method === "OPTIONS" ? undefined : JSON.stringify(body),
  }));
  let j: Record<string, unknown> = {};
  try {
    j = await r.json();
  } catch { /* 204 */ }
  return { status: r.status, j, h: r.headers };
}
function mock(out: unknown | ((name: string) => unknown)) {
  resetDeps();
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" ? MGR : null),
    rpc: (name, args) => {
      calls.push({ name, args });
      return Promise.resolve({ data: typeof out === "function" ? (out as (n: string) => unknown)(name) : out, error: null });
    },
  });
  return calls;
}

Deno.test("version: constant, body field and header on every response", async () => {
  eq(FN_VERSION, "3.0.0-alpha.7.0");
  mock({ ok: true, touched: true });
  const ok = await call({ action: "touch", trip_id: TRIP });
  eq([ok.status, ok.j.version, ok.h.get(VERSION_HEADER)], [200, FN_VERSION, FN_VERSION]);
  const bad = await call({ action: "touch" }, null);
  eq([bad.status, bad.j.version, bad.h.get(VERSION_HEADER)], [401, FN_VERSION, FN_VERSION]);
  const opt = await call(null, null, "OPTIONS");
  eq([opt.status, opt.h.get(VERSION_HEADER), opt.h.get("access-control-expose-headers")], [204, FN_VERSION, VERSION_HEADER]);
});

Deno.test("status map", () => {
  eq([statusFor("not_manager"), statusFor("not_member"), statusFor("not_active"), statusFor("name_taken"),
    statusFor("last_manager"), statusFor("role_invalid"), statusFor("name_invalid"), statusFor("x")],
    [403, 403, 409, 409, 409, 400, 400, 500]);
});

Deno.test("auth + validation: no rpc call for bad input", async () => {
  const calls = mock({});
  eq((await call({ action: "touch", trip_id: TRIP }, null)).j.error, "unauthorized");
  eq((await call({ action: "touch", trip_id: TRIP }, "bad")).status, 401);
  eq((await call({}, "jwt-ok", "GET")).status, 405);
  eq((await call({ action: "nope" })).j.error, "invalid_request");
  eq((await call({ action: "set_role", member_id: "x", role: "viewer" })).j.error, "invalid_request");
  eq((await call({ action: "set_role", member_id: MEMBER, role: "boss" })).j.error, "role_invalid");
  eq((await call({ action: "set_role", member_id: MEMBER })).j.error, "role_invalid");
  eq((await call({ action: "rename", member_id: MEMBER, display_name: 5 })).j.error, "name_invalid");
  eq((await call({ action: "rename", member_id: "x", display_name: "a" })).j.error, "invalid_request");
  eq((await call({ action: "remove", member_id: 1 })).j.error, "invalid_request");
  for (const a of ["leave", "rotate_link", "touch"]) eq((await call({ action: a, trip_id: "t" })).j.error, "invalid_request", a);
  eq(calls.length, 0);
});

Deno.test("each action → its SQL function with the caller's uid", async () => {
  const cases: [Record<string, unknown>, string, Record<string, unknown>, unknown, Record<string, unknown>][] = [
    [{ action: "set_role", member_id: MEMBER, role: "viewer" }, "member_set_role", { p_user: MGR.id, p_member: MEMBER, p_role: "viewer" },
      { member_id: MEMBER, trip_id: TRIP, role: "viewer", display_name: "איתי", changed: true },
      { member_id: MEMBER, trip_id: TRIP, role: "viewer", display_name: "איתי", changed: true }],
    [{ action: "rename", member_id: MEMBER, display_name: " איתי כ " }, "member_rename", { p_user: MGR.id, p_member: MEMBER, p_name: " איתי כ " },
      { member_id: MEMBER, trip_id: TRIP, display_name: "איתי כ", changed: true },
      { member_id: MEMBER, trip_id: TRIP, display_name: "איתי כ", changed: true }],
    [{ action: "remove", member_id: MEMBER }, "member_remove", { p_user: MGR.id, p_member: MEMBER },
      { member_id: MEMBER, trip_id: TRIP, status: "removed", display_name: "איתי" },
      { member_id: MEMBER, trip_id: TRIP, status: "removed", display_name: "איתי" }],
    [{ action: "leave", trip_id: TRIP }, "member_leave", { p_user: MGR.id, p_trip: TRIP },
      { ok: true, trip_id: TRIP, member_id: MEMBER }, { ok: true, trip_id: TRIP, member_id: MEMBER }],
    [{ action: "rotate_link", trip_id: TRIP }, "rotate_join_code", { p_user: MGR.id, p_trip: TRIP },
      { code: "K7M2Q9XA", version: 2 }, { code: "K7M2Q9XA", code_version: 2 }],
    [{ action: "touch", trip_id: TRIP }, "member_touch", { p_user: MGR.id, p_trip: TRIP },
      { ok: true, touched: false }, { ok: true, touched: false }],
  ];
  for (const [body, fn, args, out, expect] of cases) {
    const calls = mock(out);
    const r = await call(body);
    eq(r.status, 200, String(body.action));
    eq(calls.map((c) => c.name), [fn]);
    eq(calls[0].args, args, fn);
    const { version: _v, ...rest } = r.j;
    eq(rest, expect, fn);
  }
});

Deno.test("long names are cut before the database (it validates 1–40)", async () => {
  const calls = mock({ member_id: MEMBER, display_name: "x", changed: true });
  await call({ action: "rename", member_id: MEMBER, display_name: "א".repeat(500) });
  eq((calls[0].args.p_name as string).length, 200);
});

Deno.test("database refusals → HTTP status + code", async () => {
  for (const [code, st] of [["not_manager", 403], ["not_member", 403], ["not_active", 409], ["name_taken", 409],
    ["last_manager", 409], ["role_invalid", 400], ["name_invalid", 400], ["invalid_request", 400], ["weird", 500]] as const) {
    mock({ error: code });
    const r = await call({ action: "set_role", member_id: MEMBER, role: "editor" });
    eq([r.status, r.j.error], [st, code === "weird" ? "server_error" : code], code);
  }
});

Deno.test("rpc error / bad rotate payload / thrown getUser → 500", async () => {
  resetDeps();
  setDeps({ getUser: () => Promise.resolve(MGR), rpc: () => Promise.resolve({ data: null, error: { message: "boom" } }) });
  eq((await call({ action: "touch", trip_id: TRIP })).status, 500);
  mock({ code: "lower123", version: 2 });
  eq((await call({ action: "rotate_link", trip_id: TRIP })).j.error, "server_error");
  resetDeps();
  setDeps({ getUser: () => Promise.reject(new Error("auth down")), rpc: () => Promise.resolve({ data: {}, error: null }) });
  eq((await call({ action: "touch", trip_id: TRIP })).status, 500);
});

Deno.test("logs: one JSON line, no JWT, ids, codes or names", async () => {
  const lines: string[] = [];
  const orig = console.log;
  console.log = (...a: unknown[]) => lines.push(a.join(" "));
  try {
    mock({ member_id: MEMBER, trip_id: TRIP, display_name: "איתי", changed: true });
    await call({ action: "rename", member_id: MEMBER, display_name: "איתי" });
    mock({ code: "K7M2Q9XA", version: 2 });
    await call({ action: "rotate_link", trip_id: TRIP });
    mock({ error: "name_taken" });
    await call({ action: "rename", member_id: MEMBER, display_name: "איתי" }, "jwt-ok");
  } finally {
    console.log = orig;
  }
  eq(lines.length, 3);
  for (const l of lines) {
    const o = JSON.parse(l);
    eq(o.fn, "manage-members");
    for (const bad of ["jwt-ok", MEMBER, TRIP, MGR.id, "איתי", "K7M2Q9XA"]) assert(!l.includes(bad), "log leaks " + bad + ": " + l);
  }
});
