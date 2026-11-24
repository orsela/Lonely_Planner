"""Lonely Planner F13 · dev tool: boots the app (fake backend, manager of a trip) in English with the CURRENT catalog, visits the tabs and prints the Hebrew texts that have no catalog entry · version 3.0.0-alpha.18.9
CHANGE 2026-11-24 F13-TOOL-01: new file (no previous version). Not a test. Usage: python3 collect_missing.py [out.json]   (REPO_DIR=… as for the other F13 browser tests)
The list is what stage 4 still has to put into app/i18n/en.json; it also contains user content (names, notes), which must stay Hebrew."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f05")); sys.path.insert(0, str(HERE.parent / "f07"))
import harness as H
import test_f05 as T5

def main(out):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        s = H.F05Server()
        env = H.Env(b, s)
        tid, code = T5.new_trip(env)
        d = T5.boot_member(env, tid, "M", "דנה", role="manager", pre_ls=None)
        d.ctx.add_init_script("try{localStorage.setItem('pt-f13-beta','1');localStorage.setItem('pt:_device:lang','en')}catch(e){}")
        d.page.reload(); H.wait_app_state(d.page, "app", 30); d.page.wait_for_timeout(1500)
        pg = d.page
        seen = {}
        def grab(label):
            st = pg.evaluate("()=>window.__ptF13?window.__ptF13.stats():null")
            seen[label] = st["missingList"] if st else None
        grab("boot")
        n = pg.locator(".tab").count()
        for i in range(n):
            try:
                pg.locator(".tab").nth(i).click(timeout=2000); pg.wait_for_timeout(500); grab("tab%d:%s" % (i, (pg.locator(".tab").nth(i).inner_text() or "").strip()[:12]))
            except Exception as e:
                seen["tab%d" % i] = "ERR %s" % e
        allm = pg.evaluate("()=>window.__ptF13.stats().missingList")
        Path(out).write_text(json.dumps({"all": allm, "by": seen}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(len(allm), "missing texts →", out)
        env.close(); s.stop(); b.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/f13_missing.json")
