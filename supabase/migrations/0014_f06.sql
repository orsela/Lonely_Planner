-- Plan_Travel migration 0014_f06 · version 3.0.0-alpha.7 · F06 (a manager changes roles, removes members and resets the link)
-- CHANGE 2026-10-22 F06-DB-01: first version (no previous version). What changed from 0001–0013:
--   6 new service-role-only functions in `public`, used by the Edge Function `manage-members` (alpha.7.0):
--     public.member_set_role(p_user uuid, p_member uuid, p_role text)   returns jsonb   (spec §2.1)
--     public.member_rename(p_user uuid, p_member uuid, p_name text)     returns jsonb   (spec §2.2)
--     public.member_remove(p_user uuid, p_member uuid)                  returns jsonb   (spec §2.3)
--     public.member_leave(p_user uuid, p_trip uuid)                     returns jsonb   (spec §2.4)
--     public.rotate_join_code(p_user uuid, p_trip uuid)                 returns jsonb   (spec §2.5)
--     public.member_touch(p_user uuid, p_trip uuid)                     returns jsonb   (spec §2.8)
--   4 new internal helpers in `private` (closed to clients): f06_is_manager, f06_other_managers, f06_new_join_code and the
--   trigger function f06_tripname_sync + trigger `trip_kv_tripname_sync` on public.trip_kv (spec §2.7, D4).
--   CHANGED (create or replace, F05 behaviour otherwise identical, spec §2.6 / D2):
--     public.join_preview  — a `removed` row of the caller is reported as me=null (a new identity: the form shows);
--                            0012 returned me={status:'removed'} and the join page showed "הוסרת מהטיול".
--     public.join_request  — a `removed` row of the caller is RE-USED as a new request (status pending, new display_name,
--                            role = trips.default_role, joined_at = now(), approved_at = null) under the same F05 limits
--                            (3 successful requests per 24 h, 20 pending per trip, name rules); 0012 returned member_removed.
--                            `member_removed` stays a valid code but is no longer produced.
--   No new tables, no new policies, no new grants on existing tables; `public` still has exactly the 9 F01 tables. The F01
--   trigger `trip_members_last_manager` stays in force as the backstop for every role / status change below.
--
-- Contract: docs/F06_spec.md §2 (decisions D1–D13). Idempotent: `create or replace` + `drop trigger if exists` + re-applied
-- grants; safe to run more than once. Requires 0012_f05.sql (private.f05_* helpers) and pgcrypto in schema `extensions`.
--
-- Error contract (F05 pattern, deliberately NOT raised): refusals are RETURNED as {"error":"<code>"}. Codes:
--   not_manager · not_member · not_active · role_invalid · name_invalid · name_taken · last_manager · invalid_request
-- An unknown p_member is reported as `not_active` (there is no active member with that id).

-- ===========================================================================
-- 1. Internal helpers (not callable by clients)
-- ===========================================================================

-- is p_user an ACTIVE manager of p_trip?
create or replace function private.f06_is_manager(p_user uuid, p_trip uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.trip_members m
                  where m.trip_id = p_trip and m.user_id = p_user and m.role = 'manager' and m.status = 'active')
$$;

-- number of active managers of p_trip other than member p_except
create or replace function private.f06_other_managers(p_trip uuid, p_except uuid)
returns int
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.count(*)::int from public.trip_members m
   where m.trip_id = p_trip and m.role = 'manager' and m.status = 'active' and m.id <> p_except
$$;

-- a random 8-char join code from the F01 alphabet (32 chars: byte % 32 is unbiased) — same generator as 0010
create or replace function private.f06_new_join_code()
returns text
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  c_alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  v_bytes bytea := extensions.gen_random_bytes(8);
  v_code  text := '';
  v_i     int;
begin
  for v_i in 0..7 loop
    v_code := v_code || pg_catalog.substr(c_alphabet, (pg_catalog.get_byte(v_bytes, v_i) % 32) + 1, 1);
  end loop;
  return v_code;
end;
$$;

-- ===========================================================================
-- 2. member_set_role — an active manager changes an active member's role (spec §2.1)
-- ===========================================================================
create or replace function public.member_set_role(p_user uuid, p_member uuid, p_role text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m record;
begin
  if p_user is null or p_member is null then
    return private.f05_err('invalid_request');
  end if;
  if coalesce(p_role, '') not in ('manager', 'editor', 'viewer') then
    return private.f05_err('role_invalid');
  end if;
  select mm.id, mm.trip_id into m from public.trip_members mm where mm.id = p_member;
  if m.id is null then
    return private.f05_err('not_active');
  end if;
  -- serialize role / status changes in one trip (same lock as the F01 last-manager trigger)
  perform 1 from public.trips t where t.id = m.trip_id for no key update;
  select mm.id, mm.trip_id, mm.user_id, mm.status, mm.role, mm.display_name into m
    from public.trip_members mm where mm.id = p_member for update;
  if not private.f06_is_manager(p_user, m.trip_id) then
    return private.f05_err('not_manager');
  end if;
  if m.status <> 'active' then
    return private.f05_err('not_active');
  end if;
  if m.role = p_role then
    return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'role', m.role,
                                         'display_name', m.display_name, 'changed', false);
  end if;
  if m.role = 'manager' and private.f06_other_managers(m.trip_id, m.id) = 0 then
    return private.f05_err('last_manager');
  end if;
  begin
    update public.trip_members set role = p_role where id = m.id;
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'role', p_role,
                                       'display_name', m.display_name, 'changed', true);
end;
$$;

-- ===========================================================================
-- 3. member_rename — an active manager fixes an active member's display_name (spec §2.2, D7)
-- ===========================================================================
create or replace function public.member_rename(p_user uuid, p_member uuid, p_name text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m      record;
  v_name text := private.f05_clean_name(p_name);
begin
  if p_user is null or p_member is null then
    return private.f05_err('invalid_request');
  end if;
  select mm.id, mm.trip_id into m from public.trip_members mm where mm.id = p_member;
  if m.id is null then
    return private.f05_err('not_active');
  end if;
  -- serialize with join_request / other renames (name check)
  perform 1 from public.trips t where t.id = m.trip_id for no key update;
  select mm.id, mm.trip_id, mm.status, mm.display_name into m
    from public.trip_members mm where mm.id = p_member for update;
  if not private.f06_is_manager(p_user, m.trip_id) then
    return private.f05_err('not_manager');
  end if;
  if m.status <> 'active' then
    return private.f05_err('not_active');
  end if;
  if pg_catalog.char_length(v_name) < 1 or pg_catalog.char_length(v_name) > 40 then
    return private.f05_err('name_invalid');
  end if;
  if exists (select 1 from public.trip_members x
              where x.trip_id = m.trip_id and x.id <> m.id and x.status in ('pending', 'active')
                and private.f05_name_key(x.display_name) = private.f05_name_key(v_name)) then
    return private.f05_err('name_taken');
  end if;
  if m.display_name is distinct from v_name then
    update public.trip_members set display_name = v_name where id = m.id;
  end if;
  return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'display_name', v_name,
                                       'changed', m.display_name is distinct from v_name);
end;
$$;

-- ===========================================================================
-- 4. member_remove — an active manager removes another active member (spec §2.3, D2, D12)
-- ===========================================================================
create or replace function public.member_remove(p_user uuid, p_member uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m record;
begin
  if p_user is null or p_member is null then
    return private.f05_err('invalid_request');
  end if;
  select mm.id, mm.trip_id into m from public.trip_members mm where mm.id = p_member;
  if m.id is null then
    return private.f05_err('not_active');
  end if;
  perform 1 from public.trips t where t.id = m.trip_id for no key update;
  select mm.id, mm.trip_id, mm.user_id, mm.status, mm.role, mm.display_name into m
    from public.trip_members mm where mm.id = p_member for update;
  if not private.f06_is_manager(p_user, m.trip_id) then
    return private.f05_err('not_manager');
  end if;
  if m.user_id = p_user then
    return private.f05_err('invalid_request');      -- yourself: use member_leave
  end if;
  if m.status <> 'active' then
    return private.f05_err('not_active');
  end if;
  if m.role = 'manager' and private.f06_other_managers(m.trip_id, m.id) = 0 then
    return private.f05_err('last_manager');
  end if;
  begin
    update public.trip_members set status = 'removed' where id = m.id;
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  delete from private.transfer_codes c where c.member_id = m.id and c.used_at is null;
  return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'status', 'removed',
                                       'display_name', m.display_name);
end;
$$;

-- ===========================================================================
-- 5. member_leave — the caller leaves the trip (spec §2.4, D5, D6)
-- ===========================================================================
create or replace function public.member_leave(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m record;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  perform 1 from public.trips t where t.id = p_trip for no key update;
  select mm.id, mm.trip_id, mm.role into m
    from public.trip_members mm where mm.trip_id = p_trip and mm.user_id = p_user and mm.status = 'active' for update;
  if m.id is null then
    return private.f05_err('not_member');
  end if;
  if m.role = 'manager' and private.f06_other_managers(p_trip, m.id) = 0 then
    return private.f05_err('last_manager');
  end if;
  begin
    update public.trip_members set status = 'removed' where id = m.id;
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  delete from private.transfer_codes c where c.member_id = m.id and c.used_at is null;
  return pg_catalog.jsonb_build_object('ok', true, 'trip_id', p_trip, 'member_id', m.id);
end;
$$;

-- ===========================================================================
-- 6. rotate_join_code — an active manager replaces the trip's join code (spec §2.5, D3)
--    Pending rows and transfer codes are not touched.
-- ===========================================================================
create or replace function public.rotate_join_code(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_code text;
  v_ver  int;
  v_try  int;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  if not private.f06_is_manager(p_user, p_trip) then
    return private.f05_err('not_manager');
  end if;
  for v_try in 1..8 loop
    v_code := private.f06_new_join_code();
    begin
      update public.trip_join_codes
         set code = v_code, version = version + 1, rotated_at = pg_catalog.now()
       where trip_id = p_trip
       returning version into v_ver;
      if v_ver is null then
        -- a trip without a code row (not created by F04): create it
        insert into public.trip_join_codes (trip_id, code) values (p_trip, v_code) returning version into v_ver;
      end if;
      return pg_catalog.jsonb_build_object('code', v_code, 'version', v_ver);
    exception when unique_violation then
      v_ver := null;   -- the same code exists for another trip: try another
    end;
  end loop;
  raise exception 'join_code_exhausted' using errcode = 'P0001';
end;
$$;

-- ===========================================================================
-- 7. member_touch — the caller's last_seen_at, at most once per 10 minutes (spec §2.8)
-- ===========================================================================
create or replace function public.member_touch(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_id uuid;
  n    int;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  select m.id into v_id from public.trip_members m
   where m.trip_id = p_trip and m.user_id = p_user and m.status = 'active';
  if v_id is null then
    return private.f05_err('not_member');
  end if;
  update public.trip_members set last_seen_at = pg_catalog.now()
   where id = v_id and (last_seen_at is null or last_seen_at < pg_catalog.now() - interval '10 minutes');
  get diagnostics n = row_count;
  return pg_catalog.jsonb_build_object('ok', true, 'touched', n > 0);
end;
$$;

-- ===========================================================================
-- 8. join_preview / join_request (D2): a removed identity may ask again. Everything else is the 0012 code unchanged.
-- ===========================================================================
create or replace function public.join_preview(p_user uuid, p_code text, p_ip text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_trip uuid;
  t      record;
  me     record;
  v_n    int;
begin
  if p_user is null then
    return private.f05_err('invalid_request');
  end if;
  if pg_catalog.random() < 0.05 then
    delete from private.join_attempts where at < pg_catalog.now() - interval '7 days';
  end if;
  if private.f05_count('preview', p_user, null, null, null, interval '1 hour') >= 30
     or (p_ip is not null and private.f05_count('preview', null, p_ip, null, null, interval '1 hour') >= 60) then
    return private.f05_err('rate_limited');
  end if;

  v_trip := private.f05_trip_for_code(p_code);
  perform private.f05_log('preview', p_user, v_trip, p_ip, v_trip is not null);
  if v_trip is null then
    return private.f05_err('code_invalid');
  end if;

  select tr.id, tr.name, tr.start_date, tr.end_date into t from public.trips tr where tr.id = v_trip;
  select pg_catalog.count(*)::int into v_n from public.trip_members m where m.trip_id = v_trip and m.status = 'active';
  -- CHANGE 2026-10-22 F06-DB-02 (D2): a `removed` row is ignored here (the caller is shown the form, as a new identity).
  --   0012: the removed row was returned as me={status:'removed'}.
  select m.id, m.status, m.role, m.display_name into me
    from public.trip_members m where m.trip_id = v_trip and m.user_id = p_user and m.status <> 'removed';

  return pg_catalog.jsonb_build_object(
    'trip_id',    t.id,
    'name',       t.name,
    'start_date', t.start_date,
    'end_date',   t.end_date,
    'days',       case when t.start_date is not null and t.end_date is not null then (t.end_date - t.start_date) + 1 end,
    'members',    v_n,
    'manager',    private.f05_manager_name(v_trip),
    'me',         case when me.id is null then null else pg_catalog.jsonb_build_object(
                    'member_id', me.id, 'status', me.status, 'role', me.role, 'display_name', me.display_name) end);
end;
$$;

create or replace function public.join_request(p_user uuid, p_code text, p_name text, p_ip text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_trip uuid;
  v_name text := private.f05_clean_name(p_name);
  v_role text;
  me     record;
  v_id   uuid;
begin
  if p_user is null then
    return private.f05_err('invalid_request');
  end if;
  if p_ip is not null and private.f05_count('request', null, p_ip, null, null, interval '1 hour') >= 10 then
    return private.f05_err('rate_limited');
  end if;

  v_trip := private.f05_trip_for_code(p_code);
  if v_trip is null then
    perform private.f05_log('request', p_user, null, p_ip, false);
    return private.f05_err('code_invalid');
  end if;

  -- serialize requests for one trip (name check + pending cap)
  perform 1 from public.trips t where t.id = v_trip for no key update;

  -- already has a row in this trip (D7): idempotent answers, no new row, no attempt counted
  select m.id, m.status, m.role, m.display_name into me
    from public.trip_members m where m.trip_id = v_trip and m.user_id = p_user;
  -- CHANGE 2026-10-22 F06-DB-03 (D2): a `removed` row falls through to the new-request checks below and is re-used.
  --   0012: returned {"error":"member_removed"}.
  if me.id is not null and me.status <> 'removed' then
    return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', me.id, 'status', me.status,
                                         'role', me.role, 'display_name', me.display_name, 'created', false);
  end if;

  if private.f05_count('request', p_user, null, v_trip, true, interval '24 hours') >= 3 then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('rate_limited');
  end if;
  if pg_catalog.char_length(v_name) < 1 or pg_catalog.char_length(v_name) > 40 then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('name_invalid');
  end if;
  if exists (select 1 from public.trip_members m
              where m.trip_id = v_trip and m.status in ('pending', 'active')
                and private.f05_name_key(m.display_name) = private.f05_name_key(v_name)) then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('name_taken');
  end if;
  if (select pg_catalog.count(*) from public.trip_members m where m.trip_id = v_trip and m.status = 'pending') >= 20 then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('rate_limited');
  end if;

  select t.default_role into v_role from public.trips t where t.id = v_trip;
  if me.id is not null then
    -- CHANGE 2026-10-22 F06-DB-03 (D2): the removed row becomes a new pending request (same id; records keep their `by`)
    update public.trip_members
       set status = 'pending', display_name = v_name, role = coalesce(v_role, 'editor'),
           joined_at = pg_catalog.now(), approved_at = null
     where id = me.id
     returning id into v_id;
  else
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at)
      values (v_trip, p_user, v_name, coalesce(v_role, 'editor'), 'pending', pg_catalog.now())
      returning id into v_id;
  end if;
  perform private.f05_log('request', p_user, v_trip, p_ip, true);
  return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', v_id, 'status', 'pending',
                                       'role', coalesce(v_role, 'editor'), 'display_name', v_name, 'created', true);
end;
$$;

-- ===========================================================================
-- 9. Trip name in one place (spec §2.7, D4): a MANAGER's write of trip_kv 'tripname' also sets trips.name.
--    Editors' writes keep the kv-only behaviour. Never raises: a failure must not block the kv write.
-- ===========================================================================
create or replace function private.f06_tripname_sync()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_name text;
begin
  begin
    if auth.uid() is null or not private.f06_is_manager(auth.uid(), new.trip_id) then
      return null;
    end if;
    v_name := private.f05_clean_name(new.value);
    if pg_catalog.char_length(v_name) between 1 and 80 then
      update public.trips set name = v_name where id = new.trip_id and name is distinct from v_name;
    end if;
  exception when others then
    null;   -- never block the kv write
  end;
  return null;
end;
$$;

drop trigger if exists trip_kv_tripname_sync on public.trip_kv;
create trigger trip_kv_tripname_sync
  after insert or update of value on public.trip_kv
  for each row
  when (new.key = 'tripname')
  execute function private.f06_tripname_sync();

-- ===========================================================================
-- 10. Grants: every function above is service-role only (the trigger function is never called directly)
-- ===========================================================================
revoke all on function private.f06_is_manager(uuid, uuid)                 from public, anon, authenticated;
revoke all on function private.f06_other_managers(uuid, uuid)             from public, anon, authenticated;
revoke all on function private.f06_new_join_code()                        from public, anon, authenticated;
revoke all on function private.f06_tripname_sync()                        from public, anon, authenticated;
revoke all on function public.member_set_role(uuid, uuid, text)           from public, anon, authenticated;
revoke all on function public.member_rename(uuid, uuid, text)             from public, anon, authenticated;
revoke all on function public.member_remove(uuid, uuid)                   from public, anon, authenticated;
revoke all on function public.member_leave(uuid, uuid)                    from public, anon, authenticated;
revoke all on function public.rotate_join_code(uuid, uuid)                from public, anon, authenticated;
revoke all on function public.member_touch(uuid, uuid)                    from public, anon, authenticated;
revoke all on function public.join_preview(uuid, text, text)              from public, anon, authenticated;
revoke all on function public.join_request(uuid, text, text, text)        from public, anon, authenticated;

grant execute on function private.f06_is_manager(uuid, uuid)              to service_role;
grant execute on function private.f06_other_managers(uuid, uuid)          to service_role;
grant execute on function private.f06_new_join_code()                     to service_role;
grant execute on function public.member_set_role(uuid, uuid, text)        to service_role;
grant execute on function public.member_rename(uuid, uuid, text)          to service_role;
grant execute on function public.member_remove(uuid, uuid)                to service_role;
grant execute on function public.member_leave(uuid, uuid)                 to service_role;
grant execute on function public.rotate_join_code(uuid, uuid)             to service_role;
grant execute on function public.member_touch(uuid, uuid)                 to service_role;
grant execute on function public.join_preview(uuid, text, text)           to service_role;
grant execute on function public.join_request(uuid, text, text, text)     to service_role;
