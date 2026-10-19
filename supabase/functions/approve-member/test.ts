// Lonely Planner · approve-member unit tests · version 3.0.0-alpha.6.0 · F05
// CHANGE 2026-10-19 F05-FN-06: new file (no previous version). Dev self-tests for docs/F05_spec.md §3 (mocked deps).
//
// Run with Deno:      deno test --allow-env --no-check --import-map=supabase/functions/approve-member/test_import_map.json \
//                                supabase/functions/approve-member/test.ts
// Run without Deno:   node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/approve-member/test.ts

import { FN_VERSION, handler, resetDeps, setDeps } from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}
const MGR = { id: "11111111-1111-4111-8111-111111111111" };
const MEMBER = "22222222-2222-4222-8222-222222222222";

async function call(body: unknown, jwt: string | null = "jwt-ok", method = "POST") {
  const h: Record<string, string> = { "content-type": "application/json", origin: "https://orsela.github.io" };
  if (jwt !== null) h["authorization"] = `Bearer ${jwt}`;
  const r = await handler(new Request("http://x/functions/v1/approve-member", {
    method, headers: h, body: method === "GET" ? undefined : JSON.stringify(body),
  }));
  let j: Record<string, unknown> = {};
  try {
    j = await r.json();
  } catch { /* 204 */ }
  return { status: r.status, j };
}
function mock(out: unknown) {
  resetDeps();
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" ? MGR : null),
    rpc: (name, args) => {
      calls.push({ name, args });
      return Promise.resolve({ data: out, error: null });
    },
  });
  return calls;
}

Deno.test("version", () => assert(/^3\.0\.0-alpha\.6/.test(FN_VERSION)));

Deno.test("auth + validation", async () => {
  const calls = mock({});
  eq((await call({}, null)).j.error, "unauthorized");
  eq((await call({}, "bad")).status, 401);
  eq((await call({}, "jwt-ok", "GET")).status, 405);
  eq((await call({ member_id: "x", decision: "approve" })).j.error, "invalid_request");
  eq((await call({ member_id: MEMBER, decision: "maybe" })).j.error, "invalid_request");
  eq((await call({ member_id: MEMBER, decision: "approve", role: "boss" })).j.error, "role_invalid");
  eq(calls.length, 0);
});

Deno.test("approve with role / default role; reject ignores role", async () => {
  let calls = mock({ status: "active", member_id: MEMBER, role: "viewer", display_name: "נועה", trip_id: "t" });
  let r = await call({ member_id: MEMBER, decision: "approve", role: "viewer" });
  eq([r.status, r.j.status, r.j.role], [200, "active", "viewer"]);
  eq(calls[0].args, { p_user: MGR.id, p_member: MEMBER, p_decision: "approve", p_role: "viewer" });
  calls = mock({ status: "active", member_id: MEMBER, role: "editor", display_name: "נועה", trip_id: "t" });
  await call({ member_id: MEMBER, decision: "approve" });
  eq(calls[0].args.p_role, null);
  calls = mock({ status: "rejected", member_id: MEMBER, display_name: "נועה" });
  r = await call({ member_id: MEMBER, decision: "reject", role: "boss" });
  eq([r.status, r.j.status], [200, "rejected"]);
  eq(calls[0].args.p_role, null);
});

Deno.test("database refusals", async () => {
  for (const [code, st] of [["not_manager", 403], ["not_pending", 409], ["role_invalid", 400], ["invalid_request", 400], ["weird", 500]] as const) {
    mock({ error: code });
    const r = await call({ member_id: MEMBER, decision: "approve", role: "editor" });
    eq([r.status, r.j.error], [st, code === "weird" ? "server_error" : code], code);
  }
});
