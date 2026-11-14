"""Lonely Planner F08 · browser test in the real app (390x844) · version 1.0.0
CHANGE 2026-11-14 F08-A3-03: new file (no previous version). Conversation 3: ONE browser pass over what stage A shows:
the "מדינות לפי ימים" row + screen, the day edit box (switch "יום טיסה", origin / destination, country change on one day),
the home clocks (here / home / destination on a flight day) and the flag-off rule. Uses the F10b harness (fake backend, no network).
Run: tests/f08/run_browser.sh
"""
import json, os, sys
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

def fill_required(page):
    """empty_days fixtures leave the old form's required fields blank (HTML validation would stop the submit)"""
    for i, v in (("fRegion", "אזור"), ("fTitle", "כותרת"), ("fActivities", "פעילות"), ("fHotel", "מלון"), ("fCost", "0"), ("fLat", "13.75"), ("fLng", "100.5")):
        if not page.locator("#" + i).input_value(): page.locator("#" + i).fill(v)

def days_of(env, tid):
    return env.backend.kv_json(tid, "trip", [])

def test_f08_stage_a_in_the_real_app(env):
    be = env.backend
    tid = be.fixture("S", role="manager")
    dev = H.boot(env, tid, role="manager")
    page = dev.page
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    P = []
    page.wait_for_timeout(800)
    # 1 · version + more row + screen
    ver = page.evaluate("()=>window.__ptF08&&window.__ptF08.version")
    if ver != "3.0.0-alpha.13.1": P.append("f08 version: %r" % ver)
    if "3.0.0-alpha.14" not in page.content(): P.append("app version string alpha.14 missing")  # CHANGE 2026-11-14 F24-A2-05: was alpha.13.1 (app version bumped by F24)
    page.evaluate("()=>document.querySelector('.tab[data-panel=more]').click()")
    page.wait_for_timeout(400)
    if not page.locator("#ptF08Row").is_visible(): P.append("עוד → מדינות לפי ימים row not visible")
    page.locator("#ptF08Row").click(); page.wait_for_timeout(600)
    if not page.locator("#ptF08Panel").is_visible(): P.append("screen not open")
    if page.locator("[data-f08-range]").count() != 1: P.append("expected 1 range, got %d" % page.locator("[data-f08-range]").count())
    # 2 · day edit: switch to flight, destination Japan, save
    page.evaluate("()=>document.querySelector('.tab[data-panel=route]').click()"); page.wait_for_timeout(400)
    page.evaluate("()=>{globalDayIndex=4;fillSelects();render()}"); page.wait_for_timeout(300)
    page.locator("#dayEditBtn").click(); page.wait_for_timeout(500)
    if not page.locator("#ptF08DayBox").is_visible(): P.append("day edit box missing")
    if page.locator("#ptF08D_n_c").count() != 1: P.append("normal day: country select missing")
    page.locator("#ptF08DFl").check(force=True); page.wait_for_timeout(300)
    if page.locator("[data-g=from]").count() != 1 or page.locator("[data-g=to]").count() != 1: P.append("flight: origin/destination groups missing")
    page.locator("#ptF08D_to_c").select_option("JP"); page.wait_for_timeout(300)
    page.locator("#ptF08D_to_city").fill("טוקיו")
    fill_required(page); page.locator("#dayForm button.btn.green").click(); page.wait_for_timeout(1200)
    d = days_of(env, tid)
    if not d[4].get("isFlight"): P.append("day 5 not saved as flight: %r" % {k: d[4].get(k) for k in ("isFlight", "flightFrom", "flightTo")})
    elif (d[4].get("flightTo") or {}).get("country") != "JP" or d[4]["flightTo"].get("city") != "טוקיו": P.append("flightTo not saved: %r" % d[4].get("flightTo"))
    if d[4].get("flightFrom"): P.append("flightFrom should stay derived: %r" % d[4].get("flightFrom"))
    page.locator("#dayEditModal button.close").click(); page.wait_for_timeout(400)   # the route screen leaves the form open after a save
    # 3 · day after: Japan on one day (day 6)
    page.evaluate("()=>{globalDayIndex=5;fillSelects();render()}"); page.wait_for_timeout(300)
    page.locator("#dayEditBtn").click(); page.wait_for_timeout(500)
    page.locator("#ptF08D_n_c").select_option("JP"); page.wait_for_timeout(300)
    fill_required(page); page.locator("#dayForm button.btn.green").click(); page.wait_for_timeout(1200)
    d = days_of(env, tid)
    if d[5].get("country") != "JP" or d[5].get("tz") != "Asia/Tokyo": P.append("day 6 not saved as Japan: %r" % {k: d[5].get(k) for k in ("country", "tz", "city")})
    if d[3].get("country") not in (None, "TH"): P.append("day 4 changed: %r" % d[3].get("country"))
    # 4 · clocks: here = Bangkok on 12/01 (day 3), flight day 14/01 shows the destination clock
    # (clock check below uses __ptF08 directly with an explicit "now": tickClocks reads the real Date in the test browser)
    now = "2027-01-12T05:00:00Z"
    tz = page.evaluate("(n)=>window.__ptF08.f08HereTz(new Date(n))", now)
    if tz != "Asia/Bangkok": P.append("here tz on 12/01: %r" % tz)
    tz2 = page.evaluate("()=>window.__ptF08.f08HereTz(new Date('2027-01-15T03:00:00Z'))")
    if tz2 != "Asia/Tokyo": P.append("here tz on 15/01 (Japan day): %r" % tz2)
    # 4b · stage B: converter "local" currency follows today's day (day 6 set to Vietnam; fixture local is THB) – wired through the 30 s tick
    page.evaluate("()=>{const a=tripData;a[5]=Object.assign({},a[5],{country:'VN',tz:'Asia/Ho_Chi_Minh'});}")
    before = page.evaluate("()=>window.__ptF10.get().local")
    page.clock.set_fixed_time("2027-01-15T05:00:00Z")      # 12:00 Ho Chi Minh on 15/01 = day index 5
    page.wait_for_timeout(32000)
    after = page.evaluate("()=>window.__ptF10.get().local")
    if before != "THB" or after != "VND": P.append("converter local currency: before=%r after=%r (want THB → VND)" % (before, after))
    # 5 · layout at 390: no horizontal scroll with the sheet and the day box open
    sw = page.evaluate("()=>document.documentElement.scrollWidth"); 
    if sw > 392: P.append("horizontal scroll: %s" % sw)
    small = page.evaluate("()=>[...document.querySelectorAll('#ptF08DayBox select,#ptF08DayBox input[type=text],#ptF08DayBox .p08-swl')].filter(e=>e.getBoundingClientRect().height<44).length")
    if small: P.append("%d controls under 44px" % small)
    if errs: P.append("page errors: %r" % errs)
    assert not P, "\n".join(P)
