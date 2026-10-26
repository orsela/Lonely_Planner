"""Plan_Travel F05 QA · browser harness (fake backend, server, devices, helpers) · version 1.0.1
CHANGE 2026-10-19 F05-QA-03: first version (no previous version).
CHANGE 2026-10-26 QA-DEBT-09: 1.0.0 → 1.0.1: STANDALONE_JS (standalone=True devices) returned a fake MediaQueryList built
  with Object.assign onto Object.create(MediaQueryList.prototype); `matches` is a getter-only accessor there, so EVERY
  matchMedia('(display-mode: standalone)') call threw "Cannot set property matches … which has only a getter" (found by the
  F04-HOME QA team, tests/f04home/harness.py). It now returns a plain object (same fields), like the F04-HOME harness; the
  app's isStandalone() / join/flow.js caught the throw and fell back to navigator.standalone, which hid the bug.
  test_f05.py::test_h00_standalone_fake guards it. Nothing else changed. Reuses the F20 harness (tests/f20/test_f20.py, which
imports F04 → F03 → F02) for the PostgREST-like query engine, RLS rules, anonymous sign-in, flag flips and UI helpers.

What is new for F05:
- F05Server: serves the REPO layout like GitHub Pages: /Lonely_Planner/app/… = APP dir (or a flag-flipped copy),
  /Lonely_Planner/join/… = JOIN dir (or a flipped copy), everything else under /Lonely_Planner/ from the repo root, plus
  the F02 raw-storage blank page. /join/ and /app/ share one origin (spec §1.1: "same origin as /app/").
- F05Backend (extends F20Backend): an in-memory implementation of the two Edge Functions of spec §3 (`join-trip`:
  preview / request / cancel / issue_transfer / claim_transfer; `approve-member`) with the database semantics of spec §2
  (cleaned names, name_taken among pending+active case/space-insensitive, default role, removed, rate limits 3 requests per
  trip per 24 h, 20 pending per trip, 5 failed claims per hour, transfer codes 24 h single use, re-issue voids the old
  code). Response shapes and HTTP statuses are those the delivered functions produce (README of each function, observed
  through their exported handler: success = the SQL result object, refusal = {"error": code} with 400/403/404/409/429).
  Every change of trip_members is recorded as a Realtime event (INSERT / UPDATE / DELETE) for the fake library.
  Reachable both through a route-intercepted POST <PT_URL>/functions/v1/<name> and through supabase.functions.invoke.
- Devices: optional iPhone Safari UA (+ touch), optional `navigator.standalone` / display-mode standalone (the installed
  app), the F20 cookie-based offline boot.
"""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import mimetypes
import os
import random
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
os.environ.setdefault("APP_DIR", str(REPO_DIR / "app"))
os.environ.setdefault("PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS", "1")
APP_DIR = Path(os.environ["APP_DIR"])
JOIN_DIR = Path(os.environ.get("JOIN_DIR", str(REPO_DIR / "join")))

if "f20_harness" in sys.modules:
    f20 = sys.modules["f20_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f20_harness", str(REPO_DIR / "tests" / "f20" / "test_f20.py"))
    f20 = importlib.util.module_from_spec(_spec)
    sys.modules["f20_harness"] = f20
    _spec.loader.exec_module(f20)
f04, f03, f02 = f20.f04, f20.f03, f20.f02

from playwright.sync_api import Error as PWError  # noqa: E402

FAKE_JS = (HERE / "fake_supabase.js").read_text(encoding="utf-8")
PT_URL, PT_KEY = f02.PT_URL, f02.PT_KEY
JT_URL = PT_URL + "/functions/v1/join-trip"
AM_URL = PT_URL + "/functions/v1/approve-member"
ROOT = "/Lonely_Planner/"
APP = ROOT + "app/"
JOIN = ROOT + "join/"
VIEWPORT = f02.VIEWPORT
FIXED_NOW = f04.FIXED_NOW
DAY = dt.timedelta(days=1)
HOUR = dt.timedelta(hours=1)
JOIN_ALPHABET = f04.JOIN_ALPHABET
ROLES = ("viewer", "editor", "manager")
ROLE_HE = {"viewer": "צופה", "editor": "עורך", "manager": "מנהל"}
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/17.5 Mobile/15E148 Safari/604.1")
IPAD_DESKTOP_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                   "Version/17.5 Safari/605.1.15")
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
              "Mobile Safari/537.36")
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
              "Safari/537.36")
STATUS = {"unauthorized": 401, "invalid_request": 400, "name_invalid": 400, "role_invalid": 400, "code_invalid": 404,
          "name_taken": 409, "not_pending": 409, "transfer_invalid": 409, "already_member": 409, "member_removed": 403,
          "not_member": 403, "not_manager": 403, "rate_limited": 429}


def iso(t):
    return t.isoformat()


def clean_name(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def name_key(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def norm_join_code(v):
    if not isinstance(v, str):
        return None
    m = re.search(r"code=([^&\s]+)", v)
    s = m.group(1) if m else v
    s = re.sub(r"[\s-]", "", s).upper()
    return s if re.fullmatch("[%s]{8}" % JOIN_ALPHABET, s) else None


# =====================================================================================================
# Server (repo layout as on GitHub Pages)
# =====================================================================================================
class F05Server:
    def __init__(self):
        self.overrides = {}   # exact url path -> bytes
        self.app_dir = APP_DIR
        self.join_dir = JOIN_DIR
        self.log = []
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = unquote(urlparse(self.path).path)
                srv.log.append(path)
                if path in srv.overrides:
                    return self._send(200, srv.overrides[path], mimetypes.guess_type(path)[0] or "text/html")
                if path == f02.BLANK_PATH:
                    return self._send(200, b"<!doctype html><meta charset=utf-8><title>qa</title>", "text/html")
                for prefix, root in ((APP, srv.app_dir), (JOIN, srv.join_dir), (ROOT, REPO_DIR)):
                    if path == prefix.rstrip("/"):
                        self.send_response(301)
                        self.send_header("Location", prefix)
                        self.end_headers()
                        return
                    if path.startswith(prefix):
                        rel = path[len(prefix):]
                        f = (Path(root) / rel).resolve()
                        if not str(f).startswith(str(Path(root).resolve())):
                            return self._send(403, b"forbidden", "text/plain")
                        if f.is_dir():
                            if (prefix + rel + "index.html") in srv.overrides:
                                return self._send(200, srv.overrides[prefix + rel + "index.html"], "text/html")
                            f = f / "index.html"
                        if f.is_file():
                            ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                            return self._send(200, f.read_bytes(), ctype)
                        return self._send(404, b"not found", "text/plain")
                return self._send(404, b"not found", "text/plain")

            def _send(self, code, body, ctype):
                self.send_response(code)
                if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                    ctype += "; charset=utf-8"
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.origin = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def reset(self):
        self.overrides.clear()
        self.app_dir, self.join_dir = APP_DIR, JOIN_DIR

    def stop(self):
        self.httpd.shutdown()


# =====================================================================================================
# Fake backend: F20 backend + the two F05 Edge Functions + Realtime events
# =====================================================================================================
class F05Backend(f20.F20Backend):
    def __init__(self):
        super().__init__()
        self.rt_events = []          # {seq, schema, table, eventType, new, old, commit_timestamp}
        self.rt_silent = False       # subscribe succeeds but no event is ever delivered (poll-only tests)
        self.rt_subs = []            # {device, name, bindings, uid}
        self.transfers = []          # {member_id, code, expires_at, used_at}
        self.attempts = []           # {kind, uid, trip_id, ok, at}
        self.fn_calls = []           # {device, via, name, body, uid, status, resp}
        self.force = {}              # (fn, action) -> error code returned once per call while set
        self.fn_down_names = set()   # function names that fail like a network error
        self.hang_fns = set()        # function names that never answer
        self.code_seq = []           # next transfer codes to issue (tests can pin them)
        self.clock_offset = dt.timedelta(0)

    # ---------- clock ----------
    def tnow(self):
        return self.now + self.clock_offset

    # ---------- dataset helpers ----------
    def trip(self, name="יפן 2027", start=dt.date(2027, 4, 3), n_days=18, default_role="editor", managers=(("דנה", None),),
             others=(), code=None):
        """A trip as F04 leaves it + members. managers / others: (display_name, joined_at|None) — no uid = not a device."""
        tid, jc = self.seed_trip(name, n_days=n_days, start=start, code=code)
        self.rows["trips"][(tid,)]["default_role"] = default_role
        self.set_kv(tid, "tripname", name)
        k = 0
        for n, j in managers:
            k += 1
            self.add_member(tid, str(uuid.uuid4()), "manager", "active", n,
                            joined_at=j or iso(self.tnow() - dt.timedelta(days=60 - k)))
        for item in others:
            n, role = item[0], (item[1] if len(item) > 1 else "editor")
            k += 1
            self.add_member(tid, str(uuid.uuid4()), role, "active", n, joined_at=iso(self.tnow() - dt.timedelta(days=40 - k)))
        return tid, jc

    def members(self, tid, status=None):
        rows = [r for r in self.rows["trip_members"].values() if r["trip_id"] == tid and (status is None or r["status"] == status)]
        return sorted(rows, key=lambda r: (r["joined_at"] or "", r["id"]))

    def member(self, mid):
        return self.rows["trip_members"].get((mid,))

    def member_of(self, tid, uid):
        return next((r for r in self.rows["trip_members"].values() if r["trip_id"] == tid and r["user_id"] == uid), None)

    def uid_of(self, device):
        return self.uid_of_device(device)

    # ---------- Realtime ----------
    def _event(self, etype, new, old):
        with self.lock:
            self.rt_events.append({"seq": len(self.rt_events) + 1, "schema": "public", "table": "trip_members",
                                   "eventType": etype, "new": copy.deepcopy(new) if new else {},
                                   "old": {"id": old["id"]} if old else {}, "commit_timestamp": iso(self.tnow()),
                                   "errors": None})

    def mut_insert(self, row):
        self.rows["trip_members"][(row["id"],)] = row
        self._event("INSERT", row, None)

    def mut_update(self, row, **fields):
        row.update(fields)
        self._event("UPDATE", row, row)

    def mut_delete(self, row):
        self.rows["trip_members"].pop((row["id"],), None)
        self._event("DELETE", None, row)

    def new_pending(self, tid, name, uid=None, minutes_ago=5):
        """A pending request that arrives 'now' from someone else (live update tests)."""
        uid = uid or str(uuid.uuid4())
        mid = str(uuid.uuid4())
        row = {"id": mid, "trip_id": tid, "user_id": uid, "display_name": name, "role": self.rows["trips"][(tid,)]["default_role"],
               "status": "pending", "joined_at": iso(self.tnow() - dt.timedelta(minutes=minutes_ago)),
               "approved_at": None, "last_seen_at": None}
        with self.lock:
            self.mut_insert(row)
        return mid

    def rt_visible(self, uid, ev):
        if ev["eventType"] == "DELETE":
            return True
        new = ev["new"]
        return new.get("user_id") == uid or new.get("trip_id") in self.active_trips(uid)

    # ---------- binding entry ----------
    def handle(self, device, msg):
        msg = msg or {}
        op = msg.get("op")
        if op in ("rt.subscribe", "rt.poll"):
            with self.lock:
                offline = msg.get("online") is False or self.mode == "down"
                if offline:
                    return {"status": "CHANNEL_ERROR"}
                uid = self.tokens.get(msg.get("token"))
                if op == "rt.subscribe":
                    self.rt_subs.append({"device": device, "name": msg.get("name"), "bindings": msg.get("bindings"),
                                         "uid": uid, "t": time.time()})
                    return {"ok": True, "cursor": len(self.rt_events)}
                since = int(msg.get("since") or 0)
                evs = [] if self.rt_silent or not uid else [e for e in self.rt_events[since:] if self.rt_visible(uid, e)]
                return {"events": copy.deepcopy(evs), "cursor": len(self.rt_events)}
        if op == "functions.invoke" and msg.get("name") in ("join-trip", "approve-member"):
            with self.lock:
                entry = {"device": device, "t": time.time(), "op": op, "page": msg.get("page"), "online": msg.get("online"),
                         "url": str(msg.get("url") or ""), "msg": copy.deepcopy(msg)}
                self.calls.append(entry)
                name = msg.get("name")
                if msg.get("online") is False or self.mode == "down" or name in self.fn_down_names:
                    return {"offline": True}
                if name in self.hang_fns:
                    return {"hang": True}
                status, body = self.fn(device, "invoke", name, msg.get("token") or msg.get("key"), msg.get("body") or {})
                return {"httpStatus": status, "json": body}
        return super().handle(device, msg)

    # ---------- Edge Functions ----------
    def fn(self, device, via, name, bearer, body):
        with self.lock:
            uid = self.tokens.get(bearer) if bearer else None
            body = body if isinstance(body, dict) else {}
            if not uid:
                status, resp = 401, {"error": "unauthorized"}
            elif name == "join-trip":
                status, resp = self._join_trip(uid, body)
            else:
                status, resp = self._approve(uid, body)
            self.fn_calls.append({"device": device, "via": via, "name": name, "action": body.get("action") if name == "join-trip"
                                  else body.get("decision"), "body": copy.deepcopy(body), "uid": uid, "status": status,
                                  "resp": copy.deepcopy(resp)})
            return status, resp

    def calls_of(self, name=None, action=None, device=None):
        return [c for c in self.fn_calls if (name is None or c["name"] == name) and (action is None or c["action"] == action)
                and (device is None or c["device"] == device)]

    @staticmethod
    def _err(code):
        return STATUS.get(code, 500), {"error": code}

    def _count(self, kind, since, uid=None, trip=None, ok=None):
        return len([a for a in self.attempts if a["kind"] == kind and a["at"] > since and (uid is None or a["uid"] == uid)
                    and (trip is None or a["trip_id"] == trip) and (ok is None or a["ok"] == ok)])

    def _log(self, kind, uid, trip, ok):
        self.attempts.append({"kind": kind, "uid": uid, "trip_id": trip, "ok": ok, "at": self.tnow()})

    def _trip_for(self, code):
        c = norm_join_code(code)
        if not c:
            return None
        return next((r["trip_id"] for r in self.rows["trip_join_codes"].values() if r["code"] == c), None)

    def _join_trip(self, uid, b):
        act = b.get("action")
        forced = self.force.get(("join-trip", act))
        if forced:
            return self._err(forced)
        now = self.tnow()
        if act == "preview":
            if self._count("preview", now - HOUR, uid=uid) >= 30:
                return self._err("rate_limited")
            tid = self._trip_for(b.get("code"))
            self._log("preview", uid, tid, bool(tid))
            if not tid:
                return self._err("code_invalid")
            t = self.rows["trips"][(tid,)]
            s, e = dt.date.fromisoformat(t["start_date"]), dt.date.fromisoformat(t["end_date"])
            act_rows = self.members(tid, "active")
            mgrs = [r for r in act_rows if r["role"] == "manager"]
            me = self.member_of(tid, uid)
            return 200, {"trip_id": tid, "name": t["name"], "start_date": t["start_date"], "end_date": t["end_date"],
                         "days": (e - s).days + 1, "members": len(act_rows), "manager": mgrs[0]["display_name"] if mgrs else None,
                         "me": {"member_id": me["id"], "status": me["status"], "role": me["role"],
                                "display_name": me["display_name"]} if me else None}
        if act == "request":
            name = clean_name(b.get("display_name"))
            if not isinstance(b.get("display_name"), str) or not (1 <= len(name) <= 40):
                return self._err("name_invalid")
            tid = self._trip_for(b.get("code"))
            if not tid:
                self._log("request", uid, None, False)
                return self._err("code_invalid")
            me = self.member_of(tid, uid)
            if me:
                if me["status"] == "removed":
                    return self._err("member_removed")
                return 200, {"trip_id": tid, "member_id": me["id"], "status": me["status"], "role": me["role"],
                             "display_name": me["display_name"], "created": False}
            if self._count("request", now - DAY, uid=uid, trip=tid, ok=True) >= 3:
                self._log("request", uid, tid, False)
                return self._err("rate_limited")
            if len(self.members(tid, "pending")) >= 20:
                self._log("request", uid, tid, False)
                return self._err("rate_limited")
            if any(name_key(r["display_name"]) == name_key(name) for r in self.members(tid) if r["status"] in ("pending", "active")):
                self._log("request", uid, tid, False)
                return self._err("name_taken")
            mid = str(uuid.uuid4())
            row = {"id": mid, "trip_id": tid, "user_id": uid, "display_name": name,
                   "role": self.rows["trips"][(tid,)]["default_role"], "status": "pending", "joined_at": iso(now),
                   "approved_at": None, "last_seen_at": None}
            self.mut_insert(row)
            self._log("request", uid, tid, True)
            return 200, {"trip_id": tid, "member_id": mid, "status": "pending", "role": row["role"], "display_name": name,
                         "created": True}
        if act == "cancel":
            tid = b.get("trip_id")
            me = self.member_of(tid, uid) if tid else None
            if not tid or not f02.UUID_RE.match(str(tid)):
                return self._err("invalid_request")
            if not me or me["status"] != "pending":
                return self._err("not_pending")
            self.mut_delete(me)
            return 200, {"ok": True}
        if act == "issue_transfer":
            tid = b.get("trip_id")
            if not tid or not f02.UUID_RE.match(str(tid)):
                return self._err("invalid_request")
            me = self.member_of(tid, uid)
            if not me or me["status"] != "active":
                return self._err("not_member")
            for t in self.transfers:
                if t["member_id"] == me["id"] and not t["used_at"]:
                    t["used_at"] = "void"
            code = self.code_seq.pop(0) if self.code_seq else "%06d" % random.randint(0, 999999)
            exp = now + DAY
            self.transfers.append({"member_id": me["id"], "code": code, "expires_at": exp, "used_at": None, "issued_to": uid})
            return 200, {"code": code, "expires_at": iso(exp)}
        if act == "claim_transfer":
            if self._count("claim", now - HOUR, uid=uid, ok=False) >= 5:
                return self._err("rate_limited")
            code = re.sub(r"\s", "", str(b.get("code") or ""))
            t = next((x for x in self.transfers if x["code"] == code and not x["used_at"] and x["expires_at"] > now), None) \
                if re.fullmatch(r"\d{6}", code) else None
            row = self.member(t["member_id"]) if t else None
            if not t or not row:
                self._log("claim", uid, None, False)
                return self._err("transfer_invalid")
            if self.member_of(row["trip_id"], uid):
                self._log("claim", uid, row["trip_id"], False)
                return self._err("already_member")
            t["used_at"] = iso(now)
            t["claimed_by"] = uid
            self.mut_update(row, user_id=uid)
            self._log("claim", uid, row["trip_id"], True)
            return 200, {"trip_id": row["trip_id"], "member_id": row["id"], "role": row["role"], "display_name": row["display_name"]}
        return self._err("invalid_request")

    def _approve(self, uid, b):
        dec = b.get("decision")
        forced = self.force.get(("approve-member", dec))
        if forced:
            return self._err(forced)
        mid = b.get("member_id")
        if not mid or not f02.UUID_RE.match(str(mid)) or dec not in ("approve", "reject"):
            return self._err("invalid_request")
        role = b.get("role")
        if dec == "approve" and role is not None and role not in ROLES:
            return self._err("role_invalid")
        row = self.member(mid)
        if not row:
            return self._err("not_pending")
        if row["trip_id"] not in self.active_trips(uid, ("manager",)):
            return self._err("not_manager")
        if row["status"] != "pending":
            return self._err("not_pending")
        if dec == "reject":
            self.mut_delete(row)
            return 200, {"status": "rejected", "member_id": mid, "display_name": row["display_name"]}
        role = role or self.rows["trips"][(row["trip_id"],)]["default_role"]
        self.mut_update(row, status="active", role=role, approved_at=iso(self.tnow()))
        return 200, {"status": "active", "member_id": mid, "role": role, "display_name": row["display_name"],
                     "trip_id": row["trip_id"]}

    # ---------- direct actions (another device / the manager, without a browser) ----------
    def approve_direct(self, mid, role=None):
        with self.lock:
            row = self.member(mid)
            assert row and row["status"] == "pending", "harness: member %s is not pending" % mid
            role = role or self.rows["trips"][(row["trip_id"],)]["default_role"]
            self.mut_update(row, status="active", role=role, approved_at=iso(self.tnow()))

    def reject_direct(self, mid):
        with self.lock:
            row = self.member(mid)
            assert row and row["status"] == "pending", "harness: member %s is not pending" % mid
            self.mut_delete(row)


# =====================================================================================================
# Browser environment
# =====================================================================================================
STANDALONE_JS = r"""(()=>{try{Object.defineProperty(Navigator.prototype,'standalone',{configurable:true,get(){return true}})}catch(e){}
 try{const mm=window.matchMedia.bind(window);window.matchMedia=function(q){const r=mm(q);
   if(/display-mode:\s*standalone/.test(String(q))){return {matches:true,media:String(q),
     onchange:null,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent(){return false}}}return r}}catch(e){}})();"""
# CHANGE 2026-10-26 QA-DEBT-09: was Object.assign(Object.create(Object.getPrototypeOf(r)),{matches:true,…}) — threw on every call
NOT_STANDALONE_JS = r"""(()=>{try{Object.defineProperty(Navigator.prototype,'standalone',{configurable:true,get(){return false}})}catch(e){}})();"""
IPAD_TOUCH_JS = r"""(()=>{try{Object.defineProperty(Navigator.prototype,'platform',{configurable:true,get(){return 'MacIntel'}});
 Object.defineProperty(Navigator.prototype,'maxTouchPoints',{configurable:true,get(){return 5}})}catch(e){}})();"""
TOAST_JS = r"""(()=>{if(window.__qaToastLog)return;window.__qaToastLog=[];const seen=new Set();
 const scan=()=>{for(const id of ['lpjToast','ptF05Toast','ptToast']){const e=document.getElementById(id);if(!e)continue;
   const t=(e.innerText||e.textContent||'').trim();const r=e.getBoundingClientRect();
   if(t&&r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'&&+getComputedStyle(e).opacity>0){const k=id+'|'+t;
     if(!seen.has(k)){seen.add(k);window.__qaToastLog.push({id,t,at:Date.now()})}}else if(!t||r.width===0){for(const k of [...seen])if(k.startsWith(id+'|'))seen.delete(k)}}};
 const go=()=>{try{new MutationObserver(scan).observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true})}catch(e){}};
 if(document.documentElement)go();else document.addEventListener('DOMContentLoaded',go);setInterval(scan,100)})();"""


class Env(f20.Env):
    def __init__(self, browser, server):
        f02.Env.__init__(self, browser, server)
        self.backend = F05Backend()

    def new_device(self, name="A", ua=None, standalone=None, ipad_touch=False, clock="install", service_workers="block",
                   offline_boot=False, **_):
        conf = {"legacy_fake": False}
        kw = dict(viewport=VIEWPORT, locale="he-IL", timezone_id="Asia/Jerusalem", service_workers=service_workers,
                  permissions=["geolocation", "clipboard-read", "clipboard-write"],
                  geolocation={"latitude": 21.0285, "longitude": 105.8542, "accuracy": 20})
        if ua:
            kw["user_agent"] = ua
        if ua in (IPHONE_UA, ANDROID_UA) or ipad_touch:
            kw["has_touch"] = True
            kw["is_mobile"] = ua != IPAD_DESKTOP_UA
        ctx = self.browser.new_context(**kw)
        if clock == "install":
            ctx.clock.install(time=FIXED_NOW)
        ctx.expose_binding("__fakeBackend", lambda source, msg, _n=name: self.backend.handle(_n, msg))
        ctx.add_init_script(f02.WATCH_JS)
        ctx.add_init_script(f04.OPEN_JS)
        ctx.add_init_script(f20.OFFLINE_JS)
        ctx.add_init_script(TOAST_JS)
        if standalone is True:
            ctx.add_init_script(STANDALONE_JS)
        elif standalone is False:
            ctx.add_init_script(NOT_STANDALONE_JS)
        if ipad_touch:
            ctx.add_init_script(IPAD_TOUCH_JS)
        page = ctx.new_page()
        d = f03.F03Device(self, name, ctx, page, conf)
        d.navs = []
        page.on("framenavigated", lambda fr, _d=d: _d.navs.append(fr.url) if fr == _d.page.main_frame else None)
        ctx.route("**/*", lambda route, request, _d=d: self._route5(_d, route, request))
        if offline_boot:
            f20.set_offline_cookie(d, True)
        self.devices.append(d)
        return d

    def _route5(self, dev, route, request):
        url = request.url
        p = urlparse(url)
        rec = {"device": dev.name, "url": url, "method": request.method, "type": request.resource_type}
        self.net.append(rec)
        be = self.backend
        try:
            if p.hostname in ("127.0.0.1", "localhost"):
                rec["action"] = "same-origin"
                return route.continue_()
            if p.hostname == "cdn.jsdelivr.net" and "@supabase/supabase-js" in p.path:
                rec["action"] = "fake-lib"
                return route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=FAKE_JS,
                                     headers={"Access-Control-Allow-Origin": "*"})
            base = url.split("#")[0].split("?")[0].rstrip("/")
            if base in (JT_URL, AM_URL):
                name = "join-trip" if base == JT_URL else "approve-member"
                origin = request.headers.get("origin") or "*"
                cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Vary": "Origin"}
                if dev.is_offline or be.mode == "down" or name in be.fn_down_names:
                    rec["action"] = "fn-offline"
                    return route.abort("internetdisconnected")
                if request.method == "OPTIONS":
                    rec["action"] = "fn-preflight"
                    return route.fulfill(status=204, headers=cors, body="")
                if name in be.hang_fns:
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
                rec["apikey"] = hdrs.get("apikey")
                status, resp = be.fn(dev.name, "fetch", name, bearer, body)
                return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(resp))
            rec["action"] = "aborted"
            return route.abort()
        except PWError:
            pass


# =====================================================================================================
# Source helpers (flag flips)
# =====================================================================================================
JOIN_FLAG_RE = re.compile(r"""(const\s+JOIN_FEATURE\s*=\s*)(['"])(on|off)\2""")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def join_html():
    return (JOIN_DIR / "index.html").read_text(encoding="utf-8")


def flip_join(src, value="off"):
    assert JOIN_FLAG_RE.search(src), "const JOIN_FEATURE='on' not found (spec §1: top-level flag)"
    return JOIN_FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def serve_app_flags(env, join=None, **flags):
    """Serve app/index.html with JOIN_FEATURE and/or F20-era flags flipped (static copy)."""
    src = app_html()
    if join:
        src = flip_join(src, join)
    for k, v in flags.items():
        if v is None:
            continue
        assert f20.FLAGS[k].search(src), "harness: top-level %s not found" % k
        src = f20.FLAGS[k].sub(lambda m, _v=v: m.group(1) + "'" + _v + "'", src, count=1)
    env.server.overrides[APP + "index.html"] = src.encode("utf-8")
    env.server.overrides[APP] = src.encode("utf-8")


def serve_join_off(env):
    b = flip_join(join_html(), "off").encode("utf-8")
    env.server.overrides[JOIN + "index.html"] = b
    env.server.overrides[JOIN] = b


# =====================================================================================================
# Generic UI helpers
# =====================================================================================================
find, click_text, visible, wait_text, gone = f03.find, f03.click_text, f03.visible, f03.wait_text, f03.gone
norm, btext, has, wait_has = f04.norm, f04.btext, f04.has, f04.wait_has
layout_problems = f04.layout_problems
is_vis, exists = f20.is_vis, f20.exists


def wait_until(fn, timeout=10.0, page=None, interval=0.15, msg="condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except PWError as e:
            last = e
        if page is not None:
            try:
                page.wait_for_timeout(int(interval * 1000))
            except PWError:
                time.sleep(interval)
        else:
            time.sleep(interval)
    return last if last else False


def screen_of(page):
    try:
        return page.evaluate("()=>{const r=document.getElementById('lpJoin');return r?r.getAttribute('data-screen'):null}")
    except PWError:
        return None


def wait_screen(page, want, timeout=12.0):
    want = (want,) if isinstance(want, str) else tuple(want)
    s = wait_until(lambda: screen_of(page) in want and screen_of(page), timeout, page)
    if s:
        page.wait_for_timeout(250)
        return screen_of(page)
    return screen_of(page)


def text_of(page, sel):
    try:
        return page.evaluate("(s)=>{const e=document.querySelector(s);return e?(e.innerText||e.textContent||''):null}", sel)
    except PWError:
        return None


def toasts(page):
    try:
        return [t["t"] for t in page.evaluate("()=>window.__qaToastLog||[]")]
    except PWError:
        return []


def saw_toast(page, text, timeout=5.0):
    return bool(wait_until(lambda: any(norm(text) in norm(t) for t in toasts(page)) or norm(text) in btext(page), timeout, page))


def page_errors(dev):
    noise = ("Failed to load resource", "net::ERR_", "favicon")
    return dev.errors + [c for c in dev.console if c.startswith("error:") and not any(n in c for n in noise)]


def tap(page, sel, timeout=4000):
    loc = page.locator(sel).filter(visible=True).first
    loc.scroll_into_view_if_needed(timeout=timeout)
    loc.click(timeout=timeout)
    page.wait_for_timeout(250)


def app_state(page):
    return f20.state(page)


def wait_app_state(page, want=None, timeout=20.0):
    return f20.wait_state(page, want, timeout)


def running_trip(page):
    return f20.trip_id_running(page)
