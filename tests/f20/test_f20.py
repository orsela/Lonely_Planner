"""Plan_Travel F20 QA · Playwright black-box suite · version 1.1.1
CHANGE 2026-10-13 F20-QA-01: first version (no previous version).
CHANGE 2026-10-26 QA-DEBT-05: 1.1.0 → 1.1.1: MAIN_REF defaults to the alpha.4.2 commit from tests/qa_refs.py (a7c7a32; was
  "main", which stopped being alpha.4.2 at F20's merge, so every static case failed on its harness assert when the suite was
  run without the F05 runner); test_st_static[protected:*] compares with the v2.15.2 declarations from git (V2152_REF);
  test_st_static[app_version|pt_version] pin tests/qa_refs.py CURRENT_VERSION (was 3.0.0-alpha.5.1). Nothing else changed.
CHANGE 2026-10-17 F20-QA-03: 1.0.0 → 1.1.0, follows alpha.5.1 (spec D5 amended, D7, §1.3, criterion 8; dev notes §7):
  - VERSION pin → 3.0.0-alpha.5.1.
  - test_a03 (sheet → admin) replaced by test_a03_reopen_choose_to_admin_ignores_d3 (the only way from a trip to admin is
    reopening the app at ?choose=1 → chooser → admin row; "הטיולים שלי" → chooser, D3 ignored).
  - test_s02: avatar only with ≥2 trips for the super-admin too ([one] → no avatar, [four] → avatar).
  - test_s03: the sheet has NO "ניהול" section / #ptSwitchAdmin / admin texts (was: asserted them).
  - test_s07[admin] removed (no admin row in the sheet any more); [trip] unchanged.
  - New: test_e01_no_admin_text_in_trip_ui[one|four] (no "ניהול מערכת" / admin texts on home headers, "עוד", sheet,
    every tab), test_e02_hash_admin_in_running_trip_reloads_to_standalone[hashchange|trip_query],
    test_e03_hash_admin_non_admin_in_trip_cleaned_no_reload, test_e04_hash_admin_loop_guard (admin check hangs after the
    reload → lands in the trip once, hash cleaned, no reload loop).

Black-box acceptance tests for docs/F20_spec.md §3 (criteria 1–14): the super-admin start chooser (#ptChoose), the
standalone admin screen, the in-trip trip/admin switcher (avatar + sheet), the boot rules of §1.4 and the "עוד" change.
Contract: docs/F20_spec.md, plus docs/F20_dev_notes.md §4 ("For QA — stable ids and visible texts") and §6 (open points /
architect decisions) ONLY. NOT read: the implementation in app/index.html (only exact visible strings / version constants
are grepped by the static checks) and the developer's smoke files.

Architect decisions taken as spec (2026-10-13): with WIZARD_FEATURE='off' and SWITCH_FEATURE='on' a non-admin boots into
the cached trip (a switch sticks); the admin check has its own ~2.5 s bound and a timeout counts as "not super-admin";
the sheet has an extra × close button; a single member reads "חבר אחד".

Layout (reuses the F04 harness, imported as a module from ../f04/test_f04.py, which imports F03 and F02):
- f02.Server serves APP_DIR under f02.APP_PATH; flag-flipped copies (SWITCH / WIZARD / ADMIN / HOME_LAYOUT / HOME_MIN) are
  served through Server.overrides.
- The supabase-js CDN request is fulfilled with tests/f04/fake_supabase.js (unchanged).
- F20Backend (below) extends F04Backend with: several memberships per signed-in device (`links`, explicit joined_at),
  per-table hang / failure (`hang_tables`, `fail_tables`, `fail_pred`) for the admin check and the chooser loads, and an
  rpc failure switch for admin_trip_summary. platform_admins, trips, trip_countries, trip_members and admin_trip_summary
  are the F02/F03/F04 fakes with their RLS-like rules (members read their own trips; own platform_admins row only).
- "Offline" at boot = a cookie `qa_offline=1` read by an init script that makes navigator.onLine false (the page itself
  still loads from the local server, like an installed PWA served by its service worker); the fake library then answers
  every call with the supabase-js network error. Going offline while the page is open uses the real context offline mode.

Env: APP_DIR (default <repo>/app), REPO_DIR (default: two levels up), MAIN_REF (default main = alpha.4.2, the "before"
reference for protected functions and duplicate ids), QA_HEADFUL=1 to watch.
"""
import collections
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # CHANGE 2026-10-26 QA-DEBT-05: tests/qa_refs.py
import qa_refs  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
os.environ.setdefault("APP_DIR", str(REPO_DIR / "app"))
os.environ.setdefault("PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS", "1")

_spec = importlib.util.spec_from_file_location("f04_harness", str(REPO_DIR / "tests" / "f04" / "test_f04.py"))
f04 = importlib.util.module_from_spec(_spec)
sys.modules["f04_harness"] = f04
_spec.loader.exec_module(f04)
f03 = f04.f03
f02 = f04.f02

from playwright.sync_api import Error as PWError  # noqa: E402

APP_DIR = Path(os.environ["APP_DIR"])
APP_PATH = f02.APP_PATH
MAIN_REF = os.environ.get("MAIN_REF", qa_refs.REFS["3.0.0-alpha.4.2"])  # CHANGE 2026-10-26 QA-DEBT-05: default was "main"
VERSION = qa_refs.CURRENT_VERSION  # CHANGE 2026-10-26 QA-DEBT-05: was "3.0.0-alpha.5.1". CHANGE 2026-10-17 F20-QA-03: was 3.0.0-alpha.5
APP_NAME = "Lonely Planner"
OLD_NAMES = ["Plan_Travel", "Vietnam Travel Planner"]
PROTECTED = f02.PROTECTED
NC_TITLE = f02.NC_TITLE

# =====================================================================================================
# Selectors and texts (spec §1 + dev notes §4)
# =====================================================================================================
SEL = {
    "choose": "#ptChoose", "choose_title": "#ptChooseTitle", "choose_admin": "#ptChooseAdmin",
    "choose_pending": "#ptChoosePending", "choose_trips": "#ptChooseTrips", "choose_card": "#ptChooseTrips button.pt-f20-card[data-trip]",
    "choose_last": "#ptChooseLastBadge", "choose_loading": "#ptChooseLoading", "choose_err": "#ptChooseErr",
    "choose_retry": "#ptChooseRetry", "choose_none": "#ptChooseNone", "d3": "input#ptChooseD3", "d3_label": "label[for=ptChooseD3]",
    "admin": "#admin", "admin_title": "#ptAdminTitle", "admin_switch": "button#ptAdminSwitch", "admin_back": "#ptAdminBack",
    "admin_sub": ".pt-adm-head .pt-sub", "admin_head": ".pt-adm-head",
    "avatar_v2": "button#ptAvatarBtn", "avatar_v1": "button#ptAvatarBtnV1", "avatar_any": "button[data-pt-switch]",
    "sheet": "#ptF20Sheet", "sheet_box": "#ptF20SheetBox", "sw_name": "#ptSwitchName", "sw_email": "#ptSwitchEmail",
    "sw_close": "#ptF20Sheet button[data-f20-close]", "sw_scrim": "#ptF20Sheet [data-f20-close]:not(button)", "sw_trips": "#ptSwitchTrips", "sw_current": "#ptSwitchTrips .pt-f20-row[data-trip-current]",
    "sw_row": "#ptSwitchTrips button.pt-f20-row[data-trip]", "sw_admin": "button#ptSwitchAdmin", "toast": "#ptToast",
    "more_admin_row": "#ptAdminRow",
    "trip_chrome": [".tabs", "#chatFab", "#globalFxBtn"],
}
TXT = {
    "brand": APP_NAME,
    "title": "שלום {name}, לאן נכנסים?", "title_anon": "שלום, לאן נכנסים?",
    "sec_admin": "ניהול", "admin_row": "ניהול מערכת", "admin_row_sub": "כל הקבוצות והזמנת מנהלים", "pending": "{n} ממתינות",
    "sec_trips": "הטיולים שלי", "last": "אחרון", "none": "אין עדיין טיולים", "loading": "טוענים…",
    "load_err": "לא הצלחנו לטעון את הטיולים. נסו שוב.", "retry": "נסו שוב",
    "d3": "לפתוח תמיד ישר לטיול האחרון",
    "footnote": "המסך הזה מופיע רק לסופר-אדמין",
    "admin_switch": "הטיולים שלי", "admin_back_old": "חזרה לטיול", "admin_sub": "Lonely Planner · סופר-אדמין",
    "avatar_aria": "החשבון שלי ומעבר בין טיולים", "sheet_aria": "מעבר בין טיולים", "current_aria": "הטיול הנוכחי",
    "here_now": "כאן עכשיו", "sw_admin_sub": "יציאה מהטיול למסך הניהול", "sw_admin_badge": "סופר-אדמין",
    "offline_toast": "אין חיבור. נסו שוב כשהרשת תחזור.",
    "close_aria": "סגירה",
    "more_linked": "מייל מקושר",
    "admin_invite_btn": f03.TXT["invite_btn"],
}
ROLE_HE = {"manager": "מנהל", "editor": "עורך", "viewer": "צופה"}
D3_KEY = "pt:_device:open_last_trip"
CACHE_KEY = "pt:_device:active_trip"
SPEC_READ_TABLES = {"trip_members", "trips", "trip_countries", "platform_admins"}   # spec §2
SPEC_RPCS = {"admin_trip_summary"}


def flag(code):
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code)


# =====================================================================================================
# Fake backend
# =====================================================================================================
class F20Backend(f04.F04Backend):
    def __init__(self):
        super().__init__()
        self.links = []            # memberships added to every newly signed-in user: dict(trip_id, role, display_name, joined_at, status)
        self.hang_tables = set()   # queries on these tables never resolve
        self.fail_tables = set()   # queries on these tables fail like a network error
        self.fail_pred = None      # callable(req) -> True: that query fails (PostgREST permission error)
        self.rpc_fail = False
        self.delay_tables = {}     # table -> ms: the answer arrives that much later (page-side timer)

    def sign_in(self):
        res = super().sign_in()
        s = res.get("session")
        if s:
            uid = s["user"]["id"]
            for ln in self.links:
                self.add_member(ln["trip_id"], uid, ln.get("role", "editor"), ln.get("status", "active"),
                                ln.get("display_name", "QA"), joined_at=ln.get("joined_at"))
        return res

    def query(self, token, req, legacy):
        t = str(req.get("table"))
        if t in self.delay_tables:
            return {"delayMs": self.delay_tables[t], "after": self._query(token, req, legacy)}
        return self._query(token, req, legacy)

    def _query(self, token, req, legacy):
        t = str(req.get("table"))
        if t in self.hang_tables:
            return {"hang": True}
        if t in self.fail_tables:
            return {"error": dict(f02.FETCH_ERR), "status": 0, "data": None}
        if self.fail_pred and self.fail_pred(req):
            return f02._err("42501", "permission denied for table %s" % t, 403)
        return super().query(token, req, legacy)

    def rpc(self, token, fn, args):
        if self.rpc_fail and fn == "admin_trip_summary":
            self.rpc_calls.append({"fn": fn, "uid": self.tokens.get(token), "failed": True})
            return {"error": {"code": "57014", "message": "canceling statement due to statement timeout"}, "status": 500}
        return super().rpc(token, fn, args)

    # helpers
    def uid_of_device(self, device):
        for c in self.calls:
            if c["device"] == device and c.get("op") == "auth.signInAnonymously":
                s = (c.get("result") or {}).get("session")
                if s:
                    return s["user"]["id"]
        return None

    def rpcs(self, device=None):
        return [c for c in self.calls if c.get("op") == "rpc" and (device is None or c["device"] == device)]


# The F04 fake library, with one addition for the F20 timing test (§1.4 "added boot delay for a non-admin ≤ one round
# trip"): a backend answer {delayMs, after} resolves the query `after` delayMs later (in the page, without blocking the
# Python dispatcher, so concurrent queries really overlap). Everything else is the F04 file unchanged.
_Q_OLD = "var r = await backend({ op: 'query', url: url, key: key, token: t, req: req, logId: entry.t });\n        if (r && r.hang) return NEVER();"
assert _Q_OLD in f04.FAKE_JS, "harness: tests/f04/fake_supabase.js query call changed"
f04.FAKE_JS = f04.FAKE_JS.replace(_Q_OLD, _Q_OLD + "\n        if (r && r.delayMs) { await new Promise(function (res) { setTimeout(res, r.delayMs); }); r = r.after; if (r && r.hang) return NEVER(); }")


OFFLINE_JS = r"""(()=>{try{const d=Object.getOwnPropertyDescriptor(Navigator.prototype,'onLine');
 Object.defineProperty(Navigator.prototype,'onLine',{configurable:true,get(){
   try{if(/(?:^|;\s*)qa_offline=1/.test(document.cookie))return false}catch(e){}return d.get.call(this)}})}catch(e){}})();"""
NAV_JS = r"""(()=>{window.__qaNav=(window.__qaNav||0);})();"""


class Env(f04.Env):
    def __init__(self, browser, server):
        f02.Env.__init__(self, browser, server)
        self.backend = F20Backend()

    def new_device(self, name="A", **kw):
        d = super().new_device(name, **kw)
        d.ctx.add_init_script(OFFLINE_JS)
        d.navs = []
        d.page.on("framenavigated", lambda fr, _d=d: _d.navs.append(fr.url) if fr == _d.page.main_frame else None)
        return d


@pytest.fixture(scope="session")
def server():
    s = f02.Server()
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
    server.overrides.clear()
    e = Env(browser, server)
    yield e
    e.close()
    server.overrides.clear()


# =====================================================================================================
# Source helpers (flag flips, main reference)
# =====================================================================================================
def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def main_html():
    r = subprocess.run(["git", "-C", str(REPO_DIR), "show", "%s:app/index.html" % MAIN_REF], capture_output=True)
    assert r.returncode == 0, "harness: cannot read %s:app/index.html: %s" % (MAIN_REF, r.stderr.decode()[:200])
    html = r.stdout.decode("utf-8")
    assert "const APP_VERSION='3.0.0-alpha.4.2'" in html, "harness: %s is not alpha.4.2" % MAIN_REF
    return html


FLAGS = {
    "SWITCH_FEATURE": re.compile(r"""(const\s+SWITCH_FEATURE\s*=\s*)(['"])(on|off)\2"""),
    "WIZARD_FEATURE": re.compile(r"""(const\s+WIZARD_FEATURE\s*=\s*)(['"])(on|off)\2"""),
    "ADMIN_FEATURE": re.compile(r"""(const\s+ADMIN_FEATURE\s*=\s*)(['"])(on|off)\2"""),
    "HOME_MIN": re.compile(r"""(const\s+HOME_MIN\s*=\s*)(['"])(on|off)\2"""),
    "HOME_LAYOUT": re.compile(r"""((?:let|const|var)\s+HOME_LAYOUT\s*=\s*)(['"])(v1|v2)\2"""),
}


def flag_value(name, src=None):
    m = FLAGS[name].search(src if src is not None else app_html())
    return m.group(3) if m else None


def serve_flags(env, **flags):
    """Serve the app with top-level flags flipped (static copy through Server.overrides)."""
    src = app_html()
    for k, v in flags.items():
        if v is None:
            continue
        assert FLAGS[k].search(src), "harness: top-level %s not found in app/index.html" % k
        src = FLAGS[k].sub(lambda m, _v=v: m.group(1) + "'" + _v + "'", src, count=1)
    env.server.overrides[APP_PATH] = src.encode("utf-8")


# =====================================================================================================
# Dataset (newest membership first: NEW, NOFLAG, MID, OLD)
# =====================================================================================================
TRIPS = {
    # key: (trips.name, start, end, role, joined_at, countries [(code, sort)], other active members, display name)
    "NEW": ("חורף בתאילנד", "2026-12-28", "2027-01-05", "manager", "2026-09-01T10:00:00+00:00", [("VN", 1), ("TH", 0)], 3, "אור"),
    "NOFLAG": ("טיול בלי יעד", "2026-11-01", "2026-11-03", "manager", "2026-07-01T10:00:00+00:00", [], 1, "בני"),
    "MID": ("יפן 2027", "2027-04-03", "2027-04-20", "editor", "2026-05-01T10:00:00+00:00", [("JP", 0), ("KR", 1)], 2, "גלי"),
    "OLD": ("פורטוגל 2026", "2026-08-01", "2026-08-12", "viewer", "2026-01-01T10:00:00+00:00", [("PT", 0)], 0, "דנה"),
}
ORDER = ["NEW", "NOFLAG", "MID", "OLD"]
SUBS = {  # spec §1.1 sub line (dev notes §4: different years → full dates on both sides; 1 member → "חבר אחד")
    "NEW": "מנהל · 28/12/2026–05/01/2027 · 4 חברים",
    "NOFLAG": "מנהל · 01/11–03/11/2026 · 2 חברים",
    "MID": "עורך · 03/04–20/04/2027 · 3 חברים",
    "OLD": "צופה · 01/08–12/08/2026 · חבר אחד",
}
SHEET_SUBS = {"NEW": "מנהל · 28/12–05/01", "NOFLAG": "מנהל · 01/11–03/11", "MID": "עורך · 03/04–20/04", "OLD": "צופה · 01/08–12/08"}


def make_trips(be, keys=ORDER, foreign=True):
    """Create the trips + their other members; return {key: trip_id}. The device's memberships are added on sign-in."""
    ids = {}
    for k in keys:
        name, start, end, role, joined, countries, others, display = TRIPS[k]
        tid = be.add_trip(name)
        be.rows["trips"][(tid,)].update({"name": name, "start_date": start, "end_date": end})
        for code, sort in countries:     # inserted in a non-sorted order on purpose (VN before TH)
            be.rows["trip_countries"][(tid, code)] = {"trip_id": tid, "country_code": code, "sort": sort}
        for i in range(others):
            be.add_member(tid, "00000000-0000-4000-8000-%012d" % (len(be.rows["trip_members"]) + 1), "editor", "active", "חבר%d" % i)
        if k == "NEW":   # a pending and a removed member are not counted
            be.add_member(tid, "00000000-0000-4000-8000-%012d" % 900001, "editor", "pending", "ממתין")
            be.add_member(tid, "00000000-0000-4000-8000-%012d" % 900002, "viewer", "removed", "הוסר")
        be.set_kv(tid, "tripname", name)
        ids[k] = tid
        be.links.append({"trip_id": tid, "role": role, "display_name": display, "joined_at": joined})
    if foreign:  # not a member: never listed (criterion 13)
        fid = be.add_trip_full("טיול זר", "2026-10-01", "2026-10-09", countries=["GR"], managers=["זר"])
        be.set_kv(fid, "tripname", "טיול זר")
        rid = be.add_trip_full("טיול שהוסרתי ממנו", "2026-10-01", "2026-10-09", countries=["IT"], managers=["זר2"])
        be.links.append({"trip_id": rid, "role": "editor", "display_name": "הוסרתי", "status": "removed",
                         "joined_at": "2026-09-30T10:00:00+00:00"})
        ids["_foreign"], ids["_removed"] = fid, rid
    return ids


def setup(env, keys=ORDER, admin=True, email=None, confirmed=False, cached=None, d3=False, invites=True, foreign=True):
    be = env.backend
    ids = make_trips(be, keys, foreign)
    be.auto_link = None
    be.auto_admin = admin
    if email:
        if confirmed:
            be.auto_confirmed_email = email
        else:
            be.auto_email = email
    if invites:
        be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
        be.add_invite("p2@example.com", None, sent_days_ago=2, expires_in_days=5)
        be.add_invite("exp@example.com", "פג", sent_days_ago=10, expires_in_days=-3)
        be.add_invite("rev@example.com", "בוטל", sent_days_ago=3, expires_in_days=4, revoked=True)
        be.add_invite("used@example.com", "נוצל", sent_days_ago=4, expires_in_days=3, used=True)
    pre = {}
    if cached:
        tid = ids[cached]
        pre[CACHE_KEY] = json.dumps({"trip_id": tid, "role": TRIPS[cached][3]})
    if d3:
        pre[D3_KEY] = "1"
    return ids, pre


def device(env, pre=None, name="A", offline=False):
    dev = env.new_device(name)
    if pre:
        dev.seed_ls(pre)
    if offline:
        set_offline_cookie(dev, True)
    return dev


def set_offline_cookie(dev, on):
    if on:
        dev.ctx.add_cookies([{"name": "qa_offline", "value": "1", "url": dev.env.server.origin}])
    else:
        dev.ctx.clear_cookies()


# =====================================================================================================
# UI helpers
# =====================================================================================================
find, click_text, visible, wait_text, gone = f03.find, f03.click_text, f03.visible, f03.wait_text, f03.gone
body_text, chrome_visible, norm, btext, has, wait_has = f03.body_text, f03.chrome_visible, f04.norm, f04.btext, f04.has, f04.wait_has
layout_problems = f04.layout_problems

STATE_JS = """(nc)=>{const vis=e=>{if(!e)return false;const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
  for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden')return false}return true};
 if(vis(document.getElementById('ptChoose')))return 'choose';
 const ad=document.getElementById('admin');
 if(document.documentElement.classList.contains('pt-admin-open')&&vis(ad))return 'admin';
 const started=!window.__PT||window.__PT.started===true;
 for(const id of ['homeV2','home']){const h=document.getElementById(id);if(started&&h&&h.classList.contains('active')&&getComputedStyle(h).display!=='none')return 'app'}
 if(document.body&&document.body.innerText.includes(nc))return 'nc';return null}"""


def state(page):
    try:
        return page.evaluate(STATE_JS, NC_TITLE)
    except PWError:
        return None


def wait_state(page, want=None, timeout=20.0):
    end = time.time() + timeout
    s = None
    while time.time() < end:
        s = state(page)
        if s and (want is None or s == want or (isinstance(want, (list, tuple, set)) and s in want)):
            page.wait_for_timeout(500)
            return state(page) or s
        page.wait_for_timeout(150)
    return s


def boot(dev, path=APP_PATH, want=None, timeout=20.0):
    dev.page.goto(dev.env.server.origin + path, wait_until="domcontentloaded")
    s = wait_state(dev.page, want, timeout)
    if s == "app":
        f02.ensure_user(dev.page)
    return s


def cur_url(page):
    return page.evaluate("()=>location.href")


def mark_page(page):
    page.evaluate("()=>{window.__qaStay=1}")


def same_document(page):
    try:
        return page.evaluate("()=>window.__qaStay===1")
    except PWError:
        return False


def wait_reloaded(page, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if page.evaluate("()=>window.__qaStay!==1&&document.readyState!=='loading'"):
                return True
        except PWError:
            pass
        page.wait_for_timeout(150)
    return False


def ls_raw(dev):
    return dev.ls()


def cached_trip(dev):
    raw = ls_raw(dev).get(CACHE_KEY)
    try:
        return json.loads(raw).get("trip_id") if raw else None
    except Exception:
        return raw


def trip_shown(page):
    return page.evaluate("()=>{const e=document.getElementById('tripName');return e?e.textContent.trim():null}")


def trip_id_running(page):
    try:
        return page.evaluate("()=>window.__PT&&window.__PT.started?window.__PT.tripId:null")
    except PWError:
        return None


def wait_trip_shown(page, name, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if trip_shown(page) == name:
            return True
        page.wait_for_timeout(200)
    return False


def no_trip_started(page):
    """dev notes §4: __PT.phase / __PT.started === false, tripData undefined (spec AC2: 'e.g. tripData undefined')."""
    return page.evaluate("""()=>({started:window.__PT?window.__PT.started:'n/a',phase:window.__PT?window.__PT.phase:'n/a',
      tripData:typeof tripData,homeActive:['homeV2','home'].some(id=>{const h=document.getElementById(id);return !!h&&h.classList.contains('active')&&getComputedStyle(h).display!=='none'})})""")


def page_errors(dev):
    noise = ("Failed to load resource", "net::ERR_", "favicon")
    return dev.errors + [c for c in dev.console if c.startswith("error:") and not any(n in c for n in noise)]


def kv_queries_since(be, n, device=None):
    return [c for c in be.queries("trip_kv")[n:] if device is None or c["device"] == device]


def choose_rows(page):
    return page.evaluate("""(sel)=>[...document.querySelectorAll(sel)].map(b=>{const f=b.querySelector('.pt-f20-flag');
      const s=b.querySelector('.pt-f20-sub');const n=b.querySelector('b');const r=b.getBoundingClientRect();
      return {id:b.getAttribute('data-trip'),name:n?n.textContent.trim():null,sub:s?s.textContent:null,
        flag:f?f.textContent.trim():null,flagSvg:!!(f&&f.querySelector('svg')),last:!!b.querySelector('#ptChooseLastBadge'),
        text:b.innerText,w:r.width,h:r.height,vis:r.width>0&&r.height>0}})""", SEL["choose_card"])


def sheet_rows(page):
    return page.evaluate("""()=>[...document.querySelectorAll('#ptSwitchTrips .pt-f20-row')].map(b=>{const r=b.getBoundingClientRect();
      const svg=b.querySelector('svg[role=img]');return {tag:b.tagName,id:b.getAttribute('data-trip'),cur:b.getAttribute('data-trip-current'),
        ariaCur:b.getAttribute('aria-current'),check:svg?svg.getAttribute('aria-label'):null,text:b.innerText,
        sub:(b.querySelector('.pt-f20-sub')||{}).textContent||null,w:r.width,h:r.height}})""")


def is_vis(page, sel):
    return page.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();
      if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);
      if(c.display==='none'||c.visibility==='hidden'||a.hidden)return false}return true}""", sel)


def exists(page, sel):
    return page.evaluate("(s)=>!!document.querySelector(s)", sel)


def open_sheet(page, sel=None):
    sel = sel or SEL["avatar_any"]
    btn = page.locator(sel).filter(visible=True)
    assert btn.count(), "avatar button %s not visible" % sel
    btn.first.click()
    end = time.time() + 6
    while time.time() < end and not is_vis(page, SEL["sheet_box"]):
        page.wait_for_timeout(150)
    assert is_vis(page, SEL["sheet_box"]), "sheet #ptF20SheetBox did not open"
    end = time.time() + 8
    while time.time() < end and not page.evaluate("()=>!!document.querySelector('#ptSwitchTrips .pt-f20-row')"):
        page.wait_for_timeout(150)
    page.wait_for_timeout(300)


def ensure_home(page):
    f02.ensure_user(page)
    try:
        f02.tab(page, "home")
    except PWError:
        pass
    page.wait_for_timeout(300)


def enter_from_chooser(dev, tid):
    page = dev.page
    page.locator('%s[data-trip="%s"]' % (SEL["choose_card"], tid)).click()
    s = wait_state(page, "app", 20)
    f02.ensure_user(page)
    return s


def visible_texts_with(page, needle):
    return page.evaluate("""(t)=>[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();
      return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.includes(t))})
      .map(e=>e.textContent.trim().slice(0,80))""", needle)


def dup_ids(page):
    return page.evaluate("""()=>{const c={};document.querySelectorAll('[id]').forEach(e=>{c[e.id]=(c[e.id]||0)+1});
      return Object.keys(c).filter(k=>c[k]>1)}""")


# =====================================================================================================
# §1.4 boot rules (criteria 1, 2, 5, 6, 10, 11)
# =====================================================================================================
def test_b01_superadmin_online_sees_chooser_no_trip_started(env):
    """AC2 + §1.1: super-admin, online, D3 off → #ptChoose; no tab bar / chat / FX pill; html.pt-choose; the trip main script
    has not started (__PT.started false, tripData undefined, home not active, no trip_kv read); brand + title; the
    mockup footnote is not shipped; no page errors."""
    ids, pre = setup(env)
    dev = device(env, pre)
    page, be = dev.page, env.backend
    st = boot(dev)
    assert st == "choose", "super-admin did not land on the chooser (state=%s, text=%r)" % (st, btext(page)[:200])
    page.wait_for_timeout(1500)
    P = []
    nt = no_trip_started(page)
    if nt["started"] is not False or nt["tripData"] != "undefined" or nt["homeActive"] or nt["phase"] != "choose":
        P.append("trip main script ran on the chooser: %r" % nt)
    if be.queries("trip_kv"):
        P.append("trip_kv read on the chooser: %d" % len(be.queries("trip_kv")))
    if chrome_visible(page):
        P.append("trip chrome visible on the chooser: %r" % chrome_visible(page))
    if not page.evaluate("()=>document.documentElement.classList.contains('pt-choose')"):
        P.append("html.pt-choose not set")
    title = page.evaluate("()=>{const e=document.querySelector('#ptChooseTitle');return e?e.textContent:null}")
    if norm(title) != norm(TXT["title"].format(name="אור")):
        P.append("title %r, expected %r (display name of the newest membership)" % (title, TXT["title"].format(name="אור")))
    if not has(page, TXT["brand"]):
        P.append("brand %r missing" % TXT["brand"])
    for k in ("sec_admin", "admin_row", "admin_row_sub", "sec_trips", "d3"):
        if not has(page, TXT[k]):
            P.append("%r missing" % TXT[k])
    if has(page, TXT["footnote"]):
        P.append("mockup footnote shipped")
    if page.evaluate("()=>window.__qaWatch.sawNotConnected"):
        P.append("not-connected card was shown")
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("n", [1, 2])
def test_b02_non_admin_boots_trip_unchanged(env, n):
    """D4 / §1.4: not a super-admin → no chooser, boots the newest membership (no cache) as alpha.4.2."""
    ids, pre = setup(env, keys=ORDER[:n], admin=False, invites=False)
    dev = device(env, pre)
    st = boot(dev)
    P = []
    if st != "app":
        P.append("non-admin did not boot into a trip (state=%s)" % st)
    if exists(dev.page, SEL["choose"]) and is_vis(dev.page, SEL["choose"]):
        P.append("chooser shown to a non-admin")
    if st == "app" and not wait_trip_shown(dev.page, TRIPS[ORDER[0]][0]):
        P.append("not the newest membership: %r" % trip_shown(dev.page))
    if any(c["msg"].get("fn") == "admin_trip_summary" for c in env.backend.rpcs()):
        P.append("admin_trip_summary called for a non-admin")
    assert not P, "\n".join(P)


def test_b03_switch_off_is_alpha42(env):
    """AC1 (F20 part): SWITCH_FEATURE='off' → super-admin boots the trip (no chooser, no #ptChoose in the DOM), no avatar,
    'עוד' still has the F03 row 'ניהול מערכת' (#ptAdminRow) and #admin opens the F03 admin screen with 'חזרה לטיול'."""
    serve_flags(env, SWITCH_FEATURE="off")
    ids, pre = setup(env, email="or@example.com")
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    P = []
    if st != "app":
        pytest.fail("'off': super-admin did not boot into a trip (state=%s)" % st)
    if exists(page, SEL["choose"]):
        P.append("'off': #ptChoose in the DOM")
    if exists(page, SEL["avatar_any"]):
        P.append("'off': avatar button in the DOM")
    f03.open_more(page)
    if not wait_text(page, TXT["admin_row"]) or not exists(page, SEL["more_admin_row"]):
        P.append("'off': F03 row 'ניהול מערכת' (#ptAdminRow) missing in 'עוד'")
    else:
        f03.click_text(page, TXT["admin_row"])
        if not wait_text(page, TXT["admin_invite_btn"]):
            P.append("'off': F03 admin screen did not open from 'עוד'")
        if not find(page, f03.SEL["back_aria"], SEL["admin"]):
            P.append("'off': admin back control (aria 'חזרה…') missing")
        if exists(page, SEL["admin_switch"]):
            P.append("'off': F20 'הטיולים שלי' button on the admin header")
    assert not P, "\n".join(P)


def test_b04_hash_admin_superadmin_standalone(env):
    """AC5 + §1.2: opening at #admin as super-admin → standalone admin: no trip started, no trip chrome, header has
    'הטיולים שלי' and no 'חזרה לטיול', subtitle 'Lonely Planner · סופר-אדמין', the F03 list loads, hash stays #admin."""
    ids, pre = setup(env)
    dev = device(env, pre)
    page, be = dev.page, env.backend
    st = boot(dev, APP_PATH + "#admin")
    assert st == "admin", "#admin did not open the standalone admin (state=%s, text=%r)" % (st, btext(page)[:200])
    page.wait_for_timeout(1200)
    P = admin_header_problems(page)
    nt = no_trip_started(page)
    if nt["started"] is not False or nt["tripData"] != "undefined" or nt["homeActive"]:
        P.append("a trip started under the standalone admin: %r" % nt)
    if be.queries("trip_kv"):
        P.append("trip_kv read on the standalone admin")
    if not wait_text(page, TXT["admin_invite_btn"]):
        P.append("F03 admin body missing (%r)" % TXT["admin_invite_btn"])
    if not any(c["msg"].get("fn") == "admin_trip_summary" for c in be.rpcs()):
        P.append("admin_trip_summary not called")
    if "#admin" not in cur_url(page):
        P.append("hash is not #admin: %s" % cur_url(page))
    assert not P, "\n".join(P)


def admin_header_problems(page):
    P = []
    if chrome_visible(page):
        P.append("trip chrome visible on the admin screen: %r" % chrome_visible(page))
    if not is_vis(page, SEL["admin_switch"]) or norm(page.locator(SEL["admin_switch"]).first.inner_text()) != TXT["admin_switch"]:
        P.append("header button 'הטיולים שלי' (#ptAdminSwitch) missing")
    if exists(page, SEL["admin_back"]) or visible(page, TXT["admin_back_old"], SEL["admin"]) or find(page, TXT["admin_back_old"]):
        P.append("'חזרה לטיול' still on the admin header")
    sub = page.evaluate("(s)=>{const e=document.querySelector(s);return e?e.textContent:null}", SEL["admin_sub"])
    if norm(sub) != TXT["admin_sub"]:
        P.append("admin subtitle %r, expected %r" % (sub, TXT["admin_sub"]))
    if not is_vis(page, SEL["admin_title"]) or norm(page.locator(SEL["admin_title"]).inner_text()) != TXT["admin_row"]:
        P.append("admin title 'ניהול מערכת' missing")
    return P


def test_b05_hash_admin_non_admin_boots_trip_hash_cleaned(env):
    """AC5: a non-admin opening #admin boots normally into their trip; the hash is cleaned; no admin UI."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    st = boot(dev, APP_PATH + "#admin")
    P = []
    if st != "app":
        P.append("non-admin at #admin did not boot the trip (state=%s)" % st)
    page.wait_for_timeout(800)
    if "#admin" in cur_url(page):
        P.append("hash not cleaned: %s" % cur_url(page))
    if visible(page, TXT["admin_invite_btn"]) or visible(page, TXT["admin_sub"]):
        P.append("admin UI visible to a non-admin")
    assert not P, "\n".join(P)


def test_b06_choose_query_shows_chooser_ignoring_d3_and_is_removed(env):
    """§1.4 + AC6: super-admin with D3 on and a cached trip opening ?choose=1 → chooser (D3 ignored); the query is removed
    from the URL; the checkbox shows checked."""
    ids, pre = setup(env, cached="MID", d3=True)
    dev = device(env, pre)
    page = dev.page
    st = boot(dev, APP_PATH + "?choose=1")
    P = []
    if st != "choose":
        pytest.fail("?choose=1 with D3 on did not show the chooser (state=%s)" % st)
    page.wait_for_timeout(500)
    if "choose" in urlparse(cur_url(page)).query:
        P.append("?choose=1 not removed: %s" % cur_url(page))
    if not page.locator(SEL["d3"]).is_checked():
        P.append("D3 checkbox not checked although the key is set")
    assert not P, "\n".join(P)


def test_b07_d3_on_enters_cached_trip_directly(env):
    """§1.4: super-admin, D3 on, cached trip active → straight into the cached trip; the switcher (avatar) is available."""
    ids, pre = setup(env, cached="MID", d3=True)
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    P = []
    if st != "app":
        pytest.fail("D3 on: did not enter the cached trip (state=%s)" % st)
    if not wait_trip_shown(page, TRIPS["MID"][0]):
        P.append("D3 on: not the cached trip: %r" % trip_shown(page))
    ensure_home(page)
    if not page.locator(SEL["avatar_any"]).filter(visible=True).count():
        P.append("D3 on: avatar (switcher) not shown to the super-admin")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("who", ["superadmin", "non_admin"])
def test_b08_offline_boot_with_cached_trip(env, who):
    """AC10 / §1.4: offline (navigator.onLine false, backend unreachable) with a cached trip → the cached trip; no chooser;
    no not-connected card; no error text."""
    ids, pre = setup(env, admin=(who == "superadmin"), invites=False)
    dev = device(env, pre)
    page = dev.page
    st = boot(dev, want=["choose", "app"]) if who == "superadmin" else boot(dev, want="app")
    if who == "superadmin":
        assert st == "choose", "harness: online first boot (state=%s)" % st
        assert enter_from_chooser(dev, ids["MID"]) == "app"
    else:
        assert st == "app"
    key = "MID" if who == "superadmin" else "NEW"
    want = TRIPS[key][0]
    assert wait_trip_shown(page, want), "harness: entered trip %r" % trip_shown(page)
    assert trip_id_running(page) == ids[key], "harness: __PT.tripId"
    assert cached_trip(dev) == ids[key], "harness: cache %r" % cached_trip(dev)
    set_offline_cookie(dev, True)
    env.backend.mode = "down"
    page.evaluate("()=>{window.__qaWatch&&(window.__qaWatch.sawNotConnected=false)}")
    st2 = boot(dev)
    P = []
    if st2 != "app":
        P.append("offline boot did not enter the cached trip (state=%s)" % st2)
    elif trip_id_running(page) != ids[key]:
        P.append("offline boot: not the cached trip (running %r)" % trip_id_running(page))
    if page.evaluate("()=>window.__qaWatch.sawNotConnected"):
        P.append("not-connected card shown offline")
    if exists(page, SEL["choose"]) and is_vis(page, SEL["choose"]):
        P.append("chooser shown offline")
    if visible(page, TXT["load_err"]):
        P.append("error text shown offline")
    assert not P, "\n".join(P)


def test_b09_admin_check_failure_normal_boot_no_error(env):
    """AC11: platform_admins check fails (network) → behave as not super-admin: normal boot into the trip, no chooser, no
    error shown, no page errors."""
    ids, pre = setup(env)
    env.backend.fail_tables = {"platform_admins"}
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    P = []
    if st != "app":
        P.append("admin check failure: no normal boot (state=%s)" % st)
    if exists(page, SEL["choose"]) and is_vis(page, SEL["choose"]):
        P.append("chooser shown although the admin check failed")
    if page.evaluate("()=>window.__qaWatch.sawNotConnected"):
        P.append("not-connected card shown")
    for t in ("שגיאה", TXT["load_err"], "לא הצלחנו"):
        if visible(page, t):
            P.append("error text %r shown" % t)
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    if not env.backend.queries("platform_admins"):
        P.append("harness: the admin check was not made")
    assert not P, "\n".join(P)


def _home_time(dev, path=APP_PATH, timeout=20.0):
    page = dev.page
    t0 = time.time()
    page.goto(dev.env.server.origin + path, wait_until="commit")
    end = t0 + timeout
    while time.time() < end:
        s = state(page)
        if s in ("app", "choose", "nc", "admin"):
            return s, time.time() - t0
        page.wait_for_timeout(50)
    return None, time.time() - t0


@pytest.mark.parametrize("who", ["non_admin", "superadmin"])
def test_b10_admin_check_hang_bounded(env, who):
    """§1.4 + architect decision F20-BOOT-03: a hanging platform_admins check delays boot by at most ~2.5 s and then counts
    as 'not super-admin' (normal boot into the trip, no chooser, no error). Measured from navigation to the first settled
    screen against control boots of the same device (no hang): added delay ≤ 3.0 s."""
    ids, pre = setup(env, cached="MID", invites=False, admin=(who == "superadmin"))
    be = env.backend
    dev = device(env, pre)
    s0, _ = _home_time(dev)
    assert s0 in ("app", "choose"), "harness: control boot (state=%s)" % s0
    f02.ensure_user(dev.page)
    times = []
    for _ in range(2):
        s, t = _home_time(dev)
        times.append(t)
    base = min(times)
    be.hang_tables = {"platform_admins"}
    s, t = _home_time(dev, timeout=15)
    P = []
    if s != "app":
        P.append("hanging admin check: state=%s after %.1f s (expected the trip)" % (s, t))
    elif t - base > 3.0:
        P.append("hanging admin check delayed boot by %.2f s (control %.2f s, hung %.2f s) > 3.0 s" % (t - base, base, t))
    dev.page.wait_for_timeout(500)
    if exists(dev.page, SEL["choose"]) and is_vis(dev.page, SEL["choose"]):
        P.append("chooser shown with a hanging admin check")
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    print("%s: control boot %.2f s (first screen %s), hung admin check %.2f s -> %s" % (who, base, s0, t, s))
    assert not P, "\n".join(P)


def test_b15_non_admin_admin_check_runs_in_parallel(env):
    """§1.4: 'total added boot delay for a non-admin ≤ one round trip (the check may run in parallel with fetchTrips)'.
    Every trip_members read takes 1.5 s; with platform_admins ALSO taking 1.5 s the boot may not get longer by more than
    ~one round trip (0.8 s tolerance here) — a serial check would add 1.5 s."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    be = env.backend
    dev = device(env, pre)
    s0, _ = _home_time(dev)
    assert s0 == "app"
    f02.ensure_user(dev.page)
    be.delay_tables = {"trip_members": 1500}
    ctrl = min(_home_time(dev)[1] for _ in range(2))
    be.delay_tables = {"trip_members": 1500, "platform_admins": 1500}
    s, t = _home_time(dev)
    print("trip_members slow: %.2f s; trip_members + platform_admins slow: %.2f s" % (ctrl, t))
    assert s == "app", "state=%s" % s
    assert t - ctrl <= 0.8, "admin check adds %.2f s for a non-admin (serial with fetchTrips?)" % (t - ctrl)


MAPS_STUB = "window.__qaMaps=typeof window.initMap;setTimeout(function(){if(typeof window.initMap==='function')window.initMap()},0);"


def test_b14_maps_callback_on_chooser_harmless(env):
    """Regression guard (not in the spec text): the static Google Maps <script …callback=initMap> also loads on the chooser,
    before the trip main script ran. Its callback must not throw there, and entering a trip afterwards still works."""
    ids, pre = setup(env, invites=False)
    dev = device(env, pre)
    dev.ctx.route("https://maps.googleapis.com/maps/api/js**",
                  lambda r: r.fulfill(status=200, content_type="application/javascript", body=MAPS_STUB))
    page = dev.page
    assert boot(dev) == "choose"
    page.wait_for_timeout(1500)
    P = []
    if page_errors(dev):
        P.append("errors on the chooser after the Maps callback: %r" % page_errors(dev)[:3])
    if enter_from_chooser(dev, ids["MID"]) != "app" or trip_id_running(page) != ids["MID"]:
        P.append("entering a trip after the Maps callback failed")
    page.wait_for_timeout(1000)
    if page_errors(dev):
        P.append("errors after entering: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_b11_superadmin_without_trips_sees_chooser_none(env):
    """§1.4: super-admin with no trips → chooser with the admin row and 'אין עדיין טיולים' (no trip rows), not the
    not-connected card; title without a name."""
    be = env.backend
    be.auto_link, be.auto_admin = None, True
    dev = device(env)
    page = dev.page
    st = boot(dev)
    P = []
    if st != "choose":
        pytest.fail("super-admin without trips: state=%s (text=%r)" % (st, btext(page)[:200]))
    page.wait_for_timeout(1200)
    if not is_vis(page, SEL["choose_none"]) or norm(page.locator(SEL["choose_none"]).inner_text()) != TXT["none"]:
        P.append("'%s' missing" % TXT["none"])
    if choose_rows(page):
        P.append("trip rows shown: %r" % choose_rows(page))
    if not is_vis(page, SEL["choose_admin"]):
        P.append("admin row missing")
    title = page.evaluate("()=>{const e=document.querySelector('#ptChooseTitle');return e?e.textContent:null}")
    if norm(title) != TXT["title_anon"]:
        P.append("title %r, expected %r" % (title, TXT["title_anon"]))
    if page.evaluate("()=>window.__qaWatch.sawNotConnected"):
        P.append("not-connected card shown")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("dest", ["trip_query", "invite"])
def test_b12_destination_paths_skip_chooser(env, dest):
    """§1.1/§1.4: opened for a specific destination (?trip=, #invite=) → no chooser for the super-admin."""
    ids, pre = setup(env, invites=False)
    be = env.backend
    dev = device(env, pre)
    page = dev.page
    if dest == "trip_query":
        st = boot(dev, APP_PATH + "?trip=" + ids["MID"])
        assert st == "app", "?trip=: state=%s" % st
    else:
        iid, token = be.add_invite(f04.INVITE_EMAIL, f04.DRAFT, sent_days_ago=0, expires_in_days=7)
        page.goto(env.server.origin + APP_PATH + "?invite=1#invite=" + token, wait_until="domcontentloaded")
        sc = f04.wait_screen(page, ["code", "step1", "d6", "other_acct", "email", "no_invite"], 15)
        assert sc in ("code", "step1", "d6", "other_acct", "email", "no_invite"), "invite link: F04 flow not shown (screen=%s)" % sc
    page.wait_for_timeout(800)
    assert not (exists(page, SEL["choose"]) and is_vis(page, SEL["choose"])), "chooser shown for %s" % dest


def test_b13_admin_feature_off_no_chooser_switcher_lists_trips(env):
    """§1 'with ADMIN_FEATURE=off there is no admin': super-admin row exists but no chooser and no admin section; the
    switcher still lists trips (≥2 trips)."""
    serve_flags(env, ADMIN_FEATURE="off")
    ids, pre = setup(env, keys=ORDER[:2])
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    P = []
    if st != "app":
        pytest.fail("ADMIN off: super-admin did not boot a trip (state=%s)" % st)
    ensure_home(page)
    if not page.locator(SEL["avatar_any"]).filter(visible=True).count():
        pytest.fail("ADMIN off: no avatar for a user with 2 trips")
    open_sheet(page)
    if exists(page, SEL["sw_admin"]) and is_vis(page, SEL["sw_admin"]):
        P.append("ADMIN off: 'ניהול מערכת' in the sheet")
    if len(sheet_rows(page)) != 2:
        P.append("ADMIN off: sheet rows %r" % sheet_rows(page))
    assert not P, "\n".join(P)


# =====================================================================================================
# §1.1 chooser content (criteria 3, 6)
# =====================================================================================================
def test_c01_chooser_rows_order_content_flags_last_badge(env):
    """AC3 + §1.1: all active memberships newest first (not the foreign / removed trip), name = trips.name, sub
    '<תפקיד> · dd/mm–dd/mm/yyyy · <N> חברים' (N = active members; 'חבר אחד'), flag of the trip_countries sort-0 country
    (pin svg when none), 'אחרון' on the cached trip only, admin row with sub; rows ≥44px."""
    ids, pre = setup(env, cached="MID")
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    end = time.time() + 8
    while time.time() < end and len(choose_rows(page)) < 4:
        page.wait_for_timeout(200)
    rows = choose_rows(page)
    P = []
    got = [r["id"] for r in rows]
    want = [ids[k] for k in ORDER]
    if got != want:
        names = {v: k for k, v in ids.items()}
        P.append("rows %r, expected %r" % ([names.get(i, i) for i in got], ORDER))
    for k in ORDER:
        r = next((x for x in rows if x["id"] == ids[k]), None)
        if not r:
            continue
        if r["name"] != TRIPS[k][0]:
            P.append("%s: name %r" % (k, r["name"]))
        if norm(r["sub"]) != norm(SUBS[k]):
            P.append("%s: sub %r, expected %r" % (k, r["sub"], SUBS[k]))
        countries = sorted(TRIPS[k][5], key=lambda c: c[1])
        if countries:
            if r["flag"] != flag(countries[0][0]):
                P.append("%s: flag %r, expected %r (sort 0 country)" % (k, r["flag"], flag(countries[0][0])))
        elif not r["flagSvg"] or re.search("[\U0001F1E6-\U0001F1FF]", r["flag"] or ""):
            P.append("%s: no-country trip should show the pin svg (flag=%r svg=%s)" % (k, r["flag"], r["flagSvg"]))
        if r["last"] != (k == "MID"):
            P.append("%s: 'אחרון' badge = %s" % (k, r["last"]))
        if r["h"] < 44 or r["w"] < 44:
            P.append("%s: row %dx%d < 44" % (k, r["w"], r["h"]))
    lb = page.evaluate("(s)=>[...document.querySelectorAll(s)].map(e=>e.textContent.trim())", SEL["choose_last"])
    if lb != [TXT["last"]]:
        P.append("'אחרון' badges: %r" % lb)
    if has(page, "טיול זר") or has(page, "טיול שהוסרתי ממנו"):
        P.append("a trip without an active membership is listed")
    adm = page.locator(SEL["choose_admin"])
    if not adm.count() or TXT["admin_row_sub"] not in norm(adm.inner_text()) or TXT["admin_row"] not in norm(adm.inner_text()):
        P.append("admin row texts missing")
    assert not P, "\n".join(P)


def test_c01b_no_cached_trip_no_last_badge(env):
    """§1.1: the badge 'אחרון' only when the cached trip is in the list (no cache → none; a cached foreign trip → none)."""
    ids, pre = setup(env)
    dev = device(env, {CACHE_KEY: json.dumps({"trip_id": "11111111-1111-4111-8111-111111111111", "role": "editor"})})
    page = dev.page
    st = boot(dev)
    assert st == "choose", "state=%s" % st
    page.wait_for_timeout(1500)
    assert not exists(page, SEL["choose_last"]), "'אחרון' shown although the cached trip is not in the list"


@pytest.mark.parametrize("case", ["two", "zero", "rpc_fail"])
def test_c02_pending_badge(env, case):
    """AC3 + §1.1: badge '<N> ממתינות' (pending invites only, not expired/revoked/used) when N>0; omitted when 0 or when
    admin_trip_summary fails."""
    ids, pre = setup(env, invites=(case != "zero"))
    be = env.backend
    if case == "zero":
        be.add_invite("exp@example.com", "פג", sent_days_ago=10, expires_in_days=-3)
    be.rpc_fail = case == "rpc_fail"
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    page.wait_for_timeout(2000)
    vis = is_vis(page, SEL["choose_pending"])
    if case == "two":
        assert vis, "pending badge not shown (2 pending invites)"
        t = norm(page.locator(SEL["choose_pending"]).inner_text())
        assert t == TXT["pending"].format(n=2), "badge %r, expected %r" % (t, TXT["pending"].format(n=2))
    else:
        assert not vis and not has(page, "ממתינות"), "badge shown for case %s" % case
        assert is_vis(page, SEL["choose_admin"]), "admin row missing for case %s" % case
    assert any(c["msg"].get("fn") == "admin_trip_summary" for c in be.rpcs()), "admin_trip_summary not called"


def test_c03_loading_state(env):
    """§1.1: while the trip details load: header + admin row shown, trips section shows 'טוענים…' (aria-busy)."""
    ids, pre = setup(env)
    env.backend.hang_tables = {"trips"}
    dev = device(env, pre)
    page = dev.page
    st = boot(dev, timeout=15)
    P = []
    if st != "choose":
        pytest.fail("trips query hanging: state=%s (text=%r)" % (st, btext(page)[:200]))
    page.wait_for_timeout(800)
    if not is_vis(page, SEL["choose_loading"]) or norm(page.locator(SEL["choose_loading"]).inner_text()) != TXT["loading"]:
        P.append("'טוענים…' missing")
    busy = page.evaluate("()=>{const e=document.querySelector('#ptChooseLoading');return e&&(e.getAttribute('aria-busy')||(e.closest('[aria-busy]')||{}).getAttribute&&e.closest('[aria-busy]').getAttribute('aria-busy'))}")
    if str(busy) != "true":
        P.append("aria-busy not set while loading (%r)" % busy)
    if not is_vis(page, SEL["choose_admin"]) or not is_vis(page, SEL["choose_title"]):
        P.append("header / admin row not shown while loading")
    if choose_rows(page):
        P.append("rows shown while loading")
    assert not P, "\n".join(P)


def test_c03b_load_failure_and_retry(env):
    """§1.1: a failure of the details load shows 'לא הצלחנו לטעון את הטיולים. נסו שוב.' + 'נסו שוב'; retry after the
    network is back lists the trips."""
    ids, pre = setup(env)
    be = env.backend
    be.fail_tables = {"trips"}
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    if st != "choose":
        pytest.fail("trips query failing: state=%s (text=%r)" % (st, btext(page)[:200]))
    end = time.time() + 8
    while time.time() < end and not is_vis(page, SEL["choose_err"]):
        page.wait_for_timeout(200)
    P = []
    if not is_vis(page, SEL["choose_err"]) or TXT["load_err"] not in norm(page.locator(SEL["choose_err"]).inner_text()):
        P.append("error text %r missing" % TXT["load_err"])
    if not is_vis(page, SEL["choose_retry"]) or norm(page.locator(SEL["choose_retry"]).inner_text()) != TXT["retry"]:
        pytest.fail("\n".join(P + ["retry button missing"]))
    be.fail_tables = set()
    page.locator(SEL["choose_retry"]).click()
    end = time.time() + 8
    while time.time() < end and len(choose_rows(page)) < 4:
        page.wait_for_timeout(200)
    if [r["id"] for r in choose_rows(page)] != [ids[k] for k in ORDER]:
        P.append("retry did not list the trips: %r" % choose_rows(page))
    if is_vis(page, SEL["choose_err"]):
        P.append("error still shown after a successful retry")
    assert not P, "\n".join(P)


def test_c04_enter_trip_without_reload(env):
    """AC3: tapping a trip enters THAT trip without a reload (same document), the trip main script starts, trip chrome
    appears, the cached trip becomes that trip, only that trip's trip_kv is read."""
    ids, pre = setup(env, cached="NEW")
    dev = device(env, pre)
    page, be = dev.page, env.backend
    assert boot(dev) == "choose"
    page.wait_for_timeout(1200)
    mark_page(page)
    n_nav = len(dev.navs)
    n_kv = len(be.queries("trip_kv"))
    st = enter_from_chooser(dev, ids["MID"])
    P = []
    if st != "app":
        pytest.fail("tapping a trip did not enter it (state=%s)" % st)
    if not same_document(page) or len(dev.navs) != n_nav:
        P.append("the page reloaded / navigated (navs %r)" % dev.navs[n_nav:])
    if not wait_trip_shown(page, TRIPS["MID"][0]) or trip_id_running(page) != ids["MID"]:
        P.append("wrong trip: %r / %r" % (trip_shown(page), trip_id_running(page)))
    if cached_trip(dev) != ids["MID"]:
        P.append("cached trip %r, expected MID" % cached_trip(dev))
    ensure_home(page)
    if sorted(chrome_visible(page)) != sorted(SEL["trip_chrome"]):
        P.append("trip chrome after entering: %r" % chrome_visible(page))
    if page.evaluate("()=>document.documentElement.classList.contains('pt-choose')"):
        P.append("html.pt-choose still set")
    nt = no_trip_started(page)
    if nt["started"] is not True or nt["tripData"] == "undefined":
        P.append("trip main script not started: %r" % nt)
    others = [ids[k] for k in ORDER if k != "MID"]
    other = [c for c in kv_queries_since(be, n_kv) if any(o in json.dumps(c["msg"]["req"].get("filters")) for o in others)]
    if other:
        P.append("trip_kv read for another trip: %r" % [c["msg"]["req"].get("filters") for c in other][:3])
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_c05_member_count_refused_omits_part(env):
    """§2: if the member-count query is not allowed, the '· N חברים' part is omitted (rows still shown, no error)."""
    ids, pre = setup(env)
    env.backend.fail_pred = lambda req: (req.get("table") == "trip_members" and any(f.get("op") == "in" for f in req.get("filters") or []))
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    end = time.time() + 8
    while time.time() < end and len(choose_rows(page)) < 4:
        page.wait_for_timeout(200)
    rows = choose_rows(page)
    P = []
    if len(rows) != 4:
        P.append("rows %r" % rows)
    for r in rows:
        if "חבר" in (r["sub"] or ""):
            P.append("member count shown although refused: %r" % r["sub"])
        if not re.match(r"^(מנהל|עורך|צופה) · \d\d/\d\d", norm(r["sub"])):
            P.append("sub lost role/dates: %r" % r["sub"])
    if is_vis(page, SEL["choose_err"]):
        P.append("error state shown")
    if not any(any(f.get("op") == "in" for f in (c["msg"]["req"].get("filters") or [])) for c in env.backend.queries("trip_members")):
        P.append("harness: no trip_members in() count query was made")
    assert not P, "\n".join(P)


def test_c06_d3_checkbox_persist_next_boot_choose_and_off(env):
    """AC6: D3 off by default (no key); checking writes pt:_device:open_last_trip="1" without navigating; next boot goes
    straight to the cached trip; ?choose=1 still shows the chooser; unchecking removes the key; next boot = chooser."""
    ids, pre = setup(env, cached="OLD")
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    P = []
    cb = page.locator(SEL["d3"])
    if cb.is_checked() or D3_KEY in ls_raw(dev):
        P.append("D3 not off by default")
    lab = page.locator(SEL["d3_label"])
    if not lab.count() or TXT["d3"] not in norm(lab.first.inner_text()):
        P.append("label %r missing" % TXT["d3"])
    mark_page(page)
    url0 = cur_url(page)
    lab.first.click()
    page.wait_for_timeout(600)
    if ls_raw(dev).get(D3_KEY) != "1":
        P.append("checking D3 did not store %s='1' (%r)" % (D3_KEY, ls_raw(dev).get(D3_KEY)))
    if not same_document(page) or cur_url(page) != url0 or state(page) != "choose":
        P.append("changing D3 navigated")
    st = boot(dev)
    if st != "app" or not wait_trip_shown(page, TRIPS["OLD"][0]):
        P.append("D3 on: next boot did not go to the cached trip (state=%s, trip=%r)" % (st, trip_shown(page) if st == "app" else None))
    st = boot(dev, APP_PATH + "?choose=1")
    if st != "choose":
        pytest.fail("\n".join(P + ["?choose=1 with D3 on: state=%s" % st]))
    if "choose" in urlparse(cur_url(page)).query:
        P.append("?choose=1 not removed")
    if not page.locator(SEL["d3"]).is_checked():
        P.append("checkbox not checked with the key set")
    page.locator(SEL["d3_label"]).first.click()
    page.wait_for_timeout(600)
    if D3_KEY in ls_raw(dev):
        P.append("unchecking did not remove the key (%r)" % ls_raw(dev).get(D3_KEY))
    if boot(dev) != "choose":
        P.append("D3 off again: next boot is not the chooser")
    assert not P, "\n".join(P)


# =====================================================================================================
# §1.2 standalone admin (criterion 4)
# =====================================================================================================
def test_a01_chooser_admin_row_to_admin_back_and_history(env):
    """AC4: admin row → standalone admin in place (no reload, no trip chrome, header 'הטיולים שלי', no 'חזרה לטיול');
    'הטיולים שלי' → chooser (no reload); admin again → browser back → chooser (not a blank page); forward → admin."""
    ids, pre = setup(env)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    page.wait_for_timeout(800)
    mark_page(page)
    page.locator(SEL["choose_admin"]).click()
    st = wait_state(page, "admin", 10)
    P = []
    if st != "admin":
        pytest.fail("admin row did not open the admin screen (state=%s)" % st)
    P += admin_header_problems(page)
    if not wait_text(page, TXT["admin_invite_btn"]):
        P.append("F03 admin body missing")
    if not same_document(page):
        P.append("admin row reloaded the page")
    nt = no_trip_started(page)
    if nt["started"] is not False or nt["tripData"] != "undefined":
        P.append("trip started under the admin screen: %r" % nt)
    page.locator(SEL["admin_switch"]).click()
    if wait_state(page, "choose", 10) != "choose":
        P.append("'הטיולים שלי' did not return to the chooser (state=%s)" % state(page))
    if not same_document(page):
        P.append("'הטיולים שלי' reloaded the page (no trip had started)")
    page.locator(SEL["choose_admin"]).click()
    if wait_state(page, "admin", 10) != "admin":
        pytest.fail("\n".join(P + ["admin row (2nd time) did not open admin"]))
    page.go_back()
    st = wait_state(page, "choose", 10)
    if st != "choose":
        P.append("browser back from admin: state=%s (text=%r)" % (st, btext(page)[:120]))
    if not btext(page):
        P.append("blank page after back")
    page.go_forward()
    if wait_state(page, "admin", 10) != "admin":
        P.append("forward did not return to admin (state=%s)" % state(page))
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_a02_direct_admin_switch_to_chooser_in_place(env):
    """§1.2 + dev notes §6.14: opened directly at #admin, 'הטיולים שלי' shows the chooser in place (no reload, no hash)."""
    ids, pre = setup(env)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev, APP_PATH + "#admin") == "admin"
    page.wait_for_timeout(600)
    mark_page(page)
    page.locator(SEL["admin_switch"]).click()
    P = []
    if wait_state(page, "choose", 10) != "choose":
        pytest.fail("'הטיולים שלי' did not show the chooser (state=%s)" % state(page))
    if "#admin" in cur_url(page):
        P.append("hash #admin kept: %s" % cur_url(page))
    if not same_document(page):
        P.append("reloaded although no trip had started")
    end = time.time() + 8
    while time.time() < end and len(choose_rows(page)) < 4:
        page.wait_for_timeout(200)
    if len(choose_rows(page)) != 4:
        P.append("chooser rows after admin: %r" % choose_rows(page))
    assert not P, "\n".join(P)


def test_a03_reopen_choose_to_admin_ignores_d3(env):
    """D7 + §1.2/§1.4 (CHANGE 2026-10-17 F20-QA-03, replaces the alpha.5 sheet → admin test): from a running trip (D3 on)
    the way to admin is reopening the app at ?choose=1 → chooser (D3 ignored, query removed) → admin row → standalone admin
    (no trip chrome, no trip started); 'הטיולים שלי' → chooser; the D3 key is untouched."""
    ids, pre = setup(env, cached="MID", d3=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    st = boot(dev, APP_PATH + "?choose=1")
    if st != "choose":
        pytest.fail("?choose=1 from a trip (D3 on) did not show the chooser (state=%s)" % st)
    P = []
    if "choose" in urlparse(cur_url(page)).query:
        P.append("?choose=1 not removed: %s" % cur_url(page))
    page.locator(SEL["choose_admin"]).click()
    if wait_state(page, "admin", 15) != "admin":
        pytest.fail("\n".join(P + ["chooser admin row did not open admin (state=%s)" % state(page)]))
    page.wait_for_timeout(800)
    P += admin_header_problems(page)
    nt = no_trip_started(page)
    if nt["started"] is not False or nt["tripData"] != "undefined":
        P.append("trip started under the admin screen: %r" % nt)
    page.locator(SEL["admin_switch"]).click()
    if wait_state(page, "choose", 15) != "choose":
        P.append("'הטיולים שלי' did not show the chooser (state=%s)" % state(page))
    page.wait_for_timeout(600)
    if "choose" in urlparse(cur_url(page)).query or "#admin" in cur_url(page):
        P.append("URL not clean: %s" % cur_url(page))
    if ls_raw(dev).get(D3_KEY) != "1":
        P.append("D3 key changed by the navigation")
    assert not P, "\n".join(P)


# =====================================================================================================
# §1.3 switcher (criteria 7, 8, 10, 12)
# =====================================================================================================
AVATAR_JS = """(sel)=>{const a=[...document.querySelectorAll(sel)].find(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0});
 if(!a)return null;const r=a.getBoundingClientRect();const cs=getComputedStyle(a);
 const vis=e=>{const q=e.getBoundingClientRect();if(q.width<1||q.height<1)return false;const s=getComputedStyle(e);
   return s.visibility!=='hidden'&&+s.opacity!==0&&s.display!=='none'};
 const C='button,a[href],[role=button],input,select,[onclick],[data-go],[tabindex]:not([tabindex="-1"])';
 const others=[...document.querySelectorAll(C)].filter(e=>e!==a&&!a.contains(e)&&!e.contains(a)&&vis(e));
 const inter=(q)=>Math.max(0,Math.min(q.right,r.right)-Math.max(q.left,r.left))*Math.max(0,Math.min(q.bottom,r.bottom)-Math.max(q.top,r.top));
 const lab=e=>(e.id?'#'+e.id+' ':'')+((e.innerText||e.getAttribute('aria-label')||e.tagName).trim().slice(0,25));
 const overlaps=others.filter(e=>inter(e.getBoundingClientRect())>1).map(lab);
 const cx=r.left+r.width/2,cy=r.top+r.height/2;const h=document.elementFromPoint(cx,cy);
 const head=a.closest('.hv2-head,.homehero-top')||a.parentElement;
 const covered=[...head.querySelectorAll(C)].filter(e=>e!==a&&!a.contains(e)&&vis(e)).filter(e=>{const q=e.getBoundingClientRect();
   const x=Math.min(Math.max(q.left+q.width/2,0),innerWidth-1),y=Math.min(Math.max(q.top+q.height/2,0),innerHeight-1);
   const t=document.elementFromPoint(x,y);return t&&(t===a||a.contains(t))}).map(lab);
 return {id:a.id,w:r.width,h:r.height,left:r.left,right:r.right,top:r.top,radius:cs.borderRadius,text:a.textContent.trim(),
   aria:a.getAttribute('aria-label'),popup:a.getAttribute('aria-haspopup'),hit:!!h&&(h===a||a.contains(h)),overlaps,covered,iw:innerWidth,
   inHead:!!a.closest('.hv2-head,.homehero-top'),sw:document.scrollingElement.scrollWidth,
   head:(()=>{const q=head.getBoundingClientRect();return {left:q.left,right:q.right,top:q.top,bottom:q.bottom}})()}}"""

LAYOUTS = {"v2_min": {}, "v2": {"HOME_MIN": "off"}, "v1": {"HOME_LAYOUT": "v1"}}


@pytest.mark.parametrize("trips", ["two", "one"])
@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_s01_avatar_layouts_no_overlap(env, layout, trips):
    """AC7 + AC12 + §1.3: non-admin — ≥2 trips: avatar 44×44 circle, first letter of the display name, aria-label, at the
    top-left of the home header, hit-testable, overlapping no other control and covering none, no horizontal scroll —
    in HOME_LAYOUT v2 (HOME_MIN on = as delivered, and off) and v1; 1 trip: no avatar in the DOM."""
    serve_flags(env, **LAYOUTS[layout])
    keys = ORDER[:2] if trips == "two" else ORDER[:1]
    ids, pre = setup(env, keys=keys, admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    st = boot(dev)
    assert st == "app", "state=%s" % st
    f04.wait_home_any(page)
    ensure_home(page)
    page.evaluate("()=>window.scrollTo(0,0)")
    page.wait_for_timeout(400)
    sel = SEL["avatar_v1"] if layout == "v1" else SEL["avatar_v2"]
    a = page.evaluate(AVATAR_JS, sel)
    if trips == "one":
        assert a is None and not page.locator(SEL["avatar_any"]).filter(visible=True).count(), \
            "avatar shown to a non-admin with one trip (%s): %r" % (layout, a)
        return
    assert a, "avatar %s not visible (%s)" % (sel, layout)
    P = []
    if a["w"] < 43.5 or a["h"] < 43.5 or abs(a["w"] - a["h"]) > 1:
        P.append("size %.0fx%.0f (want 44x44)" % (a["w"], a["h"]))
    if not (a["radius"].endswith("%") and float(a["radius"].split("%")[0]) >= 50) and not (
            a["radius"].endswith("px") and float(a["radius"].split("px")[0]) >= a["w"] / 2 - 1):
        P.append("not a circle (border-radius %r)" % a["radius"])
    if a["text"] != TRIPS[keys[0]][7][0]:
        P.append("text %r, expected the first letter of %r" % (a["text"], TRIPS[keys[0]][7]))
    if a["aria"] != TXT["avatar_aria"]:
        P.append("aria-label %r" % a["aria"])
    hd = a["head"]
    if a["left"] + a["w"] / 2 > a["iw"] / 2 or a["top"] - hd["top"] > 24 or a["left"] - hd["left"] > 24:
        P.append("not at the top-left of the header (avatar left %.0f top %.0f; header left %.0f top %.0f)"
                 % (a["left"], a["top"], hd["left"], hd["top"]))
    if a["left"] < -0.5 or a["right"] > a["iw"] + 0.5:
        P.append("outside the viewport")
    if not a["hit"]:
        P.append("avatar is covered (not hit-testable)")
    if a["overlaps"]:
        P.append("overlaps controls: %r" % a["overlaps"])
    if a["covered"]:
        P.append("covers header controls: %r" % a["covered"])
    if a["sw"] > a["iw"] + 1:
        P.append("horizontal scroll")
    if not a["inHead"]:
        P.append("avatar not inside the home header")
    assert not P, ("%s: " % layout) + "\n".join(P)


@pytest.mark.parametrize("trips", ["one", "four"])
def test_s02_superadmin_avatar_only_with_two_trips(env, trips):
    """D5 (amended by D7, CHANGE 2026-10-17 F20-QA-03): the super-admin gets the avatar only with ≥2 active trips; with
    one trip there is no avatar button in the DOM (was: always)."""
    ids, pre = setup(env, keys=ORDER[:1] if trips == "one" else ORDER, cached="NEW", d3=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    page.wait_for_timeout(800)
    n = page.locator(SEL["avatar_any"]).filter(visible=True).count()
    if trips == "one":
        assert n == 0 and not exists(page, SEL["avatar_any"]), "avatar shown to a super-admin with one trip"
    else:
        assert n, "no avatar for a super-admin with 4 trips"


def test_s03_sheet_content_superadmin(env):
    """AC8 + §1.3: sheet = dialog 'מעבר בין טיולים' with display name, linked email (LTR), × close; 'הטיולים שלי' rows
    newest first: the current trip a non-link row with the check (role=img 'הטיול הנוכחי') and '<תפקיד> · כאן עכשיו',
    others buttons '<תפקיד> · dd/mm–dd/mm'; D7 (CHANGE 2026-10-17 F20-QA-03): NO 'ניהול' section — no #ptSwitchAdmin, no
    'ניהול מערכת' / 'יציאה מהטיול למסך הניהול' / 'סופר-אדמין'; no foreign trip; no duplicate ids; no old app name."""
    ids, pre = setup(env, cached="MID", d3=True, email="or@example.com", confirmed=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    open_sheet(page)
    P = []
    box = page.evaluate("""()=>{const b=document.getElementById('ptF20SheetBox');return {role:b.getAttribute('role'),
      modal:b.getAttribute('aria-modal'),label:b.getAttribute('aria-label')}}""")
    if box != {"role": "dialog", "modal": "true", "label": TXT["sheet_aria"]}:
        P.append("sheet box attributes %r" % box)
    nm = page.locator(SEL["sw_name"]).inner_text().strip()
    if nm != TRIPS["MID"][7]:
        P.append("display name %r, expected %r (this trip's member name)" % (nm, TRIPS["MID"][7]))
    if not is_vis(page, SEL["sw_email"]) or page.locator(SEL["sw_email"]).inner_text().strip() != "or@example.com":
        P.append("linked email not shown")
    elif f03.email_is_ltr(page, "or@example.com", SEL["sheet_box"]) not in (["ltr"],):
        P.append("email not LTR: %r" % f03.email_is_ltr(page, "or@example.com", SEL["sheet_box"]))
    cl = page.locator(SEL["sw_close"])
    if not cl.count() or cl.first.get_attribute("aria-label") != TXT["close_aria"]:
        P.append("× close button missing")
    rows = sheet_rows(page)
    order = [r["cur"] or r["id"] for r in rows]
    if order != [ids[k] for k in ORDER]:
        P.append("sheet rows order %r" % order)
    for k in ORDER:
        r = next((x for x in rows if (x["cur"] or x["id"]) == ids[k]), None)
        if not r:
            P.append("%s missing in the sheet" % k)
            continue
        if TRIPS[k][0] not in r["text"]:
            P.append("%s: name missing (%r)" % (k, r["text"]))
        if k == "MID":
            if r["tag"] == "BUTTON" or r["id"] or r["ariaCur"] != "true" or r["check"] != TXT["current_aria"]:
                P.append("current row wrong: %r" % r)
            if norm(r["sub"]) != norm("%s · %s" % (ROLE_HE["editor"], TXT["here_now"])):
                P.append("current row sub %r" % r["sub"])
        else:
            if r["tag"] != "BUTTON":
                P.append("%s: not a button" % k)
            if norm(r["sub"]) != norm(SHEET_SUBS[k]):
                P.append("%s: sub %r, expected %r" % (k, r["sub"], SHEET_SUBS[k]))
        if r["h"] < 44:
            P.append("%s: row height %.0f < 44" % (k, r["h"]))
    sbox = norm(page.locator(SEL["sheet_box"]).inner_text())
    if "טיול זר" in sbox or "טיול שהוסרתי ממנו" in sbox:
        P.append("foreign / removed trip listed in the sheet")
    # CHANGE 2026-10-17 F20-QA-03: D7 — the admin section must be absent (was: present for the super-admin)
    if exists(page, SEL["sw_admin"]):
        P.append("#ptSwitchAdmin in the sheet (D7)")
    for k in ("admin_row", "sw_admin_sub", "sw_admin_badge"):
        if TXT[k] in sbox:
            P.append("admin text %r in the sheet (D7)" % TXT[k])
    secs = page.evaluate("()=>[...document.querySelectorAll('#ptF20SheetBox .pt-f20-sec')].map(e=>e.textContent.trim())")
    if TXT["sec_admin"] in secs:
        P.append("section 'ניהול' in the sheet (D7)")
    if TXT["sec_trips"] not in sbox:
        P.append("section title 'הטיולים שלי' missing: %r" % sbox[:200])
    if dup_ids(page):
        P.append("duplicate ids: %r" % dup_ids(page))
    hits = [n for n in OLD_NAMES if n in sbox]
    if hits:
        P.append("old app name in the sheet: %r" % hits)
    assert not P, "\n".join(P)


@pytest.mark.parametrize("wizard", ["on", "off"])
def test_s04_non_admin_sheet_switch_persists(env, wizard):
    """AC7 + architect decision (WIZARD off + SWITCH on: a non-admin boots the cached trip): sheet without 'ניהול';
    tapping another trip reloads into it; it stays chosen after another reload; cache = that trip."""
    if wizard == "off":
        serve_flags(env, WIZARD_FEATURE="off")
    ids, pre = setup(env, keys=["NEW", "MID", "OLD"], admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    assert wait_trip_shown(page, TRIPS["NEW"][0]), "harness: newest first (%r)" % trip_shown(page)
    ensure_home(page)
    open_sheet(page)
    P = []
    if exists(page, SEL["sw_admin"]) or "ניהול מערכת" in norm(page.locator(SEL["sheet_box"]).inner_text()):
        P.append("'ניהול' section shown to a non-admin")
    mark_page(page)
    page.locator('%s[data-trip="%s"]' % (SEL["sw_row"], ids["OLD"])).click()
    if not wait_reloaded(page):
        P.append("tapping another trip did not reload")
    st = wait_state(page, "app", 20)
    f02.ensure_user(page)
    if st != "app" or not wait_trip_shown(page, TRIPS["OLD"][0]):
        pytest.fail("\n".join(P + ["switch: not in the chosen trip (state=%s, trip=%r)" % (st, trip_shown(page))]))
    if cached_trip(dev) != ids["OLD"]:
        P.append("cache not the chosen trip")
    st = boot(dev)
    if st != "app" or not wait_trip_shown(page, TRIPS["OLD"][0]):
        P.append("after another reload the chosen trip did not stick (%r)" % trip_shown(page))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("how", ["backdrop", "escape", "back", "x"])
def test_s05_sheet_closes(env, how):
    """§1.3: the sheet closes on backdrop tap, Escape, the browser back gesture and × — staying in the trip (no reload,
    same URL path)."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    url0 = urlparse(cur_url(page))
    open_sheet(page)
    mark_page(page)
    if how == "backdrop":
        box = page.locator(SEL["sheet_box"]).bounding_box()
        y = max(5, box["y"] - 40)
        page.mouse.click(195, y)
    elif how == "escape":
        page.keyboard.press("Escape")
    elif how == "back":
        page.go_back()
    else:
        page.locator(SEL["sw_close"]).first.click()
    page.wait_for_timeout(900)
    P = []
    if is_vis(page, SEL["sheet_box"]):
        P.append("sheet still open after %s" % how)
    if not same_document(page):
        P.append("%s left the page" % how)
    u = urlparse(cur_url(page))
    if (u.path, u.query) != (url0.path, url0.query):
        P.append("URL changed: %s" % cur_url(page))
    if state(page) != "app":
        P.append("not on the trip after %s (state=%s)" % (how, state(page)))
    assert not P, "\n".join(P)


def test_s06_current_row_does_not_navigate(env):
    """§1.3: the current trip row is not a link: tapping it does not reload / navigate."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    open_sheet(page)
    mark_page(page)
    n = len(dev.navs)
    page.locator(SEL["sw_current"]).first.click()
    page.wait_for_timeout(1200)
    assert same_document(page) and len(dev.navs) == n, "tapping the current trip navigated"
    assert wait_trip_shown(page, TRIPS["NEW"][0]), "trip changed"


@pytest.mark.parametrize("target", ["trip"])  # CHANGE 2026-10-17 F20-QA-03: [admin] removed (D7: no admin row in the sheet)
def test_s07_offline_tap_toast_no_navigation(env, target):
    """AC10 + §1.3: offline tap on another trip → toast 'אין חיבור. נסו שוב כשהרשת תחזור.', no navigation, cache
    unchanged."""
    ids, pre = setup(env, keys=ORDER[:2], admin=(target == "admin"), cached="NEW", d3=True, invites=False)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    open_sheet(page)
    mark_page(page)
    n = len(dev.navs)
    url0 = cur_url(page)
    dev.offline(True)
    page.wait_for_timeout(300)
    if target == "trip":
        page.locator('%s[data-trip="%s"]' % (SEL["sw_row"], ids["NOFLAG"])).click()
    else:
        page.locator(SEL["sw_admin"]).click()
    page.wait_for_timeout(1500)
    P = []
    toast = page.evaluate("()=>{const t=document.getElementById('ptToast');return t?t.innerText:''}")
    if TXT["offline_toast"] not in norm(toast) and not has(page, TXT["offline_toast"]):
        P.append("offline toast missing (%r)" % toast)
    if not same_document(page) or len(dev.navs) != n or cur_url(page) != url0:
        P.append("navigated while offline")
    dev.offline(False)
    if cached_trip(dev) != ids["NEW"]:
        P.append("cache changed offline: %r" % cached_trip(dev))
    assert not P, "\n".join(P)


def test_s08_more_has_no_admin_row_linked_email_stays(env):
    """AC9 + D6: with the flag on, 'עוד' has no 'ניהול מערכת' (#ptAdminRow never in the DOM) for the super-admin; the
    'מייל מקושר' row stays."""
    ids, pre = setup(env, keys=ORDER[:2], cached="NEW", d3=True, email="or@example.com", confirmed=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    f03.open_more(page)
    page.wait_for_timeout(1200)
    P = []
    if exists(page, SEL["more_admin_row"]):
        P.append("#ptAdminRow in the DOM")
    more = page.evaluate("()=>{const m=document.getElementById('more');return m?m.innerText:''}")
    if TXT["admin_row"] in norm(more):
        P.append("'ניהול מערכת' in 'עוד'")
    if TXT["more_linked"] not in norm(more):
        P.append("'מייל מקושר' row missing in 'עוד'")
    assert not P, "\n".join(P)


# =====================================================================================================
# CHANGE 2026-10-17 F20-QA-03: D7 — admin and trips never mix (criterion 8, alpha.5.1)
# =====================================================================================================
ADMIN_TEXTS = [TXT["admin_row"], TXT["sw_admin_sub"], TXT["admin_row_sub"], TXT["admin_sub"]]
TEXT_IN_UI_JS = """(ts)=>{const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
  for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden')return false}return true};
 const out=[];for(const e of document.querySelectorAll('body *')){if(!vis(e))continue;
   const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ')+' '+(e.getAttribute('aria-label')||'');
   for(const t of ts)if(own.includes(t))out.push(t+' @ '+(e.id?'#'+e.id:e.tagName)+(e.className&&typeof e.className==='string'?'.'+e.className.split(' ')[0]:''))}
 return out}"""


def admin_text_hits(page):
    return page.evaluate(TEXT_IN_UI_JS, ADMIN_TEXTS)


@pytest.mark.parametrize("trips", ["one", "four"])
def test_e01_no_admin_text_in_trip_ui(env, trips):
    """Criterion 8 / D7: super-admin inside a trip (1 trip and 4 trips): no 'ניהול מערכת' (nor the admin row sub /
    'יציאה מהטיול למסך הניהול' / 'Lonely Planner · סופר-אדמין') anywhere in the trip UI — home headers, every tab, 'עוד',
    and the switcher sheet when the avatar exists; no #ptAdminRow / #ptSwitchAdmin in the DOM; no control navigates to
    #admin (no href/data attribute naming admin)."""
    keys = ORDER[:1] if trips == "one" else ORDER
    ids, pre = setup(env, keys=keys, cached="NEW", d3=True, email="or@example.com", confirmed=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    page.wait_for_timeout(1000)
    P = []
    for tab in ("home", "route", "journal", "budget", "more"):
        try:
            f02.tab(page, tab)
        except PWError:
            P.append("tab %s missing" % tab)
            continue
        page.wait_for_timeout(700)
        h = admin_text_hits(page)
        if h:
            P.append("%s: admin text visible %r" % (tab, h[:4]))
    for sel in (SEL["more_admin_row"], SEL["sw_admin"]):
        if exists(page, sel):
            P.append("%s in the DOM" % sel)
    links = page.evaluate("""()=>[...document.querySelectorAll('a[href*="#admin"],[data-go="admin"],[data-href*="#admin"]')].map(e=>e.outerHTML.slice(0,80))""")
    if links:
        P.append("controls pointing at #admin: %r" % links)
    f02.tab(page, "home")
    page.wait_for_timeout(400)
    if trips == "four":
        open_sheet(page)
        h = admin_text_hits(page)
        if h:
            P.append("sheet: admin text %r" % h[:4])
        sb = norm(page.locator(SEL["sheet_box"]).inner_text())
        if TXT["admin_row"] in sb or TXT["sw_admin_badge"] in sb:
            P.append("sheet text has admin entry: %r" % sb[:200])
    elif exists(page, SEL["avatar_any"]):
        P.append("avatar shown with one trip")
    if "#admin" in cur_url(page):
        P.append("URL went to #admin")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("how", ["hashchange", "trip_query"])
def test_e02_hash_admin_in_running_trip_reloads_to_standalone(env, how):
    """D7 + dev notes §7 F20-D7-05 (architect): super-admin, a trip running; #admin appears (address bar hashchange, or a
    load that starts a trip: ?trip=<id>#admin) → full reload into the standalone admin: no trip started (__PT.started
    false, tripData undefined), no trip chrome, header 'הטיולים שלי' / no 'חזרה לטיול'; never the F03 screen layered over
    the trip; 'הטיולים שלי' → chooser."""
    ids, pre = setup(env, cached="MID", d3=True)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    mark_page(page)
    if how == "hashchange":
        page.evaluate("()=>{location.hash='#admin'}")
    else:
        page.goto(env.server.origin + APP_PATH + "?trip=" + ids["MID"] + "#admin", wait_until="domcontentloaded")
    end = time.time() + 15
    overlay = False
    while time.time() < end:
        try:
            if page.evaluate("()=>window.__qaStay===1&&document.documentElement.classList.contains('pt-admin-open')"):
                overlay = True
            if page.evaluate("()=>window.__qaStay!==1") and state(page) == "admin":
                break
        except PWError:
            pass
        page.wait_for_timeout(100)
    st = wait_state(page, "admin", 10)
    P = []
    if how == "hashchange" and overlay:
        P.append("admin screen was layered over the running trip before the reload")
    if st != "admin":
        pytest.fail("\n".join(P + ["%s: no standalone admin (state=%s, url=%s)" % (how, st, cur_url(page))]))
    if same_document(page):
        P.append("no full reload (admin layered over the running trip)")
    page.wait_for_timeout(800)
    nt = no_trip_started(page)
    if nt["started"] is not False or nt["tripData"] != "undefined" or nt["homeActive"]:
        P.append("trip main script running under the admin: %r" % nt)
    P += admin_header_problems(page)
    if how == "trip_query" and "trip=" in urlparse(cur_url(page)).query:
        P.append("?trip= kept on the admin URL: %s" % cur_url(page))
    page.locator(SEL["admin_switch"]).click()
    if wait_state(page, "choose", 15) != "choose":
        P.append("'הטיולים שלי' did not show the chooser (state=%s)" % state(page))
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_e03_hash_admin_non_admin_in_trip_cleaned_no_reload(env):
    """§1.2 / dev notes §7: non-admin, trip running, #admin typed → hash cleaned, same document (no reload), no admin UI,
    still the same trip."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    mark_page(page)
    n = len(dev.navs)
    page.evaluate("()=>{location.hash='#admin'}")
    page.wait_for_timeout(2500)
    P = []
    if not same_document(page):
        P.append("page reloaded")
    if "#admin" in cur_url(page):
        P.append("hash not cleaned: %s" % cur_url(page))
    if page.evaluate("()=>document.documentElement.classList.contains('pt-admin-open')") or visible(page, TXT["admin_invite_btn"]):
        P.append("admin UI shown to a non-admin")
    if state(page) != "app" or trip_id_running(page) != ids["NEW"]:
        P.append("not in the same trip (state=%s, trip=%r)" % (state(page), trip_id_running(page)))
    if any("#admin" not in u and u != dev.navs[n - 1] for u in dev.navs[n:]) and not same_document(page):
        P.append("navigations: %r" % dev.navs[n:])
    assert not P, "\n".join(P)


def test_e04_hash_admin_loop_guard(env):
    """dev notes §7 F20-D7-05 loop guard: super-admin types #admin in a running trip; after the reload the admin check
    hangs (→ not super-admin, normal boot into the trip). The page must settle in the trip — one reload, no reload loop
    (≤ 2 document loads in 12 s), no admin layered over the trip; typing #admin again within 30 s causes no reload.
    Not asserted: whether #admin is removed from the URL when the admin status is UNKNOWN (check hung) — alpha.4.2 keeps
    the hash in that case too (fresh #admin load with a hanging check, SWITCH off), see the QA report."""
    ids, pre = setup(env, cached="MID", d3=True, invites=False)
    be = env.backend
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "app"
    ensure_home(page)
    loads = []
    page.on("load", lambda: loads.append(time.time()))
    be.hang_tables = {"platform_admins"}
    page.evaluate("()=>{location.hash='#admin'}")
    page.wait_for_timeout(12000)
    P = []
    if len(loads) > 2:
        P.append("reload loop: %d document loads in 12 s" % len(loads))
    st = wait_state(page, "app", 8)
    if st != "app":
        P.append("did not settle in the trip (state=%s)" % st)
    if page.evaluate("()=>document.documentElement.classList.contains('pt-admin-open')"):
        P.append("admin layered over the trip after the guarded attempt")
    n = len(loads)
    mark_page(page)
    page.evaluate("()=>{location.hash='#admin'}")
    page.wait_for_timeout(5000)
    if len(loads) > n + 1:
        P.append("second #admin within 30 s caused %d loads" % (len(loads) - n))
    if state(page) != "app":
        P.append("second attempt: state=%s (expected to stay in the trip)" % state(page))
    print("loads after first #admin: %d, after second: %d" % (n, len(loads) - n))
    assert not P, "\n".join(P)


# =====================================================================================================
# 12 · 390px / RTL / 44px, no old name, duplicate ids
# =====================================================================================================
@pytest.mark.parametrize("scr", ["chooser", "chooser_none", "admin_header", "sheet"])
def test_l01_layout_390_rtl_touch(env, scr):
    """AC12: no horizontal scroll, RTL, every visible control ≥44px (hit-tested) on the chooser, the admin header and the
    sheet; no duplicate ids in the live DOM; no 'Plan_Travel' / 'Vietnam Travel Planner' rendered."""
    if scr == "chooser_none":
        env.backend.auto_admin = True
        dev = device(env)
        assert boot(dev) == "choose"
    else:
        ids, pre = setup(env, cached="MID", d3=(scr == "sheet"), email="or@example.com", confirmed=True)
        dev = device(env, pre)
        path = APP_PATH + "#admin" if scr == "admin_header" else APP_PATH
        st = boot(dev, path)
        assert st == {"chooser": "choose", "admin_header": "admin", "sheet": "app"}[scr], "state=%s" % st
    page = dev.page
    page.wait_for_timeout(1500)
    scope = {"chooser": SEL["choose"], "chooser_none": SEL["choose"], "admin_header": SEL["admin_head"], "sheet": SEL["sheet_box"]}[scr]
    if scr == "sheet":
        ensure_home(page)
        open_sheet(page)
    P = layout_problems(page, scope, scr)
    if scr != "sheet" and chrome_visible(page):
        P.append("%s: trip chrome visible %r" % (scr, chrome_visible(page)))
    d = dup_ids(page)
    if d:
        P.append("%s: duplicate ids %r" % (scr, d))
    txt = page.evaluate("()=>document.body.innerText+'\\n'+document.title")
    hits = [n for n in OLD_NAMES if n in txt]
    if hits:
        P.append("%s: old app name rendered %r" % (scr, hits))
    if scr in ("chooser", "admin_header") and APP_NAME not in txt:
        P.append("%s: brand %r missing" % (scr, APP_NAME))
    assert not P, "\n".join(P)


# =====================================================================================================
# 13 + §2 · Data the client reads (network under the fake)
# =====================================================================================================
def _calls_summary(calls):
    out = []
    for c in calls:
        if c.get("op") == "query":
            r = c["msg"]["req"]
            out.append(("query", r.get("table"), r.get("action")))
        elif c.get("op") == "rpc":
            out.append(("rpc", c["msg"].get("fn"), None))
        else:
            out.append((c.get("op"), None, None))
    return out


def test_d01_network_reads_only_spec_tables(env):
    """§2 + AC13 (client side): during the chooser / standalone admin phase the client only SELECTs trip_members, trips,
    trip_countries, platform_admins and calls rpc admin_trip_summary (no writes, no other table/RPC/function, no trip_kv);
    the trip-detail queries are restricted to the user's own trip ids; the first sheet open inside a trip only adds
    selects on trips / trip_countries / trip_members; external requests are only the (faked) supabase-js library;
    platform_admins is checked once per boot."""
    ids, pre = setup(env)
    be = env.backend
    dev = device(env, pre)
    page = dev.page
    assert boot(dev) == "choose"
    page.wait_for_timeout(1500)
    page.locator(SEL["choose_admin"]).click()
    assert wait_state(page, "admin", 10) == "admin"
    page.wait_for_timeout(1000)
    page.locator(SEL["admin_switch"]).click()
    assert wait_state(page, "choose", 10) == "choose"
    page.wait_for_timeout(800)
    pre_calls = [c for c in be.calls if c["device"] == "A"]
    P = []
    own = {ids[k] for k in ORDER}
    for c in pre_calls:
        op = c.get("op")
        if op in ("auth.signInAnonymously", "auth.getUser"):
            continue
        if op == "query":
            r = c["msg"]["req"]
            if r.get("table") not in SPEC_READ_TABLES or r.get("action") != "select":
                P.append("chooser/admin phase: %s %s" % (r.get("action"), r.get("table")))
            for f in r.get("filters") or []:
                if f.get("op") == "in" and f.get("col") in ("id", "trip_id"):
                    extra = set(map(str, f.get("val") or [])) - own
                    if extra:
                        P.append("%s in(%s) asks for trips that are not the user's active memberships: %r" % (r.get("table"), f.get("col"), extra))
        elif op == "rpc":
            if c["msg"].get("fn") not in SPEC_RPCS:
                P.append("rpc %s" % c["msg"].get("fn"))
        elif op == "functions.invoke":
            P.append("function %s invoked" % c["msg"].get("name"))
        elif op not in ("auth.trace",):
            P.append("unexpected backend op %s" % op)
    n_pa = len([c for c in pre_calls if c.get("op") == "query" and c["msg"]["req"].get("table") == "platform_admins"])
    if n_pa != 1:
        P.append("platform_admins queried %d times in one boot (spec: once per boot)" % n_pa)
    ext = [r["url"] for r in env.net if r.get("action") not in ("same-origin", "fake-lib")
           and not r["url"].startswith("https://maps.googleapis.com/maps/api/js?")]   # static <script> tag, alpha.4.2 markup
    if ext:   # the trip main script (maps etc.) has not run yet, so nothing else may leave the page
        P.append("external requests on the chooser/admin: %r" % ext[:5])
    # enter a trip, open the sheet: only the spec tables are added
    assert enter_from_chooser(dev, ids["MID"]) == "app"
    ensure_home(page)
    page.wait_for_timeout(1500)
    n = len(be.calls)
    open_sheet(page)
    page.wait_for_timeout(1000)
    for c in be.calls[n:]:
        if c.get("op") == "query":
            r = c["msg"]["req"]
            if r.get("table") not in SPEC_READ_TABLES - {"platform_admins"} and r.get("table") != "trip_kv":
                P.append("sheet open: %s %s" % (r.get("action"), r.get("table")))
            if r.get("table") in SPEC_READ_TABLES and r.get("action") != "select":
                P.append("sheet open: write %s %s" % (r.get("action"), r.get("table")))
        elif c.get("op") in ("rpc", "functions.invoke"):
            P.append("sheet open: %s %s" % (c.get("op"), c["msg"].get("fn") or c["msg"].get("name")))
    print("chooser/admin phase calls:", collections.Counter(_calls_summary(pre_calls)))
    assert not P, "\n".join(P)


def test_d02_non_admin_never_calls_admin_rpc(env):
    """§2: admin_trip_summary is for the admin only; a non-admin with 2 trips opening the sheet never calls it."""
    ids, pre = setup(env, keys=ORDER[:2], admin=False, invites=False)
    dev = device(env, pre)
    assert boot(dev) == "app"
    ensure_home(dev.page)
    open_sheet(dev.page)
    dev.page.wait_for_timeout(800)
    assert not [c for c in env.backend.rpcs() if c["msg"].get("fn") == "admin_trip_summary"], "admin RPC called by a non-admin"


# =====================================================================================================
# 14 · Static
# =====================================================================================================
def _extract(html, names, tmp):
    p = tmp / ("x%d.html" % (abs(hash(html)) % 10 ** 8))
    p.write_text(html, encoding="utf-8")
    r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(p)] + names)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO_DIR)] + list(args), capture_output=True, text=True)


STATIC = ["protected:" + n for n in PROTECTED] + [
    "app_version", "pt_version", "title", "flag_declared", "change_comments", "change_comments_cover_hunks",
    "node_check_app", "no_new_duplicate_ids", "no_db_or_function_change", "no_live_project_ref", "no_localstorage_clear",
    "footnote_not_shipped"]


@pytest.mark.parametrize("check", STATIC)
def test_st_static(check, tmp_path):
    """AC14: protected functions byte-identical to main (alpha.4.2); APP_VERSION / PT_VERSION = VERSION (alpha.5.1); <title> ==
    'Lonely Planner'; SWITCH_FEATURE next to ADMIN_FEATURE / WIZARD_FEATURE; 'CHANGE 2026-10-13 F20-…' present and
    near every changed hunk; node --check on every inline script; no new duplicate ids; no migration / Edge Function change
    in the branch (spec: 'No database migration, no Edge Function change')."""
    html = app_html()
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = _extract(qa_refs.v2152_html(), [name], tmp_path)["found"][name]  # CHANGE 2026-10-26 QA-DEBT-05: was main_html()
        b = _extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1, "harness: %s found %d times in v2.15.2" % (name, len(a))
        assert b and a[0] in b, "%s is not byte-identical to v2.15.2" % name
    elif check == "app_version":
        assert re.search(r"""const\s+APP_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "APP_VERSION != %s" % VERSION
    elif check == "pt_version":
        assert re.search(r"""PT_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "PT_VERSION != %s" % VERSION
    elif check == "title":
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        assert m and m.group(1).strip() == APP_NAME, "<title> %r" % (m and m.group(1))
    elif check == "flag_declared":
        blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
        blk = [b for b in blocks if re.search(r"const\s+ADMIN_FEATURE\s*=", b)]
        assert blk and re.search(r"""^\s*const\s+SWITCH_FEATURE\s*=\s*['"]on['"]""", blk[0], re.M), \
            "const SWITCH_FEATURE='on' not declared next to ADMIN_FEATURE"
    elif check == "change_comments":
        assert "CHANGE 2026-10-13 F20-" in html, "no 'CHANGE 2026-10-13 F20-…' comment in app/index.html"
        n = len(re.findall(r"CHANGE 2026-10-13 F20-[A-Z]+-\d+", html))
        assert n >= 5, "only %d F20 CHANGE comments" % n
        assert re.search(r"CHANGE 2026-10-13 F20-[^\n]*(alpha\.4\.2|no alpha\.4\.2|was )", html), "CHANGE comments do not say what changed from alpha.4.2"
    elif check == "change_comments_cover_hunks":
        r = _git("diff", "-U0", MAIN_REF, "--", "app/index.html")
        assert r.returncode == 0, r.stderr
        new = html.split("\n")
        bad = []
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", r.stdout, re.M):
            start, cnt = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            if cnt == 0:
                continue
            window = "\n".join(new[max(0, start - 1 - 40):start - 1 + cnt])
            if "F20-" not in window:
                bad.append("+%d,%d" % (start, cnt))
        assert not bad, "changed hunks without an F20 CHANGE comment within 40 lines above: %r" % bad
    elif check == "node_check_app":
        dd = tmp_path / "scripts"
        dd.mkdir()
        r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(APP_DIR / "index.html")], env={**os.environ, "DUMP_DIR": str(dd)})
        assert r.returncode == 0, r.stderr
        files = sorted(list(dd.glob("*.js")) + list(dd.glob("*.mjs")))
        assert files, "no inline scripts found"
        bad = [x.name for x in files if f02.node(["--check", str(x)]).returncode != 0]
        assert not bad, "node --check failed: %r" % bad
    elif check == "no_new_duplicate_ids":
        def dups(h):
            c = collections.Counter(re.findall(r"""\bid=["']([A-Za-z][\w:-]*)["']""", h))
            return {k for k, v in c.items() if v > 1}
        new_d = dups(html) - dups(main_html())
        assert not new_d, "new duplicate ids in the markup: %r" % sorted(new_d)
    elif check == "no_db_or_function_change":
        r = _git("diff", "--name-only", MAIN_REF)
        assert r.returncode == 0, r.stderr
        files = [f for f in r.stdout.split() if f]
        bad = [f for f in files if f.startswith("supabase/") or f.endswith(".sql")]
        assert not bad, "DB / Edge Function files changed: %r" % bad
    elif check == "no_live_project_ref":
        assert f02.LIVE_REF not in html
    elif check == "no_localstorage_clear":
        assert not re.search(r"localStorage\s*\.\s*clear\s*\(", html)
    elif check == "footnote_not_shipped":
        assert TXT["footnote"] not in html, "mockup footnote is in the app"


def test_harness_fake_semantics():
    """The fake follows spec §2 (own-membership reads, admin RPC admin-only, pending count) so the client tests rest on it."""
    be = F20Backend()
    ids = make_trips(be)
    be.auto_admin = True
    res = be.sign_in()
    tok = res["session"]["access_token"]
    uid = res["session"]["user"]["id"]
    own = sorted(be.active_trips(uid))
    assert own == sorted(ids[k] for k in ORDER)
    r = be.query(tok, {"table": "trips", "action": "select", "columns": "id,name,start_date,end_date",
                       "filters": [{"op": "in", "col": "id", "val": own + [ids["_foreign"]]}]}, False)
    assert sorted(x["id"] for x in r["data"]) == own, "foreign trip readable"
    r = be.query(tok, {"table": "trip_members", "action": "select", "columns": "trip_id",
                       "filters": [{"op": "in", "col": "trip_id", "val": own}, {"op": "eq", "col": "status", "val": "active"}]}, False)
    cnt = collections.Counter(x["trip_id"] for x in r["data"])
    assert [cnt[ids[k]] for k in ORDER] == [4, 2, 3, 1]
    be.add_invite("a@example.com", "x", sent_days_ago=0, expires_in_days=3)
    be.add_invite("b@example.com", "y", sent_days_ago=9, expires_in_days=-1)
    s = be.rpc(tok, "admin_trip_summary", {})["data"]
    assert len([x for x in s if x["kind"] == "invite" and x["status"] == "pending"]) == 1
    be.hang_tables = {"platform_admins"}
    assert be.query(tok, {"table": "platform_admins", "action": "select", "columns": "user_id", "filters": []}, False) == {"hang": True}
