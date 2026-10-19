# F05 · dev notes — a member joins from the group link, after manager approval (v3.0.0-alpha.6)

<!-- CHANGE 2026-10-19 F05-DOCS-04: new file (no previous version). -->

Contract: `docs/F05_spec.md` (mockup approved 2026-10-19, canvas row 7, artboards `F05_Join` … `F05_Invalid`). Base: `main`
at 3.0.0-alpha.5.1 (870612a). Branch `f05`. **Nothing was deployed or run against Supabase.** All checks below are local.

## 1. What changed (file / area → why)

| File / area | CHANGE ID | What changed from 3.0.0-alpha.5.1 | Spec |
|---|---|---|---|
| `supabase/migrations/0012_f05.sql` | F05-DB-01 | new: schema `private` (closed to clients) with `transfer_codes`, `join_attempts` and helpers `private.f05_*`; six service-role-only functions in `public`: `join_preview`, `join_request`, `join_cancel`, `issue_transfer`, `claim_transfer`, `approve_member`. Refusals are **returned** `{"error":code}` (not raised) so attempt rows survive. `public` keeps exactly the 9 F01 tables. | §2 |
| `supabase/functions/join-trip/*` | F05-FN-01/03/05/07 | new Edge Function (alpha.6.0): actions preview / request / cancel / issue_transfer / claim_transfer; `ip_hash` = SHA-256("lp-f05:"+first X-Forwarded-For); README, main.ts, test.ts, stub, import map | §3 |
| `supabase/functions/approve-member/*` | F05-FN-02/04/06/08 | new Edge Function (alpha.6.0) | §3 |
| `join/flow.js` | F05-JOIN-02 | new: the shared join screens (`window.LPJoin.mount`) used by `/join/` and by the app | §1.1–1.3, 1.6 |
| `join/index.html` | F05-JOIN-01 | `JOIN_FEATURE='on'`: reads `#code=`, keeps it in `sessionStorage['lp:join_code']`, strips the hash (as before), anonymous sign-in, mounts `flow.js`; "פתיחת הטיול" writes `pt:_device:active_trip` and opens `../app/`. `'off'` = the F04 page, no network. `[hidden]` rule added. | §1.1 |
| `app/index.html` flags script | F05-FLAG-01 | new `const JOIN_FEATURE='on'` (after `SWITCH_FEATURE`) | §1 |
| `app/index.html` new style + script block after the F20 block | F05-UI-01 | all F05 app UI: F05-GATE-02 (not-connected screen), F05-HOME-01 (pending card), F05-NAME-01 ("מי אני"), F05-MEMBERS-01 (USERS refill). Returns on its first line when `JOIN_FEATURE!=='on'` or not cloud. Exposes only frozen `window.__ptF05 = {version, attach, gateCard}` | §1.4, 1.5, 1.7 |
| `app/index.html` gate `showCard` | F05-GATECARD-01 | **one new line** after the F04 gateCard line: `if(window.__ptF05)window.__ptF05.gateCard(g);` | §1.4 |
| `app/index.html` gate, before the F03 bridge | F05-GATE-01 | new lines only: `window.__ptF05.attach({endpoint, approveEndpoint, key, withTimeout, timeoutMs, client, uid, ensureSession, enterTrip, started, tripId, role})` | §1.4 |
| `app/index.html` F04 `done()` | F05-DONE-01 | **existing line**: the F04 "בקרוב · דף ההצטרפות נפתח בגרסה הבאה (F05)" card is rendered only when `JOIN_FEATURE!=='on'` | — |
| `app/index.html` `PT_VERSION`, `APP_VERSION` | F05-VER-02 / -01 | `'3.0.0-alpha.5.1'` → `'3.0.0-alpha.6'` | DoD |
| `scripts/dev/f05_db_check.py`, `f05_static_check.py`, `f05_smoke.py`, `deno_test_node.mjs` | F05-DEV* | dev self-checks (below) | — |

Lines removed/changed in `app/index.html` vs `main`: exactly **3** (`PT_VERSION`, `APP_VERSION`, the F04 done "בקרוב" card line).
Everything else is additive. Protected functions byte-identical (379 / 4613 / 3427 / 178 / 9277 / 517 / 309 bytes).

## 2. Runtime hooks (new code touching existing behaviour)
- `window.openUserModal` is **wrapped** right after the main script runs (a MutationObserver microtask on `<html class>`,
  before the main script's async boot reaches `setupUsers()`): it never opens the picker in cloud mode; with no name yet it
  loads the member's name; when a name is set it says "השם שלך בטיול נקבע לפי החברות בקבוצה: <name>" (toast) instead.
  The original function body is unchanged (kept as `.__orig`).
- `activeUser` is assigned (global `let`), and the trip's `KEYS.user` (namespaced `pt:<trip>:vietnam_planner_user_v1`)
  is written with the member's `display_name`; `render()` is called when it changed.
- `USERS` (the `const` array) is **refilled in place** (`length=0` + push) with the active members ordered by `joined_at`;
  cached per trip in the namespaced key `pt_members`. Its declaration is unchanged.
- Realtime: the app subscribes to `trip_members` `trip_id=eq.<trip>` (channel `pt5-members-<trip>`); `/join/` subscribes to
  `id=eq.<member>` (channel `lpj-<member>`). Both also poll (app 60 s when visible; join page 20 s) and refresh on
  `visibilitychange`/`online`.

## 3. Flags
| Flag | Where | Default | `'off'` |
|---|---|---|---|
| `JOIN_FEATURE` | `app/index.html` flags script | `'on'` | alpha.5.1 exactly: no F05 block, gate and done-screen hooks are no-ops |
| `JOIN_FEATURE` | `join/index.html` | `'on'` | the F04 "בקרוב" page, no network, code never read |

## 4. For QA — stable ids and visible texts
**Join flow** (`/join/` and in-app): root `#lpJoin` with `data-screen` ∈ `loading|form|pending|approved|invalid|rejected|removed|error`;
title `#lpjTitle`; form `#lpjName` (maxlength 40), `#lpjSubmit` "בקשת הצטרפות", error `#lpjNameErr` (role=alert), help
`#lpjNameHelp`; pending: pill "ממתין לאישור · <name>", `#lpjCancel` "ביטול הבקשה"; approved: `#lpjOpen` ("פתיחת הטיול", or
"לא עכשיו – פתיחת הטיול כאן" on iPhone Safari), iPhone only `#lpjTransfer` with `#lpjCode` ("482 916" format) and `#lpjCopy`;
rejected: `#lpjAgain` "בקשה חדשה"; error: `#lpjRetry`; in-app back: `#lpjBack`; toast `#lpjToast` (role=status).
Texts: invalid "הקישור כבר לא פעיל"; name taken `יש כבר "<n>" בטיול. אפשר להוסיף אות או שם משפחה, למשל "<n> ל".`;
removed "הוסרת מהטיול"; rejected "הבקשה לא אושרה".
iPhone detection: UA `iPad|iPhone|iPod`, or `MacIntel` + touch; "standalone" = `navigator.standalone` or
`(display-mode: standalone)`.

**App not-connected** (`#ptGate.pt-gate-f05`): `#ptF05Transfer` (h2 `#ptF05Title` "כמעט שם"), digits `#ptF05Otp0…5`
(`inputmode=numeric`; a whole code typed/pasted into box 0 is spread), `#ptF05Err` (role=alert), `#ptF05Claim` "כניסה לטיול"
(disabled until 6 digits); `#ptF05Others` "דרכים אחרות"; `#ptF05Alt` → `#ptF05LinkBtn` (aria-expanded) → `#ptF05LinkBox`
`#ptF05LinkIn`, `#ptF05LinkErr`, `#ptF05LinkGo` "המשך" → the join flow mounts in `#ptF05Join` (gate gets `pt-f05-joining`).
Then the F04 `#ptGateInvite` card and the F02 device-code card (`#ptDeviceCode`) last.

**Manager home card**: `#ptF05Pending` (title `#ptF05PTitle` "ממתינים לאישור · N", "רק מנהלים רואים"); rows `.pt5-req[data-member]`;
role buttons `[data-role=viewer|editor|manager]` with `aria-pressed`; `[data-act=approve]` "אישור כ<צופה|עורך|מנהל>",
`[data-act=reject]` "דחייה" → `[data-act=reject-yes]` "כן, לדחות" / `[data-act=reject-no]` "ביטול"; collapsed rows
`[data-open]` "פתיחה"; offline note "אין חיבור – אפשר לאשר כשהרשת תחזור." Toast `#ptF05Toast`: "<name> הצטרף/ה כ<role>",
"הבקשה נדחתה", "הבקשה כבר טופלה".

Function endpoints: `<SUPABASE_URL>/functions/v1/join-trip`, `/functions/v1/approve-member`, headers `apikey` +
`Authorization: Bearer <session access_token>`.

## 5. Local checks (sandbox; no Deno binary, package registries blocked)
- `sudo -u postgres python3 scripts/dev/f05_db_check.py ""` → qa.f01–f04 109/37/49/90, F05 scenarios **51/51**, 0 leftovers.
- `node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/join-trip/test.ts supabase/functions/approve-member/test.ts` → **14/14** (the same runner passes create-trip's own tests with `--experimental-transform-types`).
- `python3 scripts/dev/f05_static_check.py origin/main` → all inline scripts `node --check` OK, no new duplicate ids, protected functions identical, 3 changed lines.
- `python3 scripts/dev/f05_smoke.py` (Playwright, fake supabase-js, 390px) → **28/28**: join → pending → manager approves as viewer on home → joiner opens → trip starts with "מי אני" = name; iPhone transfer code → installed app claims it; invalid code; in-app pasted link; USERS refill; no page errors.

## 6. Known limits / notes
- Rate limits are per database identity + IP hash; an attacker creating many anonymous identities is limited by the IP
  limits and by Supabase's own anonymous sign-in limit (30/h/IP by default). Turnstile deferred (D4).
- 6-digit transfer codes: 10⁶ space, 24 h, single use, ≤5 failed claims/identity/hour and ≤20/IP/hour.
- `join_attempts` cleanup is opportunistic (≈5% of previews delete rows older than 7 days).
