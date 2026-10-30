# CHANGE 2026-10-27 F21-DEVSMOKE-01: new file (no previous version). Dev smoke test for the F21 app side (not the QA suite), no
#   network: reuses the QA browser harness chain (tests/f06/harness.py → F05 → F20 → F04 → F03 → F02: GitHub-Pages-like server,
#   in-memory Supabase with email OTP, invite-manager, create-trip) and extends its backend with rpc('admin_trip_requests'),
#   invite-manager `approve_request` / `reject_request` and create-trip lookup `prefill` (docs/F21_spec.md §1.6–§1.11, the
#   server contract in the brief). Chromium 390×844, REQUEST_FEATURE on and off.
# usage: python3 scripts/dev/f21_app_smoke.py        (F21_SHOTS=<dir> also saves screenshots)
import copy
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("f06_harness", str(ROOT / "tests" / "f06" / "harness.py"))
h6 = importlib.util.module_from_spec(_spec)
sys.modules["f06_harness"] = h6
_spec.loader.exec_module(h6)
f05, f04, f02, f03 = h6.f05, h6.f04, h6.f02, h6.f04.f03

from playwright.sync_api import sync_playwright  # noqa: E402

APP = h6.APP
FLAG_RE = re.compile(r"""(const\s+REQUEST_FEATURE\s*=\s*)(['"])(on|off)\2""")
DAY = f04.DAY
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:300]))


class F21Backend(h6.F06Backend):
    def __init__(self):
        super().__init__()
        self.requests = {}       # id -> row (public fields + status)
        self.mail_today = 0
        self.cap = 50
        self.req_fail = False

    def add_request(self, name, email, countries, month=None, travellers=2, note=None, lang="he", hours_ago=2):
        rid = str(uuid.uuid4())
        self.requests[rid] = {"id": rid, "lang": lang, "name": name, "email": email, "countries": list(countries),
                              "month": month, "travellers": travellers, "note": note,
                              "verified_at": f04.iso(self.now - dt_hours(hours_ago)), "status": "pending"}
        return rid

    def _active_invite(self, email):
        r = self.find_invite_for_email(email)
        return {"id": r["id"], "draft_name": r["draft_name"], "last_sent_at": r["last_sent_at"], "expires_at": r["expires_at"]} if r else None

    def _manages(self, email):
        uid = self.user_by_email(email)
        if not uid:
            return []
        return [self.rows["trips"][(m["trip_id"],)]["name"] for m in self.rows["trip_members"].values()
                if m["user_id"] == uid and m["status"] == "active" and m["role"] == "manager"]

    def rpc(self, token, fn, args):
        if fn != "admin_trip_requests":
            return super().rpc(token, fn, args)
        uid = self.tokens.get(token) if token else None
        self.rpc_calls.append({"fn": fn, "uid": uid})
        if self.req_fail:
            return {"error": {"code": "57014", "message": "canceling statement due to statement timeout"}, "status": 500}
        if not self.is_admin(uid):
            return {"error": {"code": "42501", "message": "not_platform_admin"}, "status": 403}
        out = []
        for r in self.requests.values():
            if r["status"] != "pending":
                continue
            x = {k: copy.deepcopy(r[k]) for k in ("id", "lang", "name", "email", "countries", "month", "travellers", "note", "verified_at")}
            x["manages"] = self._manages(r["email"])
            x["active_invite"] = self._active_invite(r["email"])
            out.append(x)
        out.sort(key=lambda x: x["verified_at"], reverse=True)   # the client must sort (oldest first)
        return {"data": {"cap": self.cap, "mail_today": self.mail_today, "requests": out}, "status": 200}

    def _invite_manager(self, bearer, body):
        action = body.get("action")
        if action not in ("approve_request", "reject_request"):
            return super()._invite_manager(bearer, body)
        uid = self.tokens.get(bearer) if bearer else None
        if not self.is_admin(uid):
            return 403, {"error": "not_platform_admin"}
        r = self.requests.get(str(body.get("request_id")))
        if not r or r["status"] != "pending":
            return 409, {"ok": False, "code": "request_closed", "error": "request_closed"}
        if action == "approve_request":
            if self.email_fail:
                return 502, {"ok": False, "code": "email_failed", "error": "email_failed"}
            old = self.find_invite_for_email(r["email"])
            if old:
                old["revoked_at"] = f04.iso(self.now)
            iid, _tok = self.add_invite(r["email"], str(body.get("draft_name") or "")[:80] or None, sent_days_ago=0, expires_in_days=7)
            inv = self.invites[iid]
            inv["prefill"] = {"name": r["name"], "countries": r["countries"], "month": r["month"], "lang": r["lang"]}
            inv["lang"] = r["lang"]
            r.update(status="approved", invite_id=iid)
            return 200, {"ok": True, "invite_id": iid, "expires_at": inv["expires_at"], "revoked_invite_id": old["id"] if old else None}
        r["status"] = "rejected"
        if body.get("send_mail") is True:
            if self.mail_today >= self.cap:
                return 200, {"ok": True, "mail_skipped": "daily_limit"}
            self.mail_today += 1
        return 200, {"ok": True}

    def _create_trip(self, bearer, body):
        status, resp = super()._create_trip(bearer, body)
        if body.get("action") == "lookup" and isinstance(resp, dict) and resp.get("found"):
            uid = self.tokens.get(bearer)
            r = self.find_invite_for_email((self.users.get(uid) or {}).get("email"))
            if r and r.get("prefill"):
                resp = dict(resp, prefill=copy.deepcopy(r["prefill"]))
        return status, resp

    def fn_actions(self, action):
        return [c for c in self.fn_calls if c["action"] == action]

    def req_rpcs(self):
        return [c for c in self.rpc_calls if c["fn"] == "admin_trip_requests"]


def dt_hours(h):
    return DAY * (h / 24.0)


class SEnv(h6.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = F21Backend()

    def _route5(self, dev, route, request):
        base = request.url.split("#")[0].split("?")[0].rstrip("/")
        if base in (f04.IM_URL, f04.CT_URL):
            return f04.Env._route4(self, dev, route, request)
        return super()._route5(dev, route, request)


def serve_off(env):
    src = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    assert FLAG_RE.search(src), "REQUEST_FEATURE missing"
    b = FLAG_RE.sub(lambda m: m.group(1) + "'off'", src, count=1).encode("utf-8")
    env.server.overrides[APP] = b
    env.server.overrides[APP + "index.html"] = b


def seed_admin(be, with_requests=True):
    be.auto_admin = True
    tid = be.add_trip_full("ויאטנם 2026", "2026-09-15", "2026-10-06", countries=["VN"], others=["א", "ב"])
    be.links.append({"trip_id": tid, "role": "manager", "display_name": "אור", "joined_at": "2026-09-01T10:00:00+00:00"})
    be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
    ids = {}
    if with_requests:
        ids["dana"] = be.add_request("דנה כהן", "dana@example.com", ["JP", "KR"], "2027-04-01", 5, "משפחה עם 3 ילדים, שמענו עליכם מחברים", hours_ago=2)
        ids["tom"] = be.add_request("Tom Baker", "tom@example.co.uk", ["PT"], None, 2, None, lang="en", hours_ago=26)
        be.add_invite("ron@example.com", "טיול לתאילנד", sent_days_ago=5, expires_in_days=2)
        ids["ron"] = be.add_request("רון לוי", "ron@example.com", ["TH"], "2026-12-01", 3, None, hours_ago=30)
        mgr = be.add_account("orsela.spotify+f04@gmail.com")
        t2 = be.add_trip_full("בדיקה04", "2027-01-01", "2027-01-05", countries=["IT"])
        be.add_member(t2, mgr, "manager", "active", "בדיקה4")
        ids["t4"] = be.add_request("בדיקה4", "orsela.spotify+f04@gmail.com", ["IT"], "2027-07-01", 4, None, hours_ago=72)
        be.mail_today = 12
    return ids


def to_chooser(dev):
    dev.page.goto(dev.env.server.origin + APP, wait_until="domcontentloaded")
    dev.page.wait_for_selector("#ptChoose:not([hidden])", timeout=20000)
    dev.page.wait_for_timeout(1200)


def to_admin(dev):
    dev.page.locator("#ptChooseAdmin").click()
    dev.page.wait_for_selector("#admin .pt-adm-body", timeout=10000)
    dev.page.wait_for_timeout(1200)


def hscroll(page):
    return page.evaluate("()=>{const d=document.documentElement;const a=document.getElementById('admin');return d.scrollWidth>d.clientWidth+1||(a&&a.scrollWidth>a.clientWidth+1)}")


def small_targets(page, scope):
    return page.evaluate("""(s)=>{const r=document.querySelector(s);if(!r)return['no scope '+s];const out=[];
     r.querySelectorAll('button,a[href],input,select').forEach(e=>{const b=e.getBoundingClientRect();if(b.width===0&&b.height===0)return;
      if(e.offsetParent===null&&getComputedStyle(e).position!=='fixed')return;
      if(e.type==='checkbox'){const l=e.closest('label');const lb=l&&l.getBoundingClientRect();if(lb&&lb.height>=44)return}
      if(b.height<44&&!e.classList.contains('pt-otp'))out.push((e.id||e.tagName+'.'+e.className)+':'+Math.round(b.height))});return out}""", scope)


def text(page, sel):
    loc = page.locator(sel)
    return loc.first.inner_text().strip() if loc.count() else ""


def cards(page):
    return page.evaluate("""()=>[...document.querySelectorAll('#admin [data-request]')].map(a=>({id:a.dataset.request,
      name:a.querySelector('.pt-nm').innerText,text:a.innerText,mark:a.classList.contains('pt-f21-mark'),
      btn:a.querySelector('[data-f21-approve]').innerText,dis:a.querySelector('[data-f21-approve]').disabled}))""")


def main():
    shots = os.environ.get("F21_SHOTS")
    if shots:
        os.makedirs(shots, exist_ok=True)

    def shot(page, name, tall=None):
        if not shots:
            return
        if tall:
            page.set_viewport_size({"width": 390, "height": tall})
            page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(shots, name + ".png"), full_page=True)
        if tall:
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(200)

    srv = f05.F05Server()
    with sync_playwright() as p:
        br = p.chromium.launch()

        def fresh():
            srv.reset()
            return SEnv(br, srv)

        # ------------------------------------------------------------ 1 chooser badges (§1.6)
        print("chooser (§1.6, AC 11):")
        env = fresh()
        be = env.backend
        ids = seed_admin(be)
        dev = env.new_device("A")
        page = dev.page
        to_chooser(dev)
        check("sub 'בקשות, קבוצות והזמנת מנהלים'", "בקשות, קבוצות והזמנת מנהלים" in text(page, "#ptChooseAdmin"), text(page, "#ptChooseAdmin"))
        check("badge '4 בקשות חדשות'", text(page, "#ptChooseRequests") == "4 בקשות חדשות", text(page, "#ptChooseRequests"))
        check("badge '2 הזמנות ממתינות'", text(page, "#ptChoosePending") == "2 הזמנות ממתינות", text(page, "#ptChoosePending"))
        order = page.evaluate("()=>[...document.querySelectorAll('#ptChooseAdmin .pt-f21-badges .pt-badge')].map(e=>e.id)")
        check("requests badge first, then invites", order == ["ptChooseRequests", "ptChoosePending"], order)
        check("390: no h-scroll", not hscroll(page))
        check("touch ≥44 in chooser", not small_targets(page, "#ptChoose"), small_targets(page, "#ptChoose"))
        shot(page, "01_chooser")

        # ------------------------------------------------------------ 2 requests tab (§1.7)
        print("admin requests tab (§1.7, AC 11):")
        to_admin(dev)
        check("tabs shown", page.locator("#ptReqTabs").count() == 1)
        check("default tab = requests (N>0)", page.locator("#ptReqTabReq").get_attribute("aria-pressed") == "true")
        check("tab labels 'בקשות · 4' / 'קבוצות והזמנות · 4' (2 trips + 2 pending invites)", text(page, "#ptReqTabReq") == "בקשות · 4" and text(page, "#ptReqTabGrp") == "קבוצות והזמנות · 4",
              (text(page, "#ptReqTabReq"), text(page, "#ptReqTabGrp")))
        m = text(page, "#ptReqMeter")
        check("meter '12 מתוך 50' + role=img", "12 מתוך 50" in m and page.locator("#ptReqMeter [role=img]").get_attribute("aria-label").startswith("12 מתוך 50"), m)
        cs = cards(page)
        check("4 cards, oldest first", [c["name"] for c in cs] == ["בדיקה4", "רון לוי", "Tom Baker", "דנה כהן"], [c["name"] for c in cs])
        by = {c["name"]: c for c in cs}
        enb = page.evaluate("()=>[...document.querySelectorAll('#admin [data-request] .pt-f21-en')].map(e=>e.closest('[data-request]').querySelector('.pt-nm').innerText)")
        check("EN badge only on Tom", enb == ["Tom Baker"], enb)
        check("Tom: 'עוד לא יודעים מתי · 2 מטיילים'", "עוד לא יודעים מתי · 2 מטיילים" in by["Tom Baker"]["text"])
        check("Dana: flags + names, month, travellers, note", "🇯🇵 יפן · 🇰🇷 דרום קוריאה" in by["דנה כהן"]["text"] and "אפריל 2027 · 5 מטיילים" in by["דנה כהן"]["text"]
              and '"משפחה עם 3 ילדים' in by["דנה כהן"]["text"], by["דנה כהן"]["text"])
        check("Ron marker 'יש הזמנה פעילה · נשלחה 07/10' + amber", "יש הזמנה פעילה · נשלחה 07/10" in by["רון לוי"]["text"] and by["רון לוי"]["mark"], by["רון לוי"]["text"])
        check("t4 marker 'כבר מנהל: בדיקה04' + amber", "כבר מנהל: בדיקה04" in by["בדיקה4"]["text"] and by["בדיקה4"]["mark"])
        check("Dana / Tom not amber", not by["דנה כהן"]["mark"] and not by["Tom Baker"]["mark"])
        check("button labels", [by[n]["btn"] for n in ("דנה כהן", "Tom Baker", "רון לוי", "בדיקה4")] ==
              ["אישור", "אישור · מייל באנגלית", "אישור · מחליף את ההזמנה", "אישור טיול נוסף"], [c["btn"] for c in cs])
        check("relative times", "לפני שעתיים" in by["דנה כהן"]["text"] and "אתמול" in by["Tom Baker"]["text"] and "לפני 3 ימים" in by["בדיקה4"]["text"])
        em = page.evaluate("()=>getComputedStyle(document.querySelector('#admin [data-request] .pt-l1.pt-ltr')).direction")
        check("email LTR", em == "ltr", em)
        check("footnote", "כאן מופיעות רק בקשות שהמייל שלהן אומת" in text(page, "#admin"))
        check("390: no h-scroll", not hscroll(page))
        check("touch ≥44 in admin", not small_targets(page, "#admin"), small_targets(page, "#admin"))
        check("admin_trip_requests called", len(be.req_rpcs()) >= 1)
        shot(page, "02_admin_requests", tall=1300)
        page.locator("#ptReqTabGrp").click()
        page.wait_for_timeout(300)
        check("groups tab = F03 screen (invite button + filter seg)", page.locator("#ptInviteOpen").count() == 1 and page.locator("[data-pt-filter]").count() == 4)
        check("groups tab: no request cards", page.locator("#admin [data-request]").count() == 0)
        page.locator("#ptReqTabReq").click()
        page.wait_for_timeout(300)

        # ------------------------------------------------------------ 3 approve (§1.8, §5.2)
        print("approve (§1.8, AC 12):")
        page.locator('[data-f21-approve="%s"]' % ids["dana"]).click()
        page.wait_for_selector("#ptApName", timeout=5000)
        page.wait_for_timeout(300)
        check("title 'אישור ושליחת הזמנה'", text(page, "#ptApTitle") == "אישור ושליחת הזמנה")
        check("D16 draft 'יפן ודרום קוריאה · אפריל 2027'", page.locator("#ptApName").input_value() == "יפן ודרום קוריאה · אפריל 2027", page.locator("#ptApName").input_value())
        pre = text(page, "#ptApPre")
        check("pre-fill box rows", all(s in pre for s in ("שם בקבוצה", "דנה כהן", "🇯🇵 יפן · 🇰🇷 דרום קוריאה", "אפריל 2027 (תאריכים בוחרים באשף)", "עברית – כמו הבקשה")), pre)
        check("no active-invite box", page.locator("#ptApActive").count() == 0)
        check("send label with email", " ".join(text(page, "#ptApSend").split()) == "אישור ושליחה אל dana@example.com", text(page, "#ptApSend"))
        check("sheet touch ≥44", not small_targets(page, "#ptSheet"), small_targets(page, "#ptSheet"))
        check("390: no h-scroll", not hscroll(page))
        shot(page, "03_approve")
        page.locator("#ptApName").fill("יפן וקוריאה 2027")
        page.locator("#ptApSend").click()
        check("toast 'ההזמנה נשלחה ל-dana@example.com'", f05.saw_toast(page, "ההזמנה נשלחה ל-dana@example.com"))
        page.wait_for_timeout(800)
        a = be.fn_actions("approve_request")
        check("one approve_request with the edited name", len(a) == 1 and a[0]["body"] == {"action": "approve_request", "request_id": ids["dana"], "draft_name": "יפן וקוריאה 2027"}, a and a[0]["body"])
        check("card left the list", page.locator('[data-request="%s"]' % ids["dana"]).count() == 0)
        check("tab count 3", text(page, "#ptReqTabReq") == "בקשות · 3", text(page, "#ptReqTabReq"))
        check("groups tab gained the invite (count 5)", text(page, "#ptReqTabGrp") == "קבוצות והזמנות · 5", text(page, "#ptReqTabGrp"))

        print("approve with an active invite (D12) + email failure:")
        page.locator('[data-f21-approve="%s"]' % ids["ron"]).click()
        page.wait_for_selector("#ptApName", timeout=5000)
        page.wait_for_timeout(300)
        check("title 'אישור ושליחת הזמנה חדשה'", text(page, "#ptApTitle") == "אישור ושליחת הזמנה חדשה")
        box = text(page, "#ptApActive")
        check("amber box text", "יש כבר הזמנה פעילה למייל הזה" in box and '"טיול לתאילנד" · נשלחה 07/10 · בתוקף עד 14/10. באישור היא מבוטלת והקישור הישן מפסיק לעבוד.' in box, box)
        check("draft 'תאילנד · דצמבר 2026'", page.locator("#ptApName").input_value() == "תאילנד · דצמבר 2026")
        check("send label 'ביטול הישנה ושליחת הזמנה חדשה'", text(page, "#ptApSend") == "ביטול הישנה ושליחת הזמנה חדשה")
        check("390: no h-scroll", not hscroll(page))
        shot(page, "04_approve_replace")
        be.email_fail = True
        page.locator("#ptApSend").click()
        check("email_failed toast", f05.saw_toast(page, "המייל לא נשלח. שום דבר לא השתנה – נסו שוב."))
        page.wait_for_timeout(300)
        check("sheet stays, button restored", page.locator("#ptApSend").count() == 1 and text(page, "#ptApSend") == "ביטול הישנה ושליחת הזמנה חדשה" and page.locator("#ptApSend").is_enabled())
        be.email_fail = False
        page.locator("#ptApSend").click()
        check("ok toast after retry", f05.saw_toast(page, "ההזמנה נשלחה ל-ron@example.com"))
        page.wait_for_timeout(600)

        # ------------------------------------------------------------ 4 reject (§1.9)
        print("reject (§1.9, AC 15):")
        page.locator('[data-f21-reject="%s"]' % ids["tom"]).click()
        page.wait_for_selector("#ptRjSend", timeout=5000)
        page.wait_for_timeout(300)
        check("title", text(page, "#ptRjTitle") == "לדחות את הבקשה של Tom Baker?", text(page, "#ptRjTitle"))
        check("checkbox checked by default", page.locator("#ptRjMail").is_checked() and page.locator("#ptRjMail").is_enabled())
        check("'בשפת הבקשה (כאן: אנגלית)'", text(page, "#ptRjMailSub") == "בשפת הבקשה (כאן: אנגלית)")
        pv = page.locator("#ptRjPreview")
        check("EN preview, LTR", pv.get_attribute("dir") == "ltr" and "Your Lonely Planner request" in pv.inner_text() and "We can’t open your trip right now." in pv.inner_text())
        check("sheet touch ≥44", not small_targets(page, "#ptSheet"), small_targets(page, "#ptSheet"))
        shot(page, "05_reject")
        page.locator("#ptRjMail").uncheck()
        check("preview hides when unchecked", pv.is_hidden())
        page.locator("#ptRjMail").check()
        page.locator("#ptRjSend").click()
        check("toast", f05.saw_toast(page, "הבקשה נדחתה ונשלחה הודעה במייל"))
        page.wait_for_timeout(800)
        r = be.fn_actions("reject_request")
        check("reject_request send_mail:true", len(r) == 1 and r[0]["body"] == {"action": "reject_request", "request_id": ids["tom"], "send_mail": True}, r and r[0]["body"])
        check("meter 13 after reload", "13 מתוך 50" in text(page, "#ptReqMeter"), text(page, "#ptReqMeter"))
        print("reject at the cap:")
        be.mail_today = 50
        page.locator("#ptReqTabGrp").click()
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")   # → loadAdmin (both lists)
        page.wait_for_timeout(1000)
        page.locator("#ptReqTabReq").click()
        page.wait_for_timeout(300)
        page.locator('[data-f21-reject="%s"]' % ids["t4"]).click()
        page.wait_for_selector("#ptRjSend", timeout=5000)
        check("checkbox disabled + unchecked", page.locator("#ptRjMail").is_disabled() and not page.locator("#ptRjMail").is_checked())
        check("cap line", text(page, "#ptRjMailSub") == "התקרה היומית מלאה – הדחייה תהיה בלי מייל")
        shot(page, "06_reject_cap")
        page.locator("#ptRjSend").click()
        check("toast without mail", f05.saw_toast(page, "הבקשה נדחתה"))
        page.wait_for_timeout(600)
        check("send_mail false at the cap", be.fn_actions("reject_request")[-1]["body"]["send_mail"] is False)
        print("server answers mail_skipped:'daily_limit' (meter stale):")
        rid = be.add_request("שירה", "shira@example.com", ["GR"], None, 2)
        be.mail_today = 49
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
        page.wait_for_timeout(1000)
        be.mail_today = 50
        page.locator('[data-f21-reject="%s"]' % rid).click()
        page.wait_for_selector("#ptRjSend", timeout=5000)
        page.locator("#ptRjSend").click()
        check("toast 'הבקשה נדחתה, בלי מייל (התקרה היומית מלאה)'", f05.saw_toast(page, "הבקשה נדחתה, בלי מייל (התקרה היומית מלאה)"))
        page.wait_for_timeout(600)

        print("request_closed + empty + offline:")
        rid = be.add_request("כפול", "dup@example.com", ["FR"], None, 2)
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
        page.wait_for_timeout(1000)
        be.requests[rid]["status"] = "approved"
        page.locator('[data-f21-approve="%s"]' % rid).click()
        page.wait_for_selector("#ptApSend", timeout=5000)
        page.locator("#ptApSend").click()
        check("toast 'הבקשה כבר טופלה'", f05.saw_toast(page, "הבקשה כבר טופלה"))
        page.wait_for_timeout(800)
        check("empty 'אין בקשות חדשות'", text(page, "#ptReqEmpty") == "אין בקשות חדשות", text(page, "#admin")[:200])
        rid = be.add_request("אופליין", "off@example.com", ["ES"], None, 2)
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
        page.wait_for_timeout(1000)
        dev.offline(True)
        page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
        page.wait_for_timeout(400)
        check("offline notice", page.locator("#ptReqOffline").count() == 1)
        check("offline: actions disabled", all(c["dis"] for c in cards(page)) and page.locator("[data-f21-reject]").first.is_disabled())
        shot(page, "07_admin_offline")
        dev.offline(False)
        page.evaluate("()=>window.dispatchEvent(new Event('online'))")
        page.wait_for_timeout(800)
        check("back online: enabled", not any(c["dis"] for c in cards(page)))
        check("no page errors", not f05.page_errors(dev), f05.page_errors(dev))
        env.close()

        print("default tab with 0 requests + list failure:")
        env = fresh()
        be = env.backend
        seed_admin(be, with_requests=False)
        dev = env.new_device("B")
        page = dev.page
        to_chooser(dev)
        check("no requests badge at 0", page.locator("#ptChooseRequests").count() == 0)
        check("invites badge '1 הזמנות ממתינות'", text(page, "#ptChoosePending") == "1 הזמנות ממתינות", text(page, "#ptChoosePending"))
        to_admin(dev)
        check("default tab = groups", page.locator("#ptReqTabGrp").get_attribute("aria-pressed") == "true" and text(page, "#ptReqTabReq") == "בקשות · 0")
        env.close()
        env = fresh()
        be = env.backend
        seed_admin(be)
        be.req_fail = True
        dev = env.new_device("C")
        page = dev.page
        to_chooser(dev)
        check("failed call → no requests badge", page.locator("#ptChooseRequests").count() == 0 and text(page, "#ptChoosePending") == "2 הזמנות ממתינות")
        to_admin(dev)
        check("failed list → groups tab", page.locator("#ptReqTabGrp").get_attribute("aria-pressed") == "true")
        page.locator("#ptReqTabReq").click()
        page.wait_for_timeout(500)
        check("error + retry", page.locator("#ptReqRetry").count() == 1)
        be.req_fail = False
        page.locator("#ptReqRetry").click()
        page.wait_for_timeout(1000)
        check("retry loads", len(cards(page)) == 4)
        env.close()

        # ------------------------------------------------------------ 5 wizard pre-fill (§1.11)
        print("wizard pre-fill (§1.11, AC 16):")
        env = fresh()
        be = env.backend
        iid, _ = be.add_invite("dana@example.com", "יפן ודרום קוריאה · אפריל 2027", sent_days_ago=0, expires_in_days=7)
        be.invites[iid]["prefill"] = {"name": "דנה כהן", "countries": ["JP", "KR"], "month": "2027-04-01", "lang": "he"}
        dev = env.new_device("W")
        page = dev.page
        dev.goto(APP)
        page.locator("#ptGateInviteBtn").click()
        page.wait_for_selector("#ptWzEmail", timeout=10000)
        page.locator("#ptWzEmail").fill("dana@example.com")
        page.locator("#ptWzSend").click()
        page.wait_for_selector('#ptWizard[data-screen="code"]', timeout=10000)
        f04.type_code(page, be.otp_code)
        page.wait_for_selector('#ptWizard[data-screen="step1"]', timeout=15000)
        page.wait_for_timeout(800)
        lk = [c for c in be.ct_calls if c["action"] == "lookup"]
        check("lookup returned prefill", lk and "prefill" in lk[-1]["resp"])
        check("green box", text(page, "#ptWzF21Box") == "מילאנו מה שכתבת בבקשה, כולל היעדים בשלב 2. נשאר לבחור תאריכים.")
        check("trip name = draft", page.locator("#ptWzName").input_value() == "יפן ודרום קוריאה · אפריל 2027")
        check("name in group = requester", page.locator("#ptWzMe").input_value() == "דנה כהן")
        tags = page.evaluate("()=>[...document.querySelectorAll('#ptWizard .pt-f21-tag')].map(t=>t.closest('label').htmlFor)")
        check("'מהבקשה' tags on name + me", tags == ["ptWzName", "ptWzMe"], tags)
        check("no min on the start date", page.locator("#ptWzFrom").get_attribute("min") is None)
        check("help 'בבקשה: אפריל 2027' under the start date", page.locator("#ptWzF21Month").is_visible() and text(page, "#ptWzF21Month") == "בבקשה: אפריל 2027"
              and page.evaluate("()=>document.getElementById('ptWzFrom').nextElementSibling.id") == "ptWzF21Month")
        check("390: no h-scroll", not page.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        shot(page, "08_wizard_prefill")
        page.locator("#ptWzMe").fill("דנה")
        f04.fill_step1(page, start="2027-04-03", end="2027-04-12")
        check("help hidden once a date is picked", page.locator("#ptWzF21Month").is_hidden())
        page.locator("#ptWzNext").click()
        page.wait_for_selector('#ptWizard[data-screen="step2"]', timeout=10000)
        page.wait_for_timeout(500)
        sel = page.evaluate("()=>[...document.querySelectorAll('#ptWzSel [data-code]')].map(e=>e.dataset.code)")
        check("step 2 starts with JP, KR", sel == ["JP", "KR"], sel)
        cur = page.evaluate("()=>[...document.querySelectorAll('#ptWzCurs [data-cur]')].map(e=>e.dataset.cur)")
        check("currencies JPY, KRW derived", "JPY" in cur and "KRW" in cur, cur)
        shot(page, "09_wizard_step2")
        page.locator('[data-rm="KR"]').click()
        page.locator("#ptWzBack").click()
        page.wait_for_selector('#ptWizard[data-screen="step1"]', timeout=5000)
        page.locator("#ptWzNext").click()
        page.wait_for_selector('#ptWizard[data-screen="step2"]', timeout=5000)
        sel = page.evaluate("()=>[...document.querySelectorAll('#ptWzSel [data-code]')].map(e=>e.dataset.code)")
        check("countries applied once (removal sticks)", sel == ["JP"], sel)
        check("no page errors", not f05.page_errors(dev), f05.page_errors(dev))
        env.close()

        print("wizard without prefill:")
        env = fresh()
        be = env.backend
        be.add_invite("plain@example.com", "יוון", sent_days_ago=0, expires_in_days=7)
        dev = env.new_device("W2")
        page = dev.page
        dev.goto(APP)
        page.locator("#ptGateInviteBtn").click()
        page.wait_for_selector("#ptWzEmail", timeout=10000)
        page.locator("#ptWzEmail").fill("plain@example.com")
        page.locator("#ptWzSend").click()
        page.wait_for_selector('#ptWizard[data-screen="code"]', timeout=10000)
        f04.type_code(page, be.otp_code)
        page.wait_for_selector('#ptWizard[data-screen="step1"]', timeout=15000)
        page.wait_for_timeout(500)
        check("no box, no tags, no month help", page.locator("#ptWzF21Box").count() == 0 and page.locator(".pt-f21-tag").count() == 0
              and page.locator("#ptWzF21Month").count() == 0)
        check("today's help line kept", "מולא מההזמנה, אפשר לשנות" in text(page, "#ptWizard"))
        env.close()

        # ------------------------------------------------------------ 6 flag off (AC 1)
        print("REQUEST_FEATURE='off' (AC 1):")
        env = fresh()
        be = env.backend
        serve_off(env)
        seed_admin(be)
        dev = env.new_device("O")
        page = dev.page
        to_chooser(dev)
        t = text(page, "#ptChooseAdmin")
        check("chooser row as alpha.7.2", "כל הקבוצות והזמנת מנהלים" in t and text(page, "#ptChoosePending") == "2 ממתינות" and page.locator("#ptChooseRequests").count() == 0, t)
        to_admin(dev)
        check("no tabs", page.locator("#ptReqTabs").count() == 0 and page.locator("[data-request]").count() == 0)
        check("no admin_trip_requests call", not be.req_rpcs(), be.req_rpcs())
        env.close()
        env = fresh()
        be = env.backend
        serve_off(env)
        iid, _ = be.add_invite("dana@example.com", "יפן", sent_days_ago=0, expires_in_days=7)
        be.invites[iid]["prefill"] = {"name": "דנה כהן", "countries": ["JP"], "month": "2027-04-01", "lang": "he"}
        dev = env.new_device("O2")
        page = dev.page
        dev.goto(APP)
        page.locator("#ptGateInviteBtn").click()
        page.wait_for_selector("#ptWzEmail", timeout=10000)
        page.locator("#ptWzEmail").fill("dana@example.com")
        page.locator("#ptWzSend").click()
        page.wait_for_selector('#ptWizard[data-screen="code"]', timeout=10000)
        f04.type_code(page, be.otp_code)
        page.wait_for_selector('#ptWizard[data-screen="step1"]', timeout=15000)
        page.wait_for_timeout(500)
        check("off: wizard ignores prefill", page.locator("#ptWzF21Box").count() == 0 and page.locator("#ptWzMe").input_value() == "")
        env.close()

        print("non-admin never calls admin_trip_requests:")
        env = fresh()
        be = env.backend
        tid = be.add_trip_full("טיול", "2026-11-01", "2026-11-05", countries=["GR"])
        be.links.append({"trip_id": tid, "role": "editor", "display_name": "יעל", "joined_at": "2026-10-01T10:00:00+00:00"})
        dev = env.new_device("N")
        st = dev.goto(APP)
        dev.page.wait_for_timeout(1500)
        check("booted into the trip", st == "app", st)
        check("no admin_trip_requests", not be.req_rpcs())
        env.close()
        br.close()
    srv.stop()
    n, ok = len(results), sum(results)
    print("%d/%d checks passed" % (ok, n))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
