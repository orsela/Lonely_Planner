// Lonely Planner · vault-delete unit tests · version 3.0.0-alpha.18.0 · F12
// CHANGE 2026-11-24 F12-FN-03: new file (no previous version). Dev self-tests for claude/Plan_Travel_F12_spec.md §3 (mocked deps).
//
// Run with Deno:      deno test --allow-env --no-check --import-map=supabase/functions/vault-delete/test_import_map.json \
//                                supabase/functions/vault-delete/test.ts
// Run without Deno:   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs supabase/functions/vault-delete/test.ts

import { FN_VERSION, handler, isVaultPath, resetDeps, setDeps, statusFor, VERSION_HEADER } from "./index.ts";

function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}
const MGR = { id: "11111111-1111-4111-8111-111111111111" };
const DOC = "44444444-4444-4444-8444-444444444444";
const TRIP = "33333333-3333-4333-8333-333333333333";
const PATH = `${TRIP}/${DOC}.pdf`;

async function call(body: unknown, jwt: string | null = "jwt-ok", method = "POST") {
  const h: Record<string, string> = { "content-type": "application/json", origin: "https://orsela.github.io" };
  if (jwt !== null) h["authorization"] = `Bearer ${jwt}`;
  const r = await handler(new Request("http://x/functions/v1/vault-delete", {
    method, headers: h, body: method === "GET" || method === "OPTIONS" ? undefined : JSON.stringify(body),
  }));
  let j: Record<string, unknown> = {};
  try {
    j = await r.json();
  } catch { /* 204 */ }
  return { status: r.status, j, h: r.headers };
}
type Step = { kind: "rpc" | "remove"; name?: string; args?: Record<string, unknown>; path?: string };
function mock(opts: {
  prepare?: unknown; finish?: unknown; removeError?: string | null; rpcError?: string; user?: boolean;
} = {}) {
  resetDeps();
  const steps: Step[] = [];
  setDeps({
    getUser: (jwt) => Promise.resolve(jwt === "jwt-ok" && opts.user !== false ? MGR : null),
    rpc: (name, args) => {
      steps.push({ kind: "rpc", name, args });
      if (opts.rpcError === name) return Promise.resolve({ data: null, error: { message: "boom" } });
      const data = name === "vault_delete_prepare"
        ? (opts.prepare ?? { ok: true, trip_id: TRIP, storage_path: PATH })
        : (opts.finish ?? { ok: true, deleted: true, trip_id: TRIP });
      return Promise.resolve({ data, error: null });
    },
    removeObject: (path) => {
      steps.push({ kind: "remove", path });
      return Promise.resolve({ error: opts.removeError ? { message: opts.removeError } : null });
    },
  });
  return steps;
}

Deno.test("version: constant, body field and header on every response", async () => {
  eq(FN_VERSION, "3.0.0-alpha.18.0");
  mock();
  const ok = await call({ doc_id: DOC });
  eq([ok.status, ok.j.version, ok.h.get(VERSION_HEADER)], [200, FN_VERSION, FN_VERSION]);
  const bad = await call({ doc_id: DOC }, null);
  eq([bad.status, bad.j.version, bad.h.get(VERSION_HEADER)], [401, FN_VERSION, FN_VERSION]);
  const opt = await call(null, null, "OPTIONS");
  eq([opt.status, opt.h.get(VERSION_HEADER), opt.h.get("access-control-expose-headers")], [204, FN_VERSION, VERSION_HEADER]);
});

Deno.test("status map", () => {
  eq([statusFor("not_manager"), statusFor("not_found"), statusFor("invalid_request"), statusFor("unauthorized"), statusFor("x")],
    [403, 404, 400, 401, 500]);
});

Deno.test("happy path: prepare → remove object → finish, in that order, with the caller's id", async () => {
  const steps = mock();
  const r = await call({ doc_id: DOC });
  eq([r.status, r.j.ok, r.j.deleted], [200, true, true]);
  eq(steps, [
    { kind: "rpc", name: "vault_delete_prepare", args: { p_user: MGR.id, p_doc: DOC } },
    { kind: "remove", path: PATH },
    { kind: "rpc", name: "vault_delete_finish", args: { p_user: MGR.id, p_doc: DOC } },
  ]);
});

Deno.test("auth + validation: nothing is called for bad input", async () => {
  let steps = mock();
  eq((await call({ doc_id: DOC }, null)).j.error, "unauthorized");
  eq((await call({ doc_id: DOC }, "bad")).status, 401);
  eq((await call({}, "jwt-ok", "GET")).status, 405);
  for (const body of [{}, { doc_id: "x" }, { doc_id: 5 }, { doc_id: null }, { doc_id: `${DOC}/../x` }, []]) {
    const r = await call(body);
    eq([r.status, r.j.error], [400, "invalid_request"]);
  }
  eq(steps.length, 0);
  steps = mock({ user: false });
  eq((await call({ doc_id: DOC })).status, 401);
  eq(steps.length, 0);
});

Deno.test("a refusal by prepare stops everything: Storage is never touched", async () => {
  for (const [code, st] of [["not_manager", 403], ["not_found", 404], ["invalid_request", 400]] as const) {
    const steps = mock({ prepare: { error: code } });
    const r = await call({ doc_id: DOC });
    eq([r.status, r.j.error], [st, code]);
    eq(steps.map((s) => s.kind + ":" + (s.name ?? "")), ["rpc:vault_delete_prepare"]);
  }
});

Deno.test("Storage failure → 500, the row is NOT deleted (finish never called)", async () => {
  const steps = mock({ removeError: "storage down" });
  const r = await call({ doc_id: DOC });
  eq([r.status, r.j.error], [500, "server_error"]);
  eq(steps.map((s) => s.kind), ["rpc", "remove"]);
});

Deno.test("an odd path from the database is never handed to Storage", async () => {
  for (const p of ["../x.pdf", `${TRIP}/${DOC}.exe`, `${TRIP}/a/${DOC}.pdf`, "", null, 5]) {
    const steps = mock({ prepare: { ok: true, trip_id: TRIP, storage_path: p } });
    const r = await call({ doc_id: DOC });
    eq([r.status, r.j.error], [500, "server_error"]);
    eq(steps.filter((s) => s.kind === "remove").length, 0);
  }
  eq([isVaultPath(PATH), isVaultPath(`${TRIP}/${DOC}.jpg`), isVaultPath(`${TRIP}/${DOC}.webp`), isVaultPath(`${TRIP}/${DOC}.png`),
    isVaultPath(`${TRIP}/${DOC}.gif`)], [true, true, true, true, false]);
});

Deno.test("retry after a half-done delete: row already gone → 200 deleted:false; finish refusal / rpc errors map to HTTP", async () => {
  mock({ finish: { ok: true, deleted: false } });
  const again = await call({ doc_id: DOC });
  eq([again.status, again.j.ok, again.j.deleted], [200, true, false]);
  mock({ finish: { error: "not_manager" } });
  eq((await call({ doc_id: DOC })).status, 403);
  mock({ rpcError: "vault_delete_prepare" });
  eq((await call({ doc_id: DOC })).j.error, "server_error");
  mock({ rpcError: "vault_delete_finish" });
  eq((await call({ doc_id: DOC })).status, 500);
  mock({ prepare: "not json" });
  eq((await call({ doc_id: DOC })).status, 500);
});

Deno.test("CORS: only the app origin and localhost are allowed; no ids / paths in the response", async () => {
  mock();
  const r = await handler(new Request("http://x/", { method: "OPTIONS", headers: { origin: "https://evil.example" } }));
  eq(r.headers.get("access-control-allow-origin"), null);
  const ok = await call({ doc_id: DOC });
  eq(ok.h.get("access-control-allow-origin"), "https://orsela.github.io");
  eq(JSON.stringify(ok.j).includes(PATH), false);
});
