# F04 · DB cases the `qa.f04_run()` harness must contain (criteria 5, 10, 11, 17 + §2 validation)

Version 1.0.0 · CHANGE 2026-10-12 F04-QA: first version (no previous version).

Independent checklist written from `docs/F04_spec.md` §2 / §5 only, to compare against the dev harness
`0011_qa_f04_harness.sql` (not read). Same pattern as F01–F03: `qa` schema locked, impersonation through
`request.jwt.claims` + `set local role`, every scenario inside a sub-transaction that is always rolled back.
Calls to `create_trip_from_invite(p_user, p_email, p_payload)` / `find_invite_for_email(p_email)` run as
`service_role` unless the case says otherwise. After the run, `count(*)` of `trips`, `trip_countries`,
`trip_currencies`, `trip_members`, `trip_join_codes`, `trip_kv`, `manager_invites`, `auth.users` equals the count
before (nothing left behind).

**Fixture.** Users M (invitee, confirmed email `m@f04qa.test`), M2 (second invitee), X (outsider), E (will be editor),
V (will be viewer). Invites: I-M pending for `m@f04qa.test` (expires now()+7d), I-EXP expired, I-REV revoked,
I-USED used by another trip, I-OLD + I-NEW for the same email (I-OLD revoked by the resend/replace flow, I-NEW active).
Payload P = `{name:"יפן 2027", display_name:"דנה", start_date:"2027-04-03", end_date:"2027-04-20", home_currency:"ILS",
default_lang:"he", default_role:"editor", countries:["JP","KR"], currencies:[{code:"JPY",kind:"destination"},
{code:"KRW",kind:"destination"}], center:{lat:35.68,lng:139.69}}`.

## S · Schema / grants (C17, §2)

| # | Case | Expected |
|---|---|---|
| S1 | `create_trip_from_invite(uuid,text,jsonb)` | `prosecdef`, `provolatile='v'`, `proconfig` has `search_path=""`, returns jsonb |
| S2 | `find_invite_for_email(text)` | `prosecdef`, `search_path=""`, returns jsonb |
| S3 | execute privileges on both | `service_role`: yes; `anon`, `authenticated`, `public`: **no** (`has_function_privilege`) |
| S4 | as `authenticated` (M's claims) `select public.create_trip_from_invite(M, 'm@…', P)` | permission denied (42501); nothing written |
| S5 | as `anon` call either function | permission denied |
| S6 | no new client-writable grants | anon/authenticated privileges on every public table equal to after 0009 (F03); `trip_join_codes`: authenticated SELECT only (as F01) |
| S7 | migration idempotent | running 0010 twice succeeds, no duplicate objects |

## L · find_invite_for_email

| # | Case | Expected |
|---|---|---|
| L1 | `'m@f04qa.test'` | `{found:true, invite_id=I-M, draft_name, inviter_name, expires_at}` |
| L2 | `'  M@F04QA.TEST '` (case/space) | same as L1 (normalized) — or document that the function expects normalized input |
| L3 | email of I-EXP / I-REV / I-USED | `{found:false}` |
| L4 | unknown email | `{found:false}` exactly (no other keys) |
| L5 | email with I-OLD (revoked) + I-NEW (active) | returns I-NEW |

## C · create_trip_from_invite — happy path (C11)

| # | Case | Expected |
|---|---|---|
| C1 | (M, `m@…`, P) | returns `{trip_id, join_code, created:true}` |
| C2 | `trips` row | exactly 1 new; name, start/end dates, `home_currency='ILS'`, `default_lang='he'`, `default_role='editor'`, `status='active'`, `created_by=M` |
| C3 | `trip_countries` | JP sort 0, KR sort 1 (array order) |
| C4 | `trip_currencies` | ILS sort 0 kind base; USD, EUR sort 1–2 kind base; JPY sort 3, KRW sort 4 kind destination; 5 rows |
| C4b | home_currency='USD' | USD sort 0, then ILS and EUR (sort 1–2), base |
| C5 | `trip_members` | 1 row: user M, display_name 'דנה', role manager, status active, `approved_at` set |
| C6 | `trip_join_codes` | 1 row for the trip; `code ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$'` (no 0, 1, I, O) |
| C7 | join-code alphabet over many trips | create ≥ 50 trips in the rolled-back block: every code matches C6; all distinct |
| C8 | join-code collision | pre-seed `trip_join_codes` so the first generated code collides (e.g. stub/patch or a fixed seed): function retries and succeeds (≤ 5 tries); after 5 forced collisions → error, nothing written |
| C9 | `trip_kv` key `trip` | 1 row, `updated_by=M`; JSON array of 18 objects; `day` 1…18; `date` `03/04/2027` … `20/04/2027` consecutive `dd/mm/yyyy`; every object has exactly the keys `day,date,region,title,activities,hotel,cost,notes,lat,lng,zoom,waypoints,country` with `""`/0/`[]` empties, `lat=35.68`, `lng=139.69`, `zoom=5`, `country='JP'` |
| C10 | invite I-M | `used_at` set, `trip_id` = new trip |
| C11 | month boundary: 2027-01-30 → 2027-02-02 | 4 days: 30/01/2027, 31/01/2027, 01/02/2027, 02/02/2027 |
| C12 | leap day: 2028-02-28 → 2028-03-01 | **3 days**: 28/02/2028, 29/02/2028, 01/03/2028 |
| C13 | year boundary: 2026-12-31 → 2027-01-01 | 2 days |
| C14 | single day (start = end) | 1 day |
| C15 | 120 days | 120 days accepted; 121 → `invalid_payload` detail `end_date` (or `start_date`) |

## I · Idempotency (C10)

| # | Case | Expected |
|---|---|---|
| I1 | C1 then the same call again (M, `m@…`, P) | `{same trip_id, same join_code, created:false}`; still exactly 1 trip / 1 membership / 1 join code / 1 trip_kv row |
| I2 | retry with a **different** payload after success | still the first trip (`created:false`), payload ignored, nothing new written |
| I3 | after success, M's membership removed (status ≠ active or role ≠ manager), then retry | `invite_invalid` (used invite, no active manager membership); nothing written |
| I4 | invite used by M, retried by M2 with M's email | `invite_invalid`; no write |

## R · Refusals (C5) — each: error raised, **nothing** written (row counts unchanged, invite unchanged)

| # | Case | Expected |
|---|---|---|
| R1 | invite expired | `P0001` `invite_invalid` |
| R2 | invite revoked | `invite_invalid` |
| R3 | invite used by another trip | `invite_invalid` |
| R4 | replaced (I-OLD revoked, I-NEW active) — create succeeds on I-NEW; an explicit check that I-OLD is never consumed | I-OLD unchanged |
| R5 | no invite for the email | `invite_invalid` |
| R6 | `p_email` with different case / spaces | normalized (trim, lower) → finds I-M |

## V · Payload validation — `invalid_payload` with a `detail` naming the field; nothing written

| # | Field | Invalid values | Valid boundary |
|---|---|---|---|
| V1 | name | missing, `""`, `"   "`, 81 chars (after trim) | 1 and 80 chars; surrounding spaces trimmed |
| V2 | display_name | missing, `""`, 41 chars | 1 and 40 |
| V3 | start_date / end_date | missing, `"03/04/2027"`, `"2027-02-30"`, `"x"`, end < start, 121 days | start = end; 120 days |
| V4 | home_currency | `"GBP"`, `"ils"`, missing | ILS, USD, EUR |
| V5 | default_lang | `"en"`, missing | `"he"` |
| V6 | default_role | `"manager"`, `"admin"`, missing | editor, viewer |
| V7 | countries | `[]`, 16 codes, `["jp"]`, `["JPN"]`, `["JP","JP"]`, not an array | 1 and 15 distinct |
| V8 | currencies | element without code, `"jpy"`, `"JPYY"`, kind `"base"` / `"x"`, duplicate code, base code (`ILS`/`USD`/`EUR`) as destination, not an array | `[]`; `kind` destination / added |
| V9 | currencies total | 8 non-base codes (3 + 8 = 11) | **`too_many_currencies`** (not invalid_payload); 7 (= 10) accepted |
| V10 | center | missing, lat 90.1 / −90.1, lng 180.1 / −180.1, non-numeric | ±90 / ±180 accepted |
| V11 | unknown extra payload keys | ignored (not stored) — or documented as rejected |

## P · RLS on the new trip (C17)

| # | Caller | Call | Expected |
|---|---|---|---|
| P1 | X (outsider) | select from `trips`, `trip_countries`, `trip_currencies`, `trip_members`, `trip_kv`, `trip_join_codes` for the new trip | 0 rows each |
| P2 | M (manager) | select `trip_join_codes` for the trip | 1 row (the code) |
| P3 | E (editor, active) / V (viewer, active) added to the trip | select `trip_join_codes` | 0 rows |
| P4 | M | insert/update/delete `trip_join_codes` | refused (no client write grant) |
| P5 | M | select `trip_kv` key `trip` | 1 row (member read works) |
| P6 | anon | select any of the above | permission denied / 0 rows |

## Run check

`select * from qa.f04_run() order by id;` → every row `pass`; row counts before/after identical; advisors clean
(security + performance) after 0010 and 0011.
