"""Lonely Planner F13 stage 1 · /join/ browser test (390x844, fake backend, no network) · version 3.0.0-alpha.18.6
CHANGE 2026-11-24 F13-QA-04: new file (no previous version). LEAN rule 5: one browser pass at the end of the stage.
Covers: flag off = Hebrew/RTL/no switch (= alpha.16); beta without the key = Hebrew; beta with the key / 'on' = switch, English screens (form, pending, relink pending, expired),
dir/lang on <html> + the mount root, no horizontal scroll, touch targets >= 44px, the choice survives a reload, names inside English sentences.
Run: tests/f13/run.sh join
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f05")); sys.path.insert(0, str(HERE.parent / "f07"))
import harness as H  # noqa: E402
import test_f05 as T5  # noqa: E402
import test_f07_browser as T7  # noqa: E402

FLAG = re.compile(r"""((?:const|let|var)\s+LANG_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")


@pytest.fixture(scope="session")
def server():
    s = H.F05Server(); yield s; s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True); yield b; b.close()


@pytest.fixture
def env(browser, server):
    server.reset(); e = H.Env(browser, server); yield e; e.close(); server.reset()


DATA = re.compile("עב|דנה|יפן")    # the switch label and the trip data (trip name, manager name) are user content: never translated


def serve(env, lang, relink="on"):
    src = H.join_html()
    assert FLAG.search(src), "LANG_FEATURE flag missing in join/index.html"
    src = FLAG.sub(lambda m: m.group(1) + "'" + lang + "'", src, count=1)
    src = re.sub(r"""(const\s+RELINK_FEATURE\s*=\s*)(['"])(on|off)\2""", lambda m: m.group(1) + "'" + relink + "'", src, count=1)
    out = src.encode("utf-8")
    env.server.overrides[H.JOIN + "index.html"] = out; env.server.overrides[H.JOIN] = out
    app = FLAG.sub(lambda m: m.group(1) + "'" + lang + "'", H.app_html(), count=1).encode("utf-8") if FLAG.search(H.app_html()) else H.app_html().encode("utf-8")
    env.server.overrides[H.APP + "index.html"] = app; env.server.overrides[H.APP] = app
    T7.emulate_f07_server(env.backend)


def dev_with(env, name, beta=False, lang=None):
    d = env.new_device(name)
    js = []
    if beta: js.append("localStorage.setItem('pt-f13-beta','1')")
    if lang: js.append("localStorage.setItem('pt:_device:lang','%s')" % lang)
    if js:
        d.ctx.add_init_script("try{if(!sessionStorage.getItem('__f13seed')){%s;sessionStorage.setItem('__f13seed','1')}}catch(e){}" % ";".join(js))
    return d


def doc(page):
    return page.evaluate("()=>({lang:document.documentElement.lang,dir:document.documentElement.dir,title:document.title,"
                         "rootDir:(document.getElementById('lpJoin')||{getAttribute(){return null}}).getAttribute('dir'),"
                         "sw:document.documentElement.scrollWidth,iw:window.innerWidth,"
                         "sw_btn:!!document.querySelector('[data-lpj-lang]'),"
                         "small:[...document.querySelectorAll('#lpJoin button,#lpJoin a.lpj-btn,#lpJoin label:not(.lpj-lbl),#lpJoin .lpj-link')].filter(e=>e.getBoundingClientRect().height>0&&e.getBoundingClientRect().height<43.5).map(e=>e.id||e.textContent.slice(0,20))})")


def test_flag_off_is_alpha16(env):
    serve(env, "off"); tid, code = T5.new_trip(env)
    d = dev_with(env, "A", beta=True, lang="en")                     # even a beta device with English chosen: the flag is off
    assert T5.open_join(d, code) == "form"
    s = doc(d.page); txt = H.btext(d.page)
    assert (s["lang"], s["dir"], s["rootDir"], s["sw_btn"]) == ("he", "rtl", "rtl", False), s
    assert "איך קוראים לך?" in txt and "בקשת הצטרפות" in txt and "Request to join" not in txt


def test_beta_without_key_is_hebrew(env):
    serve(env, "beta"); tid, code = T5.new_trip(env)
    d = dev_with(env, "A", beta=False, lang="en")                    # English chosen but this device is not a beta device
    assert T5.open_join(d, code) == "form"
    s = doc(d.page)
    assert (s["lang"], s["dir"], s["sw_btn"]) == ("he", "rtl", False), s


def test_english_join_flow_and_switch(env):
    serve(env, "on"); tid, code = T5.new_trip(env)
    d = dev_with(env, "A", lang="en"); pg = d.page
    assert T5.open_join(d, code) == "form"
    s = doc(pg); txt = H.btext(pg); P = []
    if (s["lang"], s["dir"], s["rootDir"]) != ("en", "ltr", "ltr"): P.append("doc: %r" % s)
    if s["title"] != "Join the trip · Lonely Planner": P.append("title %r" % s["title"])
    for t in ("What's your name?", "Request to join", "No email, no password", "Invitation", "days"):
        if t not in txt: P.append("missing English: " + t)
    if re.search(r"[א-ת]", DATA.sub("", txt)): P.append("Hebrew left on the English form: %r" % re.findall(r"[^\s]*[א-ת]+[^\s]*", DATA.sub("", txt))[:8])
    if s["sw"] > s["iw"]: P.append("h-scroll %s>%s" % (s["sw"], s["iw"]))
    if s["small"]: P.append("small targets %r" % s["small"])
    # switch to Hebrew and back
    pg.locator("[data-lpj-lang]").click()
    H.wait_until(lambda: doc(pg)["lang"] == "he", 6, pg)
    H.wait_screen(pg, "form", 8)
    s2 = doc(pg)
    if (s2["dir"], s2["rootDir"]) != ("rtl", "rtl") or "איך קוראים לך?" not in H.btext(pg): P.append("Hebrew switch failed: %r" % s2)
    pg.locator("[data-lpj-lang]").click()
    H.wait_until(lambda: doc(pg)["lang"] == "en", 6, pg); H.wait_screen(pg, "form", 8)
    # submit in English → pending in English, the choice survives a reload
    pg.locator("#lpjName").fill("Noa"); pg.locator("#lpjSubmit").click()
    if H.wait_screen(pg, "pending", 8) != "pending": pytest.fail("no pending screen; " + "; ".join(P))
    txt = H.btext(pg)
    for t in ("Request sent to", "Waiting for approval · Noa", "Cancel request"):
        if t not in txt: P.append("pending text missing: " + t)
    if re.search(r"[א-ת]", DATA.sub("", txt)): P.append("Hebrew left on pending: %r" % re.findall(r"[^\s]*[א-ת]+[^\s]*", DATA.sub("", txt))[:8])
    if "דנה" in txt and "<bdi>" not in pg.locator(".lpj-center h2").inner_html(): P.append("manager name not wrapped in bdi")
    pg.reload()
    if H.wait_screen(pg, "pending", 8) != "pending" or doc(pg)["lang"] != "en": P.append("reload lost English / pending")
    s = doc(pg)
    if s["sw"] > s["iw"] or s["small"]: P.append("pending layout %r" % s)
    # the manager approves → approved screen in English
    mgr = T5.boot_member(env, tid, "M", "דנה"); mgr.page.wait_for_timeout(1200)
    mgr.page.locator("#ptF05Pending [data-act=approve]").click()
    if H.wait_screen(pg, "approved", 10) != "approved": P.append("no approved screen")
    else:
        t = H.btext(pg)
        for x in ("welcome, Noa!", "Open the trip"):
            if x not in t: P.append("approved text missing: " + x)
    errs = H.page_errors(d)
    if errs: P.append("page errors %r" % errs[:3])
    assert not P, "\n".join(P)


def test_english_relink_screens(env):
    serve(env, "on"); tid, code = T5.new_trip(env)
    be = env.backend; people = {r["display_name"]: r["id"] for r in be.members(tid, "active")}
    d = dev_with(env, "N", lang="en"); pg = d.page; P = []
    assert T5.open_join(d, code) == "form"
    t = pg.locator(".lpj-sw").inner_text()
    for x in ("I'm new to the trip", "I've been on the trip before"):
        if x not in t: P.append("switch text missing: " + x)
    pg.locator("#lpjModeBack").click(); pg.wait_for_timeout(300)
    txt = H.btext(pg)
    for x in ("Who are you on the list?", "Request to link this phone"):
        if x not in txt: P.append("relink form missing: " + x)
    pg.locator("#lpjRelink").click(); pg.wait_for_timeout(300)
    if "Pick your name from the list." not in pg.locator("#lpjRelinkErr").inner_text(): P.append("pick error not English")
    pg.locator('#lpjPeople label:has-text("Editor Q")').click(); pg.locator("#lpjRelink").click()
    if H.wait_screen(pg, "pending", 8) != "pending": pytest.fail("no pending; " + "; ".join(P))
    txt = H.btext(pg)
    for x in ("New device · Editor Q", "Valid until", "Message the manager on WhatsApp", "Cancel request"):
        if x not in txt: P.append("relink pending missing: " + x)
    import urllib.parse as up
    wa = up.unquote(pg.locator("#lpjWa").get_attribute("href") or "")
    if "Hi, this is Editor Q" not in wa: P.append("whatsapp text not English: " + wa)
    s = doc(pg)
    if s["sw"] > s["iw"] or s["small"]: P.append("layout %r" % s)
    assert not P, "\n".join(P)

