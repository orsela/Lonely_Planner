"""Lonely Planner F24 · browser test in the real app (390x844) · version 1.0.0
CHANGE 2026-11-14 F24-A2-03: new file (no previous version). Conversation 2: ONE browser pass over what F24 draws: the flight card, the origin
sheet, the lodging card, a booked day (no card, same HTML as with the flag off, AC3), offline (AC7), 390 px layout (AC9) and the flag-off rule (AC8).
Uses the F10b harness (fake backend, no network); the four outside sites are not opened (no network here).
Run: tests/f24/run_browser.sh
"""
import json, re, sys
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f10b"))
import harness as H  # noqa: E402

FLAG_RE = re.compile(r"""((?:const|let|var)\s+TRAVELSEARCH_FEATURE\s*=\s*)(['"])(on|off)\2""")

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

SETUP = """()=>{
 const S=(i,o)=>{tripData[i]=Object.assign({},tripData[i],o)};
 const side=(c,tz,city)=>({country:c,tz:tz,city:city});
 S(0,{isFlight:true,flightFrom:side('IL','Asia/Jerusalem',''),flightTo:side('TH','Asia/Bangkok','בנגקוק')});
 [1,2,3].forEach(i=>S(i,{country:'TH',tz:'Asia/Bangkok',city:'בנגקוק',isFlight:false}));
 S(4,{isFlight:true,flightFrom:side('TH','Asia/Bangkok','בנגקוק'),flightTo:side('JP','Asia/Tokyo','טוקיו')});
 [5,6,7,8].forEach(i=>S(i,{country:'JP',tz:'Asia/Tokyo',city:'טוקיו',isFlight:false}));
 S(7,{isBooked:true,bookedHotel:'Hotel X',bookingRef:'R1'});
 S(21,{isFlight:true,flightFrom:side('JP','Asia/Tokyo','טוקיו'),flightTo:side('IL','Asia/Jerusalem','')});
}"""

def show(page, i):
    page.evaluate("(i)=>{globalDayIndex=i;fillSelects();render()}", i); page.wait_for_timeout(500)

def card(page):
    return page.locator("#ptF24Card")

def test_f24_cards_in_the_real_app(env):
    be = env.backend
    tid = be.fixture("S", role="manager")
    dev = H.boot(env, tid, role="manager"); page = dev.page
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    P = []
    page.wait_for_timeout(800)
    ver = page.evaluate("()=>window.__ptF24&&window.__ptF24.version")
    if ver != "3.0.0-alpha.14": P.append("f24 version: %r" % ver)
    if "3.0.0-alpha.14" not in page.content(): P.append("app version string alpha.14 missing")
    H.tab(page, "route"); page.wait_for_timeout(400)
    page.locator("#routeViewToggle [data-route-view=timeline]").click(); page.wait_for_timeout(300)   # the day card (with the F24 card) is the "ציר זמן" view
    page.evaluate(SETUP); page.wait_for_timeout(300)
    page.wait_for_function("()=>window.__ptF24&&document.getElementById('ptF24Css')", timeout=5000)
    page.wait_for_timeout(1500)   # airports.json / countries.json / member count

    # AC1 · first flight day: TLV → BKK, both links prefilled, member count from trip_members
    show(page, 0)
    if card(page).count() != 1 or card(page).get_attribute("data-kind") != "flight": P.append("day 1: no flight card")
    else:
        t = card(page).inner_text()
        for needle in ("עוד אין טיסה ליום הזה", "TLV", "BKK", "ברירת מחדל", "2 נוסעים", "Google Flights", "Skyscanner"):
            if needle not in t: P.append("flight card lacks %r: %r" % (needle, t[:200]))
        hrefs = page.eval_on_selector_all("#ptF24Card a.p24-go", "(a)=>a.map(x=>[x.href,x.target,x.rel])")
        if len(hrefs) != 2: P.append("flight card links: %r" % hrefs)
        else:
            if not hrefs[0][0].startswith("https://www.google.com/travel/flights?q="): P.append("google flights href %r" % hrefs[0][0])
            if "/transport/flights/tlv/bkk/270110/" not in hrefs[1][0] or "adultsv2=2" not in hrefs[1][0]: P.append("skyscanner href %r" % hrefs[1][0])
            if any(h[1] != "_blank" or "noopener" not in h[2] for h in hrefs): P.append("links must open in a new tab with noopener: %r" % hrefs)
    # card sits under the day's reservations, inside the day card
    if not page.evaluate("()=>{const c=document.getElementById('ptF24Card');return !!c&&c.previousElementSibling&&c.previousElementSibling.id==='dayReservations'}"): P.append("card is not right after #dayReservations")

    # AC2 · origin sheet: change to LCA; the card and both links follow; next day's search is still TLV
    card(page).locator("#ptF24Chg").click(); page.wait_for_timeout(400)
    if not page.locator("#ptF24Layer").is_visible(): P.append("origin sheet not open")
    sug = page.eval_on_selector_all("#ptF24Layer [data-p24-ap]", "(b)=>b.map(x=>x.dataset.p24Ap)")
    if sug[:2] != ["TLV", "ETM"]: P.append("suggestions: %r" % sug)
    page.locator("#ptF24Q").fill("לרנקה"); page.wait_for_timeout(300)
    page.locator("[data-p24-ap=LCA]").click(); page.wait_for_timeout(200)
    if page.locator("[data-p24-ap=LCA]").get_attribute("aria-pressed") != "true": P.append("LCA not pressed")
    page.locator("#ptF24Save").click(); page.wait_for_timeout(500)
    if page.locator("#ptF24Layer").is_visible(): P.append("sheet did not close")
    t = card(page).inner_text()
    if "LCA" not in t or "נבחר ידנית" not in t: P.append("card after change: %r" % t[:200])
    hrefs = page.eval_on_selector_all("#ptF24Card a.p24-go", "(a)=>a.map(x=>x.href)")
    if not hrefs or "lca" not in hrefs[-1].lower() or "LCA" not in __import__("urllib.parse").parse.unquote(hrefs[0]): P.append("links after change: %r" % hrefs)
    rec = page.evaluate("(t)=>localStorage.getItem('pt-f24-recent-'+t)", tid)   # the app namespaces localStorage per trip on its own
    if rec != '["LCA"]': P.append("recent origins in localStorage: %r" % rec)
    # reopening the sheet shows LCA among the suggestions (last origins used on this device)
    card(page).locator("#ptF24Chg").click(); page.wait_for_timeout(300)
    sug = page.eval_on_selector_all("#ptF24Layer [data-p24-ap]", "(b)=>b.map(x=>x.dataset.p24Ap)")
    if "LCA" not in sug: P.append("recent origin missing from suggestions: %r" % sug)
    page.keyboard.press("Escape"); page.wait_for_timeout(200)

    # AC5 · mid-trip flight (day 5): origin = the previous city (BKK), destination Tokyo, one way
    show(page, 4)
    t = card(page).inner_text() if card(page).count() else ""
    if "BKK" not in t or "NRT" not in t and "HND" not in t and "טוקיו" not in t or "כיוון אחד" not in t: P.append("mid-trip flight card: %r" % t[:200])
    # return flight (day 22): origin Tokyo, destination TLV
    show(page, 21)
    t = card(page).inner_text() if card(page).count() else ""
    if "TLV" not in t or "כיוון אחד" not in t: P.append("return flight card: %r" % t[:200])

    # AC4 · lodging: Bangkok run (days 2-4) → one card on day 2, 3 nights; days 3 and 4 none
    show(page, 1)
    t = card(page).inner_text() if card(page).count() else ""
    if card(page).get_attribute("data-kind") != "hotel" or "3 לילות" not in t or "Booking" not in t or "Google Hotels" not in t: P.append("lodging card day 2: %r" % t[:200])
    hrefs = page.eval_on_selector_all("#ptF24Card a.p24-go", "(a)=>a.map(x=>x.href)")
    if not hrefs or "checkin=2027-01-11" not in hrefs[0] or "checkout=2027-01-14" not in hrefs[0] or "group_adults=2" not in hrefs[0]: P.append("booking href: %r" % hrefs)
    show(page, 2)
    if card(page).count(): P.append("day 3 (inside the run) has a card")
    # Tokyo: days 6-7 (2 nights) card on day 6, day 8 booked → no card and its HTML is byte-identical to the flag-off page (AC3)
    show(page, 5)
    t = card(page).inner_text() if card(page).count() else ""
    if "2 לילות" not in t: P.append("lodging card day 6: %r" % t[:200])
    show(page, 7)
    if card(page).count(): P.append("booked day shows a card")
    booked_on = page.evaluate("()=>document.querySelector('#route .grid .card').innerHTML")
    # a flight reservation linked to day 22 removes its card
    page.evaluate("async()=>{await SS.set(SHARED.reservations,JSON.stringify([{id:'r1',type:'flight',title:'LY',linkedDayStart:21}]))}")
    show(page, 21)
    if card(page).count(): P.append("flight day with a reservation still shows a card")

    # AC7 · offline: buttons disabled, offline line
    show(page, 0)
    page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>false,configurable:true});window.dispatchEvent(new Event('offline'))}"); page.wait_for_timeout(400)
    if page.locator("#ptF24Card a").count() != 0 or page.locator("#ptF24Card [aria-disabled=true]").count() != 2 or "אין חיבור" not in card(page).inner_text(): P.append("offline card: %r" % card(page).inner_text()[:200])
    page.evaluate("()=>{Object.defineProperty(navigator,'onLine',{get:()=>true,configurable:true});window.dispatchEvent(new Event('online'))}"); page.wait_for_timeout(400)

    # AC9 · 390 px: no horizontal scroll, touch targets ≥ 44 px (card + sheet)
    card(page).locator("#ptF24Chg").click(); page.wait_for_timeout(300)
    small = page.evaluate("()=>[...document.querySelectorAll('#ptF24Card .p24-go,#ptF24Card button,#ptF24Layer .p24-ap,#ptF24Layer .p24-x,#ptF24Layer .p24-save,#ptF24Layer .p24-in')].filter(e=>e.getBoundingClientRect().height<44).map(e=>e.className)")
    if small: P.append("controls under 44px: %r" % small)
    sw = page.evaluate("()=>document.documentElement.scrollWidth")
    if sw > 392: P.append("horizontal scroll: %s" % sw)
    page.keyboard.press("Escape")
    if errs: P.append("page errors: %r" % errs)

    # AC8 / AC3 · flag off: no card on any day, no styles, no F24 DOM; the booked day's HTML equals the flag-on page's
    src = H.app_html(); assert FLAG_RE.search(src)
    H.serve_src(env, FLAG_RE.sub(lambda m: m.group(1) + "'off'", src, count=1))
    dev2 = H.boot(env, tid, role="manager", name="B"); p2 = dev2.page
    p2.wait_for_timeout(1000); H.tab(p2, "route"); p2.wait_for_timeout(400)
    p2.locator("#routeViewToggle [data-route-view=timeline]").click(); p2.wait_for_timeout(300)
    p2.evaluate(SETUP); p2.wait_for_timeout(300)
    for i in (0, 1, 4, 5, 21):
        show(p2, i)
        if p2.locator("#ptF24Card").count(): P.append("flag off: card on day %d" % (i + 1))
    if p2.locator("#ptF24Css").count(): P.append("flag off: styles present")
    show(p2, 7)
    booked_off = p2.evaluate("()=>document.querySelector('#route .grid .card').innerHTML")
    if booked_on != booked_off: P.append("booked day HTML differs between flag on and off (AC3)")
    assert not P, "\n".join(P)
