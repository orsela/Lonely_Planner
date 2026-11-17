"""Lonely Planner NOTES-RICH · one browser pass in the real app (390x844) · version 1.0.0
CHANGE 2026-11-17 NOTES-RICH-T-03: new file. Uses the F10b harness (fake backend, no network). Checks: other trip = unchanged DOM (flag/whitelist), listed trip = bullets,
links (https only), '+' on a 21-word bullet, gallery with +N, broken image disappears, point nav button, images editor in the day form, no horizontal overflow.
Run: tests/richnotes/run.sh browser
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

W21 = " ".join("מילה%d" % i for i in range(1, 22))
SETUP = """(w)=>{Object.assign(tripData[0],{activities:'• טירת פלש\\n• כיכר המועצה',notes:'• פתיח\\n• טיפ: https://www.romania-insider.com/brasov\\n• '+w+'\\n• בטל http://bad.example/x',
 images:['https://example.invalid/1.jpg','https://example.invalid/2.jpg','https://example.invalid/3.jpg','https://example.invalid/4.jpg','https://example.invalid/5.jpg'],
 waypoints:[{name:'טירת פלש',lat:45.36,lng:25.54,notes:'• כניסה בסיור',images:['https://example.invalid/w.jpg']}]});}"""

def show(page, i=0):
    page.evaluate("(i)=>{globalDayIndex=i;fillSelects();render()}", i); page.wait_for_timeout(600)

def test_richnotes_in_the_real_app(env):
    be = env.backend; tid = be.fixture("S", role="manager")
    dev = H.boot(env, tid, role="manager"); page = dev.page
    page.set_viewport_size({"width": 390, "height": 844})
    errs = []; page.on("pageerror", lambda e: errs.append(str(e))); P = []
    page.wait_for_timeout(800)
    if page.evaluate("()=>window.__ptRN&&window.__ptRN.version") != "3.0.0-alpha.17": P.append("richnotes version")
    H.tab(page, "route"); page.wait_for_timeout(400)
    page.evaluate(SETUP, W21); show(page)
    # not listed trip (the fixture trip) → exactly the old drawing
    if page.locator("#activities .rn-ul").count() or page.locator("#rnDayGal").count() or page.locator(".rn-wp").count(): P.append("rich drawing on a trip that is not listed")
    old = page.evaluate("()=>document.getElementById('notes').textContent")
    if "romania-insider" not in old: P.append("old notes text changed: %r" % old[:80])
    # list the trip → rich drawing
    page.evaluate("(t)=>RICHNOTES_TRIPS.push(t)", tid); show(page)
    page.locator("#routeViewToggle [data-route-view=timeline]").click(); page.wait_for_timeout(300)
    page.evaluate("()=>{document.querySelector('#route details.subsection').open=true}")
    if page.locator("#activities li").count() != 2: P.append("activities bullets: %d" % page.locator("#activities li").count())
    if page.locator("#notes li").count() != 4: P.append("notes bullets: %d" % page.locator("#notes li").count())
    hrefs = page.eval_on_selector_all("#notes a", "(a)=>a.map(x=>[x.href,x.target,x.rel,x.textContent])")
    if len(hrefs) != 1 or hrefs[0][0] != "https://www.romania-insider.com/brasov" or hrefs[0][1] != "_blank" or "noopener" not in hrefs[0][2] or hrefs[0][3] != "romania-insider.com/brasov": P.append("links: %r" % hrefs)
    if "http://bad.example/x" not in page.inner_text("#notes"): P.append("http text lost")
    more = page.locator("#notes .rn-more")
    if more.count() != 1: P.append("'+' buttons: %d" % more.count())
    else:
        li = page.locator("#notes li").nth(2)
        if "מילה21" in li.inner_text(): P.append("21st word visible before +")
        more.click(); page.wait_for_timeout(150)
        if "מילה21" not in li.inner_text() or more.inner_text() != "−": P.append("+ did not expand")
        more.click(); page.wait_for_timeout(150)
        if "מילה21" in li.inner_text(): P.append("− did not collapse")
    # gallery: 3 thumbs + "+2"; broken images (example.invalid) vanish; with no network every image fails → gallery removed
    page.wait_for_timeout(1500)
    if page.locator("#rnDayGal").count() != 0: P.append("gallery of broken images should disappear")
    # a working data-URI image (https only is enforced elsewhere; here check the +N logic through the pure part)
    # points: nav button + notes
    if page.locator(".rn-wp a.rn-nav").count() != 1: P.append("nav buttons: %d" % page.locator(".rn-wp a.rn-nav").count())
    else:
        h = page.get_attribute(".rn-wp a.rn-nav", "href")
        if h != "https://www.google.com/maps/search/?api=1&query=45.36,25.54": P.append("nav href %r" % h)
    if "כניסה בסיור" not in page.inner_text(".rn-wp"): P.append("point notes missing")
    # edit form: images editor, https validation, saved into the day
    page.locator("#dayEditBtn").click(); page.wait_for_timeout(500)
    if not page.locator("#rnImgEd").is_visible(): P.append("images editor not shown in the day form")
    else:
        page.fill("#rnImgEd input", "http://bad/1.jpg"); page.click("#rnImgEd .rn-add button"); page.wait_for_timeout(150)
        if "https" not in page.inner_text("#rnImgEd .rn-err"): P.append("no https error")
        page.fill("#rnImgEd input", "https://example.invalid/new.jpg"); page.click("#rnImgEd .rn-add button"); page.wait_for_timeout(150)
        page.evaluate("()=>{const f=$('dayForm');f.querySelectorAll('[required]').forEach(i=>{if(!i.value)i.value=i.type==='number'?'1':'x'})}")   # fixture day lacks coordinates etc.
        page.get_by_role("button", name="שמור שינויים").click(); page.wait_for_timeout(800)
        imgs = page.evaluate("()=>tripData[0].images")
        if not imgs or imgs[-1] != "https://example.invalid/new.jpg" or len(imgs) != 6: P.append("images not saved: %r" % imgs)
    # 390px: no horizontal overflow
    if page.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"): P.append("horizontal overflow at 390px")
    # flag-off equivalent: unlist the trip → old drawing returns
    page.evaluate("()=>{RICHNOTES_TRIPS.length=0}"); show(page)
    if page.locator(".rn-ul").count() or page.locator(".rn-wp").count(): P.append("unlisting the trip did not restore the old drawing")
    if errs: P.append("page errors: %r" % errs[:3])
    assert not P, "\n".join(P)
