"""Lonely Planner F13 stage 2 · the trip wizard offers "English" as the group language (390x844, fake backend) · version 3.0.0-alpha.18.8
CHANGE 2026-11-24 F13-QA-11: new file (no previous version). Uses the F04-HOME harness (token link → code → step 1). Covers: a normal device (flag 'beta', no key) = English disabled with "בקרוב" and the
create-trip payload says default_lang 'he' (= alpha.18.7); a beta device = English selectable, and choosing it sends default_lang 'en'; flag 'off' even on a beta device = disabled.
The server side (migration 0025_f13.sql) was checked on the live project with SQL (condition present, grants unchanged) — see the CHANGELOG.
Run: tests/f13/run.sh wizard
"""
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f04home"))
import harness as H  # noqa: E402
import test_f04home as T  # noqa: E402
from harness import f04  # noqa: E402

FLAG = re.compile(r"""((?:const|let|var)\s+LANG_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")


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


def flag(env, value):
    src = H.app_html(); assert FLAG.search(src)
    out = FLAG.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1).encode("utf-8")
    env.server.overrides[H.APP + "index.html"] = out; env.server.overrides[H.APP] = out


def to_step1(env, beta, name):
    _, token = env.backend.add_invite(T.EMAIL, T.DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device(name, ua="desktop")
    if beta:
        dev.ctx.add_init_script("try{localStorage.setItem('pt-f13-beta','1');localStorage.setItem('pt:_device:lang','he')}catch(e){}")   # beta device, Hebrew UI
    bodies = []
    dev.page.on("request", lambda r: bodies.append(r.post_data or "") if "create-trip" in r.url and r.method == "POST" else None)
    dev.page.goto(env.server.origin + H.APP + "?invite=1#invite=" + token, wait_until="domcontentloaded")
    assert H.wait_screen(dev.page, ["code", "step1"], 20) == "code"
    H.type_code(dev.page, env.backend.otp_code)
    assert H.wait_screen(dev.page, "step1", 15) == "step1"
    return dev, bodies


def seg(page):
    return page.evaluate("""()=>[...document.querySelectorAll('#ptWzLang button')].map(b=>({t:b.textContent.trim(),dis:b.disabled,on:b.getAttribute('aria-pressed')}))""")


def create_lang(dev, bodies):
    page = dev.page
    f04.fill_step1(page, me="דנה", start="2027-04-03", end="2027-04-20"); f04.press_next(page)
    assert H.wait_screen(page, "step2") == "step2"
    f04.pick(page, "יפ", "JP"); f04.press_next(page)
    assert H.wait_screen(page, "step3") == "step3"
    try:
        f04.create_and_done(dev)
    except Exception:
        pass                                   # the fake create-trip of the F04 harness only knows 'he'; the request is what we check
    page.wait_for_timeout(700)
    for b in bodies:
        try:
            j = json.loads(b); j = j.get("payload", j)
            if "default_lang" in j: return j["default_lang"]
        except Exception:
            continue
    return None


def test_normal_device_english_stays_disabled(env):
    flag(env, "beta"); dev, bodies = to_step1(env, beta=False, name="N")
    s = seg(dev.page)
    assert [x["dis"] for x in s] == [False, True] and "בקרוב" in s[1]["t"], s
    assert create_lang(dev, bodies) == "he"


def test_beta_device_can_choose_english(env):
    flag(env, "beta"); dev, bodies = to_step1(env, beta=True, name="B")
    s = seg(dev.page)
    assert [x["dis"] for x in s] == [False, False] and "בקרוב" not in s[1]["t"], s
    dev.page.locator('#ptWzLang [data-lang="en"]').click()
    s = seg(dev.page)
    assert [x["on"] for x in s] == ["false", "true"], s
    assert create_lang(dev, bodies) == "en"


def test_flag_off_even_on_a_beta_device(env):
    flag(env, "off"); dev, bodies = to_step1(env, beta=True, name="O")
    s = seg(dev.page)
    assert [x["dis"] for x in s] == [False, True], s
    assert create_lang(dev, bodies) == "he"
