"""Lonely Planner F10b QA · browser harness (trip currencies screen: add / swap / remove) · version 1.0.0
CHANGE 2026-11-07 F10B-QA-01: new file (no previous version).

Written from docs/F10b_spec.md only. The F10B blocks of app/index.html and docs/F10b_dev_notes.md were NOT read while this
file was designed; UI is found only by the ids / texts the spec names (#ptF10bRow #ptF10bPanel #ptF10bSub #ptF10bBack
#ptF10bAdd #ptF10bPicker #ptF10bSearch #ptF10bConfirm #ptF10bSwap #ptF10bSwapGo #ptF10bRowSheet #ptF10bDoSwap
#ptF10bDoRemove #ptF10bRemove #ptF10bRemoveGo #ptF10bRO #ptF10bOff #ptF10bFxLink, [data-f10b-act]).

Reuses tests/f10/harness.py (and through it the F21 → … → F02 chain) unchanged. New here:
- F10bBackend: emulation of the spec §0 server facts on `trip_currencies` that the generic fake does not model:
  * trigger trip_currencies_limit — insert that would make >10 rows → `currency_limit: …` (23514), nothing written;
  * trigger trip_currencies_base_lock — update / delete hitting a kind='base' row → `base_currency_locked: …` (23514);
  * duplicate code on insert or on an update that renames the PK → 23505;
  * RLS: writes by managers only (insert → 42501/403, update/delete by non-managers match 0 rows, as PostgREST does);
  * PK-changing UPDATE re-keys the row (the generic fake keeps the old key);
  * `inject(action, kind)` — one-shot error injection for criterion 12 (currency_limit / dup / base / rls403 / network);
  * `writes` — every insert/upsert/update/delete request on trip_currencies as {method POST|PATCH|DELETE, body, filters}.
- Fixtures S / E / F of spec §9 (+ optional LA trip country) on top of F10Backend.fixture.
"""
import copy
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
if "f10_harness" in sys.modules:
    h10 = sys.modules["f10_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f10_harness", str(REPO_DIR / "tests" / "f10" / "harness.py"))
    h10 = importlib.util.module_from_spec(_spec)
    sys.modules["f10_harness"] = h10
    _spec.loader.exec_module(h10)

f02, f04, f05, f06, f20 = h10.f02, h10.f04, h10.f05, h10.f06, h10.f20
BASE_REF = os.environ.get("F10B_BASE_REF", "43394ff")   # 3.0.0-alpha.9 (spec "Base")
CURRENCIES, COUNTRIES = h10.CURRENCIES, h10.COUNTRIES
HE = {k: v["he"] for k, v in CURRENCIES.items()}
SYM = h10.SYM
BASES = ("ILS", "USD", "EUR")
METHOD = {"insert": "POST", "upsert": "POST", "update": "PATCH", "delete": "DELETE"}

h10.FIX.setdefault("E", ("אנגליה חורף 26", "ILS", ["GB"], []))
h10.FIX.setdefault("F", ("דרום-מזרח אסיה מלא", "ILS", ["TH", "VN", "KH"],
                         [("THB", "destination"), ("VND", "destination"), ("KHR", "destination"),
                          ("MYR", "added"), ("SGD", "added"), ("IDR", "added"), ("PHP", "added")]))

def FIX_NAME(key):
    return h10.FIX[key][0]


ERR = {
    "currency_limit": ("23514", "currency_limit: a trip can have at most 10 currencies", 400),
    "dup": ("23505", 'duplicate key value violates unique constraint "trip_currencies_pkey"', 409),
    "base": ("23514", "base_currency_locked: a base currency cannot be removed or changed", 400),
    "rls403": ("42501", 'new row violates row-level security policy for table "trip_currencies"', 403),
}


class F10bBackend(h10.F10Backend):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.writes = []
        self.injected = []

    def fixture(self, key, laos=False, **kw):
        tid = super().fixture(key, **kw)
        if laos:
            self.rows["trip_countries"][(tid, "LA")] = {"trip_id": tid, "country_code": "LA", "sort": 9}
        return tid

    def inject(self, action, kind):
        self.injected.append((action, kind))

    def cur_rows(self, tid):
        return sorted([r for r in self.rows["trip_currencies"].values() if r["trip_id"] == tid], key=lambda r: r["sort"])

    def selects(self, tid=None):
        return [c for c in self.queries("trip_currencies", "select")]

    def query(self, token, req, legacy):
        if str(req.get("table")) != "trip_currencies" or req.get("action") == "select":
            return super().query(token, req, legacy)
        act = req.get("action")
        self.writes.append({"method": METHOD.get(act, act), "action": act, "body": copy.deepcopy(req.get("values")),
                            "filters": copy.deepcopy(req.get("filters") or [])})
        for i, (a, kind) in enumerate(self.injected):
            if a == act or a == "*":
                self.injected.pop(i)
                if kind == "network":
                    return {"error": dict(f02.FETCH_ERR), "status": 0, "data": None}
                c, m, s = ERR[kind]
                return f02._err(c, m, s)
        uid = self.tokens.get(token) if token else None
        if uid is None:
            return f02._err("42501", "permission denied for table trip_currencies", 401)
        mgr = self.active_trips(uid, ("manager",))
        flt = req.get("filters") or []
        store = self.rows["trip_currencies"]
        if act in ("insert", "upsert"):
            vals = req.get("values")
            vals = vals if isinstance(vals, list) else [vals]
            for v in vals:
                if isinstance(v, dict) and v.get("trip_id") not in mgr:
                    return f02._err(*ERR["rls403"])
            for v in vals:
                if isinstance(v, dict) and (str(v.get("trip_id")), str(v.get("currency_code"))) in store and act == "insert":
                    return f02._err(*ERR["dup"])
            tids = {v.get("trip_id") for v in vals if isinstance(v, dict)}
            for t in tids:
                new = {v.get("currency_code") for v in vals if isinstance(v, dict) and v.get("trip_id") == t}
                have = {r["currency_code"] for r in store.values() if r["trip_id"] == t}
                if len(have | new) > 10:
                    return f02._err(*ERR["currency_limit"])
            return super().query(token, req, legacy)
        # update / delete: rows visible + writable
        hit = [r for r in store.values() if r["trip_id"] in mgr and all(self._match(r, f) for f in flt)]
        if any(r.get("kind") == "base" for r in hit):
            return f02._err(*ERR["base"])
        if act == "delete":
            return super().query(token, req, legacy)
        if act != "update":
            return super().query(token, req, legacy)
        v = req.get("values") or {}
        for c in v:
            if c not in ("trip_id", "currency_code", "kind", "sort"):
                return f02._err("PGRST204", "Could not find the '%s' column of 'trip_currencies' in the schema cache" % c, 400)
        if "currency_code" in v:
            if len(hit) > 1:
                return f02._err(*ERR["dup"])
            for r in hit:
                k = (str(r["trip_id"]), str(v["currency_code"]))
                if k in store and store[k] is not r:
                    return f02._err(*ERR["dup"])
        out = []
        for r in hit:
            old = (str(r["trip_id"]), str(r["currency_code"]))
            r.update(v)
            store.pop(old, None)
            store[(str(r["trip_id"]), str(r["currency_code"]))] = r
            out.append(r)
        if req.get("returning"):
            return self._shape("trip_currencies", out, req)
        return {"data": None, "status": 204, "error": None}


class Env(h10.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F10bBackend()


# =====================================================================================================
# Source helpers
# =====================================================================================================
MGR_FLAG_RE = re.compile(r"""((?:const|let|var)\s+CURMGR_FEATURE\s*=\s*)(['"])(on|off)\2""")


def flip_mgr(src, value="off"):
    assert MGR_FLAG_RE.search(src), "const CURMGR_FEATURE='on'|'off' not found (spec §1)"
    return MGR_FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def base_html():
    return h10.f02_git_show(BASE_REF)


# =====================================================================================================
# UI helpers (spec ids only)
# =====================================================================================================
VIS_JS = r"""(s)=>{const e=typeof s==='string'?document.querySelector(s):s;if(!e)return false;const r=e.getBoundingClientRect();
 if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);
 if(c.display==='none'||c.visibility==='hidden'||a.hidden)return false}return true}"""


def vis(page, sel):
    try:
        return page.evaluate(VIS_JS, sel)
    except h10.PWError:
        return False


def wait_vis(page, sel, timeout=6.0, want=True):
    return h10.wait_until(lambda: vis(page, sel) == want, timeout, page)


def open_screen(page):
    h10.tab(page, "more")
    assert wait_vis(page, "#ptF10bRow"), "#ptF10bRow not visible in 'עוד'"
    page.locator("#ptF10bRow").click()
    assert wait_vis(page, "#ptF10bPanel"), "#ptF10bPanel did not open"
    page.wait_for_timeout(600)


# Rows of the screen in DOM order: each "<he> · <CODE>" line with its group ("base" / "other").
ROWS_JS = r"""()=>{const p=document.querySelector('#ptF10bPanel');if(!p)return null;
 const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden')return false}return true};
 const lines=(p.innerText||'').split('\n').map(s=>s.replace(/\s+/g,' ').trim()).filter(Boolean);
 let g=null;const out=[];
 for(const l of lines){if(l.includes('מטבעות בסיס'))g='base';else if(l.includes('יעדים ונוספים'))g='other';
  const m=l.match(/·\s*([A-Z]{3})$/);if(m&&g)out.push({code:m[1],group:g,line:l})}
 const acts=[...p.querySelectorAll('[data-f10b-act]')].filter(vis).map(b=>({code:b.getAttribute('data-f10b-act'),aria:b.getAttribute('aria-label')||''}));
 return {rows:out,acts,text:lines.join(' | ')}}"""


def screen(page):
    return page.evaluate(ROWS_JS) or {"rows": [], "acts": [], "text": ""}


def sheet_buttons(page, sel):
    return page.evaluate(r"""(s)=>{const root=document.querySelector(s);if(!root)return [];
      const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||c.visibility==='hidden')return false}return true};
      return [...root.querySelectorAll('button,[role=radio],[role=option]')].filter(b=>!b.parentElement.closest('button')&&vis(b)).map(b=>{
        const t=(b.innerText||'').replace(/\s+/g,' ').trim();const m=t.match(/\b[A-Z]{3}\b/);
        return {text:t,code:b.dataset.code||b.dataset.cur||(m?m[0]:null),disabled:!!b.disabled||b.getAttribute('aria-disabled')==='true',
                pressed:b.getAttribute('aria-pressed'),id:b.id||''}})}""", sel)


def click_option(page, sel, code):
    ok = page.evaluate(r"""([s,code])=>{const root=document.querySelector(s);if(!root)return false;
      const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||c.visibility==='hidden')return false}return true};
      const re=new RegExp('\\b'+code+'\\b');
      const b=[...root.querySelectorAll('button,[role=radio],[role=option]')].filter(b=>!b.parentElement.closest('button')&&vis(b)&&!b.disabled&&!b.id)
        .find(b=>b.dataset.code===code||b.dataset.cur===code||re.test(b.innerText||''));
      if(!b)return false;b.scrollIntoView({block:'center'});b.click();return true}""", [sel, code])
    page.wait_for_timeout(350)
    return ok


# Sheets by spec id; when the id is missing (F10B-BUG-01) fall back to the dialog that contains the spec-named control,
# so the remaining behaviour can still be tested. test_c04_sheet_ids asserts the ids themselves.
PICK = "#ptF10bPicker, [role=dialog]:has(#ptF10bSearch)"
SWAP = "#ptF10bSwap, [role=dialog]:has(#ptF10bSwapGo)"


def open_picker(page):
    page.locator("#ptF10bAdd").click()
    assert wait_vis(page, PICK), "#ptF10bPicker did not open"
    page.wait_for_timeout(300)


def search(page, q):
    page.fill("#ptF10bSearch", q)
    page.dispatch_event("#ptF10bSearch", "input")
    page.wait_for_timeout(400)


def pick(page, code):
    """Choose `code` in the picker (search first so the row is on screen) and press confirm when the picker stays."""
    search(page, code)
    assert click_option(page, PICK, code), "picker: option %s not found / enabled (%r)" % (
        code, [b["text"] for b in sheet_buttons(page, PICK)][:12])


def confirm(page):
    page.locator("#ptF10bConfirm").click()
    page.wait_for_timeout(900)


def row_sheet(page, code):
    page.locator('#ptF10bPanel [data-f10b-act="%s"]' % code).click()
    assert wait_vis(page, "#ptF10bRowSheet"), "#ptF10bRowSheet did not open for %s" % code
    page.wait_for_timeout(250)


def text(page, sel):
    return h10.text(page, sel) or ""


def writes(be, method=None):
    return [w for w in be.writes if method is None or w["method"] == method]


def eqf(w, col):
    for f in w["filters"]:
        if f.get("op") == "eq" and f.get("col") == col:
            return f.get("val")
    return None


SIG_JS = r"""(sels)=>{const out={};const vis=e=>{for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none')return false}return true};
 const walk=(e,acc)=>{const a=[e.tagName,e.id||'',[...e.classList].sort().join('.'),e.getAttribute('aria-label')||'',e.getAttribute('placeholder')||'',
   Object.keys(e.dataset).sort().map(k=>k+'='+e.dataset[k]).join(','),vis(e)?'v':'h'];
   const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.replace(/\s+/g,' ').trim()).filter(Boolean).join('|');
   acc.push(a.join('~')+(own?' "'+own+'"':''));for(const c of e.children)if(!['SCRIPT','STYLE'].includes(c.tagName))walk(c,acc)};
 for(const s of sels){const e=document.querySelector(s);const acc=[];if(e)walk(e,acc);out[s]=acc}return out}"""

# controls < 44px and box overflow inside a container (spec §8 / criterion 15)
LAYOUT_JS = r"""(s)=>{const root=document.querySelector(s);if(!root)return null;
 const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||c.visibility==='hidden')return false}return true};
 const small=[...root.querySelectorAll('button,input,select,a[href],[role=button],[role=radio]')].filter(vis).filter(b=>!b.parentElement.closest('button'))
   .map(b=>{const r=b.getBoundingClientRect();return {t:(b.innerText||b.getAttribute('aria-label')||b.id||b.tagName).replace(/\s+/g,' ').trim().slice(0,30),h:Math.round(r.height),w:Math.round(r.width)}})
   .filter(x=>x.h<43.5);
 const over=[...root.querySelectorAll('*')].filter(vis).map(e=>e.getBoundingClientRect()).filter(r=>r.left<-0.5||r.right>innerWidth+0.5).length;
 return {small,over,dir:getComputedStyle(root).direction,scroll:document.scrollingElement.scrollWidth-innerWidth}}"""


def layout(page, sel):
    return page.evaluate(LAYOUT_JS, sel)


norm, saw_toast, toasts, page_errors, wait_until = h10.norm, f05.saw_toast, f05.toasts, h10.page_errors, h10.wait_until
boot, reboot, tripcur, go_offline, tab, open_quick_fx, codes, more_chip, open_budget = (
    h10.boot, h10.reboot, h10.tripcur, h10.go_offline, h10.tab, h10.open_quick_fx, h10.codes, h10.more_chip, h10.open_budget)
serve_src, app_html, set_pair, nums = h10.serve_src, h10.app_html, h10.set_pair, h10.nums
