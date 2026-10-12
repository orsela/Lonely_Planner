// CHANGE 2026-10-12 F04-FN-03: offline test stub (no previous version), same as invite-manager's. Stands in for
// npm:@supabase/supabase-js when the tests run without network; the tests replace every call through setDeps().
// deno-lint-ignore-file no-explicit-any
export type SupabaseClient = any;
export function createClient(..._a: unknown[]): SupabaseClient {
  throw new Error("supabase-js stub: not available in unit tests");
}
