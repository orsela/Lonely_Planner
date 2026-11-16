"""Lonely Planner F07 · conversation 3 · ONE browser pass (390x844): devices per person, "אני · <שם>" → "המכשירים שלי", the managers' login notice,
device_revoked, offline, flag off, iPhone transfer after an approved relink · version 3.0.0-alpha.16
CHANGE 2026-11-16 F07-QA-08: new file (no previous version). LEAN rule 5: one browser pass at the end of the stage, no full regression.
Harness: the F06 one (in-memory manage-members, fake supabase-js with Realtime) extended here with the facts of migration 0018 that the F06 fake
does not know: `person_id`, device sessions, the actions devices / disconnect_device / ack_device_notice and the 403 device_revoked on touch.
RELINK_FEATURE is flipped in served copies only (the repo files carry the real flag). Spec criteria covered: 2 (one person, two devices), 5 (one
list), 6 (only manager = persons), 7/8 (disconnect, client side), 9 (no button on the last / current device), 10 (login notice), 14 (flag off),
15 (390 px, touch >= 44), C11 (iPhone Safari after a relink approval). Server rules themselves: tests/f07/run.sh.
Run: tests/f07/run_page.sh   (needs playwright + chromium; no network)
"""
import importlib.util
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
sys.path.insert(0, str(HERE.parent / "f05"))
_spec = importlib.util.spec_from_file_location("f06_harness", str(HERE.parent / "f06" / "harness.py"))
H6 = importlib.util.module_from_spec(_spec); sys.modules["f06_harness"] = H6; _spec.loader.exec_module(H6)
f05, f03 = H6.f05, H6.f03
TRIP = "יפן 2027"
FLAG = re.compile(r"""((?:const|let|var)\s+RELINK_FEATURE\s*=\s*)(['"])(on|off)\2""")


def sess(device):
    """The session id the fake gives a device (the 'current_session' of `devices`)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "f07-session/" + device))


class B(H6.F06Backend):
    def __init__(self):
        super().__init__()
        self.sessions = {}            # member_id -> [ {session_id, label, via, created_at, last_seen_at, revoked} ]
        self.notices = []             # {session_id, member_id, acked}
        self._dev = None

    def mm(self, device, via, bearer, body):
        self._dev = device
        return super().mm(device, via, bearer, body)

    def add_session(self, mid, session_id, label, via="anon", days_ago=0):
        t = H6.iso(self.tnow() - H6.DAY * days_ago)
        self.sessions.setdefault(mid, []).append({"session_id": session_id, "label": label, "via": via, "created_at": t, "last_seen_at": t, "revoked": False})

    def second_row(self, tid, person_mid, label, via="anon", uid=None):
        pr = self.member(person_mid)
        mid = self.add_member(tid, uid or str(uuid.uuid4()), pr["role"], "active", pr["display_name"], joined_at=H6.iso(self.tnow() - H6.DAY))
        self.member(mid)["person_id"] = person_mid
        sid = str(uuid.uuid4()); self.add_session(mid, sid, label, via)
        return mid, sid

    def _pid(self, r):
        return r.get("person_id") or r["id"]

    def _devices(self, tid, pid):
        out = []
        for r in self.members(tid, "active"):
            if self._pid(r) != pid: continue
            live = [s for s in self.sessions.get(r["id"], []) if not s["revoked"]]
            acct = [s for s in live if s["via"] != "anon"]
            for s in (acct or live[:1] or [None]):
                out.append({"member_id": r["id"], "session_id": s["session_id"] if s else None, "label": s["label"] if s else None,
                            "via": s["via"] if s else "anon", "created_at": s["created_at"] if s else r["joined_at"],
                            "last_seen_at": s["last_seen_at"] if s else r.get("last_seen_at")})
        return out

    def _mm(self, uid, act, b):
        if act == "touch":
            for r in self.rows["trip_members"].values():
                if r["user_id"] == uid and r["trip_id"] == b.get("trip_id") and any(s["revoked"] and s["session_id"] == sess(self._dev) for s in self.sessions.get(r["id"], [])):
                    return 403, {"error": "device_revoked"}
        if act not in ("devices", "disconnect_device", "ack_device_notice"):
            return super()._mm(uid, act, b)
        tid = b.get("trip_id"); me = self.member_of(tid, uid)
        if not me or me["status"] != "active": return self._e("not_member")
        mgr = self._is_mgr(uid, tid); mp = self._pid(me)
        if act == "devices":
            persons, seen = [], set()
            for r in self.members(tid, "active"):
                p = self._pid(r)
                if p in seen or not (mgr or p == mp): continue
                seen.add(p)
                persons.append({"person_id": p, "display_name": r["display_name"], "role": r["role"], "devices": self._devices(tid, p)})
            notes = []
            if mgr:
                for n in self.notices:
                    r = self.member(n["member_id"])
                    if not n["acked"] and r and r["status"] == "active" and self._pid(r) != mp:
                        s = next(x for x in self.sessions[r["id"]] if x["session_id"] == n["session_id"])
                        notes.append({"session_id": n["session_id"], "member_id": r["id"], "person_id": self._pid(r), "display_name": r["display_name"],
                                      "via": s["via"], "label": s["label"], "created_at": s["created_at"]})
            return 200, {"ok": True, "persons": persons, "notices": notes, "is_manager": mgr, "my_person_id": mp, "current_session": sess(self._dev)}
        if act == "ack_device_notice":
            if not mgr: return self._e("not_manager")
            n = [x for x in self.notices if x["session_id"] == b.get("session_id")]
            for x in n: x["acked"] = True
            return 200, {"ok": True, "acked": bool(n)}
        row = self.member(b.get("member_id"))                                   # disconnect_device
        if not row or row["status"] != "active": return self._e("not_active")
        if self._pid(row) != mp and not mgr: return self._e("not_manager")
        if len(self._devices(tid, self._pid(row))) <= 1: return self._e("last_device")
        s = next((x for x in self.sessions.get(row["id"], []) if x["session_id"] == b.get("session_id") and not x["revoked"]), None)
        if s and s["via"] != "anon":
            s["revoked"] = True; return 200, {"ok": True, "kind": "session", "member_id": row["id"], "session_id": s["session_id"], "auth_session_deleted": True}
        for x in self.sessions.get(row["id"], []): x["revoked"] = True
        self.mut_update(row, status="removed")
        return 200, {"ok": True, "kind": "row", "member_id": row["id"], "session_id": None, "auth_session_deleted": False}


class Env7(H6.Env):
    def __init__(self, browser, server):
        super().__init__(browser, server)
        self.backend = B()
        cols = H6.f02.TABLES["trip_members"]["cols"]
        for c in ("person_id", "relink_expires_at"):
            if c not in cols: cols.append(c)


@pytest.fixture(scope="session")
def server():
    s = H6.f05.F05Server(); yield s; s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True); yield b; b.close()


@pytest.fixture
def env(browser, server):
    server.reset(); e = Env7(browser, server); yield e; e.close(); server.reset()


ACCT = re.compile(r"""((?:const|let|var)\s+ACCOUNT_FEATURE\s*=\s*)(['"])(on|off|beta)\2""")


def serve(env, relink):
    for path, src in ((H6.APP, H6.app_html()), (H6.JOIN, H6.join_html())):
        assert FLAG.search(src), "RELINK_FEATURE flag missing"
        out = FLAG.sub(lambda m: m.group(1) + "'" + relink + "'", src, count=1)
        if path == H6.APP:   # "אני · <שם>" is F22a's screen and ACCOUNT_FEATURE is 'beta' in the repo: on in the served copy only
            assert ACCT.search(out), "ACCOUNT_FEATURE flag missing"; out = ACCT.sub(lambda m: m.group(1) + "'on'", out, count=1)
        out = out.encode("utf-8")
        env.server.overrides[path + "index.html"] = out; env.server.overrides[path] = out


def boot_mgr(env, relink="on"):
    """Manager 'דנה' on device M (one session) + a second device row (Android) of the same person + a trip of three others."""
    serve(env, relink); be = env.backend
    tid, _ = be.trip(name=TRIP, managers=(), others=(("אבי", "manager"), ("Editor Q", "editor"), ("נועה", "viewer")))
    be.links = [{"trip_id": tid, "role": "manager", "display_name": "דנה", "joined_at": H6.iso(be.tnow() - 90 * H6.DAY)}]
    dev = env.new_device("M")
    dev.page.goto(env.server.origin + H6.APP, wait_until="domcontentloaded")
    assert H6.wait_app_state(dev.page, "app", 30) == "app"
    be.links = []
    me = be.member_of(tid, be.uid_of("M"))
    be.add_session(me["id"], sess("M"), "iPhone · Safari")
    mid2, s2 = be.second_row(tid, me["id"], "Android · Chrome")
    dev.page.wait_for_timeout(800)
    return tid, dev, me, mid2, s2


def open_members(page):
    f03.open_more(page); page.wait_for_timeout(300)
    f03.click_text(page, "חברים וקישור"); H6.wait_has(page, TRIP + " · מנהלים בלבד", 8); page.wait_for_timeout(1200)


def m(page):
    return page.evaluate("""()=>({sw:document.documentElement.scrollWidth,iw:window.innerWidth,
      small:[...document.querySelectorAll('.pt7-dbtn,.pt7-nacts button,#pt7RevBtn')].filter(e=>e.getBoundingClientRect().height>0&&e.getBoundingClientRect().height<43.5).map(e=>(e.id||e.innerText).slice(0,30))})""")


def txt(page, sel):
    return page.locator(sel).all_inner_texts()


def test_f07_devices_me_notice_revoked_offline(env):
    P = []; tid, dev, me, mid2, s2 = boot_mgr(env); be = env.backend; pg = dev.page
    # ---- 1. "חברים וקישור": one row per person, devices under it (AC2, AC5, AC9) ----
    open_members(pg)
    if "חברים · 4" not in H6.btext(pg): P.append("AC5: header should count 4 persons: " + H6.btext(pg)[:200])
    names = pg.evaluate("()=>[...document.querySelectorAll('[aria-label^=\"פעולות על \"]')].map(e=>e.getAttribute('aria-label'))")
    if names.count("פעולות על דנה") != 1: P.append("AC2: דנה must be ONE row, got %r" % names)
    body = H6.btext(pg)
    for t in ("iPhone · Safari", "Android · Chrome", "המכשיר הזה", "ניתוק מכשיר לא מסיר את החבר מהטיול"):
        if t not in body: P.append("members screen text missing: " + t)
    btns = pg.locator("#ptF06Members .pt7-dbtn")
    if btns.count() != 1: P.append("AC9: exactly one 'ניתוק' button expected (not on this device, not on single-device persons), got %d" % btns.count())
    mm = m(pg)
    if mm["sw"] > mm["iw"] or mm["small"]: P.append("members layout: %r" % mm)
    if btns.count() == 1:
        btns.first.click(); pg.wait_for_timeout(300)
        if "לנתק? לחצו שוב" not in H6.btext(pg): P.append("no confirm step on the first tap")
        if be.mm_of("disconnect_device"): P.append("disconnect sent on the first tap")
        pg.locator("#ptF06Members .pt7-dbtn").first.click(); pg.wait_for_timeout(1500)
        calls = be.mm_of("disconnect_device")
        if len(calls) != 1 or calls[0]["body"].get("member_id") != mid2 or calls[0]["body"].get("session_id") != s2: P.append("AC7: disconnect call wrong: %r" % [c["body"] for c in calls])
        if be.member(mid2)["status"] != "removed": P.append("AC7: the anonymous device row is not removed")
        if be.member(me["id"])["status"] != "active": P.append("AC7: the person must stay active")
        if pg.locator("#ptF06Members .pt7-dbtn").count() != 0: P.append("AC9: last device still has a button")
    # ---- 2. "אני · דנה" → "המכשירים שלי" ----
    mid3, s3 = be.second_row(tid, me["id"], "Pixel · Chrome")
    pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1200)
    f03.open_more(pg); pg.wait_for_timeout(300)
    if not pg.locator("#ptF22MeRow").count(): P.append("no 'אני · דנה' row in 'עוד'")
    else:
        pg.locator("#ptF22MeRow").click(); pg.wait_for_timeout(1500)
        card = txt(pg, "#pt7Mine")
        if not card or "המכשירים שלי" not in card[0] or "Pixel · Chrome" not in card[0] or "iPhone · Safari" not in card[0]: P.append("F07_MyDevices card wrong: %r" % card)
        if pg.locator("#pt7Mine .pt7-dbtn").count() != 1: P.append("MyDevices: one button (the other device) expected, got %d" % pg.locator("#pt7Mine .pt7-dbtn").count())
        mm = m(pg)
        if mm["sw"] > mm["iw"] or mm["small"]: P.append("MyDevices layout: %r" % mm)
    # ---- 3. offline: the disconnect buttons are disabled with the offline line ----
    pg.context.set_offline(True)
    pg.evaluate("()=>window.dispatchEvent(new Event('offline'))"); pg.wait_for_timeout(600)
    if pg.locator("#pt7Mine .pt7-dbtn:not([disabled])").count(): P.append("offline: a disconnect button is still enabled")
    pg.context.set_offline(False)
    pg.evaluate("()=>window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(500)
    # ---- 4. login notice on home (C8, AC10) ----
    editor = next(r for r in be.members(tid, "active") if r["display_name"] == "Editor Q")
    be.add_session(editor["id"], str(uuid.uuid4()), "Old phone · Chrome", "anon", days_ago=20)
    gid = str(uuid.uuid4()); be.add_session(editor["id"], gid, "Pixel · Chrome", "google"); be.notices.append({"session_id": gid, "member_id": editor["id"], "acked": False})
    pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(300)
    f03.open_home(pg) if hasattr(f03, "open_home") else pg.locator('.tab[data-panel="home"]').first.click()
    pg.wait_for_timeout(1500)
    note = txt(pg, "#pt7Notice")
    if not note or "Editor Q" not in note[0] or "נכנס/ה ממכשיר חדש" not in note[0] or "Google" not in note[0]: P.append("F07_EmailNotice card wrong: %r" % note)
    else:
        mm = m(pg)
        if mm["small"] or mm["sw"] > mm["iw"]: P.append("notice layout: %r" % mm)
        pg.locator("#pt7Notice [data-pt7=ack]").first.click(); pg.wait_for_timeout(1500)
        if not be.mm_of("ack_device_notice"): P.append("'הבנתי' did not call ack_device_notice")
        if pg.locator("#pt7Notice").count(): P.append("the notice card stays after 'הבנתי'")
    # ---- 5. device_revoked → this device signs out (AC8) ----
    for s in be.sessions[me["id"]]:
        if s["session_id"] == sess("M"): s["revoked"] = True
    pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1500)
    if not pg.locator("#pt7Rev").is_visible() or "המכשיר הזה נותק מהטיול" not in H6.btext(pg): P.append("AC8: no 'device disconnected' screen after device_revoked")
    else:
        mm = m(pg)
        if mm["small"] or mm["sw"] > mm["iw"]: P.append("revoked screen layout: %r" % mm)
    errs = H6.page_errors(dev)
    if errs: P.append("page errors: %r" % errs[:3])
    assert not P, "\n".join(P)


def test_f07_flag_off_is_alpha_15_3(env):
    P = []; tid, dev, me, mid2, s2 = boot_mgr(env, "off"); pg = dev.page
    open_members(pg)
    names = pg.evaluate("()=>[...document.querySelectorAll('[aria-label^=\"פעולות על \"]')].map(e=>e.getAttribute('aria-label'))")
    if names.count("פעולות על דנה") != 1 and names.count("פעולות על דנה") != 2: P.append("unexpected rows %r" % names)
    for sel in (".pt7-devs", ".pt7-dbtn", "#pt7Notice", "#pt7Rev", "#pt7Foot"):
        if pg.locator(sel).count(): P.append("flag off but %s exists" % sel)
    if env.backend.mm_of("devices"): P.append("flag off but the 'devices' action was called")
    assert not P, "\n".join(P)
