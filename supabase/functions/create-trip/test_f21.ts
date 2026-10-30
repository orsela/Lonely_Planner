// Lonely Planner · create-trip F21 unit tests · version 3.0.0-alpha.8.0 · F21
// CHANGE 2026-10-27 F21-FN-22: new file (no previous version). docs/F21_spec.md §3.3: `lookup` passes `prefill` through
//   from find_invite_for_email (stubbed rpc); without a prefill the answer is exactly the alpha.4.1 shape.
// Run offline: node --experimental-transform-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/create-trip/test_f21.ts

import { cleanPrefill, FN_VERSION, handler, resetDeps, setDeps } from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}

const U = { id: "11111111-1111-4111-8111-111111111111", email: "tom@example.co.uk", email_confirmed_at: "2026-10-27T08:00:00Z" };
const BASE = { found: true, invite_id: "i1", draft_name: "Portugal", inviter_name: "אור", expires_at: "2026-11-03T09:00:00Z" };
const PF = { name: "Tom Baker", countries: ["PT", "ES"], month: "2027-04-01", lang: "en" };

function mock(data: unknown) {
  resetDeps();
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" ? U as never : null),
    rpc: () => Promise.resolve({ data, error: null }),
    now: () => 1,
  });
}
async function lookup() {
  const r = await handler(new Request("http://x/functions/v1/create-trip", {
    method: "POST", headers: { "content-type": "application/json", authorization: "Bearer jwt-ok" }, body: JSON.stringify({ action: "lookup" }),
  }));
  return { status: r.status, j: await r.json() };
}

Deno.test("F21 create-trip version 3.0.0-alpha.8.0", () => {
  eq(FN_VERSION, "3.0.0-alpha.8.0");
});

Deno.test("F21 lookup with prefill → passed through {name, countries, month, lang}; no ids or email", async () => {
  mock({ ...BASE, prefill: PF });
  const r = await lookup();
  eq(r.status, 200);
  eq(r.j, { found: true, draft_name: "Portugal", inviter_name: "אור", expires_at: "2026-11-03T09:00:00Z", prefill: PF });
  mock({ ...BASE, prefill: { ...PF, month: null, lang: "he", name: "  דנה " } });
  eq((await lookup()).j.prefill, { name: "דנה", countries: ["PT", "ES"], month: null, lang: "he" });
});

Deno.test("F21 lookup without prefill → exactly the alpha.4.1 answer (no prefill key)", async () => {
  mock(BASE);
  const r = await lookup();
  eq(r.j, { found: true, draft_name: "Portugal", inviter_name: "אור", expires_at: "2026-11-03T09:00:00Z" });
  assert(!("prefill" in r.j));
  mock({ found: false });
  eq((await lookup()).j, { found: false });
});

Deno.test("F21 cleanPrefill drops malformed values (whole prefill omitted)", async () => {
  for (const bad of [null, [], "x", { ...PF, name: "" }, { ...PF, name: "x".repeat(41) }, { ...PF, countries: [] },
    { ...PF, countries: ["pt"] }, { ...PF, countries: ["PT", "PT"] }, { ...PF, countries: Array(11).fill(0).map((_, i) => "A" + String.fromCharCode(65 + i)) },
    { ...PF, month: "2027-04" }, { ...PF, month: "2027-13-01" }, { ...PF, month: 5 }, { ...PF, lang: "fr" }]) {
    eq(cleanPrefill(bad), null, JSON.stringify(bad));
  }
  mock({ ...BASE, prefill: { ...PF, lang: "fr" } });
  assert(!("prefill" in (await lookup()).j), "malformed prefill passed through");
  resetDeps();
});
