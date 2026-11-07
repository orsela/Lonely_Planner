"""Lonely Planner F10 QA · browser harness (trip currencies) · version 1.0.0
CHANGE 2026-11-07 F10-QA-01: new file (no previous version).

Written from docs/F10_spec.md (commit 8291e7d) only. The F10 implementation and docs/F10_dev_notes.md were NOT read while
this file was designed. alpha.8 element ids (4ca777b: #expenseCurRow #expenseAmount #expenseCalcBtn #expenseCalcBox
#budgetFxRow #fxAmount #fxCalculate #fxResult #quickFxRow #quickFxAmount #quickFxCalculate #quickFxResult
#quickFxAddExpenseBtn #globalFxBtn #qeCurRow #qeAmount #qeConv #resCost #rateUSD/#rateEUR/#rateVND #fxUpdate #fxAutoUpdate
#budgetSpentAmt …) are used where the spec says the place changes in content only. New UI (the "עוד" chip and its sheet,
the dynamic rate rows) is found by the texts / aria-labels of spec §3 ("עוד N מטבעות: …", "1,000 VND", "אין שער").

Reuses the F21 harness (tests/f21/harness.py → F04-HOME → F06 → F05 → F20 → F04 → F03 → F02): GitHub-Pages-like server,
PostgREST-like fake (trips / trip_countries / trip_currencies / trip_kv under the F01 RLS model), anonymous sign-in with
memberships (`backend.links`), the cookie-driven navigator.onLine switch (F20 OFFLINE_JS) and the UI helpers.

New for F10:
- F10Backend.fixture(key): the five §6 fixtures V T A G S (+ helpers for expenses, budget, fxrates).
- open.er-api.com stub (spec §2 live fetch): `env.er_payload` (default ER_PAYLOAD), `env.er_down`, call log `env.er_calls`.
- Offline device (`go_offline(dev)`): navigator.onLine false (cookie), backend down, er-api aborted and the same-origin
  countries.json / currencies.json aborted too (they are not precached, spec §1), so a cached TRIPCUR is really needed.
- Chat-assistant stub (P10): with CHAT_FEATURE flipped to 'on' the POST body is recorded in `env.chat_bodies`.
- Chip-row reader (CHIPS_JS): code / symbol / selected / src / dst / "עוד" chip / height for any chip row.
"""
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
if "f21_harness" in sys.modules:
    h21 = sys.modules["f21_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f21_harness", str(REPO_DIR / "tests" / "f21" / "harness.py"))
    h21 = importlib.util.module_from_spec(_spec)
    sys.modules["f21_harness"] = h21
    _spec.loader.exec_module(h21)
h4, f06, f05, f20, f04, f03, f02 = h21.h4, h21.f06, h21.f05, h21.f20, h21.f04, h21.f03, h21.f02

from playwright.sync_api import Error as PWError  # noqa: E402

ROOT, APP = h21.ROOT, h21.APP
APP_DIR = h21.APP_DIR
PT_URL = f02.PT_URL
CHAT_URL = PT_URL + "/functions/v1/chat-assistant"
ER_URL = "https://open.er-api.com/v6/latest/USD"
BASE_REF = os.environ.get("F10_BASE_REF", "4ca777b")     # 3.0.0-alpha.8 (spec "Base")
CACHE_KEY = "pt:_device:active_trip"
DAY = h21.DAY

COUNTRIES = {c["code"]: c for c in json.loads((APP_DIR / "countries.json").read_text(encoding="utf-8"))}
CURRENCIES = {c["code"]: c for c in json.loads((APP_DIR / "currencies.json").read_text(encoding="utf-8"))}
SYM = {k: (v.get("symbol") or k) for k, v in CURRENCIES.items()}
SYM2CODE = {"₪": "ILS", "$": "USD", "€": "EUR", "₫": "VND", "฿": "THB", "៛": "KHR"}
HOME_WORD = {"ILS": "שקלים", "USD": "דולרים", "EUR": "אירו"}

# er-api payload (USD per… i.e. units of <code> per 1 USD), spec §2: homePerUnit(c) = usd[home] / usd[c]
ER_PAYLOAD = {"result": "success", "provider": "https://www.exchangerate-api.com", "base_code": "USD",
              "time_last_update_utc": "Sat, 07 Nov 2026 00:02:31 +0000", "time_last_update_unix": 1793923351,
              "rates": {"USD": 1, "ILS": 3.7, "EUR": 0.92, "VND": 25400, "THB": 35.5, "AED": 3.6725, "KHR": 4100,
                        "GBP": 0.78, "JPY": 150.2}}


def home_per_unit(home, code, payload=ER_PAYLOAD):
    r = payload["rates"]
    return r[home] / r[code]


# =====================================================================================================
# Fixtures (spec §6): key -> (trip name, home, countries, extra trip_currencies [(code, kind)])
# =====================================================================================================
FIX = {
    "V": ("וייטנאם 2026", "ILS", ["VN"], [("VND", "destination")]),
    "T": ("תאילנד 2027", "ILS", ["TH"], [("THB", "destination")]),
    "A": ("איחוד האמירויות · ינואר 2027", "USD", ["AE"], [("AED", "destination")]),
    "G": ("יוון 2027", "ILS", ["GR"], []),
    "S": ("דרום-מזרח אסיה 2027", "ILS", ["TH", "VN", "KH"], [("THB", "destination"), ("VND", "destination"), ("KHR", "destination")]),
}
BASES = ("ILS", "USD", "EUR")
# expected TRIPCUR.list (spec §1 D6) — derived by hand from the rules, not computed by the code under test
LIST = {
    "V": ["VND", "ILS", "USD", "EUR"],
    "T": ["THB", "ILS", "USD", "EUR"],
    "A": ["AED", "USD", "ILS", "EUR"],
    "G": ["EUR", "ILS", "USD"],
    "S": ["THB", "VND", "KHR", "ILS", "USD", "EUR"],
}
LOCAL = {"V": "VND", "T": "THB", "A": "AED", "G": "EUR", "S": "THB"}
HOME = {k: v[1] for k, v in FIX.items()}

# V: the "existing expense fixture" (alpha.8 shape: amount in ₪, no homeCurrency)
V_EXPENSES = [
    {"description": "מונית משדה התעופה", "amount": 120, "category": "transport", "dayIndex": 0, "by": "אור", "createdAt": 1789900000000},
    {"description": "פו בבוקר", "amount": 56, "originalAmount": 400000, "originalCurrency": "VND", "category": "food", "dayIndex": 1,
     "by": "שירי", "createdAt": 1789990000000},
    {"description": "כרטיסים למופע", "amount": 72, "originalAmount": 20, "originalCurrency": "USD", "category": "attractions",
     "dayIndex": 2, "by": "אור", "createdAt": 1790000000000},
    {"description": "מזכרות", "amount": 210.5, "category": "shopping", "by": "שחר", "createdAt": 1790100000000},
]
V_LEGACY_RATES = {"USD": 3.6, "EUR": 3.9, "VND": 0.14}
# T: no VND anywhere
T_EXPENSES = [
    {"description": "טוק טוק", "amount": 30, "originalAmount": 300, "originalCurrency": "THB", "category": "transport", "dayIndex": 0,
     "by": "אור", "createdAt": 1789900000000, "homeCurrency": "ILS"},
    {"description": "ארוחה", "amount": 95, "category": "food", "by": "אור", "createdAt": 1789990000000},
]
# A: one USD-home expense, one AED expense, one OLD ILS expense (no homeCurrency → "(₪ מקורי)", §4)
A_EXPENSES = [
    {"description": "שווארמה", "amount": 50, "homeCurrency": "USD", "category": "food", "dayIndex": 0, "by": "אור", "createdAt": 1789900000000},
    {"description": "מונית", "amount": 27.23, "homeCurrency": "USD", "originalAmount": 100, "originalCurrency": "AED", "category": "transport",
     "dayIndex": 1, "by": "אור", "createdAt": 1789990000000},
    {"description": "ישן בשקלים", "amount": 37, "category": "other", "by": "אור", "createdAt": 1790000000000},
]
A_RATES_V2 = {"v": 2, "base": "USD", "rates": {"AED": 0.2723, "ILS": 0.27, "EUR": 1.08}, "updatedAt": 1793900000000, "source": "manual"}


class F10Backend(h21.F21Backend):
    def fixture(self, key, role="manager", name=None, expenses=None, budget=None, fxrates=None, me="אור", with_rows=True):
        """Create fixture trip `key`; the device's membership is added on sign-in (backend.links). Returns trip_id."""
        tname, home, countries, extra = FIX[key]
        tname = name or tname
        tid = self.add_trip(tname)
        self.rows["trips"][(tid,)].update({"name": tname, "start_date": "2027-01-10", "end_date": "2027-01-31", "home_currency": home})
        if with_rows:
            for i, c in enumerate(countries):
                self.rows["trip_countries"][(tid, c)] = {"trip_id": tid, "country_code": c, "sort": i}
            for i, c in enumerate([home] + [b for b in BASES if b != home]):
                self.rows["trip_currencies"][(tid, c)] = {"trip_id": tid, "currency_code": c, "kind": "base", "sort": i}
            for i, (c, kind) in enumerate(extra):
                self.rows["trip_currencies"][(tid, c)] = {"trip_id": tid, "currency_code": c, "kind": kind, "sort": 3 + i}
        start = f04.dt.date(2027, 1, 10)
        cap = COUNTRIES[countries[0]]["capital"]
        self.set_kv(tid, "trip", json.dumps(f04.empty_days(start, 22, (cap["lat"], cap["lng"]), countries[0]), ensure_ascii=False))
        self.set_kv(tid, "tripname", tname)
        if expenses is not None:
            self.set_kv(tid, "expenses", json.dumps(expenses, ensure_ascii=False))
        if budget is not None:
            self.set_kv(tid, "budget", str(budget))
        if fxrates is not None:
            self.set_kv(tid, "fxrates", fxrates if isinstance(fxrates, str) else json.dumps(fxrates))
        self.add_member(tid, str(uuid.uuid4()), "manager", "active", "מנהל אחר")
        self.links.append({"trip_id": tid, "role": role, "display_name": me,
                           "joined_at": f05.iso(self.tnow() - (40 - len(self.links)) * DAY)})
        return tid

    def kv_json(self, tid, key, default=None):
        raw = self.kv(tid, key)
        try:
            return json.loads(raw) if raw else default
        except ValueError:
            return default


class Env(h21.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F10Backend()
        self.er_payload = ER_PAYLOAD
        self.er_down = False
        self.er_calls = []
        self.chat_bodies = []

    def new_device(self, name="A", **kw):
        d = super().new_device(name, **kw)
        d.qa_off = False
        return d

    def _route5(self, dev, route, request):
        url = request.url
        p = urlparse(url)
        base = url.split("#")[0].split("?")[0].rstrip("/")
        try:
            if p.hostname == "open.er-api.com":
                self.er_calls.append({"device": dev.name, "url": url, "t": time.time(), "offline": dev.qa_off})
                self.net.append({"device": dev.name, "url": url, "method": request.method, "type": request.resource_type, "action": "er-api"})
                if dev.qa_off or self.er_down or getattr(dev, "is_offline", False):
                    return route.abort("internetdisconnected")
                return route.fulfill(status=200, content_type="application/json", body=json.dumps(self.er_payload),
                                     headers={"Access-Control-Allow-Origin": "*"})
            if base == CHAT_URL:
                origin = request.headers.get("origin") or "*"
                cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"}
                if request.method == "OPTIONS":
                    return route.fulfill(status=204, headers=cors, body="")
                try:
                    self.chat_bodies.append(json.loads(request.post_data or "{}"))
                except ValueError:
                    self.chat_bodies.append({"__raw": request.post_data})
                return route.fulfill(status=200, headers=cors, content_type="application/json", body=json.dumps({"answer": "בסדר"}))
            if dev.qa_off and p.hostname in ("127.0.0.1", "localhost") and re.search(r"/(countries|currencies)\.json$", p.path):
                self.net.append({"device": dev.name, "url": url, "action": "offline-json"})
                return route.abort("internetdisconnected")
        except PWError:
            return None
        return super()._route5(dev, route, request)


def go_offline(env, dev, on=True):
    """Offline the way the F20 suite does it (navigator.onLine=false through a cookie, backend unreachable) + er-api and the
    two JSON files aborted. The app page itself is still served (as a service worker would)."""
    dev.qa_off = bool(on)
    f20.set_offline_cookie(dev, on)
    env.backend.mode = "down" if on else "up"


# =====================================================================================================
# Source helpers
# =====================================================================================================
CUR_FLAG_RE = re.compile(r"""((?:const|let|var)\s+CURRENCY_FEATURE\s*=\s*)(['"])(on|off)\2""")
CHAT_FLAG_RE = re.compile(r"""((?:const|let|var)\s+CHAT_FEATURE\s*=\s*)(['"])(soon|on|off)\2""")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def base_html():
    return f02_git_show(BASE_REF)


def f02_git_show(ref, path="app/index.html"):
    import subprocess
    r = subprocess.run(["git", "-C", str(REPO_DIR), "show", "%s:%s" % (ref, path)], capture_output=True)
    assert r.returncode == 0, "harness: git show %s:%s failed: %s" % (ref, path, r.stderr.decode()[:200])
    return r.stdout.decode("utf-8")


def flip_currency(src, value="off"):
    assert CUR_FLAG_RE.search(src), "const CURRENCY_FEATURE='on'|'off' not found (spec §5)"
    return CUR_FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def flip_chat(src, value="on"):
    assert CHAT_FLAG_RE.search(src), "harness: CHAT_FEATURE not found"
    return CHAT_FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def serve_src(env, src):
    b = src.encode("utf-8")
    env.server.overrides[APP + "index.html"] = b
    env.server.overrides[APP] = b


# =====================================================================================================
# Boot
# =====================================================================================================
def boot(env, tid, role="manager", name="A", wait_rates=True, pre_ls=None, **kw):
    """A device whose identity is a member of every trip in backend.links; enters trip `tid` (cached as the active trip)."""
    dev = env.new_device(name, **kw)
    pre = {CACHE_KEY: json.dumps({"trip_id": tid, "role": role})}
    pre.update(pre_ls or {})
    dev.seed_ls(pre)
    st = reboot(dev)
    assert st == "app", "boot: state %r, text=%r" % (st, f04.btext(dev.page)[:300])
    return dev


def reboot(dev, timeout=25.0):
    page = dev.page
    page.goto(dev.env.server.origin + APP, wait_until="commit")
    st = f20.wait_state(page, "app", timeout)
    if st == "app":
        f02.ensure_user(page)
        page.wait_for_timeout(1200)
    return st


def tripcur(page):
    try:
        return page.evaluate("()=>{try{const t=window.__PT&&window.__PT.tripcur;return t?JSON.parse(JSON.stringify(t)):null}catch(e){return 'ERR '+e}}")
    except PWError:
        return None


def tab(page, panel):
    f02.tab(page, panel)
    page.wait_for_timeout(300)


def open_budget(page):
    tab(page, "budget")
    page.evaluate("""()=>{for(const d of document.querySelectorAll('#budget details'))d.open=true}""")
    page.wait_for_timeout(400)


# =====================================================================================================
# Chip rows
# =====================================================================================================
CHIPS_JS = r"""(sel)=>{const row=typeof sel==='string'?document.querySelector(sel):sel;if(!row)return null;
 const SYM=%s;
 const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden')return false}return true};
 const btns=[...row.querySelectorAll('button,[role=button],[role=radio],[role=option]')].filter(b=>!b.parentElement.closest('button')&&vis(b));
 return btns.map(b=>{const t=(b.innerText||b.textContent||'').replace(/\s+/g,' ').trim(),aria=b.getAttribute('aria-label')||'';
  const more=/^עוד/.test(aria)||/^עוד/.test(t);
  let code=b.dataset.cur||b.dataset.qeCur||b.dataset.code||b.dataset.currency||null;
  if(!code&&!more){const m=t.match(/\b[A-Z]{3}\b/);if(m)code=m[0];else{for(const[s,c] of Object.entries(SYM))if(t.includes(s)){code=c;break}}}
  const cl=b.classList,pressed=b.getAttribute('aria-pressed')==='true'||b.getAttribute('aria-checked')==='true'||b.getAttribute('aria-selected')==='true';
  const r=b.getBoundingClientRect();
  return {code,text:t,aria,more,selected:pressed||cl.contains('active')||cl.contains('on')||cl.contains('selected'),
   src:cl.contains('src'),dst:cl.contains('dst')&&!cl.contains('src'),h:r.height,w:r.width,x:r.left,right:r.right,top:r.top,disabled:!!b.disabled}})}""" % json.dumps(SYM2CODE, ensure_ascii=False)

ROWS = {"P1": "#expenseCurRow", "P4": "#budgetFxRow", "P5": "#quickFxRow", "P7": "#qeCurRow"}


def chips(page, row):
    return page.evaluate(CHIPS_JS, ROWS.get(row, row)) or []


def codes(page, row):
    return [c["code"] for c in chips(page, row) if not c["more"]]


def selected(page, row):
    return [c["code"] for c in chips(page, row) if c["selected"] and not c["more"]]


def pair(page, row):
    cs = chips(page, row)
    f = [c["code"] for c in cs if c["src"]]
    t = [c["code"] for c in cs if c["dst"]]
    return (f[0] if f else None, t[0] if t else None)


def click_chip(page, row, code):
    sel = ROWS.get(row, row)
    ok = page.evaluate("""([sel,code,js])=>{const f=eval(js);const row=document.querySelector(sel);if(!row)return false;
      const info=f(row);const btns=[...row.querySelectorAll('button,[role=button],[role=radio],[role=option]')].filter(b=>!b.parentElement.closest('button'));
      const vis=btns.filter(b=>{const r=b.getBoundingClientRect();return r.width>0&&r.height>0});
      const i=info.findIndex(c=>c.code===code&&!c.more);if(i<0)return false;vis[i].click();return true}""", [sel, code, CHIPS_JS])
    page.wait_for_timeout(250)
    return ok


def more_chip(page, row):
    cs = chips(page, row)
    m = [c for c in cs if c["more"]]
    return m[0] if m else None


def click_more(page, row):
    sel = ROWS.get(row, row)
    ok = page.evaluate("""(sel)=>{const row=document.querySelector(sel);if(!row)return false;
      const b=[...row.querySelectorAll('button,[role=button]')].find(b=>/^עוד/.test(b.getAttribute('aria-label')||'')||/^עוד/.test((b.innerText||'').trim()));
      if(!b)return false;b.click();return true}""", sel)
    page.wait_for_timeout(500)
    return ok


def set_pair(page, row, f, t):
    """Sequential 2-click selection (alpha.8 FX-QUICK-01 / FX-BUDGET-01): first = source, second = destination."""
    for _ in range(3):
        cur = pair(page, row)
        if cur == (f, t):
            return True
        if cur[0] is not None:
            click_chip(page, row, cur[0])       # tapping the source clears both
            if pair(page, row)[0] is not None:   # (if an implementation keeps it, tap again)
                click_chip(page, row, pair(page, row)[0])
        click_chip(page, row, f)
        click_chip(page, row, t)
    return pair(page, row) == (f, t)


# =====================================================================================================
# Text helpers
# =====================================================================================================
def text(page, sel):
    try:
        return page.evaluate("(s)=>{const e=document.querySelector(s);return e?(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim():null}", sel)
    except PWError:
        return None


def attr(page, sel, a):
    try:
        return page.evaluate("([s,a])=>{const e=document.querySelector(s);return e?e.getAttribute(a):null}", [sel, a])
    except PWError:
        return None


NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def nums(s):
    return [float(x.replace(",", "")) for x in NUM_RE.findall(s or "")]


RATE_ROWS_JS = r"""()=>{const box=[...document.querySelectorAll('#budget details')].find(d=>(d.querySelector('summary')||{}).innerText&&d.querySelector('summary').innerText.includes('מחשבון המרה'));
 if(!box)return null;const out=[];
 for(const inp of box.querySelectorAll('input')){if(['fxAmount'].includes(inp.id))continue;
  let lab=null;for(let a=inp.parentElement;a&&a!==box;a=a.parentElement){const t=(a.innerText||'').replace(/\s+/g,' ').trim();const m=t.match(/(1(?:,000|000)?)\s+([A-Z]{3})/);if(m){lab=m[1]+' '+m[2];break}}
  if(!lab)continue;const r=inp.getBoundingClientRect();out.push({label:lab,value:inp.value,id:inp.id,visible:r.width>0&&r.height>0})}
 const rowsNoInput=[];for(const e of box.querySelectorAll('*')){const t=(e.innerText||'').replace(/\s+/g,' ').trim();if(e.children.length===0&&/^(1|1,000|1000) [A-Z]{3}$/.test(t))rowsNoInput.push(t)}
 return {rows:out.filter(r=>r.visible),labels:rowsNoInput,text:(box.innerText||'').replace(/\s+/g,' ').trim()}}"""


def rate_rows(page):
    return page.evaluate(RATE_ROWS_JS)


def set_rate(page, label, value):
    return page.evaluate("""([lab,v,js])=>{const r=eval(js)();const row=r&&r.rows.find(x=>x.label===lab);if(!row)return false;
      const box=[...document.querySelectorAll('#budget details')].find(d=>d.querySelector('summary')&&d.querySelector('summary').innerText.includes('מחשבון המרה'));
      const inp=[...box.querySelectorAll('input')].filter(i=>{const q=i.getBoundingClientRect();return q.width>0}).find(i=>{for(let a=i.parentElement;a&&a!==box;a=a.parentElement){const t=(a.innerText||'').replace(/\\s+/g,' ').trim();const m=t.match(/(1(?:,000|000)?)\\s+([A-Z]{3})/);if(m)return (m[1]+' '+m[2])===lab}return false});
      if(!inp)return false;inp.value=String(v);inp.dispatchEvent(new Event('input',{bubbles:true}));inp.dispatchEvent(new Event('change',{bubbles:true}));return true}""",
                         [label, value, RATE_ROWS_JS])


def click_button_text(page, needle, scope="body"):
    ok = page.evaluate("""([n,s])=>{const root=document.querySelector(s)||document.body;
      const b=[...root.querySelectorAll('button')].find(b=>{const r=b.getBoundingClientRect();return r.width>0&&r.height>0&&(b.innerText||'').includes(n)});
      if(!b)return false;b.click();return true}""", [needle, scope])
    page.wait_for_timeout(400)
    return ok


def open_quick_fx(page):
    page.locator("#globalFxBtn").click()
    page.wait_for_timeout(500)


def hscroll(page):
    return page.evaluate("()=>document.scrollingElement.scrollWidth-innerWidth")


norm, btext, has, wait_has = f04.norm, f04.btext, f04.has, f04.wait_has
wait_until, page_errors = f05.wait_until, f05.page_errors
