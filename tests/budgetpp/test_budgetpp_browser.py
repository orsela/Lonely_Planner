"""Lonely Planner BUDGET-PP · one browser pass in the real app (390x844) · version 1.0.0
CHANGE 2026-11-17 BUDGETPP-T-03: new file. Fake backend (F10b harness). Checks: unlisted trip = no card; listed trip = 7 rows with the defaults; expense → actual per person; manager edit saves;
flights actual typed by hand; no horizontal overflow; unlisting removes the card.
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

def test_budgetpp_in_the_real_app(env):
    be = env.backend; tid = be.fixture("S", role="manager")
    dev = H.boot(env, tid, role="manager"); page = dev.page
    page.set_viewport_size({"width": 390, "height": 844})
    errs = []; page.on("pageerror", lambda e: errs.append(str(e))); P = []
    page.wait_for_timeout(800)
    if page.evaluate("()=>window.__ptBP&&window.__ptBP.version") != "3.0.0-alpha.17.1": P.append("budgetpp version")
    H.tab(page, "budget"); page.wait_for_timeout(600)
    if page.locator("#bpCard").count(): P.append("card on a trip that is not listed")
    page.evaluate("(t)=>BUDGETPP_TRIPS.push(t)", tid)
    page.evaluate("()=>renderBudget()"); page.wait_for_timeout(800)
    rows = page.locator("#bpCard .bp-row")
    if rows.count() != 7: P.append("rows: %d" % rows.count())
    t = page.inner_text("#bpCard")
    for needle in ("€450", "€520", "€280", "€125", "€50", "€250", "€1,675", "10 נוסעים", "טרם נרכש", "תל אביב – בוקרשט – תל אביב"):
        if needle not in t: P.append("card lacks %r" % needle)
    # an expense → actual per person (home currency of the fixture → € needs a rate; only check the card still draws)
    page.evaluate("""async()=>{const k=SHARED.expenses;await SS.set(k,JSON.stringify([{description:'x',amount:100,category:'food',by:'אור',createdAt:Date.now()}]));await renderBudget()}"""); page.wait_for_timeout(800)
    if page.locator("#bpCard .bp-row").count() != 7: P.append("card lost after an expense")
    # manager edit: lodging 450 → 500, travelers 8
    page.locator("#bpCard [data-bp=lodging] .bp-ed").click(); page.wait_for_timeout(200)
    page.fill("#bpP", "500"); page.fill("#bpN", "8"); page.get_by_role("button", name="שמירה").click(); page.wait_for_timeout(800)
    t = page.inner_text("#bpCard")
    if "€500" not in t or "8 נוסעים" not in t or "€1,725" not in t: P.append("after edit: %r" % t[:200])
    saved = page.evaluate("()=>SS.get('planner:budget_pp')")
    if not saved or '"lodging":500' not in saved: P.append("not saved: %r" % saved)
    # flights actual by hand
    page.locator("#bpCard [data-bp=flights] .bp-ed").click(); page.wait_for_timeout(200)
    page.fill("#bpA", "310"); page.get_by_role("button", name="שמירה").click(); page.wait_for_timeout(800)
    ft = page.inner_text("#bpCard [data-bp=flights]")
    if "€310" not in ft or "⚠️" not in ft: P.append("flights actual: %r" % ft)
    if page.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"): P.append("horizontal overflow at 390px")
    page.evaluate("()=>{BUDGETPP_TRIPS.length=0}"); page.evaluate("()=>renderBudget()"); page.wait_for_timeout(600)
    if page.locator("#bpCard").count(): P.append("unlisting did not remove the card")
    if errs: P.append("page errors: %r" % errs[:3])
    assert not P, "\n".join(P)
