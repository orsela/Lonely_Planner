-- Lonely Planner migration 0020_f23 · version 3.0.0-alpha.12 · F23 (open request without approval + AI destination ideas)
-- CHANGE 2026-11-13 F23-DB-01: new file (no previous version). What changed from 0016_f21.sql (docs/F23_spec.md C1–C13):
--   private.trip_requests: + where_mode, interests, max_flight, pref_note, suggestions, session_hash; status gains
--     'auto_approved'; the countries check now allows an EMPTY list while where_mode = 'undecided';
--   private.request_attempts.kind gains 'suggest' and 'auto'; private.mail_log.kind gains 'invite' (C4: the auto invite
--     email counts in the 50/day cap);
--   new service-role functions public.request_verify2 / request_suggest_begin / request_suggest_save / request_choose /
--     request_invite_mail_failed / request_invite_draft; helpers private.f23_*;
--   REPLACED (flagged, same signatures): public.request_start (accepts the "undecided" payload; a payload without
--     where_mode behaves exactly as in 0016) and public.admin_trip_requests (same keys + `auto`, `ai_today`, `ai_cap`;
--     verified requests that still have no destination are not listed as pending).
--   NOT changed: request_verify, request_resend, request_mail_failed, request_approve, request_approve_undo,
--     request_reject, find_invite_for_email, every table in `public`, every policy and grant on existing tables.
--
-- Idempotent (`if not exists` / `create or replace` / constraints dropped and re-added). Requires 0016_f21.sql.
-- Error contract as 0016: refusals are RETURNED as {"error":"<code>"}. New codes: suggest_limit (3 per request, D4) ·
--   suggest_unavailable (30 per Israel day, C7). Every session / state problem of suggest / choose answers the generic
--   request_unknown (criterion 8). A second auto-approval for one email on one day answers rate_limited (criterion 9).
-- Session: verify of an undecided request stores p_session_hash (SHA-256 hex of a random token made by the function and
--   returned to that browser only); suggest / choose must present it, within 30 minutes of the verification (C5).

-- ===========================================================================
-- 1. Columns and checks
-- ===========================================================================
alter table private.trip_requests add column if not exists where_mode   text  not null default 'known';
alter table private.trip_requests add column if not exists interests    text[];
alter table private.trip_requests add column if not exists max_flight   text;
alter table private.trip_requests add column if not exists pref_note    text;
alter table private.trip_requests add column if not exists suggestions  jsonb not null default '[]'::jsonb;
alter table private.trip_requests add column if not exists session_hash text;

alter table private.trip_requests drop constraint if exists trip_requests_status;
alter table private.trip_requests add  constraint trip_requests_status
  check (status in ('unverified', 'pending', 'approved', 'rejected', 'auto_approved'));

alter table private.trip_requests drop constraint if exists trip_requests_countries;
alter table private.trip_requests add  constraint trip_requests_countries
  check (array_position(countries, null) is null
         and ((cardinality(countries) between 1 and 10 and array_to_string(countries, ',') ~ '^[A-Z]{2}(,[A-Z]{2})*$')
              or (where_mode = 'undecided' and cardinality(countries) = 0)));

alter table private.trip_requests drop constraint if exists trip_requests_where_mode;
alter table private.trip_requests add  constraint trip_requests_where_mode check (where_mode in ('known', 'undecided'));
alter table private.trip_requests drop constraint if exists trip_requests_interests;
alter table private.trip_requests add  constraint trip_requests_interests
  check (interests is null or (cardinality(interests) between 1 and 6
         and interests <@ array['nature', 'food', 'beaches', 'cities', 'kids', 'extreme']::text[]));
alter table private.trip_requests drop constraint if exists trip_requests_max_flight;
alter table private.trip_requests add  constraint trip_requests_max_flight check (max_flight is null or max_flight in ('5', '8', 'any'));
alter table private.trip_requests drop constraint if exists trip_requests_pref_note;
alter table private.trip_requests add  constraint trip_requests_pref_note check (pref_note is null or char_length(pref_note) <= 100);
alter table private.trip_requests drop constraint if exists trip_requests_session_hash;
alter table private.trip_requests add  constraint trip_requests_session_hash check (session_hash is null or session_hash ~ '^[0-9a-f]{64}$');
alter table private.trip_requests drop constraint if exists trip_requests_suggestions;
alter table private.trip_requests add  constraint trip_requests_suggestions check (jsonb_typeof(suggestions) = 'array');

alter table private.request_attempts drop constraint if exists request_attempts_kind;
alter table private.request_attempts add  constraint request_attempts_kind
  check (kind in ('start', 'verify', 'resend', 'suggest', 'auto'));
create index if not exists request_attempts_kind_request_idx on private.request_attempts (kind, request_id);

alter table private.mail_log drop constraint if exists mail_log_kind;
alter table private.mail_log add  constraint mail_log_kind check (kind in ('code', 'reject', 'invite'));

-- ===========================================================================
-- 2. Helpers (private, service role only)
-- ===========================================================================
-- same value as the Edge Function's sha256Hex(normalized email)
create or replace function private.f23_email_hash(p_email text)
returns text language sql immutable set search_path = '' as $$
  select pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.lower(pg_catalog.btrim(p_email)), 'UTF8')), 'hex')
$$;

-- C7: AI calls made today (Israel day), every attempt counts whether or not the model answered
create or replace function private.f23_suggest_today()
returns int language sql stable security definer set search_path = '' as $$
  select pg_catalog.count(*)::int from private.request_attempts a
   where a.kind = 'suggest' and a.at >= private.f21_day_start()
$$;

-- F21 clean-up + verified requests that never got a destination (abandoned on the suggestions screen): 3 days
-- CHANGE 2026-11-13 F23-DB-04: was 5 days in the first draft of this file; Or decided 3 days (2026-11-13).
create or replace function private.f23_cleanup()
returns void language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.f21_cleanup();
  delete from private.trip_requests r
   where r.status = 'pending' and pg_catalog.cardinality(r.countries) = 0
     and r.verified_at < pg_catalog.now() - interval '3 days';
end;
$$;

-- C1: the approve transaction of request_approve (D12: revoke the open invite of the email → new invite → request
-- handled), without an admin. The caller holds the row lock and has done its own state checks.
-- Refuses with rate_limited when this email already had an auto-approval today (C13).
create or replace function private.f23_auto_approve(p_request uuid, p_token_hash text, p_draft text)
returns jsonb language plpgsql volatile security definer set search_path = '' as $$
declare
  r       record;
  v_draft text := nullif(pg_catalog.btrim(coalesce(p_draft, '')), '');
  v_hash  text;
  v_old   uuid;
  v_new   uuid;
  v_mail  boolean := false;
  v_exp   timestamptz := pg_catalog.now() + interval '7 days';
begin
  if p_token_hash is null or p_token_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;
  if v_draft is not null and (pg_catalog.char_length(v_draft) > 80 or v_draft ~ '[[:cntrl:]]') then
    v_draft := null;  -- the name is only a prefill of the wizard; a bad one is dropped, never a reason to refuse
  end if;
  select q.id, q.email, q.name, q.lang, q.countries, q.month, q.travellers into r
    from private.trip_requests q where q.id = p_request;
  v_hash := private.f23_email_hash(r.email);
  if private.f21_count('auto', v_hash, null, true, private.f21_day_start()) >= 1 then
    return private.f21_err('rate_limited');
  end if;

  update public.manager_invites i set revoked_at = pg_catalog.now()
   where i.email = r.email and i.used_at is null and i.revoked_at is null
  returning i.id into v_old;

  insert into public.manager_invites (email, token_hash, draft_name, invited_by, inviter_name, expires_at, last_sent_at,
                                      send_count, request_id, lang)
  values (r.email, p_token_hash, v_draft, null, 'Lonely Planner', v_exp, pg_catalog.now(), 1, p_request, r.lang)
  returning id into v_new;

  if private.f21_mail_today() < 50 then      -- C4: the invite email counts in the cap; at the cap it is skipped
    v_mail := true;
    insert into private.mail_log (kind, request_id) values ('invite', p_request);
  end if;

  update private.trip_requests q
     set status = 'auto_approved', invite_id = v_new, decided_at = pg_catalog.now(), decided_by = null,
         verified_at = coalesce(q.verified_at, pg_catalog.now()), code_hash = null, code_expires_at = null,
         session_hash = null
   where q.id = p_request;
  perform private.f21_log('auto', v_hash, null, p_request, true);

  return pg_catalog.jsonb_build_object('status', 'auto_approved', 'next', 'ready', 'request_id', p_request,
    'invite_id', v_new, 'expires_at', v_exp, 'revoked_invite_id', v_old, 'mail', v_mail, 'email', r.email,
    'name', r.name, 'lang', r.lang, 'draft_name', v_draft, 'countries', pg_catalog.to_jsonb(r.countries),
    'month', r.month, 'travellers', r.travellers);
end;
$$;

-- locks and returns the request of a suggest / choose call, or null when the session is not acceptable (C5)
create or replace function private.f23_session(p_request uuid, p_session_hash text)
returns private.trip_requests language plpgsql volatile security definer set search_path = '' as $$
declare r private.trip_requests;
begin
  if p_request is null or p_session_hash is null or p_session_hash !~ '^[0-9a-f]{64}$' then return null; end if;
  select q.* into r from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'pending' or r.where_mode <> 'undecided' or pg_catalog.cardinality(r.countries) <> 0
     or r.session_hash is null or r.session_hash <> p_session_hash
     or r.verified_at is null or r.verified_at < pg_catalog.now() - interval '30 minutes' then
    return null;
  end if;
  return r;
end;
$$;

-- ===========================================================================
-- 3. request_start — REPLACED. CHANGE 2026-11-13 F23-DB-02: what changed from 0016_f21.sql: an optional
--    `where_mode` in the payload. Absent or 'known' → every line below behaves as before. 'undecided' (C9) → `countries`
--    must be absent or empty, `interests` 1–6 distinct keys of the fixed list, `max_flight` '5' | '8' | 'any'
--    (default '5'), `pref_note` ≤ 100 characters. Limits, cap, code and the returned keys are unchanged.
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
  c_keys     constant text[] := array['nature', 'food', 'beaches', 'cities', 'kids', 'extreme'];
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
  v_mode  text := 'known';
  v_int   text[];
  v_flight text;
  v_pref  text;
begin
  perform private.f23_cleanup();
  if p_request is null or p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$'
     or p_email_hash is null or p_email_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;

  if private.f21_count('start', p_email_hash, null, null, private.f21_day_start()) >= 3
     or (p_ip is not null and private.f21_count('start', null, p_ip, null, private.f21_day_start()) >= 10) then
    return private.f21_err('rate_limited');
  end if;
  perform private.f21_log('start', p_email_hash, p_ip, null, false);

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

  -- F23: where_mode
  if p_payload ? 'where_mode' and p_payload->'where_mode' <> 'null'::jsonb then
    if pg_catalog.jsonb_typeof(p_payload->'where_mode') <> 'string' or (p_payload->>'where_mode') not in ('known', 'undecided') then
      return private.f21_bad('where_mode');
    end if;
    v_mode := p_payload->>'where_mode';
  end if;

  v_countries := array[]::text[];
  if v_mode = 'known' then
    if pg_catalog.jsonb_typeof(p_payload->'countries') is distinct from 'array'
       or pg_catalog.jsonb_array_length(p_payload->'countries') not between 1 and 10 then
      return private.f21_bad('countries');
    end if;
    for v_el in select e from pg_catalog.jsonb_array_elements(p_payload->'countries') e loop
      if pg_catalog.jsonb_typeof(v_el) <> 'string' or (v_el #>> '{}') !~ '^[A-Z]{2}$'
         or (v_el #>> '{}') = any (v_countries) then
        return private.f21_bad('countries');
      end if;
      v_countries := v_countries || (v_el #>> '{}');
    end loop;
  else
    if p_payload ? 'countries' and p_payload->'countries' <> 'null'::jsonb
       and (pg_catalog.jsonb_typeof(p_payload->'countries') <> 'array' or pg_catalog.jsonb_array_length(p_payload->'countries') <> 0) then
      return private.f21_bad('countries');
    end if;
    if pg_catalog.jsonb_typeof(p_payload->'interests') is distinct from 'array'
       or pg_catalog.jsonb_array_length(p_payload->'interests') not between 1 and 6 then
      return private.f21_bad('interests');
    end if;
    v_int := array[]::text[];
    for v_el in select e from pg_catalog.jsonb_array_elements(p_payload->'interests') e loop
      if pg_catalog.jsonb_typeof(v_el) <> 'string' or not ((v_el #>> '{}') = any (c_keys)) or (v_el #>> '{}') = any (v_int) then
        return private.f21_bad('interests');
      end if;
      v_int := v_int || (v_el #>> '{}');
    end loop;
    if p_payload ? 'max_flight' and p_payload->'max_flight' <> 'null'::jsonb then
      if pg_catalog.jsonb_typeof(p_payload->'max_flight') <> 'string' or (p_payload->>'max_flight') not in ('5', '8', 'any') then
        return private.f21_bad('max_flight');
      end if;
      v_flight := p_payload->>'max_flight';
    else
      v_flight := '5';
    end if;
    if p_payload ? 'pref_note' and p_payload->'pref_note' <> 'null'::jsonb then
      if pg_catalog.jsonb_typeof(p_payload->'pref_note') <> 'string' then return private.f21_bad('pref_note'); end if;
      v_pref := nullif(pg_catalog.btrim(p_payload->>'pref_note'), '');
      if pg_catalog.char_length(v_pref) > 100 or v_pref ~ '[[:cntrl:]]' then return private.f21_bad('pref_note'); end if;
    end if;
  end if;

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

  -- the queue counts requests that wait for the admin (a verified request without a destination does not)
  if (select pg_catalog.count(*) from private.trip_requests r
       where r.status = 'pending' and pg_catalog.cardinality(r.countries) > 0) >= 100
     or private.f21_mail_today() >= 50 then
    return private.f21_err('daily_limit');
  end if;

  delete from private.trip_requests r where r.email = v_email and r.status = 'unverified';
  insert into private.trip_requests (id, lang, name, email, countries, month, travellers, note, status, code_hash,
                                     code_expires_at, code_attempts, code_sent_at, resend_count, ip_hash,
                                     where_mode, interests, max_flight, pref_note)
  values (p_request, v_lang, v_name, v_email, v_countries, v_month, v_trav, v_note, 'unverified', p_code_hash,
          pg_catalog.now() + interval '10 minutes', 0, pg_catalog.now(), 0, p_ip,
          v_mode, v_int, v_flight, v_pref);
  insert into private.mail_log (kind, request_id) values ('code', p_request);
  update private.request_attempts a set ok = true, request_id = p_request
   where a.id = (select max(b.id) from private.request_attempts b where b.kind = 'start' and b.email_hash = p_email_hash);
  return pg_catalog.jsonb_build_object('request_id', p_request, 'sent_at', pg_catalog.now());
end;
$$;

-- ===========================================================================
-- 4. request_verify2 — new (request_verify stays for REQUEST_MODE='manual' with a known destination). Same code rules
--    as request_verify. A right code:
--      undecided, no destination yet → pending + session → {next:'suggest', left:3}                       (C2)
--      known + p_auto                → the approve transaction → {next:'ready', invite_id, mail, …}        (C1)
--      known + not p_auto            → pending, as F21 → {next:'pending'}
--    When the auto-approval is refused (rate_limited) the code is NOT consumed and nothing changes.
-- ===========================================================================
create or replace function public.request_verify2(p_request uuid, p_code_hash text, p_ip text, p_auto boolean,
                                                  p_token_hash text, p_session_hash text, p_draft text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r record;
  v_n int;
  v_out jsonb;
begin
  perform private.f23_cleanup();
  if p_request is null or p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$' or p_auto is null
     or p_session_hash is null or p_session_hash !~ '^[0-9a-f]{64}$' then
    return private.f21_err('invalid_request');
  end if;
  if p_ip is not null
     and private.f21_count('verify', null, p_ip, false, pg_catalog.now() - interval '1 hour') >= 20 then
    return private.f21_err('rate_limited');
  end if;
  select q.id, q.status, q.code_hash, q.code_expires_at, q.code_attempts, q.where_mode, q.countries into r
    from private.trip_requests q where q.id = p_request for update;
  if not found or r.status <> 'unverified' or r.code_hash is null then
    return private.f21_err('request_unknown');
  end if;
  if r.code_expires_at <= pg_catalog.now() then
    return private.f21_err('code_expired');
  end if;
  if r.code_hash = p_code_hash then
    if r.where_mode = 'undecided' and pg_catalog.cardinality(r.countries) = 0 then
      update private.trip_requests q
         set status = 'pending', verified_at = pg_catalog.now(), code_hash = null, code_expires_at = null,
             session_hash = p_session_hash
       where q.id = p_request;
      perform private.f21_log('verify', null, p_ip, p_request, true);
      return pg_catalog.jsonb_build_object('status', 'pending', 'next', 'suggest', 'request_id', p_request, 'left', 3);
    end if;
    if p_auto then
      v_out := private.f23_auto_approve(p_request, p_token_hash, p_draft);
      if v_out ? 'error' then return v_out; end if;
      perform private.f21_log('verify', null, p_ip, p_request, true);
      return v_out;
    end if;
    update private.trip_requests q
       set status = 'pending', verified_at = pg_catalog.now(), code_hash = null, code_expires_at = null
     where q.id = p_request;
    perform private.f21_log('verify', null, p_ip, p_request, true);
    return pg_catalog.jsonb_build_object('status', 'pending', 'next', 'pending', 'request_id', p_request);
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
-- 5. request_suggest_begin — called right BEFORE the AI call: checks the session (C5) and the limits (C7), counts the
--    call (p_count true), and returns the only data the prompt may get (C6: no name, no email). request_suggest_save stores the shown
--    countries afterwards (for the refresh exclusion). A call that begins counts even when the model fails.
-- ===========================================================================
create or replace function public.request_suggest_begin(p_request uuid, p_session_hash text, p_count boolean)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r private.trip_requests;
  v_used int;
begin
  if p_count is null then return private.f21_err('invalid_request'); end if;
  r := private.f23_session(p_request, p_session_hash);
  if r.id is null then return private.f21_err('request_unknown'); end if;
  select pg_catalog.count(*)::int into v_used from private.request_attempts a
   where a.kind = 'suggest' and a.request_id = p_request;
  if not p_count then   -- session check only (AI switched off / no key): nothing is counted, no limit applies
    return pg_catalog.jsonb_build_object('request_id', p_request, 'left', greatest(3 - v_used, 0));
  end if;
  if v_used >= 3 then return private.f21_err('suggest_limit'); end if;
  if private.f23_suggest_today() >= 30 then return private.f21_err('suggest_unavailable'); end if;
  perform private.f21_log('suggest', null, r.ip_hash, p_request, false);
  return pg_catalog.jsonb_build_object(
    'request_id', p_request, 'lang', r.lang, 'month', r.month, 'travellers', r.travellers,
    'interests', pg_catalog.to_jsonb(r.interests), 'max_flight', coalesce(r.max_flight, '5'), 'pref_note', r.pref_note,
    'shown', coalesce((select pg_catalog.jsonb_agg(c) from pg_catalog.jsonb_array_elements(r.suggestions) s,
                                                           pg_catalog.jsonb_array_elements(s) c), '[]'::jsonb),
    'left', 3 - (v_used + 1));
end;
$$;

create or replace function public.request_suggest_save(p_request uuid, p_session_hash text, p_countries text[])
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r private.trip_requests;
begin
  r := private.f23_session(p_request, p_session_hash);
  if r.id is null then return private.f21_err('request_unknown'); end if;
  if p_countries is null or pg_catalog.cardinality(p_countries) not between 1 and 3
     or pg_catalog.array_to_string(p_countries, ',') !~ '^[A-Z]{2}(,[A-Z]{2})*$' then
    return private.f21_err('invalid_request');
  end if;
  update private.trip_requests q set suggestions = q.suggestions || pg_catalog.jsonb_build_array(pg_catalog.to_jsonb(p_countries))
   where q.id = p_request;
  update private.request_attempts a set ok = true
   where a.id = (select max(b.id) from private.request_attempts b where b.kind = 'suggest' and b.request_id = p_request);
  return pg_catalog.jsonb_build_object('ok', true, 'left',
    3 - (select pg_catalog.count(*)::int from private.request_attempts a where a.kind = 'suggest' and a.request_id = p_request));
end;
$$;

-- ===========================================================================
-- 6. request_choose — the picked country (a suggestion, or any country from the fallback picker, C8). The Edge Function
--    checks the code against countries.json. p_auto → the approve transaction; otherwise the request waits for the
--    admin as in F21, now with its destination.
-- ===========================================================================
create or replace function public.request_choose(p_request uuid, p_session_hash text, p_country text, p_auto boolean,
                                                 p_token_hash text, p_draft text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  r private.trip_requests;
  v_out jsonb;
begin
  if p_auto is null or p_country is null or p_country !~ '^[A-Z]{2}$' then
    return private.f21_err('invalid_request');
  end if;
  r := private.f23_session(p_request, p_session_hash);
  if r.id is null then return private.f21_err('request_unknown'); end if;
  if p_auto and private.f21_count('auto', private.f23_email_hash(r.email), null, true, private.f21_day_start()) >= 1 then
    return private.f21_err('rate_limited');   -- before any change (criterion 9)
  end if;
  update private.trip_requests q set countries = array[p_country] where q.id = p_request;
  if p_auto then
    v_out := private.f23_auto_approve(p_request, p_token_hash, p_draft);
    if v_out ? 'error' then
      update private.trip_requests q set countries = array[]::text[] where q.id = p_request;
    end if;
    return v_out;
  end if;
  update private.trip_requests q set session_hash = null where q.id = p_request;
  return pg_catalog.jsonb_build_object('status', 'pending', 'next', 'pending', 'request_id', p_request);
end;
$$;

-- the invite email of an auto-approval was NOT sent: its cap row is removed (the invite itself stays valid, C4)
create or replace function public.request_invite_mail_failed(p_request uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  if p_request is null then return private.f21_err('invalid_request'); end if;
  delete from private.mail_log l
   where l.id = (select max(m.id) from private.mail_log m where m.request_id = p_request and m.kind = 'invite');
  return pg_catalog.jsonb_build_object('ok', true);
end;
$$;

-- F21 D16: the draft trip name of an automatic invite. The Edge Function builds it from the countries and month that
-- the approve transaction returned (the database has no country names) and stores it here, before the invite is used.
create or replace function public.request_invite_draft(p_request uuid, p_invite uuid, p_draft text)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_draft text := nullif(pg_catalog.btrim(coalesce(p_draft, '')), '');
  v_n int;
begin
  if p_request is null or p_invite is null or v_draft is null
     or pg_catalog.char_length(v_draft) > 80 or v_draft ~ '[[:cntrl:]]' then
    return private.f21_err('invalid_request');
  end if;
  update public.manager_invites i set draft_name = v_draft
   where i.id = p_invite and i.request_id = p_request and i.used_at is null and i.revoked_at is null
     and exists (select 1 from private.trip_requests q where q.id = p_request and q.status = 'auto_approved' and q.invite_id = p_invite);
  get diagnostics v_n = row_count;
  return pg_catalog.jsonb_build_object('ok', v_n = 1);
end;
$$;

-- ===========================================================================
-- 7. admin_trip_requests — REPLACED. CHANGE 2026-11-13 F23-DB-03: what changed from 0016_f21.sql: (a) `requests` lists
--    only pending requests that HAVE a destination (a request still on the suggestions screen needs no action);
--    (b) + `auto`: the auto-approved requests, newest first, each with its invite (C11: history "נפתח אוטומטית" + the
--    F03 invite state; revoke = the existing invite-manager action); (c) + `ai_today`, `ai_cap` (C7 counter).
--    `cap`, `mail_today` and every key of a `requests` item are unchanged.
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
  v_auto jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'not_platform_admin' using errcode = '42501';
  end if;
  perform private.f23_cleanup();
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
   where q.status = 'pending' and pg_catalog.cardinality(q.countries) > 0;

  select coalesce(pg_catalog.jsonb_agg(x.j order by x.decided_at desc, x.id), '[]'::jsonb) into v_auto
    from (select q.id, q.decided_at, pg_catalog.jsonb_build_object(
                   'id', q.id, 'lang', q.lang, 'name', q.name, 'email', q.email,
                   'countries', pg_catalog.to_jsonb(q.countries), 'month', q.month, 'travellers', q.travellers,
                   'note', q.note, 'where_mode', q.where_mode, 'decided_at', q.decided_at,
                   'invite', (select pg_catalog.jsonb_build_object('id', i.id, 'draft_name', i.draft_name,
                                       'expires_at', i.expires_at, 'used_at', i.used_at, 'revoked_at', i.revoked_at,
                                       'opened_at', i.opened_at, 'trip_id', i.trip_id)
                                from public.manager_invites i where i.id = q.invite_id)) as j
            from private.trip_requests q
           where q.status = 'auto_approved'
           order by q.decided_at desc, q.id
           limit 100) x;

  return pg_catalog.jsonb_build_object('cap', 50, 'mail_today', private.f21_mail_today(), 'requests', v_list,
                                       'auto', v_auto, 'ai_today', private.f23_suggest_today(), 'ai_cap', 30);
end;
$$;

-- ===========================================================================
-- 8. Grants: every new function service-role only (admin_trip_requests keeps authenticated + service_role)
-- ===========================================================================
revoke all on function private.f23_email_hash(text)                                          from public, anon, authenticated;
revoke all on function private.f23_suggest_today()                                           from public, anon, authenticated;
revoke all on function private.f23_cleanup()                                                 from public, anon, authenticated;
revoke all on function private.f23_auto_approve(uuid, text, text)                            from public, anon, authenticated;
revoke all on function private.f23_session(uuid, text)                                       from public, anon, authenticated;
revoke all on function public.request_start(uuid, jsonb, text, text, text)                   from public, anon, authenticated;
revoke all on function public.request_verify2(uuid, text, text, boolean, text, text, text)   from public, anon, authenticated;
revoke all on function public.request_suggest_begin(uuid, text, boolean)                           from public, anon, authenticated;
revoke all on function public.request_suggest_save(uuid, text, text[])                       from public, anon, authenticated;
revoke all on function public.request_choose(uuid, text, text, boolean, text, text)          from public, anon, authenticated;
revoke all on function public.request_invite_mail_failed(uuid)                               from public, anon, authenticated;
revoke all on function public.request_invite_draft(uuid, uuid, text)                         from public, anon, authenticated;
revoke all on function public.admin_trip_requests()                                          from public, anon;

grant execute on function private.f23_email_hash(text)                                        to service_role;
grant execute on function private.f23_suggest_today()                                         to service_role;
grant execute on function private.f23_cleanup()                                               to service_role;
grant execute on function private.f23_auto_approve(uuid, text, text)                          to service_role;
grant execute on function private.f23_session(uuid, text)                                     to service_role;
grant execute on function public.request_start(uuid, jsonb, text, text, text)                 to service_role;
grant execute on function public.request_verify2(uuid, text, text, boolean, text, text, text) to service_role;
grant execute on function public.request_suggest_begin(uuid, text, boolean)                         to service_role;
grant execute on function public.request_suggest_save(uuid, text, text[])                     to service_role;
grant execute on function public.request_choose(uuid, text, text, boolean, text, text)        to service_role;
grant execute on function public.request_invite_mail_failed(uuid)                             to service_role;
grant execute on function public.request_invite_draft(uuid, uuid, text)                       to service_role;
grant execute on function public.admin_trip_requests()                                        to authenticated, service_role;
