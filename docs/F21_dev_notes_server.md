# F21 · dev notes (server) — open request + super-admin approval (v3.0.0-alpha.8)

<!-- CHANGE 2026-10-27 F21-DOCS-10: new file (no previous version). -->

Scope: spec `docs/F21_spec.md` §2 (data), §3 (Edge Functions), §4 (limits), §5.1 (reject email), server side of §1.10.
Base `hotfix-7.2` (3.0.0-alpha.7.2), branch `f21`. **Nothing was deployed or run against Supabase**; every check below is local.

## 0. Contracts (client developers: match these exactly)

### `request-trip` (public, `POST`, header `apikey` only)
- **start** body: `{action:"start", lang:"he"|"en", name, email, countries:[ISO-2…], month:"YYYY-MM"|null, travellers:int,
  note:string|null, turnstile_token}`. `month` may also be `"YYYY-MM-01"`; countries are trimmed and upper-cased, the email
  trimmed and lower-cased, an empty note becomes null.
- **verify** body: `{action:"verify", request_id, code}` — `code` is 6 digits, spaces ignored.
- **resend** body: `{action:"resend", request_id}` (no Turnstile).
- **Success:** start / resend `200 {ok:true, request_id, sent_at}` (`sent_at` ISO timestamp from the database, use it for the
  60 s timer); verify `200 {ok:true, request_id}`.
- **Refusal body:** `{ok:false, code:"<code>", error:"<code>", …extra}` — `code` and `error` carry the same value; read it
  from the body whatever the HTTP status.

| code | HTTP | extra | when |
|---|---|---|---|
| `invalid_request` | 400 | `field` | `field` ∈ `action`, `lang`, `name`, `email`, `countries`, `month`, `travellers`, `note`, `request_id`, `code` (and `payload` only from a direct database call) |
| `turnstile_failed` | 403 | — | siteverify not successful, hostname not `orsela.github.io`, missing token, secret not configured, Cloudflare unreachable |
| `rate_limited` | 429 | `retry_in` (s) only for the resend cooldown | 4th start per email / 11th per IP per day; 21st wrong verify per IP per hour; resend < 60 s after the last send; 4th resend |
| `daily_limit` | 429 | — | cap of 50 F21 mails today (start, resend) **or** ≥100 verified requests waiting |
| `code_wrong` | 400 | `attempts_left` (4…1) | wrong code, attempts 1–4 |
| `code_locked` | 423 | — | 5th wrong code — the row is deleted (start over) |
| `code_expired` | 410 | — | > 10 min since the last send (resend still allowed) |
| `request_unknown` | 404 | — | unknown / deleted id, or already verified |
| `email_failed` | 502 | — | the code email could not be sent (start: nothing stored; resend: send again) |
| `server_error` | 500 | — | anything else |

### `invite-manager` (admin JWT; existing refusal shape `{error:code, …}`)
- `approve_request {request_id, draft_name}` → `200 {ok:true, request_id, invite_id, email, draft_name, expires_at, lang,
  revoked_invite_id}` (`revoked_invite_id` null when no invite was replaced). Errors: `400 invalid_request` (bad id),
  `400 invalid_name` (draft > 80 chars or control chars, same as `create`), `403 not_platform_admin`, `409 request_closed`,
  `502 email_failed` (nothing changed), `500 server_error`. An empty/blank `draft_name` → null.
- `reject_request {request_id, send_mail:boolean}` → `200 {ok:true, request_id, mail_sent:boolean}` plus
  `mail_skipped:"daily_limit"|"email_failed"` when a chosen mail was not sent. `send_mail` absent = false; non-boolean → 400
  `invalid_request`. Errors: `403`, `409 request_closed`.

### `public.admin_trip_requests()` (rpc, authenticated; anyone but a platform admin → error `42501`, message `not_platform_admin`)
```
{cap:50, mail_today:int,
 requests:[{id, lang:"he"|"en", name, email, countries:["PT",…], month:"YYYY-MM-01"|null, travellers:int, note:string|null,
            verified_at, manages:[trip names, sorted], active_invite:{id, draft_name, last_sent_at, expires_at}|null}]}
```
`requests` = verified pending rows only, oldest `verified_at` first. `active_invite` = unused, unrevoked and **unexpired**
(an expired-but-unrevoked invite is not shown, but approving still revokes it — it holds the one-per-email slot).
`manages` = active manager memberships of the auth user whose email (case-insensitive) is the request's email.

### `find_invite_for_email` / `create-trip lookup`
`prefill: {name, countries:[ISO-2], month:"YYYY-MM-01"|null, lang:"he"|"en"}` — present only when the invite came from a
request whose row still exists; otherwise the key is absent and the answer is exactly alpha.7.2's.

## 1. What changed (file → why)

| File | CHANGE ID | What |
|---|---|---|
| `supabase/migrations/0016_f21.sql` | F21-DB-01/02 | 3 private tables (RLS on, no policies, service role only); `manager_invites.request_id` (FK → private, on delete set null) + `lang` (default `he`); helpers `private.f21_*` (day start / month start in Asia/Jerusalem, mail count, cleanup, attempt count/log); entry RPCs `request_start`, `request_verify`, `request_resend`, `request_mail_failed`, `request_approve`, `request_approve_undo`, `request_reject` (service role); `admin_trip_requests()` (authenticated, refuses non-admins); `find_invite_for_email` replaced (+prefill). Idempotent (applied twice locally). |
| `supabase/migrations/0017_qa_f21_harness.sql` | F21-QA-01 | `qa.f21_run()` — 101 scenarios, rolled back, F01–F06 pattern |
| `supabase/functions/request-trip/*` | F21-FN-01…04 | new function alpha.8.0: index.ts, main.ts, README, test.ts (14), stub, import map |
| `supabase/functions/invite-manager/index.ts`, `main.ts`, `README.md` | F21-FN-10…13, 15 | alpha.8.0: `approve_request`, `reject_request`, English invite, reject email, `resend` in stored lang, optional `Deps.rpc` |
| `supabase/functions/invite-manager/test_f21.ts` | F21-FN-14 | 14 tests incl. the Hebrew byte-identity proof |
| `supabase/functions/create-trip/index.ts`, `main.ts`, `README.md` | F21-FN-20, 23 | alpha.8.0: `lookup` passes `prefill` (shape-checked by `cleanPrefill`) |
| `supabase/functions/create-trip/test.ts` | F21-FN-21 | **one existing line**: version pin alpha.4 → alpha.8 |
| `supabase/functions/create-trip/test_f21.ts` | F21-FN-22 | 4 tests |
| `scripts/dev/f21_db_check.py` | F21-DEVDB-01 | local Postgres check (below) |

Hebrew invite byte-identity: `test_f21.ts` holds SHA-256 snapshots of `renderInviteEmail()` output for two inputs, taken
from the alpha.7.2 file (index.ts sha256 `4c8b4599…4fd5`) **before** any F21 edit; `lang:'he'` and no `lang` both match. The
Hebrew code path in `renderInviteEmail` is untouched (the `en` branch returns before it).

## 2. Interpretations and deviations (spec silent or needed a mechanism)
1. **`request_mail_failed(p_request, p_action)`** — a new service-role RPC not listed in §2.6. §3.1 says "if the email fails:
   delete the row (the code mail log row is removed with it)", and the function has no table access. `'start'` deletes the
   unverified row and its code mail row; `'resend'` deletes the newest code mail row, restores `resend_count` and lifts the
   cooldown. The new code hash stays (the previous code is already dead), so the requester taps "resend" again.
2. **`private.mail_log.request_id`** (nullable, **no FK**) — added so (1) removes exactly the unsent mail. No FK on purpose:
   replacing or cleaning up a request must never give mail headroom back (D10).
3. **Extra result keys:** `request_resend` also returns `email, lang` (needed to send the new code); `request_approve` also
   returns `email, name, lang, draft_name` (for the invite email). Both are service-role only.
4. **Limits order in `request_start`:** per-email/per-IP limits are checked first and every start that reaches the database
   is logged as an attempt (even an invalid one — "counted ok or not"), then validation, then queue (≥100 pending) and cap
   (both `daily_limit`). The function validates before Turnstile, so a normal client never spends an attempt on a bad form.
5. **Resend codes:** cooldown and the 4th resend both answer `rate_limited` (cooldown adds `retry_in`), to stay within the
   result codes of the brief. **Verify on an already verified request** → `request_unknown`.
6. **Approve revokes any open invite of the email**, expired or not (an expired-unrevoked invite still holds the unique
   slot; otherwise the insert would fail). `revoked_invite_id` is that id. `request_approve` / `request_reject` also check
   `platform_admins` themselves (`not_platform_admin`), in addition to the function's `requireAdmin`.
7. **D12 atomicity:** revoke + insert + status change run in one function call (one transaction); `f21_db_check.py` proves a
   failing insert rolls the revoke back. `request_approve_undo` re-opens the revoked invite only if no other open invite
   exists for the email and only deletes an invite whose `request_id` matches.
8. **Reject mail that fails to send:** the reject stands, the answer is `mail_skipped:'email_failed'`; the `reject` row in
   `mail_log` stays (counted) and `reject_mailed` stays true — see open question 2.
9. **Hashes:** `ip_hash` = plain SHA-256 hex of the first `X-Forwarded-For` (spec wording; F05 used a prefix). Code hash =
   SHA-256 hex of `lower(request_id) + code`, no separator.
10. **`admin_trip_requests()` is `volatile`** (it runs cleanup); `month` is returned as `YYYY-MM-01`.
11. **English resend greeting:** `resend` of an `en` invite reads the requester's name from `find_invite_for_email().prefill`;
    for an already-expired invite there is no prefill and the greeting is "Hi,". The English email does not show the
    inviter's (Hebrew) name — the artboard has none.
12. **Logs** carry only fn, version, action, status, error code, event, request/invite ids and a masked mailer error (addresses
    and any 6-digit run replaced). `request-trip` adds the `X-Function-Version` header (as manage-members / join-trip).

## 3. Open questions
1. **QA version pins:** `tests/qa_versions.json` (`invite-manager`, `create-trip` → 3.0.0-alpha.8.0, + `request-trip`) and four
   cases in `tests/f04/function_test.ts` (CT-00, IM-00, NAME-02, NAME-03) pin alpha.4.x / 4.1 and now fail. Not my files.
2. Should a reject mail that failed to send un-count the cap row and set `reject_mailed=false`? (One more RPC; today it stays
   counted — conservative for the Gmail quota.)
3. `qa.f06_run()` rows 910/911 (pin the exact contents of schema `private`) fail by design after 0016; QA owns 0015 — keep as
   "expected" (as F05 100/101) or amend that harness. `qa.f21_run()` 908 covers the new contents.

## 4. How to run the checks
```
service postgresql start
sudo -u postgres python3 scripts/dev/f21_db_check.py ""
#   0001…0015, 0016 ×2, 0017 ×2 on a scratch DB; qa.f01–f06 + qa.f21; D12 atomicity; direct-call permission checks
node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
     supabase/functions/request-trip/test.ts supabase/functions/invite-manager/test_f21.ts supabase/functions/create-trip/test_f21.ts \
     supabase/functions/invite-manager/test.ts supabase/functions/create-trip/test.ts
```
Results 2026-10-30: qa.f01 109/109, f02 37/37, f03 49/49, f04 90/90, f05 118/120 (+2 expected F06 D2), f06 169/171 (+2 expected,
open question 3), **qa.f21 101/101**, extra DB checks 6/6, 0 leftovers. Functions: request-trip 14/14, invite-manager
21/21 + 14/14, create-trip 9/9 + 4/4; join-trip 11/11, approve-member 4/4, manage-members 8/8, QA f06 19/19, QA f05 12/13
(pre-existing KNOWN-BUG F05-QA-D1), QA f04 27/31 (the 4 version pins of open question 1).
(`--experimental-transform-types` is needed: the functions use TypeScript parameter properties.)

## 5. Deploy notes for Or (beyond spec §7)
- `request-trip` imports `../invite-manager/index.ts`: deploy from the repo with the CLI (bundles it) or give both files to
  the dashboard/MCP deploy. **Verify JWT OFF** for `request-trip` (as for invite-manager / create-trip).
- Do not set `TURNSTILE_ALLOW_LOCALHOST` in production.
- Order: `0016_f21.sql` then `0017_qa_f21_harness.sql` (needs `pgcrypto` in `extensions`, present on Supabase). Expect
  qa.f06 910/911 to fail (open question 3).
- Deploy `invite-manager` / `create-trip` alpha.8.0 only after 0016 (they read `manager_invites.lang` / call the new RPCs).

## Architect answers (2026-10-30)
- Failed reject email still counts toward the 50/day cap: accepted (conservative for the Gmail account).
- English resend of an expired invite greets "Hi,": accepted.
- `tests/qa_versions.json` bumped to alpha.8 / alpha.8.0 (+ request-trip). The 4 hard-coded alpha.4.x pins in
  `tests/f04/function_test.ts` (CT-00, IM-00, NAME-02, NAME-03) and `qa.f06_run()` rows 910/911 (exact `private` contents)
  are expected F21 changes — the QA team updates or deselects them with a reason, as in `tests/run_all.sh`.
- Page ↔ server: the page sends `month` as `YYYY-MM-01`; the server accepts `YYYY-MM` and `YYYY-MM-01` — compatible.
