# F04-HOME — An invited manager ends up with the app on the home screen, and the email code never gets lost · spec

<!-- CHANGE 2026-10-26 F04H-DOCS-01: new file (no previous version). -->

Version target: **3.0.0-alpha.7.1** (app + `/invite/` page). **Client only:** no migration, no Edge Function change.
One dashboard change by Or (Supabase Auth email templates, §3.5). Mockup approved by Or 2026-10-26: canvas
https://claude.ai/artifact/FtgwXNmFKoSSrgnuqghbMG, row 10 (artboards `H_InApp`, `H_Install`, `H_Gate`, `H_Code`, `H_Email`,
`H_Done`). Decisions: claude/Plan_Travel_F21_decisions.md D14 + D15 (project doc).

User value: a manager who opens the invite from a phone (1) never loses the page while fetching the 6-digit code from
the mail, and (2) finishes with Lonely Planner on the home screen, connected to the trip they created — on iPhone too,
where Safari and the home-screen app do not share storage.

Base: `main` at 3.0.0-alpha.7 (F06, b66fcb7). Branch `f04-home`. Because nothing depends on a server deploy, the branch
merges to `main` after QA + Or's phone check (push rule in INDEX). Runs **before F21**; F21's `/request/` page reuses
§3.1 (in-app browser) and §3.3 (code-screen resume).

## 0. Decisions

| # | Decision |
|---|---|
| D14a (Or) | **Install before the wizard:** `/invite/` first asks to add the app to the home screen, open it from there and tap "כניסה עם המייל"; the wizard then runs inside the installed app. Skippable ("להמשיך בדפדפן בלי להתקין"). |
| D14b (Or) | **Install after the wizard, for whoever skipped:** "הטיול נוצר" gets a card "מוסיפים את האפליקציה למסך הבית". iPhone: the installed app signs in with the manager's (already verified) email — 6-digit code, no new transfer code. Android: install button. |
| D15a (Or) | **Leave the mail app's in-app browser:** `/invite/` detects it and moves to the real browser (Android: automatic to Chrome; iPhone: "פתיחה בספארי" button + manual steps). |
| D15b (Or) | **The wizard remembers the code screen:** a reload / reopen within 10 minutes of sending returns to the code boxes with the same email, without sending a new code. |
| D15c (Or) | **The code in the email subject**, e.g. "481562 – קוד הכניסה ל-Lonely Planner"; the confusing confirm link is removed from the OTP emails. Or edits the two templates in the Supabase dashboard. |
| D15-rejected (Or) | "Confirm by tapping in the mail" and reading the mailbox (Gmail API) — not built. |
| C1 (Claude) | The gate's F04 card becomes **"מנהל/ת טיול" → "כניסה עם המייל"** (was "קיבלת הזמנה לנהל טיול?" → "כניסה עם הזמנה"), moved to the top of the gate. One entry for both cases: an unused invite → wizard; already a manager → the trip opens. |
| C2 (Claude, found in this spec) | **Android install button lives in the app, not on `/invite/`.** Chrome only offers installation (`beforeinstallprompt`) on pages inside the manifest scope (`/app/`); `/invite/` is deliberately outside it (F03-LAND-06). On Android the browser and the installed app share storage, so installing at "הטיול נוצר" loses nothing. `/invite/` on Android shows the existing "פתיחה באפליקציה והקמת הטיול" button + one line "בסוף ההקמה תוכלו להתקין את האפליקציה". (Deviation from the Android variant of `H_Install`; reported to Or.) |
| C3 (Claude, found in this spec) | **Bug fixed:** today, in an installed app with a fresh identity, "כניסה עם הזמנה" for a manager whose invite was already used switches the session to the manager (`signInWithOtp`), then shows "לא מצאנו הזמנה פעילה…" and "חזרה" returns to the not-connected gate **without reloading** — the trip only appears after the app is restarted. Now: after verification, no open invite **and** active memberships → boot into the trip. |
| C4 (Claude) | Resume state is kept in `localStorage` (not `sessionStorage`): an in-app browser or a new tab loses `sessionStorage`. Stored: email + sentAt + sendKind + origin, **never the code**; 10-minute TTL; cleared on success, on "שינוי מייל" and on exit. |

Out of scope: F21 itself; a full "sign in on a new phone" for members (F07); English UI (F13).

## 1. Screens (Hebrew, RTL, 390px, touch ≥44px, existing `pt-*` styles and the `/invite/` page styles)

### 1.1 `/invite/` inside a mail app's in-app browser (artboard `H_InApp`)
Shown **only** when the token check returned *valid* and §3.1 says "in-app". Card "פותחים בדפדפן הרגיל" + explanation.
- iPhone: primary "פתיחה בספארי" → `x-safari-https://<same page>#invite=<token>`; under it "הכפתור לא עבד?" with 2 steps
  (⋯ → "פתיחה בספארי").
- Android: automatic `intent:` hop to Chrome on load (§3.1); visible fallback button "לא נפתח? פתיחה ב-Chrome".
- Footer line: "ההזמנה עצמה בתוקף. אם הדף נסגר – לוחצים שוב על הכפתור במייל."
- Invalid / no-connection states are unchanged (no redirect for an invalid token).

### 1.2 `/invite/` in the real browser (artboard `H_Install`)
Valid card shrinks to one row (✓ "ההזמנה שלך אומתה", draft name, expiry). Then:
- **iPhone Safari, not standalone:** card "קודם מוסיפים את האפליקציה למסך הבית" with 3 steps (share icon → "הוספה למסך
  הבית" → open Lonely Planner and tap "כניסה עם המייל"); info line "באפליקציה נשלח קוד בן 6 ספרות למייל שאליו נשלחה ההזמנה.
  הקוד מופיע בכותרת המייל – רואים אותו בהתראה." The page does **not** know the email (the token check returns no email,
  F03), so the mockup's address is replaced by this wording.
  Button "הוספתי – מה עכשיו?" opens a short sheet repeating step 3. Link "להמשיך בדפדפן בלי להתקין" → today's
  `../app/?invite=1#invite=<token>`. Extra small line under the steps: "לא רואים 'הוספה למסך הבית'? פותחים את הדף בספארי"
  (SFSafariViewController cannot be detected and has no such action).
- **Android (C2):** today's primary button "פתיחה באפליקציה והקמת הטיול" + line "בסוף ההקמה תוכלו להתקין את האפליקציה".
- **Desktop / other:** today's page unchanged.
- The existing installed-app note now names "כניסה עם המייל".

### 1.3 The installed app's gate (artboard `H_Gate`)
First card (top): "מנהל/ת טיול" + badge "חדש", text "קיבלת הזמנה במייל, או שכבר הקמת טיול בדפדפן? נשלח קוד למייל שלך,
ותמשיך/י בדיוק מאיפה שעצרת.", primary "כניסה עם המייל", two bullets (open invite → wizard; existing trip → opens). Then
the F05 cards (transfer code, join link) unchanged, then the F02 device-code card last (unchanged, emergency).

### 1.4 Code screen (artboard `H_Code`)
Today's F04 code screen plus:
- When resumed (§3.3): info banner "חזרת לדף – הקוד ששלחנו לפני N דקות עדיין תקף. לא נשלח קוד חדש." (role=status).
- Card "איפה הקוד? בהתראה של המייל" with the notification illustration (sender, subject with the code) and the line
  "רואים את הקוד בלי לצאת מהדף. באייפון עם אפליקציית Mail המקלדת מציעה אותו לבד. הדבקה ממלאת את כל התיבות."
- The resend cooldown continues from the stored `sentAt`.

### 1.5 OTP email (artboard `H_Email`) — §3.5.

### 1.6 "הטיול נוצר" (artboard `H_Done`)
Above the join-link card, **only when not standalone** (`display-mode: standalone` false and `navigator.standalone` not
true): card "מוסיפים את האפליקציה למסך הבית".
- iPhone: 3 ticks (share → add; open Lonely Planner; "כניסה עם המייל" ← code to `<the verified email>` ← the trip opens).
- Android with a captured `beforeinstallprompt`: button "התקנת האפליקציה" → `prompt()`; on `appinstalled` the card turns
  into "האפליקציה הותקנה – אפשר לפתוח אותה ממסך הבית". Without the event (already installed / not offered): 2-line manual
  hint (⋮ → "התקנת אפליקציה" / "הוספה למסך הבית").
- Bottom button becomes "אחר כך – כניסה לטיול כאן" (outline) when the card shows; otherwise today's "כניסה לטיול ←".

## 2. Data
No schema change. New device keys (raw, outside any trip prefix): `pt:_device:wz_resume` (JSON `{email, sentAt, kind,
origin, v:1}`), TTL 10 min, never holds a code or a token.

## 3. Logic

### 3.1 In-app browser detection and hop (`/invite/` only)
- `inApp = /\b(GSA|FBAN|FBAV|Instagram|Line|LinkedInApp|Outlook|; wv\))/i.test(ua) || (isIOS && !/Safari\//.test(ua))`
  (iOS WKWebView in Gmail/Outlook lacks the `Safari/` token; Android WebView carries `; wv)`). Not detectable:
  SFSafariViewController — covered by the extra line in 1.2.
- iPhone hop: `location.href = 'x-safari-https://' + host + path + '#invite=' + token` on button tap only (never
  automatic). Known: works on iOS 15/17/18, not 16; from inside Gmail — **unverified, phone check**. The manual steps stay
  visible.
- Android hop: automatic once per load: `intent://<host><path>?t=<token>#Intent;scheme=https;package=com.android.chrome;end`
  — an intent URI cannot carry the page's own `#fragment`, so for this one hop the token travels as `?t=`; on load the page
  moves `?t=` into memory, then `history.replaceState` drops it (same as it does with `#invite=` today). `referrer` is
  already `no-referrer`. Fallback button = the same URL.
- The token is never stored and never logged (unchanged rule).

### 3.2 Install step on `/invite/` (iPhone)
`isIOS && !navigator.standalone && !inApp` → 1.2 iPhone variant. Skip link keeps today's behaviour.

### 3.3 Code-screen resume (app wizard; reused by F21)
- On a successful send: write `pt:_device:wz_resume`.
- On wizard open (`openWizard`, any origin) and on boot with `?invite=1`: a valid entry (< 10 min) with the same origin
  family → go straight to the code screen with that email, banner on, cooldown from `sentAt`, **no send**.
- Clear on: verify success, "שינוי מייל", explicit exit, TTL.

### 3.4 "כניסה עם המייל" in the installed app (C1 + C3)
Same flow as today's entry mode (`openWizard('gate','entry','')`) with the new texts. After `verifyOtp`:
1. `lookup` finds an invite → wizard step 1 (today).
2. No invite → `api.activeTrips()`; ≥1 active membership → close the wizard and **reload into the trip**
   (`location.replace(location.pathname)`; the gate's normal boot picks the last/only trip, F20 rules for the super-admin).
3. No invite and no trips → today's "לא מצאנו הזמנה פעילה…" card.

### 3.5 Supabase Auth email templates (Or, dashboard — one step at a time)
`{{ .Token }}` is supported in subjects (Supabase's own default reauthentication subject is "`{{ .Token }}` is your
verification code"). Two templates: **Change email address** (new manager, `updateUser`) and **Magic link** (existing
manager, `signInWithOtp`). Subject: `{{ .Token }} – קוד הכניסה ל-Lonely Planner`. Body (both): brand, "קוד האימות שלך:",
the code in large monospace, "חוזרים לאפליקציה ומקלידים את הקוד. הוא תקף שעה ופעם אחת.", "לא ביקשת קוד? אפשר להתעלם
מהמייל." — **no `{{ .ConfirmationURL }}` link**. Claude prepares the exact HTML in `docs/F04-HOME_email_templates.md`.
(F04 spec §5.1 had "keeping the link"; superseded.)

### 3.6 Flag
`HOME_INSTALL_FEATURE='on'` in the app and a same-named constant in `/invite/`. `'off'` → exactly alpha.7 behaviour
(gate texts, no resume, no install cards, no in-app hop). The email templates are independent of the flag.

## 4. Acceptance criteria
1. Flag off (app and `/invite/`) → alpha.7 behaviour; F04/F05/F06/F20 suites pass except version pins.
2. `/invite/` valid token with an in-app UA (Gmail iOS, Gmail Android WebView, Outlook) → 1.1; with Safari/Chrome UA → 1.2;
   invalid token → today's invalid card, no hop, no install card.
3. iPhone in-app: "פתיחה בספארי" navigates to `x-safari-https://…#invite=<token>`; no automatic navigation.
4. Android in-app: one automatic `intent://…?t=` navigation per load; arriving with `?t=` works like `#invite=`, and the
   address bar shows neither after load.
5. iPhone Safari (not standalone): install card with 3 steps; "להמשיך בדפדפן" opens the wizard exactly as today.
6. Android Chrome: no install card on `/invite/`; the C2 line shows.
7. Gate: the "מנהל/ת טיול" card is first; "כניסה עם המייל" opens the email step; F05 cards and the device-code card still
   work.
8. C3: fresh identity, manager email with a used invite and ≥1 active trip → after the code the app opens that trip
   (no restart); with no trips → the "לא מצאנו הזמנה" card.
9. Resume: send a code, reload within 10 min → code screen, same email, banner, no second send (network log), cooldown
   continues; after 10 min → normal start; after success / "שינוי מייל" / exit → key gone; the key never contains digits of
   the code or the token.
10. "הטיול נוצר" in a browser tab → install card (iPhone ticks / Android button when `beforeinstallprompt` was captured);
    in standalone → no card, bottom button unchanged.
11. 390px: no horizontal scroll, RTL, touch ≥44px on all 6 artboards' screens; URLs and emails LTR.
12. Offline: `/invite/` shows today's no-connection state; the resume banner never claims a code is valid when offline
    (text unchanged, send/verify disabled as today).
13. Protected functions byte-identical (`drawMap`, `drawGoogleMap`, `drawSchematicMap`, `fallbackToSchematic`, `SEED_DATA`,
    `stayBlock`, `bookingUrl`); `APP_VERSION`/`PT_VERSION` = 3.0.0-alpha.7.1; `/invite/` version comment alpha.7.1; every
    change marked `CHANGE 2026-10-2x F04H-…` with what changed from alpha.7; `node --check` on all script blocks; no
    duplicate ids.
14. No new Supabase advisor warnings (none expected — no server change).

## 5. Deployment (one step at a time, Or confirms each)
1. Or updates the two email templates (§3.5) from `docs/F04-HOME_email_templates.md`, then asks for one code (e.g. "כניסה
   עם הזמנה" on a spare browser) and confirms the subject shows the code and the body has no link.
2. Claude merges `f04-home` → `main` after QA.
3. Phone check (Or): from Gmail on the iPhone tap a fresh test invite → 1.1 → "פתיחה בספארי" (note if it worked) → 1.2 →
   add to home screen → "כניסה עם המייל" → code from the notification → wizard → trip. Second run: skip the install, finish
   in Safari, then install and "כניסה עם המייל" → the trip opens (C3). Android (if available): Gmail → Chrome hop → wizard
   → "התקנת האפליקציה".
