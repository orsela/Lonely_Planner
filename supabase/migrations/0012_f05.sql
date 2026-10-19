-- Plan_Travel migration 0012_f05 · version 3.0.0-alpha.6 · F05 (a member joins from the group link, after manager approval)
-- CHANGE 2026-10-19 F05-DB-01: first version (no previous version). What changed from 0001–0011:
--   2 new tables (private.transfer_codes, private.join_attempts — RLS on, NO policies, no client grants) and
--   6 new service-role-only functions used by the Edge Functions `join-trip` and `approve-member`:
--     public.join_preview(p_user uuid, p_code text, p_ip text)                         returns jsonb
--     public.join_request(p_user uuid, p_code text, p_name text, p_ip text)            returns jsonb
--     public.join_cancel(p_user uuid, p_trip uuid)                                     returns jsonb
--     public.issue_transfer(p_user uuid, p_trip uuid)                                  returns jsonb
--     public.claim_transfer(p_user uuid, p_code text, p_ip text)                       returns jsonb
--     public.approve_member(p_user uuid, p_member uuid, p_decision text, p_role text)  returns jsonb
--   No change to existing tables, columns, policies, triggers or grants; `public` still has exactly the 9 F01 tables (the
--   F02/F03/F04 harness rows "no new tables in public" stay true). The F01 triggers stay in force (last manager).
--
-- Contract: docs/F05_spec.md §2 (decisions D1–D9). Idempotent: `create … if not exists` / `create or replace` + re-applied
-- grants; safe to run more than once. Requires pgcrypto in schema `extensions` (gen_random_bytes, digest) — present on
-- Supabase, and already used by 0010.
--
-- Error contract (deliberately NOT raised): business refusals are RETURNED as {"error":"<code>"} so that the attempt rows
-- written for rate limiting are kept (a raised exception would roll them back). Codes:
--   code_invalid · name_invalid · name_taken · rate_limited · member_removed · not_pending · not_member ·
--   transfer_invalid · already_member · not_manager · role_invalid · invalid_request
-- A success never contains the key "error". p_ip is an opaque hash computed by the Edge Function (never a raw address).
--
-- Rate limits (spec §2.4), counted in private.join_attempts:
--   preview  ≤30 per user per hour, ≤60 per ip per hour
--   request  ≤3 successful requests per (user, trip) per 24 h; ≤10 attempts per ip per hour; ≤20 pending rows per trip
--   claim    ≤5 failed per user per hour, ≤20 failed per ip per hour
-- join_attempts rows older than 7 days are deleted opportunistically by join_preview / join_request (no cron).

-- ===========================================================================
-- 1. Schema `private` and tables
-- ===========================================================================
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to service_role;

create table if not exists private.transfer_codes (
  id          uuid primary key default gen_random_uuid(),
  member_id   uuid not null references public.trip_members (id) on delete cascade,
  code_hash   text not null,
  expires_at  timestamptz not null,
  used_at     timestamptz,
  created_at  timestamptz not null default now(),
  constraint transfer_codes_hash_format check (code_hash ~ '^[0-9a-f]{64}$')
);
create unique index if not exists transfer_codes_open_hash_key on private.transfer_codes (code_hash) where used_at is null;
create index if not exists transfer_codes_member_id_idx on private.transfer_codes (member_id);

create table if not exists private.join_attempts (
  id       bigint generated always as identity primary key,
  kind     text not null,
  user_id  uuid,
  trip_id  uuid,
  ip_hash  text,
  ok       boolean not null default false,
  at       timestamptz not null default now(),
  constraint join_attempts_kind check (kind in ('preview', 'request', 'claim'))
);
create index if not exists join_attempts_kind_user_at_idx on private.join_attempts (kind, user_id, at);
create index if not exists join_attempts_kind_ip_at_idx   on private.join_attempts (kind, ip_hash, at);
create index if not exists join_attempts_trip_at_idx      on private.join_attempts (trip_id, at);
create index if not exists join_attempts_at_idx           on private.join_attempts (at);

alter table private.transfer_codes enable row level security;
alter table private.join_attempts  enable row level security;
-- no policies: service role only (same as manager_invites / relink_tokens); the schema itself is closed to clients too
revoke all on private.transfer_codes from public, anon, authenticated;
revoke all on private.join_attempts  from public, anon, authenticated;
grant select, insert, update, delete on private.transfer_codes to service_role;
grant select, insert, update, delete on private.join_attempts  to service_role;

-- ===========================================================================
-- 2. Internal helpers (not callable by clients)
-- ===========================================================================

-- display name as stored: trimmed, internal whitespace collapsed to one space
create or replace function private.f05_clean_name(p text)
returns text
language sql
immutable
set search_path = ''
as $$
  select pg_catalog.regexp_replace(pg_catalog.btrim(coalesce(p, '')), '\s+', ' ', 'g')
$$;

-- comparison key for "name taken" (D5): clean + lower case
create or replace function private.f05_name_key(p text)
returns text
language sql
immutable
set search_path = ''
as $$
  select pg_catalog.lower(private.f05_clean_name(p))
$$;

-- the trip behind a join code (upper-cased, trimmed); null when unknown or the trip is archived
create or replace function private.f05_trip_for_code(p_code text)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select c.trip_id
    from public.trip_join_codes c
    join public.trips t on t.id = c.trip_id
   where c.code = pg_catalog.upper(pg_catalog.btrim(coalesce(p_code, '')))
     and t.status = 'active'
$$;

-- the trip's earliest active manager (the name shown on the join page)
create or replace function private.f05_manager_name(p_trip uuid)
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select m.display_name
    from public.trip_members m
   where m.trip_id = p_trip and m.role = 'manager' and m.status = 'active'
   order by coalesce(m.approved_at, m.joined_at) asc nulls last, m.joined_at asc
   limit 1
$$;

create or replace function private.f05_count(p_kind text, p_user uuid, p_ip text, p_trip uuid, p_ok boolean, p_since interval)
returns int
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.count(*)::int
    from private.join_attempts a
   where a.kind = p_kind
     and (p_user is null or a.user_id = p_user)
     and (p_ip   is null or a.ip_hash = p_ip)
     and (p_trip is null or a.trip_id = p_trip)
     and (p_ok   is null or a.ok = p_ok)
     and a.at > pg_catalog.now() - p_since
$$;

create or replace function private.f05_log(p_kind text, p_user uuid, p_trip uuid, p_ip text, p_ok boolean)
returns void
language sql
volatile
security definer
set search_path = ''
as $$
  insert into private.join_attempts (kind, user_id, trip_id, ip_hash, ok) values (p_kind, p_user, p_trip, p_ip, p_ok)
$$;

create or replace function private.f05_err(p_code text)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select pg_catalog.jsonb_build_object('error', p_code)
$$;

-- ===========================================================================
-- 3. join_preview — what the join page shows, plus the caller's own membership state (spec §1.1)
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
  select m.id, m.status, m.role, m.display_name into me
    from public.trip_members m where m.trip_id = v_trip and m.user_id = p_user;

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

-- ===========================================================================
-- 4. join_request — create a pending membership (spec §1.1, D5–D7)
-- ===========================================================================
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
  if me.id is not null then
    if me.status = 'removed' then
      return private.f05_err('member_removed');
    end if;
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
  insert into public.trip_members (trip_id, user_id, display_name, role, status, joined_at)
    values (v_trip, p_user, v_name, coalesce(v_role, 'editor'), 'pending', pg_catalog.now())
    returning id into v_id;
  perform private.f05_log('request', p_user, v_trip, p_ip, true);
  return pg_catalog.jsonb_build_object('trip_id', v_trip, 'member_id', v_id, 'status', 'pending',
                                       'role', coalesce(v_role, 'editor'), 'display_name', v_name, 'created', true);
end;
$$;

-- ===========================================================================
-- 5. join_cancel — the requester withdraws their own pending request (spec §1.2)
-- ===========================================================================
create or replace function public.join_cancel(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  n int;
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  delete from public.trip_members m where m.trip_id = p_trip and m.user_id = p_user and m.status = 'pending';
  get diagnostics n = row_count;
  if n = 0 then
    return private.f05_err('not_pending');
  end if;
  return pg_catalog.jsonb_build_object('ok', true);
end;
$$;

-- ===========================================================================
-- 6. issue_transfer — a 6-digit, 24 h, single-use code that moves the caller's ACTIVE membership to another identity
--    (D1: iPhone Safari → the installed app). Earlier unused codes of the same member are deleted.
-- ===========================================================================
create or replace function public.issue_transfer(p_user uuid, p_trip uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_member uuid;
  v_code   text;
  v_bytes  bytea;
  v_try    int;
  v_exp    timestamptz := pg_catalog.now() + interval '24 hours';
begin
  if p_user is null or p_trip is null then
    return private.f05_err('invalid_request');
  end if;
  select m.id into v_member from public.trip_members m
   where m.trip_id = p_trip and m.user_id = p_user and m.status = 'active';
  if v_member is null then
    return private.f05_err('not_member');
  end if;
  delete from private.transfer_codes c where c.member_id = v_member and c.used_at is null;
  for v_try in 1..8 loop
    v_bytes := extensions.gen_random_bytes(4);
    -- 32 random bits mod 10^6: bias < 0.03%, irrelevant for a 24 h single-use code behind a rate limit
    v_code := pg_catalog.lpad(((((pg_catalog.get_byte(v_bytes, 0)::bigint << 24) | (pg_catalog.get_byte(v_bytes, 1)::bigint << 16)
                               | (pg_catalog.get_byte(v_bytes, 2)::bigint << 8) | pg_catalog.get_byte(v_bytes, 3)::bigint) % 1000000))::text, 6, '0');
    begin
      insert into private.transfer_codes (member_id, code_hash, expires_at)
        values (v_member, pg_catalog.encode(extensions.digest(v_code, 'sha256'), 'hex'), v_exp);
      return pg_catalog.jsonb_build_object('code', v_code, 'expires_at', v_exp);
    exception when unique_violation then
      -- an open code with the same digits exists (another member); try other digits
      null;
    end;
  end loop;
  raise exception 'transfer_code_exhausted' using errcode = 'P0001';
end;
$$;

-- ===========================================================================
-- 7. claim_transfer — the new identity takes over the membership (same member id, name, role, records)
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
  end if;
  update private.transfer_codes set used_at = pg_catalog.now() where id = c.id;
  perform private.f05_log('claim', p_user, m.trip_id, p_ip, true);
  return pg_catalog.jsonb_build_object('trip_id', m.trip_id, 'member_id', m.id, 'role', m.role,
                                       'display_name', m.display_name);
end;
$$;

-- ===========================================================================
-- 8. approve_member — an active manager approves (with a role, D3) or rejects (deletes, D6) a pending row
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
begin
  if p_user is null or p_member is null or coalesce(p_decision, '') not in ('approve', 'reject') then
    return private.f05_err('invalid_request');
  end if;
  select mm.id, mm.trip_id, mm.status, mm.display_name into m
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

  if p_decision = 'reject' then
    delete from public.trip_members where id = m.id;
    return pg_catalog.jsonb_build_object('status', 'rejected', 'member_id', m.id, 'display_name', m.display_name);
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
                                       'display_name', m.display_name, 'trip_id', m.trip_id);
end;
$$;

-- ===========================================================================
-- 9. Grants: every function above is service-role only
-- ===========================================================================
revoke all on function private.f05_clean_name(text)                                     from public, anon, authenticated;
revoke all on function private.f05_name_key(text)                                       from public, anon, authenticated;
revoke all on function private.f05_trip_for_code(text)                                  from public, anon, authenticated;
revoke all on function private.f05_manager_name(uuid)                                   from public, anon, authenticated;
revoke all on function private.f05_count(text, uuid, text, uuid, boolean, interval)     from public, anon, authenticated;
revoke all on function private.f05_log(text, uuid, uuid, text, boolean)                 from public, anon, authenticated;
revoke all on function private.f05_err(text)                                            from public, anon, authenticated;
revoke all on function public.join_preview(uuid, text, text)                           from public, anon, authenticated;
revoke all on function public.join_request(uuid, text, text, text)                     from public, anon, authenticated;
revoke all on function public.join_cancel(uuid, uuid)                                  from public, anon, authenticated;
revoke all on function public.issue_transfer(uuid, uuid)                               from public, anon, authenticated;
revoke all on function public.claim_transfer(uuid, text, text)                         from public, anon, authenticated;
revoke all on function public.approve_member(uuid, uuid, text, text)                   from public, anon, authenticated;

grant execute on function private.f05_clean_name(text)                                  to service_role;
grant execute on function private.f05_name_key(text)                                    to service_role;
grant execute on function private.f05_trip_for_code(text)                               to service_role;
grant execute on function private.f05_manager_name(uuid)                                to service_role;
grant execute on function private.f05_count(text, uuid, text, uuid, boolean, interval)  to service_role;
grant execute on function private.f05_log(text, uuid, uuid, text, boolean)              to service_role;
grant execute on function private.f05_err(text)                                         to service_role;
grant execute on function public.join_preview(uuid, text, text)                        to service_role;
grant execute on function public.join_request(uuid, text, text, text)                  to service_role;
grant execute on function public.join_cancel(uuid, uuid)                               to service_role;
grant execute on function public.issue_transfer(uuid, uuid)                            to service_role;
grant execute on function public.claim_transfer(uuid, text, text)                      to service_role;
grant execute on function public.approve_member(uuid, uuid, text, text)                to service_role;
