# approve-member · Edge Function (F05)

<!-- CHANGE 2026-10-19 F05-FN-08: new file (no previous version). -->

An active manager approves a pending member with a role (viewer / editor / manager; none → the trip's default) or rejects
the request (the pending row is deleted). Version **3.0.0-alpha.6.0**. Contract: `docs/F05_spec.md` §3. `verify_jwt=false`.

`POST {member_id, decision:'approve'|'reject', role?}` → `rpc approve_member` (0012_f05.sql; the manager check is there).
200 `{status:'active', member_id, role, display_name, trip_id}` or `{status:'rejected', member_id, display_name}`.
Errors: 401 `unauthorized` · 400 `invalid_request` / `role_invalid` · 403 `not_manager` · 409 `not_pending` · 405 · 500.

Tests: `test.ts` (same runners as join-trip).
