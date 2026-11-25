"""Lonely Planner · Vietnam parity test (replaces the byte-identical check for drawMap / drawSchematicMap / bookingUrl) · version 1.0.0
CHANGE 2026-11-25 VNPAR-01: new file (no previous version). TRIP-COUNTRY-A (bookingUrl), TRIP-COUNTRY (drawSchematicMap neutral grid) and
OFFMAP-VIEW (drawMap hook) changed these three protected functions on purpose, each behind a flag with a CHANGE comment. What must stay true is
the behaviour for the Vietnam trip (id f0200000-0000-4000-8000-000000000001): the real current app and the baseline app e711542 (== v2.15.2 for
these functions) must produce the same route/day schematic map HTML on every day and the same booking link for every stay, with the production
flags. Real app + fake backend (F10 harness), no network. Run: tests/vnparity/run.sh"""
import os, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault('REPO_DIR', str(REPO)); os.environ.setdefault('APP_DIR', str(REPO / 'app'))
sys.path.insert(0, str(REPO / 'tests' / 'f10b'))
import harness as H
from playwright.sync_api import sync_playwright
h10 = H.h10
VN = 'f0200000-0000-4000-8000-000000000001'
BASE_REF = os.environ.get('V2152_REF', 'e711542')
JS = """()=>{const out={maps:[],book:[]};const gi=globalDayIndex,mp=mapProvider,mm=mapMode;
 for(let i=0;i<tripData.length;i++){for(const mode of ['route','day']){globalDayIndex=i;mapProvider='schematic';mapMode=mode;
  try{drawMap();const m=document.getElementById('map');out.maps.push(i+mode+':'+(m?m.innerHTML:''))}catch(e){out.maps.push(i+mode+':ERR '+e.message)}}
  try{out.book.push(i+':'+bookingUrl(i))}catch(e){out.book.push(i+':ERR '+e.message)}}
 globalDayIndex=gi;mapProvider=mp;mapMode=mm;out.n=tripData.length;return out}"""
fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else ' ' + str(extra)))
    if not cond: fails.append(name)

def run(br, base_html):
    srv = H.f05.F05Server(); env = H.Env(br, srv)
    try:
        be = env.backend; orig = be.add_trip
        be.add_trip = lambda name='QA trip', tid=None, _o=orig: _o(name, tid=VN)
        tid = be.fixture('V', role='manager'); assert tid == VN, tid
        if base_html is not None:
            env.server.overrides[h10.APP + 'index.html'] = base_html; env.server.overrides[h10.APP] = base_html
        dev = h10.boot(env, tid, role='manager'); pg = dev.page; errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        res = pg.evaluate(JS); res['errs'] = errs; dev.page.close(); return res
    finally:
        env.close(); srv.stop()

base = subprocess.run(['git', '-C', str(REPO), 'show', BASE_REF + ':app/index.html'], capture_output=True).stdout
assert base, 'baseline app not found: ' + BASE_REF
if os.environ.get('VNPAR_SELFTEST'):   # negative control: a deliberately different baseline must make the test fail
    base = base.replace(b"group_adults:'2'", b"group_adults:'9'", 1); assert b"group_adults:'9'" in base
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True)
    cur = run(br, None); old = run(br, base)
    check('both apps loaded the Vietnam trip with its days', cur['n'] == old['n'] and cur['n'] >= 20, (cur['n'], old['n']))
    check('no page errors (current app)', not cur['errs'], cur['errs'][:2])
    bad = [i for i, (a, b) in enumerate(zip(cur['maps'], old['maps'])) if a != b]
    check('schematic route/day map HTML identical on every day (%d renders)' % len(cur['maps']), len(cur['maps']) == len(old['maps']) and not bad, bad[:3])
    check('schematic map is really drawn (svg present)', all('<svg' in m for m in cur['maps'][:4]))
    badb = [i for i, (a, b) in enumerate(zip(cur['book'], old['book'])) if a != b]
    check('booking links identical for every day (%d)' % len(cur['book']), len(cur['book']) == len(old['book']) and not badb, badb[:3])
    check('some booking links exist (not all empty)', any(b.split(':', 1)[1] for b in cur['book']))
    br.close()
print('\nVietnam parity: %s' % ('all passed' if not fails else 'FAILED: ' + '; '.join(fails)))
sys.exit(1 if fails else 0)
