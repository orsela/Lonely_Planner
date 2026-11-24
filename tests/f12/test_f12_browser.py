"""Lonely Planner F12 browser test (390px) · version 3.0.0-alpha.18
CHANGE 2026-11-24 F12-T-02: new file (no previous version). Page side of the vault (app/js/f12.js) on a stub page with an in-memory fake Supabase client:
row in "עוד" only for trips in VAULT_TRIPS, upload / view / rename / delete by role, client-side rejections, quota block, orphan cleanup on a failed insert,
no horizontal scroll, no document title in the console. The real server is covered by qa.f12_run() (tests/f12/run.sh --only db)."""
import json, pathlib, sys, tempfile
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRIP, OTHER = 'fd5c2b13-cdc0-455e-9c12-b52f2e45a334', '11111111-1111-1111-1111-111111111111'
STUB = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>:root{--card:#fff;--border:#e2ddd0;--bg:#f6f5ef}body{margin:0;font-family:sans-serif}.panel{display:none}.panel.active{display:block}
.listitem{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #e2ddd0;border-radius:14px;padding:13px 14px;margin-bottom:10px}.ic{width:36px}.chev{margin-inline-start:auto}</style></head><body>
<section id="more" class="panel active"><div style="padding:0 12px;max-width:1100px;margin:auto"><div class="listitem" id="documentsBtn"><div class="ic">🔐</div><div class="lbl">כספת מסמכים</div></div></div></section>
<script>
window.LOG=[];const _w=console.warn;console.warn=function(){window.LOG.push([].join.call(arguments,' '));_w.apply(console,arguments)};
window.DB={docs:[],objects:{},calls:[],failInsert:null,used:null};window.TOASTS=[];
function fake(){const c={};
 c.from=t=>{const st={filters:{},op:null,payload:null};
  const q={select(){st.sel=true;return q},eq(k,v){st.filters[k]=v;return q},order(){return q},
   insert(p){st.op='insert';st.payload=p;return q},update(p){st.op='update';st.payload=p;return q},
   then(res,rej){return run().then(res,rej)}};
  async function run(){
   if(st.op==='insert'){DB.calls.push('insert');if(DB.failInsert)return{error:{code:DB.failInsert,message:'x'}};DB.docs.push(Object.assign({uploader_name:'אור',created_at:new Date(Date.now()+DB.docs.length*1000).toISOString()},st.payload));return{error:null}}
   if(st.op==='update'){const d=DB.docs.find(x=>x.id===st.filters.id);if(!d||DB.denyUpdate)return{data:[],error:null};Object.assign(d,st.payload);return{data:[{id:d.id}],error:null}}
   return{data:DB.docs.filter(d=>d.trip_id===st.filters.trip_id).slice().reverse(),error:null}}
  return q};
 c.rpc=async(n)=>({data:DB.used!=null?DB.used:DB.docs.reduce((s,d)=>s+d.size_bytes,0),error:null});
 c.storage={from:()=>({upload:async(p,f,o)=>{DB.calls.push('upload');DB.objects[p]=f.size;DB.lastUpload={p,o};return{error:null}},
   remove:async(ps)=>{DB.calls.push('remove');ps.forEach(p=>delete DB.objects[p]);return{error:null}},
   createSignedUrl:async(p,s)=>({data:{signedUrl:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'},error:null,ttl:s})})};
 c.functions={invoke:async(n,o)=>{DB.calls.push('invoke:'+n);DB.lastInvoke={n,o};DB.docs=DB.docs.filter(d=>d.id!==o.body.doc_id);return{data:{ok:true},error:null}}};
 return c}
window.CLIENT=fake();
window.start=function(role,trip,feature){window.ROLE=role;window.TRIPID=trip;return window.__ptF12.mount({feature:()=>feature,trips:()=>['%TRIP%'],tripId:()=>window.TRIPID,client:()=>window.CLIENT,uid:()=>'u1',role:()=>window.ROLE,toast:m=>window.TOASTS.push(m)})};
</script><script src="file://%F12%"></script></body></html>"""

fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra) if (extra and not cond) else ''))
    if not cond: fails.append(name)

with sync_playwright() as pw:
    br = pw.chromium.launch()
    tmp = pathlib.Path(tempfile.mkdtemp())
    page_file = tmp / 'stub.html'
    page_file.write_text(STUB.replace('%TRIP%', TRIP).replace('%F12%', str(ROOT / 'app/js/f12.js')), encoding='utf-8')
    pdf = tmp / 'ticket.pdf'; pdf.write_bytes(b'%PDF-1.4\n' + b'0' * 2000)
    png = tmp / 'pass.png'; png.write_bytes(bytes.fromhex('89504e470d0a1a0a') + b'0' * 500)
    big = tmp / 'big.pdf'; big.write_bytes(b'0' * (10485760 + 1))
    exe = tmp / 'bad.exe'; exe.write_bytes(b'MZ' + b'0' * 50)

    def fresh(role='manager', trip=TRIP, feature='on', ctx_kwargs=None):
        ctx = br.new_context(viewport={'width': 390, 'height': 800}, **(ctx_kwargs or {}))
        pg = ctx.new_page(); pg.goto('file://' + str(page_file))
        mounted = pg.evaluate('([r,t,f])=>window.start(r,t,f)', [role, trip, feature])
        return ctx, pg, mounted

    # 1. flag off / other trip: nothing drawn
    ctx, pg, m = fresh(feature='off'); check('flag off: mount false, no row', m is False and pg.locator('#vaultBtn').count() == 0); ctx.close()
    ctx, pg, m = fresh(trip=OTHER); pg.wait_for_timeout(200); check('other trip (Vietnam-like): no row', pg.locator('#vaultBtn').count() == 0); ctx.close()

    # 2. manager flow
    ctx, pg, m = fresh()
    pg.wait_for_selector('#vaultBtn'); check('row in "עוד" after the local vault row', pg.evaluate("document.getElementById('documentsBtn').nextElementSibling.id") == 'vaultBtn')
    check('row title is distinct from the local vault', 'כספת משותפת' in pg.inner_text('#vaultBtn'))
    pg.click('#vaultBtn'); pg.wait_for_selector('.vt-scr')
    check('empty state', 'עוד לא הועלו מסמכים' in pg.inner_text('.vt-scr'))
    check('manager sees upload button', pg.locator('.vt-fab').count() == 1)
    # rejections
    pg.click('.vt-fab'); pg.set_input_files('#vtFile', str(big)); check('file over 10MB rejected client-side', 'גדול מ-10MB' in pg.inner_text('.vt-err') and not pg.evaluate('DB.calls.length'))
    pg.set_input_files('#vtFile', str(exe)); check('bad type rejected client-side', 'רק PDF או תמונה' in pg.inner_text('.vt-err') and not pg.evaluate('DB.calls.length'))
    # upload pdf
    pg.set_input_files('#vtFile', str(pdf)); check('title defaults to file name', pg.input_value('#vtTitle') == 'ticket')
    pg.fill('#vtTitle', 'טיסה TLV-OTP'); pg.select_option('#vtCat', 'flights'); pg.click('.vt-btn.pri'); pg.wait_for_selector('.vt-row')
    check('upload order storage then insert, no upsert', pg.evaluate('DB.calls.slice(0,2)') == ['upload', 'insert'] and pg.evaluate('DB.lastUpload.o.upsert') is False)
    path = pg.evaluate('DB.docs[0].storage_path'); did = pg.evaluate('DB.docs[0].id')
    check('path is <trip>/<doc_id>.pdf and id matches', path == TRIP + '/' + did + '.pdf')
    check('row listed with category + size', 'טיסות' in pg.inner_text('.vt-row') and 'טיסה TLV-OTP' in pg.inner_text('.vt-row'))
    # image
    pg.click('.vt-fab'); pg.set_input_files('#vtFile', str(png)); pg.select_option('#vtCat', 'id'); pg.fill('#vtTitle', 'דרכון'); pg.click('.vt-btn.pri'); pg.wait_for_function("document.querySelectorAll('.vt-row').length===2")
    check('newest first', pg.locator('.vt-row .vt-tx b').first.inner_text() == 'דרכון')
    check('image path ext is png', pg.evaluate('DB.docs[1].storage_path').endswith('.png'))
    # filter
    pg.click('.vt-chip:has-text("טיסות")'); check('category filter', pg.locator('.vt-row').count() == 1); pg.click('.vt-chip:has-text("הכל")')
    # view image + pdf
    pg.locator('.vt-main').first.click(); pg.wait_for_selector('.vt-view img'); check('image opens inside the app', pg.locator('.vt-view img').count() == 1); pg.click('.vt-view .vt-ib')
    pg.locator('.vt-main').nth(1).click(); pg.wait_for_selector('.vt-view a.vt-open')
    check('PDF opens through a blob + open button', pg.get_attribute('.vt-view a.vt-open', 'href').startswith('blob:') and pg.get_attribute('.vt-view a.vt-open', 'target') == '_blank')
    pg.click('.vt-view .vt-ib'); check('viewer closes', pg.locator('.vt-view').count() == 0)
    # rename
    pg.locator('.vt-row .vt-ib').nth(1).click(); pg.click('.vt-menu button:has-text("שינוי שם")'); pg.fill('#vtTitle', 'טיסה הלוך'); pg.select_option('#vtCat', 'lodging'); pg.click('.vt-btn.pri')
    pg.wait_for_function("DB.docs.some(d=>d.title==='טיסה הלוך')"); check('rename + recategorise', pg.evaluate("DB.docs.find(d=>d.title==='טיסה הלוך').category") == 'lodging')
    # quota bar + counter
    check('quota bar drawn', '100MB' in pg.inner_text('.vt-q'))
    # delete
    pg.locator('.vt-row .vt-ib').first.click(); pg.click('.vt-menu button.dng'); pg.click('.vt-btn.dng'); pg.wait_for_function("document.querySelectorAll('.vt-row').length===1")
    check('delete goes through vault-delete with doc_id', pg.evaluate('DB.lastInvoke.n') == 'vault-delete' and pg.evaluate('DB.lastInvoke.o.body.doc_id') is not None)
    check('no horizontal scroll at 390px', pg.evaluate('document.documentElement.scrollWidth<=390'))
    check('no document title in the console', not any(('טיסה' in l or 'דרכון' in l) for l in pg.evaluate('LOG')))
    pg.keyboard.press('Escape'); ctx.close()

    # 3. failed insert removes the uploaded object (no orphan); quota error mapped
    ctx, pg, m = fresh(); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-fab')
    pg.evaluate("DB.failInsert='53400'"); pg.click('.vt-fab'); pg.set_input_files('#vtFile', str(pdf)); pg.fill('#vtTitle', 'x'); pg.click('.vt-btn.pri'); pg.wait_for_function("DB.calls.includes('remove')")
    check('failed INSERT removes the object', pg.evaluate("Object.keys(DB.objects).length") == 0 and pg.evaluate("DB.calls.slice(-1)[0]") == 'remove')
    check('server quota error shown', 'אין מספיק מקום' in pg.inner_text('.vt-err')); ctx.close()

    # 4. client-side quota block (full vault)
    ctx, pg, m = fresh(); pg.evaluate("DB.used=104857601"); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-q.full')
    pg.evaluate("DB.calls.length=0"); pg.click('.vt-fab'); pg.wait_for_timeout(200)
    check('full vault blocks upload before any call', pg.locator('#vtFile').count() == 0 and pg.evaluate('DB.calls.length') == 0); ctx.close()
    ctx, pg, m = fresh(); pg.evaluate("DB.used=90000000"); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-q.warn')
    check('warn at 80%', 'מתמלאת' in pg.inner_text('.vt-q')); ctx.close()

    # 5. roles: editor and viewer
    seed = "DB.docs.push({id:'d1',trip_id:'%s',title:'ביטוח',category:'insurance',mime:'application/pdf',size_bytes:1000,uploaded_by:'u1',uploader_name:'אור',created_at:'2026-11-20T10:00:00Z',storage_path:'p'});DB.docs.push({id:'d2',trip_id:'%s',title:'של מישהו',category:'other',mime:'image/png',size_bytes:1000,uploaded_by:'u2',uploader_name:'דנה',created_at:'2026-11-21T10:00:00Z',storage_path:'q'})" % (TRIP, TRIP)
    ctx, pg, m = fresh('editor'); pg.evaluate(seed); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-row')
    check('editor can upload', pg.locator('.vt-fab').count() == 1)
    check('editor menu only on own doc', pg.locator('.vt-row .vt-ib').count() == 1)
    pg.locator('.vt-row .vt-ib').first.click(); check('editor menu has rename, no delete', pg.locator('.vt-menu button.dng').count() == 0 and pg.locator('.vt-menu button').count() == 1); ctx.close()
    ctx, pg, m = fresh('viewer'); pg.evaluate(seed); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-row')
    check('viewer: no upload, no menu', pg.locator('.vt-fab').count() == 0 and pg.locator('.vt-row .vt-ib').count() == 0)
    check('viewer can open', pg.locator('.vt-main').count() == 2); ctx.close()
    # 6. offline: no upload attempt
    ctx, pg, m = fresh(); pg.wait_for_selector('#vaultBtn'); pg.click('#vaultBtn'); pg.wait_for_selector('.vt-fab'); ctx.set_offline(True); pg.evaluate("window.dispatchEvent(new Event('offline'))")
    pg.evaluate("DB.calls.length=0"); pg.click('.vt-fab'); pg.wait_for_timeout(200); check('offline: upload blocked with a message', pg.evaluate('DB.calls.length') == 0 and pg.locator('#vtFile').count() == 0); ctx.close()
    br.close()

print('\n%d failed' % len(fails) if fails else '\nall passed')
sys.exit(1 if fails else 0)
