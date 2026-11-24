// Lonely Planner · translate-content tests · version 3.0.0-alpha.19.0 · F13-TR
// CHANGE 2026-11-24 F13-TR-FN-03: new file. Stubbed deps; run: node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs supabase/functions/translate-content/test.ts
import { handler, parseArray, resetDeps, setDeps, statusFor } from "./index.ts";
function eq(a: unknown, b: unknown, m = "") { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${m} expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); }
const TRIP = "11111111-2222-4333-8444-555555555555", O = "https://orsela.github.io";
let rpcs: string[] = [], take: any = { ok: true, used: 1, cap: 3 }, up: () => Promise<Response>;
const ok = (arr: unknown) => async () => new Response(JSON.stringify({ content: [{ type: "text", text: JSON.stringify(arr) }], stop_reason: "end_turn" }), { status: 200 });
function setup() {
  rpcs = []; up = ok(["Hanoi", "Rest day"]);
  setDeps({ getUser: async (j: string) => (j === "good" ? { id: "u1" } : null), rpc: async (n: string) => { rpcs.push(n); return { data: n === "tr_take" ? take : { ok: true }, error: null }; }, fetch: (() => up()) as any, env: (k: string) => (k === "ANTHROPIC_API_KEY" ? "k" : undefined) });
}
const req = (body: unknown, auth = "Bearer good") => new Request("https://x/f", { method: "POST", headers: { origin: O, authorization: auth }, body: JSON.stringify(body) });
Deno.test("maps hebrew to english, skips non-hebrew + dupes", async () => {
  setup(); take = { ok: true, used: 1, cap: 3 };
  const r = await handler(req({ trip_id: TRIP, strings: ["האנוי", "יום מנוחה", "האנוי", "Hotel 5"] }));
  eq(r.status, 200); eq((await r.json()).map, { "האנוי": "Hanoi", "יום מנוחה": "Rest day" }); eq(rpcs, ["tr_take"]);
});
Deno.test("no auth 401; not member 403; cap 429", async () => {
  setup(); eq((await handler(req({ trip_id: TRIP, strings: ["א"] }, "Bearer bad"))).status, 401);
  take = { error: "not_member" }; eq((await handler(req({ trip_id: TRIP, strings: ["א"] }))).status, 403);
  take = { error: "daily_cap", used: 3, cap: 3 }; eq((await handler(req({ trip_id: TRIP, strings: ["א"] }))).status, 429);
});
Deno.test("bad model output refunds the run", async () => {
  setup(); take = { ok: true, used: 1, cap: 3 }; up = ok(["only one"]);
  const r = await handler(req({ trip_id: TRIP, strings: ["א", "ב"] }));
  eq(r.status, 502); eq(rpcs, ["tr_take", "tr_refund"]);
});
Deno.test("nothing to translate costs nothing; invalid body 400", async () => {
  setup(); const r = await handler(req({ trip_id: TRIP, strings: ["abc"] })); eq(r.status, 200); eq(rpcs, []);
  eq((await handler(req({ trip_id: "x", strings: [] }))).status, 400);
});
Deno.test("parseArray + statusFor", () => { eq(parseArray('```json\n["a","b"]\n```', 2), ["a", "b"]); eq(parseArray("[1]", 1), null); eq(statusFor("daily_cap"), 429); resetDeps(); });
