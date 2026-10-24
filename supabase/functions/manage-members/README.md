# manage-members · Edge Function (F06)

<!-- CHANGE 2026-10-22 F06-FN-06: new file (no previous version). -->

A manager changes a member's role or name, removes a member and resets the join link; any member leaves the trip or
records "last seen". Version **3.0.0-alpha.7.0**. Contract: `docs/F06_spec.md` §3.1 (D13: one function, one auth path).
`verify_jwt=false`; the function verifies the bearer JWT itself (`auth.getUser`), like `approve-member`.

| action | input | SQL (0014_f06.sql) | success (200) |
|---|---|---|---|
| `set_role` | `member_id, role` (viewer / editor / manager) | `member_set_role` | `{member_id, trip_id, role, display_name, changed}` |
| `rename` | `member_id, display_name` | `member_rename` | `{member_id, trip_id, display_name, changed}` |
| `remove` | `member_id` | `member_remove` | `{member_id, trip_id, status:'removed', display_name}` |
| `leave` | `trip_id` | `member_leave` | `{ok:true, trip_id, member_id}` |
| `rotate_link` | `trip_id` | `rotate_join_code` | `{code, code_version}` (the SQL `version`; `version` in the body is the function version) |
| `touch` | `trip_id` | `member_touch` (≤ once / 10 min) | `{ok:true, touched}` |

Every body carries `version` and every response the header `X-Function-Version: 3.0.0-alpha.7.0` (exposed via CORS).
Errors `{error, version}`: 401 `unauthorized` · 400 `invalid_request` / `role_invalid` / `name_invalid` · 403 `not_manager`
/ `not_member` · 409 `not_active` / `name_taken` / `last_manager` · 405 · 500.

All permission checks (active manager of that trip, last manager, name rules) are in the database functions. Logs: one
JSON line per request with action, status and error code — never the JWT, ids, codes or names. Secrets: none beyond
Supabase's own.

Tests: `test.ts` (mocked deps). Deno: `deno test --allow-env --no-check --import-map=test_import_map.json test.ts`;
without Deno: `node --experimental-strip-types scripts/dev/deno_test_node.mjs supabase/functions/manage-members/test.ts`.
