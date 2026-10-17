# F20 · QA report — super-admin start chooser, standalone admin, in-trip switcher

Version: app 3.0.0-alpha.5 (`SWITCH_FEATURE`) · F20 QA suite 1.0.0 · F03 suite 1.0.3 · F04 suite 1.4.0 · 2026-10-16.
CHANGE 2026-10-13 F20-QA-01: first version of this report (no previous version).

Contract: `docs/F20_spec.md`, the dev notes §4 ("For QA — stable ids and visible texts") and §6 (open points / architect
decisions) only. The implementation in `app/index.html` was not read; the static checks grep only version constants and
visible strings. The architect's decisions are treated as spec: with WIZARD off + SWITCH on, a non-admin boots the cached trip;
the admin check has its own ~2.5 s bound and a timeout counts as not super-admin; the sheet has a × close button; one member is shown as "חבר אחד".

## Automated
Branch `f20` @ 9d703e2 (+ QA files below), sandbox only (no Supabase, no network services). Playwright 390×844, Chromium.
Runner: `tests/f20/run.sh` (runs every regression suite twice: the app as delivered, `SWITCH_FEATURE='on'`, and a copy with `'off'`).

| Suite | SWITCH_FEATURE='on' (as delivered) | SWITCH_FEATURE='off' |
|---|---|---|
| F20 browser suite (tests/f20/test_f20.py 1.0.0; its off / ADMIN-off / WIZARD-off / layout cases are flipped inside the suite) | **77/77** | (covered inside: `test_b03_switch_off_is_alpha42`) |
| F04 browser suite 1.4.0 | 126/126 | 126/126 |
| F03 regression, WIZARD on | 47 passed, 1 skipped, 11 deselected | 47 passed, 1 skipped, 11 deselected |
| F03 regression, WIZARD off | 55 passed, 1 skipped, 3 deselected | 55 passed, 1 skipped, 3 deselected |
| F02 regression, WIZARD on | 36 passed, 1 skipped, 3 deselected | 36 passed, 1 skipped, 3 deselected |
| F02 regression, WIZARD off | 36 passed, 1 skipped, 3 deselected | 36 passed, 1 skipped, 3 deselected |
| Deno: F04 function tests · create-trip · invite-manager | 31/31 · 9/9 · 21/21 (no function change in F20) | — |
| DB / Edge Functions | `git diff main --stat`: only app/index.html, docs, tests; no `supabase/` or `*.sql` file → **no migration needed** | — |

The skipped tests point to the real database (F02 C16 and F03 DB/function level). The deselected tests are the same lists as the F04 runner, and nothing was added for F20. Run on their own against alpha.5, they fail exactly as before:
- F03: version pins alpha.3.4, the /invite/ "בקרוב" button, and the F03 landing that F04 replaced.
- F02: version pins alpha.2, and the manifest name that F04 §8 changed.

### Failures before the regression update (all expected by spec, none a defect)
These are the suites as committed at c8f9d10, run against alpha.5 with SWITCH on:
- **F03 WIZARD on: 17 failed.** These are `test_ac02_admin_entry_for_admin`, `test_ac02_admin_rpc_refused_shows_no_list`, `test_ac03…`, `test_ac04…`, `test_ac05…` ×2, `test_ac07…` ×2, `test_ac08…`, `test_ac09…`, `test_ac13…`, `test_ac14…` ×3 and `test_ac17_390_rtl_touch[admin|invite-sheet|actions-sheet]`.
  - Cause: a super-admin now boots on the chooser (F20 §1.1), so `boot()` timed out waiting for the home screen. The "ניהול מערכת" row is also gone from "עוד" (F20 §1.5, AC9).
- **F04: 4 failed.**
  - `test_c21_static[app_version|pt_version]`: the version is now alpha.5.
  - `test_n01_no_old_name_rendered[admin]`: same cause as the F03 failures (the admin path).
  - `test_c19_boot_prefers_cached_trip_only_when_on[off]`: the architect's decision, dev notes §6.6.
- F02: no F20 failures.

### Regression updates (`CHANGE 2026-10-13 F20-QA-02`, minimal, flag-detected so 'off' runs the old path unchanged)
- **tests/f03/test_f03.py 1.0.2 → 1.0.3**
  - `boot()`: when the chooser shows, it taps the trip's row. `enter=False` stops on the chooser.
  - `open_admin()`: when the avatar exists, it goes avatar sheet → "ניהול מערכת"; otherwise through "עוד" as before.
  - New helpers `switch_ui`, `open_switch_sheet` and `open_switch_admin`.
  - `test_ac02_admin_entry_for_admin`: with SWITCH on, the row must be absent from "עוד" and present with "סופר-אדמין" in the sheet. The admin screen opens, "הטיולים שלי" leads to the chooser, and the admin flag is not persisted.
  - `test_ac02_admin_rpc_refused_shows_no_list` and `test_ac14_offline_admin`: with SWITCH on, they enter through the chooser's admin row.
- **tests/f04/test_f04.py 1.3.0 → 1.4.0**
  - `VERSION` is now 3.0.0-alpha.5.
  - `test_c19_boot_prefers_cached_trip_only_when_on[off]`: it expects the cached trip when the served app has SWITCH on (dev notes §6.6), and still expects the newest membership when SWITCH is off.

### F20 suite coverage (criterion → tests)
| AC | Tests |
|---|---|
| 1 flag off = alpha.4.2 | `b03` (no #ptChoose / avatar, F03 row in "עוד", admin "חזרה…" back) + the whole F02/F03/F04 matrix with SWITCH off |
| 2 chooser, no trip started | `b01` (no tab bar/chat/FX, `html.pt-choose`, `__PT.started===false`, `tripData` undefined, no trip_kv read, footnote not shipped) |
| 3 list / enter / pending | `c01` (4 trips newest first, foreign + removed membership hidden, names, sub lines incl. cross-year dates and "חבר אחד", sort-0 flag, pin svg, "אחרון"), `c01b`, `c02[two\|zero\|rpc_fail]`, `c03` loading + aria-busy, `c03b` failure + retry, `c04` enter without reload (same document, right trip id, cache, only that trip's trip_kv), `c05` member count refused → part omitted |
| 4 standalone admin | `a01` (row → admin in place; header "הטיולים שלי", no "חזרה לטיול", "Lonely Planner · סופר-אדמין"; → chooser; back / forward), `a02` |
| 5 `#admin` | `b04` (super-admin, no trip started), `b05` (non-admin → trip, hash cleaned) |
| 6 D3 | `b06` (`?choose=1` with D3 on, query removed), `b07`, `c06` (off by default, key "1", no navigation, next boot, uncheck removes key) |
| 7 non-admin switcher | `s01[v2_min\|v2\|v1 × one\|two]`, `s04[wizard on\|off]` (switch reloads, sticks after reload), `s05[backdrop\|escape\|back\|x]`, `s06` |
| 8 super-admin in trip | `s02[one\|four]`, `s03` (sheet content, email LTR, current row check + "כאן עכשיו", "ניהול" section), `a03` (sheet → admin reload, → chooser with D3 on) |
| 9 "עוד" | `s08` (#ptAdminRow not in DOM, "מייל מקושר" stays) |
| 10 offline | `b08[superadmin\|non_admin]` (offline boot → cached trip), `s07[trip\|admin]` (toast, no navigation) |
| 11 admin check failure | `b09` (failure), `b10[non_admin\|superadmin]` (hang: trip after 2.66 s vs 0.1 s control, ≤3 s), `b15` (check runs in parallel with fetchTrips: +0.02 s with both 1.5 s slow) |
| 12 390px | `l01[chooser\|chooser_none\|admin_header\|sheet]` + `s01` (avatar 44×44 circle, top-left of the header, no overlap / covering in v2+HOME_MIN, v2, v1) |
| 13 RLS / §2 | `d01`, `d02`, `test_harness_fake_semantics` (below); DB-side: no new SQL |
| 14 static | `st_static[...]`: protected ×7 byte-identical to `main`, APP/PT_VERSION alpha.5, `<title>` "Lonely Planner", flag next to ADMIN_FEATURE, F20 CHANGE comments present and near every changed hunk, `node --check`, no new duplicate ids (markup + live DOM in `l01`/`s03`), footnote absent |
| §1.4 other rows | `b11` (no trips → chooser + "אין עדיין טיולים"), `b12[trip_query\|invite]`, `b13` (ADMIN off: no chooser, sheet lists trips without "ניהול"), `b14` (Maps callback on the chooser harmless) |

### Network requests (spec §2, observed under the fake, `test_d01`)
Path: boot → chooser → admin → "הטיולים שלי" → chooser. Calls observed:
- `platform_admins` select: 1 (once per boot).
- `trip_members` select: 2 (own memberships, then the member count with `in(trip_id)` + status active).
- `trips` select: 1, with `in(id)`, own trips only.
- `trip_countries` select: 1.
- `rpc admin_trip_summary`: 3 (once per chooser show plus the admin list).

There were no writes, no other table, RPC or function, and no `trip_kv` read. Every `in(...)` asks only for the user's active trips. The first sheet open inside a trip adds only selects on trips, trip_countries and trip_members. A non-admin never calls the admin RPC (`d02`). The only external request is the static Google Maps `<script>` tag, which is the same markup as alpha.4.2 (see open question 1).

## Defects found
None in the product.

| # | Found | Cause | Fix |
|---|---|---|---|
| — | (test infra) a first draft of `test_c04` flagged "trip_kv read for another trip" on a key-less trip_kv query | QA filter bug: it matched queries that did not name any trip | the filter now flags only queries naming another of the user's trips |
| — | (test infra) `test_b08` checked the offline trip by `#tripName` | the trip name is not cached for offline use (F02 §3 behaviour), so the fallback name shows offline | `b08` now checks the running trip id (`__PT.tripId`) and the cache |

## Open questions
1. **Google Maps loads on the chooser and the standalone admin.** The static `<script …maps/api/js…callback=initMap>` tag is still requested before any trip starts. `test_b14` shows its callback does no harm there, and entering a trip still works. It does cost data, and it calls Google before the user picks a trip. Should it wait until a trip starts? The spec is silent.
2. **`admin_trip_summary` runs every time the chooser shows** (3 calls in a chooser → admin → chooser round trip). This is fine for the data size, but not cached; noted only.
3. **Sheet header name.** The sheet shows the display name of the *current trip's* membership. The chooser title uses the *newest* membership's name. Both match the spec wording, but a user with different names per trip sees two names.
4. **Offline at boot is simulated** with `navigator.onLine=false` plus an unreachable backend. The page itself is served locally, standing in for the service worker. The real installed-app offline start is on the phone list.
5. Not verifiable here (dev notes §6.15):
   - real RLS answers for the member-count `in(...)` query per role (a refused count is handled: `test_c05`)
   - iOS back gesture on the sheet
   - Safari flag emoji

## Phone checklist (tests/f20/MANUAL.md)
- [ ] Opening the app as super-admin shows "שלום <שם>, לאן נכנסים?", with no tab bar. The "ממתינות" badge has the right N, the trips are newest first with flags, and the last trip shows "אחרון".
- [ ] "ניהול מערכת" opens admin, with "Lonely Planner · סופר-אדמין" and "הטיולים שלי" and no "חזרה לטיול". "הטיולים שלי" returns to the chooser, and the back gesture from admin does too.
- [ ] In a trip, the avatar is top-left and covers nothing. The sheet shows name, email, ✓ "כאן עכשיו" and "ניהול מערכת". Choosing another trip reloads into it, and the choice sticks. The sheet closes on ×, backdrop and back.
- [ ] "עוד" has no "ניהול מערכת". "מייל מקושר" is still there.
- [ ] D3 "לפתוח תמיד ישר לטיול האחרון" opens the last trip directly. Admin → "הטיולים שלי" still shows the chooser. Unchecking it brings the chooser back.
- [ ] A non-admin device with one trip is unchanged and has no avatar. Opening `#admin` on it lands in the trip, with the hash cleaned.
- [ ] Airplane mode: the app opens into the last trip. Tapping another trip in the sheet shows "אין חיבור…" and stays.
- [ ] iOS back gesture on the sheet. Flag emoji in Safari.

## Files (QA)
- New: `tests/f20/test_f20.py`, `tests/f20/run.sh`, `tests/f20/MANUAL.md`, `docs/qa/F20_QA.md`.
- Changed: `tests/f03/test_f03.py` (1.0.3) and `tests/f04/test_f04.py` (1.4.0), both marked `CHANGE 2026-10-13 F20-QA-02`.

## alpha.5.1 (2026-10-17) — D7: admin and trips never mix
CHANGE 2026-10-17 F20-QA-03: new section. Contract: spec §0 D5 (amended) and D7, §1.3, criterion 8, plus dev notes §7 ("For QA" ids and texts, and the architect decision F20-D7-05). Branch `f20` @ 387111f; sandbox only.

### Test changes (all marked `CHANGE 2026-10-17 F20-QA-03`)
- **F20 suite 1.0.0 → 1.1.0**
  - `VERSION` is now 3.0.0-alpha.5.1.
  - `test_a03` now goes: running trip with D3 on → reopen at `?choose=1` → chooser, with the query removed → admin row → standalone admin (no trip started) → "הטיולים שלי" → chooser, with the D3 key untouched.
  - `test_s02` is now `test_s02_superadmin_avatar_only_with_two_trips[one|four]`: [one] expects no avatar in the DOM.
  - `test_s03`: the sheet must have no "ניהול" section, no `#ptSwitchAdmin`, and none of "ניהול מערכת" / "יציאה מהטיול למסך הניהול" / "סופר-אדמין".
  - `test_s07[admin]` is removed (the row no longer exists); `[trip]` is unchanged.
  - New tests:
    - `test_e01_no_admin_text_in_trip_ui[one|four]`: super-admin in a trip. The admin texts must not show on any tab (home, route, journal, budget, עוד), nor in the sheet when one exists. `#ptAdminRow` and `#ptSwitchAdmin` must not be in the DOM, and no control may point at `#admin`.
    - `test_e02_hash_admin_in_running_trip_reloads_to_standalone[hashchange|trip_query]`: `#admin` typed in a running trip, or a `?trip=<id>#admin` load, does a full reload into the standalone admin. It is never layered over the trip (sampled every 100 ms before the reload). After the reload `__PT.started` is false, `tripData` is undefined, there is no trip chrome, the header is right, and `?trip=` is dropped. "הטיולים שלי" → chooser.
    - `test_e03_hash_admin_non_admin_in_trip_cleaned_no_reload`: a non-admin who types `#admin` stays in the same document and the same trip, the hash is cleaned, and no admin UI shows.
    - `test_e04_hash_admin_loop_guard`: super-admin types `#admin`, and after the reload the admin check hangs. Result: exactly 1 reload, the page settles in the trip with no admin overlay, and a second `#admin` within 30 s causes no reload.
- **F03 suite 1.0.3 → 1.0.4**
  - `open_admin()` with SWITCH on now reopens the app at `?choose=1` and taps `#ptChooseAdmin`. The F20-QA-02 path through the avatar sheet is gone. The flag is read from the served source, because a super-admin with one trip has no avatar.
  - `test_ac02_admin_entry_for_admin` (SWITCH on): no "ניהול מערכת" in "עוד" or on the trip home, then the chooser path and the header button "הטיולים שלי" → chooser.
  - `open_switch_admin` is replaced by `open_chooser_admin`.
- **F04 suite 1.4.0 → 1.4.1:** `VERSION` is now 3.0.0-alpha.5.1. `test_n01[admin]` reaches admin through the F03 helper.
- **MANUAL.md 1.1.0:** sections 3, 4 and 5 now have no admin inside a trip and the avatar only with ≥2 trips. New section 8 adds the phone checks for D7, including "reach admin by reopening the app".

### Results (`bash tests/f20/run.sh`, both SWITCH states)
| Suite | SWITCH_FEATURE='on' | SWITCH_FEATURE='off' |
|---|---|---|
| F20 browser suite 1.1.0 | **82/82** (77 − `s07[admin]` + 6 new) | (flag-off cases inside the suite) |
| F04 suite 1.4.1 | 126/126 | 126/126 |
| F03 regression 1.0.4, WIZARD on / off | 47 passed, 1 skipped, 11 deselected / 55 passed, 1 skipped, 3 deselected | same |
| F02 regression, WIZARD on / off | 36 passed, 1 skipped, 3 deselected each | same |
| Deno: F04 function tests · create-trip · invite-manager | 31/31 · 9/9 · 21/21 | — |
| DB / Edge Functions | no `supabase/` or `*.sql` change vs `main` → no migration | — |

Overall rc=0. The deselected lists are unchanged; they are the same expected set as alpha.5.

### Failures before the update (all expected by D7 or by the version bump; dev notes §7 lists the same set)
- **F20: 6 failed.**
  - `test_st_static[app_version|pt_version]`: version pin.
  - `test_a03…`, `test_s03…` and `test_s07…[admin]`: they used the removed sheet "ניהול" row.
  - `test_s02…[one]`: it expected the old avatar rule.
- **F04: 3 failed with SWITCH on, 2 with SWITCH off.**
  - `test_c21_static[app_version|pt_version]`: version pin.
  - `test_n01[admin]` (SWITCH on only): the old `open_admin` path.
- **F03 with SWITCH on: 15 failed in each WIZARD state.** The F20-QA-02 `open_admin` relied on the sheet row.
- After the update, all of these pass.

### Defects
None in the product.

### Observation (not a defect; same as alpha.4.2)
When the admin status is **unknown** because the `platform_admins` check hangs or fails, a page that ends up in a trip keeps `#admin` in the address bar. Two cases show this:
- after the F20-D7-05 reload (`test_e04`)
- with SWITCH off, on a fresh `#admin` load with a hanging check

It does not affect behaviour: no admin is shown and there is no reload loop. A real non-admin always has the hash cleaned (`test_b05`, `test_e03`). Question for the architect: should an unknown admin status also clean the hash?
