"""Lonely Planner F13 · dev tool: DEEP crawl — boots the app (fake backend, manager of a trip) in English, then clicks through tabs, the "עוד" list, panels and dialogs and prints the Hebrew texts that have no catalog entry · version 3.0.0-alpha.21.9
CHANGE 2026-11-25 F13-TOOL-02: new file (no previous version). collect_missing.py only visits the main tabs; this one also opens every visible list item / button one level deep (skipping destructive and outbound ones), so it reaches the screens behind them. Not a test; fake backend only.
Usage: python3 collect_deep.py [out.json] [rounds] [manager|viewer|gate|acct]   (REPO_DIR=… as for the other F13 browser tests)"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f05")); sys.path.insert(0, str(HERE.parent / "f07"))
import harness as H
import test_f05 as T5

# never click: destructive, outbound, sign-out, share/send, paid AI
SKIP = re.compile(r"מחיק|הסר|הסרה|יציאה|התנתק|ניתוק|שליחה|שלח|וואטסאפ|ווטסאפ|WhatsApp|Delete|Remove|Sign out|Share|שיתוף|איפוס|reset|ביטול הטיול|Google|גוגל", re.I)
SEL = ".listitem, button, [data-go], .chip, .tab, summary, [role=button]"


def main(out, rounds, scenario="manager"):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        s = H.F05Server(); env = H.Env(b, s)
        tid, code = T5.new_trip(env)
        if scenario == "gate":                              # a device with no trip: the "not connected" gate + the screens behind it
            d = env.new_device("G")
        else:
            d = T5.boot_member(env, tid, "M", "דנה", role=("viewer" if scenario == "viewer" else "manager"), pre_ls=None)
        d.ctx.add_init_script("try{localStorage.setItem('pt-f13-beta','1');localStorage.setItem('pt:_device:lang','en')%s}catch(e){}" % (";localStorage.setItem('pt-f22-beta','1')" if scenario == "acct" else ""))   # acct = manager with the F22a account screens (beta device)
        d.ctx.on("page", lambda pg: pg.close())          # external links open new pages: drop them
        pg = d.page
        pg.on("dialog", lambda dlg: dlg.dismiss())
        def boot():
            if scenario == "gate":
                pg.goto(env.server.origin + H.APP, wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            else:
                pg.reload(); H.wait_app_state(pg, "app", 30); pg.wait_for_timeout(1200)
        boot()
        def stats():
            st = pg.evaluate("()=>window.__ptF13?window.__ptF13.stats():null")
            return st["missingList"] if st else []
        seen = {}
        def grab(label):
            try:
                for t in stats(): seen.setdefault(t, label)
            except Exception:
                pass
        grab("boot")
        clicked = 0
        JS = """()=>{const out=[];const seen=new Set();for(const el of document.querySelectorAll(%r)){const r=el.getBoundingClientRect();if(r.width<4||r.height<4)continue;const cs=getComputedStyle(el);if(cs.visibility==='hidden'||cs.display==='none')continue;const t=(el.innerText||el.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ');if(!t||t.length>60||seen.has(t))continue;seen.add(t);out.push(t)}return out}""" % SEL
        def visible_texts():
            try: return pg.evaluate(JS)
            except Exception: return []
        def click_text(t):
            nonlocal clicked
            try:
                loc = pg.locator(SEL).filter(has_text=t).first
                loc.click(timeout=800, no_wait_after=True); clicked += 1; pg.wait_for_timeout(250); return True
            except Exception:
                return False
        for r in range(rounds):
            boot()
            n_tabs = pg.locator(".tab").count()
            for ti in range(n_tabs):
                try: pg.locator(".tab").nth(ti).click(timeout=1500); pg.wait_for_timeout(300)
                except Exception: continue
                tlabel = (pg.locator(".tab").nth(ti).inner_text() or "").strip().replace("\n", " ")[:14]
                grab("tab:" + tlabel)
                base = [t for t in visible_texts() if not SKIP.search(t)]
                for t in base:
                    boot(); pg.locator(".tab").nth(ti).click(timeout=1500); pg.wait_for_timeout(250)
                    if not click_text(t): continue
                    grab("%s › %s" % (tlabel, t[:24]))
                    # depth 2: whatever opened (new clickables), one click each
                    for t2 in [x for x in visible_texts() if x not in base and not SKIP.search(x)][:25]:
                        if click_text(t2):
                            grab("%s › %s › %s" % (tlabel, t[:16], t2[:20]))
                            pg.keyboard.press("Escape")
        Path(out).write_text(json.dumps({"count": len(seen), "missing": seen}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(len(seen), "missing texts after", clicked, "clicks →", out)
        env.close(); s.stop(); b.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/f13_deep.json", int(sys.argv[2]) if len(sys.argv) > 2 else 1, sys.argv[3] if len(sys.argv) > 3 else "manager")
