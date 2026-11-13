# F23 — client dev notes (`/request/` page, app admin screen)

<!-- CHANGE 2026-11-13 F23-DOCS-12: new file (no previous version). Client stage of F23; the server stage is in
     docs/F23_dev_notes_server.md. Spec: docs/F23_spec.md. -->

Branch `f23`. App **3.0.0-alpha.12** (`APP_VERSION`, `PT_VERSION`); `/request/` page 3.0.0-alpha.12. Nothing merged or
deployed. Per the push rule the client stays on the branch until migration 0020 and the two functions are live.

## `/request/` (request/index.html)
| Flag (top of the script) | Shipped | Meaning |
|---|---|---|
| `REQUEST_FEATURE` | `'on'` | unchanged (F21): `'off'` = the closed card, no network |
| `REQUEST_MODE` | `'auto'` | `'manual'` = the alpha.8 texts (hero, privacy, code screen) — the F21 page |
| `SUGGEST_FEATURE` | `'on'` | `'off'` = no "יודע/ת לאן / עוד לא החלטתי" choice |

- The screen after the code follows the **server's answer** (`next`), not the page flags: `ready` → the new ready screen,
  `suggest` → the ideas, none → the F21 "request sent" screen.
- Screens: `data-screen` = `form | code | suggest | ready | sent | limit | inapp | closed`. New ids are listed in the
  comment at the top of the file.
- Copy is taken from the approved artboards `FB_Request`, `FB_Suggest`, `FB_Ready`. Copy **not** in the artboards,
  written here (Or to confirm on the phone check):
  - all English texts of the new parts (the feedback doc has no English wording);
  - code screen in auto mode: button "אימות והמשך", footer "לא הגיע? בדקו בתיקיית הספאם." (the F21 texts spoke of approval);
  - undecided form errors "בחרו לפחות דבר אחד." / "עד 100 תווים."; fallback line "בוחרים מדינה מהרשימה וממשיכים כרגיל.";
    loading line "מחפשים יעדים שמתאימים לכם…"; session expired toast "עבר יותר מדי זמן. מתחילים מחדש.";
    continue button before a pick "בחרו יעד כדי להמשיך"; ready step 1 without a month "…היעד כבר ממולא."
- Behaviour choices:
  - No idea is pre-selected (the artboard shows one selected as an example); the continue button is disabled until a pick.
  - The undecided form hides the long "משהו שכדאי שנדע?" note (the artboard has only the short "עוד משהו?").
  - Touch targets of the interest chips are 44 px (40 px in the artboard) — criterion 12.
  - The suggest screen has no language switch (the ideas come in the request's language); the ready screen has one.
  - The ready data incl. the invite token is kept in `sessionStorage` (`pt:_device:rq_ready`, this tab, 24 h) so a reload
    still shows the button. The suggest session is memory only: a reload on the ideas screen returns to the form.
  - `suggest` uses a 25 s client limit (the server waits up to 10 s for the model).

## App admin screen (app/index.html)
- New flag `REQAUTO_FEATURE='on'` (`'off'` = the alpha.11 screen). Additive: `reqA`, `reqAutoState`, `reqAutoCard`; three
  flagged insertions in `loadReq`, `reqBody`, `reqClick`.
- Meter card: second row "הצעות AI היום N מתוך 30" (`#ptReqAi`), only when the server sends `ai_cap`.
- Under the pending requests: "נפתחו אוטומטית · N" (`#ptReqAutoTitle`, `#ptReqAuto`), one card per request with the badges
  "נפתח אוטומטית", the invite state (ממתין להקמה · בתוקף עד dd/mm / הטיול הוקם / ההזמנה בוטלה / פג תוקף) and, when the
  destination came from the ideas, "יעד מהצעות AI". An open invite has the button "פעולות · ביטול ההזמנה" → the existing
  F03 invite sheet (resend / revoke with confirmation). The automatic invites also appear in "קבוצות והזמנות" like any invite.
- **No mockup existed for this screen** (C11 was approved as text). Screenshot shown to Or 13/11; `REQAUTO_FEATURE='off'`
  reverts it.
- The default tab rule is unchanged (requests tab only when something waits for approval), so in auto mode the screen
  opens on "קבוצות והזמנות" and the start chooser shows no requests badge.

## Tests (local, 2026-11-13)
`tests/f23/run.sh` → db 49/49 (+ regression as in the server notes), int 11/11, f21 function suites green,
**page 8/8** (`tests/f23/request_page_test.mjs`: criteria 1, 2, 3 page side, 4, 5, 6, 8, 9, 11, 12 at 390 px, he + en),
**app 3/3** (`tests/f23/test_f23_admin.py`). F21 browser tests `c11_admin_requests_tab`, `c11_chooser_badges`,
`c19_admin_requests_offline` pass on the new app.

## Not done / not tested
- **The F21 browser suite (`tests/f21/test_f21.py`, ~8 min) was not run on the new `/request/` page.** As shipped
  (`auto` / `on`) its request-page cases are expected to fail on the new texts; criterion 11 needs a run with the page
  served with `REQUEST_MODE='manual'`, `SUGGEST_FEATURE='off'` (the harness swaps flags the way it does for
  `REQUEST_FEATURE`). For the QA stage.
- Full regression `tests/run_all.sh`, independent QA, offline behaviour of the new screens, iPhone / in-app browser path
  into `/invite/` from the ready button, real Turnstile, real function, real AI answers.
- `tests/qa_versions.json` app line is still alpha.8 (stale since F10); the F23 tests pass `QA_EXPECTED_VERSION`.
- Line 2 of the hero ("…וקישורים לחיפוש טיסות ומלונות") describes F24, which is not built yet — see STATUS.
