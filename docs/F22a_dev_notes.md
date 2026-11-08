# F22a — dev notes (app 3.0.0-alpha.11)

<!-- CHANGE 2026-11-07 F22A-DOCS-03: new file (no previous version). -->

Contract: `docs/F22a_spec.md` (C1–C13). Scope: `app/index.html`, `invite/index.html`, new `privacy/index.html`,
`terms/index.html`, `tests/f22a/`. **No migration, no Edge Function, no dashboard change, no secret.** `/join/` unchanged
(byte-identical to alpha.10: nothing in F22a changes its behaviour; its version comment stays alpha.7.2).

## Flag
`ACCOUNT_FEATURE` (flags script, after `CURMGR_FEATURE`; same constant in `/invite/`):
- `'off'` → the F22 head block returns on its first line, `window.__ptF22` is absent, every gate hook (`F22A-GATE-02..04`)
  is a no-op → alpha.10 (tested: gate DOM signature equals 76d2495, no "אני" row, F03 email row as before).
- `'on'` → for everyone.
- `'beta'` (shipped) → only where raw `localStorage['pt-f22-beta']==='1'`. Opening `…/app/#f22beta` sets it,
  `#f22beta-off` removes it; the hash is removed at once. A hash typed into an already open app is handled by a
  `hashchange` listener that applies it and reloads. Storage is accessed with the browser's own `Storage.prototype` methods
  captured before the F02 gate namespaces localStorage (same technique as F04-HOME's RAWLS). `/invite/` reads the same key.

## Tags
F22A-FLAG-01/02, F22A-UI-01 (head style + script: RET-01/02, GATE-01, WEL-01, ME-01, WZ-01, sheets), F22A-GATE-02 (bridge),
F22A-GATE-03 (takeover before boot), F22A-GATE-04 (one line in the existing `showCard()` — the only touched existing function
body, next to the F04/F05 hooks, same pattern), F22A-F04-01/02 (`window.__ptF04.openEntry`), F22A-VER-01/02,
F22A-INV-01..03 / -FLAG, F22A-PRIV-01, F22A-TERMS-01, F22A-QA-01..03. Protected functions untouched (static test).

## Flow type (C3) — implicit, client options unchanged
The gate creates the client with `detectSessionInUrl:false` and the default `flowType` (supabase-js v2 default =
`'implicit'`). **I did not change the client options.** Reasons: `flowType:'pkce'` changes `signInWithOtp` / `updateUser`
email links to `?code=` + a code verifier in storage — the F03 email-link confirmation and the F04 OTP flows were built and
QA'd against the implicit shape; switching them is a regression risk for no gain (OTP codes don't care, links would).
With implicit, `linkIdentity` / `signInWithOAuth` return to `redirectTo` with `#access_token=…&refresh_token=…&provider_token=…`
(or `error`/`error_code`/`error_description`, query or hash). The F22 head block (placed **before** the F03 block, so F03's
hash reader never sees an OAuth hash) reads it, clears the URL with `history.replaceState`, and the gate hands over
(`takeOverBoot`) before trip boot: `setSession({access_token, refresh_token})` → session stored by supabase-js under the
usual key. A `?code=` return (if the project ever answers PKCE) is also handled: `exchangeCodeForSession(code)`.
Intent marker: `sessionStorage['pt22:intent']` = `link` | `signin` (+ `pt22:from`), read once and removed on every load.
Without a marker (return landed in another browsing context, R3) only a hash carrying `provider_token` is taken
(F03's email hash never carries it); intent then = `link` if the returned uid equals the device's stored uid, else `signin`.
The Google `provider_token` is never stored.

## Rulings → code
| Ruling | Where / how |
|---|---|
| C1/C2 | "אני" → `linkIdentity` (needs the session; same uid). Gate / `/invite/` → `signInWithOAuth`; guard: a device whose uid has active memberships never starts it (toast "הטלפון הזה כבר בטיול…"). F04 email step: `link` inside a running trip, `signin` otherwise. |
| C4 | `error_code=identity_already_exists` on a `link` return → trip boots, "אני" opens, sheet `#ptF22Conflict` (texts of F22_Conflict). "בחירת חשבון אחר" = `linkIdentity` again with `prompt=select_account`. The Google address is not in the error, so the sheet says "חשבון ה-Google שבחרת" instead of the masked address in the mockup. |
| C5 | `__ptF22.gateCard(g)` after F04/F05/F04-HOME: hero "ברוכים הבאים", the F04-HOME card `#ptGateInvite` rewritten as "כבר בטיול? כניסה עם החשבון" (Google + the same `#ptGateInviteBtn` relabelled "קוד למייל" → the existing code flow), "בקרוב" chips, F05's "דרכים אחרות" label → "בלי חשבון" with the join-link card and the transfer-code card under it, device-code card last, legal links footer. |
| C6 | `welcomeFlow`: super-admin (F20 check) → normal boot (F20 chooser); confirmed email + open invite (create-trip `lookup`) → `__ptF04.openEntry('gate')` (wizard skips the code: email already confirmed); 0 trips → F22_NoTrips (from `/invite/`: "לא מצאנו הזמנה פעילה למייל הזה"); 1 trip → F22_Welcome, enters after 1.8 s or on tap; 2+ → F22_Welcome with the list (F20's chooser is super-admin only, so the list is shown here). |
| C7 | Row `#ptF22MeRow` "אני · <display_name>" at the top of F03's "החשבון שלי"; F03's email rows are hidden by CSS (`html.pt-f22`), the F03 card is hidden when it has no visible admin row. Screen `#ptF22Me` (a `.panel`): sync card (→ backup screen) + "חשבון כניסה" (`#ptF22Acct`). "קוד למייל" = the F04 code screen (`openEntry('me')` → `updateUser({email})` + `verifyOtp email_change`; done → F04-HOME C3 reload into the trip). Address masked (`abc•••@domain`), read only from the device's own `auth.getUser()`; nothing written to any table. |
| C8 | "הסרה" → sheet; D12 warning when Google is the only way. ≥2 identities → `unlinkIdentity`. Refused → `#ptF22UnlinkRefused` with the error code; recorded in `window.__ptF22.diag().lastUnlinkError`. No server function. |
| C9 | `isIOS() && standalone` → no Google button on the gate, "אני" or the email step; line "באייפון: כניסה עם קוד למייל". |
| C10 | `/invite/` valid card: "המשך עם Google" under the code button → `../app/?f22=google` (no token needed: lookup finds the invite by the confirmed email). F04 email step: Google under "שליחת קוד". |
| C11 | Inline SVG of Google's 4-colour "G" (standard paths), white button, #747775 border, Roboto/Arial, text "המשך עם Google". No external request. |
| C12 | `/privacy/`, `/terms/`: static, no script, no external request, Hebrew + English summary, contact orsela@gmail.com, "טיוטה לאישור" only in the HTML comment. |
| §5.12 | Google / unlink / "בחירת חשבון אחר" carry `data-pt22-net` → disabled offline; line "אין חיבור. צריך חיבור כדי לחבר או להסיר חשבון…" (F10b wording pattern). |

## R1 — to verify on the phone
Not testable offline. Expected (GoTrue source): `unlinkIdentity` on a user with a single identity → HTTP 422
`single_identity_not_deletable` ("User must have at least 1 identity after unlinking"). An anonymous user has **no**
identity row, so anonymous + Google = 1 identity → refused. The app shows the refusal sheet with the code.
**Phone result: _to verify on phone_** (Or: link Google in "אני" on a member device, press הסרה → note the code shown).
If confirmed, D12's "always allowed" needs the R1 server function (Or's decision).

## Known limits
- R3 (installed Android PWA): if the OAuth return opens a Chrome tab instead of the app, the session is stored in the shared
  origin storage, so the tab is signed in; the installed app picks it up on its next start (same localStorage) but shows no
  "החשבון חובר" toast. If Or sees this, the C9 rule is extended to Android standalone (one condition in `googleHidden()`).
- Conflict sheet cannot show the other Google address (not returned by Supabase).
- Welcome screen's member count needs `trip_members` read (existing RLS: members of the trip) — shown when it loads.
- F07 will add "המכשירים שלי" into `#ptF22MeBody` and the managers' "נכנס/ה ממכשיר חדש" notice (the welcome footnote line of
  the mockup is therefore not shown yet).

## Tests (tests/f22a, `run.sh`)
Fake supabase-js (F05) patched at serve time with `linkIdentity` / `signInWithOAuth` / `setSession` / `exchangeCodeForSession`
/ `unlinkIdentity`; `F22Backend` models S1 (auto-link by verified email), S2 (`identity_already_exists`) and R1.
41 tests: acceptance 1–12 (11 = flag 'off' and 'beta' without the key: gate DOM equal to alpha.10 76d2495, no "אני" row),
13 static (protected functions == v2.15.2, versions, CHANGE tags, flag 'beta', node --check, legal pages, no secrets, no new
duplicate ids, /join/ unchanged). Not covered offline: the real Google consent screen, R1's real answer, R3 (installed PWA).

## Regression run (2026-11-08, QA_EXPECTED_VERSION=3.0.0-alpha.11)
`tests/run_all.sh --only "f04h f04 f03on f20" -j 2` + `tests/f10b/run.sh` + `tests/f22a/run.sh`:
- f04 118/118 (7 desel) · f10b 23/23 · f22a 41/41.
- f04h and f20: one static failure each, `no_duplicate_ids` — the F22 screens are alternative JS templates and repeated ids
  in the source; fixed with the house convention (one source occurrence per id via `aid()`, like F03's `LAND_H1`). Rerun
  after the fix: f04h `test_f4h_13_static` 14/14, f20 `test_st_static` 17/17, f22a 41/41.
- f03on: `test_ac16_off_more_panel_identical_to_alpha2` fails on the **F10b** row "💱 מטבעות · N מתוך 10" (alpha.10,
  CURMGR_FEATURE on in the ADMIN_FEATURE='off' copy) — pre-existing since alpha.10, not F22a. Needs a deselect / flipped
  copy in tests/run_all.sh by the QA owner of F10b.
- `/invite/` changed (C10): tests/f21 `test_c20_static[invite_unchanged]` (byte-identical to alpha.7.2) will fail by design
  — superseded by F22a C10; not run here (f21 not in the targeted set).
