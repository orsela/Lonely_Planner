# F04-HOME · dev notes (3.0.0-alpha.7.1)

<!-- CHANGE 2026-10-26 F04H-DOCS-03: new file (no previous version). -->

Contract: `docs/F04-HOME_spec.md` (+ `docs/F04-HOME_email_templates.md`, no code). Base `origin/main` = 3.0.0-alpha.7 (b66fcb7).
Files: `app/index.html`, `invite/index.html`; dev tools `scripts/dev/f04home_smoke.py`, `scripts/dev/f04home_static_check.py`.
Client only: no migration, no Edge Function, no new external script, no new network call (the `/invite/` hops are
navigations of the page itself).

## 1. What changed where (by CHANGE id)

All new code is behind `HOME_INSTALL_FEATURE` (`HOMEI` in the F04 block). With `'off'` in both files every F04H line is a no-op.

### app/index.html
| CHANGE id | Where | What |
|---|---|---|
| F04H-FLAG-01 | flags script, after `MEMBERS_FEATURE` | `const HOME_INSTALL_FEATURE='on'` + comment |
| F04H-VER-01 / -02 | `APP_VERSION` / `PT_VERSION` | `'3.0.0-alpha.7'` → `'3.0.0-alpha.7.1'` |
| F04H-UI-01 | end of the F04 `<style>` | new classes only (`pt-f04h-*`, `#ptGate.pt-gate-f04h…`) |
| F04H-CORE-01 | F04 script, after `let api` | `HOMEI`; `RAWLS` = `Storage.prototype` get/set/remove captured at parse time (before the F02 gate wraps them) for the raw key `pt:_device:wz_resume`; `readResume` (validates `{email,sentAt,kind,origin,v:1}`, TTL 10 min, deletes a stale/invalid entry), `writeResume`, `clearResume`, `resumeInto` |
| F04H-CORE-02 | `window.__ptF04` | two more frozen members: `gateTop`, `resumeBoot` |
| F04H-RES-01…11 | `wz.resumed`, `openWizard`, `closeWizard`, `begin`, `codeScreen`, `resumeCooldown`, `netPaint`, `send`, `verify`, `resumeBoot`, gate line before `boot()` | §3.3 resume: write on a successful send; open (any origin) with a valid entry of the same origin → code screen, no send, cooldown from `sentAt`; clear on verify success, "שינוי מייל", leaving the wizard (`closeWizard`: exit / done → trip), TTL |
| F04H-CODE-01 | `codeExtras()` | resume banner (`#ptWzResume`, role=status, hidden offline) + card "איפה הקוד? בהתראה של המייל" (`#ptWzWhere`) |
| F04H-GATE-01…04 | `gateCard`, `gateTop`, email screen title, `showCard` | C1 card ("מנהל/ת טיול", badge "חדש", text, primary "כניסה עם המייל", 2 bullets; same button element/id/action); moved to the top after the F05 cards; email step title "כניסה עם המייל" |
| F04H-C3-01 / -02 | `afterVerified`, `bootIntoTrip()` | no invite + ≥1 active membership → clear resume, busy screen, `location.replace(location.pathname)` |
| F04H-DONE-01…03 | `beforeinstallprompt` / `appinstalled` listeners at F04 script start, `done()`, `installCard` / `paintInstall` | §1.6 install card (not standalone only), bottom button → outline "אחר כך – כניסה לטיול כאן" |

### invite/index.html
| CHANGE id | What |
|---|---|
| F04H-INV-VER, F04H-INV-01 | header comment: version alpha.7.1 + what changed |
| F04H-INV-02 | new CSS (`h-*` classes only) |
| F04H-INV-FLAG | top-level `const HOME_INSTALL_FEATURE='on'` (same convention as `/join/`) |
| F04H-INV-03 | §3.1 detection (spec regex), `renderHome()`: 1.1 in-app (iPhone "פתיחה בספארי" on tap only + manual steps; Android one automatic `intent://…?t=` per load + fallback button), 1.2 iPhone install card + "הוספתי – מה עכשיו?" sheet + skip link (= today's link), Android = one-row card + today's steps/button + C2 line, desktop = today's page |
| F04H-INV-04 | installed-app note names "כניסה עם המייל" ('off': "כניסה עם הזמנה") |
| F04H-INV-05 | `?t=` read into memory like `#invite=` ('off': ignored); the existing `replaceState` removes it |
| F04H-INV-06 | valid + flag on → `renderHome`; invalid / no connection unchanged, never hop |

Protected functions untouched (byte-identical, checked). Existing lines edited: 5 in the app (email title, `afterVerified`
no-invite line, `__ptF04` export, two versions) and 3 in `/invite/` (header comment, the note line, the check `.then`);
everything else is inserted.

## 2. Spec ambiguities and how they were resolved
1. **Reload of a wizard opened from the invite link.** The F03 landing removes `?invite=1` together with `#invite=`, so a
   reload never had `?invite=1`. After a successful send from origin `invite` the wizard puts the token-free marker
   `?invite=1` back with `history.replaceState`; `clearResume` removes it. The gate calls `__ptF04.resumeBoot()` just before
   `boot()` (F04H-RES-11).
2. **"Same origin family"** = the same origin string (`gate` | `invite`). A gate-origin resume happens when the user taps
   "כניסה עם המייל" again (the gate does not auto-open the wizard; spec names only `openWizard` and `?invite=1`).
3. **Mode after a boot resume** is `entry` ("שינוי מייל" visible): the stored fields (spec §2) do not include the mode.
4. **Email step texts:** only the title changed ("כניסה עם המייל"); subtitle/label kept (no new text in the spec).
5. **Gate bullets** (spec gives only their meaning): "יש הזמנה פתוחה – ממשיכים להקמת הטיול" / "כבר הקמת טיול – הוא נפתח".
6. **Notification illustration** shows `••••••` instead of example digits, so nobody types a sample code. *Deviation from
   the mockup's sample subject — for Or to confirm.*
7. **Banner N** = whole minutes since `sentAt`, at least 1 ("לפני 1 דקות" for the first two minutes — spec text kept verbatim).
8. **AC 12:** the banner is hidden while offline; the existing offline notice and disabled buttons are unchanged.
9. **C3 for every origin** (gate and invite). The wizard is not "closed" visually before the reload: the busy screen
   "פותחים את הטיול…" stays until `location.replace`, because `closeWizard()` would uncover the trip chrome (html has no
   `pt-gate` class at that point). The resume entry is cleared first.
10. **`beforeinstallprompt`:** stored, `preventDefault()` NOT called, so Chrome's own install UI is exactly as in alpha.7.
    The listener lives at the top of the F04 script (head, before the gate boots), so it exists only with
    `WIZARD_FEATURE='on'` and cloud — the only cases with a done screen.
11. **Done card without the event** (Android already installed / desktop Chrome not offering) shows the manual 2-line hint.
12. **/invite/ in-app view only for iOS/Android UAs**; a desktop UA matching the regex (e.g. Outlook desktop) gets the desktop
    page. Wording of the 1.1 explanation, the manual steps and the sheet text is mine (spec gives the headings/buttons).
13. **/invite/ Android variant** = today's `valid()` output with its first card replaced by the one-row card, plus the C2
    line under the button (no duplicated markup). Desktop: today's page; only the note text changes (flag on).
14. `F04_VERSION` inside the F04 block stays `'3.0.0-alpha.4'` (block-internal; F05/F06 edits to this block did not bump it either).

## 3. Not done / needs the phone check
- `x-safari-https://` from inside Gmail, the Android `intent://` hop, a real `beforeinstallprompt` / `appinstalled`, and the iOS
  Mail one-time-code suggestion can only be verified on devices (spec §5.3). SFSafariViewController is not detectable (spec).
- Email templates (§3.5): dashboard step for Or; nothing in code.

## 4. Dev results (2026-10-26)
- `python3 scripts/dev/f04home_static_check.py` → ALL OK: node --check 11/11 blocks, no new duplicate ids, 7/7 protected
  identical, versions alpha.7.1 (app ×2, invite comment), flag in both files, 30/30 diff hunks carry an F04H CHANGE tag,
  every edited existing line is gated / a version line, resume key written once with `{email,sentAt,kind,origin,v}` only.
- `PYTHONPATH=<pytest site-packages> python3 scripts/dev/f04home_smoke.py` → 76/76 (gate, resume gate/invite/TTL/clear, C3 both
  ways, done card desktop/iPhone/standalone/Android-with-event, /invite/ 1.1 iOS+Android, ?t=, iPhone install, Android C2,
  desktop, invalid, flag 'off' sanity, 390px / touch ≥44 on the screens visited).
- Flag-off regression: see §5.

## 5. Flag-off regression (existing QA suites on a copy with HOME_INSTALL_FEATURE='off' vs the alpha.7 base)
Copies of the repo: `off` = this branch with `HOME_INSTALL_FEATURE='off'` in app + /invite/; `base` = app + /invite/ from
`origin/main` (alpha.7). Same harness, same machine, run in parallel:

| suite | base (alpha.7) | flag off (alpha.7.1) |
|---|---|---|
| tests/f04/test_f04.py | 117 passed, 8 failed, 1 skipped | 117 passed, 8 failed, 1 skipped — the same 8 |
| tests/f05/test_f05.py | 68 passed, 20 failed, 1 skipped | 68 passed, 20 failed, 1 skipped — the same 20 |
| tests/f06/test_f06.py | 70 passed | 70 passed |

The failing F04/F05 cases fail identically on alpha.7 itself (version pins, protected-function refs of older bases, and
cases superseded by F05/F06 — e.g. the F04 "קישור הצטרפות לקבוצה" row replaced by F06), so they are pre-existing, not F04H.
With the flag ON, F04 cases that pin the old gate texts ("קיבלת הזמנה לנהל טיול?", "כניסה עם הזמנה", the /invite/ note) are
expected to change — the QA suite for F04-HOME owns those.
