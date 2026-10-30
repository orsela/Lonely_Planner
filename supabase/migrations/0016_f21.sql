-- Lonely Planner migration 0016_f21 · version 3.0.0-alpha.8 · F21 (anyone can request a trip; the super-admin approves)
-- CHANGE 2026-10-27 F21-DB-01: new file (no previous version). What changed from 0001–0015 (docs/F21_spec.md §2):
--   3 new tables in schema `private` (trip_requests, request_attempts, mail_log — RLS on, NO policies, no client grants);
--   2 new columns on public.manager_invites (request_id → private.trip_requests, lang 'he'|'en' default 'he');
--   service-role-only functions public.request_start / request_verify / request_resend / request_mail_failed /
--   request_approve / request_approve_undo / request_reject; helpers private.f21_*; the admin RPC
--   public.admin_trip_requests() (authenticated, refuses non-admins); public.find_invite_for_email replaced (same
--   signature, + `prefill` when the invite came from a request). No new policies, no new grants on existing tables,
--   `public` keeps exactly the 9 F01 tables.
--
-- Contract: docs/F21_spec.md §2, §4 (decisions D1, D5, D6, D10, D12, C2–C5). Idempotent: `if not exists` /
-- `create or replace` + re-applied grants; safe to run more than once. Requires 0012_f05.sql (schema `private`).
--
-- Error contract (F05 pattern): business refusals are RETURNED as {"error":"<code>"} (never raised), so the attempt and
-- counter rows written for the limits are kept. A success never contains the key "error". Codes:
--   invalid_request {field?} · rate_limited {retry_in?} · daily_limit · code_wrong {attempts_left} · code_expired ·
--   code_locked · request_unknown · request_closed · not_platform_admin
-- p_ip / p_email_hash are opaque SHA-256 hex hashes computed by the Edge Function (never a raw address or email).
--
-- Day boundary for the cap and every per-day limit (C3): the calendar day in Asia/Jerusalem.
-- Limits (§4): start ≤3 per email_hash and ≤10 per ip per day (every start attempt counts); ≤100 verified pending rows
--   (beyond → daily_limit); verify ≤5 wrong per request (5th → code_locked, row deleted), ≤20 wrong per ip per hour;
--   resend ≥60 s after the previous send, ≤3 per request; cap 50 F21 mails ('code' + 'reject') per day.

-- ===========================================================================
-- 1. Tables
-- ===========================================================================
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to service_role;

create table if not exists private.trip_requests (
  id              uuid primary key default gen_random_uuid(),
  lang            text not null,
  name            text not null,
  email           text not null,
  countries       text[] not null,
  month           date,
  travellers      smallint not null,
  note            text,
  status          text not null default 'unverified',
  code_hash       text,
  code_expires_at timestamptz,
  code_attempts   smallint not null default 0,
  code_sent_at    timestamptz,
  resend_count    smallint not null default 0,
  ip_hash         text,
  verified_at     timestamptz,
  decided_at      timestamptz,
  decided_by      uuid,
  reject_mailed   boolean,
  invite_id       uuid references public.manager_invites (id) on delete set null,
  created_at      timestamptz not null default now(),
  constraint trip_requests_lang       check (lang in ('he', 'en')),
  constraint trip_requests_name_len   check (char_length(name) between 1 and 40),
  constraint trip_requests_email_low  check (email = lower(email)),
  constraint trip_requests_countries  check (cardinality(countries) between 1 and 10
                                             and array_to_string(countries, ',') ~ '^[A-Z]{2}(,[A-Z]{2})*$'
                                             and array_position(countries, null) is null),
  constraint trip_requests_month_day1 check (month is null or extract(day from month) = 1),
  constraint trip_requests_travellers check (travellers between 1 and 30),
  constraint trip_requests_note_len   check (note is null or char_length(note) <= 200),
  constraint trip_requests_status     check (status in ('unverified', 'pending', 'approved', 'rejected')),
  constraint trip_requests_code_hash  check (code_hash is null or code_hash ~ '^[0-9a-f]{64}$')
);
create index if not exists trip_requests_status_verified_idx on private.trip_requests (status, verified_at);
create index if not exists trip_requests_email_created_idx   on private.trip_requests (email, created_at);

create table if not exists private.request_attempts (
  id          bigint generated always as identity primary key,
  kind        text not null,
  email_hash  text,
  ip_hash     text,
  request_id  uuid,
  ok          boolean not null default false,
  at          timestamptz not null default now(),
  constraint request_attempts_kind check (kind in ('start', 'verify', 'resend'))
);
create index if not exists request_attempts_kind_email_at_idx on private.request_attempts (kind, email_hash, at);
create index if not exists request_attempts_kind_ip_at_idx    on private.request_attempts (kind, ip_hash, at);

-- request_id (no FK on purpose: deleting or replacing a request must never give mail headroom back, D10) lets
-- request_mail_failed() remove exactly the row of a mail that was NOT sent (spec §3.1 "the code mail log row is removed").
create table if not exists private.mail_log (
  id          bigint generated always as identity primary key,
  kind        text not null,
  request_id  uuid,
  at          timestamptz not null default now(),
  constraint mail_log_kind check (kind in ('code', 'reject'))
);
create index if not exists mail_log_at_idx on private.mail_log (at);

alter table private.trip_requests    enable row level security;
alter table private.request_attempts enable row level security;
alter table private.mail_log         enable row level security;
-- no policies: service role only (the schema itself is closed to clients too)
revoke all on private.trip_requests    from public, anon, authenticated;
revoke all on private.request_attempts from public, anon, authenticated;
revoke all on private.mail_log         from public, anon, authenticated;
grant select, insert, update, delete on private.trip_requests    to service_role;
grant select, insert, update, delete on private.request_attempts to service_role;
grant select, insert, update, delete on private.mail_log         to service_role;

-- ===========================================================================
-- 2. public.manager_invites: request link + email language (§2.4). Existing rows get 'he'.
-- ===========================================================================
alter table public.manager_invites add column if not exists request_id uuid;
alter table public.manager_invites add column if not exists lang text not null default 'he';
do $f21$
begin
  if not exists (select 1 from pg_catalog.pg_constraint
                  where conrelid = 'public.manager_invites'::regclass and conname = 'manager_invites_request_id_fkey') then
    alter table public.manager_invites
      add constraint manager_invites_request_id_fkey foreign key (request_id)
      references private.trip_requests (id) on delete set null;
  end if;
  if not exists (select 1 from pg_catalog.pg_constraint
                  where conrelid = 'public.manager_invites'::regclass and conname = 'manager_invites_lang') then
    alter table public.manager_invites add constraint manager_invites_lang check (lang in ('he', 'en'));
  end if;
end
$f21$;

-- ===========================================================================
-- 3. Internal helpers (private, service role only)
-- ===========================================================================
create or replace function private.f21_err(p_code text)
returns jsonb language sql immutable set search_path = '' as $$
  select pg_catalog.jsonb_build_object('error', p_code)
$$;

create or replace function private.f21_bad(p_field text)
returns jsonb language sql immutable set search_path = '' as $$
  select pg_catalog.jsonb_build_object('error', 'invalid_request', 'field', p_field)
$$;

-- start of today in Asia/Jerusalem (C3)
create or replace function private.f21_day_start()
returns timestamptz language sql stable set search_path = '' as $$
  select (pg_catalog.date_trunc('day', pg_catalog.now() at time zone 'Asia/Jerusalem')) at time zone 'Asia/Jerusalem'
$$;

-- first day of the current month in Asia/Jerusalem (D7 month window)
create or replace function private.f21_month_start()
returns date language sql stable set search_path = '' as $$
  select pg_catalog.date_trunc('month', pg_catalog.now() at time zone 'Asia/Jerusalem')::date
$$;

create or replace function private.f21_mail_today()
returns int language sql stable security definer set search_path = '' as $$
  select pg_catalog.count(*)::int from private.mail_log l where l.at >= private.f21_day_start()
$$;

-- D5 / C5: opportunistic clean-up, run by every request-trip call and every admin list load
create or replace function private.f21_cleanup()
returns void language plpgsql volatile security definer set search_path = '' as $$
begin
  delete from private.trip_requests r where r.status = 'rejected'   and r.decided_at < pg_catalog.now() - interval '5 days';
  delete from private.trip_requests r where r.status = 'unverified' and r.created_at < pg_catalog.now() - interval '5 days';
  delete from private.request_attempts a where a.at < pg_catalog.now() - interval '7 days';
  delete from private.mail_log l where l.at < pg_catalog.now() - interval '7 days';
end;
$$;

create or replace function private.f21_count(p_kind text, p_email_hash text, p_ip text, p_ok boolean, p_since timestamptz)
returns int language sql stable security definer set search_path = '' as $$
  select pg_catalog.count(*)::int
    from private.request_attempts a
   where a.kind = p_kind
     and (p_email_hash is null or a.email_hash = p_email_hash)
     and (p_ip is null or a.ip_hash = p_ip)
     and (p_ok is null or a.ok = p_ok)
     and a.at >= p_since
$$;

create or replace function private.f21_log(p_kind text, p_email_hash text, p_ip text, p_request uuid, p_ok boolean)
returns void language sql volatile security definer set search_path = '' as $$
  insert into private.request_attempts (kind, email_hash, ip_hash, request_id, ok)
  values (p_kind, p_email_hash, p_ip, p_request, p_ok)
$$;

-- ===========================================================================
-- 4. request_start — validates, limits, cap; inserts an `unverified` row with the code hash (10 min); logs a code mail
-- ===========================================================================
create or replace function public.request_start(p_request uuid, p_payload jsonb, p_email_hash text, p_ip text, p_code_hash text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  c_email_re constant text := '^[^[:space:]@<>()",;:\\[\]]+@[^[:space:]@<>()",;:\\[\]]+\.[^[:space:]@<>()",;:\\[\]]{2,}$';
  v_lang  text;
  v_name  text;
  v_email text;
  v_countries text[];
  v_month date;
  v_trav  int;
  v_note  text;
  v_el    jsonb;
  v_m     text;
  v_cur   date := private.f21_month_start();
begin
  perform private.f21_cleanup();
  if p_request is null or p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$'
     or p_email_hash is null or p_email_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;

  -- §4 per-day limits: every start attempt counts, ok or not
  if private.f21_count('start', p_email_hash, null, null, private.f21_day_start()) >= 3
     or (p_ip is not null and private.f21_count('start', null, p_ip, null, private.f21_day_start()) >= 10) then
    return private.f21_err('rate_limited');
  end if;
  perform private.f21_log('start', p_email_hash, p_ip, null, false);

  -- validation (same rules as the form, spec §1.2)
  if p_payload is null or pg_catalog.jsonb_typeof(p_payload) <> 'object' then
    return private.f21_bad('payload');
  end if;
  v_lang := p_payload->>'lang';
  if v_lang is null or v_lang not in ('he', 'en') then return private.f21_bad('lang'); end if;
  if pg_catalog.jsonb_typeof(p_payload->'name') is distinct from 'string' then return private.f21_bad('name'); end if;
  v_name := pg_catalog.btrim(p_payload->>'name');
  if pg_catalog.char_length(v_name) not between 1 and 40 or v_name ~ '[[:cntrl:]]' then return private.f21_bad('name'); end if;
  if pg_catalog.jsonb_typeof(p_payload->'email') is distinct from 'string' then return private.f21_bad('email'); end if;
  v_email := pg_catalog.lower(pg_catalog.btrim(p_payload->>'email'));
  if pg_catalog.char_length(v_email) not between 6 and 254 or v_email !~ c_email_re then return private.f21_bad('email'); end if;
  if pg_catalog.jsonb_typeof(p_payload->'countries') is distinct from 'array'
     or pg_catalog.jsonb_array_length(p_payload->'countries') not between 1 and 10 then
    return private.f21_bad('countries');
  end if;
  v_countries := array[]::text[];
  for v_el in select e from pg_catalog.jsonb_array_elements(p_payload->'countries') e loop
    if pg_catalog.jsonb_typeof(v_el) <> 'string' or (v_el #>> '{}') !~ '^[A-Z]{2}$'
       or (v_el #>> '{}') = any (v_countries) then
      return private.f21_bad('countries');
    end if;
    v_countries := v_countries || (v_el #>> '{}');
  end loop;
  if p_payload->'month' is null or p_payload->'month' = 'null'::jsonb then
    v_month := null;
  else
    v_m := case when pg_catalog.jsonb_typeof(p_payload->'month') = 'string' then p_payload->>'month' end;
    if v_m is null or v_m !~ '^\d{4}-(0[1-9]|1[0-2])(-01)?$' then return private.f21_bad('month'); end if;
    v_month := pg_catalog.to_date(pg_catalog.left(v_m, 7) || '-01', 'YYYY-MM-DD');
    if v_month < v_cur or v_month >= (v_cur + interval '18 months')::date then return private.f21_bad('month'); end if;
  end if;
  if pg_catalog.jsonb_typeof(p_payload->'travellers') is distinct from 'number'
     or (p_payload->>'travellers') !~ '^\d{1,2}$' then
    return private.f21_bad('travellers');
  end if;
  v_trav := (p_payload->>'travellers')::int;
  if v_trav not between 1 and 30 then return private.f21_bad('travellers'); end if;
  if p_payload->'note' is null or p_payload->'note' = 'null'::jsonb then
    v_note := null;
  elsif pg_catalog.jsonb_typeof(p_payload->'note') <> 'string' then
    return private.f21_bad('note');
  else
    v_note := nullif(pg_catalog.btrim(p_payload->>'note'), '');
    if pg_catalog.char_length(v_note) > 200 then return private.f21_bad('note'); end if;
  end if;

  -- queue and cap (D10): both answer daily_limit
  if (select pg_catalog.count(*) from private.trip_requests r where r.status = 'pending') >= 100
     or private.f21_mail_today() >= 50 then
    return private.f21_err('daily_limit');
  end if;

  delete from private.trip_requests r where r.email = v_email and r.status = 'unverified';
  insert into private.trip_requests (id, lang, name, email, countries, month, travellers, note, status, code_hash,
                                     code_expires_at, code_attempts, code_sent_at, resend_count, ip_hash)
  values (p_request, v_lang, v_name, v_email, v_countries, v_month, v_trav, v_note, 'unverified', p_code_hash,
          pg_catalog.now() + interval '10 minutes', 0, pg_catalog.now(), 0, p_ip);
  insert into private.mail_log (kind, request_id) values ('code', p_request);
  update private.request_attempts a set ok = true, request_id = p_request
   where a.id = (select max(b.id) from private.request_attempts b where b.kind = 'start' and b.email_hash = p_email_hash);
  return pg_catalog.jsonb_build_object('request_id', p_request, 'sent_at', pg_catalog.now());
end;
$$;

-- ===========================================================================
-- 5. request_verify — right code → pending; wrong → code_wrong {attempts_left}; 5th wrong → code_locked (row deleted)
-- ===========================================================================
create or replace function public.request_verify(p_request uuid, p_code_hash text, p_ip text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r record;
  v_n int;
begin
  perform private.f21_cleanup();
  if p_request is null or p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;
  if p_ip is not null
     and private.f21_count('verify', null, p_ip, false, pg_catalog.now() - interval '1 hour') >= 20 then
    return private.f21_err('rate_limited');
  end if;
  select q.id, q.status, q.code_hash, q.code_expires_at, q.code_attempts into r
    from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'unverified' or r.code_hash is null then
    return private.f21_err('request_unknown');
  end if;
  if r.code_expires_at <= pg_catalog.now() then
    return private.f21_err('code_expired');
  end if;
  if r.code_hash = p_code_hash then
    update private.trip_requests q
       set status = 'pending', verified_at = pg_catalog.now(), code_hash = null, code_expires_at = null
     where q.id = p_request;
    perform private.f21_log('verify', null, p_ip, p_request, true);
    return pg_catalog.jsonb_build_object('status', 'pending', 'request_id', p_request);
  end if;
  perform private.f21_log('verify', null, p_ip, p_request, false);
  v_n := r.code_attempts + 1;
  if v_n >= 5 then
    delete from private.trip_requests q where q.id = p_request;
    return private.f21_err('code_locked');
  end if;
  update private.trip_requests q set code_attempts = v_n where q.id = p_request;
  return pg_catalog.jsonb_build_object('error', 'code_wrong', 'attempts_left', 5 - v_n);
end;
$$;

-- ===========================================================================
-- 6. request_resend — cooldown 60 s, ≤3 per request, cap; replaces the hash (the previous code stops working).
--    Returns {request_id, sent_at, email, lang}.
-- ===========================================================================
create or replace function public.request_resend(p_request uuid, p_code_hash text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r record;
  v_wait int;
begin
  perform private.f21_cleanup();
  if p_request is null or p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;
  select q.id, q.status, q.code_sent_at, q.resend_count, q.ip_hash, q.email, q.lang into r
    from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'unverified' then
    return private.f21_err('request_unknown');
  end if;
  if r.code_sent_at is not null and r.code_sent_at > pg_catalog.now() - interval '60 seconds' then
    v_wait := pg_catalog.ceil(extract(epoch from (r.code_sent_at + interval '60 seconds' - pg_catalog.now())))::int;
    return pg_catalog.jsonb_build_object('error', 'rate_limited', 'retry_in', greatest(v_wait, 1));
  end if;
  if r.resend_count >= 3 then
    return private.f21_err('rate_limited');
  end if;
  if private.f21_mail_today() >= 50 then
    return private.f21_err('daily_limit');
  end if;
  update private.trip_requests q
     set code_hash = p_code_hash, code_expires_at = pg_catalog.now() + interval '10 minutes', code_attempts = 0,
         code_sent_at = pg_catalog.now(), resend_count = r.resend_count + 1
   where q.id = p_request;
  insert into private.mail_log (kind, request_id) values ('code', p_request);
  perform private.f21_log('resend', null, r.ip_hash, p_request, true);
  -- email + lang: the Edge Function needs them to send the new code (it never reads the private table itself)
  return pg_catalog.jsonb_build_object('request_id', p_request, 'sent_at', pg_catalog.now(), 'email', r.email, 'lang', r.lang);
end;
$$;

-- ===========================================================================
-- 7. request_mail_failed — the code email of a start / resend was NOT sent (spec §3.1):
--    'start'  → the unverified row and its code mail row are deleted;
--    'resend' → the newest code mail row is deleted, resend_count goes back, the cooldown is lifted (a new resend may
--               follow at once). The code hash stays the new one (nobody knows it); the requester taps "resend" again.
-- ===========================================================================
create or replace function public.request_mail_failed(p_request uuid, p_action text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  if p_request is null or p_action is null or p_action not in ('start', 'resend') then
    return private.f21_err('invalid_request');
  end if;
  delete from private.mail_log l
   where l.id = (select max(m.id) from private.mail_log m where m.request_id = p_request and m.kind = 'code');
  if p_action = 'start' then
    delete from private.trip_requests q where q.id = p_request and q.status = 'unverified';
  else
    update private.trip_requests q
       set resend_count = greatest(q.resend_count - 1, 0), code_sent_at = pg_catalog.now() - interval '61 seconds'
     where q.id = p_request and q.status = 'unverified';
  end if;
  return pg_catalog.jsonb_build_object('ok', true);
end;
$$;

-- ===========================================================================
-- 8. request_approve — one transaction (D12): pending → revoke the open invite of the email → new invite → approved
-- ===========================================================================
create or replace function public.request_approve(p_admin uuid, p_request uuid, p_token_hash text, p_draft text, p_inviter text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r        record;
  v_draft  text := nullif(pg_catalog.btrim(coalesce(p_draft, '')), '');
  v_inv    text := pg_catalog.left(nullif(pg_catalog.btrim(coalesce(p_inviter, '')), ''), 40);
  v_old    uuid;
  v_new    uuid;
  v_exp    timestamptz := pg_catalog.now() + interval '7 days';
begin
  if p_admin is null or p_request is null or p_token_hash is null or p_token_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;
  if not exists (select 1 from public.platform_admins a where a.user_id = p_admin) then
    return private.f21_err('not_platform_admin');
  end if;
  if v_draft is not null and (pg_catalog.char_length(v_draft) > 80 or v_draft ~ '[[:cntrl:]]') then
    return private.f21_bad('draft_name');
  end if;
  select q.id, q.status, q.email, q.name, q.lang into r
    from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'pending' then
    return private.f21_err('request_closed');
  end if;

  -- D12: the open invite of this email (unused, unrevoked; expired or not) is revoked — it holds the one-per-email slot
  update public.manager_invites i set revoked_at = pg_catalog.now()
   where i.email = r.email and i.used_at is null and i.revoked_at is null
  returning i.id into v_old;

  insert into public.manager_invites (email, token_hash, draft_name, invited_by, inviter_name, expires_at, last_sent_at,
                                      send_count, request_id, lang)
  values (r.email, p_token_hash, v_draft, p_admin, coalesce(v_inv, 'מנהל המערכת'), v_exp, pg_catalog.now(), 1,
          p_request, r.lang)
  returning id into v_new;

  update private.trip_requests q
     set status = 'approved', invite_id = v_new, decided_at = pg_catalog.now(), decided_by = p_admin
   where q.id = p_request;

  return pg_catalog.jsonb_build_object('invite_id', v_new, 'expires_at', v_exp, 'revoked_invite_id', v_old,
                                       'email', r.email, 'name', r.name, 'lang', r.lang, 'draft_name', v_draft);
end;
$$;

-- ===========================================================================
-- 9. request_approve_undo — only when the invite email failed: delete the new invite, re-open the revoked one,
--    request back to pending (spec §2.6, criterion 14)
-- ===========================================================================
create or replace function public.request_approve_undo(p_invite uuid, p_revoked uuid, p_request uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  if p_invite is null or p_request is null then
    return private.f21_err('invalid_request');
  end if;
  delete from public.manager_invites i where i.id = p_invite and i.request_id = p_request and i.used_at is null;
  if p_revoked is not null then
    update public.manager_invites i set revoked_at = null
     where i.id = p_revoked and i.used_at is null
       and not exists (select 1 from public.manager_invites o
                        where o.email = i.email and o.id <> i.id and o.used_at is null and o.revoked_at is null);
  end if;
  update private.trip_requests q
     set status = 'pending', invite_id = null, decided_at = null, decided_by = null
   where q.id = p_request and q.status = 'approved';
  return pg_catalog.jsonb_build_object('ok', true);
end;
$$;

-- ===========================================================================
-- 10. request_reject — pending → rejected; when p_mail and under the cap logs a reject mail (C2)
-- ===========================================================================
create or replace function public.request_reject(p_admin uuid, p_request uuid, p_mail boolean)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r record;
  v_mail boolean := false;
  v_reason text;
begin
  if p_admin is null or p_request is null or p_mail is null then
    return private.f21_err('invalid_request');
  end if;
  if not exists (select 1 from public.platform_admins a where a.user_id = p_admin) then
    return private.f21_err('not_platform_admin');
  end if;
  select q.id, q.status, q.email, q.name, q.lang into r
    from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'pending' then
    return private.f21_err('request_closed');
  end if;
  if p_mail then
    if private.f21_mail_today() >= 50 then
      v_reason := 'daily_limit';
    else
      v_mail := true;
      insert into private.mail_log (kind, request_id) values ('reject', p_request);
    end if;
  else
    v_reason := 'not_requested';
  end if;
  update private.trip_requests q
     set status = 'rejected', decided_at = pg_catalog.now(), decided_by = p_admin, reject_mailed = v_mail
   where q.id = p_request;
  if v_mail then
    return pg_catalog.jsonb_build_object('mail', true, 'lang', r.lang, 'email', r.email, 'name', r.name);
  end if;
  return pg_catalog.jsonb_build_object('mail', false, 'reason', v_reason);
end;
$$;

-- ===========================================================================
-- 11. admin_trip_requests — the super-admin's list (§2.7). Verified pending requests only, oldest verification first.
-- ===========================================================================
create or replace function public.admin_trip_requests()
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_list jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'not_platform_admin' using errcode = '42501';
  end if;
  perform private.f21_cleanup();
  select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
           'id',          q.id,
           'lang',        q.lang,
           'name',        q.name,
           'email',       q.email,
           'countries',   pg_catalog.to_jsonb(q.countries),
           'month',       q.month,
           'travellers',  q.travellers,
           'note',        q.note,
           'verified_at', q.verified_at,
           'manages',     coalesce((select pg_catalog.jsonb_agg(t.name order by t.name)
                                      from public.trip_members m
                                      join public.trips t on t.id = m.trip_id
                                      join auth.users u on u.id = m.user_id
                                     where pg_catalog.lower(u.email) = q.email
                                       and m.role = 'manager' and m.status = 'active'), '[]'::jsonb),
           'active_invite', (select pg_catalog.jsonb_build_object('id', i.id, 'draft_name', i.draft_name,
                                      'last_sent_at', coalesce(i.last_sent_at, i.created_at), 'expires_at', i.expires_at)
                               from public.manager_invites i
                              where i.email = q.email and i.used_at is null and i.revoked_at is null
                                and i.expires_at > pg_catalog.now()
                              order by i.created_at desc limit 1)
         ) order by q.verified_at, q.id), '[]'::jsonb)
    into v_list
    from private.trip_requests q
   where q.status = 'pending';
  return pg_catalog.jsonb_build_object('cap', 50, 'mail_today', private.f21_mail_today(), 'requests', v_list);
end;
$$;

-- ===========================================================================
-- 12. find_invite_for_email — replaced (same signature). CHANGE 2026-10-27 F21-DB-02: what changed from 0010_f04.sql:
--     + `lang` is read, and `prefill {name, countries, month, lang}` is added when the invite has a request_id whose
--     request row still exists. Output for every other invite is unchanged (same keys, same values).
-- ===========================================================================
create or replace function public.find_invite_for_email(p_email text)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_email text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_email, '')));
  r record;
  q record;
  v_out jsonb;
begin
  if v_email = '' then
    return pg_catalog.jsonb_build_object('found', false);
  end if;
  select i.id, i.draft_name, i.inviter_name, i.expires_at, i.request_id
    into r
    from public.manager_invites i
   where i.email = v_email
     and i.used_at is null
     and i.revoked_at is null
     and i.expires_at > pg_catalog.now()
   order by i.created_at desc
   limit 1;
  if not found then
    return pg_catalog.jsonb_build_object('found', false);
  end if;
  v_out := pg_catalog.jsonb_build_object(
    'found', true,
    'invite_id', r.id,
    'draft_name', r.draft_name,
    'inviter_name', r.inviter_name,
    'expires_at', r.expires_at);
  if r.request_id is not null then
    select t.name, t.countries, t.month, t.lang into q from private.trip_requests t where t.id = r.request_id;
    if found then
      v_out := v_out || pg_catalog.jsonb_build_object('prefill', pg_catalog.jsonb_build_object(
        'name', q.name, 'countries', pg_catalog.to_jsonb(q.countries), 'month', q.month, 'lang', q.lang));
    end if;
  end if;
  return v_out;
end;
$$;

-- ===========================================================================
-- 13. Grants (§2.9): every new function service-role only, except admin_trip_requests (+ authenticated)
-- ===========================================================================
revoke all on function private.f21_err(text)                                         from public, anon, authenticated;
revoke all on function private.f21_bad(text)                                         from public, anon, authenticated;
revoke all on function private.f21_day_start()                                       from public, anon, authenticated;
revoke all on function private.f21_month_start()                                     from public, anon, authenticated;
revoke all on function private.f21_mail_today()                                      from public, anon, authenticated;
revoke all on function private.f21_cleanup()                                         from public, anon, authenticated;
revoke all on function private.f21_count(text, text, text, boolean, timestamptz)     from public, anon, authenticated;
revoke all on function private.f21_log(text, text, text, uuid, boolean)              from public, anon, authenticated;
revoke all on function public.request_start(uuid, jsonb, text, text, text)           from public, anon, authenticated;
revoke all on function public.request_verify(uuid, text, text)                       from public, anon, authenticated;
revoke all on function public.request_resend(uuid, text)                             from public, anon, authenticated;
revoke all on function public.request_mail_failed(uuid, text)                        from public, anon, authenticated;
revoke all on function public.request_approve(uuid, uuid, text, text, text)          from public, anon, authenticated;
revoke all on function public.request_approve_undo(uuid, uuid, uuid)                 from public, anon, authenticated;
revoke all on function public.request_reject(uuid, uuid, boolean)                    from public, anon, authenticated;
revoke all on function public.admin_trip_requests()                                  from public, anon;
revoke all on function public.find_invite_for_email(text)                            from public, anon, authenticated;

grant execute on function private.f21_err(text)                                      to service_role;
grant execute on function private.f21_bad(text)                                      to service_role;
grant execute on function private.f21_day_start()                                    to service_role;
grant execute on function private.f21_month_start()                                  to service_role;
grant execute on function private.f21_mail_today()                                  to service_role;
grant execute on function private.f21_cleanup()                                      to service_role;
grant execute on function private.f21_count(text, text, text, boolean, timestamptz)  to service_role;
grant execute on function private.f21_log(text, text, text, uuid, boolean)           to service_role;
grant execute on function public.request_start(uuid, jsonb, text, text, text)        to service_role;
grant execute on function public.request_verify(uuid, text, text)                    to service_role;
grant execute on function public.request_resend(uuid, text)                          to service_role;
grant execute on function public.request_mail_failed(uuid, text)                     to service_role;
grant execute on function public.request_approve(uuid, uuid, text, text, text)       to service_role;
grant execute on function public.request_approve_undo(uuid, uuid, uuid)              to service_role;
grant execute on function public.request_reject(uuid, uuid, boolean)                 to service_role;
grant execute on function public.admin_trip_requests()                               to authenticated, service_role;
grant execute on function public.find_invite_for_email(text)                         to service_role;
