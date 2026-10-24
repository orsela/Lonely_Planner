// Lonely Planner · join-trip unit tests · version 3.0.0-alpha.7.0 · F05
// CHANGE 2026-10-22 F06-FN-08: version pin alpha.6 → alpha.7 and the X-Function-Version header check (was: alpha.6 pin only).
// CHANGE 2026-10-19 F05-FN-05: new file (no previous version). Dev self-tests for docs/F05_spec.md §3 with mocked
//   getUser / rpc through setDeps() (no network, no database). The QA team's own suite is separate (tests/f05/).
//
// Run with Deno:      deno test --allow-env --no-check --import-map=supabase/functions/join-trip/test_import_map.json \
//                                supabase/functions/join-trip/test.ts
// Run without Deno:   node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/join-trip/test.ts

import { FN_VERSION, handler, ipHash, normJoinCode, resetDeps, setDeps, statusFor } from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}
const ANON = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", is_anonymous: true };
const TRIP = "f0500000-0000-4000-8000-000000000001";

function req(body: unknown, opts: { jwt?: string | null; method?: string; origin?: string; ip?: string } = {}): Request {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (opts.jwt !== null) h["authorization"] = `Bearer ${opts.jwt ?? "jwt-ok"}`;
  if (opts.origin) h["origin"] = opts.origin;
  if (opts.ip) h["x-forwarded-for"] = opts.ip;
  return new Request("http://x/functions/v1/join-trip", {
    method: opts.method || "POST", headers: h, body: opts.method === "GET" ? undefined : JSON.stringify(body),
  });
}
async function call(body: unknown, opts = {}) {
  const r = await handler(req(body, opts));
  let j: Record<string, unknown> = {};
  try {
    j = await r.json();
  } catch { /* 204 */ }
  return { status: r.status, j, r };
}
type Call = { name: string; args: Record<string, unknown> };
function mock(out: unknown, user: unknown = ANON) {
  resetDeps();
  const calls: Call[] = [];
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" ? user as never : null),
    rpc: (name, args) => {
      calls.push({ name, args });
      return Promise.resolve((typeof out === "function" ? out(name, args) : { data: out, error: null }) as never);
    },
  });
  return calls;
}

Deno.test("version + status map", () => {
  assert(/^3\.0\.0-alpha\.7/.test(FN_VERSION));
  eq([statusFor("code_invalid"), statusFor("name_taken"), statusFor("rate_limited"), statusFor("member_removed"), statusFor("x")],
    [404, 409, 429, 403, 500]);
});

Deno.test("normJoinCode accepts link / hash / spaces / lower case; rejects others", () => {
  eq(normJoinCode("https://orsela.github.io/Lonely_Planner/join/#code=x7k2m9qp"), "X7K2M9QP");
  eq(normJoinCode(" x7k2 m9qp "), "X7K2M9QP");
  eq(normJoinCode("X7K2-M9QP"), "X7K2M9QP");
  eq(normJoinCode("X7K2M9Q0"), null); // 0 is not in the alphabet
  eq(normJoinCode("X7K2M9Q"), null);
  eq(normJoinCode(42), null);
});

Deno.test("ipHash: sha-256 hex of the first forwarded address, never the address", async () => {
  const h = await ipHash(req({}, { ip: "203.0.113.7, 10.0.0.1" }));
  assert(h && /^[0-9a-f]{64}$/.test(h) && !h.includes("203"));
  eq(h, await ipHash(req({}, { ip: "203.0.113.7" })));
  eq(await ipHash(req({})), null);
});

Deno.test("CORS, OPTIONS, method, auth", async () => {
  mock({});
  let r = await call({}, { method: "OPTIONS", origin: "https://orsela.github.io" });
  eq(r.status, 204);
  eq(r.r.headers.get("access-control-allow-origin"), "https://orsela.github.io");
  r = await call({}, { method: "GET" });
  eq([r.status, r.j.error], [405, "method_not_allowed"]);
  r = await call({ action: "preview", code: "X7K2M9QP" }, { jwt: null });
  eq([r.status, r.j.error], [401, "unauthorized"]);
  r = await call({ action: "preview", code: "X7K2M9QP" }, { jwt: "bad" });
  eq([r.status, r.j.error], [401, "unauthorized"]);
  r = await call({ action: "nope" });
  eq([r.status, r.j.error], [400, "invalid_request"]);
  r = await call({ action: "preview", code: "X7K2M9QP" }, { origin: "https://evil.example" });
  eq(r.r.headers.get("access-control-allow-origin"), null);
});

Deno.test("preview: anonymous user ok, args, output whitelisted", async () => {
  const calls = mock({ trip_id: TRIP, name: "יפן 2027", start_date: "2027-04-03", end_date: "2027-04-20", days: 18, members: 5,
    manager: "דנה", me: null, secret: "x" });
  const r = await call({ action: "preview", code: "#code=x7k2m9qp" }, { ip: "203.0.113.7" });
  eq(r.status, 200);
  eq(Object.keys(r.j).sort(), ["days", "end_date", "manager", "me", "members", "name", "start_date", "trip_id"]);
  eq(calls[0].name, "join_preview");
  eq(calls[0].args.p_code, "X7K2M9QP");
  eq(calls[0].args.p_user, ANON.id);
  assert(typeof calls[0].args.p_ip === "string" && (calls[0].args.p_ip as string).length === 64);
});

Deno.test("preview: malformed code → 404 code_invalid without a database call", async () => {
  const calls = mock({});
  const r = await call({ action: "preview", code: "abc" });
  eq([r.status, r.j.error, calls.length], [404, "code_invalid", 0]);
});

Deno.test("database refusals map to HTTP errors", async () => {
  for (const [code, st] of [["code_invalid", 404], ["name_taken", 409], ["name_invalid", 400], ["rate_limited", 429],
    ["member_removed", 403]] as const) {
    mock({ error: code });
    const r = await call({ action: "request", code: "X7K2M9QP", display_name: "נועה" });
    eq([r.status, r.j.error], [st, code], code);
  }
  mock({ error: "something_new" });
  const r = await call({ action: "request", code: "X7K2M9QP", display_name: "נועה" });
  eq([r.status, r.j.error], [500, "server_error"]);
  mock(() => ({ data: null, error: { message: "boom" } }));
  const r2 = await call({ action: "request", code: "X7K2M9QP", display_name: "נועה" });
  eq([r2.status, r2.j.error], [500, "server_error"]);
});

Deno.test("request: name passed through (the database cleans it), non-string → name_invalid", async () => {
  const calls = mock({ trip_id: TRIP, member_id: "m1", status: "pending", role: "editor", display_name: "נועה", created: true });
  let r = await call({ action: "request", code: "X7K2M9QP", display_name: "  נועה " });
  eq(r.status, 200);
  eq(calls[0].args.p_name, "  נועה ");
  eq(r.j.status, "pending");
  r = await call({ action: "request", code: "X7K2M9QP", display_name: 5 });
  eq([r.status, r.j.error], [400, "name_invalid"]);
});

Deno.test("cancel / issue_transfer need a trip uuid", async () => {
  mock({ ok: true });
  let r = await call({ action: "cancel", trip_id: "x" });
  eq([r.status, r.j.error], [400, "invalid_request"]);
  r = await call({ action: "cancel", trip_id: TRIP });
  eq([r.status, r.j.ok], [200, true]);
  mock({ code: "482916", expires_at: "2027-01-01T00:00:00Z" });
  r = await call({ action: "issue_transfer", trip_id: TRIP });
  eq([r.status, r.j.code], [200, "482916"]);
  mock({ code: "48291", expires_at: "x" });
  r = await call({ action: "issue_transfer", trip_id: TRIP });
  eq([r.status, r.j.error], [500, "server_error"]);
  mock({ error: "not_member" });
  r = await call({ action: "issue_transfer", trip_id: TRIP });
  eq([r.status, r.j.error], [403, "not_member"]);
});

Deno.test("claim_transfer", async () => {
  const calls = mock({ trip_id: TRIP, member_id: "m1", role: "editor", display_name: "נועה" });
  let r = await call({ action: "claim_transfer", code: "482 916" });
  eq([r.status, r.j.trip_id, r.j.role], [200, TRIP, "editor"]);
  eq(calls[0].args.p_code, "482 916");
  for (const code of ["transfer_invalid", "already_member", "rate_limited"]) {
    mock({ error: code });
    r = await call({ action: "claim_transfer", code: "000000" });
    eq(r.j.error, code);
  }
  r = await call({ action: "claim_transfer" });
  eq([r.status, r.j.error], [409, "transfer_invalid"]);
});

// CHANGE 2026-10-22 F06-FN-08: new test (no previous version) — the X-Function-Version header on success and on errors.
Deno.test("X-Function-Version header (alpha.7.0)", async () => {
  mock({ trip_id: TRIP, name: "t", me: null });
  const ok = await call({ action: "preview", code: "X7K2M9QP" });
  eq(ok.r.headers.get("X-Function-Version"), FN_VERSION);
  const bad = await call({ action: "preview", code: "x" }, { jwt: null });
  eq([bad.status, bad.r.headers.get("X-Function-Version")], [401, FN_VERSION]);
});
