# request-trip · Edge Function (F21)

<!-- CHANGE 2026-10-27 F21-FN-04: new file (no previous version). -->

Public endpoint of the `/request/` page, version **3.0.0-alpha.8.0**. Contract: `docs/F21_spec.md` §3.1, §4; the exact
result codes and field names are in `docs/F21_dev_notes_server.md` → "Contracts". `POST` body `{action, …}`, no session
(the page sends only the anon `apikey`).

| action | input | success (200) |
|---|---|---|
| `start` | `lang, name, email, countries, month, travellers, note, turnstile_token` | `{ok:true, request_id, sent_at}` |
| `verify` | `request_id, code` | `{ok:true, request_id}` |
| `resend` | `request_id` | `{ok:true, request_id, sent_at}` |

Refusals: `{ok:false, code, error, …}` (same value in `code` and `error`) with an HTTP status.

## Deployment (after `0016_f21.sql`)
1. Secrets: `TURNSTILE_SECRET` (Cloudflare Turnstile secret key, Or enters it); `GMAIL_USER` / `GMAIL_APP_PASSWORD` already
   exist. Optional `TURNSTILE_ALLOW_LOCALHOST=1` only for a local test page (never in production).
2. Deploy with the shared helper file: `index.ts` imports `../invite-manager/index.ts`, so the bundle must contain both
   (`supabase functions deploy request-trip --no-verify-jwt` from the repo root bundles the relative import; in the
   dashboard editor add `invite-manager/index.ts` beside it, or deploy with the CLI/MCP `files` list including it).
3. **Verify JWT OFF** (`verify_jwt=false`): the page has no session.
4. Quick check from a browser console on the app origin: `{"action":"verify","request_id":"x","code":"1"}` →
   `400 {ok:false, code:"invalid_request", field:"request_id"}`.

## Tests
`test.ts` (stubbed RPCs, SMTP and siteverify; no network):
```
node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs supabase/functions/request-trip/test.ts
deno test --allow-env --no-check --import-map=supabase/functions/request-trip/test_import_map.json supabase/functions/request-trip/test.ts
```
