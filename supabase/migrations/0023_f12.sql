-- Plan_Travel migration 0023_f12 · version 3.0.0-alpha.18 · F12 (shared document vault, conversation 1: server)
-- CHANGE 2026-11-24 F12-DB-01: first version (no previous version). What changed from 0001–0022:
--   1 new private Storage bucket `trip-docs` (10 MB per file; pdf / jpeg / png / webp). Object path `<trip_id>/<doc_id>.<ext>`
--     (ext = pdf | jpg | png | webp) — the original file name is never part of the path.
--   1 new table in `public`: trip_docs (the 10th public table; the old "public = 9 F01 tables" QA rows are superseded on purpose).
--     RLS on. authenticated: SELECT (any active member of the trip) · INSERT (manager / editor, uploaded_by = auth.uid()) ·
--     UPDATE of title + category only (manager, or the uploader while still manager / editor). NO delete grant and no policy:
--     a document is removed only by the Edge Function `vault-delete` (service role: object first, then row — no orphans).
--     anon: nothing.
--   1 BEFORE INSERT trigger on trip_docs (security definer): the object must already exist in `trip-docs` with the SAME size and
--     the same owner (a client cannot declare a smaller size to dodge the quota), uploader_name is taken from trip_members
--     (not from the client), and the trip's total stays <= 100 MB (D6) — over the cap = SQLSTATE 53400, nothing stored.
--   storage.objects policies (bucket `trip-docs` only): SELECT any active member of the trip in the path; INSERT manager / editor
--     while the trip is under the 100 MB cap; DELETE only the uploader's own object while NO trip_docs row points at it
--     (clean-up after a refused insert). No UPDATE (no upsert, no overwrite).
--   4 small functions in `public`: vault_path_trip(text) (the trip of a well-formed path, else null), vault_used_bytes(uuid)
--     (bytes used by a trip, members only — feeds the quota bar), and the service-role-only vault_delete_prepare /
--     vault_delete_finish used by `vault-delete` (alpha.18.0).
-- Contract: claude/Plan_Travel_F12_spec.md §2–§4 + F12_decisions D1, D4, D6, D9. Deviation from the spec text: DELETE is
--   service-role only (the spec said "manager only in RLS") — stricter, and the only way to keep object + row in step.
-- Idempotent: `if not exists` / `create or replace` / drop-then-create for policies and the trigger; safe to run twice.
-- Requires 0001 (trip_role, trips, trip_members). Does NOT touch any existing table, policy or function.

-- ============================== 1. bucket ==============================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('trip-docs', 'trip-docs', false, 10485760,
        array['application/pdf', 'image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
   set public = false,
       file_size_limit = 10485760,
       allowed_mime_types = array['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];

-- ============================== 2. table ==============================
create table if not exists public.trip_docs (
  id            uuid        primary key default gen_random_uuid(),
  trip_id       uuid        not null references public.trips (id) on delete cascade,
  title         text        not null,
  category      text        not null,
  storage_path  text        not null,
  mime          text        not null,
  size_bytes    integer     not null,
  uploaded_by   uuid        references auth.users (id) on delete set null,
  uploader_name text        not null default '',
  created_at    timestamptz not null default now(),
  constraint trip_docs_title_len   check (char_length(btrim(title)) between 1 and 80),
  constraint trip_docs_category    check (category in ('flights', 'lodging', 'insurance', 'id', 'other')),
  constraint trip_docs_mime        check (mime in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')),
  constraint trip_docs_size        check (size_bytes between 1 and 10485760),
  constraint trip_docs_path_unique unique (storage_path),
  constraint trip_docs_path_shape  check (storage_path = trip_id::text || '/' || id::text || '.' ||
                                          case mime when 'application/pdf' then 'pdf' when 'image/jpeg' then 'jpg'
                                                    when 'image/png' then 'png' else 'webp' end)
);
create index if not exists trip_docs_trip_created_idx on public.trip_docs (trip_id, created_at desc);

alter table public.trip_docs enable row level security;
revoke all on table public.trip_docs from public, anon, authenticated;
grant select on public.trip_docs to authenticated;
grant insert (id, trip_id, title, category, storage_path, mime, size_bytes, uploaded_by) on public.trip_docs to authenticated;
grant update (title, category) on public.trip_docs to authenticated;
grant all on public.trip_docs to service_role;

drop policy if exists trip_docs_select on public.trip_docs;
create policy trip_docs_select on public.trip_docs for select to authenticated
  using (public.trip_role(trip_id) is not null);

drop policy if exists trip_docs_insert on public.trip_docs;
create policy trip_docs_insert on public.trip_docs for insert to authenticated
  with check (uploaded_by = auth.uid() and public.trip_role(trip_id) in ('manager', 'editor'));

drop policy if exists trip_docs_update on public.trip_docs;
create policy trip_docs_update on public.trip_docs for update to authenticated
  using (public.trip_role(trip_id) = 'manager'
         or (uploaded_by = auth.uid() and public.trip_role(trip_id) in ('manager', 'editor')))
  with check (public.trip_role(trip_id) = 'manager'
         or (uploaded_by = auth.uid() and public.trip_role(trip_id) in ('manager', 'editor')));

-- ============================== 3. helper functions ==============================
-- The trip of a well-formed object path "<trip uuid>/<doc uuid>.<pdf|jpg|png|webp>"; null for anything else.
create or replace function public.vault_path_trip(p_name text)
returns uuid
language sql
immutable
set search_path = ''
as $$
  select case
           when p_name ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|jpg|png|webp)$'
           then pg_catalog.split_part(p_name, '/', 1)::uuid
         end
$$;

-- Bytes used by a trip's documents; null unless the caller is an active member (feeds the quota bar; also used by the upload policy).
create or replace function public.vault_used_bytes(p_trip uuid)
returns bigint
language sql
stable
security definer
set search_path = ''
as $$
  select case when public.trip_role(p_trip) is null then null
              else (select coalesce(pg_catalog.sum(d.size_bytes), 0)::bigint from public.trip_docs d where d.trip_id = p_trip)
         end
$$;

revoke execute on function public.vault_path_trip(text)  from public, anon;
revoke execute on function public.vault_used_bytes(uuid) from public, anon;
grant  execute on function public.vault_path_trip(text)  to authenticated, service_role;
grant  execute on function public.vault_used_bytes(uuid) to authenticated, service_role;

-- ============================== 4. insert trigger ==============================
create or replace function public.trip_docs_before_insert()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  c_cap  constant bigint := 104857600;   -- D6: 100 MB per trip
  v_size bigint;
  v_own  text;
  v_used bigint;
  v_name text;
begin
  -- one upload per trip at a time (the sum below must not race)
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('trip_docs:' || new.trip_id::text, 0));

  select (o.metadata ->> 'size')::bigint, o.owner_id
    into v_size, v_own
    from storage.objects o
   where o.bucket_id = 'trip-docs' and o.name = new.storage_path;
  if not found then
    raise exception 'trip_docs: object not found' using errcode = 'P0002';
  end if;
  if v_size is distinct from new.size_bytes::bigint then
    raise exception 'trip_docs: size does not match the object' using errcode = 'P0002';
  end if;
  if new.uploaded_by is not null and v_own is distinct from new.uploaded_by::text then
    raise exception 'trip_docs: object belongs to another user' using errcode = 'P0002';
  end if;

  select coalesce(pg_catalog.sum(d.size_bytes), 0) into v_used from public.trip_docs d where d.trip_id = new.trip_id;
  if v_used + new.size_bytes > c_cap then
    raise exception 'trip_docs: quota exceeded' using errcode = '53400';
  end if;

  select m.display_name into v_name
    from public.trip_members m
   where m.trip_id = new.trip_id and m.user_id = new.uploaded_by and m.status = 'active'
   order by m.joined_at desc nulls last
   limit 1;
  new.uploader_name := coalesce(v_name, '');
  new.title := pg_catalog.btrim(new.title);
  return new;
end;
$$;
revoke all on function public.trip_docs_before_insert() from public, anon, authenticated;

drop trigger if exists trip_docs_before_insert on public.trip_docs;
create trigger trip_docs_before_insert before insert on public.trip_docs
  for each row execute function public.trip_docs_before_insert();

-- ============================== 5. storage.objects policies (bucket trip-docs only) ==============================
drop policy if exists trip_docs_obj_select on storage.objects;
create policy trip_docs_obj_select on storage.objects for select to authenticated
  using (bucket_id = 'trip-docs' and public.trip_role(public.vault_path_trip(name)) is not null);

drop policy if exists trip_docs_obj_insert on storage.objects;
create policy trip_docs_obj_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'trip-docs'
              and public.trip_role(public.vault_path_trip(name)) in ('manager', 'editor')
              and coalesce(public.vault_used_bytes(public.vault_path_trip(name)), 0) < 104857600);

drop policy if exists trip_docs_obj_delete_orphan on storage.objects;
create policy trip_docs_obj_delete_orphan on storage.objects for delete to authenticated
  using (bucket_id = 'trip-docs'
         and owner_id = (auth.uid())::text
         and public.trip_role(public.vault_path_trip(name)) in ('manager', 'editor')
         and not exists (select 1 from public.trip_docs d where d.storage_path = name));

-- ============================== 6. vault-delete support (service role only) ==============================
-- Step 1: may this user delete this document? → {ok:true, trip_id, storage_path} | {error: invalid_request | not_found | not_manager}
-- A non-member gets not_found (no hint that the document exists).
create or replace function public.vault_delete_prepare(p_user uuid, p_doc uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  d public.trip_docs;
  v_role text;
begin
  if p_user is null or p_doc is null then
    return private.f05_err('invalid_request');
  end if;
  select * into d from public.trip_docs t where t.id = p_doc;
  if not found then
    return private.f05_err('not_found');
  end if;
  select m.role into v_role from public.trip_members m
   where m.trip_id = d.trip_id and m.user_id = p_user and m.status = 'active'
   order by (m.role = 'manager') desc limit 1;
  if v_role is null then
    return private.f05_err('not_found');
  end if;
  if v_role <> 'manager' then
    return private.f05_err('not_manager');
  end if;
  return pg_catalog.jsonb_build_object('ok', true, 'trip_id', d.trip_id, 'storage_path', d.storage_path);
end;
$$;

-- Step 2 (after the object is gone): re-checks the manager and deletes the row. A row that is already gone → {ok:true, deleted:false}.
create or replace function public.vault_delete_finish(p_user uuid, p_doc uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  d public.trip_docs;
  r jsonb;
begin
  r := public.vault_delete_prepare(p_user, p_doc);
  if r ? 'error' then
    if r ->> 'error' = 'not_found' and not exists (select 1 from public.trip_docs t where t.id = p_doc) then
      return pg_catalog.jsonb_build_object('ok', true, 'deleted', false);
    end if;
    return r;
  end if;
  delete from public.trip_docs t where t.id = p_doc returning * into d;
  return pg_catalog.jsonb_build_object('ok', true, 'deleted', true, 'trip_id', d.trip_id);
end;
$$;

revoke all on function public.vault_delete_prepare(uuid, uuid) from public, anon, authenticated;
revoke all on function public.vault_delete_finish(uuid, uuid)  from public, anon, authenticated;
grant execute on function public.vault_delete_prepare(uuid, uuid) to service_role;
grant execute on function public.vault_delete_finish(uuid, uuid)  to service_role;
