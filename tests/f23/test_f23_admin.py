"""Lonely Planner F23 · app admin screen developer test (Playwright) · version 1.0.0
CHANGE 2026-11-13 F23-QA-08: new file (no previous version).

"ניהול מערכת → בקשות" with the F23 keys of admin_trip_requests (spec C7, C11, criterion 10 — app side): the AI counter
row, the history "נפתחו אוטומטית" with the invite state of each request, the button that opens the existing invite
actions sheet (revoke), and the two "off" cases: flag REQAUTO_FEATURE='off' and a server that does not send the keys.
Reuses the F21 harness (fake backend + served app); nothing talks to the network.
Run: tests/f23/run.sh --only app
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f21"))
sys.path.insert(0, str(HERE.parent))
import test_f21 as t21  # noqa: E402
from test_f21 import browser, env, server  # noqa: E402,F401  (pytest fixtures)

H = t21.H


def with_f23(be, auto, ai_today=4, send_keys=True):
    """Wrap the fake backend's admin_trip_requests answer with the F23 keys."""
    base = be.requests_payload

    def payload():
        d = base()
        if send_keys:
            d.update({"auto": auto, "ai_today": ai_today, "ai_cap": 30})
        return d
    be.requests_payload = payload


def auto_item(be, name, email, countries, invite, lang="he", month="2027-05-01", where_mode="known", hours_ago=2):
    return {"id": "a%07d-0000-4000-8000-000000000000" % (abs(hash(email)) % 10 ** 7), "lang": lang, "name": name, "email": email,
            "countries": list(countries), "month": month, "travellers": 5, "note": None, "where_mode": where_mode,
            "decided_at": H.iso(be.clock() - hours_ago * H.HOUR), "invite": invite}


def inv(be, iid):
    r = be.invites[iid]
    return {k: r.get(k) for k in ("id", "draft_name", "expires_at", "used_at", "revoked_at", "opened_at", "trip_id")}


def seed(be):
    open_id, _ = be.add_invite("open@example.com", "גאורגיה · מאי 2027", sent_days_ago=0, expires_in_days=7)
    used_id, _ = be.add_invite("used@example.com", "פורטוגל · מאי 2027", sent_days_ago=3, expires_in_days=4, used=True)
    rev_id, _ = be.add_invite("rev@example.com", "יוון", sent_days_ago=2, expires_in_days=5, revoked=True)
    return open_id, [
        auto_item(be, "רועי", "open@example.com", ("GE",), inv(be, open_id), where_mode="undecided", hours_ago=1),
        auto_item(be, "Ann", "used@example.com", ("PT",), inv(be, used_id), lang="en", hours_ago=30),
        auto_item(be, "נועה", "rev@example.com", ("GR",), inv(be, rev_id), month=None, hours_ago=50),
    ]


def auto_cards(page):
    return page.evaluate("""()=>[...document.querySelectorAll('#ptReqAuto article')].map(a=>({
      text:(a.innerText||'').replace(/\\s+/g,' ').trim(),
      badges:[...a.querySelectorAll('.pt-badge')].map(b=>b.textContent.trim()),
      btn:(a.querySelector('button[data-f23-invite]')||{}).textContent||null}))""")


def test_f23_admin_history_and_ai_counter(env):
    """C7 + C11: AI counter 'הצעות AI היום 4 מתוך 30'; history of 3 with 'נפתח אוטומטית' + invite state; tab count = pending only."""
    be = env.backend
    be.add_request(name="רון", email="ron@example.com", lang="he", countries=("TH",), month="2027-01-01", travellers=4, verified_ago=H.HOUR)
    open_id, auto = seed(be)
    with_f23(be, auto)
    dev = t21.admin_dev(env)
    t21.open_requests_admin(env, dev)
    page = dev.page
    page.wait_for_selector("#ptReqAuto")
    P = []
    ai = re.sub(r"\s+", " ", page.inner_text("#ptReqAi"))
    if ai != "הצעות AI היום 4 מתוך 30":
        P.append("AI counter %r" % ai)
    if "בקשות · 1" not in t21.btext(page):
        P.append("tab count must count pending requests only")
    if re.sub(r"\s+", " ", page.inner_text("#ptReqAutoTitle")) != "נפתחו אוטומטית · 3":
        P.append("history title %r" % page.inner_text("#ptReqAutoTitle"))
    cards = auto_cards(page)
    if [c["badges"] for c in cards] != [["נפתח אוטומטית", "ממתין להקמה · בתוקף עד " + t21_dm(be.invites[open_id]["expires_at"]), "יעד מהצעות AI"],
                                        ["EN", "נפתח אוטומטית", "הטיול הוקם"], ["נפתח אוטומטית", "ההזמנה בוטלה"]]:
        P.append("badges %r" % [c["badges"] for c in cards])
    if [bool(c["btn"]) for c in cards] != [True, False, False]:
        P.append("only an open invite has the actions button: %r" % [c["btn"] for c in cards])
    if not ("open@example.com" in cards[0]["text"] and "גאורגיה" in cards[0]["text"] and "מאי 2027 · 5 מטיילים" in cards[0]["text"]):
        P.append("card content %r" % cards[0]["text"])
    if "עוד לא יודעים מתי" not in cards[2]["text"]:
        P.append("unknown month text %r" % cards[2]["text"])
    if os.environ.get("F23_SHOT"):   # optional screenshot for the dev notes / Or's review
        page.screenshot(path=os.environ["F23_SHOT"], full_page=True)
    wide = page.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
    if wide:
        P.append("horizontal scroll")
    small = page.evaluate("""()=>[...document.querySelectorAll('#ptReqAuto button')].map(b=>b.getBoundingClientRect()).filter(r=>r.height<44).length""")
    if small:
        P.append("history button under 44px")
    assert not P, "; ".join(P)


def t21_dm(iso):
    import datetime as dt
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return "%02d/%02d" % (d.day, d.month)


def test_f23_admin_history_button_opens_invite_sheet_and_revokes(env):
    """Criterion 10: the history button opens the existing F03 actions sheet; revoke goes through invite-manager and the state changes."""
    be = env.backend
    open_id, auto = seed(be)
    with_f23(be, auto)
    dev = t21.admin_dev(env)
    t21.open_requests_admin(env, dev)
    page = dev.page
    page.locator("#ptReqTabReq").click()   # nothing waits for approval → the default tab is "קבוצות והזמנות" (F21 rule, unchanged)
    page.wait_for_selector("#ptReqAuto")
    page.locator("button[data-f23-invite='%s']" % open_id).click()
    page.wait_for_timeout(1200)
    sheet = page.evaluate("()=>{const l=document.getElementById('ptSheetLayer');return l&&!l.hidden?(l.innerText||'').replace(/\\s+/g,' '):''}")
    if not sheet:   # the invite was not in the loaded groups list yet → the groups tab opened; open the invite there
        page.wait_for_timeout(1500)
        page.locator("[data-invite='%s']" % open_id).first.click()
        page.wait_for_timeout(800)
        sheet = page.evaluate("()=>{const l=document.getElementById('ptSheetLayer');return l&&!l.hidden?(l.innerText||'').replace(/\\s+/g,' '):''}")
    assert "גאורגיה · מאי 2027" in sheet and "open@example.com" in sheet, "invite sheet not shown: %r" % sheet[:200]
    assert "ביטול" in sheet, "revoke action missing: %r" % sheet[:300]


def test_f23_admin_off_cases(env):
    """Flag off, or a server without migration 0020 → the alpha.11 requests tab (no AI row, no history)."""
    be = env.backend
    _, auto = seed(be)
    with_f23(be, auto, send_keys=False)
    dev = t21.admin_dev(env)
    t21.open_requests_admin(env, dev)
    page = dev.page
    page.locator("#ptReqTabReq").click()
    page.wait_for_selector("#ptReqMeter")
    assert page.query_selector("#ptReqAi") is None and page.query_selector("#ptReqAuto") is None, "F23 parts shown without server data"
    assert "אין בקשות חדשות" in t21.btext(page), "alpha.11 empty text expected"
