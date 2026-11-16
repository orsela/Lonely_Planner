"""Lonely Planner F07 · conversation 2 · ONE browser pass (390x844): /join/ relink screens + the manager's home card · version 3.0.0-alpha.16
CHANGE 2026-11-16 F07-QA-07: new file (no previous version). LEAN rule 5: one browser pass at the end of the stage, no full regression.
Uses the F05 harness (fake backend, no network) and adds a small emulation of the F07 server facts the F05 fake does not know
(`people` / `relink` in the preview, a `person` request, the `relink` flag of approve-member). Flags are flipped in served copies only.
Covers spec criteria 1, 2, 3 (screens), 4 (names only), 11 (the switch), 14 (flag off = alpha.15.3 look), 15 (390 px) — server rules are tests/f07/run.sh.
Run: tests/f07/run_page.sh
"""
import datetime as dt
import re
import sys
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f05"))
import harness as H  # noqa: E402
import test_f05 as T5  # noqa: E402

FLAG = lambda name: re.compile(r"""((?:const|let|var)\s+%s\s*=\s*)(['"])(on|off)\2""" % name)


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


def serve(env, relink):
    """Serve the app and /join/ with RELINK_FEATURE flipped in both."""
    for path, src in ((H.APP, H.app_html()), (H.JOIN, H.join_html())):
        assert FLAG("RELINK_FEATURE").search(src), "RELINK_FEATURE flag missing in " + path
        out = FLAG("RELINK_FEATURE").sub(lambda m: m.group(1) + "'" + relink + "'", src, count=1).encode("utf-8")
        env.server.overrides[path + "index.html"] = out
        env.server.overrides[path] = out


def emulate_f07_server(be):
    """People / relink in the preview, `person` in request, `relink` in approve (the facts of migration 0018)."""
    orig_join, orig_app = be._join_trip, be._approve
    cols = H.f02.TABLES["trip_members"]["cols"]          # the fake's column whitelist: migration 0018 added two columns
    for c in ("person_id", "relink_expires_at"):
        if c not in cols: cols.append(c)

    def join(uid, b):
        act = b.get("action")
        if act == "request" and b.get("person"):
            tid = be._trip_for(b.get("code"))
            if not tid:
                return be._err("code_invalid")
            pr = be.member(b["person"])
            if not pr or pr["trip_id"] != tid or pr["status"] != "active":
                return be._err("person_invalid")
            exp = H.iso(be.tnow() + dt.timedelta(hours=24))
            row = {"id": str(uuid.uuid4()), "trip_id": tid, "user_id": uid, "display_name": pr["display_name"], "role": pr["role"],
                   "status": "pending", "joined_at": H.iso(be.tnow()), "approved_at": None, "last_seen_at": None,
                   "person_id": pr["id"], "relink_expires_at": exp}
            be.mut_insert(row)
            return 200, {"trip_id": tid, "member_id": row["id"], "status": "pending", "role": pr["role"], "display_name": pr["display_name"],
                         "created": True, "relink": True, "person_id": pr["id"], "expires_at": exp}
        st, resp = orig_join(uid, b)
        if act == "preview" and st == 200:
            tid = resp["trip_id"]
            resp["people"] = [{"person_id": r["id"], "display_name": r["display_name"]} for r in be.members(tid, "active")]
            mine = be.member_of(tid, uid)
            if mine and mine.get("relink_expires_at"):
                if mine["relink_expires_at"] <= H.iso(be.tnow()):
                    resp["relink"] = {"status": "expired", "display_name": mine["display_name"]}; resp["me"] = None
                    be.mut_delete(mine)
                else:
                    resp["relink"] = {"status": "pending", "display_name": mine["display_name"], "role": mine["role"], "expires_at": mine["relink_expires_at"]}
            else:
                resp["relink"] = None
        return st, resp

    def approve(uid, b):
        row = be.member(b.get("member_id"))
        rl = bool(row and row.get("relink_expires_at") and b.get("decision") == "approve")
        pr = be.member(row["person_id"]) if rl else None
        if rl and pr:
            b = dict(b, role=pr["role"])
        st, resp = orig_app(uid, b)
        if st == 200 and rl:
            resp["relink"] = True
            row["relink_expires_at"] = None
        return st, resp
    be._join_trip, be._approve = join, approve


def seed_relink_row(be, tid, person_mid, minutes=60):
    """A pending relink row from another identity; `minutes` > 0 = expires in the future, < 0 = already expired."""
    pr = be.member(person_mid); uid = str(uuid.uuid4())
    row = {"id": str(uuid.uuid4()), "trip_id": tid, "user_id": uid, "display_name": pr["display_name"], "role": pr["role"], "status": "pending",
           "joined_at": H.iso(be.tnow()), "approved_at": None, "last_seen_at": None, "person_id": pr["id"],
           "relink_expires_at": H.iso(be.tnow() + dt.timedelta(minutes=minutes))}
    be.mut_insert(row); return uid, row


def metrics(page):
    return page.evaluate("""()=>({sw:document.documentElement.scrollWidth,iw:window.innerWidth,
      small:[...document.querySelectorAll('#lpJoin button,#lpJoin a.lpj-btn,#lpJoin label,#lpJoin .lpj-link,#ptF05Pending button')].filter(e=>e.getBoundingClientRect().height>0&&e.getBoundingClientRect().height<43.5).map(e=>(e.id||e.innerText).slice(0,30))})""")


def test_f07_relink_flow_in_the_browser(env):
    be = env.backend; emulate_f07_server(be); serve(env, "on")
    tid, code = T5.new_trip(env)
    people = {r["display_name"]: r["id"] for r in be.members(tid, "active")}
    assert "Editor Q" in people and "דנה" in people
    P = []
    # --- the member's new phone: screen F07_Join ---
    dev = env.new_device("N")
    st = T5.open_join(dev, code); pg = dev.page
    assert st == "form", st
    if not pg.locator("#lpjModeBack").count():
        pytest.fail("no switch 'כבר הייתי בטיול' on /join/ with RELINK_FEATURE='on'")
    for t in ("אני חדש/ה בטיול", "כבר הייתי בטיול"):
        if t not in pg.locator(".lpj-sw").inner_text(): P.append("switch text missing: " + t)
    pg.locator("#lpjModeBack").click(); pg.wait_for_timeout(300)
    names = pg.locator("#lpjPeople label").all_inner_texts()
    if sorted(n.strip() for n in names) != sorted(people): P.append("name list %r != active members %r (names only, no roles)" % (names, list(people)))
    if any(r in " ".join(names) for r in ("מנהל", "עורך", "צופה")): P.append("a role is shown in the name list")
    m = metrics(pg)
    if m["sw"] > m["iw"]: P.append("F07_Join: horizontal scroll %s>%s" % (m["sw"], m["iw"]))
    if m["small"]: P.append("F07_Join: touch targets < 44px: %r" % m["small"])
    pg.locator("#lpjRelink").click(); pg.wait_for_timeout(300)
    if not pg.locator("#lpjRelinkErr").is_visible(): P.append("no error when no name is picked")
    pg.locator('#lpjPeople label:has-text("Editor Q")').click()
    pg.locator("#lpjRelink").click()
    if H.wait_screen(pg, "pending", 8) != "pending": pytest.fail("no pending screen after the relink request; " + "; ".join(P))
    rows = [r for r in be.members(tid, "pending")]
    if len(rows) != 1 or rows[0]["person_id"] != people["Editor Q"] or rows[0]["display_name"] != "Editor Q": P.append("AC1: pending row wrong: %r" % rows)
    txt = H.btext(pg)
    for t in ("מכשיר חדש · Editor Q · עורך", "בתוקף עד", "שליחת הודעה למנהל בווטסאפ"):
        if t not in txt: P.append("F07_Pending text missing: " + t)
    if "wa.me" not in (pg.locator("#lpjWa").get_attribute("href") or ""): P.append("WhatsApp link missing")
    m = metrics(pg)
    if m["sw"] > m["iw"] or m["small"]: P.append("F07_Pending layout: %r" % m)
    # reload keeps the relink pending screen (preview → relink.status pending)
    pg.reload(); pg.wait_for_timeout(500)
    if H.wait_screen(pg, "pending", 8) != "pending" or "מכשיר חדש" not in H.btext(pg): P.append("reload lost the relink pending screen")
    # --- the manager's home: F07_HomeManager ---
    mgr = T5.boot_member(env, tid, "M", "דנה")
    mgr.page.wait_for_timeout(1500)
    if not T5.card_vis(mgr.page):
        pytest.fail("manager card not shown; %s; errors=%r; dom=%r now=%r tnow=%r rows=%r" % ("; ".join(P), H.page_errors(mgr)[:3], mgr.page.evaluate("()=>({exists:!!document.getElementById('ptF05Pending'),home:(document.getElementById('home')||{}).className,started:window.__PT&&window.__PT.started,role:window.__PT&&window.__PT.role})"), mgr.page.evaluate("()=>new Date().toISOString()"), H.iso(be.tnow()), [(r['status'],r.get('relink_expires_at')) for r in be.members(tid)]))
    c = T5.card_rows(mgr.page)
    if len(c) != 1 or "מכשיר חדש" not in c[0]["text"] or "Editor Q" not in c[0]["text"]: P.append("F07_HomeManager row: %r" % c)
    if c and (c[0]["roles"] or c[0]["approve"] != "אישור המכשיר"): P.append("role picker shown or wrong approve label: %r" % c[0])
    if not mgr.page.locator("#pt7Warn").is_visible(): P.append("warning line missing")
    m = metrics(mgr.page)
    if m["small"]: P.append("manager card touch targets < 44px: %r" % m["small"])
    mgr.page.locator("#ptF05Pending [data-act=approve]").click()
    if not H.saw_toast(mgr.page, "המכשיר החדש חובר", 6): P.append("no relink toast after approval (toasts: %r)" % H.toasts(mgr.page))
    # AC2: the device is active with the person's current role; the new phone moves on by itself and says what does not move
    if H.wait_screen(pg, "approved", 10) != "approved": P.append("the waiting screen did not move to approved")
    else:
        if "לא עוברים" not in H.btext(pg): P.append("approved screen: note about the old phone's data missing")
        if not pg.locator("#lpjOpen").count(): P.append("no open button")
    act = [r for r in be.members(tid, "active") if r["display_name"] == "Editor Q"]
    if len(act) != 2 or {r["role"] for r in act} != {"editor"}: P.append("AC2: expected 2 active Editor Q rows with role editor, got %r" % [(r["id"][:4], r["role"]) for r in act])
    errs = H.page_errors(dev) + H.page_errors(mgr)
    if errs: P.append("page errors: %r" % errs[:3])
    assert not P, "\n".join(P)


def test_f07_expired_screen(env):
    be = env.backend; emulate_f07_server(be); serve(env, "on")
    tid, code = T5.new_trip(env)
    editor = next(r for r in be.members(tid, "active") if r["display_name"] == "Editor Q")
    dev = env.new_device("X")
    # the same identity as the expired row: create it after the device has a session
    dev.page.goto(env.server.origin + H.JOIN + "#code=" + code, wait_until="domcontentloaded")
    assert H.wait_screen(dev.page, "form", 15) == "form"
    uid = be.uid_of("X"); P = []
    row = {"id": str(uuid.uuid4()), "trip_id": tid, "user_id": uid, "display_name": "Editor Q", "role": "editor", "status": "pending",
           "joined_at": H.iso(be.tnow() - dt.timedelta(hours=25)), "approved_at": None, "last_seen_at": None, "person_id": editor["id"],
           "relink_expires_at": H.iso(be.tnow() - dt.timedelta(hours=1))}
    be.mut_insert(row)
    dev.page.reload()
    if H.wait_screen(dev.page, "expired", 10) != "expired": pytest.fail("no expired screen: " + H.btext(dev.page)[:200])
    txt = H.btext(dev.page)
    for t in ("הבקשה פגה", "בקשה חדשה", "חזרה לבחירת שם"):
        if t not in txt: P.append("F07_Expired text missing: " + t)
    m = metrics(dev.page)
    if m["sw"] > m["iw"] or m["small"]: P.append("F07_Expired layout: %r" % m)
    dev.page.locator("#lpjRelinkAgain").click()
    if H.wait_screen(dev.page, "pending", 8) != "pending": P.append("'בקשה חדשה' did not reach the pending screen")
    assert not P, "\n".join(P)


def test_f07_flag_off_is_the_old_page(env):
    be = env.backend; emulate_f07_server(be); serve(env, "off")
    tid, code = T5.new_trip(env)
    dev = env.new_device("O"); st = T5.open_join(dev, code)
    P = []
    if st != "form": P.append("screen %r" % st)
    if dev.page.locator(".lpj-sw, #lpjModeBack").count(): P.append("switch shown with RELINK_FEATURE='off'")
    if any("f07.js" in r["url"] for r in env.net): P.append("f07.js loaded with the flag off")
    seed_relink_row(be, tid, next(r["id"] for r in be.members(tid, "active") if r["display_name"] == "Editor Q"))
    mgr = T5.boot_member(env, tid, "M", "דנה"); mgr.page.wait_for_timeout(1200)
    c = T5.card_rows(mgr.page)
    if not c or "מכשיר חדש" in c[0]["text"] or not c[0]["roles"]: P.append("flag off: manager card is not the alpha.15.3 one (with role picker): %r" % c)
    assert not P, "\n".join(P)
