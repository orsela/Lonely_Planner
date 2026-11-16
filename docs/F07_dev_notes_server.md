# F07 dev notes — server (conversation 1 of 3)

<!-- CHANGE 2026-11-16 F07-DOCS-04: new file (no previous version). Spec docs/F07_spec.md + claude/Plan_Travel_F07_decisions.md (project library); order of work in claude/Plan_Travel_LEAN_RULES.md (LEAN-05). -->

**Branch `f07-build`** (from `main` 2942f13, alpha.15.3). Version target **3.0.0-alpha.16** (the spec's "alpha.12" is out of date). No client code in this conversation; `RELINK_FEATURE` does not exist yet (conversation 2 adds it, default `'off'`).

## What was built
- `supabase/migrations/0018_f07.sql` — `trip_members.person_id` / `relink_expires_at`; `private.member_sessions`; helpers `private.f07_*`; replaced `join_preview`, `join_request` (+`p_person`), `approve_member`, `claim_transfer`, `member_set_role|rename|remove|leave`, `member_touch` (+session args), `private.f06_other_managers` (persons); new `device_list`, `device_disconnect`, `device_notice_ack`. Idempotent. Service role only.
- `supabase/migrations/0019_qa_f07_harness.sql` — `qa.f07_run()` (46 scenarios; AC1–9, 12, 13 and C1/C3/C5/C8/C11/C12).
- Edge Functions, all **3.0.0-alpha.16.0**: `join-trip` (preview `people` + `relink`, request `person`), `approve-member` (`relink` flag), `manage-members` (touch records the session; actions `devices`, `disconnect_device`, `ack_device_notice`; codes `device_revoked` 403, `last_device` 409).
- Tests: `tests/f07/run.sh` (fn: join-trip 14, approve-member 6, manage-members 15; F05/F06 QA function tests; db: `tests/f07/db_check.py`). Version pins moved in `tests/qa_versions.json`, `tests/f06/function_test.ts`.

## Decisions vs the spec (none changes a user-visible rule)
1. `member_sessions.via` is any lower-case provider name (`^[a-z][a-z0-9_]{1,29}$`: `email`, `google`, …), not only `('anon','email')` — spec C3 says "or the provider name"; F22a has Google.
2. **The `auth.sessions` row is deleted inside `device_disconnect`** (SQL, one transaction), not by the Edge Function. If the delete is refused, the session is still marked `revoked_at` and the device's next `touch` answers `device_revoked`. Result field `auth_session_deleted` says which happened. *To confirm on the real project after 0018 (Claude, conversation 1 follow-up):* a throwaway test is in the checklist below.
3. Session id comes from the `session_id` claim of the JWT the function has already verified with `auth.getUser(jwt)`; `via` from `user.is_anonymous` / `app_metadata.provider` / `identities` (`viaOf`). Label from the User-Agent (`deviceLabel`: "Android · Chrome"); the raw UA is never stored. Because GoTrue may reject a token whose session was deleted, a revoked device can also get a plain 401 — the client must treat both `device_revoked` and 401 as "sign out".
4. Device model (`private.f07_devices`): a row with live account sessions = one device per such session; any other active row = one device. A row whose sessions are all revoked is not a device. The last device of a person cannot be disconnected (`last_device`).
5. C5 lazy expiry: `join_preview` reports `relink.status='expired'` **once** (with the name), then deletes the row; a reload shows the normal join form. The client keeps "expired" in memory for its screen.
6. New error codes: `person_invalid` (guessed / foreign / removed person, or the person was removed before approval — the request row is deleted), `last_device`, `device_revoked`. `already_member` is also returned to an active member asking to relink.
7. `claim_transfer` (F05) also deletes the moved row's old sessions (C11) — otherwise the old phone would stay in the device list.
8. Not changed: `public.admin_trip_summary()` (0008) still counts member **rows** (devices). It is platform-admin only; fix in the next admin change.

## Deploy order (push rule)
1. **Or** runs `supabase/migrations/0018_f07.sql`, then `0019_qa_f07_harness.sql`, in the SQL Editor of project `plan-travel` (never `vietnam-trip-2026`).
2. Claude: `select * from qa.f07_run() order by id;` → expect 46/46 (the harness needs a working `auth.sessions`; it rolls everything back).
3. Claude: `deploy_edge_function` for `join-trip`, `approve-member`, `manage-members` (files `index.ts` + `main.ts`, verify_jwt false). **Not before step 1**: the deployed functions call the new SQL signatures (`join_request(…, p_person)`, `member_touch(…, p_session, …)`); the *old* functions keep working after step 1 (defaults), so there is no gap in that direction.
4. Smoke: POST without a token → 401 with `X-Function-Version: 3.0.0-alpha.16.0` on `join-trip` / `manage-members`.
5. Conversation 2 starts from this branch.

## Known / open
- `tests/f05/function_test.ts` F5-FN-02b (approve-member has no version header) is the old open finding F05-QA-D1, unchanged.
- DB rows superseded on purpose (listed in `tests/f07/db_check.py`): qa.f05 #2; qa.f06 #900 #901 #910 #911; qa.f21 #908. `tests/run_all.sh` still lists only the older ones — add these when the full regression is run before v3.0.0.
- A client on alpha.15.x keeps working against the new server (touch/join/approve calls are backward compatible); it simply never sends `person` and ignores `people` / `relink`.
