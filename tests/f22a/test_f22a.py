"""Lonely Planner F22a QA · Playwright suite (sign in with Google) · version 1.0.0
CHANGE 2026-11-07 F22A-QA-02: new file (no previous version).

Contract: docs/F22a_spec.md §5 acceptance 1–13 (dev suite; the independent QA team writes its own). Google is never reached:
tests/f22a/harness.py patches the fake supabase-js so linkIdentity / signInWithOAuth "return from Google" with the URL the
backend scripts (token hash, ?code=, or error_code=…). Every test names its criterion: test_aNN_… . 390×844 Chromium, he-IL.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

f02, f04, f05, f20 = H.f02, H.f04, H.f05, H.f20
VERSION = os.environ.get("QA_EXPECTED_VERSION", "3.0.0-alpha.11")
NOA = "noa.family@gmail.com"
YOAV = "yoav.k@gmail.com"


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
    H.serve(e, "on")
    yield e
    e.close()
    server.reset()


def errs(dev):
    return ["page error: %s" % x for x in H.page_errors(dev)]


def press_google(page, sel):
    assert H.wait_vis(page, sel), "%s not visible" % sel
    page.locator(sel).click()


def members_rows(be):
    return len(be.rows["trip_members"])


# =====================================================================================================
# 11 · flag off = alpha.10 · beta switch
# =====================================================================================================
def _capture(env, src, name):
    H.serve(env, src=src)
    dev = env.new_device(name)
    dev.page.goto(env.server.origin + H.APP, wait_until="commit")
    assert f20.wait_state(dev.page, "nc", 20) == "nc"
    dev.page.wait_for_timeout(600)
    sig = dev.page.evaluate(H.SIG_JS, ["#ptGate"])
    sig["#ptGate"] = [re.sub(r'(ptDeviceCode~[^"]*)"[0-9a-f]{8}"', r'\1"XXXXXXXX"', x) for x in sig["#ptGate"]]   # random uid
    return dev, sig


@pytest.mark.parametrize("variant", ["off", "beta_without_key"])
def test_a11_flag_off_gate_equals_alpha10(env, variant):
    """11 / C13: 'off' (and 'beta' on a device without the key) → the gate is the alpha.10 gate, no Google, no F22 DOM."""
    _, a10 = _capture(env, H.base_file(), "A10")
    src = H.flip(H.app_html(), "off" if variant == "off" else "beta")
    dev, cur = _capture(env, src, "CUR")
    P = []
    if a10 != cur:
        import difflib
        P.append("gate differs from alpha.10:\n" + "\n".join(list(difflib.unified_diff(a10["#ptGate"], cur["#ptGate"], lineterm=""))[:30]))
    found = dev.page.evaluate("()=>[...document.querySelectorAll('[id^=ptF22],.pt22-gbtn')].map(e=>e.id||e.className)")
    if found or "Google" in H.body(dev.page):
        P.append("F22 DOM / Google present: %r" % found)
    if dev.page.evaluate("()=>document.documentElement.classList.contains('pt-f22')"):
        P.append("html.pt-f22 set")
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a11_flag_off_more_equals_alpha10(env):
    """11: inside a trip with 'off' the "עוד" panel has no "אני" row (alpha.10 rows)."""
    H.serve(env, "off")
    tid, dev = H.boot_member(env)
    H.h10.tab(dev.page, "more")
    dev.page.wait_for_timeout(1200)
    P = []
    if dev.page.evaluate("()=>!!document.getElementById('ptF22MeRow')||!!document.getElementById('ptF22Me')"):
        P.append("'אני' row / screen present with flag off")
    if not H.vis(dev.page, "#ptLinkEmailRow") and not H.vis(dev.page, "#ptEmailRow"):
        P.append("F03 email row hidden with flag off")
    assert not P + errs(dev), "\n".join(P)


def test_a11_beta_hash_switch(env):
    """Flag 'beta': #f22beta sets localStorage['pt-f22-beta']='1' and clears the hash; #f22beta-off removes it."""
    H.serve(env, "beta")
    dev = env.new_device("B")
    page = dev.page
    page.goto(env.server.origin + H.APP + "#f22beta", wait_until="commit")
    assert f20.wait_state(page, "nc", 20) == "nc"
    P = []
    if dev.ls().get(H.BETA_KEY) != "1":
        P.append("beta key not set")
    if "#f22beta" in H.url(page):
        P.append("hash not cleared: " + H.url(page))
    if not H.wait_vis(page, "#ptF22GateGoogle"):
        P.append("beta device: no Google button on the gate")
    page.goto(env.server.origin + H.APP + "#f22beta-off", wait_until="commit")
    f20.wait_state(page, "nc", 20)
    page.wait_for_timeout(500)
    if H.BETA_KEY in dev.ls():
        P.append("beta key not removed by #f22beta-off")
    if H.vis(page, "#ptF22GateGoogle"):
        P.append("Google still shown after #f22beta-off")
    assert not P + errs(dev), "\n".join(P)


# =====================================================================================================
# 1 · 2 · link inside the trip (same uid)
# =====================================================================================================
@pytest.mark.parametrize("role", ["editor", "viewer"])
def test_a01_member_links_google_same_uid(env, role):
    be = env.backend
    be.google(NOA)
    tid, dev = H.boot_member(env, role=role)
    page = dev.page
    uid0, n0 = dev.uid(), members_rows(be)
    H.open_me(page)
    P = []
    t = H.text(page, "#ptF22Me")
    for w in ("אני · נועה", "חשבון כניסה", "לא חובה", "המשך עם Google", "קוד למייל", "Facebook"):
        if w not in t:
            P.append("'אני' screen lacks %r" % w)
    press_google(page, "#ptF22Google")
    H.after_return(dev)
    if not H.in_trip(dev):
        pytest.fail("not back in the trip after the return")
    if not H.wait_vis(page, "#ptF22GoogleRow", 10):
        P.append("Google row not shown after the return (back on 'אני')")
    if dev.uid() != uid0:
        P.append("uid changed %s → %s" % (uid0, dev.uid()))
    if "google" not in be.identities(uid0):
        P.append("backend: no google identity on the same uid")
    if "מוגן" not in H.text(page, "#ptF22Badge"):
        P.append("badge %r (want מוגן)" % H.text(page, "#ptF22Badge"))
    m = H.text(page, "#ptF22GoogleMail")
    if NOA in H.body(page) or not re.fullmatch(r"noa•••@gmail\.com", m):
        P.append("email not masked / shown in full: %r" % m)
    if "החשבון חובר" not in H.toasts(page):
        P.append("toast %r" % H.toasts(page))
    if any(k in H.url(page) for k in ("access_token", "code=", "error")):
        P.append("URL not clean: " + H.url(page))
    mem = be.member_of(tid, uid0)
    if not mem or mem["role"] != role or members_rows(be) != n0:
        P.append("membership changed")
    calls = [c for c in be.oauth_calls]
    if [c["op"] for c in calls] != ["link"]:
        P.append("OAuth calls %r (C2: link only inside a trip)" % [c["op"] for c in calls])
    elif (calls[0]["options"] or {}).get("redirectTo") != env.server.origin + H.APP:
        P.append("redirectTo %r" % (calls[0]["options"] or {}).get("redirectTo"))
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a02_manager_with_email_adds_google(env):
    be = env.backend
    be.google("dana@example.com")
    tid, dev = H.boot_member(env, role="manager", me="דנה")
    uid = dev.uid()
    u = be.users[uid]
    u.update({"email": "dana@example.com", "email_confirmed_at": "2026-11-01T10:00:00Z", "is_anonymous": False,
              "identities": [H._ident(uid, "email", "dana@example.com")]})
    page = dev.page
    H.h10.tab(page, "more")
    page.wait_for_timeout(900)
    P = []
    if H.vis(page, "#ptEmailRow") or H.vis(page, "#ptLinkEmailRow"):
        P.append("F03 email row still in 'עוד' (C7: it moves into the card)")
    H.open_me(page)
    if not H.vis(page, "#ptF22EmailRow"):
        P.append("email row not in the card")
    press_google(page, "#ptF22Google")
    H.after_return(dev)
    H.in_trip(dev)
    if not H.wait_vis(page, "#ptF22GoogleRow", 10) or not H.vis(page, "#ptF22EmailRow"):
        P.append("both rows (Google + email) not shown")
    if sorted(be.identities(uid)) != ["email", "google"] or dev.uid() != uid:
        P.append("identities %r / uid changed" % be.identities(uid))
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a02_pkce_code_return(env):
    """C3: a ?code= return (PKCE) is exchanged and removed from the URL."""
    be = env.backend
    be.google(NOA)
    be.oauth_shape = "code"
    tid, dev = H.boot_member(env)
    uid = dev.uid()
    H.open_me(dev.page)
    press_google(dev.page, "#ptF22Google")
    H.after_return(dev)
    H.in_trip(dev)
    P = []
    if not be.ops("auth.exchangeCode"):
        P.append("exchangeCodeForSession not called")
    if "code=" in H.url(dev.page):
        P.append("?code= left in the URL")
    if not H.wait_vis(dev.page, "#ptF22GoogleRow", 10) or dev.uid() != uid:
        P.append("not linked / uid changed")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 3 · 5 · gate sign-in (new phone)
# =====================================================================================================
@pytest.mark.parametrize("trips", [1, 2])
def test_a03_gate_google_enters_trip(env, trips):
    be = env.backend
    uid, tids = be.manager_account("dana@example.com", trips=trips)
    be.users[uid]["identities"] = [H._ident(uid, "email", "dana@example.com")]
    be.google("dana@example.com")
    dev = H.gate(env)
    page = dev.page
    P = []
    g = H.text(page, "#ptGate")
    for w in ("ברוכים הבאים", "כבר בטיול? כניסה עם החשבון", "המשך עם Google", "קוד למייל", "בלי חשבון", "מדיניות פרטיות"):
        if w not in g:
            P.append("gate lacks %r" % w)
    if g.find("כבר בטיול") > g.find("בלי חשבון"):
        P.append("account card is not above 'בלי חשבון'")
    n0 = members_rows(be)
    press_google(page, "#ptF22GateGoogle")
    H.after_return(dev)
    if [c["op"] for c in be.oauth_calls] != ["signin"]:
        P.append("OAuth calls %r (C2: signInWithOAuth on the gate)" % [c["op"] for c in be.oauth_calls])
    if trips == 1 and not H.vis(page, "#ptF22Screen") and H.in_trip(dev, 1):
        w = ""     # 1 trip: the welcome screen already moved on into the trip (1.8 s)
    else:
        if not H.wait_vis(page, "#ptF22Screen", 10):
            pytest.fail("welcome screen not shown: %r" % H.body(page)[:200])
        w = H.text(page, "#ptF22Screen")
    if w:
        if "שלום דנה" not in w or "d" not in H.text(page, "#ptF22WelMail") or "dana@example.com" in w:
            P.append("welcome header %r" % w[:120])
        if "מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים" not in w:
            P.append("one-time line missing")
    if trips == 2:
        if page.locator("#ptF22Screen [data-pt22-trip]").count() != 2:
            P.append("2 trips: list of 2 not shown")
        page.locator("#ptF22Screen [data-pt22-trip]").nth(1).click()
    if not H.in_trip(dev, 20):
        P.append("did not enter the trip")
    if dev.uid() != uid:
        P.append("signed in as %s, want the existing user %s" % (dev.uid(), uid))
    if members_rows(be) != n0:
        P.append("new trip_members row created")
    if "google" not in be.identities(uid):
        P.append("S1 auto-link not modelled / not used")
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a05_no_trips_screen_and_sign_out(env):
    be = env.backend
    be.google(YOAV)
    dev = H.gate(env)
    page = dev.page
    press_google(page, "#ptF22GateGoogle")
    H.after_return(dev)
    P = []
    if not H.wait_vis(page, "#ptF22Screen", 10) or "החשבון הזה עוד לא בטיול" not in H.text(page, "#ptF22Screen"):
        pytest.fail("NoTrips screen not shown: %r" % H.body(page)[:200])
    t = H.text(page, "#ptF22Screen")
    for w in ("לנסות חשבון אחר", "פתיחת קישור ההצטרפות", "בקשה לפתיחת טיול חדש", "יציאה מהחשבון", "yoa•••@gmail.com"):
        if w not in t:
            P.append("NoTrips lacks %r" % w)
    if YOAV in t:
        P.append("full email shown")
    page.locator("#ptF22SignOut").click()
    if f20.wait_state(page, "nc", 20) != "nc":
        P.append("sign out did not return to the gate")
    elif not H.vis(page, "#ptF22GateGoogle"):
        P.append("clean gate without the account card")
    if dev.uid() and be.users.get(dev.uid(), {}).get("email") == YOAV:
        P.append("still signed in as the Google user")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 4 · conflict
# =====================================================================================================
def test_a04_conflict_sheet_nothing_changes(env):
    be = env.backend
    other = be.email_account(YOAV, google=True)
    be.oauth_pick = YOAV
    tid, dev = H.boot_member(env)
    page = dev.page
    uid = dev.uid()
    H.open_me(page)
    press_google(page, "#ptF22Google")
    H.after_return(dev)
    H.in_trip(dev)
    P = []
    if not H.wait_vis(page, "#ptF22Conflict", 10):
        pytest.fail("conflict sheet not shown: %r" % H.body(page)[:200])
    t = H.text(page, "#ptF22Conflict")
    for w in ("החשבון הזה כבר שייך למישהו אחר באפליקציה", "לא שינינו כלום", "נועה", "בחירת חשבון אחר", "סגירה"):
        if w not in t:
            P.append("conflict sheet lacks %r" % w)
    if dev.uid() != uid or be.identities(uid) != [] or be.identities(other) != ["email", "google"]:
        P.append("identities / uid changed")
    if "error" in H.url(page):
        P.append("URL not clean")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 6 · invites
# =====================================================================================================
def test_a06_invite_google_same_email_wizard(env):
    be = env.backend
    iid, token = be.add_invite("dana@example.com", "יפן 2027", sent_days_ago=0, expires_in_days=7)
    be.google("dana@example.com")
    H.serve(env, "on", invite="on")
    dev = env.new_device("I")
    page = dev.page
    page.goto(env.server.origin + H.ROOT + "invite/#invite=" + token, wait_until="domcontentloaded")
    P = []
    if not H.wait_vis(page, "#ptF22InvGoogle", 10):
        pytest.fail("/invite/: no Google button: %r" % H.body(page)[:200])
    page.locator("#ptF22InvGoogle").click()
    page.wait_for_timeout(1500)
    H.after_return(dev)
    if not H.wait(lambda: H.vis(page, "#ptWizard") and "פרטי הטיול" in H.text(page, "#ptWizard"), 15, page):
        P.append("wizard step 1 not reached: %r" % H.body(page)[:200])
    elif "יפן 2027" not in page.evaluate("()=>document.getElementById('ptWzName')&&document.getElementById('ptWzName').value||''"):
        P.append("wizard not prefilled from the invite")
    if not be.ct("lookup"):
        P.append("create-trip lookup not called")
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a06_invite_google_other_email(env):
    be = env.backend
    iid, token = be.add_invite("dana@example.com", "יפן 2027", sent_days_ago=0, expires_in_days=7)
    be.google(YOAV)
    H.serve(env, "on", invite="on")
    dev = env.new_device("I")
    page = dev.page
    page.goto(env.server.origin + H.ROOT + "invite/#invite=" + token, wait_until="domcontentloaded")
    assert H.wait_vis(page, "#ptF22InvGoogle", 10)
    page.locator("#ptF22InvGoogle").click()
    page.wait_for_timeout(1500)
    H.after_return(dev)
    P = []
    if not H.wait(lambda: "לא מצאנו הזמנה פעילה למייל הזה" in H.body(page), 12, page):
        P.append("other-email message not shown: %r" % H.body(page)[:200])
    if be.ct("create") or be.trips_created:
        P.append("something was created")
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a06_invite_off_unchanged(env):
    """C13: /invite/ with ACCOUNT_FEATURE='off' has no Google button (same valid card as alpha.10)."""
    be = env.backend
    iid, token = be.add_invite("dana@example.com", "יפן 2027", sent_days_ago=0, expires_in_days=7)
    H.serve(env, "on", invite="off")
    dev = env.new_device("I")
    dev.page.goto(env.server.origin + H.ROOT + "invite/#invite=" + token, wait_until="domcontentloaded")
    assert H.wait(lambda: "ההזמנה שלך אומתה" in H.body(dev.page), 10, dev.page)
    assert "Google" not in H.body(dev.page)


def test_a06_wizard_email_step_google(env):
    """C10: the F04 email step ("כניסה עם המייל" from the gate) shows "המשך עם Google" under "שליחת קוד"."""
    dev = H.gate(env)
    page = dev.page
    page.locator("#ptGateInviteBtn").click()
    P = []
    if not H.wait_vis(page, "#ptWzSend", 10):
        pytest.fail("email step not opened")
    if not H.wait_vis(page, "#ptF22WzGoogle", 5):
        P.append("no Google button on the email step")
    else:
        y = page.evaluate("()=>[document.getElementById('ptWzSend').getBoundingClientRect().top,document.getElementById('ptF22WzGoogle').getBoundingClientRect().top]")
        if not y[1] > y[0]:
            P.append("Google is not under 'שליחת קוד'")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 7 · unlink
# =====================================================================================================
def test_a07_unlink_with_two_identities(env):
    be = env.backend
    tid, dev = H.boot_member(env, role="manager", me="דנה")
    uid = dev.uid()
    be.users[uid].update({"email": "dana@example.com", "email_confirmed_at": "2026-11-01T10:00:00Z", "is_anonymous": False,
                          "identities": [H._ident(uid, "email", "dana@example.com"), H._ident(uid, "google", "dana@example.com")]})
    page = dev.page
    H.open_me(page)
    P = []
    page.locator("#ptF22Unlink").click()
    assert H.wait_vis(page, "#ptF22UnlinkSheet")
    if H.vis(page, "#ptF22UnlinkWarn"):
        P.append("last-identity warning shown with 2 identities")
    page.locator("#ptF22UnlinkGo").click()
    page.wait_for_timeout(1200)
    if H.vis(page, "#ptF22GoogleRow"):
        P.append("Google row still shown")
    if be.identities(uid) != ["email"] or dev.uid() != uid or not H.in_trip(dev, 3):
        P.append("identities %r / session or trip changed" % be.identities(uid))
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_a07_unlink_last_identity_refused(env):
    be = env.backend
    be.google(NOA)
    tid, dev = H.boot_member(env)
    page = dev.page
    uid = dev.uid()
    H.open_me(page)
    press_google(page, "#ptF22Google")
    H.after_return(dev)
    H.in_trip(dev)
    assert H.wait_vis(page, "#ptF22Unlink", 10)
    page.locator("#ptF22Unlink").click()
    P = []
    if not H.wait_vis(page, "#ptF22UnlinkWarn"):
        P.append("D12 warning missing")
    elif "אישור מנהל" not in H.text(page, "#ptF22UnlinkWarn"):
        P.append("warning text %r" % H.text(page, "#ptF22UnlinkWarn"))
    page.locator("#ptF22UnlinkGo").click()
    if not H.wait_vis(page, "#ptF22UnlinkRefused"):
        P.append("refusal explanation not shown")
    elif "single_identity_not_deletable" not in H.text(page, "#ptF22UnlinkRefused"):
        P.append("error code not shown for R1")
    d = page.evaluate("()=>window.__ptF22.diag()")
    if (d.get("lastUnlinkError") or {}).get("code") != "single_identity_not_deletable":
        P.append("diag %r" % d)
    if be.identities(uid) != ["google"] or dev.uid() != uid:
        P.append("something changed")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 8 · cancel / error
# =====================================================================================================
@pytest.mark.parametrize("where,kind", [("me", "cancel"), ("me", "error"), ("gate", "cancel"), ("gate", "error")])
def test_a08_cancel_or_error(env, where, kind):
    be = env.backend
    be.google(NOA)
    be.oauth_next = kind
    if where == "me":
        tid, dev = H.boot_member(env)
        uid = dev.uid()
        H.open_me(dev.page)
        press_google(dev.page, "#ptF22Google")
    else:
        dev = H.gate(env)
        uid = dev.uid()
        press_google(dev.page, "#ptF22GateGoogle")
    H.after_return(dev)
    page = dev.page
    P = []
    want = "הכניסה בוטלה" if kind == "cancel" else "הכניסה נכשלה"
    if not H.wait(lambda: want in H.toasts(page), 10, page):
        P.append("toast %r (want %r)" % (H.toasts(page), want))
    if where == "me" and not (H.in_trip(dev, 5) and H.vis(page, "#ptF22Me")):
        P.append("not back on 'אני'")
    if where == "gate" and f20.wait_state(page, "nc", 5) != "nc":
        P.append("not back on the gate")
    if any(k in H.url(page) for k in ("error", "access_token", "code=")):
        P.append("URL not clean: " + H.url(page))
    if dev.uid() != uid or (uid and be.identities(uid)):
        P.append("identity changed")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 9 · masked address only on the owner's device
# =====================================================================================================
def test_a09_email_not_visible_to_others(env):
    be = env.backend
    be.google(NOA)
    tid, a = H.boot_member(env, role="editor", me="נועה", name="A")
    H.open_me(a.page)
    press_google(a.page, "#ptF22Google")
    H.after_return(a)
    H.in_trip(a)
    be.links.append({"trip_id": tid, "role": "manager", "display_name": "דנה"})
    b = env.new_device("B")
    b.seed_ls({H.CACHE_KEY: json.dumps({"trip_id": tid, "role": "manager"})})
    assert H.h10.reboot(b) == "app"
    P = []
    for tab in ("home", "more"):
        H.h10.tab(b.page, tab)
        b.page.wait_for_timeout(700)
        html = b.page.content()
        if "noa.family" in html.lower() or "noa•••" in html.lower():
            P.append("other member's DOM contains the address (%s)" % tab)
    leaks = [c for c in be.calls if c["device"] == "B" and "noa" in json.dumps(c.get("result") or {}).lower()
             and c.get("op") == "query"]
    if leaks:
        P.append("API responses to B contain the address: %r" % [c["msg"].get("req", {}).get("table") for c in leaks])
    writes = [c for c in be.calls if c.get("op") == "query" and (c["msg"].get("req") or {}).get("action") != "select"
              and "noa" in json.dumps(c["msg"]).lower()]
    if writes:
        P.append("the address was written to a table")
    assert not P, "\n".join(P)


# =====================================================================================================
# 10 · iPhone standalone (C9)
# =====================================================================================================
def test_a10_iphone_standalone_hides_google(env):
    dev = H.gate(env, ua=f05.IPHONE_UA, standalone=True)
    P = []
    if H.vis(dev.page, "#ptF22GateGoogle"):
        P.append("Google shown on the gate in iPhone standalone")
    if "באייפון: כניסה עם קוד למייל" not in H.text(dev.page, "#ptGate"):
        P.append("iPhone hint missing on the gate")
    if not H.vis(dev.page, "#ptGateInviteBtn"):
        P.append("'קוד למייל' missing")
    env.server.reset()
    H.serve(env, "on")
    tid, m = H.boot_member(env, name="M", ua=f05.IPHONE_UA, standalone=True)
    H.open_me(m.page)
    if H.vis(m.page, "#ptF22Google") or "באייפון: כניסה עם קוד למייל" not in H.text(m.page, "#ptF22Me"):
        P.append("'אני': Google shown / hint missing")
    s = H.gate(env, name="S", ua=f05.IPHONE_UA, standalone=False)
    if not H.vis(s.page, "#ptF22GateGoogle"):
        P.append("Safari tab: Google not shown")
    assert not P, "\n".join(P)


# =====================================================================================================
# 12 · 390 px + offline
# =====================================================================================================
def _lay(page, sel, P):
    L = H.layout(page, sel)
    if L is None:
        P.append("%s not found" % sel)
        return
    if L["scroll"] > 1 or L["over"]:
        P.append("%s: horizontal overflow (%d / %d)" % (sel, L["scroll"], L["over"]))
    if L["small"]:
        P.append("%s: touch < 44px %r" % (sel, L["small"][:6]))
    if L["dir"] != "rtl":
        P.append("%s not RTL" % sel)


def test_a12_layout_390(env):
    be = env.backend
    be.google(YOAV)
    P = []
    g = H.gate(env)
    _lay(g.page, "#ptGate", P)
    press_google(g.page, "#ptF22GateGoogle")
    H.after_return(g)
    if H.wait_vis(g.page, "#ptF22Screen", 10):
        _lay(g.page, "#ptF22Screen", P)
    tid, dev = H.boot_member(env, name="M")
    H.open_me(dev.page)
    _lay(dev.page, "#ptF22Me", P)
    assert not P, "\n".join(P)


def test_a12_offline_buttons_disabled(env):
    tid, dev = H.boot_member(env)
    page = dev.page
    H.open_me(page)
    H.h10.go_offline(env, dev, True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    page.wait_for_timeout(400)
    P = []
    if not page.evaluate("()=>document.getElementById('ptF22Google').disabled"):
        P.append("Google not disabled offline")
    if not H.vis(page, "#ptF22Off"):
        P.append("offline line missing")
    H.h10.go_offline(env, dev, False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    page.wait_for_timeout(600)
    if page.evaluate("()=>document.getElementById('ptF22Google').disabled"):
        P.append("Google still disabled online")
    assert not P + errs(dev), "\n".join(P)


# =====================================================================================================
# 13 · static
# =====================================================================================================
STATIC = ["protected:" + n for n in f02.PROTECTED] + ["versions", "change_comments", "flag_beta", "node_check",
                                                     "legal_pages", "no_secrets", "no_new_dup_ids", "join_unchanged"]


def _scripts(src):
    return re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", src, re.S)


@pytest.mark.parametrize("check", STATIC)
def test_a13_static(check, tmp_path):
    html, inv = H.app_html(), H.invite_html()
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = f20._extract(f02.qa_refs.v2152_html(), [name], tmp_path)["found"][name]
        b = f20._extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1 and b and a[0] in b, "%s not byte-identical to v2.15.2" % name
    elif check == "versions":
        assert re.search(r"const APP_VERSION='%s'" % re.escape(VERSION), html)
        assert re.search(r"const PT_VERSION='%s'" % re.escape(VERSION), html)
        assert "version %s" % VERSION in inv
        for p in ("privacy", "terms"):
            assert "version %s" % VERSION in (H.REPO_DIR / p / "index.html").read_text(encoding="utf-8")
    elif check == "change_comments":
        for src, label in ((html, "app"), (inv, "invite")):
            tags = re.findall(r"CHANGE 2026-11-07 F22A-[A-Z0-9-]+[^\n]*", src)
            assert tags and any(re.search(r"alpha\.10|was |no previous version", t) for t in tags), label
    elif check == "flag_beta":
        assert H.flag_value(html) == "beta" and H.flag_value(inv) == "beta"
    elif check == "node_check":
        bad = []
        for label, f in (("app", H.APP_DIR / "index.html"), ("invite", H.INVITE_DIR / "index.html")):
            dd = tmp_path / label
            dd.mkdir()
            r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(f)], env={**os.environ, "DUMP_DIR": str(dd)})
            assert r.returncode == 0, r.stderr
            files = sorted(list(dd.glob("*.js")) + list(dd.glob("*.mjs")))
            assert files, label
            bad += ["%s/%s" % (label, x.name) for x in files if f02.node(["--check", str(x)]).returncode]
        assert not bad, bad
    elif check == "legal_pages":
        for p in ("privacy", "terms"):
            s = (H.REPO_DIR / p / "index.html").read_text(encoding="utf-8")
            assert "<script" not in s and "orsela@gmail.com" in s and 'lang="en"' in s and "טיוטה לאישור" in s
            assert not re.search(r"""(src|href)=["']https?://""", s), "external request in /%s/" % p
    elif check == "no_secrets":
        for s in (html, inv):
            assert not re.search(r"GOCSPX-|sb_secret_|service_role", s)
    elif check == "no_new_dup_ids":
        import collections

        def dups(h):
            c = collections.Counter(re.findall(r"""\bid=["']([A-Za-z][\w:-]*)["']""", h))
            return {k for k, v in c.items() if v > 1}
        strip = lambda h: re.sub(r"<script\b.*?</script>", "", h, flags=re.S)   # screens are JS templates, one in the DOM at a time
        new = dups(strip(html)) - dups(strip(H.base_file()))
        assert not new, sorted(new)
    elif check == "join_unchanged":
        assert (H.REPO_DIR / "join" / "index.html").read_text(encoding="utf-8") == H.base_file("join/index.html")
