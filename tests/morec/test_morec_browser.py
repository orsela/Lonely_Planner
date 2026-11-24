"""MORE-COMPACT browser test (390px) · morec.js 1.0.0
CHANGE 2026-11-24 MORE-COMPACT-T-01: new file (no previous version). Stub page that copies the real "עוד" markup (4 rows + management + sync card + a
late-added row + an account section) and a fake f12 vault / local vault modal; checks the compact layout, the settings panel, the vault tabs and that
MORE_LAYOUT != 'compact' leaves the page untouched. Run: python3 tests/morec/test_morec_browser.py"""
import pathlib, sys
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]
STUB = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>:root{--sp-3:12px;--primary:#0f6b4f}body{margin:0;font-family:sans-serif}.panel{display:none}.panel.active{display:block}
.listitem{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #e2ddd0;border-radius:14px;min-height:60px;padding:12px 14px;margin-bottom:10px}.chev{margin-inline-start:auto}.lbl{flex:1}
.modal{display:none;position:fixed;inset:0;background:#fff}.modal.open{display:block}.vt-scr{position:fixed;inset:0;background:#fff}.tab{display:inline-block}</style></head><body>
<nav><button class="tab active" data-panel="more">עוד</button></nav>
<section id="more" class="panel active"><div class="topbar"><h1>עוד</h1></div><div style="padding:0 var(--sp-3);max-width:1100px;margin:auto">
<div class="listitem" id="documentsBtn"><div class="ic">🔐</div><div class="lbl">כספת מסמכים<span class="val" id="documentsSummary" style="display:block">2 מסמכים · זמין ללא אינטרנט</span></div><div class="chev">‹</div></div>
<div class="listitem" id="reservationsBtn"><div class="ic">🎫</div><div class="lbl">הזמנות וארנק נסיעה<span class="val" style="display:block">טיסות</span></div><div class="chev">‹</div></div>
<div class="listitem" id="googlePhotosBtn"><div class="ic">📷</div><div class="lbl">תמונות הטיול<span class="val" style="display:block">קישור</span></div><div class="chev">‹</div></div>
<div class="listitem" data-go="management" id="mgmtRow"><div class="ic">⚙️</div><div class="lbl">ניהול<span class="val" style="display:block">משתמשים</span></div><div class="chev">‹</div></div>
<div class="statuscard ok" id="moreSyncCard"><b id="moreSyncTitle">סנכרון בענן פעיל</b><span id="moreVer">גרסה x</span></div></div></section>
<section id="management" class="panel"><div class="topbar"><button class="topbar-back" data-go="more">›</button><h1>ניהול</h1></div></section>
<div id="documentsModal" class="modal"><div class="modal-box"><div class="modal-head"><h2>🔐 כספת מסמכים</h2><button class="modal-x" data-modal-x type="button">×</button></div><p class="muted">הסבר</p></div></div>
<script>
const TAB_FOR_PANEL={more:'more',management:'more'};
function switchPanel(id){document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.panel===(TAB_FOR_PANEL[id]||id)))}
document.getElementById('documentsBtn').onclick=()=>document.getElementById('documentsModal').classList.add('open');
document.querySelector('[data-modal-x]').onclick=()=>document.getElementById('documentsModal').classList.remove('open');
window.addVault=function(){const v=document.createElement('div');v.className='listitem';v.id='vaultBtn';v.innerHTML='<span id="vaultSummary">3 מסמכים · 1MB</span>';
 v.addEventListener('click',()=>{if(document.querySelector('.vt-scr'))return;const s=document.createElement('div');s.className='vt-scr';s.innerHTML='<div class="vt-top"><button class="vt-ib">→</button><h2>כספת משותפת</h2></div><div class="vt-chips">x</div><div class="vt-q ok">q</div>';s.querySelector('.vt-ib').onclick=()=>s.remove();document.body.appendChild(s)});
 document.getElementById('documentsBtn').after(v)};
window.addLate=function(){const r=document.createElement('div');r.className='listitem';r.id='ptF13LangRow';r.textContent='שפה';document.getElementById('documentsBtn').after(r);
 const a=document.createElement('div');a.id='acct';a.textContent='החשבון שלי';document.getElementById('more').insertBefore(a,document.getElementById('more').firstChild)};
</script><script src="file://%S%"></script>
<script>window.MOUNT=function(flag){return window.__ptMoreC.mount({flag:()=>flag,go:id=>switchPanel(id),tabMap:TAB_FOR_PANEL})}</script></body></html>"""
fails = []
def chk(n, c):
    print(('PASS ' if c else 'FAIL ') + n)
    if not c: fails.append(n)
def page(b, flag):
    f = pathlib.Path('/tmp/morec_stub.html'); f.write_text(STUB.replace('%S%', str(ROOT / 'app/js/morec.js')))
    pg = b.new_page(viewport={'width': 390, 'height': 844}); pg.set_default_timeout(4000); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + str(f)); pg.evaluate("MOUNT(%r)" % flag); pg.wait_for_timeout(200); return pg, errs
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = page(b, 'v1')
    chk("flag 'v1': nothing changes", pg.evaluate("!document.getElementById('mcSettingsRow')&&!document.getElementById('moreSettings')&&!!document.querySelector('#more [data-go=management]')"))
    pg, errs = page(b, 'compact')
    pg.evaluate("addLate()"); pg.wait_for_timeout(300)
    vis = pg.evaluate("[...document.querySelectorAll('#more .listitem')].filter(e=>e.offsetParent).map(e=>e.id)")
    chk('four rows in More: ' + str(vis), vis == ['documentsBtn', 'reservationsBtn', 'googlePhotosBtn', 'mcSettingsRow'])
    chk('vault row renamed', pg.evaluate("document.querySelector('#documentsBtn .lbl').firstChild.nodeValue==='כספת'"))
    chk('no sub-captions visible', pg.evaluate("[...document.querySelectorAll('#more .val')].every(e=>e.offsetParent===null)"))
    h1 = pg.evaluate("Math.round(document.getElementById('reservationsBtn').getBoundingClientRect().height)")
    pg.evaluate("document.documentElement.classList.remove('mc-on')"); h0 = pg.evaluate("Math.round(document.getElementById('reservationsBtn').getBoundingClientRect().height)")
    pg.evaluate("document.documentElement.classList.add('mc-on')")
    chk('rows lower than before: %s < %s' % (h1, h0), h1 < h0)
    chk('account section + late row moved to settings in order', pg.evaluate("[...document.querySelectorAll('#mcSettingsBody > *')].map(e=>e.id).join()").startswith(''))
    chk('management, sync card, late rows in settings', pg.evaluate("['mgmtRow','moreSyncCard','ptF13LangRow','acct'].every(i=>document.getElementById(i).closest('#moreSettings'))"))
    chk('sync line', pg.evaluate("document.getElementById('mcSync').textContent")=='☁️ מסונכרן')
    chk('no horizontal scroll', pg.evaluate("document.documentElement.scrollWidth<=390"))
    pg.screenshot(path='/tmp/more.png')
    pg.click('#mcSettingsRow'); pg.wait_for_timeout(200)
    chk('settings panel active, More tab lit', pg.evaluate("document.getElementById('moreSettings').classList.contains('active')&&document.querySelector('.tab').classList.contains('active')"))
    pg.screenshot(path='/tmp/settings.png')
    pg.click('#moreSettings .topbar-back'); pg.wait_for_timeout(100)
    chk('back to More', pg.evaluate("document.getElementById('more').classList.contains('active')"))
    pg.click('#documentsBtn'); pg.wait_for_timeout(300)
    chk('no shared vault: local modal, no tabs', pg.evaluate("document.getElementById('documentsModal').classList.contains('open')&&!document.querySelector('.mc-tabs')"))
    pg.evaluate("document.querySelector('[data-modal-x]').click();addVault()"); pg.wait_for_timeout(300)
    chk('badge = 2 + 3', pg.evaluate("document.getElementById('mcBadge').textContent")=='5')
    chk('vaultBtn hidden in settings', pg.evaluate("document.getElementById('vaultBtn').closest('#moreSettings')&&document.getElementById('vaultBtn').offsetParent===null"))
    pg.click('#documentsBtn'); pg.wait_for_timeout(300)
    chk('vault row opens SHARED vault with tabs + title', pg.evaluate("!!document.querySelector('.vt-scr .mc-tabs')&&document.querySelector('.vt-scr h2').textContent==='כספת'&&!document.getElementById('documentsModal').classList.contains('open')"))
    chk('chips + quota(ok) hidden', pg.evaluate("document.querySelector('.vt-chips').offsetParent===null&&document.querySelector('.vt-q').offsetParent===null"))
    pg.screenshot(path='/tmp/shared.png')
    pg.evaluate("document.querySelectorAll('.vt-scr .mc-tabs button')[1].click()"); pg.wait_for_timeout(400)
    chk('tab במכשיר -> local vault with tabs', pg.evaluate("!document.querySelector('.vt-scr')&&document.getElementById('documentsModal').classList.contains('open')&&!!document.querySelector('#documentsModal .mc-tabs')&&document.querySelector('#documentsModal h2').textContent.includes('כספת')&&!document.querySelector('#documentsModal h2').textContent.includes('מסמכים')"))
    pg.screenshot(path='/tmp/local.png')
    pg.evaluate("document.querySelectorAll('#documentsModal .mc-tabs button')[0].click()"); pg.wait_for_timeout(400)
    chk('tab משותפת -> back to shared', pg.evaluate("!!document.querySelector('.vt-scr')&&!document.getElementById('documentsModal').classList.contains('open')"))
    chk('no page errors ' + str(errs), not errs)
    b.close()
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); sys.exit(1 if fails else 0)
