# F04-HOME · QA report (3.0.0-alpha.7.1)

<!-- CHANGE 2026-10-26 F04H-QA-05: new file (no previous version). -->

Implementation: `f04-home` @ **7fdd234**. Suite: `tests/f04home/` (written from `docs/F04-HOME_spec.md` at ee5c723 before the
implementation existed; branch `f04-home-qa`), run on branch `qa-run` = 7fdd234 + the suite. The implementation was read only
to triage failures. No Supabase / network call.

## Results

| Run | Collected | Passed | Failed | Skipped / xfail |
|---|---|---|---|---|
| Baseline ee5c723 (no implementation), suite 1.0.0 | 93 | 46 | 46 (feature missing / static pins) | 1 skip |
| 7fdd234, suite 1.0.0 | 93 | 91 | 1 | 1 skip |
| 7fdd234, suite 1.0.1 (test fix F04H-QA-FIX-01) | 93 | 91 | 0 | 1 skip (F4H-14) + 1 xfail (F4H-09e[exit]) |
| `run.sh --only static` (F4H-13) | 15 | 15 | 0 | — |
| `run.sh --only off`: F04 suite on a copy with `HOME_INSTALL_FEATURE='off'` (app + /invite/) | 121 (5 deselected pins) | 118 | 3 | — |
| `run.sh --only off`: F05 suite | 89 | 75 | 13 | 1 skip |
| `run.sh --only off`: F06 suite | 70 | 70 | 0 | — |

## Failures and triage

| Case | Cat. | One line |
|---|---|---|
| F4H-09e[exit] (1.0.0) | c | Spec §3.3 "clear on … explicit exit" names no exit control on the code screen and the app has none (exits are via the result cards / done → trip, which clear the key through `closeWizard`). Test 1.0.1 xfails when no exit control exists; assertion unchanged when one does. |

**Implementation bugs (category a): none found.**

## Criterion 1 — flag off

With `HOME_INSTALL_FEATURE='off'` in both files the existing suites give exactly the failures they give on ee5c723 itself
(recorded in `tests/f04home/off_baseline_ee5c723.txt`: F04 `test_c15_more_join_link_row[manager]`,
`test_n01_no_old_name_rendered[more_sheet]`, `test_n03_whatsapp_text_name_and_url[sheet]` — the "עוד" sheet changed by F06;
F05: 11 behaviour cases + `test_s01_static[app_version|pt_version]`, all pre-existing). No new failure → criterion 1 met.
In-suite F4H-01a–d (invite page text identical to ee5c723's in 5 UAs, gate, no resume, done) pass.

## Dev decisions that settle QA ambiguities
Resume and C3 for both gate and invite entry; token-less `?invite=1` marker restored after an invite-path send (removed on
verify/exit); "שינוי מייל" offered after an invite-path reload; notification illustration shows `••••••`; Chrome's install
banner not suppressed (no `preventDefault`); gate bullets, in-app manual steps and the "הוספתי – מה עכשיו?" sheet text written
by dev; email step: only the title changed. Still open for Or: §3.3 "explicit exit" (no control), banner "לפני 1 דקות"
wording for the first two minutes (dev note §2.7), the `••••••` sample (deviation from the mockup).

## Not covered here
- Criterion 14 (advisors): dashboard check; no server change.
- Harness finding outside F04-HOME: `tests/f05/harness.py` STANDALONE_JS makes `matchMedia('(display-mode: standalone)')`
  throw (getter-only `matches`); F05/F06 standalone tests should be re-checked with a plain-object fake.

## Phone check left for Or (spec §5.3)
1. Email templates (§5.1): subject shows the code, body has no link.
2. iPhone, from Gmail: a fresh test invite → 1.1 → "פתיחה בספארי" (note whether it works from inside Gmail; iOS 16 known
   not to) → 1.2 → add to home screen → "כניסה עם המייל" → code from the notification (and the Mail keyboard suggestion) →
   wizard → trip.
3. Second run: skip the install, finish in Safari, then install and "כניסה עם המייל" → the trip opens with no restart (C3).
4. Reload / switch to the mail app during the code step → code screen resumes, no second email.
5. Android (if available): Gmail → automatic Chrome hop (`intent://`) → wizard → "התקנת האפליקציה" (real
   `beforeinstallprompt` / `appinstalled`).
6. SFSafariViewController case ("לא רואים 'הוספה למסך הבית'?" line) — only visible on a device.

## Phone check (Or, Android, 2026-10-26 20:10–20:13)
<!-- CHANGE 2026-10-26 F04H-DOCS-04: phone check added. -->
- Step 1 (templates): code requested from a private tab → subject shows the 6 digits, body code only, no link — OK (Or).
- Step 3 (invite `86e0887e…` to orsela@gmail.com): Gmail → opened in a Chrome tab (no in-app browser, so no hop) → `/invite/`
  → "פתיחה באפליקציה והקמת הטיול" → code → after switching to Gmail and back the page was still waiting (no reload, so the
  resume banner did not need to show) → wizard → trip "F04-HOME" created 18:12:55Z → "הטיול נוצר" showed the
  install card **with the install button** (`beforeinstallprompt`) — OK.
- Not checked on a phone: iPhone (Or has no iPhone): in-app hop to Safari, Safari install card, "כניסה עם המייל" in a fresh
  installed app (C3); new-manager template "Change email address" (no second email). Check with the first real iPhone /
  new manager.
