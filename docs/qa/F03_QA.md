# F03 · QA report — super-admin invites a manager

Version: app 3.0.0-alpha.3.4 · invite-manager 3.0.0-alpha.3.7 · DB 0008/0009 · 2026-10-12.
CHANGE 2026-10-12 F03-QA-01: first version of this report.

## Automated
| Suite | Result |
|---|---|
| F03 browser suite (tests/f03, Playwright 390×844, written by the QA team from the spec only) | 58 passed, 1 skipped |
| F02 regression, ADMIN_FEATURE=on / off | 37/37 each (+1 DB-only skip) |
| invite-manager Deno tests (supabase/functions/invite-manager/test.ts) | 18/18 |
| DB `qa.f03_run()` on plan-travel | 49/49, nothing left behind |
| DB regression `qa.f01_run()` / `qa.f02_run()` | 109/109 · 37/37 |
| Supabase advisors | no new issues; expected note: `admin_trip_summary` is security definer and refuses non-admins |

Regression tests added for every defect found on the phone: invite link while the app is open (hash change,
`?invite=1`, launchQueue), percent-encoded hash, `/invite/` page outcomes, subject encoding round-trip, SMTP dialogue.

## On Or's phone (2026-10-09 → 2026-10-12)
- [x] Link email to the phone identity — same user id, trip membership kept.
- [x] "ניהול מערכת" appears only after being registered as platform admin.
- [x] Create invite → email arrives, correct Hebrew subject, designed RTL layout.
- [x] Resend → new email, old link shows "הקישור כבר לא בתוקף"; send count and expiry update.
- [x] Revoke → link stops working; "הקישור נפתח" date recorded.
- [x] Button in the email opens the invite page directly ("ההזמנה שלך אומתה").

## Defects found and fixed
| # | Found | Cause | Fix |
|---|---|---|---|
| 1 | Link email showed "אין חיבור" | Gmail refused the SMTP password; 5xx mapped to "offline" | new app password; 5xx → sending-failed text |
| 2 | Invite email arrived as raw MIME | denomailer broke the Hebrew subject header | own MIME + SMTP client |
| 3 | Button did nothing with the app open | installed app captured the link | `/invite/` page outside the app scope (+ reload / launchQueue in the app) |
| 4 | Button not a link at all | `APP_URL` secret was `ttps://…` | secret fixed; code hardening planned for F04 |
