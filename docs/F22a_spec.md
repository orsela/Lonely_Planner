# F22a — Sign in with Google (account backup for every member) · spec

<!-- CHANGE 2026-11-07 F22A-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.11** (app + `/join/` + new static pages `/privacy/`, `/terms/`). **No migration and no new
Edge Function are expected** (see R1 for the one possible exception). F07 moves to alpha.12 and is rebased on this.
Mockup approved by Or 2026-11-07: canvas https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, **row 15** (`F22_Me`,
`F22_Linked`, `F22_Gate`, `F22_Welcome`, `F22_NoTrips`, `F22_Conflict`). Decisions: claude/Plan_Travel_F22_decisions.md
(D1–D12). Spike: `spike/f22/` (main b32ef62) — results below.

User value: any member (not only managers) can attach a Google account to the phone in one tap. A new or wiped phone
then gets back into the trip with "המשך עם Google" — same name, role and records, no manager approval, no ghost member.

Base: `main` at 3.0.0-alpha.10 + spike page. Branch **`f22a`**. Push rule (INDEX): client code may merge once the
dashboard setup below is confirmed (it is already done, see §0.2). The live project `vietnam-trip-2026` is never touched.

## 0. Facts this spec builds on

### 0.1 Spike results (2026-11-07, Or, Chrome on the computer and Android)
| # | Test | Result |
|---|---|---|
| S1 | Clean browser → `signInWithOAuth(google)` with orsela@gmail.com | Returned **uid 4ed9cc42** (Or's existing user). Supabase **auto-linked** Google to the user whose verified email matches (email was linked in F04). Identities after: `email`, `google`. |
| S2 | New anonymous identity → `linkIdentity(google)` with the same Google account | Redirect back with `error_code=identity_already_exists`; the anonymous identity is unchanged. |
| S3 | `linkIdentity` before "Allow manual linking" was saved | `Manual linking is disabled` — the dashboard switch is required. |
| — | Not yet tested | Successful link to a fresh anonymous identity (needs a 2nd Gmail as Google test user); return into the **installed** PWA; iPhone. |

### 0.2 Setup already done (Or, 2026-11-07)
- Google Cloud project **Lonely Planner** (`gen-lang-client-0905333908`): consent screen External, **Testing**, test user
  orsela@gmail.com; OAuth client "Lonely Planner Web" (origin `https://orsela.github.io`, redirect
  `https://zwufpxnioqaweobnvffs.supabase.co/auth/v1/callback`). The secret never enters the chat or the repo.
- Supabase: Google provider on; anonymous sign-ins on; **Allow manual linking on**; Redirect URLs include
  `https://orsela.github.io/Lonely_Planner/**`.

## 1. Decisions (from claude/Plan_Travel_F22_decisions.md)
| # | Decision |
|---|---|
| D4 | F22a = Google + linking infrastructure + the "חשבון כניסה" card + `/privacy/` and `/terms/`. Facebook/X = F22b, WhatsApp = F22c (shown as "בקרוב" chips only). |
| D6 | **Every member** can link an account (not only managers). |
| D7 | Account already belongs to another user: device with **no trips** → switch to that account; device **with trips** → explanation only, nothing changes. |
| D8 | Manager invites (F03/F21) stay by email. A Google sign-in whose verified email equals the invite email is accepted like a verified code. |
| D12 | Removing the sign-in account is **always** allowed, with a warning; if no other way remains, the warning says a new phone will need manager approval. The current device stays in the trip. |

Out of scope: Facebook, X, WhatsApp (F22b/c); device lists, relink requests and the managers' "נכנס/ה ממכשיר חדש" notice
(F07 — see §6); removing a linked email (stays as in F04); iPhone standalone OAuth (C9).

## 2. Architect rulings
| # | Ruling |
|---|---|
| C1 | **Same uid.** Linking uses `supabase.auth.linkIdentity({provider:'google'})` on the device's current user (anonymous or email). Membership, RLS and every `auth.uid()` check stay as they are — **no server change**. |
| C2 | **Which call where.** Inside a trip ("אני · <שם>", device has trips) → `linkIdentity` only. On the gate / landing (device has **no** trips) → `signInWithOAuth` only. So `linkIdentity` never replaces an identity that owns trips, and `signInWithOAuth` never discards one. |
| C3 | **Return handling.** The app client keeps `detectSessionInUrl:false` (F03 owns the hash). A new F22 block, placed with the F03 hash reader, handles the OAuth return: `?code=` (PKCE → `exchangeCodeForSession`) or a token hash (implicit), and `error`/`error_code`/`error_description` in query or hash. It clears the URL with `history.replaceState` before trip boot. Dev picks the flow type that works with the existing client without changing F03/F04 email flows; the choice and reason go in `docs/F22a_dev_notes.md`. `redirectTo` = the app URL (`location.origin+location.pathname`). A pending-intent marker in `sessionStorage` (`link` / `signin`) tells the return which screen to show. |
| C4 | **Conflict (D7).** `identity_already_exists` on a `link` return → `F22_Conflict` sheet over "אני"; nothing changes. (A device with trips never starts `signInWithOAuth`, so the "switch" branch of D7 is the gate path itself.) |
| C5 | **Gate (`F22_Gate`).** The F04-HOME gate card "מנהל/ת טיול → כניסה עם המייל" becomes **"כבר בטיול? כניסה עם החשבון"** for managers and members: "המשך עם Google" + "קוד למייל" (the existing F04-HOME code flow). Below, "בלי חשבון": join link and Safari transfer code as today. This **replaces F07 C10** (F07 keeps only its relink path). |
| C6 | **After sign-in (`F22_Welcome` / `F22_NoTrips`).** Reuse F04-HOME C3: open invite → wizard; no invite + 1 trip → enter it; 2+ trips → the F20 trip chooser; super-admin → F20 "לאן נכנסים?". New only: the welcome header ("שלום <display_name>, ברוך/ה השב/ה", provider + masked email) and the one-time line "מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים". No trips and no invite → `F22_NoTrips` (another account / join link / F21 request / sign out). |
| C7 | **"אני · <שם>" screen.** New row in "עוד" for every member (F07 D7, built here; F07 adds "המכשירים שלי" to it). F22a content: the sync card and the **"חשבון כניסה"** card (`F22_Me` / `F22_Linked`). For a manager the F03 "החשבון שלי" email section moves into this card (same `updateUser({email})` + code screen); nothing else in "עוד" changes. The email/Google address is shown masked and **only to its owner**. |
| C8 | **Unlink (D12).** "הסרה" on the Google row: confirm sheet; text adds the "אישור מנהל בטלפון חדש" warning when Google is the only identity left. ≥2 identities → `supabase.auth.unlinkIdentity(googleIdentity)`. Only identity → see R1. The device keeps its session and trips either way. |
| C9 | **iPhone.** In iOS standalone mode the Google button is hidden on the gate and in "אני", with the line "באייפון: כניסה עם קוד למייל" (the OAuth return would land in Safari, not the app). Safari tab: Google shown normally. |
| C10 | **Invites (D8).** `/invite/` and the F04 email step add "המשך עם Google" under the code option. `create-trip` already requires a *confirmed* email from `auth.getUser` (`verifiedUser`); a Google user's email is confirmed, so `find_invite_for_email` works unchanged. A Google email that differs from the invite → the existing "ההזמנה נשלחה למייל אחר" message. |
| C11 | **Google button.** Built per Google's sign-in branding guidelines (official "G" mark, approved colours and wording "המשך עם Google"); the mark is an inline SVG from Google's published asset, no external request. |
| C12 | **Static pages.** `/privacy/` and `/terms/` (Hebrew, with a short English section), no scripts, linked from "אני" and from the gate footer. Content drafted by Claude and **approved by Or before merge**: what is stored (display name, trip data, email or Google id, no passport/booking/payment data — INDEX F18–F19 rule), who sees it, deletion on request (orsela@gmail.com), no ads/sale. |
| C13 | Flag **`ACCOUNT_FEATURE='off'`** → app, `/join/` and `/invite/` behave exactly as alpha.10 (gate text, "עוד" rows, no Google anywhere). `/privacy/` and `/terms/` stay published (harmless). |

## 3. Setup steps outside the code (Or, one step at a time, after the pages are live)
1. Google Auth Platform → Branding: home page `https://orsela.github.io/Lonely_Planner/`, privacy
   `…/privacy/`, terms `…/terms/`; authorized domains as the console requires (R2). **No logo** (it triggers brand verification).
2. Audience → **Publish app** → In production.
3. Until step 2: only Google test users can sign in — enough for QA and the phone check.

## 4. Risks to settle first in development (stop and report if one fails)
| # | Risk | Plan |
|---|---|---|
| R1 | `unlinkIdentity` refuses to remove a user's **last** identity (anonymous user + Google). | Try it. If refused: a minimal `manage-account` Edge Function (service role) that deletes that `auth.identities` row for the caller only — **only after Or approves** this server change; otherwise "הסרה" on the last identity is disabled with an explanation and D12 goes back to Or. |
| R2 | Publishing may require verifying `orsela.github.io` and/or accepting `zwufpxnioqaweobnvffs.supabase.co` as an authorized domain. | Check while filling Branding; report what Google asks before doing anything that costs money (none expected). |
| R3 | Return into the **installed** Android PWA. | First dev build behind the flag on a branch preview: Or presses "המשך עם Google" inside the installed app; if the return lands in a Chrome tab, fall back to C9's iPhone rule for Android standalone too and report. |
| R4 | Auto-linking by verified email (S1) merges a Google sign-in into any user with the same confirmed email. | Intended (it is the "new phone" path). QA checks that a manager whose Google email differs from the linked email is **not** merged (two separate users, F04 D6 explanation if relevant). |

## 5. Acceptance criteria
1. A member (editor/viewer) on an anonymous identity opens "עוד → אני · <שם>", presses "המשך עם Google", completes Google → back in the app, **same uid**, "מוגן" card with masked email, all trips and role unchanged.
2. Same for a manager whose identity already has a linked email: Google is added; both rows shown.
3. A fresh browser/identity: gate → "המשך עם Google" with that account → enters the trip directly (1 trip) or the chooser (2+), no approval, no new `trip_members` row.
4. Google account that already belongs to another user, pressed in "אני" → `F22_Conflict`; uid, trips and identities unchanged.
5. Gate sign-in with a Google account that has no trips and no invite → `F22_NoTrips`; "יציאה מהחשבון" returns to a clean gate.
6. Invite: Google with the invite's email → wizard (F04) prefilled; different email → existing "מייל אחר" message, nothing created.
7. Unlink with 2+ identities → Google row gone, session and trips unchanged; with 1 identity → per R1 outcome, warning text shown.
8. OAuth error or cancel at Google → back in the same screen with "הכניסה בוטלה / נכשלה", nothing changed, URL clean.
9. The masked address is visible only on the owner's device; no other member's screen or API response contains it (RLS/response check).
10. iPhone standalone (UA emulation): no Google button, the "קוד למייל" hint shown (C9).
11. `ACCOUNT_FEATURE='off'` → identical to alpha.10: regression suites F01–F06, F10/F10b, F20, F21, F04-HOME green.
12. 390 px, RTL, touch ≥ 44 px, no horizontal scroll, offline: Google and unlink buttons disabled with the F10b offline line.
13. Version `3.0.0-alpha.11`, CHANGE comments on every touched block, CHANGELOG, `docs/F22a_dev_notes.md`, QA report.

## 6. Effect on F07 (applied in `docs/F07_spec.md`, branch `f07`)
F07 becomes alpha.12 and is rebased on F22a. D6 "email backup" → "sign-in account (email or Google, later Facebook/X/
WhatsApp)", built by F22a; C9 → points to F22a C7; C10 → replaced by F22a C5; C3/C4/C8 keep their logic but
`member_sessions.via` takes the provider name (`anon`, `email`, `google`, …); acceptance 8/10/11 say "account" instead
of "email". The `F07_MyDevices` artboard is superseded by `F22_Me` (devices card added by F07).

## 7. Deploy order
Dev on `f22a` → QA (independent, from this spec) → Or: phone check on Android (R3) → merge → Or: Branding + Publish (§3)
→ delete `spike/f22/`.
