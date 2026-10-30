"""Lonely Planner F21 QA · local PostgreSQL test of migration 0016_f21.sql (+ 0017 harness) · version 1.0.0
CHANGE 2026-10-30 F21-QA-01: new file (no previous version).

Black-box test of docs/F21_spec.md §2 (data), §4 (limits), D5/C5 (cleanup), D12 (approve replaces an active invite), the undo
path, grants/RLS and criterion 17, on a scratch LOCAL database. The SQL bodies of 0016/0017 were NOT read: the functions
are called with the signatures of spec §2.6–§2.8 and the results / table contents are checked against the spec.
Never touches Supabase or the network.

Steps
  1. scratch DB `pt_f21_qa`, scripts/dev/supabase_local_shim.sql + 0001…0015 (the alpha.7.2 schema)
  2. fixture: one F03 invite (no request) → snapshot S0 (public tables, policies, table grants, find_invite_for_email output)
  3. 0016_f21.sql, 0017_qa_f21_harness.sql → snapshot S1; S0 vs S1 (criterion 17 "no new policies or grants on existing
     tables"; §2.4 "existing rows = he"; §2.8 "unchanged output otherwise")
  4. qa.f01…f06_run() + qa.f21_run() (each scenario rolled back by the harness itself)
  5. own scenarios DB-xx (below), each in BEGIN … ROLLBACK; then "nothing left behind"

usage: python3 tests/f21/db_test.py [--keep] [--regression] [--setup-only]
  --setup-only   only build the database (0001…0017) and keep it (used by tests/f21/integration_test.ts, F21_QA_DB)
  --keep         keep the scratch database (for poking around)
  --regression   output for tests/run_all.sh job db21 (same line format as tests/f06/db_check.py)
Exit 0 only when every row passes. Time is simulated by moving timestamps (created_at / at / code_* / decided_at) back.
Superseded qa.f06_run() rows (F21 §2 adds three private tables + private.f21_* helpers on purpose): #910, #911 — they
run and are reported, and DB-03 below asserts the new exact contents of schema private instead.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations"
SHIM = ROOT / "scripts" / "dev" / "supabase_local_shim.sql"
DB = os.environ.get("F21_QA_DB", "pt_f21_qa")
BEFORE = ["0001_core.sql", "0002_qa_f01_harness.sql", "0003_qa_f01_fix_case12.sql", "0004_qa_search_path.sql", "0006_f02.sql",
          "0007_qa_f02_harness.sql", "0008_f03.sql", "0009_qa_f03_harness.sql", "0010_f04.sql", "0011_qa_f04_harness.sql",
          "0012_f05.sql", "0013_qa_f05_harness.sql", "0014_f06.sql", "0015_qa_f06_harness.sql"]
F21 = ["0016_f21.sql", "0017_qa_f21_harness.sql"]
SUPERSEDED = {("qa.f05_run", "100"): "F06 D2 (removed identities may ask again; docs/qa/F06_QA.md §1)",
              ("qa.f05_run", "101"): "F06 D2",
              ("qa.f06_run", "910"): "F21 §2: private.f21_* helpers (DB-03.private_fn)",
              ("qa.f06_run", "911"): "F21 §2: private gains trip_requests, request_attempts, mail_log (DB-03)"}
F01_TABLES = ["manager_invites", "platform_admins", "relink_tokens", "trip_countries", "trip_currencies", "trip_join_codes",
              "trip_kv", "trip_members", "trips"]
SR_FUNCS = ["request_start(uuid,jsonb,text,text,text)", "request_verify(uuid,text,text)", "request_resend(uuid,text)",
            "request_approve(uuid,uuid,text,text,text)", "request_approve_undo(uuid,uuid,uuid)", "request_reject(uuid,uuid,boolean)"]

TMP = Path(tempfile.mkdtemp(prefix="f21qa_"))
os.chmod(TMP, 0o755)


def psql(*a, db=DB):
    args = ["sudo", "-u", "postgres", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"]
    if db:
        args += ["-d", db]
    return subprocess.run(args + list(a), capture_output=True, text=True, cwd="/tmp")


def sql_rows(sql):
    """Run sql (may contain several statements); return the rows of every SELECT as lists split on '\x1f'."""
    f = TMP / ("q_%s.sql" % uuid.uuid4().hex[:8])
    f.write_text(sql, encoding="utf-8")
    r = psql("-A", "-t", "-F", "\x1f", "-f", str(f))
    f.unlink()
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-1500:])
    return [ln.split("\x1f") for ln in r.stdout.splitlines() if ln.strip()]


def one(sql):
    rows = sql_rows(sql)
    return rows[-1][0] if rows else None


def jget(sql):
    v = one(sql)
    return json.loads(v) if v not in (None, "") else None


# ---------------------------------------------------------------------------------------------------------------------
# SQL building blocks (executed as postgres unless a role is set)
# ---------------------------------------------------------------------------------------------------------------------
H = "encode(sha256(convert_to(%s,'UTF8')),'hex')"      # sha256 hex of a text expression
JM = "(date_trunc('day', now() at time zone 'Asia/Jerusalem') at time zone 'Asia/Jerusalem')"   # Jerusalem midnight today
HELPERS = r"""
create schema if not exists qa21;
grant usage on schema qa21 to public;
-- run a statement as the CURRENT role; returns the JSON result, or ERR:<sqlstate>:<message>
create or replace function qa21.try(p_sql text) returns text language plpgsql as $$
declare r text;
begin
  execute p_sql into r;
  return coalesce(r, 'NULL');
exception when others then
  return 'ERR:' || sqlstate || ':' || sqlerrm;
end $$;
grant execute on function qa21.try(text) to public;
create or replace function qa21.payload(p_email text, p_lang text default 'he', p_countries text[] default array['PT'],
  p_month text default null, p_travellers int default 2, p_note text default null, p_name text default 'דנה') returns jsonb
language sql as $$ select jsonb_build_object('lang',p_lang,'name',p_name,'email',p_email,'countries',to_jsonb(p_countries),
  'month',p_month,'travellers',p_travellers,'note',p_note) $$;
grant execute on function qa21.payload(text,text,text[],text,int,text,text) to public;
-- service-role call of request_start with code '111111'; returns the result jsonb
create or replace function qa21.start(p_id uuid, p_payload jsonb, p_ip text default 'ip-1', p_code text default '111111') returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role;
  r := public.request_start(p_id, p_payload, encode(sha256(convert_to(lower(p_payload->>'email'),'UTF8')),'hex'),
        encode(sha256(convert_to(p_ip,'UTF8')),'hex'), encode(sha256(convert_to(p_id::text || p_code,'UTF8')),'hex'));
  reset role; return r; end $$;
create or replace function qa21.verify(p_id uuid, p_code text, p_ip text default 'ip-1') returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role;
  r := public.request_verify(p_id, encode(sha256(convert_to(p_id::text || p_code,'UTF8')),'hex'), encode(sha256(convert_to(p_ip,'UTF8')),'hex'));
  reset role; return r; end $$;
create or replace function qa21.resend(p_id uuid, p_code text) returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role;
  r := public.request_resend(p_id, encode(sha256(convert_to(p_id::text || p_code,'UTF8')),'hex'));
  reset role; return r; end $$;
create or replace function qa21.approve(p_admin uuid, p_id uuid, p_tok text, p_draft text) returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role;
  r := public.request_approve(p_admin, p_id, encode(sha256(convert_to(p_tok,'UTF8')),'hex'), p_draft, 'אור');
  reset role; return r; end $$;
create or replace function qa21.undo(p_inv uuid, p_rev uuid, p_id uuid) returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role; r := public.request_approve_undo(p_inv, p_rev, p_id); reset role; return r; end $$;
create or replace function qa21.reject(p_admin uuid, p_id uuid, p_mail boolean) returns jsonb
language plpgsql as $$ declare r jsonb; begin
  set local role service_role; r := public.request_reject(p_admin, p_id, p_mail); reset role; return r; end $$;
-- a verified pending request (start + verify), verified p_ago ago
create or replace function qa21.pending(p_email text, p_lang text default 'he', p_ago interval default '1 hour',
  p_countries text[] default array['PT','ES'], p_month text default '2027-04-01', p_name text default 'דנה', p_note text default null)
returns uuid language plpgsql as $$ declare v_id uuid := gen_random_uuid(); r jsonb; begin
  r := qa21.start(v_id, qa21.payload(p_email, p_lang, p_countries, p_month, 4, p_note, p_name), 'ip-' || p_email);
  if r ? 'error' then raise exception 'qa21.pending start: %', r; end if;
  r := qa21.verify(v_id, '111111', 'ip-' || p_email);
  if coalesce(r->>'error','') <> '' then raise exception 'qa21.pending verify: %', r; end if;
  update private.trip_requests set verified_at = now() - p_ago where trip_requests.id = v_id;
  -- the test fixtures' own attempts / mails must not eat the limits under test
  delete from private.request_attempts; delete from private.mail_log;
  return v_id; end $$;
create or replace function qa21.user(p_email text, p_admin boolean default false) returns uuid language plpgsql as $$
declare u uuid := gen_random_uuid(); begin
  insert into auth.users(id, aud, role, email, is_anonymous) values (u, 'authenticated', 'authenticated', p_email, false);
  if p_admin then insert into public.platform_admins(user_id) values (u); end if;
  return u; end $$;
create or replace function qa21.manager(p_uid uuid, p_trip text, p_role text default 'manager', p_status text default 'active')
returns uuid language plpgsql as $$ declare t uuid := gen_random_uuid(); begin
  insert into public.trips(id, name) values (t, p_trip);
  insert into public.trip_members(trip_id, user_id, display_name, role, status) values (t, p_uid, 'דנה', p_role, p_status);
  return t; end $$;
create or replace function qa21.invite(p_email text, p_draft text default 'טיול ישן', p_sent_ago interval default '2 days',
  p_exp interval default '5 days') returns uuid language plpgsql as $$ declare i uuid := gen_random_uuid(); begin
  insert into public.manager_invites(id, email, token_hash, draft_name, expires_at, last_sent_at, created_at, inviter_name)
  values (i, p_email, encode(sha256(convert_to(i::text,'UTF8')),'hex'), p_draft, now() + p_exp, now() - p_sent_ago, now() - p_sent_ago, 'אור');
  return i; end $$;
-- admin_trip_requests() as an authenticated user (claims), returns the JSON or ERR:…
create or replace function qa21.admin_list(p_uid uuid) returns text language plpgsql as $$ declare r text; begin
  perform set_config('request.jwt.claims', json_build_object('sub', p_uid, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
  set local role authenticated;
  r := qa21.try('select public.admin_trip_requests()::text');
  reset role; return r; end $$;
create or replace function qa21.mails(p_n int, p_kind text default 'code', p_at timestamptz default now()) returns void
language sql as $$ insert into private.mail_log(kind, at) select p_kind, p_at from generate_series(1, p_n) $$;
"""

RESULTS = []   # (id, criteria, ok, desc, detail)


def rec(tid, crit, ok, desc, detail=""):
    RESULTS.append((tid, crit, bool(ok), desc, detail))


def scenario(tid, crit, desc):
    """Decorator: body(sql) → runs inside BEGIN … ROLLBACK; returns (ok, detail)."""
    def deco(fn):
        def run():
            try:
                ok, detail = fn()
            except Exception as e:   # noqa: BLE001
                ok, detail = False, "EXCEPTION " + str(e)[:900]
            rec(tid, crit, ok, desc, detail)
        SCENARIOS.append(run)
        return fn
    return deco


SCENARIOS = []


def tx(body):
    """BEGIN; body; ROLLBACK — returns the rows of every select in body."""
    return sql_rows("begin;\n" + body + "\nrollback;\n")


def kv(body):
    """tx() where body selects pairs ('key', value) → dict."""
    out = {}
    for r in tx(body):
        if len(r) >= 2:
            out[r[0]] = r[1]
    return out


def J(s):
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return s


def err(v):
    v = J(v)
    if isinstance(v, dict):
        return v.get("error")
    return None


# =====================================================================================================================
# Catalog snapshots
# =====================================================================================================================
SNAP_SQL = r"""
select 'tables', string_agg(c.relname, ',' order by c.relname) from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind in ('r','p','v','m');
select 'policies', coalesce(string_agg(schemaname||'.'||tablename||':'||policyname||':'||cmd||':'||array_to_string(roles,'+')||':'||coalesce(qual,'')||':'||coalesce(with_check,''), E'\n' order by tablename, policyname), '')
  from pg_policies where schemaname in ('public');
select 'tgrants', coalesce(string_agg(table_schema||'.'||table_name||':'||grantee||':'||privilege_type, ',' order by table_schema, table_name, grantee, privilege_type), '')
  from information_schema.role_table_grants where table_schema = 'public' and grantee in ('anon','authenticated','service_role','PUBLIC');
select 'cgrants', coalesce(string_agg(table_name||'.'||column_name||':'||grantee||':'||privilege_type, ',' order by table_name, column_name, grantee, privilege_type), '')
  from information_schema.column_privileges where table_schema = 'public' and grantee in ('anon','authenticated');
select 'rls', string_agg(c.relname||':'||c.relrowsecurity, ',' order by c.relname) from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r';
select 'privfn', string_agg(p.proname, ',' order by p.proname) from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'private';
select 'find', public.find_invite_for_email('legacy@example.com')::text;
select 'mi_cols', string_agg(column_name||':'||data_type||':'||is_nullable||':'||coalesce(column_default,''), ',' order by ordinal_position)
  from information_schema.columns where table_schema = 'public' and table_name = 'manager_invites';
"""


def snapshot():
    return {r[0]: (r[1] if len(r) > 1 else "") for r in sql_rows(SNAP_SQL)}


# =====================================================================================================================
# Scenarios
# =====================================================================================================================
S0, S1 = {}, {}


def static_checks():
    # ---- DB-01 tables + columns (§2.1–§2.3)
    want = {
        "trip_requests": ["id", "lang", "name", "email", "countries", "month", "travellers", "note", "status", "code_hash",
                          "code_expires_at", "code_attempts", "code_sent_at", "resend_count", "ip_hash", "verified_at",
                          "decided_at", "decided_by", "reject_mailed", "invite_id", "created_at"],
        "request_attempts": ["id", "kind", "email_hash", "ip_hash", "request_id", "ok", "at"],
        "mail_log": ["id", "kind", "at"],
    }
    for t, cols in want.items():
        have = [r[0] for r in sql_rows("select column_name from information_schema.columns where table_schema='private' "
                                       "and table_name='%s' order by ordinal_position" % t)]
        missing = [c for c in cols if c not in have]
        extra = [c for c in have if c not in cols]
        rec("DB-01." + t, "17", not missing, "§2.1–3 private.%s has the spec columns" % t,
            "missing %s; extra (not in spec, informational) %s" % (missing, extra))
    types = dict(sql_rows("select column_name, data_type||':'||is_nullable||':'||coalesce(column_default,'') from information_schema.columns "
                          "where table_schema='private' and table_name='trip_requests'"))
    exp = {"id": "uuid:NO:gen_random_uuid()", "countries": "ARRAY:NO:", "month": "date:YES:", "travellers": "smallint:NO:",
           "code_attempts": "smallint:NO:0", "resend_count": "smallint:NO:0", "created_at": "timestamp with time zone:NO:now()",
           "decided_by": "uuid:YES:", "invite_id": "uuid:YES:", "reject_mailed": "boolean:YES:"}
    bad = {k: types.get(k) for k, v in exp.items() if types.get(k) != v}
    rec("DB-01.types", "17", not bad, "§2.1 column types / defaults of trip_requests", "differs: %s" % bad)
    idx = [r[0] for r in sql_rows("select pg_get_indexdef(i.indexrelid) from pg_index i join pg_class c on c.oid=i.indrelid "
                                  "join pg_namespace n on n.oid=c.relnamespace where n.nspname='private' and c.relname in "
                                  "('trip_requests','request_attempts','mail_log')")]
    need = ["(status, verified_at)", "(email, created_at)", "(kind, email_hash, at)", "(kind, ip_hash, at)", "mail_log USING btree (at)"]
    miss = [n for n in need if not any(n in i for i in idx)]
    rec("DB-01.indexes", "17", not miss, "§2.1–3 indexes", "missing %s in %s" % (miss, idx))
    fks = [r[0] for r in sql_rows("select conrelid::regclass||':'||pg_get_constraintdef(oid) from pg_constraint where contype='f' and "
                                  "(conrelid='private.trip_requests'::regclass or (conrelid='public.manager_invites'::regclass and "
                                  "pg_get_constraintdef(oid) like '%trip_requests%'))")]
    ok = any("invite_id" in f and "manager_invites(id)" in f and "ON DELETE SET NULL" in f for f in fks) and \
        any("request_id" in f and "trip_requests(id)" in f and "ON DELETE SET NULL" in f for f in fks)
    rec("DB-01.fks", "17", ok, "§2.1/§2.4 invite_id → manager_invites ON DELETE SET NULL; request_id → trip_requests ON DELETE SET NULL", fks)

    # ---- DB-02 RLS on, no policies on the 3 tables; anon/authenticated cannot read/write (criterion 17)
    rl = dict(sql_rows("select c.relname, c.relrowsecurity::text||'/'||(select count(*) from pg_policies p where p.schemaname='private' "
                       "and p.tablename=c.relname) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='private' "
                       "and c.relname in ('trip_requests','request_attempts','mail_log')"))
    rec("DB-02.rls", "17", rl == {"trip_requests": "true/0", "request_attempts": "true/0", "mail_log": "true/0"},
        "§2.1–3 RLS on, no policies", rl)
    probes = []
    for role in ("anon", "authenticated"):
        for t in ("trip_requests", "request_attempts", "mail_log"):
            for stmt in ("select count(*)::text from private.%s" % t,
                         "insert into private.%s default values returning 1::text" % t,
                         "update private.%s set id = id returning 1::text" % t,
                         "delete from private.%s returning 1::text" % t):
                v = one("begin; set local role %s; select qa21.try($q$%s$q$); rollback;" % (role, stmt))
                probes.append((role, stmt.split()[0], t, v))
    leaks = [p for p in probes if not str(p[3]).startswith("ERR:42501")]
    rec("DB-02.access", "17", not leaks, "criterion 17: the 3 tables unreadable / unwritable by anon and authenticated (42501)",
        "not refused: %s" % leaks[:6])

    # ---- DB-03 schema private exact contents (supersedes qa.f06_run #911) + public keeps the 9 F01 tables
    pt = [r[0] for r in sql_rows("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='private' "
                                 "and c.relkind in ('r','p','v','m') order by 1")]
    rec("DB-03.private", "17", pt == ["join_attempts", "mail_log", "request_attempts", "transfer_codes", "trip_requests"],
        "§2: schema private = F05 tables + the three F21 tables (updates qa.f06_run #911)", pt)
    new_fn = sorted(set(S1.get("privfn", "").split(",")) - set(S0.get("privfn", "").split(",")))
    gone_fn = sorted(set(S0.get("privfn", "").split(",")) - set(S1.get("privfn", "").split(",")))
    rec("DB-03.private_fn", "17", new_fn and all(f.startswith("f21_") for f in new_fn) and not gone_fn and "f21_cleanup" in new_fn and "f21_mail_today" in new_fn,
        "§2.3/§2.5: new private helpers are f21_* (incl. f21_cleanup, f21_mail_today), none removed (updates qa.f06_run #910)",
        "new %s; removed %s" % (new_fn, gone_fn))
    pub = S1.get("tables", "").split(",")
    rec("DB-03.public", "17", pub == F01_TABLES, "§2.9: public keeps exactly the 9 F01 tables", pub)

    # ---- DB-04 manager_invites additions (§2.4) and S0 vs S1 (criterion 17)
    cols = dict((c.split(":")[0], c) for c in S1.get("mi_cols", "").split(","))
    ok = cols.get("request_id", "").startswith("request_id:uuid:YES") and cols.get("lang", "") == "lang:text:NO:'he'::text"
    rec("DB-04.cols", "17", ok, "§2.4 manager_invites.request_id uuid null, lang text not null default 'he'",
        {k: cols.get(k) for k in ("request_id", "lang")})
    old_cols = S0.get("mi_cols", "").split(",")
    rec("DB-04.other_cols", "17", [c for c in S1.get("mi_cols", "").split(",") if not c.startswith(("request_id:", "lang:"))] == old_cols,
        "§2.4 no other change to manager_invites columns", "")
    chk = one("select qa21.try($q$insert into public.manager_invites(email, token_hash, expires_at, lang) values ('x@e.co', repeat('d',64), now()+interval '1 day', 'fr') returning 1::text$q$)")
    rec("DB-04.lang_check", "17", str(chk).startswith("ERR:23514"), "§2.4 lang check in ('he','en')", chk)
    leg = one("select lang from public.manager_invites where email='legacy@example.com'")
    rec("DB-04.existing_he", "17", leg == "he", "§2.4 existing rows = 'he'", leg)
    for k, crit, desc in (("policies", "17", "no new / changed policies on public tables"),
                          ("tgrants", "17", "no new table grants on public tables (anon/authenticated/service_role)"),
                          ("cgrants", "17", "no new column grants on public tables"),
                          ("rls", "17", "RLS flags of public tables unchanged")):
        rec("DB-04." + k, crit, S0.get(k) == S1.get(k), "criterion 17: " + desc,
            "" if S0.get(k) == S1.get(k) else "before:\n%s\nafter:\n%s" % (S0.get(k), S1.get(k)))
    rec("DB-04.find_unchanged", "16", J(S0.get("find")) == J(S1.get("find")),
        "§2.8 find_invite_for_email unchanged for an invite without request_id", "before %s / after %s" % (S0.get("find"), S1.get("find")))

    # ---- DB-05 function grants and attributes (§2.6, §2.7, §2.9)
    rows = sql_rows("select p.oid::regprocedure::text, p.prosecdef::text, coalesce(array_to_string(p.proconfig,','),''), "
                    "has_function_privilege('anon', p.oid, 'EXECUTE')::text, has_function_privilege('authenticated', p.oid, 'EXECUTE')::text, "
                    "has_function_privilege('service_role', p.oid, 'EXECUTE')::text, "
                    "(select count(*) from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a where a.grantee = 0)::text "
                    "from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and "
                    "p.proname in ('request_start','request_verify','request_resend','request_approve','request_approve_undo','request_reject','admin_trip_requests','find_invite_for_email')")
    got = {r[0]: r[1:] for r in rows}
    for f in SR_FUNCS + ["admin_trip_requests()", "find_invite_for_email(text)"]:
        g = got.get(f)
        if g is None:
            rec("DB-05." + f.split("(")[0], "17", False, "§2.6 %s exists with the spec signature" % f, "not found; have %s" % sorted(got))
            continue
        sd, cfg, anon, auth, sr, pub = g
        want_auth = "true" if f.startswith("admin_trip_requests") else "false"
        ok = sd == "true" and cfg in ('search_path=""', "search_path=''") and anon == "false" and auth == want_auth and sr == "true" and pub == "0"
        rec("DB-05." + f.split("(")[0], "17", ok, "§2.6/2.9 %s: security definer, search_path='', exec anon=false authenticated=%s service_role=true, not PUBLIC" % (f, want_auth),
            "secdef=%s config=%s anon=%s auth=%s sr=%s public=%s" % (sd, cfg, anon, auth, sr, pub))
    extra = [r[0] for r in sql_rows("select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' "
                                    "and (has_function_privilege('anon', p.oid, 'EXECUTE') or has_function_privilege('authenticated', p.oid, 'EXECUTE')) "
                                    "and (p.proname like 'request%' or p.proname like '%f21%')")]
    rec("DB-05.no_public_request_fn", "17", not extra, "§2.9 no request_* / f21 function executable by anon/authenticated", extra)
    sr_more = [r[0] for r in sql_rows("select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' "
                                      "and p.proname like 'request%'")]
    unspec = [f for f in sr_more if f not in SR_FUNCS]
    rec("DB-05.unspecified_fn", "17", True, "informational: public request_* functions not named by the spec", unspec)

    # ---- DB-06 constraints of trip_requests (§2.1) — direct inserts as postgres
    base = dict(lang="'he'", name="'דנה'", email="'a@e.co'", countries="array['PT']", month="null", travellers="2", note="null", status="'pending'")
    bads = {"lang fr": {"lang": "'fr'"}, "name empty": {"name": "''"}, "name 41": {"name": "repeat('א',41)"},
            "email upper": {"email": "'A@e.co'"}, "countries 0": {"countries": "array[]::text[]"},
            "countries 11": {"countries": "array['PT','ES','FR','IT','DE','GR','TH','VN','JP','US','GB']"},
            "country lower": {"countries": "array['pt']"}, "country 3 letters": {"countries": "array['PRT']"},
            "month day 2": {"month": "'2027-04-02'"}, "travellers 0": {"travellers": "0"}, "travellers 31": {"travellers": "31"},
            "note 201": {"note": "repeat('n',201)"}, "status x": {"status": "'done'"}}
    fails = []
    for k, over in list(bads.items()) + [("valid", {})]:
        v = dict(base, **over)
        q = "insert into private.trip_requests(lang,name,email,countries,month,travellers,note,status) values (%s) returning 1::text" % ",".join(
            v[c] for c in ("lang", "name", "email", "countries", "month", "travellers", "note", "status"))
        r = one("begin; select qa21.try($q$%s$q$); rollback;" % q)
        refused = str(r).startswith("ERR:23514") or str(r).startswith("ERR:23502")
        if (k == "valid") == refused:
            fails.append((k, r))
    rec("DB-06.checks", "4", not fails, "§2.1 check constraints (name 1–40, lower email, 1–10 ^[A-Z]{2}$ countries, day-1 month, travellers 1–30, note ≤200, status, lang)", fails)


@scenario("DB-10", "5", "request_start valid → {request_id}, row unverified with the code hash, 10-min expiry, one 'code' mail, start attempt logged")
def _():
    d = kv("""select 'r', qa21.start('10000000-0000-4000-8000-000000000001', qa21.payload('Dana@Example.com '))::text;
      select 'row', row_to_json(t)::text from private.trip_requests t;
      select 'mails', count(*)::text from private.mail_log where kind='code';
      select 'att', count(*)::text from private.request_attempts where kind='start';
      select 'exp', extract(epoch from (code_expires_at - now()))::int::text from private.trip_requests;""")
    r, row = J(d.get("r")), J(d.get("row")) or {}
    P = []
    if not isinstance(r, dict) or r.get("request_id") != "10000000-0000-4000-8000-000000000001":
        P.append("result %r" % r)
    if row.get("status") != "unverified":
        P.append("status %r" % row.get("status"))
    if row.get("code_hash") in (None, ""):
        P.append("no code hash")
    if d.get("exp") not in ("600", "599", "601"):
        P.append("code_expires_at - now = %s s (want 600)" % d.get("exp"))
    if d.get("mails") != "1":
        P.append("code mails %s" % d.get("mails"))
    if d.get("att") != "1":
        P.append("start attempts %s" % d.get("att"))
    return not P, "; ".join(P) + " | row email=%r" % row.get("email")


@scenario("DB-11", "4", "request_start refuses invalid payloads with a RETURNED {error} (no raise), no row, no mail")
def _():
    cases = {"name41": "qa21.payload('a@e.co', p_name => repeat('א',41))", "name0": "qa21.payload('a@e.co', p_name => '   ')",
             "email": "qa21.payload('not-an-email')", "c0": "qa21.payload('a@e.co', p_countries => array[]::text[])",
             "c11": "qa21.payload('a@e.co', p_countries => array['PT','ES','FR','IT','DE','GR','TH','VN','JP','US','GB'])",
             "cbad": "qa21.payload('a@e.co', p_countries => array['XX1'])",
             "trav0": "qa21.payload('a@e.co', p_travellers => 0)", "trav31": "qa21.payload('a@e.co', p_travellers => 31)",
             "note201": "qa21.payload('a@e.co', p_note => repeat('n',201))", "lang": "qa21.payload('a@e.co', p_lang => 'fr')",
             "month_past": "qa21.payload('a@e.co', p_month => to_char(now() - interval '2 months','YYYY-MM-01'))",
             "month_19": "qa21.payload('a@e.co', p_month => to_char(now() + interval '19 months','YYYY-MM-01'))",
             "month_day2": "qa21.payload('a@e.co', p_month => to_char(now() + interval '2 months','YYYY-MM-02'))"}
    bad = []
    for k, p in cases.items():
        d = kv("select 'r', qa21.try($q$select qa21.start(gen_random_uuid(), %s)::text$q$); select 'n', count(*)::text from private.trip_requests;"
               " select 'm', count(*)::text from private.mail_log;" % p)
        r = d.get("r", "")
        if r.startswith("ERR:") or err(r) != "invalid_request" or d.get("n") != "0" or d.get("m") != "0":
            bad.append("%s → %s rows=%s mails=%s" % (k, r[:160], d.get("n"), d.get("m")))
    ok18 = kv("select 'r', qa21.start(gen_random_uuid(), qa21.payload('a@e.co', p_month => to_char(now() at time zone 'Asia/Jerusalem' + interval '17 months','YYYY-MM-01')))::text;"
              "select 'r0', qa21.start(gen_random_uuid(), qa21.payload('b@e.co', p_month => to_char(now() at time zone 'Asia/Jerusalem','YYYY-MM-01')))::text;")
    if err(ok18.get("r")) or err(ok18.get("r0")):
        bad.append("current month / +17 months refused: %s %s" % (ok18.get("r"), ok18.get("r0")))
    return not bad, "; ".join(bad)


@scenario("DB-12", "6", "request_start deletes earlier UNVERIFIED rows of the same email; a pending row of that email stays")
def _():
    d = kv("""select 'p', qa21.pending('same@e.co')::text;
      select 'a', qa21.start('12000000-0000-4000-8000-00000000000a', qa21.payload('same@e.co'))::text;
      select 'b', qa21.start('12000000-0000-4000-8000-00000000000b', qa21.payload('same@e.co'))::text;
      select 'rows', string_agg(id::text||':'||status, ',' order by status) from private.trip_requests;""")
    rows = d.get("rows", "")
    ok = "12000000-0000-4000-8000-00000000000a" not in rows and "12000000-0000-4000-8000-00000000000b:unverified" in rows and ":pending" in rows
    return ok, rows


@scenario("DB-13", "8", "§4 start ≤3 per email per day (counted ok or not): 4th → rate_limited, no row")
def _():
    d = kv("""select 'r1', qa21.start(gen_random_uuid(), qa21.payload('lim@e.co'), 'ip-a')::text;
      select 'r2', qa21.start(gen_random_uuid(), qa21.payload('lim@e.co'), 'ip-b')::text;
      select 'r3', qa21.try($q$select qa21.start(gen_random_uuid(), qa21.payload('lim@e.co', p_travellers => 0), 'ip-c')::text$q$);
      select 'r4', qa21.start('13000000-0000-4000-8000-000000000004', qa21.payload('lim@e.co'), 'ip-d')::text;
      select 'other', qa21.start(gen_random_uuid(), qa21.payload('other@e.co'), 'ip-e')::text;
      select 'n4', count(*)::text from private.trip_requests where id='13000000-0000-4000-8000-000000000004';""")
    ok = err(d.get("r4")) == "rate_limited" and d.get("n4") == "0" and not err(d.get("other")) and err(d.get("r3")) == "invalid_request"
    return ok, d


@scenario("DB-14", "8", "§4 start ≤10 per IP per day: 11th → rate_limited; another IP still ok")
def _():
    body = "".join("select 'r%d', qa21.start(gen_random_uuid(), qa21.payload('ip%d@e.co'), 'ip-same')::text;\n" % (i, i) for i in range(1, 12))
    d = kv(body + "select 'x', qa21.start(gen_random_uuid(), qa21.payload('ipx@e.co'), 'ip-other')::text;")
    firsts = [err(d.get("r%d" % i)) for i in range(1, 11)]
    ok = not any(firsts) and err(d.get("r11")) == "rate_limited" and not err(d.get("x"))
    return ok, {"1-10": firsts, "11": d.get("r11"), "other ip": d.get("x")}


@scenario("DB-15", "8,9", "C3: the day = calendar day in Asia/Jerusalem — attempts / mails before Jerusalem midnight do not count")
def _():
    d = kv("""select 'a', qa21.start(gen_random_uuid(), qa21.payload('day@e.co'), 'ip-d1')::text;
      select 'b', qa21.start(gen_random_uuid(), qa21.payload('day@e.co'), 'ip-d2')::text;
      select 'c', qa21.start(gen_random_uuid(), qa21.payload('day@e.co'), 'ip-d3')::text;
      update private.request_attempts set at = %s - interval '1 minute';
      select 'd', qa21.start(gen_random_uuid(), qa21.payload('day@e.co'), 'ip-d4')::text;
      select 'm0', private.f21_mail_today()::text;
      select qa21.mails(3, 'code', %s - interval '1 minute');
      select qa21.mails(2, 'reject', %s + interval '1 second');
      select 'm1', private.f21_mail_today()::text;
      select 'jm', %s::text;""" % (JM, JM, JM, JM))
    # m0: mails of a,b,c (moved? no — only attempts moved) + d = 4; then +2 rejects after midnight (if now > midnight+1s) = 6
    ok = not err(d.get("d")) and d.get("m1") == str(int(d.get("m0", "-99")) + 2)
    return ok, d


@scenario("DB-16", "9", "§4 cap: 50 F21 mails today → start daily_limit (no row); 49 → ok; reject mails count too")
def _():
    d = kv("""select qa21.mails(49);
      select 'ok49', qa21.start(gen_random_uuid(), qa21.payload('c49@e.co'), 'ip-c49')::text;
      select 'm', private.f21_mail_today()::text;
      select 'cap', qa21.start('16000000-0000-4000-8000-000000000001', qa21.payload('c50@e.co'), 'ip-c50')::text;
      select 'n', count(*)::text from private.trip_requests where id='16000000-0000-4000-8000-000000000001';
      delete from private.mail_log; select qa21.mails(25); select qa21.mails(25, 'reject');
      select 'cap2', qa21.start(gen_random_uuid(), qa21.payload('c51@e.co'), 'ip-c51')::text;
      select 'm2', private.f21_mail_today()::text;""")
    ok = not err(d.get("ok49")) and d.get("m") == "50" and err(d.get("cap")) == "daily_limit" and d.get("n") == "0" \
        and err(d.get("cap2")) == "daily_limit" and d.get("m2") == "50"
    return ok, d


@scenario("DB-17", "9", "§4 verified-pending queue ≤100: with 100 pending, start → daily_limit")
def _():
    d = kv("""insert into private.trip_requests(lang,name,email,countries,travellers,status,verified_at)
        select 'he','q','q'||g||'@e.co',array['PT'],2,'pending',now() from generate_series(1,100) g;
      select 'r', qa21.start(gen_random_uuid(), qa21.payload('q101@e.co'), 'ip-q')::text;
      delete from private.trip_requests where email='q1@e.co';
      select 'r99', qa21.start(gen_random_uuid(), qa21.payload('q102@e.co'), 'ip-q2')::text;""")
    return err(d.get("r")) == "daily_limit" and not err(d.get("r99")), d


@scenario("DB-20", "6", "request_verify right code → pending + verified_at, code cleared")
def _():
    d = kv("""select qa21.start('20000000-0000-4000-8000-000000000001', qa21.payload('v@e.co'));
      select 'r', qa21.verify('20000000-0000-4000-8000-000000000001', '111111')::text;
      select 'row', row_to_json(t)::text from private.trip_requests t;""")
    row = J(d.get("row")) or {}
    ok = not err(d.get("r")) and row.get("status") == "pending" and row.get("verified_at") and not row.get("code_hash")
    return ok, "r=%s status=%s verified_at=%s code_hash=%s" % (d.get("r"), row.get("status"), row.get("verified_at"), row.get("code_hash"))


@scenario("DB-21", "6", "request_verify wrong → code_wrong attempts_left 4,3,2,1; 5th wrong → code_locked and the row is deleted")
def _():
    d = kv("select qa21.start('21000000-0000-4000-8000-000000000001', qa21.payload('w@e.co'));" +
           "".join("select 'w%d', qa21.verify('21000000-0000-4000-8000-000000000001', '99999%d')::text;" % (i, i) for i in range(1, 6)) +
           "select 'n', count(*)::text from private.trip_requests; select 'after', qa21.verify('21000000-0000-4000-8000-000000000001', '111111')::text;")
    ws = [J(d.get("w%d" % i)) or {} for i in range(1, 6)]
    left = [w.get("attempts_left") for w in ws[:4]]
    ok = [err(w) for w in ws[:4]] == ["code_wrong"] * 4 and left == [4, 3, 2, 1] and err(ws[4]) == "code_locked" and d.get("n") == "0" \
        and err(d.get("after")) in ("request_unknown", "code_locked")
    return ok, {"w": [d.get("w%d" % i) for i in range(1, 6)], "rows": d.get("n"), "after": d.get("after")}


@scenario("DB-22", "6", "request_verify after 10 min → code_expired; unknown id → request_unknown")
def _():
    d = kv("""select qa21.start('22000000-0000-4000-8000-000000000001', qa21.payload('x@e.co'));
      update private.trip_requests set code_expires_at = now() - interval '1 second', code_sent_at = now() - interval '10 minutes 1 second', created_at = now() - interval '10 minutes 1 second';
      select 'r', qa21.verify('22000000-0000-4000-8000-000000000001', '111111')::text;
      select 'u', qa21.verify('22000000-0000-4000-8000-0000000000ff', '111111')::text;
      select 'st', status from private.trip_requests;""")
    return err(d.get("r")) == "code_expired" and err(d.get("u")) == "request_unknown" and d.get("st") == "unverified", d


@scenario("DB-23", "8", "§4 verify: ≤20 wrong per IP per hour — the 21st wrong verify from that IP → rate_limited (even with a right code); 1 h later ok")
def _():
    ids = ["23000000-0000-4000-8000-00000000000%d" % i for i in range(1, 7)]
    body = "".join("select qa21.start('%s', qa21.payload('r%d@e.co'), 'ip-s%d');" % (x, i, i) for i, x in enumerate(ids))
    for i in range(5):
        body += "".join("select 'w%d_%d', qa21.verify('%s', '00000%d', 'ip-bad')::text;" % (i, k, ids[i], k) for k in range(4))
    body += "select 'r21', qa21.verify('%s', '111111', 'ip-bad')::text;" % ids[5]
    body += "select 'r21other', qa21.verify('%s', '111111', 'ip-good')::text;" % ids[4]
    body += "update private.request_attempts set at = now() - interval '61 minutes';"
    body += "select 'later', qa21.verify('%s', '111111', 'ip-bad')::text;" % ids[5]
    d = kv(body)
    wrong = [err(d.get("w%d_%d" % (i, k))) for i in range(5) for k in range(4)]
    ok = wrong == ["code_wrong"] * 20 and err(d.get("r21")) == "rate_limited" and not err(d.get("r21other")) and not err(d.get("later"))
    return ok, {"20 wrong": sorted(set(map(str, wrong))), "21st": d.get("r21"), "other ip": d.get("r21other"), "after 1h": d.get("later")}


@scenario("DB-30", "6", "request_resend: before 60 s refused (hash unchanged); after 60 s ok, hash replaced, old code dead, new code verifies; +1 code mail")
def _():
    d = kv("""select qa21.start('30000000-0000-4000-8000-000000000001', qa21.payload('rs@e.co'));
      select 'h0', code_hash from private.trip_requests;
      select 'early', qa21.resend('30000000-0000-4000-8000-000000000001', '222222')::text;
      select 'h1', code_hash from private.trip_requests;
      update private.trip_requests set code_sent_at = now() - interval '61 seconds';
      select 'late', qa21.resend('30000000-0000-4000-8000-000000000001', '222222')::text;
      select 'h2', code_hash from private.trip_requests;
      select 'cnt', resend_count::text from private.trip_requests;
      select 'mails', count(*)::text from private.mail_log;
      select 'old', qa21.verify('30000000-0000-4000-8000-000000000001', '111111')::text;
      select 'new', qa21.verify('30000000-0000-4000-8000-000000000001', '222222')::text;
      select 'st', status from private.trip_requests;""")
    ok = err(d.get("early")) and d.get("h0") == d.get("h1") and not err(d.get("late")) and d.get("h2") != d.get("h0") \
        and d.get("cnt") == "1" and d.get("mails") == "2" and err(d.get("old")) == "code_wrong" and not err(d.get("new")) and d.get("st") == "pending"
    return ok, {k: d.get(k) for k in ("early", "late", "cnt", "mails", "old", "new", "st")}


@scenario("DB-31", "6", "request_resend: ≤3 per request — the 4th is refused")
def _():
    body = "select qa21.start('31000000-0000-4000-8000-000000000001', qa21.payload('r4@e.co'), 'ip-r4');"
    for i in range(1, 5):
        body += "update private.trip_requests set code_sent_at = now() - interval '61 seconds';"
        body += "select 'r%d', qa21.resend('31000000-0000-4000-8000-000000000001', '33333%d')::text;" % (i, i)
    body += "select 'h', code_hash from private.trip_requests; select 'want3', encode(sha256(convert_to('31000000-0000-4000-8000-000000000001333333','UTF8')),'hex');"
    d = kv(body)
    ok = [err(d.get("r%d" % i)) for i in (1, 2, 3)] == [None, None, None] and err(d.get("r4")) and d.get("h") == d.get("want3")
    return ok, {k: d.get(k) for k in ("r1", "r2", "r3", "r4")}


@scenario("DB-32", "6,9", "request_resend at the cap → daily_limit (no new hash); an expired code can be replaced by a resend and the new one verifies")
def _():
    d = kv("""select qa21.start('32000000-0000-4000-8000-000000000001', qa21.payload('rc@e.co'), 'ip-rc');
      update private.trip_requests set code_sent_at = now() - interval '11 minutes', code_expires_at = now() - interval '1 minute';
      select 'exp', qa21.verify('32000000-0000-4000-8000-000000000001', '111111')::text;
      select qa21.mails(49);
      select 'cap', qa21.resend('32000000-0000-4000-8000-000000000001', '444444')::text;
      delete from private.mail_log;
      select 'ok', qa21.resend('32000000-0000-4000-8000-000000000001', '444444')::text;
      select 'v', qa21.verify('32000000-0000-4000-8000-000000000001', '444444')::text;""")
    ok = err(d.get("exp")) == "code_expired" and err(d.get("cap")) == "daily_limit" and not err(d.get("ok")) and not err(d.get("v"))
    return ok, d


APPROVE_FIX = """
select 'admin', qa21.user('or@e.co', true)::text;
"""


@scenario("DB-40", "12", "request_approve (no invite): one new invite with request_id, lang, draft_name, 7 days, F03 columns; request approved + invite_id + decided_*")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('new@e.co', 'en')::text);
      select 'r', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-40', 'Portugal & Spain · April 2027')::text;
      select 'inv', row_to_json(i)::text from public.manager_invites i where email='new@e.co';
      select 'req', row_to_json(t)::text from private.trip_requests t;
      select 'admin_id', x from v where k='admin';
      select 'exp_days', round(extract(epoch from (expires_at - now()))/86400)::text from public.manager_invites where email='new@e.co';
      select 'tok', encode(sha256(convert_to('tok-40','UTF8')),'hex');""")
    r, inv, req = J(d.get("r")) or {}, J(d.get("inv")) or {}, J(d.get("req")) or {}
    P = []
    if not isinstance(r, dict) or err(r) or r.get("invite_id") != inv.get("id") or "expires_at" not in r or "revoked_invite_id" not in r:
        P.append("result %r" % r)
    if r.get("revoked_invite_id") is not None:
        P.append("revoked_invite_id %r (no old invite)" % r.get("revoked_invite_id"))
    want = {"request_id": req.get("id"), "lang": "en", "draft_name": "Portugal & Spain · April 2027", "token_hash": d.get("tok"),
            "invited_by": d.get("admin_id"), "send_count": 1, "used_at": None, "revoked_at": None, "inviter_name": "אור"}
    for k, v in want.items():
        if inv.get(k) != v:
            P.append("invite.%s=%r want %r" % (k, inv.get(k), v))
    if d.get("exp_days") != "7" or not inv.get("last_sent_at"):
        P.append("expires in %s days, last_sent_at %r" % (d.get("exp_days"), inv.get("last_sent_at")))
    if req.get("status") != "approved" or req.get("invite_id") != inv.get("id") or req.get("decided_by") != d.get("admin_id") or not req.get("decided_at"):
        P.append("request %r" % {k: req.get(k) for k in ("status", "invite_id", "decided_by", "decided_at")})
    return not P, "; ".join(P)


@scenario("DB-41", "12", "request_approve on a request that is not pending (unverified / approved / rejected / unknown) → request_closed, nothing inserted")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('p', qa21.pending('p@e.co')::text), ('j', qa21.pending('j@e.co')::text);
      select qa21.start('41000000-0000-4000-8000-000000000001', qa21.payload('u@e.co'), 'ip-u');
      select 'a1', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='p'), 'tok-41a', 'x')::text;
      select 'a2', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='p'), 'tok-41b', 'x')::text;
      select 'rj', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='j'), false)::text;
      select 'a3', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='j'), 'tok-41c', 'x')::text;
      select 'a4', qa21.approve((select x::uuid from v where k='admin'), '41000000-0000-4000-8000-000000000001', 'tok-41d', 'x')::text;
      select 'a5', qa21.approve((select x::uuid from v where k='admin'), '41000000-0000-4000-8000-0000000000ff', 'tok-41e', 'x')::text;
      select 'inv', count(*)::text from public.manager_invites where email <> 'legacy@example.com';""")
    ok = not err(d.get("a1")) and [err(d.get(k)) for k in ("a2", "a3", "a4", "a5")] == ["request_closed"] * 4 and d.get("inv") == "1"
    return ok, d


@scenario("DB-42", "13", "D12: approve with an active invite for the email → old revoked_at set (its id returned), new invite active; exactly one active invite")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('old', qa21.invite('rep@e.co')::text), ('req', qa21.pending('rep@e.co')::text);
      select 'r', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-42', 'חדש')::text;
      select 'old_id', x from v where k='old';
      select 'old_rev', (revoked_at is not null)::text from public.manager_invites where id = (select x::uuid from v where k='old');
      select 'active', count(*)::text from public.manager_invites where email='rep@e.co' and used_at is null and revoked_at is null;
      select 'new_req', (request_id = (select x::uuid from v where k='req'))::text from public.manager_invites where email='rep@e.co' and revoked_at is null;""")
    r = J(d.get("r")) or {}
    ok = not err(r) and r.get("revoked_invite_id") == d.get("old_id") and d.get("old_rev") == "true" and d.get("active") == "1" and d.get("new_req") == "true"
    return ok, d


@scenario("DB-43", "14", "request_approve_undo (email failed): the new invite deleted, the old one active again (revoked_at null), request back to pending")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('old', qa21.invite('undo@e.co')::text), ('req', qa21.pending('undo@e.co')::text);
      insert into v select 'r', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-43', 'x')::text;
      select 'u', qa21.undo(((select x from v where k='r')::jsonb->>'invite_id')::uuid, ((select x from v where k='r')::jsonb->>'revoked_invite_id')::uuid, (select x::uuid from v where k='req'))::text;
      select 'n_inv', count(*)::text from public.manager_invites where email='undo@e.co';
      select 'old_open', (revoked_at is null)::text from public.manager_invites where id=(select x::uuid from v where k='old');
      select 'st', status||':'||coalesce(invite_id::text,'-') from private.trip_requests;
      select 'list', qa21.admin_list((select x::uuid from v where k='admin'));
      insert into v select 'r2', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-43b', 'x')::text;
      select 'again', x from v where k='r2';""")
    lst = J(d.get("list")) or {}
    reqs = lst.get("requests") if isinstance(lst, dict) else None
    ok = not err(d.get("u")) and d.get("n_inv") == "1" and d.get("old_open") == "true" and d.get("st") == "pending:-" \
        and isinstance(reqs, list) and len(reqs) == 1 and not err(d.get("again"))
    return ok, {k: d.get(k) for k in ("u", "n_inv", "old_open", "st", "again")}


@scenario("DB-44", "14", "request_approve_undo without an old invite (p_revoked null): new invite deleted, request pending")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('undo2@e.co')::text);
      insert into v select 'r', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-44', 'x')::text;
      select 'u', qa21.undo(((select x from v where k='r')::jsonb->>'invite_id')::uuid, null, (select x::uuid from v where k='req'))::text;
      select 'n_inv', count(*)::text from public.manager_invites where email='undo2@e.co';
      select 'st', status from private.trip_requests;""")
    return not err(d.get("u")) and d.get("n_inv") == "0" and d.get("st") == "pending", d


@scenario("DB-50", "15", "request_reject with mail under the cap → rejected + {mail:true, lang, email, name}, one 'reject' mail logged, reject_mailed")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('rj@e.co', 'en', p_name => 'Ann')::text);
      select 'r', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), true)::text;
      select 'row', row_to_json(t)::text from private.trip_requests t;
      select 'mails', count(*)::text from private.mail_log where kind='reject';
      select 'admin', x from v where k='admin';""")
    r, row = J(d.get("r")) or {}, J(d.get("row")) or {}
    ok = r.get("mail") is True and r.get("lang") == "en" and r.get("email") == "rj@e.co" and r.get("name") == "Ann" \
        and row.get("status") == "rejected" and row.get("decided_at") and row.get("decided_by") == d.get("admin") \
        and row.get("reject_mailed") is True and d.get("mails") == "1"
    return ok, {"r": r, "status": row.get("status"), "reject_mailed": row.get("reject_mailed"), "mails": d.get("mails")}


@scenario("DB-51", "15", "request_reject without mail → rejected, {mail:false, reason}, no mail logged")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('rj2@e.co')::text);
      select 'r', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), false)::text;
      select 'st', status||':'||coalesce(reject_mailed::text,'null') from private.trip_requests;
      select 'mails', count(*)::text from private.mail_log;""")
    r = J(d.get("r")) or {}
    return r.get("mail") is False and "reason" in r and d.get("st") in ("rejected:false", "rejected:null") and d.get("mails") == "0", d


@scenario("DB-52", "9,15", "request_reject with mail AT the cap → still rejected, {mail:false, reason:'daily_limit'}, no mail logged")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('rj3@e.co')::text);
      select qa21.mails(50);
      select 'r', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), true)::text;
      select 'st', status from private.trip_requests;
      select 'mails', count(*)::text from private.mail_log;""")
    r = J(d.get("r")) or {}
    return r.get("mail") is False and r.get("reason") == "daily_limit" and d.get("st") == "rejected" and d.get("mails") == "50", d


@scenario("DB-53", "9", "C2: an approval at the cap still creates the invite (invites are not counted, never blocked)")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('cap@e.co')::text);
      select qa21.mails(50);
      select 'r', qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-53', 'x')::text;
      select 'm', private.f21_mail_today()::text;""")
    return not err(d.get("r")) and d.get("m") == "50", d


@scenario("DB-54", "15", "request_reject of a request that is not pending → request_closed")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('rj4@e.co')::text);
      select 'r1', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), false)::text;
      select 'r2', qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), true)::text;
      select 'm', count(*)::text from private.mail_log;""")
    return not err(d.get("r1")) and err(d.get("r2")) == "request_closed" and d.get("m") == "0", d


@scenario("DB-60", "15", "D5 cleanup: rejected > 5 d and unverified > 5 d deleted; 4-day-old ones kept; verified pending > 5 d kept; attempts / mail_log > 7 d deleted")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text);
      insert into v values ('rej6', qa21.pending('r6@e.co')::text), ('rej4', qa21.pending('r4@e.co')::text), ('pend30', qa21.pending('p30@e.co', p_ago => '30 days')::text);
      select qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='rej6'), false);
      select qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='rej4'), false);
      update private.trip_requests set decided_at = now() - interval '5 days 1 minute' where id = (select x::uuid from v where k='rej6');
      update private.trip_requests set decided_at = now() - interval '4 days 23 hours' where id = (select x::uuid from v where k='rej4');
      update private.trip_requests set created_at = now() - interval '30 days' where id = (select x::uuid from v where k='pend30');
      select qa21.start('60000000-0000-4000-8000-000000000006', qa21.payload('u6@e.co'), 'ip-u6');
      select qa21.start('60000000-0000-4000-8000-000000000004', qa21.payload('u4@e.co'), 'ip-u4');
      update private.trip_requests set created_at = now() - interval '5 days 1 minute' where id = '60000000-0000-4000-8000-000000000006';
      update private.trip_requests set created_at = now() - interval '4 days 23 hours' where id = '60000000-0000-4000-8000-000000000004';
      delete from private.request_attempts; delete from private.mail_log;
      insert into private.request_attempts(kind, at) values ('start', now() - interval '7 days 1 minute'), ('verify', now() - interval '6 days 23 hours');
      select qa21.mails(1, 'code', now() - interval '7 days 1 minute'); select qa21.mails(1, 'reject', now() - interval '6 days 23 hours');
      set local role service_role; select private.f21_cleanup(); reset role;
      select 'left', string_agg(email||':'||status, ',' order by email) from private.trip_requests;
      select 'att', count(*)::text from private.request_attempts; select 'mail', count(*)::text from private.mail_log;""")
    left = d.get("left", "")
    ok = left == "p30@e.co:pending,r4@e.co:rejected,u4@e.co:unverified" and d.get("att") == "1" and d.get("mail") == "1"
    return ok, d


@scenario("DB-61", "15", "C5: admin_trip_requests() runs the cleanup (a 6-day-old rejected row disappears on the admin list load)")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('rej', qa21.pending('c5@e.co')::text);
      select qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='rej'), false);
      update private.trip_requests set decided_at = now() - interval '6 days';
      select 'before', count(*)::text from private.trip_requests;
      select 'l', left(qa21.admin_list((select x::uuid from v where k='admin')), 40);
      select 'after', count(*)::text from private.trip_requests;""")
    return d.get("before") == "1" and d.get("after") == "0", d


@scenario("DB-62", "15", "C5: every request-trip call runs the cleanup — after request_start / request_verify / request_resend an old rejected row is gone")
def _():
    out = {}
    for call in ("start", "verify", "resend"):
        d = kv("""create temp table v(k text, x text) on commit drop;
          insert into v values ('admin', qa21.user('or@e.co', true)::text), ('rej', qa21.pending('c5b@e.co')::text);
          select qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='rej'), false);
          update private.trip_requests set decided_at = now() - interval '6 days';
          select qa21.start('62000000-0000-4000-8000-000000000001', qa21.payload('c5c@e.co'), 'ip-c5c');
          update private.trip_requests set decided_at = now() - interval '6 days' where status = 'rejected';
          update private.trip_requests set code_sent_at = now() - interval '2 minutes' where status = 'unverified';
          select 'x', (%s)::text;
          select 'n', count(*)::text from private.trip_requests where status = 'rejected';""" % {
            "start": "qa21.start(gen_random_uuid(), qa21.payload('c5d@e.co'), 'ip-c5d')",
            "verify": "qa21.verify('62000000-0000-4000-8000-000000000001', '000000', 'ip-c5c')",
            "resend": "qa21.resend('62000000-0000-4000-8000-000000000001', '555555')"}[call])
        out[call] = d.get("n")
    # the start call that created 62…01 already ran a cleanup BEFORE the rejected row was aged again; only the call under test can remove it
    return all(v == "0" for v in out.values()), "rejected rows left after the call: %s (SQL functions; the Edge Function may call the cleanup itself — see function tests)" % out


@scenario("DB-70", "11,17", "admin_trip_requests(): anon → permission denied; authenticated non-admin → not_platform_admin; admin → {cap:50, mail_today, requests}")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('user', qa21.user('someone@e.co')::text);
      select 'anon', qa21.try('select 1') ;
      set local role anon; select 'anon2', qa21.try('select public.admin_trip_requests()::text'); reset role;
      select 'user', qa21.admin_list((select x::uuid from v where k='user'));
      select 'admin', qa21.admin_list((select x::uuid from v where k='admin'));""")
    a = J(d.get("admin")) or {}
    ok = str(d.get("anon2")).startswith("ERR:42501") and "not_platform_admin" in str(d.get("user")) and str(d.get("user")).startswith("ERR:") \
        and isinstance(a, dict) and a.get("cap") == 50 and "mail_today" in a and a.get("requests") == []
    return ok, {k: str(d.get(k))[:160] for k in ("anon2", "user", "admin")}


@scenario("DB-71", "11", "admin_trip_requests(): only verified pending rows, oldest first; exact fields; no hashes / codes / ip; month and countries as stored")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text);
      insert into v values ('new', qa21.pending('new@e.co', 'he', '1 hour', array['JP'], null, 'נועה', 'הערה קצרה')::text);
      insert into v values ('old', qa21.pending('old@e.co', 'en', '3 days', array['PT','ES','FR'], '2027-04-01', 'Ann')::text);
      insert into v values ('rej', qa21.pending('rej@e.co')::text), ('apr', qa21.pending('apr@e.co')::text);
      select qa21.reject((select x::uuid from v where k='admin'), (select x::uuid from v where k='rej'), false);
      select qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='apr'), 'tok-71', 'x');
      select qa21.start(gen_random_uuid(), qa21.payload('unv@e.co'), 'ip-unv');
      select 'l', qa21.admin_list((select x::uuid from v where k='admin'));
      select 'ids', (select x from v where k='old')||','||(select x from v where k='new');""")
    lst = J(d.get("l")) or {}
    reqs = lst.get("requests") if isinstance(lst, dict) else None
    P = []
    if not isinstance(reqs, list):
        return False, "no list: %s" % d.get("l")
    if [r.get("id") for r in reqs] != d.get("ids", "").split(","):
        P.append("ids/order %s want %s" % ([r.get("email") for r in reqs], "old,new"))
    keys = {"id", "lang", "name", "email", "countries", "month", "travellers", "note", "verified_at", "manages", "active_invite"}
    for r in reqs:
        if set(r) != keys:
            P.append("keys %s (want exactly %s)" % (sorted(r), sorted(keys)))
            break
    raw = d.get("l", "")
    for bad in ("code_hash", "ip_hash", "email_hash", "code_expires", "rej@e.co", "apr@e.co", "unv@e.co"):
        if bad in raw:
            P.append("leaks %s" % bad)
    if reqs and len(reqs) == 2:
        o, n = reqs
        if (o.get("lang"), o.get("name"), o.get("countries"), str(o.get("month"))[:10], o.get("travellers"), o.get("note")) != ("en", "Ann", ["PT", "ES", "FR"], "2027-04-01", 4, None):
            P.append("old row values %s" % o)
        if (n.get("month"), n.get("note"), n.get("manages"), n.get("active_invite")) != (None, "הערה קצרה", [], None):
            P.append("new row values %s" % n)
    return not P, "; ".join(P)


@scenario("DB-72", "11", "admin_trip_requests(): D6 markers — manages = trip names of ACTIVE MANAGER memberships of the auth user with that email; active_invite = {id, draft_name, last_sent_at, expires_at}")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('mu', qa21.user('mgr@e.co')::text);
      select qa21.manager((select x::uuid from v where k='mu'), 'יפן 2027');
      select qa21.manager((select x::uuid from v where k='mu'), 'יוון 2028');
      select qa21.manager((select x::uuid from v where k='mu'), 'עורך בלבד', 'editor');
      select qa21.manager((select x::uuid from v where k='mu'), 'הוסר', 'manager', 'removed');
      insert into v values ('inv', qa21.invite('inv@e.co', 'טיול ישן', '3 days', '4 days')::text);
      select qa21.invite('exp@e.co', 'פג', '9 days', '-2 days');
      select qa21.pending('mgr@e.co', p_ago => '3 hours'); select qa21.pending('inv@e.co', p_ago => '2 hours'); select qa21.pending('exp@e.co', p_ago => '1 hour');
      select 'l', qa21.admin_list((select x::uuid from v where k='admin'));
      select 'inv', x from v where k='inv';""")
    lst = J(d.get("l")) or {}
    reqs = {r.get("email"): r for r in (lst.get("requests") or [])} if isinstance(lst, dict) else {}
    P = []
    m = reqs.get("mgr@e.co", {})
    if sorted(m.get("manages") or []) != sorted(["יפן 2027", "יוון 2028"]) or m.get("active_invite") is not None:
        P.append("manager row: manages=%r active_invite=%r" % (m.get("manages"), m.get("active_invite")))
    i = reqs.get("inv@e.co", {})
    ai = i.get("active_invite") or {}
    if set(ai) != {"id", "draft_name", "last_sent_at", "expires_at"} or ai.get("id") != d.get("inv") or ai.get("draft_name") != "טיול ישן" or i.get("manages") != []:
        P.append("invite row: %r" % i)
    e = reqs.get("exp@e.co", {})
    if e.get("active_invite") is not None:
        P.append("expired invite reported as active: %r" % e.get("active_invite"))
    return not P, "; ".join(P)


@scenario("DB-73", "11", "admin_trip_requests().mail_today = today's mail_log count (code + reject), cap 50")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text);
      select qa21.mails(7); select qa21.mails(3, 'reject'); select qa21.mails(4, 'code', %s - interval '5 minutes');
      select 'l', qa21.admin_list((select x::uuid from v where k='admin'));""" % JM)
    lst = J(d.get("l")) or {}
    return isinstance(lst, dict) and lst.get("mail_today") == 10 and lst.get("cap") == 50, d.get("l", "")[:200]


@scenario("DB-80", "16", "§2.8 find_invite_for_email: invite from a request → prefill {name, countries, month, lang}; month null kept")
def _():
    d = kv("""create temp table v(k text, x text) on commit drop;
      insert into v values ('admin', qa21.user('or@e.co', true)::text), ('req', qa21.pending('pf@e.co', 'en', '1 hour', array['PT','ES'], '2027-04-01', 'Ann')::text),
        ('req2', qa21.pending('pf2@e.co', 'he', '1 hour', array['JP'], null, 'נועה')::text);
      select qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req'), 'tok-80', 'Portugal & Spain · April 2027');
      select qa21.approve((select x::uuid from v where k='admin'), (select x::uuid from v where k='req2'), 'tok-80b', 'יפן');
      set local role service_role;
      select 'f', public.find_invite_for_email('pf@e.co')::text; select 'f2', public.find_invite_for_email('pf2@e.co')::text;
      select 'g', public.find_invite_for_email('legacy@example.com')::text;
      reset role;""")
    f, f2, g = J(d.get("f")) or {}, J(d.get("f2")) or {}, J(d.get("g")) or {}
    pf, pf2 = f.get("prefill") or {}, f2.get("prefill") or {}
    ok = set(pf) == {"name", "countries", "month", "lang"} and pf.get("name") == "Ann" and pf.get("countries") == ["PT", "ES"] \
        and str(pf.get("month"))[:10] == "2027-04-01" and pf.get("lang") == "en" and f.get("draft_name") == "Portugal & Spain · April 2027" \
        and pf2.get("month") is None and pf2.get("lang") == "he" and "prefill" not in g
    return ok, {"f": d.get("f"), "f2": d.get("f2"), "legacy": d.get("g")}


@scenario("DB-81", "17", "service-role-only: anon and authenticated cannot execute request_start / verify / resend / approve / undo / reject (42501)")
def _():
    bad = []
    for role in ("anon", "authenticated"):
        for call in ("public.request_start(gen_random_uuid(), '{}'::jsonb, 'x', 'x', 'x')", "public.request_verify(gen_random_uuid(), 'x', 'x')",
                     "public.request_resend(gen_random_uuid(), 'x')", "public.request_approve(gen_random_uuid(), gen_random_uuid(), 'x', 'x', 'x')",
                     "public.request_approve_undo(gen_random_uuid(), gen_random_uuid(), gen_random_uuid())",
                     "public.request_reject(gen_random_uuid(), gen_random_uuid(), true)", "public.find_invite_for_email('a@e.co')"):
            v = one("begin; set local role %s; select qa21.try($q$select %s::text$q$); rollback;" % (role, call))
            if not str(v).startswith("ERR:42501"):
                bad.append((role, call.split("(")[0], v[:80]))
    return not bad, bad


@scenario("DB-82", "17", "refusals are RETURNED as {\"error\":code}, never raised (service role)")
def _():
    d = kv("""set local role service_role;
      select 'v', qa21.try($q$select public.request_verify(gen_random_uuid(), repeat('a',64), 'x')::text$q$);
      select 'r', qa21.try($q$select public.request_resend(gen_random_uuid(), repeat('a',64))::text$q$);
      select 'a', qa21.try($q$select public.request_approve(gen_random_uuid(), gen_random_uuid(), repeat('a',64), 'x', 'x')::text$q$);
      select 'j', qa21.try($q$select public.request_reject(gen_random_uuid(), gen_random_uuid(), true)::text$q$);
      reset role;""")
    ok = all(not str(d.get(k, "")).startswith("ERR:") and err(d.get(k)) for k in "vraj")
    return ok, d


def run_harness_rows():
    out = []
    for run in ("f01", "f02", "f03", "f04", "f05", "f06", "f21"):
        cols = "id, pass, scenario, actual" if run == "f01" else "id, pass, name, detail"
        r = psql("-A", "-t", "-F", "\t", "-c", "select %s from qa.%s_run() order by id" % (cols, run))
        rows = [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]
        out.append((run, rows, r.returncode, r.stderr))
    return out


def main():
    regression = "--regression" in sys.argv
    files = [SHIM] + [MIG / n for n in BEFORE]
    for f in files + [MIG / n for n in F21]:
        shutil.copy(f, TMP / f.name)
    psql("-c", "drop database if exists %s" % DB, db=None)
    r = psql("-c", "create database %s" % DB, db=None)
    if r.returncode:
        print(r.stderr)
        return 2
    for f in files:
        r = psql("-1", "-f", str(TMP / f.name))
        print("apply %-30s %s" % (f.name, "OK" if r.returncode == 0 else "FAIL\n" + r.stderr[-2000:]))
        if r.returncode:
            return 1
    # fixture before F21: a legacy F03 invite (no request) → §2.4 'existing rows = he', §2.8 'unchanged output otherwise'
    sql_rows("insert into public.manager_invites(email, token_hash, draft_name, expires_at, last_sent_at, inviter_name) values "
             "('legacy@example.com', repeat('e',64), 'יפן 2027', now() + interval '5 days', now() - interval '2 days', 'אור');")
    S0.update(snapshot())
    for n in F21:
        r = psql("-1", "-f", str(TMP / n))
        print("apply %-30s %s" % (n, "OK" if r.returncode == 0 else "FAIL\n" + r.stderr[-2000:]))
        if r.returncode:
            return 1
    S1.update(snapshot())
    if "--setup-only" in sys.argv:   # for tests/f21/integration_test.ts: schema 0001…0017 ready, database kept
        shutil.rmtree(TMP, ignore_errors=True)
        print("SETUP OK", DB)
        return 0
    harness = run_harness_rows()
    sql_rows(HELPERS)
    static_checks()
    for s in SCENARIOS:
        s()
    # nothing left behind (every scenario rolled back; only the legacy fixture invite remains)
    left = one("select ((select count(*) from private.trip_requests)+(select count(*) from private.request_attempts)+(select count(*) from private.mail_log)"
               "+(select count(*) from public.manager_invites where email <> 'legacy@example.com')+(select count(*) from auth.users)+(select count(*) from public.trips))::text")
    rec("DB-99", "17", left == "0", "nothing left behind by qa.*_run() and the scenarios", "rows left: %s" % left)
    sql_rows("drop schema qa21 cascade;")

    ok_all = True
    for run, rows, rc, se in harness:
        fails = [x for x in rows if len(x) > 1 and x[1] != "t"]
        sup = [x for x in fails if ("qa.%s_run" % run, x[0]) in SUPERSEDED]
        real = [x for x in fails if x not in sup]
        print("qa.%s_run(): %d/%d pass%s" % (run, len(rows) - len(fails), len(rows), "" if not rc else " ERROR " + se[-300:]))
        for x in fails:
            tag = "SUPERSEDED (%s)" % SUPERSEDED[("qa.%s_run" % run, x[0])] if x in sup else ""
            print("    FAIL %s %s :: %s %s" % (x[0], x[2][:120] if len(x) > 2 else "", (x[3] if len(x) > 3 else "")[:300], tag))
        ok_all &= not real and not rc and bool(rows)
    n_ok = sum(1 for r in RESULTS if r[2])
    print("f21_db_test: %d/%d pass" % (n_ok, len(RESULTS)))
    for tid, crit, ok, desc, detail in RESULTS:
        if regression and ok:
            continue
        print("  %-4s %-22s [C%s] %s%s" % ("ok" if ok else "FAIL", tid, crit, desc, "" if ok and not detail else "\n         " + str(detail)[:1200]))
    ok_all &= n_ok == len(RESULTS)
    print("leftover rows after the runs:", left)
    if "--keep" not in sys.argv:
        psql("-c", "drop database if exists %s" % DB, db=None)
    shutil.rmtree(TMP, ignore_errors=True)
    print("ALL OK" if ok_all else "FAILURES")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
