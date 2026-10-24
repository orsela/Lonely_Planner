"""Lonely Planner F06 QA · Playwright black-box suite · version 1.0.0
CHANGE 2026-10-22 F06-QA-04: first version (no previous version).

Black-box browser tests for docs/F06_spec.md §1, §3.3–§3.4 and §4 criteria 1–3, 5, 8, 10, 12–14, 18–19 (+ client side of 9, 11,
16). Contract: the spec ONLY — F06 element ids are not in the spec, so elements are found by role, visible Hebrew text and the
aria-labels the spec names ("פעולות על <name>", aria-pressed on the role segment). alpha.6 ids that already exist on main
(#newWaypoint, #wpName, #saveWaypoint, #mgmtUsers, #ptF05Pending, #lpJoin data-screen …) are used as before. Places where
only an id from the F06 dev notes can make a selector reliable are marked `TODO(dev-notes id)`.

Harness: tests/f06/harness.py (F05 harness + in-memory manage-members, D2 join-trip, tripname trigger). 390×844 Chromium,
he-IL, Asia/Jerusalem, clock installed at 2026-10-12 06:00Z (09:00 local).

Env: APP_DIR / JOIN_DIR / REPO_DIR, QA_HEADFUL=1 to watch.
"""
import datetime as dt
import json
import os
import re
import time
import uuid

import pytest

import harness as H
from harness import f02, f03, f04, f20, norm, btext, has, wait_has, layout_problems, is_vis, wait_until

from playwright.sync_api import Error as PWError

TXT = {
    # 1.1 "עוד"
    "members_row": "חברים וקישור",
    "members_sub": "{n} חברים · תפקידים · קישור הצטרפות",
    "badge": "{p} ממתינים",
    "f04_row": "קישור הצטרפות לקבוצה",
    "me_section": "אני בטיול",
    "leave_row": "יציאה מהטיול",
    "leave_sub_only": "את/ה המנהל/ת היחיד/ה – קודם ממנים מנהל",
    # 1.2 members screen
    "subtitle": "{trip} · מנהלים בלבד",
    "link_help": "מי שפותח – ממתין לאישורך",
    "wa": "שליחה בווטסאפ",
    "copy": "העתקה",
    "reset": "איפוס",
    "pending_short": "{p} ממתינים לאישור",
    "to_home": "לאישור בבית",
    "count": "חברים · {n}",
    "mgrs": "{m} מנהלים",
    "one_mgr": "מנהל/ת אחד/ת",
    "me_tag": "(את/ה)",
    "seen_today": "פעיל/ה היום",
    "seen_yday": "פעיל/ה אתמול",
    "seen_days": "לפני {d} ימים",
    "seen_never": "עוד לא נכנס/ה",
    "actions_aria": "פעולות על {name}",
    "footnote": "שינוי תפקיד או הסרה נכנסים לתוקף מיד, גם בטלפון של החבר.",
    "offline": "אין חיבור – אפשר לשנות כשהרשת תחזור.",
    # 1.3 sheet
    "joined": "הצטרף/ה ב-{d}",
    "save": "שמירה",
    "remove_row": "הסרה מהטיול",
    "t_role": "{name} עכשיו {role}",
    "taken": 'יש כבר "{n}" בטיול.',
    # 1.4
    "remove_q": "להסיר את {name} מהטיול?",
    "remove_yes": "הסרה",
    "cancel": "ביטול",
    "t_removed": "{name} הוסר/ה מהטיול",
    # 1.5
    "rotate_q": "לאפס את קישור ההצטרפות?",
    "rotate_yes": "איפוס הקישור",
    "t_rotated": "נוצר קישור חדש",
    # 1.6
    "only_box": "את/ה המנהל/ת היחיד/ה בטיול",
    "appoint": "למנות מנהל אחר",
    "sysadmin": "אין בטיול חברים אחרים? פונים למנהל המערכת.",
    # 1.7
    "leave_q": 'לצאת מ"{trip}"?',
    "leave_yes": "יציאה",
    # 1.8
    "changed": "ההרשאה שלך השתנתה ל",
    "changed_by": "שינה/תה את התפקיד שלך.",
    "viewer_line": "אפשר לראות הכול, אבל לא לשנות.",
    "got_it": "הבנתי",
    "removed_title": 'כבר אינך חבר/ה ב"{trip}"',
    "removed_text": "מנהל הטיול הסיר אותך. הנתונים של הטיול נמחקו מהטלפון הזה.",
    "ask_again": "בקשה להצטרף שוב",
    "ask_link": "בקשו מהמנהל את קישור ההצטרפות",
    "my_trips": "הטיולים שלי",
    "dropped_re": r"(\d+)\s*שינויים[^\n]*לא נשמרו",
    # D10
    "viewer_toast": "צופה בלבד – השינוי לא נשמר",
    "viewer_tag": "צופה",
    # F05 (unchanged)
    "f05_removed": "הוסרת מהטיול",
}
ROLE_WORD = {"viewer": "צופה", "editor": "עורך", "manager": "מנהל"}
ROLE_RE = {"viewer": r"צופה", "editor": r"עורכ(?:ת|/ת)?|עורך(?:/ת)?", "manager": r"מנהל(?:ת|/ת)?"}
TRIP = "יפן 2027"


# =====================================================================================================
# Fixtures
# =====================================================================================================
@pytest.fixture(scope="session")
def server():
    s = H.f05.F05Server()
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
def new_trip(env, others=(("אבי", "manager"), ("Editor Q", "editor"), ("נועה", "viewer")), name=TRIP, **kw):
    """A trip without the device's own member (the device is attached by boot())."""
    return env.backend.trip(name=name, managers=(), others=others, **kw)


def boot(env, links, dev_name="M", pre_ls=None, want="app", **dev_kw):
    """links: [(trip_id, role, display_name)] attached to the device's anonymous identity at sign-in (first = joined earliest)."""
    be = env.backend
    be.links = [{"trip_id": t, "role": r, "display_name": n, "joined_at": H.iso(be.tnow() - (90 - i) * H.DAY)}
                for i, (t, r, n) in enumerate(links)]
    dev = env.new_device(dev_name, **dev_kw)
    if pre_ls:
        dev.seed_ls(pre_ls)
    dev.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")
    st = H.wait_app_state(dev.page, want, 30)
    be.links = []
    assert st == want, "boot: state %r (want %r), text=%r" % (st, want, btext(dev.page)[:200])
    dev.page.wait_for_timeout(800)
    H.watch(dev.page, TXT["viewer_toast"], TXT["changed"], TXT["t_rotated"])
    return dev


def boot_one(env, role="manager", me="דנה", others=None, **kw):
    tid, code = new_trip(env, **({"others": others} if others is not None else {}))
    dev = boot(env, [(tid, role, me)], **kw)
    return tid, code, dev


def my_row(env, dev, tid):
    return env.backend.member_of(tid, env.backend.uid_of(dev.name))


def mm(env, action=None, device=None):
    return [c for c in env.backend.mm_of(action, device) if c["action"] != "touch" or action == "touch"]


def open_more(page):
    f03.open_more(page)
    page.wait_for_timeout(300)


def open_members(page, trip=TRIP):
    open_more(page)
    f03.click_text(page, TXT["members_row"])
    assert wait_has(page, TXT["subtitle"].format(trip=trip), 8), "members screen did not open (text=%r)" % btext(page)[:300]
    page.wait_for_timeout(500)


def action_buttons(page):
    """Names on the "⋯" buttons in DOM (= display) order: aria-label "פעולות על <name>"."""
    return page.evaluate("""()=>[...document.querySelectorAll('[aria-label^="פעולות על "]')].filter(e=>{const r=e.getBoundingClientRect();
      return r.width>0&&r.height>0}).map(e=>e.getAttribute('aria-label').replace(/^פעולות על /,'').trim())""")


def tap_actions(page, name):
    loc = page.locator('[aria-label^="%s"]' % TXT["actions_aria"].format(name=name)).filter(visible=True)
    assert loc.count(), "no visible '%s' button (have %r)" % (TXT["actions_aria"].format(name=name), action_buttons(page))
    loc.first.click()
    page.wait_for_timeout(600)


def role_buttons(page):
    """The role segment (aria-pressed) in the open sheet. TODO(dev-notes id): scope to the sheet container once its id is known."""
    return page.evaluate("""()=>[...document.querySelectorAll('[aria-pressed]')].filter(e=>{const r=e.getBoundingClientRect();
      return r.width>0&&r.height>0&&/^(צופה|עורכ|עורך|מנהל)/.test((e.innerText||'').trim())}).map(e=>({t:(e.innerText||'').trim(),
      p:e.getAttribute('aria-pressed'),d:!!e.disabled||e.getAttribute('aria-disabled')==='true'}))""")


def tap_role(page, role):
    loc = page.locator("[aria-pressed]").filter(visible=True).filter(has_text=re.compile("^(%s)" % ROLE_RE[role]))
    assert loc.count(), "role button %s not found (%r)" % (role, role_buttons(page))
    loc.first.click()
    page.wait_for_timeout(700)


def click_exact(page, text):
    f03.click_text(page, text, exact=True)
    page.wait_for_timeout(400)


def seen(page, text):
    return has(page, text) or H.seen_count(page, text) > 0


def is_removed_screen(page, trip=TRIP):
    return has(page, TXT["removed_title"].format(trip=trip))


def chrome(page):
    return f03.chrome_visible(page)


def add_expense_try(page, desc, amount=12):
    try:
        f02.tab(page, "budget")
        page.evaluate("()=>{const d=document.getElementById('addExpenseDetails');if(d)d.open=true}")
        f02.click(page, '#expenseCurRow [data-cur="ILS"]')
        page.fill("#expenseDescription", desc)
        page.fill("#expenseAmount", str(amount))
        f02.click(page, "#saveExpense")
    except PWError:
        pass
    page.wait_for_timeout(1200)


def add_journal_try(page, text):
    try:
        f02.tab(page, "journal")
        page.fill("#journalText", text)
        f02.click(page, "#saveJournal")
    except PWError:
        pass
    page.wait_for_timeout(1200)


def add_waypoint_try(page, name):
    try:
        f02.tab(page, "route")
        page.evaluate("()=>{const b=document.getElementById('newWaypoint');if(b)b.click()}")
        page.wait_for_timeout(400)
        page.evaluate("()=>{const d=document.getElementById('wpManual');if(d)d.open=true}")
        page.fill("#wpName", name)
        page.fill("#wpLat", "21.0285")
        page.fill("#wpLng", "105.8542")
        f02.click(page, "#saveWaypoint")
    except PWError:
        pass
    page.wait_for_timeout(1200)


def add_checkin_try(page, note):
    """The check-in save path of alpha.6 (ciSave) with a fixed position — the sheet's geolocation UI is not under test."""
    page.evaluate("(n)=>{try{return ciSave({lat:21.0285,lng:105.8542,acc:10},null,n)}catch(e){return String(e)}}", note)
    page.wait_for_timeout(1200)


def kv_writes(env, device, since=0):
    return [c for c in env.backend.queries("trip_kv", ("upsert", "insert", "update", "delete"))[since:] if c["device"] == device]


def text_in_trip_ls(dev, tid, text):
    return [k for k, v in H.ls_trip(dev, tid).items() if text in (v or "")]


def other_state_ok(dev, other_tid):
    """After leaving / removal: the next active trip runs, or the not-connected card (F02/F05) is shown."""
    page = dev.page
    st = H.app_state(page)
    if other_tid:
        return st == "app" and H.running_trip(page) == other_tid
    return st == "nc" or is_vis(page, "#ptF05Transfer") or has(page, "כמעט שם") or has(page, f02.NC_TITLE)


# =====================================================================================================
# 0 · Flag (criterion 1 / §1 "off = alpha.6")
# =====================================================================================================
def test_a01_flag_declared():
    """§1: const MEMBERS_FEATURE='on' in the app next to JOIN_FEATURE, and a top-level const in /join/."""
    html = H.app_html()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    blk = [b for b in blocks if re.search(r"const\s+JOIN_FEATURE\s*=", b)]
    assert blk and re.search(r"""^\s*const\s+MEMBERS_FEATURE\s*=\s*['"]on['"]""", blk[0], re.M), \
        "const MEMBERS_FEATURE='on' not declared in the script that declares JOIN_FEATURE"
    assert re.search(r"""const\s+MEMBERS_FEATURE\s*=\s*['"]on['"]""", H.join_html()), "/join/: const MEMBERS_FEATURE='on' missing"


@pytest.mark.parametrize("role", ["manager", "editor", "viewer"])
def test_a02_flag_off_more_is_alpha6(env, role):
    """C1: MEMBERS_FEATURE='off' → "עוד" as alpha.6: managers see the F04 row "קישור הצטרפות לקבוצה"; nobody sees "חברים
    וקישור" / "אני בטיול" / "יציאה מהטיול"; the "ניהול → משתמשים" row is there; no manage-members call at all (no touch)."""
    H.serve_members_off(env)
    tid, code, dev = boot_one(env, role=role, me="דנה" if role == "manager" else "חבר")
    page, P = dev.page, []
    open_more(page)
    if H.visible(page, TXT["members_row"]) or H.visible(page, TXT["leave_row"]) or H.visible(page, TXT["me_section"]):
        P.append("'off': an F06 row is shown")
    if (role == "manager") != bool(H.visible(page, TXT["f04_row"])):
        P.append("'off': F04 join-link row shown=%s for a %s" % (H.visible(page, TXT["f04_row"]), role))
    if not H.exists(page, "#mgmtUsers"):
        P.append("'off': ניהול → משתמשים row (#mgmtUsers) missing")
    page.wait_for_timeout(1500)
    if env.backend.mm_calls:
        P.append("'off': manage-members called: %r" % [c["action"] for c in env.backend.mm_calls])
    assert not P, "\n".join(P)


def test_a03_flag_off_viewer_write_as_alpha6(env):
    """C1 + D10 'off': no viewer guard — a viewer's expense is written locally, sent, rejected by RLS and kept in the queue
    exactly as alpha.6 (F02 C3); no "צופה בלבד" toast."""
    H.serve_members_off(env)
    tid, code, dev = boot_one(env, role="viewer", me="חבר")
    page = dev.page
    n0 = len(env.backend.queries("trip_kv"))
    add_expense_try(page, "QA F06 off viewer")
    P = []
    if not kv_writes(env, dev.name, n0):
        P.append("'off': the viewer write was not sent (alpha.6 sends it and RLS rejects it)")
    if not text_in_trip_ls(dev, tid, "QA F06 off viewer"):
        P.append("'off': local copy not kept")
    if seen(page, TXT["viewer_toast"]):
        P.append("'off': viewer toast shown")
    assert not P, "\n".join(P)


def test_a04_flag_off_no_membership_watch(env):
    """C1 'off': no membership watch — a member removed on the server is not thrown out on visibilitychange / after 60 s
    (alpha.6 behaviour; the next boot shows the alpha.6 state)."""
    H.serve_members_off(env)
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    env.backend.remove_direct(my_row(env, dev, tid)["id"])
    H.to_background_and_back(dev.page)
    dev.page.clock.run_for(61000)
    dev.page.wait_for_timeout(800)
    assert not is_removed_screen(dev.page), "'off': the F06 removed screen was shown"


def test_a05_flag_off_join_removed_message(env):
    """C1 'off' (/join/): the F05 "removed" branch is kept for flag off. Server emulated as alpha.6 (member_removed) because the
    D2 SQL change is server-side and not flag-controlled (README A-1)."""
    H.serve_members_off(env, app=False, join=True)
    be = env.backend
    be.legacy_removed = True
    tid, code = new_trip(env)
    dev = env.new_device("J")
    dev.page.goto(env.server.origin + H.APP, wait_until="domcontentloaded")   # get an identity on this origin
    H.wait_app_state(dev.page, None, 20)
    uid = be.uid_of("J")
    be.add(tid, "הוסר", status="removed", uid=uid)
    dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    assert wait_has(dev.page, TXT["f05_removed"], 10), "'off': F05 removed message missing (text=%r)" % btext(dev.page)[:200]


# =====================================================================================================
# 1 · "עוד" (criterion 2, §1.1)
# =====================================================================================================
@pytest.mark.parametrize("role", ["manager", "editor", "viewer"])
def test_b01_more_rows_by_role(env, role):
    """C2: managers see "חברים וקישור" with sub "<N> חברים · תפקידים · קישור הצטרפות" (N = active members) and NOT the F04
    row; editors / viewers see neither; everyone sees section "אני בטיול" with "יציאה מהטיול"; "ניהול → משתמשים" hidden."""
    tid, code, dev = boot_one(env, role=role, me="דנה" if role == "manager" else "חבר")
    page, P = dev.page, []
    env.backend.add(tid, "ממתין", status="pending")
    env.backend.add(tid, "הוסר", status="removed")
    open_more(page)
    n = len(env.backend.members(tid, "active"))
    if role == "manager":
        if not H.visible(page, TXT["members_row"]):
            P.append("manager: row %r missing" % TXT["members_row"])
        if not has(page, TXT["members_sub"].format(n=n)):
            P.append("manager: sub %r missing" % TXT["members_sub"].format(n=n))
        if H.visible(page, TXT["f04_row"]):
            P.append("manager: the replaced F04 row is still shown")
    elif H.visible(page, TXT["members_row"]):
        P.append("%s sees %r" % (role, TXT["members_row"]))
    if not (H.visible(page, TXT["me_section"]) and H.visible(page, TXT["leave_row"])):
        P.append("%s: 'אני בטיול' / 'יציאה מהטיול' missing" % role)
    if H.is_vis(page, "#mgmtUsers"):
        P.append("'ניהול → משתמשים' (#mgmtUsers) visible in cloud mode")
    page.evaluate("()=>{try{switchPanel('management')}catch(e){}}")
    page.wait_for_timeout(400)
    if H.is_vis(page, "#mgmtUsers"):
        P.append("#mgmtUsers visible on the management panel in cloud mode")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("p", [0, 2])
def test_b02_pending_badge(env, p):
    """C2 + §1.1: amber badge "<P> ממתינים" only when P>0."""
    tid, code, dev = boot_one(env)
    for i in range(p):
        env.backend.add(tid, "ממתין%d" % i, status="pending")
    dev.page.reload(wait_until="domcontentloaded")
    H.wait_app_state(dev.page, "app", 20)
    open_more(dev.page)
    shown = has(dev.page, TXT["badge"].format(p=p))
    assert shown == (p > 0) and (p > 0 or not has(dev.page, "ממתינים")), "badge shown=%s for P=%d" % (shown, p)


@pytest.mark.parametrize("managers", [1, 2])
def test_b03_only_manager_leave_sub(env, managers):
    """§1.1: for the only manager the leave row sub reads "את/ה המנהל/ת היחיד/ה – קודם ממנים מנהל"; with a second manager it
    does not."""
    others = (("אבי", "manager"), ("Editor Q", "editor")) if managers == 2 else (("Editor Q", "editor"),)
    tid, code, dev = boot_one(env, others=others)
    open_more(dev.page)
    shown = has(dev.page, TXT["leave_sub_only"])
    assert shown == (managers == 1), "only-manager sub shown=%s with %d managers" % (shown, managers)


# =====================================================================================================
# 2 · Members screen (criterion 3, §1.2)
# =====================================================================================================
def test_c01_list_order_counts(env):
    """C3: exactly the active members (pending / removed not listed); me first (+ "(את/ה)"), then managers, then by joined_at;
    "חברים · N", "<M> מנהלים"; the footnote."""
    be = env.backend
    tid, code = new_trip(env, others=(("Editor Q", "editor"), ("אבי", "manager"), ("נועה", "viewer"), ("רון", "manager")))
    be.add(tid, "ממתין", status="pending")
    be.add(tid, "הוסר", status="removed")
    dev = boot(env, [(tid, "manager", "דנה")])
    page, P = dev.page, []
    open_members(page)
    names = action_buttons(page)
    act = be.members(tid, "active")
    mgrs = [r["display_name"] for r in act if r["role"] == "manager" and r["display_name"] != "דנה"]
    rest = [r["display_name"] for r in act if r["role"] != "manager"]
    want = ["דנה"] + mgrs + rest
    if [re.sub(r"\s*\(את/ה\)$", "", n) for n in names] != want:
        P.append("order %r, want %r" % (names, want))
    if any(n in btext(page) for n in ("ממתין", "הוסר")):
        P.append("pending / removed member listed")
    if not has(page, TXT["count"].format(n=len(act))) or not has(page, TXT["mgrs"].format(m=3)):
        P.append("counts: want %r and %r" % (TXT["count"].format(n=len(act)), TXT["mgrs"].format(m=3)))
    if not has(page, TXT["me_tag"]):
        P.append("'(את/ה)' missing")
    if not has(page, TXT["footnote"]):
        P.append("footnote missing")
    assert not P, "\n".join(P)


def test_c02_last_seen_and_badges(env):
    """§1.2 rows: last seen relative ("פעיל/ה היום", "פעיל/ה אתמול", "לפני 3 ימים", "עוד לא נכנס/ה"), "מנהל/ת אחד/ת" with
    one manager, role badges."""
    be = env.backend
    tid, code = new_trip(env, others=())
    now = be.tnow()
    be.add(tid, "היום", last_seen=now - H.HOUR)
    be.add(tid, "אתמול", last_seen=now - H.DAY)
    be.add(tid, "שלושה", role="viewer", last_seen=now - 3 * H.DAY)
    be.add(tid, "אף פעם", last_seen=None)
    dev = boot(env, [(tid, "manager", "דנה")])
    page, P = dev.page, []
    open_members(page)
    for k, a in (("seen_today", {}), ("seen_yday", {}), ("seen_days", {"d": 3}), ("seen_never", {})):
        if not has(page, TXT[k].format(**a)):
            P.append("missing %r" % TXT[k].format(**a))
    if not has(page, TXT["one_mgr"]):
        P.append("'מנהל/ת אחד/ת' missing with one manager")
    for w in ("עורך", "צופה", "מנהל"):
        if not re.search(w, btext(page)):
            P.append("role badge %s missing" % w)
    assert not P, "\n".join(P)


def url_style(page):
    return page.evaluate("""()=>{const all=[...document.querySelectorAll('body *')].filter(e=>(e.textContent||'').includes('join/#code=')
      &&![...e.children].some(c=>(c.textContent||'').includes('join/#code='))&&e.getBoundingClientRect().width>0);
      return all.map(e=>{const s=getComputedStyle(e);return {t:e.textContent.trim(),dir:s.direction,ff:s.fontFamily}})}""")


def test_c03_link_card(env):
    """C3 + §1.2 link card: help text, the current URL (from trip_join_codes, LTR, monospace), WhatsApp with the URL, copy
    writes the URL, "איפוס" present."""
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    open_members(page)
    url = f04.JOIN_BASE + "#code=" + code
    st = url_style(page)
    if not st or code not in st[0]["t"]:
        P.append("URL with the current code not shown: %r" % st)
    elif st[0]["dir"] != "ltr" or "mono" not in st[0]["ff"].lower():
        P.append("URL not LTR monospace: %r" % st[0])
    if not has(page, TXT["link_help"]) or not H.visible(page, TXT["reset"]):
        P.append("help / 'איפוס' missing")
    if not env.backend.queries("trip_join_codes"):
        P.append("trip_join_codes not read")
    w = f04.wa_url(dev) or ""
    if url not in f04.wa_text(w):
        P.append("WhatsApp lacks the URL: %r" % w)
    click_exact(page, TXT["copy"])
    if url not in (page.evaluate("()=>window.__qaWatch&&window.__qaWatch.copied") or ""):
        P.append("copy did not write the URL")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("p", [0, 2])
def test_c04_pending_shortcut(env, p):
    """C3 + D9: the shortcut "<P> ממתינים לאישור" + "לאישור בבית" only with P>0; it navigates home where the F05 card is."""
    tid, code, dev = boot_one(env)
    for i in range(p):
        env.backend.add(tid, "ממתין%d" % i, status="pending")
    page = dev.page
    open_members(page)
    shown = has(page, TXT["pending_short"].format(p=p)) and H.visible(page, TXT["to_home"])
    assert shown == (p > 0), "shortcut shown=%s for P=%d" % (shown, p)
    if p:
        click_exact(page, TXT["to_home"])
        assert wait_until(lambda: is_vis(page, "#ptF05Pending"), 6, page), "did not reach home with the F05 pending card"


def test_c05_live_refresh(env):
    """§1.2 Live: a member approved / renamed elsewhere appears in the list without reload."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page = dev.page
    open_members(page)
    f20.mark_page(page)
    mid = be.new_pending(tid, "חדשה")
    be.approve_direct(mid, "editor")
    be.rename_direct(be.members(tid, "active")[1]["id"], "שם מעודכן")
    ok = wait_until(lambda: "חדשה" in action_buttons(page) and "שם מעודכן" in action_buttons(page), 6, page)
    assert ok and f20.same_document(page), "list not refreshed live: %r" % action_buttons(page)


def test_c06_stale_non_manager_sent_back(env):
    """§1.2: a manager demoted while the screen is open no longer sees the list (sent back to "עוד" / home). (open: the
    toast text is not in the spec — only 'nothing but a toast' is asserted.)"""
    be = env.backend
    tid, code, dev = boot_one(env)
    page = dev.page
    open_members(page)
    be.set_role_direct(my_row(env, dev, tid)["id"], "editor")
    H.to_background_and_back(page)
    ok = wait_until(lambda: not action_buttons(page), 8, page)
    assert ok, "demoted manager still sees the member list: %r" % action_buttons(page)


# =====================================================================================================
# 3 · Member sheet, remove, rotate, only manager (criteria 5, §1.3–1.6; client side of 4, 6, 7, 11)
# =====================================================================================================
def test_d01_set_role_from_sheet(env):
    """§1.3: the sheet shows name + "הצטרף/ה ב-dd/mm/yyyy"; the segment marks the current role (aria-pressed); tapping
    another role saves at once (manage-members set_role {member_id, role}) → toast "<name> עכשיו <role>"."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    open_members(page)
    row = next(r for r in be.members(tid, "active") if r["display_name"] == "Editor Q")
    tap_actions(page, "Editor Q")
    d = dt.datetime.fromisoformat(row["joined_at"]).astimezone(dt.timezone(dt.timedelta(hours=3)))   # Jerusalem, October (IDT)
    if not has(page, TXT["joined"].format(d=d.strftime("%d/%m/%Y"))):
        P.append("header 'הצטרף/ה ב-%s' missing" % d.strftime("%d/%m/%Y"))
    rb = role_buttons(page)
    if [b["p"] for b in rb] != ["false", "true", "false"]:
        P.append("segment aria-pressed %r (want צופה/עורך*/מנהל)" % rb)
    tap_role(page, "viewer")
    c = mm(env, "set_role")
    if not c or c[-1]["body"].get("member_id") != row["id"] or c[-1]["body"].get("role") != "viewer":
        P.append("set_role call %r" % [x["body"] for x in c])
    if be.member(row["id"])["role"] != "viewer":
        P.append("role not stored")
    if not wait_until(lambda: seen(page, TXT["t_role"].format(name="Editor Q", role="צופה")), 4, page):
        P.append("toast %r missing" % TXT["t_role"].format(name="Editor Q", role="צופה"))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("case", ["ok", "taken", "invalid"])
def test_d02_rename_from_sheet(env, case):
    """C6 client + §1.3: name input maxlength 40 + "שמירה" (rename); valid → saved and shown in the list; name_taken /
    name_invalid → inline error as F05 1.6b, no change."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    open_members(page)
    tap_actions(page, "Editor Q")
    inp = page.locator('input[maxlength="40"]').filter(visible=True)   # TODO(dev-notes id): the sheet's name input
    assert inp.count(), "name input (maxlength 40) not found in the sheet"
    new = {"ok": "קווין", "taken": "אבי", "invalid": "   "}[case]
    inp.first.fill(new)
    click_exact(page, TXT["save"])
    c = mm(env, "rename")
    row = next(r for r in be.members(tid) if r["user_id"] and r["display_name"] in ("Editor Q", "קווין"))
    if case == "ok":
        if not c or row["display_name"] != "קווין" or not wait_until(lambda: "קווין" in action_buttons(page), 4, page):
            P.append("rename not saved / not shown: %r %r" % (row["display_name"], action_buttons(page)))
    else:
        if row["display_name"] != "Editor Q":
            P.append("name changed on a refusal")
        if case == "taken" and not wait_has(page, TXT["taken"].format(n="אבי"), 4):
            P.append("inline name_taken text missing")
        if case == "invalid" and not c and not page.evaluate("()=>[...document.querySelectorAll('[aria-invalid=true],.error,[role=alert]')].length"):
            P.append("empty name: neither refused by the server nor marked invalid inline")
    assert not P, "\n".join(P)


def test_d03_remove_confirm_flow(env):
    """C7 client + §1.4: "הסרה מהטיול" → alert "להסיר את <name> מהטיול?" + "הסרה" / "ביטול"; ביטול → nothing; הסרה → remove
    → toast "<name> הוסר/ה מהטיול", the sheet closes and the row disappears. My own row has no "הסרה מהטיול"."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    open_members(page)
    tap_actions(page, "נועה")
    click_exact(page, TXT["remove_row"])
    if not wait_has(page, TXT["remove_q"].format(name="נועה"), 4):
        P.append("confirm text missing")
    click_exact(page, TXT["cancel"])
    if mm(env, "remove"):
        P.append("ביטול sent remove")
    if not H.visible(page, TXT["remove_row"]):
        tap_actions(page, "נועה")
    click_exact(page, TXT["remove_row"])
    click_exact(page, TXT["remove_yes"])
    page.wait_for_timeout(800)
    row = next(r for r in be.members(tid) if r["display_name"] == "נועה")
    if not mm(env, "remove") or row["status"] != "removed":
        P.append("remove not sent / stored")
    if not wait_until(lambda: seen(page, TXT["t_removed"].format(name="נועה")), 4, page):
        P.append("toast missing")
    if "נועה" in action_buttons(page):
        P.append("removed row still listed")
    tap_actions(page, "דנה")
    if H.visible(page, TXT["remove_row"]):
        P.append("'הסרה מהטיול' on my own row")
    assert not P, "\n".join(P)


def test_d04_two_managers_self_demote(env):
    """C5: with two managers I may step down from my own sheet; afterwards "חברים וקישור" disappears from my "עוד" without
    reload."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page = dev.page
    open_members(page)
    f20.mark_page(page)
    tap_actions(page, "דנה")
    assert not [b for b in role_buttons(page) if b["d"]], "role segment disabled although another manager exists"
    tap_role(page, "editor")
    assert my_row(env, dev, tid)["role"] == "editor", "self-demotion not stored"
    page.wait_for_timeout(1500)
    open_more(page)
    assert wait_until(lambda: not H.visible(page, TXT["members_row"]), 5, page), "'חברים וקישור' still in 'עוד'"
    assert f20.same_document(page), "page reloaded"


def test_d05_only_manager_sheet(env):
    """§1.6 (C10 / D6 client): my sheet as the only manager: segment disabled except מנהל, name editable, amber box "את/ה
    המנהל/ת היחיד/ה בטיול", "למנות מנהל אחר" closes the sheet and the list stays, "אין בטיול חברים אחרים? פונים למנהל המערכת."."""
    tid, code, dev = boot_one(env, others=(("Editor Q", "editor"),))
    page, P = dev.page, []
    open_members(page)
    tap_actions(page, "דנה")
    rb = role_buttons(page)
    if not rb or [b["d"] for b in rb] != [True, True, False]:
        P.append("segment disabled flags %r (want צופה/עורך disabled, מנהל enabled)" % rb)
    for k in ("only_box", "sysadmin"):
        if not has(page, TXT[k]):
            P.append("%r missing" % TXT[k])
    if not page.locator('input[maxlength="40"]').filter(visible=True).count():
        P.append("my name is not editable")
    click_exact(page, TXT["appoint"])
    page.wait_for_timeout(500)
    if has(page, TXT["only_box"]) or "Editor Q" not in action_buttons(page):
        P.append("'למנות מנהל אחר' did not close the sheet back to the list")
    if mm(env, "set_role"):
        P.append("set_role sent")
    assert not P, "\n".join(P)


def test_d06_rotate_link(env):
    """§1.5 (C11 client): "איפוס" → alert "לאפס את קישור ההצטרפות?" + "איפוס הקישור" / "ביטול" → rotate_link {trip_id}; the
    card shows the new URL and a toast "נוצר קישור חדש" with "שליחה בווטסאפ"."""
    be = env.backend
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    be.add(tid, "ממתין", status="pending")
    open_members(page)
    click_exact(page, TXT["reset"])
    if not wait_has(page, TXT["rotate_q"], 4):
        P.append("confirm missing")
    click_exact(page, TXT["rotate_yes"])
    page.wait_for_timeout(800)
    new = be.join_code(tid)
    c = mm(env, "rotate_link")
    if not c or c[-1]["body"].get("trip_id") != tid or new == code:
        P.append("rotate_link not sent: %r" % [x["body"] for x in c])
    if not wait_until(lambda: "join/#code=" + new in btext(page), 4, page) or "join/#code=" + code in btext(page):
        P.append("card does not show the new URL")
    if not wait_until(lambda: seen(page, TXT["t_rotated"]), 4, page):
        P.append("toast missing")
    if len(H.find(page, TXT["wa"], exact=True)) < 2:
        P.append("toast has no 'שליחה בווטסאפ' action (only the card button found)")
    assert not P, "\n".join(P)


# =====================================================================================================
# 4 · Leave (criterion 10, §1.7)
# =====================================================================================================
@pytest.mark.parametrize("other", [True, False])
def test_e01_leave(env, other):
    """C10: "יציאה מהטיול" → `לצאת מ"<trip>"?` → "יציאה" → leave {trip_id} → my row removed, every pt:<trip>: key gone, then
    the next active trip or the not-connected card."""
    be = env.backend
    tid, code = new_trip(env)
    links = [(tid, "editor", "חבר")]
    t2 = None
    if other:
        t2, _ = be.trip(name="קבוצה 2", managers=(("מנהל2", None),))
        links.append((t2, "viewer", "חבר"))
    dev = boot(env, links, pre_ls={"pt:_device:active_trip": json.dumps({"trip_id": tid})})
    page, P = dev.page, []
    assert H.running_trip(page) == tid, "harness: started trip %r" % H.running_trip(page)
    open_more(page)
    click_exact(page, TXT["leave_row"])
    if not wait_has(page, TXT["leave_q"].format(trip=TRIP), 4):
        P.append("confirm missing")
    click_exact(page, TXT["leave_yes"])
    page.wait_for_timeout(1500)
    if not mm(env, "leave") or my_row(env, dev, tid)["status"] != "removed":
        P.append("leave not sent / stored")
    if not wait_until(lambda: other_state_ok(dev, t2), 15, page):
        P.append("after leave: state %r trip %r" % (H.app_state(page), H.running_trip(page)))
    left = list(H.ls_trip(dev, tid))
    if left:
        P.append("pt:<trip>: keys left: %r" % left[:5])
    assert not P, "\n".join(P)


def test_e02_only_manager_leave_shows_1_6(env):
    """C10 + D6: the only manager taps "יציאה מהטיול" → 1.6 (explanation + "למנות מנהל אחר"), not the confirm; no leave."""
    tid, code, dev = boot_one(env, others=(("Editor Q", "editor"),))
    page = dev.page
    open_more(page)
    click_exact(page, TXT["leave_row"])
    assert wait_has(page, TXT["only_box"], 4) and H.visible(page, TXT["appoint"]), "1.6 not shown"
    assert not has(page, TXT["leave_q"].format(trip=TRIP)) and not mm(env, "leave"), "leave confirm / call for the only manager"


# =====================================================================================================
# 5 · Removed member's phone (criterion 8, §1.8b, §3.4)
# =====================================================================================================
def removed_problems(dev, tid, other=False):
    page, P = dev.page, []
    if not has(page, TXT["removed_text"]):
        P.append("text %r missing" % TXT["removed_text"])
    if chrome(page):
        P.append("trip chrome shown on 1.8b: %r" % chrome(page))
    if H.running_trip(page) == tid:
        P.append("the trip still runs")
    left = [k for k in H.ls_trip(dev, tid)]
    if left:
        P.append("pt:<trip>: keys left: %r" % left[:5])
    if bool(H.visible(page, TXT["my_trips"])) != other:
        P.append("'הטיולים שלי' shown=%s (other trip=%s)" % (H.visible(page, TXT["my_trips"]), other))
    rec = dev.ls().get("pt:_device:removed")
    try:
        if not rec or json.loads(rec).get("trip_id") != tid:
            P.append("pt:_device:removed %r" % rec)
    except ValueError:
        P.append("pt:_device:removed not JSON: %r" % rec)
    return P


@pytest.mark.parametrize("how", ["visible", "poll60", "online"])
def test_f01_removed_while_open(env, how):
    """C8 + D11: removed by the manager while the app is open (no Realtime for the row, D11) → 1.8b on return to the app
    (visibilitychange), within 60 s, or on `online`; pt:<trip>:* gone; pt:_device:removed kept."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    be.remove_direct(my_row(env, dev, tid)["id"])
    if how == "visible":
        H.to_background_and_back(page)
    elif how == "poll60":
        page.clock.run_for(61000)
    else:
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    assert wait_until(lambda: is_removed_screen(page), 6, page), "1.8b not shown (%s): %r" % (how, btext(page)[:200])
    P = removed_problems(dev, tid)
    assert not P, "\n".join(P)


def test_f02_removed_at_next_boot(env):
    """C8: at the next boot the same screen shows (from pt:_device:removed) and the trip does not open."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    be.remove_direct(my_row(env, dev, tid)["id"])
    H.to_background_and_back(dev.page)
    assert wait_until(lambda: is_removed_screen(dev.page), 6, dev.page)
    dev.page.reload(wait_until="domcontentloaded")
    dev.page.wait_for_timeout(2500)
    assert is_removed_screen(dev.page), "1.8b not shown at the next boot"
    assert H.running_trip(dev.page) != tid, "the removed trip opened"


def test_f03_removed_with_other_trip(env):
    """§1.8b: "הטיולים שלי" only with another active trip; it opens that trip."""
    be = env.backend
    tid, code = new_trip(env)
    t2, _ = be.trip(name="קבוצה 2", managers=(("מנהל2", None),))
    dev = boot(env, [(tid, "editor", "חבר"), (t2, "editor", "חבר")], pre_ls={"pt:_device:active_trip": json.dumps({"trip_id": tid})})
    page = dev.page
    be.remove_direct(my_row(env, dev, tid)["id"])
    H.to_background_and_back(page)
    assert wait_until(lambda: is_removed_screen(page), 6, page)
    P = removed_problems(dev, tid, other=True)
    if not P:
        click_exact(page, TXT["my_trips"])
        if not wait_until(lambda: H.running_trip(page) == t2, 10, page):
            P.append("'הטיולים שלי' did not lead to the other trip")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("cached", [True, False])
def test_f04_ask_again(env, cached):
    """§1.8b + D2 / C9: "בקשה להצטרף שוב" opens /join/ with the cached join code → the normal form → a request makes the SAME
    row pending; without a cached code the line "בקשו מהמנהל את קישור ההצטרפות". The cached code is seeded through the
    spec's record pt:_device:removed.join_code (§3.4)."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    mid = my_row(env, dev, tid)["id"]
    be.remove_direct(mid)
    rec = {"trip_id": tid, "name": TRIP, "n_dropped": 0}
    if cached:
        rec["join_code"] = code
    dev.seed_ls({"pt:_device:removed": json.dumps(rec)})
    page.reload(wait_until="domcontentloaded")
    assert wait_until(lambda: is_removed_screen(page), 10, page), "1.8b not shown from pt:_device:removed"
    if not cached:
        assert has(page, TXT["ask_link"]), "line %r missing without a cached code" % TXT["ask_link"]
        return
    click_exact(page, TXT["ask_again"])
    assert H.f05.wait_screen(page, ("form",), 12) == "form", "join form not shown (text=%r)" % btext(page)[:200]
    page.locator("#lpjName").fill("חבר חוזר")
    page.locator("#lpjSubmit").click()
    assert H.f05.wait_screen(page, ("pending",), 8) == "pending", "request did not reach the waiting screen"
    row = be.member(mid)
    assert row["status"] == "pending" and row["display_name"] == "חבר חוזר" and \
        len([r for r in be.members(tid) if r["user_id"] == row["user_id"]]) == 1, "D2: not the same row: %r" % row


def test_f05_removed_with_queued_changes(env):
    """C8 + D8: removed with unsent offline changes → dropped, 1.8b shows "N שינויים … לא נשמרו" with the right N, nothing
    reaches trip_kv."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    before = be.kv(tid, "expenses")
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    add_expense_try(page, "QA F06 lost 1")
    add_journal_try(page, "QA F06 lost 2")
    n = len(H.queue(dev, tid))
    be.remove_direct(my_row(env, dev, tid)["id"])
    dev.offline(False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    assert wait_until(lambda: is_removed_screen(page), 8, page), "1.8b not shown"
    m = re.search(TXT["dropped_re"], btext(page))
    assert n >= 1 and m and int(m.group(1)) == n, "dropped line %r, queue had %d" % (m and m.group(0), n)
    assert be.kv(tid, "expenses") == before, "a dropped change reached trip_kv"


def test_f06_removed_identity_join_link(env):
    """C9 client + D2: a removed member who opens the join link sees the normal form (not "הוסרת מהטיול")."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    be.remove_direct(my_row(env, dev, tid)["id"])
    dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    assert H.f05.wait_screen(dev.page, ("form", "removed"), 12) == "form" and not has(dev.page, TXT["f05_removed"]), \
        "removed identity: screen %r" % H.f05.screen_of(dev.page)


# =====================================================================================================
# 6 · Role change on the member's phone (criteria 13, 14, §1.8a)
# =====================================================================================================
def card_shown(page, role):
    t = btext(page)
    return bool(re.search(re.escape(TXT["changed"]) + "(" + ROLE_RE[role] + ")", t)) and norm(TXT["changed_by"]) in t


@pytest.mark.parametrize("frm,to", [("editor", "viewer"), ("viewer", "editor"), ("editor", "manager"), ("manager", "editor")])
def test_g01_role_change_realtime(env, frm, to):
    """C14: role changed by a manager while the phone is open on home → 1.8a within ≤3 s (Realtime on the own row);
    viewer → the extra line; "הבנתי" hides it and it stays hidden after reload (per trip + role)."""
    be = env.backend
    others = (("אבי", "manager"), ("Editor Q", "editor"))
    tid, code, dev = boot_one(env, role=frm, me="חבר", others=others)
    page, P = dev.page, []
    f02.tab(page, "home")
    be.set_role_direct(my_row(env, dev, tid)["id"], to)
    if not wait_until(lambda: card_shown(page, to), 3.5, page):
        P.append("1.8a not shown within 3 s (text=%r)" % btext(page)[:300])
    else:
        if (to == "viewer") != has(page, TXT["viewer_line"]):
            P.append("viewer line shown=%s for %s" % (has(page, TXT["viewer_line"]), to))
        click_exact(page, TXT["got_it"])
        if card_shown(page, to):
            P.append("'הבנתי' did not hide the card")
        page.reload(wait_until="domcontentloaded")
        H.wait_app_state(page, "app", 20)
        page.wait_for_timeout(1500)
        if card_shown(page, to):
            P.append("card back after reload")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("how", ["poll60", "visible"])
def test_g02_role_change_without_realtime(env, how):
    """C14 + D11: Realtime silent → 1.8a after ≤60 s (poll) or at once on returning to the app."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    be.rt_silent = True
    be.set_role_direct(my_row(env, dev, tid)["id"], "viewer")
    page.wait_for_timeout(1500)
    if how == "poll60":
        page.clock.run_for(61000)
    else:
        H.to_background_and_back(page)
    assert wait_until(lambda: card_shown(page, "viewer"), 6, page), "1.8a not shown (%s)" % how


def test_g03_dismiss_is_per_role(env):
    """§1.8a: dismissing for viewer does not hide a later change to editor."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    mid = my_row(env, dev, tid)["id"]
    be.set_role_direct(mid, "viewer")
    assert wait_until(lambda: card_shown(page, "viewer"), 4, page)
    click_exact(page, TXT["got_it"])
    be.set_role_direct(mid, "editor")
    assert wait_until(lambda: card_shown(page, "editor"), 4, page), "change to editor not shown after dismissing viewer"


def test_g04_demotion_drops_queue(env):
    """C13 + D8: queued offline changes, demoted to viewer, back online → dropped; 1.8a says "N שינויים … לא נשמרו" with the
    right N; the queue is empty; nothing reaches trip_kv."""
    be = env.backend
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    before = (be.kv(tid, "expenses"), be.kv(tid, "journal"))
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    add_expense_try(page, "QA F06 demote 1")
    add_journal_try(page, "QA F06 demote 2")
    n = len(H.queue(dev, tid))
    be.set_role_direct(my_row(env, dev, tid)["id"], "viewer")
    dev.offline(False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    f02.tab(page, "home")
    P = []
    if not wait_until(lambda: card_shown(page, "viewer"), 8, page):
        P.append("1.8a not shown")
    m = re.search(TXT["dropped_re"], btext(page))
    if not (n >= 1 and m and int(m.group(1)) == n):
        P.append("dropped line %r, queue had %d" % (m and m.group(0), n))
    page.wait_for_timeout(1500)
    if H.queue(dev, tid):
        P.append("queue not empty: %r" % H.queue(dev, tid))
    if (be.kv(tid, "expenses"), be.kv(tid, "journal")) != before:
        P.append("dropped changes reached trip_kv")
    assert not P, "\n".join(P)


# =====================================================================================================
# 7 · Viewer guard (criterion 12, D10, §3.3)
# =====================================================================================================
ACTS = {"expense": add_expense_try, "journal": add_journal_try, "waypoint": add_waypoint_try, "checkin": add_checkin_try}


@pytest.mark.parametrize("what", list(ACTS))
def test_h01_viewer_guard(env, what):
    """C12: as viewer, adding a <what> → toast "צופה בלבד – השינוי לא נשמר"; no trip_kv write; the text never lands in a
    pt:<trip>: localStorage key; the queue stays empty; the screen shows the cloud state (the item is not shown)."""
    be = env.backend
    tid, code, dev = boot_one(env, role="viewer", me="חבר")
    page = dev.page
    n0 = len(be.queries("trip_kv"))
    label = "QA F06 guard " + what
    ACTS[what](page, label)
    page.wait_for_timeout(1500)
    P = []
    if not seen(page, TXT["viewer_toast"]):
        P.append("toast missing")
    if kv_writes(env, dev.name, n0):
        P.append("trip_kv write sent: %r" % [c["msg"]["req"]["action"] for c in kv_writes(env, dev.name, n0)])
    if text_in_trip_ls(dev, tid, label):
        P.append("written to localStorage: %r" % text_in_trip_ls(dev, tid, label))
    if H.queue(dev, tid):
        P.append("queued: %r" % H.queue(dev, tid))
    if label in btext(page):
        P.append("the screen shows the blocked item (not the cloud state)")
    assert not P, "\n".join(P)


def test_h02_toast_once_per_5s(env):
    """§3.3: the toast at most once per 5 s; after 5 s it shows again."""
    tid, code, dev = boot_one(env, role="viewer", me="חבר")
    page = dev.page
    add_expense_try(page, "QA F06 t1")
    add_expense_try(page, "QA F06 t2")
    n1 = H.seen_count(page, TXT["viewer_toast"])
    page.clock.run_for(6000)
    page.wait_for_timeout(500)
    add_expense_try(page, "QA F06 t3")
    n2 = H.seen_count(page, TXT["viewer_toast"])
    assert n1 == 1 and n2 == 2, "toast rising edges: %d within 5 s (want 1), %d after (want 2)" % (n1, n2)


@pytest.mark.parametrize("role", ["editor", "manager"])
def test_h03_editors_and_managers_write(env, role):
    """C12: editors and managers write as before (no toast, trip_kv updated)."""
    be = env.backend
    tid, code, dev = boot_one(env, role=role, me="חבר" if role == "editor" else "דנה")
    add_expense_try(dev.page, "QA F06 write " + role)
    ok = wait_until(lambda: "QA F06 write " + role in (be.kv(tid, "expenses") or ""), 10, dev.page)
    assert ok and not seen(dev.page, TXT["viewer_toast"]), "%s write: reached=%s toast=%s" % (role, ok, seen(dev.page, TXT["viewer_toast"]))


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_h04_viewer_tag(env, role):
    """D10: a "צופה" tag in the home header only for viewers. TODO(dev-notes id): header tag id; matched here as an element
    whose whole text is "צופה" in the top 160 px of home."""
    tid, code, dev = boot_one(env, role=role, me="חבר")
    page = dev.page
    f02.tab(page, "home")
    page.evaluate("()=>window.scrollTo(0,0)")
    tag = page.evaluate("""()=>[...document.querySelectorAll('body *')].some(e=>{const r=e.getBoundingClientRect();
      return r.width>0&&r.height>0&&r.top<160&&(e.innerText||'').trim()==='צופה'&&!e.closest('[aria-pressed]')})""")
    assert tag == (role == "viewer"), "'צופה' tag shown=%s for %s" % (tag, role)


def test_h05_touch_on_start(env):
    """C16 client (§2.8 / §3.1): app start calls manage-members touch {trip_id}; returning to the app calls it again (the
    server rate-limits)."""
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    n = len(env.backend.mm_of("touch"))
    H.to_background_and_back(dev.page)
    dev.page.wait_for_timeout(800)
    t = env.backend.mm_of("touch")
    assert n >= 1 and t[0]["body"].get("trip_id") == tid and len(t) > n, "touch calls %r" % [c["body"] for c in t]


# =====================================================================================================
# 8 · Offline (criterion 19)
# =====================================================================================================
def test_j01_members_offline(env):
    """C19: offline → the cached list stays, all action buttons disabled, "אין חיבור – אפשר לשנות כשהרשת תחזור."; no
    manage-members call is possible; online again → enabled."""
    tid, code, dev = boot_one(env)
    page, P = dev.page, []
    open_members(page)
    names = action_buttons(page)
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    page.wait_for_timeout(800)
    if action_buttons(page) != names:
        P.append("cached list changed offline: %r" % action_buttons(page))
    if not has(page, TXT["offline"]):
        P.append("offline line missing")
    dis = page.evaluate("""()=>[...document.querySelectorAll('[aria-label^="פעולות על "]')].map(b=>b.disabled||b.getAttribute('aria-disabled')==='true')""")
    if not dis or not all(dis):
        P.append("'⋯' buttons not disabled: %r" % dis)
    n = len(mm(env))
    for t in (TXT["reset"],):
        try:
            c = [x for x in H.find(page, t, exact=True) if x["top"]]
            if c:
                page.mouse.click(c[0]["x"], c[0]["y"])
                page.wait_for_timeout(300)
                if has(page, TXT["rotate_q"]):
                    click_exact(page, TXT["rotate_yes"])
        except PWError:
            pass
    if len(mm(env)) != n:
        P.append("a manage-members call was made offline")
    dev.offline(False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    page.wait_for_timeout(1200)
    dis = page.evaluate("""()=>[...document.querySelectorAll('[aria-label^="פעולות על "]')].map(b=>b.disabled)""")
    if not dis or any(dis):
        P.append("online again: still disabled %r" % dis)
    assert not P, "\n".join(P)


def test_j02_leave_offline_impossible(env):
    """C19: leaving offline is impossible (a toast; no call; still in the trip, data kept)."""
    tid, code, dev = boot_one(env, role="editor", me="חבר")
    page = dev.page
    keys = set(H.ls_trip(dev, tid))
    open_more(page)
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    click_exact(page, TXT["leave_row"])
    if has(page, TXT["leave_q"].format(trip=TRIP)):
        click_exact(page, TXT["leave_yes"])
    page.wait_for_timeout(1200)
    assert not mm(env, "leave") and H.running_trip(page) == tid and set(H.ls_trip(dev, tid)) >= keys, \
        "offline leave went through (calls %r, trip %r)" % (mm(env, "leave"), H.running_trip(page))
    assert seen(page, "אין חיבור"), "no offline toast"


# =====================================================================================================
# 9 · 390px / RTL / touch on the 8 artboards (criterion 18)
# =====================================================================================================
SCREENS = ["more", "members", "sheet", "remove_confirm", "rotate_confirm", "last_manager", "leave_confirm", "changed", "removed"]


@pytest.mark.parametrize("scr", SCREENS)
def test_l01_layout_390(env, scr):
    """C18: no horizontal scroll, RTL, touch ≥44px; on the members screen the URL is LTR."""
    be = env.backend
    role = "editor" if scr in ("leave_confirm", "changed", "removed") else "manager"
    others = (("Editor Q", "editor"),) if scr == "last_manager" else (("אבי", "manager"), ("Editor Q", "editor"))
    tid, code, dev = boot_one(env, role=role, me="דנה" if role == "manager" else "חבר", others=others)
    page = dev.page
    if scr == "more":
        open_more(page)
    elif scr in ("members", "sheet", "remove_confirm", "rotate_confirm", "last_manager"):
        open_members(page)
        if scr == "sheet":
            tap_actions(page, "Editor Q")
        elif scr == "remove_confirm":
            tap_actions(page, "Editor Q")
            click_exact(page, TXT["remove_row"])
        elif scr == "rotate_confirm":
            click_exact(page, TXT["reset"])
        elif scr == "last_manager":
            tap_actions(page, "דנה")
    elif scr == "leave_confirm":
        open_more(page)
        click_exact(page, TXT["leave_row"])
    elif scr == "changed":
        f02.tab(page, "home")
        be.set_role_direct(my_row(env, dev, tid)["id"], "viewer")
        assert wait_until(lambda: card_shown(page, "viewer"), 4, page)
    else:
        be.remove_direct(my_row(env, dev, tid)["id"])
        H.to_background_and_back(page)
        assert wait_until(lambda: is_removed_screen(page), 6, page)
    page.wait_for_timeout(500)
    P = layout_problems(page, None, scr)
    if scr == "members":
        st = url_style(page)
        if not st or st[0]["dir"] != "ltr":
            P.append("URL not LTR: %r" % st)
    assert not P, "\n".join(P)
