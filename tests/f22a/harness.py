"""Lonely Planner F22a QA · browser harness (sign in with Google) · version 1.0.0
CHANGE 2026-11-07 F22A-QA-01: new file (no previous version).

Reuses tests/f10/harness.py (and through it F21 → F04-HOME → F06 → F05 → F20 → F04 → F03 → F02) unchanged. New here:
- OAUTH_JS: the fake supabase-js (tests/f05/fake_supabase.js, served by the F05 route) gets the auth calls F22a uses, patched in
  at serve time: linkIdentity / signInWithOAuth (the backend decides the outcome and returns the redirect URL; the fake then
  navigates there, as supabase-js does: location.assign + reload, so the app loads again with the return URL), setSession
  (accepts any token the backend minted), exchangeCodeForSession (?code= / PKCE path), unlinkIdentity.
- F22Backend: Google accounts (`google(email)`), identities on every user, the Supabase rules the spike showed (S1 auto-link
  by verified email on signInWithOAuth, S2 identity_already_exists on linkIdentity) and the R1 rule (unlinkIdentity of the
  last identity → single_identity_not_deletable). `oauth_next` scripts the next round trip: 'ok' | 'cancel' | 'error' |
  'conflict' (forced) ; `oauth_shape` = 'hash' (implicit, default) | 'code' (PKCE ?code=).
Nothing here talks to the network.
"""
import copy
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
if "f10_harness" in sys.modules:
    h10 = sys.modules["f10_harness"]
else:
    _spec = importlib.util.spec_from_file_location("f10_harness", str(REPO_DIR / "tests" / "f10" / "harness.py"))
    h10 = importlib.util.module_from_spec(_spec)
    sys.modules["f10_harness"] = h10
    _spec.loader.exec_module(h10)

f02, f03, f04, f05, f06, f20, h4 = h10.f02, h10.f03, h10.f04, h10.f05, h10.f06, h10.f20, h10.h4
from playwright.sync_api import Error as PWError  # noqa: E402

APP = h10.APP
ROOT = f05.ROOT
APP_DIR = h10.APP_DIR
INVITE_DIR = REPO_DIR / "invite"
PT_URL, PT_KEY = f02.PT_URL, f02.PT_KEY
BASE_REF = os.environ.get("F22A_BASE_REF", "76d2495")     # 3.0.0-alpha.10 (main before F22a)
AUTH_KEY = f02.AUTH_KEY
BETA_KEY = "pt-f22-beta"
CACHE_KEY = h10.CACHE_KEY

# ---------------------------------------------------------------------------------------------------- fake library patch
OAUTH_JS = r"""
      /* F22A-QA-01: OAuth round trip (tests/f22a/harness.py) */
      linkIdentity: async function (creds) {
        creds = creds || {};
        var t = await token();
        log('auth.linkIdentity', { clientId: clientId, provider: creds.provider, options: clone(creds.options || {}) });
        var r = await backend({ op: 'auth.linkIdentity', url: url, key: key, token: t, creds: clone(creds) });
        if (!r || r.error) return { data: { provider: creds.provider, url: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        setTimeout(function () { location.assign(r.url); setTimeout(function () { location.reload(); }, 60); }, 30);
        return { data: { provider: creds.provider, url: r.url }, error: null };
      },
      signInWithOAuth: async function (creds) {
        creds = creds || {};
        log('auth.signInWithOAuth', { clientId: clientId, provider: creds.provider, options: clone(creds.options || {}) });
        var r = await backend({ op: 'auth.signInWithOAuth', url: url, key: key, token: await token(), creds: clone(creds) });
        if (!r || r.error) return { data: { provider: creds.provider, url: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        setTimeout(function () { location.assign(r.url); setTimeout(function () { location.reload(); }, 60); }, 30);
        return { data: { provider: creds.provider, url: r.url }, error: null };
      },
      exchangeCodeForSession: async function (code) {
        log('auth.exchangeCodeForSession', { clientId: clientId });
        var r = await backend({ op: 'auth.exchangeCode', url: url, key: key, code: String(code || '') });
        if (!r || r.error) return { data: { user: null, session: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        await writeSession(r.session); emit('SIGNED_IN', r.session);
        return { data: { user: r.session.user, session: r.session }, error: null };
      },
      unlinkIdentity: async function (identity) {
        var t = await token();
        log('auth.unlinkIdentity', { clientId: clientId, provider: identity && identity.provider });
        var r = await backend({ op: 'auth.unlinkIdentity', url: url, key: key, token: t, identity: clone(identity || {}) });
        if (!r || r.error) return { data: null, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        var s = await readSession(); if (s) { s.user = r.user; await writeSession(s); emit('USER_UPDATED', s); }
        return { data: {}, error: null };
      },
"""
SETSESSION_OLD = """        if (s && tokens && tokens.access_token === s.access_token) return { data: { user: s.user, session: s }, error: null };"""
SETSESSION_NEW = SETSESSION_OLD + """
        /* F22A-QA-01: a token the backend minted (OAuth return hash) is accepted like supabase-js does after /user */
        var rs = await backend({ op: 'auth.setSession', url: url, key: key, tokens: clone(tokens || {}) });
        if (rs && rs.session) { await writeSession(rs.session); emit('SIGNED_IN', rs.session); return { data: { user: rs.session.user, session: rs.session }, error: null }; }"""
_ANCHOR = "      startAutoRefresh: async function () {}"


def patch_fake():
    src = f05.FAKE_JS
    if "F22A-QA-01" in src:
        return
    assert _ANCHOR in src and SETSESSION_OLD in src, "harness: tests/f05/fake_supabase.js changed (anchor not found)"
    f05.FAKE_JS = src.replace(_ANCHOR, OAUTH_JS + _ANCHOR).replace(SETSESSION_OLD, SETSESSION_NEW)


patch_fake()

OAUTH_ERR = {
    "cancel": {"error": "access_denied", "error_code": "access_denied", "error_description": "The user denied the request"},
    "error": {"error": "server_error", "error_code": "unexpected_failure", "error_description": "Unable to exchange external code"},
    "conflict": {"error": "server_error", "error_code": "identity_already_exists",
                 "error_description": "Identity is already linked to another user"},
}


def _ident(uid, provider, email):
    iid = str(uuid.uuid4())
    return {"id": iid, "identity_id": iid, "user_id": uid, "provider": provider,
            "identity_data": {"email": email, "email_verified": True, "sub": uuid.uuid4().hex[:21]},
            "created_at": "2026-11-01T10:00:00Z", "last_sign_in_at": "2026-11-01T10:00:00Z"}


class F22Backend(h10.F10Backend):
    def __init__(self):
        super().__init__()
        self.google_accounts = {}     # email -> {"name": ...}
        self.oauth_next = "ok"
        self.oauth_pick = None        # email chosen "at Google" for the next round trip
        self.oauth_shape = "hash"
        self.codes = {}               # PKCE code -> uid
        self.oauth_calls = []         # {op, device, options, outcome}
        self.unlink_calls = []

    # ---------- setup ----------
    def google(self, email, name="QA"):
        self.google_accounts[email.lower()] = {"name": name}
        return email.lower()

    def email_account(self, email, google=False):
        """An existing confirmed email account (F04) — with google=True also the Google identity (S1 already happened)."""
        uid = self.add_account(email)
        u = self.users[uid]
        u["identities"] = [_ident(uid, "email", email)]
        if google:
            self.google(email)
            u["identities"].append(_ident(uid, "google", email))
        return uid

    def identities(self, uid):
        return [i["provider"] for i in (self.users.get(uid) or {}).get("identities") or []]

    def owner_of_google(self, email):
        for uid, u in self.users.items():
            for i in u.get("identities") or []:
                if i["provider"] == "google" and str(i["identity_data"].get("email", "")).lower() == email:
                    return uid
        return None

    def _session(self, uid):
        tok = "fake-at." + uid + "." + uuid.uuid4().hex[:8]
        self.tokens[tok] = uid
        return {"access_token": tok, "refresh_token": "fake-rt-" + uuid.uuid4().hex, "token_type": "bearer",
                "expires_in": 3600, "expires_at": int(time.time()) + 3600, "user": copy.deepcopy(self.users[uid])}

    def _return_url(self, creds, uid=None, err=None):
        base = ((creds.get("options") or {}).get("redirectTo") or "").split("#")[0]
        if err:
            if self.oauth_shape == "code":
                return base + ("&" if "?" in base else "?") + urlencode(err)
            return base + "#" + urlencode(err)
        if self.oauth_shape == "code":
            code = uuid.uuid4().hex
            self.codes[code] = uid
            return base + ("&" if "?" in base else "?") + "code=" + code
        s = self._session(uid)
        return base + "#" + urlencode({"access_token": s["access_token"], "expires_at": s["expires_at"], "expires_in": 3600,
                                        "provider_token": "ya29.fake", "refresh_token": s["refresh_token"],
                                        "token_type": "bearer"})

    # ---------- binding ----------
    def handle(self, device, msg):
        msg = msg or {}
        op = msg.get("op")
        if op not in ("auth.linkIdentity", "auth.signInWithOAuth", "auth.exchangeCode", "auth.setSession", "auth.unlinkIdentity"):
            return super().handle(device, msg)
        with self.lock:
            entry = {"device": device, "t": time.time(), "op": op, "page": msg.get("page"), "online": msg.get("online"),
                     "url": str(msg.get("url") or ""), "msg": copy.deepcopy(msg)}
            self.calls.append(entry)
            if msg.get("online") is False or self.mode == "down":
                return {"error": {"name": "AuthRetryableFetchError", "message": "Failed to fetch", "status": 0}}
            if str(msg.get("url") or "").rstrip("/") != PT_URL or msg.get("key") != PT_KEY:
                return {"error": {"code": "FAKE_WRONG_PROJECT", "message": "fake: wrong project/key", "status": 0}}
            res = getattr(self, "_" + op.split(".")[1])(device, msg)
            entry["result"] = copy.deepcopy(res)
            return res

    def _pick(self):
        e = self.oauth_pick or (next(iter(self.google_accounts)) if self.google_accounts else "qa.google@example.com")
        self.google_accounts.setdefault(e, {"name": "QA"})
        return e

    def _linkIdentity(self, device, msg):
        creds = msg.get("creds") or {}
        uid = self.tokens.get(msg.get("token"))
        rec = {"op": "link", "device": device, "options": creds.get("options"), "uid": uid}
        self.oauth_calls.append(rec)
        if not uid:
            return {"error": {"name": "AuthSessionMissingError", "message": "Auth session missing!", "status": 400}}
        nxt, self.oauth_next = self.oauth_next, "ok"
        if nxt in OAUTH_ERR:
            rec["outcome"] = nxt
            return {"url": self._return_url(creds, err=OAUTH_ERR[nxt])}
        email = self._pick()
        owner = self.owner_of_google(email)
        if owner and owner != uid:          # S2
            rec["outcome"] = "conflict"
            return {"url": self._return_url(creds, err=OAUTH_ERR["conflict"])}
        u = self.users[uid]
        u.setdefault("identities", [])
        if not owner:
            u["identities"].append(_ident(uid, "google", email))
        if not u.get("email"):
            u.update({"email": email, "email_confirmed_at": f05.iso(self.tnow())})
        u["is_anonymous"] = False
        rec["outcome"] = "ok"
        return {"url": self._return_url(creds, uid=uid)}

    def _signInWithOAuth(self, device, msg):
        creds = msg.get("creds") or {}
        rec = {"op": "signin", "device": device, "options": creds.get("options"), "uid": self.tokens.get(msg.get("token"))}
        self.oauth_calls.append(rec)
        nxt, self.oauth_next = self.oauth_next, "ok"
        if nxt in OAUTH_ERR:
            rec["outcome"] = nxt
            return {"url": self._return_url(creds, err=OAUTH_ERR[nxt])}
        email = self._pick()
        uid = self.owner_of_google(email)
        if not uid:
            uid = self.user_by_email(email)          # S1: auto-link by verified email
            if uid:
                self.users[uid].setdefault("identities", []).append(_ident(uid, "google", email))
        if not uid:
            uid = str(uuid.uuid4())
            self.users[uid] = {"id": uid, "aud": "authenticated", "role": "authenticated", "email": email, "phone": "",
                               "is_anonymous": False, "email_confirmed_at": f05.iso(self.tnow()),
                               "app_metadata": {"provider": "google", "providers": ["google"]}, "user_metadata": {},
                               "identities": [_ident(uid, "google", email)], "created_at": f05.iso(self.tnow()),
                               "updated_at": f05.iso(self.tnow())}
        rec["outcome"] = "ok"
        rec["result_uid"] = uid
        return {"url": self._return_url(creds, uid=uid)}

    def _exchangeCode(self, device, msg):
        uid = self.codes.pop(str(msg.get("code") or ""), None)
        if not uid:
            return {"error": {"name": "AuthApiError", "message": "invalid flow state, no valid flow state found", "status": 404,
                              "code": "flow_state_not_found"}}
        return {"session": self._session(uid)}

    def _setSession(self, device, msg):
        t = (msg.get("tokens") or {}).get("access_token")
        uid = self.tokens.get(t)
        if not uid:
            return {"error": {"name": "AuthApiError", "message": "invalid JWT", "status": 401}}
        s = self._session(uid)
        self.tokens[t] = uid
        s["access_token"] = t
        return {"session": s}

    def _unlinkIdentity(self, device, msg):
        uid = self.tokens.get(msg.get("token"))
        ident = msg.get("identity") or {}
        self.unlink_calls.append({"device": device, "uid": uid, "provider": ident.get("provider")})
        if not uid:
            return {"error": {"name": "AuthApiError", "message": "invalid JWT", "status": 401}}
        u = self.users[uid]
        ids = u.get("identities") or []
        if len(ids) <= 1:      # R1 as GoTrue answers it (status 422)
            return {"error": {"name": "AuthApiError", "message": "User must have at least 1 identity after unlinking",
                              "status": 422, "code": "single_identity_not_deletable"}}
        u["identities"] = [i for i in ids if i.get("identity_id") != ident.get("identity_id")]
        return {"user": copy.deepcopy(u)}


class Env(h10.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F22Backend()


# ---------------------------------------------------------------------------------------------------- sources
FLAG_RE = re.compile(r"""((?:const|let|var)\s+ACCOUNT_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")


def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def invite_html():
    return (INVITE_DIR / "index.html").read_text(encoding="utf-8")


def flag_value(src):
    m = FLAG_RE.search(src)
    return m.group(3) if m else None


def flip(src, value):
    assert FLAG_RE.search(src), "ACCOUNT_FEATURE not declared"
    return FLAG_RE.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1)


def base_file(rel="app/index.html"):
    return h10.f02_git_show(BASE_REF, rel)


def serve(env, flag="on", src=None, invite=None):
    b = (src if src is not None else flip(app_html(), flag)).encode("utf-8")
    env.server.overrides[APP + "index.html"] = b
    env.server.overrides[APP] = b
    if invite is not None:
        ib = (invite if not invite in ("on", "off", "beta") else flip(invite_html(), invite)).encode("utf-8")
        env.server.overrides[ROOT + "invite/index.html"] = ib
        env.server.overrides[ROOT + "invite/"] = ib


# ---------------------------------------------------------------------------------------------------- UI helpers
VIS_JS = r"""(s)=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();
 if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);
 if(c.display==='none'||c.visibility==='hidden'||a.hidden)return false}return true}"""


def vis(page, sel):
    try:
        return page.evaluate(VIS_JS, sel)
    except PWError:
        return False


def wait(fn, timeout=8.0, page=None):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if fn():
                return True
        except PWError:
            pass
        if page is not None:
            try:
                page.wait_for_timeout(150)
                continue
            except PWError:
                pass
        time.sleep(0.15)
    return False


def wait_vis(page, sel, timeout=8.0):
    return wait(lambda: vis(page, sel), timeout, page)


def text(page, sel):
    try:
        return page.evaluate("(s)=>{const e=document.querySelector(s);return e?(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim():''}", sel)
    except PWError:
        return ""


def body(page):
    return text(page, "body")


def url(page):
    try:
        return page.evaluate("()=>location.href")
    except PWError:
        return ""


def toasts(page):
    try:
        return page.evaluate("()=>{const e=document.getElementById('ptF22Toast');return e?(e.innerText||'').trim():''}")
    except PWError:
        return ""


def in_trip(dev, timeout=25.0):
    """The trip runs (main script started) — any panel may be open (after a link return the app opens "אני")."""
    js = "()=>!!(window.__PT&&window.__PT.started&&window.__PT.phase==='running'&&window.__PT.tripId)"
    return wait(lambda: dev.page.evaluate(js), timeout, dev.page)


def boot_member(env, key="V", role="editor", name="A", me="נועה", **kw):
    """A device whose anonymous identity is a member of fixture trip `key` (F10 fixture), booted into it."""
    tid = env.backend.fixture(key, role=role, me=me)
    dev = env.new_device(name, **kw)
    dev.seed_ls({CACHE_KEY: json.dumps({"trip_id": tid, "role": role})})
    st = h10.reboot(dev)
    assert st == "app", "boot: state %r" % st
    env.backend.links.clear()   # later devices sign in without memberships
    return tid, dev


def open_me(page):
    h10.tab(page, "more")
    assert wait_vis(page, "#ptF22MeRow"), "#ptF22MeRow not visible in 'עוד'"
    page.locator("#ptF22MeRow").click()
    assert wait_vis(page, "#ptF22Me"), "#ptF22Me did not open"
    page.wait_for_timeout(700)


def gate(env, name="G", **kw):
    dev = env.new_device(name, **kw)
    dev.page.goto(env.server.origin + APP, wait_until="commit")
    st = f20.wait_state(dev.page, "nc", 20)
    assert st == "nc", "gate: state %r" % st
    return dev


def after_return(dev, timeout=20.0):
    """Wait for the reload that ends the fake round trip and for the app to settle."""
    dev.page.wait_for_timeout(900)
    try:
        dev.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
    except PWError:
        pass
    dev.page.wait_for_timeout(1200)


def page_errors(dev):
    return f20.page_errors(dev)


SIG_JS = r"""(sels)=>{const out={};const vis=e=>{for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none')return false}return true};
 const walk=(e,acc)=>{const a=[e.tagName,e.id||'',[...e.classList].sort().join('.'),e.getAttribute('aria-label')||'',vis(e)?'v':'h'];
   const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.replace(/\s+/g,' ').trim()).filter(Boolean).join('|');
   acc.push(a.join('~')+(own?' "'+own+'"':''));for(const c of e.children)if(!['SCRIPT','STYLE'].includes(c.tagName))walk(c,acc)};
 for(const s of sels){const e=document.querySelector(s);const acc=[];if(e)walk(e,acc);out[s]=acc}return out}"""

LAYOUT_JS = r"""(s)=>{const root=document.querySelector(s);if(!root)return null;
 const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||c.visibility==='hidden')return false}return true};
 const small=[...root.querySelectorAll('button,input,select,a[href],[role=button]')].filter(vis).filter(b=>!b.parentElement.closest('button'))
   .map(b=>{const r=b.getBoundingClientRect();return {t:(b.innerText||b.getAttribute('aria-label')||b.id||b.tagName).replace(/\s+/g,' ').trim().slice(0,30),h:Math.round(r.height),w:Math.round(r.width)}})
   .filter(x=>x.h<43.5||x.w<43.5);
 const over=[...root.querySelectorAll('*')].filter(vis).filter(e=>{const r=e.getBoundingClientRect();return r.right>innerWidth+0.5||r.left<-0.5}).length;
 return {small,over,scroll:document.scrollingElement.scrollWidth-innerWidth,dir:getComputedStyle(root).direction}}"""


def layout(page, sel):
    return page.evaluate(LAYOUT_JS, sel)
