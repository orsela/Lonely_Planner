"""Lonely Planner F04-HOME QA · browser harness (fake backend, devices, helpers) · version 1.0.0
CHANGE 2026-10-26 F04H-QA-02: first version (no previous version). Reuses the F06 harness (tests/f06/harness.py → F05 → F20 →
F04 → F03 → F02) for the GitHub-Pages-like server (/Lonely_Planner/app/, /Lonely_Planner/invite/ on one origin), the
PostgREST-like query engine with the F01 RLS model, anonymous sign-in, the F05 fake supabase-js with Realtime
(tests/f05/fake_supabase.js — used unchanged: auth.verifyOtp / signInWithOtp / updateUser / resend are already routed to the
F04 backend semantics) and the UI helpers.

Written from docs/F04-HOME_spec.md (commit ee5c723) only; the F04-HOME implementation was NOT read. alpha.7 ids that already
exist at ee5c723 (#ptGate, #ptF05Transfer, #ptF05Otp0…5, #ptF05Claim, #ptF05LinkBtn, #ptF05LinkIn, #ptF05LinkGo,
#ptDeviceCode, #lpJoin) are used where the spec says "unchanged".

What is new for F04-HOME:
- Routing: the F05/F06 route handler aborted invite-manager and create-trip requests (those suites never ran the wizard or
  /invite/). F4HEnv sends both to the F04 handler (fake invite-manager `check`, fake create-trip `lookup` / `create`).
- F4HBackend helpers: `manager_account(email, trips=n)` = an existing confirmed account that is an active manager of n trips
  (C3); `used_invite(email)` = an invite already used (lookup answers {found:false}); `sends()` = OTP send calls
  (updateUser{email} / signInWithOtp / resend) — the "network log" of criterion 9; `verifies()`.
- Devices: `new_device(ua=…, standalone=…, bip=…)`. UAS has Gmail iOS (WKWebView, no "Safari/"), Outlook iOS, GSA iOS,
  Gmail Android WebView ("; wv)"), Safari iPhone, Chrome Android, desktop Chrome. standalone=True → navigator.standalone AND
  display-mode: standalone; 'ios' → navigator.standalone only; 'display' → display-mode only; False → navigator.standalone
  false explicitly.
- External navigations: EXTNAV_JS listens to the Navigation API `navigate` event (fires for location.href / assign / replace /
  anchor clicks, also for custom schemes) and records every navigation to `x-safari-https:` / `x-safari-http:` / `intent:`
  (and window.open with such a URL), then cancels it so the page stays. Records go to the Python side
  (dev.ext_navs: [{url, how, page, t}]) so they survive reloads. Verified in Chromium headless (scratch experiment).
- Install events: BIP_JS gives window.__qaFireBip() (dispatches a fake `beforeinstallprompt` with prompt() / userChoice;
  prompt calls are reported to dev.bip_prompts) and window.__qaFireInstalled() (dispatches `appinstalled`). bip='auto'
  fires the event once 400 ms after DOMContentLoaded on every document of the device (like Chrome when the app is
  installable and not installed).
- Flag flips: HOME_INSTALL_FEATURE in app/ (const) and /invite/ ("a same-named constant": const|let|var). When the
  constant is ABSENT (e.g. ee5c723, before the implementation exists) the page is served unchanged — that IS alpha.7 — and
  `serve_home_off` returns the list of files where the flag was missing (the static test F4H-13 reports it separately).
"""
import copy
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))

if "f06_harness" in sys.modules:
    f06 = sys.modules["f06_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f06_harness", str(REPO_DIR / "tests" / "f06" / "harness.py"))
    f06 = importlib.util.module_from_spec(_spec)
    sys.modules["f06_harness"] = f06
    _spec.loader.exec_module(f06)
f05, f20, f04, f03, f02 = f06.f05, f06.f20, f06.f04, f06.f03, f06.f02

from playwright.sync_api import Error as PWError  # noqa: E402

ROOT, APP = f05.ROOT, f05.APP
INVITE = ROOT + "invite/"
INVITE_DIR = REPO_DIR / "invite"
APP_DIR = f05.APP_DIR
VIEWPORT, FIXED_NOW, DAY, HOUR = f05.VIEWPORT, f05.FIXED_NOW, f05.DAY, f05.HOUR
MINUTE = dt.timedelta(minutes=1)
PT_URL = f05.PT_URL
IM_URL, CT_URL = f04.IM_URL, f04.CT_URL
RESUME_KEY = "pt:_device:wz_resume"
BASE_REF = os.environ.get("BASE_REF", "ee5c723")      # alpha.7 + the spec: the "before" for protected functions / ids
INVITE_EMAIL = f04.INVITE_EMAIL
DRAFT = f04.DRAFT

UAS = {
    "gmail_ios": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                  "Mobile/15E148"),
    "outlook_ios": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Mobile/15E148 Outlook-iOS/4.2427.0"),
    "gsa_ios": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "GSA/328.0.660222349 Mobile/15E148 Safari/604.1"),
    "gmail_android_wv": ("Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240805.005; wv) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.134 Mobile Safari/537.36"),
    "safari_iphone": f05.IPHONE_UA,
    "chrome_android": f05.ANDROID_UA,
    "desktop": f05.DESKTOP_UA,
}
IOS_UAS = {"gmail_ios", "outlook_ios", "gsa_ios", "safari_iphone"}
ANDROID_UAS = {"gmail_android_wv", "chrome_android"}
IN_APP_UAS = {"gmail_ios", "outlook_ios", "gsa_ios", "gmail_android_wv"}


# =====================================================================================================
# Fake backend
# =====================================================================================================
class F4HBackend(f06.F06Backend):
    def manager_account(self, email=INVITE_EMAIL, trips=1, names=("יפן 2027", "יוון 2028")):
        """An existing confirmed account (the one that ran the wizard in a browser) that manages `trips` active trips."""
        uid = self.add_account(email)
        tids = []
        for i in range(trips):
            tid, _ = self.trip(name=names[i % len(names)], managers=(), others=())
            self.add_member(tid, uid, "manager", "active", "דנה", joined_at=f05.iso(self.tnow() - (30 - i) * DAY))
            tids.append(tid)
        return uid, tids

    def used_invite(self, email=INVITE_EMAIL, draft=DRAFT, trip_id=None):
        iid, token = self.add_invite(email, draft, sent_days_ago=3, expires_in_days=4, used=True)
        self.invites[iid]["trip_id"] = trip_id
        return iid, token

    def sends(self, device=None):
        """OTP send calls (the 'network log' of criterion 9): updateUser with an email, signInWithOtp, resend."""
        out = []
        for c in self.calls:
            if device is not None and c["device"] != device:
                continue
            op = c.get("op")
            if op == "auth.updateUser" and ((c["msg"].get("attrs") or {}).get("email")):
                out.append(c)
            elif op in ("auth.signInWithOtp", "auth.resend"):
                out.append(c)
        return out

    def verifies(self, device=None):
        return [c for c in self.calls if c.get("op") == "auth.verifyOtp" and (device is None or c["device"] == device)]

    def lookups(self):
        return self.ct("lookup")

    def checks(self):
        """invite-manager `check` calls (fn_calls is shared with the F05 join-trip log; those rows carry a 'name')."""
        return [c for c in self.fn_calls if c.get("action") == "check" and "name" not in c]


# =====================================================================================================
# Browser environment
# =====================================================================================================
EXTNAV_JS = r"""(()=>{if(window.__qaExtNavOn)return;window.__qaExtNavOn=1;window.__qaExtNavs=[];
 const RE=/^(x-safari-https?:|intent:)/i;
 const rep=(u,how)=>{const r={url:String(u),how,page:String(location.href),t:Date.now()};window.__qaExtNavs.push(r);
   try{window.__qaExtNav&&window.__qaExtNav(r)}catch(e){}};
 try{navigation.addEventListener('navigate',e=>{const u=e.destination&&e.destination.url;
   if(u&&RE.test(u)){rep(u,'navigate:'+e.navigationType);if(e.cancelable)e.preventDefault()}})}catch(e){}
 try{const o=window.open;window.open=function(u){if(u&&RE.test(String(u))){rep(u,'window.open');return null}
   return o.apply(this,arguments)}}catch(e){}
})();"""

BIP_JS = r"""(()=>{if(window.__qaBip)return;const B=window.__qaBip={fired:0,prompts:0,installed:0,auto:%s};
 window.__qaFireBip=()=>{const e=new Event('beforeinstallprompt',{cancelable:true});
   e.platforms=['web'];e.userChoice=Promise.resolve({outcome:'accepted',platform:'web'});
   e.prompt=()=>{B.prompts++;try{window.__qaBipReport&&window.__qaBipReport('prompt')}catch(x){}return Promise.resolve({outcome:'accepted'})};
   B.fired++;window.dispatchEvent(e);return true};
 window.__qaFireInstalled=()=>{B.installed++;window.dispatchEvent(new Event('appinstalled'));return true};
 if(B.auto){const go=()=>setTimeout(()=>window.__qaFireBip(),400);
   if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go,{once:true});else go()}
})();"""

# only navigator.standalone (iOS home-screen app) / only display-mode: standalone (Android installed PWA)
IOS_STANDALONE_JS = r"""(()=>{try{Object.defineProperty(Navigator.prototype,'standalone',{configurable:true,get(){return true}})}catch(e){}})();"""
# NOTE: tests/f05/harness.py STANDALONE_JS builds its fake MediaQueryList with Object.assign onto an object whose prototype is
# MediaQueryList.prototype; `matches` is a getter-only accessor there, so every matchMedia('(display-mode: standalone)') call
# THROWS "Cannot set property matches … which has only a getter" (seen in F4H-00b). This harness uses a plain object.
DISPLAY_STANDALONE_JS = r"""(()=>{try{const mm=window.matchMedia.bind(window);window.matchMedia=function(q){
   if(/display-mode:\s*standalone/.test(String(q))){return {matches:true,media:String(q),onchange:null,addListener(){},removeListener(){},
     addEventListener(){},removeEventListener(){},dispatchEvent(){return false}}}return mm(q)}}catch(e){}})();"""
STANDALONE_JS = IOS_STANDALONE_JS + DISPLAY_STANDALONE_JS


class Env(f06.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F4HBackend()

    def new_device(self, name="A", ua=None, standalone=None, bip=None, clock="install", service_workers="block",
                   offline_boot=False, **_):
        """ua: a key of UAS or a raw UA string. standalone: True | 'ios' | 'display' | False | None. bip: 'auto' | None."""
        ua_s = UAS.get(ua, ua) if ua else None
        mobile = bool(ua_s) and bool(re.search(r"iPhone|Android", ua_s))
        conf = {"legacy_fake": False}
        kw = dict(viewport=VIEWPORT, locale="he-IL", timezone_id="Asia/Jerusalem", service_workers=service_workers,
                  permissions=["geolocation", "clipboard-read", "clipboard-write"],
                  geolocation={"latitude": 21.0285, "longitude": 105.8542, "accuracy": 20})
        if ua_s:
            kw["user_agent"] = ua_s
        if mobile:
            kw["has_touch"] = True
            kw["is_mobile"] = True
        ctx = self.browser.new_context(**kw)
        if clock == "install":
            ctx.clock.install(time=FIXED_NOW)
        ctx.expose_binding("__fakeBackend", lambda source, msg, _n=name: self.backend.handle(_n, msg))
        page = ctx.new_page()
        d = f03.F03Device(self, name, ctx, page, conf)
        d.ua_key = ua if ua in UAS else None
        d.ext_navs, d.bip_prompts, d.navs = [], [], []
        ctx.expose_binding("__qaExtNav", lambda source, rec, _d=d: _d.ext_navs.append(dict(rec or {})))
        ctx.expose_binding("__qaBipReport", lambda source, what, _d=d: _d.bip_prompts.append({"what": what, "t": time.time()}))
        ctx.add_init_script(f02.WATCH_JS)
        ctx.add_init_script(f04.OPEN_JS)
        ctx.add_init_script(f20.OFFLINE_JS)
        ctx.add_init_script(f05.TOAST_JS)
        ctx.add_init_script(f06.TEXTS_JS)
        ctx.add_init_script(f06.VIS_JS)
        ctx.add_init_script(EXTNAV_JS)
        ctx.add_init_script(BIP_JS % ("true" if bip == "auto" else "false"))
        if standalone is True:
            ctx.add_init_script(STANDALONE_JS)
        elif standalone == "ios":
            ctx.add_init_script(IOS_STANDALONE_JS)
        elif standalone == "display":
            ctx.add_init_script(DISPLAY_STANDALONE_JS)
        elif standalone is False:
            ctx.add_init_script(f05.NOT_STANDALONE_JS)
        page.on("framenavigated", lambda fr, _d=d: _d.navs.append(fr.url) if fr == _d.page.main_frame else None)
        ctx.route("**/*", lambda route, request, _d=d: self._route5(_d, route, request))
        if offline_boot:
            f20.set_offline_cookie(d, True)
        self.devices.append(d)
        return d

    def _route5(self, dev, route, request):
        base = request.url.split("#")[0].split("?")[0].rstrip("/")
        if base in (IM_URL, CT_URL):
            return f04.Env._route4(self, dev, route, request)   # fake invite-manager check + fake create-trip
        return super()._route5(dev, route, request)


# =====================================================================================================
# Source helpers (flag flips, baseline)
# =====================================================================================================
HOME_FLAG_RE = re.compile(r"""((?:const|let|var)\s+HOME_INSTALL_FEATURE\s*=\s*)(['"])(on|off)\2""")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def invite_html():
    return (INVITE_DIR / "index.html").read_text(encoding="utf-8")


def base_file(rel):
    r = subprocess.run(["git", "-C", str(REPO_DIR), "show", "%s:%s" % (BASE_REF, rel)], capture_output=True)
    assert r.returncode == 0, "harness: cannot read %s:%s: %s" % (BASE_REF, rel, r.stderr.decode()[:200])
    return r.stdout.decode("utf-8")


def flag_value(src):
    m = HOME_FLAG_RE.search(src)
    return m.group(3) if m else None


def flip_home(src, value="off"):
    """Returns (src', found). Absent flag → unchanged source (= alpha.7)."""
    if not HOME_FLAG_RE.search(src):
        return src, False
    return HOME_FLAG_RE.sub(lambda m: m.group(1) + m.group(2) + value + m.group(2), src, count=1), True


def serve_home_off(env, app=True, invite=True):
    """Serve app/ and/or /invite/ with HOME_INSTALL_FEATURE='off'. Returns the files in which the flag was missing."""
    missing = []
    if app:
        s, ok = flip_home(app_html())
        if not ok:
            missing.append("app/index.html")
        env.server.overrides[APP + "index.html"] = s.encode("utf-8")
        env.server.overrides[APP] = s.encode("utf-8")
    if invite:
        s, ok = flip_home(invite_html())
        if not ok:
            missing.append("invite/index.html")
        env.server.overrides[INVITE + "index.html"] = s.encode("utf-8")
        env.server.overrides[INVITE] = s.encode("utf-8")
    return missing


# =====================================================================================================
# Helpers
# =====================================================================================================
norm, btext, has, wait_has = f04.norm, f04.btext, f04.has, f04.wait_has
find, click_text, visible, wait_text = f03.find, f03.click_text, f03.visible, f03.wait_text
layout_problems, is_vis, exists, wait_until = f04.layout_problems, f20.is_vis, f20.exists, f05.wait_until
page_errors, app_state, wait_app_state, running_trip = f05.page_errors, f05.app_state, f05.wait_app_state, f05.running_trip
screen, wait_screen, type_code, send_email = f04.screen, f04.wait_screen, f04.type_code, f04.send_email


def ext_navs(dev, kind=None):
    """kind: 'safari' | 'intent' | None (both)."""
    out = []
    for r in dev.ext_navs:
        u = r.get("url", "")
        if kind == "safari" and not u.lower().startswith("x-safari-"):
            continue
        if kind == "intent" and not u.lower().startswith("intent:"):
            continue
        out.append(r)
    return out


def resume_raw(dev):
    """Raw value of pt:_device:wz_resume (read on the harness blank page of the same origin: no namespacing layer)."""
    try:
        return dev.ls().get(RESUME_KEY)
    except PWError:
        return None


def resume_entry(dev):
    raw = resume_raw(dev)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"__unparsable": raw}


def bip_state(page):
    try:
        return page.evaluate("()=>Object.assign({},window.__qaBip||{})")
    except PWError:
        return {}


def fire_bip(page):
    return page.evaluate("()=>window.__qaFireBip()")


def fire_installed(page):
    return page.evaluate("()=>window.__qaFireInstalled()")


def url_now(page):
    try:
        return page.evaluate("()=>location.href")
    except PWError:
        return page.url


def text_order(page, texts):
    """Document-order index of the first VISIBLE text node (or element innerText) containing each text; None if absent."""
    return page.evaluate(r"""(ts)=>{const N=s=>String(s||'').replace(/[‎‏‪-‮⁦-⁩]/g,'').replace(/[–—‒−]/g,'-').replace(/\s+/g,' ').trim();
      const vis=e=>{if(!e)return false;const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
        for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden')return false}return true};
      const all=[...document.body.querySelectorAll('*')];
      return ts.map(t=>{const k=N(t);const i=all.findIndex(e=>vis(e)&&![...e.children].some(c=>N(c.innerText).includes(k))&&N(e.innerText).includes(k));return i<0?null:i})}""", list(texts))


def anchors_with(page, needle):
    return page.evaluate("""(n)=>[...document.querySelectorAll('a[href]')].filter(a=>{const r=a.getBoundingClientRect();return r.width>0&&r.height>0})
      .map(a=>({href:a.href,raw:a.getAttribute('href'),text:(a.innerText||'').trim()})).filter(a=>a.text.includes(n)||a.raw.includes(n))""", needle)


def clock_ms(page):
    return page.evaluate("()=>Date.now()")
