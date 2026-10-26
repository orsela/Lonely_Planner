# F04-HOME · Independent QA suite — in-app browser hop, install cards, gate "כניסה עם המייל", code-screen resume (3.0.0-alpha.7.1)

<!-- CHANGE 2026-10-26 F04H-QA-01: new file (no previous version). -->

Contract: `docs/F04-HOME_spec.md` at commit **ee5c723** (alpha.7 code + the spec) **only**. The F04-HOME implementation
(app/index.html and invite/index.html after ee5c723, any F04-HOME dev notes) was not read; the suite was written before it
existed. The alpha.7 code at ee5c723 was read for existing ids and harness behaviour only. Conventions follow F05/F06
(`tests/f05/*`, `tests/f06/*`).

## Files

| File | What | Cases |
|---|---|---|
| `harness.py` | Extends the F06 harness (→ F05 → F20 → F04 → F03 → F02; fake supabase-js with Realtime `tests/f05/fake_supabase.js` reused unchanged). Adds: invite-manager / create-trip routing (the F05/F06 route handler aborted them), `F4HBackend` (manager account with 0/≥1 active trips, used invite → lookup `{found:false}`, send / verify / check logs), devices with UA presets (Gmail iOS WKWebView without `Safari/`, Outlook iOS, GSA iOS, Gmail Android WebView `; wv)`, Safari iPhone, Chrome Android, desktop) and `navigator.standalone` / `display-mode: standalone` variants, capture of `x-safari-https:` / `intent:` navigations (Navigation API `navigate` event + `window.open`; the navigation is recorded on the Python side and cancelled, the page stays), fake `beforeinstallprompt` (prompt() calls recorded) and `appinstalled`, HOME_INSTALL_FEATURE flips for app/ and /invite/. | — |
| `test_f04home.py` | Playwright, 390×844, he-IL, Asia/Jerusalem, clock installed at 2026-10-12 06:00Z and moved with `page.clock`. | **41** test functions, **93** collected cases |
| `run.sh` | Runner: `--only f04h \| off \| static`. | — |
| `off_baseline_ee5c723.txt` | Failures of the F04/F05/F06 suites on ee5c723 itself (pre-existing, not F04-HOME); `--only off` ignores them. | 3 F04 + 13 F05 |

## How to run

```bash
tests/f04home/run.sh                 # browser suite + flag-off regression
tests/f04home/run.sh --only f04h     # the browser suite (≈6 min)
tests/f04home/run.sh --only static   # F4H-13 only
tests/f04home/run.sh --only off      # criterion 1: repo copy with HOME_INSTALL_FEATURE='off' in app/ AND invite/ →
                                     # F04 (tests/f05/run.sh --join on --only f04), F05 (--only f05), F06 (tests/f06/run.sh --only f06)
OFF_SUITES="f04 f05 f06 f20" tests/f04home/run.sh --only off   # + F20
```

Env: `REPO_DIR`, `APP_DIR`, `BASE_REF` (default `ee5c723`, the "before" for protected functions and duplicate ids),
`QA_HEADFUL=1`. pytest fallback path: `/root/.local/share/uv/tools/pytest/lib/python3.13/site-packages`. No Supabase,
no network.

Expected failures in the `off` run (spec criterion 1 "except version pins"): F05 `test_s01_static[app_version|pt_version|change_comments]`
(pins alpha.6 / F05 tag rule). F04/F20 version pins are deselected by `tests/f05/run.sh`. Failures that already occur on
ee5c723 are listed in `off_baseline_ee5c723.txt` and not counted: F04 `test_c15_more_join_link_row[manager]`,
`test_n01_no_old_name_rendered[more_sheet]`, `test_n03_whatsapp_text_name_and_url[sheet]` (the "עוד" sheet as changed by
F06) and 11 F05 cases (pending-name, removed identity, claim, home pending card, layout, node_check/duplicate ids vs its
alpha.5.1 reference). Anything else is a finding.

### Selectors
F04-HOME ids are not in the spec: elements are found by the §1 Hebrew texts (`TXT` at the top of `test_f04home.py`). alpha.7
ids the spec keeps unchanged are used as in F05 (`#ptF05Otp0`, `#ptF05Claim`, `#ptF05LinkBtn`, `#ptF05LinkIn`,
`#ptDeviceCode`). Wizard screens are detected by the F04 suite's text markers (`f04.screen`). The resume key is read by
name (`pt:_device:wz_resume`, raw localStorage on a blank page of the same origin).

## Criteria → tests

| # | Criterion (short) | Tests |
|---|---|---|
| 1 | flag off = alpha.7 | F4H-01a (invite text == ee5c723 page, 5 UAs), 01b gate, 01c no resume/no key, 01d done; `run.sh --only off` |
| 2 | in-app / real browser / invalid on /invite/ | F4H-02a [4 in-app UAs], 02b [3], 02c [4 UAs × #invite / ?t=] |
| 3 | iPhone button-only Safari hop | F4H-03a [Gmail iOS, GSA iOS] (no auto nav in 3 s; exact `x-safari-https://host/path#invite=<t>`) |
| 4 | Android one automatic intent hop; `?t=` consumed and removed | F4H-04a (exact intent URL, exactly one, fallback = same URL), 04b [3 UAs], 04c (token never stored/logged) |
| 5 | iPhone Safari install card; skip link = today | F4H-05a, 05b, 05c [standalone variants] |
| 6 | Android: no install card, C2 line | F4H-06a, 06b (desktop = today) |
| 7 | gate: "מנהל/ת טיול" first; entry; F05 + device-code cards work | F4H-07a [iPhone, Android], 07b (two bullets), 07c (entry → email → open invite → step 1), 07d |
| 8 | C3 | F4H-08a (used invite + 1 trip → that trip opens, no reload by the test), 08b (no trips → "לא מצאנו הזמנה") |
| 9 | resume | F4H-09a (3 min: code screen, same email, banner N=3, role=status, no 2nd send, key schema), 09b (cooldown continues), 09c (invite origin, `?invite=1`), 09d (10 min → normal start, key gone), 09e [verify / שינוי מייל / exit], 09f (never code / token), 09g ("איפה הקוד?" card) |
| 10 | done install card / standalone | F4H-10a (iPhone ticks, email LTR, "אחר כך" enters), 10b (BIP → prompt once → appinstalled text), 10c (no BIP → manual hint), 10d [3 standalone variants] |
| 11 | 390px, RTL, ≥44px, LTR emails | F4H-11 [inapp_ios, inapp_android, install_ios, install_android, gate, code_resumed, done_ios, done_android] |
| 12 | offline | F4H-12a [4 UAs], 12b (resume offline never claims "עדיין תקף", no send, verify/resend disabled) |
| 13 | static | F4H-13 [7 protected functions, app_version, pt_version, invite_version_comment, flag_declared, change_comments, node_check, no_duplicate_ids, no_live_project_ref] |
| 14 | advisors | F4H-14 (skip: dashboard check) |
| — | harness sanity | F4H-00a (backend semantics), 00b [4 UAs] (UA, standalone variants, external-nav capture, BIP, clock across reload), 00c (invite-manager + create-trip routing) |

## Self-check against ee5c723 (implementation not present), 2026-10-26

`pytest test_f04home.py`: **93 collected → 46 passed, 46 failed, 1 skipped** (≈6 min; first run had a test-side bug in
the node --check script extraction, fixed). Every failure is "F04-HOME UI / behaviour missing" or a static pin
(versions, flag, F04H CHANGE tags) — no harness error. Passes (all expected on alpha.7):

- harness sanity: F4H-00a, 00b ×4, 00c;
- flag off: F4H-01a ×5, 01b, 01c, 01d (the flag is absent at ee5c723, so the served page IS alpha.7);
- cases whose expected outcome is the same in alpha.7: 02b ×3 (no in-app card in real browsers), 02c ×8 (invalid token),
  04c (token not stored), 05c ×2 (no install card in standalone), 07d (F05 / device cards), 10d ×3 (no card in standalone),
  12a ×4 (offline invite page);
- static: 7 protected functions, no_duplicate_ids, no_live_project_ref, node_check.

`run.sh --only off` on ee5c723 (≈45 min): the flag is missing, so the copy equals the repo (warned). F06 70/70; F04 118 pass /
3 fail; F05 75 pass / 13 fail / 1 skip — all 16 failures exist on ee5c723 itself (recorded in `off_baseline_ee5c723.txt`),
so after the implementation the off run must show no failure outside that list and the version pins.

## Run on the implementation (7fdd234 + this suite, branch qa-run), 2026-10-26

| Run | Collected | Passed | Failed | Skipped / xfail |
|---|---|---|---|---|
| browser suite 1.0.0 | 93 | 91 | 1 (F4H-09e[exit], category c) | 1 skip (F4H-14) |
| browser suite 1.0.1 (F04H-QA-FIX-01) | 93 | 91 | 0 | 1 skip + 1 xfail (F4H-09e[exit]) |
| `--only static` | 15 | 15 | 0 | — |
| `--only off` (flag flipped in both files) | F04 121 / F05 89 / F06 70 | 118 / 75 / 70 | 3 / 13 / 0 — exactly the ee5c723 list | F05 1 skip |

Details and triage: `docs/qa/F04-HOME_QA.md` (branch qa-run).

## Harness finding (outside F04-HOME)
`tests/f05/harness.py` `STANDALONE_JS` builds its fake `MediaQueryList` with `Object.assign` onto an object whose prototype
is `MediaQueryList.prototype`; `matches` is getter-only there, so every `matchMedia('(display-mode: standalone)')` call
throws in F05/F06 standalone devices. This suite uses its own plain-object fake (F4H-00b checks it).

## Spec ambiguities (written before the implementation; dev decisions reported 2026-10-26 settle 1, 4, 5, 8, 12, 13)
1. §3.3 "same origin family": undefined. Tests: a gate send resumes from the gate entry; an invite send resumes on `?invite=1`.
2. §3.3 "explicit exit": no exit control is named for the code screen. F4H-09e[exit] looks for a visible "חזרה" / "ביטול" / "יציאה" / "סגירה" there and fails if none.
3. §3.3 "Clear on … TTL": whether an expired key must be deleted or only ignored. F4H-09d requires it gone after the reopen.
4. Resume after reload in the installed app: automatic, or only after tapping "כניסה עם המייל"? Tests accept both.
5. Criterion 12 "never claims a code is valid when offline (text unchanged …)": read as "no 'עדיין תקף' while offline; today's offline line; send/verify disabled".
6. §1.2 desktop "today's page unchanged" vs "the installed-app note now names 'כניסה עם המייל'": tests require the new wording wherever the note shows.
7. §1.2 "valid card shrinks to one row" on iPhone: F4H-05a requires today's "מה יקרה עכשיו" card to be gone there; Android/desktop keep it?
8. §1.3 bullet texts are not given (F4H-07b only counts two); badge "חדש" assumed visible text.
9. §1.6 desktop browser tab (not standalone, neither iPhone nor Android): which install-card variant, if any — not tested.
10. §1.4 banner minutes: rounding (floor/round) and singular ("דקה") not specified — tests use N = 2 and 3 (+5 s).
11. §3.1 isIOS for iPad (desktop UA + touch) is not defined — not tested.
12. Email-screen texts in the new entry ("Same flow … with the new texts"): which texts change is not listed; tests detect the email step by its input + "שליחת קוד" only.
13. §1.1 iPhone manual steps: exact wording not given beyond "הכפתור לא עבד?" and "פתיחה בספארי".
