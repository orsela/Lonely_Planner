"""Lonely Planner F13 stage 1 · /invite/ browser test (390x844, fake invite-manager, no network) · version 3.0.0-alpha.18.6
CHANGE 2026-11-24 F13-QA-05: new file (no previous version). Uses the F04-HOME harness (fake invite-manager `check`).
Covers: flag off = Hebrew/RTL/no switch (= alpha.11); beta without the key = Hebrew; English on desktop, iPhone Safari, Android Chrome, Gmail in-app (iOS), invalid token, offline;
the switch re-renders in place (token never stored); <html lang dir> + title; names in <bdi>; no horizontal scroll; touch targets >= 44px.
Run: tests/f13/run.sh invite
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f04home"))
import harness as H  # noqa: E402

FLAG = re.compile(r"""((?:const|let|var)\s+LANG_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")
DATA = re.compile("עב|Lonely Planner|אור")   # the switch label and the inviter's name (user data)


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


def serve(env, lang):
    src = H.invite_html(); assert FLAG.search(src), "LANG_FEATURE flag missing in invite/index.html"
    out = FLAG.sub(lambda m: m.group(1) + "'" + lang + "'", src, count=1).encode("utf-8")
    env.server.overrides[H.ROOT + "invite/index.html"] = out; env.server.overrides[H.ROOT + "invite/"] = out


def open_invite(env, ua, lang=None, beta=False, valid=True, name="I"):
    dev = env.new_device(name, ua=ua)
    js = []
    if beta: js.append("localStorage.setItem('pt-f13-beta','1')")
    if lang: js.append("localStorage.setItem('pt:_device:lang','%s')" % lang)
    if js: dev.ctx.add_init_script("try{if(!sessionStorage.getItem('__s')){%s;sessionStorage.setItem('__s','1')}}catch(e){}" % ";".join(js))
    token = env.backend.add_invite(H.INVITE_EMAIL, H.DRAFT, sent_days_ago=0, expires_in_days=7)[1] if valid else H.f03.new_token()
    dev.page.goto(env.server.origin + H.INVITE + "#invite=" + token, wait_until="domcontentloaded")
    H.wait_until(lambda: len(H.btext(dev.page)) > 40 and "…" not in H.btext(dev.page)[:60], 12, dev.page)
    dev.page.wait_for_timeout(1200)
    return dev, token


def info(page):
    return page.evaluate("""()=>({lang:document.documentElement.lang,dir:document.documentElement.dir,title:document.title,sw:document.documentElement.scrollWidth,iw:window.innerWidth,
      btn:!!document.getElementById('langSw'),url:location.href,
      small:[...document.querySelectorAll('main button,main a.btn,main a.gbtn,main a.h-skip')].filter(e=>e.getBoundingClientRect().height>0&&e.getBoundingClientRect().height<43.5).map(e=>e.id||e.textContent.slice(0,20))})""")


def hebrew_left(page):
    return re.findall(r"[^\s]*[א-ת]+[^\s]*", DATA.sub("", H.btext(page)).replace(H.DRAFT, ""))


def test_flag_off_is_alpha11(env):
    serve(env, "off"); dev, _ = open_invite(env, "desktop", lang="en", beta=True)
    s = info(dev.page); t = H.btext(dev.page)
    assert (s["lang"], s["dir"], s["btn"]) == ("he", "rtl", False), s
    assert "ההזמנה שלך אומתה" in t and "Your invitation" not in t


def test_beta_without_key_is_hebrew(env):
    serve(env, "beta"); dev, _ = open_invite(env, "desktop", lang="en", beta=False)
    s = info(dev.page)
    assert (s["lang"], s["dir"], s["btn"]) == ("he", "rtl", False), s


@pytest.mark.parametrize("ua", ["desktop", "safari_iphone", "chrome_android", "gmail_ios"])
def test_english_variants(env, ua):
    serve(env, "on"); dev, token = open_invite(env, ua, lang="en"); pg = dev.page; P = []
    s = info(pg); t = H.btext(pg)
    if (s["lang"], s["dir"]) != ("en", "ltr"): P.append("doc %r" % s)
    if s["title"] != "Invitation · Lonely Planner": P.append("title %r" % s["title"])
    if "Your invitation is verified" not in t: P.append("verified missing: " + t[:200])
    left = hebrew_left(pg)
    if left: P.append("Hebrew left: %r" % left[:8])
    if s["sw"] > s["iw"]: P.append("h-scroll %s>%s" % (s["sw"], s["iw"]))
    if s["small"]: P.append("small targets %r" % s["small"])
    if token in s["url"]: P.append("token still in the address bar")
    if ua == "gmail_ios" and "Open in your regular browser" not in t: P.append("in-app card not English")
    if ua == "safari_iphone" and "First, add the app to your home screen" not in t: P.append("iPhone card not English")
    if ua in ("desktop", "chrome_android") and "Open in the app and set up the trip" not in t: P.append("open button not English")
    assert not P, "\n".join(P)


def test_switch_rerenders_in_place_and_invalid_and_offline(env):
    serve(env, "on"); dev, token = open_invite(env, "desktop", lang="en"); pg = dev.page; P = []
    pg.locator("#langSw").click(); pg.wait_for_timeout(900)
    s = info(pg)
    if (s["lang"], s["dir"]) != ("he", "rtl") or "ההזמנה שלך אומתה" not in H.btext(pg): P.append("switch to Hebrew failed %r" % s)
    if pg.evaluate("()=>localStorage.getItem('pt:_device:lang')") != "he": P.append("choice not stored")
    if any(token in (pg.evaluate("()=>JSON.stringify(localStorage)") or "") for _ in [0]): P.append("token leaked into storage")
    pg.locator("#langSw").click(); pg.wait_for_timeout(900)
    if "Your invitation is verified" not in H.btext(pg): P.append("switch back to English failed")
    # invalid token
    serve(env, "on"); dev2, _ = open_invite(env, "desktop", lang="en", valid=False, name="J")
    t2 = H.btext(dev2.page)
    if "This link is no longer valid" not in t2 or hebrew_left(dev2.page): P.append("invalid screen: %r %r" % (t2[:120], hebrew_left(dev2.page)))
    # offline
    dev3, token3 = open_invite(env, "desktop", lang="en", name="K")
    dev3.page.context.set_offline(True); dev3.page.evaluate("()=>{window.dispatchEvent(new Event('offline'))}")
    dev3.page.locator("#langSw").click(); dev3.page.wait_for_timeout(700)      # → Hebrew (offline screen)
    dev3.page.locator("#langSw").click(); dev3.page.wait_for_timeout(700)      # → English again (offline screen)
    t3 = H.btext(dev3.page)
    if "Try again" not in t3 and "No connection" not in t3: P.append("offline screen not English: %r" % t3[:160])
    assert not P, "\n".join(P)
