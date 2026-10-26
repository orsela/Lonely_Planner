"""Lonely Planner F04-HOME QA · Playwright black-box suite · version 1.0.0
CHANGE 2026-10-26 F04H-QA-03: first version (no previous version).

Black-box acceptance tests for docs/F04-HOME_spec.md (commit ee5c723) §4 criteria 1–14, with the screens of §1 and the logic
of §3. Contract: the spec ONLY. NOT read: the F04-HOME implementation (app/index.html and invite/index.html after ee5c723),
any F04-HOME dev notes. The alpha.7 code at ee5c723 was read for existing ids / harness behaviour only.

Test ids: F4H-<criterion><letter> (F4H-00x = harness sanity, not a criterion). Every test docstring starts with its id.
Elements are found by the visible Hebrew texts of §1 (TXT below); new F04-HOME element ids are not in the spec. alpha.7 ids
that the spec keeps "unchanged" (F05 gate cards, device-code card) are used as in the F05 suite.

Harness: tests/f04home/harness.py (F06 harness + routed invite-manager / create-trip, UA + standalone devices, external
navigation capture, fake beforeinstallprompt / appinstalled). 390×844 Chromium, he-IL, Asia/Jerusalem, browser clock
installed at 2026-10-12 06:00Z (time flows; tests move it with page.clock.fast_forward / run_for).

Env: REPO_DIR, APP_DIR, BASE_REF (default ee5c723), QA_HEADFUL=1 to watch.
"""
import collections
import json
import os
import re
import time
import uuid

import pytest

import harness as H
from harness import f02, f03, f04, f05, f20, norm, btext, has, wait_has, layout_problems, is_vis, wait_until

from playwright.sync_api import Error as PWError

VERSION = "3.0.0-alpha.7.1"
EMAIL = H.INVITE_EMAIL
DRAFT = H.DRAFT

TXT = {
    # 1.1 in-app card on /invite/
    "inapp_title": "פותחים בדפדפן הרגיל",
    "open_safari": "פתיחה בספארי",
    "btn_failed": "הכפתור לא עבד?",
    "open_chrome": "לא נפתח? פתיחה ב-Chrome",
    "inapp_footer": "ההזמנה עצמה בתוקף. אם הדף נסגר – לוחצים שוב על הכפתור במייל.",
    # 1.2 real browser on /invite/
    "inv_ok": "ההזמנה שלך אומתה",
    "install_title": "קודם מוסיפים את האפליקציה למסך הבית",
    "add_to_home": "הוספה למסך הבית",
    "email_entry": "כניסה עם המייל",
    "info_line": "באפליקציה נשלח קוד בן 6 ספרות למייל שאליו נשלחה ההזמנה. הקוד מופיע בכותרת המייל – רואים אותו בהתראה.",
    "added_btn": "הוספתי – מה עכשיו?",
    "skip_link": "להמשיך בדפדפן בלי להתקין",
    "no_a2hs_a": "לא רואים",
    "no_a2hs_b": "פותחים את הדף בספארי",
    "open_app_btn": "פתיחה באפליקציה והקמת הטיול",
    "c2_line": "בסוף ההקמה תוכלו להתקין את האפליקציה",
    "inv_steps": "מה יקרה עכשיו",
    "inv_note_old": 'ולבחור "כניסה עם הזמנה"',
    "inv_bad": "הקישור כבר לא בתוקף",
    "inv_net": "אין חיבור. נסו שוב",
    "inv_loading": "בודקים את ההזמנה",
    # 1.3 gate
    "mgr_title": "מנהל/ת טיול",
    "badge": "חדש",
    "gate_text": "קיבלת הזמנה במייל, או שכבר הקמת טיול בדפדפן? נשלח קוד למייל שלך, ותמשיך/י בדיוק מאיפה שעצרת.",
    "old_gate_title": "קיבלת הזמנה לנהל טיול?",
    "old_gate_btn": "כניסה עם הזמנה",
    "f05_transfer": "כמעט שם",
    "f05_link": "יש לי קישור הצטרפות מווטסאפ",
    "device_card": f02.NC_BODY,
    # 1.4 code screen
    "banner_re": r"חזרת לדף - הקוד ששלחנו לפני (\d+) דקות עדיין תקף\. לא נשלח קוד חדש\.",
    "still_valid": "עדיין תקף",
    "where_title": "איפה הקוד? בהתראה של המייל",
    "where_line": "רואים את הקוד בלי לצאת מהדף. באייפון עם אפליקציית Mail המקלדת מציעה אותו לבד. הדבקה ממלאת את כל התיבות.",
    "resend_wait_re": r"שליחה חוזרת בעוד\s*(\d+):(\d\d)",
    "resend": "שליחה חוזרת",
    "change_email": "שינוי מייל",
    "verify_btn": "אימות והמשך להקמה",
    "offline": "אין חיבור. נסו שוב כשהרשת תחזור.",
    "no_invite": "לא מצאנו הזמנה פעילה",
    # 1.6 done
    "done_title": "הטיול נוצר",
    "a2hs_card": "מוסיפים את האפליקציה למסך הבית",
    "install_btn": "התקנת האפליקציה",
    "installed": "האפליקציה הותקנה – אפשר לפתוח אותה ממסך הבית",
    "manual_install": "התקנת אפליקציה",
    "later": "אחר כך – כניסה לטיול כאן",
    "enter": "כניסה לטיול ←",
    "join_card": "קישור הצטרפות לקבוצה",
}
EXIT_WORDS = ("חזרה", "ביטול", "יציאה", "סגירה")


# =====================================================================================================
# Fixtures
# =====================================================================================================
@pytest.fixture(scope="session")
def server():
    s = f05.F05Server()
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
def bad_token():
    return f03.new_token()      # well-formed, unknown to the backend → check answers {valid:false}


def invite_dev(env, ua, token=None, standalone=None, how="hash", name="I", wait=True, **kw):
    """Open /invite/ with the token (#invite=<t> | ?t=<t>). Returns (dev, token)."""
    if token is None:
        _, token = env.backend.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device(name, ua=ua, standalone=standalone, **kw)
    path = H.INVITE + ("#invite=" + token if how == "hash" else "?t=" + token)
    dev.page.goto(env.server.origin + path, wait_until="domcontentloaded")
    if wait:
        wait_invite(dev.page)
    return dev, token


def wait_invite(page, settle_ms=1500):
    wait_until(lambda: not has(page, TXT["inv_loading"]) and len(btext(page)) > 20, 12, page)
    page.wait_for_timeout(settle_ms)      # room for an automatic hop (Android, §3.1)


def gate_dev(env, ua="safari_iphone", standalone=True, name="G", **kw):
    dev = env.new_device(name, ua=ua, standalone=standalone, **kw)
    dev.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")
    st = f20.wait_state(dev.page, "nc", 25)
    assert st == "nc", "not-connected gate not reached (state=%r, text=%r)" % (st, btext(dev.page)[:200])
    dev.page.wait_for_timeout(400)
    return dev


def tap_entry(page, label=TXT["email_entry"]):
    assert H.wait_text(page, label, 8), "gate button %r not found (text=%r)" % (label, btext(page)[:300])
    H.click_text(page, label)
    page.wait_for_timeout(500)


def gate_to_code(env, email=EMAIL, invite=True, **kw):
    """Fresh device → gate → "כניסה עם המייל" → email → send → code screen. Returns dev."""
    if invite:
        env.backend.add_invite(email, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = gate_dev(env, **kw)
    tap_entry(dev.page)
    assert H.wait_screen(dev.page, "email") == "email", "email step not reached (screen=%s)" % H.screen(dev.page)
    H.send_email(dev, email)
    assert H.wait_screen(dev.page, "code") == "code", "code screen not reached (screen=%s, text=%r)" % (
        H.screen(dev.page), btext(dev.page)[-200:])
    return dev


def token_to_code(env, ua="safari_iphone", standalone=False, name="T", **kw):
    """Fresh device → app/?invite=1#invite=<token> (as today) → code screen. Returns (dev, token)."""
    _, token = env.backend.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device(name, ua=ua, standalone=standalone, **kw)
    dev.page.goto(env.server.origin + H.APP + "?invite=1#invite=" + token, wait_until="domcontentloaded")
    st = H.wait_screen(dev.page, ["code", "step1"], 20)
    assert st == "code", "code screen not reached from the token link (screen=%s, text=%r)" % (st, btext(dev.page)[:200])
    return dev, token


def reopen_after_reload(dev, path=None, entry=TXT["email_entry"]):
    """Reload (or load `path`) and come back to the wizard: the app may resume by itself, else the gate entry is tapped."""
    page = dev.page
    if path:
        f03.fresh_load(dev, path, ready=False)
    else:
        page.reload(wait_until="domcontentloaded")
    st = H.wait_screen(page, ["code", "email", "nc", "step1", "no_invite"], 25)
    if st == "nc":
        tap_entry(page, entry)
        st = H.wait_screen(page, ["code", "email", "step1", "no_invite"], 15)
    page.wait_for_timeout(500)
    return st


def shown_email(page, email):
    """The email is visible as text or as the value of a visible input."""
    return page.evaluate("""(e)=>{const vis=x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0};
      if((document.body.innerText||'').toLowerCase().includes(e))return true;
      return [...document.querySelectorAll('input')].some(i=>vis(i)&&String(i.value).toLowerCase()===e)}""", email.lower())


def banner_minutes(page):
    m = re.search(TXT["banner_re"], btext(page))
    return int(m.group(1)) if m else None


def cooldown_left(page):
    m = re.search(TXT["resend_wait_re"], btext(page))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def role_status_has(page, text):
    return page.evaluate("""(t)=>[...document.querySelectorAll('[role=status]')].some(e=>{const r=e.getBoundingClientRect();
      return r.width>0&&r.height>0&&(e.innerText||'').replace(/\\s+/g,' ').replace(/[\\u2013\\u2014]/g,'-').includes(t)})""", norm(text))


def buttons_disabled(page, label):
    c = H.find(page, label)
    return [x["disabled"] for x in c] if c else None


def key_problems(entry, raw, code, token, label):
    P = []
    if entry is None:
        return ["%s: %s not written" % (label, H.RESUME_KEY)]
    if code and code in (raw or ""):
        P.append("%s: the key contains the 6-digit code" % label)
    if token and token in (raw or ""):
        P.append("%s: the key contains the invite token" % label)
    if isinstance(entry, dict):
        extra = set(entry) - {"email", "sentAt", "kind", "origin", "v"}
        if extra:
            P.append("%s: unexpected fields %r (spec §2: {email, sentAt, kind, origin, v:1})" % (label, sorted(extra)))
        for k in ("email", "sentAt", "kind", "origin", "v"):
            if k not in entry:
                P.append("%s: field %r missing" % (label, k))
        if entry.get("v") != 1:
            P.append("%s: v=%r (expected 1)" % (label, entry.get("v")))
    else:
        P.append("%s: not a JSON object: %r" % (label, raw))
    return P


def wizard_to_done(env, ua, standalone, name="W", bip=None):
    """Browser tab (or installed app) → token link → code → steps 1–3 → create → "הטיול נוצר". Returns (dev, token)."""
    dev, token = token_to_code(env, ua=ua, standalone=standalone, name=name, bip=bip)
    page = dev.page
    H.type_code(page, env.backend.otp_code)
    assert H.wait_screen(page, "step1", 15) == "step1", "step 1 not reached (screen=%s)" % H.screen(page)
    f04.fill_step1(page, me="דנה", start="2027-04-03", end="2027-04-20")
    f04.press_next(page)
    assert H.wait_screen(page, "step2") == "step2", "step 2 not reached"
    f04.pick(page, "יפ", "JP")
    f04.press_next(page)
    assert H.wait_screen(page, "step3") == "step3", "step 3 not reached"
    f04.create_and_done(dev)
    page.wait_for_timeout(600)
    return dev, token


def visible_exact(page, text):
    return bool([x for x in H.find(page, text, exact=True)])


# =====================================================================================================
# F4H-00 · harness sanity (independent of the implementation — must pass on ee5c723)
# =====================================================================================================
def test_f4h_00a_backend_semantics():
    """F4H-00a: fake backend — create-trip lookup found / not found (unused vs used invite), activeTrips 0 / ≥1 for the
    manager account, signInWithOtp {shouldCreateUser:false} + verifyOtp(type 'email') switch to the account that owns the
    email, updateUser(email of another account) → email_exists."""
    be = H.F4HBackend()
    P = []
    uid, tids = be.manager_account("m@example.com", trips=1)
    be.used_invite("m@example.com", trip_id=tids[0])
    tok = "fake-at.%s.x" % uid
    be.tokens[tok] = uid
    st, r = be._create_trip(tok, {"action": "lookup"})
    if (st, r) != (200, {"found": False}):
        P.append("used invite: lookup %r %r" % (st, r))
    if be.active_trips(uid) != set(tids):
        P.append("manager activeTrips %r != %r" % (be.active_trips(uid), tids))
    uid0, t0 = be.manager_account("n@example.com", trips=0)
    if be.active_trips(uid0):
        P.append("trips=0 account has trips")
    be.add_invite("new@example.com", DRAFT, sent_days_ago=0, expires_in_days=7)
    s = be.sign_in()["session"]
    if "error" not in be.update_user(s["access_token"], {"email": "m@example.com"}, {}):
        P.append("updateUser(other account's email) did not answer email_exists")
    if "error" in be.update_user(s["access_token"], {"email": "new@example.com"}, {}):
        P.append("updateUser(new email) failed")
    if "error" in be.verify_otp("A", s["access_token"], {"email": "new@example.com", "token": be.otp_code, "type": "email_change"}):
        P.append("verifyOtp email_change failed")
    st, r = be._create_trip(s["access_token"], {"action": "lookup"})
    if not (st == 200 and r.get("found") is True and r.get("draft_name") == DRAFT):
        P.append("unused invite: lookup %r %r" % (st, r))
    s2 = be.sign_in()["session"]
    if be.sign_in_with_otp("B", s2["access_token"], {"email": "m@example.com", "options": {"shouldCreateUser": False}}).get("error"):
        P.append("signInWithOtp failed")
    v = be.verify_otp("B", s2["access_token"], {"email": "m@example.com", "token": be.otp_code, "type": "email"})
    if not v.get("session") or v["session"]["user"]["id"] != uid:
        P.append("verifyOtp(type email) did not switch to the manager account: %r" % v)
    assert not P, "\n".join(P)


HARNESS_PAGE = """<!doctype html><meta charset=utf-8><body>
<button id=s onclick="location.href='x-safari-https://h.test/Lonely_Planner/invite/#invite=abc'">s</button>
<button id=i onclick="location.href='intent://h.test/p?t=abc#Intent;scheme=https;package=com.android.chrome;end'">i</button>
<a id=a href="x-safari-https://h.test/q#invite=zz">a</a>
<button id=r onclick="location.replace('intent://h.test/r?t=1#Intent;scheme=https;end')">r</button>
<script>window.__alive=1;window.__bip=null;window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();window.__bip=e});
window.addEventListener('appinstalled',()=>{window.__inst=1})</script></body>"""


@pytest.mark.parametrize("ua", ["gmail_ios", "gmail_android_wv", "safari_iphone", "desktop"])
def test_f4h_00b_device_harness(env, ua):
    """F4H-00b: device harness — UA string reaches navigator.userAgent; standalone variants (navigator.standalone /
    display-mode); x-safari-https: and intent: navigations (location.href, location.replace, anchor) are captured and the
    page stays; fake beforeinstallprompt (prompt() reported) and appinstalled; the installed clock keeps its time across a
    reload."""
    env.server.overrides["/Lonely_Planner/__qa__/h.html"] = HARNESS_PAGE.encode("utf-8")
    P = []
    for sa, want_nav, want_dm in ((None, None, False), (True, True, True), ("ios", True, False), ("display", None, True),
                                  (False, False, False)):
        dev = env.new_device("H%s" % sa, ua=ua, standalone=sa)
        page = dev.page
        page.goto(env.server.origin + "/Lonely_Planner/__qa__/h.html", wait_until="domcontentloaded")
        got = page.evaluate("()=>({ua:navigator.userAgent,st:navigator.standalone,dm:matchMedia('(display-mode: standalone)').matches})")
        if got["ua"] != H.UAS[ua]:
            P.append("UA not applied: %r" % got["ua"])
        if (want_nav is True and got["st"] is not True) or (want_nav is False and got["st"] is not False):
            P.append("standalone=%r: navigator.standalone=%r" % (sa, got["st"]))
        if got["dm"] != want_dm:
            P.append("standalone=%r: display-mode standalone=%r" % (sa, got["dm"]))
    dev = env.new_device("N", ua=ua)
    page = dev.page
    page.goto(env.server.origin + "/Lonely_Planner/__qa__/h.html", wait_until="domcontentloaded")
    for sel in ("#s", "#i", "#a", "#r"):
        page.click(sel)
        page.wait_for_timeout(300)
    urls = [r["url"] for r in dev.ext_navs]
    if len(urls) != 4 or not urls[0].startswith("x-safari-https://") or not urls[1].startswith("intent://") \
            or not urls[2].startswith("x-safari-https://") or not urls[3].startswith("intent://"):
        P.append("external navigations not captured: %r" % urls)
    if page.evaluate("()=>window.__alive") != 1 or "/__qa__/h.html" not in page.url:
        P.append("page left on an external navigation: %r" % page.url)
    H.fire_bip(page)
    page.wait_for_timeout(100)
    page.evaluate("()=>window.__bip&&window.__bip.prompt()")
    page.wait_for_timeout(200)
    if len(dev.bip_prompts) != 1:
        P.append("prompt() not reported: %r" % dev.bip_prompts)
    H.fire_installed(page)
    if page.evaluate("()=>window.__inst") != 1:
        P.append("appinstalled not dispatched")
    t0 = H.clock_ms(page)
    page.clock.fast_forward(5 * 60 * 1000)
    page.reload(wait_until="domcontentloaded")
    t1 = H.clock_ms(page)
    if not (t1 - t0 >= 5 * 60 * 1000):
        P.append("clock did not keep time across reload (%d ms)" % (t1 - t0))
    dev2 = env.new_device("B", ua=ua, bip="auto")
    dev2.page.goto(env.server.origin + "/Lonely_Planner/__qa__/h.html", wait_until="domcontentloaded")
    dev2.page.wait_for_timeout(900)
    if not dev2.page.evaluate("()=>!!window.__bip"):
        P.append("bip='auto' did not fire beforeinstallprompt")
    assert not P, "\n".join(P)


def test_f4h_00c_routes_invite_and_wizard(env):
    """F4H-00c: the routed fake invite-manager answers /invite/'s check (a valid token shows the valid card on the page as
    served) and the routed fake create-trip answers the wizard's lookup (token link → code → step 1). Runs on the current
    pages whatever their version; only proves the harness wiring."""
    dev, token = invite_dev(env, "desktop")
    assert has(dev.page, TXT["inv_ok"]), "valid card not shown: %r" % btext(dev.page)[:300]
    assert env.backend.checks() and env.backend.checks()[-1]["body"].get("token") == token, "check not routed"
    d2, _ = token_to_code(env, ua="desktop", standalone=None, name="W")
    H.type_code(d2.page, env.backend.otp_code)
    assert H.wait_screen(d2.page, "step1", 15) == "step1", "lookup not routed (screen=%s)" % H.screen(d2.page)
    assert env.backend.lookups(), "no lookup call recorded"


# =====================================================================================================
# F4H-01 · flag off = alpha.7 (browser part; the F04/F05/F06 suites on a flipped copy: run.sh --only off)
# =====================================================================================================
def _base_invite_text(env, ua, token):
    """Body text of the alpha.7 /invite/ page (BASE_REF) for the same token and UA, served at /Lonely_Planner/invite_a7/."""
    src = H.base_file("invite/index.html").encode("utf-8")
    env.server.overrides[H.ROOT + "invite_a7/"] = src
    env.server.overrides[H.ROOT + "invite_a7/index.html"] = src
    dev = env.new_device("BASE", ua=ua)
    dev.page.goto(env.server.origin + H.ROOT + "invite_a7/#invite=" + token, wait_until="domcontentloaded")
    wait_invite(dev.page, 500)
    return btext(dev.page)


@pytest.mark.parametrize("ua", ["gmail_ios", "gmail_android_wv", "safari_iphone", "chrome_android", "desktop"])
def test_f4h_01a_off_invite_is_alpha7(env, ua):
    """F4H-01a (criterion 1): /invite/ with HOME_INSTALL_FEATURE='off' renders exactly the alpha.7 page text for a valid
    token in every UA (no in-app card, no hop, no install card, no C2 line, note still names "כניסה עם הזמנה")."""
    H.serve_home_off(env)
    dev, token = invite_dev(env, ua)
    page = dev.page
    P = []
    base = _base_invite_text(env, ua, token)
    if btext(page) != base:
        P.append("text differs from alpha.7:\n  off:     %r\n  alpha.7: %r" % (btext(page)[:400], base[:400]))
    if H.ext_navs(dev):
        P.append("external navigation with the flag off: %r" % [r["url"] for r in H.ext_navs(dev)])
    for k in ("inapp_title", "install_title", "c2_line"):
        if has(page, TXT[k]):
            P.append("%r shown with the flag off" % TXT[k])
    assert not P, "\n".join(P)


def test_f4h_01b_off_gate_is_alpha7(env):
    """F4H-01b (criterion 1): app with the flag off — gate keeps the alpha.7 F04 card ("קיבלת הזמנה לנהל טיול?" /
    "כניסה עם הזמנה", below the F05 cards); no "מנהל/ת טיול" card; the button opens the email step."""
    H.serve_home_off(env)
    dev = gate_dev(env)
    page = dev.page
    P = []
    for k in ("old_gate_title", "old_gate_btn", "f05_transfer", "f05_link", "device_card"):
        if not has(page, TXT[k]):
            P.append("gate lacks %r" % TXT[k])
    if has(page, TXT["mgr_title"]) or has(page, TXT["gate_text"]):
        P.append("F04-HOME gate card shown with the flag off")
    o = H.text_order(page, [TXT["f05_transfer"], TXT["old_gate_title"], TXT["device_card"]])
    if None not in o and not (o[0] < o[1] < o[2]):
        P.append("alpha.7 gate order changed: %r" % o)
    assert not P, "\n".join(P)
    tap_entry(page, TXT["old_gate_btn"])
    assert H.wait_screen(page, "email") == "email", "alpha.7 entry did not open the email step"


def test_f4h_01c_off_no_resume_no_key(env):
    """F4H-01c (criterion 1): flag off — sending a code writes no pt:_device:wz_resume; reload + "כניסה עם הזמנה" starts at
    the email step (no resume, no banner); the code screen has no "איפה הקוד?" card."""
    H.serve_home_off(env)
    env.backend.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = gate_dev(env)
    page = dev.page
    tap_entry(page, TXT["old_gate_btn"])
    assert H.wait_screen(page, "email") == "email"
    H.send_email(dev, EMAIL)
    assert H.wait_screen(page, "code") == "code"
    P = []
    if has(page, TXT["where_title"]):
        P.append("'איפה הקוד?' card shown with the flag off")
    if H.resume_raw(dev) is not None:
        P.append("%s written with the flag off: %r" % (H.RESUME_KEY, H.resume_raw(dev)))
    n = len(env.backend.sends())
    page.clock.fast_forward(60 * 1000)
    st = reopen_after_reload(dev, entry=TXT["old_gate_btn"])
    if st != "email":
        P.append("after reload: screen %s (alpha.7: the email step)" % st)
    if banner_minutes(page) is not None or has(page, TXT["still_valid"]):
        P.append("resume banner with the flag off")
    if len(env.backend.sends()) != n:
        P.append("a send happened on reopen")
    assert not P, "\n".join(P)


def test_f4h_01d_off_done_screen_unchanged(env):
    """F4H-01d (criterion 1): flag off — "הטיול נוצר" in an iPhone browser tab has no install card and the bottom button
    is today's "כניסה לטיול ←"."""
    H.serve_home_off(env)
    dev, _ = wizard_to_done(env, "safari_iphone", False)
    page = dev.page
    P = []
    if has(page, TXT["a2hs_card"]):
        P.append("install card shown with the flag off")
    if not H.find(page, TXT["enter"]):
        P.append("bottom button %r missing" % TXT["enter"])
    if has(page, TXT["later"]):
        P.append("%r shown with the flag off" % TXT["later"])
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-02 · /invite/: in-app vs real browser vs invalid
# =====================================================================================================
@pytest.mark.parametrize("ua", ["gmail_ios", "outlook_ios", "gsa_ios", "gmail_android_wv"])
def test_f4h_02a_inapp_card(env, ua):
    """F4H-02a (criterion 2, §1.1, §3.1): valid token in a mail app's in-app browser → card "פותחים בדפדפן הרגיל" with the
    iPhone button / Android fallback button and the footer line; no install card (1.2) on top of it."""
    dev, token = invite_dev(env, ua)
    page = dev.page
    P = []
    if not has(page, TXT["inapp_title"]):
        P.append("in-app card %r not shown (text=%r)" % (TXT["inapp_title"], btext(page)[:300]))
    if not has(page, TXT["inapp_footer"]):
        P.append("footer line missing")
    if ua in H.IOS_UAS:
        if not H.find(page, TXT["open_safari"]):
            P.append("iPhone: button %r missing" % TXT["open_safari"])
        if not has(page, TXT["btn_failed"]):
            P.append("iPhone: %r + manual steps missing" % TXT["btn_failed"])
    else:
        if not H.find(page, TXT["open_chrome"]):
            P.append("Android: fallback %r missing" % TXT["open_chrome"])
    if has(page, TXT["install_title"]):
        P.append("install card (1.2) shown inside the in-app browser")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("ua", ["safari_iphone", "chrome_android", "desktop"])
def test_f4h_02b_real_browser_no_inapp_card(env, ua):
    """F4H-02b (criterion 2): valid token in Safari / Chrome / desktop → no in-app card, no external navigation; the valid
    row "ההזמנה שלך אומתה" is shown (1.2)."""
    dev, token = invite_dev(env, ua)
    page = dev.page
    P = []
    if has(page, TXT["inapp_title"]):
        P.append("in-app card shown in a real browser")
    if H.ext_navs(dev):
        P.append("external navigation in a real browser: %r" % [r["url"] for r in H.ext_navs(dev)])
    if not has(page, TXT["inv_ok"]):
        P.append("valid row %r missing" % TXT["inv_ok"])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("ua", ["gmail_ios", "gmail_android_wv", "safari_iphone", "chrome_android"])
@pytest.mark.parametrize("how", ["hash", "query"])
def test_f4h_02c_invalid_token_no_hop_no_install(env, ua, how):
    """F4H-02c (criterion 2, §1.1 last bullet): invalid token (#invite= or ?t=) → today's invalid card, no hop, no in-app
    card, no install card, no C2 line."""
    dev, _ = invite_dev(env, ua, token=bad_token(), how=how)
    page = dev.page
    page.wait_for_timeout(800)
    P = []
    if not has(page, TXT["inv_bad"]):
        P.append("invalid card missing (text=%r)" % btext(page)[:200])
    if H.ext_navs(dev):
        P.append("hop for an invalid token: %r" % [r["url"] for r in H.ext_navs(dev)])
    for k in ("inapp_title", "install_title", "c2_line"):
        if has(page, TXT[k]):
            P.append("%r shown for an invalid token" % TXT[k])
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-03 · iPhone in-app: button-only hop to Safari
# =====================================================================================================
@pytest.mark.parametrize("ua", ["gmail_ios", "gsa_ios"])
def test_f4h_03a_iphone_button_only_hop(env, ua):
    """F4H-03a (criterion 3, §3.1): no automatic navigation after load (3 s); "פתיחה בספארי" navigates to exactly
    x-safari-https://<host><path>#invite=<token> (same page); the manual steps stay visible after the tap."""
    dev, token = invite_dev(env, ua)
    page = dev.page
    page.wait_for_timeout(3000)
    P = []
    if H.ext_navs(dev):
        P.append("automatic navigation on iPhone: %r" % [r["url"] for r in H.ext_navs(dev)])
    c = H.find(page, TXT["open_safari"])
    assert c, "button %r missing (text=%r)" % (TXT["open_safari"], btext(page)[:300])
    page.mouse.click(c[0]["x"], c[0]["y"])
    page.wait_for_timeout(800)
    host = env.server.origin.split("://", 1)[1]
    want = "x-safari-https://%s%s#invite=%s" % (host, H.INVITE, token)
    got = [r["url"] for r in H.ext_navs(dev, "safari")]
    if got != [want]:
        P.append("Safari hop: %r (expected exactly [%r])" % (got, want))
    if H.ext_navs(dev, "intent"):
        P.append("intent: navigation on iPhone")
    if not has(page, TXT["btn_failed"]):
        P.append("manual steps not visible after the tap")
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-04 · Android in-app: one automatic intent hop; ?t= consumed
# =====================================================================================================
def test_f4h_04a_android_single_auto_hop(env):
    """F4H-04a (criterion 4, §3.1): exactly ONE automatic navigation per load to
    intent://<host><path>?t=<token>#Intent;scheme=https;package=com.android.chrome;end; the fallback "לא נפתח? פתיחה
    ב-Chrome" goes to the same URL; no x-safari navigation."""
    dev, token = invite_dev(env, "gmail_android_wv")
    page = dev.page
    page.wait_for_timeout(3000)
    host = env.server.origin.split("://", 1)[1]
    want = "intent://%s%s?t=%s#Intent;scheme=https;package=com.android.chrome;end" % (host, H.INVITE, token)
    P = []
    auto = [r["url"] for r in H.ext_navs(dev, "intent")]
    if auto != [want]:
        P.append("automatic hop: %r (expected exactly one %r)" % (auto, want))
    if H.ext_navs(dev, "safari"):
        P.append("x-safari navigation on Android")
    c = H.find(page, TXT["open_chrome"])
    if not c:
        P.append("fallback %r missing" % TXT["open_chrome"])
    else:
        n = len(dev.ext_navs)
        page.mouse.click(c[0]["x"], c[0]["y"])
        page.wait_for_timeout(800)
        tap = [r["url"] for r in dev.ext_navs[n:]]
        if tap != [want]:
            P.append("fallback button: %r (expected [%r])" % (tap, want))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("ua", ["chrome_android", "safari_iphone", "desktop"])
def test_f4h_04b_query_t_works_like_hash_and_is_removed(env, ua):
    """F4H-04b (criterion 4): arriving with ?t=<token> works like #invite=<token> (check called with that token, valid card)
    and after load the address bar shows neither ?t= nor #invite= (history.replaceState)."""
    dev, token = invite_dev(env, ua, how="query")
    page = dev.page
    P = []
    chk = env.backend.checks()
    if not chk or chk[-1]["body"].get("token") != token:
        P.append("check not called with the ?t= token: %r" % [c["body"].get("token") for c in chk])
    if not has(page, TXT["inv_ok"]):
        P.append("valid card not shown for ?t= (text=%r)" % btext(page)[:200])
    u = H.url_now(page)
    if "t=" in u.split("/invite/", 1)[-1] or "invite=" in u or token in u:
        P.append("address bar still carries the token: %r" % u)
    assert not P, "\n".join(P)


def test_f4h_04c_token_never_stored_or_logged(env):
    """F4H-04c (§3.1 last bullet): after the ?t= and #invite= arrivals and the hop, the token is not in localStorage /
    sessionStorage / cookies / the console / any request URL except the hop target itself."""
    _, token = env.backend.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    P = []
    for ua, how in (("gmail_android_wv", "hash"), ("chrome_android", "query"), ("gmail_ios", "hash")):
        dev, _ = invite_dev(env, ua, token=token, how=how, name=ua)
        page = dev.page
        ss = page.evaluate("()=>JSON.stringify(Object.assign({},sessionStorage))")
        if any(token in (k + str(v)) for k, v in dev.ls().items()) or token in ss:
            P.append("%s/%s: token stored" % (ua, how))
        if any(token in c.get("value", "") for c in dev.ctx.cookies()):
            P.append("%s/%s: token in a cookie" % (ua, how))
        if [m for m in dev.console + dev.errors if token in m]:
            P.append("%s/%s: token logged" % (ua, how))
    bad = [r["url"] for r in env.net if token in r["url"] and "?t=" not in r["url"]]
    if bad:
        P.append("token in a request URL: %r" % bad)
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-05 · iPhone Safari install card
# =====================================================================================================
def test_f4h_05a_iphone_install_card(env):
    """F4H-05a (criterion 5, §1.2, §3.2): iPhone Safari (not standalone) → valid card shrinks to one row (✓ "ההזמנה שלך
    אומתה", draft name, expiry); card "קודם מוסיפים את האפליקציה למסך הבית" with 3 steps (… "הוספה למסך הבית" … "כניסה עם
    המייל"), the info line, the "לא רואים…" line, "הוספתי – מה עכשיו?" opens a sheet repeating step 3; the installed-app note
    names "כניסה עם המייל" (not "כניסה עם הזמנה"); no "מה יקרה עכשיו" 4-step card."""
    dev, token = invite_dev(env, "safari_iphone", standalone=False)
    page = dev.page
    t = btext(page)
    P = []
    for k in ("inv_ok", "install_title", "add_to_home", "email_entry", "info_line", "no_a2hs_a", "no_a2hs_b", "added_btn",
              "skip_link"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if DRAFT not in t:
        P.append("draft name %r not in the valid row" % DRAFT)
    exp = (H.FIXED_NOW + 7 * H.DAY).astimezone().strftime("%d/%m/%Y")
    if not re.search(r"\d\d/\d\d/\d{4}", t):
        P.append("expiry date missing (expected about %s)" % exp)
    if norm(TXT["inv_note_old"]) in t:
        P.append("installed-app note still names 'כניסה עם הזמנה'")
    if has(page, TXT["inv_steps"]):
        P.append("today's 4-step 'מה יקרה עכשיו' card still shown (valid card should shrink to one row)")
    o = H.text_order(page, [TXT["install_title"], TXT["add_to_home"], TXT["email_entry"]])
    if None not in o and not (o[0] < o[1] <= o[2]):
        P.append("install steps out of order: %r" % o)
    assert not P, "\n".join(P)
    before = btext(page)
    c = H.find(page, TXT["added_btn"])
    page.mouse.click(c[0]["x"], c[0]["y"])
    page.wait_for_timeout(700)
    after = btext(page)
    assert after != before and after.count(norm(TXT["email_entry"])) > before.count(norm(TXT["email_entry"])) or \
        page.locator("[role=dialog]:visible, dialog[open]").count(), \
        "'הוספתי – מה עכשיו?' did not open a sheet repeating step 3 ('כניסה עם המייל')"


def test_f4h_05b_skip_link_opens_wizard_as_today(env):
    """F4H-05b (criterion 5): "להמשיך בדפדפן בלי להתקין" → ../app/?invite=1#invite=<token> (today's link) → the app opens
    the wizard exactly as today: code screen with the invite email, one send (updateUser email_change)."""
    dev, token = invite_dev(env, "safari_iphone", standalone=False)
    page = dev.page
    a = [x for x in H.anchors_with(page, TXT["skip_link"]) if TXT["skip_link"] in x["text"]]
    P = []
    want = env.server.origin + H.APP + "?invite=1#invite=" + token
    if not a:
        P.append("skip link is not an <a href> (text %r)" % TXT["skip_link"])
    elif a[0]["href"] != want:
        P.append("skip link href %r != %r" % (a[0]["href"], want))
    assert not P, "\n".join(P)
    H.click_text(page, TXT["skip_link"])
    st = H.wait_screen(page, ["code", "step1"], 20)
    assert st == "code", "wizard code screen not reached (screen=%s, text=%r)" % (st, btext(page)[:200])
    if not shown_email(page, EMAIL):
        P.append("invite email not shown on the code screen")
    s = env.backend.sends()
    if len(s) != 1 or s[0]["op"] != "auth.updateUser":
        P.append("sends %r (today: exactly one updateUser{email})" % [c["op"] for c in s])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("sa", [True, "ios"])
def test_f4h_05c_iphone_standalone_no_install_card(env, sa):
    """F4H-05c (§3.2 `!navigator.standalone`): /invite/ opened with navigator.standalone true → no install card."""
    dev, _ = invite_dev(env, "safari_iphone", standalone=sa)
    assert not has(dev.page, TXT["install_title"]), "install card shown although navigator.standalone is true"
    assert has(dev.page, TXT["inv_ok"]), "valid row missing"


# =====================================================================================================
# F4H-06 · Android Chrome (C2) and desktop on /invite/
# =====================================================================================================
def test_f4h_06a_android_chrome_c2(env):
    """F4H-06a (criterion 6, C2): Android Chrome → no install card; today's button "פתיחה באפליקציה והקמת הטיול" (→
    ../app/?invite=1#invite=<token>) + the line "בסוף ההקמה תוכלו להתקין את האפליקציה"; note names "כניסה עם המייל"."""
    dev, token = invite_dev(env, "chrome_android")
    page = dev.page
    P = []
    if has(page, TXT["install_title"]):
        P.append("install card shown on Android")
    if not has(page, TXT["c2_line"]):
        P.append("C2 line %r missing" % TXT["c2_line"])
    a = [x for x in H.anchors_with(page, TXT["open_app_btn"]) if TXT["open_app_btn"] in x["text"]]
    if not a or a[0]["href"] != env.server.origin + H.APP + "?invite=1#invite=" + token:
        P.append("button %r → %r" % (TXT["open_app_btn"], a and a[0]["href"]))
    if norm(TXT["inv_note_old"]) in btext(page):
        P.append("installed-app note still names 'כניסה עם הזמנה'")
    assert not P, "\n".join(P)


def test_f4h_06b_desktop_today(env):
    """F4H-06b (§1.2 desktop): desktop → today's page: valid card, "מה יקרה עכשיו", the open-app button; no install card,
    no C2 line, no in-app card. The installed-app note, if shown, names "כניסה עם המייל" (§1.2 last bullet)."""
    dev, token = invite_dev(env, "desktop")
    page = dev.page
    P = []
    for k in ("inv_ok", "inv_steps", "open_app_btn"):
        if not has(page, TXT[k]):
            P.append("desktop lacks today's %r" % TXT[k])
    for k in ("install_title", "c2_line", "inapp_title"):
        if has(page, TXT[k]):
            P.append("desktop shows %r" % TXT[k])
    if norm(TXT["inv_note_old"]) in btext(page):
        P.append("installed-app note still names 'כניסה עם הזמנה'")
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-07 · the installed app's gate
# =====================================================================================================
@pytest.mark.parametrize("ua", ["safari_iphone", "chrome_android"])
def test_f4h_07a_gate_card_first_texts(env, ua):
    """F4H-07a (criterion 7, §1.3, C1): the "מנהל/ת טיול" card (badge "חדש", text, "כניסה עם המייל") is FIRST; then the F05
    cards (transfer code "כמעט שם", join link); the device-code card last. The alpha.7 texts "קיבלת הזמנה לנהל טיול?" /
    "כניסה עם הזמנה" are gone."""
    dev = gate_dev(env, ua=ua, standalone=True)
    page = dev.page
    P = []
    for k in ("mgr_title", "badge", "gate_text", "email_entry", "f05_transfer", "f05_link", "device_card"):
        if not has(page, TXT[k]):
            P.append("gate lacks %r" % TXT[k])
    for k in ("old_gate_title", "old_gate_btn"):
        if has(page, TXT[k]):
            P.append("old text %r still shown" % TXT[k])
    o = H.text_order(page, [TXT["mgr_title"], TXT["email_entry"], TXT["f05_transfer"], TXT["f05_link"], TXT["device_card"]])
    if None in o or not (o[0] < o[2] and o[1] < o[2] and o[2] < o[3] < o[4]):
        P.append("gate order (mgr, button, transfer, link, device code) = %r" % o)
    assert not P, "\n".join(P)


def test_f4h_07b_gate_card_two_bullets(env):
    """F4H-07b (§1.3 "two bullets (open invite → wizard; existing trip → opens)"): the manager card has two bullet items.
    The bullet wording is not in the spec: the test only requires two list items / bullet lines inside the card."""
    dev = gate_dev(env)
    n = dev.page.evaluate("""(t)=>{const N=s=>String(s||'').replace(/\\s+/g,' ').trim();
      const els=[...document.querySelectorAll('section,div,article')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&N(e.innerText).includes(t)&&N(e.innerText).includes('כניסה עם המייל')});
      const card=els.filter(e=>!els.some(o=>o!==e&&e.contains(o)))[0];if(!card)return -1;
      const li=card.querySelectorAll('li').length;if(li)return li;
      return N(card.innerText).split(/[•·●]/).length-1}""", TXT["mgr_title"])
    assert n >= 2, "manager card: %d bullet items (expected 2; -1 = card not found)" % n


def test_f4h_07c_entry_opens_email_step(env):
    """F4H-07c (criterion 7, §3.4): "כניסה עם המייל" opens the email step (today's entry mode: email input + "שליחת קוד"); no
    auth call before "שליחת קוד"; with an unused invite for the email → code → wizard step 1 (C1 case 1)."""
    env.backend.add_invite("new.manager@example.com", DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = gate_dev(env)
    page = dev.page
    tap_entry(page)
    P = []
    if H.wait_screen(page, "email") != "email":
        P.append("email step not shown (screen=%s)" % H.screen(page))
    if env.backend.sends():
        P.append("send before 'שליחת קוד'")
    assert not P, "\n".join(P)
    H.send_email(dev, "new.manager@example.com")
    assert H.wait_screen(page, "code") == "code", "code screen not reached"
    H.type_code(page, env.backend.otp_code)
    assert H.wait_screen(page, "step1", 15) == "step1", "open invite: wizard step 1 not reached (screen=%s)" % H.screen(page)


def test_f4h_07d_f05_and_device_cards_still_work(env):
    """F4H-07d (criterion 7): with the new card on top, the F05 transfer code still opens the trip, the join-link box still
    opens, and the device-code card shows the 8-character device code."""
    be = env.backend
    tid, _ = be.trip(name="יפן 2027", managers=(("אבי", None),), others=())
    sp = be.sign_in()["session"]
    be.add_member(tid, sp["user"]["id"], "editor", "active", "Safari")
    st, r = be._join_trip(sp["user"]["id"], {"action": "issue_transfer", "trip_id": tid})
    assert st == 200, "harness: issue_transfer %r" % r
    dev = gate_dev(env)
    page = dev.page
    P = []
    code = page.evaluate("()=>{const e=document.getElementById('ptDeviceCode');return e?e.textContent.trim():null}")
    if not code or len(code) != 8:
        P.append("device code %r" % code)
    try:
        page.locator("#ptF05LinkBtn").click(timeout=4000)
        page.wait_for_timeout(300)
        if not is_vis(page, "#ptF05LinkIn"):
            P.append("join-link box did not open")
    except PWError as e:
        P.append("join-link button: %s" % str(e)[:120])
    page.locator("#ptF05Otp0").fill(r["code"])
    page.wait_for_timeout(250)
    page.locator("#ptF05Claim").click()
    if H.wait_app_state(page, "app", 20) != "app":
        P.append("transfer code did not open the trip (state=%s)" % H.app_state(page))
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-08 · C3: used invite + active trip → trip opens without restart; no trips → "לא מצאנו הזמנה"
# =====================================================================================================
def test_f4h_08a_c3_used_invite_with_trip_opens_trip(env):
    """F4H-08a (criterion 8, C3, §3.4.2): installed app, fresh identity; "כניסה עם המייל" with the manager's email (an
    existing account whose invite is used and who manages one active trip) → code → the app boots into THAT trip with no
    restart by the user (no reload done by the test); "לא מצאנו הזמנה" is never shown."""
    be = env.backend
    uid, tids = be.manager_account(EMAIL, trips=1)
    be.used_invite(EMAIL, trip_id=tids[0])
    dev = gate_to_code(env, invite=False)
    page = dev.page
    f06h = H.f06
    f06h.watch(page, TXT["no_invite"])
    H.type_code(page, be.otp_code)
    st = H.wait_app_state(page, "app", 25)
    P = []
    if st != "app":
        P.append("the trip did not open after the code (state=%s, text=%r)" % (st, btext(page)[:300]))
    elif H.running_trip(page) != tids[0]:
        P.append("running trip %r != the manager's trip %r" % (H.running_trip(page), tids[0]))
    if has(page, TXT["no_invite"]) or f06h.seen_count(page, TXT["no_invite"]) > 0:
        P.append("'לא מצאנו הזמנה' shown")
    vo = be.verifies()
    if not vo or (vo[-1]["msg"].get("params") or {}).get("type") not in ("email", "magiclink"):
        P.append("verifyOtp not type 'email' (existing account): %r" % [(c["msg"].get("params") or {}).get("type") for c in vo])
    if be.ct("create"):
        P.append("create-trip 'create' called")
    assert not P, "\n".join(P)


def test_f4h_08b_c3_no_trips_no_invite_card(env):
    """F4H-08b (criterion 8, §3.4.3): same, but the account has no active trip → today's "לא מצאנו הזמנה פעילה…" card."""
    be = env.backend
    be.manager_account(EMAIL, trips=0)
    be.used_invite(EMAIL)
    dev = gate_to_code(env, invite=False)
    page = dev.page
    H.type_code(page, be.otp_code)
    st = H.wait_screen(page, "no_invite", 15)
    P = []
    if st != "no_invite":
        P.append("no-invite card not shown (screen=%s, state=%s)" % (st, H.app_state(page)))
    if H.app_state(page) == "app":
        P.append("a trip was started")
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-09 · code-screen resume (D15b, C4, §3.3)
# =====================================================================================================
def test_f4h_09a_resume_gate_within_10_min(env):
    """F4H-09a (criterion 9): gate entry, code sent; 3 min later the app is reloaded and "כניסה עם המייל" tapped (or the
    app resumes by itself) → code screen with the same email, banner "חזרת לדף – הקוד ששלחנו לפני 3 דקות עדיין תקף. לא נשלח
    קוד חדש." (role=status), NO second send (network log), no verify; the key is {email,sentAt,kind,origin,v:1} without
    code / token."""
    be = env.backend
    dev = gate_to_code(env)
    page = dev.page
    P = []
    t_send = H.clock_ms(page)
    raw, ent = H.resume_raw(dev), H.resume_entry(dev)
    P += key_problems(ent, raw, be.otp_code, None, "after send")
    if isinstance(ent, dict):
        if str(ent.get("email", "")).lower() != EMAIL:
            P.append("key email %r" % ent.get("email"))
        if not isinstance(ent.get("sentAt"), (int, float)) or abs(ent["sentAt"] - t_send) > 15000:
            P.append("sentAt %r not the send time (~%d)" % (ent.get("sentAt"), t_send))
    n = len(be.sends())
    if banner_minutes(page) is not None:
        P.append("banner shown on a fresh send")
    page.clock.fast_forward(3 * 60 * 1000 + 5000)
    st = reopen_after_reload(dev)
    if st != "code":
        P.append("after reload: screen %s (expected the code screen)" % st)
    else:
        if not shown_email(page, EMAIL):
            P.append("code screen without the same email")
        if banner_minutes(page) != 3:
            P.append("banner minutes %r (expected 3; text=%r)" % (banner_minutes(page), btext(page)[:300]))
        elif not role_status_has(page, "לא נשלח קוד חדש"):
            P.append("banner is not role=status")
    if len(be.sends()) != n:
        P.append("a second code was sent on resume: %r" % [c["op"] for c in be.sends()[n:]])
    if be.verifies():
        P.append("verifyOtp called on resume")
    assert not P, "\n".join(P)


def test_f4h_09b_resume_cooldown_continues(env):
    """F4H-09b (criterion 9, §1.4): reload 20 s after sending → the resend countdown continues from sentAt (≈0:25 left, not
    0:45); after 45 s from sentAt "שליחה חוזרת" is enabled."""
    dev = gate_to_code(env)
    page = dev.page
    page.clock.run_for(20000)
    st = reopen_after_reload(dev)
    assert st == "code", "not resumed to the code screen (screen=%s)" % st
    P = []
    left = cooldown_left(page)
    if left is None or not (18 <= left <= 27):
        P.append("countdown after reload at +20 s: %r s (expected ≈25)" % left)
    page.clock.run_for(27000)
    page.wait_for_timeout(400)
    if cooldown_left(page) is not None:
        P.append("still counting down 47 s after sentAt (%r)" % cooldown_left(page))
    r = [x for x in H.find(page, TXT["resend"]) if "בעוד" not in x["text"]]
    if not r or r[0]["disabled"]:
        P.append("'שליחה חוזרת' not enabled after 45 s")
    assert not P, "\n".join(P)


def test_f4h_09c_resume_invite_origin(env):
    """F4H-09c (criterion 9, §3.3 "on boot with ?invite=1"): token link → code sent; 2 min later app/?invite=1 is loaded →
    code screen with the invite email, banner "…לפני 2 דקות…", no second send; key origin differs from a gate send."""
    be = env.backend
    dev, token = token_to_code(env)
    page = dev.page
    P = []
    raw, ent = H.resume_raw(dev), H.resume_entry(dev)
    P += key_problems(ent, raw, be.otp_code, token, "invite send")
    n = len(be.sends())
    page.clock.fast_forward(2 * 60 * 1000 + 5000)
    st = reopen_after_reload(dev, path=H.APP + "?invite=1")
    if st != "code":
        P.append("app/?invite=1: screen %s (expected the code screen)" % st)
    elif banner_minutes(page) != 2:
        P.append("banner minutes %r (expected 2)" % banner_minutes(page))
    if not shown_email(page, EMAIL):
        P.append("invite email not shown")
    if len(be.sends()) != n:
        P.append("a second code was sent")
    assert not P, "\n".join(P)


def test_f4h_09d_after_10_min_normal_start(env):
    """F4H-09d (criterion 9): reload 10 min + 5 s after sending → normal start (the email step, no banner), no send on
    reopen, and the expired key is gone (§3.3 "Clear on … TTL")."""
    be = env.backend
    dev = gate_to_code(env)
    page = dev.page
    n = len(be.sends())
    page.clock.fast_forward(10 * 60 * 1000 + 5000)
    st = reopen_after_reload(dev)
    P = []
    if st != "email":
        P.append("after 10 min: screen %s (expected the email step)" % st)
    if banner_minutes(page) is not None or has(page, TXT["still_valid"]):
        P.append("resume banner after the TTL")
    if len(be.sends()) != n:
        P.append("a code was sent on reopen")
    if H.resume_raw(dev) is not None:
        P.append("expired key still stored: %r" % H.resume_raw(dev))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("how", ["verify_success", "change_email", "exit"])
def test_f4h_09e_key_cleared(env, how):
    """F4H-09e (criterion 9, C4): the key is removed on verify success (wizard step 1 reached), on "שינוי מייל" and on an
    explicit exit from the code screen (the spec does not name the exit control: any visible "חזרה" / "ביטול" / "יציאה" /
    "סגירה" control on the code screen is used)."""
    be = env.backend
    dev = gate_to_code(env)
    page = dev.page
    assert H.resume_raw(dev) is not None, "precondition: key not written after the send"
    if how == "verify_success":
        H.type_code(page, be.otp_code)
        assert H.wait_screen(page, "step1", 15) == "step1", "step 1 not reached"
    elif how == "change_email":
        H.click_text(page, TXT["change_email"])
        assert H.wait_screen(page, "email") == "email", "'שינוי מייל' did not return to the email step"
    else:
        c = [x for w in EXIT_WORDS for x in H.find(page, w, exact=True)]
        assert c, "no explicit exit control on the code screen (looked for %r) — spec §3.3 'explicit exit'" % (EXIT_WORDS,)
        page.mouse.click(c[0]["x"], c[0]["y"])
        page.wait_for_timeout(800)
    page.wait_for_timeout(400)
    assert H.resume_raw(dev) is None, "%s: key still stored: %r" % (how, H.resume_raw(dev))


def test_f4h_09f_key_never_holds_code_or_token(env):
    """F4H-09f (criterion 9 last clause, §2): token link → code sent → wrong code → resend → right code: at every step the
    key holds neither the 6-digit code (nor the wrong one typed) nor the invite token."""
    be = env.backend
    dev, token = token_to_code(env)
    page = dev.page
    P = []
    snaps = [("sent", H.resume_raw(dev))]
    H.type_code(page, "135790")
    page.wait_for_timeout(800)
    snaps.append(("wrong code", H.resume_raw(dev)))
    page.clock.run_for(46000)
    page.wait_for_timeout(300)
    r = [x for x in H.find(page, TXT["resend"]) if "בעוד" not in x["text"]]
    if r and not r[0]["disabled"]:
        page.mouse.click(r[0]["x"], r[0]["y"])
        page.wait_for_timeout(800)
    snaps.append(("resent", H.resume_raw(dev)))
    for label, raw in snaps:
        if raw is None:
            P.append("%s: key missing" % label)
            continue
        for secret, what in ((be.otp_code, "code"), ("135790", "typed code"), (token, "token")):
            if secret in raw:
                P.append("%s: key contains the %s: %r" % (label, what, raw))
    assert not P, "\n".join(P)


def test_f4h_09g_code_screen_where_is_code_card(env):
    """F4H-09g (§1.4): the code screen (fresh send, not resumed) shows "איפה הקוד? בהתראה של המייל" and its line, and no
    resume banner."""
    dev = gate_to_code(env)
    page = dev.page
    P = []
    for k in ("where_title", "where_line"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if banner_minutes(page) is not None:
        P.append("resume banner on a fresh send")
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-10 · "הטיול נוצר": install card only outside standalone
# =====================================================================================================
def _done_card_common(page, P):
    if not has(page, TXT["a2hs_card"]):
        P.append("install card %r missing" % TXT["a2hs_card"])
        return
    o = H.text_order(page, [TXT["a2hs_card"], TXT["join_card"]])
    if None not in o and not o[0] < o[1]:
        P.append("install card is not above the join-link card (%r)" % o)
    if not H.find(page, TXT["later"]):
        P.append("bottom button %r missing" % TXT["later"])
    if [x for x in H.find(page, TXT["enter"]) if norm(x["text"]) == norm(TXT["enter"])]:
        P.append("today's %r still shown next to the card" % TXT["enter"])


def test_f4h_10a_done_iphone_browser_ticks(env):
    """F4H-10a (criterion 10, §1.6 iPhone): Safari tab → card "מוסיפים את האפליקציה למסך הבית" above the join-link card,
    3 ticks naming "כניסה עם המייל" and the verified email (LTR); bottom "אחר כך – כניסה לטיול כאן" enters the trip."""
    dev, _ = wizard_to_done(env, "safari_iphone", False)
    page = dev.page
    P = []
    _done_card_common(page, P)
    if not has(page, TXT["email_entry"]):
        P.append("ticks do not name %r" % TXT["email_entry"])
    if EMAIL not in btext(page).lower():
        P.append("ticks do not show the verified email")
    else:
        d = f03.email_is_ltr(page, EMAIL)
        if not d or any(x != "ltr" for x in d):
            P.append("verified email not LTR: %r" % d)
    if H.find(page, TXT["install_btn"]):
        P.append("Android install button on iPhone")
    assert not P, "\n".join(P)
    H.click_text(page, TXT["later"])
    assert H.wait_app_state(page, "app", 20) == "app", "'%s' did not open the trip" % TXT["later"]


def test_f4h_10b_done_android_bip_prompt_and_installed(env):
    """F4H-10b (criterion 10, §1.6 Android): Chrome tab with a captured beforeinstallprompt → button "התקנת האפליקציה" →
    prompt() called once; on appinstalled the card reads "האפליקציה הותקנה – אפשר לפתוח אותה ממסך הבית"."""
    dev, _ = wizard_to_done(env, "chrome_android", False, bip="auto")
    page = dev.page
    P = []
    _done_card_common(page, P)
    c = H.find(page, TXT["install_btn"])
    if not c:
        P.append("button %r missing (beforeinstallprompt was fired %r times)" % (TXT["install_btn"], H.bip_state(page).get("fired")))
        assert not P, "\n".join(P)
    page.mouse.click(c[0]["x"], c[0]["y"])
    page.wait_for_timeout(600)
    if len(dev.bip_prompts) != 1:
        P.append("prompt() called %d times (expected 1)" % len(dev.bip_prompts))
    H.fire_installed(page)
    if not wait_has(page, TXT["installed"], 5):
        P.append("appinstalled: %r not shown" % TXT["installed"])
    assert not P, "\n".join(P)


def test_f4h_10c_done_android_without_bip_manual_hint(env):
    """F4H-10c (§1.6): Chrome tab without beforeinstallprompt → 2-line manual hint ("התקנת אפליקציה" / "הוספה למסך
    הבית"), no install button."""
    dev, _ = wizard_to_done(env, "chrome_android", False)
    page = dev.page
    P = []
    _done_card_common(page, P)
    if not has(page, TXT["manual_install"]) or not has(page, TXT["add_to_home"]):
        P.append("manual hint missing (%r / %r)" % (TXT["manual_install"], TXT["add_to_home"]))
    if H.find(page, TXT["install_btn"], exact=True):
        P.append("install button without a captured beforeinstallprompt")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("ua,sa", [("safari_iphone", "ios"), ("chrome_android", "display"), ("safari_iphone", True)])
def test_f4h_10d_done_standalone_no_card(env, ua, sa):
    """F4H-10d (criterion 10): in standalone (navigator.standalone true, or display-mode: standalone) → no install card and
    the bottom button is today's "כניסה לטיול ←"."""
    dev, _ = wizard_to_done(env, ua, sa, bip="auto" if ua == "chrome_android" else None)
    page = dev.page
    P = []
    if has(page, TXT["a2hs_card"]):
        P.append("install card shown in standalone")
    if has(page, TXT["later"]):
        P.append("%r shown in standalone" % TXT["later"])
    if not [x for x in H.find(page, TXT["enter"]) if norm(x["text"]) == norm(TXT["enter"])]:
        P.append("bottom button %r missing" % TXT["enter"])
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-11 · 390px: no horizontal scroll, RTL, touch ≥44px, URLs/emails LTR (6 artboards)
# =====================================================================================================
LAYOUT = ["inapp_ios", "inapp_android", "install_ios", "install_android", "gate", "code_resumed", "done_ios",
          "done_android"]


@pytest.mark.parametrize("scr", LAYOUT)
def test_f4h_11_layout_390(env, scr):
    """F4H-11 (criterion 11): each F04-HOME screen at 390px — no horizontal scroll, RTL, every hit-testable control ≥44px,
    nothing outside the viewport; the email on the code / done screens is LTR. The screen must first show its F04-HOME
    marker text (else the layout check is meaningless)."""
    marker = None
    if scr == "inapp_ios":
        dev, _ = invite_dev(env, "gmail_ios")
        marker = TXT["inapp_title"]
    elif scr == "inapp_android":
        dev, _ = invite_dev(env, "gmail_android_wv")
        marker = TXT["inapp_title"]
    elif scr == "install_ios":
        dev, _ = invite_dev(env, "safari_iphone", standalone=False)
        marker = TXT["install_title"]
    elif scr == "install_android":
        dev, _ = invite_dev(env, "chrome_android")
        marker = TXT["c2_line"]
    elif scr == "gate":
        dev = gate_dev(env)
        marker = TXT["mgr_title"]
    elif scr == "code_resumed":
        dev = gate_to_code(env)
        dev.page.clock.fast_forward(2 * 60 * 1000)
        reopen_after_reload(dev)
        marker = TXT["still_valid"]
    elif scr == "done_ios":
        dev, _ = wizard_to_done(env, "safari_iphone", False)
        marker = TXT["a2hs_card"]
    else:
        dev, _ = wizard_to_done(env, "chrome_android", False, bip="auto")
        marker = TXT["a2hs_card"]
    page = dev.page
    assert has(page, marker), "%s: marker %r not shown — screen not reached (text=%r)" % (scr, marker, btext(page)[:200])
    P = layout_problems(page, None, scr)
    if scr in ("code_resumed", "done_ios"):
        d = f03.email_is_ltr(page, EMAIL)
        inp = page.evaluate("(e)=>[...document.querySelectorAll('input')].filter(i=>String(i.value).toLowerCase()===e).map(i=>getComputedStyle(i).direction)", EMAIL)
        if (d and any(x != "ltr" for x in d)) or any(x != "ltr" for x in inp) or (not d and not inp):
            P.append("%s: email not shown LTR (text %r, inputs %r)" % (scr, d, inp))
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-12 · offline
# =====================================================================================================
@pytest.mark.parametrize("ua", ["gmail_ios", "gmail_android_wv", "safari_iphone", "chrome_android"])
def test_f4h_12a_invite_offline_today(env, ua):
    """F4H-12a (criterion 12): /invite/ offline (navigator.onLine false) → today's no-connection state "אין חיבור. נסו
    שוב" with "נסו שוב"; no hop, no in-app card, no install card."""
    _, token = env.backend.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device("O", ua=ua, offline_boot=True)
    dev.page.goto(env.server.origin + H.INVITE + "#invite=" + token, wait_until="domcontentloaded")
    wait_invite(dev.page)
    page = dev.page
    P = []
    if not has(page, TXT["inv_net"]):
        P.append("no-connection state missing (text=%r)" % btext(page)[:200])
    if H.ext_navs(dev):
        P.append("hop while offline")
    for k in ("inapp_title", "install_title", "c2_line"):
        if has(page, TXT[k]):
            P.append("%r shown offline" % TXT[k])
    assert not P, "\n".join(P)


def test_f4h_12b_resume_offline_never_claims_valid(env):
    """F4H-12b (criterion 12): a valid resume entry, the app reopened offline → nothing says the code is still valid
    ("עדיין תקף" absent), no send; if the code screen is shown, verify and resend are disabled and today's offline line is
    shown."""
    be = env.backend
    dev = gate_to_code(env)
    page = dev.page
    n = len(be.sends())
    page.clock.fast_forward(60 * 1000)
    f20.set_offline_cookie(dev, True)
    page.reload(wait_until="domcontentloaded")
    st = H.wait_screen(page, ["code", "email", "nc"], 25)
    if st == "nc":
        c = H.find(page, TXT["email_entry"])
        if c and not c[0]["disabled"]:
            page.mouse.click(c[0]["x"], c[0]["y"])
            page.wait_for_timeout(800)
    page.wait_for_timeout(800)
    P = []
    if has(page, TXT["still_valid"]):
        P.append("offline: the banner claims the code is still valid")
    if len(be.sends()) != n:
        P.append("offline: a send was attempted")
    if H.screen(page) == "code":
        for lab in (TXT["verify_btn"], TXT["resend"]):
            d = buttons_disabled(page, lab)
            if d and not all(d):
                P.append("offline: %r enabled" % lab)
        if not has(page, TXT["offline"]):
            P.append("offline line %r missing on the code screen" % TXT["offline"])
    assert not P, "\n".join(P)


# =====================================================================================================
# F4H-13 · static
# =====================================================================================================
STATIC = ["protected:" + n for n in f02.PROTECTED] + ["app_version", "pt_version", "invite_version_comment",
                                                     "flag_declared", "change_comments", "node_check", "no_duplicate_ids",
                                                     "no_live_project_ref"]


def _scripts(src):
    """Inline classic/module scripts, parsed with html.parser (a regex on "<script" also matches the word inside comments
    and JS strings of the app — that gave false node --check failures on alpha.7)."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.out, self.cur = [], None

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                a = dict(attrs)
                t = (a.get("type") or "").strip().lower()
                ok = "src" not in a and t in ("", "module", "text/javascript", "application/javascript")
                self.cur = [("module" if t == "module" else ""), []] if ok else None

        def handle_data(self, data):
            if self.cur is not None:
                self.cur[1].append(data)

        def handle_endtag(self, tag):
            if tag == "script" and self.cur is not None:
                self.out.append((self.cur[0], "".join(self.cur[1])))
                self.cur = None

    p = P()
    p.feed(src)
    p.close()
    return p.out


@pytest.mark.parametrize("check", STATIC)
def test_f4h_13_static(check, tmp_path):
    """F4H-13 (criterion 13): protected functions byte-identical to ee5c723 (alpha.7); APP_VERSION / PT_VERSION =
    3.0.0-alpha.7.1; /invite/ version comment alpha.7.1; HOME_INSTALL_FEATURE declared ('on') in app/ and /invite/;
    'CHANGE 2026-10-2x F04H-…' comments saying what changed from alpha.7 in both files; node --check on every inline
    script; no new duplicate ids in app/, none in /invite/; no live project ref."""
    html, inv = H.app_html(), H.invite_html()
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = f20._extract(H.base_file("app/index.html"), [name], tmp_path)["found"][name]
        b = f20._extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1 and b and a[0] in b, "%s is not byte-identical to %s" % (name, H.BASE_REF)
    elif check == "app_version":
        assert re.search(r"""const\s+APP_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "APP_VERSION != " + VERSION
    elif check == "pt_version":
        assert re.search(r"""PT_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "PT_VERSION != " + VERSION
    elif check == "invite_version_comment":
        head = "\n".join(re.findall(r"<!--(.*?)-->", inv, re.S))
        assert re.search(r"version\s+%s\b" % re.escape(VERSION), head), "/invite/ version comment is not %s" % VERSION
    elif check == "flag_declared":
        assert H.flag_value(html) == "on", "HOME_INSTALL_FEATURE='on' not declared in app/index.html (got %r)" % H.flag_value(html)
        assert H.flag_value(inv) == "on", "HOME_INSTALL_FEATURE='on' not declared in invite/index.html (got %r)" % H.flag_value(inv)
    elif check == "change_comments":
        for src, label in ((html, "app/index.html"), (inv, "invite/index.html")):
            tags = re.findall(r"CHANGE 2026-10-2\d F04H-[A-Z0-9-]+[^\n]*", src)
            assert tags, "no 'CHANGE 2026-10-2x F04H-…' comment in " + label
            assert any(re.search(r"alpha\.7|was |no previous version|what changed", t) for t in tags), \
                "%s: F04H CHANGE comments do not say what changed from alpha.7: %r" % (label, tags[:3])
    elif check == "node_check":
        bad = []
        for label, src in (("app", html), ("invite", inv)):
            for i, (attrs, code) in enumerate(_scripts(src)):
                p = tmp_path / ("%s_%d.%s" % (label, i, "mjs" if "module" in attrs else "js"))
                p.write_text(code, encoding="utf-8")
                if f02.node(["--check", str(p)]).returncode:
                    bad.append(p.name)
        assert not bad, "node --check failed: %r" % bad
    elif check == "no_duplicate_ids":
        def dups(h):
            c = collections.Counter(re.findall(r"""\bid=["']([A-Za-z][\w:-]*)["']""", h))
            return {k for k, v in c.items() if v > 1}
        new = dups(html) - dups(H.base_file("app/index.html"))
        assert not new, "new duplicate ids in app/: %r" % sorted(new)
        assert not dups(inv), "duplicate ids in /invite/: %r" % sorted(dups(inv))
    elif check == "no_live_project_ref":
        for s in (html, inv):
            assert f02.LIVE_REF not in s


# =====================================================================================================
# F4H-14 · advisors (outside this suite)
# =====================================================================================================
def test_f4h_14_advisors_manual():
    """F4H-14 (criterion 14): "no new Supabase advisor warnings" is checked in the Supabase dashboard (no server change in
    F04-HOME; this suite never calls Supabase)."""
    pytest.skip("criterion 14 is a dashboard check (Supabase advisors) — not automatable offline")
