// CHANGE 2026-11-24 F12-FN-02: copy of manage-members's offline test stub (no previous version).
//   Stands in for npm:@supabase/supabase-js when the tests run without network; the tests replace every call through setDeps().
// deno-lint-ignore-file no-explicit-any
export type SupabaseClient = any;
export function createClient(..._a: unknown[]): SupabaseClient {
  throw new Error("supabase-js stub: not available in unit tests");
}
