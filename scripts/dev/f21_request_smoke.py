# CHANGE 2026-10-27 F21-REQ-SMOKE-01: new file (no previous version). Dev smoke test for the F21 /request/ page (not the QA
#   suite), no network: a local GitHub-Pages-like static server for the repo, Chromium at 390x844, the Edge Function
#   request-trip route-intercepted by an in-memory fake (start / verify / resend with the spec §3.1 result codes), and the
#   Turnstile script replaced by a fake that honours Cloudflare's documented test site keys (always-pass
#   1x00000000000000000000AA → token; always-fail 2x00000000000000000000AB → no token). Covers both languages and both
#   REQUEST_FEATURE states: closed card without network, language rules, in-app hop (iPhone / Android), validation bounds,
#   start → code → verify → sent, error mapping, resume (no send on reload, key contents, clears), daily cap, offline,
#   390px layout (no horizontal scroll, touch >= 44px, no duplicate ids, LTR emails/codes).
# usage: python3 scripts/dev/f21_request_smoke.py        (F21_SHOTS=<dir> also saves screenshots)
import http.server
import json
import os
import re
import sys
import threading
import time
import uuid
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = "/request/"
SRC = (ROOT / "request" / "index.html").read_text(encoding="utf-8")
FLAG_RE = re.compile(r"""(const\s+REQUEST_FEATURE\s*=\s*)(['"])(on|off)\2""")
KEY_RE = re.compile(r"""(const\s+TURNSTILE_SITE_KEY\s*=\s*)(['"])([^'"]*)\2""")
PASS_KEY, FAIL_KEY = "1x00000000000000000000AA", "2x00000000000000000000AB"
LANG_KEY, RESUME_KEY = "pt:_device:rq_lang", "pt:_device:rq_resume"
GOOD = "123456"
IOS_GSA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
           "GSA/330.0.661587829 Mobile/15E148")
ANDROID_WV = ("Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
              "Chrome/126.0.0.0 Mobile Safari/537.36")
ANDROID_CHROME = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile "
                  "Safari/537.36")

FAKE_TS = r"""(function(){var n=0,w={};window.turnstile={
 render:function(el,o){var id='ts'+(++n);w[id]={el:el,o:o};window.__ts={renders:(window.__ts&&window.__ts.renders||0)+1,
  resets:window.__ts&&window.__ts.resets||0,lang:o.language,sitekey:o.sitekey};
  var d=document.createElement('div');d.className='fake-ts';d.style.cssText='width:300px;max-width:100%;height:65px;border:1px solid #ccc';
  d.textContent='[turnstile '+o.sitekey+']';el.appendChild(d);
  setTimeout(function(){if(!w[id])return;if(o.sitekey==='1x00000000000000000000AA')o.callback('XXXX.DUMMY.TOKEN.XXXX');
   else if(o['error-callback'])o['error-callback']('blocked')},30);return id},
 reset:function(id){window.__ts.resets++;var x=w[id];if(x)setTimeout(function(){if(w[id]&&x.o.sitekey==='1x00000000000000000000AA')x.o.callback('XXXX.DUMMY.TOKEN.XXXX')},30)},
 remove:function(id){var x=w[id];if(x){try{x.el.innerHTML=''}catch(e){}delete w[id]}}};
 var s=document.currentScript&&document.currentScript.src||'';var m=/onload=([A-Za-z_$][\w$]*)/.exec(s);
 if(m&&typeof window[m[1]]==='function')setTimeout(window[m[1]],0);})();"""

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:400]))


# ------------------------------------------------------------------ static server with per-path overrides
class Srv:
    def __init__(self):
        self.overrides = {}
        outer = self

        class H(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                p = self.path.split("?")[0].split("#")[0]
                if p in outer.overrides:
                    b = outer.overrides[p]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                return super().do_GET()

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=str(ROOT)))
        self.port = self.httpd.server_address[1]
        self.origin = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def variant(self, flag="on", key=PASS_KEY):
        s = FLAG_RE.sub(lambda m: m.group(1) + "'" + flag + "'", SRC, count=1)
        s = KEY_RE.sub(lambda m: m.group(1) + "'" + key + "'", s, count=1)
        b = s.encode("utf-8")
        self.overrides[PAGE] = b
        self.overrides[PAGE + "index.html"] = b


# ------------------------------------------------------------------ fake request-trip
class Fake:
    def __init__(self):
        self.calls, self.rows, self.mode = [], {}, {}

    def handle(self, body):
        a = body.get("action")
        self.calls.append(body)
        forced = self.mode.get(a)
        if forced:
            return forced
        if a == "start":
            if body.get("turnstile_token") != "XXXX.DUMMY.TOKEN.XXXX":
                return {"ok": False, "code": "turnstile_failed"}
            rid = str(uuid.uuid4())
            self.rows[rid] = {"status": "unverified", "wrong": 0, "body": body}
            return {"ok": True, "request_id": rid, "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        row = self.rows.get(body.get("request_id"))
        if not row:
            return {"ok": False, "code": "request_unknown"}
        if a == "verify":
            if body.get("code") == GOOD:
                row["status"] = "pending"
                return {"ok": True}
            row["wrong"] += 1
            if row["wrong"] >= 5:
                del self.rows[body["request_id"]]
                return {"ok": False, "code": "code_locked"}
            return {"ok": False, "code": "code_wrong", "attempts_left": 5 - row["wrong"]}
        if a == "resend":
            return {"ok": True, "request_id": body["request_id"], "sent_at": "x"}
        return {"ok": False, "code": "invalid_request"}

    def n(self, action):
        return len([c for c in self.calls if c.get("action") == action])


def main():
    srv = Srv()
    shots = os.environ.get("F21_SHOTS")
    if shots:
        os.makedirs(shots, exist_ok=True)

    with sync_playwright() as p:
        br = p.chromium.launch()

        def device(ua=None, locale="en-US", flag="on", key=PASS_KEY, fake=None):
            srv.variant(flag, key)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, locale=locale,
                                 service_workers="block", has_touch=True)
            d = type("D", (), {})()
            d.ctx, d.fake, d.net, d.reqnav = ctx, fake or Fake(), [], []

            def route(r, req):
                u = req.url
                d.net.append(u)
                if "challenges.cloudflare.com/turnstile" in u:
                    return r.fulfill(status=200, content_type="text/javascript", body=FAKE_TS)
                if "/functions/v1/request-trip" in u:
                    if req.method == "OPTIONS":
                        return r.fulfill(status=204)
                    hd = req.headers
                    d.lastHeaders = hd
                    out = d.fake.handle(json.loads(req.post_data or "{}"))
                    return r.fulfill(status=200, content_type="application/json", body=json.dumps(out))
                if u.startswith(srv.origin):
                    return r.continue_()
                return r.abort()

            ctx.route("**/*", route)
            d.page = ctx.new_page()
            cdp = ctx.new_cdp_session(d.page)
            cdp.send("Page.enable")
            cdp.on("Page.frameRequestedNavigation", lambda ev: d.reqnav.append(ev.get("url")))
            return d

        def go(d, q="", until="domcontentloaded"):
            d.page.goto(srv.origin + PAGE + q, wait_until=until)
            d.page.wait_for_function("()=>{const a=document.getElementById('rqApp');return a&&a.dataset.screen!=='loading'}")

        def screen(d):
            return d.page.evaluate("()=>document.getElementById('rqApp').dataset.screen")

        def shot(d, name):
            if shots:
                d.page.screenshot(path=os.path.join(shots, name + ".png"), full_page=True)

        def ls(d, k):
            return d.page.evaluate("k=>localStorage.getItem(k)", k)

        def layout(d, label):
            r = d.page.evaluate(r"""()=>{
              const de=document.documentElement,out={sw:de.scrollWidth,cw:de.clientWidth,small:[],dup:[]};
              const ids={};document.querySelectorAll('[id]').forEach(e=>{ids[e.id]=(ids[e.id]||0)+1});
              out.dup=Object.keys(ids).filter(k=>ids[k]>1);
              document.querySelectorAll('button,a[href],select,input,textarea').forEach(e=>{
                const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden'||e.closest('[hidden]'))return;
                let r=e.getBoundingClientRect();if(!r.width&&!r.height)return;
                if(e.type==='checkbox'){const l=e.closest('label');if(l)r=l.getBoundingClientRect()}
                if(r.height<44-0.5||r.width<44-0.5)out.small.push((e.id||e.tagName+'.'+e.className)+' '+Math.round(r.width)+'x'+Math.round(r.height));
              });return out}""")
            check("%s: no horizontal scroll (%s <= %s)" % (label, r["sw"], r["cw"]), r["sw"] <= r["cw"], r)
            check("%s: touch targets >= 44px" % label, not r["small"], r["small"])
            check("%s: no duplicate ids" % label, not r["dup"], r["dup"])

        def fill_form(d, name="Dana Cohen", email="  Dana@Example.com ", countries=("JP", "KR"), month_idx=6, travellers=None, note=None):
            pg = d.page
            pg.fill("#rqName", name)
            pg.fill("#rqEmail", email)
            pg.wait_for_function("()=>document.querySelector('#rqWhere')")
            for c in countries:
                pg.click("#rqWhere")
                pg.fill("#rqWhere", c)
                pg.wait_for_selector('#rqWhereList button[data-code="%s"]' % c)
                pg.click('#rqWhereList button[data-code="%s"]' % c)
            if month_idx is not None:
                pg.select_option("#rqWhen", index=month_idx)
            if travellers is not None:
                pg.fill("#rqCount", str(travellers))
            if note is not None:
                pg.fill("#rqNote", note)

        def ts_ready(d):
            d.page.wait_for_function("()=>window.__ts&&window.__ts.renders>0")
            time.sleep(0.1)

        def type_code(d, code):
            d.page.click("#rqOtp0")
            d.page.keyboard.type(code)

        # ------------------------------------------------------------ 1 flag off (AC 1)
        print("flag off (AC 1):")
        for loc in ("he-IL", "en-US"):
            d = device(locale=loc, flag="off")
            go(d)
            t = d.page.inner_text("#rqApp")
            check("closed card [%s]" % loc, screen(d) == "closed" and "הבקשות סגורות כרגע" in t and "Requests are closed right now" in t, t)
            time.sleep(0.4)
            other = [u for u in d.net if not u.rstrip("/").endswith("/request")]
            check("no network beyond the page itself [%s]" % loc, not other, other)
            if loc == "he-IL":
                shot(d, "f21_closed")
                layout(d, "closed")
            d.ctx.close()

        # ------------------------------------------------------------ 2 language (AC 2)
        print("language (AC 2):")
        d = device(locale="he-IL")
        go(d)
        ts_ready(d)
        check("Hebrew device → he RTL", d.page.evaluate("()=>[document.documentElement.lang,document.documentElement.dir]") == ["he", "rtl"])
        check("Hebrew form: no D11a English box", d.page.query_selector("#rqEnInfo") is None)
        check("Turnstile language = he", d.page.evaluate("()=>window.__ts.lang") == "he")
        check("switch on the right in RTL", d.page.evaluate("()=>{const r=document.querySelector('.rq-lang').getBoundingClientRect();return r.right>300}"))
        check("aria-pressed he", d.page.get_attribute("#rqLangHe", "aria-pressed") == "true")
        texts = d.page.inner_text("#rqApp")
        check("Hebrew texts", "רוצים להקים טיול?" in texts and "שליחת קוד אימות" in texts and "נמחקת אחרי 5 ימים" in texts, texts[:300])
        layout(d, "form he")
        shot(d, "f21_form_he")
        fill_form(d, name="דנה כהן", note="משפחה עם 3 ילדים")
        d.page.click("#rqUnsure")
        d.page.click("#rqPlus")
        d.page.click("#rqLangEn")
        check("switch → en LTR", d.page.evaluate("()=>[document.documentElement.lang,document.documentElement.dir]") == ["en", "ltr"])
        vals = d.page.evaluate("()=>({n:rqName.value,e:rqEmail.value,c:[...document.querySelectorAll('#rqChips .rq-chip')].map(x=>x.dataset.code),u:rqUnsure.checked,w:rqWhen.disabled,t:rqCount.value,note:rqNote.value,chip:document.querySelector('#rqChips .rq-chip').innerText})")
        check("switch keeps typed values", vals["n"] == "דנה כהן" and vals["c"] == ["JP", "KR"] and vals["u"] and vals["w"] and vals["t"] == "3" and vals["note"] == "משפחה עם 3 ילדים", vals)
        check("chips re-render in English", "Japan" in vals["chip"], vals)
        check("choice stored", ls(d, LANG_KEY) == "en")
        check("EN form shows the D11a box", d.page.query_selector("#rqEnInfo") is not None and "Hebrew for now" in d.page.inner_text("#rqEnInfo"))
        check("switch on the right in LTR", d.page.evaluate("()=>{const r=document.querySelector('.rq-lang').getBoundingClientRect();return r.right>300}"))
        ts_ready(d)
        check("Turnstile re-rendered in en", d.page.evaluate("()=>window.__ts.lang") == "en")
        go(d)
        check("reload → stored choice en (Hebrew device)", d.page.evaluate("()=>document.documentElement.lang") == "en")
        go(d, "?lang=he")
        check("?lang=he wins over stored", d.page.evaluate("()=>document.documentElement.lang") == "he")
        d.ctx.close()
        d = device(locale="en-US")
        go(d, "?lang=en")
        ts_ready(d)
        check("?lang=en → English LTR", d.page.evaluate("()=>[document.documentElement.lang,document.documentElement.dir]") == ["en", "ltr"])
        layout(d, "form en")
        shot(d, "f21_form_en")
        d.ctx.close()
        d = device(locale="en-US")
        go(d, "#lang=he")
        check("#lang=he → Hebrew", d.page.evaluate("()=>document.documentElement.lang") == "he")
        d.ctx.close()
        d = device(locale="fr-FR")
        go(d)
        check("non-Hebrew device → en", d.page.evaluate("()=>document.documentElement.lang") == "en")
        d.ctx.close()

        # ------------------------------------------------------------ 3 in-app (AC 3)
        print("in-app browser (AC 3):")
        d = device(ua=IOS_GSA, locale="he-IL")
        go(d)
        check("iPhone Gmail → in-app screen", screen(d) == "inapp")
        time.sleep(0.3)
        check("iPhone: no automatic navigation", not d.reqnav, d.reqnav)
        t = d.page.inner_text("#rqApp")
        check("iPhone texts", "פותחים בדפדפן הרגיל" in t and "פתיחה בספארי" in t and "הכפתור לא עבד?" in t and "להמשיך כאן בכל זאת" in t, t)
        layout(d, "in-app iPhone he")
        shot(d, "f21_inapp_ios_he")
        d.page.click("#rqSafari")
        time.sleep(0.3)
        want = "x-safari-https://127.0.0.1:%d%s?lang=he" % (srv.port, PAGE)
        check("Safari button → x-safari-https://…/request/?lang=he", want in d.reqnav, d.reqnav)
        d.page.click("#rqLangEn")
        check("in-app re-renders in en without a hop", screen(d) == "inapp" and "Open in Safari" in d.page.inner_text("#rqApp"))
        d.page.click("#rqHere")
        check("'continue here' → form", screen(d) == "form")
        d.page.click("#rqLangHe")
        check("in-app not shown again after 'continue here'", screen(d) == "form")
        d.ctx.close()
        d = device(ua=ANDROID_WV, locale="en-US")
        go(d, "?lang=en", until="commit")  # the automatic intent:// hop runs during parsing
        time.sleep(0.5)
        intents = [u for u in d.reqnav if u.startswith("intent://")]
        want = "intent://127.0.0.1:%d%s?lang=en#Intent;scheme=https;package=com.android.chrome;end" % (srv.port, PAGE)
        check("Android WebView → one automatic intent:// hop", intents == [want], d.reqnav)
        check("Android in-app texts", "Switching to Chrome" in d.page.inner_text("#rqApp") and d.page.query_selector("#rqChrome") is not None)
        layout(d, "in-app Android en")
        shot(d, "f21_inapp_android_en")
        d.page.click("#rqLangHe")
        time.sleep(0.3)
        check("language switch does not hop again", len([u for u in d.reqnav if u.startswith("intent://")]) == 1, d.reqnav)
        d.page.click("#rqChrome")
        time.sleep(0.3)
        check("fallback button → intent:// (lang he)", any(u.startswith("intent://") and "lang=he" in u for u in d.reqnav), d.reqnav)
        d.ctx.close()
        d = device(ua=ANDROID_CHROME, locale="en-US")
        go(d)
        time.sleep(0.3)
        check("Android Chrome → form, no hop", screen(d) == "form" and not d.reqnav, d.reqnav)
        d.ctx.close()

        # ------------------------------------------------------------ 4 validation (AC 4)
        print("validation (AC 4):")
        d = device(locale="he-IL")
        go(d)
        ts_ready(d)
        pg = d.page
        pg.click("#rqSend")
        check("empty form → inline errors, focus on name", pg.query_selector("#rqNameErr") and pg.evaluate("()=>document.activeElement.id") == "rqName")
        check("button stays enabled", pg.is_enabled("#rqSend"))
        layout(d, "form errors he")
        shot(d, "f21_form_errors_he")

        def only_err(setup, field, label):
            go(d)
            ts_ready(d)
            fill_form(d)
            pg.evaluate(setup)
            n0 = d.fake.n("start")
            pg.click("#rqSend")
            errs = pg.evaluate("()=>[...document.querySelectorAll('.rq-err')].map(e=>e.id)")
            check("%s → inline %s, no call" % (label, field), errs == [field] and d.fake.n("start") == n0, errs)

        only_err("()=>{rqName.value='x'.repeat(41)}", "rqNameErr", "name 41")
        only_err("()=>{rqName.value='   '}", "rqNameErr", "name 0")
        only_err("()=>{rqEmail.value='dana@'}", "rqEmailErr", "bad email")
        only_err("()=>{document.querySelectorAll('#rqChips button[data-rm]').forEach(b=>b.click())}", "rqCountriesErr", "0 countries")
        only_err("()=>{const o=document.createElement('option');o.value='2030-01-01';o.textContent='x';rqWhen.appendChild(o);rqWhen.value='2030-01-01'}", "rqMonthErr", "month outside 18")
        only_err("()=>{rqWhen.value=''}", "rqMonthErr", "no month, not 'unsure'")
        only_err("()=>{rqCount.value='0'}", "rqTravellersErr", "travellers 0")
        only_err("()=>{rqCount.value='31'}", "rqTravellersErr", "travellers 31")
        only_err("()=>{rqNote.value='a'.repeat(201)}", "rqNoteErr", "note 201")
        go(d)
        ts_ready(d)
        fill_form(d, countries=("JP", "KR", "TH", "VN", "LA", "KH", "MY", "SG", "ID", "PH", "MM"))
        n0 = d.fake.n("start")
        pg.click("#rqSend")
        check("11 countries → inline, no call", pg.query_selector("#rqCountriesErr") is not None and d.fake.n("start") == n0)
        opts = pg.evaluate("()=>[...rqWhen.options].map(o=>o.value).filter(Boolean)")
        check("month select: 18 months from the current month", len(opts) == 18 and opts[0] == time.strftime("%Y-%m-01"), opts[:2])
        check("stepper clamps to 1..30", pg.evaluate("()=>{rqCount.value='30';rqPlus.click();const a=rqCount.value;rqCount.value='1';rqMinus.click();return a+'/'+rqCount.value}") == "30/1")
        pg.fill("#rqNote", "abc")
        check("note live counter", pg.inner_text("#rqNoteCount") == "3/200")
        pg.fill("#rqWhere", "פורט")
        pg.wait_for_selector('#rqWhereList button[data-code]')
        check("type-ahead matches Hebrew names", pg.query_selector('#rqWhereList button[data-code="PT"]') is not None)
        pg.fill("#rqWhere", "")
        pg.evaluate("()=>rqWhere.blur()")
        pg.click("#rqWhere")
        first = pg.evaluate("()=>[...document.querySelectorAll('#rqWhereList button[data-code]')].map(b=>b.dataset.code)")
        check("empty type-ahead lists popular countries", len(first) > 0, first)
        d.ctx.close()

        # ------------------------------------------------------------ 5 happy path + Turnstile (AC 5, 6, 7)
        print("start → code → verify → sent (AC 5–7):")
        d = device(locale="he-IL")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d, note="  משפחה  ")
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        b = d.fake.calls[-1]
        check("start body", b["action"] == "start" and b["lang"] == "he" and b["email"] == "dana@example.com" and b["countries"] == ["JP", "KR"]
              and re.match(r"^\d{4}-\d{2}-01$", b["month"] or "") and b["travellers"] == 2 and b["note"] == "משפחה"
              and b["turnstile_token"] == "XXXX.DUMMY.TOKEN.XXXX" and b["name"] == "Dana Cohen", b)
        check("headers: apikey + json", d.lastHeaders.get("apikey", "").startswith("sb_publishable_") and "application/json" in d.lastHeaders.get("content-type", ""))
        rk = json.loads(ls(d, RESUME_KEY) or "{}")
        check("resume key {request_id,email,sentAt,lang,v:1}", sorted(rk) == ["email", "lang", "request_id", "sentAt", "v"] and rk["v"] == 1 and rk["lang"] == "he", rk)
        t = pg.inner_text("#rqApp")
        check("code screen texts", "בדקו את המייל" in t and "הקוד בתוקף 10 דקות" in t and "שליחה חוזרת בעוד 1:00" in t or "שליחה חוזרת בעוד 0:5" in t, t)
        check("email LTR", pg.get_attribute("#rqCodeEmail", "dir") == "ltr" and pg.evaluate("()=>getComputedStyle(document.querySelector('.rq-otp-row')).direction") == "ltr")
        check("first box autocomplete=one-time-code, inputmode numeric", pg.get_attribute("#rqOtp0", "autocomplete") == "one-time-code" and pg.get_attribute("#rqOtp3", "inputmode") == "numeric")
        layout(d, "code he")
        shot(d, "f21_code_he")
        # reload → resume, no send
        n_start = d.fake.n("start")
        go(d)
        check("reload within 10 min → code screen, banner, no send", screen(d) == "code" and pg.query_selector("#rqResumed") is not None and d.fake.n("start") == n_start and d.fake.n("resend") == 0)
        check("banner text", "חזרת לדף – הקוד ששלחנו לפני דקה עדיין תקף." in pg.inner_text("#rqResumed"), pg.inner_text("#rqResumed"))
        shot(d, "f21_code_resumed_he")
        # wrong code
        type_code(d, "111111")
        pg.wait_for_function("()=>!rqCodeErr.hidden")
        check("code_wrong → red boxes + attempts left", "נשארו 4 ניסיונות" in pg.inner_text("#rqCodeErr") and pg.evaluate("()=>rqOtpRow.classList.contains('bad')"), pg.inner_text("#rqCodeErr"))
        shot(d, "f21_code_wrong_he")
        # paste with spaces fills all
        pg.evaluate("""()=>{const dt=new DataTransfer();dt.setData('text','123 456');rqOtp2.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))}""")
        pg.wait_for_function("()=>rqApp.dataset.screen==='sent'")
        check("paste '123 456' fills all + verifies → sent", d.fake.calls[-1] == {"action": "verify", "request_id": rk["request_id"], "code": GOOD}, d.fake.calls[-1])
        check("resume key cleared on success", ls(d, RESUME_KEY) is None)
        t = pg.inner_text("#rqApp")
        check("sent screen (resumed: only the email is known)", "הבקשה נשלחה" in t and "dana@example.com" in t and "מה עכשיו?" in t, t)
        go(d)
        check("reload after success → form", screen(d) == "form")
        d.ctx.close()

        # full summary when the form is in memory; English
        d = device(locale="en-US")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d, travellers=5)
        pg.click("#rqUnsure")
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        b = d.fake.calls[-1]
        check("unsure → month null; lang en", b["month"] is None and b["lang"] == "en" and b["travellers"] == 5 and b["note"] is None, b)
        layout(d, "code en")
        shot(d, "f21_code_en")
        check("resend disabled during cooldown", not pg.is_enabled("#rqResend") and "Resend in" in pg.inner_text("#rqResend"))
        type_code(d, GOOD)
        pg.wait_for_function("()=>rqApp.dataset.screen==='sent'")
        t = pg.inner_text("#rqApp")
        check("sent summary (en): flags+names, not sure, travellers, email", "Japan" in t and "South Korea" in t and "Not sure yet" in t and "5" in t and "dana@example.com" in t, t)
        layout(d, "sent en")
        shot(d, "f21_sent_en")
        d.page.click("#rqLangHe")
        check("sent re-renders in he", "הבקשה נשלחה" in pg.inner_text("#rqApp") and "יפן" in pg.inner_text("#rqApp"))
        layout(d, "sent he")
        shot(d, "f21_sent_he")
        d.ctx.close()

        # cooldown continues from the stored sentAt after a reload; resend
        d = device(locale="en-US")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        pg.evaluate("()=>{const o=JSON.parse(localStorage.getItem('pt:_device:rq_resume'));o.sentAt-=61000;localStorage.setItem('pt:_device:rq_resume',JSON.stringify(o))}")
        go(d)
        pg.wait_for_function("()=>!rqResend.disabled")
        check("cooldown continues from stored sentAt", pg.inner_text("#rqResend") == "Resend code")
        pg.click("#rqResend")
        pg.wait_for_function("()=>rqResend.disabled&&rqResend.innerText.indexOf('Resend in')===0")
        check("resend → call + new cooldown + key refreshed", d.fake.n("resend") == 1 and json.loads(ls(d, RESUME_KEY))["sentAt"] > time.time() * 1000 - 5000)
        check("resend sends only the request id", d.fake.calls[-1] == {"action": "resend", "request_id": json.loads(ls(d, RESUME_KEY))["request_id"]}, d.fake.calls[-1])
        d.ctx.close()

        # month label on sent (he)
        d = device(locale="he-IL")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d, month_idx=1)
        lbl = pg.evaluate("()=>rqWhen.options[rqWhen.selectedIndex].text")
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        type_code(d, GOOD)
        pg.wait_for_function("()=>rqApp.dataset.screen==='sent'")
        check("sent 'מתי' = month label", pg.inner_text("#rqSumWhen") == lbl, (pg.inner_text("#rqSumWhen"), lbl))
        d.ctx.close()

        # ------------------------------------------------------------ 6 errors, fix email, lock, TTL
        print("errors / resume clears (AC 6, 7):")
        d = device(locale="he-IL")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        pg.click("#rqFix")
        check("'תיקון המייל' → form with values, key gone", screen(d) == "form" and pg.input_value("#rqEmail") == "dana@example.com"
              and pg.input_value("#rqName") == "Dana Cohen" and ls(d, RESUME_KEY) is None)
        ts_ready(d)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        for i in range(5):
            type_code(d, "00000%d" % i)
            time.sleep(0.25)
        pg.wait_for_function("()=>rqApp.dataset.screen==='form'")
        check("5 wrong → code_locked → form with values + toast, key gone", pg.input_value("#rqName") == "Dana Cohen" and "יותר מדי ניסיונות" in pg.inner_text("#rqToast") and ls(d, RESUME_KEY) is None)
        ts_ready(d)
        d.fake.mode["verify"] = {"ok": False, "code": "code_expired"}
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        type_code(d, GOOD)
        pg.wait_for_function("()=>!rqCodeErr.hidden")
        check("code_expired → message + resend enabled", "הקוד פג. שלחו קוד חדש." in pg.inner_text("#rqCodeErr") and pg.is_enabled("#rqResend"))
        d.fake.mode["resend"] = {"ok": False, "code": "daily_limit"}
        pg.click("#rqResend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='limit'")
        check("resend → daily_limit → 1.4", "נסו שוב מחר" in pg.inner_text("#rqApp"))
        d.ctx.close()
        # TTL
        d = device(locale="he-IL")
        pg = d.page
        go(d)
        pg.evaluate("k=>localStorage.setItem(k,JSON.stringify({request_id:'abc',email:'a@b.co',sentAt:Date.now()-601000,lang:'he',v:1}))", RESUME_KEY)
        go(d)
        check("TTL passed → form, key gone, no call", screen(d) == "form" and ls(d, RESUME_KEY) is None and not d.fake.calls)
        pg.evaluate("k=>localStorage.setItem(k,'{bad json')", RESUME_KEY)
        go(d)
        check("corrupt key → form", screen(d) == "form" and ls(d, RESUME_KEY) is None)
        pg.evaluate("k=>localStorage.setItem(k,JSON.stringify({request_id:'abc',email:'a@b.co',sentAt:Date.now()-120000,lang:'en',v:1}))", RESUME_KEY)
        go(d)
        check("resume restores the request language", screen(d) == "code" and d.page.evaluate("()=>document.documentElement.lang") == "en"
              and "2 minutes ago" in pg.inner_text("#rqResumed"))
        type_code(d, GOOD)
        pg.wait_for_function("()=>rqApp.dataset.screen==='form'")
        check("request_unknown → form + toast, key gone", ls(d, RESUME_KEY) is None and "start again" in pg.inner_text("#rqToast"))
        d.ctx.close()

        # ------------------------------------------------------------ 7 start error mapping (AC 5, 8, 9, 19)
        print("start errors (AC 5, 8, 9, 19):")
        for lang, loc in (("he", "he-IL"), ("en", "en-US")):
            d = device(locale=loc)
            pg = d.page
            go(d)
            ts_ready(d)
            fill_form(d)
            d.fake.mode["start"] = {"ok": False, "code": "daily_limit"}
            pg.click("#rqSend")
            pg.wait_for_function("()=>rqApp.dataset.screen==='limit'")
            t = pg.inner_text("#rqApp")
            check("daily_limit → 1.4 [%s]" % lang, ("נסו שוב מחר" in t and "בקשה שכבר שלחתם" in t) if lang == "he" else ("Please try again tomorrow" in t and "isn't affected" in t), t)
            layout(d, "limit " + lang)
            shot(d, "f21_limit_" + lang)
            pg.click("#rqBack")
            check("'back to the form' keeps values [%s]" % lang, screen(d) == "form" and pg.input_value("#rqName") == "Dana Cohen" and len(pg.query_selector_all("#rqChips .rq-chip")) == 2)
            check("no resume key after daily_limit", ls(d, RESUME_KEY) is None)
            d.ctx.close()
        d = device(locale="he-IL")
        pg = d.page
        go(d)
        check("1.4 never on page load", screen(d) == "form" and not d.fake.calls)
        ts_ready(d)
        fill_form(d)
        d.fake.mode["start"] = {"ok": False, "code": "rate_limited"}
        pg.click("#rqSend")
        pg.wait_for_function("()=>!rqToast.hidden")
        check("rate_limited → toast", pg.inner_text("#rqToast") == "יותר מדי בקשות היום. נסו שוב מחר.", pg.inner_text("#rqToast"))
        d.fake.mode["start"] = {"ok": False, "code": "turnstile_failed"}
        r0 = pg.evaluate("()=>window.__ts.resets")
        ts_ready(d)
        pg.click("#rqSend")
        pg.wait_for_function("r=>window.__ts.resets>r", arg=r0)
        check("turnstile_failed → toast + widget reset", "בדיקת האבטחה נכשלה" in pg.inner_text("#rqToast"))
        d.fake.mode["start"] = {"ok": False, "code": "invalid_request", "field": "email"}
        time.sleep(0.15)
        pg.click("#rqSend")
        pg.wait_for_selector("#rqEmailErr")
        check("invalid_request{field:email} → inline", pg.query_selector("#rqEmailErr") is not None)
        d.fake.mode["start"] = {"ok": False, "code": "email_failed"}
        time.sleep(0.15)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqToast.innerText==='משהו השתבש. נסו שוב.'")
        check("other → generic toast", True)
        n0 = len(d.fake.calls)
        d.ctx.set_offline(True)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqToast.innerText.indexOf('אין חיבור')===0")
        check("offline → toast, values kept, no call", pg.input_value("#rqName") == "Dana Cohen" and len(d.fake.calls) == n0 and screen(d) == "form")
        d.ctx.set_offline(False)
        d.ctx.close()
        # always-fail site key: widget blocks → no token → inline, no call
        d = device(locale="en-US", key=FAIL_KEY)
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d)
        pg.click("#rqSend")
        check("always-fail test key → no token → inline, no call", pg.query_selector("#rqTsErr") is not None and not d.fake.calls)
        d.ctx.close()
        # C4: same success shape regardless (client handles any ok:true with request_id)
        print("storage blocked:")
        d = device(locale="he-IL")
        d.ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
        pg = d.page
        go(d)
        ts_ready(d)
        fill_form(d)
        pg.click("#rqSend")
        pg.wait_for_function("()=>rqApp.dataset.screen==='code'")
        type_code(d, GOOD)
        pg.wait_for_function("()=>rqApp.dataset.screen==='sent'")
        check("localStorage throwing → flow still works", True)
        d.ctx.close()
        br.close()

    print("\n%d/%d checks passed" % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
