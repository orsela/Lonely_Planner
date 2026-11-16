// Lonely Planner · manage-members unit tests · version 3.0.0-alpha.16.0 · F06 (+F07)
// CHANGE 2026-11-16 F07-FN-06: version pin alpha.7 → alpha.16; touch now sends p_session / p_label / p_via; new tests for devices,
//   disconnect_device, ack_device_notice, device_revoked / last_device, the JWT session id, the provider and the device label.
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
  eq(FN_VERSION, "3.0.0-alpha.16.0");
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
  eq((await call({ action: "set_role", member_id: MEMBER })).j.error, "invalid_request");              // C6 missing
  eq((await call({ action: "set_role", member_id: MEMBER, role: "Viewer" })).j.error, "role_invalid");   // C6 case
  eq((await call({ action: "set_role", member_id: MEMBER, role: 3 })).j.error, "role_invalid");
  eq((await call({ action: "rename", member_id: MEMBER })).j.error, "invalid_request");                  // C6 missing
  eq((await call({ action: "remove" })).j.error, "invalid_request");
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
      { ok: true, trip_id: TRIP, member_id: MEMBER }, { trip_id: TRIP, member_id: MEMBER }],
    [{ action: "rotate_link", trip_id: TRIP }, "rotate_join_code", { p_user: MGR.id, p_trip: TRIP },
      { code: "K7M2Q9XA", link_version: 2 }, { code: "K7M2Q9XA", link_version: 2 }],
    [{ action: "touch", trip_id: TRIP }, "member_touch", { p_user: MGR.id, p_trip: TRIP, p_session: null, p_label: null, p_via: "anon" },
      { ok: true, touched: false }, { touched: false }],
  ];
  for (const [body, fn, args, out, expect] of cases) {
    const calls = mock(out);
    const r = await call(body);
    eq(r.status, 200, String(body.action));
    eq(calls.map((c) => c.name), [fn]);
    eq(calls[0].args, args, fn);
    const { version: _v, ok: _ok, ...rest } = r.j;   // CHANGE 2026-10-24 F06-FN-09: every success body now has ok:true
    eq(_ok, true, String(body.action) + " ok");
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
  mock({ code: "lower123", link_version: 2 });
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
    mock({ code: "K7M2Q9XA", link_version: 2 });
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

// CHANGE 2026-11-16 F07-FN-06: new tests (no previous version) — docs/F07_spec.md §2.2 (C3, C4, C8, D4).
import { deviceLabel, jwtSessionId, viaOf } from "./index.ts";
const SESSION = "44444444-4444-4444-8444-444444444444";
function fakeJwt(claims: Record<string, unknown>): string {
  const b64 = (o: unknown) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64({ alg: "HS256" })}.${b64(claims)}.sig`;
}
function mockUser(user: { id: string; via?: string }, out: unknown | ((name: string) => unknown)) {
  resetDeps();
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  setDeps({
    getUser: () => Promise.resolve(user),
    rpc: (name, args) => {
      calls.push({ name, args });
      return Promise.resolve({ data: typeof out === "function" ? (out as (n: string) => unknown)(name) : out, error: null });
    },
  });
  return calls;
}
async function callUA(body: unknown, jwt: string, ua: string | null) {
  const h: Record<string, string> = { "content-type": "application/json", origin: "https://orsela.github.io", authorization: `Bearer ${jwt}` };
  if (ua) h["user-agent"] = ua;
  const r = await handler(new Request("http://x/functions/v1/manage-members", { method: "POST", headers: h, body: JSON.stringify(body) }));
  return { status: r.status, j: await r.json() as Record<string, unknown> };
}

Deno.test("F07 jwtSessionId: the session_id claim, only when it is a uuid", () => {
  eq(jwtSessionId(fakeJwt({ session_id: SESSION, sub: "x" })), SESSION);
  eq(jwtSessionId(fakeJwt({ session_id: "nope" })), null);
  eq(jwtSessionId(fakeJwt({ sub: "x" })), null);
  eq(jwtSessionId("garbage"), null);
  eq(jwtSessionId("a.%%%.c"), null);
});

Deno.test("F07 viaOf: anon, provider, linked identities, safe names", () => {
  eq(viaOf({ id: "u", is_anonymous: true }), "anon");
  eq(viaOf({ id: "u", app_metadata: { provider: "email" } }), "email");
  eq(viaOf({ id: "u", app_metadata: { provider: "google" } }), "google");
  eq(viaOf({ id: "u", app_metadata: { provider: "anonymous" }, identities: [{ provider: "email" }] }), "email");
  eq(viaOf({ id: "u", app_metadata: { provider: "Sign-In With X!" } }), "sign_in_with_x_");
  eq(viaOf({ id: "u" }), "email");
});

Deno.test("F07 deviceLabel: readable, never the raw User-Agent", () => {
  eq(deviceLabel("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36"), "Android · Chrome");
  eq(deviceLabel("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1"), "iPhone · Safari");
  eq(deviceLabel("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36 Edg/126.0"), "Windows · Edge");
  eq(deviceLabel("curl/8.0"), null);
  eq(deviceLabel(null), null);
});

Deno.test("F07 touch sends the device's session, label and sign-in kind to the database", async () => {
  const calls = mockUser({ id: MGR.id, via: "google" }, { ok: true, touched: true });
  const r = await callUA({ action: "touch", trip_id: TRIP }, fakeJwt({ session_id: SESSION }),
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/126.0 Safari/537.36");
  eq(r.status, 200);
  eq(calls[0].args, { p_user: MGR.id, p_trip: TRIP, p_session: SESSION, p_label: "Windows · Chrome", p_via: "google" });
});

Deno.test("F07 touch: device_revoked → 403; the status map has the new codes", async () => {
  mockUser({ id: MGR.id, via: "email" }, { error: "device_revoked" });
  const r = await callUA({ action: "touch", trip_id: TRIP }, fakeJwt({ session_id: SESSION }), null);
  eq([r.status, r.j.error, r.j.version], [403, "device_revoked", FN_VERSION]);
  eq([statusFor("device_revoked"), statusFor("last_device")], [403, 409]);
});

Deno.test("F07 devices: arrays pass through, current_session is the caller's own", async () => {
  const persons = [{ person_id: "p1", display_name: "דנה", role: "manager", devices: [{ member_id: MEMBER, session_id: SESSION, via: "anon" }] }];
  const calls = mockUser({ id: MGR.id, via: "anon" }, { persons, notices: [{ session_id: SESSION }], is_manager: true, my_person_id: "p1", secret: 1 });
  const r = await callUA({ action: "devices", trip_id: TRIP }, fakeJwt({ session_id: SESSION }), null);
  eq(r.status, 200);
  eq([r.j.persons, r.j.is_manager, r.j.my_person_id, r.j.current_session, "secret" in r.j], [persons, true, "p1", SESSION, false]);
  eq([calls[0].name, calls[0].args], ["device_list", { p_user: MGR.id, p_trip: TRIP }]);
  eq((await callUA({ action: "devices" }, fakeJwt({}), null)).j.error, "invalid_request");
});

Deno.test("F07 disconnect_device and ack_device_notice: validation, arguments, refusals", async () => {
  let calls = mockUser({ id: MGR.id, via: "anon" }, { ok: true, kind: "session", member_id: MEMBER, session_id: SESSION, auth_session_deleted: true });
  let r = await callUA({ action: "disconnect_device", trip_id: TRIP, member_id: MEMBER, session_id: SESSION }, fakeJwt({}), null);
  eq([r.status, r.j.kind, r.j.auth_session_deleted], [200, "session", true]);
  eq(calls[0].args, { p_user: MGR.id, p_trip: TRIP, p_member: MEMBER, p_session: SESSION });
  r = await callUA({ action: "disconnect_device", trip_id: TRIP, member_id: MEMBER }, fakeJwt({}), null);
  eq(calls[1].args.p_session, null);
  for (const bad of [{ trip_id: "x", member_id: MEMBER }, { trip_id: TRIP }, { trip_id: TRIP, member_id: MEMBER, session_id: "x" }]) {
    r = await callUA({ action: "disconnect_device", ...bad }, fakeJwt({}), null);
    eq([r.status, r.j.error], [400, "invalid_request"]);
  }
  for (const [code, st] of [["last_device", 409], ["not_manager", 403], ["not_active", 409], ["not_member", 403]] as const) {
    mockUser({ id: MGR.id }, { error: code });
    r = await callUA({ action: "disconnect_device", trip_id: TRIP, member_id: MEMBER }, fakeJwt({}), null);
    eq([r.status, r.j.error], [st, code]);
  }
  calls = mockUser({ id: MGR.id }, { ok: true, acked: true });
  r = await callUA({ action: "ack_device_notice", trip_id: TRIP, session_id: SESSION }, fakeJwt({}), null);
  eq([r.status, r.j.acked, calls[0].name, calls[0].args], [200, true, "device_notice_ack", { p_user: MGR.id, p_trip: TRIP, p_session: SESSION }]);
  r = await callUA({ action: "ack_device_notice", trip_id: TRIP }, fakeJwt({}), null);
  eq([r.status, r.j.error], [400, "invalid_request"]);
});
