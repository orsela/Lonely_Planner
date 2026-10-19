// CHANGE 2026-10-19 F05-FN-04: copy of create-trip's offline test stub (no previous version).
//   Stands in for npm:@supabase/supabase-js when the tests run without network; the tests replace every call through setDeps().
// deno-lint-ignore-file no-explicit-any
export type SupabaseClient = any;
export function createClient(..._a: unknown[]): SupabaseClient {
  throw new Error("supabase-js stub: not available in unit tests");
}
