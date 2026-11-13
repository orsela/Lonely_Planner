# F23 — server dev notes (migration 0020/0021, `request-trip`, `invite-manager`)

<!-- CHANGE 2026-11-13 F23-DOCS-10: new file (no previous version). Server stage of F23 only; the `/request/` page and the
     admin screen are in docs/F23_dev_notes_client.md. Spec: docs/F23_spec.md. -->

Branch `f23`, base `main` e477da0 (3.0.0-alpha.11). Function versions **3.0.0-alpha.12.0** (`request-trip`,
`invite-manager`). The app and `/request/` are untouched in this stage.

## What was built
| Piece | File | Notes |
|---|---|---|
| Migration | `supabase/migrations/0020_f23.sql` | idempotent; requires 0016 |
| QA harness | `supabase/migrations/0021_qa_f23_harness.sql` | `select * from qa.f23_run() order by id;` → 49 rows |
| Shared approval module (C1, R2) | `supabase/functions/_shared/approve.ts` | token, invite email send, D16 draft name |
| Country list for functions (C6) | `supabase/functions/_shared/countries.ts` | generated: `python3 scripts/dev/gen_fn_countries.py` |
| `request-trip` | `supabase/functions/request-trip/index.ts` | auto-approval, `suggest`, `choose` |
| `invite-manager` | `supabase/functions/invite-manager/index.ts` | `approve_request` sends through the shared module; nothing else |
| Tests | `tests/f23/run.sh`, `tests/f23/integration_test.ts` | functions wired to local PostgreSQL |

## Contracts (for the client stage)
`request-trip` (POST `{action, …}`, anon apikey):

| action | input | success (200) |
|---|---|---|
| `start` | F21 fields; undecided: `where_mode:'undecided'`, `interests[1..6]`, `max_flight '5'|'8'|'any'` (default 5), `pref_note ≤100`, no `countries` | `{ok, request_id, sent_at}` (unchanged) |
| `verify` | `request_id, code` (+ `undecided:true` when the form was undecided) | auto + known: `{ok, request_id, next:'ready', invite_token, mail_sent, countries, month, travellers, draft_name}` · undecided: `{ok, request_id, next:'suggest', token, left:3}` · manual + known: `{ok, request_id}` (F21) |
| `suggest` | `request_id, token` | `{ok, request_id, items:[{country, reason, tags}], left}` or `{ok, request_id, fallback:true, items:[], left}` |
| `choose` | `request_id, token, country` | auto: as `ready` above · manual: `{ok, request_id, next:'pending'}` |

- `FB_Ready` button → `/invite/#invite=<invite_token>`. `mail_sent:false` → hide "שמרנו גם קישור במייל" (C4).
- New refusals: `suggest_limit` 429 (a 4th `suggest`; the page disables the button at `left:0`). A second auto-approval for
  one email on one day → `rate_limited` 429 (the F21 "try tomorrow" text, criterion 9) — from `verify` or `choose`; the
  code is not consumed. Every session problem of `suggest` / `choose` → `request_unknown` 404 (criterion 8).
- `admin_trip_requests()` gains `auto` (auto-approved requests, newest first, ≤100, each with `invite {id, draft_name,
  expires_at, used_at, revoked_at, opened_at, trip_id}` and `where_mode`), `ai_today`, `ai_cap` (30). `requests` now holds
  only pending requests that have a destination. Revoke = the existing `invite-manager` `revoke {invite_id}`.

## Switches
| Switch | Where | Meaning |
|---|---|---|
| `REQUEST_MODE` | built-in default `'auto'` in `request-trip`; the **secret** `REQUEST_MODE` (`auto`/`manual`) wins | `manual` = F21: known requests use the old `request_verify` and wait for the admin |
| `SUGGEST_FEATURE` | secret, `'off'` | `suggest` answers the fallback, nothing counted (the page has its own flag, C9) |
| `ANTHROPIC_API_KEY` | secret (Or) | absent → fallback, nothing counted |
| `SUGGEST_MODEL` | optional secret | overrides the constant `SUGGEST_MODEL` (`claude-haiku-5-5`) |

## Decisions taken while building (flag to Or / QA)
1. **Session token (C5).** "Same request token as verify": F21's verify had no token, so `verify` now creates one for an
   undecided request (random 32 bytes, only its hash stored in `trip_requests.session_hash`), valid 30 minutes.
2. **Two columns/kinds beyond C10:** `session_hash` (above); `mail_log.kind 'invite'` (C4 counts the invite email in the
   50/day cap); `request_attempts.kind 'auto'` (C13 one auto-approval per email per day) next to `'suggest'`.
3. **Auto invite has no admin:** `invited_by` null, `inviter_name` "Lonely Planner" — the Hebrew email headline reads
   "Lonely Planner מזמין אותך לנהל את הטיול …" (**approved by Or 2026-11-13**). The English automatic email was reworded
   on Or's decision (2026-11-13): subject "Your trip is ready to set up", opening "Your email is verified, so your trip is
   ready to set up.", button "Set up the trip". The admin's approval email (manual mode) keeps the F21 text.
4. **Draft trip name (F21 D16)** is built in the function after the approve transaction (the database has no country
   names) and stored with `request_invite_draft`.
5. **Mail failure / cap on the auto invite** never fails the flow: the token is already returned to the browser.
6. **AI count:** a call counts when it starts (per request and per day), also when the model fails; "AI off" and "no key"
   count nothing. The daily cap answers the fallback without calling the model.
7. **A verified request that never got a destination** is deleted after **3 days** (Or, 2026-11-13) and is not listed
   for the admin. Unverified requests keep the F21 rule (5 days).
8. `request_start` and `admin_trip_requests` were **replaced** (same signatures); `request_verify`, `request_approve`,
   `request_approve_undo`, `request_reject`, `find_invite_for_email` are untouched.
9. F21 test files got one line each pinning `REQUEST_MODE='manual'` (`RT.setRequestMode`), and the version pins moved.

## Superseded QA rows (on purpose)
`qa.f21_run()` rows **7, 101, 128** on a database with 0020: row 7 expects `mail_log.kind='invite'` to be refused; its
insert now succeeds and adds one mail to the counts read by 101 and 128. Expected on the real database: f21 98/101.

## Test results (local, 2026-11-13)
- `tests/f23/run.sh --only db`: qa.f23_run 49/49; f01 109/109, f02 37/37, f03 49/49, f04 90/90, f05 118/120 (100, 101),
  f06 169/171 (910, 911), f21 98/101 (7, 101, 128). Migrations applied twice (idempotent).
- `tests/f23/run.sh --only int`: 11/11 (criteria 2–9, 11 server side, logs).
- `tests/f23/run.sh --only f21`: request-trip 14/14, invite-manager 21/21 + 14/14, tests/f21/function_test 33/33.
- `tests/f21/run.sh --only int` 10/10; `--only db` 67/67 (that runner builds 0001…0017 only).

## Not done / not tested
- No real Anthropic call (stubbed) — model name, latency and answer quality are unverified until the key exists.
- Not run on Deno (Node shim only) and not deployed; R2 (Connector + relative imports: `request-trip` now needs
  `invite-manager/index.ts`, `_shared/approve.ts`, `_shared/countries.ts`) is still open.
- Full regression `tests/run_all.sh` not run (heavy; 75% rule). `tests/f21/db_test.py` own scenarios not run on a
  database that has 0020.
- Until the F23 page is merged, the live F21 page keeps working against the new function in auto mode, but shows its old
  "request sent" screen while the invite email already arrives. Deploy the server and merge the client close together,
  or deploy with the secret `REQUEST_MODE=manual` first.
