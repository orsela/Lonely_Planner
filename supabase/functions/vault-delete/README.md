# vault-delete · Edge Function (F12)

<!-- CHANGE 2026-11-24 F12-FN-04: new file (no previous version). -->

A trip **manager** deletes one document of the shared vault. Version **3.0.0-alpha.18.0**. Contract: `claude/Plan_Travel_F12_spec.md` §3.
`verify_jwt=false`; the function verifies the bearer JWT itself (`auth.getUser`), like `manage-members`.

`POST {doc_id}` → `public.vault_delete_prepare(p_user, p_doc)` (manager check, returns the object path) → Storage `remove` of
`trip-docs/<path>` → `public.vault_delete_finish(p_user, p_doc)` (manager check again, deletes the row).
Object first, row second: a failure between them leaves a row without an object (retry-able), never an object without a row.

| status | body | when |
|---|---|---|
| 200 | `{ok:true, deleted, version}` | done (`deleted:false` = row already gone) |
| 400 | `invalid_request` | `doc_id` missing / not a uuid |
| 401 | `unauthorized` | no / bad JWT |
| 403 | `not_manager` | an active member who is not a manager |
| 404 | `not_found` | no such document, **or** the caller is not an active member of its trip (no existence hint) |
| 405 | `method_not_allowed` | not POST |
| 500 | `server_error` | Storage or database failure; the row is kept |

Every response carries `X-Function-Version` (exposed via CORS). Logs: status + error code only — never the JWT, ids, paths or names.
Secrets: none beyond Supabase's own. The path from the database is re-validated (`<uuid>/<uuid>.<pdf|jpg|png|webp>`) before Storage is called.

Tests: `test.ts` (mocked deps, 9 tests). Without Deno:
`node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs supabase/functions/vault-delete/test.ts`
