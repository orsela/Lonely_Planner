"""Lonely Planner F21 QA · browser harness (/request/ + app admin requests, fake backend) · version 1.0.0
CHANGE 2026-10-30 F21-QA-04: new file (no previous version).

Written from docs/F21_spec.md only (the F21 implementation in app/index.html and request/index.html was NOT read; only the
top-level constants the brief names — REQUEST_FEATURE, TURNSTILE_SITE_KEY — and spec texts/ids are grepped).
Reuses the F04-HOME harness (tests/f04home/harness.py → F06 → F05 → F20 → F04 → F03 → F02): GitHub-Pages-like server
(/Lonely_Planner/app/, /request/, /invite/ on one origin), fake supabase-js, the F03 invite-manager / F04 create-trip
fakes, device UA presets and the x-safari / intent navigation capture.

New for F21:
- F21Backend.request_trip(): an in-memory `request-trip` per spec §3.1/§4 (start / verify / resend, Turnstile siteverify with
  Cloudflare's documented test semantics: the dummy token "XXXX.DUMMY.TOKEN.XXXX" passes unless `ts_fail`; an empty token
  fails), the D10 cap (mail_log), per-email / per-IP limits, code TTL 10 min, 5 wrong → locked, resend 60 s / ≤3.
  `rt_force[action] = code` forces a refusal; `rt_calls` is the network log of the page.
- rpc('admin_trip_requests') computed from the fake requests (pending only, oldest first, manages, active_invite).
- invite-manager approve_request / reject_request (spec §3.2) on the F03 fake invites (+ request_id, lang), D12 revoke,
  undo on email failure, reject mail with the cap.
- create-trip lookup adds `prefill` for an invite created from a request (§3.3).
- Fake Cloudflare Turnstile api.js (the real one is unreachable offline): window.turnstile.render/reset/remove/getResponse,
  `?onload=` callback, test site keys 1x00000000000000000000AA (always passes → callback('XXXX.DUMMY.TOKEN.XXXX')) and
  2x00000000000000000000AB (always fails → error-callback, no token). Calls are recorded in window.__qaTs.
- serve_request(env, key=PASS_KEY, flag=None): /request/ with TURNSTILE_SITE_KEY rewritten (the page's real key only works on
  orsela.github.io) and optionally REQUEST_FEATURE flipped; serve_app_request(env, 'off') flips the app flag.
"""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
if "f04home_harness" in sys.modules:
    h4 = sys.modules["f04home_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f04home_harness", str(REPO_DIR / "tests" / "f04home" / "harness.py"))
    h4 = importlib.util.module_from_spec(_spec)
    sys.modules["f04home_harness"] = h4
    _spec.loader.exec_module(h4)
f06, f05, f20, f04, f03, f02 = h4.f06, h4.f05, h4.f20, h4.f04, h4.f03, h4.f02

from playwright.sync_api import Error as PWError  # noqa: E402

ROOT, APP, INVITE = h4.ROOT, h4.APP, h4.INVITE
REQUEST = ROOT + "request/"
REQUEST_DIR = REPO_DIR / "request"
APP_DIR = h4.APP_DIR
PT_URL = f02.PT_URL
RT_URL = PT_URL + "/functions/v1/request-trip"
IM_URL, CT_URL = f04.IM_URL, f04.CT_URL
VIEWPORT, FIXED_NOW, DAY, HOUR, MINUTE = h4.VIEWPORT, h4.FIXED_NOW, h4.DAY, h4.HOUR, h4.MINUTE
PASS_KEY = "1x00000000000000000000AA"
FAIL_KEY = "2x00000000000000000000AB"
DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"
RESUME_KEY = "pt:_device:rq_resume"
LANG_KEY = "pt:_device:rq_lang"
UAS = h4.UAS
COUNTRIES = {c["code"]: c for c in json.loads((APP_DIR / "countries.json").read_text(encoding="utf-8"))}
iso = f05.iso
RT_STATUS = {"invalid_request": 400, "turnstile_failed": 403, "rate_limited": 429, "daily_limit": 429, "code_wrong": 400,
             "code_expired": 410, "code_locked": 423, "request_unknown": 404, "email_failed": 502}


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def jm_midnight(t):
    """Start of the Asia/Jerusalem calendar day containing t (C3). Israel: UTC+2 (winter) / +3 (summer); the test dates
    are in October (+3 until the last Sunday of October) — computed with zoneinfo when available."""
    try:
        from zoneinfo import ZoneInfo
        loc = t.astimezone(ZoneInfo("Asia/Jerusalem"))
        return loc.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)
    except Exception:  # pragma: no cover
        return (t + 3 * HOUR).replace(hour=0, minute=0, second=0, microsecond=0) - 3 * HOUR


def month_list(now, n=18):
    loc = now + 3 * HOUR
    y, m = loc.year, loc.month
    out = []
    for _ in range(n):
        out.append("%04d-%02d-01" % (y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


# =====================================================================================================
# Fake backend
# =====================================================================================================
class F21Backend(h4.F4HBackend):
    def __init__(self):
        super().__init__()
        self.requests = {}        # id -> row (private.trip_requests)
        self.r_attempts = []      # {kind, email_hash, ip, ok, at}
        self.mail_log = []        # {kind, at}
        self.code_mails = []      # {to, lang, code, request_id, subject}
        self.reject_mails = []    # {to, lang}
        self.rt_calls = []        # {device, body, status, resp, apikey, auth}
        self.rt_force = {}        # action -> error code
        self.rt_down = False
        self.rt_hang = False
        self.ts_fail = False      # siteverify refuses every token
        self.req_rpc_fail = False  # admin_trip_requests fails
        self.next_code = None     # force the next code (else random)
        self.seq = 0

    # ---------- clock ----------
    def clock(self):
        try:
            return self.tnow()
        except Exception:
            return self.now

    # ---------- dataset helpers ----------
    def add_request(self, name="דנה", email="dana@example.com", lang="he", countries=("PT", "ES"), month="2027-04-01",
                    travellers=4, note=None, status="pending", verified_ago=HOUR, rid=None):
        rid = rid or str(uuid.uuid4())
        now = self.clock()
        self.requests[rid] = {"id": rid, "lang": lang, "name": name, "email": email, "countries": list(countries), "month": month,
                              "travellers": travellers, "note": note, "status": status, "code": None, "code_expires_at": None,
                              "code_attempts": 0, "code_sent_at": None, "resend_count": 0,
                              "verified_at": iso(now - verified_ago) if status != "unverified" else None,
                              "decided_at": None, "decided_by": None, "invite_id": None, "created_at": iso(now - verified_ago - MINUTE)}
        return rid

    def mails_today(self):
        start = jm_midnight(self.clock())
        return len([m for m in self.mail_log if m["at"] >= start])

    def fill_cap(self, n=50, kind="code"):
        for _ in range(n):
            self.mail_log.append({"kind": kind, "at": self.clock()})

    # ---------- request-trip (§3.1, §4) ----------
    def rt_http(self, device, headers, body):
        with self.lock:
            body = body if isinstance(body, dict) else {}
            ip = (headers.get("x-forwarded-for") or "127.0.0.1").split(",")[0].strip()
            status, resp = self._rt(body, ip)
            self.rt_calls.append({"device": device, "action": body.get("action"), "body": copy.deepcopy(body), "status": status,
                                  "resp": copy.deepcopy(resp), "apikey": headers.get("apikey"),
                                  "auth": headers.get("authorization"), "t": time.time()})
            return status, resp

    def rt(self, action=None, device=None):
        return [c for c in self.rt_calls if (action is None or c["action"] == action) and (device is None or c["device"] == device)]

    def _refuse(self, code, **extra):
        return RT_STATUS.get(code, 500), dict({"ok": False, "code": code, "error": code}, **extra)

    def _new_code(self):
        if self.next_code:
            c, self.next_code = self.next_code, None
            return c
        return "%06d" % (int(uuid.uuid4().int % 1000000))

    def _cleanup(self):
        now = self.clock()
        for rid, r in list(self.requests.items()):
            if r["status"] == "rejected" and r["decided_at"] and f03.parse(r["decided_at"]) < now - 5 * DAY:
                del self.requests[rid]
            elif r["status"] == "unverified" and f03.parse(r["created_at"]) < now - 5 * DAY:
                del self.requests[rid]

    def _validate(self, b):
        now = self.clock()
        if b.get("lang") not in ("he", "en"):
            return "lang"
        name = str(b.get("name") or "").strip()
        if not (1 <= len(name) <= 40):
            return "name"
        email = str(b.get("email") or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return "email"
        cs = b.get("countries")
        if not isinstance(cs, list) or not (1 <= len(cs) <= 10) or not all(isinstance(c, str) and re.fullmatch("[A-Z]{2}", c) for c in cs):
            return "countries"
        m = b.get("month")
        if m is not None:
            mm = str(m)[:7] + "-01"
            if mm not in month_list(now):
                return "month"
        t = b.get("travellers")
        if not isinstance(t, int) or not (1 <= t <= 30):
            return "travellers"
        n = b.get("note")
        if n is not None and len(str(n)) > 200:
            return "note"
        return None

    def _rt(self, b, ip):
        act = b.get("action")
        now = self.clock()
        self._cleanup()
        if act in self.rt_force:
            return self._refuse(self.rt_force[act])
        if act == "start":
            f = self._validate(b)
            if f:
                return self._refuse("invalid_request", field=f)
            tok = b.get("turnstile_token")
            if self.ts_fail or tok != DUMMY_TOKEN:
                return self._refuse("turnstile_failed")
            email = b["email"].strip().lower()
            eh = sha(email)
            day = jm_midnight(now)
            if len([a for a in self.r_attempts if a["kind"] == "start" and a["email_hash"] == eh and a["at"] >= day]) >= 3 or \
               len([a for a in self.r_attempts if a["kind"] == "start" and a["ip"] == ip and a["at"] >= day]) >= 10:
                self.r_attempts.append({"kind": "start", "email_hash": eh, "ip": ip, "ok": False, "at": now})
                return self._refuse("rate_limited")
            self.r_attempts.append({"kind": "start", "email_hash": eh, "ip": ip, "ok": True, "at": now})
            if self.mails_today() >= 50 or len([r for r in self.requests.values() if r["status"] == "pending"]) >= 100:
                return self._refuse("daily_limit")
            for rid, r in list(self.requests.items()):
                if r["email"] == email and r["status"] == "unverified":
                    del self.requests[rid]
            rid = str(uuid.uuid4())
            code = self._new_code()
            self.requests[rid] = {"id": rid, "lang": b["lang"], "name": b["name"].strip(), "email": email, "countries": list(b["countries"]),
                                  "month": (str(b["month"])[:7] + "-01") if b.get("month") else None, "travellers": b["travellers"],
                                  "note": (b.get("note") or None), "status": "unverified", "code": code,
                                  "code_expires_at": now + 10 * MINUTE, "code_attempts": 0, "code_sent_at": now, "resend_count": 0,
                                  "verified_at": None, "decided_at": None, "decided_by": None, "invite_id": None, "created_at": iso(now)}
            self.mail_log.append({"kind": "code", "at": now})
            self.code_mails.append({"to": email, "lang": b["lang"], "code": code, "request_id": rid})
            return 200, {"ok": True, "request_id": rid, "sent_at": iso(now)}
        if act == "verify":
            rid = b.get("request_id")
            code = re.sub(r"\s", "", str(b.get("code") or ""))
            if len([a for a in self.r_attempts if a["kind"] == "verify" and a["ip"] == ip and not a["ok"] and a["at"] >= now - HOUR]) >= 20:
                return self._refuse("rate_limited")
            r = self.requests.get(rid)
            if not r or r["status"] != "unverified":
                return self._refuse("request_unknown")
            if now >= r["code_expires_at"]:
                return self._refuse("code_expired")
            if code != r["code"]:
                r["code_attempts"] += 1
                self.r_attempts.append({"kind": "verify", "email_hash": None, "ip": ip, "ok": False, "at": now})
                if r["code_attempts"] >= 5:
                    del self.requests[rid]
                    return self._refuse("code_locked")
                return self._refuse("code_wrong", attempts_left=5 - r["code_attempts"])
            r.update(status="pending", verified_at=iso(now), code=None)
            return 200, {"ok": True, "request_id": rid}
        if act == "resend":
            rid = b.get("request_id")
            r = self.requests.get(rid)
            if not r or r["status"] != "unverified":
                return self._refuse("request_unknown")
            if now < r["code_sent_at"] + dt.timedelta(seconds=60) or r["resend_count"] >= 3:
                return self._refuse("rate_limited")
            if self.mails_today() >= 50:
                return self._refuse("daily_limit")
            code = self._new_code()
            r.update(code=code, code_sent_at=now, code_expires_at=now + 10 * MINUTE, resend_count=r["resend_count"] + 1, code_attempts=0)
            self.mail_log.append({"kind": "code", "at": now})
            self.code_mails.append({"to": r["email"], "lang": r["lang"], "code": code, "request_id": rid})
            return 200, {"ok": True, "request_id": rid, "sent_at": iso(now)}
        return self._refuse("invalid_request", field="action")

    # ---------- rpc admin_trip_requests (§2.7) ----------
    def rpc(self, token, fn, args):
        if fn != "admin_trip_requests":
            return super().rpc(token, fn, args)
        uid = self.tokens.get(token) if token else None
        self.rpc_calls.append({"fn": fn, "uid": uid})
        if self.req_rpc_fail:
            return {"error": {"code": "57014", "message": "canceling statement due to statement timeout"}, "status": 500}
        if uid is None:
            return {"error": {"code": "42501", "message": "permission denied for function admin_trip_requests"}, "status": 401}
        if not self.is_admin(uid):
            return {"error": {"code": "42501", "message": "not_platform_admin", "details": None, "hint": None}, "status": 403}
        self._cleanup()
        return {"data": self.requests_payload(), "status": 200}

    def requests_payload(self):
        out = []
        for r in sorted([r for r in self.requests.values() if r["status"] == "pending"], key=lambda r: r["verified_at"]):
            owner = self.user_by_email(r["email"])
            manages = []
            if owner:
                for m in self.rows["trip_members"].values():
                    if m["user_id"] == owner and m["role"] == "manager" and m["status"] == "active":
                        manages.append(self.rows["trips"][(m["trip_id"],)]["name"])
            act = self.find_invite_for_email(r["email"])
            out.append({"id": r["id"], "lang": r["lang"], "name": r["name"], "email": r["email"], "countries": r["countries"],
                        "month": r["month"], "travellers": r["travellers"], "note": r["note"], "verified_at": r["verified_at"],
                        "manages": manages, "active_invite": {k: act[k] for k in ("id", "draft_name", "last_sent_at", "expires_at")} if act else None})
        return {"cap": 50, "mail_today": self.mails_today(), "requests": out}

    # ---------- invite-manager approve / reject (§3.2) ----------
    def _invite_manager(self, bearer, body):
        action = body.get("action")
        if action not in ("approve_request", "reject_request"):
            return super()._invite_manager(bearer, body)
        uid = self.tokens.get(bearer) if bearer else None
        if not self.is_admin(uid):
            return 403, f03.FN_ERROR("not_platform_admin")
        r = self.requests.get(str(body.get("request_id")))
        if not r or r["status"] != "pending":
            return 409, {"error": "request_closed"}
        now = self.clock()
        if action == "reject_request":
            r.update(status="rejected", decided_at=iso(now), decided_by=uid)
            if not body.get("send_mail"):
                return 200, {"ok": True, "request_id": r["id"], "mail_sent": False}
            if self.mails_today() >= 50:
                return 200, {"ok": True, "request_id": r["id"], "mail_sent": False, "mail_skipped": "daily_limit"}
            if self.email_fail:
                return 200, {"ok": True, "request_id": r["id"], "mail_sent": False, "mail_skipped": "email_failed"}
            self.mail_log.append({"kind": "reject", "at": now})
            self.reject_mails.append({"to": r["email"], "lang": r["lang"]})
            return 200, {"ok": True, "request_id": r["id"], "mail_sent": True}
        name = body.get("draft_name")
        name = str(name).strip() if name is not None else None
        if name and len(name) > 80:
            return 400, f03.FN_ERROR("invalid_name")
        old = self.find_invite_for_email(r["email"])
        if old:
            old["revoked_at"] = iso(now)
        token = f03.new_token()
        row = {"id": str(uuid.uuid4()), "email": r["email"], "token_hash": f03.sha256_hex(token), "draft_name": name or None,
               "invited_by": uid, "expires_at": iso(now + 7 * DAY), "used_at": None, "revoked_at": None, "trip_id": None,
               "created_at": iso(now), "send_count": 1, "last_sent_at": iso(now), "opened_at": None, "inviter_name": "אור",
               "request_id": r["id"], "lang": r["lang"]}
        self.invites[row["id"]] = row
        if self.email_fail:
            del self.invites[row["id"]]
            if old:
                old["revoked_at"] = None
            return 502, f03.FN_ERROR("email_failed")
        self.emails.append({"to": row["email"], "subject": "Your trip request was approved" if r["lang"] == "en" else "הוזמנת לנהל טיול ב-Lonely Planner",
                            "link": "https://orsela.github.io/Lonely_Planner/invite/#invite=" + token, "token": token, "invite_id": row["id"],
                            "lang": r["lang"]})
        r.update(status="approved", decided_at=iso(now), decided_by=uid, invite_id=row["id"])
        return 200, {"ok": True, "request_id": r["id"], "invite_id": row["id"], "email": row["email"], "draft_name": row["draft_name"],
                     "expires_at": row["expires_at"], "lang": r["lang"], "revoked_invite_id": old["id"] if old else None}

    # ---------- create-trip lookup prefill (§3.3) ----------
    def _create_trip(self, bearer, body):
        status, resp = super()._create_trip(bearer, body)
        if body.get("action") == "lookup" and status == 200 and resp.get("found"):
            uid = self.tokens.get(bearer)
            inv = self.find_invite_for_email(self.users[uid]["email"])
            req = self.requests.get(inv.get("request_id")) if inv and inv.get("request_id") else None
            if req:
                resp = dict(resp, prefill={"name": req["name"], "countries": list(req["countries"]), "month": req["month"], "lang": req["lang"]})
        return status, resp


# =====================================================================================================
# Fake Turnstile (Cloudflare test-key semantics)
# =====================================================================================================
TURNSTILE_JS = r"""(()=>{const S=window.__qaTs=window.__qaTs||{renders:[],resets:0,removes:0,widgets:{}};let n=0;
 const run=(id)=>{const w=S.widgets[id];if(!w)return;w.token=null;setTimeout(()=>{if(!S.widgets[id])return;
   if(String(w.o.sitekey).startsWith('1x')){w.token='XXXX.DUMMY.TOKEN.XXXX';w.el.querySelector('span').textContent='Success!';
     try{w.o.callback&&w.o.callback(w.token)}catch(e){}}
   else{w.el.querySelector('span').textContent='Verification failed';try{w.o['error-callback']&&w.o['error-callback']('110200')}catch(e){}}},250)};
 window.turnstile={render(el,o){if(typeof el==='string')el=document.querySelector(el);const id='qa-ts-'+(++n);
   const box=document.createElement('div');box.setAttribute('data-qa-turnstile',id);box.style.cssText='width:300px;max-width:100%;height:65px;border:1px solid #ccc;display:flex;align-items:center;justify-content:center;font:14px sans-serif';
   box.innerHTML='<span>Verifying…</span>';el.appendChild(box);S.widgets[id]={el:box,o:Object.assign({},o),token:null};
   S.renders.push({sitekey:o.sitekey,language:o.language||null,theme:o.theme||null,size:o.size||null,appearance:o.appearance||null});run(id);return id},
  reset(id){S.resets++;const k=id||Object.keys(S.widgets).pop();if(k)run(k)},
  remove(id){S.removes++;const k=id||Object.keys(S.widgets).pop();const w=S.widgets[k];if(w){w.el.remove();delete S.widgets[k]}},
  getResponse(id){const k=id||Object.keys(S.widgets).pop();return S.widgets[k]?S.widgets[k].token||undefined:undefined},
  isExpired(){return false},execute(id){const k=id||Object.keys(S.widgets).pop();if(k)run(k)},ready(cb){cb&&cb()}};
 try{const src=(document.currentScript&&document.currentScript.src)||'';const cb=new URL(src).searchParams.get('onload');
   if(cb&&typeof window[cb]==='function')setTimeout(()=>window[cb](),0)}catch(e){}})();"""


class Env(h4.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F21Backend()

    def new_device(self, name="A", ua=None, locale="he-IL", languages=None, **kw):
        if locale == "he-IL" and not languages:
            return super().new_device(name, ua=ua, **kw)
        # same as the F04-HOME device, other locale (navigator.languages follows the context locale)
        orig = self.browser.new_context
        def nc(**k):
            k["locale"] = locale
            return orig(**k)
        self.browser.new_context = nc
        try:
            d = super().new_device(name, ua=ua, **kw)
        finally:
            self.browser.new_context = orig
        if languages:
            d.ctx.add_init_script("try{Object.defineProperty(Navigator.prototype,'languages',{configurable:true,get(){return %s}})}catch(e){}" % json.dumps(languages))
        return d

    def _route5(self, dev, route, request):
        url = request.url
        p = urlparse(url)
        base = url.split("#")[0].split("?")[0].rstrip("/")
        try:
            if p.hostname == "challenges.cloudflare.com":
                self.net.append({"device": dev.name, "url": url, "method": request.method, "type": request.resource_type, "action": "fake-turnstile"})
                if getattr(dev, "is_offline", False):
                    return route.abort("internetdisconnected")
                return route.fulfill(status=200, content_type="application/javascript", body=TURNSTILE_JS,
                                     headers={"Access-Control-Allow-Origin": "*"})
            if base == RT_URL:
                rec = {"device": dev.name, "url": url, "method": request.method, "type": request.resource_type}
                self.net.append(rec)
                be = self.backend
                origin = request.headers.get("origin") or "*"
                cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Vary": "Origin"}
                if dev.is_offline or be.rt_down or be.mode == "down":
                    rec["action"] = "rt-offline"
                    return route.abort("internetdisconnected")
                if request.method == "OPTIONS":
                    rec["action"] = "rt-preflight"
                    return route.fulfill(status=204, headers=cors, body="")
                if be.rt_hang:
                    rec["action"] = "rt-hang"
                    return None
                try:
                    body = json.loads(request.post_data or "{}")
                except ValueError:
                    body = {"__unparsable": request.post_data}
                rec["action"] = "rt"
                rec["body"] = body
                status, resp = be.rt_http(dev.name, {k.lower(): v for k, v in request.headers.items()}, body)
                return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(resp))
        except PWError:
            return None
        return super()._route5(dev, route, request)


# =====================================================================================================
# Source helpers
# =====================================================================================================
REQ_FLAG_RE = re.compile(r"""((?:const|let|var)\s+REQUEST_FEATURE\s*=\s*)(['"])(on|off)\2""")
KEY_RE = re.compile(r"""((?:const|let|var)\s+TURNSTILE_SITE_KEY\s*=\s*)(['"])([^'"]*)\2""")


def request_html():
    return (REQUEST_DIR / "index.html").read_text(encoding="utf-8")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def serve_request(env, key=PASS_KEY, flag=None):
    src = request_html()
    assert KEY_RE.search(src), "harness: const TURNSTILE_SITE_KEY not found in request/index.html"
    src = KEY_RE.sub(lambda m: m.group(1) + m.group(2) + key + m.group(2), src, count=1)
    if flag:
        assert REQ_FLAG_RE.search(src), "harness: const REQUEST_FEATURE not found in request/index.html"
        src = REQ_FLAG_RE.sub(lambda m: m.group(1) + m.group(2) + flag + m.group(2), src, count=1)
    b = src.encode("utf-8")
    env.server.overrides[REQUEST + "index.html"] = b
    env.server.overrides[REQUEST] = b


def serve_app_request(env, flag="off"):
    src = app_html()
    assert REQ_FLAG_RE.search(src), "harness: const REQUEST_FEATURE not found in app/index.html"
    src = REQ_FLAG_RE.sub(lambda m: m.group(1) + m.group(2) + flag + m.group(2), src, count=1)
    env.server.overrides[APP + "index.html"] = src.encode("utf-8")
    env.server.overrides[APP] = src.encode("utf-8")


# =====================================================================================================
# Helpers
# =====================================================================================================
norm, btext, has, wait_has = f04.norm, f04.btext, f04.has, f04.wait_has
find, click_text, visible, wait_text = f03.find, f03.click_text, f03.visible, f03.wait_text
layout_problems, is_vis, exists, wait_until = f04.layout_problems, f20.is_vis, f20.exists, f05.wait_until
page_errors, app_state, wait_app_state = f05.page_errors, f05.app_state, f05.wait_app_state
ext_navs, url_now, toasts, saw_toast = h4.ext_navs, h4.url_now, f05.toasts, f05.saw_toast


def ts_state(page):
    try:
        return page.evaluate("()=>JSON.parse(JSON.stringify(Object.assign({},window.__qaTs||{},{widgets:undefined})))")
    except PWError:
        return {}


def ls_get(dev, key):
    try:
        return dev.ls().get(key)
    except PWError:
        return None


def flag(code):
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code)
