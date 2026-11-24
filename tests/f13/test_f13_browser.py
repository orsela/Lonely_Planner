"""Lonely Planner F13 · stage 0 · one browser pass in the real app page (390x844) · version 3.0.0-alpha.17.2
CHANGE 2026-11-24 F13-QA-04: new file (no previous version). No backend: app/ is served as static files, every other host is aborted (the app stays at its gate; only <html> and f13.js are checked).
Cases: (A) as shipped (LANG_FEATURE='beta'), fresh device = Hebrew/RTL, no catalog request; (B) #f13beta then #f13en = English/LTR and the catalog is fetched; (C) flag 'off' copy with
the beta key and English stored = still Hebrew/RTL, no catalog request, storage untouched; (D) the Vietnam trip stays Hebrew/RTL, another trip is English, leaving restores English;
(E) no horizontal overflow at 390px in Hebrew.
"""
import functools
import http.server
import os
import shutil
import tempfile
import threading
from pathlib import Path

import pytest

REPO = Path(os.environ.get("REPO_DIR", str(Path(__file__).resolve().parents[2])))
VN = "f0200000-0000-4000-8000-000000000001"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _serve(directory):
    h = functools.partial(_Quiet, directory=str(directory))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


@pytest.fixture(scope="session")
def servers():
    tmp = Path(tempfile.mkdtemp(prefix="f13app_"))
    off = tmp / "app_off"
    shutil.copytree(REPO / "app", off)
    html = (off / "index.html").read_text(encoding="utf-8")
    assert "const LANG_FEATURE='beta';" in html, "shipped flag is not 'beta'"
    (off / "index.html").write_text(html.replace("const LANG_FEATURE='beta';", "const LANG_FEATURE='off';"), encoding="utf-8")
    a, b = _serve(REPO / "app"), _serve(off)
    yield {"shipped": "http://127.0.0.1:%d/index.html" % a.server_port, "off": "http://127.0.0.1:%d/index.html" % b.server_port}
    a.shutdown(); b.shutdown(); shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    exe = os.environ.get("CHROME_PATH") or ("/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=exe) if exe else p.chromium.launch(headless=True)
        yield b
        b.close()


def new_page(browser, store=None):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block", locale="he-IL")   # an Israeli phone: browser language Hebrew
    seen = []

    def route(r):
        u = r.request.url
        seen.append(u)
        if u.startswith("http://127.0.0.1"):
            r.continue_()
        else:
            r.abort()
    ctx.route("**/*", route)
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, page, seen, errs


def doc(page):
    return page.evaluate("()=>[document.documentElement.lang,document.documentElement.dir]")


def raw(page, *keys):
    """the browser's own localStorage (the F02 gate wraps Storage.prototype getItem/setItem; property access is the raw store)"""
    return page.evaluate("(ks)=>ks.map(k=>Object.prototype.hasOwnProperty.call(localStorage,k)?localStorage[k]:null)", list(keys))


def f13errs(errs):
    return [e for e in errs if "f13" in e.lower() or "__ptF13" in e]


def test_a_shipped_fresh_device_is_hebrew(browser, servers):
    ctx, page, seen, errs = new_page(browser)
    page.goto(servers["shipped"]); page.wait_for_timeout(800)
    P = []
    if doc(page) != ["he", "rtl"]: P.append("doc %r" % doc(page))
    if page.evaluate("()=>window.__ptF13&&window.__ptF13.mode") != "beta": P.append("mode")
    if page.evaluate("()=>window.__ptF13.active()"): P.append("active on a fresh device")
    if any("i18n/en.json" in u for u in seen): P.append("catalog fetched")
    if page.evaluate("()=>window.__ptF13.VERSION") != "3.0.0-alpha.17.2": P.append("version")
    if page.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"): P.append("horizontal overflow at 390px")
    if f13errs(errs): P.append("f13 page errors %r" % f13errs(errs))
    ctx.close()
    assert not P, "\n".join(P)


def test_b_beta_switch_then_english(browser, servers):
    ctx, page, seen, errs = new_page(browser)
    page.goto(servers["shipped"] + "#f13beta"); page.wait_for_timeout(600)
    P = []
    if raw(page, "pt-f13-beta") != ["1"]: P.append("beta key not set")
    if page.evaluate("()=>location.hash") != "": P.append("hash not removed")
    if doc(page) != ["he", "rtl"]: P.append("beta alone must not change the language: %r" % doc(page))
    page.goto(servers["shipped"] + "#f13en"); page.wait_for_timeout(300)
    page.reload(); page.wait_for_timeout(900)
    if raw(page, "pt:_device:lang") != ["en"]: P.append("device lang not stored")
    if doc(page) != ["en", "ltr"]: P.append("english doc %r" % doc(page))
    if not any("i18n/en.json" in u for u in seen): P.append("catalog not fetched")
    if page.evaluate("()=>window.__ptF13.locale()") != "en-GB": P.append("locale")
    if page.evaluate("()=>new Date(Date.UTC(2026,10,24)).toLocaleDateString('he-IL',{timeZone:'UTC'})") != "24/11/2026": P.append("he-IL wrapper")
    page.goto(servers["shipped"] + "#f13he"); page.wait_for_timeout(300); page.reload(); page.wait_for_timeout(600)
    if doc(page) != ["he", "rtl"]: P.append("back to hebrew %r" % doc(page))
    page.goto(servers["shipped"] + "#f13beta-off"); page.wait_for_timeout(600)
    if raw(page, "pt-f13-beta", "pt:_device:lang") != [None, None]: P.append("beta-off did not clear")
    if f13errs(errs): P.append("f13 page errors %r" % f13errs(errs))
    ctx.close()
    assert not P, "\n".join(P)


def test_c_flag_off_ignores_everything(browser, servers):
    ctx, page, seen, errs = new_page(browser)
    ctx.add_init_script("try{localStorage.setItem('pt-f13-beta','1');localStorage.setItem('pt:_device:lang','en')}catch(e){}")
    page.goto(servers["off"] + "#f13en"); page.wait_for_timeout(900)
    P = []
    if doc(page) != ["he", "rtl"]: P.append("off must stay hebrew: %r" % doc(page))
    if page.evaluate("()=>window.__ptF13.mode") != "off": P.append("mode")
    if any("i18n/en.json" in u for u in seen): P.append("catalog fetched with the flag off")
    if page.evaluate("()=>location.hash") != "#f13en": P.append("off must not consume the hash")
    if page.evaluate("()=>String(Date.prototype.toLocaleDateString).includes('native code')") is not True: P.append("Date patched with the flag off")
    if f13errs(errs): P.append("f13 page errors %r" % f13errs(errs))
    ctx.close()
    assert not P, "\n".join(P)


def test_d_vietnam_trip_is_forced_hebrew(browser, servers):
    ctx, page, seen, errs = new_page(browser)
    page.goto(servers["shipped"] + "#f13beta"); page.wait_for_timeout(500)
    page.goto(servers["shipped"] + "#f13en"); page.wait_for_timeout(300); page.reload(); page.wait_for_timeout(700)
    P = []
    if doc(page) != ["en", "ltr"]: P.append("english before %r" % doc(page))
    page.evaluate("(t)=>window.__ptF13.setTrip(t)", VN)
    if doc(page) != ["he", "rtl"]: P.append("vietnam %r" % doc(page))
    page.evaluate("()=>window.__ptF13.setTrip('fd5c2b13-cdc0-455e-9c12-b52f2e45a334')")
    if doc(page) != ["en", "ltr"]: P.append("other trip %r" % doc(page))
    page.evaluate("()=>window.__ptF13.setTrip(null)")
    if doc(page) != ["en", "ltr"]: P.append("no trip %r" % doc(page))
    ctx.close()
    assert not P, "\n".join(P)


def test_f_browser_language_applies_when_enabled(browser, servers):
    """spec §4.3: with F13 enabled on the device and no explicit choice, an English browser gets English (device > trip > browser > he)"""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block", locale="en-GB")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
    page = ctx.new_page()
    page.goto(servers["shipped"]); page.wait_for_timeout(500)
    P = []
    if doc(page) != ["he", "rtl"]: P.append("not enabled on this device yet: %r" % doc(page))
    page.goto(servers["shipped"] + "#f13beta"); page.wait_for_timeout(300); page.reload(); page.wait_for_timeout(700)
    if doc(page) != ["en", "ltr"]: P.append("enabled + english browser %r" % doc(page))
    page.goto(servers["shipped"] + "#f13he"); page.wait_for_timeout(300); page.reload(); page.wait_for_timeout(700)
    if doc(page) != ["he", "rtl"]: P.append("explicit device choice beats the browser %r" % doc(page))
    ctx.close()
    assert not P, "\n".join(P)
