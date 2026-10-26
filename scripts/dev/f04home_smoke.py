# CHANGE 2026-10-26 F04H-DEVSMOKE-01: new file (no previous version). Dev smoke test for F04-HOME (not the QA suite), no
#   network: reuses the QA browser harness chain (tests/f06/harness.py → F05 → F20 → F04 → F03 → F02: GitHub-Pages-like
#   server, in-memory Supabase with email OTP, create-trip, invite-manager) and walks the F04-HOME flows in Chromium at 390px:
#   gate card order/texts, code-screen resume (gate + invite origins, TTL, no re-send, key contents), C3 boot into the trip,
#   the done-screen install card (desktop / iPhone / standalone / captured beforeinstallprompt), the /invite/ variants
#   (in-app iPhone + Android, iPhone Safari, Android Chrome, desktop, ?t= arrival, invalid token) and flag 'off' sanity.
# usage: python3 scripts/dev/f04home_smoke.py            (F04H_SHOTS=<dir> also saves screenshots)
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("f06_harness", str(ROOT / "tests" / "f06" / "harness.py"))
h6 = importlib.util.module_from_spec(_spec)
sys.modules["f06_harness"] = h6
_spec.loader.exec_module(h6)
f05, f04, f02 = h6.f05, h6.f04, h6.f02

from playwright.sync_api import sync_playwright  # noqa: E402

APP, INVITE = h6.APP, h6.ROOT + "invite/"
EMAIL, MGR_EMAIL, DRAFT = "dana@example.com", "mgr@example.com", "יפן 2027"
RESUME_KEY = "pt:_device:wz_resume"
GMAIL_IOS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                "GSA/330.0.661587829 Mobile/15E148")
GMAIL_ANDROID_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                    "Chrome/126.0.0.0 Mobile Safari/537.36")
FLAG_RE = re.compile(r"""(const\s+HOME_INSTALL_FEATURE\s*=\s*)(['"])(on|off)\2""")
BIP_JS = r"""(()=>{window.__qaBip={prompted:0};setTimeout(()=>{const e=new Event('beforeinstallprompt');
 e.prompt=()=>{window.__qaBip.prompted++;return Promise.resolve()};e.userChoice=Promise.resolve({outcome:'accepted'});
 window.dispatchEvent(e)},50)})();"""

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:300]))


class SEnv(h6.Env):
    """F06 env + the F04 invite-manager / create-trip routes (the F05/F06 route handlers do not serve them)."""

    def _route5(self, dev, route, request):
        base = request.url.split("#")[0].split("?")[0].rstrip("/")
        if base in (f04.IM_URL, f04.CT_URL):
            return f04.Env._route4(self, dev, route, request)
        return super()._route5(dev, route, request)


def serve_off(env):
    for path, f in ((APP, ROOT / "app" / "index.html"), (INVITE, ROOT / "invite" / "index.html")):
        src = f.read_text(encoding="utf-8")
        assert FLAG_RE.search(src), "flag missing in %s" % f
        b = FLAG_RE.sub(lambda m: m.group(1) + "'off'", src, count=1).encode("utf-8")
        env.server.overrides[path] = b
        env.server.overrides[path + "index.html"] = b


def ls(dev):
    return h6.ls_page(dev)


def n_sends(be, devname):
    n = len([t for t in be.traces if t["device"] == devname and t["kind"] in ("auth.updateUser", "auth.signInWithOtp")])
    return n


def wizard_screen(page):
    return page.evaluate("()=>{const w=document.getElementById('ptWizard');return w?w.getAttribute('data-screen'):null}")


def wait_wizard(page, want, timeout=15):
    want = (want,) if isinstance(want, str) else tuple(want)
    end = time.time() + timeout
    s = None
    while time.time() < end:
        try:
            s = wizard_screen(page)
        except Exception:
            s = None
        if s in want:
            page.wait_for_timeout(250)
            return s
        page.wait_for_timeout(150)
    return s


def hscroll(page):
    return page.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1")


def small_targets(page, scope):
    return page.evaluate("""(s)=>{const r=document.querySelector(s);if(!r)return['no scope '+s];const out=[];
     r.querySelectorAll('button,a[href],input').forEach(e=>{const b=e.getBoundingClientRect();if(b.width===0&&b.height===0)return;
      if(e.offsetParent===null&&getComputedStyle(e).position!=='fixed')return;
      if(b.height<44&&!e.classList.contains('pt-otp'))out.push((e.id||e.tagName)+':'+Math.round(b.height))});return out}""", scope)


def gate_to_email(dev):
    page = dev.page
    st = dev.goto(APP)
    assert st == "nc", "not the gate: %s" % st
    page.locator("#ptGateInviteBtn").click()
    return wait_wizard(page, "email")


def send_email(page, email):
    page.locator("#ptWzEmail").fill(email)
    page.locator("#ptWzSend").click()
    return wait_wizard(page, "code")


def main():
    shots = os.environ.get("F04H_SHOTS")

    def shot(page, name):
        if shots:
            page.screenshot(path=os.path.join(shots, name + ".png"), full_page=True)

    srv = f05.F05Server()
    with sync_playwright() as p:
        br = p.chromium.launch()

        def fresh():
            srv.reset()
            return SEnv(br, srv)

        # ---------------------------------------------------------------- 1 gate (C1)
        print("gate (§1.3, AC 7):")
        env = fresh()
        dev = env.new_device("G")
        st = dev.goto(APP)
        page = dev.page
        order = page.evaluate("()=>[...document.getElementById('ptGate').children].map(e=>e.id||e.className)")
        check("gate first card = #ptGateInvite", order and order[0] == "ptGateInvite", order)
        check("F05 transfer second, device-code card last", order[1] == "ptF05Transfer" and "pt-gate-card" in order[-1], order)
        t = page.locator("#ptGateInvite").inner_text()
        check("card texts", all(x in t for x in ("מנהל/ת טיול", "חדש", "כניסה עם המייל",
                                                 "קיבלת הזמנה במייל, או שכבר הקמת טיול בדפדפן? נשלח קוד למייל שלך, ותמשיך/י בדיוק מאיפה שעצרת.")), t)
        top = page.evaluate("()=>{const g=document.getElementById('ptGate');return [g.scrollTop,document.getElementById('ptGateInvite').getBoundingClientRect().top]}")
        check("card visible at the top (not pushed off)", top[1] >= 0, top)
        check("390px: no horizontal scroll / touch ≥44", not hscroll(page) and not small_targets(page, "#ptGate"), small_targets(page, "#ptGate"))
        shot(page, "gate")
        page.locator("#ptGateInviteBtn").click()
        check("button opens the email step", wait_wizard(page, "email") == "email")
        check("email step title 'כניסה עם המייל'", page.locator("#ptWzTitle").inner_text().strip() == "כניסה עם המייל")
        check("no page errors", not h6.page_errors(dev), h6.page_errors(dev))
        env.close()

        # ---------------------------------------------------------------- 2 resume, gate origin (AC 9)
        print("code-screen resume, gate origin (§3.3, AC 9):")
        env = fresh()
        be = env.backend
        be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
        dev = env.new_device("R")
        page = dev.page
        gate_to_email(dev)
        check("code screen after send", send_email(page, EMAIL) == "code")
        page.wait_for_timeout(500)
        n1 = n_sends(be, "R")
        check("one send", n1 == 1, n1)
        check("'איפה הקוד?' card", page.locator("#ptWzWhere").count() == 1 and "רואים את הקוד בלי לצאת מהדף" in page.locator("#ptWzWhere").inner_text())
        check("no resume banner on a fresh send", page.locator("#ptWzResume").count() == 0)
        raw = ls(dev).get(RESUME_KEY)
        j = json.loads(raw or "{}")
        check("resume key written {email,sentAt,kind,origin,v}", j.get("email") == EMAIL and j.get("origin") == "gate" and j.get("v") == 1
              and j.get("kind") in ("change", "signin") and isinstance(j.get("sentAt"), (int, float)), raw)
        check("key has no code digits / no token", be.otp_code not in raw and not re.search(r"[A-Za-z0-9_-]{43}", raw), raw)
        shot(page, "code")
        page.clock.run_for(20000)
        page.reload(wait_until="domcontentloaded")
        st = f02.wait_ready(page)
        check("reload → gate", st == "nc", st)
        page.locator("#ptGateInviteBtn").click()
        check("'כניסה עם המייל' → code screen (resumed)", wait_wizard(page, "code") == "code", wizard_screen(page))
        page.wait_for_timeout(600)
        check("same email", page.locator("#ptWzCodeEmail").input_value() == EMAIL)
        bt = page.locator("#ptWzResume").inner_text() if page.locator("#ptWzResume").count() else ""
        check("banner text + role=status", "חזרת לדף – הקוד ששלחנו לפני" in bt and "עדיין תקף. לא נשלח קוד חדש." in bt
              and page.locator("#ptWzResume").get_attribute("role") == "status", bt)
        check("no second send", n_sends(be, "R") == n1, n_sends(be, "R"))
        rs = page.locator("#ptWzResend").inner_text()
        check("cooldown continues (≈25s left)", "שליחה חוזרת בעוד 0:2" in rs or "שליחה חוזרת בעוד 0:1" in rs, rs)
        dev.offline(True)
        page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
        page.wait_for_timeout(300)
        check("offline: banner hidden", page.locator("#ptWzResume").is_hidden())
        dev.offline(False)
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
        page.wait_for_timeout(300)
        check("390px code screen: no h-scroll", not hscroll(page))
        shot(page, "code_resumed")
        f04.type_code(page, be.otp_code)
        check("code → step 1", wait_wizard(page, "step1") == "step1", wizard_screen(page))
        check("key gone after success", RESUME_KEY not in ls(dev))
        env.close()

        # "שינוי מייל" clears, TTL
        env = fresh()
        be = env.backend
        be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
        dev = env.new_device("T")
        page = dev.page
        gate_to_email(dev)
        send_email(page, EMAIL)
        page.wait_for_timeout(400)
        page.locator("#ptWzChangeEmail").click()
        page.wait_for_timeout(200)
        check("'שינוי מייל' → key gone", RESUME_KEY not in ls(dev))
        send_email(page, EMAIL)
        page.wait_for_timeout(400)
        check("send again → key back", RESUME_KEY in ls(dev))
        page.clock.run_for(11 * 60 * 1000)
        page.reload(wait_until="domcontentloaded")
        f02.wait_ready(page)
        n = n_sends(be, "T")
        page.locator("#ptGateInviteBtn").click()
        check("after 10 min → normal start (email step)", wait_wizard(page, "email") == "email", wizard_screen(page))
        check("expired key removed", RESUME_KEY not in ls(dev))
        check("no send on open", n_sends(be, "T") == n)
        env.close()

        # ---------------------------------------------------------------- 3 resume, invite origin (?invite=1)
        print("code-screen resume, invite origin (boot with ?invite=1):")
        env = fresh()
        be = env.backend
        iid, token = be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
        dev = env.new_device("I")
        page = dev.page
        dev.goto(APP + "?invite=1#invite=" + token, ready=False)
        check("token link → code screen", wait_wizard(page, "code") == "code", wizard_screen(page))
        page.wait_for_timeout(500)
        n1 = n_sends(be, "I")
        check("address bar: ?invite=1 marker, no token", page.url.endswith("/app/?invite=1") and token not in page.url, page.url)
        raw = ls(dev).get(RESUME_KEY) or ""
        check("key origin=invite, no token", '"origin":"invite"' in raw and token not in raw, raw)
        page.reload(wait_until="domcontentloaded")
        check("reload → code screen directly", wait_wizard(page, "code") == "code", wizard_screen(page))
        page.wait_for_timeout(600)
        check("banner + same email + no second send", page.locator("#ptWzResume").count() == 1 and
              page.locator("#ptWzCodeEmail").input_value() == EMAIL and n_sends(be, "I") == n1, (n_sends(be, "I"), n1))
        check("no page errors", not h6.page_errors(dev), h6.page_errors(dev))
        env.close()

        # ---------------------------------------------------------------- 4 C3 (AC 8)
        print("C3 — verified manager, used invite (AC 8):")
        env = fresh()
        be = env.backend
        uid = be.add_account(MGR_EMAIL)
        tid, _ = be.trip("יוון 2027", managers=())
        be.add_member(tid, uid, "manager", "active", "אור")
        be.add_invite(MGR_EMAIL, DRAFT, sent_days_ago=3, expires_in_days=4, used=True)
        dev = env.new_device("C")
        page = dev.page
        gate_to_email(dev)
        send_email(page, MGR_EMAIL)
        page.wait_for_timeout(400)
        f04.type_code(page, be.otp_code)
        ok = h6.wait_until(lambda: h6.running_trip(page) == tid, 25, page)
        check("after the code the trip opens without restart", ok, (h6.running_trip(page), wizard_screen(page), f04.btext(page)[:120]))
        check("key gone", RESUME_KEY not in ls(dev))
        env.close()
        env = fresh()
        be = env.backend
        be.add_account("nobody@example.com")
        dev = env.new_device("D")
        page = dev.page
        gate_to_email(dev)
        send_email(page, "nobody@example.com")
        page.wait_for_timeout(400)
        f04.type_code(page, be.otp_code)
        check("no trips → 'לא מצאנו הזמנה פעילה'", wait_wizard(page, "card:noinvite") == "card:noinvite", wizard_screen(page))
        env.close()

        # ---------------------------------------------------------------- 5 done screen (AC 10)
        print("'הטיול נוצר' install card (AC 10):")

        def to_done(env, name, **kw):
            be = env.backend
            iid, token = be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
            dev = env.new_device(name, **kw)
            page = dev.page
            dev.goto(APP + "?invite=1#invite=" + token, ready=False)
            wait_wizard(page, "code")
            page.wait_for_timeout(400)
            f04.type_code(page, be.otp_code)
            wait_wizard(page, "step1")
            f04.fill_step1(page, me="דנה", start="2027-04-03", end="2027-04-10")
            f04.press_next(page)
            wait_wizard(page, "step2")
            f04.pick(page, "יפ", "JP")
            f04.press_next(page)
            wait_wizard(page, "step3")
            page.locator("#ptWzCreate").click()
            return dev, wait_wizard(page, "done")

        env = fresh()
        dev, st = to_done(env, "W")
        page = dev.page
        check("done reached (desktop browser tab)", st == "done", st)
        check("install card above the join card", page.evaluate(
            "()=>{const a=document.getElementById('ptWzInstall'),b=document.getElementById('ptWzLinkCard');return !!a&&!!b&&!!(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING)}"))
        it = page.locator("#ptWzInstall").inner_text()
        check("title + manual hint (no captured event)", "מוסיפים את האפליקציה למסך הבית" in it and "התקנת אפליקציה" in it, it)
        eb = page.locator("#ptWzEnter")
        check("bottom button 'אחר כך – כניסה לטיול כאן' outline", eb.inner_text().strip() == "אחר כך – כניסה לטיול כאן"
              and "pt-out" in (eb.get_attribute("class") or ""))
        check("390px done: no h-scroll, touch ≥44", not hscroll(page) and not small_targets(page, "#ptWizard"), small_targets(page, "#ptWizard"))
        shot(page, "done_desktop")
        eb.click()
        check("enter → trip", h6.wait_until(lambda: h6.running_trip(page), 20, page))
        env.close()

        env = fresh()
        dev, st = to_done(env, "S", ua=f05.IPHONE_UA, standalone=False)
        page = dev.page
        it = page.locator("#ptWzInstall").inner_text() if page.locator("#ptWzInstall").count() else ""
        check("iPhone: 3 ticks with the verified email", "כניסה עם המייל" in it and EMAIL in it and
              page.locator("#ptWzInstall .pt-f04h-tick").count() == 3, it)
        check("iPhone: email LTR", page.evaluate("()=>{const b=document.querySelector('#ptWzInstall bdi');return b&&getComputedStyle(b).direction}") == "ltr")
        shot(page, "done_iphone")
        env.close()

        env = fresh()
        dev, st = to_done(env, "P", standalone=True)
        page = dev.page
        check("standalone: no card, bottom button unchanged", page.locator("#ptWzInstall").count() == 0 and
              page.locator("#ptWzEnter").inner_text().strip() == "כניסה לטיול ←")
        env.close()

        env = fresh()
        orig_new = env.new_device

        def new_with_bip(name, **kw):
            d = orig_new(name, **kw)
            d.ctx.add_init_script(BIP_JS)
            return d
        env.new_device = new_with_bip
        dev, st = to_done(env, "B", ua=f05.ANDROID_UA)
        page = dev.page
        btn = page.locator("#ptWzInstallBtn")
        check("Android + captured beforeinstallprompt: 'התקנת האפליקציה'", btn.count() == 1 and btn.inner_text().strip() == "התקנת האפליקציה")
        if btn.count():
            btn.click()
            page.wait_for_timeout(300)
            check("prompt() called", page.evaluate("()=>window.__qaBip.prompted") == 1)
            page.evaluate("()=>window.dispatchEvent(new Event('appinstalled'))")
            page.wait_for_timeout(200)
            check("appinstalled → 'האפליקציה הותקנה…'", "האפליקציה הותקנה – אפשר לפתוח אותה ממסך הבית" in page.locator("#ptWzInstall").inner_text())
        env.close()

        # ---------------------------------------------------------------- 6 /invite/ (AC 2–6)
        print("/invite/ (AC 2–6):")

        def inv_dev(env, name, ua=None, standalone=None):
            d = env.new_device(name, ua=ua, standalone=standalone)
            d.reqnav = []
            cdp = d.ctx.new_cdp_session(d.page)
            cdp.send("Page.enable")
            cdp.on("Page.frameRequestedNavigation", lambda ev, _d=d: _d.reqnav.append(ev.get("url")))
            return d

        env = fresh()
        be = env.backend
        _, token = be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
        d = inv_dev(env, "IG", GMAIL_IOS_UA)
        d.page.goto(srv.origin + INVITE + "#invite=" + token, wait_until="domcontentloaded")
        ok = h6.wait_has(d.page, "פותחים בדפדפן הרגיל", 8)
        check("Gmail iOS → 1.1 in-app card", ok, f04.btext(d.page)[:200])
        t = f04.btext(d.page)
        check("1.1 texts", all(x in t for x in ("פתיחה בספארי", "הכפתור לא עבד?", "ההזמנה עצמה בתוקף. אם הדף נסגר - לוחצים שוב על הכפתור במייל."))
              , t)
        d.page.wait_for_timeout(500)
        check("no automatic navigation on iPhone", not d.reqnav, d.reqnav)
        check("390px: no h-scroll, touch ≥44", not hscroll(d.page) and not small_targets(d.page, "main"), small_targets(d.page, "main"))
        shot(d.page, "invite_inapp_ios")
        d.page.locator("#hSafari").click()
        d.page.wait_for_timeout(500)
        want = "x-safari-https://127.0.0.1:%d%s#invite=%s" % (srv.port, INVITE, token)
        check("'פתיחה בספארי' → x-safari-https://…#invite=<token>", want in d.reqnav, d.reqnav)
        check("address bar clean", "#invite" not in d.page.url, d.page.url)

        d = inv_dev(env, "IA", GMAIL_ANDROID_UA)
        d.page.goto(srv.origin + INVITE + "#invite=" + token, wait_until="domcontentloaded")
        h6.wait_has(d.page, "פותחים בדפדפן הרגיל", 8)
        d.page.wait_for_timeout(800)
        intents = [u for u in d.reqnav if u.startswith("intent://")]
        want = "intent://127.0.0.1:%d%s?t=%s#Intent;scheme=https;package=com.android.chrome;end" % (srv.port, INVITE, token)
        check("Android WebView → one automatic intent:// hop", intents == [want], d.reqnav)
        check("fallback button 'לא נפתח? פתיחה ב-Chrome'", d.page.locator("#hChrome").inner_text().strip() == "לא נפתח? פתיחה ב-Chrome")
        shot(d.page, "invite_inapp_android")

        d = inv_dev(env, "IT", f05.ANDROID_UA)
        d.page.goto(srv.origin + INVITE + "?t=" + token, wait_until="domcontentloaded")
        ok = h6.wait_has(d.page, "בסוף ההקמה תוכלו להתקין את האפליקציה", 8)
        check("arriving with ?t= works like #invite= (Android Chrome → C2 line)", ok, f04.btext(d.page)[:200])
        check("?t= gone from the address bar", "?t=" not in d.page.url and token not in d.page.url, d.page.url)
        check("Android: no install card, today's button", "קודם מוסיפים" not in f04.btext(d.page) and d.page.locator("#open").count() == 1)
        check("Android: no hop in real Chrome", not d.reqnav, d.reqnav)
        shot(d.page, "invite_android")

        d = inv_dev(env, "IS", f05.IPHONE_UA, standalone=False)
        d.page.goto(srv.origin + INVITE + "#invite=" + token, wait_until="domcontentloaded")
        ok = h6.wait_has(d.page, "קודם מוסיפים את האפליקציה למסך הבית", 8)
        check("iPhone Safari → install card", ok, f04.btext(d.page)[:200])
        t = f04.btext(d.page)
        check("3 steps + info + small line", d.page.locator(".steps.go .step").count() == 3 and
              "הקוד מופיע בכותרת המייל - רואים אותו בהתראה." in t and "לא רואים 'הוספה למסך הבית'? פותחים את הדף בספארי" in t, t)
        href = d.page.locator("#hSkip").get_attribute("href")
        check("'להמשיך בדפדפן בלי להתקין' = today's link", href == "../app/?invite=1#invite=" + token, href)
        check("390px: no h-scroll, touch ≥44", not hscroll(d.page) and not small_targets(d.page, "main"), small_targets(d.page, "main"))
        shot(d.page, "invite_ios")
        d.page.locator("#hAdded").click()
        d.page.wait_for_timeout(200)
        check("'הוספתי – מה עכשיו?' opens the sheet", d.page.locator("#hLayer").is_visible())
        shot(d.page, "invite_ios_sheet")
        d.page.locator("#hSheetOk").click()
        check("sheet closes", d.page.locator("#hLayer").is_hidden())
        d.page.locator("#hSkip").click()
        check("skip → the wizard as today", wait_wizard(d.page, "code") == "code", wizard_screen(d.page))

        d = inv_dev(env, "ID")
        d.page.goto(srv.origin + INVITE + "#invite=" + token, wait_until="domcontentloaded")
        h6.wait_has(d.page, "ההזמנה שלך אומתה", 8)
        t = f04.btext(d.page)
        check("desktop: today's page + note names 'כניסה עם המייל'", "ההקמה לוקחת כ-3 דקות." in t and 'ולבחור "כניסה עם המייל"' in t
              and "קודם מוסיפים" not in t, t)

        d = inv_dev(env, "IX", GMAIL_ANDROID_UA)
        d.page.goto(srv.origin + INVITE + "#invite=" + "Z" * 43, wait_until="domcontentloaded")
        h6.wait_has(d.page, "הקישור כבר לא בתוקף", 8)
        d.page.wait_for_timeout(600)
        check("invalid token in-app: invalid card, no hop", not d.reqnav and "פותחים בדפדפן" not in f04.btext(d.page), d.reqnav)
        env.close()

        # ---------------------------------------------------------------- 7 flag off (AC 1 sanity)
        print("HOME_INSTALL_FEATURE='off' (AC 1 sanity):")
        env = fresh()
        serve_off(env)
        be = env.backend
        _, token = be.add_invite(EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
        dev = env.new_device("O")
        page = dev.page
        dev.goto(APP)
        t = page.locator("#ptGateInvite").inner_text()
        order = page.evaluate("()=>[...document.getElementById('ptGate').children].map(e=>e.id||e.className)")
        check("gate: alpha.7 card + order", "קיבלת הזמנה לנהל טיול?" in t and "כניסה עם הזמנה" in t and order[0] == "ptF05Transfer", order)
        page.locator("#ptGateInviteBtn").click()
        wait_wizard(page, "email")
        check("email title alpha.7", page.locator("#ptWzTitle").inner_text().strip() == "כניסה עם הזמנה")
        send_email(page, EMAIL)
        page.wait_for_timeout(400)
        check("no resume key, no 'איפה הקוד?' card", RESUME_KEY not in ls(dev) and page.locator("#ptWzWhere").count() == 0)
        d = inv_dev(env, "OG", GMAIL_IOS_UA)
        d.page.goto(srv.origin + INVITE + "#invite=" + token, wait_until="domcontentloaded")
        h6.wait_has(d.page, "ההזמנה שלך אומתה", 8)
        t = f04.btext(d.page)
        check("/invite/ in-app UA: alpha.7 page, no hop", "פותחים בדפדפן" not in t and 'ולבחור "כניסה עם הזמנה"' in t and not d.reqnav, t[:200])
        d = inv_dev(env, "OT", f05.ANDROID_UA)
        d.page.goto(srv.origin + INVITE + "?t=" + token, wait_until="domcontentloaded")
        h6.wait_has(d.page, "הקישור כבר לא בתוקף", 8)
        check("/invite/ ?t= ignored when off", "הקישור כבר לא בתוקף" in f04.btext(d.page))
        env.close()
        br.close()
    srv.stop()
    print("%d/%d ok" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
