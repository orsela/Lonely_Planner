# F23 — Open trip request without approval + AI destination ideas · spec

<!-- CHANGE 2026-11-13 F23-DOCS-01: new file (no previous version). Source: user feedback 2026-11-09,
     decisions claude/Plan_Travel_Feedback_2026-11-09_decisions.md, mockup row 17 approved by Or 2026-11-13. -->
<!-- CHANGE 2026-11-13 F23-DOCS-02: what changed from the previous version: Or set the order (F23 now, before F07 →
     target alpha.12, F07 moves to alpha.13) and approved the AI cost with a lower cap (30 calls/day instead of 100). -->
<!-- CHANGE 2026-11-13 F23-DOCS-03: what changed from the previous version: copied into the repo from the project doc
     claude/Plan_Travel_F23_spec.md, + decisions D7–D9 (Or, 2026-11-13, after the server stage). Nothing else changed. -->

Version target: **3.0.0-alpha.12** (built before F07, which moves to alpha.13 and rebases on this), pages `/request/` +
app admin screen, migration **0020_f23.sql** (+ QA harness **0021**; independent of F07's reserved 0018/0019), changes to
**`request-trip`** and **`invite-manager`**. Mockup approved by Or 2026-11-13: canvas
https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, **row 17**, artboards `FB_Request`, `FB_Suggest`, `FB_Ready`.

User value: a visitor understands in three lines what Lonely Planner does, gets into setting up a trip right after the
email code (no "if approved" wait), and can start even without a destination: AI suggests three that fit.

Base: `main` at the version current when work starts. Branch **`f23`**. Push rule (INDEX): client code stays on the
branch until the migration and functions are deployed. Flag **`REQUEST_FEATURE`** keeps its meaning (`'off'` = closed);
new flag **`REQUEST_MODE='auto'|'manual'`** (`'manual'` = exactly F21) and **`SUGGEST_FEATURE='on'|'off'`**.

## 0. Decisions (Or, 2026-11-09 / 13)
| # | Decision |
|---|---|
| D1 | Three "what we do / what we don't" lines at the top of `/request/`, Hebrew and English. |
| D2 | **No manual approval.** A verified email is the gate; the requester continues straight to the trip wizard. |
| D3 | "Not decided yet" on "לאן?" → after email verification, **3 AI destination suggestions** to pick from. |
| D4 | (mockup) Suggestions can be refreshed **twice** per request (3 sets max). |
| D5 | (mockup) An invite email with the link is still sent, for those who continue later. |
| D6 | (13/11) Order: F23 now, before F07. AI cost approved with a cap of **30 calls per day**. |
| D7 | (13/11) Hebrew automatic invite email: inviter shown as "Lonely Planner" ("Lonely Planner מזמין אותך לנהל את הטיול …"). |
| D8 | (13/11) English automatic invite email does not say "approved": subject "Your trip is ready to set up", opening "Your email is verified, so your trip is ready to set up.", button "Set up the trip". The admin's approval email (manual mode) keeps the F21 text. |
| D9 | (13/11) A verified request that never got a destination is deleted after **3 days** and is not listed for the admin. Unverified requests keep 5 days. |

## 1. Architect rulings
| # | Ruling |
|---|---|
| C1 | **Auto-approve inside `verify`.** When `REQUEST_MODE='auto'` and the code is correct, `request-trip` runs the same server logic as `invite-manager.approve_request` (shared module, not an HTTP call): creates the manager invite linked to the request (`request_id`, `lang`, prefill), replacing an active invite for that email as in F21 D12. The request gets `status='auto_approved'`. The response returns the **invite token** to this browser only. |
| C2 | **Undecided destination.** If the request has no countries, `verify` returns `next:'suggest'` and does **not** create the invite yet. The invite is created by the `choose` action (C5) with the picked country. |
| C3 | **Continue button** on `FB_Ready` → `/invite/#invite=<token>`. Everything after that is the existing F04/F04-HOME path (in-app browser escape, install, wizard prefilled). Nothing new in the wizard. |
| C4 | **Invite email (D5)** is sent in the request language and **counted** in the F21 daily cap (D10). If the cap is reached, the email is skipped and the screen line "שמרנו גם קישור במייל" is hidden; the flow continues. |
| C5 | **New `request-trip` actions** (public, verify_jwt=false, same request token as `verify`): `suggest {request_id, token}` and `choose {request_id, token, country}`. Both accepted only for a verified request with no countries, within 30 minutes of verification. |
| C6 | **AI call.** `suggest` calls the Anthropic Messages API from the function (secret **`ANTHROPIC_API_KEY`**, set by Or in the dashboard; model: the current Haiku-class model, name in a constant). The prompt gets only: month/year or "unknown", traveler count, interest keys, max flight hours from Israel, the free note (≤100 chars, passed as quoted data, never as instructions) and the request language. **No name and no email.** Output: strict JSON, 3 items `{country (ISO-2), reason (≤140 chars), tags (≤3, ≤20 chars each)}`. Each country is checked against `countries.json`; invalid or duplicate items are dropped; previously shown countries are excluded on refresh. Fewer than 3 valid → show what is valid; 0 → fallback C8. |
| C7 | **Limits.** 3 `suggest` calls per request (D4); global **30 calls per Israel calendar day** (constant `SUGGEST_DAILY_CAP=30`, same day rule as F21 C3); 10 s timeout. Counted in `private.request_attempts` (new kind `suggest`). The admin requests screen shows "הצעות AI היום: N מתוך 30" next to the F21 mail counter. |
| C8 | **Fallback.** AI off, over the cap, timeout or 0 valid → `FB_Suggest` shows "אי אפשר להציע יעדים כרגע" + the regular country picker; the flow continues normally. |
| C9 | **Form (`FB_Request`).** "לאן?" gets a segmented choice "יודע/ת לאן" / "✨ עוד לא החלטתי" (default: knows). Undecided shows: interests (6 fixed chips: `nature`, `food`, `beaches`, `cities`, `kids`, `extreme`; at least 1), max flight (`5`/`8`/`any`, default `5`), note (≤100). With `SUGGEST_FEATURE='off'` the segmented choice is hidden. |
| C10 | **Data.** Migration 0020: `private.trip_requests` gains `where_mode text check in ('known','undecided') default 'known'`, `interests text[]`, `max_flight text`, `pref_note text`, `suggestions jsonb` (last shown sets, for the refresh exclusion), `status` gains `'auto_approved'`. Existing cleanup (F21 D5, C5) unchanged; `auto_approved` follows the "handled" path. |
| C11 | **Admin screen ("ניהול מערכת → בקשות").** Auto-approved requests are listed as history with the label "נפתח אוטומטית" and the invite status (F03 derived status). Revoke works as for any invite until it is used. The badge counter counts only requests that still need action (in auto mode: none, so it is hidden). Manual mode = F21 unchanged. |
| C12 | **Copy.** `/request/` subtitle "מקימים כאן טיול משותף ומקבלים אפליקציה אחת לכל המטיילים." + the 3 lines (D1) as in `FB_Request`; English per the approved feedback doc. "הבקשה נשלחה" / "If approved" disappears in auto mode; `FB_Ready` replaces it. Privacy line: "בקשה שהמייל שלה לא אומת נמחקת אחרי 5 ימים". AI disclaimer as in `FB_Suggest`. |
| C13 | **Abuse.** Unchanged gates: Turnstile, 3 requests/email/day, 10/IP/day, 20 wrong codes/IP/hour, 50 form emails/day. Plus: one auto-approval per email per day. Kill switch: `REQUEST_MODE='manual'` or `REQUEST_FEATURE='off'`. |

## 2. Risks (stop and report)
| # | Risk | Plan |
|---|---|---|
| R1 | Anthropic API cost (paid, approved by Or with the 30/day cap). | Haiku-class model + C7 caps. Or supplies the key; nothing is enabled without it (`suggest` → fallback C8). Raising the cap needs Or's approval. |
| R2 | The Connector can't deploy relative imports (INDEX: request-trip was deployed with a shortened copy of invite-manager). | Shared approve logic goes in one file deployed with both functions (`request-trip/main.ts` + `_shared/approve.ts`); if the Connector refuses, report before copying code. |
| R3 | Empty trips from throwaway emails. | Accepted (verified email + limits). Admin history (C11) makes them visible. |

## 3. Acceptance criteria
1. `/request/` shows the subtitle and the 3 lines in Hebrew and English.
2. Known destination: form → code → correct code → `FB_Ready` with destination, month, travelers; "הקמת הטיול" opens `/invite/#invite=…` and the wizard is prefilled. No admin action.
3. Invite email arrives in the request language; at the daily cap it is skipped and the line is hidden.
4. Undecided: interests required; after the code, 3 suggestions with reason and tags; refresh twice, then the button is disabled ("נשארו 0"); a refresh never repeats a shown country.
5. "המשך עם <country>" → `FB_Ready` with that country; the wizard is prefilled with it.
6. AI failure, no key, timeout, invalid JSON or the 30/day cap → fallback picker; the flow completes.
7. The AI request body contains no name and no email (function test inspects the outgoing body).
8. `suggest`/`choose` with a wrong token, an unverified request, a request with countries, or after 30 min → generic refusal, nothing changes.
9. A second auto-approval for the same email on the same day → refused with the F21 "try tomorrow" text.
10. Admin list shows "נפתח אוטומטית" items and the AI counter; revoke makes `/invite/` show "הקישור כבר לא בתוקף".
11. `REQUEST_MODE='manual'` → F21 behaviour and F21 suites green; `SUGGEST_FEATURE='off'` → no segmented choice.
12. 390 px, RTL/LTR, touch ≥ 44 px, no horizontal scroll; `qa.f23_run()` green; F21 regression green.
13. Version `3.0.0-alpha.12`, CHANGE comments, CHANGELOG, `docs/F23_dev_notes.md`, QA report.

## 4. Deploy order (Or, one step at a time)
Dev on `f23` → QA → Or: add secret `ANTHROPIC_API_KEY` → Or: run 0020 + 0021 → deploy `request-trip`, `invite-manager`
→ merge → Or: phone check (known destination + undecided).
