-- Plan_Travel migration 0018_f07 · version 3.0.0-alpha.16 · F07 (a member who changed phones gets back into the trip)
-- CHANGE 2026-11-16 F07-DB-01: first version (no previous version). What changed from 0001–0017, 0020–0022:
--   trip_members + person_id (one person = rows sharing person_id; backfilled = id; set by a BEFORE INSERT trigger) and
--     relink_expires_at; index (trip_id, person_id). No policy / grant change: every device row is a normal member row.
--   1 new table private.member_sessions (RLS on, no policies, service role only) — one row per auth session of a member row.
--   REPLACED (create or replace / drop of the old signature, behaviour otherwise as in 0012 / 0014):
--     private.f06_other_managers  counts distinct PERSONS                       (spec C2)
--     public.join_preview         + people[], relink{}, members = persons, lazy expiry (C5, D5)
--     public.join_request         + p_person (relink request, C5/C7); old 4-argument form dropped, new has a default
--     public.approve_member       a relink row takes the person's CURRENT role + name, role parameter ignored (C6)
--     public.claim_transfer       as 0012 + the moved row's old sessions are deleted (C11)
--     public.member_set_role / member_rename / member_remove / member_leave   apply to the whole person (C1, C2, D3)
--     public.member_touch         + p_session / p_label / p_via: records the session (C3), answers device_revoked (C4);
--                                 old 2-argument form dropped, the new one has defaults for the 3 new arguments
--   NEW service-role-only functions for manage-members (alpha.16.0):
--     public.device_list(p_user, p_trip)                          persons + devices (+ login notices for managers)  (D4, C8)
--     public.device_disconnect(p_user, p_trip, p_member, p_session)                                                  (C4, C9)
--     public.device_notice_ack(p_user, p_trip, p_session)                                                            (C8)
--   Deviations from docs/F07_spec.md (both decided in conversation 1, see docs/F07_dev_notes_server.md):
--     (1) member_sessions.via is any lower-case provider name (email, google, …), not only ('anon','email'): spec C3 says
--         "or the provider name" and F22a uses Google. (2) device_disconnect deletes the auth.sessions row itself (inside the
--         database function, as the service role's owner) instead of the Edge Function — one transaction; if the delete is
--         refused the session is still marked revoked, and member_touch then answers device_revoked (the device signs out).
--
-- Contract: docs/F07_spec.md §1–§2 (C1–C12, D1–D7). Idempotent: `if not exists` / `create or replace` / `drop … if exists` +
-- re-applied grants; safe to run more than once. Requires 0001, 0012, 0014 and pgcrypto in schema `extensions`.
-- Error contract (as F05/F06, RETURNED not raised): new codes person_invalid · last_device · device_revoked, plus the F05/F06
-- ones (already_member, not_member, not_manager, not_active, not_pending, last_manager, …).

-- ===========================================================================
-- 1. Columns, trigger, table
-- ===========================================================================
alter table public.trip_members add column if not exists person_id uuid;
alter table public.trip_members add column if not exists relink_expires_at timestamptz;
update public.trip_members set person_id = id where person_id is null;
alter table public.trip_members alter column person_id set not null;
create index if not exists trip_members_trip_person_idx on public.trip_members (trip_id, person_id);

create or replace function private.f07_set_person()
returns trigger
language plpgsql
volatile
set search_path = ''
as $$
begin
  if new.person_id is null then
    new.person_id := new.id;
  end if;
  return new;
end;
$$;
drop trigger if exists trip_members_set_person on public.trip_members;
create trigger trip_members_set_person
  before insert on public.trip_members
  for each row execute function private.f07_set_person();

create table if not exists private.member_sessions (
  id           uuid primary key default gen_random_uuid(),
  member_id    uuid not null references public.trip_members (id) on delete cascade,
  session_id   uuid not null,
  label        text,
  via          text not null default 'anon',
  created_at   timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at   timestamptz,
  acked_at     timestamptz,
  acked_by     uuid references auth.users (id) on delete set null,
  constraint member_sessions_member_session_key unique (member_id, session_id),
  constraint member_sessions_label check (label is null or char_length(label) <= 60),
  constraint member_sessions_via check (via ~ '^[a-z][a-z0-9_]{1,29}$')
);
create index if not exists member_sessions_session_idx on private.member_sessions (session_id);
alter table private.member_sessions enable row level security;
revoke all on private.member_sessions from public, anon, authenticated;
grant select, insert, update, delete on private.member_sessions to service_role;

-- ===========================================================================
-- 2. Internal helpers
-- ===========================================================================

-- the person_id of p_user's ACTIVE row in p_trip (null when none)
create or replace function private.f07_person_of(p_user uuid, p_trip uuid)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select m.person_id from public.trip_members m
   where m.trip_id = p_trip and m.user_id = p_user and m.status = 'active'
$$;

-- C5: an expired relink request is treated as absent — deleted by whichever function sees it next
create or replace function private.f07_expire(p_trip uuid)
returns void
language sql
volatile
security definer
set search_path = ''
as $$
  delete from public.trip_members m
   where m.trip_id = p_trip and m.status = 'pending'
     and m.relink_expires_at is not null and m.relink_expires_at <= pg_catalog.now()
$$;

-- C2: active managers other than the PERSON behind member p_except
create or replace function private.f06_other_managers(p_trip uuid, p_except uuid)
returns int
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.count(distinct m.person_id)::int from public.trip_members m
   where m.trip_id = p_trip and m.role = 'manager' and m.status = 'active' and m.id <> p_except
     and m.person_id is distinct from (select x.person_id from public.trip_members x where x.id = p_except)
$$;

-- the devices of one person: a row with live account sessions (any provider but 'anon') = one device per such session;
-- every other active row = one device (its latest live session, or none recorded yet). A row whose sessions are all
-- revoked is not a device any more.
create or replace function private.f07_devices(p_trip uuid, p_person uuid)
returns table (member_id uuid, session_id uuid, label text, via text, created_at timestamptz, last_seen_at timestamptz)
language sql
stable
security definer
set search_path = ''
as $$
  select m.id, s.session_id, s.label, s.via, s.created_at, s.last_seen_at
    from public.trip_members m
    join private.member_sessions s on s.member_id = m.id
   where m.trip_id = p_trip and m.person_id = p_person and m.status = 'active'
     and s.revoked_at is null and s.via <> 'anon'
  union all
  select m.id, ls.session_id, ls.label, coalesce(ls.via, 'anon'),
         coalesce(ls.created_at, m.joined_at), coalesce(ls.last_seen_at, m.last_seen_at)
    from public.trip_members m
    left join lateral (select s.* from private.member_sessions s
                        where s.member_id = m.id and s.revoked_at is null
                        order by s.last_seen_at desc limit 1) ls on true
   where m.trip_id = p_trip and m.person_id = p_person and m.status = 'active'
     and not exists (select 1 from private.member_sessions s2
                      where s2.member_id = m.id and s2.revoked_at is null and s2.via <> 'anon')
     and (ls.session_id is not null
          or not exists (select 1 from private.member_sessions s3 where s3.member_id = m.id))
$$;

-- ===========================================================================
-- 3. join_preview — F06 version + people[] / relink{} / persons count (spec §2.1)
-- ===========================================================================
create or replace function public.join_preview(p_user uuid, p_code text, p_ip text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_trip   uuid;
  t        record;
  me       record;
  rl       record;
  v_n      int;
  v_relink jsonb := null;
  v_people jsonb;
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

  -- relink state of the caller BEFORE the lazy delete, so an expired request is reported once (D5)
  select m.display_name, m.role, m.relink_expires_at into rl
    from public.trip_members m
   where m.trip_id = v_trip and m.user_id = p_user and m.status = 'pending' and m.relink_expires_at is not null;
  if rl.display_name is not null then
    v_relink := case when rl.relink_expires_at <= pg_catalog.now()
                     then pg_catalog.jsonb_build_object('status', 'expired', 'display_name', rl.display_name)
                     else pg_catalog.jsonb_build_object('status', 'pending', 'display_name', rl.display_name,
                                                        'role', rl.role, 'expires_at', rl.relink_expires_at) end;
  end if;
  perform private.f07_expire(v_trip);

  select tr.id, tr.name, tr.start_date, tr.end_date into t from public.trips tr where tr.id = v_trip;
  select pg_catalog.count(distinct m.person_id)::int into v_n
    from public.trip_members m where m.trip_id = v_trip and m.status = 'active';
  select m.id, m.status, m.role, m.display_name into me
    from public.trip_members m where m.trip_id = v_trip and m.user_id = p_user and m.status <> 'removed';
  -- names only, no roles (D2); only with a valid, current code (it was checked above) (C7)
  select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('person_id', p.person_id, 'display_name', p.display_name)
                                       order by pg_catalog.lower(p.display_name), p.person_id), '[]'::jsonb)
    into v_people
    from (select distinct on (m.person_id) m.person_id, m.display_name
            from public.trip_members m
           where m.trip_id = v_trip and m.status = 'active'
           order by m.person_id, m.joined_at) p;

  return pg_catalog.jsonb_build_object(
    'trip_id',    t.id,
    'name',       t.name,
    'start_date', t.start_date,
    'end_date',   t.end_date,
    'days',       case when t.start_date is not null and t.end_date is not null then (t.end_date - t.start_date) + 1 end,
    'members',    v_n,
    'manager',    private.f05_manager_name(v_trip),
    'me',         case when me.id is null then null else pg_catalog.jsonb_build_object(
                    'member_id', me.id, 'status', me.status, 'role', me.role, 'display_name', me.display_name) end,
    'people',     v_people,
    'relink',     v_relink);
end;
$$;

-- ===========================================================================
-- 4. join_request — F06 version + p_person: "I was already on the trip" (C5, C7)
-- ===========================================================================
drop function if exists public.join_request(uuid, text, text, text);
create or replace function public.join_request(p_user uuid, p_code text, p_name text, p_ip text, p_person uuid default null)
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
  pr     record;
  v_id   uuid;
  v_exp  timestamptz := pg_catalog.now() + interval '24 hours';
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

  perform 1 from public.trips t where t.id = v_trip for no key update;
  perform private.f07_expire(v_trip);

  select m.id, m.status, m.role, m.display_name, m.person_id, m.relink_expires_at into me
    from public.trip_members m where m.trip_id = v_trip and m.user_id = p_user;
  if me.id is not null and me.status <> 'removed' then
    if p_person is not null and me.status = 'active' then
      return private.f05_err('already_member');
    end if;
    return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', me.id, 'status', me.status,
                                         'role', me.role, 'display_name', me.display_name, 'created', false,
                                         'relink', me.relink_expires_at is not null,
                                         'expires_at', me.relink_expires_at);
  end if;

  if private.f05_count('request', p_user, null, v_trip, true, interval '24 hours') >= 3 then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('rate_limited');
  end if;

  if p_person is null then
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
  else
    -- C5/C7: only an ACTIVE person of THIS trip can be chosen; a guessed / foreign / removed id looks the same
    select m.person_id, m.display_name, m.role into pr
      from public.trip_members m
     where m.trip_id = v_trip and m.person_id = p_person and m.status = 'active'
     order by m.joined_at limit 1;
    if pr.person_id is null then
      perform private.f05_log('request', p_user, v_trip, p_ip, false);
      return private.f05_err('person_invalid');
    end if;
  end if;
  if (select pg_catalog.count(*) from public.trip_members m where m.trip_id = v_trip and m.status = 'pending') >= 20 then
    perform private.f05_log('request', p_user, v_trip, p_ip, false);
    return private.f05_err('rate_limited');
  end if;

  if p_person is not null then
    -- one open relink per person: a newer request replaces an older one of another device
    delete from public.trip_members m
     where m.trip_id = v_trip and m.person_id = p_person and m.status = 'pending'
       and m.relink_expires_at is not null and m.user_id <> p_user;
    if me.id is not null then
      update public.trip_members
         set status = 'pending', person_id = pr.person_id, display_name = pr.display_name, role = pr.role,
             relink_expires_at = v_exp, joined_at = pg_catalog.now(), approved_at = null
       where id = me.id
       returning id into v_id;
    else
      insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at, person_id, relink_expires_at)
        values (v_trip, p_user, pr.display_name, pr.role, 'pending', pg_catalog.now(), pr.person_id, v_exp)
        returning id into v_id;
    end if;
    perform private.f05_log('request', p_user, v_trip, p_ip, true);
    return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', v_id, 'status', 'pending', 'role', pr.role,
                                         'display_name', pr.display_name, 'created', true,
                                         'relink', true, 'person_id', pr.person_id, 'expires_at', v_exp);
  end if;

  select t.default_role into v_role from public.trips t where t.id = v_trip;
  if me.id is not null then
    -- F06 D2: the removed row becomes a new pending request (a NEW person: person_id = its own id)
    update public.trip_members
       set status = 'pending', display_name = v_name, role = coalesce(v_role, 'editor'), person_id = id,
           relink_expires_at = null, joined_at = pg_catalog.now(), approved_at = null
     where id = me.id
     returning id into v_id;
  else
    insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at)
      values (v_trip, p_user, v_name, coalesce(v_role, 'editor'), 'pending', pg_catalog.now())
      returning id into v_id;
  end if;
  perform private.f05_log('request', p_user, v_trip, p_ip, true);
  return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', v_id, 'status', 'pending',
                                       'role', coalesce(v_role, 'editor'), 'display_name', v_name, 'created', true,
                                       'relink', false);
end;
$$;

-- ===========================================================================
-- 5. approve_member — a relink row takes the person's CURRENT role and name (C6)
-- ===========================================================================
create or replace function public.approve_member(p_user uuid, p_member uuid, p_decision text, p_role text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m      record;
  v_role text;
  pr     record;
begin
  if p_user is null or p_member is null or coalesce(p_decision, '') not in ('approve', 'reject') then
    return private.f05_err('invalid_request');
  end if;
  select mm.id, mm.trip_id, mm.status, mm.display_name, mm.person_id, mm.relink_expires_at into m
    from public.trip_members mm where mm.id = p_member for update;
  if m.id is null then
    return private.f05_err('not_pending');
  end if;
  if not exists (select 1 from public.trip_members x
                  where x.trip_id = m.trip_id and x.user_id = p_user and x.role = 'manager' and x.status = 'active') then
    return private.f05_err('not_manager');
  end if;
  if m.status <> 'pending' then
    return private.f05_err('not_pending');
  end if;
  if m.relink_expires_at is not null and m.relink_expires_at <= pg_catalog.now() then
    delete from public.trip_members where id = m.id;       -- C5: expired = absent
    return private.f05_err('not_pending');
  end if;

  if p_decision = 'reject' then
    delete from public.trip_members where id = m.id;
    return pg_catalog.jsonb_build_object('status', 'rejected', 'member_id', m.id, 'display_name', m.display_name);
  end if;

  if m.relink_expires_at is not null then
    -- C6: role parameter ignored; the person may have been renamed / re-roled / removed since the request
    select x.display_name, x.role into pr from public.trip_members x
     where x.trip_id = m.trip_id and x.person_id = m.person_id and x.status = 'active' and x.id <> m.id
     order by x.joined_at limit 1;
    if pr.role is null then
      delete from public.trip_members where id = m.id;
      return private.f05_err('person_invalid');
    end if;
    update public.trip_members
       set status = 'active', role = pr.role, display_name = pr.display_name, approved_at = pg_catalog.now(),
           relink_expires_at = null
     where id = m.id;
    return pg_catalog.jsonb_build_object('status', 'active', 'member_id', m.id, 'role', pr.role,
                                         'display_name', pr.display_name, 'trip_id', m.trip_id, 'relink', true);
  end if;

  if p_role is null or p_role = '' then
    select t.default_role into v_role from public.trips t where t.id = m.trip_id;
  else
    v_role := p_role;
  end if;
  if v_role not in ('viewer', 'editor', 'manager') then
    return private.f05_err('role_invalid');
  end if;
  update public.trip_members
     set status = 'active', role = v_role, approved_at = pg_catalog.now()
   where id = m.id;
  return pg_catalog.jsonb_build_object('status', 'active', 'member_id', m.id, 'role', v_role,
                                       'display_name', m.display_name, 'trip_id', m.trip_id, 'relink', false);
end;
$$;

-- ===========================================================================
-- 6. claim_transfer — 0012 body; the moved row also forgets the old identity's sessions (C11)
-- ===========================================================================
create or replace function public.claim_transfer(p_user uuid, p_code text, p_ip text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_code text := pg_catalog.regexp_replace(coalesce(p_code, ''), '\s', '', 'g');
  c      record;
  m      record;
begin
  if p_user is null then
    return private.f05_err('invalid_request');
  end if;
  if private.f05_count('claim', p_user, null, null, false, interval '1 hour') >= 5
     or (p_ip is not null and private.f05_count('claim', null, p_ip, null, false, interval '1 hour') >= 20) then
    return private.f05_err('rate_limited');
  end if;
  if v_code !~ '^[0-9]{6}$' then
    perform private.f05_log('claim', p_user, null, p_ip, false);
    return private.f05_err('transfer_invalid');
  end if;

  select tc.id, tc.member_id into c
    from private.transfer_codes tc
   where tc.code_hash = pg_catalog.encode(extensions.digest(v_code, 'sha256'), 'hex')
     and tc.used_at is null
     and tc.expires_at > pg_catalog.now()
     for update;
  if c.id is null then
    perform private.f05_log('claim', p_user, null, p_ip, false);
    return private.f05_err('transfer_invalid');
  end if;

  select mm.id, mm.trip_id, mm.user_id, mm.status, mm.role, mm.display_name into m
    from public.trip_members mm where mm.id = c.member_id for update;
  if m.id is null or m.status <> 'active' then
    perform private.f05_log('claim', p_user, m.trip_id, p_ip, false);
    return private.f05_err('transfer_invalid');
  end if;

  if m.user_id <> p_user then
    if exists (select 1 from public.trip_members x where x.trip_id = m.trip_id and x.user_id = p_user) then
      perform private.f05_log('claim', p_user, m.trip_id, p_ip, false);
      return private.f05_err('already_member');
    end if;
    update public.trip_members set user_id = p_user where id = m.id;
    delete from private.member_sessions s where s.member_id = m.id;     -- F07 C11 (person_id is kept by the update)
  end if;
  update private.transfer_codes set used_at = pg_catalog.now() where id = c.id;
  perform private.f05_log('claim', p_user, m.trip_id, p_ip, true);
  return pg_catalog.jsonb_build_object('trip_id', m.trip_id, 'member_id', m.id, 'role', m.role,
                                       'display_name', m.display_name);
end;
$$;

-- ===========================================================================
-- 7. member_set_role / member_rename / member_remove / member_leave — apply to the whole person (C1, C2, D3)
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
  if p_user is null or p_member is null or p_role is null then
    return private.f05_err('invalid_request');
  end if;
  if p_role not in ('manager', 'editor', 'viewer') then
    return private.f05_err('role_invalid');
  end if;
  select mm.id, mm.trip_id into m from public.trip_members mm where mm.id = p_member;
  if m.id is null then
    return private.f05_err('not_active');
  end if;
  perform 1 from public.trips t where t.id = m.trip_id for no key update;
  select mm.id, mm.trip_id, mm.user_id, mm.person_id, mm.status, mm.role, mm.display_name into m
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
    update public.trip_members set role = p_role
     where trip_id = m.trip_id and person_id = m.person_id and status = 'active';
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
  if p_user is null or p_member is null or p_name is null then
    return private.f05_err('invalid_request');
  end if;
  select mm.id, mm.trip_id into m from public.trip_members mm where mm.id = p_member;
  if m.id is null then
    return private.f05_err('not_active');
  end if;
  perform 1 from public.trips t where t.id = m.trip_id for no key update;
  select mm.id, mm.trip_id, mm.person_id, mm.status, mm.display_name into m
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
  -- C2: the name must be free among other PERSONS (the person's own device rows share the name)
  if exists (select 1 from public.trip_members x
              where x.trip_id = m.trip_id and x.person_id <> m.person_id and x.status in ('pending', 'active')
                and private.f05_name_key(x.display_name) = private.f05_name_key(v_name)) then
    return private.f05_err('name_taken');
  end if;
  if m.display_name is distinct from v_name then
    update public.trip_members set display_name = v_name
     where trip_id = m.trip_id and person_id = m.person_id and status = 'active';
  end if;
  return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'display_name', v_name,
                                       'changed', m.display_name is distinct from v_name);
end;
$$;

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
  select mm.id, mm.trip_id, mm.user_id, mm.person_id, mm.status, mm.role, mm.display_name into m
    from public.trip_members mm where mm.id = p_member for update;
  if not private.f06_is_manager(p_user, m.trip_id) then
    return private.f05_err('not_manager');
  end if;
  if m.person_id is not distinct from private.f07_person_of(p_user, m.trip_id) then
    return private.f05_err('invalid_request');      -- yourself (any of your own devices): use member_leave
  end if;
  if m.status <> 'active' then
    return private.f05_err('not_active');
  end if;
  if m.role = 'manager' and private.f06_other_managers(m.trip_id, m.id) = 0 then
    return private.f05_err('last_manager');
  end if;
  begin
    update public.trip_members set status = 'removed'
     where trip_id = m.trip_id and person_id = m.person_id and status = 'active';
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  delete from public.trip_members where trip_id = m.trip_id and person_id = m.person_id and status = 'pending';  -- open relink
  delete from private.transfer_codes c
   where c.used_at is null and c.member_id in (select x.id from public.trip_members x where x.person_id = m.person_id);
  delete from public.relink_tokens r
   where r.used_at is null and r.member_id in (select x.id from public.trip_members x where x.person_id = m.person_id);
  return pg_catalog.jsonb_build_object('member_id', m.id, 'trip_id', m.trip_id, 'status', 'removed',
                                       'display_name', m.display_name);
end;
$$;

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
  select mm.id, mm.trip_id, mm.person_id, mm.role into m
    from public.trip_members mm where mm.trip_id = p_trip and mm.user_id = p_user and mm.status = 'active' for update;
  if m.id is null then
    return private.f05_err('not_member');
  end if;
  if m.role = 'manager' and private.f06_other_managers(p_trip, m.id) = 0 then
    return private.f05_err('last_manager');
  end if;
  begin
    update public.trip_members set status = 'removed'
     where trip_id = p_trip and person_id = m.person_id and status = 'active';
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  delete from public.trip_members where trip_id = p_trip and person_id = m.person_id and status = 'pending';
  delete from private.transfer_codes c
   where c.used_at is null and c.member_id in (select x.id from public.trip_members x where x.person_id = m.person_id);
  delete from public.relink_tokens r
   where r.used_at is null and r.member_id in (select x.id from public.trip_members x where x.person_id = m.person_id);
  return pg_catalog.jsonb_build_object('ok', true, 'trip_id', p_trip, 'member_id', m.id);
end;
$$;

-- ===========================================================================
-- 8. member_touch — last_seen_at (10 min) + the auth session of this device (C3); answers device_revoked (C4)
-- ===========================================================================
drop function if exists public.member_touch(uuid, uuid);
create or replace function public.member_touch(p_user uuid, p_trip uuid, p_session uuid default null,
                                               p_label text default null, p_via text default 'anon')
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_id    uuid;
  n       int;
  v_via   text := coalesce(nullif(pg_catalog.btrim(p_via), ''), 'anon');
  v_label text := nullif(pg_catalog.left(pg_catalog.btrim(coalesce(p_label, '')), 60), '');
  v_rev   timestamptz;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  if v_via !~ '^[a-z][a-z0-9_]{1,29}$' then
    v_via := 'anon';
  end if;
  select m.id into v_id from public.trip_members m
   where m.trip_id = p_trip and m.user_id = p_user and m.status = 'active';
  if v_id is null then
    return private.f05_err('not_member');
  end if;
  perform private.f07_expire(p_trip);

  if p_session is not null then
    select s.revoked_at into v_rev from private.member_sessions s where s.member_id = v_id and s.session_id = p_session;
    if v_rev is not null then
      return private.f05_err('device_revoked');
    end if;
    insert into private.member_sessions as s (member_id, session_id, label, via)
      values (v_id, p_session, v_label, v_via)
    on conflict (member_id, session_id) do update
      set last_seen_at = pg_catalog.now(), via = excluded.via, label = coalesce(excluded.label, s.label)
      where s.last_seen_at < pg_catalog.now() - interval '10 minutes' or s.via is distinct from excluded.via;
  end if;

  update public.trip_members set last_seen_at = pg_catalog.now()
   where id = v_id and (last_seen_at is null or last_seen_at < pg_catalog.now() - interval '10 minutes');
  get diagnostics n = row_count;
  return pg_catalog.jsonb_build_object('ok', true, 'touched', n > 0);
end;
$$;

-- ===========================================================================
-- 9. device_list — persons with their devices (a manager: everyone + login notices; a member: only their own person)
-- ===========================================================================
create or replace function public.device_list(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_person  uuid;
  v_mgr     boolean;
  v_persons jsonb;
  v_notices jsonb := '[]'::jsonb;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  v_person := private.f07_person_of(p_user, p_trip);
  if v_person is null then
    return private.f05_err('not_member');
  end if;
  v_mgr := private.f06_is_manager(p_user, p_trip);

  select coalesce(pg_catalog.jsonb_agg(x.j order by x.k, x.pid), '[]'::jsonb) into v_persons
    from (select pg_catalog.lower(p.display_name) as k, p.person_id as pid,
                 pg_catalog.jsonb_build_object(
                   'person_id', p.person_id, 'display_name', p.display_name, 'role', p.role,
                   'devices', coalesce((select pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
                                 'member_id', d.member_id, 'session_id', d.session_id, 'label', d.label, 'via', d.via,
                                 'created_at', d.created_at, 'last_seen_at', d.last_seen_at)
                                 order by d.created_at, d.member_id)
                               from private.f07_devices(p_trip, p.person_id) d), '[]'::jsonb)) as j
            from (select distinct on (m.person_id) m.person_id, m.display_name, m.role
                    from public.trip_members m
                   where m.trip_id = p_trip and m.status = 'active' and (v_mgr or m.person_id = v_person)
                   order by m.person_id, m.joined_at) p) x;

  if v_mgr then
    -- C8: a new ACCOUNT session of a person who had an earlier session, unacknowledged, ≤ 7 days old; not the caller's own person
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
             'session_id', s.session_id, 'member_id', m.id, 'person_id', m.person_id, 'display_name', m.display_name,
             'via', s.via, 'label', s.label, 'created_at', s.created_at) order by s.created_at desc), '[]'::jsonb)
      into v_notices
      from private.member_sessions s
      join public.trip_members m on m.id = s.member_id
     where m.trip_id = p_trip and m.status = 'active' and m.person_id <> v_person
       and s.via <> 'anon' and s.acked_at is null and s.revoked_at is null
       and s.created_at > pg_catalog.now() - interval '7 days'
       and exists (select 1 from private.member_sessions e
                     join public.trip_members em on em.id = e.member_id
                    where em.trip_id = p_trip and em.person_id = m.person_id and e.created_at < s.created_at);
  end if;

  return pg_catalog.jsonb_build_object('persons', v_persons, 'notices', v_notices, 'is_manager', v_mgr,
                                       'my_person_id', v_person);
end;
$$;

-- ===========================================================================
-- 10. device_disconnect — D4 / C4 / C9. The member acts on their own person, a manager on anyone.
--     An account session: revoked + its auth.sessions row deleted. An anonymous device: that row becomes `removed`.
--     A person's last device is refused (last_device).
-- ===========================================================================
create or replace function public.device_disconnect(p_user uuid, p_trip uuid, p_member uuid, p_session uuid default null)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  m          record;
  v_caller   uuid;
  v_live     int;
  v_account  boolean;
  s          record;
  v_deleted  int := 0;
  v_ids      uuid[];
begin
  if p_user is null or p_trip is null or p_member is null then
    return private.f05_err('invalid_request');
  end if;
  v_caller := private.f07_person_of(p_user, p_trip);
  if v_caller is null then
    return private.f05_err('not_member');
  end if;
  perform 1 from public.trips t where t.id = p_trip for no key update;
  select mm.id, mm.trip_id, mm.user_id, mm.person_id, mm.status into m
    from public.trip_members mm where mm.id = p_member and mm.trip_id = p_trip for update;
  if m.id is null or m.status <> 'active' then
    return private.f05_err('not_active');
  end if;
  if m.person_id <> v_caller and not private.f06_is_manager(p_user, p_trip) then
    return private.f05_err('not_manager');
  end if;
  if (select pg_catalog.count(*) from private.f07_devices(p_trip, m.person_id)) <= 1 then
    return private.f05_err('last_device');                                        -- C9
  end if;

  v_account := exists (select 1 from private.member_sessions x
                        where x.member_id = m.id and x.revoked_at is null and x.via <> 'anon');
  select x.session_id, x.via into s from private.member_sessions x
   where x.member_id = m.id and x.session_id = p_session and x.revoked_at is null;

  if s.session_id is not null and (s.via <> 'anon' or v_account) then
    -- account session: dead refresh token + revoked marker; the member row (and the other devices) stay
    update private.member_sessions set revoked_at = pg_catalog.now() where member_id = m.id and session_id = s.session_id;
    v_ids := array[s.session_id];
    begin
      if pg_catalog.to_regclass('auth.sessions') is not null then
        delete from auth.sessions a where a.id = s.session_id and a.user_id = m.user_id;
        get diagnostics v_deleted = row_count;
      end if;
    exception when others then
      v_deleted := 0;       -- refused: member_touch answers device_revoked instead (≤ 60 s while the app is open)
    end;
    return pg_catalog.jsonb_build_object('ok', true, 'kind', 'session', 'member_id', m.id, 'session_id', s.session_id,
                                         'auth_session_deleted', v_deleted > 0);
  end if;

  -- anonymous device: one identity = one row
  begin
    update public.trip_members set status = 'removed' where id = m.id;
  exception when check_violation then
    if sqlerrm like 'last_manager%' then
      return private.f05_err('last_manager');
    end if;
    raise;
  end;
  select coalesce(pg_catalog.array_agg(x.session_id), '{}') into v_ids
    from private.member_sessions x where x.member_id = m.id and x.revoked_at is null;
  update private.member_sessions set revoked_at = pg_catalog.now() where member_id = m.id and revoked_at is null;
  begin
    if pg_catalog.to_regclass('auth.sessions') is not null and pg_catalog.cardinality(v_ids) > 0 then
      delete from auth.sessions a where a.id = any (v_ids) and a.user_id = m.user_id;
    end if;
  exception when others then
    null;                   -- the row is `removed`: RLS already cuts the device off
  end;
  delete from private.transfer_codes c where c.member_id = m.id and c.used_at is null;
  return pg_catalog.jsonb_build_object('ok', true, 'kind', 'row', 'member_id', m.id, 'session_id', null,
                                       'auth_session_deleted', false);
end;
$$;

-- ===========================================================================
-- 11. device_notice_ack — "הבנתי": any manager acknowledges a login notice for everybody (C8)
-- ===========================================================================
create or replace function public.device_notice_ack(p_user uuid, p_trip uuid, p_session uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  n int;
begin
  if p_user is null or p_trip is null or p_session is null then
    return private.f05_err('invalid_request');
  end if;
  if not private.f06_is_manager(p_user, p_trip) then
    return private.f05_err('not_manager');
  end if;
  update private.member_sessions s set acked_at = pg_catalog.now(), acked_by = p_user
   where s.session_id = p_session and s.acked_at is null
     and s.member_id in (select m.id from public.trip_members m where m.trip_id = p_trip);
  get diagnostics n = row_count;
  return pg_catalog.jsonb_build_object('ok', true, 'acked', n > 0);
end;
$$;

-- ===========================================================================
-- 12. Grants: everything above is service-role only
-- ===========================================================================
revoke all on function private.f07_set_person()                              from public, anon, authenticated;
revoke all on function private.f07_person_of(uuid, uuid)                     from public, anon, authenticated;
revoke all on function private.f07_expire(uuid)                              from public, anon, authenticated;
revoke all on function private.f07_devices(uuid, uuid)                       from public, anon, authenticated;
revoke all on function private.f06_other_managers(uuid, uuid)                from public, anon, authenticated;
revoke all on function public.join_preview(uuid, text, text)                 from public, anon, authenticated;
revoke all on function public.join_request(uuid, text, text, text, uuid)     from public, anon, authenticated;
revoke all on function public.approve_member(uuid, uuid, text, text)         from public, anon, authenticated;
revoke all on function public.claim_transfer(uuid, text, text)               from public, anon, authenticated;
revoke all on function public.member_set_role(uuid, uuid, text)              from public, anon, authenticated;
revoke all on function public.member_rename(uuid, uuid, text)                from public, anon, authenticated;
revoke all on function public.member_remove(uuid, uuid)                      from public, anon, authenticated;
revoke all on function public.member_leave(uuid, uuid)                       from public, anon, authenticated;
revoke all on function public.member_touch(uuid, uuid, uuid, text, text)     from public, anon, authenticated;
revoke all on function public.device_list(uuid, uuid)                        from public, anon, authenticated;
revoke all on function public.device_disconnect(uuid, uuid, uuid, uuid)      from public, anon, authenticated;
revoke all on function public.device_notice_ack(uuid, uuid, uuid)            from public, anon, authenticated;

grant execute on function private.f07_person_of(uuid, uuid)                  to service_role;
grant execute on function private.f07_expire(uuid)                           to service_role;
grant execute on function private.f07_devices(uuid, uuid)                    to service_role;
grant execute on function private.f06_other_managers(uuid, uuid)             to service_role;
grant execute on function public.join_preview(uuid, text, text)              to service_role;
grant execute on function public.join_request(uuid, text, text, text, uuid)  to service_role;
grant execute on function public.approve_member(uuid, uuid, text, text)      to service_role;
grant execute on function public.claim_transfer(uuid, text, text)            to service_role;
grant execute on function public.member_set_role(uuid, uuid, text)           to service_role;
grant execute on function public.member_rename(uuid, uuid, text)             to service_role;
grant execute on function public.member_remove(uuid, uuid)                   to service_role;
grant execute on function public.member_leave(uuid, uuid)                    to service_role;
grant execute on function public.member_touch(uuid, uuid, uuid, text, text) to service_role;
grant execute on function public.device_list(uuid, uuid)                     to service_role;
grant execute on function public.device_disconnect(uuid, uuid, uuid, uuid)   to service_role;
grant execute on function public.device_notice_ack(uuid, uuid, uuid)         to service_role;
