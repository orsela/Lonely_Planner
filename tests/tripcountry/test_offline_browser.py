"""Lonely Planner TC-BUG-01 browser test · 390px, offline start of a cloud trip that is not Vietnam · version 3.0.0-alpha.18.4
CHANGE 2026-11-24 TC-OFF-T-02: new file (no previous version). Real app + fake backend (F10b harness), no network. Five checks (5 = the route-screen schematic map):
1 opened online, then started offline -> the trip's own 10 days (no Vietnam), a copy is on the device; 2 never opened, started offline -> an empty trip with the notice,
never the Vietnam seed, no page error; 3 flag 'off' offline = alpha.18.3 (the Vietnam seed, the bug) - proves 'off' is unchanged; 4 no horizontal scroll at 390px.
Run: tests/tripcountry/run_browser.sh"""
import datetime as dt, json, os, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault('REPO_DIR', str(REPO)); os.environ.setdefault('APP_DIR', str(REPO / 'app'))
sys.path.insert(0, str(REPO / 'tests' / 'f10b'))
import harness as H
from playwright.sync_api import sync_playwright
h10, f04 = H.h10, H.f04 if hasattr(H, 'f04') else H.h10.f04
FLAG = re.compile(r"""((?:const|let|var)\s+TRIPOFFLINE_FEATURE\s*=\s*)(['"])(on|off)\2""")
MAPJS = "()=>{mapProvider='schematic';mapMode='route';drawMap();const m=document.getElementById('map');return m?m.innerHTML:''}"
VN_WORDS = ('האנוי', 'טיסה להאנוי')
fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else ' ' + str(extra)))
    if not cond: fails.append(name)
STATE = """()=>({n:tripData.length,first:tripData[0]&&tripData[0].region,title:tripData[0]&&tripData[0].title,
 ls:(()=>{try{return JSON.parse(localStorage.getItem('planner:trip')).length}catch(e){return null}})(),
 hscroll:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,body:document.body.innerText})"""

def make(env):
    be = env.backend; tid = be.fixture('E', role='manager'); cap = h10.COUNTRIES['GB']['capital']
    be.set_kv(tid, 'trip', json.dumps(f04.empty_days(dt.date(2027, 5, 26), 10, (cap['lat'], cap['lng']), 'GB'), ensure_ascii=False))
    return tid

def flip(env, value):
    src = h10.app_html()
    assert FLAG.search(src), 'TRIPOFFLINE_FEATURE not found'
    b = FLAG.sub(lambda m: m.group(1) + "'" + value + "'", src, count=1).encode('utf-8')
    env.server.overrides[h10.APP + 'index.html'] = b; env.server.overrides[h10.APP] = b

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True)
    for flag in ('on', 'off'):
        srv = H.f05.F05Server(); env = H.Env(br, srv); flip(env, flag)
        try:
            tid = make(env)
            dev = h10.boot(env, tid, role='manager'); pg = dev.page; errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            on = pg.evaluate(STATE)
            h10.go_offline(env, dev, True); st = h10.reboot(dev); off = pg.evaluate(STATE)
            if flag == 'on':
                check('1 online load = 10 days', on['n'] == 10, on['n'])
                check('1 offline start (opened before) = the trip\'s own 10 days, no Vietnam', st == 'app' and off['n'] == 10 and not any(w in off['body'] for w in VN_WORDS), (st, off['n']))
                check('1 a copy of the days is on the device', off['ls'] == 10, off['ls'])
                check('4 no horizontal scroll at 390px', not off['hscroll'])
                svg = pg.evaluate(MAPJS); check('5 route map offline: no Vietnam outline / river / Tonkin Gulf', '<svg' in svg and '<polygon' not in svg and 'טונקין' not in svg, svg[:120])
                # 2: a second device that never opened the trip online
                dev2 = h10.boot(env, tid, role='manager', name='B', offline_boot=True) if False else None
            else:
                check('3 flag off, offline = alpha.18.3 (the Vietnam seed)', off['n'] == 22 and off['first'] == 'טיסות', (off['n'], off['first']))
                svg = pg.evaluate(MAPJS); check('5 flag off: the route map still draws the Vietnam shapes (= alpha.18.3)', '<polygon' in svg and 'טונקין' in svg)
            dev.page.close()
        finally:
            env.close(); srv.stop()
    # 2: never opened on this device, offline from the first start
    srv = H.f05.F05Server(); env = H.Env(br, srv); flip(env, 'on')
    try:
        tid = make(env); h10.go_offline(env, None, True) if False else None
        dev = env.new_device('C'); dev.seed_ls({h10.CACHE_KEY: json.dumps({'trip_id': tid, 'role': 'manager'})})
        h10.go_offline(env, dev, True); errs = []; dev.page.on('pageerror', lambda e: errs.append(str(e)))
        st = h10.reboot(dev); r = dev.page.evaluate(STATE); dev.page.wait_for_timeout(2200)
        body = dev.page.evaluate('()=>document.body.innerText')
        check('2 never opened + offline: empty trip, not the Vietnam seed', st == 'app' and r['n'] == 0 and not any(w in body for w in VN_WORDS), (st, r['n']))
        check('2 notice shown', 'אין עותק של הטיול במכשיר' in body)
        check('2 no page error', not errs, errs[:2])
        check('4 no horizontal scroll at 390px (empty trip)', not r['hscroll'])
    finally:
        env.close(); srv.stop()
    # CHANGE 2026-11-25 TC-EMPTY-T-01: 6 = a cloud trip with no stored days, device ONLINE: no "no local copy" toast, journal save does not throw and says there are no days
    srv = H.f05.F05Server(); env = H.Env(br, srv); flip(env, 'on')
    try:
        tid = env.backend.fixture('E', role='manager'); env.backend.set_kv(tid, 'trip', '[]')  # a stored trip with 0 days
        dev = h10.boot(env, tid, role='manager'); errs = []; dev.page.on('pageerror', lambda e: errs.append(str(e)))
        dev.page.wait_for_timeout(2200)
        r = dev.page.evaluate(STATE)
        check('6 online + stored 0-day trip: 0 days, no Vietnam seed', r['n'] == 0 and not any(w in r['body'] for w in VN_WORDS), r['n'])
        check('6 online: the "no local copy" toast is NOT shown', 'אין עותק של הטיול במכשיר' not in r['body'])
        dev.page.evaluate("()=>{document.getElementById('journalText').value='בדיקה';document.getElementById('saveJournal').click()}")
        dev.page.wait_for_timeout(800)
        body = dev.page.evaluate('()=>document.body.innerText')
        check('6 journal save on a 0-day trip: no page error', not errs, errs[:2])
        check('6 journal save on a 0-day trip: says there are no days', 'אין עדיין ימים בטיול' in body)
    finally:
        env.close(); srv.stop()
    br.close()
print('all passed' if not fails else 'failed: %d' % len(fails)); sys.exit(1 if fails else 0)
