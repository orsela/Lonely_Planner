// Plan_Travel · create-trip unit tests · version 3.0.0-alpha.4.0 · F04
// CHANGE 2026-10-12 F04-FN-03: new file (no previous version). Deno tests for docs/F04_spec.md §3.1 with mocked
//   getUser / rpc / clock through setDeps() (no network, no database).
//
// Run (network available):  deno test --allow-env supabase/functions/create-trip/test.ts
// Run offline:              deno test --allow-env --no-check --import-map=supabase/functions/create-trip/test_import_map.json \
//                                     supabase/functions/create-trip/test.ts
// No assertion library is imported (to stay runnable offline).

import { DEFAULT_JOIN_URL, FN_VERSION, handler, resetDeps, resolveJoinBase, setDeps } from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}

const U = { id: "11111111-1111-4111-8111-111111111111", email: "Dana@Example.com", email_confirmed_at: "2026-10-12T08:00:00Z" };
const PAYLOAD = {
  name: "יפן 2027", display_name: "דנה", start_date: "2027-04-03", end_date: "2027-04-20", home_currency: "ILS",
  default_lang: "he", default_role: "editor", countries: ["JP", "KR"],
  currencies: [{ code: "JPY", kind: "destination" }, { code: "KRW", kind: "destination" }], center: { lat: 35.68, lng: 139.65 },
};

function req(body: unknown, opts: { jwt?: string | null; method?: string; origin?: string } = {}): Request {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (opts.jwt !== null) h["authorization"] = `Bearer ${opts.jwt ?? "jwt-ok"}`;
  if (opts.origin) h["origin"] = opts.origin;
  return new Request("http://x/functions/v1/create-trip", {
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
function mock(user: unknown = U, rpcImpl?: (name: string, args: Record<string, unknown>) => unknown) {
  resetDeps();
  const calls: Call[] = [];
  let t = 1_000_000;
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" ? user as never : null),
    rpc: (name, args) => {
      calls.push({ name, args });
      const out = rpcImpl ? rpcImpl(name, args) : name === "find_invite_for_email"
        ? { data: { found: true, invite_id: "i1", draft_name: "יפן 2027", inviter_name: "אור", expires_at: "2026-10-19T00:00:00Z" }, error: null }
        : { data: { trip_id: "t1", join_code: "X7K2M9QP", created: true }, error: null };
      return Promise.resolve(out as never);
    },
    now: () => t,
  });
  return { calls, advance: (ms: number) => (t += ms) };
}

Deno.test("version + JOIN_URL validation", () => {
  assert(/^3\.0\.0-alpha\.4/.test(FN_VERSION));
  eq(resolveJoinBase(undefined).url, DEFAULT_JOIN_URL);
  eq(resolveJoinBase("https://example.org/join/").url, "https://example.org/join/");
  for (const bad of ["ttps://example.org/join/", "http://example.org/join/", "https://example.org/join", "not a url", "https:///"]) {
    const r = resolveJoinBase(bad);
    eq(r.url, DEFAULT_JOIN_URL, bad);
    assert(r.fallback, bad);
  }
});

Deno.test("401 unauthorized: no bearer, bad bearer, unknown JWT", async () => {
  mock();
  eq((await call({ action: "lookup" }, { jwt: null })).j, { error: "unauthorized" });
  eq((await call({ action: "lookup" }, { jwt: null })).status, 401);
  eq((await call({ action: "lookup" }, { jwt: "nope" })).status, 401);
});

Deno.test("403 email_not_verified: anonymous / unconfirmed / no email; no rpc call", async () => {
  for (const u of [{ id: "a", is_anonymous: true, email: null }, { id: "b", email: "x@y.com", email_confirmed_at: null }, { id: "c", email: "", email_confirmed_at: "2026-01-01" }]) {
    const m = mock(u);
    const r = await call({ action: "create", ...PAYLOAD });
    eq(r.status, 403);
    eq(r.j, { error: "email_not_verified" });
    eq(m.calls.length, 0);
  }
});

Deno.test("lookup: found → no ids, no email; email normalized for the rpc", async () => {
  const m = mock();
  const r = await call({ action: "lookup" });
  eq(r.status, 200);
  eq(r.j, { found: true, draft_name: "יפן 2027", inviter_name: "אור", expires_at: "2026-10-19T00:00:00Z" });
  eq(m.calls[0], { name: "find_invite_for_email", args: { p_email: "dana@example.com" } });
  const m2 = mock(U, () => ({ data: { found: false }, error: null }));
  eq((await call({ action: "lookup" })).j, { found: false });
  eq(m2.calls.length, 1);
});

Deno.test("create: rpc args, join_url, created flag, CORS", async () => {
  const m = mock();
  const r = await call({ action: "create", ...PAYLOAD, extra: "ignored" }, { origin: "https://orsela.github.io" });
  eq(r.status, 200);
  eq(r.j, { trip_id: "t1", join_code: "X7K2M9QP", join_url: "https://orsela.github.io/Plan_Travel/join/#code=X7K2M9QP", created: true });
  eq(r.r.headers.get("access-control-allow-origin"), "https://orsela.github.io");
  eq(m.calls[0].name, "create_trip_from_invite");
  eq(m.calls[0].args, { p_user: U.id, p_email: "dana@example.com", p_payload: PAYLOAD });
  mock(U, () => ({ data: { trip_id: "t1", join_code: "X7K2M9QP", created: false }, error: null }));
  eq((await call({ action: "create", ...PAYLOAD })).j.created, false);
});

Deno.test("create: error mapping", async () => {
  mock(U, () => ({ data: null, error: { message: "invite_invalid", code: "P0001" } }));
  let r = await call({ action: "create", ...PAYLOAD });
  eq([r.status, r.j], [409, { error: "invite_invalid" }]);
  mock(U, () => ({ data: null, error: { message: "invalid_payload", details: "end_date", code: "P0001" } }));
  r = await call({ action: "create", ...PAYLOAD });
  eq([r.status, r.j], [400, { error: "invalid_payload", field: "end_date" }]);
  mock(U, () => ({ data: null, error: { message: "too_many_currencies", code: "P0001" } }));
  r = await call({ action: "create", ...PAYLOAD });
  eq([r.status, r.j], [400, { error: "too_many_currencies" }]);
  mock(U, () => ({ data: null, error: { message: "boom", code: "XX000" } }));
  r = await call({ action: "create", ...PAYLOAD });
  eq([r.status, r.j], [500, { error: "server_error" }]);
});

Deno.test("rate limit: 10 create / 30 lookup per 10 min per user → 429; window slides; resetDeps clears", async () => {
  const m = mock();
  for (let i = 0; i < 10; i++) eq((await call({ action: "create", ...PAYLOAD })).status, 200, `create ${i}`);
  eq((await call({ action: "create", ...PAYLOAD })).j, { error: "rate_limited" });
  for (let i = 0; i < 30; i++) eq((await call({ action: "lookup" })).status, 200, `lookup ${i}`);
  eq((await call({ action: "lookup" })).status, 429);
  m.advance(10 * 60 * 1000 + 1);
  eq((await call({ action: "create", ...PAYLOAD })).status, 200);
  mock();
  eq((await call({ action: "create", ...PAYLOAD })).status, 200);
});

Deno.test("bad requests: unknown action 400, GET 405, OPTIONS 204, foreign origin gets no allow header", async () => {
  mock();
  eq((await call({ action: "nope" })).j, { error: "invalid_request" });
  eq((await call(null, { method: "GET" })).status, 405);
  const o = await handler(new Request("http://x", { method: "OPTIONS", headers: { origin: "http://localhost:8080" } }));
  eq(o.status, 204);
  eq(o.headers.get("access-control-allow-origin"), "http://localhost:8080");
  const f = await call({ action: "lookup" }, { origin: "https://evil.example" });
  eq(f.r.headers.get("access-control-allow-origin"), null);
});

Deno.test("logs never contain the JWT, email or payload names", async () => {
  const lines: string[] = [];
  const orig = console.log;
  console.log = (...a: unknown[]) => lines.push(a.join(" "));
  try {
    mock();
    await call({ action: "lookup" });
    await call({ action: "create", ...PAYLOAD });
    mock(U, () => ({ data: null, error: { message: "invalid_payload", details: "name" } }));
    await call({ action: "create", ...PAYLOAD });
  } finally {
    console.log = orig;
  }
  const all = lines.join("\n");
  assert(lines.length >= 3, "expected log lines");
  for (const s of ["jwt-ok", "dana@", "Dana@", "יפן", "דנה", "X7K2M9QP"]) assert(!all.includes(s), `log leaked ${s}`);
});
