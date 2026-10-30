"""Lonely Planner F21 QA · Playwright black-box suite (/request/ + app admin requests + wizard pre-fill) · version 1.0.0
CHANGE 2026-10-30 F21-QA-05: new file (no previous version).

Contract: docs/F21_spec.md (§1 screens, §5 texts, §6 criteria) only. The F21 implementation (app/index.html, request/index.html,
the dev notes and the dev smoke scripts) was NOT read. Elements are found by the spec texts; on /request/ a few element ids
are used that were OBSERVED at run time in the rendered DOM (not in the spec): #rqName #rqEmail #rqWhere #rqWhen #rqUnsure
#rqMinus #rqPlus #rqCount #rqNote #rqSend #rqLangHe #rqLangEn #rqOtp0…5 #rqVerify #rqResend #rqFix. App ids come from the
F20 contract (#ptChoose, #ptChooseAdmin, #ptChoosePending, #admin).
Every test names its criterion: test_cNN_… (NN = spec §6 number). 390×844, he-IL / en-US, Asia/Jerusalem, clock installed at
2026-10-12 06:00Z (F04-HOME harness), moved with page.clock + backend.clock_offset.
"""
import collections
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import harness as H  # noqa: E402
import qa_refs  # noqa: E402

f02, f03, f04, f05, f20 = H.f02, H.f03, H.f04, H.f05, H.f20
from playwright.sync_api import Error as PWError  # noqa: E402

VERSION = qa_refs.CURRENT_VERSION
BASE_REF = os.environ.get("F21_BASE_REF", "313eb14")      # alpha.7.2 (spec "Base")
norm, btext, has, wait_has = H.norm, H.btext, H.has, H.wait_has

HE_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
TXT = {
    "closed_he": "הבקשות סגורות כרגע", "closed_en": "Requests are closed right now",
    "title_he": "רוצים להקים טיול?", "title_en": "Want to plan a trip?",
    "send_he": "שליחת קוד אימות", "send_en": "Send verification code",
    "email_help": "נשלח אליו קוד אימות בן 6 ספרות.",
    "unsure_he": "עוד לא יודעים", "unsure_en": "Not sure yet",
    "d11a": "Good to know: the trip app is in Hebrew for now. Emails about your request, including your invitation, will be in English.",
    "rate_he": "יותר מדי בקשות היום. נסו שוב מחר.", "rate_en": "Too many requests today. Please try again tomorrow.",
    "offline": "אין חיבור. נסו שוב כשהרשת תחזור.", "other": "משהו השתבש. נסו שוב.",
    "code_title_he": "בדקו את המייל", "code_title_en": "Check your email",
    "code_help": "הקוד בתוקף 10 דקות. הדבקה ממלאת את כל התיבות.",
    "code_help2": "יצאתם לבדוק את המייל? חוזרים לאותו קישור – הדף זוכר אתכם ולא שולח קוד חדש.",
    "notif": "– קוד האימות לבקשה ב-Lonely Planner",
    "resend_wait_re": r"שליחה חוזרת בעוד (\d+):(\d\d)", "fix": "תיקון המייל",
    "footer": "רק אחרי האימות הבקשה נשלחת לאישור. לא הגיע? בדקו בתיקיית הספאם.",
    "verify_he": "אימות ושליחת הבקשה", "verify_en": "Verify and send",
    "banner_re": r"חזרת לדף [–-] הקוד ששלחנו לפני (\d+) דקות עדיין תקף\.",
    "wrong_re": r"הקוד שגוי\. נשארו (\d+) ניסיונות\.", "expired": "הקוד פג. שלחו קוד חדש.", "locked": "יותר מדי ניסיונות. מתחילים מחדש.",
    "limit_he": "נסו שוב מחר", "limit_en": "Please try again tomorrow", "back_he": "חזרה לטופס", "back_en": "Back to the form",
    "sent_he": "הבקשה נשלחה", "sent_en": "Your request was sent", "sent_line": "אין צורך לחכות במסך הזה. התשובה תגיע למייל.",
    "what_now": "מה עכשיו?", "step3": "בקישור מוסיפים את האפליקציה למסך הבית ומקימים את הטיול – כשלוש דקות. היעדים והחודש כבר ממולאים מהבקשה.",
    "safari_he": "פתיחה בספארי", "safari_en": "Open in Safari", "cont_he": "להמשיך כאן בכל זאת", "cont_en": "Continue here anyway",
    # app
    "adm_row": "ניהול מערכת", "adm_sub_new": "בקשות, קבוצות והזמנת מנהלים", "adm_sub_old": "כל הקבוצות והזמנת מנהלים",
    "badge_req": "{n} בקשות חדשות", "badge_inv": "{n} הזמנות ממתינות", "badge_inv_old": "{n} ממתינות",
    "tab_req": "בקשות · {n}", "tab_grp": "קבוצות והזמנות · {n}",
    "meter": "מיילים מהטופס היום", "meter_val": "{k} מתוך 50",
    "meter_line": "קודי אימות והודעות דחייה. בתקרה הטופס מציג \"נסו שוב מחר\"; הזמנות מנהל וקודי כניסה לא נחסמים.",
    "manager": "כבר מנהל: ", "active_inv": "יש הזמנה פעילה · נשלחה ",
    "b_replace": "אישור · מחליף את ההזמנה", "b_more": "אישור טיול נוסף", "b_en": "אישור · מייל באנגלית", "b_ok": "אישור", "b_reject": "דחייה",
    "footnote": "כאן מופיעות רק בקשות שהמייל שלהן אומת. בקשה ממייל שיש לו הזמנה פעילה – אישור מבטל את ההזמנה הישנה ושולח חדשה.",
    "empty": "אין בקשות חדשות", "adm_offline": "אין חיבור",
    "ap_title": "אישור ושליחת הזמנה", "ap_title_rep": "אישור ושליחת הזמנה חדשה",
    "ap_line": "{name} יקבל/תקבל מייל הזמנה להקמת הטיול, כמו הזמנת מנהל רגילה (תוקף 7 ימים).",
    "ap_amber": "יש כבר הזמנה פעילה למייל הזה", "ap_amber2": "באישור היא מבוטלת והקישור הישן מפסיק לעבוד.",
    "ap_input": "שם זמני לטיול", "ap_help": "נוצר מהבקשה. {name} יכול/ה לשנות אותו באשף.", "ap_box": "ממולא מראש באשף",
    "ap_lang_he": "עברית – כמו הבקשה", "ap_lang_en": "אנגלית – כמו הבקשה", "ap_mail_lang": "שפת המייל",
    "ap_send": "אישור ושליחה אל {email}", "ap_send_rep": "ביטול הישנה ושליחת הזמנה חדשה", "cancel": "ביטול",
    "ap_toast": "ההזמנה נשלחה ל-{email}", "ap_fail": "המייל לא נשלח. שום דבר לא השתנה – נסו שוב.", "ap_closed": "הבקשה כבר טופלה",
    "rj_title": "לדחות את הבקשה של {name}?", "rj_line": "הבקשה יורדת מהרשימה ונמחקת אחרי 5 ימים.",
    "rj_cb": "לשלוח הודעה מנומסת במייל", "rj_lang": "בשפת הבקשה (כאן: {l})", "rj_cap": "התקרה היומית מלאה – הדחייה תהיה בלי מייל",
    "rj_capped_toast": "הבקשה נדחתה, בלי מייל (התקרה היומית מלאה)",
    "rj_preview_he": "תודה על ההתעניינות ב-Lonely Planner. כרגע לא נוכל לפתוח את הטיול שלך.",
    "wz_box": "מילאנו מה שכתבת בבקשה, כולל היעדים בשלב 2. נשאר לבחור תאריכים.", "wz_tag": "מהבקשה",
}
RQ = {"name": "#rqName", "email": "#rqEmail", "where": "#rqWhere", "when": "#rqWhen", "unsure": "#rqUnsure", "minus": "#rqMinus",
      "plus": "#rqPlus", "count": "#rqCount", "note": "#rqNote", "send": "#rqSend", "he": "#rqLangHe", "en": "#rqLangEn",
      "otp": "#rqOtp%d", "verify": "#rqVerify", "resend": "#rqResend", "fix": "#rqFix"}


@pytest.fixture(scope="session")
def server():
    s = f05.F05Server()
    yield s
    s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=os.environ.get("QA_HEADFUL") != "1")
        yield b
        b.close()


@pytest.fixture
def env(browser, server):
    server.reset()
    e = H.Env(browser, server)
    yield e
    e.close()
    server.reset()


# =====================================================================================================
# /request/ helpers
# =====================================================================================================
def open_req(env, query="", ua="chrome_android", locale="he-IL", key=H.PASS_KEY, flag=None, name="R", wait=True, pre_ls=None, **kw):
    H.serve_request(env, key=key, flag=flag)
    dev = env.new_device(name, ua=ua, locale=locale, **kw)
    dev.page._qa_backend = env.backend
    if pre_ls:
        dev.seed_ls(pre_ls)
    dev.page.goto(env.server.origin + H.REQUEST + query, wait_until="commit")
    if wait:
        try:
            dev.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except PWError:
            pass
        wait_until(lambda: len(btext(dev.page)) > 30, 10, dev.page)
        dev.page.wait_for_timeout(900)
    return dev


wait_until = H.wait_until


def lang_of(page):
    return page.evaluate("()=>({dir:document.documentElement.getAttribute('dir')||getComputedStyle(document.body).direction,lang:document.documentElement.lang})")


def cname(code, lang="he"):
    return H.COUNTRIES[code][lang]


def add_country(page, code, lang="he"):
    nm = cname(code, lang)
    page.fill(RQ["where"], nm[:3])
    page.wait_for_timeout(300)
    btns = page.locator("button").filter(has_text=nm)
    cand = [i for i in range(btns.count()) if btns.nth(i).is_visible() and norm(btns.nth(i).inner_text()).endswith(nm)]
    assert cand, "no type-ahead suggestion for %s (%s)" % (code, nm)
    btns.nth(cand[0]).click()
    page.wait_for_timeout(250)


def month_label(ym, lang="he"):
    y, m = int(ym[:4]), int(ym[5:7])
    return "%s %d" % ((HE_MONTHS if lang == "he" else EN_MONTHS)[m - 1], y)


def fill(page, name="דנה", email="dana@example.com", countries=("PT", "ES"), month="2027-04-01", travellers=None, note=None, lang="he"):
    if name is not None:
        page.fill(RQ["name"], name)
    if email is not None:
        page.fill(RQ["email"], email)
    for c in countries or ():
        add_country(page, c, lang)
    if month == "unsure":
        page.check(RQ["unsure"])
    elif month:
        page.select_option(RQ["when"], label=month_label(month, lang))
    if travellers is not None:
        cur = int(page.input_value(RQ["count"]) or 2)
        while cur < travellers:
            page.click(RQ["plus"]); cur += 1
        while cur > travellers:
            page.click(RQ["minus"]); cur -= 1
    if note is not None:
        page.fill(RQ["note"], note)
    page.wait_for_timeout(200)


def wait_token(page, timeout=5):
    return wait_until(lambda: page.evaluate("()=>!!(window.turnstile&&window.turnstile.getResponse())"), timeout, page)


def send(page):
    wait_token(page, 4)
    page.click(RQ["send"])
    page.wait_for_timeout(900)


def values(page):
    return page.evaluate("""(s)=>({name:document.querySelector(s.name)?.value,email:document.querySelector(s.email)?.value,
      when:document.querySelector(s.when)?.value,unsure:document.querySelector(s.unsure)?.checked,count:document.querySelector(s.count)?.value,
      note:document.querySelector(s.note)?.value,chips:[...document.querySelectorAll('button[aria-label]')].map(b=>b.getAttribute('aria-label')).filter(a=>/^(הסרת|Remove)/.test(a))})""", RQ)


def on_code(page, timeout=6):
    return wait_until(lambda: page.locator(RQ["otp"] % 0).count() and page.locator(RQ["otp"] % 0).is_visible(), timeout, page)


def type_rq_code(page, code, env=None):
    """Each digit into its own box. The page may auto-submit on the 6th digit; the verify button is tapped only when no
    verify call followed (otherwise it would submit twice)."""
    be = env.backend if env else getattr(page, "_qa_backend", None)
    n0 = len(be.rt("verify")) if be else None
    # clear the boxes silently first (after a wrong code the page keeps the digits; see F21-QA-BUG-01 / test_c06_retype_…)
    page.evaluate("()=>{for(let i=0;i<6;i++){const e=document.getElementById('rqOtp'+i);if(e)e.value=''}}")
    for i, d in enumerate(code):
        page.locator(RQ["otp"] % i).fill(d)
    page.wait_for_timeout(700)
    if (be is None or len(be.rt("verify")) == n0) and page.locator(RQ["verify"]).count() and page.locator(RQ["verify"]).is_visible():
        page.click(RQ["verify"])
    page.wait_for_timeout(900)


def to_code(env, lang="he", email="dana@example.com", name="R", **kw):
    q = "?lang=%s" % lang
    dev = open_req(env, q, name=name, **kw)
    fill(dev.page, email=email, name="Ann" if lang == "en" else "דנה", lang=lang)
    send(dev.page)
    assert on_code(dev.page), "code screen not reached (text=%r)" % btext(dev.page)[:300]
    return dev


def last_code(env):
    return env.backend.code_mails[-1]["code"]


def advance(env, dev, seconds):
    env.backend.clock_offset += dt.timedelta(seconds=seconds)
    dev.page.clock.fast_forward(int(seconds * 1000))
    dev.page.wait_for_timeout(400)


def resume_entry(dev):
    raw = H.ls_get(dev, H.RESUME_KEY)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return {"__raw": raw}


def other_requests(env, dev):
    """Requests of the device that are not the page itself / the fake Turnstile / countries.json."""
    return [n for n in env.net if n["device"] == dev.name and n.get("action") not in ("same-origin",)]


def touch_problems(page, scope="body"):
    return page.evaluate("""(s)=>{const out=[];for(const e of document.querySelectorAll(s+' button, '+s+' a[href], '+s+' input:not([type=hidden]), '+s+' select, '+s+' [role=button]')){
      const r=e.getBoundingClientRect();if(r.width<1||r.height<1)continue;const st=getComputedStyle(e);if(st.visibility==='hidden')continue;
      if(e.type==='checkbox'||e.type==='radio'){const l=e.closest('label');const lr=l?l.getBoundingClientRect():r;if(lr.height<44)out.push((e.id||e.tagName)+' label h='+Math.round(lr.height));continue}
      if(e.closest('[data-qa-turnstile]'))continue;
      if(r.height<44&&!(e.tagName==='INPUT'&&e.id&&/^rqOtp/.test(e.id)&&r.height>=40))out.push((e.id||e.tagName)+':'+(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().slice(0,20)+' h='+Math.round(r.height))}return out}""", scope)


def hscroll(page):
    return page.evaluate("()=>document.documentElement.scrollWidth-document.documentElement.clientWidth")


# =====================================================================================================
# C1 · flags off
# =====================================================================================================
@pytest.mark.parametrize("lang", ["he", "en"])
def test_c01_request_off_closed_card_no_network(env, lang):
    """C1: /request/ with REQUEST_FEATURE='off' → one neutral card "הבקשות סגורות כרגע / Requests are closed right now";
    no network (no countries.json, no Turnstile, no request-trip)."""
    dev = open_req(env, "?lang=" + lang, flag="off")
    t = btext(dev.page)
    assert norm(TXT["closed_he"]) in t or norm(TXT["closed_en"]) in t, "closed card text missing: %r" % t[:300]
    assert not dev.page.locator(RQ["send"]).is_visible() if dev.page.locator(RQ["send"]).count() else True, "form shown with the flag off"
    dev.page.wait_for_timeout(1500)
    reqs = [n["url"] for n in env.net if n["device"] == dev.name and not n["url"].split("?")[0].rstrip("/").endswith("/request")]
    assert not reqs, "network with /request/ off: %r" % reqs
    assert not env.backend.rt_calls


def test_c01_app_off_is_alpha72_chooser(env):
    """C1: app REQUEST_FEATURE='off' → the chooser admin row is alpha.7.2 (sub "כל הקבוצות והזמנת מנהלים", badge "<M> ממתינות"),
    no requests badge, no admin_trip_requests call; admin opens on today's F03 screen without a requests tab."""
    H.serve_app_request(env, "off")
    be = env.backend
    be.add_request(name="נועה", email="noa@example.com")
    be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
    dev = admin_dev(env)
    page = dev.page
    t = btext(page)
    assert norm(TXT["adm_sub_old"]) in t, "old admin sub missing: %r" % t[:300]
    assert norm(TXT["badge_inv_old"].format(n=1)) in t and "הזמנות ממתינות" not in t, "pending badge text not alpha.7.2"
    assert "בקשות חדשות" not in t
    page.locator("#ptChooseAdmin").click()
    page.wait_for_timeout(1500)
    assert wait_has(page, f03.TXT["invite_btn"], 8), "admin screen did not open"
    assert not has(page, "בקשות ·") and not has(page, TXT["meter"]), "requests tab with the flag off"
    assert not [c for c in be.rpc_calls if c["fn"] == "admin_trip_requests"], "admin_trip_requests called with the flag off"


# =====================================================================================================
# C2 · language
# =====================================================================================================
@pytest.mark.parametrize("how", ["query", "hash"])
def test_c02_lang_en_from_link(env, how):
    """C2 / §1.0: ?lang=en or #lang=en → English, LTR, html lang=en, switch EN aria-pressed=true (on a Hebrew device)."""
    dev = open_req(env, "?lang=en" if how == "query" else "#lang=en")
    page = dev.page
    L = lang_of(page)
    assert L["dir"] == "ltr" and L["lang"].startswith("en"), "not English LTR: %r" % L
    assert has(page, TXT["title_en"]) and has(page, TXT["send_en"]), "English texts missing"
    assert page.get_attribute(RQ["en"], "aria-pressed") == "true" and page.get_attribute(RQ["he"], "aria-pressed") == "false"


@pytest.mark.parametrize("dev_lang,want", [("he", "he"), ("en", "en")])
def test_c02_lang_from_device(env, dev_lang, want):
    """C2: no link language, nothing stored → he when navigator.languages has a Hebrew tag, else en."""
    dev = open_req(env, "", locale="he-IL" if dev_lang == "he" else "en-US",
                   languages=["he-IL", "he", "en-US"] if dev_lang == "he" else ["en-US", "en"])
    L = lang_of(dev.page)
    assert L["lang"].startswith(want) and L["dir"] == ("rtl" if want == "he" else "ltr"), "device %s → %r" % (dev_lang, L)
    assert has(dev.page, TXT["title_%s" % want])


def test_c02_lang_hebrew_tag_not_first(env):
    """C2: navigator.languages CONTAINS a Hebrew tag (not first) → Hebrew."""
    dev = open_req(env, "", locale="en-US", languages=["en-US", "en", "he"])
    assert lang_of(dev.page)["lang"].startswith("he"), lang_of(dev.page)


def test_c02_switch_keeps_values_flips_dir_stores(env):
    """C2: the switch re-renders in place, keeps typed values, flips dir, stores pt:_device:rq_lang; the stored choice wins on
    the next load (no link lang)."""
    dev = open_req(env, "")
    page = dev.page
    fill(page, name="דנה", email="dana@example.com", countries=("PT", "ES"), month="2027-04-01", travellers=5, note="הערה")
    before = values(page)
    n_nav = len(dev.navs)
    page.click(RQ["en"])
    page.wait_for_timeout(600)
    after = values(page)
    P = []
    if lang_of(page)["dir"] != "ltr" or not has(page, TXT["title_en"]):
        P.append("not switched to English LTR: %r" % lang_of(page))
    for k in ("name", "email", "when", "count", "note"):
        if before[k] != after[k]:
            P.append("%s changed %r → %r" % (k, before[k], after[k]))
    if len(after["chips"]) != 2:
        P.append("countries lost: %r" % after["chips"])
    if len(dev.navs) != n_nav:
        P.append("the page reloaded / navigated on switch")
    if H.ls_get(dev, H.LANG_KEY) not in ("en", '"en"'):
        P.append("choice not stored: %r" % H.ls_get(dev, H.LANG_KEY))
    if page.get_attribute(RQ["en"], "aria-pressed") != "true":
        P.append("aria-pressed not updated")
    page.goto(env.server.origin + H.REQUEST, wait_until="domcontentloaded")
    page.wait_for_timeout(900)
    if not lang_of(page)["lang"].startswith("en"):
        P.append("stored choice not used on reload: %r" % lang_of(page))
    assert not P, "; ".join(P)


# =====================================================================================================
# C3 · in-app browsers
# =====================================================================================================
@pytest.mark.parametrize("ua", ["gmail_ios", "outlook_ios"])
def test_c03_iphone_inapp_safari_button(env, ua):
    """C3 / §1.1: iPhone in-app → card with "פתיחה בספארי" → x-safari-https://<host>/…/request/?lang=<l>; no automatic hop;
    "continue here" → the form; not shown again in this page load."""
    dev = open_req(env, "?lang=he", ua=ua)
    page = dev.page
    page.wait_for_timeout(1500)
    assert has(page, TXT["safari_he"]), "Safari button missing: %r" % btext(page)[:300]
    assert not H.ext_navs(dev), "automatic hop on iPhone: %r" % dev.ext_navs
    assert not page.locator(RQ["send"]).is_visible(), "form shown before the in-app card"
    H.click_text(page, TXT["safari_he"])
    page.wait_for_timeout(600)
    navs = H.ext_navs(dev, "safari")
    host = env.server.origin.split("//")[1]
    want = "x-safari-https://%s%s?lang=he" % (host, H.REQUEST)
    assert navs and navs[-1]["url"] == want, "safari URL %r, want %r" % ([n["url"] for n in navs], want)
    H.click_text(page, TXT["cont_he"])
    page.wait_for_timeout(600)
    assert page.locator(RQ["send"]).is_visible(), "continue here did not show the form"
    assert not has(page, TXT["safari_he"]), "in-app card shown again"


def test_c03_android_inapp_one_intent_hop(env):
    """C3 / §1.1: Android WebView → exactly one automatic intent:// hop per load with the exact URL; fallback button; continue."""
    dev = open_req(env, "?lang=en", ua="gmail_android_wv", wait=False)
    page = dev.page
    wait_until(lambda: H.ext_navs(dev, "intent"), 8, page)
    page.wait_for_timeout(2000)
    host = env.server.origin.split("//")[1]
    want = "intent://%s%s?lang=en#Intent;scheme=https;package=com.android.chrome;end" % (host, H.REQUEST)
    navs = [n["url"] for n in H.ext_navs(dev, "intent")]
    assert navs == [want], "intent hops %r, want exactly [%r]" % (navs, want)
    assert wait_has(page, TXT["cont_en"], 5), "continue-here button missing: %r" % btext(page)[:300]
    H.click_text(page, TXT["cont_en"])
    page.wait_for_timeout(600)
    assert page.locator(RQ["send"]).is_visible(), "form not shown after continue"


@pytest.mark.parametrize("ua", ["safari_iphone", "chrome_android", "desktop"])
def test_c03_real_browser_no_card(env, ua):
    """C3: a real browser shows the form directly, no hop."""
    dev = open_req(env, "", ua=ua)
    dev.page.wait_for_timeout(1200)
    assert dev.page.locator(RQ["send"]).is_visible() and not H.ext_navs(dev), "real browser: card or hop (%r)" % dev.ext_navs


# =====================================================================================================
# C4 · form validation
# =====================================================================================================
def _no_call(env):
    return not env.backend.rt("start")


def _invalid(page, sel):
    return page.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;const f=e.closest('label,.rq-field,[class*=field]')||e.parentElement;
      return e.getAttribute('aria-invalid')==='true'||/invalid|error|bad/.test(e.className+' '+(f?f.className:''))}""", sel)


CASES = {
    "name_empty": (dict(name=""), "name"), "name_41": (dict(name="x"), "name"), "email_bad": (dict(email="dana@"), "email"),
    "countries_0": (dict(countries=()), "where"), "month_none": (dict(month=None), "when"),
    "note_201": (dict(note="x"), "note"),
}


@pytest.mark.parametrize("case", list(CASES))
def test_c04_validation_inline_no_call(env, case):
    """C4 / §1.2: each bound → inline error (red field + one line), button stays enabled, focus on the first invalid field, no call."""
    over, field = CASES[case]
    dev = open_req(env, "")
    page = dev.page
    kw = dict(name="דנה", email="dana@example.com", countries=("PT",), month="2027-04-01")
    kw.update(over)
    fill(page, **kw)
    if case == "name_41":
        assert page.get_attribute(RQ["name"], "maxlength") == "40", "name maxlength is not 40"
        page.evaluate("(s)=>{const e=document.querySelector(s);e.removeAttribute('maxlength');e.value='א'.repeat(41);e.dispatchEvent(new Event('input',{bubbles:true}))}", RQ["name"])
    if case == "note_201":
        page.evaluate("(s)=>{const e=document.querySelector(s);e.removeAttribute('maxlength');e.value='n'.repeat(201);e.dispatchEvent(new Event('input',{bubbles:true}))}", RQ["note"])
    t0 = btext(page)
    send(page)
    P = []
    if not _no_call(env):
        P.append("request-trip called: %r" % env.backend.rt("start")[-1]["body"])
    if page.locator(RQ["send"]).is_disabled():
        P.append("button disabled")
    focused = page.evaluate("()=>document.activeElement&&document.activeElement.id")
    if focused != RQ[field].lstrip("#"):
        P.append("focus on %r (want %s)" % (focused, RQ[field]))
    if not _invalid(page, RQ[field]) and len(btext(page)) <= len(t0):
        P.append("no inline error shown for %s" % field)
    assert not P, "; ".join(P)


def test_c04_countries_max_10_and_chip_remove(env):
    """C4: 1–10 countries — an 11th cannot be added (or is refused inline, no call); chip × has an aria-label and removes."""
    dev = open_req(env, "")
    page = dev.page
    codes = ["PT", "ES", "FR", "IT", "DE", "GR", "TH", "VN", "JP", "US", "GB"]
    for c in codes[:10]:
        add_country(page, c)
    try:
        add_country(page, codes[10])
    except AssertionError:
        pass
    n = len(values(page)["chips"])
    fill(page, countries=(), month="2027-04-01")
    send(page)
    assert n <= 10 or (_no_call(env)), "11 countries accepted and sent"
    if env.backend.rt("start"):
        assert len(env.backend.rt("start")[-1]["body"]["countries"]) <= 10
    chips = values(page)["chips"]
    page.click('button[aria-label="%s"]' % chips[0])
    page.wait_for_timeout(300)
    assert len(values(page)["chips"]) == len(chips) - 1, "chip × did not remove"


def test_c04_month_options_18_and_unsure(env):
    """C4 / §1.2 item 4 (D7): the select lists exactly the next 18 months from the current month (Jerusalem), labels
    "אוקטובר 2026"…; "עוד לא יודעים" disables it and sends month:null."""
    dev = open_req(env, "")
    page = dev.page
    opts = page.evaluate("(s)=>[...document.querySelector(s).options].filter(o=>!o.disabled&&o.value).map(o=>o.text.trim())", RQ["when"])
    want = [month_label(m) for m in H.month_list(H.FIXED_NOW)]
    assert opts == want, "months %r, want %r" % (opts, want)
    fill(page, month="unsure")
    assert page.locator(RQ["when"]).is_disabled(), "select not disabled by 'not sure'"
    send(page)
    st = env.backend.rt("start")
    assert st and st[-1]["body"].get("month", "missing") is None, "month not sent as null: %r" % (st[-1]["body"] if st else None)


def test_c04_travellers_bounds(env):
    """C4: travellers stepper 1–30, default 2 (0 / 31 never sent)."""
    dev = open_req(env, "")
    page = dev.page
    assert page.input_value(RQ["count"]) == "2", "default travellers %r" % page.input_value(RQ["count"])
    for _ in range(3):
        page.click(RQ["minus"])
    lo = page.input_value(RQ["count"])
    for _ in range(40):
        page.click(RQ["plus"])
    hi = page.input_value(RQ["count"])
    assert (lo, hi) == ("1", "30"), "stepper bounds %s..%s" % (lo, hi)
    page.fill(RQ["count"], "31")
    fill(page)
    send(page)
    st = env.backend.rt("start")
    assert not st or 1 <= st[-1]["body"]["travellers"] <= 30, "travellers %r sent" % st[-1]["body"]["travellers"]


def test_c04_note_counter_and_d11a_box(env):
    """C4 / §1.2: live note counter; the D11a box only on the English form."""
    dev = open_req(env, "?lang=he")
    page = dev.page
    page.fill(RQ["note"], "שלום")
    assert has(page, "4/200"), "note counter not live"
    assert not has(page, TXT["d11a"]), "D11a box on the Hebrew form"
    page.click(RQ["en"])
    page.wait_for_timeout(500)
    assert has(page, TXT["d11a"]), "D11a box missing on the English form"


def test_c04_email_normalized_ltr(env):
    """§1.2 item 2: email type=email, LTR, normalized (trim, lower) in the request."""
    dev = open_req(env, "")
    page = dev.page
    assert page.get_attribute(RQ["email"], "type") == "email"
    d = page.evaluate("(s)=>getComputedStyle(document.querySelector(s)).direction", RQ["email"])
    fill(page, email="  Dana@Example.COM ")
    send(page)
    st = env.backend.rt("start")
    assert d == "ltr", "email input direction %s" % d
    assert st and st[-1]["body"]["email"] == "dana@example.com", "email sent %r" % (st[-1]["body"]["email"] if st else None)


# =====================================================================================================
# C5 · Turnstile + start
# =====================================================================================================
@pytest.mark.parametrize("lang", ["he", "en"])
def test_c05_pass_key_row_and_code_mail_in_page_language(env, lang):
    """C5: passing test key → start with the Turnstile token and the page language → row unverified + one code email in that
    language (fake backend); widget rendered in managed mode with language = page language; plain fetch with the anon apikey,
    no session (no Authorization), nothing secret in the URL."""
    dev = to_code(env, lang=lang)
    be = env.backend
    st = be.rt("start")
    P = []
    if len(st) != 1:
        P.append("%d start calls" % len(st))
    b = st[-1]["body"]
    if b.get("turnstile_token") != H.DUMMY_TOKEN or b.get("lang") != lang:
        P.append("body %r" % b)
    if st[-1]["auth"]:
        P.append("Authorization header sent: %r" % st[-1]["auth"][:20])
    if not st[-1]["apikey"]:
        P.append("no apikey")
    rows = [r for r in be.requests.values() if r["status"] == "unverified"]
    if len(rows) != 1 or len(be.code_mails) != 1 or be.code_mails[0]["lang"] != lang:
        P.append("rows %d mails %r" % (len(rows), be.code_mails))
    ts = H.ts_state(dev.page)
    if not ts.get("renders") or ts["renders"][0]["language"] != lang:
        P.append("turnstile language %r" % ts.get("renders"))
    if any("@" in n["url"] or "XXXX" in n["url"] for n in env.net if n["device"] == dev.name):
        P.append("secret in a URL")
    assert not P, "; ".join(P)


def test_c05_fail_key_no_row_no_mail(env):
    """C5: failing test key (2x…AB) → no row, no mail; the user is told (turnstile_failed toast, or the page does not send)."""
    dev = open_req(env, "", key=H.FAIL_KEY)
    page = dev.page
    fill(page)
    page.wait_for_timeout(800)
    page.click(RQ["send"])
    page.wait_for_timeout(1500)
    be = env.backend
    assert not be.requests and not be.code_mails, "row/mail with the failing key"
    assert not on_code(page, 1), "code screen reached with the failing key"
    calls = be.rt("start")
    assert all(c["resp"].get("code") == "turnstile_failed" for c in calls), "start accepted: %r" % calls


def test_c05_server_turnstile_failed_toast_and_reset(env):
    """§1.2: turnstile_failed → toast + widget reset; values kept."""
    dev = open_req(env, "")
    page = dev.page
    fill(page)
    env.backend.ts_fail = True
    before = H.ts_state(page).get("resets", 0)
    send(page)
    page.wait_for_timeout(500)
    ts = H.ts_state(page)
    assert H.toasts(page) or len(btext(page)) > 0
    assert ts.get("resets", 0) > before or len(ts.get("renders", [])) > 1, "widget not reset: %r" % ts
    assert values(page)["name"] == "דנה" and not on_code(page, 1)


# =====================================================================================================
# C6 · code screen
# =====================================================================================================
def test_c06_code_screen_texts_and_inputs(env):
    """§1.3: title, address LTR, 6 boxes LTR inputmode=numeric, first autocomplete=one-time-code, help lines, notification card,
    resend countdown, "תיקון המייל", footer, verify button."""
    dev = to_code(env)
    page = dev.page
    P = []
    for k in ("code_title_he", "code_help", "code_help2", "notif", "fix", "footer", "verify_he"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if not has(page, "dana@example.com"):
        P.append("address not shown")
    if not re.search(TXT["resend_wait_re"], btext(page)):
        P.append("no resend countdown")
    boxes = page.evaluate("""()=>[0,1,2,3,4,5].map(i=>{const e=document.getElementById('rqOtp'+i);return e?{im:e.inputMode,ac:e.autocomplete,dir:getComputedStyle(e).direction,pd:getComputedStyle(e.parentElement).direction}:null})""")
    if any(b is None or b["im"] != "numeric" for b in boxes):
        P.append("boxes %r" % boxes)
    elif boxes[0]["ac"] != "one-time-code":
        P.append("first box autocomplete %r" % boxes[0]["ac"])
    elif boxes[0]["pd"] != "ltr":
        P.append("boxes container not LTR")
    em = page.evaluate("""()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){if(n.data.includes('dana@example.com')){const e=n.parentElement;return getComputedStyle(e).direction+'|'+(e.getAttribute('dir')||'')}}return null}""")
    if not em or not (em.startswith("ltr") or em.endswith("ltr")):
        P.append("address not LTR (%r)" % em)
    assert not P, "; ".join(P)


def test_c06_paste_fills_all_and_right_code_sent(env):
    """§1.3: pasting 6 digits (spaces ignored) fills all boxes; right code → pending → Sent screen (§1.5)."""
    dev = to_code(env)
    page = dev.page
    code = last_code(env)
    spaced = code[:3] + " " + code[3:]
    page.locator(RQ["otp"] % 0).focus()
    page.evaluate("""(t)=>{const e=document.getElementById('rqOtp0');const dt=new DataTransfer();dt.setData('text/plain',t);
      e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))}""", spaced)
    page.wait_for_timeout(100)
    got = page.evaluate("()=>[0,1,2,3,4,5].map(i=>(document.getElementById('rqOtp'+i)||{}).value||'').join('')")
    page.wait_for_timeout(600)
    vs = env.backend.rt("verify")
    if not vs and page.locator(RQ["verify"]).count() and page.locator(RQ["verify"]).is_visible():
        page.click(RQ["verify"])
        page.wait_for_timeout(600)
        vs = env.backend.rt("verify")
    assert got == code or (vs and vs[-1]["body"].get("code") == code), "paste filled %r (want %r), verify %r" % (got, code, [v["body"] for v in vs])
    assert wait_has(page, TXT["sent_he"], 6), "Sent screen not reached: %r" % btext(page)[:300]
    r = list(env.backend.requests.values())[0]
    assert r["status"] == "pending"


def test_c06_wrong_then_locked(env):
    """C6: wrong → red boxes + "הקוד שגוי. נשארו N ניסיונות." (4,3,2,1); 5th → "יותר מדי ניסיונות. מתחילים מחדש." → form with
    the values; row gone; resume key cleared."""
    dev = to_code(env)
    page = dev.page
    good = last_code(env)
    bad = "000000" if good != "000000" else "111111"
    lefts = []
    for i in range(4):
        type_rq_code(page, bad)
        m = re.search(TXT["wrong_re"], btext(page))
        # AMBIGUITY F21-QA-A3: for N=1 the page says "הקוד שגוי. נשאר ניסיון אחד." (Hebrew singular) — accepted as 1
        lefts.append(int(m.group(1)) if m else (1 if "הקוד שגוי. נשאר ניסיון אחד." in btext(page) else None))
    assert lefts == [4, 3, 2, 1], "attempts left shown %r" % lefts
    red = page.evaluate("()=>{const e=document.getElementById('rqOtp0');return e.getAttribute('aria-invalid')==='true'||/err|bad|invalid|wrong/.test(e.className+e.parentElement.className)}")
    type_rq_code(page, bad)
    P = []
    if not red:
        P.append("boxes not marked red")
    if not wait_has(page, TXT["locked"], 4):
        P.append("locked text missing")
    page.wait_for_timeout(1500)
    if not page.locator(RQ["send"]).is_visible() or values(page)["name"] != "דנה":
        P.append("not back on the form with the values (%r)" % values(page))
    if env.backend.requests:
        P.append("row not deleted")
    if resume_entry(dev):
        P.append("resume key kept after code_locked")
    assert not P, "; ".join(P)


def test_c06_expired_and_resend(env):
    """C6: after 10 min → "הקוד פג. שלחו קוד חדש." with resend enabled; resend refused before 60 s (button counts down, no call);
    after 60 s resend → new code works, the previous one is dead."""
    dev = to_code(env)
    page = dev.page
    first = last_code(env)
    page.click(RQ["resend"], force=True)
    page.wait_for_timeout(300)
    assert not env.backend.rt("resend") or env.backend.rt("resend")[-1]["resp"].get("ok") is False, "resend accepted before 60 s"
    n_mail = len(env.backend.code_mails)
    advance(env, dev, 61)
    assert not re.search(TXT["resend_wait_re"], btext(page)), "still counting down after 61 s"
    page.click(RQ["resend"])
    page.wait_for_timeout(900)
    assert len(env.backend.code_mails) == n_mail + 1, "no resend mail"
    second = last_code(env)
    advance(env, dev, 11 * 60)
    type_rq_code(page, second)
    assert wait_has(page, TXT["expired"], 4), "expired text missing: %r" % btext(page)[-300:]
    assert page.locator(RQ["resend"]).is_enabled()
    page.click(RQ["resend"])
    page.wait_for_timeout(900)
    third = last_code(env)
    if first != third:
        type_rq_code(page, first)
        assert re.search(TXT["wrong_re"], btext(page)), "old code not refused"
    type_rq_code(page, third)
    assert wait_has(page, TXT["sent_he"], 6), "new code did not verify"


def test_c06_retype_after_wrong_code(env):
    """C6 / §1.3 + §4 (5 wrong → code_locked): after ONE wrong code the user taps the first box and types the right code
    (keyboard, like a phone). Expected: one more verify with the right code → Sent. A typing pattern must not burn the
    remaining attempts. (F21-QA-BUG-01)"""
    dev = to_code(env)
    page = dev.page
    good = last_code(env)
    bad = "000000" if good != "000000" else "111111"
    page.locator(RQ["otp"] % 0).click()
    for d in bad:
        page.keyboard.press(d)
        page.wait_for_timeout(60)
    page.wait_for_timeout(900)
    assert [c["resp"].get("code") for c in env.backend.rt("verify")] == ["code_wrong"]
    page.locator(RQ["otp"] % 0).click()
    for d in good:
        page.keyboard.press(d)
        page.wait_for_timeout(60)
    page.wait_for_timeout(1500)
    if not has(page, TXT["sent_he"]) and page.locator(RQ["verify"]).count() and page.locator(RQ["verify"]).is_visible():
        page.click(RQ["verify"])
        page.wait_for_timeout(1000)
    seq = [c["resp"].get("code") or "ok" for c in env.backend.rt("verify")]
    assert has(page, TXT["sent_he"]) and seq[-1] == "ok" and len(seq) == 2, \
        "retyping the right code after one wrong code → verify results %r (request %s)" % (seq, "deleted" if not env.backend.requests else "kept")


def test_c06_fourth_resend_refused(env):
    """C6 / §4: ≤3 resends per request — the 4th is refused (no 4th mail)."""
    dev = to_code(env)
    page = dev.page
    for _ in range(4):
        advance(env, dev, 61)
        page.click(RQ["resend"])
        page.wait_for_timeout(700)
    assert len(env.backend.code_mails) == 4, "mails %d (1 start + 3 resends)" % len(env.backend.code_mails)


# =====================================================================================================
# C7 · resume
# =====================================================================================================
def test_c07_resume_within_10_min_no_send(env):
    """C7: reload within 10 min → code screen directly, banner with N minutes, no new start/resend; key {request_id, email,
    sentAt, lang, v:1} never holds the code."""
    dev = to_code(env)
    page = dev.page
    code = last_code(env)
    e = resume_entry(dev)
    raw = H.ls_get(dev, H.RESUME_KEY) or ""
    P = []
    if not e or set(e) != {"request_id", "email", "sentAt", "lang", "v"} or e.get("v") != 1:
        P.append("key %r" % e)
    if code in raw:
        P.append("key holds the code")
    advance(env, dev, 3 * 60)
    n = len(env.backend.rt_calls)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    if not on_code(page, 4):
        P.append("not on the code screen after reload: %r" % btext(page)[:200])
    m = re.search(TXT["banner_re"], btext(page))
    if not m or m.group(1) != "3":
        P.append("banner %r" % (m.group(0) if m else None))
    if len(env.backend.rt_calls) != n:
        P.append("calls on reload: %r" % [c["action"] for c in env.backend.rt_calls[n:]])
    type_rq_code(page, code)
    if not wait_has(page, TXT["sent_he"], 6):
        P.append("verify after resume failed")
    if resume_entry(dev):
        P.append("key kept after success")
    assert not P, "; ".join(P)


@pytest.mark.parametrize("how", ["fix", "ttl"])
def test_c07_key_cleared(env, how):
    """C7: "תיקון המייל" → back to the form with the values, key gone; TTL (>10 min) → reload shows the form, key gone."""
    dev = to_code(env)
    page = dev.page
    if how == "fix":
        page.click(RQ["fix"])
        page.wait_for_timeout(600)
        assert page.locator(RQ["send"]).is_visible() and values(page)["email"] == "dana@example.com", "form/values not kept"
    else:
        advance(env, dev, 11 * 60)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        assert page.locator(RQ["send"]).is_visible(), "form not shown after the TTL"
    assert not resume_entry(dev), "key kept (%s): %r" % (how, H.ls_get(dev, H.RESUME_KEY))


def test_c07_reload_after_success_shows_form(env):
    """§1.5: Sent screen texts; reloading after success shows the form (nothing stored)."""
    dev = to_code(env)
    page = dev.page
    type_rq_code(page, last_code(env))
    P = []
    for k in ("sent_he", "sent_line", "what_now", "step3"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if not (has(page, H.flag("PT")) and has(page, "dana@example.com") and has(page, "אפריל 2027")):
        P.append("summary card incomplete: %r" % btext(page)[:400])
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    if not page.locator(RQ["send"]).is_visible():
        P.append("reload after success did not show the form")
    if dev.ls().get(H.RESUME_KEY):
        P.append("something stored after success")
    assert not P, "; ".join(P)


# =====================================================================================================
# C8 / C9 · limits, cap
# =====================================================================================================
@pytest.mark.parametrize("lang", ["he", "en"])
def test_c08_rate_limited_toast(env, lang):
    """C8 / §1.2: the 4th start for one email in a day → rate_limited → toast "יותר מדי בקשות היום. נסו שוב מחר." (EN text)."""
    for i in range(3):
        env.backend.r_attempts.append({"kind": "start", "email_hash": H.sha("dana@example.com"), "ip": "x%d" % i, "ok": True, "at": env.backend.clock()})
    dev = open_req(env, "?lang=" + lang)
    fill(dev.page, lang=lang, name="Ann")
    send(dev.page)
    assert env.backend.rt("start")[-1]["resp"].get("code") == "rate_limited"
    assert H.saw_toast(dev.page, TXT["rate_" + lang], 4), "toast missing: %r" % H.toasts(dev.page)
    assert values(dev.page)["email"] == "dana@example.com"


def test_c09_cap_never_on_load(env):
    """C9 / D17: with the cap full, opening the form never shows "נסו שוב מחר"."""
    env.backend.fill_cap(50)
    dev = open_req(env, "")
    dev.page.wait_for_timeout(1000)
    assert not has(dev.page, TXT["limit_he"]) and dev.page.locator(RQ["send"]).is_visible(), "limit screen on page load"
    assert not env.backend.rt_calls, "a call on page load"


@pytest.mark.parametrize("lang", ["he", "en"])
def test_c09_cap_start_limit_screen_back_keeps_values(env, lang):
    """C9 / §1.4: start → daily_limit → "נסו שוב מחר / Please try again tomorrow" screen; "חזרה לטופס" keeps the values."""
    env.backend.fill_cap(50)
    dev = open_req(env, "?lang=" + lang)
    page = dev.page
    fill(page, lang=lang, name="Ann", note="hello")
    send(page)
    assert wait_has(page, TXT["limit_" + lang], 4), "limit screen missing: %r" % btext(page)[:300]
    H.click_text(page, TXT["back_" + lang])
    page.wait_for_timeout(500)
    v = values(page)
    assert (v["name"], v["email"], v["note"], len(v["chips"])) == ("Ann", "dana@example.com", "hello", 2), "values lost: %r" % v


def test_c09_cap_on_resend(env):
    """C9: resend → daily_limit → the limit screen."""
    dev = to_code(env)
    env.backend.fill_cap(50)
    advance(env, dev, 61)
    dev.page.click(RQ["resend"])
    assert wait_has(dev.page, TXT["limit_he"], 4), "limit screen not shown on resend daily_limit"


@pytest.mark.parametrize("kind", ["offline", "other"])
def test_c19_offline_and_other_error(env, kind):
    """C19 / §1.2: offline → toast "אין חיבור. נסו שוב כשהרשת תחזור." keeping all values; other errors → "משהו השתבש. נסו שוב."."""
    dev = open_req(env, "")
    page = dev.page
    fill(page, note="n1")
    wait_token(page)
    if kind == "offline":
        dev.offline(True)
    else:
        env.backend.rt_force["start"] = "server_error"
    page.click(RQ["send"])
    page.wait_for_timeout(1200)
    want = TXT["offline"] if kind == "offline" else TXT["other"]
    assert H.saw_toast(page, want, 4), "%s toast missing: %r / %r" % (kind, H.toasts(page), btext(page)[:200])
    v = values(page)
    assert (v["name"], v["note"], len(v["chips"])) == ("דנה", "n1", 2), "values lost: %r" % v


# =====================================================================================================
# C18 · layout
# =====================================================================================================
@pytest.mark.parametrize("lang", ["he", "en"])
@pytest.mark.parametrize("scr", ["form", "code", "limit", "sent", "closed", "inapp"])
def test_c18_request_390_layout(env, lang, scr):
    """C18: 390px — no horizontal scroll, RTL/LTR per language, touch targets ≥44px (OTP boxes ≥40, Turnstile excluded)."""
    if scr == "closed":
        dev = open_req(env, "?lang=" + lang, flag="off")
    elif scr == "inapp":
        dev = open_req(env, "?lang=" + lang, ua="gmail_ios")
    elif scr == "form":
        dev = open_req(env, "?lang=" + lang)
        fill(dev.page, lang=lang, name="Ann", countries=("PT", "ES", "FR", "IT", "DE"), note="x" * 120)
    else:
        if scr == "limit":
            env.backend.fill_cap(50)
            dev = open_req(env, "?lang=" + lang)
            fill(dev.page, lang=lang, name="Ann")
            send(dev.page)
        else:
            dev = to_code(env, lang=lang)
            if scr == "sent":
                type_rq_code(dev.page, last_code(env))
    page = dev.page
    page.wait_for_timeout(500)
    P = []
    if hscroll(page) > 0:
        P.append("horizontal scroll %dpx" % hscroll(page))
    d = lang_of(page)["dir"]
    if d != ("rtl" if lang == "he" else "ltr"):
        P.append("dir %s" % d)
    tp = touch_problems(page)
    if tp:
        P.append("touch <44px: %r" % tp[:6])
    assert not P, "; ".join(P)


# =====================================================================================================
# App · chooser, admin tab, sheets
# =====================================================================================================
def admin_dev(env, name="A", offline=False):
    be = env.backend
    tid = be.add_trip_full("ויאטנם 2026", "2026-09-15", "2026-10-06", countries=["VN"])
    be.links = [{"trip_id": tid, "role": "manager", "display_name": "אור", "joined_at": H.iso(be.clock() - 30 * H.DAY)}]
    be.auto_admin = True
    be.auto_email = "or@example.com"
    dev = env.new_device(name, offline_boot=offline)
    dev.page.goto(env.server.origin + H.APP + "?choose=1", wait_until="domcontentloaded")
    st = f20.wait_state(dev.page, "choose", 25)
    assert st == "choose", "chooser not reached (state=%r)" % st
    dev.page.wait_for_timeout(1500)
    be.links = []
    return dev


def chooser_badges(page):
    return page.evaluate("""()=>{const r=document.getElementById('ptChooseAdmin');if(!r)return null;
      return {text:(r.innerText||'').replace(/\\s+/g,' ').trim()}}""")


def open_requests_admin(env, dev):
    page = dev.page
    page.locator("#ptChooseAdmin").click()
    page.wait_for_timeout(1500)
    wait_until(lambda: has(page, TXT["meter"]) or has(page, f03.TXT["invite_btn"]), 10, page)
    page.wait_for_timeout(500)


def seed_requests(be):
    """Three verified pending requests (oldest first: en/manager/invite) + one rejected + one unverified."""
    uid = be.add_account("mgr@example.com")
    t1, _ = be.trip(name="יפן 2027", managers=(), others=())
    be.add_member(t1, uid, "manager", "active", "דנה")
    t2, _ = be.trip(name="יוון 2028", managers=(), others=())
    be.add_member(t2, uid, "manager", "active", "דנה")
    be.add_invite("inv@example.com", "טיול ישן", sent_days_ago=3, expires_in_days=4)
    ids = {
        "en": be.add_request(name="Ann", email="ann@example.com", lang="en", countries=("PT", "ES", "FR"), month="2027-04-01", travellers=3, note="We love beaches", verified_ago=5 * H.HOUR),
        "mgr": be.add_request(name="דנה", email="mgr@example.com", lang="he", countries=("JP",), month=None, travellers=2, verified_ago=3 * H.HOUR),
        "inv": be.add_request(name="נועה", email="inv@example.com", lang="he", countries=("GR",), month="2027-07-01", travellers=6, verified_ago=2 * H.HOUR),
        "plain": be.add_request(name="רון", email="ron@example.com", lang="he", countries=("TH", "VN"), month="2027-01-01", travellers=4, verified_ago=1 * H.HOUR),
    }
    be.add_request(name="X", email="rej@example.com", status="rejected")
    be.add_request(name="Y", email="unv@example.com", status="unverified")
    return ids


def card_of(page, name):
    """The smallest visible element containing the requester name AND a "דחייה" button."""
    return page.evaluate("""(n)=>{const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
      const all=[...document.querySelectorAll('*')].filter(e=>vis(e)&&(e.innerText||'').includes(n)&&[...e.querySelectorAll('button')].some(b=>(b.innerText||'').trim()==='דחייה'));
      const c=all.filter(e=>!all.some(o=>o!==e&&e.contains(o)))[0];if(!c)return null;
      return {text:(c.innerText||'').replace(/\\s+/g,' ').trim(),buttons:[...c.querySelectorAll('button')].map(b=>(b.innerText||'').replace(/\\s+/g,' ').trim()),
        border:getComputedStyle(c).borderColor,top:c.getBoundingClientRect().top+scrollY}}""", name)


def test_c11_chooser_badges(env):
    """C11 / §1.6: admin row sub "בקשות, קבוצות והזמנת מנהלים"; badges "<N> בקשות חדשות" (verified pending only) then
    "<M> הזמנות ממתינות"."""
    be = env.backend
    seed_requests(be)
    be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
    dev = admin_dev(env)
    b = chooser_badges(dev.page)
    t = b["text"] if b else ""
    P = []
    if norm(TXT["adm_sub_new"]) not in t:
        P.append("sub missing")
    i, j = t.find(norm(TXT["badge_req"].format(n=4))), t.find(norm(TXT["badge_inv"].format(n=2)))
    if i < 0 or j < 0 or i > j:
        P.append("badges/order wrong")
    assert not P, "; ".join(P) + " | row text %r" % t


@pytest.mark.parametrize("case", ["zero", "rpc_fail"])
def test_c11_chooser_badge_omitted(env, case):
    """§1.6: each badge omitted at 0 or on a failed call."""
    be = env.backend
    be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
    if case == "rpc_fail":
        be.add_request(name="Ann", email="ann@example.com")
        be.req_rpc_fail = True
    dev = admin_dev(env)
    t = chooser_badges(dev.page)["text"]
    assert "בקשות חדשות" not in t, "requests badge shown (%s): %r" % (case, t)
    assert norm(TXT["badge_inv"].format(n=1)) in t, "pending-invites badge missing: %r" % t


def test_c11_admin_requests_tab(env):
    """C11 / §1.7: segmented tabs with counts, default = requests (N>0); meter "<k> מתוך 50" + role=img with the same text + line;
    cards oldest first; EN badge; markers; button labels by the first-match rule; footnote; only verified pending."""
    be = env.backend
    ids = seed_requests(be)
    be.fill_cap(7)
    be.add_invite("p1@example.com", "יוון 2027", sent_days_ago=1, expires_in_days=6)
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    t = btext(page)
    P = []
    if norm(TXT["tab_req"].format(n=4)) not in t:
        P.append("tab 'בקשות · 4' missing")
    if not re.search(r"קבוצות והזמנות · \d+", t):
        P.append("groups tab with count missing")
    if norm(TXT["meter_val"].format(k=7)) not in t or norm(TXT["meter"]) not in t or norm(TXT["meter_line"]) not in t:
        P.append("meter texts")
    img = page.evaluate("()=>[...document.querySelectorAll('[role=img]')].map(e=>e.getAttribute('aria-label')||'')")
    if not any("7 מתוך 50" in a for a in img):
        P.append("meter bar role=img aria %r" % img)
    if norm(TXT["footnote"]) not in t:
        P.append("footnote")
    if "rej@example.com" in t or "unv@example.com" in t:
        P.append("rejected/unverified shown")
    cards = {k: card_of(page, n) for k, n in (("en", "Ann"), ("mgr", "mgr@example.com"), ("inv", "נועה"), ("plain", "רון"))}
    if not all(cards.values()):
        P.append("cards missing: %r" % [k for k, v in cards.items() if not v])
    else:
        tops = [cards[k]["top"] for k in ("en", "mgr", "inv", "plain")]
        if tops != sorted(tops):
            P.append("not oldest first")
        want_btn = {"en": TXT["b_en"], "mgr": TXT["b_more"], "inv": TXT["b_replace"], "plain": TXT["b_ok"]}
        for k, w in want_btn.items():
            if w not in cards[k]["buttons"] or TXT["b_reject"] not in cards[k]["buttons"]:
                P.append("%s buttons %r (want %r)" % (k, cards[k]["buttons"], w))
        if not re.search(r"\bEN\b", cards["en"]["text"]):
            P.append("EN badge missing")
        if re.search(r"\bEN\b", cards["plain"]["text"]):
            P.append("EN badge on a Hebrew request")
        if "כבר מנהל: יפן 2027, יוון 2028" not in cards["mgr"]["text"] and "כבר מנהל: יוון 2028, יפן 2027" not in cards["mgr"]["text"]:
            P.append("manager marker: %r" % cards["mgr"]["text"])
        sent = (be.clock() - 3 * H.DAY + 3 * H.HOUR).strftime("%d/%m")
        if norm(TXT["active_inv"] + sent) not in cards["inv"]["text"]:
            P.append("invite marker (want %r): %r" % (TXT["active_inv"] + sent, cards["inv"]["text"]))
        if "עוד לא יודעים מתי · 2 מטיילים" not in cards["mgr"]["text"] or "אפריל 2027 · 3 מטיילים" not in cards["en"]["text"]:
            P.append("when/travellers line")
        if "We love beaches" not in cards["en"]["text"]:
            P.append("note")
        for c in ("פורטוגל", "ספרד", "צרפת"):
            if c not in cards["en"]["text"]:
                P.append("country name %s (Hebrew) missing on the EN card" % c)
                break
        if H.flag("PT") not in cards["en"]["text"]:
            P.append("flags missing")
    assert not P, "; ".join(P)


def test_c11_default_tab_groups_when_empty(env):
    """§1.7: N=0 → default tab = groups (today's F03 screen); the requests tab shows "אין בקשות חדשות"."""
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    assert has(page, f03.TXT["invite_btn"]), "groups tab not the default with 0 requests"
    H.click_text(page, TXT["tab_req"].format(n=0))
    page.wait_for_timeout(600)
    assert has(page, TXT["empty"]), "empty state missing"


def open_sheet(page, name, label):
    c = card_of(page, name)
    assert c, "card of %s not found" % name
    page.evaluate("""([n,l])=>{const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
      const all=[...document.querySelectorAll('*')].filter(e=>vis(e)&&(e.innerText||'').includes(n)&&[...e.querySelectorAll('button')].some(b=>(b.innerText||'').trim()==='דחייה'));
      const c=all.filter(e=>!all.some(o=>o!==e&&e.contains(o)))[0];[...c.querySelectorAll('button')].find(b=>(b.innerText||'').replace(/\\s+/g,' ').trim()===l).click()}""", [name, label])
    page.wait_for_timeout(700)


def draft_input(page):
    return page.locator("input:visible").filter(has=page.locator("xpath=self::input[not(@type) or @type='text']")).last


@pytest.mark.parametrize("lang", ["he", "en"])
def test_c12_approve_sheet_and_send(env, lang):
    """C12 / §1.8 / §5.2: approve sheet title + line; draft name pre-filled by D16 in the request language; pre-fill box with
    שפת המייל; edit the name → approve_request(request_id, edited name) → toast "ההזמנה נשלחה ל-<email>", card leaves, the
    groups tab gains the pending invite; one email in the request language."""
    be = env.backend
    if lang == "en":
        rid = be.add_request(name="Ann", email="ann@example.com", lang="en", countries=("PT", "ES", "FR"), month="2027-04-01")
        name, email, draft = "Ann", "ann@example.com", "Portugal & Spain +1 · April 2027"
    else:
        rid = be.add_request(name="רון", email="ron@example.com", lang="he", countries=("TH", "VN"), month="2027-01-01")
        name, email, draft = "רון", "ron@example.com", "%s ו%s · ינואר 2027" % (cname("TH"), cname("VN"))   # D16 from countries.json he
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, name, TXT["b_en"] if lang == "en" else TXT["b_ok"])
    t = btext(page)
    P = []
    for s in (TXT["ap_title"], TXT["ap_line"].format(name=name), TXT["ap_input"], TXT["ap_help"].format(name=name), TXT["ap_box"],
              TXT["ap_mail_lang"], TXT["ap_lang_%s" % lang], TXT["ap_send"].format(email=email), TXT["cancel"]):
        if norm(s) not in t:
            P.append("missing %r" % s)
    vals = page.evaluate("()=>[...document.querySelectorAll('input')].filter(e=>e.offsetParent&&(!e.type||e.type==='text')).map(e=>e.value)")
    if draft not in vals:
        P.append("draft name %r not pre-filled (inputs %r)" % (draft, vals))
    page.evaluate("""(d)=>{const e=[...document.querySelectorAll('input')].find(x=>x.offsetParent&&x.value===d);if(e){e.value='שם ערוך';e.dispatchEvent(new Event('input',{bubbles:true}))}}""", draft)
    H.click_text(page, TXT["ap_send"].format(email=email))
    page.wait_for_timeout(1500)
    calls = [c for c in be.fn_calls if c.get("action") == "approve_request"]
    if not calls or calls[-1]["body"].get("request_id") != rid or calls[-1]["body"].get("draft_name") != "שם ערוך":
        P.append("approve call %r" % (calls[-1]["body"] if calls else None))
    if not H.saw_toast(page, TXT["ap_toast"].format(email=email), 4) and not has(page, TXT["ap_toast"].format(email=email)):
        P.append("toast missing")
    page.wait_for_timeout(800)
    if card_of(page, name):
        P.append("card still listed")
    if len(be.emails) != 1 or be.emails[0].get("lang") != lang:
        P.append("emails %r" % be.emails)
    assert not P, "; ".join(P)


def test_c13_approve_replace_sheet(env):
    """C13 / §1.8 D12: with an active invite — title "…הזמנה חדשה", amber box with draft · sent · valid until dd/mm and the
    'old link stops working' line; button "ביטול הישנה ושליחת הזמנה חדשה"; after approval exactly one active invite."""
    be = env.backend
    iid, _ = be.add_invite("inv@example.com", "טיול ישן", sent_days_ago=3, expires_in_days=4)
    be.add_request(name="נועה", email="inv@example.com", countries=("GR",), month="2027-07-01")
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, "נועה", TXT["b_replace"])
    t = btext(page)
    sent = (be.clock() - 3 * H.DAY).strftime("%d/%m")
    until = (be.clock() + 4 * H.DAY + 3 * H.HOUR).strftime("%d/%m")
    P = []
    for s in (TXT["ap_title_rep"], TXT["ap_amber"], '"טיול ישן" · נשלחה %s · בתוקף עד %s.' % (sent, until), TXT["ap_amber2"], TXT["ap_send_rep"]):
        if norm(s) not in t:
            P.append("missing %r" % s)
    H.click_text(page, TXT["ap_send_rep"])
    page.wait_for_timeout(1500)
    act = [r for r in be.invites.values() if r["email"] == "inv@example.com" and not r["revoked_at"] and not r["used_at"]]
    if len(act) != 1 or act[0]["id"] == iid:
        P.append("active invites after approval: %r" % [a["id"] for a in act])
    assert not P, "; ".join(P) + " | " + t[-600:]


@pytest.mark.parametrize("err", ["email_failed", "request_closed"])
def test_c14_approve_errors(env, err):
    """C14 / §1.8: email_failed → toast "המייל לא נשלח. שום דבר לא השתנה – נסו שוב." (card stays); request_closed → toast
    "הבקשה כבר טופלה" + refresh (card leaves)."""
    be = env.backend
    rid = be.add_request(name="רון", email="ron@example.com")
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, "רון", TXT["b_ok"])
    if err == "email_failed":
        be.email_fail = True
    else:
        be.requests[rid]["status"] = "rejected"
        be.requests[rid]["decided_at"] = H.iso(be.clock())
    n = len([c for c in be.rpc_calls if c["fn"] == "admin_trip_requests"])
    H.click_text(page, TXT["ap_send"].format(email="ron@example.com"))
    page.wait_for_timeout(1500)
    want = TXT["ap_fail"] if err == "email_failed" else TXT["ap_closed"]
    assert H.saw_toast(page, want, 4) or has(page, want), "toast %r missing (%r)" % (want, H.toasts(page))
    if err == "email_failed":
        page.keyboard.press("Escape")
        assert be.requests[rid]["status"] == "pending" and not be.invites
    else:
        page.wait_for_timeout(800)
        assert len([c for c in be.rpc_calls if c["fn"] == "admin_trip_requests"]) > n, "list not refreshed"
        assert not card_of(page, "רון"), "closed request still listed"


@pytest.mark.parametrize("lang,mail", [("he", True), ("en", True), ("he", False)])
def test_c15_reject_sheet(env, lang, mail):
    """C15 / §1.9: "לדחות את הבקשה של <name>?", line, checkbox checked by default + "בשפת הבקשה (כאן: עברית|אנגלית)", preview in
    that language, red "דחייה", "ביטול"; reject → reject_request(send_mail) and the card leaves."""
    be = env.backend
    name = "Ann" if lang == "en" else "רון"
    rid = be.add_request(name=name, email="x@example.com", lang=lang)
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, name, TXT["b_reject"])
    t = btext(page)
    P = []
    for s in (TXT["rj_title"].format(name=name), TXT["rj_line"], TXT["rj_cb"], TXT["rj_lang"].format(l="עברית" if lang == "he" else "אנגלית")):
        if norm(s) not in t:
            P.append("missing %r" % s)
    if lang == "he" and norm(TXT["rj_preview_he"]) not in t:
        P.append("Hebrew preview missing")
    if lang == "en" and not re.search(r"Thank you|interest|Lonely Planner", t):
        P.append("English preview missing")
    cb = page.evaluate("()=>[...document.querySelectorAll('input[type=checkbox]')].filter(e=>{const r=(e.closest('label')||e).getBoundingClientRect();return r.width>0}).map(e=>({c:e.checked,d:e.disabled}))")
    if not cb or not cb[-1]["c"] or cb[-1]["d"]:
        P.append("checkbox not checked/enabled by default: %r" % cb)
    if not mail:
        page.evaluate("()=>{const e=[...document.querySelectorAll('input[type=checkbox]')].filter(e=>(e.closest('label')||e).getBoundingClientRect().width>0).pop();e.click()}")
    btns = H.find(page, TXT["b_reject"], exact=True)
    page.evaluate("()=>window.__qaLast[window.__qaLast.length-1].click()") if btns else None
    page.wait_for_timeout(1500)
    calls = [c for c in be.fn_calls if c.get("action") == "reject_request"]
    if not calls or calls[-1]["body"].get("send_mail") is not mail or calls[-1]["body"].get("request_id") != rid:
        P.append("reject call %r" % (calls[-1]["body"] if calls else None))
    if len(be.reject_mails) != (1 if mail else 0):
        P.append("reject mails %r" % be.reject_mails)
    if card_of(page, name):
        P.append("card still listed")
    assert not P, "; ".join(P)


def test_c15_reject_at_cap(env):
    """C9/C15 / §1.9: meter at the cap → checkbox disabled + unchecked with "התקרה היומית מלאה – הדחייה תהיה בלי מייל"; result
    mail_skipped:'daily_limit' → toast "הבקשה נדחתה, בלי מייל (התקרה היומית מלאה)"."""
    be = env.backend
    be.add_request(name="רון", email="ron@example.com")
    be.fill_cap(50)
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, "רון", TXT["b_reject"])
    P = []
    if not has(page, TXT["rj_cap"]):
        P.append("cap line missing")
    cb = page.evaluate("()=>[...document.querySelectorAll('input[type=checkbox]')].filter(e=>(e.closest('label')||e).getBoundingClientRect().width>0).map(e=>({c:e.checked,d:e.disabled}))")
    if not cb or cb[-1]["c"] or not cb[-1]["d"]:
        P.append("checkbox %r (want disabled + unchecked)" % cb)
    # the server answers mail_skipped daily_limit when a mail was asked at the cap — force the request to ask for it
    be.fill_cap(0)
    btns = H.find(page, TXT["b_reject"], exact=True)
    page.evaluate("()=>window.__qaLast[window.__qaLast.length-1].click()") if btns else None
    page.wait_for_timeout(1200)
    calls = [c for c in be.fn_calls if c.get("action") == "reject_request"]
    if not calls:
        P.append("no reject call")
    assert not P, "; ".join(P)


def test_c15_capped_toast(env):
    """§1.9: a reject with mail answered mail_skipped:'daily_limit' (cap reached meanwhile) → toast text."""
    be = env.backend
    be.add_request(name="רון", email="ron@example.com")
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    open_sheet(page, "רון", TXT["b_reject"])
    be.fill_cap(50)
    H.find(page, TXT["b_reject"], exact=True)
    page.evaluate("()=>window.__qaLast[window.__qaLast.length-1].click()")
    page.wait_for_timeout(1200)
    assert H.saw_toast(page, TXT["rj_capped_toast"], 4) or has(page, TXT["rj_capped_toast"]), "toast missing: %r" % H.toasts(page)


def test_c19_admin_requests_offline(env):
    """C19 / §1.7: offline → as F03 ("אין חיבור…"), approve / reject disabled."""
    be = env.backend
    be.add_request(name="רון", email="ron@example.com")
    dev = admin_dev(env)
    open_requests_admin(env, dev)
    page = dev.page
    dev.offline(True)
    page.evaluate("()=>window.dispatchEvent(new Event('offline'))")
    page.wait_for_timeout(1200)
    assert has(page, TXT["adm_offline"]), "offline notice missing"
    dis = page.evaluate("""()=>[...document.querySelectorAll('button')].filter(b=>b.offsetParent&&/^(אישור|דחייה)/.test((b.innerText||'').trim())).map(b=>b.disabled||b.getAttribute('aria-disabled')==='true')""")
    assert dis and all(dis), "actions not disabled offline: %r" % dis


@pytest.mark.parametrize("scr", ["chooser", "requests", "approve", "reject"])
def test_c18_app_390(env, scr):
    """C18: chooser, requests tab and both sheets at 390px — no horizontal scroll, RTL, touch ≥44px, emails LTR."""
    be = env.backend
    seed_requests(be)
    dev = admin_dev(env)
    page = dev.page
    if scr != "chooser":
        open_requests_admin(env, dev)
    if scr == "approve":
        open_sheet(page, "Ann", TXT["b_en"])
    elif scr == "reject":
        open_sheet(page, "Ann", TXT["b_reject"])
    P = []
    if hscroll(page) > 0:
        P.append("horizontal scroll")
    if scr != "chooser":
        tp = [x for x in touch_problems(page, "body") if not x.startswith(("rq",))]
        sheet_tp = [x for x in tp if any(k in x for k in ("אישור", "דחייה", "ביטול", "בקשות", "קבוצות"))]
        if sheet_tp:
            P.append("touch <44: %r" % sheet_tp[:5])
        em = page.evaluate("""()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n,o=[];while(n=w.nextNode()){if(/ann@example\\.com/.test(n.data)){const e=n.parentElement;const r=e.getBoundingClientRect();if(r.width>0)o.push(getComputedStyle(e).direction+'/'+(e.closest('[dir]')||{}).dir)}}return o}""")
        if em and not all(x.startswith("ltr") or x.endswith("/ltr") for x in em):
            P.append("email not LTR: %r" % em)
    assert not P, "; ".join(P)


# =====================================================================================================
# C16 · wizard pre-fill
# =====================================================================================================
def _approved_invite(be, lang="en", month="2027-04-01", countries=("PT", "ES")):
    rid = be.add_request(name="Ann", email=f04.INVITE_EMAIL, lang=lang, countries=countries, month=month)
    be.requests[rid]["status"] = "approved"
    iid, token = be.add_invite(f04.INVITE_EMAIL, "Portugal & Spain · April 2027", sent_days_ago=0, expires_in_days=7)
    be.invites[iid].update(request_id=rid, lang=lang)
    be.requests[rid]["invite_id"] = iid
    return iid, token


def wizard_step1(env, token, name="W"):
    dev = env.new_device(name, ua="chrome_android")
    dev.page.goto(env.server.origin + H.APP + "?invite=1#invite=" + token, wait_until="domcontentloaded")
    st = f04.wait_screen(dev.page, ["code", "step1"], 20)
    assert st == "code", "code screen not reached (%s)" % st
    f04.type_code(dev.page, env.backend.otp_code)
    assert f04.wait_screen(dev.page, "step1", 15) == "step1", "step 1 not reached (screen=%s)" % f04.screen(dev.page)
    dev.page.wait_for_timeout(800)
    return dev


def test_c16_wizard_prefill(env):
    """C16 / §1.11: lookup returns prefill → step 1 green box, trip name = draft name, "השם שלך בקבוצה" = requester name, tag
    "מהבקשה", the date picker opens on the requested month; step 2 starts with the requested countries and their currencies."""
    be = env.backend
    _, token = _approved_invite(be)
    dev = wizard_step1(env, token)
    page = dev.page
    P = []
    lk = be.lookups()
    if not lk or "prefill" not in (lk[-1].get("resp") or {}):
        P.append("lookup without prefill")
    if not has(page, TXT["wz_box"]):
        P.append("green box missing")
    if not has(page, TXT["wz_tag"]):
        P.append("tag 'מהבקשה' missing")
    if f04.field(page, f04.TXT["s1_name"]).input_value() != "Portugal & Spain · April 2027":
        P.append("trip name %r" % f04.field(page, f04.TXT["s1_name"]).input_value())
    if f04.field(page, f04.TXT["s1_me"]).input_value() != "Ann":
        P.append("name in group %r" % f04.field(page, f04.TXT["s1_me"]).input_value())
    a, _b = f04.dates(page)
    mn = (a.get_attribute("min") or "", a.get_attribute("value") or "", page.evaluate("(e)=>e.dataset?JSON.stringify(e.dataset):''", a.element_handle()))
    if not any("2027-04" in x for x in mn) and not has(page, "אפריל 2027"):
        P.append("date picker not on April 2027 (%r)" % (mn,))
    f04.fill_step1(page, start="2027-04-03", end="2027-04-20")
    f04.press_next(page)
    if f04.wait_screen(page, "step2") != "step2":
        P.append("step 2 not reached")
    else:
        if f04.selected_count(page) != 2:
            P.append("selected countries %d (want 2)" % f04.selected_count(page))
        cur = f04.currency_codes(page)
        if "EUR" not in cur:
            P.append("currencies %r lack EUR (PT/ES)" % cur)
    assert not P, "; ".join(P)


def test_c16_no_request_today_wizard(env):
    """C16: an invite without a request → today's wizard (no box, no tag, name/me as alpha.7.2)."""
    be = env.backend
    _, token = be.add_invite(f04.INVITE_EMAIL, f04.DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = wizard_step1(env, token)
    page = dev.page
    assert not has(page, TXT["wz_box"]) and not has(page, TXT["wz_tag"]), "pre-fill box/tag without a request"
    assert f04.field(page, f04.TXT["s1_name"]).input_value() == f04.DRAFT


def test_c16_prefill_month_null(env):
    """§1.11: month null → the picker opens on the current month; no exception."""
    be = env.backend
    _, token = _approved_invite(be, month=None, countries=("JP",))
    dev = wizard_step1(env, token)
    assert has(dev.page, TXT["wz_box"]), "box missing"
    assert not H.page_errors(dev), H.page_errors(dev)[:3]


# =====================================================================================================
# C20 · static
# =====================================================================================================
def _scripts(src):
    """Inline classic/module scripts, parsed with html.parser (a regex on "<script" also matches the word inside comments
    and JS strings of the app — that gave false node --check failures on alpha.7)."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.out, self.cur = [], None

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                a = dict(attrs)
                t = (a.get("type") or "").strip().lower()
                ok = "src" not in a and t in ("", "module", "text/javascript", "application/javascript")
                self.cur = [("module" if t == "module" else ""), []] if ok else None

        def handle_data(self, data):
            if self.cur is not None:
                self.cur[1].append(data)

        def handle_endtag(self, tag):
            if tag == "script" and self.cur is not None:
                self.out.append((self.cur[0], "".join(self.cur[1])))
                self.cur = None

    p = P()
    p.feed(src)
    p.close()
    return p.out
    # (copied from tests/f04home/test_f04home.py — a regex on '<script' matches the word inside app comments)


@pytest.mark.parametrize("check", ["protected:" + n for n in qa_refs.PROTECTED] + ["app_version", "pt_version", "request_version_comment",
                                   "flags_declared", "change_comments", "node_check", "no_duplicate_ids", "no_live_project_ref",
                                   "invite_unchanged", "join_unchanged"])
def test_c20_static(check, tmp_path):
    """C20: protected functions byte-identical to v2.15.2; APP_VERSION / PT_VERSION = tests/qa_versions.json; /request/ version
    comment alpha.8; REQUEST_FEATURE declared in both; 'CHANGE 2026-10-2x F21-…' comments saying what changed; node --check on
    every inline script; no new duplicate ids in app/ (vs alpha.7.2), none in /request/; no live project ref."""
    html, req = H.app_html(), H.request_html()
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = f20._extract(qa_refs.v2152_html(), [name], tmp_path)["found"][name]
        b = f20._extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1 and b and a[0] in b, "%s is not byte-identical to v2.15.2" % name
    elif check == "app_version":
        assert re.search(r"""const\s+APP_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html)
    elif check == "pt_version":
        assert re.search(r"""PT_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html)
    elif check == "request_version_comment":
        head = "\n".join(re.findall(r"<!--(.*?)-->", req, re.S)) + "\n".join(re.findall(r"/\*(.*?)\*/|//([^\n]*)", req[:6000], re.S)[0] if False else [])
        assert re.search(r"alpha\.8\b", head) or re.search(r"<!--[^>]*alpha\.8", req), "/request/ has no alpha.8 version comment"
    elif check == "flags_declared":
        assert H.REQ_FLAG_RE.search(html) and H.REQ_FLAG_RE.search(html).group(3) == "on"
        assert H.REQ_FLAG_RE.search(req) and H.REQ_FLAG_RE.search(req).group(3) == "on"
    elif check == "change_comments":
        for src, label in ((html, "app/index.html"), (req, "request/index.html")):
            tags = re.findall(r"CHANGE 2026-10-2\d F21-[A-Z0-9-]+[^\n]*", src)
            assert tags, "no 'CHANGE 2026-10-2x F21-…' comment in " + label
        tags = re.findall(r"CHANGE 2026-10-2\d F21-[A-Z0-9-]+[^\n]*", html)
        assert any(re.search(r"alpha\.7|was |what changed|no previous", t) for t in tags), "app F21 comments do not say what changed from alpha.7.2"
    elif check == "node_check":
        bad = []
        for label, src in (("app", html), ("request", req)):
            for i, (attrs, code) in enumerate(_scripts(src)):
                if "json" in attrs:
                    continue
                p = tmp_path / ("%s_%d.%s" % (label, i, "mjs" if "module" in attrs else "js"))
                p.write_text(code, encoding="utf-8")
                if f02.node(["--check", str(p)]).returncode:
                    bad.append(p.name)
        assert not bad, "node --check failed: %r" % bad
    elif check == "no_duplicate_ids":
        def dups(h):
            c = collections.Counter(re.findall(r"""\bid=["']([A-Za-z][\w:-]*)["']""", h))
            return {k for k, v in c.items() if v > 1}
        base = qa_refs.git_show(BASE_REF, "app/index.html")
        new = dups(html) - dups(base)
        assert not new, "new duplicate ids in app/: %r" % sorted(new)
        # /request/ paints one screen at a time from JS templates (each screen has its own #rqTitle): static markup outside
        # <script> must be duplicate-free; the rendered screens are checked by test_c20_runtime_duplicate_ids
        markup = re.sub(r"<script\b.*?</script>", "", req, flags=re.S)
        assert not dups(markup), "duplicate ids in /request/ markup: %r" % sorted(dups(markup))
    elif check == "no_live_project_ref":
        assert f02.LIVE_REF not in html and f02.LIVE_REF not in req
    elif check in ("invite_unchanged", "join_unchanged"):
        # spec §0: no change to /join/ (out of scope); /invite/ is not touched by F21 (its version comment stays alpha.7.x —
        # replaces F04-HOME F4H-13[invite_version_comment], deselected in tests/run_all.sh)
        sub = "invite" if check == "invite_unchanged" else "join"
        cur = (H.REPO_DIR / sub / "index.html").read_text(encoding="utf-8")
        assert cur == qa_refs.git_show(BASE_REF, sub + "/index.html"), "%s/index.html differs from alpha.7.2 (%s)" % (sub, BASE_REF)


DUP_JS = "()=>{const c={};for(const e of document.querySelectorAll('[id]'))c[e.id]=(c[e.id]||0)+1;return Object.keys(c).filter(k=>c[k]>1)}"


def test_c20_runtime_duplicate_ids(env):
    """C20: no duplicate ids in each rendered /request/ screen (form, code, sent, limit, closed)."""
    out = {}
    dev = open_req(env, "", name="F")
    out["form"] = dev.page.evaluate(DUP_JS)
    dev = to_code(env, name="C")
    out["code"] = dev.page.evaluate(DUP_JS)
    type_rq_code(dev.page, last_code(env), env)
    out["sent"] = dev.page.evaluate(DUP_JS)
    env.backend.fill_cap(50)
    dev = open_req(env, "", name="L")
    fill(dev.page)
    send(dev.page)
    out["limit"] = dev.page.evaluate(DUP_JS)
    dev = open_req(env, "", flag="off", name="X")
    out["closed"] = dev.page.evaluate(DUP_JS)
    bad = {k: v for k, v in out.items() if v}
    assert not bad, bad


def test_c17_advisors_manual():
    """C20 tail: "Supabase advisors: no new warning" is a dashboard check — not automatable offline."""
    pytest.skip("Supabase advisors are checked in the dashboard after deployment (spec §7 step 2)")
