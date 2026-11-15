-- Lonely Planner F14 DB test · version 1.0.0 · tests migration 0022_f14.sql
-- CHANGE 2026-11-15 F14-QA-01: new file (no previous version). Everything runs in one transaction that is rolled back.
begin;
insert into auth.users(id, aud, role, email, is_anonymous) values
  ('14000000-0000-4000-8000-0000000000a1','authenticated','authenticated','m@e.co',false),
  ('14000000-0000-4000-8000-0000000000a2','authenticated','authenticated','v@e.co',false),
  ('14000000-0000-4000-8000-0000000000a3','authenticated','authenticated','p@e.co',false),
  ('14000000-0000-4000-8000-0000000000a4','authenticated','authenticated','o@e.co',false);
insert into public.trips(id, name) values ('14000000-0000-4000-8000-0000000000b1','T1'), ('14000000-0000-4000-8000-0000000000b2','T2');
insert into public.trip_members(trip_id,user_id,display_name,role,status) values
  ('14000000-0000-4000-8000-0000000000b1','14000000-0000-4000-8000-0000000000a1','mgr','manager','active'),
  ('14000000-0000-4000-8000-0000000000b1','14000000-0000-4000-8000-0000000000a2','viewer','viewer','active'),
  ('14000000-0000-4000-8000-0000000000b1','14000000-0000-4000-8000-0000000000a3','pend','editor','pending'),
  ('14000000-0000-4000-8000-0000000000b2','14000000-0000-4000-8000-0000000000a1','mgr2','manager','active');

create temp table t(id text, ok boolean, detail text);
grant all on t to public;
do $$
declare
  u1 uuid := '14000000-0000-4000-8000-0000000000a1'; u2 uuid := '14000000-0000-4000-8000-0000000000a2';
  u3 uuid := '14000000-0000-4000-8000-0000000000a3'; u4 uuid := '14000000-0000-4000-8000-0000000000a4';
  t1 uuid := '14000000-0000-4000-8000-0000000000b1'; t2 uuid := '14000000-0000-4000-8000-0000000000b2';
  r jsonb; i int;
begin
  r := public.chat_take(u1, t1, 3);
  insert into t values ('DB01 first take', r = '{"ok":true,"used":1,"cap":3}'::jsonb, r::text);
  r := public.chat_take(u2, t1, 3);   -- a viewer counts on the SAME trip counter
  insert into t values ('DB02 viewer allowed, shared counter', r = '{"ok":true,"used":2,"cap":3}'::jsonb, r::text);
  r := public.chat_take(u1, t1, 3);
  insert into t values ('DB03 third take = cap reached but ok', r = '{"ok":true,"used":3,"cap":3}'::jsonb, r::text);
  r := public.chat_take(u1, t1, 3);
  insert into t values ('DB04 over cap', r = '{"error":"daily_cap","used":3,"cap":3}'::jsonb, r::text);
  r := public.chat_take(u2, t1, 3);
  insert into t values ('DB05 over cap for another member too', r->>'error' = 'daily_cap', r::text);
  insert into t values ('DB06 counter did not move past cap', (select n from private.chat_usage where trip_id=t1)=3, (select n::text from private.chat_usage where trip_id=t1));
  r := public.chat_take(u1, t2, 3);
  insert into t values ('DB07 other trip has its own counter', r = '{"ok":true,"used":1,"cap":3}'::jsonb, r::text);
  r := public.chat_take(u3, t1, 3);
  insert into t values ('DB08 pending member refused', r = '{"error":"not_member"}'::jsonb, r::text);
  r := public.chat_take(u4, t1, 3);
  insert into t values ('DB09 stranger refused', r = '{"error":"not_member"}'::jsonb, r::text);
  r := public.chat_take(u2, t2, 3);
  insert into t values ('DB10 member of another trip refused', r = '{"error":"not_member"}'::jsonb, r::text);
  insert into t values ('DB11 refusals did not count', (select n from private.chat_usage where trip_id=t1)=3 and (select n from private.chat_usage where trip_id=t2)=1, '');
  r := public.chat_refund(t1);
  insert into t values ('DB12 refund gives one back', r = '{"ok":true,"used":2}'::jsonb, r::text);
  r := public.chat_take(u1, t1, 3);
  insert into t values ('DB13 take works again after refund', r = '{"ok":true,"used":3,"cap":3}'::jsonb, r::text);
  for i in 1..5 loop perform public.chat_refund(t2); end loop;
  insert into t values ('DB14 refund never below 0', (select n from private.chat_usage where trip_id=t2)=0, (select n::text from private.chat_usage where trip_id=t2));
  r := public.chat_refund(gen_random_uuid());
  insert into t values ('DB15 refund of unknown trip is harmless', r = '{"ok":true,"used":0}'::jsonb, r::text);
  insert into t values ('DB16 invalid args', public.chat_take(null,t1,3)->>'error'='invalid_request' and public.chat_take(u1,null,3)->>'error'='invalid_request'
     and public.chat_take(u1,t1,0)->>'error'='invalid_request' and public.chat_take(u1,t1,null)->>'error'='invalid_request' and public.chat_refund(null)->>'error'='invalid_request', '');
  -- a new UTC day: yesterday's full counter does not block today, and old rows (> 7 days) are removed
  insert into private.chat_usage(trip_id, day, n) values (t1, (now() at time zone 'UTC')::date - 1, 3), (t2, (now() at time zone 'UTC')::date - 9, 5);
  r := public.chat_take(u1, t1, 3);   -- separate statement: a subquery in the same statement would not see the delete
  insert into t values ('DB17 old rows deleted by the next take', r->>'error' = 'daily_cap'
     and not exists (select 1 from private.chat_usage where day < (now() at time zone 'UTC')::date - 7)
     and exists (select 1 from private.chat_usage where trip_id=t1 and day=(now() at time zone 'UTC')::date - 1), r::text);
  delete from private.chat_usage where trip_id = t1 and day = (now() at time zone 'UTC')::date;
  r := public.chat_take(u1, t1, 3);
  insert into t values ('DB18 yesterday full, today starts at 1', r = '{"ok":true,"used":1,"cap":3}'::jsonb, r::text);
  delete from public.trips where id = t2;
  insert into t values ('DB19 trip delete cascades the counter', not exists (select 1 from private.chat_usage where trip_id=t2), '');
end $$;

-- grants / RLS
insert into t select 'DB20 RLS on, no policies', c.relrowsecurity and not exists (select 1 from pg_policies p where p.schemaname='private' and p.tablename='chat_usage'), ''
  from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='private' and c.relname='chat_usage';
insert into t values ('DB21 no client grants on the table', not exists (select 1 from information_schema.role_table_grants g where g.table_schema='private' and g.table_name='chat_usage' and g.grantee in ('anon','authenticated','public')), '');
insert into t values ('DB22 functions: service_role only',
  has_function_privilege('service_role','public.chat_take(uuid,uuid,int)','execute') and has_function_privilege('service_role','public.chat_refund(uuid)','execute')
  and not has_function_privilege('anon','public.chat_take(uuid,uuid,int)','execute') and not has_function_privilege('authenticated','public.chat_take(uuid,uuid,int)','execute')
  and not has_function_privilege('anon','public.chat_refund(uuid)','execute') and not has_function_privilege('authenticated','public.chat_refund(uuid)','execute'), '');
insert into t values ('DB23 public still has exactly 9 tables', (select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE')=9,
  (select count(*)::text from information_schema.tables where table_schema='public' and table_type='BASE TABLE'));
select id, case when ok then 'PASS' else 'FAIL' end, detail from t order by id;
rollback;
