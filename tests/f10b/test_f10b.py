"""Lonely Planner F10b QA · Playwright black-box suite (trip currencies screen) · version 1.0.0
CHANGE 2026-11-07 F10B-QA-02: new file (no previous version).

Contract: docs/F10b_spec.md ONLY (§0 server facts emulated in harness.F10bBackend, §1–§8, criteria §9 1–15; 16 = the F10
suite run separately; 17 = phone check, not here). The F10B implementation blocks and docs/F10b_dev_notes.md were not read
while these tests were written. Every test names its criterion: test_cNN_… . 390×844 Chromium, he-IL.
Fixtures (§9): S (ILS; TH VN KH; 6), E (ILS; GB; 3), F (S + MYR SGD IDR PHP = 10), `laos=True` adds trip country LA.
"""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
from harness import norm, text, vis, writes, eqf, screen  # noqa: E402

f02 = H.f02
S_LIST = ["THB", "VND", "KHR", "ILS", "USD", "EUR"]
KHR_EXP = [
    {"description": "טוק טוק", "amount": 30, "originalAmount": 100000, "originalCurrency": "KHR", "category": "transport",
     "dayIndex": 0, "by": "אור", "createdAt": 1789900000000, "homeCurrency": "ILS"},
    {"description": "שוק", "amount": 12, "originalAmount": 40000, "originalCurrency": "KHR", "category": "food",
     "dayIndex": 1, "by": "אור", "createdAt": 1789910000000, "homeCurrency": "ILS"},
    {"description": "מקדש", "amount": 45, "originalAmount": 150000, "originalCurrency": "KHR", "category": "attractions",
     "dayIndex": 2, "by": "אור", "createdAt": 1789920000000, "homeCurrency": "ILS"},
    {"description": "פאד תאי", "amount": 20, "originalAmount": 200, "originalCurrency": "THB", "category": "food",
     "dayIndex": 3, "by": "אור", "createdAt": 1789930000000, "homeCurrency": "ILS"},
]


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


def start(env, key, role="manager", **kw):
    tid = env.backend.fixture(key, role=role, **kw)
    dev = H.boot(env, tid, role=role)
    return tid, dev, dev.page


def codes_of(be, tid):
    return [r["currency_code"] for r in be.cur_rows(tid)]


def chip_text(page, row="P1"):
    """All chip texts + "עוד" aria of a chip row (to see a code / symbol anywhere in it)."""
    return " ".join("%s %s %s" % (c["code"] or "", c["text"], c["aria"]) for c in H.h10.chips(page, row))


def done_swap_pick(page):
    """After choosing in the picker: the spec allows the swap sheet to open on the choice or after confirm."""
    if not H.wait_vis(page, H.SWAP, 1.5):
        if vis(page, "#ptF10bConfirm"):
            H.confirm(page)
    return H.wait_vis(page, H.SWAP, 4)


def errs(dev):
    return ["page error: %s" % e for e in H.page_errors(dev)]


# =====================================================================================================
# 1 · entry row + list
# =====================================================================================================
@pytest.mark.parametrize("role", ["manager", "editor"])
def test_c01_more_row_and_list(env, role):
    tid, dev, page = start(env, "S", role)
    P = []
    H.tab(page, "more")
    if not H.wait_vis(page, "#ptF10bRow"):
        pytest.fail("#ptF10bRow not visible for %s" % role)
    rt = text(page, "#ptF10bRow")
    if "מטבעות" not in rt or "6 מתוך 10" not in rt:
        P.append("#ptF10bRow text %r (want 'מטבעות' + '6 מתוך 10')" % rt)
    order = page.evaluate("""()=>{const r=document.getElementById('ptF10bRow');
      const f=[...document.querySelectorAll('#more *')].find(e=>e.children.length<4&&(e.innerText||'').includes('חברים וקישור')&&!e.contains(r));
      if(!f)return 'no-f06';return (f.compareDocumentPosition(r)&Node.DOCUMENT_POSITION_FOLLOWING)?'after':'before'}""")
    if order == "before":
        P.append("#ptF10bRow is before the F06 row 'חברים וקישור' (§2: after it)")
    page.locator("#ptF10bRow").click()
    if not H.wait_vis(page, "#ptF10bPanel"):
        pytest.fail("#ptF10bPanel did not open")
    page.wait_for_timeout(600)
    sc = screen(page)
    base = [r["code"] for r in sc["rows"] if r["group"] == "base"]
    other = [r["code"] for r in sc["rows"] if r["group"] == "other"]
    if base != ["ILS", "USD", "EUR"]:
        P.append("base group %r, want ILS USD EUR" % base)
    if other != ["THB", "VND", "KHR"]:
        P.append("other group %r, want THB VND KHR (sort order)" % other)
    pt = text(page, "#ptF10bPanel")
    if pt.count("קבוע") < 3:
        P.append("'קבוע' appears %d× (want ≥3 base rows)" % pt.count("קבוע"))
    for w in ("מטבע הבית", "בסיס", "🇹🇭 תאילנד", "🇻🇳 וייטנאם", "🇰🇭 קמבודיה", "מטבעות"):
        if w not in pt:
            P.append("screen lacks %r" % w)
    sub = text(page, "#ptF10bSub")
    if "6 מתוך 10" not in sub or H.FIX_NAME("S") not in sub:
        P.append("#ptF10bSub %r (want '<trip name> · 6 מתוך 10')" % sub)
    for s in ("#globalFxBtn", ".tab[data-panel=\"more\"]"):
        if not vis(page, s):
            P.append("%s hidden on the screen (§3: stays)" % s)
    if not page.evaluate("()=>{const t=document.querySelector('.tab[data-panel=\"more\"]');return !!t&&(t.classList.contains('active')||t.getAttribute('aria-selected')==='true')}"):
        P.append("'עוד' tab not active on the screen")
    if role == "manager" and sorted(a["code"] for a in sc["acts"]) != ["KHR", "THB", "VND"]:
        P.append("⋯ buttons %r (manager: THB VND KHR)" % sc["acts"])
    if role == "manager":
        a = [x for x in sc["acts"] if x["code"] == "THB"]
        if a and a[0]["aria"] != "פעולות על באט":
            P.append("⋯ aria-label %r (want 'פעולות על באט')" % a[0]["aria"])
    page.locator("#ptF10bBack").click()
    page.wait_for_timeout(500)
    if vis(page, "#ptF10bPanel") or not vis(page, "#more"):
        P.append("back › did not return to 'עוד'")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 2 · Quick FX link
# =====================================================================================================
def test_c02_quick_fx_link(env):
    tid, dev, page = start(env, "S", "viewer")
    H.open_quick_fx(page)
    P = []
    if not H.wait_vis(page, "#ptF10bFxLink"):
        pytest.fail("#ptF10bFxLink not visible in #fxQuickModal (viewer)")
    if "ניהול מטבעות" not in text(page, "#ptF10bFxLink"):
        P.append("link text %r" % text(page, "#ptF10bFxLink"))
    if not page.evaluate("()=>{const l=document.getElementById('ptF10bFxLink'),m=document.getElementById('fxQuickModal');return !!l&&!!m&&m.contains(l)}"):
        P.append("#ptF10bFxLink not inside #fxQuickModal")
    page.locator("#ptF10bFxLink").click()
    if not H.wait_vis(page, "#ptF10bPanel"):
        P.append("tap did not open #ptF10bPanel")
    if vis(page, "#fxQuickModal .modal-box") or page.evaluate("()=>document.getElementById('fxQuickModal').classList.contains('open')"):
        P.append("#fxQuickModal still open after the tap")
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 3 · add GBP in England
# =====================================================================================================
def test_c03_england_add_gbp(env):
    be = env.backend
    tid, dev, page = start(env, "E")
    H.open_screen(page)
    H.open_picker(page)
    P = []
    pk = text(page, H.PICK)
    if "הוספת מטבע" not in pk or "3 מתוך 10 · נשארו 7" not in pk:
        P.append("picker header %r (want 'הוספת מטבע' + '3 מתוך 10 · נשארו 7')" % pk[:120])
    i, j = pk.find("מוצעים"), pk.find("כל המטבעות")
    if i < 0 or j < 0 or not (i < pk.find("GBP") < j):
        P.append("GBP not in 'מוצעים' before 'כל המטבעות' (idx %d %d %d)" % (i, pk.find("GBP"), j))
    if page.locator("#ptF10bConfirm").is_enabled():
        P.append("#ptF10bConfirm enabled before a choice")
    H.pick(page, "GBP")
    ct = text(page, "#ptF10bConfirm")
    if ct != "הוספת לירה שטרלינג (GBP)":
        P.append("confirm text %r" % ct)
    H.confirm(page)
    H.wait_until(lambda: "GBP" in codes_of(be, tid), 6, page)
    ins = writes(be, "POST")
    body = ins[0]["body"] if ins else None
    body = body[0] if isinstance(body, list) else body
    want = {"trip_id": tid, "currency_code": "GBP", "kind": "destination", "sort": 3}
    if len(writes(be)) != 1 or not body or {k: body.get(k) for k in want} != want:
        P.append("writes %r, want one insert %r" % (be.writes, want))
    H.wait_until(lambda: "GBP" in ((H.tripcur(page) or {}).get("list") or []), 6, page)
    tc = H.tripcur(page) or {}
    if "GBP" not in (tc.get("list") or []) or tc.get("local") != "GBP":
        P.append("TRIPCUR %r (want GBP in list, local GBP)" % {k: tc.get(k) for k in ("list", "local")})
    if not H.saw_toast(page, "לירה שטרלינג נוסף"):
        P.append("toast 'לירה שטרלינג נוסף' not seen (%r)" % H.toasts(page))
    if "4 מתוך 10" not in text(page, "#ptF10bSub"):
        P.append("#ptF10bSub %r (want 4 מתוך 10)" % text(page, "#ptF10bSub"))
    if "4 מתוך 10" not in text(page, "#ptF10bRow"):
        P.append("#ptF10bRow %r (want 4 מתוך 10)" % text(page, "#ptF10bRow"))
    H.open_budget(page)
    if "£" not in chip_text(page, "P1"):
        P.append("expense chip row lacks £: %r" % chip_text(page, "P1"))
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 4 · search
# =====================================================================================================
def test_c04_search_and_disabled(env):
    tid, dev, page = start(env, "S")
    H.open_screen(page)
    H.open_picker(page)
    P = []
    if "6 מתוך 10 · נשארו 4" not in text(page, H.PICK):
        P.append("picker sub %r" % text(page, H.PICK)[:100])
    for q in ("ין", "JPY", "jpy", "יפן", "japan", "Japanese"):
        H.search(page, q)
        got = [b["code"] for b in H.sheet_buttons(page, H.PICK)]
        if "JPY" not in got:
            P.append("search %r: JPY not found (%r)" % (q, got[:10]))
    for c in ("THB", "ILS"):
        H.search(page, c)
        bs = [b for b in H.sheet_buttons(page, H.PICK) if b["code"] == c]
        if not bs:
            P.append("search %s: no row" % c)
        elif not bs[0]["disabled"] or "כבר בטיול" not in bs[0]["text"]:
            P.append("%s row %r (want disabled + 'כבר בטיול')" % (c, bs[0]))
    H.search(page, "JPY")
    H.click_option(page, H.PICK, "JPY")
    pr = [b for b in H.sheet_buttons(page, H.PICK) if b["code"] == "JPY"]
    if pr and pr[0]["pressed"] != "true":
        P.append("chosen JPY aria-pressed %r" % pr[0]["pressed"])
    if not page.locator("#ptF10bConfirm").is_enabled():
        P.append("confirm still disabled after a choice")
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_c04_sheet_ids(env):
    """§4: the picker sheet is `#ptF10bPicker` and the swap sheet `#ptF10bSwap` (ids named by the spec)."""
    tid, dev, page = start(env, "F", laos=True)
    H.open_screen(page)
    H.open_picker(page)
    P = []
    if not page.evaluate("()=>!!document.getElementById('ptF10bPicker')"):
        P.append("picker open but no element #ptF10bPicker (the sheet holding #ptF10bSearch has id %r)" %
                 page.evaluate("()=>{const s=document.getElementById('ptF10bSearch');const d=s&&s.closest('[role=dialog]');return d?d.id:null}"))
    H.pick(page, "LAK")
    if done_swap_pick(page) and not page.evaluate("()=>!!document.getElementById('ptF10bSwap')"):
        P.append("swap sheet open but no element #ptF10bSwap")
    assert not P, "\n".join(P)


# =====================================================================================================
# 5 · 'added'
# =====================================================================================================
def test_c05_added_kind_last(env):
    be = env.backend
    tid, dev, page = start(env, "S")
    H.open_screen(page)
    H.open_picker(page)
    H.pick(page, "JPY")
    H.confirm(page)
    H.wait_until(lambda: "JPY" in ((H.tripcur(page) or {}).get("list") or []), 6, page)
    P = []
    row = next((r for r in be.cur_rows(tid) if r["currency_code"] == "JPY"), None)
    if not row or row["kind"] != "added" or row["sort"] != 6:
        P.append("JPY row %r (want kind added, sort 6)" % row)
    lst = (H.tripcur(page) or {}).get("list") or []
    if lst != S_LIST + ["JPY"]:
        P.append("TRIPCUR.list %r, want %r" % (lst, S_LIST + ["JPY"]))
    sc = screen(page)
    if [r["code"] for r in sc["rows"] if r["group"] == "other"][-1:] != ["JPY"] or "נוסף ידנית" not in sc["text"]:
        P.append("screen other group %r / sub 'נוסף ידנית' missing" % [r["code"] for r in sc["rows"]])
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 6 · full → swap via add
# =====================================================================================================
def test_c06_full_swap_lak_for_khr(env):
    be = env.backend
    tid, dev, page = start(env, "F", laos=True)
    H.open_screen(page)
    P = []
    if "10 מתוך 10 · מלא" not in text(page, "#ptF10bSub"):
        P.append("#ptF10bSub %r (want '10 מתוך 10 · מלא')" % text(page, "#ptF10bSub"))
    H.open_picker(page)
    pk = text(page, H.PICK)
    if "יש כבר 10 – בוחרים מטבע ואז מה יוצא" not in pk:
        P.append("picker sub at 10: %r" % pk[:120])
    i, j = pk.find("מוצעים"), pk.find("כל המטבעות")
    if not (0 <= i < pk.find("LAK") < j):
        P.append("LAK not suggested")
    H.pick(page, "LAK")
    if not done_swap_pick(page):
        pytest.fail("#ptF10bSwap did not open (%r)" % P)
    st = text(page, H.SWAP)
    if "מוסיפים ₭ קיפ · LAK" not in st or "יש כבר 10 מטבעות – בחרו אחד שיוצא במקומו" not in st:
        P.append("swap sheet text %r" % st[:160])
    opts = sorted({b["code"] for b in H.sheet_buttons(page, H.SWAP) if b["code"] and b["id"] != "ptF10bSwapGo"})
    if opts != sorted(["THB", "VND", "KHR", "MYR", "SGD", "IDR", "PHP"]):
        P.append("swap options %r (want the 7 non-base)" % opts)
    if page.locator("#ptF10bSwapGo").is_enabled():
        P.append("#ptF10bSwapGo enabled before a choice")
    H.click_option(page, H.SWAP, "KHR")
    if text(page, "#ptF10bSwapGo") != "החלפת KHR ב-LAK":
        P.append("swap button %r" % text(page, "#ptF10bSwapGo"))
    page.locator("#ptF10bSwapGo").click()
    H.wait_until(lambda: "LAK" in codes_of(be, tid), 6, page)
    page.wait_for_timeout(800)
    pa, po, de = writes(be, "PATCH"), writes(be, "POST"), writes(be, "DELETE")
    if len(pa) != 1 or po or de:
        P.append("writes PATCH %d POST %d DELETE %d (want 1/0/0): %r" % (len(pa), len(po), len(de), be.writes))
    elif (pa[0]["body"] or {}).get("currency_code") != "LAK" or eqf(pa[0], "currency_code") != "KHR" or eqf(pa[0], "trip_id") != tid:
        P.append("PATCH %r" % pa[0])
    elif {k: pa[0]["body"].get(k) for k in ("kind", "sort")} != {"kind": "destination", "sort": 10}:
        P.append("PATCH kind/sort %r (want destination, max(sort)+1=10)" % pa[0]["body"])
    cs = codes_of(be, tid)
    if len(cs) != 10 or "KHR" in cs:
        P.append("DB codes %r" % cs)
    H.wait_until(lambda: "KHR" not in ((H.tripcur(page) or {}).get("list") or ["KHR"]), 6, page)
    if "10 מתוך 10" not in text(page, "#ptF10bSub"):
        P.append("count %r" % text(page, "#ptF10bSub"))
    if not H.saw_toast(page, "נכנס במקום"):
        P.append("swap toast not seen %r" % H.toasts(page))
    if "KHR" in ((H.tripcur(page) or {}).get("list") or []):
        P.append("KHR still in TRIPCUR")
    H.open_budget(page)
    for r in ("P1", "P4", "P7"):
        t = chip_text(page, r)
        if "KHR" in t or "៛" in t:
            P.append("%s still shows KHR: %r" % (r, t))
    H.open_quick_fx(page)
    t = chip_text(page, "P5")
    if "KHR" in t or "៛" in t:
        P.append("P5 still shows KHR: %r" % t)
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 7 · ⋯ swap THB → JPY
# =====================================================================================================
def test_c07_row_swap_thb_jpy(env):
    be = env.backend
    tid, dev, page = start(env, "S")
    H.open_screen(page)
    H.row_sheet(page, "THB")
    P = []
    rs = text(page, "#ptF10bRowSheet")
    if "באט · THB" not in rs or "החלפה במטבע אחר" not in text(page, "#ptF10bDoSwap") or "הסרה מהטיול" not in text(page, "#ptF10bDoRemove"):
        P.append("row sheet %r" % rs)
    page.locator("#ptF10bDoSwap").click()
    if not H.wait_vis(page, H.PICK):
        pytest.fail("#ptF10bDoSwap did not open the picker")
    H.pick(page, "JPY")
    if vis(page, "#ptF10bConfirm"):
        H.confirm(page)
    if vis(page, H.SWAP):
        P.append("swap mode showed a second list (#ptF10bSwap)")
        if vis(page, "#ptF10bSwapGo"):
            page.locator("#ptF10bSwapGo").click()
    H.wait_until(lambda: "JPY" in codes_of(be, tid), 6, page)
    page.wait_for_timeout(600)
    pa = writes(be, "PATCH")
    if len(pa) != 1 or writes(be, "POST") or writes(be, "DELETE"):
        P.append("writes %r (want exactly one PATCH)" % be.writes)
    elif pa[0]["body"].get("currency_code") != "JPY" or eqf(pa[0], "currency_code") != "THB" or pa[0]["body"].get("kind") != "added":
        P.append("PATCH %r" % pa[0])
    cs = codes_of(be, tid)
    if "THB" in cs or "JPY" not in cs or len(cs) != 6:
        P.append("DB codes %r" % cs)
    H.wait_until(lambda: "JPY" in ((H.tripcur(page) or {}).get("list") or []), 6, page)
    lst = (H.tripcur(page) or {}).get("list") or []
    if "THB" in lst or lst[-1:] != ["JPY"]:
        P.append("TRIPCUR.list %r (want THB gone, JPY last)" % lst)
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 8 · ⋯ remove KHR
# =====================================================================================================
def test_c08_remove_khr_keeps_expenses(env):
    be = env.backend
    tid, dev, page = start(env, "S", expenses=KHR_EXP)
    before = be.kv(tid, "expenses")
    H.open_screen(page)
    H.row_sheet(page, "KHR")
    page.locator("#ptF10bDoRemove").click()
    if not H.wait_vis(page, "#ptF10bRemove"):
        pytest.fail("#ptF10bRemove alert did not open")
    P = []
    at = text(page, "#ptF10bRemove")
    for w in ("להסיר ריאל קמבודי מהטיול?", "3 הוצאות נשמרו בריאל קמבודי", "הן יישארו כמו שהן",
              "ריאל קמבודי לא יופיע יותר בממיר ובשבבים.", "ביטול"):
        if w not in at:
            P.append("alert lacks %r: %r" % (w, at))
    page.locator("#ptF10bRemoveGo").click()
    H.wait_until(lambda: "KHR" not in codes_of(be, tid), 6, page)
    page.wait_for_timeout(800)
    de = writes(be, "DELETE")
    if len(de) != 1 or writes(be, "POST") or writes(be, "PATCH"):
        P.append("writes %r (want exactly one DELETE)" % be.writes)
    elif eqf(de[0], "currency_code") != "KHR" or eqf(de[0], "trip_id") != tid:
        P.append("DELETE filters %r" % de[0]["filters"])
    if be.kv(tid, "expenses") != before:
        P.append("expenses changed:\n before %r\n after  %r" % (before, be.kv(tid, "expenses")))
    if (tid, "KH") not in be.rows["trip_countries"]:
        P.append("trip country KH removed")
    if "5 מתוך 10" not in text(page, "#ptF10bSub"):
        P.append("count %r (want 5 מתוך 10)" % text(page, "#ptF10bSub"))
    if not H.saw_toast(page, "ריאל קמבודי הוסר"):
        P.append("toast 'ריאל קמבודי הוסר' not seen %r" % H.toasts(page))
    assert not P + errs(dev), "\n".join(P + errs(dev))


def test_c08_remove_alert_without_expenses(env):
    """§5: with k=0 the "<k> הוצאות…" sentence is absent; "ביטול" writes nothing."""
    be = env.backend
    tid, dev, page = start(env, "S")
    H.open_screen(page)
    H.row_sheet(page, "VND")
    page.locator("#ptF10bDoRemove").click()
    assert H.wait_vis(page, "#ptF10bRemove"), "#ptF10bRemove did not open"
    at = text(page, "#ptF10bRemove")
    P = []
    if "הוצאות נשמרו" in at or (H.HE["VND"] + " לא יופיע יותר בממיר ובשבבים.") not in at:
        P.append("alert text %r" % at)
    H.h10.click_button_text(page, "ביטול", "#ptF10bRemove")
    page.wait_for_timeout(500)
    if be.writes:
        P.append("'ביטול' sent writes %r" % be.writes)
    assert not P, "\n".join(P)


# =====================================================================================================
# 9 · base rows locked
# =====================================================================================================
def test_c09_base_rows_no_actions(env):
    be = env.backend
    tid, dev, page = start(env, "F", laos=True)
    H.open_screen(page)
    P = []
    n = page.evaluate("()=>document.querySelectorAll('[data-f10b-act=\"ILS\"],[data-f10b-act=\"USD\"],[data-f10b-act=\"EUR\"]').length")
    if n:
        P.append("%d ⋯ buttons for base rows" % n)
    acts = sorted(a["code"] for a in screen(page)["acts"])
    if acts != sorted(["THB", "VND", "KHR", "MYR", "SGD", "IDR", "PHP"]):
        P.append("⋯ codes %r" % acts)
    # the swap list (add at 10) must not offer a base row
    H.open_picker(page)
    H.pick(page, "LAK")
    if done_swap_pick(page):
        o = {b["code"] for b in H.sheet_buttons(page, H.SWAP)}
        if o & set(H.BASES):
            P.append("swap list offers base %r" % (o & set(H.BASES)))
    # the row sheet swap-mode picker shows base codes disabled ("כבר בטיול"), so no PATCH can target a base row
    if be.writes:
        P.append("writes %r" % be.writes)
    assert not P, "\n".join(P)


# =====================================================================================================
# 10 · editor / viewer read-only
# =====================================================================================================
@pytest.mark.parametrize("role", ["editor", "viewer"])
def test_c10_read_only_roles(env, role):
    be = env.backend
    tid, dev, page = start(env, "S", role)
    H.open_screen(page)
    P = []
    sc = screen(page)
    if sc["acts"] or page.evaluate("()=>document.querySelectorAll('#ptF10bPanel [data-f10b-act]').length"):
        P.append("⋯ present: %r" % sc["acts"])
    if vis(page, "#ptF10bAdd"):
        P.append("#ptF10bAdd visible")
    if not vis(page, "#ptF10bRO") or "רק מנהל הטיול יכול להוסיף, להחליף או להסיר מטבעות." not in text(page, "#ptF10bRO"):
        P.append("#ptF10bRO %r (visible %s)" % (text(page, "#ptF10bRO"), vis(page, "#ptF10bRO")))
    if len(sc["rows"]) != 6:
        P.append("list %r (want the same 6)" % [r["code"] for r in sc["rows"]])
    H.open_quick_fx(page)
    page.locator("#ptF10bFxLink").click()
    page.wait_for_timeout(800)
    if be.writes:
        P.append("write requests sent: %r" % be.writes)
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 11 · offline manager
# =====================================================================================================
def test_c11_offline_manager(env):
    be = env.backend
    tid, dev, page = start(env, "S")
    H.open_screen(page)          # online open (fills the caches)
    H.go_offline(env, dev, True)
    assert H.reboot(dev) == "app", "offline reboot failed"
    H.open_screen(page)
    P = []
    sc = screen(page)
    if sorted(r["code"] for r in sc["rows"]) != sorted(S_LIST):
        P.append("offline list %r" % [r["code"] for r in sc["rows"]])
    if [r["code"] for r in sc["rows"] if r["group"] == "base"] != ["ILS", "USD", "EUR"]:
        P.append("offline base group %r" % sc["rows"])
    if not vis(page, "#ptF10bOff") or "אין חיבור. צריך חיבור כדי לשנות מטבעות – הרשימה מוצגת כפי שנשמרה." not in text(page, "#ptF10bOff"):
        P.append("#ptF10bOff %r" % text(page, "#ptF10bOff"))
    if sc["acts"]:
        P.append("⋯ offline: %r" % sc["acts"])
    if not page.locator("#ptF10bAdd").count() or page.locator("#ptF10bAdd").is_enabled():
        P.append("#ptF10bAdd not present-and-disabled offline")
    H.go_offline(env, dev, False)
    page.evaluate("()=>window.dispatchEvent(new Event('online'))")
    if not H.wait_until(lambda: len(screen(page)["acts"]) == 3, 10, page):
        P.append("back online: ⋯ did not return (%r)" % screen(page)["acts"])
    if not H.wait_until(lambda: page.locator("#ptF10bAdd").is_enabled(), 5, page):
        P.append("back online: add still disabled")
    if vis(page, "#ptF10bOff"):
        P.append("back online: #ptF10bOff still shown")
    if be.writes:
        P.append("writes %r" % be.writes)
    assert not P, "\n".join(P)


# =====================================================================================================
# 12 · errors
# =====================================================================================================
ERR_CASES = {
    "currency_limit": ("insert", "הטיול הגיע ל-10 מטבעות – בחרו מטבע להחלפה"),
    "dup": ("insert", "JPY כבר בטיול"),
    "rls403": ("insert", "רק מנהל הטיול יכול לשנות מטבעות"),
    "network": ("insert", "אין חיבור – נסו שוב"),
    "base": ("delete", "מטבע בסיס קבוע"),
}


@pytest.mark.parametrize("kind", list(ERR_CASES))
def test_c12_errors(env, kind):
    be = env.backend
    tid, dev, page = start(env, "S")
    H.open_screen(page)
    act, msg = ERR_CASES[kind]
    if kind == "rls403":
        # role really changed meanwhile: the device's member row becomes editor → the emulated RLS answers 42501/403
        for m in be.rows["trip_members"].values():
            if m["trip_id"] == tid and m["display_name"] == "אור":
                m["role"] = "editor"
    else:
        be.inject(act, kind)
    n_sel = len(be.selects())
    if act == "insert":
        H.open_picker(page)
        H.pick(page, "JPY")
        H.confirm(page)
    else:
        H.row_sheet(page, "KHR")
        page.locator("#ptF10bDoRemove").click()
        H.wait_vis(page, "#ptF10bRemove")
        page.locator("#ptF10bRemoveGo").click()
    page.wait_for_timeout(1200)
    P = []
    if not H.saw_toast(page, msg, 5):
        P.append("message %r not shown (toasts %r)" % (msg, H.toasts(page)))
    if not vis(page, "#ptF10bPanel"):
        P.append("screen closed")
    if kind != "network" and len(be.selects()) <= n_sel:
        P.append("list not reloaded (no trip_currencies select after the error)")
    if sorted(codes_of(be, tid)) != sorted(S_LIST):
        P.append("partial state: %r" % codes_of(be, tid))
    if len(screen(page)["rows"]) != 6:
        P.append("screen list %r (want unchanged 6)" % [r["code"] for r in screen(page)["rows"]])
    if kind == "rls403":
        H.wait_until(lambda: not screen(page)["acts"] and not vis(page, "#ptF10bAdd"), 4, page)
        if screen(page)["acts"] or vis(page, "#ptF10bAdd"):
            P.append("not repainted read-only after 403 (acts %r, add %s)" % (screen(page)["acts"], vis(page, "#ptF10bAdd")))
    P += errs(dev)
    assert not P, "\n".join(P)


# =====================================================================================================
# 13 · rates for a new code
# =====================================================================================================
def test_c13_rate_added_to_saved_object(env):
    be = env.backend
    saved = {"v": 2, "base": "ILS", "rates": {"USD": 3.6, "EUR": 3.9}, "updatedAt": 1793900000000, "source": "manual",
             "USD": 3.6, "EUR": 3.9, "VND": 0.14}
    tid, dev, page = start(env, "E", fxrates=saved)
    n_er = len(env.er_calls)
    H.open_screen(page)
    H.open_picker(page)
    H.pick(page, "GBP")
    H.confirm(page)
    H.wait_until(lambda: "GBP" in ((be.kv_json(tid, "fxrates", {}) or {}).get("rates") or {}), 8, page)
    P = []
    v = be.kv_json(tid, "fxrates", {})
    want = H.h10.home_per_unit("ILS", "GBP")
    g = (v.get("rates") or {}).get("GBP")
    if not isinstance(g, (int, float)) or abs(g - want) > 1e-6 * want:
        P.append("saved rates.GBP %r, want %r" % (g, want))
    for k, val in saved.items():
        if k == "rates":
            for c, x in val.items():
                if v.get("rates", {}).get(c) != x:
                    P.append("rates.%s changed %r → %r" % (c, x, v.get("rates", {}).get(c)))
        elif k not in ("updatedAt",) and v.get(k) != val:
            P.append("key %s changed %r → %r" % (k, val, v.get(k)))
    if len(env.er_calls) - n_er != 1:
        P.append("er-api calls %d (want 1)" % (len(env.er_calls) - n_er))
    H.open_quick_fx(page)
    H.set_pair(page, "P5", "GBP", "ILS")
    page.fill("#quickFxAmount", "10")
    page.locator("#quickFxCalculate").click()
    page.wait_for_timeout(500)
    r = text(page, "#quickFxResult")
    if not any(abs(x - 10 * want) < 0.06 for x in H.nums(r)):
        P.append("£10→₪ result %r (want ≈%.2f)" % (r, 10 * want))
    assert not P + errs(dev), "\n".join(P + errs(dev))


# =====================================================================================================
# 14 · flag off = alpha.9
# =====================================================================================================
def capture(dev):
    page = dev.page
    H.tab(page, "more")
    page.wait_for_timeout(800)
    a = page.evaluate(H.SIG_JS, ["#more"])
    H.open_quick_fx(page)
    b = page.evaluate(H.SIG_JS, ["#fxQuickModal"])
    ids = page.evaluate("()=>['ptF10bRow','ptF10bFxLink','ptF10bPanel'].filter(i=>document.getElementById(i))")
    f02.close_modal(page, "fxQuickModal")
    import re as _re
    a["#more"] = [_re.sub(r'"\d+ חברים', '"N חברים', x) if "ptF06MembersSub" in x else x for x in a["#more"]]
    return {**a, **b}, ids


def test_c14_flag_off_equals_alpha9(env):
    """C14: flag off → no F10b ids; DOM of "עוד" and #fxQuickModal equals alpha.9. The member count in the F06 row is
    normalised: each booted device joins the trip as a new member, so the second device sees one more member."""
    be = env.backend
    tid = be.fixture("S")
    H.serve_src(env, H.base_html())
    a9, _ = capture(H.boot(env, tid, name="A9"))
    env.server.reset()
    H.serve_src(env, H.flip_mgr(H.app_html(), "off"))
    n_w = len(be.writes)
    off, ids = capture(H.boot(env, tid, name="OFF"))
    import difflib
    P = ["F10b element present with flag off: %r" % ids] if ids else []
    for s in a9:
        if a9[s] != off.get(s):
            d = list(difflib.unified_diff(a9[s], off.get(s) or [], "alpha.9", "flag off", n=1, lineterm=""))
            P.append("%s differs:\n%s" % (s, "\n".join(d[:30])))
    if len(be.writes) != n_w:
        P.append("writes with flag off")
    assert not P, "\n".join(P)


# =====================================================================================================
# 15 · 390 px layout
# =====================================================================================================
def check_layout(page, sel, P):
    L = H.layout(page, sel)
    if L is None:
        P.append("%s not found" % sel)
        return
    if L["scroll"] > 1 or L["over"]:
        P.append("%s: horizontal overflow (scroll %d, %d boxes outside)" % (sel, L["scroll"], L["over"]))
    if L["small"]:
        P.append("%s: controls < 44px %r" % (sel, L["small"][:8]))
    if L["dir"] != "rtl":
        P.append("%s direction %r" % (sel, L["dir"]))


def test_c15_layout_390(env):
    tid, dev, page = start(env, "F", laos=True, expenses=KHR_EXP)
    P = []
    H.open_screen(page)
    check_layout(page, "#ptF10bPanel", P)
    H.row_sheet(page, "KHR")
    check_layout(page, "#ptF10bRowSheet", P)
    page.locator("#ptF10bDoRemove").click()
    if H.wait_vis(page, "#ptF10bRemove"):
        check_layout(page, "#ptF10bRemove", P)
        H.h10.click_button_text(page, "ביטול", "#ptF10bRemove")
    page.wait_for_timeout(400)
    H.open_picker(page)
    check_layout(page, H.PICK, P)
    H.pick(page, "LAK")
    if done_swap_pick(page):
        check_layout(page, H.SWAP, P)
    else:
        P.append("#ptF10bSwap did not open")
    assert not P, "\n".join(P)
