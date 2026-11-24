-- Lonely Planner QA · F12 DB-level test harness · version 3.0.0-alpha.18 · F12 (QA 1.0.0)
-- CHANGE 2026-11-24 F12-QA-01: first version (no previous version). Installs qa.f12_run() in the locked `qa` schema, same pattern
--   as qa.f21_run() (0017) and reusing its helpers (qa.f21_as / f21_rec / f21_try / f21_e): all test data (users, trips, members,
--   storage objects, documents) lives in a sub-transaction that is always rolled back (raise 'f12_rollback'); search_path pinned to
--   '', nothing granted to public/anon/authenticated, SECURITY INVOKER (runs as postgres). The Storage "no direct delete" guard of the
--   hosted project is lifted inside the sub-transaction only (storage.allow_delete_query) — nothing real is deleted or kept.
--
-- Run (after 0023_f12.sql):   select * from qa.f12_run() order by id;
-- Output: one row per scenario (id, name, pass, detail = 'expected: … | actual: …'). Each name starts with the spec §7 criterion
--   it covers (AC1 … AC10) where there is one. Client-side criteria (7, 8, 9 grep part, 10) belong to conversations 2–3.
-- Criteria covered here: 2, 3, 4 (server side), 5, 6; 1 only as "the new table/functions are inert for other trips".

create schema if not exists qa;
revoke all on schema qa from public, anon, authenticated;

-- 'ok N' (rows affected) | 'error <sqlstate>' while impersonating p_uid / p_role
create or replace function qa.f12_do(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f21_as(p_uid, p_role);
  execute p_sql;
  get diagnostics n = row_count;
  execute 'reset role';
  return 'ok ' || n;
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate;
end $f$;

-- rows returned by p_sql while impersonating ('N rows' | 'error <sqlstate>')
create or replace function qa.f12_count(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare n bigint;
begin
  perform qa.f21_as(p_uid, p_role);
  execute 'select count(*) from (' || p_sql || ') f12_s' into n;
  execute 'reset role';
  return n || ' rows';
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate;
end $f$;

-- first column of the first row of p_sql while impersonating ('null' when none; 'error <sqlstate>' on failure)
create or replace function qa.f12_val(p_uid uuid, p_role text, p_sql text)
returns text language plpgsql set search_path = '' as $f$
declare v text;
begin
  perform qa.f21_as(p_uid, p_role);
  execute p_sql into v;
  execute 'reset role';
  return coalesce(v, 'null');
exception when others then
  execute 'reset role';
  return 'error ' || sqlstate;
end $f$;

-- a service-role call: p_expr is a SQL expression returning jsonb
create or replace function qa.f12_j(p_expr text)
returns jsonb language plpgsql set search_path = '' as $f$
declare v jsonb;
begin
  execute 'select ' || p_expr into v;
  return v;
exception when others then
  return pg_catalog.jsonb_build_object('raised', sqlstate || ' ' || sqlerrm);
end $f$;

-- INSERT of a storage object (as postgres, bypasses RLS): owner + declared size in the metadata like Storage writes it
create or replace function qa.f12_obj(p_path text, p_owner uuid, p_size bigint)
returns void language plpgsql set search_path = '' as $f$
begin
  insert into storage.objects (bucket_id, name, owner_id, metadata)
  values ('trip-docs', p_path, p_owner::text, pg_catalog.jsonb_build_object('size', p_size, 'mimetype', 'application/pdf'));
end $f$;

-- INSERT of a document row (as the caller's role) → 'ok 1' | 'error <sqlstate>'
create or replace function qa.f12_doc(p_uid uuid, p_role text, p_id uuid, p_trip uuid, p_by uuid, p_size bigint, p_title text default 'טיסה לבוקרשט')
returns text language plpgsql set search_path = '' as $f$
begin
  return qa.f12_do(p_uid, p_role, pg_catalog.format(
    'insert into public.trip_docs (id, trip_id, title, category, storage_path, mime, size_bytes, uploaded_by) values (%L, %L, %L, %L, %L, %L, %s, %L)',
    p_id, p_trip, p_title, 'flights', p_trip::text || '/' || p_id::text || '.pdf', 'application/pdf', p_size, p_by));
end $f$;

create or replace function qa.f12_run()
returns table(id int, name text, pass boolean, detail text)
language plpgsql set search_path = '' as $$
#variable_conflict use_column
declare
  r      jsonb := '[]'::jsonb;
  au     constant text := 'authenticated';
  u_a1   constant uuid := 'f1200000-0000-4000-8000-0000000000a1';   -- manager of T1
  u_e1   constant uuid := 'f1200000-0000-4000-8000-0000000000e1';   -- editor of T1
  u_e2   constant uuid := 'f1200000-0000-4000-8000-0000000000e2';   -- second editor of T1
  u_v1   constant uuid := 'f1200000-0000-4000-8000-0000000000b1';   -- viewer of T1
  u_x1   constant uuid := 'f1200000-0000-4000-8000-0000000000c1';   -- removed editor of T1
  u_m2   constant uuid := 'f1200000-0000-4000-8000-0000000000d1';   -- manager of T2 (outsider for T1)
  t1     constant uuid := 'f1200000-0000-4000-8000-000000000101';
  t2     constant uuid := 'f1200000-0000-4000-8000-000000000102';
  d1     constant uuid := 'f1200000-0000-4000-8000-0000000001d1';
  d2     constant uuid := 'f1200000-0000-4000-8000-0000000001d2';
  d3     constant uuid := 'f1200000-0000-4000-8000-0000000001d3';
  d4     constant uuid := 'f1200000-0000-4000-8000-0000000001d4';
  d5     constant uuid := 'f1200000-0000-4000-8000-0000000001d5';
  d6     constant uuid := 'f1200000-0000-4000-8000-0000000001d6';
  d7     constant uuid := 'f1200000-0000-4000-8000-0000000001d7';
  d8     constant uuid := 'f1200000-0000-4000-8000-0000000001d8';
  d9     constant uuid := 'f1200000-0000-4000-8000-0000000001d9';
  dz     uuid;
  dv     constant uuid := 'f1200000-0000-4000-8000-0000000001f1';
  dm     constant uuid := 'f1200000-0000-4000-8000-0000000001f2';
  dx     constant uuid := 'f1200000-0000-4000-8000-0000000001f3';
  dy     constant uuid := 'f1200000-0000-4000-8000-0000000001f4';
  mb     constant bigint := 1048576;
  res    jsonb;
  i      int;
  s1 text; s2 text; s3 text; s4 text; s5 text;
  n_trips_before bigint; n_users_before bigint; n_docs_before bigint; n_obj_before bigint;
begin
  select count(*) into n_trips_before from public.trips;
  select count(*) into n_users_before from auth.users;
  select count(*) into n_docs_before from public.trip_docs;
  select count(*) into n_obj_before from storage.objects where bucket_id = 'trip-docs';

  begin
    -- ================= SETUP (postgres, bypasses RLS) =================
    perform qa.f21_as(null, 'postgres');
    perform pg_catalog.set_config('storage.allow_delete_query', 'true', true);
    insert into auth.users (id, aud, role, email, instance_id, created_at, updated_at)
      select u, 'authenticated', 'authenticated', null, '00000000-0000-0000-0000-000000000000', now(), now()
        from unnest(array[u_a1, u_e1, u_e2, u_v1, u_x1, u_m2]) u;
    insert into public.trips (id, name, start_date, end_date, default_role, created_by) values
      (t1, 'F12 רומניה 2027', '2027-04-03', '2027-04-20', 'editor', u_a1),
      (t2, 'F12 קבוצה 2',     '2027-05-30', '2027-06-02', 'viewer', u_m2);
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, approved_at) values
      (t1, u_a1, 'דנה',   'manager', 'active',  now() - interval '90 days', now() - interval '90 days'),
      (t1, u_e1, 'עדן',   'editor',  'active',  now() - interval '70 days', now() - interval '70 days'),
      (t1, u_e2, 'נועם',  'editor',  'active',  now() - interval '69 days', now() - interval '69 days'),
      (t1, u_v1, 'צופה',  'viewer',  'active',  now() - interval '60 days', now() - interval '60 days'),
      (t1, u_x1, 'הוסר',  'editor',  'removed', now() - interval '50 days', now() - interval '50 days'),
      (t2, u_m2, 'מנהל2', 'manager', 'active',  now() - interval '20 days', now() - interval '20 days');

    -- ================= 0xx · schema (§3) =================
    r := qa.f21_rec(r, 1, '§3 bucket trip-docs: private, 10 MB, pdf/jpeg/png/webp', 'false/10485760/application/pdf,image/jpeg,image/png,image/webp',
      (select b.public::text || '/' || b.file_size_limit::text || '/' ||
              (select string_agg(m, ',' order by m) from unnest(b.allowed_mime_types) m)
         from storage.buckets b where b.id = 'trip-docs'));
    r := qa.f21_rec(r, 2, '§3 trip_docs: RLS on; anon has no privilege; authenticated cannot DELETE or UPDATE size/path/owner', 'true/false/false/false/false/true',
      (select c.relrowsecurity::text from pg_catalog.pg_class c where c.oid = 'public.trip_docs'::regclass) || '/' ||
      pg_catalog.has_table_privilege('anon', 'public.trip_docs', 'select')::text || '/' ||
      pg_catalog.has_table_privilege('authenticated', 'public.trip_docs', 'delete')::text || '/' ||
      pg_catalog.has_column_privilege('authenticated', 'public.trip_docs', 'size_bytes', 'update')::text || '/' ||
      pg_catalog.has_column_privilege('authenticated', 'public.trip_docs', 'uploader_name', 'insert')::text || '/' ||
      pg_catalog.has_column_privilege('authenticated', 'public.trip_docs', 'title', 'update')::text);
    alter table public.trip_docs disable trigger trip_docs_before_insert;   -- the CHECKs are tested on their own (the trigger would answer first)
    r := qa.f21_rec(r, 3, '§3 constraints: bad size / mime / category / title / path → check_violation (as the owner role)', 'error 23514/error 23514/error 23514/error 23514/error 23514/error 23514/error 23514',
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, 'x', 'flights', t1||'/'||d9||'.pdf', 'application/pdf', 10485761)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, 'x', 'flights', t1||'/'||d9||'.pdf', 'text/html', 10)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, 'x', 'visa', t1||'/'||d9||'.pdf', 'application/pdf', 10)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, '   ', 'flights', t1||'/'||d9||'.pdf', 'application/pdf', 10)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, repeat('ש', 81), 'flights', t1||'/'||d9||'.pdf', 'application/pdf', 10)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, 'x', 'flights', t1||'/original-name.pdf', 'application/pdf', 10)) || '/' ||
      qa.f21_try(format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes) values (%L,%L,%L,%L,%L,%L,%s)', d9, t1, 'x', 'flights', t1||'/'||d9||'.png', 'application/pdf', 10)));

    alter table public.trip_docs enable trigger trip_docs_before_insert;

    -- ================= 1xx · upload of the object (§2, AC2, AC6) =================
    r := qa.f21_rec(r, 101, 'AC2 editor uploads an object into his trip''s folder', 'ok 1',
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d1||'.pdf', u_e1)));
    r := qa.f21_rec(r, 102, 'AC2 manager uploads an object', 'ok 1',
      qa.f12_do(u_a1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d2||'.pdf', u_a1)));
    r := qa.f21_rec(r, 103, 'AC2 viewer cannot upload an object (server side)', 'error 42501',
      qa.f12_do(u_v1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d3||'.pdf', u_v1)));
    r := qa.f21_rec(r, 104, 'AC6 a manager of ANOTHER trip cannot write into this trip''s folder', 'error 42501',
      qa.f12_do(u_m2, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d3||'.pdf', u_m2)));
    r := qa.f21_rec(r, 105, 'AC6 anon cannot upload', 'error 42501',
      qa.f12_do(null, 'anon', format('insert into storage.objects (bucket_id, name) values (%L, %L)', 'trip-docs', t1||'/'||d3||'.pdf')));
    r := qa.f21_rec(r, 106, 'AC6 a removed member cannot upload', 'error 42501',
      qa.f12_do(u_x1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d3||'.pdf', u_x1)));
    r := qa.f21_rec(r, 107, '§3 malformed paths are refused (original name, wrong extension, nested folder, not a uuid)', 'error 42501/error 42501/error 42501/error 42501',
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/passport.pdf', u_e1)) || '/' ||
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d3||'.exe', u_e1)) || '/' ||
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/x/'||d3||'.pdf', u_e1)) || '/' ||
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', 'not-a-uuid/'||d3||'.pdf', u_e1)));

    -- ================= 2xx · the document row (§2, §3, AC2, AC4, AC6) =================
    perform qa.f21_as(null, 'postgres');
    update storage.objects set metadata = pg_catalog.jsonb_build_object('size', 5 * mb, 'mimetype', 'application/pdf')
     where bucket_id = 'trip-docs' and name in (t1||'/'||d1||'.pdf', t1||'/'||d2||'.pdf');
    r := qa.f21_rec(r, 201, 'AC2 editor inserts a row for his object (size = the object''s)', 'ok 1',
      qa.f12_doc(u_e1, au, d1, t1, u_e1, 5 * mb, '  טיסת הלוך  '));
    r := qa.f21_rec(r, 202, '§3 uploader_name comes from trip_members and the title is trimmed (not from the client)', 'עדן/טיסת הלוך',
      (select t.uploader_name || '/' || t.title from public.trip_docs t where t.id = d1));
    r := qa.f21_rec(r, 203, 'AC2 manager inserts a row', 'ok 1', qa.f12_doc(u_a1, au, d2, t1, u_a1, 5 * mb));
    r := qa.f21_rec(r, 204, '§3 a client cannot set uploader_name or created_at', 'error 42501/error 42501',
      qa.f12_do(u_e1, au, format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes,uploaded_by,uploader_name) values (%L,%L,%L,%L,%L,%L,%s,%L,%L)',
        d3, t1, 'x', 'other', t1||'/'||d3||'.pdf', 'application/pdf', 10, u_e1, 'מתחזה')) || '/' ||
      qa.f12_do(u_e1, au, format('insert into public.trip_docs (id,trip_id,title,category,storage_path,mime,size_bytes,uploaded_by,created_at) values (%L,%L,%L,%L,%L,%L,%s,%L,%L)',
        d3, t1, 'x', 'other', t1||'/'||d3||'.pdf', 'application/pdf', 10, u_e1, now() - interval '9 days')));
    perform qa.f12_obj(t1||'/'||dv||'.pdf', u_v1, 1000);
    perform qa.f12_obj(t1||'/'||dm||'.pdf', u_m2, 1000);
    perform qa.f12_obj(t1||'/'||dx||'.pdf', u_x1, 1000);
    perform qa.f12_obj(t1||'/'||dy||'.pdf', null, 1000);
    r := qa.f21_rec(r, 205, 'AC2 a viewer cannot insert a row (even for an object that exists)', 'error 42501',
      qa.f12_doc(u_v1, au, dv, t1, u_v1, 1000));
    r := qa.f21_rec(r, 206, 'AC6 a manager of another trip, a removed member and anon cannot insert a row', 'error 42501/error 42501/error 42501',
      qa.f12_doc(u_m2, au, dm, t1, u_m2, 1000) || '/' || qa.f12_doc(u_x1, au, dx, t1, u_x1, 1000) || '/' || qa.f12_doc(null, 'anon', dy, t1, null, 1000));
    r := qa.f21_rec(r, 207, 'AC2 an editor cannot file a row under someone else''s user id (the object is the manager''s)', 'error 42501',
      qa.f12_doc(u_e1, au, d2, t1, u_a1, 5 * mb));
    perform qa.f12_obj(t1||'/'||d4||'.pdf', u_e1, 9 * mb);
    r := qa.f21_rec(r, 208, 'AC4/AC5 the declared size must equal the object''s size (no quota dodging)', 'error P0002',
      qa.f12_doc(u_e1, au, d4, t1, u_e1, 1000));
    r := qa.f21_rec(r, 209, '§3 a row for an object that was never uploaded is refused', 'error P0002',
      qa.f12_doc(u_e1, au, d5, t1, u_e1, 1000));
    r := qa.f21_rec(r, 210, '§3 a row cannot point at another user''s object', 'error P0002',
      qa.f12_doc(u_e2, au, d4, t1, u_e2, 9 * mb));
    perform qa.f12_obj(t1||'/'||d6||'.pdf', u_e1, 10485761);
    r := qa.f21_rec(r, 211, 'AC4 a file over 10 MB is refused by the row even when the object exists (server side)', 'error 23514',
      qa.f12_doc(u_e1, au, d6, t1, u_e1, 10485761));

    -- ================= 3xx · read access (AC2, AC6) =================
    r := qa.f21_rec(r, 301, 'AC6 every active role reads the rows and the objects of its trip', '2 rows/2 rows/2 rows/' ||
      (select count(*)::text from storage.objects o where o.bucket_id = 'trip-docs' and o.name like t1||'/%') || ' rows',
      qa.f12_count(u_a1, au, format('select 1 from public.trip_docs where trip_id = %L', t1)) || '/' ||
      qa.f12_count(u_e1, au, format('select 1 from public.trip_docs where trip_id = %L', t1)) || '/' ||
      qa.f12_count(u_v1, au, format('select 1 from public.trip_docs where trip_id = %L', t1)) || '/' ||
      qa.f12_count(u_v1, au, format('select 1 from storage.objects where bucket_id = %L and name like %L', 'trip-docs', t1||'/%')) );
    r := qa.f21_rec(r, 302, 'AC6 another trip''s manager and a removed member read 0 rows and 0 objects; anon is refused', '0 rows/0 rows/0 rows/0 rows/error 42501',
      qa.f12_count(u_m2, au, 'select 1 from public.trip_docs') || '/' ||
      qa.f12_count(u_x1, au, 'select 1 from public.trip_docs') || '/' ||
      qa.f12_count(u_m2, au, format('select 1 from storage.objects where bucket_id = %L', 'trip-docs')) || '/' ||
      qa.f12_count(u_x1, au, format('select 1 from storage.objects where bucket_id = %L', 'trip-docs')) || '/' ||
      qa.f12_count(null, 'anon', 'select 1 from public.trip_docs'));
    r := qa.f21_rec(r, 303, 'AC6 anon sees no object of the bucket', '0 rows or error 42501',
      qa.f12_count(null, 'anon', format('select 1 from storage.objects where bucket_id = %L', 'trip-docs')));

    -- ================= 4xx · rename / recategorise (§2 UPDATE) =================
    s1 := qa.f12_do(u_e1, au, format('update public.trip_docs set title = %L, category = %L where id = %L', 'שם חדש', 'lodging', d1));
    s2 := qa.f12_do(u_a1, au, format('update public.trip_docs set title = %L where id = %L', 'שם מנהל', d1));
    r := qa.f21_rec(r, 401, '§2 the uploader renames his own document; the manager renames anyone''s', 'ok 1/ok 1', s1 || '/' || s2);
    r := qa.f21_rec(r, 402, '§2 another editor and a viewer cannot rename someone else''s document (0 rows)', 'ok 0/ok 0',
      qa.f12_do(u_e2, au, format('update public.trip_docs set title = %L where id = %L', 'פרצה', d2)) || '/' ||
      qa.f12_do(u_v1, au, format('update public.trip_docs set title = %L where id = %L', 'פרצה', d2)));
    r := qa.f21_rec(r, 403, '§2 size / path / owner / trip cannot be changed by a client', 'error 42501/error 42501/error 42501/error 42501',
      qa.f12_do(u_a1, au, format('update public.trip_docs set size_bytes = 1 where id = %L', d1)) || '/' ||
      qa.f12_do(u_a1, au, format('update public.trip_docs set storage_path = %L where id = %L', t1||'/'||d9||'.pdf', d1)) || '/' ||
      qa.f12_do(u_a1, au, format('update public.trip_docs set uploaded_by = %L where id = %L', u_a1, d1)) || '/' ||
      qa.f12_do(u_a1, au, format('update public.trip_docs set trip_id = %L where id = %L', t2, d1)));
    r := qa.f21_rec(r, 404, '§2 a title of 0 or 81 characters / an unknown category is refused on update', 'error 23514/error 23514/error 23514',
      qa.f12_do(u_a1, au, format('update public.trip_docs set title = %L where id = %L', '', d1)) || '/' ||
      qa.f12_do(u_a1, au, format('update public.trip_docs set title = %L where id = %L', repeat('ש', 81), d1)) || '/' ||
      qa.f12_do(u_a1, au, format('update public.trip_docs set category = %L where id = %L', 'visa', d1)));

    -- ================= 5xx · delete (AC3) =================
    r := qa.f21_rec(r, 501, 'AC3 no client can DELETE a row (editor, manager, anon)', 'error 42501/error 42501/error 42501',
      qa.f12_do(u_e1, au, format('delete from public.trip_docs where id = %L', d1)) || '/' ||
      qa.f12_do(u_a1, au, format('delete from public.trip_docs where id = %L', d1)) || '/' ||
      qa.f12_do(null, 'anon', format('delete from public.trip_docs where id = %L', d1)));
    r := qa.f21_rec(r, 502, 'AC3 vault_delete_prepare: manager ok (+ path); editor not_manager; viewer not_manager', 'ok/' || t1 || '/' || d1 || '.pdf/not_manager/not_manager',
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_a1, d1))) || '/' ||
      (qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_a1, d1))->>'storage_path') || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_e1, d1))) || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_v1, d1))));
    r := qa.f21_rec(r, 503, 'AC6 vault_delete_prepare: another trip''s manager / a removed member / an unknown document → not_found; nulls → invalid_request',
      'not_found/not_found/not_found/invalid_request/invalid_request',
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_m2, d1))) || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_x1, d1))) || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_a1, d9))) || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', null::uuid, d1))) || '/' ||
      qa.f21_e(qa.f12_j(format('public.vault_delete_prepare(%L, %L)', u_a1, null::uuid))));
    s1 := qa.f21_e(qa.f12_j(format('public.vault_delete_finish(%L, %L)', u_e1, d2)));
    s2 := qa.f21_e(qa.f12_j(format('public.vault_delete_finish(%L, %L)', u_m2, d2)));
    s3 := coalesce(qa.f12_j(format('public.vault_delete_finish(%L, %L)', u_a1, d2))->>'deleted', 'null');
    res := qa.f12_j(format('public.vault_delete_finish(%L, %L)', u_a1, d2));
    s4 := coalesce(res->>'deleted', 'null');
    s5 := qa.f21_e(res);
    r := qa.f21_rec(r, 504, 'AC3 vault_delete_finish: an editor deletes nothing; the other trip''s manager deletes nothing; the manager deletes the row; twice is harmless',
      'not_manager/not_found/true/false/ok', s1 || '/' || s2 || '/' || s3 || '/' || s4 || '/' || s5);
    r := qa.f21_rec(r, 505, 'AC3 after finish the row is gone and the other rows are untouched', '0/1',
      (select count(*) from public.trip_docs t where t.id = d2)::text || '/' || (select count(*) from public.trip_docs t where t.id = d1)::text);
    r := qa.f21_rec(r, 506, 'C12 the vault-delete functions are service-role only; the helpers are for authenticated members only',
      'false/false/false/false/true/true/false/true',
      pg_catalog.has_function_privilege('authenticated', 'public.vault_delete_prepare(uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('anon', 'public.vault_delete_finish(uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.vault_delete_finish(uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('anon', 'public.vault_used_bytes(uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.vault_used_bytes(uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('service_role', 'public.vault_delete_prepare(uuid, uuid)', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('authenticated', 'public.trip_docs_before_insert()', 'execute')::text || '/' ||
      pg_catalog.has_function_privilege('service_role', 'public.vault_delete_finish(uuid, uuid)', 'execute')::text);

    -- ================= 6xx · orphan clean-up (AC5) =================
    r := qa.f21_rec(r, 601, 'AC5 an editor cannot delete an object that a document row points at (0 rows)', 'ok 0',
      qa.f12_do(u_e1, au, format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d1||'.pdf')));
    r := qa.f21_rec(r, 602, 'AC5 another user (even the manager) cannot delete the editor''s orphan object (0 rows)', 'ok 0',
      qa.f12_do(u_a1, au, format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d4||'.pdf')));
    r := qa.f21_rec(r, 603, 'AC5 the uploader removes his own orphan object (after a refused row)', 'ok 1/0 rows',
      qa.f12_do(u_e1, au, format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d4||'.pdf')) || '/' ||
      qa.f12_count(null, 'postgres', format('select 1 from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d4||'.pdf')));
    r := qa.f21_rec(r, 604, 'AC5 a viewer and an outsider cannot delete any object (0 rows)', 'ok 0/ok 0',
      qa.f12_do(u_v1, au, format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d1||'.pdf')) || '/' ||
      qa.f12_do(u_m2, au, format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d1||'.pdf')));
    r := qa.f21_rec(r, 605, 'AC5 anon cannot delete an object (0 rows or refusal)', 'ok 0 or error 42501',
      qa.f12_do(null, 'anon', format('delete from storage.objects where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d1||'.pdf')));
    r := qa.f21_rec(r, 606, '§3 no client can overwrite an object (no UPDATE policy: 0 rows)', 'ok 0 or error 42501',
      qa.f12_do(u_e1, au, format('update storage.objects set name = name where bucket_id = %L and name = %L', 'trip-docs', t1||'/'||d1||'.pdf')));

    -- ================= 7xx · quota 100 MB per trip (D6, AC5) =================
    -- T1 now holds one 5 MB row (d1). Add 9 × 10 MB documents → 95 MB, then 5 MB → exactly 100 MB, then 1 byte → refused.
    perform qa.f21_as(null, 'postgres');
    r := qa.f21_rec(r, 701, 'D6 vault_used_bytes: a member sees the trip''s bytes, an outsider gets null', '5242880/null',
      qa.f12_val(u_a1, au, format('select public.vault_used_bytes(%L)::text', t1)) || '/' ||
      qa.f12_val(u_m2, au, format('select public.vault_used_bytes(%L)::text', t1)));
    perform qa.f21_as(null, 'postgres');
    for i in 1..9 loop
      dz := pg_catalog.gen_random_uuid();
      perform qa.f12_obj(t1||'/'||dz||'.pdf', u_a1, 10485760);
      if qa.f12_doc(u_a1, au, dz, t1, u_a1, 10485760) <> 'ok 1' then
        r := qa.f21_rec(r, 702, 'D6 filling the trip with 10 MB documents', 'ok 1', qa.f12_doc(u_a1, au, dz, t1, u_a1, 10485760));
      end if;
    end loop;
    perform qa.f21_as(null, 'postgres');
    perform qa.f12_obj(t1||'/'||d5||'.pdf', u_a1, 5 * mb);
    s1 := qa.f12_doc(u_a1, au, d5, t1, u_a1, 5 * mb);
    s2 := (select sum(t.size_bytes)::text from public.trip_docs t where t.trip_id = t1);
    r := qa.f21_rec(r, 703, 'D6/AC5 a document that brings the trip to EXACTLY 100 MB is accepted', 'ok 1/104857600', s1 || '/' || s2);
    perform qa.f12_obj(t1||'/'||d9||'.pdf', u_a1, 1);
    s1 := qa.f12_doc(u_a1, au, d9, t1, u_a1, 1);
    s2 := (select count(*)::text from public.trip_docs t where t.id = d9);
    r := qa.f21_rec(r, 704, 'D6/AC5 the next byte is refused (53400) and nothing is stored', 'error 53400/0', s1 || '/' || s2);
    r := qa.f21_rec(r, 705, 'D6/AC5 at the cap even the OBJECT upload is refused (no orphan can pile up)', 'error 42501',
      qa.f12_do(u_e1, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t1||'/'||d7||'.pdf', u_e1)));
    r := qa.f21_rec(r, 706, 'D6 the cap is per trip: the other trip can still take an object', 'ok 1',
      qa.f12_do(u_m2, au, format('insert into storage.objects (bucket_id, name, owner_id) values (%L, %L, %L)', 'trip-docs', t2||'/'||d8||'.pdf', u_m2)));

    -- ================= 8xx · isolation, cascade, schema =================
    r := qa.f21_rec(r, 801, 'AC1 the new objects do not touch other tables: public = 9 F01 tables + trip_docs, no new policy on them', '10/trip_docs',
      (select count(*)::text from pg_catalog.pg_tables t where t.schemaname = 'public') || '/' ||
      (select string_agg(t.tablename, ',') from pg_catalog.pg_tables t where t.schemaname = 'public'
         and t.tablename not in ('trips', 'trip_join_codes', 'trip_countries', 'trip_currencies', 'trip_members', 'relink_tokens', 'trip_kv',
                                 'platform_admins', 'manager_invites')));
    perform qa.f21_as(null, 'postgres');
    delete from public.trips where id = t1;
    r := qa.f21_rec(r, 802, '§3 deleting a trip removes its document rows (cascade, T1)', '0',
      (select count(*)::text from public.trip_docs t where t.trip_id = t1));

    raise exception 'f12_rollback';
  exception when others then
    perform qa.f21_as(null, 'postgres');
    if sqlerrm <> 'f12_rollback' then
      r := qa.f21_rec(r, 998, 'harness aborted', 'f12_rollback', sqlstate || ' ' || sqlerrm);
    end if;
  end;

  r := qa.f21_rec(r, 999, 'Leftovers after the run: 0 f12 users / trips / documents / objects, counts unchanged', '0/0/0/true',
    (select count(*) from auth.users u where u.id::text like 'f1200000-%')::text || '/' ||
    (select count(*) from public.trips t where t.name like 'F12 %')::text || '/' ||
    (select count(*) from public.trip_docs d where d.trip_id::text like 'f1200000-%')::text || '/' ||
    ((select count(*) from public.trips) = n_trips_before and (select count(*) from auth.users) = n_users_before
      and (select count(*) from public.trip_docs) = n_docs_before
      and (select count(*) from storage.objects where bucket_id = 'trip-docs') = n_obj_before)::text);

  return query select (e->>'id')::int, e->>'name', (e->>'pass')::boolean, e->>'detail' from pg_catalog.jsonb_array_elements(r) e;
end $$;

revoke all on all functions in schema qa from public, anon, authenticated;
