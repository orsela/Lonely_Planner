"""Lonely Planner F13 · dev tool: English crawl of the chat sheet (F14) and the flight / lodging search cards (F24) · version 3.0.0-alpha.21.9
CHANGE 2026-11-25 F13-TOOL-04: new file (no previous version). Not a test. Uses the F10b harness (fake backend, no network); the chat endpoint is answered by page.route with canned answers (plain answer, a flight and a hotel search_links action, a hotel request without a date, every refusal status),
and the F24 cards are driven the way tests/f24/test_f24_browser.py does (flight day, origin sheet, lodging card, booked day, offline). Prints the Hebrew texts shown in English without a catalog entry; names the user typed and the canned Hebrew answers of the stub are skipped.
Usage: python3 collect_chat.py [out.json]   (REPO_DIR=… as for the other F13 browser tests)"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f10b"))
import harness as H  # noqa: E402

CHAT = H.h10.CHAT_URL
CORS = {"Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"}
FLAG = re.compile(r"""((?:const|let|var)\s+LANG_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")
STUB_TEXTS = {"שלום מהשרת", "הנה הקישורים 👇", "ברירת מחדל"}      # the stub's own canned answers are not app texts
USER = re.compile(r"^(דנה|אור|שירי|שחר|עמית|עפרי|ד|יפן 2027|ויאטנם 2026|כמה ימים בטיול\?|תמצא לי .*|שאלה \d+)$")
SETUP = """()=>{
 const S=(i,o)=>{tripData[i]=Object.assign({},tripData[i],o)};
 const side=(c,tz,city)=>({country:c,tz:tz,city:city});
 S(0,{isFlight:true,flightFrom:side('IL','Asia/Jerusalem',''),flightTo:side('TH','Asia/Bangkok','בנגקוק')});
 [1,2,3].forEach(i=>S(i,{country:'TH',tz:'Asia/Bangkok',city:'בנגקוק',isFlight:false}));
 S(4,{isFlight:true,flightFrom:side('TH','Asia/Bangkok','בנגקוק'),flightTo:side('JP','Asia/Tokyo','טוקיו')});
 [5,6,7,8].forEach(i=>S(i,{country:'JP',tz:'Asia/Tokyo',city:'טוקיו',isFlight:false}));
 S(7,{isBooked:true,bookedHotel:'Hotel X',bookingRef:'R1'});
}"""


def main(out):
    from playwright.sync_api import sync_playwright
    seen = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        server = H.f05.F05Server(); env = H.Env(b, server)
        tid = env.backend.fixture("S", role="manager")
        src = FLAG.sub(lambda m: m.group(1) + "'on'", H.app_html(), count=1)
        H.serve_src(env, src)
        dev = H.boot(env, tid, role="manager"); page = dev.page
        queue = []
        def handler(route, request):
            cors = dict(CORS, **{"Access-Control-Allow-Origin": request.headers.get("origin") or "*"})
            if request.method == "OPTIONS":
                return route.fulfill(status=204, headers=cors, body="")
            status, body = queue.pop(0) if queue else (200, {"answer": "ברירת מחדל", "action": None})
            return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(body))
        page.route(CHAT + "**", handler)
        page.wait_for_timeout(1500)
        page.evaluate("()=>window.__ptF13&&window.__ptF13.setLang('en')"); page.wait_for_timeout(800)
        page.reload(); page.wait_for_function("()=>window.__ptF13&&window.__ptF13.stats&&document.getElementById('chatFab')", timeout=30000); page.wait_for_timeout(2500)      # a device whose language is English from the start (what a real English user gets)
        def grab(label):
            try:
                st = page.evaluate("()=>window.__ptF13?window.__ptF13.stats():null")
                for t in (st["missingList"] if st else []):
                    if t not in STUB_TEXTS and not USER.match(t): seen.setdefault(t, label)
            except Exception as e:
                seen.setdefault("(grab failed: %s)" % str(e)[:60], label)
        def ask(text, label):
            page.fill("#chatInput", text); page.click("#chatSendBtn")
            try: page.wait_for_function("()=>!document.querySelector('.chat-typing')&&!document.getElementById('chatSendBtn').disabled", timeout=15000)
            except Exception: pass
            page.wait_for_timeout(400); grab(label)
        grab("boot")
        # ---- chat (F14)
        page.click("#chatFab"); page.wait_for_timeout(500); grab("chat: sheet opened (empty state, suggestions)")
        for chip in page.locator("#chatBody [data-chat-q], .chat-chip, .chat-sug button").all()[:6]:
            try: grab("chat: chip " + (chip.inner_text() or "")[:20])
            except Exception: pass
        queue.append((200, {"answer": "שלום מהשרת", "action": None})); ask("כמה ימים בטיול?", "chat: plain answer")
        queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "flight", "from": "Batumi", "to": "Tel Aviv", "date": "2027-05-17"}}})); ask("תמצא לי טיסה", "chat: flight card")
        queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "hotel", "to": "Tbilisi", "checkin": "2027-05-17", "checkout": "2027-05-20"}}})); ask("תמצא לי מלון", "chat: hotel card")
        queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "hotel", "to": "Tbilisi"}}})); ask("תמצא לי מלון בלי תאריך", "chat: hotel without a date")
        for status, body in ((429, {"error": "daily_cap", "used": 100, "cap": 100}), (401, {"error": "unauthorized"}), (403, {"error": "not_member"}), (503, {"error": "chat_off"}), (502, {"error": "upstream_error"})):
            queue.append((status, body)); ask("שאלה %d" % status, "chat: refusal %d" % status)
        page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>false,configurable:true});window.dispatchEvent(new Event('offline'))}"); page.wait_for_timeout(600); grab("chat: offline")
        page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>true,configurable:true});window.dispatchEvent(new Event('online'))}"); page.wait_for_timeout(400)
        try: page.click("#chatScrim", timeout=1500, position={"x": 5, "y": 5}); page.wait_for_timeout(400)      # close the sheet (the scrim covers the app while it is open)
        except Exception: page.keyboard.press("Escape"); page.wait_for_timeout(400)
        # ---- F24 cards on the route screen
        H.tab(page, "route"); page.wait_for_timeout(400)
        page.locator("#routeViewToggle [data-route-view=timeline]").click(); page.wait_for_timeout(300)
        page.evaluate(SETUP); page.wait_for_function("()=>window.__ptF24&&document.getElementById('ptF24Css')", timeout=5000); page.wait_for_timeout(1500)
        def show(i, label):
            page.evaluate("(i)=>{globalDayIndex=i;fillSelects();render()}", i); page.wait_for_timeout(600); grab(label)
        show(0, "f24: first flight day (TLV → BKK)")
        try:
            page.locator("#ptF24Card #ptF24Chg").click(timeout=2000); page.wait_for_timeout(500); grab("f24: origin sheet")
            page.locator("#ptF24Q").fill("larnaca"); page.wait_for_timeout(400); grab("f24: origin search")
            page.locator("#ptF24Q").fill("zzzz"); page.wait_for_timeout(400); grab("f24: origin search, no result")
            page.locator("#ptF24Q").fill("לרנקה"); page.wait_for_timeout(300)
            page.locator("[data-p24-ap=LCA]").click(timeout=1500); page.locator("#ptF24Save").click(timeout=1500); page.wait_for_timeout(500); grab("f24: origin changed")
        except Exception as e:
            seen.setdefault("(f24 origin sheet failed: %s)" % str(e)[:70], "f24")
        show(1, "f24: lodging card (hotel day)")
        show(4, "f24: second flight day (BKK → TYO)")
        show(7, "f24: booked day (no card)")
        page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>false,configurable:true});window.dispatchEvent(new Event('offline'))}"); page.wait_for_timeout(500)
        show(0, "f24: offline")
        Path(out).write_text(json.dumps({"count": len(seen), "missing": seen}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(len(seen), "missing texts →", out)
        env.close(); server.stop(); b.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/f13_chat.json")
