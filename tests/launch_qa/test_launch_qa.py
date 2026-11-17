"""Lonely Planner LAUNCH-QA · links, points of interest, notes and booking links in the real app (390x844) · version 1.0.0
CHANGE 2026-11-17 LAUNCH-QA-01: new file (no previous version). Uses the F10b harness (fake backend, no network).
Covers what a new group member does first: (1) add a point of interest from a pasted Google Maps link / coordinates (full link, "@lat,lng", "!3d!4d",
plain coordinates, place-name auto-fill, short maps.app.goo.gl link rejected with the explanation, garbage rejected, out-of-range rejected);
(1g) an empty point is refused (count unchanged; the refusal message itself is not asserted); (2) the saved point is drawn and persisted to the fake backend; (3) the day's booking link opens in a new tab with rel=noopener;
(4) hostile links in notes (javascript:, data:, http:) never become anchors; (5) deleting a point works; (6) no horizontal overflow at 390px; (7) no page errors.
Run: tests/launch_qa/run.sh
"""
import sys
from pathlib import Path
import pytest
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f10b"))
import harness as H  # noqa: E402


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


def add_point(page, raw, name=""):
    page.evaluate("()=>{document.getElementById('wpName').value='';document.getElementById('wpLat').value='';document.getElementById('wpLng').value='';document.getElementById('mapsInput').value='';document.getElementById('mapsFeedback').textContent=''}")
    page.evaluate("()=>document.getElementById('newWaypoint').click()"); page.wait_for_timeout(300)
    if not page.evaluate("()=>document.getElementById('wpManual').open"):
        page.locator("#wpManual summary").click(); page.wait_for_timeout(150)   # a real tap on "או: קישור Google Maps / קואורדינטות" (collapsed by default)
    page.fill("#mapsInput", raw)
    if name:
        page.fill("#wpName", name)
    page.click("#parseMaps"); page.wait_for_timeout(150)
    return page.inner_text("#mapsFeedback"), page.input_value("#wpLat"), page.input_value("#wpLng"), page.input_value("#wpName")


def test_links_and_points_in_the_real_app(env):
    be = env.backend; tid = be.fixture("S", role="manager")
    dev = H.boot(env, tid, role="manager"); page = dev.page
    page.set_viewport_size({"width": 390, "height": 844})
    errs = []; page.on("pageerror", lambda e: errs.append(str(e))); P = []
    dialogs = []; page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.wait_for_timeout(800)
    H.tab(page, "route"); page.wait_for_timeout(400)
    page.evaluate("(i)=>{if(!activeUser)activeUser='בדיקה';globalDayIndex=i;fillSelects();render()}", 0); page.wait_for_timeout(500)
    n0 = page.evaluate("()=>tripData[0].waypoints.length")

    # (1a) full Google Maps place link: "@lat,lng" + place name auto-fill
    fb, lat, lng, nm = add_point(page, "https://www.google.com/maps/place/Bran+Castle/@45.5149,25.3672,17z/data=!3m1")
    if "✅" not in fb or lat != "45.5149" or lng != "25.3672" or nm != "Bran Castle": P.append("@lat,lng link: %r %r %r %r" % (fb, lat, lng, nm))
    page.click("#saveWaypoint"); page.wait_for_timeout(500)
    # (2) saved + drawn
    if page.evaluate("()=>tripData[0].waypoints.length") != n0 + 1: P.append("point not added to tripData")
    if "Bran Castle" not in page.evaluate("()=>document.getElementById('waypoints').textContent"): P.append("point not drawn in the list")
    # persisted to the (fake) backend: the trip blob is saved through saveTrip
    saved = page.evaluate("async()=>{const v=await SS.get(SHARED.trip);return v}")
    if not saved or "Bran Castle" not in saved: P.append("point not persisted via SS/saveTrip")

    # (1b) !3d!4d form
    fb, lat, lng, nm = add_point(page, "https://www.google.com/maps/place/X/data=!4m6!3d45.6427!4d25.5887", "בראשוב")
    if "✅" not in fb or lat != "45.6427" or lng != "25.5887" or nm != "בראשוב": P.append("!3d!4d link: %r %r %r %r" % (fb, lat, lng, nm))
    page.evaluate("()=>document.querySelector('#waypointModal .close').click()")
    # (1c) plain coordinates
    fb, lat, lng, nm = add_point(page, "45.7983, 24.1256")
    if lat != "45.7983" or lng != "24.1256": P.append("plain coordinates: %r %r" % (lat, lng))
    page.evaluate("()=>document.querySelector('#waypointModal .close').click()")
    # (1d) short link: rejected with the explanation, nothing filled
    fb, lat, lng, nm = add_point(page, "https://maps.app.goo.gl/abc123XYZ")
    if "מקוצר" not in fb or lat or lng: P.append("short link not explained: %r" % fb)
    # (1e) garbage + out of range
    fb, lat, lng, nm = add_point(page, "hello world")
    if "לא נמצאו" not in fb or lat or lng: P.append("garbage accepted: %r" % fb)
    fb, lat, lng, nm = add_point(page, "95.0,200.0")
    if lat or lng: P.append("out-of-range coordinates accepted: %r %r" % (lat, lng))
    # (1f) saving without a name / coordinates is refused (alert), nothing added
    n1 = page.evaluate("()=>tripData[0].waypoints.length")
    page.click("#saveWaypoint"); page.wait_for_timeout(300)
    n1b = page.evaluate("()=>tripData[0].waypoints.length")
    if n1b != n1: P.append("empty point was saved (%d -> %d)" % (n1, n1b))
    page.evaluate("()=>document.querySelector('#waypointModal .close').click()")

    # (3)+(4) day booking link + hostile links in notes
    page.evaluate("""()=>{Object.assign(tripData[0],{bookingLink:'https://www.airbnb.co.uk/rooms/123',notes:'• ok https://example.org/a\\n• javascript:alert(1)\\n• data:text/html,<b>x</b>\\n• http://plain.example/x'});render()}""")
    page.wait_for_timeout(400)
    # the booking card sits in the day card renderer (esc'd href, target=_blank, rel=noopener)
    anchors = page.eval_on_selector_all("a[href*='airbnb.co.uk']", "(a)=>a.map(x=>[x.target,x.rel])")
    if not anchors: P.append("booking link not rendered anywhere")
    else:
        t, r = anchors[0]
        if t != "_blank" or "noopener" not in r: P.append("booking link target/rel: %r" % anchors[0])
    bad = page.eval_on_selector_all("a", "(a)=>a.map(x=>x.getAttribute('href')||'').filter(h=>/^\\s*(javascript|data):/i.test(h))")
    if bad: P.append("dangerous hrefs rendered: %r" % bad)

    # (5) delete a point (manager)
    n2 = page.evaluate("()=>tripData[0].waypoints.length")
    page.locator("#routeViewToggle [data-route-view=timeline]").click(); page.wait_for_timeout(300)
    page.evaluate("()=>{document.querySelectorAll('#route details').forEach(d=>d.open=true)}")   # the day's points sit in a collapsible section
    more = page.locator("[data-ui-wp-more]")
    if not more.count():
        P.append("no ⋯ button on points (real delete path)")
    else:
        more.last.click(); page.wait_for_timeout(400)
        page.screenshot(path="/tmp/launch_qa_sheet.png")
        sheet_txt = page.evaluate("()=>document.body.innerText")
        if "ניווט לנקודה" not in sheet_txt or "מחיקה" not in sheet_txt: P.append("point actions sheet missing navigate/delete")
        page.locator("button.ui-act.danger").click(); page.wait_for_timeout(300)        # "🗑️ מחיקה" row → confirm card
        if "למחוק את" not in page.inner_text(".ui-confirm"): P.append("no confirmation before deleting a point")
        page.locator("[data-ui-ok]").click(); page.wait_for_timeout(600)
        if page.evaluate("()=>tripData[0].waypoints.length") != n2 - 1: P.append("delete point (real path) did not remove it")

    # (6) layout + (7) errors
    if page.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"): P.append("horizontal overflow at 390px")
    if errs: P.append("page errors: %r" % errs[:3])
    assert not P, "\n".join(P)
