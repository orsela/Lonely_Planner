"""Lonely Planner F14 · step 3 · ONE browser pass in the real app (390x844) with a stubbed chat endpoint · version 3.0.0-alpha.15
CHANGE 2026-11-15 F14-A3-03: new file (no previous version). What it covers (spec criteria in brackets): CHAT_FEATURE='on' opens the sheet and a question goes to the
endpoint with the user's JWT, trip_id and tripInfo, never the anon key [1, 2]; a flight request becomes the FB_Chat card with two prefilled links and no approve button
[5]; a request without a date becomes a plain question line, no card [6]; 429 daily_cap and 503 chat_off give one friendly line and ONE request each (no retry) [3, 4];
offline disables the link buttons [9]; 390 px layout, touch >= 44 px, no horizontal scroll [10]; CHAT_FEATURE='soon' (today) makes no request at all [4].
Uses the F10b harness (fake backend, no network); the endpoint is answered by page.route here.
Run: tests/f14/run.sh --only app
"""
import json, sys
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f10b"))
import harness as H  # noqa: E402

CHAT = H.h10.CHAT_URL
PT_KEY = H.f05.PT_KEY
CORS = {"Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"}


@pytest.fixture(scope="session")
def server():
    s = H.f05.F05Server(); yield s; s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True); yield b; b.close()


@pytest.fixture
def env(browser, server):
    server.reset(); e = H.Env(browser, server); yield e; e.close(); server.reset()


def stub(page, queue, seen):
    """Answers POSTs to the chat endpoint from `queue` [(status, body)]; every real request is appended to `seen`."""
    def handler(route, request):
        cors = dict(CORS, **{"Access-Control-Allow-Origin": request.headers.get("origin") or "*"})
        if request.method == "OPTIONS":
            return route.fulfill(status=204, headers=cors, body="")
        seen.append({"headers": request.headers, "body": json.loads(request.post_data or "{}")})
        status, body = queue.pop(0) if queue else (200, {"answer": "ברירת מחדל", "action": None})
        return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(body))
    page.route(CHAT + "**", handler)


def ask(page, text):
    page.fill("#chatInput", text); page.click("#chatSendBtn")
    page.wait_for_function("()=>!document.querySelector('.chat-typing')&&!document.getElementById('chatSendBtn').disabled", timeout=15000)
    page.wait_for_timeout(250)


def last_texts(page, n=1):
    return page.eval_on_selector_all("#chatBody .chat-bubble", "(b)=>b.map(x=>x.innerText)")[-n:]


def test_f14_chat_in_the_real_app(env):
    be = env.backend
    tid = be.fixture("S", role="manager")
    H.serve_src(env, H.app_html())   # CHAT_FEATURE is 'on' in the page since F14-FLAG-01
    dev = H.boot(env, tid, role="manager"); page = dev.page
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    P = []
    seen, queue = [], []
    stub(page, queue, seen)
    page.wait_for_timeout(800)
    ver = page.evaluate("()=>window.__ptF14&&window.__ptF14.version")
    if ver != "3.0.0-alpha.15": P.append("f14 version: %r" % ver)
    if page.evaluate("()=>window.__PT.version") != "3.0.0-alpha.16": P.append("app version: %r" % page.evaluate("()=>window.__PT.version"))
    if not page.evaluate("()=>window.__ptF14.enabled()"): P.append("f14 not enabled with CHAT_FEATURE='on'")
    page.wait_for_function("()=>document.getElementById('ptF14Css')", timeout=5000)
    page.wait_for_timeout(1200)   # airports.json / countries.json

    # AC1 · the sheet opens and a plain question goes out with the user's JWT, the trip id and tripInfo; the answer is shown
    page.click("#chatFab"); page.wait_for_timeout(300)
    if not page.locator("#chatSheet.open").count(): P.append("chat sheet did not open")
    queue.append((200, {"answer": "שלום מהשרת", "action": None}))
    ask(page, "כמה ימים בטיול?")
    if len(seen) != 1: P.append("requests for one question: %d" % len(seen))
    else:
        h, b = seen[0]["headers"], seen[0]["body"]
        auth = h.get("authorization", "")
        if not auth.startswith("Bearer ") or len(auth) < 20 or PT_KEY in auth: P.append("authorization is not a user JWT: %r" % auth[:40])
        if "apikey" in h: P.append("apikey header was sent")
        if b.get("trip_id") != tid: P.append("trip_id %r != %r" % (b.get("trip_id"), tid))
        ti = b.get("tripInfo") or {}
        if not ti.get("today") or ti.get("members") != 2 or not ti.get("name"): P.append("tripInfo: %r" % ti)
        tr = b.get("trip") or []
        if not tr or not all(len(str(x.get("date", ""))) == 10 and "-" in str(x["date"]) for x in tr[:3]): P.append("trip dates are not ISO: %r" % tr[:2])
        if b.get("question") != "כמה ימים בטיול?": P.append("question: %r" % b.get("question"))
    if "שלום מהשרת" not in last_texts(page)[0]: P.append("answer not shown: %r" % last_texts(page))

    # AC5 · flight request → FB_Chat card: two prefilled links, no approve / cancel buttons, nothing saved
    queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "flight", "from": "Batumi", "to": "Tel Aviv", "date": "2027-05-17"}}}))
    ask(page, "תמצא לי טיסה הביתה מבטומי ב-17/5")
    card = page.locator("#chatBody .p14-card[data-p14-kind=flight]")
    if card.count() != 1: P.append("flight card count: %d" % card.count())
    else:
        t = card.inner_text()
        for needle in ("BUS", "TLV", "17/05", "נוסעים", "Google Flights", "Skyscanner"):
            if needle not in t: P.append("flight card lacks %r: %r" % (needle, t[:160]))
        hrefs = card.locator("a.p14-go").evaluate_all("(a)=>a.map(x=>[x.href,x.target,x.rel])")
        if len(hrefs) != 2: P.append("flight links: %r" % hrefs)
        else:
            if not hrefs[0][0].startswith("https://www.google.com/travel/flights?q="): P.append("google flights href %r" % hrefs[0][0])
            if "/transport/flights/bus/tlv/270517/" not in hrefs[1][0] or "adultsv2=2" not in hrefs[1][0]: P.append("skyscanner href %r" % hrefs[1][0])
            if any(x[1] != "_blank" or "noopener" not in x[2] for x in hrefs): P.append("links must open in a new tab with noopener: %r" % hrefs)
    if page.locator("#chatBody [data-chat-approve], #chatBody [data-chat-cancel]").count(): P.append("an approve / cancel button is shown for search_links")
    stored = page.evaluate("()=>localStorage.getItem('planner:chat:history:v1')") or ""
    if "p14-card" in stored: P.append("card HTML was saved in the chat history")

    # AC9 · offline: the card's buttons are disabled and the offline line shows; back online they work again
    page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>false,configurable:true});window.dispatchEvent(new Event('offline'))}"); page.wait_for_timeout(500)
    if page.locator("#chatBody .p14-card a").count() != 0 or page.locator("#chatBody .p14-card [aria-disabled=true]").count() != 2 or "אין חיבור" not in page.locator("#chatBody .p14-card").inner_text(): P.append("offline card: %r" % page.locator("#chatBody .p14-card").inner_text()[:160])
    page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>true,configurable:true});window.dispatchEvent(new Event('online'))}"); page.wait_for_timeout(500)
    if page.locator("#chatBody .p14-card a.p14-go").count() != 2: P.append("links did not come back online")

    # AC6 · a hotel request with no date → one plain question line, no card
    n_cards = page.locator("#chatBody .p14-card").count()
    queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "hotel", "to": "Tbilisi"}}}))
    ask(page, "תמצא לי מלון בטביליסי")
    if page.locator("#chatBody .p14-card").count() != n_cards: P.append("a card appeared for a hotel request without a date")
    if "מאיזה תאריך" not in last_texts(page)[0]: P.append("no date question: %r" % last_texts(page))

    # AC3 / AC4 · refusals: one friendly line and exactly ONE request each, no retry
    for status, body, needle in ((429, {"error": "daily_cap", "used": 100, "cap": 100}, "מכסת השאלות"), (401, {"error": "unauthorized"}, "להתחבר מחדש"),
                                 (403, {"error": "not_member"}, "אין לך גישה"), (503, {"error": "chat_off"}, "יחזור בקרוב"), (502, {"error": "upstream_error"}, "לא הצליח לענות")):
        before = len(seen); queue.append((status, body)); ask(page, "שאלה %d" % status)
        if len(seen) - before != 1: P.append("%d: %d requests (retry?)" % (status, len(seen) - before))
        if needle not in last_texts(page)[0]: P.append("%d: friendly line missing: %r" % (status, last_texts(page)))
    sent_after = len(seen); page.wait_for_timeout(1500)
    if len(seen) != sent_after: P.append("a request went out by itself after a refusal")
    # the friendly lines never go back to the model as history
    queue.append((200, {"answer": "בסדר", "action": None})); ask(page, "ועכשיו?")
    hist = [x["text"] for x in seen[-1]["body"].get("history", [])]
    if any(("מכסת השאלות" in x) or ("להתחבר מחדש" in x) or ("אין לך גישה" in x) for x in hist): P.append("friendly lines went back as history: %r" % hist)

    # AC10 · 390 px: no horizontal scroll, touch targets >= 44 px, the card fits
    queue.append((200, {"answer": "הנה הקישורים 👇", "action": {"type": "search_links", "description": "", "params": {"kind": "hotel", "to": "Batumi", "date": "2027-05-07", "nights": 3}}}))
    ask(page, "מלון בבטומי ל-3 לילות מ-7/5/2027")
    small = page.evaluate("()=>[...document.querySelectorAll('#chatBody .p14-card .p14-go')].filter(e=>e.getBoundingClientRect().height<44).map(e=>e.className)")
    if small: P.append("card controls under 44px: %r" % small)
    w = page.evaluate("()=>{const c=[...document.querySelectorAll('#chatBody .p14-card')].pop();const b=c.getBoundingClientRect();return [b.left,b.right,document.documentElement.scrollWidth]}")
    if w[0] < 0 or w[1] > 390 or w[2] > 392: P.append("card / page overflow: %r" % w)
    hotel = page.locator("#chatBody .p14-card[data-p14-kind=hotel]").last
    if "3 לילות" not in hotel.inner_text() or "Booking" not in hotel.inner_text(): P.append("hotel card: %r" % hotel.inner_text()[:160])
    if errs: P.append("page errors: %r" % errs)

    # AC4 · CHAT_FEATURE='soon' (today's value): no request, no F14 styles; the button is the old toast
    H.serve_src(env, H.h10.flip_chat(H.app_html(), "soon"))
    seen2 = []; q2 = []
    dev2 = H.boot(env, tid, role="manager", name="B"); p2 = dev2.page
    stub(p2, q2, seen2)
    p2.wait_for_timeout(1000)
    if p2.evaluate("()=>window.__ptF14.enabled()"): P.append("soon: f14 enabled")
    if p2.locator("#ptF14Css").count(): P.append("soon: styles present")
    p2.click("#chatFab"); p2.wait_for_timeout(600)
    if p2.locator("#chatSheet.open").count(): P.append("soon: the sheet opened")
    if seen2: P.append("soon: %d requests" % len(seen2))
    assert not P, "\n".join(P)
