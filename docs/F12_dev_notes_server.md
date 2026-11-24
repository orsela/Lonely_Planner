# F12 · shared document vault — dev notes, conversation 1 (server) · 3.0.0-alpha.18

<!-- CHANGE 2026-11-24 F12-DOC-01: new file (no previous version). -->

Branch `f12-build` (from `origin/main` `fa183cd`). Spec: `claude/Plan_Travel_F12_spec.md`, decisions D1–D9 in `claude/Plan_Travel_F12_decisions.md`.
Applied to `plan-travel` (`zwufpxnioqaweobnvffs`) on 24/11: `0023_f12.sql`, `0024_qa_f12_harness.sql`; Edge Function `vault-delete` v1 (alpha.18.0, verify_jwt off).

## What exists
- **Bucket** `trip-docs`: private, 10 MB, pdf/jpeg/png/webp. Path `<trip_id>/<doc_id>.<pdf|jpg|png|webp>`.
- **Table** `public.trip_docs` (10th public table). authenticated: SELECT (active member), INSERT (manager/editor, `uploaded_by = auth.uid()`;
  columns id, trip_id, title, category, storage_path, mime, size_bytes, uploaded_by only), UPDATE title+category (manager, or the uploader
  while manager/editor). No DELETE grant. anon: nothing.
- **Trigger** `trip_docs_before_insert`: the object must exist with the same size and owner; uploader_name from trip_members; title trimmed;
  trip total ≤ 104857600 bytes (SQLSTATE 53400) under a per-trip advisory lock.
- **storage.objects policies** (bucket only): SELECT member; INSERT manager/editor while trip < 100 MB; DELETE own orphan (no row points at it). No UPDATE.
- **Functions**: `vault_path_trip(text)`, `vault_used_bytes(uuid)` (member → bytes, outsider → null; for the quota bar), service-role-only
  `vault_delete_prepare` / `vault_delete_finish`.
- **vault-delete**: POST `{doc_id}` → prepare → Storage remove → finish. Errors 401/400/403/404/405/500.

## Contract for the page (conversation 2)
1. Upload order: `storage.upload(<trip>/<doc>.<ext>, file, {upsert:false})` → `insert into trip_docs (id, trip_id, title, category, storage_path, mime, size_bytes, uploaded_by)`.
   `id` must equal the doc uuid in the path, `size_bytes` = the file's size, `mime` ∈ the four types, ext ∈ pdf/jpg/png/webp (jpeg → `jpg`).
2. If the INSERT fails (53400 quota, P0002 object problem, 23514 check, 42501 role) → `storage.remove([path])` as the uploader (allowed while no row points at it).
3. Quota bar: `rpc('vault_used_bytes', {p_trip})`; warn at 80 %, block at 100 % (the server blocks both the object upload and the row).
4. Delete (manager): `functions.invoke('vault-delete', {doc_id})`; never `from('trip_docs').delete()` (no grant).
5. Rename / recategorise: `update trip_docs set title, category` only.

## Deviations from the spec text
- DELETE on trip_docs is service-role only (spec: "manager in RLS") — stricter; keeps object and row in step.
- The uploader may rename only while still manager/editor (spec: "or the uploader").
- The trigger also refuses a row whose object has another owner or a different size than declared (closes a quota-dodging hole; not in the spec).

## Tests
`tests/f12/run.sh` — vault-delete 9/9 (Node); local DB: qa.f12_run() 48/48, all other harnesses without new failures. On `plan-travel`: qa.f12_run() 48/48.
Old QA rows superseded on purpose (public now has 10 tables, trip_docs has its own policies/grants): f02#54, f03#54, f04#126, f05#208–210,
f06#912–913, f21#909–910, f23#407 (listed in `tests/f12/db_check.py` EXPECTED). The old F05/F06/F21 rows from F07 stay as in `tests/f07/db_check.py`.

## Known limits / for later conversations
- A storage object can be orphaned if the client dies between upload and insert (no cron cleanup in F12). Deleting a whole trip removes the rows (cascade) but not the objects.
- `qa.f12_run()` inserts into `storage.objects` directly and lifts the hosted "no direct delete" guard (`storage.allow_delete_query`) inside its rolled-back sub-transaction only.
- Phone checks (PDF, image, offline) belong to conversation 3; no client code yet; `VAULT_FEATURE` does not exist yet.
