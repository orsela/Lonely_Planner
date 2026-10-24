# join-trip · Edge Function (F05)

<!-- CHANGE 2026-10-19 F05-FN-07: new file (no previous version). -->

A device joins a trip from the group link, waits for the manager, and (iPhone) moves its membership to the installed app
with a transfer code. Version **3.0.0-alpha.7.0** <!-- CHANGE 2026-10-22 F06-FN-07: was 3.0.0-alpha.6.0; + header `X-Function-Version`; F06 D2: `member_removed` is no longer produced by the database -->. Contract: `docs/F05_spec.md` §3. `verify_jwt=false`; the function
verifies the bearer JWT itself (`auth.getUser`). Any signed-in identity, **anonymous included**.

| action | input | success (200) |
|---|---|---|
| `preview` | `code` (8 chars; a whole link or `#code=` is accepted) | `{trip_id, name, start_date, end_date, days, members, manager, me:{member_id,status,role,display_name}\|null}` |
| `request` | `code, display_name` | `{trip_id, member_id, status, role, display_name, created}` |
| `cancel` | `trip_id` | `{ok:true}` |
| `issue_transfer` | `trip_id` | `{code:"######", expires_at}` (active members only) |
| `claim_transfer` | `code` (6 digits, spaces ok) | `{trip_id, member_id, role, display_name}` |

Errors `{error}`: 401 `unauthorized` · 400 `invalid_request` / `name_invalid` · 404 `code_invalid` · 409 `name_taken` /
`not_pending` / `transfer_invalid` / `already_member` · 403 `member_removed` / `not_member` · 429 `rate_limited` · 405 · 500.

Each action calls the matching service-role SQL function of `0012_f05.sql` (all validation, rate limits and writes are in
the database). The caller's address goes to the database only as `ip_hash` = SHA-256("lp-f05:" + first X-Forwarded-For).
Logs: action, status, error code — never the JWT, codes, names or addresses. Secrets: none beyond Supabase's own.

Tests: `test.ts` (mocked deps). Deno: `deno test --allow-env --no-check --import-map=test_import_map.json test.ts`;
without Deno: `node --experimental-strip-types scripts/dev/deno_test_node.mjs supabase/functions/join-trip/test.ts`.
