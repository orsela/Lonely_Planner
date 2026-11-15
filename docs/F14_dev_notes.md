# F14 dev notes (smart chat, stage 1)

<!-- CHANGE 2026-11-15 F14-DOCS-03: new file (no previous version). Spec: claude/Plan_Travel_F14_spec.md (project library). -->

## Step 1 — migration 0022 (done 2026-11-15, branch `f14`, base main e4af5c0)
- `supabase/migrations/0022_f14.sql`: `private.chat_usage`, `public.chat_take(p_user, p_trip, p_cap)`, `public.chat_refund(p_trip)`. Service role only.
- Tests: `tests/f14/run.sh --only db` → 23/23 (DB01–DB23: cap, shared counter, viewer allowed, pending/stranger refused, refunds, UTC day, 7-day cleanup, cascade, RLS, grants, public still 9 tables).
- Regression: qa.f01–f06 unchanged; **qa.f21 #908 now fails on purpose** (it lists the exact private tables; `chat_usage` is new). Add `f21:908` to the superseded list of the full run (`tests/run_all.sh`) in the pre-v3.0.0 round.
- Decision vs spec: no `0023` QA harness in the `qa` schema (LEAN) — the same checks are `tests/f14/db_test.sql`; after Or applies 0022, Claude runs the same assertions once on the real database in a rolled-back `execute_sql` transaction.
