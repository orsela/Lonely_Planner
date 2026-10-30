# F21 · dev notes — app side (v3.0.0-alpha.8)

<!-- CHANGE 2026-10-27 F21-DOCS-02: new file (no previous version). -->

Contract: `docs/F21_spec.md` §1.6–§1.9, §1.11, §5.2, criteria 1, 11–16 (client side), 18–20. Mockup: canvas row 9, artboards
`F21_Choose`, `F21_Admin`, `F21_Approve`, `F21_ApproveReplace`, `F21_Reject`, `F21_WizardPrefill` (read with the Artifact tool;
spec text wins where they differ, §5 below). Base: hotfix `313eb14` (3.0.0-alpha.7.2). Nothing deployed, pushed or committed by
this developer; everything below ran locally (fake supabase-js, route-intercepted functions).

## 1. What changed (all in `app/index.html` unless noted)

| Area | CHANGE ID | What changed from alpha.7.2 | Spec |
|---|---|---|---|
| flags script | F21-FLAG-01 | new `const REQUEST_FEATURE='on'` right after `HOME_INSTALL_FEATURE` | §1 |
| new `<style>` block after the F03 styles | F21-UI-01 | `pt-f21-*` classes only (tabs, badges, meter, cards, sheets, wizard box/tags) | §1.6–§1.11 |
| F03 block, `openAdmin` | F21-ADMIN-01 | 1 line: `req.tab=null` (default tab chosen again on every open) | §1.7 |
| F03 block, `loadAdmin` | F21-ADMIN-02 | 1 line: `loadReq()` in parallel with `admin_trip_summary` (so `online` re-loads both) | §1.7 |
| F03 block, `renderAdmin` (end) | F21-ADMIN-03 | 1 line: `reqDecorate(el)` — tabs on top; requests tab replaces the body; groups tab = alpha.7.2 screen untouched | §1.7 |
| F03 block, `adminClick` | F21-ADMIN-04 | 1 line: `reqClick(t)` (tabs, approve, reject, retry) | §1.7 |
| F03 block, new functions | F21-ADMIN-05 | `loadReq`, `reqDecorate`, `reqCard`, `reqBody`, `openApprove`, `openReject`, D16 `reqDraft`, countries.json names (he/en) | §1.7–§1.9, §5.2 |
| F20 block, `showChooser` | F21-CHOOSE-01 | 1 line: `loadReqCount()` (super-admin only) | §1.6 |
| F20 block, `renderChooser` | F21-CHOOSE-02 | 1 line: `reqBadges()` after the admin row is built | §1.6 |
| F20 block, new functions | F21-CHOOSE-03 | `loadReqCount`, `reqBadges` (new sub text, indigo requests badge, amber badge text "<M> הזמנות ממתינות") | §1.6 |
| F04 block, `afterVerified` | F21-WIZ-01 | 1 line: `f21Prefill(res)` after `wz.invite=…` | §1.11 |
| F04 block, `step1` (end) | F21-WIZ-02 | 1 line: `f21Step1()` — green box, "מהבקשה" tags, date `min` | §1.11 |
| F04 block, `step2` | F21-WIZ-03 | 1 line: `f21Countries()` after the data load — requested countries via `addCountry` (currencies derived as by hand), once | §1.11 |
| F04 block, new functions | F21-WIZ-04 | `f21Prefill`, `f21Step1`, `f21Countries` | §1.11 |
| `PT_VERSION`, `APP_VERSION` | F21-VER-02 / -01 | `'3.0.0-alpha.7.2'` → `'3.0.0-alpha.8'` (CHANGE comment prepended, chain kept) | §6.20 |
| `scripts/dev/fake_supabase.js` | F21-DEVFAKE-01/02 | additive: own `platform_admins` row and `rpc('admin_trip_requests')` from sessionStorage `{admins, requests, mail_today, cap}`; other rpc → PGRST202; every existing table/branch unchanged | brief |
| `scripts/dev/f21_app_smoke.py` | F21-DEVSMOKE-01 | new | — |
| `scripts/dev/f21_static_check.py` | F21-DEVCHK-01 | new | — |

Not changed: `app/sw.js` (no previous feature touched it for a version bump; the update check reads `APP_VERSION` from the page),
`<title>`, the manifest, every protected function. Existing lines removed/changed vs `313eb14`: exactly **2** (the version lines);
everything else is additive. The three IIFEs each have their own `const REQ = REQUEST_FEATURE==='on'`; every hook line starts
with `if(REQ…)`.

## 2. Flag

| `REQUEST_FEATURE` | Effect |
|---|---|
| `'on'` (default) | as §1 above |
| `'off'` | alpha.7.2 exactly: no tabs, no `admin_trip_requests` call (chooser or admin), chooser row "כל הקבוצות והזמנת מנהלים" + "<M> ממתינות", wizard ignores `prefill` (also the requester name) |

Needs `ADMIN_FEATURE='on'` (admin tab), `SWITCH_FEATURE='on'` (chooser badge), `WIZARD_FEATURE='on'` (pre-fill); each part is
simply absent when its host block is off.

## 3. Behaviour details / interpretations

- **Default tab** (§1.7): requests when N>0, else groups; decided once per open, when the list arrives. Until then (or when the
  list call fails / is offline at open) the groups tab is shown, so the F03 screen never waits for the new call. A
  `not_platform_admin` from `admin_trip_requests` hides the tabs (F03's own summary call closes the screen in that case anyway).
- **M** in "קבוצות והזמנות · M" = the F03 "הכל" count (pending + expired invites + active + ended trips); no count while loading.
- **Card order**: sorted client-side by `verified_at` ascending (does not trust server order).
- **Relative time**: עכשיו / לפני N דקות / לפני שעה / לפני שעתיים / לפני N שעות / אתמול / לפני יומיים / לפני N ימים (from `verified_at`).
- **Travellers**: "1" reads "מטייל אחד", otherwise "N מטיילים".
- **Country names** come from `countries.json` (he for cards/sheet, request language for D16); fallback = F03's `COUNTRY_HE`, then the code.
- **D16** (§5.2): first two names joined " ו" (he) / " & " (en), " ועוד N" / " +N", " · <month year>" in the request language, cut to 80.
  Example: JP+KR, 2027-04 → "יפן ודרום קוריאה · אפריל 2027" (the artboard's "יפן וקוריאה" is a shortened name not in countries.json).
- **Approve**: empty draft name is refused inline ("צריך לתת שם זמני לטיול."), >80 → F03's `invalid_name` text. ok → toast, the card
  leaves at once, then `loadAdmin()` (both lists; the groups tab gains the invite). `email_failed` → toast, the sheet **stays
  open** with the button restored (retry without retyping). `request_closed` → sheet closes, toast "הבקשה כבר טופלה", list
  refreshed. Other codes → F03's `errText` inline. Error code is read from `{ok:false, code}` (any HTTP status) or invoke()'s
  `{error}` — the server developer's `invite-manager` returns `{error:'email_failed'}` 502 / `{error:'request_closed'}` 409, both handled.
- **Reject**: success toasts — "הבקשה נדחתה ונשלחה הודעה במייל" (mail asked, sent), "הבקשה נדחתה" (no mail), "הבקשה נדחתה, בלי מייל
  (התקרה היומית מלאה)" (`mail_skipped:'daily_limit'`, spec), "הבקשה נדחתה, המייל לא נשלח" (`mail_skipped:'email_failed'`). The
  first, second and fourth texts are mine (spec defines only the cap one). The preview hides when the box is unchecked. At the cap
  (meter `mail_today ≥ cap`) the box is disabled + unchecked with the cap line and `send_mail:false` is sent.
- **Sheets** have no × (the artboards have none); close = "ביטול", backdrop, Escape (F03 sheet layer).
- **Offline**: as F03 — notice "אין חיבור — הרשימה תתעדכן כשהרשת תחזור", list kept if it was loaded, approve/reject disabled; `online` reloads.
- **Wizard date picker** (§1.11 "opens on the requested month"; changed 2026-10-30, F21-WZ-01/02, architect answer to Q1): a native
  `<input type=date>` cannot be told which month to open on, and a `min` would forbid an earlier start, so no `min` is set.
  Instead, while no start date is picked and the request has a month, a help line `#ptWzF21Month` "בבקשה: <month year>"
  (Hebrew month names) sits under the start-date field; it hides once a date is picked (shows again if cleared). Null month → no line.
- **Wizard tags**: "מהבקשה" on שם הטיול (when it equals the invite's draft name) and on השם שלך בקבוצה (when it equals the
  requester name); the green field tint goes away at the first edit; the existing help "מולא מההזמנה, אפשר לשנות" is removed when
  the tag is shown (the artboard has the tag instead). Requested countries are added once per wizard (a removed country does not
  come back after "חזרה").
- Gender: "<name> יקבל/תקבל …" and "<name> יכול/ה …" with the full name (the artboards inflect a first name; we do not know gender).

## 4. How to run

```
python3 scripts/dev/f21_static_check.py              # base 313eb14 (alpha.7.2) by default
PYTHONPATH=/root/.local/share/uv/tools/pytest/lib/python3.13/site-packages \
  F21_SHOTS=<dir> python3 scripts/dev/f21_app_smoke.py
```
The smoke reuses `tests/f06/harness.py` (→ F05 → F20 → F04 → F03 → F02) unchanged and subclasses its backend with
`admin_trip_requests`, `approve_request` / `reject_request` and lookup `prefill`. Results at the time of writing: static ALL OK,
smoke 94/94 (2026-10-30, after F21-WZ-01).

Regression (`tests/run_all.sh --only "f03on f04 f20 f06"`, clone deepened to full history, 2026-10-30):

| Job | Result | Failures |
|---|---|---|
| f03on | 47 passed, 1 failed, 1 skipped | `test_ac18_static[app_version]` — version pin (qa_versions.json = alpha.7.2) |
| f04 | 116 passed, 2 failed, 1 skipped | `test_c21_static[app_version|pt_version]` — version pins |
| f06 | 70 passed | — |
| f20 | 74 passed, 6 failed | 2 version pins; 4 intended §1.6 changes: `test_b01…`, `test_c01…` ("כל הקבוצות והזמנת מנהלים" → "בקשות, קבוצות והזמנת מנהלים"), `test_c02_pending_badge[two]` ("2 ממתינות" → "2 הזמנות ממתינות"), `test_d01_network_reads_only_spec_tables` (new RPC `admin_trip_requests`). The same 4 (6 cases) pass on a copy with `REQUEST_FEATURE='off'`. |

## 5. Deviations from the mockup (spec wins)

- Approve-replace line: spec's common line "<name> יקבל/תקבל מייל הזמנה להקמת הטיול, כמו הזמנת מנהל רגילה (תוקף 7 ימים)." (artboard: "…מייל הזמנה חדש, ממולא מהבקשה…").
- Approve-replace pre-fill box has the "שפת המייל" row and "(תאריכים בוחרים באשף)" after the month (spec §1.8; artboard omits both).
- Chooser footnote ("חדש ב-F21…") and the wizard line "לוח השנה נפתח על …" are annotations, not shipped.
- The approve button in a card is wider than "דחייה" (flex 1.6 : 1) so "אישור · מחליף את ההזמנה" stays on one line at 390px.

## 6. Open questions for the architect

1. Date picker: is `min` = 1st of the requested month acceptable (blocks an earlier first pick), or should we only show a help line?
2. QA version pins: `tests/qa_versions.json` still says `3.0.0-alpha.7.2` (not my file); the release step must bump it to alpha.8.
3. F20 QA asserts the alpha.7.2 chooser texts ("כל הקבוצות והזמנת מנהלים", "<N> ממתינות"); with the flag on these change by spec §1.6.
   These cases need a flag-off supplementary job (like `sup_f04_home`) or an F21 update of the expectations.
4. Should an empty draft name be allowed on approve (server accepts `null` for F03 `create`)? Implemented: required.
5. Reject success toasts other than the cap one are not in the spec (texts in §3 above).

## Architect answers (2026-10-30)
1. Wizard date picker: no `min` (it would forbid an earlier start). Instead a help line under the start-date field, "בבקשה: <month year>", while no date is picked (F21-WZ fix).
2. `tests/qa_versions.json` bumped to alpha.8 / alpha.8.0 (e2d0d13).
3. F20 §1.6 changes: the QA team adds a flag-off supplementary job (as `sup_f04_home`) and updates expectations.
4. Draft name required on approve: accepted.
5. Reject toasts "הבקשה נדחתה ונשלחה הודעה במייל" / "הבקשה נדחתה" / "הבקשה נדחתה, המייל לא נשלח": accepted.
