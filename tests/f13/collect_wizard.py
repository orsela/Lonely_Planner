"""Lonely Planner F13 · dev tool: English crawl of the screens collect_deep.py cannot reach — the invite wizard (code, steps 1-3, done) and the "not connected" gate with its sub-screens · version 3.0.0-alpha.21.9
CHANGE 2026-11-25 F13-TOOL-03: new file (no previous version). Not a test. Prints the Hebrew texts shown in English without a catalog entry (names the user typed are user content and stay).
Usage: python3 collect_wizard.py [out.json] [wizard|gate]   (REPO_DIR=… as for the other F13 browser tests)"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
MODE = sys.argv[2] if len(sys.argv) > 2 else "wizard"      # wizard (F04-HOME harness) | gate (F05 harness): the two harness packages share the module name "harness"
if MODE == "wizard":
    sys.path.insert(0, str(HERE.parent / "f04home"))
    import harness as H  # noqa: E402
    import test_f04home as T  # noqa: E402
    from harness import f04  # noqa: E402
else:
    sys.path.insert(0, str(HERE.parent / "f05")); sys.path.insert(0, str(HERE.parent / "f07"))
    import harness as H  # noqa: E402

BETA_EN = "try{localStorage.setItem('pt-f13-beta','1');localStorage.setItem('pt:_device:lang','en')}catch(e){}"
BETA_HE = BETA_EN.replace("'en'", "'he'")
SKIP = re.compile(r"מחיק|הסר|יציאה|ניתוק|שליחה|שלח|וואטסאפ|ווטסאפ|Delete|Remove|Sign out|Google", re.I)
USER = re.compile(r"^(דנה|אור|יפן.*|יפן)$")


def stats(page):
    try:
        st = page.evaluate("()=>window.__ptF13?window.__ptF13.stats():null")
        return st["missingList"] if st else []
    except Exception:
        return []


def main(out):
    from playwright.sync_api import sync_playwright
    seen = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        server = (H.f05.F05Server() if MODE == "wizard" else H.F05Server()); env = H.Env(b, server)
        def grab(page, label):
            # the wizard helpers type into Hebrew labels, so the device runs in Hebrew and is flipped to English only for the look
            try: page.evaluate("()=>window.__ptF13&&window.__ptF13.setLang('en')"); page.wait_for_timeout(400)
            except Exception: pass
            for t in stats(page):
                if not USER.match(t): seen.setdefault(t, label)
            try: page.evaluate("()=>window.__ptF13&&window.__ptF13.setLang('he')"); page.wait_for_timeout(300)
            except Exception: pass
        if MODE == "wizard":
          # ---- wizard: token link -> code -> steps 1..3 -> done
          _, token = env.backend.add_invite(T.EMAIL, T.DRAFT, sent_days_ago=0, expires_in_days=7)
          dev = env.new_device("W", ua="desktop")
          dev.ctx.add_init_script(BETA_HE)
          pg = dev.page
          pg.goto(env.server.origin + H.APP + "?invite=1#invite=" + token, wait_until="domcontentloaded")
          H.wait_screen(pg, ["code", "step1"], 20); pg.wait_for_timeout(500); grab(pg, "wizard: code")
          H.type_code(pg, env.backend.otp_code)
          H.wait_screen(pg, "step1", 15); pg.wait_for_timeout(500); grab(pg, "wizard: step1")
          f04.fill_step1(pg, me="דנה", start="2027-04-03", end="2027-04-20"); f04.press_next(pg)
          H.wait_screen(pg, "step2"); pg.wait_for_timeout(500); grab(pg, "wizard: step2")
          f04.pick(pg, "יפ", "JP"); f04.press_next(pg)
          H.wait_screen(pg, "step3"); pg.wait_for_timeout(500); grab(pg, "wizard: step3")
          try:
              f04.create_and_done(dev)
          except Exception as e:
              seen.setdefault("(create_and_done raised: %s)" % str(e)[:60], "wizard: done")
          pg.wait_for_timeout(800); grab(pg, "wizard: done")
        else:
          # ---- gate: a device with no trip; open the sub-screens one level deep
          env2 = H.Env(b, server)
          g = env2.new_device("G")
          g.ctx.add_init_script(BETA_EN)
          gp = g.page
          gp.goto(env2.server.origin + H.APP, wait_until="domcontentloaded")
          try: gp.wait_for_selector("#ptF05Transfer", state="visible", timeout=15000)
          except Exception: seen.setdefault("(gate screen #ptF05Transfer NOT reached: %s)" % gp.inner_text("body")[:60].replace("\n", " "), "gate")
          gp.wait_for_timeout(500); grab(gp, "gate")
          texts = gp.evaluate("""()=>[...document.querySelectorAll('button,a,[role=button],.listitem')].filter(e=>{const r=e.getBoundingClientRect();return r.width>4&&r.height>4}).map(e=>(e.innerText||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ')).filter((t,i,a)=>t&&t.length<60&&a.indexOf(t)===i)""")
          for t in texts:
              if SKIP.search(t): continue
              try:
                  gp.goto(env2.server.origin + H.APP, wait_until="domcontentloaded")
                  gp.wait_for_selector("#ptF05Transfer", state="visible", timeout=8000); gp.wait_for_timeout(300)
                  gp.locator("button,a,[role=button],.listitem").filter(has_text=t).first.click(timeout=800, no_wait_after=True)
                  gp.wait_for_timeout(500); grab(gp, "gate › " + t[:30])
              except Exception:
                  continue
        Path(out).write_text(json.dumps({"count": len(seen), "missing": seen}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(len(seen), "missing texts →", out)
        env.close(); server.stop(); b.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/f13_%s.json" % MODE)
