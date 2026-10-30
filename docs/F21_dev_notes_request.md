# F21 · `/request/` page · dev notes

<!-- CHANGE 2026-10-27 F21-DOCS-REQ-01: new file (no previous version). -->

Scope: `docs/F21_spec.md` §1.0–§1.5 (the public, bilingual `/request/` page) and the client side of AC 1–10, 18, 19.
Page version **3.0.0-alpha.8**. Built from the spec and the approved canvas, row 9 (`F21_InApp`, `F21_Request`,
`F21_RequestEN`, `F21_Limit`, `F21_Code`, `F21_Sent`), which I read directly from the artifact.

## Files
- `request/index.html`: one self-contained file (CSS + one inline script). It loads only `../app/countries.json` and the
  Turnstile script, and only after the flag check. With `REQUEST_FEATURE='off'` it shows the closed card and makes no
  network requests at all, so the logic is not split into a `flow.js`.
- `scripts/dev/f21_request_smoke.py`: Playwright 390×844, 130 checks.
- `scripts/dev/f21_request_static_check.py`: 30 checks.

## How to run
```
python3 scripts/dev/f21_request_static_check.py
python3 scripts/dev/f21_request_smoke.py            # F21_SHOTS=<dir> also saves full-page screenshots
```
The smoke test has no network. It serves the repo from a local static server and rewrites the served page to set the
flag and the Turnstile site key per case. It intercepts `request-trip` with an in-memory fake (start / verify / resend and
every spec error code). It replaces the Turnstile script with a fake that honours Cloudflare's test site keys
(`1x00000000000000000000AA` returns a dummy token; `2x00000000000000000000AB` blocks).

## Constants
- `REQUEST_FEATURE='on'`.
- `TURNSTILE_SITE_KEY='1x00000000000000000000AA'`: Cloudflare's always-pass test key. Or replaces it at deploy
  (spec §7 step 1). The smoke test does not depend on this value, because it rewrites the constant in the served file.
- Endpoint and publishable key: the same as `/join/`.

## Behaviour notes and interpretations
1. **Language** (§1.0). The order is `?lang=` → `#lang=` → `pt:_device:rq_lang` → `navigator.languages` (he/iw → he,
   else en). A resumed code screen opens in the request's stored `lang` unless the link names one. The switch sits at the
   top-right in both languages and is ≥44px high; the mockup's pills are 36px, which is below the touch rule.
2. **In-app** (§1.1). The detection is a marked copy of `/invite/` (the static check verifies the UA regexes are
   byte-identical). The hop URL carries only `?lang=<current>`. The Android automatic hop runs once per load; re-rendering
   for a language switch never hops again. "Continue here" hides the screen for the rest of the page load. The mockup's
   iPhone/Android demo toggle and its grey annotation line are not shipped.
3. **Form** (§1.2).
   - The email is normalised (trim, lower) before both validation and sending.
   - The note is trimmed; an empty note is sent as `null`.
   - "Not sure yet" sends `month:null`.
   - The 18 months run from the current month in `Asia/Jerusalem` (C3).
   - The stepper's number is also an editable `<input type=number>` (1–30), so out-of-range values (AC 4 "0/31") can
     reach validation; the buttons clamp.
   - Countries: `countries.json` is fetched once. An empty type-ahead lists popular countries. Matching uses
     `he`/`en`/code. Results show at most 8, with prefix matches first, then popular ones.
   - Validation runs only on send. Errors show inline (red field plus one line), the button stays enabled, and focus
     moves to the first invalid field.
   - A missing Turnstile token (widget not solved or blocked) gives an inline line under the widget and no call. The spec
     does not cover this case.
   - A Turnstile token is single-use. The widget is reset after every failed `start` and removed on success.
4. **Error mapping.**
   - `daily_limit` → 1.4 (never on load, D17).
   - `rate_limited` → toast.
   - `turnstile_failed` → toast + `turnstile.reset`.
   - `invalid_request{field}` → inline on that field. The field names match `0016_f21.sql` `f21_bad()`: name, email,
     countries, month, travellers, note. `lang`/`payload` → generic toast.
   - Offline (`navigator.onLine === false` or a network failure while offline) → the offline toast, with values kept.
   - Anything else → "משהו השתבש. נסו שוב.".
5. **Code** (§1.3).
   - Paste or autofill strips non-digits, so "123 456" works.
   - Six digits auto-submit (as in the F04 wizard).
   - The resend cooldown is 60 s from `sentAt` and survives a reload.
   - `code_expired` enables resend at once.
   - `code_locked` and `request_unknown` both go back to the form with a toast and clear the key. `request_unknown` is not
     in §1.3's list, but the server can return it (e.g. a resumed id deleted by cleanup).
   - The resumed banner is hidden while offline, as in F04-HOME AC 12.
   - The notification illustration shows dots, not digits, like F04-HOME `codeExtras()`, so nobody types an example code.
     The mockup shows "729 015".
6. **Resume.** `pt:_device:rq_resume` = `{request_id, email, sentAt, lang, v:1}`, written on a successful `start` and
   `resend`. A corrupt, expired or invalid entry is deleted on load. It is cleared on verify success, "תיקון המייל",
   `code_locked`, `request_unknown` and TTL. All storage access is wrapped in try/catch; the smoke test runs the whole flow
   with `localStorage` throwing.
7. **Sent** (§1.5). The summary comes from the form values in memory. **After a resume** (reload on the code screen) those
   values are gone, because the key holds only id and email by spec, so the card shows only the email row. If the server's
   `verify` success adds a `request:{countries, month, travellers}` object, the page uses it (open question 1).
8. **Closed card.** One card with both lines ("הבקשות סגורות כרגע" and "Requests are closed right now") and no language
   switch. Nothing is fetched.

## Open questions for the architect
1. Should the summary on the Sent screen after a resume show where/when/travellers? Options: (a) `verify` returns them
   (the page already reads `r.request.{countries,month,travellers}`), or (b) accept an email-only summary in that case
   (current behaviour).
2. Turnstile widget unsolved or blocked when the user taps send: I show an inline line under the widget and make no call.
   Is that acceptable, or should the button send anyway and let the server answer `turnstile_failed`?
3. The language switch is 44px high, not the mockup's 36px, to meet the touch rule. Please confirm.

## Architect answers (2026-10-30)
1. Sent summary after a resumed code screen: email only is accepted for alpha.8 (the server need not return the request).
2. Turnstile not solved on send → inline line, no call: accepted.
3. 44px language switch and chip × (DoD touch rule): accepted.
4. `TURNSTILE_SITE_KEY` = real site key from Or (F21-REQ-04); static 30/30 and smoke 130/130 re-run green after the change.
