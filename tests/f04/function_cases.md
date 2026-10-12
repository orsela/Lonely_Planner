# F04 · create-trip + invite-manager additions — black-box cases (criteria 5, 6, 10, 18)

Version 1.0.0 · CHANGE 2026-10-12 F04-QA: first version (no previous version).

Written from `docs/F04_spec.md` §3 / §5 and the export surface in `supabase/functions/create-trip/README.md`
(`handler`, `setDeps({getUser, rpc, now})`, `resetDeps`, `FN_VERSION`) and the exported types of
`invite-manager/index.ts` (`makeHandler(Deps)`, `resolveAppUrl`, `DEFAULT_APP_URL`). `create-trip/index.ts` was not read.
Automated in `tests/f04/function_test.ts` (ids below). The database side of the same criteria (what the RPCs do) is in
`tests/f04/sql/qa_f04_cases.md`; the browser side over a fake with the same semantics is `tests/f04/test_f04.py`.

**Conventions.** `POST /functions/v1/create-trip`, body `{action, …}`. "verified" = `getUser(jwt)` returns a user with
`email` and `email_confirmed_at`. RPC errors are PostgREST-shaped `{code:'P0001', message:<code>, details:<field>}`.
Error bodies `{"error":"<code>", …}`.

## Access (C5)

| id | caller | action | expected |
|---|---|---|---|
| CT-01 | no `Authorization`; `Bearer not.a.jwt` (getUser → null) | lookup, create | 401/403, no `found`/`trip_id`/`draft_name`; **no RPC call** |
| CT-02 | anonymous user (no email) | lookup, create | 403 `email_not_verified`; no RPC call |
| CT-03 | email set, `email_confirmed_at` null; or confirmed with empty email | lookup, create | 403 `email_not_verified`; no RPC call |
| CT-12 | verified user; body carries `email`/`p_email`/`p_user`/`user_id` of someone else | lookup, create | RPC args use the JWT user's id and email only |

## lookup (C6)

| id | RPC answer | expected |
|---|---|---|
| CT-10 | `find_invite_for_email` → `{found, invite_id, draft_name, inviter_name, expires_at, email, token_hash}` | 200, keys **exactly** `found, draft_name, inviter_name, expires_at`; raw body has no invite id, user id, email, hash, "token"; RPC called once with `p_email` = JWT email |
| CT-11 | `{found:false}` | 200 `{"found":false}` exactly |

## create (C5, C10)

| id | RPC answer | expected |
|---|---|---|
| CT-20 | `{trip_id, join_code, created:true}` | RPC `create_trip_from_invite(p_user=uid, p_email=email, p_payload)`; every payload field forwarded unchanged; 200 keys exactly `trip_id, join_code, join_url, created`; `join_url = https://orsela.github.io/Plan_Travel/join/#code=<code>` (JOIN_URL unset); no email in the body |
| CT-21 | same with `created:false` (idempotent retry) | 200, same trip/code, `created:false`, same join_url |
| CT-22 | error `invite_invalid` | 409 `invite_invalid`, no trip data |
| CT-23 | error `invalid_payload`, `details` = each field (name … center) | 400 `{error:'invalid_payload', field:<details>}` |
| CT-24 | error `too_many_currencies` | 400 `too_many_currencies` |
| CT-25 | any other DB error; RPC throws | 5xx, DB text not in the body |

## Rate limit (§3.1)

| id | case | expected |
|---|---|---|
| CT-30 | 11 creates by one user within 10 min (controlled clock) | #11 → 429 `rate_limited`, RPC not called; another user still 200; that user's lookup still 200; after 10 min + 1 s → 200 |
| CT-31 | 31 lookups | #31 → 429 `rate_limited`; create unaffected; window slides |
| CT-32 | limit reached, then `resetDeps()` | 200 again (README: resetDeps clears the limiter) |

## HTTP surface

| id | case | expected |
|---|---|---|
| CT-40 | preflight from `https://orsela.github.io`, `http://localhost[:5173/:8080]` | 2xx, origin echoed, same as `invite-manager` `corsHeaders(origin)`; Allow-Headers include authorization, apikey, content-type; POST responses echo the origin |
| CT-40b | preflight from `https://evil.example`, `https://orsela.github.io.evil.example`, `http://localhost.evil.example`, `null` | origin not echoed, not `*` |
| CT-41 | GET; unknown / empty / missing action; malformed JSON | GET 405; others 4xx (never 5xx); no RPC call |
| CT-50 | `JOIN_URL` = unset / `https://example.org/qa/join/` / `ttps://…` / `http://…` / no trailing `/` / `""` / `not a url` / `https://` | only the valid https value with a trailing `/` is used, everything else → default; an invalid value is never logged. (Fresh module per case, so load-time or call-time reading both work.) Note: `https:///x/` is not a failure case — WHATWG parses it as host `x`. |
| CT-60 | lookup, create, anonymous, invalid_payload, invite_invalid, DB error whose message contains the email | captured `console.*` output has no JWT, no email address, no trip name / display name / draft / inviter name |
| CT-00 | exports | `handler`, `setDeps`, `resetDeps`, `FN_VERSION` = 3.0.0-alpha.4.x |

## invite-manager alpha.4 additions (C6, C18)

| id | case | expected |
|---|---|---|
| IM-00 | exports | `FN_VERSION` 3.0.0-alpha.4.x; `DEFAULT_APP_URL` = `https://orsela.github.io/Plan_Travel/app/` |
| IM-01 | `resolveAppUrl` on `ttps://…`, `http://…`, `""`, `"  "`, `not a url`, `https://` | default, `fallback:true`; `https://example.org/qa/app/` kept, `fallback:false`; `undefined` → default |
| IM-02 | `makeHandler` with APP_URL `ttps://…` / `""` / `not a url`, two creates | both emails link to `https://orsela.github.io/Plan_Travel/…#invite=<43>`; no `ttps://` and no empty/relative href in the mail; `app_url_invalid_fallback` logged exactly once; the bad value never logged |
| IM-03 | valid APP_URL | link built from it; no warning |
| IM-10 | `check` valid token | keys exactly `valid, draft_name, inviter_name, expires_at, email`; `email` = the invite address; no hash |
| IM-11 | `check` expired / revoked / used / unknown / malformed / `""` / number / missing | every body byte-identical `{"valid":false}` (shape unchanged), status 200, no `@` |

Not covered here (needs the deployed function / real DB): the real `auth.getUser(jwt)` wiring and the real RPC shapes —
checked by the DB harness (`qa.f04_run()`) and the phone checklist (`tests/f04/MANUAL.md`).
