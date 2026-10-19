# CHANGE 2026-10-19 F05-DEVSMOKE-01: new file (no previous version). Dev smoke test (not the QA suite), no network:
#   serves the repo locally, replaces supabase-js with a tiny in-memory fake (state in Python, shared by all "devices"),
#   answers join-trip / approve-member with a simplified Python model, and walks the F05 flows in Chromium at 390px:
#   join page → name → pending → manager approves on home → joiner sees "approved"; iPhone UA → transfer code;
#   installed app (not connected) → transfer code → trip opens; "מי אני" = member name; name_taken; invalid code.
# usage: python3 scripts/dev/f05_smoke.py
import functools
import os
import http.server
import json
import re
import socketserver
import threading
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CODE = "ABCDEFGH"

FAKE_JS = r"""
(function(){
 function q(table){
  const st={table,op:'select',filters:[],single:false,cols:'*',row:null};
  const b={
   select(c){if(st.op==='select')st.cols=c||'*';return b},
   eq(k,v){st.filters.push(['eq',k,v]);return b},in(k,v){st.filters.push(['in',k,v]);return b},
   like(k,v){st.filters.push(['like',k,v]);return b},
   order(){return b},limit(){return b},
   maybeSingle(){st.single=true;return b},single(){st.single=true;return b},
   upsert(row){st.op='upsert';st.row=row;return b},insert(row){st.op='upsert';st.row=row;return b},
   delete(){st.op='delete';return b},update(row){st.op='update';st.row=row;return b},
   then(res,rej){return window.__fb({op:'q',q:st,token:tok()}).then(r=>res(r),rej)}
  };return b}
 const KEY='sb-zwufpxnioqaweobnvffs-auth-token';
 let store=null;
 function tok(){try{const s=JSON.parse((store?store.getItem(KEY):localStorage.getItem(KEY))||'null');return s&&s.access_token}catch(e){return null}}
 window.supabase={createClient(u,k,o){
  store=o&&o.auth&&o.auth.storage||null;
  const get=()=>{try{return JSON.parse((store?store.getItem(KEY):localStorage.getItem(KEY))||'null')}catch(e){return null}};
  const set=v=>{const s=JSON.stringify(v);store?store.setItem(KEY,s):localStorage.setItem(KEY,s)};
  return{
   auth:{
    async getSession(){const s=get();return{data:{session:s},error:null}},
    async signInAnonymously(){const r=await window.__fb({op:'anon'});const s={access_token:r.token,user:{id:r.uid,is_anonymous:true}};set(s);return{data:{user:s.user,session:s},error:null}},
    async getUser(){const s=get();return{data:{user:s&&s.user},error:null}},
    onAuthStateChange(){return{data:{subscription:{unsubscribe(){}}}}}
   },
   from:q,
   channel(n){const ch={on(e,f,cb){window.__chans=(window.__chans||[]);window.__chans.push(cb);return ch},subscribe(){return ch}};return ch},
   removeChannel(){},rpc(){return Promise.resolve({data:null,error:{message:'no rpc'}})}
  }}};
})();
"""


class Backend:
    def __init__(self):
        self.users = {}            # token -> uid
        self.trip = str(uuid.uuid4())
        self.mgr = str(uuid.uuid4())
        self.users["tok-mgr"] = self.mgr
        self.members = [dict(id=str(uuid.uuid4()), trip_id=self.trip, user_id=self.mgr, display_name="דנה", role="manager",
                             status="active", joined_at="2026-10-01T10:00:00Z")]
        days = [dict(day=i + 1, date="0%d/04/2027" % (3 + i), region="", title="", activities="", hotel="", cost=0, notes="",
                     lat=35.68, lng=139.65, zoom=5, waypoints=[], country="JP") for i in range(3)]
        self.kv = {"trip": json.dumps(days, ensure_ascii=False), "tripname": "יפן 2027"}
        self.transfer = {}

    def uid(self, token):
        return self.users.get(token)

    def handle(self, msg):
        if msg["op"] == "anon":
            t = "tok-" + uuid.uuid4().hex[:8]
            self.users[t] = str(uuid.uuid4())
            return {"token": t, "uid": self.users[t]}
        q = msg["q"]
        uid = self.uid(msg.get("token"))
        tbl = q["table"]
        if tbl == "trip_members":
            rows = [r for r in self.members if r["user_id"] == uid or any(
                m["user_id"] == uid and m["status"] == "active" and m["trip_id"] == r["trip_id"] for m in self.members)]
        elif tbl == "trip_kv":
            rows = [dict(trip_id=self.trip, key=k, value=v) for k, v in self.kv.items()] if any(
                m["user_id"] == uid and m["status"] == "active" for m in self.members) else []
            if q["op"] == "upsert":
                r = q["row"]
                self.kv[r["key"]] = r["value"]
                return {"data": None, "error": None}
        elif tbl == "trips":
            rows = [dict(id=self.trip, name="יפן 2027", start_date="2027-04-03", end_date="2027-04-05")]
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
        uid = self.uid(token)
        if not uid:
            return 401, {"error": "unauthorized"}
        me = next((m for m in self.members if m["user_id"] == uid and m["trip_id"] == self.trip), None)
        a = body.get("action")
        if name == "join-trip":
            code = (body.get("code") or "").upper()
            if a in ("preview", "request") and CODE not in code:
                return 404, {"error": "code_invalid"}
            if a == "preview":
                return 200, dict(trip_id=self.trip, name="יפן 2027", start_date="2027-04-03", end_date="2027-04-05", days=3,
                                 members=sum(m["status"] == "active" for m in self.members), manager="דנה",
                                 me=me and dict(member_id=me["id"], status=me["status"], role=me["role"], display_name=me["display_name"]))
            if a == "request":
                nm = " ".join((body.get("display_name") or "").split())
                if me:
                    return 200, dict(trip_id=self.trip, member_id=me["id"], status=me["status"], role=me["role"], display_name=me["display_name"], created=False)
                if any(m["display_name"].lower() == nm.lower() for m in self.members):
                    return 409, {"error": "name_taken"}
                m = dict(id=str(uuid.uuid4()), trip_id=self.trip, user_id=uid, display_name=nm, role="editor", status="pending",
                         joined_at="2026-10-19T10:00:00Z")
                self.members.append(m)
                return 200, dict(trip_id=self.trip, member_id=m["id"], status="pending", role="editor", display_name=nm, created=True)
            if a == "issue_transfer":
                c = "482916"
                self.transfer[c] = me["id"]
                return 200, {"code": c, "expires_at": "2027-01-01T00:00:00Z"}
            if a == "claim_transfer":
                mid = self.transfer.pop(re.sub(r"\s", "", body.get("code", "")), None)
                if not mid:
                    return 409, {"error": "transfer_invalid"}
                m = next(m for m in self.members if m["id"] == mid)
                m["user_id"] = uid
                return 200, dict(trip_id=m["trip_id"], member_id=m["id"], role=m["role"], display_name=m["display_name"])
            if a == "cancel":
                self.members = [m for m in self.members if not (m["user_id"] == uid and m["status"] == "pending")]
                return 200, {"ok": True}
        if name == "approve-member":
            if not me or me["role"] != "manager":
                return 403, {"error": "not_manager"}
            m = next((m for m in self.members if m["id"] == body.get("member_id")), None)
            if not m or m["status"] != "pending":
                return 409, {"error": "not_pending"}
            if body.get("decision") == "reject":
                self.members.remove(m)
                return 200, {"status": "rejected", "member_id": m["id"], "display_name": m["display_name"]}
            m["status"], m["role"] = "active", body.get("role") or "editor"
            return 200, dict(status="active", member_id=m["id"], role=m["role"], display_name=m["display_name"], trip_id=self.trip)
        return 400, {"error": "invalid_request"}


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Quiet, directory=str(ROOT))
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    srv = serve()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    be = Backend()
    results = []
    shots = os.environ.get("F05_SHOTS")

    def shot(page, name):
        if shots:
            page.screenshot(path=os.path.join(shots, name + ".png"))

    def check(name, cond, detail=""):
        results.append(cond)
        print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:300]))

    with sync_playwright() as p:
        br = p.chromium.launch()

        def device(ua=None, token=None):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, service_workers="block")
            ctx.expose_binding("__fb", lambda src, msg: be.handle(msg))

            def route(r, req):
                u = req.url
                if "supabase-js" in u:
                    return r.fulfill(status=200, content_type="text/javascript", body=FAKE_JS)
                m = re.search(r"/functions/v1/(join-trip|approve-member)", u)
                if m:
                    if req.method == "OPTIONS":
                        return r.fulfill(status=204)
                    tok = (req.headers.get("authorization") or "").replace("Bearer ", "")
                    st, out = be.fn(m.group(1), tok, json.loads(req.post_data or "{}"))
                    return r.fulfill(status=st, content_type="application/json", body=json.dumps(out))
                if u.startswith(base):
                    return r.continue_()
                return r.fulfill(status=204, body="")
            ctx.route("**/*", route)
            if token:
                ctx.add_init_script("localStorage.setItem('sb-zwufpxnioqaweobnvffs-auth-token',JSON.stringify({access_token:'%s',user:{id:'%s'}}))" % (token, be.uid(token)))
            return ctx

        # --- joiner (Android/desktop UA) ---
        j = device().new_page()
        errs = []
        j.on("pageerror", lambda e: errs.append(str(e)))
        j.goto(base + "/join/#code=" + CODE.lower())
        j.wait_for_selector("#lpJoin[data-screen=form]")
        check("join: hash removed from the address bar", "#" not in j.url, j.url)
        shot(j, '1_join')
        check("join: header shows trip + manager", "יפן 2027" in j.inner_text("#lpJoin") and "דנה" in j.inner_text("#lpJoin"))
        j.fill("#lpjName", "דנה")
        j.click("#lpjSubmit")
        j.wait_for_selector("#lpjNameErr")
        check("join: name taken message", "יש כבר" in j.inner_text("#lpjNameErr"))
        j.fill("#lpjName", "  נועה ")
        j.click("#lpjSubmit")
        j.wait_for_selector("#lpJoin[data-screen=pending]")
        shot(j, '2_pending')
        check("join: pending screen", "ממתין לאישור · נועה" in j.inner_text("#lpJoin"))
        sw = j.evaluate("document.documentElement.scrollWidth")
        check("join: no horizontal scroll at 390", sw <= 390, sw)

        # --- manager on the app home ---
        mctx = device(token="tok-mgr")
        mctx.add_init_script("localStorage.setItem('pt:_device:active_trip',JSON.stringify({trip_id:'%s',role:'manager'}))" % be.trip)
        mp = mctx.new_page()
        merrs = []
        mp.on("pageerror", lambda e: merrs.append(str(e)))
        mp.goto(base + "/app/")
        mp.wait_for_selector("#ptF05Pending", timeout=20000)
        txt = mp.inner_text("#ptF05Pending")
        shot(mp, '5_home_manager')
        check("manager: pending card with נועה", "ממתינים לאישור · 1" in txt and "נועה" in txt, txt)
        check("manager: editor preselected", mp.get_attribute("#ptF05Pending [data-role=editor]", "aria-pressed") == "true")
        check("manager: active user = member name", mp.evaluate("activeUser") == "דנה", mp.evaluate("activeUser"))
        check("manager: USERS = members", mp.evaluate("USERS.slice()") == ["דנה"], mp.evaluate("USERS.slice()"))
        check("manager: user picker not open", not mp.evaluate("document.getElementById('userModal').classList.contains('open')"))
        for sel in ["#chatFab", ".tabs, nav"]:
            pass
        mp.click("#ptF05Pending [data-role=viewer]")
        check("manager: role switch updates button", "אישור כצופה" in mp.inner_text("#ptF05Pending"))
        mp.click("#ptF05Pending [data-act=approve]")
        mp.wait_for_function("!document.getElementById('ptF05Pending')")
        check("manager: card gone after approve", True)
        check("manager: USERS refreshed", mp.evaluate("USERS.slice()") == ["דנה", "נועה"], mp.evaluate("USERS.slice()"))

        # --- joiner sees approval (poll/visibility) ---
        j.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        j.wait_for_selector("#lpJoin[data-screen=approved]")
        check("join: approved, role viewer", "צופה" in j.inner_text("#lpJoin"))
        check("join: no transfer card on non-iPhone", j.query_selector("#lpjTransfer") is None)
        j.click("#lpjOpen")
        j.wait_for_url("**/app/**")
        j.wait_for_function("window.__PT&&window.__PT.started", timeout=20000)
        check("join → app: trip started", j.evaluate("window.__PT.tripId") == be.trip)
        j.wait_for_function("typeof activeUser!=='undefined'&&activeUser==='נועה'", timeout=10000)
        check("join → app: מי אני = נועה", True)

        # --- iPhone: transfer code, then the installed app claims it ---
        ios = device(ua="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        ip = ios.new_page()
        ip.goto(base + "/join/#code=" + CODE)
        ip.wait_for_selector("#lpJoin[data-screen=form]")
        ip.fill("#lpjName", "איתי")
        ip.click("#lpjSubmit")
        ip.wait_for_selector("#lpJoin[data-screen=pending]")
        mid = next(m["id"] for m in be.members if m["display_name"] == "איתי")
        be.fn("approve-member", "tok-mgr", {"member_id": mid, "decision": "approve", "role": "editor"})
        ip.evaluate("(window.__chans||[]).forEach(cb=>cb({}))")   # Realtime event
        ip.wait_for_selector("#lpJoin[data-screen=approved]")
        ip.wait_for_function("document.getElementById('lpjCode').textContent.replace(/\\s/g,'')==='482916'")
        shot(ip, '3_approved_ios')
        check("iPhone: transfer code shown", True)
        app2 = device().new_page()   # the 'installed app' = a fresh identity
        app2.goto(base + "/app/")
        app2.wait_for_selector("#ptF05Transfer")
        shot(app2, '4_gate')
        check("app not connected: transfer card on top", app2.evaluate("document.getElementById('ptGate').firstElementChild.id") == "ptF05Transfer")
        check("app not connected: F04 invite + device card kept", app2.query_selector("#ptGateInvite") is not None and app2.query_selector("#ptDeviceCode") is not None)
        app2.focus("#ptF05Otp0")
        app2.keyboard.type("48")
        check("app: typing advances focus", app2.evaluate("document.activeElement.id") == "ptF05Otp2", app2.evaluate("document.activeElement.id"))
        app2.evaluate("[0,1,2,3,4,5].forEach(i=>document.getElementById('ptF05Otp'+i).value='')")
        app2.focus("#ptF05Otp0")
        app2.keyboard.insert_text("482916")   # one-time-code autofill / paste puts the whole code into box 1
        app2.wait_for_function("!document.getElementById('ptF05Claim').disabled")
        app2.click("#ptF05Claim")
        app2.wait_for_function("window.__PT&&window.__PT.started", timeout=20000)
        check("app: claim → trip started", app2.evaluate("window.__PT.tripId") == be.trip)
        app2.wait_for_function("activeUser==='איתי'", timeout=10000)
        check("app: מי אני = איתי", True)

        # --- invalid code; in-app paste of a bad link ---
        bad = device().new_page()
        bad.goto(base + "/join/#code=ZZZZZZZZ")
        bad.wait_for_selector("#lpJoin[data-screen=invalid]")
        shot(bad, '6_invalid')
        check("invalid code screen", "הקישור כבר לא פעיל" in bad.inner_text("#lpJoin"))
        g = device().new_page()
        g.goto(base + "/app/")
        g.wait_for_selector("#ptF05LinkBtn")
        g.click("#ptF05LinkBtn")
        g.fill("#ptF05LinkIn", "hello")
        g.click("#ptF05LinkGo")
        check("in-app link: bad input message", "לא נראה כמו קישור" in g.inner_text("#ptF05LinkErr"))
        g.fill("#ptF05LinkIn", "https://x/join/#code=" + CODE)
        g.click("#ptF05LinkGo")
        g.wait_for_selector("#lpJoin[data-screen=form]")
        check("in-app link: join form inside the app", g.is_visible("#lpjName"))
        g.click("#lpjBack")
        check("in-app link: back to the gate", g.is_visible("#ptF05Transfer"))

        check("no page errors (join/manager)", not errs and not [e for e in merrs if "google" not in e.lower()], errs + merrs)
        br.close()
    srv.shutdown()
    print("F05 smoke: %d/%d" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
