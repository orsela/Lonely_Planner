# F21 — Anyone can request to open a trip; the super-admin approves · spec

<!-- CHANGE 2026-10-26 F21-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.8** (app + new `/request/` page), migration **0016_f21.sql** (+ QA harness **0017**), new
Edge Function **`request-trip`** (alpha.8.0), additive changes to **`invite-manager`** and **`create-trip`** (alpha.8.0).
Mockup approved by Or 2026-10-26: canvas https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, **row 9** (14 artboards
`F21_*`). Decisions D1–D17: project doc `claude/Plan_Travel_F21_decisions.md`.

User value: a family that heard about Lonely Planner opens one link Or shared, says where and when, verifies its email and
is done. Or sees the request in "ניהול מערכת" and approves with one tap; the approval is the normal F03 manager invite,
already filled with what they asked for. Nobody waits for Or to type an email address, and nothing reaches Or by mail.

Base: `main` at 3.0.0-alpha.7.1 + QA-DEBT (d148d74). Branch `f21`. Push rule (INDEX): the app and `/request/` stay on `f21`
until the migration and the functions are deployed. Reuses F04-HOME §3.1 (in-app browser hop) and §3.3 (code-screen resume).
The live project `vietnam-trip-2026` is never touched.

## 0. Decisions

| # | Decision |
|---|---|
| D1 (Or) | Email verified with **our own 6-digit code** (hash in `private`, sent by our SMTP like `invite-manager`) — not Supabase Auth OTP. A rejected requester never exists in Auth. Only verified requests reach the admin. The F04 wizard verifies the email again, as today. |
| D2 (Or) | **Turnstile on the request form only** + database rate limits. `/join/` unchanged. |
| D3 (Or) | Separate page **`/request/`** (outside the PWA scope, like `/invite/` and `/join/`). |
| D4 (Or) | On every reject the admin chooses whether to send a polite email. |
| D5 (Or) | Rejected requests and unverified requests are deleted after 5 days. A verified pending request stays until Or handles it. |
| D6 (Or) | Email that already manages a trip or has an active invite → reaches the admin **with a marker**. An existing manager may request another trip. |
| D7 (Or) | "When" = month + year over the next 18 months, or "עוד לא יודעים". Exact dates are chosen in the wizard. |
| D8 (Or) | Fields: where (countries from `countries.json`), when, email, requester name, approximate number of travellers, short free note. |
| D9 (Or) | `/request/` is **bilingual** (Hebrew / English), language switch at the top-right corner in both languages. The request's language is stored; code and reject emails use it. Wizard and app stay Hebrew until F13. |
| D10 (Or) | **Daily cap of 50 F21 emails** (code emails incl. resends + reject emails, together). At the cap the form says "נסו שוב מחר"; F03 invites and F04 Auth OTP always keep headroom. No separate Gmail account. |
| D11 (Or) | English requester: (a) the form says before sending that the app is in Hebrew for now; (b) the invite email sent on approval is in the request's language — `invite-manager` gets an English template. |
| D12 (Or) | Approving when the same email has an active invite: the old invite is **revoked** and a new one is sent, linked to the request and pre-filled (bypasses `invite_exists` only on this path). |
| D13 (Or) | Entry point: **direct link only** (Or shares it). No buttons on the gate or `/join/`. |
| D14–D15 (Or) | Shipped in F04-HOME; `/request/` reuses the in-app hop, the code-screen resume and the code-in-subject email. |
| D16 (Or) | `draft_name` is generated **in the request's language** (e.g. "Portugal"); the admin may edit it before approving. |
| D17 (Or) | "נסו שוב מחר" appears **only after tapping send** (and on a code resend), never on opening the form. |
| C1 (Claude) | Approve / reject are new **admin actions in `invite-manager`** (it already has the admin check, invite creation, SMTP and the templates). `request-trip` is public (no identity) and handles start / verify / resend only. |
| C2 (Claude) | Invite emails sent on approval are **not** counted in the D10 cap and are never blocked by it (they are F03 invites). Reject mails are counted; at the cap a reject still succeeds, without mail. |
| C3 (Claude) | Day boundary for the cap and the per-day limits = calendar day in `Asia/Jerusalem`. |
| C4 (Claude) | The form answers identically whether or not the email is known (no account enumeration); the D6 marker is admin-only. |
| C5 (Claude) | Cleanup (D5) is opportunistic: every `request-trip` call and every admin list load runs `private.f21_cleanup()`. No pg_cron. |

Out of scope: an English wizard/app (F13); a status page for the requester; any notification to Or outside the app; entry
buttons elsewhere (D13); changes to `/join/`.

## 1. Screens (390px, touch ≥44px; `/request/` bilingual RTL/LTR; app screens Hebrew RTL with the F03/F20 `pt-*` styles)

Flags: `REQUEST_FEATURE='on'|'off'` in the app (next to `HOME_INSTALL_FEATURE`) and a same-named constant in `/request/`.
App `'off'` = exactly alpha.7.1 (no requests tab, no badge). `/request/` `'off'` = a single neutral card "הבקשות סגורות כרגע /
Requests are closed right now" (no network). Mockup annotations (the small grey lines explaining the design) are **not**
shipped unless listed below.

### 1.0 `/request/` page frame
- Language: `?lang=he|en` or `#lang=` from the link → else stored choice `pt:_device:rq_lang` → else `he` if
  `navigator.languages` contains a Hebrew tag, else `en`. Switch = segmented "עב / EN" at the top-right in both languages
  (`aria-pressed`); switching re-renders in place, keeps typed values, flips `dir`, stores the choice.
- Brand "Lonely Planner"; no trip chrome. No supabase-js and no session: plain `fetch` to `request-trip` with the anon
  `apikey`. Nothing secret in the URL.

### 1.1 In-app browser (artboard `F21_InApp`)
Same detection and hop as F04-HOME §3.1, copied into `/request/` (marked `CHANGE … F21-REQ-…, copy of /invite/ inApp()`):
- iPhone: "פתיחה בספארי / Open in Safari" → `x-safari-https://<host>/…/request/?lang=<l>`; manual 2 steps under it.
- Android: one automatic `intent://<host>/…/request/?lang=<l>#Intent;scheme=https;package=com.android.chrome;end` per load,
  fallback button.
- New vs `/invite/`: an outline button "להמשיך כאן בכל זאת / Continue here anyway" → the form (state kept in memory).
- Shown before the form only; once the user chose "continue here" it is not shown again in this page load.

### 1.2 Form (artboards `F21_Request`, `F21_RequestEN`)
Green header "רוצים להקים טיול? / Want to plan a trip?" + one line. Card fields, in order:
1. Name — 1–40 chars after trim (`maxlength=40`).
2. Email — `type=email`, LTR, normalized (trim, lower); help "נשלח אליו קוד אימות בן 6 ספרות."
3. Where — chips + type-ahead over `../app/countries.json` (names in the page language, matching `he`/`en` and the code;
   popular first); 1–10 countries; chip × removes (`aria-label`).
4. When — `<select>` of the next **18 months** starting with the current month (C3 calendar), labels "אפריל 2027 / April
   2027"; checkbox "עוד לא יודעים / Not sure yet" disables the select (sends `month:null`).
5. Travellers — stepper − / + , 1–30, default 2.
6. Note — optional, ≤200 chars, live counter.
7. **English only (D11a):** info box "Good to know: the trip app is in Hebrew for now. Emails about your request, including
   your invitation, will be in English."
8. Turnstile widget (managed mode, `language` = page language).
9. Button "שליחת קוד אימות / Send verification code" → `request-trip` `start`.
Under the card the privacy line (HE/EN as in the artboards): email used only for this request, never shown; declined or
unverified requests are deleted after 5 days.

Validation is inline (red field + one line); the button stays enabled and focuses the first invalid field. Result mapping:
`daily_limit` → 1.4 (D17); `rate_limited` → toast "יותר מדי בקשות היום. נסו שוב מחר. / Too many requests today. Please try
again tomorrow."; `turnstile_failed` → toast + widget reset; `invalid_request` with field → inline; offline → toast "אין
חיבור. נסו שוב כשהרשת תחזור." keeping all values; other → "משהו השתבש. נסו שוב.".

### 1.3 Code (artboard `F21_Code`)
"בדקו את המייל / Check your email", the address (LTR), six digit boxes (LTR, `inputmode=numeric`, first box
`autocomplete=one-time-code`, paste/autofill of 6 digits — spaces ignored — fills all), help "הקוד בתוקף 10 דקות. הדבקה
ממלאת את כל התיבות." + "יצאתם לבדוק את המייל? חוזרים לאותו קישור – הדף זוכר אתכם ולא שולח קוד חדש.", the notification
illustration card (F04-HOME 1.4 wording adapted: "<code> – קוד האימות לבקשה ב-Lonely Planner"), links "שליחה חוזרת בעוד
m:ss" (60 s cooldown from `sentAt`) · "תיקון המייל" (back to the form, values kept in memory; clears the resume key), footer
"רק אחרי האימות הבקשה נשלחת לאישור. לא הגיע? בדקו בתיקיית הספאם.", button "אימות ושליחת הבקשה / Verify and send".
- Resume (F04-HOME §3.3 pattern): on a successful `start`/`resend` write `pt:_device:rq_resume` =
  `{request_id, email, sentAt, lang, v:1}`; on page load a valid entry (< 10 min) → this screen directly, with the F04-HOME
  resumed banner ("חזרת לדף – הקוד ששלחנו לפני N דקות עדיין תקף."), **no send**. Never stores the code. Cleared on verify
  success, "תיקון המייל", TTL, `code_locked`.
- Errors: `code_wrong` → red boxes + "הקוד שגוי. נשארו N ניסיונות."; `code_expired` → "הקוד פג. שלחו קוד חדש." (resend
  enabled); `code_locked` (5 wrong) → "יותר מדי ניסיונות. מתחילים מחדש." → form with values if in memory; resend →
  `daily_limit` → 1.4.

### 1.4 Daily cap (artboard `F21_Limit`) — D10 + D17
Clock icon, "נסו שוב מחר / Please try again tomorrow", the line and the two ticks of the artboard, outline button "חזרה
לטופס / Back to the form" (values kept). Reached only from `start`/`resend` returning `daily_limit`.

### 1.5 Sent (artboard `F21_Sent`)
✓, "הבקשה נשלחה / Your request was sent", "אין צורך לחכות במסך הזה. התשובה תגיע למייל.", summary card (where with flags,
when or "עוד לא יודעים", travellers, email LTR), "מה עכשיו?" 3 steps (step 3: "בקישור מוסיפים את האפליקציה למסך הבית
ומקימים את הטיול – כשלוש דקות. היעדים והחודש כבר ממולאים מהבקשה."). English texts mirror. Reloading after success shows
the form (nothing stored).

### 1.6 Chooser badge (artboard `F21_Choose`) — app, F20 `#ptChoose`
The "ניהול מערכת" row: sub "בקשות, קבוצות והזמנת מנהלים"; badges "<N> בקשות חדשות" (indigo, N = verified pending requests)
then the existing amber pending-invites badge, text now "<M> הזמנות ממתינות" (was "<M> ממתינות"). Each badge omitted at 0
or on a failed call.

### 1.7 Admin — requests tab (artboard `F21_Admin`) — app, F03/F20 `#admin`
- Segmented control at the top: "בקשות · N" / "קבוצות והזמנות · M" (M = today's card count). Default tab = requests when
  N>0, else groups. The groups tab is today's F03 screen unchanged.
- Mail meter card: "מיילים מהטופס היום" + "<k> מתוך 50" + bar (`role=img` with the same text) + the line "קודי אימות והודעות
  דחייה. בתקרה הטופס מציג "נסו שוב מחר"; הזמנות מנהל וקודי כניסה לא נחסמים."
- Request cards, oldest first: name, relative time of verification, badge **EN** when `lang='en'`, email (LTR), flags +
  country names (Hebrew), "<month> · N מטיילים" or "עוד לא יודעים מתי · N מטיילים", note in a quote box when present.
  Markers (D6, amber card border): "כבר מנהל: <trip names, comma>" and/or "יש הזמנה פעילה · נשלחה dd/mm".
  Primary button label, first match: active invite → "אישור · מחליף את ההזמנה"; already manager → "אישור טיול נוסף";
  `en` → "אישור · מייל באנגלית"; else "אישור". Secondary "דחייה".
- Footnote: "כאן מופיעות רק בקשות שהמייל שלהן אומת. בקשה ממייל שיש לו הזמנה פעילה – אישור מבטל את ההזמנה הישנה ושולח
  חדשה."
- Empty: "אין בקשות חדשות" (muted). Offline: as F03 ("אין חיבור…", actions disabled).

### 1.8 Approve sheet (artboards `F21_Approve`, `F21_ApproveReplace`)
Title "אישור ושליחת הזמנה" (with an active invite: "אישור ושליחת הזמנה חדשה"); line "<name> יקבל/תקבל מייל הזמנה להקמת
הטיול, כמו הזמנת מנהל רגילה (תוקף 7 ימים)."
- Active invite (D12): amber box "יש כבר הזמנה פעילה למייל הזה" + `"<draft name>" · נשלחה dd/mm · בתוקף עד dd/mm. באישור
  היא מבוטלת והקישור הישן מפסיק לעבוד.`
- Input "שם זמני לטיול" pre-filled by D16 (§5.2), ≤80, help "נוצר מהבקשה. <name> יכול/ה לשנות אותו באשף."
- Box "ממולא מראש באשף": שם בקבוצה, יעדים ומטבעות (flags + names), חודש ("<month> (תאריכים בוחרים באשף)" or "עוד לא
  יודעים – בוחרים באשף"), **שפת המייל** ("עברית – כמו הבקשה" / "אנגלית – כמו הבקשה").
- Buttons: "אישור ושליחה אל <email>" (with active invite: "ביטול הישנה ושליחת הזמנה חדשה") and "ביטול".
- Results: ok → toast "ההזמנה נשלחה ל-<email>", the card leaves the list, the groups tab gains the pending invite;
  `email_failed` → toast "המייל לא נשלח. שום דבר לא השתנה – נסו שוב."; `request_closed` → toast "הבקשה כבר טופלה" + refresh.

### 1.9 Reject sheet (artboard `F21_Reject`)
"לדחות את הבקשה של <name>?", "הבקשה יורדת מהרשימה ונמחקת אחרי 5 ימים.", checkbox (checked by default) "לשלוח הודעה
מנומסת במייל" + "בשפת הבקשה (כאן: <עברית|אנגלית>)", preview of the mail text in that language (§5.1), red "דחייה",
"ביטול". When the meter is at the cap: checkbox disabled and unchecked with "התקרה היומית מלאה – הדחייה תהיה בלי מייל".
Result `mail_skipped:'daily_limit'` → toast "הבקשה נדחתה, בלי מייל (התקרה היומית מלאה)".

### 1.10 Emails (artboards `F21_CodeEmail`, `F21_InviteEmailEN`)
- Code email (`request-trip`): subject "<6 digits> – קוד האימות לבקשה ב-Lonely Planner" / "<6 digits> – your Lonely
  Planner verification code" (digits without a space; the artboard's space is cosmetic); body as `H_Email` with "קוד
  האימות לבקשה שלך:", the code in large monospace, "חוזרים לדף הבקשה ומקלידים את הקוד. הוא תקף 10 דקות.", ignore line.
  **No link.** HTML + plain text, `dir` per language.
- English invite email (`invite-manager`, D11b): subject "Your trip request was approved", body as the artboard (greeting by
  requester name, approved line, trip name, button "Accept and set up the trip" → the same `/invite/` link as F03, the
  Hebrew-for-now note, validity line with dd/mm/yyyy, footer). LTR. Same link builder as the Hebrew template.
- Reject email (§5.1).
- From name "Lonely Planner" (as F04-NAME-01).

### 1.11 Wizard pre-fill (artboard `F21_WizardPrefill`) — app, F04 wizard
When `lookup` returns `prefill`: step 1 shows the green box "מילאנו מה שכתבת בבקשה, כולל היעדים בשלב 2. נשאר לבחור
תאריכים.", trip name = draft name (today), "השם שלך בקבוצה" = requester name, tag "מהבקשה" on pre-filled fields, the date
picker opens on the requested month (current month when null); step 2 starts with the requested countries selected
(currencies derived exactly as when the user picks them). Everything stays editable. Without `prefill` → today's wizard.

## 2. Data — migration 0016_f21.sql (Or runs it in the SQL Editor; Claude verifies by reading)

1. `private.trip_requests` — `id uuid pk default gen_random_uuid()`, `lang text not null check in ('he','en')`, `name
   text not null check (char_length between 1 and 40)`, `email text not null check (email = lower(email))`, `countries
   text[] not null check (cardinality between 1 and 10)` (each `^[A-Z]{2}$`), `month date null check (extract(day)=1)`,
   `travellers smallint not null check between 1 and 30`, `note text null check (char_length <= 200)`, `status text not
   null check in ('unverified','pending','approved','rejected')`, `code_hash text`, `code_expires_at timestamptz`,
   `code_attempts smallint not null default 0`, `code_sent_at timestamptz`, `resend_count smallint not null default 0`,
   `ip_hash text`, `verified_at`, `decided_at timestamptz`, `decided_by uuid`, `reject_mailed boolean`, `invite_id uuid →
   public.manager_invites(id) on delete set null`, `created_at timestamptz not null default now()`. Indexes: `(status,
   verified_at)`, `(email, created_at)`. RLS on, **no policies**.
2. `private.request_attempts` — `id bigint identity pk`, `kind text check in ('start','verify','resend')`, `email_hash
   text`, `ip_hash text`, `request_id uuid`, `ok boolean`, `at timestamptz default now()`; indexes `(kind, email_hash, at)`,
   `(kind, ip_hash, at)`. RLS on, no policies.
3. `private.mail_log` — `id bigint identity pk`, `kind text check in ('code','reject')`, `at timestamptz default now()`;
   index `(at)`. RLS on, no policies. Counted by `private.f21_mail_today()` (C3 day).
4. `public.manager_invites` add: `request_id uuid null → private.trip_requests(id) on delete set null`, `lang text not
   null default 'he' check in ('he','en')`. Existing rows = `he`. No other change to the table, its policies or grants.
5. `private.f21_cleanup()` — deletes `rejected` with `decided_at < now()-5d`, `unverified` with `created_at < now()-5d`,
   attempts and mail_log older than 7 days.
6. Service-role-only functions (security definer, `set search_path=''`, F05 pattern, refusals **returned** as
   `{"error":code}`):
   - `request_start(p_request uuid, p_payload jsonb, p_email_hash text, p_ip text, p_code_hash text)` — validates, applies limits
     (§4), cap, deletes earlier `unverified` rows of the same email, inserts `unverified` with the code hash (10 min),
     logs a `code` mail, returns `{request_id}`.
   - `request_verify(p_request uuid, p_code_hash text, p_ip text)` → `pending` + `verified_at`, clears the code; or
     `code_wrong {attempts_left}` / `code_expired` / `code_locked` / `request_unknown`.
   - `request_resend(p_request uuid, p_code_hash text)` — cooldown 60 s, ≤3 resends, cap; replaces the hash.
   - `request_approve(p_admin uuid, p_request uuid, p_token_hash text, p_draft text, p_inviter text)` — in one
     transaction: request must be `pending` (else `request_closed`); revoke any active invite for that email (returns its
     id); insert the new invite (`request_id`, `lang`, `draft_name`, 7 days, F03 columns); request → `approved`,
     `invite_id`, `decided_*`. Returns `{invite_id, expires_at, revoked_invite_id}`.
   - `request_approve_undo(p_invite uuid, p_revoked uuid, p_request uuid)` — used only when the email fails: delete the
     new invite, clear `revoked_at` on the revoked one, request back to `pending`.
   - `request_reject(p_admin uuid, p_request uuid, p_mail boolean)` → `rejected`; when `p_mail` and under the cap logs a
     `reject` mail and returns `{mail:true, lang, email, name}`, else `{mail:false, reason}`.
7. Admin RPC `public.admin_trip_requests()` → jsonb, `security definer`, executable by `authenticated`, raises
   `not_platform_admin` unless `is_platform_admin()` (F03 pattern). Runs cleanup, then returns `{cap:50, mail_today,
   requests:[{id, lang, name, email, countries, month, travellers, note, verified_at, manages:[trip names of active
   manager memberships of a user whose auth email = email], active_invite:{id, draft_name, last_sent_at, expires_at} |
   null}]}` for `pending` rows only. Never returns code hashes, ip hashes or rejected/unverified rows.
8. `find_invite_for_email` (replace, same signature): adds `prefill` when the invite has `request_id`: `{name, countries,
   month, lang}`; unchanged output otherwise.
9. Grants: every new function `revoke all … from public, anon, authenticated` and `grant execute … to service_role`, except
   `admin_trip_requests` (+ `authenticated`). `public` keeps exactly the 9 F01 tables.
10. QA harness `0017_qa_f21_harness.sql`: `qa.f21_run()` in the locked `qa` schema, rolled back, F01–F06 pattern.

## 3. Edge Functions (Claude deploys; `verify_jwt=false`)

### 3.1 `request-trip` (new) — public, no identity
Body `{action, …}`; CORS for `https://orsela.github.io` and `http://localhost:*`. `ip_hash` = SHA-256 of the first
`x-forwarded-for` address; `email_hash` = SHA-256 of the normalized email. Code = 6 random digits (crypto), stored as
SHA-256(request_id ‖ code); the function creates the request id itself (`crypto.randomUUID()`) before calling
`request_start`, so the stored hash can include it.
- `start {lang, name, email, countries, month, travellers, note, turnstile_token}` → Turnstile `siteverify` with secret
  `TURNSTILE_SECRET` and the remote IP; must succeed and `hostname` must be `orsela.github.io` (or `localhost` when
  `TURNSTILE_ALLOW_LOCALHOST=1`) → `request_start` → send the code email (§1.10) → `{ok:true, request_id, sent_at}`. If
  the email fails: delete the row, `{ok:false, code:'email_failed'}` (the `code` mail log row is removed with it).
- `verify {request_id, code}` → `request_verify`.
- `resend {request_id}` → new code → `request_resend` → email.
- Same success shape whatever the email's history (C4). Logs: one JSON line per request with action, status and error
  code only — never email, name, note, code or token. Version header `alpha.8.0`.
- Imports the MIME + SMTP helpers from `../invite-manager/index.ts` (no copy; deploy includes that file).
- Secrets: existing `GMAIL_USER`, `GMAIL_APP_PASSWORD` + new `TURNSTILE_SECRET` (Or enters it in the dashboard).

### 3.2 `invite-manager` (additive, alpha.8.0)
- New admin actions (same `requireAdmin`): `approve_request {request_id, draft_name}` → token → `request_approve` →
  render the invite in the invite's `lang` → send; on send failure `request_approve_undo` and `email_failed`.
  `reject_request {request_id, send_mail}` → `request_reject` → when `mail:true` send the reject email (failure →
  `{ok:true, mail_skipped:'email_failed'}`, the reject stands).
- `renderInviteEmail` gains an optional `lang` (default `he` = today's output byte-identical); `en` = §1.10.
  `resend` uses the invite's stored `lang`. `create` (F03 sheet) unchanged (`he`).
- `create` keeps `invite_exists` (D12 is approval-only).

### 3.3 `create-trip` (additive, alpha.8.0)
`lookup` passes `prefill` through from `find_invite_for_email`. `create` unchanged (the wizard sends what the user
confirmed).

## 4. Limits (D2, D10)
- start: ≤3 per email per day, ≤10 per IP per day (counted ok or not); verified-pending queue ≤100 rows (beyond →
  `daily_limit`).
- verify: ≤5 wrong codes per request (then `code_locked`, the row is deleted); ≤20 wrong per IP per hour → `rate_limited`.
- resend: ≥60 s after the previous send, ≤3 per request.
- Cap: 50 F21 mails per day (`code` + `reject`), checked before every code send and every reject mail.

## 5. Texts and names

### 5.1 Reject email
HE — subject "הבקשה שלך ל-Lonely Planner"; body "תודה על ההתעניינות ב-Lonely Planner. כרגע לא נוכל לפתוח את הטיול שלך.
אפשר לשלוח בקשה חדשה בעתיד." EN — subject "Your Lonely Planner request"; body as the artboard. No links, no reason.

### 5.2 D16 draft name (client, approve sheet)
`<names> · <month>` in the request's language: first two countries (`countries.json` `he`/`en`) joined with " ו" / " & ",
plus " ועוד N" / " +N" when more; " · <month name year>" when a month exists. Cut to 80 chars.

## 6. Acceptance criteria
1. Flags off → app = alpha.7.1 (F02–F06/F20/F04-HOME suites pass except version pins); `/request/` off → the closed card,
   no network.
2. `/request/` language: `?lang=en` → English LTR; switch keeps typed values; choice remembered; Hebrew device → HE.
3. In-app UA (as F04-HOME criterion 2) → 1.1; iPhone button → `x-safari-https://…/request/?lang=…`; Android one automatic
   `intent://` hop; "continue here" shows the form.
4. Form validation: each field's bounds (name 0/41, bad email, 0 or 11 countries, month outside 18 months, travellers 0/31,
   note 201) → inline error, no call. English form shows the D11a box; Hebrew does not.
5. Turnstile: failing test key → `turnstile_failed`, no row, no mail; passing key → row `unverified` + one code email in
   the page language with the code in the subject and no link.
6. Verify: right code → `pending`; wrong → `code_wrong` with attempts left; 5 wrong → `code_locked`, row gone; after 10
   min → `code_expired`; resend before 60 s refused, 4th resend refused, a resend kills the previous code.
7. Resume: reload within 10 min → code screen, banner, no send (network log); after "תיקון המייל"/success/TTL → key gone;
   the key never holds the code.
8. Limits: 4th start for one email in a day, 11th per IP → `rate_limited`; 21st wrong verify per IP per hour →
   `rate_limited`.
9. Cap: with 50 `mail_log` rows today, `start` and `resend` → `daily_limit` → 1.4 (never shown on page load); reject with
   mail → succeeds with `mail_skipped:'daily_limit'`; an F03 `create` and an approval still send.
10. C4: the `start` response for a manager's email equals the one for a new email (shape and status).
11. Admin: requests tab only for the super-admin; list shows only verified pending requests, oldest first; badges EN /
    "כבר מנהל: …" / "יש הזמנה פעילה · נשלחה dd/mm" correct; the button label rule of 1.7; the meter equals today's
    `mail_log` count; chooser badges show N requests and M pending invites.
12. Approve (no invite): one new invite with `request_id`, `lang` and the edited draft name; request `approved`; one email
    in the request language (English template for `en`, today's Hebrew template byte-identical for `he`); the link opens
    `/invite/` as F03/F04-HOME.
13. Approve with an active invite (D12): old invite `revoked_at` set and its link checks invalid; new invite active; exactly
    one active invite for the email afterwards.
14. Email failure on approve → no new invite, the old invite active again, request still `pending`.
15. Reject with/without mail: request `rejected`; mail in the request language only when chosen; after 5 days (simulated)
    the row is gone, as is a 5-day-old unverified row; a verified pending row older than 5 days stays.
16. Wizard pre-fill: lookup for the approved email returns `prefill`; step 1 shows the box, the name, the requested month;
    step 2 starts with the requested countries and their currencies; an invite without a request → today's wizard.
17. Security: `trip_requests`, `request_attempts`, `mail_log` unreadable/unwritable by `anon`/`authenticated`;
    `admin_trip_requests()` → `not_platform_admin` for anyone else; new `invite-manager` actions refuse non-admins; no new
    policies or grants on existing tables (`qa.f21_run()`); logs carry no email/name/code.
18. 390px: no horizontal scroll on all 14 artboards' screens; RTL/LTR per language; touch ≥44px; emails, codes and URLs LTR.
19. Offline: `/request/` keeps values and shows the offline toast; the admin requests tab follows F03 offline behaviour.
20. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`,
    `SEED_DATA`, `stayBlock`, `bookingUrl`); `APP_VERSION`/`PT_VERSION` = 3.0.0-alpha.8; `/request/` version comment
    alpha.8; functions `alpha.8.0`; every change marked `CHANGE 2026-10-2x F21-…` with what changed from alpha.7.1;
    `node --check` on all script blocks; no duplicate ids; Supabase advisors: no new warning.

## 7. Deployment (one step at a time, Or confirms each)
1. Or: free Cloudflare account → Turnstile → add widget for `orsela.github.io` (managed) → sends Claude the **site key**
   (public; Claude puts it in `/request/`) and enters the **secret key** as Supabase secret `TURNSTILE_SECRET`.
2. Or runs `0016_f21.sql`, then `0017_qa_f21_harness.sql`; Claude verifies (`qa.f01–f06_run()` + `qa.f21_run()`).
3. Claude deploys `request-trip`, then `invite-manager` and `create-trip` (alpha.8.0); F03/F04 function tests re-run first.
4. Claude merges `f21` → `main` (app + `/request/`).
5. Phone check (Or, Android): open `/request/` from WhatsApp → request in Hebrew with a second address → code from the
   notification → "נשלחה"; the chooser shows "1 בקשות חדשות" → approve → invite mail → `/invite/` → wizard pre-filled.
   Second run in English with another address → reject with mail → English reject mail. Once: approve for an email with
   an active invite → old link invalid.
6. Claude: architecture doc — "מחוץ לתחום: הרשמה עצמית של מנהלים" reworded to "בקשה פתוחה + אישור סופר-אדמין (F21)";
   Backlog F21 → "הושלם" after the phone check.

## 8. Test strategy
- Functions: node-run Deno tests (`scripts/dev/deno_test_node.mjs`) with stubbed RPCs, SMTP and `siteverify`
  (Cloudflare's documented always-pass / always-fail test keys for the browser tests).
- DB: `qa.f21_run()` for §2 constraints, limits, cap, D12 transaction, undo, cleanup, grants.
- Client: Playwright 390×844, both languages, both flag states, F02 fake supabase-js extended with
  `rpc('admin_trip_requests')` and route-intercepted `request-trip` / `invite-manager` / `create-trip`.
- Separate dev and QA agents from this spec; QA does not read the implementation.
