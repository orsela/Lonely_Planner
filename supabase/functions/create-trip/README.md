# create-trip · Edge Function (F04)

<!-- CHANGE 2026-10-12 F04-FN-04: new file (no previous version). -->

An invited manager with a verified email looks up the invite and creates the trip. Version **3.0.0-alpha.4.0**.
Contract: `docs/F04_spec.md` §3.1. One function, `POST` body `{action, …}`; every action needs
`Authorization: Bearer <user JWT>` (the function verifies it itself with the service client's `auth.getUser(jwt)`).

| action | input | success (200) | errors |
|---|---|---|---|
| `lookup` | — | `{found:true, draft_name, inviter_name, expires_at}` or `{found:false}` (never ids, tokens or the email) | — |
| `create` | `name, display_name, start_date, end_date, home_currency, default_lang, default_role, countries[], currencies[], center` | `{trip_id, join_code, join_url, created}` | 409 `invite_invalid`, 400 `invalid_payload` `{field}`, 400 `too_many_currencies` |

Common errors: 401 `unauthorized` (missing/invalid bearer or unknown JWT), 403 `email_not_verified` (anonymous user,
no email, or `email_confirmed_at` empty), 400 `invalid_request` (unknown action), 429 `rate_limited` (per user, in
memory: 10 `create` / 30 `lookup` per 10 minutes), 405 `method_not_allowed`, 500 `server_error`.

- `lookup` → `rpc('find_invite_for_email', {p_email})`; `create` → `rpc('create_trip_from_invite', {p_user, p_email, p_payload})`
  (migration `0010_f04.sql`, service role only). The database does all validation, the writes and the idempotency:
  a retry by the same manager returns the same trip with `created:false`.
- `join_url` = `JOIN_URL` base + `#code=` + code. `JOIN_URL` (optional secret) is used only if it parses as a URL,
  starts with `https://`, has a host and ends with `/`; otherwise the default `https://orsela.github.io/Plan_Travel/join/`
  is used and one line `join_url_invalid_fallback` is logged (never the value).
- CORS identical to `invite-manager` (`https://orsela.github.io`, `http://localhost[:port]`).
- Logs: one JSON line per request: action, status, error code. Never the JWT, email, payload or names.

## Testability

`index.ts` exports `FN_VERSION`, `handler(req)`, `setDeps({getUser?, rpc?, now?})` (replaces the Supabase calls and
the clock) and `resetDeps()` (restores them and clears the rate limiter). It does not start a server when imported;
`main.ts` calls `startServer()`.

## Deployment (Claude via the connector, spec §6.4)

Create function `create-trip` with `index.ts` + `main.ts` (entry `main.ts`), **Verify JWT off**. No new secrets
(optional `JOIN_URL`). `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are provided (or `PT_SERVICE_KEY`, preferred).
Apply `0010_f04.sql` first.

## Tests

```
deno test --allow-env supabase/functions/create-trip/test.ts                                  # with network
deno test --allow-env --import-map=supabase/functions/create-trip/test_import_map.json \
          supabase/functions/create-trip/test.ts                                              # offline (stub for supabase-js)
```
