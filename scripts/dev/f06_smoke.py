# CHANGE 2026-10-22 F06-DEVSMOKE-01: new file (no previous version). Dev smoke test (not the QA suite), no network:
#   serves the repo locally, replaces supabase-js with the F05 smoke's in-memory fake (state in Python, shared by all
#   "devices"), answers join-trip / approve-member / manage-members with a simplified Python model of 0012 + 0014 (RLS on
#   trip_kv: managers/editors write, viewers are refused with 42501) and walks the F06 flows in Chromium at 390px.
# usage: python3 scripts/dev/f06_smoke.py          (F06_SHOTS=<dir> also saves screenshots)
import json
import os
import random
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_smoke import FAKE_JS, serve  # noqa: E402  (same fake supabase-js + static server as the F05 smoke)

from playwright.sync_api import sync_playwright  # noqa: E402

ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOT = Path(__file__).resolve().parents[2]


class Backend:
    def __init__(self):
        self.users = {}
        self.trip = str(uuid.uuid4())
        self.code = "ABCDEFGH"
        self.code_version = 1
        self.members = []
        self.calls = []
        days = [dict(day=i + 1, date="0%d/04/2027" % (3 + i), region="", title="", activities="", hotel="", cost=0, notes="",
                     lat=35.68, lng=139.65, zoom=5, waypoints=[], country="JP") for i in range(3)]
        self.kv = {"trip": json.dumps(days, ensure_ascii=False), "tripname": "יפן 2027"}

    def add(self, tok, name, role, status="active", seen=None):
        uid = str(uuid.uuid4())
        self.users[tok] = uid
        m = dict(id=str(uuid.uuid4()), trip_id=self.trip, user_id=uid, display_name=name, role=role, status=status,
                 joined_at="2026-10-%02dT10:00:00Z" % (len(self.members) + 1), last_seen_at=seen)
        self.members.append(m)
        return m

    def me(self, uid):
        return next((m for m in self.members if m["user_id"] == uid), None)

    def active(self, uid, roles=None):
        m = self.me(uid)
        return bool(m and m["status"] == "active" and (roles is None or m["role"] in roles))

    def handle(self, msg):
        if msg["op"] == "anon":
            t = "tok-" + uuid.uuid4().hex[:8]
            self.users[t] = str(uuid.uuid4())
            return {"token": t, "uid": self.users[t]}
        q = msg["q"]
        uid = self.users.get(msg.get("token"))
        tbl = q["table"]
        if tbl == "trip_members":
            rows = [dict(r) for r in self.members if r["user_id"] == uid or self.active(uid)]
        elif tbl == "trip_kv":
            if q["op"] in ("upsert", "delete"):
                if not self.active(uid, ("manager", "editor")):
                    return {"data": None, "error": {"message": "new row violates row-level security policy", "code": "42501"}}
                if q["op"] == "upsert":
                    self.kv[q["row"]["key"]] = q["row"]["value"]
                    return {"data": None, "error": None}
                key = next((v for op, k, v in q["filters"] if k == "key"), None)
                had = key in self.kv
                self.kv.pop(key, None)
                return {"data": [{"key": key}] if had else [], "error": None}
            rows = [dict(trip_id=self.trip, key=k, value=v) for k, v in self.kv.items()] if self.active(uid) else []
        elif tbl == "trips":
            rows = [dict(id=self.trip, name=self.kv.get("tripname"), start_date="2027-04-03", end_date="2027-04-05")] if self.active(uid) else []
        elif tbl == "trip_join_codes":
            rows = [dict(trip_id=self.trip, code=self.code, version=self.code_version)] if self.active(uid, ("manager",)) else []
        else:
            rows = []
        for op, k, v in q["filters"]:
            if op == "eq":
                rows = [r for r in rows if str(r.get(k)) == str(v)]
            elif op == "in":
                rows = [r for r in rows if r.get(k) in v]
            elif op == "like":
                pre = v.rstrip("%").replace("\\", "")
                rows = [r for r in rows if str(r.get(k, "")).startswith(pre)]
        if q["single"]:
            return {"data": rows[0] if rows else None, "error": None}
        return {"data": rows, "error": None}

    def fn(self, name, token, body):
        uid = self.users.get(token)
        if not uid:
            return 401, {"error": "unauthorized"}
        self.calls.append((name, body.get("action") or body.get("decision")))
        me = self.me(uid)
        a = body.get("action")
        mgr = bool(me and me["status"] == "active" and me["role"] == "manager")
        others = lambda m: [x for x in self.members if x["role"] == "manager" and x["status"] == "active" and x["id"] != m["id"]]
        if name == "join-trip":
            code = (body.get("code") or "").upper()
            if a in ("preview", "request") and self.code not in code:
                return 404, {"error": "code_invalid"}
            if a == "preview":
                vis = me if me and me["status"] != "removed" else None          # F06 D2
                return 200, dict(trip_id=self.trip, name=self.kv.get("tripname"), start_date="2027-04-03", end_date="2027-04-05", days=3,
                                 members=sum(m["status"] == "active" for m in self.members), manager="דנה",
                                 me=vis and dict(member_id=vis["id"], status=vis["status"], role=vis["role"], display_name=vis["display_name"]))
            if a == "request":
                nm = " ".join((body.get("display_name") or "").split())
                if me and me["status"] != "removed":
                    return 200, dict(trip_id=self.trip, member_id=me["id"], status=me["status"], role=me["role"], display_name=me["display_name"], created=False)
                if any(m["display_name"].lower() == nm.lower() and m["status"] != "removed" for m in self.members):
                    return 409, {"error": "name_taken"}
                if me:                                                          # D2: re-use the removed row
                    me.update(status="pending", display_name=nm, role="editor", joined_at="2026-10-22T10:00:00Z")
                    m = me
                else:
                    m = self.add("x-" + uuid.uuid4().hex, nm, "editor", "pending")
                    self.users.pop(next(k for k, v in self.users.items() if v == m["user_id"]))
                    m["user_id"] = uid
                return 200, dict(trip_id=self.trip, member_id=m["id"], status="pending", role="editor", display_name=nm, created=True)
            if a == "cancel":
                self.members = [m for m in self.members if not (m["user_id"] == uid and m["status"] == "pending")]
                return 200, {"ok": True}
        if name == "approve-member":
            if not mgr:
                return 403, {"error": "not_manager"}
            m = next((m for m in self.members if m["id"] == body.get("member_id")), None)
            if not m or m["status"] != "pending":
                return 409, {"error": "not_pending"}
            m["status"], m["role"] = "active", body.get("role") or "editor"
            return 200, dict(status="active", member_id=m["id"], role=m["role"], display_name=m["display_name"], trip_id=self.trip)
        if name == "manage-members":
            t = next((m for m in self.members if m["id"] == body.get("member_id")), None)
            if a in ("set_role", "rename", "remove"):
                if not mgr:
                    return 403, {"error": "not_manager"}
                if not t or t["status"] != "active":
                    return 409, {"error": "not_active"}
            if a == "set_role":
                if t["role"] == "manager" and body["role"] != "manager" and not others(t):
                    return 409, {"error": "last_manager"}
                t["role"] = body["role"]
                return 200, dict(member_id=t["id"], trip_id=self.trip, role=t["role"], display_name=t["display_name"], changed=True, version="x")
            if a == "rename":
                nm = " ".join((body.get("display_name") or "").split())
                if not 1 <= len(nm) <= 40:
                    return 400, {"error": "name_invalid"}
                if any(x["id"] != t["id"] and x["status"] in ("active", "pending") and x["display_name"].lower() == nm.lower() for x in self.members):
                    return 409, {"error": "name_taken"}
                t["display_name"] = nm
                return 200, dict(member_id=t["id"], trip_id=self.trip, display_name=nm, changed=True)
            if a == "remove":
                if t["user_id"] == uid:
                    return 400, {"error": "invalid_request"}
                t["status"] = "removed"
                return 200, dict(member_id=t["id"], trip_id=self.trip, status="removed", display_name=t["display_name"])
            if a == "leave":
                if not me or me["status"] != "active":
                    return 403, {"error": "not_member"}
                if me["role"] == "manager" and not others(me):
                    return 409, {"error": "last_manager"}
                me["status"] = "removed"
                return 200, dict(ok=True, trip_id=self.trip, member_id=me["id"])
            if a == "rotate_link":
                if not mgr:
                    return 403, {"error": "not_manager"}
                self.code = "".join(random.choice(ALPHA) for _ in range(8))
                self.code_version += 1
                return 200, dict(code=self.code, code_version=self.code_version)
            if a == "touch":
                if not me or me["status"] != "active":
                    return 403, {"error": "not_member"}
                me["last_seen_at"] = "2026-10-22T10:00:00Z"
                return 200, dict(ok=True, touched=True)
        return 400, {"error": "invalid_request"}


def main():
    srv = serve()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    be = Backend()
    mgr = be.add("tok-mgr", "דנה", "manager", seen="2026-10-22T08:00:00Z")
    noa = be.add("tok-noa", "נועה", "editor", seen="2026-10-21T08:00:00Z")
    itai = be.add("tok-itai", "איתי", "viewer")
    amit = be.add("tok-amit", "עמית", "editor")
    be.add("tok-roni", "רוני", "editor", status="pending")
    results = []
    shots = os.environ.get("F06_SHOTS")
    app_html = (ROOT / "app" / "index.html").read_text(encoding="utf-8")

    def shot(page, name):
        if shots:
            page.screenshot(path=os.path.join(shots, name + ".png"), full_page=False)

    def check(name, cond, detail=""):
        results.append(bool(cond))
        print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:300]))

    with sync_playwright() as p:
        br = p.chromium.launch()
        errors = []

        def device(token=None, flag_off=False):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block", has_touch=True)
            ctx.expose_binding("__fb", lambda src, msg: be.handle(msg))

            def route(r, req):
                u = req.url
                if "supabase-js" in u:
                    return r.fulfill(status=200, content_type="text/javascript", body=FAKE_JS)
                m = re.search(r"/functions/v1/(join-trip|approve-member|manage-members)", u)
                if m:
                    if req.method == "OPTIONS":
                        return r.fulfill(status=204)
                    tok = (req.headers.get("authorization") or "").replace("Bearer ", "")
                    st, out = be.fn(m.group(1), tok, json.loads(req.post_data or "{}"))
                    return r.fulfill(status=st, content_type="application/json", body=json.dumps(out))
                if flag_off and re.search(r"/app/(index\.html)?$", u.split("?")[0]):
                    return r.fulfill(status=200, content_type="text/html", body=app_html.replace("const MEMBERS_FEATURE='on';", "const MEMBERS_FEATURE='off';"))
                if u.startswith(base):
                    return r.continue_()
                return r.fulfill(status=204, body="")
            ctx.route("**/*", route)
            if token:
                ctx.add_init_script("localStorage.setItem('sb-zwufpxnioqaweobnvffs-auth-token',JSON.stringify({access_token:'%s',user:{id:'%s'}}));"
                                    "if(!localStorage.getItem('pt:_device:active_trip'))localStorage.setItem('pt:_device:active_trip',JSON.stringify({trip_id:'%s',role:null}))"
                                    % (token, be.users[token], be.trip))
            return ctx

        def open_app(ctx):
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(base + "/app/")
            pg.wait_for_function("window.__PT&&window.__PT.started", timeout=20000)
            pg.wait_for_function("typeof tripData!=='undefined'&&tripData.length>0", timeout=20000)
            return pg

        def no_hscroll(pg):
            return pg.evaluate("document.documentElement.scrollWidth<=390")

        def small_targets(pg, sel):
            return pg.evaluate("""s=>[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return[e.id||e.textContent.trim().slice(0,20),Math.round(r.width),Math.round(r.height)]}).filter(x=>x[1]<44||x[2]<44)""", sel)

        # ---------------- flag off: alpha.6 "עוד" ----------------
        off = open_app(device("tok-mgr", flag_off=True))
        off.click(".tab[data-panel=more]")
        off.wait_for_selector("#ptJoinRow", timeout=10000)
        check("flag off: F04 row 'קישור הצטרפות לקבוצה', no F06 rows, no __ptF06, ניהול ← משתמשים visible",
              off.query_selector("#ptF06MembersRow") is None and off.query_selector("#ptF06LeaveRow") is None
              and off.evaluate("typeof window.__ptF06==='undefined'") and off.evaluate("getComputedStyle(document.getElementById('mgmtUsers')).display!=='none'"))
        check("flag off: version 3.0.0-alpha.7", off.evaluate("window.__PT.version") == "3.0.0-alpha.7")
        off.context.close()

        # ---------------- manager: "עוד" + members screen ----------------
        mp = open_app(device("tok-mgr"))
        mp.click(".tab[data-panel=more]")
        mp.wait_for_selector("#ptF06MembersRow")
        mp.wait_for_function("document.getElementById('ptF06MembersSub').textContent.indexOf('4 חברים')===0")
        shot(mp, "1_more")
        check("עוד: 'חברים וקישור' with '4 חברים' and badge '1 ממתינים'; F04 row absent",
              "חברים וקישור" in mp.inner_text("#ptF06MembersRow") and mp.inner_text("#ptF06PendingBadge") == "1 ממתינים" and mp.query_selector("#ptJoinRow") is None,
              mp.inner_text("#ptF06MembersRow"))
        check("עוד: 'יציאה מהטיול' says only manager", "המנהל/ת היחיד/ה" in mp.inner_text("#ptF06LeaveSub"))
        check("ניהול ← משתמשים hidden in cloud mode", mp.evaluate("getComputedStyle(document.getElementById('mgmtUsers')).display==='none'"))
        mp.click("#ptF06MembersRow")
        mp.wait_for_selector("#ptF06Members.active #ptF06List .pt6-mrow")
        mp.wait_for_function("document.getElementById('ptF06Url').textContent.indexOf('#code=ABCDEFGH')>0")
        shot(mp, "2_members")
        names = mp.eval_on_selector_all("#ptF06List .pt6-mrow b", "els=>els.map(e=>e.childNodes[0].textContent.trim())")
        check("members: active only, me first, then by joined_at", names == ["דנה", "נועה", "איתי", "עמית"], names)
        check("members: counts 'חברים · 4' / 'מנהל/ת אחד/ת'", mp.inner_text("#ptF06ListTitle") == "חברים · 4" and mp.inner_text("#ptF06MgrCount") == "מנהל/ת אחד/ת")
        check("members: last seen texts", "עוד לא נכנס/ה" in mp.inner_text("#ptF06List") and "(את/ה)" in mp.inner_text("#ptF06List"), mp.inner_text("#ptF06List"))
        check("members: pending shortcut", mp.inner_text("#ptF06PendingTxt") == "1 ממתינים לאישור")
        check("members: URL is LTR", mp.evaluate("getComputedStyle(document.getElementById('ptF06Url')).direction") == "ltr")
        check("members: no horizontal scroll at 390", no_hscroll(mp))
        check("members: touch targets ≥44px", not small_targets(mp, "#ptF06Members button, #ptF06Members a"), small_targets(mp, "#ptF06Members button, #ptF06Members a"))
        check("tab bar visible, 'עוד' active", mp.evaluate("document.querySelector('.tab[data-panel=more]').classList.contains('active')"))

        # member sheet: role + name
        mp.click("[aria-label='פעולות על איתי']")
        mp.wait_for_selector("#ptF06Box #ptF06Roles")
        shot(mp, "3_sheet")
        check("sheet: viewer pressed, remove row present", mp.get_attribute("#ptF06Roles [data-role=viewer]", "aria-pressed") == "true" and mp.query_selector("#ptF06RemoveRow") is not None)
        check("sheet: touch targets ≥44px", not small_targets(mp, "#ptF06Box button, #ptF06Box input"), small_targets(mp, "#ptF06Box button, #ptF06Box input"))
        mp.fill("#ptF06NameIn", "נועה")
        mp.click("#ptF06NameSave")
        mp.wait_for_selector("#ptF06NameErr:not([hidden])")
        check("rename: name_taken inline", 'יש כבר "נועה" בטיול' in mp.inner_text("#ptF06NameErr"))
        mp.fill("#ptF06NameIn", "  איתי   כהן ")
        mp.click("#ptF06NameSave")
        mp.wait_for_selector("#ptF06Layer[hidden]", state="attached")
        check("rename: saved", next(m for m in be.members if m["id"] == itai["id"])["display_name"] == "איתי כהן")
        mp.click("[aria-label='פעולות על נועה']")
        mp.click("#ptF06Roles [data-role=viewer]")
        mp.wait_for_function("document.getElementById('ptF06Toast')&&document.getElementById('ptF06Toast').textContent.indexOf('נועה עכשיו צופה')>=0")
        check("set_role: נועה → viewer stored + toast", noa["role"] == "viewer")

        # rotate
        old = be.code
        mp.click("#ptF06Rotate")
        mp.wait_for_selector("#ptF06RotateT")
        shot(mp, "4_rotate")
        check("rotate dialog: points incl. '4 החברים' and the pending line", "4 החברים בטיול לא מושפעים" in mp.inner_text("#ptF06Box") and "הבקשה הממתינה נשארת" in mp.inner_text("#ptF06Box"))
        mp.click("#ptF06RotateYes")
        mp.wait_for_function("document.getElementById('ptF06Url').textContent.indexOf('%s')<0" % old)
        check("rotate: new code shown + toast with WhatsApp action", be.code in mp.inner_text("#ptF06Url") and "נוצר קישור חדש" in mp.inner_text("#ptF06Toast") and mp.query_selector("#ptF06ToastAct") is not None)

        # only manager: own sheet, leave → 1.6
        mp.click("[aria-label='פעולות על דנה']")
        mp.wait_for_selector("#ptF06OnlyMgr")
        shot(mp, "5_lastmanager")
        check("only manager: amber box, viewer/editor disabled, no remove row",
              mp.is_disabled("#ptF06Roles [data-role=viewer]") and mp.is_disabled("#ptF06Roles [data-role=editor]") and mp.query_selector("#ptF06RemoveRow") is None)
        mp.click("#ptF06PickMgr")
        check("'למנות מנהל אחר' closes the sheet, list stays", mp.evaluate("document.getElementById('ptF06Layer').hidden") and mp.is_visible("#ptF06List"))
        mp.click("#ptF06Back")
        mp.click("#ptF06LeaveRow")
        mp.wait_for_selector("#ptF06OnlyMgr")
        check("leave as only manager → 1.6 instead of the confirm", mp.query_selector("#ptF06LeaveT") is None)
        mp.keyboard.press("Escape")

        # remove עמית
        mp.click("#ptF06MembersRow")
        mp.wait_for_selector("[aria-label='פעולות על עמית']")
        mp.click("[aria-label='פעולות על עמית']")
        mp.click("#ptF06RemoveRow")
        mp.wait_for_selector("#ptF06RemoveT")
        shot(mp, "6_remove")
        check("remove dialog title", mp.inner_text("#ptF06RemoveT") == "להסיר את עמית מהטיול?")
        mp.click("#ptF06RemoveYes")
        mp.wait_for_function("document.getElementById('ptF06Toast').textContent.indexOf('עמית הוסר/ה מהטיול')>=0")
        mp.wait_for_function("document.getElementById('ptF06ListTitle').textContent==='חברים · 3'")
        check("remove: עמית removed, list updated", amit["status"] == "removed")
        check("pending shortcut → home", (mp.click("#ptF06ToHome") or True) and mp.evaluate("['homeV2','home'].some(i=>document.getElementById(i)&&document.getElementById(i).classList.contains('active'))"))
        check("touch called on start", ("manage-members", "touch") in be.calls)

        # ---------------- viewer (נועה): guard ----------------
        np_ = open_app(device("tok-noa"))
        np_.wait_for_selector("#ptF06ViewerTag", timeout=10000)
        check("viewer: 'צופה' tag in the home header", np_.inner_text("#ptF06ViewerTag") == "צופה")
        kv_before = dict(be.kv)
        ls_before = np_.evaluate("localStorage.getItem('planner:expenses')")
        np_.keyboard.press("Shift")
        res = np_.evaluate("SS.set('planner:expenses',JSON.stringify([{amount:1,by:'נועה'}]))")
        np_.wait_for_function("document.getElementById('ptF06Toast')&&document.getElementById('ptF06Toast').classList.contains('on')")
        check("viewer guard: toast 'צפייה בלבד – השינוי לא נשמר'", np_.inner_text("#ptF06Toast") == "צפייה בלבד – השינוי לא נשמר")
        np_.keyboard.press("Shift")
        np_.evaluate("SS.del('planner:tripname')")
        check("viewer guard: SS.set returns false; trip_kv, localStorage and queue unchanged",
              res is False and be.kv == kv_before and np_.evaluate("localStorage.getItem('planner:expenses')") == ls_before
              and np_.evaluate("localStorage.getItem('planner:__queue__')") in (None, "[]"), (res, ls_before))
        check("viewer guard: device-only key still written", np_.evaluate("localStorage.setItem('planner:qe:cur','USD'),localStorage.getItem('planner:qe:cur')") == "USD")
        np_.evaluate("localStorage.setItem('lp_join_code','%s')" % be.code)
        # role change live: viewer → editor (realtime) → 1.8a
        noa["role"] = "editor"
        np_.evaluate("(window.__chans||[]).forEach(cb=>{try{cb({})}catch(e){}})")
        np_.wait_for_selector("#ptF06Changed", timeout=5000)
        check("1.8a: 'ההרשאה שלך השתנתה לעורך', tag gone", "ההרשאה שלך השתנתה לעורך" in np_.inner_text("#ptF06Changed") and np_.query_selector("#ptF06ViewerTag") is None)
        np_.click("#ptF06Ack")
        check("1.8a: 'הבנתי' hides it", np_.query_selector("#ptF06Changed") is None)
        # demotion with 2 queued changes → dropped
        np_.evaluate("localStorage.setItem('planner:__queue__',JSON.stringify([{type:'set',key:'planner:expenses',value:'[]'},{type:'set',key:'planner:checkins',value:'[]'}]))")
        noa["role"] = "viewer"
        kv_before = dict(be.kv)
        np_.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        np_.wait_for_selector("#ptF06Dropped", timeout=5000)
        shot(np_, "7_changed")
        check("D8: '2 שינויים שעשית בלי רשת לא נשמרו.', queue empty, nothing reached trip_kv",
              np_.inner_text("#ptF06Dropped") == "2 שינויים שעשית בלי רשת לא נשמרו." and np_.evaluate("localStorage.getItem('planner:__queue__')") == "[]" and be.kv == kv_before)
        check("viewer screen: no horizontal scroll", no_hscroll(np_))
        # removed live → 1.8b
        noa["status"] = "removed"
        np_.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        np_.wait_for_selector("#ptF06Removed", timeout=5000)
        shot(np_, "8_removed")
        trip_keys = np_.evaluate("Object.keys(localStorage).filter(k=>k.indexOf('pt:%s:')===0)" % be.trip)
        check("1.8b: title, rejoin button, keys pt:<trip>:* gone, cached trip cleared",
              'כבר אינך חבר/ה ב"יפן 2027"' in np_.inner_text("#ptF06RemovedTitle") and np_.query_selector("#ptF06Rejoin") is not None
              and not trip_keys and np_.evaluate("localStorage.getItem('pt:_device:active_trip')") is None, trip_keys)
        check("1.8b: no trip chrome visible", not np_.is_visible(".tabs"))
        np_.reload()
        np_.wait_for_selector("#ptF06Removed", timeout=10000)
        check("1.8b again at the next boot (device record; raw key, the app's localStorage view is namespaced)", np_.evaluate("Object.keys(localStorage).includes('pt:_device:removed')"))
        np_.click("#ptF06Rejoin")
        np_.wait_for_selector("#lpJoin[data-screen=form]", timeout=10000)
        check("rejoin: /join/ shows the normal form (D2)", np_.query_selector("#lpjName") is not None and not np_.evaluate("!!localStorage.getItem('pt:_device:removed')"))
        np_.fill("#lpjName", "נועה")
        np_.click("#lpjSubmit")
        np_.wait_for_selector("#lpJoin[data-screen=pending]")
        check("rejoin: same row → pending", noa["status"] == "pending" and sum(m["user_id"] == noa["user_id"] for m in be.members) == 1)

        # ---------------- leave (איתי כהן, viewer → leave is allowed) ----------------
        ip = open_app(device("tok-itai"))
        ip.click(".tab[data-panel=more]")
        ip.wait_for_selector("#ptF06LeaveRow")
        check("editor/viewer: no 'חברים וקישור' row", ip.query_selector("#ptF06MembersRow") is None)
        ip.click("#ptF06LeaveRow")
        ip.wait_for_selector("#ptF06LeaveT")
        shot(ip, "9_leave")
        check("leave dialog title", ip.inner_text("#ptF06LeaveT") == 'לצאת מ"יפן 2027"?')
        ip.click("#ptF06LeaveYes")
        ip.wait_for_selector("#ptGate", timeout=20000)
        check("leave: removed, local clean-up, not-connected card, no 1.8b",
              itai["status"] == "removed" and ip.query_selector("#ptF06Removed") is None
              and not ip.evaluate("Object.keys(localStorage).filter(k=>k.indexOf('pt:%s:')===0)" % be.trip))

        # ---------------- manager sees the re-request; demoting a second manager hides the row ----------------
        mp.evaluate("(window.__chans||[]).forEach(cb=>{try{cb({})}catch(e){}})")
        mp.wait_for_selector("#ptF05Pending", timeout=10000)
        check("manager home: נועה's new request in the F05 card", "נועה" in mp.inner_text("#ptF05Pending"))
        be.fn("approve-member", "tok-mgr", {"member_id": noa["id"], "decision": "approve", "role": "manager"})
        mp.evaluate("(window.__chans||[]).forEach(cb=>{try{cb({})}catch(e){}})")
        mp.click(".tab[data-panel=more]")
        mp.click("#ptF06MembersRow")
        mp.wait_for_function("document.getElementById('ptF06MgrCount').textContent==='2 מנהלים'")
        mp.click("[aria-label='פעולות על דנה']")
        mp.wait_for_selector("#ptF06Roles")
        check("two managers: my sheet is the normal one (I may step down)", mp.query_selector("#ptF06OnlyMgr") is None and not mp.is_disabled("#ptF06Roles [data-role=editor]"))
        mp.click("#ptF06Roles [data-role=editor]")
        mp.wait_for_function("!document.getElementById('ptF06MembersRow')", timeout=5000)
        check("self-demote: row gone without reload, back on עוד", mgr["role"] == "editor" and mp.evaluate("document.getElementById('more').classList.contains('active')"))

        check("no page errors", not [e for e in errors if "google" not in e.lower()], errors)
        br.close()
    srv.shutdown()
    print("F06 smoke: %d/%d" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
