"""Lonely Planner F10 QA · Playwright black-box suite (trip currencies) · version 1.0.1
CHANGE 2026-11-07 F10-QA-FIX-00: 1.0.0 → 1.0.1 — two test-side fixes after the implementation landed (FIX-01, FIX-02 below);
  no assertion about behaviour was weakened. Selectors needed no dev-notes ids.
CHANGE 2026-11-07 F10-QA-02: new file (no previous version).

Contract: docs/F10_spec.md (§1 TRIPCUR, §2 rates, §3 places P1–P10, §4 expenses, §5 flag, §6 criteria 1–13) ONLY. The F10
implementation and docs/F10_dev_notes.md were not read while these tests were written. alpha.8 ids (4ca777b) are used for the
places the spec changes in content only; new UI is found by spec texts / aria-labels (see harness.py header).
Every test names its criterion: test_cNN_… (NN = spec §6 number). 390×844 Chromium, he-IL, Asia/Jerusalem, clock installed at
2026-10-12 06:00Z (F04-HOME harness). Fixtures V T A G S of §6 are built in harness.F10Backend.fixture().

Reading of the spec where it is internally loose (also listed in docs/qa/F10_QA.md):
- Criterion 1 says "every text in P1–P10 equals alpha.8 except chip order", but the §3 table itself changes some V texts
  (P2 placeholder "סכום ב-<sym>", P6 "<home sym> ⇄ <local sym>" = "₪ ⇄ ₫", P5 "הוספה כהוצאה", P3 header / "1,000 VND",
  P1/P5 defaults = local, P10 v2 shape). Where §3 defines the new text, the §3 form is asserted; everything §3 does not
  name (all P9 amounts, P4 result, P2 calc box, P7 preview, P8, totals) must equal alpha.8 byte for byte.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
from harness import chips, codes, selected, pair, click_chip, set_pair, text, attr, nums, norm, btext  # noqa: E402

from playwright.sync_api import Error as PWError  # noqa: E402

f02, f04, f05, f20 = H.f02, H.f04, H.f05, H.f20
REPO = H.REPO_DIR
VERSION = os.environ.get("QA_EXPECTED_VERSION", "3.0.0-alpha.10")  # CHANGE 2026-11-07 F10B-QA-FIX-01: reads QA_EXPECTED_VERSION, default alpha.10 (was: hardcoded "3.0.0-alpha.9")
TX = {
    "more_aria_re": r"^עוד\s+(\d+)\s+מטבעות:\s*(.+)$",
    "no_rate": "אין שער",
    "no_rate_msg": "אין שער ל-{c} – עדכנו שערים בתקציב",
    "live_unsaved": "שערים חיים · לא נשמרו",
    "viewer": "צפייה בלבד",
    "old_marker": "(₪ מקורי)",
    "add_as_expense": "הוספה כהוצאה",
    "add_re": r"הוספה כהוצאה|הוסף כהוצאה",   # §3 P5 wording or the unchanged alpha.8 button text (criterion 1)
    "save_rates": "שמור שערים",
    "auto": "עדכון אוטומטי",
}


@pytest.fixture(scope="session")
def server():
    s = H.f05.F05Server()
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


def dash(s):
    return norm(s).replace("–", "-").replace("—", "-")


def first_codes(page, row, n=None):
    c = codes(page, row)
    return c[:n] if n else c


def visible_texts(page, sel):
    return text(page, sel) or ""


def errors(dev):
    return H.page_errors(dev)


# =====================================================================================================
# Capture of every P1–P10 place for the V regression (works on alpha.8 and alpha.9: alpha.8 ids only)
# =====================================================================================================
def capture_v(env, dev, chat=False):
    page = dev.page
    out = {}
    H.open_budget(page)
    # P9 · budget totals / category tiles / expense list / daily burn / personal
    for sel in ("#budgetSpentAmt", "#budgetAvailAmt", "#budgetAvailSub", "#catChips", "#expenseList", "#budgetBurn",
                "#personalSpentSummary"):
        out["P9" + sel] = text(page, sel)
    # P9 · expense detail card (⋯ on the first expense row)
    try:
        page.locator("[data-ui-exp-more]").first.click(timeout=3000)
        page.wait_for_timeout(500)
        out["P9 detail"] = text(page, "#uiActTitle")
        page.keyboard.press("Escape")
        page.evaluate("()=>{const x=document.querySelector('[data-ui-x]');if(x)x.click()}")
        page.wait_for_timeout(300)
    except PWError:
        out["P9 detail"] = None
    # P1 / P2 · add-expense chips, VND calc
    out["P1 chips"] = sorted(codes(page, "P1"))
    click_chip(page, "P1", "VND")
    page.fill("#expenseAmount", "400000")
    out["P2 placeholder VND"] = attr(page, "#expenseAmount", "placeholder")
    out["P2 btn VND"] = text(page, "#expenseCalcBtn")
    page.locator("#expenseCalcBtn").click()
    page.wait_for_timeout(500)
    out["P2 calcbox"] = text(page, "#expenseCalcBox")
    click_chip(page, "P1", "ILS")
    out["P2 placeholder ILS"] = attr(page, "#expenseAmount", "placeholder")
    out["P2 calc row ILS visible"] = H.f20.is_vis(page, "#expenseCalcRow")
    page.fill("#expenseAmount", "")
    # P3 · rate rows
    rr = H.rate_rows(page) or {}
    out["P3 rows"] = [(re.sub(r"1,?000", "1000", r["label"]), float(r["value"] or 0)) for r in rr.get("rows", [])]
    # P4 · budget converter VND→ILS 100000
    out["P4 chips"] = sorted(codes(page, "P4"))
    out["P4 set"] = set_pair(page, "P4", "VND", "ILS")
    page.fill("#fxAmount", "100000")
    page.locator("#fxCalculate").click()
    page.wait_for_timeout(500)
    out["P4 result"] = text(page, "#fxResult")
    # P7 · quick expense preview
    out["P7 chips"] = sorted(codes(page, "P7"))
    click_chip(page, "P7", "VND")
    page.fill("#qeAmount", "250000")
    page.wait_for_timeout(500)
    out["P7 preview"] = text(page, "#qeConv")
    page.fill("#qeAmount", "")
    # P6 · floating button ; P5 · quick sheet VND→ILS 100000
    out["P6"] = text(page, "#globalFxBtn")
    H.open_quick_fx(page)
    out["P5 chips"] = sorted(codes(page, "P5"))
    set_pair(page, "P5", "VND", "ILS")
    page.fill("#quickFxAmount", "100000")
    page.locator("#quickFxCalculate").click()
    page.wait_for_timeout(500)
    out["P5 result nums"] = nums(text(page, "#quickFxResult"))
    out["P5 add visible"] = H.f20.is_vis(page, "#quickFxAddExpenseBtn")
    out["P5 add text"] = text(page, "#quickFxAddExpenseBtn")
    f02.close_modal(page, "fxQuickModal")
    # P8 · reservation cost placeholder (attribute; the modal does not need to open)
    out["P8"] = attr(page, "#resCost", "placeholder")
    # home budget widget (P9)
    H.tab(page, "home")
    page.wait_for_timeout(500)
    out["P9#homeBurn"] = text(page, "#homeBurn")
    return out


def chat_fx(env, dev, question="כמה זה 100 דולר?"):
    page = dev.page
    n = len(env.chat_bodies)
    page.evaluate("()=>{const b=document.getElementById('chatFab');if(b)b.click()}")
    page.wait_for_timeout(500)
    page.fill("#chatInput", question)
    page.locator("#chatSendBtn").click()
    H.wait_until(lambda: len(env.chat_bodies) > n, 10, page)
    return env.chat_bodies[-1].get("fx") if len(env.chat_bodies) > n else "NO REQUEST"


# =====================================================================================================
# Criterion 1 · V regression vs alpha.8
# =====================================================================================================
def test_c01_v_regression_vs_alpha8(env):
    """C1: V with saved legacy rates — every P1–P10 number/text equals alpha.8 (4ca777b) except chip order and the texts the
    §3 table itself redefines (asserted in their §3 form). Totals of the expense fixture identical."""
    be = env.backend
    tid = be.fixture("V", expenses=H.V_EXPENSES, budget=23000, fxrates=H.V_LEGACY_RATES)
    H.serve_src(env, H.flip_chat(H.base_html(), "on"))
    old = H.boot(env, tid, name="OLD")
    base = capture_v(env, old)
    base_fx = chat_fx(env, old)
    env.server.reset()
    H.serve_src(env, H.flip_chat(H.app_html(), "on"))
    dev = H.boot(env, tid, name="NEW")
    new = capture_v(env, dev)
    new_fx = chat_fx(env, dev)
    P = []
    # harness sanity (the alpha.8 run must have produced the fixture's numbers)
    assert base["P9#budgetSpentAmt"] == "458.5 ₪", "harness: alpha.8 total %r" % base["P9#budgetSpentAmt"]
    same = [k for k in base if k.startswith("P9")] + ["P2 calcbox", "P4 result", "P7 preview", "P8", "P5 result nums",
                                                      "P5 add visible", "P2 calc row ILS visible"]
    for k in same:
        if norm(str(base[k])) != norm(str(new[k])):
            P.append("%s differs from alpha.8:\n   alpha.8: %r\n   alpha.9: %r" % (k, base[k], new[k]))
    for k in ("P1 chips", "P4 chips", "P5 chips", "P7 chips"):
        if new[k] != sorted(H.LIST["V"]) and not (k == "P7 chips" and set(new[k]) == set(H.LIST["V"])):
            P.append("%s: currencies %r, want the V list %r" % (k, new[k], H.LIST["V"]))
    # P3: same rates, rows in list order except home, VND per 1,000
    if sorted(new["P3 rows"]) != sorted(base["P3 rows"]):
        P.append("P3 rate rows: alpha.8 %r, alpha.9 %r" % (base["P3 rows"], new["P3 rows"]))
    # §3-redefined texts (asserted in §3 form)
    if new["P2 placeholder VND"] != "סכום ב-₫":
        P.append("P2 placeholder (VND picked) %r, want 'סכום ב-₫' (§3 P2)" % new["P2 placeholder VND"])
    if new["P2 placeholder ILS"] not in ("סכום ב-₪", base["P2 placeholder ILS"]):
        P.append("P2 placeholder (ILS picked) %r" % new["P2 placeholder ILS"])
    if "חשב לשקלים" not in (new["P2 btn VND"] or ""):
        P.append("P2 button %r, want 'חשב לשקלים'" % new["P2 btn VND"])
    if new["P6"] != "₪ ⇄ ₫":
        P.append("P6 %r, want '₪ ⇄ ₫' (§3 P6: <home sym> ⇄ <local sym>)" % new["P6"])
    if not re.search(TX["add_re"], new["P5 add text"] or ""):
        P.append("P5 add button %r, want 'הוספה כהוצאה' (§3 P5) or alpha.8 'הוסף כהוצאה'" % new["P5 add text"])
    # P10 chat fx: {base, rates} + home/local, numbers equal to the legacy ones
    if not isinstance(new_fx, dict):
        P.append("P10: no fx in the chat request (%r)" % new_fx)
    else:
        r = new_fx.get("rates") or {}
        if new_fx.get("base") != "ILS" or new_fx.get("home") != "ILS" or new_fx.get("local") != "VND":
            P.append("P10 fx base/home/local %r" % {k: new_fx.get(k) for k in ("base", "home", "local")})
        want = {"USD": 3.6, "EUR": 3.9, "VND": 0.14 / 1000}
        for c, v in want.items():
            if not isinstance(r.get(c), (int, float)) or abs(r[c] - v) > 1e-9:
                P.append("P10 fx.rates.%s=%r, want %r (homePerUnit)" % (c, r.get(c), v))
    if base_fx != {"USD": 3.6, "EUR": 3.9, "VND": 0.14}:
        P.append("harness: alpha.8 chat fx %r" % base_fx)
    P += ["page error: %s" % e for e in errors(dev)]
    assert not P, "\n".join(P)


def test_c01_v_defaults_and_order(env):
    """C1 + D6 + §3 P1/P4/P5/P7: V chip order VND ₪ $ € (VND first = rightmost in RTL); defaults: P1/P7 = local VND on a
    fresh device, P4/P5 from VND to ILS; TRIPCUR as §1."""
    be = env.backend
    tid = be.fixture("V", expenses=H.V_EXPENSES, fxrates=H.V_LEGACY_RATES)
    dev = H.boot(env, tid)
    page = dev.page
    P = []
    tc = H.tripcur(page)
    if not isinstance(tc, dict):
        P.append("window.__PT.tripcur missing (%r)" % tc)
    else:
        if tc.get("home") != "ILS" or tc.get("local") != "VND" or tc.get("list") != H.LIST["V"]:
            P.append("tripcur %r" % {k: tc.get(k) for k in ("home", "local", "list")})
        if (tc.get("unit") or {}).get("VND") != 1000:
            P.append("tripcur.unit.VND %r, want 1000" % (tc.get("unit") or {}).get("VND"))
    H.open_budget(page)
    for row in ("P1", "P4", "P7"):
        cs = chips(page, row)
        if [c["code"] for c in cs] != H.LIST["V"]:
            P.append("%s order %r, want %r" % (row, [c["code"] for c in cs], H.LIST["V"]))
        elif row != "P7" and not cs[0]["x"] > cs[-1]["x"]:
            P.append("%s: first chip is not the rightmost (RTL)" % row)
    if selected(page, "P1") != ["VND"]:
        P.append("P1 default %r, want VND" % selected(page, "P1"))
    if selected(page, "P7") != ["VND"]:
        P.append("P7 default %r, want VND" % selected(page, "P7"))
    if pair(page, "P4") != ("VND", "ILS"):
        P.append("P4 default %r, want VND→ILS" % (pair(page, "P4"),))
    H.open_quick_fx(page)
    if codes(page, "P5") != H.LIST["V"]:
        P.append("P5 order %r" % codes(page, "P5"))
    if pair(page, "P5") != ("VND", "ILS"):
        P.append("P5 default %r, want VND→ILS (§3 P5 = P4)" % (pair(page, "P5"),))
    assert not P, "\n".join(P)


def test_c01_v_new_expense_shape(env):
    """C1 + §4: in V a VND expense saves amount in ₪ (same number as alpha.8), homeCurrency 'ILS', originalAmount /
    originalCurrency; an ILS expense has no original fields. Existing expenses are not rewritten."""
    be = env.backend
    tid = be.fixture("V", expenses=H.V_EXPENSES, fxrates=H.V_LEGACY_RATES)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    click_chip(page, "P1", "VND")
    page.fill("#expenseDescription", "QA VND")
    page.fill("#expenseAmount", "100000")
    page.locator("#expenseCalcBtn").click()
    page.wait_for_timeout(400)
    page.locator("#saveExpense").click()
    H.wait_until(lambda: "QA VND" in (be.kv(tid, "expenses") or ""), 10, page)
    click_chip(page, "P1", "ILS")
    page.fill("#expenseDescription", "QA ILS")
    page.fill("#expenseAmount", "33")
    page.locator("#saveExpense").click()
    H.wait_until(lambda: "QA ILS" in (be.kv(tid, "expenses") or ""), 10, page)
    items = be.kv_json(tid, "expenses", [])
    P = []
    if items[:len(H.V_EXPENSES)] != H.V_EXPENSES:
        P.append("existing expenses were rewritten")
    v = next((e for e in items if e.get("description") == "QA VND"), None)
    i = next((e for e in items if e.get("description") == "QA ILS"), None)
    if not v or abs(float(v.get("amount", 0)) - 14) > 1e-6 or v.get("homeCurrency") != "ILS" or v.get("originalCurrency") != "VND" \
            or v.get("originalAmount") != 100000:
        P.append("VND expense %r (want amount 14, homeCurrency ILS, originalAmount 100000, originalCurrency VND)" % v)
    if not i or i.get("amount") != 33 or i.get("homeCurrency") != "ILS" or "originalCurrency" in i or "originalAmount" in i:
        P.append("ILS expense %r (want amount 33, homeCurrency ILS, no original fields)" % i)
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 2 · T
# =====================================================================================================
def test_c02_thailand(env):
    """C2: T defaults to THB in P1/P4/P5/P7; P6 "₪ ⇄ ฿"; P3 rows THB, USD, EUR with header "שערים בשקלים"; no VND / ₫
    anywhere in the budget tab, the FX sheet or the floating button."""
    be = env.backend
    tid = be.fixture("T", expenses=H.T_EXPENSES)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    P = []
    for row in ("P1", "P7"):
        if codes(page, row) != H.LIST["T"]:
            P.append("%s chips %r, want %r" % (row, codes(page, row), H.LIST["T"]))
        if selected(page, row) != ["THB"]:
            P.append("%s default %r, want THB" % (row, selected(page, row)))
    if pair(page, "P4") != ("THB", "ILS"):
        P.append("P4 default %r, want THB→ILS" % (pair(page, "P4"),))
    rr = H.rate_rows(page) or {}
    labs = [r["label"] for r in rr.get("rows", [])]
    if labs != ["1 THB", "1 USD", "1 EUR"]:
        P.append("P3 rows %r, want ['1 THB','1 USD','1 EUR']" % labs)
    if "שערים בשקלים" not in (rr.get("text") or ""):
        P.append("P3 header 'שערים בשקלים' missing")
    t = text(page, "#budget") or ""
    for bad in ("VND", "₫", "דונג"):
        if bad in t:
            P.append("budget tab shows %r" % bad)
    if text(page, "#globalFxBtn") != "₪ ⇄ ฿":
        P.append("P6 %r, want '₪ ⇄ ฿'" % text(page, "#globalFxBtn"))
    H.open_quick_fx(page)
    if codes(page, "P5") != H.LIST["T"]:
        P.append("P5 chips %r" % codes(page, "P5"))
    if pair(page, "P5") != ("THB", "ILS"):
        P.append("P5 default %r, want THB→ILS" % (pair(page, "P5"),))
    q = text(page, "#fxQuickModal") or ""
    for bad in ("VND", "₫"):
        if bad in q:
            P.append("FX sheet shows %r" % bad)
    # P5 result uses symbols; target = home → "הוספה כהוצאה"
    page.fill("#quickFxAmount", "1000")
    page.locator("#quickFxCalculate").click()
    page.wait_for_timeout(500)
    res = text(page, "#quickFxResult") or ""
    if "฿" not in res or "₪" not in res:
        P.append("P5 result %r does not use symbols ฿ / ₪" % res)
    want = 1000 * H.home_per_unit("ILS", "THB")   # live in-memory rates (no saved rates, online)
    if not any(abs(n - round(want, 2)) < 0.02 for n in nums(res)):
        P.append("P5 result %r, want ≈ %.2f ₪ (live homePerUnit)" % (res, want))
    if not H.f20.is_vis(page, "#quickFxAddExpenseBtn") or not re.search(TX["add_re"], text(page, "#quickFxAddExpenseBtn") or ""):
        P.append("P5: 'הוספה כהוצאה' not shown for target = home")
    P += ["page error: %s" % e for e in errors(dev)]
    assert not P, "\n".join(P)


def test_c02_live_defaults_label(env):
    """§2 Defaults: no saved rates + online → live rates fetched once per session, used in memory, shown as
    "שערים חיים · לא נשמרו"; nothing written to trip_kv."""
    be = env.backend
    tid = be.fixture("T")
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    P = []
    if not H.wait_has(page, TX["live_unsaved"], 6):
        P.append("label %r not shown" % TX["live_unsaved"])
    n = len([c for c in env.er_calls if c["url"].startswith(H.ER_URL)])
    if n != 1:
        P.append("er-api called %d times in the session (want 1)" % n)
    if be.kv(tid, "fxrates") is not None:
        P.append("live default rates were saved to trip_kv: %r" % be.kv(tid, "fxrates"))
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 3 · A (home USD)
# =====================================================================================================
def p9_texts(page):
    out = {}
    # CHANGE 2026-11-07 F10-QA-FIX-01: #budgetBurn removed from this list — no such element exists in alpha.8 (4ca777b) or
    #   alpha.9 (renderDailyBurn skips it); the burn widget is #homeBurn, asserted at the end of test_c03. Was: listed here.
    for sel in ("#budgetSpentAmt", "#budgetAvailAmt", "#budgetAvailSub", "#catChips", "#expenseList",
                "#personalSpentSummary", "#qeRecent"):
        out[sel] = text(page, sel) or ""
    return out


def test_c03_uae_dollars_everywhere(env):
    """C3: A — every P9 amount shows "$" and none shows ₪ (except an ILS chip and the "(₪ מקורי)" marker); old ILS expense
    converted with the current rate and marked "(₪ מקורי)" (§4); P2 button "חשב לדולרים"; P8 "עלות ($ / AED)"; P6 "$ ⇄ AED"."""
    be = env.backend
    tid = be.fixture("A", expenses=H.A_EXPENSES, budget=2000, fxrates=H.A_RATES_V2)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    P = []
    tc = H.tripcur(page) or {}
    if tc.get("home") != "USD" or tc.get("local") != "AED" or tc.get("list") != H.LIST["A"]:
        P.append("tripcur %r" % {k: tc.get(k) for k in ("home", "local", "list")} if isinstance(tc, dict) else tc)
    t = p9_texts(page)
    for sel, v in t.items():
        if sel == "#qeRecent":
            continue
        if "$" not in v:
            P.append("P9 %s has no '$': %r" % (sel, v[:160]))
        if "₪" in v.replace(TX["old_marker"], ""):
            P.append("P9 %s shows ₪: %r" % (sel, v[:200]))
        if "ש״ח" in v or 'ש"ח' in v:
            P.append("P9 %s shows ש״ח: %r" % (sel, v[:200]))
    if TX["old_marker"] not in t["#expenseList"]:
        P.append("old ILS expense not marked %r in the expense list" % TX["old_marker"])
    want_total = 50 + 27.23 + 37 * 0.27
    if not any(abs(n - want_total) < 0.02 for n in nums(t["#budgetSpentAmt"])):
        P.append("total %r, want ≈ %.2f $ (old ₪ expense converted at 0.27)" % (t["#budgetSpentAmt"], want_total))
    # P2
    click_chip(page, "P1", "AED")
    if "חשב לדולרים" not in (text(page, "#expenseCalcBtn") or ""):
        P.append("P2 button %r, want 'חשב לדולרים'" % text(page, "#expenseCalcBtn"))
    if attr(page, "#expenseAmount", "placeholder") != "סכום ב-AED":
        P.append("P2 placeholder %r, want 'סכום ב-AED' (AED symbol = code)" % attr(page, "#expenseAmount", "placeholder"))
    click_chip(page, "P1", "USD")
    if H.f20.is_vis(page, "#expenseCalcBtn"):
        P.append("P2 button visible while picked = home (USD)")
    # P7 preview in home currency
    click_chip(page, "P7", "AED")
    page.fill("#qeAmount", "100")
    page.wait_for_timeout(500)
    pv = text(page, "#qeConv") or ""
    if "$" not in pv or "₪" in pv or not any(abs(n - 27.23) < 1.01 for n in nums(pv)):
        P.append("P7 preview %r, want ≈ $27" % pv)
    page.fill("#qeAmount", "")
    if attr(page, "#resCost", "placeholder") != "עלות ($ / AED)":
        P.append("P8 %r, want 'עלות ($ / AED)'" % attr(page, "#resCost", "placeholder"))
    if text(page, "#globalFxBtn") != "$ ⇄ AED":
        P.append("P6 %r, want '$ ⇄ AED'" % text(page, "#globalFxBtn"))
    rr = H.rate_rows(page) or {}
    if "שערים בדולרים" not in (rr.get("text") or ""):
        P.append("P3 header 'שערים בדולרים' missing")
    labs = [r["label"] for r in rr.get("rows", [])]
    if labs != ["1 AED", "1 ILS", "1 EUR"]:
        P.append("P3 rows %r, want ['1 AED','1 ILS','1 EUR']" % labs)
    # expense detail card (P9) for the AED expense and the old ILS one
    for idx, need in ((1, "$"), (2, TX["old_marker"])):
        try:
            page.locator('[data-ui-exp-more="%d"]' % idx).first.click(timeout=3000)
            page.wait_for_timeout(500)
            d = (text(page, "#uiActTitle") or "") + " " + (text(page, ".ui-sheet-h") or "")
            if need not in d or ("₪" in d.replace(TX["old_marker"], "") and need == "$"):
                P.append("expense detail card %d %r (want %r, no ₪)" % (idx, d, need))
            page.evaluate("()=>{const x=document.querySelector('[data-ui-x]');if(x)x.click()}")
            page.wait_for_timeout(300)
        except PWError as e:
            P.append("expense detail card %d not reachable (%s)" % (idx, str(e)[:80]))
    H.tab(page, "home")
    hb = text(page, "#homeBurn") or ""
    if "$" not in hb or "₪" in hb:
        P.append("home budget widget %r" % hb)
    P += ["page error: %s" % e for e in errors(dev)]
    assert not P, "\n".join(P)


def test_c03_uae_aed_expense_saved_in_usd(env):
    """C3 + §4: an AED expense saves amount in USD + homeCurrency 'USD' + originalCurrency 'AED' (+ originalAmount)."""
    be = env.backend
    tid = be.fixture("A", expenses=H.A_EXPENSES, fxrates=H.A_RATES_V2)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    click_chip(page, "P1", "AED")
    page.fill("#expenseDescription", "QA AED")
    page.fill("#expenseAmount", "200")
    page.locator("#expenseCalcBtn").click()
    page.wait_for_timeout(500)
    box = text(page, "#expenseCalcBox") or ""
    page.locator("#saveExpense").click()
    ok = H.wait_until(lambda: "QA AED" in (be.kv(tid, "expenses") or ""), 10, page)
    items = be.kv_json(tid, "expenses", [])
    e = next((x for x in items if x.get("description") == "QA AED"), None)
    P = []
    if not ok or not e:
        P.append("expense not saved (calc box %r)" % box)
    else:
        if abs(float(e.get("amount", 0)) - 200 * 0.2723) > 0.01:
            P.append("amount %r, want %.4f USD" % (e.get("amount"), 200 * 0.2723))
        if e.get("homeCurrency") != "USD" or e.get("originalCurrency") != "AED" or e.get("originalAmount") != 200:
            P.append("fields %r" % e)
    if "$" not in box or "₪" in box:
        P.append("calc box %r should be in $" % box)
    # quick expense in AED
    click_chip(page, "P7", "AED")
    page.fill("#qeAmount", "100")
    page.fill("#qeDesc", "QA QE AED")
    page.locator("#qeSave").click()
    H.wait_until(lambda: "QA QE AED" in (be.kv(tid, "expenses") or ""), 10, page)
    q = next((x for x in be.kv_json(tid, "expenses", []) if x.get("description") == "QA QE AED"), None)
    if not q or abs(float(q.get("amount", 0)) - 27.23) > 0.011 or q.get("homeCurrency") != "USD" or q.get("originalCurrency") != "AED":
        P.append("quick expense %r (want amount 27.23 USD, homeCurrency USD, originalCurrency AED)" % q)
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 4 · G
# =====================================================================================================
def test_c04_greece(env):
    """C4: G — local = EUR (a base currency used by the country); chip order € ₪ $; P6 "₪ ⇄ €"."""
    be = env.backend
    tid = be.fixture("G")
    dev = H.boot(env, tid)
    page = dev.page
    P = []
    tc = H.tripcur(page)
    if not isinstance(tc, dict) or tc.get("local") != "EUR" or tc.get("home") != "ILS" or tc.get("list") != H.LIST["G"]:
        P.append("tripcur %r, want local EUR, list %r" % (tc, H.LIST["G"]))
    H.open_budget(page)
    for row in ("P1", "P4", "P7"):
        if codes(page, row) != H.LIST["G"]:
            P.append("%s order %r, want € ₪ $" % (row, codes(page, row)))
    if selected(page, "P1") != ["EUR"]:
        P.append("P1 default %r, want EUR" % selected(page, "P1"))
    if text(page, "#globalFxBtn") != "₪ ⇄ €":
        P.append("P6 %r, want '₪ ⇄ €'" % text(page, "#globalFxBtn"))
    H.open_quick_fx(page)
    if codes(page, "P5") != H.LIST["G"]:
        P.append("P5 order %r" % codes(page, "P5"))
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 5 · S (6 currencies → 5 + "עוד")
# =====================================================================================================
MORE_SHEET_JS = r"""(rowSel)=>{const row=document.querySelector(rowSel);
 const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden'||+s.opacity===0)return false}return true};
 const cand=[...document.querySelectorAll('button,[role=button],[role=option],[role=radio]')].filter(b=>vis(b)&&!(row&&row.contains(b))&&/(^|\s)(EUR|€)(\s|$)/.test((b.innerText||'').replace(/\s+/g,' ').trim()));
 const inBudgetRows=b=>['#expenseCurRow','#budgetFxRow','#quickFxRow','#qeCurRow'].some(s=>{const r=document.querySelector(s);return r&&r.contains(b)});
 const c=cand.filter(b=>!inBudgetRows(b));if(!c.length)return null;const b=c[0];
 let box=b;for(let a=b.parentElement;a&&a!==document.body;a=a.parentElement){const s=getComputedStyle(a);if(a.getAttribute('role')==='dialog'||s.position==='fixed'){box=a;break}}
 const r=box.getBoundingClientRect();
 return {text:(box.innerText||'').replace(/\s+/g,' ').trim(),chips:[...box.querySelectorAll('button')].filter(vis).map(x=>({t:(x.innerText||'').replace(/\s+/g,' ').trim(),h:x.getBoundingClientRect().height})),
  left:r.left,right:r.right,w:r.width,dir:getComputedStyle(box).direction}}"""


def pick_from_more(page, code_text="EUR"):
    return page.evaluate("""(t)=>{const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
      const rows=['#expenseCurRow','#budgetFxRow','#quickFxRow','#qeCurRow'].map(s=>document.querySelector(s)).filter(Boolean);
      const b=[...document.querySelectorAll('button,[role=button],[role=option],[role=radio]')].filter(b=>vis(b)&&!rows.some(r=>r.contains(b))&&new RegExp('(^|\\\\s)('+t+'|€)(\\\\s|$)').test((b.innerText||'').replace(/\\s+/g,' ').trim()));
      if(!b.length)return false;b[0].click();return true}""", code_text)


@pytest.mark.parametrize("row", ["P1", "P4", "P5", "P7"])
def test_c05_s_five_plus_more(env, row):
    """C5 / §3 / D7: S has 6 currencies → each chip row shows 5 chips + a dashed "עוד" chip (label "עוד" + hidden symbols,
    aria-label "עוד 1 מטבעות: …") that opens a sheet listing EUR; picking EUR closes the sheet and shows EUR selected in the
    5th slot."""
    be = env.backend
    tid = be.fixture("S")
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    if row == "P5":
        H.open_quick_fx(page)
    P = []
    cs = chips(page, row)
    reg = [c for c in cs if not c["more"]]
    more = [c for c in cs if c["more"]]
    if [c["code"] for c in reg] != H.LIST["S"][:5]:
        P.append("%s first chips %r, want %r" % (row, [c["code"] for c in reg], H.LIST["S"][:5]))
    if len(more) != 1:
        P.append("%s: %d 'עוד' chips (row %r)" % (row, len(more), [c["text"] for c in cs]))
    else:
        m = more[0]
        mm = re.match(TX["more_aria_re"], m["aria"])
        if not mm or mm.group(1) != "1" or not ("EUR" in mm.group(2) or "€" in mm.group(2)):
            P.append("%s 'עוד' aria-label %r, want 'עוד 1 מטבעות: €/EUR'" % (row, m["aria"]))
        if "עוד" not in m["text"] or "€" not in m["text"]:
            P.append("%s 'עוד' chip text %r (want 'עוד' + hidden symbol €)" % (row, m["text"]))
        if cs[-1] is not m:
            P.append("%s 'עוד' is not the last chip" % row)
        style = page.evaluate("""(sel)=>{const r=document.querySelector(sel);const b=[...r.querySelectorAll('button')].find(b=>/^עוד/.test(b.getAttribute('aria-label')||''));
          return b?getComputedStyle(b).borderStyle:null}""", H.ROWS[row])
        if style and "dashed" not in style:
            P.append("%s 'עוד' chip border %r (want dashed)" % (row, style))
        H.click_more(page, row)
        sh = page.evaluate(MORE_SHEET_JS, H.ROWS[row])
        if not sh:
            P.append("%s: 'עוד' sheet with EUR did not open" % row)
        else:
            if not pick_from_more(page, "EUR"):
                P.append("%s: EUR chip not clickable in the sheet" % row)
            page.wait_for_timeout(500)
            if page.evaluate(MORE_SHEET_JS, H.ROWS[row]):
                P.append("%s: the sheet stays open after picking" % row)
            after = [c for c in chips(page, row) if not c["more"]]
            if len(after) < 5 or after[4]["code"] != "EUR":
                P.append("%s: 5th slot after picking = %r (want EUR)" % (row, [c["code"] for c in after]))
            elif row in ("P1", "P7") and not after[4]["selected"]:
                P.append("%s: EUR in the 5th slot is not selected" % row)
            elif row in ("P4", "P5") and not (after[4]["src"] or after[4]["dst"]):
                P.append("%s: EUR in the 5th slot is neither source nor target" % row)
    assert not P, "\n".join(P)


def test_c05_s_units_per_1000(env):
    """C5 + C2 (§2 Unit): VND and KHR rate rows read per 1,000 ("1,000 VND", "1,000 KHR"); THB per 1; typed amounts are whole
    units (no ×1000): 100,000 VND in the add-expense calc = 100000 × homePerUnit(VND)."""
    be = env.backend
    tid = be.fixture("S")
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    P = []
    tc = H.tripcur(page) or {}
    if isinstance(tc, dict) and ((tc.get("unit") or {}).get("VND") != 1000 or (tc.get("unit") or {}).get("KHR") != 1000
                                 or (tc.get("unit") or {}).get("THB", 1) != 1):
        P.append("tripcur.unit %r" % tc.get("unit"))
    rr = H.rate_rows(page) or {}
    labs = [r["label"] for r in rr.get("rows", [])]
    want = ["1 THB", "1,000 VND", "1,000 KHR", "1 USD", "1 EUR"]
    if labs != want:
        P.append("P3 rows %r, want %r" % (labs, want))
    vnd = next((r for r in rr.get("rows", []) if r["label"] == "1,000 VND"), None)
    w = 1000 * H.home_per_unit("ILS", "VND")
    if vnd and abs(float(vnd["value"] or 0) - w) > 0.01:
        P.append("1,000 VND row value %r, want ≈ %.4f" % (vnd["value"], w))
    click_chip(page, "P1", "VND")
    page.fill("#expenseAmount", "100000")
    page.locator("#expenseCalcBtn").click()
    page.wait_for_timeout(500)
    box = text(page, "#expenseCalcBox") or ""
    exp = 100000 * H.home_per_unit("ILS", "VND")
    if not any(abs(n - round(exp, 2)) < 0.02 for n in nums(box)):
        P.append("calc box %r, want ≈ %.2f ₪" % (box, exp))
    if "1,000 VND" not in box:
        P.append("calc box rate text %r, want '1,000 VND = …'" % box)
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 6 · rates
# =====================================================================================================
def test_c06_save_writes_v2_and_legacy_and_alpha8_reads_it(env):
    """C6: "שמור שערים" in V writes v2 ({v:2, base:'ILS', rates{VND,USD,EUR}, updatedAt, source}) AND the legacy USD/EUR/VND
    (VND per 1,000) in the same object; the alpha.8 app (4ca777b, getFxRates) reads the saved object correctly."""
    be = env.backend
    tid = be.fixture("V", fxrates=H.V_LEGACY_RATES)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    P = []
    ok = H.set_rate(page, "1 USD", 3.55) and H.set_rate(page, "1 EUR", 3.95) and \
        (H.set_rate(page, "1,000 VND", 0.142) or H.set_rate(page, "1000 VND", 0.142))
    if not ok:
        P.append("rate inputs not found (rows %r)" % (H.rate_rows(page) or {}).get("rows"))
    H.click_button_text(page, TX["save_rates"], "#budget")
    H.wait_until(lambda: "3.55" in (be.kv(tid, "fxrates") or ""), 8, page)
    v = be.kv_json(tid, "fxrates", {})
    if v.get("v") != 2 or v.get("base") != "ILS" or v.get("source") not in ("live", "manual") or not isinstance(v.get("updatedAt"), (int, float)):
        P.append("v2 header %r" % {k: v.get(k) for k in ("v", "base", "source", "updatedAt")})
    r = v.get("rates") or {}
    for c, want in (("USD", 3.55), ("EUR", 3.95), ("VND", 0.000142)):
        if not isinstance(r.get(c), (int, float)) or abs(r[c] - want) > 1e-9:
            P.append("rates.%s=%r, want %r (home per 1 unit)" % (c, r.get(c), want))
    for c, want in (("USD", 3.55), ("EUR", 3.95), ("VND", 0.142)):
        if not isinstance(v.get(c), (int, float)) or abs(v[c] - want) > 1e-9:
            P.append("legacy %s=%r, want %r" % (c, v.get(c), want))
    # an alpha.8 device reads it
    H.serve_src(env, H.base_html())
    old = H.boot(env, tid, name="OLD8")
    H.open_budget(old.page)
    got = [old.page.input_value(s) for s in ("#rateUSD", "#rateEUR", "#rateVND")]
    if [float(x or 0) for x in got] != [3.55, 3.95, 0.142]:
        P.append("alpha.8 reads %r, want [3.55, 3.95, 0.142]" % got)
    assert not P, "\n".join(P)


def test_c06_legacy_object_read_as_v2(env):
    """§2 Reading: a legacy {USD,EUR,VND} object is read as v2 base ILS in an ILS trip (V); ignored in a USD-home trip (A →
    "no saved rates")."""
    be = env.backend
    tid = be.fixture("V", fxrates=H.V_LEGACY_RATES)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    rr = H.rate_rows(page) or {}
    vals = {re.sub(r"1,?000", "1000", r["label"]): float(r["value"] or 0) for r in rr.get("rows", [])}
    assert vals == {"1000 VND": 0.14, "1 USD": 3.6, "1 EUR": 3.9}, "V rate rows %r" % vals


def test_c06_live_fetch_home_per_unit_uae(env):
    """C6: live fetch ("עדכון אוטומטי") in A computes homePerUnit from the stubbed er-api payload: AED ≈ 0.2723 USD,
    ILS = 1/3.7, EUR = 1/0.92; one call to https://open.er-api.com/v6/latest/USD."""
    be = env.backend
    tid = be.fixture("A", fxrates=H.A_RATES_V2)
    env.er_payload = dict(H.ER_PAYLOAD)
    dev = H.boot(env, tid)
    page = dev.page
    H.open_budget(page)
    n0 = len(env.er_calls)
    if not H.click_button_text(page, TX["auto"], "#budget"):
        page.locator("#fxAutoUpdate").click()
    page.wait_for_timeout(1500)
    P = []
    calls = env.er_calls[n0:]
    if len(calls) != 1 or calls[0]["url"] != H.ER_URL:
        P.append("er-api calls %r" % [c["url"] for c in calls])
    rr = H.rate_rows(page) or {}
    vals = {r["label"]: float(r["value"] or 0) for r in rr.get("rows", [])}
    for lab, code in (("1 AED", "AED"), ("1 ILS", "ILS"), ("1 EUR", "EUR")):
        w = H.home_per_unit("USD", code)
        if lab not in vals or abs(vals[lab] - w) > 5e-4:
            P.append("%s = %r, want ≈ %.4f" % (lab, vals.get(lab), w))
    if "1 AED" in vals and abs(vals["1 AED"] - 0.2723) > 5e-4:
        P.append("AED %r not ≈ 0.2723" % vals["1 AED"])
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 7 · missing rate
# =====================================================================================================
def test_c07_missing_rate_offline_uae(env):
    """C7: offline, no saved rates, trip A (TRIPCUR from an earlier online open) → the AED chip shows "אין שער" message and
    conversion is disabled; no exception."""
    be = env.backend
    tid = be.fixture("A")
    env.er_down = True
    dev = H.boot(env, tid)
    H.go_offline(env, dev, True)
    st = H.reboot(dev)
    page = dev.page
    assert st == "app", "offline reboot state %r" % st
    H.open_budget(page)
    P = []
    tc = H.tripcur(page) or {}
    if not isinstance(tc, dict) or tc.get("home") != "USD":
        P.append("offline tripcur %r (cache not used)" % tc)
    msg = TX["no_rate_msg"].format(c="AED")
    rr = H.rate_rows(page) or {}
    if TX["no_rate"] not in (rr.get("text") or ""):
        P.append("P3: no 'אין שער' on the AED row")
    click_chip(page, "P1", "AED")
    page.fill("#expenseAmount", "100")
    btn_disabled = page.evaluate("()=>{const b=document.getElementById('expenseCalcBtn');if(!b)return true;const r=b.getBoundingClientRect();return b.disabled||r.width===0}")
    if not btn_disabled:
        page.locator("#expenseCalcBtn").click()
        page.wait_for_timeout(400)
    if not H.wait_has(page, dash(msg), 3) and not H.wait_has(page, msg, 1):
        P.append("P1/P2: message %r not shown" % msg)
    box = text(page, "#expenseCalcBox") or ""
    if nums(box) and "=" in box:
        P.append("P2 converted without a rate: %r" % box)
    page.fill("#expenseDescription", "QA no rate")
    page.locator("#saveExpense").click()
    page.wait_for_timeout(800)
    if "QA no rate" in (page.evaluate("()=>localStorage.getItem('planner:expenses')||''") or ""):
        P.append("an AED expense was saved without a rate")
    # quick expense + quick FX
    click_chip(page, "P7", "AED")
    page.fill("#qeAmount", "50")
    page.wait_for_timeout(400)
    qv = text(page, "#qeConv") or ""
    if nums(qv) and nums(qv)[0] > 0:
        P.append("P7 preview converted without a rate: %r" % qv)
    H.open_quick_fx(page)
    set_pair(page, "P5", "AED", "USD")
    page.fill("#quickFxAmount", "100")
    page.locator("#quickFxCalculate").click()
    page.wait_for_timeout(400)
    res = text(page, "#quickFxResult") or ""
    if re.search(r"=\s*[\d$]", res) or "NaN" in res or "Infinity" in res:
        P.append("P5 converted without a rate: %r" % res)
    if TX["no_rate"] not in btext(page):
        P.append("P5: no 'אין שער' message")
    P += ["page error: %s" % e for e in errors(dev)]
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 8 · offline cache
# =====================================================================================================
def snapshot_rows(page):
    H.open_budget(page)
    out = {r: [(c["code"], c["text"]) for c in chips(page, r)] for r in ("P1", "P4", "P7")}
    out["P6"] = text(page, "#globalFxBtn")
    out["P8"] = attr(page, "#resCost", "placeholder")
    return out


def test_c08_offline_tripcur_from_cache(env):
    """C8 / §1: after one online open, reload offline → TRIPCUR from the device cache (`pt:<trip>:…:tripcur`), same chips and
    symbols; countries.json / currencies.json are not in the service-worker precache."""
    be = env.backend
    tid = be.fixture("T")
    dev = H.boot(env, tid)
    page = dev.page
    on_tc = H.tripcur(page)
    on = snapshot_rows(page)
    keys = [k for k in H.f06.ls_page(dev) if k.startswith("pt:%s:" % tid) and k.endswith(":tripcur")]
    H.go_offline(env, dev, True)
    st = H.reboot(dev)
    assert st == "app", "offline reboot %r" % st
    P = []
    if not keys:
        P.append("no per-trip '…:tripcur' localStorage key after the online open (keys %r)" %
                 [k for k in H.f06.ls_page(dev) if k.startswith("pt:%s:" % tid)][:20])
    off_tc = H.tripcur(page)
    if not isinstance(on_tc, dict):
        P.append("online tripcur %r" % on_tc)
    elif {k: off_tc.get(k) for k in ("home", "local", "list", "sym")} != {k: on_tc.get(k) for k in ("home", "local", "list", "sym")}:
        P.append("offline tripcur %r != online %r" % (off_tc, on_tc))
    off = snapshot_rows(page)
    if off != on:
        P.append("offline rows differ:\n online %r\n offline %r" % (on, off))
    sw = (REPO / "app" / "sw.js").read_text(encoding="utf-8")
    if "countries.json" in sw or "currencies.json" in sw:
        P.append("sw.js mentions countries.json / currencies.json (must not be precached)")
    assert not P, "\n".join(P)


def test_c08_fallback_no_cache_no_network(env):
    """§1 Fallback: no cache and no network → home ILS, list VND ILS USD EUR, local VND (today's behaviour)."""
    be = env.backend
    tid = be.fixture("T")
    dev = env.new_device("A")
    dev.seed_ls({H.CACHE_KEY: json.dumps({"trip_id": tid, "role": "manager"})})
    # first boot online only to sign in (identity), then wipe the trip cache keys and boot offline
    st = H.reboot(dev)
    assert st == "app"
    # CHANGE 2026-11-07 F10-QA-FIX-02: the cache is wiped from the raw blank page (not the running app page, which wrote it
    #   back before the reload — a harness bug, the device still had a cache). Was: removeItem on the app page.
    dev.page.goto(env.server.origin + f02.BLANK_PATH, wait_until="commit")
    dev.page.evaluate("(p)=>{for(const k of Object.keys(localStorage))if(k.startsWith(p)&&/tripcur/.test(k))localStorage.removeItem(k)}", "pt:%s:" % tid)
    assert not [k for k in H.f06.ls_page(dev) if "tripcur" in k], "harness: tripcur cache not wiped"
    H.go_offline(env, dev, True)
    st = H.reboot(dev)
    assert st == "app", "offline boot %r" % st
    tc = H.tripcur(dev.page)
    assert isinstance(tc, dict) and tc.get("home") == "ILS" and tc.get("local") == "VND" and tc.get("list") == ["VND", "ILS", "USD", "EUR"], \
        "fallback tripcur %r" % tc


# =====================================================================================================
# Criterion 9 · isolation (F20 switcher)
# =====================================================================================================
def switch_to(dev, tid):
    page = dev.page
    H.tab(page, "home")
    btn = page.locator("button[data-pt-switch]").filter(visible=True)
    assert btn.count(), "F20 avatar/switch button not visible"
    btn.first.click()
    page.wait_for_selector("#ptSwitchTrips button.pt-f20-row[data-trip='%s']" % tid, timeout=8000)
    page.locator("#ptSwitchTrips button.pt-f20-row[data-trip='%s']" % tid).click()
    page.wait_for_timeout(1500)
    st = f20.wait_state(page, "app", 20)
    f02.ensure_user(page)
    page.wait_for_timeout(1200)
    return st


def test_c09_switch_trip_rebuilds_rows_picks_per_trip(env):
    """C9: switching T → A with the F20 switcher rebuilds every row (A list, $ home, P6, P8, P3); remembered picks are per
    trip (`planner:lastExpenseCurrency` / `planner:qe:cur` under the per-trip prefix)."""
    be = env.backend
    t = be.fixture("T")
    a = be.fixture("A", fxrates=H.A_RATES_V2)
    dev = H.boot(env, t)
    page = dev.page
    H.open_budget(page)
    click_chip(page, "P1", "USD")
    click_chip(page, "P7", "ILS")
    P = []
    assert switch_to(dev, a) == "app"
    if f20.trip_id_running(page) != a:
        pytest.fail("harness: switch did not enter A")
    H.open_budget(page)
    if H.tripcur(page) is None or (H.tripcur(page) or {}).get("home") != "USD":
        P.append("A tripcur %r" % H.tripcur(page))
    for row in ("P1", "P4", "P7"):
        if codes(page, row) != H.LIST["A"]:
            P.append("A %s %r" % (row, codes(page, row)))
    if selected(page, "P1") != ["AED"] or selected(page, "P7") != ["AED"]:
        P.append("A picks P1 %r P7 %r (want AED = local; T picks must not leak)" % (selected(page, "P1"), selected(page, "P7")))
    if text(page, "#globalFxBtn") != "$ ⇄ AED" or attr(page, "#resCost", "placeholder") != "עלות ($ / AED)":
        P.append("A P6 %r / P8 %r" % (text(page, "#globalFxBtn"), attr(page, "#resCost", "placeholder")))
    labs = [r["label"] for r in (H.rate_rows(page) or {}).get("rows", [])]
    if labs != ["1 AED", "1 ILS", "1 EUR"]:
        P.append("A P3 rows %r" % labs)
    raw = H.f06.ls_page(dev)
    if raw.get("pt:%s:planner:lastExpenseCurrency" % t) != "USD" or raw.get("pt:%s:planner:qe:cur" % t) != "ILS":
        P.append("T picks not stored per trip: %r" % {k: v for k, v in raw.items() if "lastExpenseCurrency" in k or "qe:cur" in k})
    assert switch_to(dev, t) == "app"
    H.open_budget(page)
    if selected(page, "P1") != ["USD"] or selected(page, "P7") != ["ILS"]:
        P.append("back in T: P1 %r P7 %r (want USD / ILS remembered)" % (selected(page, "P1"), selected(page, "P7")))
    if codes(page, "P1") != H.LIST["T"] or text(page, "#globalFxBtn") != "₪ ⇄ ฿":
        P.append("back in T rows %r / P6 %r" % (codes(page, "P1"), text(page, "#globalFxBtn")))
    assert not P, "\n".join(P)


def test_c09_remembered_code_not_in_list_falls_back(env):
    """§3: a remembered code that is not in `list` falls back to `local`."""
    be = env.backend
    tid = be.fixture("T")
    pre = {"pt:%s:planner:lastExpenseCurrency" % tid: "VND", "pt:%s:planner:qe:cur" % tid: "VND"}
    dev = H.boot(env, tid, pre_ls=pre)
    H.open_budget(dev.page)
    assert selected(dev.page, "P1") == ["THB"] and selected(dev.page, "P7") == ["THB"], \
        "P1 %r P7 %r" % (selected(dev.page, "P1"), selected(dev.page, "P7"))


# =====================================================================================================
# Criterion 10 · viewer
# =====================================================================================================
def test_c10_viewer_converts_but_cannot_save_rates(env):
    """C10: a viewer can convert (P4) but "שמור שערים" is blocked by the F06 guard ("צפייה בלבד"); trip_kv unchanged."""
    be = env.backend
    tid = be.fixture("V", role="viewer", fxrates=H.V_LEGACY_RATES)
    before = be.kv(tid, "fxrates")
    dev = H.boot(env, tid, role="viewer")
    page = dev.page
    H.f06.watch(page, TX["viewer"])
    H.open_budget(page)
    P = []
    set_pair(page, "P4", "VND", "ILS")
    page.fill("#fxAmount", "100000")
    page.locator("#fxCalculate").click()
    page.wait_for_timeout(500)
    if 14 not in nums(text(page, "#fxResult")):
        P.append("viewer convert result %r, want 14" % text(page, "#fxResult"))
    H.set_rate(page, "1 USD", 9.99)
    H.click_button_text(page, TX["save_rates"], "#budget")
    page.wait_for_timeout(1500)
    if H.f06.seen_count(page, TX["viewer"]) < 1 and not H.wait_has(page, TX["viewer"], 2):
        P.append("no 'צפייה בלבד' toast")
    if be.kv(tid, "fxrates") != before:
        P.append("viewer changed fxrates: %r" % be.kv(tid, "fxrates"))
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 11 · flag off
# =====================================================================================================
SIG_JS = r"""(sels)=>{const out={};const vis=e=>{for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none')return false}return true};
 const walk=(e,acc)=>{const a=[e.tagName,e.id||'',[...e.classList].sort().join('.'),e.getAttribute('aria-label')||'',e.getAttribute('placeholder')||'',
   Object.keys(e.dataset).sort().map(k=>k+'='+e.dataset[k]).join(','),vis(e)?'v':'h'];
   const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.replace(/\s+/g,' ').trim()).filter(Boolean).join('|');
   acc.push(a.join('~')+(own?' "'+own+'"':''));for(const c of e.children)if(!['SCRIPT','STYLE'].includes(c.tagName))walk(c,acc)};
 for(const s of sels){const e=document.querySelector(s);const acc=[];if(e)walk(e,acc);out[s]=acc}return out}"""


def flag_off_capture(env, dev):
    page = dev.page
    H.open_budget(page)
    H.open_quick_fx(page)
    sig = page.evaluate(SIG_JS, ["#budget", "#fxQuickModal", "#globalFxBtn"])
    f02.close_modal(page, "fxQuickModal")
    return sig


@pytest.mark.parametrize("key", ["V", "T"])
def test_c11_flag_off_dom_equals_alpha8(env, key):
    """C11 / C3 / §5: CURRENCY_FEATURE='off' → the DOM of the budget tab (incl. quick expense card), the FX sheet and the
    floating button equals alpha.8 for V and T (structure, ids, classes, data-*, aria, placeholders, visibility, texts)."""
    be = env.backend
    exps = H.V_EXPENSES if key == "V" else H.T_EXPENSES
    tid = be.fixture(key, expenses=exps, budget=23000, fxrates=H.V_LEGACY_RATES)
    H.serve_src(env, H.base_html())
    a8 = flag_off_capture(env, H.boot(env, tid, name="A8"))
    env.server.reset()
    H.serve_src(env, H.flip_currency(H.app_html(), "off"))
    off = flag_off_capture(env, H.boot(env, tid, name="OFF"))
    P = []
    import difflib
    for s in a8:
        if a8[s] != off[s]:
            d = list(difflib.unified_diff(a8[s], off[s], "alpha.8", "flag off", n=1, lineterm=""))
            P.append("%s differs (%d lines):\n%s" % (s, len(d), "\n".join(d[:30])))
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 12 · 390px
# =====================================================================================================
def chip_heights(page, sel):
    return [(c["text"], round(c["h"])) for c in chips(page, sel) if c["h"] < 44 - 0.5]


def test_c12_390_layout(env):
    """C12: 390px — no horizontal scroll on the budget tab, the FX sheet and the "עוד" sheet; every chip (P1/P4/P5/P7 rows,
    "עוד" chip, sheet chips) ≥44px tall; RTL."""
    be = env.backend
    tid = be.fixture("S", expenses=H.T_EXPENSES)
    dev = H.boot(env, tid)
    page = dev.page
    P = []
    H.open_budget(page)
    if H.hscroll(page) > 1:
        P.append("budget tab: horizontal scroll %dpx" % H.hscroll(page))
    if page.evaluate("()=>document.documentElement.getAttribute('dir')") != "rtl":
        P.append("html not dir=rtl")
    for row in ("P1", "P4", "P7"):
        small = chip_heights(page, row)
        if small:
            P.append("%s chips < 44px: %r" % (row, small))
        rd = page.evaluate("(s)=>{const e=document.querySelector(s);return e?getComputedStyle(e).direction:null}", H.ROWS[row])
        if rd != "rtl":
            P.append("%s direction %r" % (row, rd))
    H.click_more(page, "P1")
    sh = page.evaluate(MORE_SHEET_JS, H.ROWS["P1"])
    if not sh:
        P.append("'עוד' sheet did not open")
    else:
        if H.hscroll(page) > 1 or sh["left"] < -0.5 or sh["right"] > 390.5:
            P.append("'עוד' sheet overflows (scroll %d, box %.0f..%.0f)" % (H.hscroll(page), sh["left"], sh["right"]))
        small = [c for c in sh["chips"] if c["h"] < 43.5 and c["t"] not in ("×", "✕")]
        if small:
            P.append("'עוד' sheet chips < 44px: %r" % small)
        if sh["dir"] != "rtl":
            P.append("'עוד' sheet direction %r" % sh["dir"])
        page.keyboard.press("Escape")
        pick_from_more(page, "EUR")
        page.wait_for_timeout(300)
    H.open_quick_fx(page)
    if H.hscroll(page) > 1:
        P.append("FX sheet: horizontal scroll %dpx" % H.hscroll(page))
    small = chip_heights(page, "P5")
    if small:
        P.append("P5 chips < 44px: %r" % small)
    box = page.evaluate("()=>{const b=document.querySelector('#fxQuickModal .modal-box');if(!b)return null;const r=b.getBoundingClientRect();return [r.left,r.right]}")
    if box and (box[0] < -0.5 or box[1] > 390.5):
        P.append("FX sheet box outside 390px: %r" % box)
    assert not P, "\n".join(P)


# =====================================================================================================
# Criterion 13 · no server change + static (§5)
# =====================================================================================================
def git(*a):
    return subprocess.run(["git", "-C", str(REPO)] + list(a), capture_output=True, text=True).stdout


STATIC = ["no_migration_or_function_change", "csp_unchanged", "versions", "flag", "changelog", "change_comments", "sw_precache"]


@pytest.mark.parametrize("check", STATIC)
def test_c13_static(check):
    """C13 + §5: migrations and supabase/functions untouched vs 4ca777b; CSP unchanged (no new origin); PT_VERSION and
    APP_VERSION '3.0.0-alpha.9'; CURRENCY_FEATURE='on' next to REQUEST_FEATURE; CHANGELOG entry; CHANGE … F10- comments;
    countries.json / currencies.json not precached."""
    src = H.app_html()
    base = H.base_html()
    if check == "no_migration_or_function_change":
        d = git("diff", "--name-only", H.BASE_REF, "--", "supabase").split()
        assert not d, "supabase/ changed vs alpha.8: %r" % d
    elif check == "csp_unchanged":
        rx = re.compile(r'<meta[^>]+Content-Security-Policy[^>]*>', re.I)
        assert rx.findall(src) == rx.findall(base), "CSP meta changed"
        hosts = lambda s: set(re.findall(r"https://([a-z0-9.-]+)", s))  # noqa: E731
        new = hosts(src) - hosts(base)
        assert not new, "new network origins in app/index.html: %r" % sorted(new)
    elif check == "versions":
        for n in ("APP_VERSION", "PT_VERSION"):
            assert re.search(r"""%s\s*=\s*['"]%s['"]""" % (n, re.escape(VERSION)), src), "%s is not %s" % (n, VERSION)
    elif check == "flag":
        m = re.search(r"""const\s+CURRENCY_FEATURE\s*=\s*['"]on['"]""", src)
        assert m, "const CURRENCY_FEATURE='on' missing"
        r = re.search(r"const\s+REQUEST_FEATURE\s*=", src)
        assert r and abs(src[:m.start()].count("\n") - src[:r.start()].count("\n")) <= 15, "CURRENCY_FEATURE not next to REQUEST_FEATURE"
    elif check == "changelog":
        cl = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        assert VERSION in cl and "F10" in cl, "CHANGELOG has no 3.0.0-alpha.9 / F10 entry"
    elif check == "change_comments":
        tags = re.findall(r"CHANGE 2026-11-\d\d F10-[A-Z]+-\d+", src)
        assert len(tags) >= 10, "only %d 'CHANGE 2026-11-xx F10-<AREA>-NN' comments" % len(tags)
        assert re.search(r"CHANGE 2026-11-\d\d F10-VER-0\d", src), "no F10-VER-0N comment"
    elif check == "sw_precache":
        sw = (REPO / "app" / "sw.js").read_text(encoding="utf-8")
        assert "countries.json" not in sw and "currencies.json" not in sw, "sw.js precaches the JSON files"


def test_c11_flag_off_behaviour_equals_alpha8(env):
    """C11 / §5 (behaviour, beyond the DOM): with CURRENCY_FEATURE='off' the full V capture of P1–P10 (texts, numbers, chip
    sets, placeholders, totals, chat fx) is identical to alpha.8 — no §3 text applies when the flag is off."""
    be = env.backend
    tid = be.fixture("V", expenses=H.V_EXPENSES, budget=23000, fxrates=H.V_LEGACY_RATES)
    H.serve_src(env, H.flip_chat(H.base_html(), "on"))
    old = H.boot(env, tid, name="OLD")
    base, base_fx = capture_v(env, old), chat_fx(env, old)
    env.server.reset()
    H.serve_src(env, H.flip_chat(H.flip_currency(H.app_html(), "off"), "on"))
    dev = H.boot(env, tid, name="OFF")
    off, off_fx = capture_v(env, dev), chat_fx(env, dev)
    P = ["%s: alpha.8 %r / off %r" % (k, base[k], off.get(k)) for k in base if norm(str(base[k])) != norm(str(off.get(k)))]
    if base_fx != off_fx:
        P.append("chat fx: alpha.8 %r / off %r" % (base_fx, off_fx))
    if H.tripcur(dev.page) not in (None,):
        P.append("window.__PT.tripcur exposed with the flag off: %r" % H.tripcur(dev.page))
    P += ["page error: %s" % e for e in errors(dev)]
    assert not P, "\n".join(P)
