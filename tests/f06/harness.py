"""Lonely Planner F06 QA · browser harness (fake backend, devices, helpers) · version 1.0.0
CHANGE 2026-10-22 F06-QA-03: first version (no previous version). Reuses the F05 harness (tests/f05/harness.py → F20 → F04 →
F03 → F02) for the GitHub-Pages-like server, the PostgREST-like query engine with the F01 RLS model, anonymous sign-in, the
F05 fake supabase-js with Realtime (tests/f05/fake_supabase.js — used unchanged: it already routes any
functions.invoke(name) to the backend), join-trip / approve-member and the UI helpers.

What is new for F06 (written from docs/F06_spec.md §2–§3 only; the F06 app code, 0014_f06.sql and the manage-members source
were NOT read):
- F06Backend.manage-members: in-memory set_role / rename / remove / leave / rotate_link / touch with the §2 semantics
  (active-manager check, not_active targets, last_manager, name rules of F05 D5, transfer codes deleted on removal/leave,
  rotation = new 8-char code + version+1, touch at most once per 10 min) and the §3.1 HTTP statuses. Every trip_members
  change is a Realtime event. Reachable through a route-intercepted POST <PT_URL>/functions/v1/manage-members and through
  supabase.functions.invoke('manage-members').
- join-trip D2 (§2.6): a removed identity previews as a new one (me=null) and its request re-uses the row (pending, new
  name, default role, joined_at=now, approved_at=null). `legacy_removed=True` emulates the alpha.6 server (member_removed).
- tripname trigger (§2.7): a trip_kv write of key 'tripname' by an active manager updates trips.name (cleaned, 1–80).
- Realtime for removed members (D11): by default a removed member gets NO event for its own row (`rt_removed_events=False`,
  the spec's assumption); tests can turn it on (what RLS `user_id = auth.uid()` would actually allow — see README A-11).
- Text watcher (TEXTS_JS): counts the rising edges of chosen texts in document.body.innerText every 100 ms, so toasts are
  seen whatever element shows them (F06 element ids are not in the spec).
"""
import copy
import datetime as dt
import importlib.util
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))

if "f05_harness" in sys.modules:
    f05 = sys.modules["f05_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f05_harness", str(REPO_DIR / "tests" / "f05" / "harness.py"))
    f05 = importlib.util.module_from_spec(_spec)
    sys.modules["f05_harness"] = f05
    _spec.loader.exec_module(f05)
f20, f04, f03, f02 = f05.f20, f05.f04, f05.f03, f05.f02

from playwright.sync_api import Error as PWError  # noqa: E402

PT_URL = f05.PT_URL
MM_URL = PT_URL + "/functions/v1/manage-members"
ROOT, APP, JOIN = f05.ROOT, f05.APP, f05.JOIN
APP_DIR, JOIN_DIR = f05.APP_DIR, f05.JOIN_DIR
VIEWPORT, FIXED_NOW, DAY, HOUR = f05.VIEWPORT, f05.FIXED_NOW, f05.DAY, f05.HOUR
MINUTE = dt.timedelta(minutes=1)
JOIN_ALPHABET = f05.JOIN_ALPHABET
ROLES = ("viewer", "editor", "manager")
MM_STATUS = {"unauthorized": 401, "invalid_request": 400, "role_invalid": 400, "name_invalid": 400, "not_manager": 403,
             "not_member": 403, "not_active": 409, "name_taken": 409, "last_manager": 409}
FN_VERSION = "3.0.0-alpha.7.0"
iso, clean_name = f05.iso, f05.clean_name


def name_key(s):
    # F05 D5 / F06 D7: case- and space-insensitive (private.f05_name_key = lower(clean))
    return clean_name(s).lower()


# =====================================================================================================
# Fake backend
# =====================================================================================================
class F06Backend(f05.F05Backend):
    def __init__(self):
        super().__init__()
        self.mm_calls = []             # {device, via, action, body, uid, status, resp}
        self.mm_force = {}             # action -> error code (returned while set)
        self.mm_down = False           # manage-members fails like a network error
        self.mm_hang = False
        self.legacy_removed = False    # True: join-trip answers member_removed for a removed identity (alpha.6 server)
        self.rt_removed_events = False  # D11: a removed member receives no Realtime event for its own row
        self.touches = []

    # ---------- dataset ----------
    def add(self, tid, name, role="editor", status="active", uid=None, days_ago=30, last_seen=None):
        uid = uid or str(uuid.uuid4())
        mid = self.add_member(tid, uid, role, status, name, joined_at=iso(self.tnow() - dt.timedelta(days=days_ago)))
        row = self.member(mid)
        row["last_seen_at"] = iso(last_seen) if isinstance(last_seen, dt.datetime) else last_seen
        return mid

    def trip_name(self, tid):
        return self.rows["trips"][(tid,)]["name"]

    def join_code(self, tid):
        r = self.rows["trip_join_codes"].get((tid,))
        return r["code"] if r else None

    def kv_json(self, tid, key, default=None):
        raw = self.kv(tid, key)
        try:
            return json.loads(raw) if raw else default
        except ValueError:
            return default

    # ---------- Realtime: removed members do not see their own row (D11 default) ----------
    def rt_visible(self, uid, ev):
        if ev["eventType"] == "DELETE":
            return True
        new = ev["new"]
        if new.get("user_id") == uid and new.get("status") != "active" and new.get("trip_id") not in self.active_trips(uid):
            return self.rt_removed_events or new.get("status") == "pending"
        return super().rt_visible(uid, ev)

    # ---------- binding entry ----------
    def handle(self, device, msg):
        msg = msg or {}
        if msg.get("op") == "functions.invoke" and msg.get("name") == "manage-members":
            with self.lock:
                self.calls.append({"device": device, "t": time.time(), "op": "functions.invoke", "page": msg.get("page"),
                                   "online": msg.get("online"), "url": str(msg.get("url") or ""), "msg": copy.deepcopy(msg)})
                if msg.get("online") is False or self.mode == "down" or self.mm_down:
                    return {"offline": True}
                if self.mm_hang:
                    return {"hang": True}
                status, body = self.mm(device, "invoke", msg.get("token") or msg.get("key"), msg.get("body") or {})
                return {"httpStatus": status, "json": body}
        return super().handle(device, msg)

    # ---------- trip_kv tripname trigger (§2.7) ----------
    def query(self, token, req, legacy):
        res = super().query(token, req, legacy)
        try:
            if str(req.get("table")) == "trip_kv" and req.get("action") in ("insert", "upsert", "update") and not (res or {}).get("error"):
                uid = self.tokens.get(token) if token else None
                vals = req.get("values")
                vals = vals if isinstance(vals, list) else [vals]
                flt = {f.get("col"): f.get("val") for f in req.get("filters") or [] if f.get("op") == "eq"}
                for v in vals:
                    if not isinstance(v, dict) or "value" not in v:
                        continue
                    tid = v.get("trip_id") or flt.get("trip_id")
                    key = v.get("key") or flt.get("key")
                    if key != "tripname" or not tid or (tid,) not in self.rows["trips"]:
                        continue
                    if uid and tid in self.active_trips(uid, ("manager",)):
                        nm = clean_name(v.get("value") if isinstance(v.get("value"), str) else "")
                        if 1 <= len(nm) <= 80:
                            self.rows["trips"][(tid,)]["name"] = nm
        except Exception:  # pragma: no cover - the trigger never blocks the write (§2.7)
            pass
        return res

    # ---------- join-trip D2 (§2.6) ----------
    def _join_trip(self, uid, b):
        act = b.get("action")
        if act in ("preview", "request") and not self.legacy_removed and not self.force.get(("join-trip", act)):
            tid = self._trip_for(b.get("code"))
            me = self.member_of(tid, uid) if tid else None
            if me and me["status"] == "removed":
                if act == "preview":
                    # §2.6: answer as for a new identity (me = null) — hide the removed row for the duration of the call
                    self.rows["trip_members"].pop((me["id"],), None)
                    try:
                        return super()._join_trip(uid, b)
                    finally:
                        self.rows["trip_members"][(me["id"],)] = me
                return self._rerequest(uid, tid, me, b)
        return super()._join_trip(uid, b)

    def _rerequest(self, uid, tid, me, b):
        now = self.tnow()
        name = clean_name(b.get("display_name"))
        if not isinstance(b.get("display_name"), str) or not (1 <= len(name) <= 40):
            return self._err("name_invalid")
        if self._count("request", now - DAY, uid=uid, trip=tid, ok=True) >= 3:
            self._log("request", uid, tid, False)
            return self._err("rate_limited")
        if len(self.members(tid, "pending")) >= 20:
            self._log("request", uid, tid, False)
            return self._err("rate_limited")
        if any(name_key(r["display_name"]) == name_key(name) for r in self.members(tid)
               if r["status"] in ("pending", "active") and r["id"] != me["id"]):
            self._log("request", uid, tid, False)
            return self._err("name_taken")
        self.mut_update(me, status="pending", display_name=name, role=self.rows["trips"][(tid,)]["default_role"],
                        joined_at=iso(now), approved_at=None)
        self._log("request", uid, tid, True)
        return 200, {"trip_id": tid, "member_id": me["id"], "status": "pending", "role": me["role"], "display_name": name,
                     "created": False}

    # ---------- manage-members (§2, §3.1) ----------
    def mm(self, device, via, bearer, body):
        with self.lock:
            uid = self.tokens.get(bearer) if bearer else None
            body = body if isinstance(body, dict) else {}
            act = body.get("action")
            if not uid:
                status, resp = 401, {"error": "unauthorized"}
            elif self.mm_force.get(act):
                code = self.mm_force[act]
                status, resp = MM_STATUS.get(code, 500), {"error": code}
            else:
                status, resp = self._mm(uid, act, body)
            if act == "rotate_link" and status == 200:
                resp = dict(resp, link_version=resp.get("version"))   # see README A-FN-1
            resp = dict(resp, version=FN_VERSION)
            self.mm_calls.append({"device": device, "via": via, "action": act, "body": copy.deepcopy(body), "uid": uid,
                                  "status": status, "resp": copy.deepcopy(resp)})
            return status, resp

    def mm_of(self, action=None, device=None):
        return [c for c in self.mm_calls if (action is None or c["action"] == action) and (device is None or c["device"] == device)]

    def _e(self, code):
        return MM_STATUS.get(code, 500), {"error": code}

    def _is_mgr(self, uid, tid):
        return tid in self.active_trips(uid, ("manager",))

    def _n_mgr(self, tid):
        return len([r for r in self.members(tid, "active") if r["role"] == "manager"])

    def _drop_transfers(self, mid):
        self.transfers = [t for t in self.transfers if not (t["member_id"] == mid and not t["used_at"])]

    def _mm(self, uid, act, b):
        U = f02.UUID_RE
        if act in ("set_role", "rename", "remove"):
            mid = b.get("member_id")
            if not isinstance(mid, str) or not U.match(mid):
                return self._e("invalid_request")
            row = self.member(mid)
            if not row or not self._is_mgr(uid, row["trip_id"]):
                return self._e("not_manager")
            if row["status"] != "active":
                return self._e("not_active")
            tid = row["trip_id"]
            if act == "set_role":
                role = b.get("role")
                if role not in ROLES:
                    return self._e("role_invalid")
                if role == row["role"]:
                    return 200, {"ok": True, "member_id": mid, "role": role, "changed": False}
                if row["role"] == "manager" and self._n_mgr(tid) <= 1:
                    return self._e("last_manager")
                self.mut_update(row, role=role)
                return 200, {"ok": True, "member_id": mid, "role": role, "changed": True}
            if act == "rename":
                nm = clean_name(b.get("display_name"))
                if not isinstance(b.get("display_name"), str) or not (1 <= len(nm) <= 40):
                    return self._e("name_invalid")
                if any(name_key(r["display_name"]) == name_key(nm) for r in self.members(tid)
                       if r["status"] in ("pending", "active") and r["id"] != mid):
                    return self._e("name_taken")
                self.mut_update(row, display_name=nm)
                return 200, {"ok": True, "member_id": mid, "display_name": nm}
            # remove
            if row["user_id"] == uid:
                return self._e("invalid_request")
            if row["role"] == "manager" and self._n_mgr(tid) <= 1:
                return self._e("last_manager")
            self.mut_update(row, status="removed")
            self._drop_transfers(mid)
            return 200, {"ok": True, "member_id": mid}
        if act in ("leave", "rotate_link", "touch"):
            tid = b.get("trip_id")
            if not isinstance(tid, str) or not U.match(tid):
                return self._e("invalid_request")
            if act == "rotate_link":
                if not self._is_mgr(uid, tid):
                    return self._e("not_manager")
                jc = self.rows["trip_join_codes"][(tid,)]
                jc["code"] = self.new_join_code()
                jc["version"] += 1
                jc["rotated_at"] = iso(self.tnow())
                return 200, {"code": jc["code"], "version": jc["version"]}
            me = self.member_of(tid, uid)
            if not me or me["status"] != "active":
                return self._e("not_member")
            if act == "leave":
                if me["role"] == "manager" and self._n_mgr(tid) <= 1:
                    return self._e("last_manager")
                self.mut_update(me, status="removed")
                self._drop_transfers(me["id"])
                return 200, {"ok": True}
            # touch: at most once per 10 minutes
            last = me.get("last_seen_at")
            now = self.tnow()
            if not last or dt.datetime.fromisoformat(last) <= now - 10 * MINUTE:
                me["last_seen_at"] = iso(now)
                self.touches.append({"member_id": me["id"], "at": iso(now)})
                return 200, {"ok": True, "last_seen_at": iso(now), "written": True}
            return 200, {"ok": True, "last_seen_at": last, "written": False}
        return self._e("invalid_request")

    # ---------- direct actions (the manager on another phone, without a browser) ----------
    def set_role_direct(self, mid, role):
        with self.lock:
            self.mut_update(self.member(mid), role=role)

    def remove_direct(self, mid):
        with self.lock:
            row = self.member(mid)
            self.mut_update(row, status="removed")
            self._drop_transfers(mid)

    def rename_direct(self, mid, name):
        with self.lock:
            self.mut_update(self.member(mid), display_name=name)


# =====================================================================================================
# Browser environment
# =====================================================================================================
# Rising-edge counter for texts in the page (toasts, banners) — independent of element ids.
TEXTS_JS = r"""(()=>{if(window.__qaTexts)return;const W=window.__qaTexts={want:[],seen:{},on:{},at:{}};
 const n=s=>String(s||'').replace(/[‎‏‪-‮⁦-⁩]/g,'').replace(/[–—‒−]/g,'-')
   .replace(/[״“”„]/g,'"').replace(/\s+/g,' ');
 window.__qaWatchTexts=a=>{for(const t of a){const k=n(t).trim();if(!W.want.includes(k)){W.want.push(k);W.seen[k]=0;W.on[k]=false;W.at[k]=[]}}};
 setInterval(()=>{let b='';try{b=n(document.body?document.body.innerText:'')}catch(e){}
   for(const k of W.want){const p=b.includes(k);if(p&&!W.on[k]){W.seen[k]++;W.at[k].push(Date.now())}W.on[k]=p}},100)})();"""
VIS_JS = r"""(()=>{window.__qaSetVis=(v)=>{window.__qaVis=v;try{Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>window.__qaVis})}catch(e){}
 try{Object.defineProperty(document,'hidden',{configurable:true,get:()=>window.__qaVis==='hidden'})}catch(e){}
 document.dispatchEvent(new Event('visibilitychange'))}})();"""


class Env(f05.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F06Backend()

    def new_device(self, name="A", **kw):
        d = super().new_device(name, **kw)
        d.ctx.add_init_script(TEXTS_JS)
        d.ctx.add_init_script(VIS_JS)
        return d

    def _route5(self, dev, route, request):
        url = request.url
        base = url.split("#")[0].split("?")[0].rstrip("/")
        if base != MM_URL:
            return super()._route5(dev, route, request)
        be = self.backend
        rec = {"device": dev.name, "url": url, "method": request.method, "type": request.resource_type}
        self.net.append(rec)
        try:
            origin = request.headers.get("origin") or "*"
            cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Vary": "Origin",
                    "x-function-version": FN_VERSION}
            if dev.is_offline or be.mode == "down" or be.mm_down:
                rec["action"] = "fn-offline"
                return route.abort("internetdisconnected")
            if request.method == "OPTIONS":
                rec["action"] = "fn-preflight"
                return route.fulfill(status=204, headers=cors, body="")
            if be.mm_hang:
                rec["action"] = "fn-hang"
                return None
            try:
                body = json.loads(request.post_data or "{}")
            except ValueError:
                body = {"__unparsable": request.post_data}
            rec["body"] = body
            hdrs = {k.lower(): v for k, v in request.headers.items()}
            auth = hdrs.get("authorization") or ""
            bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
            rec["action"] = "fn"
            status, resp = be.mm(dev.name, "fetch", bearer, body)
            return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(resp))
        except PWError:
            pass


# =====================================================================================================
# Source helpers (flag flips)
# =====================================================================================================
MEMBERS_FLAG_RE = re.compile(r"""(const\s+MEMBERS_FEATURE\s*=\s*)(['"])(on|off)\2""")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def join_html():
    return (JOIN_DIR / "index.html").read_text(encoding="utf-8")


def flip_members(src, value="off"):
    assert MEMBERS_FLAG_RE.search(src), "const MEMBERS_FEATURE='on' not found (spec §1: flag next to JOIN_FEATURE)"
    return MEMBERS_FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def serve_members_off(env, app=True, join=True):
    if app:
        b = flip_members(app_html(), "off").encode("utf-8")
        env.server.overrides[APP + "index.html"] = b
        env.server.overrides[APP] = b
    if join:
        b = flip_members(join_html(), "off").encode("utf-8")
        env.server.overrides[JOIN + "index.html"] = b
        env.server.overrides[JOIN] = b


# =====================================================================================================
# UI helpers
# =====================================================================================================
norm, btext, has, wait_has = f05.norm, f05.btext, f05.has, f05.wait_has
find, click_text, visible, wait_text = f05.find, f05.click_text, f05.visible, f05.wait_text
layout_problems, is_vis, exists, wait_until = f05.layout_problems, f05.is_vis, f05.exists, f05.wait_until
page_errors, app_state, wait_app_state, running_trip = f05.page_errors, f05.app_state, f05.wait_app_state, f05.running_trip


def watch(page, *texts):
    page.evaluate("(a)=>window.__qaWatchTexts&&window.__qaWatchTexts(a)", list(texts))


def seen_count(page, text):
    try:
        return page.evaluate("(k)=>{const W=window.__qaTexts;return W?(W.seen[k]||0):-1}", norm(text))
    except PWError:
        return -1


def set_visibility(page, v):
    page.evaluate("(v)=>window.__qaSetVis(v)", v)


def to_background_and_back(page, hidden_ms=500):
    set_visibility(page, "hidden")
    page.wait_for_timeout(hidden_ms)
    set_visibility(page, "visible")


def ls_page(dev):
    """localStorage read through the app page itself (same origin) — works while the device is offline, unlike the F02 raw
    page (which has to navigate to a blank page first)."""
    try:
        return dev.page.evaluate(f02.RAW_LS_DUMP)
    except PWError:
        return dev.ls()


def ls_trip(dev, tid):
    p = "pt:%s:" % tid
    return {k: v for k, v in ls_page(dev).items() if k.startswith(p)}


def queue(dev, tid):
    return f02.queue_of(ls_page(dev), "pt:%s:" % tid) or []
