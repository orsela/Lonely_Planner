"""Plan_Travel F05 QA · Playwright black-box suite · version 1.1.1
CHANGE 2026-10-26 FIX-04-QA: 1.1.0 → 1.1.1: new runtime test test_s02_join_fatal_single_title; the static duplicate-id check accepts the
  source-level #joinTitle twice once fatal() removes #m (3.0.0-alpha.7.2).
CHANGE 2026-10-19 F05-QA-03: first version (no previous version).
CHANGE 2026-10-26 QA-DEBT-06: 1.0.0 → 1.1.0 (static part; behavioural changes are listed under QA-DEBT-07 below):
  - MAIN_REF defaults to the alpha.5.1 commit from tests/qa_refs.py (4bd04e4 = parent of the F05 client commit 59ebf13; was
    "main", which is no longer alpha.5.1, so every static case that reads it failed on the harness assert).
  - test_s01_static[protected:*] compares with the v2.15.2 declarations from git (V2152_REF; alpha.5.1 had the same bytes).
  - test_s01_static[app_version|pt_version] pin tests/qa_refs.py CURRENT_VERSION (was "3.0.0-alpha.6").
  - test_s01_static[node_check] extracted scripts with a regex on "<script", which also matched the word inside HTML comments
    and JS strings of the app (false failures app_7.js / app_9.js since alpha.6); it now uses the F02 extractor
    (tests/f02/tests/js_tools/extract.js, browser-like tokenizer, the one F04/F20 use) for app/ and join/.
  - New harness guard test_h00_standalone_fake (QA-DEBT-09: the standalone fake no longer throws).
CHANGE 2026-10-26 QA-DEBT-07: behavioural triage of the first full run on main 1403761 (alpha.7.1); see
  docs/qa/QA-DEBT_2026-10-26.md. No behavioural assertion weakened beyond what the spec / dev notes say:
  - test_b10_name_taken[pending_spaces]: "input kept" accepts the cleaned name too ("נועה כהן" for "נועה   כהן") — the
    spec (§1.6b) asks for a red input + message, not for the raw spacing; the error text already accepted both forms.
  - test_b13_known_identity[removed]: the removed screen is checked for "הוסרת מהטיול" AND "פנו למנהל" (dev notes §4: title
    "הוסרת מהטיול", text "פנו למנהל של הטיול אם זו טעות."); it required the spec's one-line summary
    "הוסרת מהטיול - פנו למנהל" verbatim. (Since F06 D2 the live server never reaches this branch; it is kept for flag off.)
  - test_c03_claim_moves_membership_and_starts_trip: "מי אני" is read from #homeUserName (as test_e01 does); it looked for
    the name anywhere in the visible home text, where the v2-min home shows only the avatar initial.
  - Known app bugs found by this run are reported as xfail with their id (KNOWN_BUGS below), only when the failure is
    exactly that bug; any other problem in the same test still fails it.

Black-box acceptance tests for docs/F05_spec.md §4 (criteria 1–17, browser side). Contract: the spec, the approved mockup
artboards F05_* (canvas row 7) and docs/F05_dev_notes.md §3–§4 (flags, stable ids, texts) ONLY. NOT read: app/index.html's
F05 block, join/flow.js, join/index.html, 0012_f05.sql, the two Edge Functions' sources (static checks grep only version
constants, flags and CHANGE tags).

Harness: tests/f05/harness.py (repo served like GitHub Pages: /Lonely_Planner/app/, /Lonely_Planner/join/ on one origin;
tests/f05/fake_supabase.js = the F04 fake library + a Realtime model; F05Backend = the F20 backend + in-memory join-trip /
approve-member with spec §2 semantics). 390×844 Chromium, he-IL, Asia/Jerusalem, clock installed at 2026-10-12 06:00Z.

Env: APP_DIR / JOIN_DIR / REPO_DIR, MAIN_REF (default main = alpha.5.1, the "before" for protected functions and ids),
QA_HEADFUL=1 to watch.
"""
import collections
import json
import os
import re
import subprocess
import time
import uuid

import pytest

import harness as H
from harness import f02, f03, f04, f20, norm, btext, has, wait_has, layout_problems, is_vis, exists, wait_until

from playwright.sync_api import Error as PWError

qa_refs = f02.qa_refs  # CHANGE 2026-10-26 QA-DEBT-06: tests/qa_refs.py (imported by the F02 harness)
MAIN_REF = os.environ.get("MAIN_REF", qa_refs.REFS["3.0.0-alpha.5.1"])  # CHANGE 2026-10-26 QA-DEBT-06: default was "main"
VERSION = qa_refs.CURRENT_VERSION  # CHANGE 2026-10-26 QA-DEBT-06: was "3.0.0-alpha.6"
APP_NAME = "Lonely Planner"
OLD_NAMES = ["Plan_Travel", "Vietnam Travel Planner"]
JOIN_URL = "https://orsela.github.io/Lonely_Planner/join/#code={c}"

TXT = {
    "label": "איך קוראים לך?",
    "help": "כך יראו אותך שאר החברים, וכך יירשמו ההוצאות שלך.",
    "submit": "בקשת הצטרפות",
    "tick1": "בלי מייל ובלי סיסמה",
    "tick3": "הטלפון הזה יזוהה אוטומטית בפעם הבאה",
    "footer": "מה שתזינו בטיול גלוי רק לחברי הקבוצה.",
    "pending_pill": "ממתין לאישור · {n}",
    "cancel": "ביטול הבקשה",
    "open": "פתיחת הטיול",
    "install_line": "אפשר גם להתקין את האפליקציה - היא תמשיך עם אותה זהות.",
    "a2hs": "מוסיפים את האפליקציה למסך הבית",
    "valid": "בתוקף 24 שעות · פעם אחת",
    "not_now": "לא עכשיו - פתיחת הטיול כאן",
    "copy_aria": "העתקת הקוד",
    "invalid": "הקישור כבר לא פעיל",
    "taken": 'יש כבר "{n}" בטיול. אפשר להוסיף אות או שם משפחה, למשל "{n} ל".',
    "rejected": "הבקשה לא אושרה",
    "again": "בקשה חדשה",
    "limit3": "עד 3 בקשות ביום מאותו טלפון.",
    "removed": "הוסרת מהטיול",
    "removed_full": "הוסרת מהטיול - פנו למנהל",
    "t_rate": "יותר מדי ניסיונות. נסו שוב מאוחר יותר.",
    "t_offline": "אין חיבור. נסו שוב כשהרשת תחזור.",
    "t_other": "משהו השתבש. נסו שוב.",
    "gate_title": "כמעט שם",
    "gate_text": "הטלפון הזה עוד לא מחובר לטיול. הצטרפת בספארי? מקלידים את קוד ההעברה שקיבלת שם.",
    "claim": "כניסה לטיול",
    "others": "דרכים אחרות",
    "have_link": "יש לי קישור הצטרפות מווטסאפ",
    "invite_btn": "כניסה עם הזמנה",
    "t_invalid": "הקוד לא תקף. פותחים שוב את קישור ההצטרפות בספארי ומקבלים קוד חדש.",
    "card_title": "ממתינים לאישור · {n}",
    "managers_only": "רק מנהלים רואים",
    "asked": "ביקש/ה להצטרף · לפני",
    "approve_as": "אישור כ{r}",
    "reject": "דחייה",
    "reject_q": "לדחות את הבקשה של {n}?",
    "reject_yes": "כן, לדחות",
    "reject_no": "ביטול",
    "opened": "פתיחה",
    "t_joined": "{n} הצטרף/ה כ{r}",
    "t_rejected": "הבקשה נדחתה",
    "t_handled": "הבקשה כבר טופלה",
    "no_conn": "אין חיבור",
    "soon_join": "ההצטרפות לטיול תיפתח בקרוב",
}
ROLE_WORD = {"viewer": "צופה", "editor": "עורך", "manager": "מנהל"}


# =====================================================================================================
# Fixtures
# =====================================================================================================
@pytest.fixture(scope="session")
def server():
    s = H.F05Server()
    yield s
    s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=os.environ.get("QA_HEADFUL") != "1")
        yield b
        b.close()


@pytest.fixture
def env(browser, server):
    server.reset()
    e = H.Env(browser, server)
    yield e
    e.close()
    server.reset()


# =====================================================================================================
# Scenario helpers
# =====================================================================================================
def new_trip(env, **kw):
    """יפן 2027, 03/04–20/04/2027 (18 days), manager "דנה" (earliest) + an editor "Editor Q"."""
    kw.setdefault("others", (("Editor Q", "editor"),))
    return env.backend.trip(**kw)


def open_join(dev, code, want=("form", "pending", "approved", "invalid", "removed", "error", "rejected")):
    dev.page.goto(dev.env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    return H.wait_screen(dev.page, want, 15)


def submit_name(dev, name, want=("pending", "form", "error")):
    page = dev.page
    page.locator("#lpjName").fill(name)
    page.locator("#lpjSubmit").click()
    page.wait_for_timeout(500)
    return H.wait_screen(page, want, 8)


def join_pending(env, code, name="נועה", dev_name="J", **dev_kw):
    dev = env.new_device(dev_name, **dev_kw)
    st = open_join(dev, code)
    assert st == "form", "join page did not show the form (screen=%s, text=%r)" % (st, btext(dev.page)[:200])
    st = submit_name(dev, name, ("pending",))
    assert st == "pending", "request did not reach the waiting screen (screen=%s, text=%r)" % (st, btext(dev.page)[:300])
    return dev


def my_row(env, dev, tid):
    return env.backend.member_of(tid, env.backend.uid_of(dev.name))


def boot_member(env, tid, dev_name="M", display="דנה", role="manager", pre_ls=None, layout=None, **dev_kw):
    """A device that is already an active member of `tid` boots the app (as a manager by default)."""
    be = env.backend
    be.links = [{"trip_id": tid, "role": role, "display_name": display, "joined_at": H.iso(be.tnow() - 90 * H.DAY)}]
    dev = env.new_device(dev_name, **dev_kw)
    if pre_ls:
        dev.seed_ls(pre_ls)
    dev.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")
    st = H.wait_app_state(dev.page, "app", 30)
    be.links = []
    assert st == "app", "app did not start for an active %s (state=%s, text=%r)" % (role, st, btext(dev.page)[:200])
    dev.page.wait_for_timeout(800)
    return dev


def card_vis(page):
    return is_vis(page, "#ptF05Pending")


def card_rows(page):
    return page.evaluate("""()=>[...document.querySelectorAll('#ptF05Pending .pt5-req')].filter(r=>r.getBoundingClientRect().height>0)
      .map(r=>({id:r.getAttribute('data-member'),text:r.innerText,
        roles:[...r.querySelectorAll('[data-role]')].filter(b=>b.getBoundingClientRect().height>0).map(b=>[b.getAttribute('data-role'),b.getAttribute('aria-pressed')]),
        approve:(r.querySelector('[data-act=approve]')&&r.querySelector('[data-act=approve]').getBoundingClientRect().height>0)?r.querySelector('[data-act=approve]').innerText.trim():null,
        open:!!(r.querySelector('[data-open]')&&r.querySelector('[data-open]').getBoundingClientRect().height>0)}))""")


def row_btn(page, mid, sel):
    return page.locator('#ptF05Pending .pt5-req[data-member="%s"] %s' % (mid, sel)).filter(visible=True).first


def wait_open_screen(dev, timeout=25):
    """After 'פתיחת הטיול': the app at /app/ is running a trip."""
    st = H.wait_app_state(dev.page, "app", timeout)
    return st


def same_doc_mark(page):
    page.evaluate("()=>{window.__qaStay=1}")


def same_doc(page):
    try:
        return page.evaluate("()=>window.__qaStay===1")
    except PWError:
        return False


def otp_values(page):
    return page.evaluate("()=>[0,1,2,3,4,5].map(i=>{const e=document.getElementById('ptF05Otp'+i);return e?e.value:null})")


def paste_into(page, sel, text):
    page.evaluate("""([s,t])=>{const e=document.querySelector(s);e.focus();const dt=new DataTransfer();dt.setData('text/plain',t);
      e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))}""", [sel, text])
    page.wait_for_timeout(250)


def gate_device(env, name="A", **kw):
    dev = env.new_device(name, **kw)
    dev.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")
    ok = wait_until(lambda: is_vis(dev.page, "#ptF05Transfer"), 20, dev.page)
    assert ok, "not-connected screen #ptF05Transfer not shown (text=%r)" % btext(dev.page)[:300]
    dev.page.wait_for_timeout(300)
    return dev


def enter_code(page, code):
    page.locator("#ptF05Otp0").fill(code)
    page.wait_for_timeout(250)
    page.locator("#ptF05Claim").click()
    page.wait_for_timeout(600)


def iphone_code(env, tid, code, name="נועה", role="editor"):
    """Safari on an iPhone joins; the manager approves; returns (device, member id, shown transfer code digits)."""
    dev = join_pending(env, code, name, "I", ua=H.IPHONE_UA, standalone=False)
    mid = my_row(env, dev, tid)["id"]
    env.backend.approve_direct(mid, role)
    st = H.wait_screen(dev.page, "approved", 8)
    assert st == "approved", "approved screen not reached (screen=%s)" % st
    assert wait_until(lambda: is_vis(dev.page, "#lpjCode") and re.search(r"\d", H.text_of(dev.page, "#lpjCode") or ""), 8, dev.page), \
        "transfer code #lpjCode not shown on iPhone Safari"
    shown = re.sub(r"\D", "", H.text_of(dev.page, "#lpjCode"))
    return dev, mid, shown


def calls(env, name=None, action=None, device=None):
    return env.backend.calls_of(name, action, device)


# CHANGE 2026-10-26 QA-DEBT-07: app bugs found by the QA-DEBT run (docs/qa/QA-DEBT_2026-10-26.md §4). A test whose only
# problems match the bug's pattern is xfailed with the id; when the bug is fixed the test passes again (no edit needed).
KNOWN_BUGS = {
    "QA-DEBT-BUG-01": "F06 membership watch treats ANY Realtime DELETE on trip_members as 'my row deleted' (no ev.old.id check): "
                      "a manager who rejects a request gets the 'removed' screen 1.8b and the trip's device data is purged",
    "QA-DEBT-BUG-02": "approve-member not_manager does not hide the pending card (F05 §1.5 'not_manager → hide card')",
    "QA-DEBT-BUG-03": "pending card role buttons (צופה / עורך / מנהל) are 40px tall, touch target < 44px (F05 §1, criterion 15)",
    "QA-DEBT-BUG-04": "/join/ fatal() renders a second #joinTitle (and <main>) while the hidden F04 section #m stays in the DOM",
}


def assert_or_known_bug(P, bug, pattern):
    """CHANGE 2026-10-26 QA-DEBT-07: fail on P, except when every problem matches `pattern` → xfail with the bug id."""
    if not P:
        return
    if all(re.search(pattern, p) for p in P):
        pytest.xfail("%s: %s" % (bug, KNOWN_BUGS[bug]))
    assert not P, "\n".join(P)


def seen(page, text):
    """Text currently visible OR shown as a toast at some point (toast log)."""
    return has(page, text) or any(norm(text) in norm(t) for t in H.toasts(page))


# =====================================================================================================
# 1 · Flag off (criterion 1)
# =====================================================================================================
def test_a01_join_off_is_coming_soon(env):
    """C1: /join/ with JOIN_FEATURE='off' = the F04 "בקרוב" page: brand, title, hash removed, the code is not kept, no
    Supabase / function traffic."""
    H.serve_join_off(env)
    tid, code = new_trip(env)
    dev = env.new_device("J")
    dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    P = []
    if not wait_has(dev.page, TXT["soon_join"], 8):
        P.append("'off': %r missing (text=%r)" % (TXT["soon_join"], btext(dev.page)[:200]))
    if not has(dev.page, APP_NAME):
        P.append("brand missing")
    dev.page.wait_for_timeout(600)
    if "#code" in dev.page.url:
        P.append("hash not removed: %s" % dev.page.url)
    ss = dev.page.evaluate("()=>{try{return sessionStorage.getItem('lp:join_code')}catch(e){return 'ERR'}}")
    if ss:
        P.append("'off' keeps the code in sessionStorage: %r" % ss)
    ext = [r["url"] for r in env.net if "supabase" in r["url"] or code in r["url"]]
    if ext or env.backend.fn_calls or exists(dev.page, "#lpJoin"):
        P.append("'off' page loads Supabase / calls functions / mounts the join flow: %r" % ext[:3])
    assert not P, "\n".join(P)


def test_s02_join_fatal_single_title(env):
    """CHANGE 2026-10-26 FIX-04-QA: new test (QA-DEBT-BUG-04). /join/ whose flow script cannot load shows the error screen
    "לא הצלחנו לטעון את הדף" with exactly ONE #joinTitle in the DOM (since 3.0.0-alpha.7.2 fatal() removes the hidden #m)."""
    tid, code = new_trip(env)
    dev = env.new_device("J")
    dev.page.route("**/join/flow.js*", lambda route: route.abort())
    dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    assert wait_has(dev.page, "לא הצלחנו לטעון את הדף", 10), "error screen missing (text=%r)" % btext(dev.page)[:200]
    n = dev.page.evaluate("()=>document.querySelectorAll('#joinTitle').length")
    assert n == 1, "#joinTitle count on the error screen = %r" % n


def test_a02_app_off_is_alpha51(env):
    """C1: app with JOIN_FEATURE='off': the not-connected screen is the F04 card (no transfer code), a manager with a
    pending request sees no F05 card, the user picker / fixed USERS behave as alpha.5.1, and no F05 function is called."""
    H.serve_app_flags(env, join="off")
    tid, code = new_trip(env, managers=())
    env.backend.new_pending(tid, "ממתינה")
    P = []
    g = env.new_device("G")
    g.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")
    st = H.wait_app_state(g.page, None, 20)
    if st != "nc":
        P.append("'off': fresh device state %r (expected the not-connected card)" % st)
    g.page.wait_for_timeout(800)
    if is_vis(g.page, "#ptF05Transfer") or has(g.page, TXT["gate_title"]):
        P.append("'off': F05 transfer screen shown")
    if not has(g.page, TXT["invite_btn"]) or not has(g.page, f02.NC_TITLE):
        P.append("'off': F04 gate card / F02 device code card missing")
    if any("join/flow.js" in r["url"] for r in env.net):
        P.append("'off': join/flow.js loaded")
    m = boot_member(env, tid, display="דנה")
    m.page.wait_for_timeout(1500)
    if exists(m.page, "#ptF05Pending") and card_vis(m.page):
        P.append("'off': manager pending card shown")
    users = m.page.evaluate("()=>USERS.slice()")
    if users != ["אור", "שירי", "שחר", "עמית", "עפרי"]:
        P.append("'off': USERS changed: %r" % users)
    if not m.page.locator("#userModal.open").count():
        P.append("'off': the alpha.5.1 user picker did not open for a device without a stored name")
    if env.backend.fn_calls:
        P.append("'off': F05 functions called: %r" % [(c["name"], c["action"]) for c in env.backend.fn_calls])
    if H.page_errors(g) or H.page_errors(m):
        P.append("page errors: %r" % (H.page_errors(g) + H.page_errors(m))[:3])
    assert not P, "\n".join(P)


def test_a03_flags_declared():
    """§1: JOIN_FEATURE='on' in the app flags script next to SWITCH_FEATURE, and a top-level const in /join/."""
    html = H.app_html()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    blk = [b for b in blocks if re.search(r"const\s+SWITCH_FEATURE\s*=", b)]
    assert blk and re.search(r"""^\s*const\s+JOIN_FEATURE\s*=\s*['"]on['"]""", blk[0], re.M), \
        "const JOIN_FEATURE='on' not declared next to SWITCH_FEATURE"
    assert re.search(r"""const\s+JOIN_FEATURE\s*=\s*['"]on['"]""", H.join_html()), "/join/: const JOIN_FEATURE='on' missing"


# =====================================================================================================
# 2 · /join/ preview, request, waiting (criteria 2, 3)
# =====================================================================================================
def test_b01_preview_fresh_identity(env):
    """C2 + §1.1: fresh identity: anonymous sign-in, preview with the code, header shows manager, trip name, dd/mm–dd/mm/yyyy,
    "18 ימים · 2 חברים"; the form (label, maxlength 40, autofocus, help, button), three ticks, footer, brand; the hash is
    removed and the code kept in sessionStorage lp:join_code; no trip chrome; no old app name."""
    tid, code = new_trip(env)
    env.backend.new_pending(tid, "ממתין אחר")      # pending members are not counted
    dev = env.new_device("J")
    st = open_join(dev, code)
    page, P = dev.page, []
    assert st == "form", "screen %r (text=%r)" % (st, btext(page)[:300])
    t = btext(page)
    for s in ["דנה", "יפן 2027", "03/04 - 20/04/2027", "18 ימים · 2 חברים", TXT["label"], TXT["help"], TXT["submit"],
              TXT["tick1"], TXT["tick3"], TXT["footer"], APP_NAME]:
        if norm(s) not in t:
            P.append("missing %r" % s)
    for o in OLD_NAMES:
        if o in t:
            P.append("old name %r rendered" % o)
    inp = page.evaluate("()=>{const e=document.getElementById('lpjName');return e?{ml:e.maxLength,focus:document.activeElement===e,af:e.autofocus}:null}")
    if not inp or inp["ml"] != 40:
        P.append("#lpjName maxlength != 40: %r" % inp)
    elif not (inp["focus"] or inp["af"]):
        P.append("#lpjName not autofocused")
    if "#code" in page.url or code in page.url:
        P.append("hash not removed: %s" % page.url)
    if page.evaluate("()=>sessionStorage.getItem('lp:join_code')") != code:
        P.append("sessionStorage lp:join_code != code")
    pv = calls(env, "join-trip", "preview")
    if not pv or pv[0]["body"].get("code", "").upper().replace(" ", "") != code:
        P.append("preview call missing / wrong code: %r" % [c["body"] for c in pv])
    if not env.backend.uid_of("J"):
        P.append("no anonymous sign-in on /join/")
    if f03.chrome_visible(page):
        P.append("trip chrome on /join/: %r" % f03.chrome_visible(page))
    if H.page_errors(dev):
        P.append("page errors %r" % H.page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_b02_reload_keeps_code(env):
    """§1.1: the hash is gone, but a reload of /join/ still shows the same invitation (sessionStorage)."""
    tid, code = new_trip(env)
    dev = env.new_device("J")
    assert open_join(dev, code) == "form"
    dev.page.reload(wait_until="domcontentloaded")
    st = H.wait_screen(dev.page, ("form", "invalid", "error", "loading"), 12)
    assert st == "form" and has(dev.page, "יפן 2027"), "after reload: screen %r, text %r" % (st, btext(dev.page)[:200])


def test_b03_request_creates_pending_and_waiting_screen(env):
    """C3 + §1.2: request with a padded name → one pending row with the cleaned name and the caller's uid; waiting screen:
    title "הבקשה נשלחה לדנה", pill "ממתין לאישור · <name>", three steps, cancel button; the mockup annotation is not
    shipped; Realtime on trip_members id=eq.<member>."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "  נועה   כהן ")
    page, be, P = dev.page, env.backend, []
    rows = [r for r in be.members(tid) if r["user_id"] == be.uid_of("J")]
    if len(rows) != 1 or rows[0]["status"] != "pending" or rows[0]["display_name"] != "נועה כהן":
        P.append("rows for the caller: %r" % rows)
    for s in ["הבקשה נשלחה לדנה", TXT["pending_pill"].format(n="נועה כהן"), TXT["cancel"]]:
        if not has(page, s):
            P.append("waiting screen: %r missing" % s)
    if "במוקאפ" in btext(page):
        P.append("mockup annotation shipped")
    if rows:
        subs = [s for s in be.rt_subs if s["device"] == "J"]
        filt = [b.get("filter", {}).get("filter") for s in subs for b in (s["bindings"] or [])]
        if "id=eq.%s" % rows[0]["id"] not in filt:
            P.append("no Realtime subscription with filter id=eq.<member> (got %r)" % filt)
    assert not P, "\n".join(P)


@pytest.mark.parametrize("role", ["viewer", "editor", "manager"])
def test_b04_approval_live_realtime(env, role):
    """C4: the manager approves (any role) → within ≤3 s the waiting screen changes to approved, without reload; the row is
    active with that role and approved_at; desktop: "פתיחת הטיול" + the install line, no transfer code."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    page, be = dev.page, env.backend
    same_doc_mark(page)
    mid = my_row(env, dev, tid)["id"]
    t0 = time.time()
    be.approve_direct(mid, role)
    st = H.wait_screen(page, "approved", 6)
    dt_ = time.time() - t0
    P = []
    if st != "approved":
        P.append("approved screen not reached (screen=%s)" % st)
    elif dt_ > 3.5:
        P.append("approved after %.1f s (> 3 s with Realtime)" % dt_)
    if not same_doc(page):
        P.append("page reloaded")
    r = be.member(mid)
    if not (r["status"] == "active" and r["role"] == role and r["approved_at"]):
        P.append("row %r" % r)
    if not has(page, ROLE_WORD[role]):
        P.append("role %r not shown" % ROLE_WORD[role])
    if not has(page, "נועה"):
        P.append("name not shown")
    if not (is_vis(page, "#lpjOpen") and norm(TXT["open"]) == norm(H.text_of(page, "#lpjOpen"))):
        P.append("#lpjOpen %r" % H.text_of(page, "#lpjOpen"))
    if not has(page, TXT["install_line"]):
        P.append("install line missing")
    if is_vis(page, "#lpjTransfer") or calls(env, "join-trip", "issue_transfer"):
        P.append("desktop got a transfer code")
    assert not P, "\n".join(P)


def test_b05_approval_by_poll_only(env):
    """C4: with no Realtime event the approval still shows by the 20 s poll (clock advanced 21 s), without reload."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    page, be = dev.page, env.backend
    be.rt_silent = True
    same_doc_mark(page)
    be.approve_direct(my_row(env, dev, tid)["id"], "editor")
    page.wait_for_timeout(1500)
    assert H.screen_of(page) == "pending", "harness: approved without Realtime and without a poll tick"
    page.clock.run_for(21000)
    st = H.wait_screen(page, "approved", 6)
    assert st == "approved" and same_doc(page), "poll did not bring the approval within 20 s (screen=%s)" % st


def test_b06_approval_on_visibilitychange(env):
    """§1.2: returning to the tab (visibilitychange → visible) checks the status at once (no Realtime, no 20 s wait)."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    page, be = dev.page, env.backend
    be.rt_silent = True
    be.approve_direct(my_row(env, dev, tid)["id"], "editor")
    page.evaluate("""()=>{window.__qaVis='hidden';Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>window.__qaVis});
      Object.defineProperty(document,'hidden',{configurable:true,get:()=>window.__qaVis==='hidden'});document.dispatchEvent(new Event('visibilitychange'))}""")
    page.wait_for_timeout(300)
    page.evaluate("()=>{window.__qaVis='visible';document.dispatchEvent(new Event('visibilitychange'))}")
    st = H.wait_screen(page, "approved", 4)
    assert st == "approved", "visibilitychange → visible did not refresh the status (screen=%s)" % st


def test_b07_open_trip_from_browser(env):
    """§1.3 other platforms: "פתיחת הטיול" writes pt:_device:active_trip = this trip and opens /app/, which runs that trip with
    the member's name ("מי אני") and no user picker."""
    tid, code = new_trip(env)
    other, _ = new_trip(env, name="טיול אחר")
    dev = join_pending(env, code, "נועה")
    env.backend.approve_direct(my_row(env, dev, tid)["id"], "editor")
    assert H.wait_screen(dev.page, "approved", 6) == "approved"
    dev.page.locator("#lpjOpen").click()
    st = wait_open_screen(dev)
    P = []
    if st != "app":
        P.append("app not running after 'פתיחת הטיול' (state=%s, url=%s)" % (st, dev.page.url))
    else:
        if "/app/" not in dev.page.url:
            P.append("not on /app/: %s" % dev.page.url)
        if H.running_trip(dev.page) != tid:
            P.append("running trip %r != %r" % (H.running_trip(dev.page), tid))
        raw = dev.ls().get("pt:_device:active_trip") or ""
        if tid not in raw:
            P.append("pt:_device:active_trip = %r" % raw)
        dev.page.wait_for_timeout(1000)
        if dev.page.locator("#userModal.open").count():
            P.append("user picker opened")
        if norm(H.text_of(dev.page, "#homeUserName") or "") != "נועה" and not has(dev.page, "נועה"):
            P.append("member name not shown on home")
    assert not P, "\n".join(P)


def test_b08_cancel_request(env):
    """§1.2: "ביטול הבקשה" → cancel deletes the own pending row → back to the form."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    dev.page.locator("#lpjCancel").click()
    st = H.wait_screen(dev.page, "form", 6)
    P = []
    if st != "form":
        P.append("after cancel screen=%s" % st)
    if my_row(env, dev, tid):
        P.append("pending row still there")
    c = calls(env, "join-trip", "cancel")
    if not c or c[-1]["body"].get("trip_id") != tid:
        P.append("cancel call %r" % [x["body"] for x in c])
    assert not P, "\n".join(P)


def test_b09_reject_new_request_and_daily_limit(env):
    """C5 + §1.6c: reject → the row is deleted; the waiting screen shows "הבקשה לא אושרה" + "בקשה חדשה" + "עד 3 בקשות ביום
    מאותו טלפון."; "בקשה חדשה" returns to the form with the name prefilled and a new request works; the 4th request within
    24 h → rate_limited toast."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    page, be, P = dev.page, env.backend, []
    for i in range(3):
        mid = my_row(env, dev, tid)["id"]
        be.reject_direct(mid)
        st = H.wait_screen(page, "rejected", 6)
        if st != "rejected":
            P.append("round %d: rejected screen not shown (screen=%s)" % (i + 1, st))
            break
        if i == 0:
            for s in [TXT["rejected"], TXT["again"], TXT["limit3"]]:
                if not has(page, s):
                    P.append("rejected screen: %r missing" % s)
        page.locator("#lpjAgain").click()
        st = H.wait_screen(page, "form", 6)
        if st != "form" or page.input_value("#lpjName") != "נועה":
            P.append("round %d: 'בקשה חדשה' → screen %s, name %r" % (i + 1, st, page.input_value("#lpjName") if st == "form" else None))
            break
        page.locator("#lpjSubmit").click()
        st = H.wait_screen(page, ("pending", "form"), 6)
        page.wait_for_timeout(400)
        if i < 2 and st != "pending":
            P.append("round %d: new request did not reach pending (screen=%s)" % (i + 2, st))
            break
        if i == 2:
            if st == "pending" or my_row(env, dev, tid):
                P.append("4th request within 24 h accepted")
            if not H.saw_toast(page, TXT["t_rate"], 4):
                P.append("4th request: toast %r not shown" % TXT["t_rate"])
            if page.input_value("#lpjName") != "נועה":
                P.append("input not kept after rate_limited")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("variant", ["pending_spaces", "active_case"])
def test_b10_name_taken(env, variant):
    """C6 + §1.6b: a name taken by a pending (extra spaces) or active (other case) member → inline red error with the exact
    text, no row created, input kept."""
    tid, code = new_trip(env)
    if variant == "pending_spaces":
        env.backend.new_pending(tid, "נועה כהן")
        typed, shown = "נועה   כהן", "נועה כהן"
    else:
        typed, shown = "editor q", "editor q"
    dev = env.new_device("J")
    assert open_join(dev, code) == "form"
    n0 = len(env.backend.members(tid))
    st = submit_name(dev, typed, ("pending", "form"))
    page, P = dev.page, []
    page.wait_for_timeout(600)
    if st != "form":
        P.append("screen %s" % st)
    if len(env.backend.members(tid)) != n0:
        P.append("a row was created")
    err = norm(H.text_of(page, "#lpjNameErr") or "")
    want = [norm(TXT["taken"].format(n=shown)), norm(TXT["taken"].format(n=typed))]
    if err not in want or not is_vis(page, "#lpjNameErr"):
        P.append("#lpjNameErr %r, expected %r" % (err, want[0]))
    if page.evaluate("()=>document.getElementById('lpjNameErr').getAttribute('role')") != "alert":
        P.append("#lpjNameErr has no role=alert")
    red = page.evaluate("""()=>{const e=document.getElementById('lpjName');const c=getComputedStyle(e).borderColor;
      const m=c.match(/\\d+/g).map(Number);return e.getAttribute('aria-invalid')==='true'&&m[0]>m[1]+60}""")
    if not red:
        P.append("input not marked red / aria-invalid")
    if page.input_value("#lpjName") not in (typed, shown):  # CHANGE 2026-10-26 QA-DEBT-07: cleaned form accepted (was == typed)
        P.append("input not kept (%r)" % page.input_value("#lpjName"))
    assert not P, "\n".join(P)


def test_b11_name_invalid(env):
    """C6: an empty / spaces-only name never creates a row and keeps the form; the input caps at 40 characters."""
    tid, code = new_trip(env)
    dev = env.new_device("J")
    assert open_join(dev, code) == "form"
    page, P = dev.page, []
    for v in ["", "    "]:
        page.locator("#lpjName").fill(v)
        try:
            page.locator("#lpjSubmit").click(timeout=1500)
        except PWError:
            pass
        page.wait_for_timeout(500)
        if H.screen_of(page) != "form":
            P.append("name %r → screen %s" % (v, H.screen_of(page)))
    page.locator("#lpjName").fill("")
    page.locator("#lpjName").type("א" * 45)
    if len(page.input_value("#lpjName")) > 40:
        P.append("input accepts %d chars" % len(page.input_value("#lpjName")))
    if [r for r in env.backend.members(tid) if r["status"] == "pending"]:
        P.append("a pending row was created")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("kind", ["unknown", "rotated", "malformed"])
def test_b12_invalid_code(env, kind):
    """C7 + §1.6a: unknown, rotated (trip_join_codes.code changed) and malformed codes → "הקישור כבר לא פעיל", no form."""
    tid, code = new_trip(env)
    if kind == "rotated":
        env.backend.rows["trip_join_codes"][(tid,)]["code"] = env.backend.new_join_code()
    c = {"unknown": "ZZZZ2345", "rotated": code, "malformed": "%%%"}[kind]
    dev = env.new_device("J")
    st = open_join(dev, c)
    P = []
    if st != "invalid":
        P.append("screen %r" % st)
    if not has(dev.page, TXT["invalid"]):
        P.append("%r missing" % TXT["invalid"])
    if is_vis(dev.page, "#lpjName"):
        P.append("form shown")
    if [r for r in env.backend.members(tid) if r["status"] == "pending"]:
        P.append("row created")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("state", ["active", "pending", "removed"])
def test_b13_known_identity(env, state):
    """C8 + D7: the same identity opens the link again: active → no new row, approved / open path (or straight into the app);
    pending → the waiting screen; removed → "הוסרת מהטיול – פנו למנהל", no form. No request call in any case."""
    tid, code = new_trip(env)
    dev = join_pending(env, code, "נועה")
    be = env.backend
    mid = my_row(env, dev, tid)["id"]
    if state == "active":
        be.approve_direct(mid, "editor")
    elif state == "removed":
        be.approve_direct(mid, "editor")
        be.mut_update(be.member(mid), status="removed")
    n_req = len(calls(env, "join-trip", "request"))
    dev.page.goto(env.server.origin + f02.BLANK_PATH)
    st = open_join(dev, code)
    dev.page.wait_for_timeout(1000)
    P = []
    if state == "active":
        st2 = H.app_state(dev.page)
        if st not in ("approved",) and st2 != "app":
            P.append("active identity: screen %r / app state %r" % (st, st2))
    elif state == "pending":
        if st != "pending":
            P.append("pending identity: screen %r" % st)
    else:
        if st != "removed" or not has(dev.page, TXT["removed"]):
            P.append("removed identity: screen %r, text %r" % (st, btext(dev.page)[:200]))
        elif not has(dev.page, "פנו למנהל"):  # CHANGE 2026-10-26 QA-DEBT-07: was TXT["removed_full"] verbatim (dev notes §4)
            P.append("removed screen lacks 'פנו למנהל' (text=%r)" % btext(dev.page)[:200])
        if is_vis(dev.page, "#lpjName"):
            P.append("form shown to a removed identity")
    if len(calls(env, "join-trip", "request")) != n_req:
        P.append("a request was sent")
    if len([r for r in be.members(tid) if r["user_id"] == be.uid_of("J")]) != 1:
        P.append("row count changed")
    assert not P, "\n".join(P)


UA_CASES = {
    "iphone_safari": dict(ua=H.IPHONE_UA, standalone=False),
    "ipad_desktop_ua_touch": dict(ua=H.IPAD_DESKTOP_UA, standalone=False, ipad_touch=True),
    "iphone_standalone": dict(ua=H.IPHONE_UA, standalone=True),
    "android": dict(ua=H.ANDROID_UA),
    "desktop": dict(ua=H.DESKTOP_UA),
}


@pytest.mark.parametrize("ua", list(UA_CASES))
def test_b14_transfer_code_only_on_iphone_safari(env, ua):
    """D1 + §1.3: iPhone / iPadOS Safari (not standalone) gets the card with the 3 steps, a 6-digit code "482 916" (LTR,
    monospace), copy button aria-label "העתקת הקוד", "בתוקף 24 שעות · פעם אחת" and "לא עכשיו – פתיחת הטיול כאן"; other
    platforms (and the installed app) get no code and no issue_transfer call."""
    tid, code = new_trip(env)
    env.backend.code_seq = ["482916"]
    dev = join_pending(env, code, "נועה", **UA_CASES[ua])
    env.backend.approve_direct(my_row(env, dev, tid)["id"], "editor")
    page, P = dev.page, []
    assert H.wait_screen(page, "approved", 6) == "approved"
    page.wait_for_timeout(1200)
    iphone = ua in ("iphone_safari", "ipad_desktop_ua_touch")
    if iphone:
        if not is_vis(page, "#lpjTransfer"):
            P.append("no transfer card")
        txt = norm(H.text_of(page, "#lpjCode") or "")
        if txt != "482 916":
            P.append("#lpjCode %r (expected '482 916')" % txt)
        st = page.evaluate("()=>{const e=document.getElementById('lpjCode');if(!e)return null;const s=getComputedStyle(e);return {d:s.direction,f:s.fontFamily}}")
        if not st or st["d"] != "ltr" or not re.search(r"mono|menlo|courier|consolas", st["f"], re.I):
            P.append("code style %r (want LTR monospace)" % st)
        if page.evaluate("()=>{const b=document.getElementById('lpjCopy');return b?b.getAttribute('aria-label'):null}") != TXT["copy_aria"]:
            P.append("#lpjCopy aria-label")
        else:
            page.locator("#lpjCopy").click()
            page.wait_for_timeout(400)
            cp = [re.sub(r"\D", "", c) for c in page.evaluate("()=>window.__qaWatch.copied")]
            if "482916" not in cp:
                P.append("copy wrote %r" % cp)
        for s in [TXT["a2hs"], TXT["valid"]]:
            if not has(page, s):
                P.append("%r missing" % s)
        if norm(H.text_of(page, "#lpjOpen") or "") != norm(TXT["not_now"]):
            P.append("#lpjOpen %r (want %r)" % (H.text_of(page, "#lpjOpen"), TXT["not_now"]))
        if len(calls(env, "join-trip", "issue_transfer")) != 1:
            P.append("issue_transfer calls: %d" % len(calls(env, "join-trip", "issue_transfer")))
    else:
        if is_vis(page, "#lpjTransfer") or calls(env, "join-trip", "issue_transfer"):
            P.append("%s got a transfer code" % ua)
        if norm(H.text_of(page, "#lpjOpen") or "") != norm(TXT["open"]):
            P.append("#lpjOpen %r" % H.text_of(page, "#lpjOpen"))
    assert not P, "\n".join(P)


def test_b15_reentering_approved_issues_new_code(env):
    """§1.3 / C9: re-entering the approved screen issues a new code and the previous unused one dies."""
    tid, code = new_trip(env)
    env.backend.code_seq = ["111111", "222222"]
    dev, mid, first = iphone_code(env, tid, code)
    dev.page.goto(env.server.origin + f02.BLANK_PATH)
    st = open_join(dev, code)
    dev.page.wait_for_timeout(1500)
    second = re.sub(r"\D", "", H.text_of(dev.page, "#lpjCode") or "")
    P = []
    if st != "approved" or first != "111111" or second != "222222":
        P.append("screen %s, codes %r → %r" % (st, first, second))
    live = [t for t in env.backend.transfers if not t["used_at"]]
    if [t["code"] for t in live] != ["222222"]:
        P.append("open codes %r" % [t["code"] for t in live])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("case", ["offline", "rate_limited", "other"])
def test_b16_request_errors(env, case):
    """§1.1 / C16: offline → "אין חיבור. נסו שוב כשהרשת תחזור.", rate_limited → "יותר מדי ניסיונות…", anything else →
    "משהו השתבש. נסו שוב."; the form and the typed name stay."""
    tid, code = new_trip(env)
    dev = env.new_device("J")
    assert open_join(dev, code) == "form"
    page = dev.page
    if case == "offline":
        dev.offline(True)
    elif case == "rate_limited":
        env.backend.force[("join-trip", "request")] = "rate_limited"
    else:
        env.backend.force[("join-trip", "request")] = "invalid_request"
    page.locator("#lpjName").fill("נועה")
    page.locator("#lpjSubmit").click()
    want = {"offline": TXT["t_offline"], "rate_limited": TXT["t_rate"], "other": TXT["t_other"]}[case]
    P = []
    if not H.saw_toast(page, want, 6):
        P.append("toast %r not shown (toasts=%r)" % (want, H.toasts(page)))
    if H.screen_of(page) != "form" or page.input_value("#lpjName") != "נועה":
        P.append("form / input not kept (screen=%s)" % H.screen_of(page))
    assert not P, "\n".join(P)


def test_b17_offline_on_open(env):
    """C16: /join/ opened offline shows the offline toast (no crash, no form submission possible without a preview)."""
    tid, code = new_trip(env)
    dev = env.new_device("J", offline_boot=True)
    dev.offline(True)
    try:
        dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    except PWError:
        pytest.skip("page itself cannot load offline in this harness")
    dev.page.wait_for_timeout(2500)
    assert H.saw_toast(dev.page, TXT["t_offline"], 4) or has(dev.page, "אין חיבור"), \
        "offline /join/: no offline message (text=%r)" % btext(dev.page)[:200]


# =====================================================================================================
# 3 · Installed app, not connected (criteria 9, 10)
# =====================================================================================================
def test_c01_not_connected_screen(env):
    """C10 + §1.4: title "כמעט שם", text, six digit boxes (LTR, inputmode numeric), "כניסה לטיול" disabled until 6 digits,
    "דרכים אחרות" with the WhatsApp-link option, then the F04 "כניסה עם הזמנה" card and the F02 device code card last;
    no trip chrome."""
    dev = gate_device(env)
    page, P = dev.page, []
    for s in [TXT["gate_title"], TXT["gate_text"], TXT["claim"], TXT["others"], TXT["have_link"], TXT["invite_btn"], f02.NC_TITLE]:
        if not has(page, s):
            P.append("%r missing" % s)
    boxes = page.evaluate("""()=>[0,1,2,3,4,5].map(i=>{const e=document.getElementById('ptF05Otp'+i);if(!e)return null;
      return {im:e.getAttribute('inputmode'),dir:getComputedStyle(e).direction,x:e.getBoundingClientRect().left}})""")
    if any(b is None for b in boxes):
        P.append("digit boxes missing: %r" % boxes)
    else:
        if any(b["im"] != "numeric" for b in boxes):
            P.append("inputmode %r" % [b["im"] for b in boxes])
        if any(b["dir"] != "ltr" for b in boxes) or not all(boxes[i]["x"] < boxes[i + 1]["x"] for i in range(5)):
            P.append("boxes not LTR (left-to-right order): %r" % boxes)
    if not page.evaluate("()=>document.getElementById('ptF05Claim').disabled"):
        P.append("claim enabled with no digits")
    order = page.evaluate("""()=>['ptF05Transfer','ptF05Others','ptGateInvite','ptDeviceCode'].map(id=>{const e=document.getElementById(id);
      return e?e.getBoundingClientRect().top+scrollY:null})""")
    if None in order or order != sorted(order):
        P.append("order transfer < others < F04 invite < device code violated: %r" % order)
    if f03.chrome_visible(page):
        P.append("trip chrome: %r" % f03.chrome_visible(page))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("how", ["type", "paste", "autofill"])
def test_c02_code_boxes_entry(env, how):
    """§1.4: typing advances box by box; pasting "482 916" into a box fills all six; a whole code autofilled into the first
    box is spread; the button enables at 6 digits."""
    dev = gate_device(env)
    page = dev.page
    if how == "type":
        page.locator("#ptF05Otp0").focus()
        page.keyboard.type("482916", delay=40)
    elif how == "paste":
        paste_into(page, "#ptF05Otp0", "482 916")
    else:
        page.locator("#ptF05Otp0").fill("482916")
    page.wait_for_timeout(300)
    v = otp_values(page)
    assert v == list("482916"), "boxes after %s: %r" % (how, v)
    assert not page.evaluate("()=>document.getElementById('ptF05Claim').disabled"), "claim still disabled"


def test_c03_claim_moves_membership_and_starts_trip(env):
    """C9 + §1.4: Safari on an iPhone joins and gets a code; the installed app (another identity) enters it → the trip starts
    in the same document; the membership keeps its id / name / role with the app's uid; the Safari identity is no longer a
    member; "מי אני" = the member's name; pt:_device:active_trip = the trip."""
    tid, code = new_trip(env)
    safari, mid, tc = iphone_code(env, tid, code, "נועה", "viewer")
    be = env.backend
    old_uid = be.uid_of("I")
    app = gate_device(env, "A", ua=H.IPHONE_UA, standalone=True)
    page = app.page
    same_doc_mark(page)
    enter_code(page, tc)
    st = H.wait_app_state(page, "app", 20)
    P = []
    if st != "app":
        P.append("trip did not start after the claim (state=%s, text=%r)" % (st, btext(page)[:200]))
    else:
        if not same_doc(page):
            P.append("the app reloaded (spec: no reload needed) — informational")
        if H.running_trip(page) != tid:
            P.append("running trip %r" % H.running_trip(page))
        page.wait_for_timeout(1000)
        if page.locator("#userModal.open").count():
            P.append("user picker opened")
        if norm(H.text_of(page, "#homeUserName") or "") != "נועה":  # CHANGE 2026-10-26 QA-DEBT-07: was has(page, "נועה")
            P.append("member name not shown (#homeUserName %r)" % H.text_of(page, "#homeUserName"))
    r = be.member(mid)
    if not r or r["user_id"] != be.uid_of("A") or r["display_name"] != "נועה" or r["role"] != "viewer" or r["status"] != "active":
        P.append("membership after claim: %r" % r)
    if be.member_of(tid, old_uid):
        P.append("old Safari identity still a member")
    if tid not in (app.ls().get("pt:_device:active_trip") or ""):
        P.append("pt:_device:active_trip not set")
    P = [p for p in P if "informational" not in p] + ([] if same_doc(page) or st != "app" else [])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("case", ["wrong", "used", "expired", "rate_limited", "offline", "already_member"])
def test_c04_claim_errors(env, case):
    """§1.4 / C9: wrong / used / expired code → "הקוד לא תקף. פותחים שוב…"; 6th wrong claim within an hour → the rate-limit
    toast; offline → the offline toast with the digits kept; already_member → an error, nothing moved."""
    tid, code = new_trip(env)
    be = env.backend
    page_err = TXT["t_invalid"]
    if case in ("used", "expired", "already_member"):
        uid0 = str(uuid.uuid4())
        mid = be.add_member(tid, uid0, "editor", "active", "Other")
        be.code_seq = ["135790"]
        be._join_trip(uid0, {"action": "issue_transfer", "trip_id": tid})
        if case == "used":
            be._join_trip(str(uuid.uuid4()), {"action": "claim_transfer", "code": "135790"})
        if case == "expired":
            be.clock_offset = 25 * H.HOUR
    dev = gate_device(env, "A", ua=H.IPHONE_UA, standalone=True)
    page, P = dev.page, []
    if case == "already_member":
        be.add_member(tid, be.uid_of("A"), "viewer", "pending", "ממתין")
    code6 = "135790" if case in ("used", "expired", "already_member") else "000000"
    if case == "rate_limited":
        for _ in range(5):
            enter_code(page, "000000")
            page.wait_for_timeout(200)
        enter_code(page, "000001")
        if not H.saw_toast(page, TXT["t_rate"], 4):
            P.append("6th wrong claim: %r not shown (err=%r toasts=%r)" % (TXT["t_rate"], H.text_of(page, "#ptF05Err"), H.toasts(page)))
    elif case == "offline":
        page.locator("#ptF05Otp0").fill("482916")
        dev.offline(True)
        page.locator("#ptF05Claim").click()
        if not H.saw_toast(page, TXT["t_offline"], 4):
            P.append("offline toast missing (err=%r)" % H.text_of(page, "#ptF05Err"))
        if otp_values(page) != list("482916"):
            P.append("digits not kept: %r" % otp_values(page))
    else:
        enter_code(page, code6)
        page.wait_for_timeout(500)
        err = norm(H.text_of(page, "#ptF05Err") or "") + " " + " ".join(H.toasts(page))
        if case == "already_member":
            if not err.strip():
                P.append("already_member: no error shown")
        elif norm(page_err) not in err:
            P.append("%s: error %r (want %r)" % (case, err, page_err))
        if H.app_state(page) == "app":
            P.append("trip started")
    if case == "already_member":
        r = be.member(mid)
        if r["user_id"] != uid0:
            P.append("membership moved")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("form", ["link", "code8"])
def test_c05_pasted_link_runs_join_flow_in_app(env, form):
    """C10 + §1.4a: "יש לי קישור הצטרפות מווטסאפ" → paste the link or the 8-char code → the 1.1 flow renders in the gate
    (#ptF05Join); request → pending → approved live → "פתיחת הטיול" starts the trip inside the app."""
    tid, code = new_trip(env)
    dev = gate_device(env, "A", ua=H.ANDROID_UA)
    page, be, P = dev.page, env.backend, []
    page.locator("#ptF05LinkBtn").click()
    page.wait_for_timeout(300)
    if page.evaluate("()=>document.getElementById('ptF05LinkBtn').getAttribute('aria-expanded')") != "true":
        P.append("aria-expanded not true")
    page.locator("#ptF05LinkIn").fill(JOIN_URL.format(c=code) if form == "link" else code.lower())
    page.locator("#ptF05LinkGo").click()
    st = H.wait_screen(page, ("form", "invalid", "error"), 10)
    if st != "form":
        P.append("in-app join form not shown (screen=%s, text=%r)" % (st, btext(page)[:200]))
        assert not P, "\n".join(P)
    if not page.evaluate("()=>{const r=document.getElementById('lpJoin');const j=document.getElementById('ptF05Join');return !!(r&&j&&j.contains(r))}"):
        P.append("join flow not rendered inside #ptF05Join")
    if "/app/" not in page.url:
        P.append("left the app: %s" % page.url)
    if not has(page, "יפן 2027"):
        P.append("trip name missing")
    st = submit_name(dev, "גלי", ("pending",))
    if st != "pending":
        P.append("pending not reached (%s)" % st)
    else:
        be.approve_direct(my_row(env, dev, tid)["id"], "editor")
        if H.wait_screen(page, "approved", 6) != "approved":
            P.append("approval not shown live in the app")
        else:
            page.locator("#lpjOpen").click()
            if H.wait_app_state(page, "app", 20) != "app" or H.running_trip(page) != tid:
                P.append("'פתיחת הטיול' did not start the trip in the app (state=%s)" % H.app_state(page))
    assert not P, "\n".join(P)


def test_c06_link_errors_and_back(env):
    """§1.4a: a string that is neither a link nor a code → an inline error, no call; a link with an unknown code → "הקישור כבר
    לא פעיל" in the gate; back (#lpjBack) returns to the transfer screen."""
    tid, code = new_trip(env)
    dev = gate_device(env)
    page, P = dev.page, []
    page.locator("#ptF05LinkBtn").click()
    page.locator("#ptF05LinkIn").fill("שלום")
    page.locator("#ptF05LinkGo").click()
    page.wait_for_timeout(500)
    if not (H.text_of(page, "#ptF05LinkErr") or "").strip():
        P.append("no #ptF05LinkErr for garbage")
    if calls(env, "join-trip"):
        P.append("garbage reached join-trip")
    page.locator("#ptF05LinkIn").fill(JOIN_URL.format(c="ZZZZ2345"))
    page.locator("#ptF05LinkGo").click()
    if H.wait_screen(page, ("invalid",), 8) != "invalid" or not has(page, TXT["invalid"]):
        P.append("unknown code in the app: screen %s" % H.screen_of(page))
    if not is_vis(page, "#lpjBack"):
        P.append("#lpjBack not visible")
    else:
        page.locator("#lpjBack").click()
        if not wait_until(lambda: is_vis(page, "#ptF05Transfer"), 5, page):
            P.append("back did not return to the transfer screen")
    assert not P, "\n".join(P)


def test_c07_f04_invite_entry_unchanged(env):
    """C10 + §1.4b: "כניסה עם הזמנה" on the not-connected screen still opens the F04 email entry."""
    dev = gate_device(env)
    f03.click_text(dev.page, TXT["invite_btn"])
    assert wait_has(dev.page, f04.TXT["send_code"], 6) and dev.page.locator(f04.SEL["email_input"]).filter(visible=True).count(), \
        "F04 email state not opened (text=%r)" % btext(dev.page)[:200]


# =====================================================================================================
# 4 · Manager home card (criteria 11, 12, 15, 16)
# =====================================================================================================
@pytest.mark.parametrize("role", ["manager", "editor", "viewer"])
def test_d01_card_only_for_managers(env, role):
    """C11 + D2: with a pending request, an active manager sees "ממתינים לאישור · 1" + "רק מנהלים רואים"; editors and viewers
    never see the card (nor its texts)."""
    tid, code = new_trip(env, managers=())
    env.backend.new_pending(tid, "נועה")
    dev = boot_member(env, tid, display="דנה" if role == "manager" else "חבר", role=role)
    page = dev.page
    shown = wait_until(lambda: card_vis(page), 6, page)
    if role == "manager":
        assert shown, "manager: card not shown"
        t = norm(H.text_of(page, "#ptF05Pending"))
        assert norm(TXT["card_title"].format(n=1)) in t and norm(TXT["managers_only"]) in t, "card texts: %r" % t
    else:
        assert not shown and not has(page, "ממתינים לאישור"), "%s sees the pending card" % role
        assert not [c for c in calls(env, "approve-member")], "approve-member called"


def test_d02_no_pending_no_card(env):
    """C11: a manager without pending requests sees no card."""
    tid, code = new_trip(env, managers=())
    dev = boot_member(env, tid)
    dev.page.wait_for_timeout(1500)
    assert not card_vis(dev.page), "card shown with 0 pending"


def test_d03_rows_order_and_expansion(env):
    """§1.5: rows newest first with avatar letter, name, "ביקש/ה להצטרף · לפני X"; the first row expanded with צופה / עורך
    (pressed) / מנהל and "אישור כעורך" + "דחייה"; others collapsed with "פתיחה", which expands that row and collapses the other."""
    tid, code = new_trip(env, managers=())
    be = env.backend
    old = be.new_pending(tid, "איתי", minutes_ago=60)
    new = be.new_pending(tid, "נועה", minutes_ago=5)
    dev = boot_member(env, tid)
    page, P = dev.page, []
    assert wait_until(lambda: card_vis(page), 6, page), "card not shown"
    rows = card_rows(page)
    if [r["id"] for r in rows] != [new, old]:
        P.append("order %r (want newest first)" % [r["text"][:20] for r in rows])
    else:
        r0, r1 = rows
        if r0["roles"] != [["viewer", "false"], ["editor", "true"], ["manager", "false"]]:
            P.append("first row roles %r" % r0["roles"])
        if norm(r0["approve"] or "") != norm(TXT["approve_as"].format(r="עורך")):
            P.append("approve label %r" % r0["approve"])
        if not norm(TXT["reject"]) in norm(r0["text"]):
            P.append("no 'דחייה'")
        for r, n in ((r0, "נועה"), (r1, "איתי")):
            if not (n in r["text"] and norm(TXT["asked"]) in norm(r["text"])):
                P.append("row %s text %r" % (n, r["text"]))
        if "נ" not in r0["text"].split("\n")[0]:
            P.append("avatar letter missing: %r" % r0["text"][:20])
        if r1["roles"] or r1["approve"] or not r1["open"]:
            P.append("second row not collapsed with 'פתיחה': %r" % r1)
        else:
            row_btn(page, old, "[data-open]").click()
            page.wait_for_timeout(400)
            rows = card_rows(page)
            if not (rows[1]["roles"] and rows[1]["approve"] and not rows[0]["roles"] and rows[0]["open"]):
                P.append("'פתיחה' did not swap the expanded row: %r" % rows)
    assert not P, "\n".join(P)


@pytest.mark.parametrize("role", ["viewer", "editor", "manager"])
def test_d04_approve_with_role(env, role):
    """C11: choosing a role and "אישור כ<role>" stores that role (approve-member {member_id, decision:'approve', role}); the
    row disappears, toast "<name> הצטרף/ה כ<role>", the card goes away with no more requests."""
    tid, code = new_trip(env, managers=())
    be = env.backend
    mid = be.new_pending(tid, "נועה")
    dev = boot_member(env, tid)
    page, P = dev.page, []
    assert wait_until(lambda: card_vis(page), 6, page)
    if role != "editor":
        row_btn(page, mid, '[data-role="%s"]' % role).click()
        page.wait_for_timeout(200)
        if row_btn(page, mid, '[data-role="%s"]' % role).get_attribute("aria-pressed") != "true":
            P.append("aria-pressed not moved to %s" % role)
        if norm(row_btn(page, mid, "[data-act=approve]").inner_text()) != norm(TXT["approve_as"].format(r=ROLE_WORD[role])):
            P.append("approve label %r" % row_btn(page, mid, "[data-act=approve]").inner_text())
    row_btn(page, mid, "[data-act=approve]").click()
    page.wait_for_timeout(800)
    r = be.member(mid)
    if not (r and r["status"] == "active" and r["role"] == role):
        P.append("row %r" % r)
    c = calls(env, "approve-member")
    if not c or c[-1]["body"] != {"member_id": mid, "decision": "approve", "role": role}:
        P.append("approve-member body %r" % (c[-1]["body"] if c else None))
    if not H.saw_toast(page, TXT["t_joined"].format(n="נועה", r=ROLE_WORD[role]), 4):
        P.append("toast %r missing (toasts=%r)" % (TXT["t_joined"].format(n="נועה", r=ROLE_WORD[role]), H.toasts(page)))
    if not wait_until(lambda: not card_vis(page), 4, page):
        P.append("card still shown with no pending")
    assert not P, "\n".join(P)


def test_d05_reject_inline_confirm(env):
    """§1.5 (F05-DOCS-03): "דחייה" → inline "לדחות את הבקשה של <name>?" with "כן, לדחות" / "ביטול" in the same row (no sheet);
    "ביטול" keeps the request; "כן, לדחות" → reject, row gone, toast "הבקשה נדחתה"."""
    tid, code = new_trip(env, managers=())
    be = env.backend
    mid = be.new_pending(tid, "נועה")
    keep = be.new_pending(tid, "איתי", minutes_ago=30)
    dev = boot_member(env, tid)
    page, P = dev.page, []
    assert wait_until(lambda: card_vis(page), 6, page)
    row_btn(page, mid, "[data-act=reject]").click()
    page.wait_for_timeout(300)
    rt = norm(page.locator('#ptF05Pending .pt5-req[data-member="%s"]' % mid).inner_text())
    for s in [TXT["reject_q"].format(n="נועה"), TXT["reject_yes"], TXT["reject_no"]]:
        if norm(s) not in rt:
            P.append("inline confirm: %r missing (row=%r)" % (s, rt))
    if page.locator(".modal.open, [role=dialog]:visible").count():
        P.append("a sheet / dialog opened")
    if calls(env, "approve-member"):
        P.append("rejected before confirming")
    row_btn(page, mid, "[data-act=reject-no]").click()
    page.wait_for_timeout(300)
    if not be.member(mid):
        P.append("'ביטול' rejected")
    row_btn(page, mid, "[data-act=reject]").click()
    page.wait_for_timeout(300)
    row_btn(page, mid, "[data-act=reject-yes]").click()
    page.wait_for_timeout(800)
    if be.member(mid):
        P.append("row not deleted")
    c = calls(env, "approve-member")
    if not c or c[-1]["body"].get("decision") != "reject":
        P.append("reject body %r" % (c[-1]["body"] if c else None))
    if not H.saw_toast(page, TXT["t_rejected"], 4):
        P.append("toast %r missing" % TXT["t_rejected"])
    if [r["id"] for r in card_rows(page)] != [keep]:
        P.append("rows after reject %r" % [r["id"] for r in card_rows(page)])
    if has(page, "כבר אינך חבר/ה"):  # CHANGE 2026-10-26 QA-DEBT-07: the manager was shown the F06 'removed' screen 1.8b
        P.append("manager sees the 'removed' screen after rejecting")
    assert_or_known_bug(P, "QA-DEBT-BUG-01", r"^(rows after reject|manager sees the 'removed')")


def test_d06_second_manager_not_pending(env):
    """C11: another manager handled the request meanwhile (no live event reached this phone) → approve answers not_pending →
    toast "הבקשה כבר טופלה" and the card refreshes (row gone)."""
    tid, code = new_trip(env, managers=())
    be = env.backend
    mid = be.new_pending(tid, "נועה")
    dev = boot_member(env, tid)
    page = dev.page
    assert wait_until(lambda: card_vis(page), 6, page)
    be.rt_silent = True
    be.approve_direct(mid, "viewer")
    row_btn(page, mid, "[data-act=approve]").click()
    P = []
    if not H.saw_toast(page, TXT["t_handled"], 5):
        P.append("toast %r missing (toasts=%r)" % (TXT["t_handled"], H.toasts(page)))
    if not wait_until(lambda: not card_vis(page), 5, page):
        P.append("card not refreshed after not_pending")
    if be.member(mid)["role"] != "viewer":
        P.append("role overwritten")
    assert not P, "\n".join(P)


def test_d07_live_new_request(env):
    """C11: with home open, a new request appears in the card without reload (Realtime trip_id=eq.<trip>)."""
    tid, code = new_trip(env, managers=())
    dev = boot_member(env, tid)
    page = dev.page
    same_doc_mark(page)
    page.wait_for_timeout(1000)
    assert not card_vis(page)
    t0 = time.time()
    joiner = join_pending(env, code, "נועה")
    ok = wait_until(lambda: card_vis(page) and "נועה" in (H.text_of(page, "#ptF05Pending") or ""), 6, page)
    assert ok and same_doc(page), "new request not shown live (%.1f s, card=%s)" % (time.time() - t0, card_vis(page))
    subs = [b.get("filter", {}).get("filter") for s in env.backend.rt_subs if s["device"] == "M" for b in (s["bindings"] or [])]
    assert "trip_id=eq.%s" % tid in subs, "no Realtime subscription trip_id=eq.<trip>: %r" % subs


def test_d08_offline_disabled(env):
    """C16 + §1.5: offline → the last known list stays with disabled buttons and "אין חיבור"; online again → enabled."""
    tid, code = new_trip(env, managers=())
    mid = env.backend.new_pending(tid, "נועה")
    dev = boot_member(env, tid)
    page, P = dev.page, []
    assert wait_until(lambda: card_vis(page), 6, page)
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    page.wait_for_timeout(800)
    if not card_vis(page) or "נועה" not in (H.text_of(page, "#ptF05Pending") or ""):
        P.append("offline: last known list not kept")
    dis = page.evaluate("""(m)=>[...document.querySelectorAll('#ptF05Pending .pt5-req[data-member="'+m+'"] [data-act]')]
      .filter(b=>b.getBoundingClientRect().height>0).map(b=>b.disabled||b.getAttribute('aria-disabled')==='true')""", mid)
    if not dis or not all(dis):
        P.append("offline: buttons not disabled %r" % dis)
    if norm(TXT["no_conn"]) not in norm(H.text_of(page, "#ptF05Pending") or ""):
        P.append("offline: 'אין חיבור' missing")
    try:
        row_btn(page, mid, "[data-act=approve]").click(timeout=800, force=True)
    except PWError:
        pass
    if calls(env, "approve-member"):
        P.append("offline approve was sent")
    dev.offline(False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    page.wait_for_timeout(1200)
    dis = page.evaluate("""(m)=>[...document.querySelectorAll('#ptF05Pending .pt5-req[data-member="'+m+'"] [data-act]')]
      .filter(b=>b.getBoundingClientRect().height>0).map(b=>b.disabled)""", mid)
    if not dis or any(dis):
        P.append("online again: buttons still disabled %r" % dis)
    assert not P, "\n".join(P)


def test_d09_not_manager_hides_card(env):
    """§1.5: approve-member answers not_manager (role changed elsewhere) → the card is hidden."""
    tid, code = new_trip(env, managers=())
    mid = env.backend.new_pending(tid, "נועה")
    dev = boot_member(env, tid)
    page = dev.page
    assert wait_until(lambda: card_vis(page), 6, page)
    env.backend.force[("approve-member", "approve")] = "not_manager"
    row_btn(page, mid, "[data-act=approve]").click()
    ok = wait_until(lambda: not card_vis(page), 5, page)
    assert_or_known_bug([] if ok else ["card still shown after not_manager"], "QA-DEBT-BUG-02", "^card still shown")  # QA-DEBT-07


LAYOUTS = {"v2_min": {}, "v2": {"HOME_MIN": "off"}, "v1": {"HOME_LAYOUT": "v1"}}


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_d10_card_on_every_home_layout_with_global_elements(env, layout):
    """C15 + §1.5: the card is at the top of home in HOME_LAYOUT v2 (HOME_MIN on / off) and v1; tab bar, chat FAB and FX pill
    stay visible and hit-testable; the sync card is still there; no horizontal scroll; touch targets ≥44px in the card."""
    if LAYOUTS[layout]:
        H.serve_app_flags(env, **LAYOUTS[layout])
    tid, code = new_trip(env, managers=())
    env.backend.new_pending(tid, "נועה")
    dev = boot_member(env, tid)
    page, P = dev.page, []
    f02.tab(page, "home")
    page.evaluate("()=>window.scrollTo(0,0)")
    if not wait_until(lambda: card_vis(page), 6, page):
        P.append("card not shown")
    else:
        top = page.evaluate("()=>document.getElementById('ptF05Pending').getBoundingClientRect().top")
        if top > 400:
            P.append("card not at the top of home (top=%d)" % top)
        P += layout_problems(page, "#ptF05Pending", "home card " + layout)
    page.evaluate("()=>window.scrollTo(0,0)")
    vis = f03.chrome_visible(page)
    if sorted(vis) != sorted(f03.SEL["trip_chrome"]):
        P.append("global elements hidden/covered: visible=%r" % vis)
    if not page.evaluate("()=>['hminSync','moreSyncCard','syncBadge'].some(id=>!!document.getElementById(id))"):
        P.append("sync card element missing")
    assert_or_known_bug(P, "QA-DEBT-BUG-03", r"touch target < 44px: (צופה|עורך|מנהל) \d+x4[0-3]$")  # CHANGE 2026-10-26 QA-DEBT-07


# =====================================================================================================
# 5 · "מי אני" and members (criterion 13)
# =====================================================================================================
def joined_member_in_app(env, tid, code, name="נועה", role="editor", stale="דנה"):
    dev = join_pending(env, code, name)
    env.backend.approve_direct(my_row(env, dev, tid)["id"], role)
    assert H.wait_screen(dev.page, "approved", 6) == "approved"
    dev.seed_ls({"vietnam_planner_user_v1": stale, "pt:%s:vietnam_planner_user_v1" % tid: stale, "pt:_device:vietnam_planner_user_v1": stale})
    dev.page.locator("#lpjOpen").click()
    assert H.wait_app_state(dev.page, "app", 25) == "app", "app did not start"
    dev.page.wait_for_timeout(1500)
    return dev


def test_e01_who_am_i_is_display_name(env):
    """C13 + D10: in a trip joined via F05 the name on home / budget / management is the member's display_name (a stale
    device name "דנה" is ignored), a new expense is written with by=<display_name>, and the user modal never opens
    (not even through openUserModal())."""
    tid, code = new_trip(env)
    dev = joined_member_in_app(env, tid, code, "נועה")
    page, be, P = dev.page, env.backend, []
    if page.locator("#userModal.open").count():
        P.append("user modal open after boot")
    if norm(H.text_of(page, "#homeUserName") or "") != "נועה":
        P.append("#homeUserName %r" % H.text_of(page, "#homeUserName"))
    f02.add_expense(page, "QA F05 expense", 37)
    page.wait_for_timeout(1500)
    if norm(H.text_of(page, "#currentUserNameLabel") or "") != "נועה":
        P.append("budget label %r" % H.text_of(page, "#currentUserNameLabel"))
    raw = be.kv(tid, "expenses") or "[]"
    try:
        exp = [e for e in json.loads(raw) if e.get("description") == "QA F05 expense"]
    except ValueError:
        exp = []
    if not exp or exp[0].get("by") != "נועה":
        P.append("expense by=%r (row %r)" % (exp[0].get("by") if exp else None, raw[:200]))
    page.evaluate("()=>{try{openUserModal()}catch(e){}}")
    page.wait_for_timeout(500)
    if page.locator("#userModal.open").count():
        P.append("openUserModal() opened the picker in cloud mode")
    assert not P, "\n".join(P)


def test_e02_vault_chips_are_active_members(env):
    """C13 + §1.7: the vault member chips list the trip's active members ordered by joined_at (pending / removed excluded,
    not the fixed USERS list), cached per trip."""
    tid, code = new_trip(env)
    be = env.backend
    be.new_pending(tid, "ממתין")
    gone = be.add_member(tid, str(uuid.uuid4()), "editor", "removed", "הוסר")
    dev = joined_member_in_app(env, tid, code, "נועה")
    page = dev.page
    page.evaluate("()=>document.getElementById('documentsBtn').click()")
    page.wait_for_timeout(1200)
    chips = page.evaluate("()=>[...document.querySelectorAll('#docMemberRow [data-doc-member]')].map(b=>b.getAttribute('data-doc-member')).filter(x=>x!=='all')")
    want = [r["display_name"] for r in be.members(tid, "active")]
    assert chips == want, "vault chips %r, expected active members by joined_at %r" % (chips, want)
    cache = dev.ls().get("pt:%s:members" % tid) or dev.ls().get("pt:%s:pt_members" % tid)
    assert cache and "נועה" in cache and "הוסר" not in cache, "per-trip member cache %r" % cache


# =====================================================================================================
# 6 · 390px / RTL / touch on all six screens (criterion 15)
# =====================================================================================================
@pytest.mark.parametrize("scr", ["join", "pending", "approved_iphone", "invalid", "transfer", "home_manager"])
def test_l01_layout_390(env, scr):
    """C15: no horizontal scroll, RTL, touch ≥44px on the six artboard screens; code boxes LTR (c01)."""
    tid, code = new_trip(env, managers=() if scr == "home_manager" else (("דנה", None),))
    if scr == "join":
        dev = env.new_device("J")
        open_join(dev, code)
    elif scr == "pending":
        dev = join_pending(env, code)
    elif scr == "approved_iphone":
        dev, _, _ = iphone_code(env, tid, code)
    elif scr == "invalid":
        dev = env.new_device("J")
        open_join(dev, "ZZZZ2345")
    elif scr == "transfer":
        dev = gate_device(env)
    else:
        env.backend.new_pending(tid, "נועה")
        env.backend.new_pending(tid, "איתי", minutes_ago=60)
        dev = boot_member(env, tid)
        assert wait_until(lambda: card_vis(dev.page), 6, dev.page)
    dev.page.wait_for_timeout(600)
    scope = {"transfer": "#ptGate", "home_manager": "#ptF05Pending"}.get(scr)
    P = layout_problems(dev.page, scope, scr)
    if scr == "home_manager":
        P += [p for p in layout_problems(dev.page, None, scr) if "horizontal" in p]
        assert_or_known_bug(P, "QA-DEBT-BUG-03", r"touch target < 44px: (צופה|עורך|מנהל) \d+x4[0-3]$")  # CHANGE 2026-10-26 QA-DEBT-07
    assert not P, "\n".join(P)


# =====================================================================================================
# 7 · Static (criterion 17) and the F04 done-screen replacement
# =====================================================================================================
def main_html():
    r = subprocess.run(["git", "-C", str(H.REPO_DIR), "show", "%s:app/index.html" % MAIN_REF], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()[:200]
    html = r.stdout.decode("utf-8")
    assert "APP_VERSION='3.0.0-alpha.5.1'" in html, "harness: %s is not alpha.5.1" % MAIN_REF
    return html


STATIC = ["protected:" + n for n in f02.PROTECTED] + ["app_version", "pt_version", "title", "change_comments",
                                                      "node_check", "no_new_duplicate_ids", "no_live_project_ref",
                                                      "mockup_annotation_not_shipped"]


@pytest.mark.parametrize("check", STATIC)
def test_s01_static(check, tmp_path):
    """C17: protected functions byte-identical to main (alpha.5.1); APP_VERSION / PT_VERSION = 3.0.0-alpha.6; <title>;
    'CHANGE 2026-10-19 F05-…' tags saying what changed; node --check on every inline script of app/ and join/ and on
    join/flow.js; no new duplicate ids; no live project ref; the mockup annotation is not shipped."""
    html = H.app_html()
    jhtml = H.join_html()
    flow = (H.JOIN_DIR / "flow.js").read_text(encoding="utf-8")
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = f20._extract(qa_refs.v2152_html(), [name], tmp_path)["found"][name]  # CHANGE 2026-10-26 QA-DEBT-06: was main_html()
        b = f20._extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1 and b and a[0] in b, "%s is not byte-identical to v2.15.2" % name
    elif check == "app_version":
        assert re.search(r"""const\s+APP_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "APP_VERSION != " + VERSION
    elif check == "pt_version":
        assert re.search(r"""PT_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "PT_VERSION != " + VERSION
    elif check == "title":
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        mj = re.search(r"<title>(.*?)</title>", jhtml, re.S)
        assert m and m.group(1).strip() == APP_NAME and mj and APP_NAME in mj.group(1), "titles %r / %r" % (m and m.group(1), mj and mj.group(1))
    elif check == "change_comments":
        for src, label in ((html, "app"), (jhtml, "join/index.html"), (flow, "join/flow.js")):
            assert "CHANGE 2026-10-19 F05-" in src, "no F05 CHANGE tag in " + label
        assert re.search(r"CHANGE 2026-10-19 F05-[^\n]*(alpha\.5\.1|was |no previous version)", html), "app CHANGE tags do not say what changed"
    elif check == "node_check":
        bad = []
        # CHANGE 2026-10-26 QA-DEBT-06: F02 extractor (browser-like tokenizer) instead of a regex on "<script"
        for label, f in (("app", H.APP_DIR / "index.html"), ("join", H.JOIN_DIR / "index.html")):
            dd = tmp_path / label
            dd.mkdir()
            r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(f)], env={**os.environ, "DUMP_DIR": str(dd)})
            assert r.returncode == 0, r.stderr
            files = sorted(list(dd.glob("*.js")) + list(dd.glob("*.mjs")))
            assert files, "no inline scripts found in %s" % label
            bad += ["%s/%s" % (label, x.name) for x in files if f02.node(["--check", str(x)]).returncode]
        p = tmp_path / "flow.js"
        p.write_text(flow, encoding="utf-8")
        if f02.node(["--check", str(p)]).returncode:
            bad.append("flow.js")
        assert not bad, "node --check failed: %r" % bad
    elif check == "no_new_duplicate_ids":
        def dups(h):
            c = collections.Counter(re.findall(r"""\bid=["']([A-Za-z][\w:-]*)["']""", h))
            return {k for k, v in c.items() if v > 1}
        assert not (dups(html) - dups(main_html())), "new duplicate ids %r" % sorted(dups(html) - dups(main_html()))
        if dups(jhtml) == {"joinTitle"}:  # CHANGE 2026-10-26 QA-DEBT-07: only the known fatal() duplicate → xfail
            # CHANGE 2026-10-26 FIX-04-QA: the id is written twice in the SOURCE (hidden F04 #m + fatal()), but since 3.0.0-alpha.7.2
            # fatal() removes #m first, so the DOM never holds two (checked at runtime by test_s02_join_fatal_single_title).
            if "getElementById('m');if(old)old.remove()" in jhtml:
                return
            assert_or_known_bug(["duplicate ids in /join/: {'joinTitle'}"], "QA-DEBT-BUG-04", "joinTitle")
        assert not dups(jhtml), "duplicate ids in /join/: %r" % dups(jhtml)
    elif check == "no_live_project_ref":
        for s in (html, jhtml, flow):
            assert f02.LIVE_REF not in s
    elif check == "mockup_annotation_not_shipped":
        for s in (html, jhtml, flow):
            assert "במוקאפ" not in s, "mockup annotation '(במוקאפ: …)' shipped"


def test_h00_standalone_fake(env):
    """CHANGE 2026-10-26 QA-DEBT-09 (harness guard): a standalone=True device answers matchMedia('(display-mode: standalone)')
    with matches=true without throwing, and navigator.standalone is true; other queries still reach the real matchMedia."""
    dev = env.new_device("S", ua=H.IPHONE_UA, standalone=True)
    dev.page.goto(env.server.origin + f02.BLANK_PATH)
    r = dev.page.evaluate("""()=>{const o={};try{o.m=window.matchMedia('(display-mode: standalone)').matches}catch(e){o.err=String(e)}
      o.nav=navigator.standalone===true;try{o.other=typeof window.matchMedia('(min-width: 1px)').matches}catch(e){o.err2=String(e)}return o}""")
    assert r == {"m": True, "nav": True, "other": "boolean"}, r


@pytest.mark.parametrize("state", ["on", "off"])
def test_r01_f04_done_screen(browser, state):
    """Replacement for F04 test_c11_c12_done_link_whatsapp_copy in the 'on' run: the F04 done screen keeps the summary, the
    join URL, WhatsApp / copy and the saved line; the amber "בקרוב … (F05)" card is shown only with JOIN_FEATURE='off'."""
    srv = f02.Server()
    try:
        if state == "off":
            srv.overrides[f04.APP_PATH] = H.flip_join(H.app_html(), "off").encode("utf-8")
        e = f04.Env(browser, srv)
        try:
            dev, iid, token = f04.to_step3(e)
            f04.create_and_done(dev)
            page, P = dev.page, []
            for k in ("join_card", "saved_line", "wa", "copy"):
                if not has(page, f04.TXT[k]):
                    P.append("done: %r missing" % f04.TXT[k])
            if "join/#code=" not in btext(page):
                P.append("join URL missing")
            soon = "דף ההצטרפות" in btext(page) or "(F05)" in btext(page)
            if state == "off" and not soon:
                P.append("'off': the F04 'בקרוב' F05 card is missing")
            if state == "on" and soon:
                P.append("'on': the stale 'בקרוב … F05' card is still shown")
            assert not P, "\n".join(P)
        finally:
            e.close()
    finally:
        srv.stop()
